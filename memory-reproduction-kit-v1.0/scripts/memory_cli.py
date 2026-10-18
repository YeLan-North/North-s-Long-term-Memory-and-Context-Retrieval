#!/usr/bin/env python3
"""Local OpenViking REST helper. Explicit writes, vector-only; no generation model."""
import argparse, hashlib, json, urllib.error, urllib.parse, urllib.request
from pathlib import Path

def request(base,path,body=None):
    req=urllib.request.Request(base+path,data=None if body is None else json.dumps(body,ensure_ascii=False).encode(),headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=300) as response:data=json.load(response)
    if data.get('status')=='error':raise RuntimeError(json.dumps(data,ensure_ascii=False))
    return data

def ensure_dir(base,uri):
    # Check existence first; do not treat every HTTP400 as an already-existing directory.
    try:request(base,'/api/v1/fs/stat?'+urllib.parse.urlencode({'uri':uri}));return
    except urllib.error.HTTPError as exc:
        if exc.code!=404:raise
    parent=uri.rsplit('/',1)[0]
    if parent!='viking:/' and parent!=uri:ensure_dir(base,parent)
    request(base,'/api/v1/fs/mkdir',{'uri':uri,'description':'Explicit local memory collection'})

def put(base,source,uri):
    ensure_dir(base,uri.rsplit('/',1)[0]);text=source.read_text(encoding='utf-8')
    request(base,'/api/v1/content/write',{'uri':uri,'content':text,'wait':True,'processing_mode':'vectors_only'})
    read=request(base,'/api/v1/content/read?'+urllib.parse.urlencode({'uri':uri,'raw':'true'}))['result']
    if read!=text:raise ValueError('原文读回不一致：'+uri)
    return {'file':source.name,'uri':uri,'sha256_utf8':hashlib.sha256(text.encode()).hexdigest(),'readback_equal':True}

def main():
    p=argparse.ArgumentParser();p.add_argument('--base',default='http://127.0.0.1:1933')
    sub=p.add_subparsers(dest='action',required=True)
    sub.add_parser('health')
    f=sub.add_parser('find');f.add_argument('query');f.add_argument('--uri',required=True);f.add_argument('--limit',type=int,default=5)
    r=sub.add_parser('read');r.add_argument('uri')
    a=sub.add_parser('put-file');a.add_argument('file',type=Path);a.add_argument('--uri',required=True);a.add_argument('--receipt',type=Path,required=True)
    d=sub.add_parser('put-dir');d.add_argument('directory',type=Path);d.add_argument('--uri',required=True);d.add_argument('--receipt',type=Path,required=True)
    args=p.parse_args()
    if args.base.rstrip('/')!='http://127.0.0.1:1933':raise SystemExit('此示例只允许本地1933；远程认证请使用官方客户端另行配置。')
    if args.action=='health':result=request(args.base,'/health')
    elif args.action=='find':result=request(args.base,'/api/v1/search/find',{'query':args.query,'target_uri':args.uri,'limit':args.limit})
    elif args.action=='read':result=request(args.base,'/api/v1/content/read?'+urllib.parse.urlencode({'uri':args.uri,'raw':'true'}))
    else:
        records=[];failures=[]
        entries=[(args.file,args.uri)] if args.action=='put-file' else [(f,args.uri.rstrip('/')+'/'+f.relative_to(args.directory).as_posix()) for f in sorted(args.directory.rglob('*.md'))]
        if not entries:raise SystemExit('没有找到待导入的Markdown文件。')
        for file,uri in entries:
            try:records.append(put(args.base,file,uri))
            except Exception as exc:failures.append({'file':str(file),'uri':uri,'error':str(exc)})
        result={'complete':not failures,'stored':records,'errors':failures}
        args.receipt.parent.mkdir(parents=True,exist_ok=True);args.receipt.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
        print(json.dumps({'complete':not failures,'stored':len(records),'errors':len(failures)}))
        if failures:raise SystemExit(2)
        return
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
