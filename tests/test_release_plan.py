"""Release plans must never silently choose another generation's source."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
(ROOT / '.cache/tests').mkdir(parents=True, exist_ok=True)
tempfile.tempdir = str(ROOT / '.cache/tests')


class ReleasePlanTests(unittest.TestCase):
    def test_generation_mapping_and_collision(self):
        spec = importlib.util.spec_from_file_location('release_plan', ROOT / 'scripts/release_plugins.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for index, folder, version in [('package.v2.json', 'plugins.v2', '1.1.0'),
                                            ('package.v3.json', 'plugins.v3', '2.0.0')]:
                directory = root / folder / 'example'
                directory.mkdir(parents=True)
                (directory / '__init__.py').write_text(f'class Example:\n    plugin_version = "{version}"\n')
                (root / index).write_text(json.dumps({'Example': {'version': version, 'release': True,
                    'history': {f'v{version}': 'release'}}}))
            plan = module.plan_releases(root, {})
            self.assertEqual([p['directory'] for p in plan], ['plugins.v2/example', 'plugins.v3/example'])
            self.assertEqual([p['tag'] for p in plan], ['Example_v1.1.0', 'Example_v2.0.0'])
            previous = {index: json.loads((root / index).read_text()) for index in ['package.v2.json', 'package.v3.json']}
            self.assertEqual(module.plan_releases(root, previous), [])
            entry = {'Example': {'version': '1.1.0', 'release': True, 'history': {'v1.1.0': 'release'}}}
            (root / 'package.v3.json').write_text(json.dumps(entry))
            (root / 'plugins.v3/example/__init__.py').write_text('class Example:\n    plugin_version = "1.1.0"\n    v3 = True\n')
            with self.assertRaises(ValueError):
                module.plan_releases(root, {})

    def test_repository_versions_match_sources(self):
        import ast
        for index, folder in [('package.v2.json', 'plugins.v2'), ('package.v3.json', 'plugins.v3')]:
            data = json.loads((ROOT / index).read_text(encoding='utf-8'))['ReleaseGroupStats']
            tree = ast.parse((ROOT / folder / 'releasegroupstats/__init__.py').read_text(encoding='utf-8-sig'))
            cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'ReleaseGroupStats')
            version = next(ast.literal_eval(n.value) for n in cls.body if isinstance(n, ast.Assign)
                           and any(isinstance(t, ast.Name) and t.id == 'plugin_version' for t in n.targets))
            self.assertEqual(data['version'], version)
            self.assertEqual(next(iter(data['history'])), 'v' + version)
