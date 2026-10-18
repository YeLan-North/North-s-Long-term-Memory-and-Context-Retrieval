#!/usr/bin/env python3
"""Download a pinned PyPI sdist, verify its published hash, patch forced Metal, build."""
import hashlib, json, os, subprocess, sys, tarfile, urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
VERSION='0.3.36'

def main():
    if sys.version_info < (3,12): raise SystemExit('此安全解包脚本要求 Python 3.12+，参考环境为3.13。')
    dest=ROOT/'vendor/llama-cpu-build';dest.mkdir(parents=True,exist_ok=True)
    with urllib.request.urlopen(f'https://pypi.org/pypi/llama-cpp-python/{VERSION}/json') as r: info=json.load(r)
    entry=next(x for x in info['urls'] if x['packagetype']=='sdist')
    archive=dest/entry['filename']
    if not archive.exists(): urllib.request.urlretrieve(entry['url'],archive)
    digest=hashlib.sha256(archive.read_bytes()).hexdigest()
    if digest != entry['digests']['sha256']: raise SystemExit('源包SHA256不符，停止。')
    with tarfile.open(archive) as tar: tar.extractall(dest, filter='data')
    source=next(p for p in dest.iterdir() if p.is_dir() and p.name.startswith(('llama_cpp_python-','llama-cpp-python-')))
    cmake=source/'CMakeLists.txt';text=cmake.read_text()
    old='set(GGML_METAL "ON" CACHE BOOL "ggml: enable Metal" FORCE)'
    new='set(GGML_METAL "OFF" CACHE BOOL "ggml: enable Metal" FORCE)'
    if old not in text and new not in text: raise SystemExit('上游CMake结构不符，停止，需重新审查。')
    cmake.write_text(text.replace(old,new))
    env=os.environ.copy();env['CMAKE_ARGS']='-DGGML_METAL=OFF -DGGML_BLAS=OFF -DGGML_NATIVE=OFF'
    env['CMAKE_BUILD_PARALLEL_LEVEL']='4'
    if sys.platform=='darwin':
        sdk=subprocess.check_output(['xcrun','--show-sdk-path'],text=True).strip()
        env['SDKROOT']=sdk;env['CXXFLAGS']=f'-isystem {sdk}/usr/include/c++/v1'
        env['CMAKE_ARGS']+=f' -DCMAKE_OSX_SYSROOT={sdk}'
    python=ROOT/'.venv/bin/python'
    wheels=dest/'wheels';wheels.mkdir(exist_ok=True)
    subprocess.run([str(python),'-m','pip','wheel','--no-deps',str(source),'-w',str(wheels)],env=env,check=True)
    wheel=next(wheels.glob('llama_cpp_python-*.whl'))
    subprocess.run([str(python),'-m','pip','install','--force-reinstall','--no-deps',str(wheel)],check=True)
    subprocess.run([str(python),'-m','pip','install','typing-extensions>=4.5.0','numpy>=1.20.0','diskcache>=5.6.1','jinja2>=2.11.3'],check=True)
    (dest/'source-receipt.json').write_text(json.dumps({'version':VERSION,'url':entry['url'],'sha256':digest,'patch':'GGML_METAL forced ON -> OFF'},indent=2))
    print('CPU版构建并安装完成；请继续做真实嵌入测试。')

if __name__ == '__main__': main()
