"""Regression tests; core tests use real files and no MoviePilot runtime."""
import importlib.util
import json
from pathlib import Path
import tempfile
import threading
import sys
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
(ROOT / '.cache' / 'tests').mkdir(parents=True, exist_ok=True)
tempfile.tempdir = str(ROOT / '.cache' / 'tests')
package = types.ModuleType('release_stats_core')
package.__path__ = [str(ROOT / 'plugins.v2/releasegroupstats')]
sys.modules[package.__name__] = package
spec = importlib.util.spec_from_file_location(
    'release_stats_core.scanner', ROOT / 'plugins.v2/releasegroupstats/scanner.py')
scanner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scanner)


class ScannerTests(unittest.TestCase):
    """Exercise recognition, traversal and storage contracts."""

    def test_recognition_boundaries_and_suffix_priority(self):
        matcher = scanner.Matcher()
        self.assertEqual(matcher.match('The.Lee.Movie.2024.1080p.mkv'), '其它')
        self.assertEqual(matcher.match('Movie.1080p-FRDS.mkv'), '朋友')
        self.assertEqual(matcher.match('Movie.1080p-VCB-Studio.mkv'), 'anime')
        self.assertEqual(matcher.match('CHD.Movie.2024-FRDS.mkv'), '朋友')
        self.assertEqual(matcher.match('Film.HDChinaTown.mkv'), '其它')

    def test_parent_fallback_and_custom_rules(self):
        matcher = scanner.Matcher('我的组|MYGROUP\n坏规则|[\nmissing separator')
        self.assertEqual(matcher.match('episode01.mkv', 'Series-FRDS'), '朋友')
        self.assertEqual(matcher.match('Film-MYGROUP.mkv'), '我的组')
        self.assertEqual(len(matcher.errors), 2)

    def test_extensions(self):
        self.assertEqual(scanner.extensions('MKV, .MP4;ts\n# ignored\nmkv'), {'.mkv', '.mp4', '.ts'})

    def test_overlapping_roots_and_streamed_statistics(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            child = root / 'Series-FRDS'
            child.mkdir()
            (child / 'episode01.MKV').write_bytes(b'abc')
            (root / 'Film-VCB-Studio.mkv').write_bytes(b'12345')
            (root / 'poster.jpg').write_bytes(b'ignored')
            roots = scanner.normalize_paths(f'{child};{root}\n{root}')
            self.assertEqual(len(roots), 1)
            result = scanner.scan(roots, scanner.extensions(''), scanner.Matcher(), threading.Event())
            self.assertEqual(result['total_files'], 2)
            self.assertEqual(result['total_size_bytes'], 8)
            self.assertEqual(result['groups']['朋友']['count'], 1)
            self.assertFalse(result['partial'])

    def test_invalid_roots_fail_but_empty_readable_root_succeeds(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                scanner.scan([str(Path(tmp) / 'missing')], scanner.extensions(''), scanner.Matcher(), threading.Event())
            self.assertEqual(scanner.scan([tmp], scanner.extensions(''), scanner.Matcher(), threading.Event())['total_files'], 0)

    def test_partial_result_is_explicit(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = scanner.scan([tmp, str(Path(tmp) / 'missing')], scanner.extensions(''), scanner.Matcher(), threading.Event())
            self.assertTrue(result['partial'])
            self.assertEqual(result['error_count'], 1)

    def test_cancel_does_not_return_a_snapshot(self):
        event = threading.Event()
        event.set()
        with tempfile.TemporaryDirectory() as tmp, self.assertRaises(scanner.ScanCancelled):
            scanner.scan([tmp], scanner.extensions(''), scanner.Matcher(), event)

    def test_examples_are_bounded(self):
        with tempfile.TemporaryDirectory() as tmp:
            for i in range(30):
                (Path(tmp) / f'film{i}-FRDS.mkv').touch()
            result = scanner.scan([tmp], scanner.extensions(''), scanner.Matcher(), threading.Event())
            self.assertEqual(result['total_files'], 30)
            self.assertLessEqual(len(result['groups']['朋友']['files']), 10)

    def test_failed_atomic_replace_preserves_old_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'stats_data.json'
            path.write_text('{"old": true}', encoding='utf-8')
            with patch.object(scanner.os, 'replace', side_effect=OSError('disk error')):
                with self.assertRaises(OSError):
                    scanner.save_snapshot(path, {'new': True})
            self.assertEqual(json.loads(path.read_text()), {'old': True})
            self.assertEqual(list(Path(tmp).iterdir()), [path])

    def test_old_snapshot_validation(self):
        old = {'total_files': 2, 'total_size_bytes': 10,
               'groups': {'朋友': {'count': 2, 'size_bytes': 10, 'files': ['x'] * 100}}}
        clean = scanner.validate_snapshot(old)
        self.assertEqual(clean['total_files'], 2)
        self.assertLessEqual(len(clean['groups']['朋友']['files']), 10)
        with self.assertRaises(ValueError):
            scanner.validate_snapshot({'groups': []})

    def test_invalid_legacy_metadata_cannot_break_status(self):
        with self.assertRaises(ValueError):
            scanner.validate_snapshot({'groups': {}, 'last_scan_time': None})

    def test_custom_parent_rule_overrides_builtin_filename(self):
        matcher = scanner.Matcher('自定义|MYGROUP')
        self.assertEqual(matcher.match('episode-FRDS.mkv', 'Series-MYGROUP'), '自定义')

    def test_unreadable_root_does_not_replace_results_with_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            def unreadable(directory, onerror, **kwargs):
                onerror(PermissionError('denied'))
                return iter([])
            with patch.object(scanner.os, 'walk', side_effect=unreadable), self.assertRaises(ValueError):
                scanner.scan([tmp], scanner.extensions(''), scanner.Matcher(), threading.Event())


if __name__ == '__main__':
    unittest.main()
