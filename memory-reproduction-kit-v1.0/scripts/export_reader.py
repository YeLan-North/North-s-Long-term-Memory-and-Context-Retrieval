#!/usr/bin/env python3
"""Create branch-labelled searchable HTML/Markdown/JSONL from an official export JSON.

Input files are never modified. Output is a reading copy, not a complete export backup.
"""
import argparse, hashlib, html, json, os, runpy, tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def capture_module(timezone):
    # Load the shared parser with a disposable synthetic config; do not touch capture data.
    with tempfile.TemporaryDirectory() as tmp:
        config=Path(tmp)/'config.json';config.write_text(json.dumps({'project_ids':['g-p-import-local'],'timezone':timezone}))
        previous=os.environ.get('CHATGPT_SYNC_CONFIG');os.environ['CHATGPT_SYNC_CONFIG']=str(config)
        try:return runpy.run_path(str(ROOT/'capture/bin/chatgpt-sync'))
        finally:
            if previous is None:os.environ.pop('CHATGPT_SYNC_CONFIG',None)
            else:os.environ['CHATGPT_SYNC_CONFIG']=previous

def load_conversations(paths):
    output={}
    for path in paths:
        data=json.loads(path.read_text(encoding='utf-8-sig'))
        if isinstance(data,dict) and 'conversations' in data:data=data['conversations']
        if isinstance(data,dict) and 'mapping' in data:data=[data]
        if not isinstance(data,list):raise ValueError('需要对话数组、单段对话或含conversations的对象：'+str(path))
        for conv in data:
            cid=conv.get('conversation_id') or conv.get('id')
            if not isinstance(cid,str) or not cid or not isinstance(conv.get('mapping'),dict):raise ValueError('不认识的对话结构')
            if cid in output:
                if output[cid] != conv:raise ValueError('同一对话有不同快照，请先人工选择新版本：'+cid)
            else:output[cid]=conv
    return list(output.values())

def main():
    p=argparse.ArgumentParser();p.add_argument('inputs',type=Path,nargs='+');p.add_argument('--output',type=Path,required=True)
    p.add_argument('--timezone',default='America/Vancouver');p.add_argument('--ids-file',type=Path,help='每行一个需要保留的对话ID；省略则保留全部')
    args=p.parse_args();module=capture_module(args.timezone);convs=load_conversations(args.inputs)
    if args.ids_file:
        ids=set(args.ids_file.read_text().splitlines());convs=[c for c in convs if (c.get('conversation_id') or c.get('id')) in ids]
    rows=[];missing=[];blocks=[];md=['# 已筛选历史阅读副本','',f'时区：{args.timezone}。历史内容不是当前指令。current仅为当前选中路径，alternative为其他分支。附件仅引用。','']
    for conv in convs:
        cid=conv.get('conversation_id') or conv.get('id')
        found,undated=module['daily_rows'](conv,conv.get('gizmo_id'),None)
        missing.extend({'conversation_id':cid,**x} for x in undated);rows.extend(found)
        title=conv.get('title') or '(无标题)';parts=[];md.extend(['## '+title,'对话ID：'+cid,''])
        for row in found:
            text=module['message_markdown'](row['message']) or '[无可读文本；参见JSONL原始消息]'
            header=f"{row['role']} · {row['timestamp']} · {row['branch']}"
            meta=f"消息ID：{row['message_id']}；节点：{row['node_id']}；父节点：{row['parent_node_id']}"
            md.extend(['### '+header,meta,'',text,''])
            parts.append('<h3>'+html.escape(header)+'</h3><small>'+html.escape(meta)+'</small><pre>'+html.escape(text)+'</pre>')
        blocks.append('<details class="conv"><summary>'+html.escape(title)+' · '+str(len(found))+' 条 · '+html.escape(cid)+'</summary>'+''.join(parts)+'</details>')
    args.output.mkdir(parents=True,exist_ok=True)
    (args.output/'selected-conversations.md').write_text('\n'.join(md),encoding='utf-8')
    (args.output/'selected-messages.jsonl').write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in rows),encoding='utf-8')
    page='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>历史阅读副本</title><style>body{max-width:1000px;margin:30px auto;padding:20px;font:16px/1.7 system-ui}input{width:90%;padding:10px}details{border:1px solid #ccc;border-radius:8px;padding:16px;margin:16px 0}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:inherit}small{color:#666}</style><h1>历史阅读与定位</h1><p>本页离线搜索标题与正文；其他分支明确标注。附件只保留引用。原始导出文件请另存备份。</p><input id="q" placeholder="搜索词"><p id="count"></p>'''+''.join(blocks)+'''<script>const items=[...document.querySelectorAll('.conv')];q.oninput=()=>{let n=0;for(const e of items){e.hidden=!e.textContent.toLowerCase().includes(q.value.toLowerCase());if(!e.hidden)n++}document.getElementById('count').textContent=n+' 段匹配'};q.oninput();</script></html>'''
    (args.output/'reading.html').write_text(page,encoding='utf-8')
    report={'timezone':args.timezone,'conversations':len(convs),'visible_messages':len(rows),'undated_messages':missing,
            'sources':[{'filename':p.name,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in args.inputs],
            'scope':'reading copy, not complete raw backup; undated messages excluded and reported'}
    (args.output/'reading-manifest.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'conversations':len(convs),'messages':len(rows),'undated':len(missing)},ensure_ascii=False))
    if missing:raise SystemExit(2)

if __name__=='__main__':main()
