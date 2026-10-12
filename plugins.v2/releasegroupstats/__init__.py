"""Release group statistics: managed tasks, native pages and stable APIs."""
import json
from pathlib import Path
import threading
from apscheduler.triggers.cron import CronTrigger
from app.log import logger
from app.plugins import _PluginBase
from app.core.config import settings
from app.core.event import eventmanager, Event
from app.schemas.types import EventType
from . import scanner, ui
from .models import RankingView, ScanStatus, StatusResponse


class ReleaseGroupStats(_PluginBase):
    """Scan mounted media directories and aggregate release group distributions."""
    plugin_name = '发布组统计'
    plugin_desc = '扫描媒体目录，统计发布组文件数量与逻辑容量'
    plugin_icon = 'https://raw.githubusercontent.com/MrGlaucus/MoviePilot-Plugins/main/icons/Ptools_B.png'
    plugin_color = '#4F6BED'
    plugin_version = '1.1.1'
    plugin_author = 'MrGlaucus'
    author_url = 'https://github.com/MrGlaucus'
    plugin_config_prefix = 'releasegroupstats_'
    plugin_order = 10
    auth_level = 1
    STATS_FILE = 'stats_data.json'

    def __init__(self):
        """Keep task resources and mutable state local to each plugin instance."""
        super().__init__()
        self._lock = threading.RLock()
        self._lifecycle = threading.RLock()
        self._cancel = threading.Event()
        self._thread = None
        self._stopped = True
        self._enabled = False
        self._stats_data = {}
        self._state = 'idle'
        self._message = ''
        self._warnings = []
        self._checked = self._videos = self._errors = 0
        self._config = {}
        self._view = RankingView()
        self._trigger = None
        self._matcher = scanner.Matcher()

    def init_plugin(self, config=None):
        """Stop the old task before replacing configuration and loading a snapshot."""
        with self._lifecycle:
            self.stop_service()
            with self._lock:
                self._config = dict(config or {})
                self._enabled = bool(self._config.get('enabled', False))
                self._warnings = []
                self._trigger = None
                self._message = ''
                self._checked = self._videos = self._errors = 0
                if self._thread and self._thread.is_alive():
                    self._enabled = False
                    self._warnings = ['旧扫描仍在等待文件系统响应，请稍后重新保存配置']
                    return
                self._cancel = threading.Event()
                self._stopped = False
                self._state = 'idle'
                self._matcher = scanner.Matcher(self._config.get('custom_rules') or '')
                self._warnings.extend(self._matcher.errors)
                cron = (self._config.get('cron') or '').strip()
                if cron:
                    try:
                        self._trigger = CronTrigger.from_crontab(cron, timezone=settings.TZ)
                    except (ValueError, TypeError) as exc:
                        self._warnings.append(f'定时表达式无效：{exc}')
                self._load_stats()
                once = bool(self._config.get('onlyonce'))
                if once:
                    self._config['onlyonce'] = False
                    self.update_config(dict(self._config))
            if once:
                response = self._schedule_once()
                if not response.success:
                    with self._lock:
                        self._message = response.message

    def _schedule_once(self):
        """Start the explicitly requested one-shot task using the managed worker."""
        return self.start_scan()

    def _remove_once(self):
        """V2 has no pending host one-shot job to remove."""

    def _load_stats(self):
        """Restore legacy JSON; a corrupt snapshot cannot break plugin loading."""
        try:
            path = Path(self.get_data_path()) / self.STATS_FILE
            if not path.exists():
                return
            self._stats_data = scanner.validate_snapshot(json.loads(path.read_text(encoding='utf-8')))
        except (OSError, ValueError, TypeError) as exc:
            self._warnings.append('历史统计读取失败；请检查数据文件或重新扫描')
            logger.warning(f'发布组统计读取失败：{exc}')

    def get_state(self):
        """Expose the configured enable switch to the host."""
        return self._enabled

    def _status(self):
        """Build a consistent status object while the instance lock is held."""
        return ScanStatus(enabled=self._enabled and not self._stopped,
            running=bool(self._thread and self._thread.is_alive()), state=self._state,
            checked_files=self._checked, video_files=self._videos, error_count=self._errors,
            message=self._message, warnings=list(self._warnings),
            last_scan_time=self._stats_data.get('last_scan_time', ''))

    def _response(self, success=True, message=''):
        """Use the same declared envelope for all control endpoints."""
        with self._lock:
            if not success and message:
                self._message = message
            return StatusResponse(success=success, message=message, data=self._status())

    def get_status(self) -> StatusResponse:
        """Poll task status without changing or clearing its result."""
        return self._response()

    def set_ranking_view(self, payload: RankingView) -> StatusResponse:
        """Change transient table ordering and page without rescanning the library."""
        with self._lock:
            self._view = payload
            return self._response()

    def start_scan(self) -> StatusResponse:
        """Reserve the worker slot atomically before starting a background task."""
        with self._lock:
            if self._stopped or not self._enabled:
                return self._response(False, '请先启用插件')
            if self._thread and self._thread.is_alive():
                return self._response(False, '扫描正在进行中')
            roots = scanner.normalize_paths(self._config.get('scan_paths') or '')
            if not roots:
                return self._response(False, '请先配置媒体目录')
            self._cancel.clear()
            self._state, self._message = 'running', ''
            self._checked = self._videos = self._errors = 0
            allowed = scanner.extensions(self._config.get('custom_extensions') or '')
            self._thread = threading.Thread(target=self._run_scan, args=(roots, allowed, self._matcher),
                name=f'{self.__class__.__name__}-scan', daemon=True)
            try:
                self._thread.start()
            except RuntimeError:
                self._state = 'failed'
                self._message = '无法启动扫描任务，请稍后重试'
                return self._response(False, self._message)
            return self._response(True, '扫描已启动')

    def _progress(self, checked, videos, errors):
        """Publish bounded counters, without exposing the mutable snapshot."""
        with self._lock:
            self._checked, self._videos, self._errors = checked, videos, errors

    def _run_scan(self, roots, allowed, matcher):
        """Only publish a completed, durably saved and uncancelled snapshot."""
        try:
            result = scanner.scan(roots, allowed, matcher, self._cancel, self._progress)
            with self._lock:
                if self._cancel.is_set() or self._stopped:
                    raise scanner.ScanCancelled()
                scanner.save_snapshot(Path(self.get_data_path()) / self.STATS_FILE, result)
                self._stats_data = result
                self._state = 'partial' if result['partial'] else 'completed'
                self._message = f"扫描完成：{result['total_files']:,} 个视频文件，耗时 {result['scan_duration_seconds']} 秒"
            logger.info(self._message)
        except scanner.ScanCancelled:
            with self._lock:
                self._state = 'stopped' if self._stopped else 'cancelled'
                self._message = '扫描已取消，上次结果已保留'
        except Exception as exc:
            with self._lock:
                self._state = 'failed'
                self._message = '扫描或保存失败，上次结果已保留；请检查目录、权限及日志'
            logger.error(f'发布组统计扫描失败：{exc}', exc_info=True)

    def cancel_scan(self) -> StatusResponse:
        """Request cooperative cancellation; keep the slot until the worker exits."""
        with self._lock:
            if not self._thread or not self._thread.is_alive():
                return self._response(False, '当前没有正在执行的扫描')
            self._cancel.set()
            self._state = 'cancelling'
            return self._response(True, '已请求取消扫描')

    def stop_service(self):
        """Prevent new work, signal cancellation and wait briefly for the old task."""
        with self._lifecycle:
            with self._lock:
                self._stopped = True
                self._cancel.set()
                thread = self._thread
            self._remove_once()
            if thread and thread is not threading.current_thread() and thread.is_alive():
                thread.join(timeout=5)
            with self._lock:
                self._state = 'stopped'

    def get_service(self):
        """Register a validated cron trigger in the host scheduler."""
        if not self._enabled or not self._trigger or self._stopped:
            return []
        return [{'id': f'{self.__class__.__name__}.Scan', 'name': '发布组统计定时扫描',
                 'trigger': self._trigger, 'func': self.start_scan, 'kwargs': {}}]

    @staticmethod
    def get_command():
        """Preserve the existing remote command name."""
        return [{'cmd': '/release_group_scan', 'event': EventType.PluginAction,
                 'desc': '发布组统计扫描', 'category': '插件功能',
                 'data': {'action': 'release_group_scan'}}]

    @eventmanager.register(EventType.PluginAction)
    def remote_scan(self, event: Event):
        """Ignore unrelated actions and commands explicitly targeting another instance."""
        data = (event.event_data or {}) if event else {}
        if data.get('action') != 'release_group_scan':
            return
        if data.get('plugin_id') and data['plugin_id'] != self.__class__.__name__:
            return
        response = self.start_scan()
        logger.info(f'发布组统计命令：{response.message}')

    def get_api(self):
        """Register authenticated APIs with explicit Pydantic response schemas."""
        return [{'path': '/' + path, 'endpoint': endpoint, 'methods': [method], 'auth': 'bear',
                 'summary': title, 'response_model': StatusResponse}
                for path, endpoint, method, title in [
                    ('start_scan', self.start_scan, 'POST', '开始发布组扫描'),
                    ('cancel_scan', self.cancel_scan, 'POST', '取消发布组扫描'),
                    ('ranking_view', self.set_ranking_view, 'POST', '切换排名排序与页码'),
                    ('status', self.get_status, 'GET', '读取发布组扫描状态')]]

    def get_form(self):
        """Return settings and persisted validation warnings."""
        with self._lock:
            return ui.form(list(self._warnings))

    def get_page(self):
        """Render the last successful snapshot alongside current task state."""
        with self._lock:
            return ui.page(self._stats_data, self._status(), self.__class__.__name__,
                           self._config.get('ranking_filter') or '', {'sort': self._view.sort, 'descending': self._view.descending, 'page': self._view.page})

    def get_dashboard_meta(self):
        """Keep the existing widget identity compatible with saved dashboards."""
        return [{'key': 'stats', 'name': '发布组统计'}]

    def get_dashboard(self, key='stats', **kwargs):
        """Provide an empty widget before the first successful scan."""
        if key not in ('stats', None, ''):
            return None
        with self._lock:
            return ui.dashboard(self._stats_data, self._status())
