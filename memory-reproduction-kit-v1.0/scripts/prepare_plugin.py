#!/usr/bin/env python3
"""Fetch official source at a fixed commit; create a local recall-only plugin package."""
import argparse, json, shlex, shutil, subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
COMMIT='0fcc1663811914484163993735dfbef2c3ca2080'
URL='https://github.com/volcengine/OpenViking.git'

def write(p,v):
    p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')

def main():
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,help='已校验且检出固定提交的完整OpenViking仓库；省去下载')
    args=p.parse_args();source=args.source or ROOT/'vendor/OpenViking'
    if not source.exists():
        source.mkdir(parents=True)
        subprocess.run(['git','init',str(source)],check=True)
        subprocess.run(['git','-C',str(source),'remote','add','origin',URL],check=True)
        subprocess.run(['git','-C',str(source),'fetch','--depth','1','origin',COMMIT],check=True)
        subprocess.run(['git','-C',str(source),'checkout',COMMIT],check=True)
    actual=subprocess.check_output(['git','-C',str(source),'rev-parse','HEAD'],text=True).strip()
    if actual!=COMMIT: raise SystemExit('仓库提交不符；不自动切换已有仓库。')
    target=ROOT/'runtime/plugin-marketplace';plugin=target/'plugin'
    if plugin.exists(): raise SystemExit('插件目录已存在；移动旧目录备份后再准备，避免覆盖本地修改。')
    shutil.copytree(source/'examples/codex-memory-plugin',plugin)
    shared=plugin/'scripts/shared'
    if shared.exists(): shutil.rmtree(shared)
    shutil.copytree(source/'examples/memory-plugin-shared/lib',shared)
    node=shutil.which('node')
    if not node: raise SystemExit('需要 Node.js；请安装 Node 22+ 后重试。')
    env=json.loads((ROOT/'runtime/plugin-env.json').read_text())
    write(plugin/'.mcp.json',{'mcpServers':{'openviking-memory':{'command':node,'args':['servers/mcp-proxy.mjs'],'cwd':'.','startup_timeout_sec':30,'env':env}}})
    prefix='/usr/bin/env '+' '.join(shlex.quote(k+'='+v) for k,v in env.items())+' '+shlex.quote(node)
    hooks={}
    for event,matcher,script,timeout in [('SessionStart','clear|startup|resume','session-start-commit.mjs',70),('UserPromptSubmit','*','auto-recall.mjs',130)]:
        hooks[event]=[{'matcher':matcher,'hooks':[{'type':'command','command':prefix+' "${PLUGIN_ROOT}/scripts/'+script+'"','timeout':timeout}]}]
    write(plugin/'hooks/hooks.json',{'hooks':hooks})
    write(target/'.agents/plugins/marketplace.json',{'name':'local-memory-kit','description':'Local recall-only adaptation','plugins':[{'name':'openviking-memory','source':{'source':'local','path':'./plugin'},'policy':{'installation':'AVAILABLE','authentication':'ON_USE'},'category':'Productivity'}]})
    # Preserve official plugin metadata and upstream license; label the adaptation.
    metadata=json.loads((plugin/'.codex-plugin/plugin.json').read_text())
    metadata['description']='Local recall-only adaptation; chat capture and extraction disabled.'
    write(plugin/'.codex-plugin/plugin.json',metadata)
    for filename in ['LICENSE','NOTICE']:
        if (source/filename).is_file():shutil.copyfile(source/filename,target/filename)
    (target/'UPSTREAM_COMMIT').write_text(COMMIT+'\n')
    print('本地插件已准备，尚未注册、启用或信任。接下来按教程执行 codex plugin marketplace add / add。')

if __name__ == '__main__':main()
