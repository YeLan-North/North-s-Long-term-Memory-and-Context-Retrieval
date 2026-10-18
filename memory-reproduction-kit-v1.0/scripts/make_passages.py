#!/usr/bin/env python3
"""Lossless per-message body chunks with model-token budgets and source metadata."""
import argparse, hashlib, json, re
from pathlib import Path
from export_reader import capture_module

def main():
    p=argparse.ArgumentParser();p.add_argument('jsonl',type=Path);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--model',type=Path,required=True);p.add_argument('--max-tokens',type=int,default=480)
    args=p.parse_args()
    if not 128<=args.max_tokens<=480:raise SystemExit('max-tokens范围128–480；需为512上下文留出余量。')
    from llama_cpp import Llama
    model=Llama(model_path=str(args.model),embedding=True,n_gpu_layers=0,verbose=False)
    count=lambda text:len(model.tokenize(text.encode('utf-8'),add_bos=True))
    module=capture_module('UTC');out=args.output
    if out.exists() and any(out.iterdir()):raise SystemExit('输出目录必须为空，避免遗留旧分片。请使用新版本目录。')
    out.mkdir(parents=True,exist_ok=True);manifest=[];seen=set()
    for line in args.jsonl.read_text(encoding='utf-8').splitlines():
        row=json.loads(line);cid=row['conversation_id'];node=row['node_id'];key=(cid,node)
        if key in seen:raise ValueError('重复消息节点')
        seen.add(key)
        text=module['message_markdown'](row['message']) or ''
        identity=hashlib.sha256((cid+'\0'+node).encode()).hexdigest()[:24]
        parts=[];start=0
        # All metadata is also included in the token budget. Full title remains in JSONL.
        while start<len(text) or not parts:
            number=len(parts)+1
            meta={k:row.get(k) for k in ['conversation_id','node_id','parent_node_id','message_id','role','timestamp','branch','source_order']}
            header='# 历史消息片段\n'+json.dumps(meta,ensure_ascii=False,separators=(',',':'))+f'\npart={number}; body_start={start}\n\n'
            if count(header)>=args.max_tokens:raise ValueError('来源元数据超过预算，需缩短ID或使用更长上下文模型。')
            lo,hi=start,len(text)
            while lo<hi:
                mid=(lo+hi+1)//2
                if count(header+text[start:mid])<=args.max_tokens:lo=mid
                else:hi=mid-1
            end=lo
            if end==start and start<len(text):raise ValueError('无法容纳一个正文字符')
            body=text[start:end];name=f'{identity}-p{number:04d}.md'
            (out/name).write_text(header+body,encoding='utf-8')
            manifest.append({'file':name,**meta,'part':number,'body_start':start,'body_end':end,
                             'tokens':count(header+body),'body_sha256':hashlib.sha256(body.encode()).hexdigest()})
            parts.append(body);start=end
            if start==len(text):break
        assert ''.join(parts)==text
    (out/'manifest.json').write_text(json.dumps({'input_sha256':hashlib.sha256(args.jsonl.read_bytes()).hexdigest(),'messages':len(seen),'parts':manifest},ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'messages':len(seen),'passages':len(manifest),'max_tokens':max([x['tokens'] for x in manifest],default=0)}))

if __name__=='__main__':main()
