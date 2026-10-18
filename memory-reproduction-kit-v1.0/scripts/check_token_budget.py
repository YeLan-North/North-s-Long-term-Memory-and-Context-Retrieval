#!/usr/bin/env python3
"""Check Markdown files against the embedding model's actual tokenizer."""
import argparse,json
from pathlib import Path

def main():
    p=argparse.ArgumentParser();p.add_argument('directory',type=Path);p.add_argument('--model',type=Path,required=True);p.add_argument('--limit',type=int,default=480)
    args=p.parse_args()
    from llama_cpp import Llama
    model=Llama(model_path=str(args.model),embedding=True,n_gpu_layers=0,verbose=False)
    counts=[{'file':f.relative_to(args.directory).as_posix(),'tokens':len(model.tokenize(f.read_bytes(),add_bos=True))} for f in sorted(args.directory.rglob('*.md'))]
    if not counts:raise SystemExit('未找到Markdown文件。')
    print(json.dumps({'files':len(counts),'max_tokens':max(x['tokens'] for x in counts),'oversized':[x for x in counts if x['tokens']>args.limit]},ensure_ascii=False,indent=2))
    if any(x['tokens']>args.limit for x in counts):raise SystemExit(2)

if __name__=='__main__':main()
