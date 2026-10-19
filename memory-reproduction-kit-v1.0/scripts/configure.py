#!/usr/bin/env python3
"""Generate only local package configuration; never edit global host settings."""
import argparse, datetime as dt, json, re
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]

def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

def main():
    p = argparse.ArgumentParser(); p.add_argument('--settings', type=Path, default=ROOT/'settings.json')
    args = p.parse_args(); s = json.loads(args.settings.read_text(encoding='utf-8'))
    ids = s['project_ids']
    if not isinstance(ids, list) or not ids or any(not isinstance(x,str) or not re.fullmatch(r'g-p-[A-Za-z0-9-]+', x) or 'REPLACE' in x for x in ids):
        raise SystemExit('请先填写实际项目 ID；不接受空白名单或示例值。')
    ZoneInfo(s['timezone'])
    boundary = s.get('diary_boundary', '00:00')
    if not isinstance(boundary, str) or not re.fullmatch(r'\d{2}:\d{2}(?::\d{2})?', boundary):
        raise SystemExit('diary_boundary 必须为本地 HH:MM 或 HH:MM:SS。')
    try:
        dt.time.fromisoformat(boundary)
    except ValueError:
        raise SystemExit('diary_boundary 超出有效时间范围。')
    if not re.fullmatch(r'[a-zA-Z0-9_-]+', s['memory_collection']):
        raise SystemExit('memory_collection 仅允许英文字母、数字、下划线和短横线。')
    runtime = ROOT/'runtime'
    for sub in ['models','data','hook-state','daily','memory-source','passages','cards']:
        (runtime/sub).mkdir(parents=True, exist_ok=True)
    write(ROOT/'capture/config.json', {'project_ids': ids, 'timezone': s['timezone'], 'format':'markdown'})
    write(runtime/'ov.conf', {
        'server': {'host':'127.0.0.1','port':1933},
        'storage': {'workspace':str(runtime/'data'),'vectordb':{'backend':'local'},'agfs':{'backend':'local'}},
        'embedding': {'dense':{'provider':'local','model':'bge-small-zh-v1.5-f16','dimension':512,'input':'text','cache_dir':str(runtime/'models')}},
        'auto_generate_l0':False,'auto_generate_l1':False})
    write(runtime/'ovcli.conf', {'url':'http://127.0.0.1:1933','plugin':{'codex':{'autoCapture':False,'autoRecall':True,'usageView':'off','recallCompress':'off'}}})
    env = {'OPENVIKING_CLI_CONFIG_FILE':str(runtime/'ovcli.conf'),'OPENVIKING_CONFIG_FILE':str(runtime/'ov.conf'),
           'OPENVIKING_CODEX_STATE_DIR':str(runtime/'hook-state'),'OPENVIKING_STATE_DIR':str(runtime/'hook-state'),
           'OPENVIKING_CREDENTIAL_SOURCE':'cli','OPENVIKING_USAGE_VIEW':'off','OPENVIKING_AUTO_CAPTURE':'0',
           'OPENVIKING_RECALL_COMPRESS':'off','OPENVIKING_RECALL_QUERY_EXPANSION':'off',
           'OPENVIKING_RECALL_COMPRESS_DETECT_ON_STARTUP':'0'}
    write(runtime/'plugin-env.json',env)
    replacements = {'{{KIT_ROOT}}':str(ROOT),'{{PROJECT_IDS}}':', '.join(ids),'{{TIMEZONE}}':s['timezone'],
                    '{{DIARY_BOUNDARY}}':boundary,'{{ASSISTANT}}':s['assistant_name'],'{{SENDER}}':s['sender_email'],'{{RECIPIENT}}':s['recipient_email'],
                    '{{MEMORY_ROOT}}':'viking://user/default/resources/'+s['memory_collection']}
    for source in (ROOT/'templates').glob('*.md'):
        text=source.read_text(encoding='utf-8')
        for old,new in replacements.items(): text=text.replace(old,new)
        target=runtime/'instructions'/source.name;target.parent.mkdir(exist_ok=True);target.write_text(text,encoding='utf-8')
    print('已生成 capture/config.json、runtime 配置和个性化指令；尚未下载依赖、注册插件或创建任务。')

if __name__ == '__main__': main()
