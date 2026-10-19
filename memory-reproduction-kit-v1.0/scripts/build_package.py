#!/usr/bin/env python3
"""Build a clean, allowlisted v1.1 source ZIP; never include configured runtime data."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
ROOT_FILES = ['.gitignore', 'LICENSE', 'NOTICE.md', 'README.md', 'VALIDATION.md',
              'WINDOWS.md', 'memory-guide.html', '长期记忆与历史保存复现教程.md',
              'dependency-sources.json', 'reference-environment.txt', 'settings.example.json',
              'capture/CHANGES.md', 'capture/LICENSE', 'capture/Start-Capture.command']
PATTERNS = ['scripts/*.py', 'scripts/*.command', 'tests/*.py', 'templates/*.md',
            'capture/bin/chatgpt-sync', 'capture/bin/chatgpt-window', 'capture/bin/aster-diary',
            'capture/tests/*.py', 'capture/tests/*.cjs', 'capture/extension/*.js',
            'capture/extension/*.json', 'capture/extension/*.html', 'capture/extension/icons/*']
EMPTY_CONFIG = {'project_ids': [], 'timezone': 'America/Vancouver', 'format': 'markdown'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    config = ROOT / 'capture/config.json'
    if json.loads(config.read_text(encoding='utf-8')) != EMPTY_CONFIG:
        raise SystemExit('Refusing to package a configured project whitelist; build from a clean checkout.')
    files = {ROOT / name for name in ROOT_FILES} | {config}
    for pattern in PATTERNS:
        files.update(path for path in ROOT.glob(pattern) if path.is_file())
    for path in files:
        if not path.is_file():
            raise SystemExit('Missing distribution source: ' + str(path))
    manifest = {'version': '1.1', 'capture_version': '0.7.0',
                'scope': 'allowlisted source only; excludes runtime, real settings, capture data/state and caches',
                'files': [{'path': str(p.relative_to(ROOT)), 'bytes': p.stat().st_size,
                           'sha256': hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(files)]}
    (ROOT / 'PACKAGE-MANIFEST.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    files.add(ROOT / 'PACKAGE-MANIFEST.json')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(args.output, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(files):
            # Retain the established directory name so existing instructions still resolve.
            archive.write(path, 'memory-reproduction-kit-v1.0/' + str(path.relative_to(ROOT)))
    print(json.dumps({'version': '1.1', 'files': len(files), 'zip': str(args.output),
                      'sha256': hashlib.sha256(args.output.read_bytes()).hexdigest()}, indent=2))


if __name__ == '__main__':
    main()
