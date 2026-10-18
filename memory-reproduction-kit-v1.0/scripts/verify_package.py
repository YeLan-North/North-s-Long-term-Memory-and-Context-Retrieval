#!/usr/bin/env python3
"""Verify distributed source files. Runtime configuration changes are expected later."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def main():
    manifest=json.loads((ROOT/'PACKAGE-MANIFEST.json').read_text());errors=[]
    for entry in manifest['files']:
        path=ROOT/entry['path']
        if not path.is_file():errors.append({'path':entry['path'],'error':'missing'});continue
        if hashlib.sha256(path.read_bytes()).hexdigest()!=entry['sha256']:errors.append({'path':entry['path'],'error':'changed'})
    print(json.dumps({'checked':len(manifest['files']),'ok':not errors,'errors':errors},ensure_ascii=False,indent=2))
    if errors:raise SystemExit(2)

if __name__=='__main__':main()
