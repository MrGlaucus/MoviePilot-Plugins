"""Filesystem statistics without MoviePilot dependencies."""
import json
import math
import os
from pathlib import Path
import re
import tempfile
import time

from .rules import RELEASE_GROUPS

DEFAULT_EXTENSIONS = {'.mkv', '.mp4', '.avi', '.iso', '.ts', '.flv', '.wmv', '.mov', '.m4v', '.webm'}
SAMPLE_LIMIT = 10


class ScanCancelled(Exception):
    """A cancelled traversal must not publish a snapshot."""


def extensions(value):
    """Normalize user extension lists, falling back to the built-in set."""
    tokens = re.split(r'[,;\s]+', '\n'.join(
        line for line in (value or '').splitlines() if not line.strip().startswith('#')))
    result = {'.' + token.lower().lstrip('.') for token in tokens if token.strip('.')}
    return result or set(DEFAULT_EXTENSIONS)


def normalize_paths(value):
    """Canonicalize paths and discard duplicates and nested roots."""
    paths = sorted({os.path.normcase(os.path.realpath(os.path.expanduser(p.strip())))
                    for p in re.split(r'[;\r\n]+', value or '') if p.strip()}, key=len)
    roots = []
    for path in paths:
        nested = False
        for root in roots:
            try:
                nested = os.path.commonpath([root, path]) == root
            except ValueError:  # Different Windows drives.
                pass
            if nested:
                break
        if not nested:
            roots.append(path)
    return roots


class Matcher:
    """Precompiled custom rules and bounded built-in aliases."""

    def __init__(self, custom=''):
        self.errors = []
        self.custom = []
        self.builtin = []
        for number, line in enumerate((custom or '').splitlines(), 1):
            if not line.strip() or line.lstrip().startswith('#'):
                continue
            try:
                name, pattern = line.split('|', 1)
                if not name.strip() or not pattern.strip():
                    raise ValueError('分类名和表达式不能为空')
                self.custom.append((name.strip(), re.compile(pattern, re.I)))
            except (ValueError, re.error) as exc:
                self.errors.append(f'自定义规则第 {number} 行无效：{exc}')
        for name, aliases in RELEASE_GROUPS.items():
            for alias in [re.escape(name)] + aliases:
                # Site aliases often include alternatives, so keep the group intact.
                regex = re.compile(r'(?<![A-Za-z0-9])(?:' + alias + r')(?![A-Za-z0-9])', re.I)
                self.builtin.append((name, regex))

    def _match_text(self, text):
        """Prefer trailing release tags; short aliases only match at the end."""
        candidates = []
        for name, regex in self.builtin:
            for match in regex.finditer(text):
                tail = text[match.end():].strip(' ._-[]()【】')
                if not tail:
                    candidates.append((match.start(), len(match.group()), name))
        if candidates:
            return max(candidates)[2]
        for name, regex in self.builtin:
            match = regex.search(text)
            if match and (len(match.group()) > 3 or re.search(r'[^\x00-\x7f]', match.group())):
                return name
        return None

    def match(self, filename, parent=''):
        """Use custom rules, then filename tags, then immediate parent tags."""
        stem = Path(filename).stem
        for text in (stem, parent):
            for name, regex in self.custom:
                if regex.search(text):
                    return name
        for text in (stem, parent):
            found = self._match_text(text)
            if found:
                return found
        return '其它'


def scan(roots, allowed, matcher, cancelled, progress=None):
    """Stream directory trees into bounded statistics, reporting read failures."""
    started = time.monotonic()
    result = {'schema_version': 2, 'total_files': 0, 'total_size_bytes': 0,
              'groups': {}, 'checked_files': 0, 'error_count': 0, 'errors': [],
              'scan_paths': list(roots), 'partial': False}
    readable = 0

    def check_cancel():
        if cancelled.is_set():
            raise ScanCancelled()

    def error(exc):
        result['error_count'] += 1
        if len(result['errors']) < SAMPLE_LIMIT:
            result['errors'].append(str(exc))

    for directory in roots:
        check_cancel()
        if not os.path.isdir(directory):
            error(f'目录不可用：{directory}')
            continue
        visited_root = False
        for current, dirs, files in os.walk(directory, onerror=error, followlinks=False):
            check_cancel()
            if not visited_root:
                readable += 1
                visited_root = True
            dirs[:] = [d for d in dirs if not os.path.islink(os.path.join(current, d))]
            for filename in files:
                check_cancel()
                result['checked_files'] += 1
                path = Path(current) / filename
                if path.suffix.lower() in allowed and not path.is_symlink():
                    try:
                        size = path.stat().st_size
                    except OSError as exc:
                        error(exc)
                        continue
                    name = matcher.match(filename, Path(current).name)
                    group = result['groups'].setdefault(name, {'count': 0, 'size_bytes': 0, 'files': []})
                    group['count'] += 1
                    group['size_bytes'] += size
                    if len(group['files']) < SAMPLE_LIMIT:
                        group['files'].append(str(path))
                    result['total_files'] += 1
                    result['total_size_bytes'] += size
                if progress and result['checked_files'] % 100 == 0:
                    progress(result['checked_files'], result['total_files'], result['error_count'])
    check_cancel()
    if not readable:
        raise ValueError('没有可读取的扫描目录；保留上次统计结果')
    result['partial'] = result['error_count'] > 0
    result['last_scan_timestamp'] = time.time()
    result['last_scan_time'] = time.strftime('%Y-%m-%d %H:%M:%S')
    result['scan_duration_seconds'] = round(time.monotonic() - started, 2)
    if progress:
        progress(result['checked_files'], result['total_files'], result['error_count'])
    return result


def validate_snapshot(data):
    """Read historical snapshots safely and bound legacy full path lists."""
    if not isinstance(data, dict) or not isinstance(data.get('groups'), dict):
        raise ValueError('统计结果结构无效')
    clean = dict(data)
    if not isinstance(data.get('last_scan_time', ''), str):
        raise ValueError('扫描时间无效')
    for key in ['last_scan_timestamp', 'scan_duration_seconds', 'checked_files', 'error_count']:
        value = data.get(key, 0)
        if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
            raise ValueError('扫描元数据无效')
    if type(data.get('partial', False)) is not bool:
        raise ValueError('统计完整性标记无效')
    clean['groups'] = {}
    for name, group in data['groups'].items():
        if not isinstance(group, dict):
            raise ValueError('发布组结果结构无效')
        count, size = group.get('count'), group.get('size_bytes')
        if type(count) is not int or type(size) is not int or min(count, size) < 0:
            raise ValueError('统计数量或容量无效')
        paths = group.get('files', [])
        if not isinstance(paths, list):
            raise ValueError('样例列表无效')
        clean['groups'][name] = {'count': count, 'size_bytes': size,
                                 'files': [p for p in paths[:SAMPLE_LIMIT] if isinstance(p, str)]}
    clean['total_files'] = sum(g['count'] for g in clean['groups'].values())
    clean['total_size_bytes'] = sum(g['size_bytes'] for g in clean['groups'].values())
    clean.pop('top5', None)  # Rankings are derived from the current snapshot.
    return clean


def save_snapshot(path, data):
    """Flush a temporary file and atomically replace the last successful snapshot."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent,
                                         prefix='.stats-', suffix='.tmp', delete=False) as file:
            temporary = file.name
            json.dump(data, file, ensure_ascii=False)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary, path)
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)
