"""Plan and package exact-generation releases; never publish from this script."""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import re
import subprocess
import zipfile

INDEXES = {'package.json': 'plugins', 'package.v2.json': 'plugins.v2', 'package.v3.json': 'plugins.v3'}


def source_files(directory):
    """Exclude interpreter caches from release assets and collision checks."""
    return sorted(p for p in directory.rglob('*') if p.is_file()
                  and '__pycache__' not in p.parts and p.suffix not in ['.pyc', '.pyo'])


def fingerprint(directory):
    """Compare complete package contents for repeated IDs and versions."""
    digest = hashlib.sha256()
    for path in source_files(directory):
        digest.update(path.relative_to(directory).as_posix().encode())
        digest.update(b'\0')
        digest.update(path.read_bytes())
    return digest.hexdigest()


def plan_releases(root, previous, only_package=None):
    """Only new versions are automatic release candidates; validate before any upload."""
    root = Path(root)
    plan, tags = [], {}
    for index, folder in INDEXES.items():
        if only_package and index != only_package:
            continue
        if not (root / index).exists():
            continue
        entries = json.loads((root / index).read_text(encoding='utf-8'))
        for plugin_id, entry in entries.items():
            version = entry.get('version', '')
            if not entry.get('release') or previous.get(index, {}).get(plugin_id, {}).get('version') == version:
                continue
            if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]*', plugin_id) or not re.fullmatch(r'\d+(?:\.\d+){1,3}', version):
                raise ValueError(f'Invalid plugin ID or version: {plugin_id} {version}')
            directory = root / folder / plugin_id.lower()
            tree = ast.parse((directory / '__init__.py').read_text(encoding='utf-8-sig'))
            cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == plugin_id)
            declared = next(ast.literal_eval(n.value) for n in cls.body if isinstance(n, ast.Assign)
                            and any(isinstance(t, ast.Name) and t.id == 'plugin_version' for t in n.targets))
            if declared != version or next(iter(entry.get('history', {})), '') != f'v{version}':
                raise ValueError(f'{index}: {plugin_id} source/index/history version mismatch')
            tag = f'{plugin_id}_v{version}'
            signature = fingerprint(directory)
            if tag in tags:
                if tags[tag] != signature:
                    raise ValueError(f'{tag}: different generations have different source; use distinct versions')
                continue
            tags[tag] = signature
            plan.append({'tag': tag, 'directory': f'{folder}/{plugin_id.lower()}',
                         'asset': f'.cache/releases/{plugin_id.lower()}_v{version}.zip'})
    return plan


def main():
    """Read the previous Git indexes, validate a full plan, then build zip assets."""
    parser = argparse.ArgumentParser()
    parser.add_argument('--before')
    parser.add_argument('--package', choices=INDEXES)
    parser.add_argument('--output', default='.cache/release-plan.json')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    previous = {}
    if args.before and set(args.before) != {'0'}:
        subprocess.run(['git', 'rev-parse', '--verify', f'{args.before}^{{commit}}'], cwd=root, check=True, capture_output=True)
        for index in INDEXES:
            result = subprocess.run(['git', 'show', f'{args.before}:{index}'], cwd=root, capture_output=True, text=True, encoding='utf-8')
            previous[index] = json.loads(result.stdout) if result.returncode == 0 else {}
    plan = plan_releases(root, previous, args.package)
    for item in plan:
        directory = root / item['directory']
        (root / item['asset']).parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(root / item['asset'], 'w', zipfile.ZIP_DEFLATED) as archive:
            for path in source_files(directory):
                archive.write(path, path.relative_to(directory.parent).as_posix())
    output = root / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'Validated and packaged {len(plan)} release(s)')


if __name__ == '__main__':
    main()
