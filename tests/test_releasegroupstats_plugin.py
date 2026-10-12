"""Host-boundary tests use explicit MoviePilot substitutes, not a real host."""
import importlib.util
import json
import logging
from pathlib import Path
import sys
import tempfile
import threading
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / '.cache/test-deps'))
(ROOT / '.cache/tests').mkdir(parents=True, exist_ok=True)
tempfile.tempdir = str(ROOT / '.cache/tests')


def load_plugin(version):
    """Import each generation through its production package namespace."""
    for name in list(sys.modules):
        if name == 'app' or name.startswith('app.'):
            del sys.modules[name]
    for name in ['app', 'app.plugins', 'app.core', 'app.core.config', 'app.core.event',
                 'app.log', 'app.schemas', 'app.schemas.types', 'app.sdk',
                 'app.sdk.plugin', 'app.sdk.config', 'app.sdk.events', 'app.sdk.logging']:
        mod = types.ModuleType(name)
        mod.__path__ = []
        sys.modules[name] = mod

    class Base:
        def get_data_path(self):
            return self.data_path

        def update_config(self, config):
            self.saved_config = config

    class Events:
        def register(self, event):
            def decorate(func):
                func.registered_event = event
                return func
            return decorate

    settings = types.SimpleNamespace(TZ='Asia/Shanghai')
    for name in ['app.plugins', 'app.sdk.plugin']:
        sys.modules[name]._PluginBase = Base
    for name in ['app.core.config', 'app.sdk.config']:
        sys.modules[name].settings = settings
    for name in ['app.core.event', 'app.sdk.events']:
        sys.modules[name].eventmanager = Events()
        sys.modules[name].Event = types.SimpleNamespace
    for name in ['app.log', 'app.sdk.logging']:
        logger = logging.getLogger('test')
        if not logger.handlers:
            logger.addHandler(logging.NullHandler())
        logger.propagate = False
        sys.modules[name].logger = logger
    sys.modules['app.schemas.types'].EventType = types.SimpleNamespace(PluginAction='plugin.action')
    location = ROOT / f'plugins.{version}/releasegroupstats/__init__.py'
    spec = importlib.util.spec_from_file_location('app.plugins.releasegroupstats', location,
                                                  submodule_search_locations=[str(location.parent)])
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class PluginTests(unittest.TestCase):
    """Run common lifecycle and UI contracts for both generations."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()

    def plugin(self, version='v2', **config):
        module = load_plugin(version)
        plugin = module.ReleaseGroupStats()
        plugin.data_path = Path(self.tmp.name) / 'data'
        plugin.init_plugin({'enabled': True, 'scan_paths': self.tmp.name, **config})
        self.addCleanup(plugin.stop_service)
        return module, plugin

    def test_both_generations_scan_and_persist(self):
        for version in ['v2', 'v3']:
            with self.subTest(version=version):
                _, plugin = self.plugin(version)
                (Path(self.tmp.name) / 'Film-FRDS.mkv').write_bytes(b'abc')
                self.assertTrue(plugin.start_scan().success)
                plugin._thread.join(3)
                self.assertEqual(plugin.get_status().data.state, 'completed')
                self.assertEqual(plugin._stats_data['total_files'], 1)
                self.assertEqual(json.loads((plugin.data_path / 'stats_data.json').read_text(encoding='utf-8'))['total_files'], 1)

    def test_concurrent_start_is_rejected_and_stop_cancels(self):
        module, plugin = self.plugin()
        entered = threading.Event()

        def blocked(*args, **kwargs):
            entered.set()
            args[3].wait(3)
            raise module.scanner.ScanCancelled()

        with patch.object(module.scanner, 'scan', side_effect=blocked):
            self.assertTrue(plugin.start_scan().success)
            self.assertTrue(entered.wait(1))
            self.assertFalse(plugin.start_scan().success)
            plugin.stop_service()
            self.assertFalse(plugin._thread.is_alive())
            self.assertFalse(plugin.start_scan().success)
            self.assertFalse(plugin._stats_data)

    def test_failure_and_cancellation_preserve_last_snapshot(self):
        module, plugin = self.plugin()
        plugin._stats_data = {'total_files': 9, 'groups': {}}
        for failure in [ValueError('unreadable'), module.scanner.ScanCancelled()]:
            with patch.object(module.scanner, 'scan', side_effect=failure):
                plugin.start_scan()
                plugin._thread.join(2)
                self.assertEqual(plugin._stats_data['total_files'], 9)

    def test_invalid_cron_and_rule_do_not_crash_load(self):
        _, plugin = self.plugin(cron='invalid', custom_rules='broken|[')
        self.assertEqual(plugin.get_service(), [])
        self.assertGreaterEqual(len(plugin.get_status().data.warnings), 2)

    def test_valid_cron_uses_real_trigger_and_timezone(self):
        from apscheduler.triggers.cron import CronTrigger
        _, plugin = self.plugin(cron='0 2 * * *')
        service = plugin.get_service()[0]
        self.assertIsInstance(service['trigger'], CronTrigger)
        self.assertEqual(str(service['trigger'].timezone), 'Asia/Shanghai')

    def test_once_switch_resets_and_disabled_state_rejects_scan(self):
        _, plugin = self.plugin(enabled=False, onlyonce=True)
        self.assertFalse(plugin.saved_config['onlyonce'])
        self.assertFalse(plugin.start_scan().success)

    def test_reload_clears_previous_config(self):
        _, plugin = self.plugin(cron='0 2 * * *')
        plugin.init_plugin(None)
        self.assertFalse(plugin.get_state())
        self.assertEqual(plugin.get_service(), [])

    def test_rejected_manual_scan_is_visible_after_page_reload(self):
        _, plugin = self.plugin(scan_paths='')
        result = plugin.start_scan()
        self.assertFalse(result.success)
        self.assertIn(result.message, json.dumps(plugin.get_page(), ensure_ascii=False))

    def test_save_failure_does_not_replace_memory_snapshot(self):
        module, plugin = self.plugin()
        plugin._stats_data = {'total_files': 7, 'groups': {}}
        with patch.object(module.scanner, 'save_snapshot', side_effect=OSError('full')):
            plugin.start_scan()
            plugin._thread.join(2)
        self.assertEqual(plugin.get_status().data.state, 'failed')
        self.assertEqual(plugin._stats_data['total_files'], 7)

    def test_stale_result_is_discarded_after_cancel(self):
        module, plugin = self.plugin()
        entered, release = threading.Event(), threading.Event()
        def ignores_cancel(*args, **kwargs):
            entered.set()
            release.wait(2)
            return {'total_files': 999, 'groups': {}, 'partial': False, 'scan_duration_seconds': 0}
        with patch.object(module.scanner, 'scan', side_effect=ignores_cancel):
            plugin.start_scan()
            self.assertTrue(entered.wait(1))
            plugin.cancel_scan()
            release.set()
            plugin._thread.join(2)
        self.assertFalse(plugin._stats_data)
        self.assertEqual(plugin.get_status().data.state, 'cancelled')

    def test_v3_once_uses_and_removes_instance_job(self):
        module, plugin = self.plugin('v3')
        jobs = []
        scheduler = types.SimpleNamespace(
            add_plugin_once_job=lambda *args, **kwargs: jobs.append(('add', args, kwargs)) or True,
            remove_plugin_once_job=lambda *args: jobs.append(('remove', args)))
        with patch.object(module, 'scheduler_sdk', scheduler):
            plugin.init_plugin({'enabled': True, 'scan_paths': self.tmp.name, 'onlyonce': True})
            self.assertEqual(jobs[-1][0], 'add')
            self.assertEqual(jobs[-1][1][0], 'ReleaseGroupStats')
            self.assertFalse(plugin.saved_config['onlyonce'])
            plugin.stop_service()
            self.assertEqual(jobs[-1], ('remove', ('ReleaseGroupStats', 'scan_once')))

    def test_unwritable_data_directory_does_not_break_plugin_load(self):
        _, plugin = self.plugin()
        with patch.object(plugin, 'get_data_path', side_effect=PermissionError('denied')):
            plugin.init_plugin({'enabled': True, 'scan_paths': self.tmp.name})
        self.assertTrue(plugin.get_status().data.warnings)

    def test_reload_refuses_new_work_until_old_worker_exits(self):
        module, plugin = self.plugin()
        entered, release = threading.Event(), threading.Event()
        def blocked(*args, **kwargs):
            entered.set()
            release.wait(3)
            return {'total_files': 999, 'groups': {}, 'partial': False, 'scan_duration_seconds': 0}
        with patch.object(module.scanner, 'scan', side_effect=blocked):
            plugin.start_scan()
            self.assertTrue(entered.wait(1))
            with patch.object(plugin._thread, 'join'):
                plugin.init_plugin({'enabled': True, 'scan_paths': self.tmp.name})
            self.assertFalse(plugin.start_scan().success)
            release.set()
            plugin._thread.join(2)
            self.assertFalse(plugin._stats_data)

    def test_ui_and_api_are_serializable_and_instance_scoped(self):
        for version in ['v2', 'v3']:
            with self.subTest(version=version):
                _, plugin = self.plugin(version)
                self.assertTrue(plugin.get_dashboard('stats'))
                self.assertIsNone(plugin.get_dashboard('unknown'))
                for value in [plugin.get_page(), plugin.get_form(), plugin.get_dashboard('stats')]:
                    json.dumps(value)
                for route in plugin.get_api():
                    self.assertEqual(route['auth'], 'bear')
                    self.assertTrue(route['response_model'])
                self.assertTrue(hasattr(plugin.remote_scan, 'registered_event'))

    def test_ranking_uses_explicit_rows_and_server_view_controls(self):
        module, plugin = self.plugin()
        plugin._stats_data = {'total_files': 15, 'total_size_bytes': 15,
            'groups': {f'group{i}': {'count': 1, 'size_bytes': i, 'files': []} for i in range(15)}}
        page = json.dumps(plugin.get_page(), ensure_ascii=False)
        self.assertIn('VTable', page)
        self.assertNotIn('VDataTable', page)
        plugin.set_ranking_view(module.RankingView(sort='name', descending=False, page=2))
        page = json.dumps(plugin.get_page(), ensure_ascii=False)
        self.assertIn('第 2 / 2 页', page)

    def test_running_page_refreshes_until_worker_finishes(self):
        for version in ['v2', 'v3']:
            with self.subTest(version=version):
                module, plugin = self.plugin(version)
                entered, release = threading.Event(), threading.Event()
                original = module.scanner.scan
                def delayed(*args, **kwargs):
                    entered.set()
                    release.wait(3)
                    return original(*args, **kwargs)
                with patch.object(module.scanner, 'scan', side_effect=delayed):
                    plugin.start_scan()
                    self.assertTrue(entered.wait(1))
                    running = json.dumps(plugin.get_page(), ensure_ascii=False)
                    self.assertIn('update:modelValue', running)
                    self.assertIn('plugin/ReleaseGroupStats/status', running)
                    release.set()
                    plugin._thread.join(2)
                completed = json.dumps(plugin.get_page(), ensure_ascii=False)
                self.assertIn('扫描完成', completed)
                self.assertNotIn('VSnackbar', completed)
                self.assertNotIn('indeterminate', completed)
                self.assertFalse(plugin.get_status().data.running)

    def test_podium_contains_only_three_highest_groups(self):
        module, _ = self.plugin()
        stats = {'total_files': 10, 'total_size_bytes': 10, 'groups': {
            name: {'count': count, 'size_bytes': count, 'files': []}
            for name, count in [('fourth', 1), ('second', 3), ('first', 4), ('third', 2)]}}
        podium = json.dumps(module.ui.podium(stats), ensure_ascii=False)
        for name in ['first', 'second', 'third', '冠军', '亚军', '季军']:
            self.assertIn(name, podium)
        self.assertNotIn('fourth', podium)
        self.assertTrue(module.ui.podium({'groups': {}}))


if __name__ == '__main__':
    unittest.main()
