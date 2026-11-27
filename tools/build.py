# Required Notice: Copyright (c) 2026 DrMoMing (https://github.com/DrMoMing/GenshinRewardScanner)
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# AI-generated project code: written and modified with OpenAI Codex.
"""Standalone review-tree build; no local development history is required."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def checked_support(archive):
    manifest = json.loads((ROOT/'build-support.json').read_text(encoding='utf8'))
    if list(sys.version_info[:2]) != manifest['python']:
        raise RuntimeError('需要与支持包一致的 Python ' + '.'.join(map(str, manifest['python'])))
    if sha(archive) != manifest['sha256']:
        raise RuntimeError('构建支持包 SHA256 不符')
    destination = ROOT/'.build'/('runtime-support-'+manifest['sha256'][:16])
    destination.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as source:
        for item in source.infolist():
            target = destination/item.filename
            if not target.resolve().is_relative_to(destination.resolve()) or (item.external_attr >> 16) & 0o170000 == 0o120000:
                raise RuntimeError('支持包中含非法路径或链接')
            if item.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            elif not target.is_file() or sha(target) != manifest['files'][item.filename]:
                target.parent.mkdir(parents=True, exist_ok=True)
                with source.open(item) as incoming, target.open('wb') as outgoing:
                    shutil.copyfileobj(incoming, outgoing)
        if set(source.namelist()) != set(manifest['files']):
            raise RuntimeError('支持包文件清单不符')
    for name, digest in manifest['files'].items():
        if sha(destination/name) != digest:
            raise RuntimeError('支持文件校验失败：' + name)
    if {p.relative_to(destination).as_posix() for p in destination.rglob('*') if p.is_file()} != set(manifest['files']):
        raise RuntimeError('支持包缓存含清单外文件；请使用新的干净源码副本')
    return destination


def compile_host(destination):
    framework = Path(os.environ['WINDIR'])/'Microsoft.NET/Framework64/v4.0.30319'
    source = ROOT/'native/desktop_host'
    destination.mkdir(parents=True, exist_ok=True)
    temporary = ROOT/'.build/compiler-temp'
    temporary.mkdir(parents=True, exist_ok=True)
    references = ['WPF/PresentationFramework.dll', 'WPF/PresentationCore.dll', 'WPF/WindowsBase.dll', 'System.Xaml.dll']
    subprocess.run([str(framework/'csc.exe'), '/nologo', '/target:winexe', '/platform:x64',
        '/codepage:65001', '/utf8output', '/out:'+str(destination/'NativeDesktopHost.exe'),
        '/win32manifest:'+str(ROOT/'packaging/desktop_web_host.manifest'),
        '/win32icon:'+str(source/'brand.ico'), '/reference:System.Web.Extensions.dll', '/reference:Microsoft.CSharp.dll',
        *['/reference:'+str(framework/name) for name in references], *map(str, sorted(source.glob('*.cs')))], check=True,
        env=dict(os.environ, TEMP=str(temporary), TMP=str(temporary)))
    for path in source.glob('*'):
        if path.suffix in ('.xaml', '.ico', '.json'):
            shutil.copy2(path, destination/path.name)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--support', type=Path, required=True, help='配套 Release 构建支持包.zip')
    parser.add_argument('--check', action='store_true', help='只校验完整性与编译生产源码')
    parser.add_argument('--iscc', type=Path, help='可选：Inno Setup ISCC.exe，额外生成安装包')
    args = parser.parse_args()
    support = checked_support(args.support)
    import py_compile
    for path in (ROOT/'src').glob('*.py'):
        py_compile.compile(str(path), cfile=str(ROOT/'.build/check-pyc'/path.with_suffix('.pyc').name), doraise=True)
    required = ['Assets/原神/副本结算页/材料图标', 'Assets/原神/副本结算页/详情布局/文字候选.json', 'src/artifact_layout.py']
    assert all((ROOT/path).exists() for path in required), '缺少生产识别资源'
    host = ROOT/'.build/desktop_host'
    compile_host(host)
    if args.check:
        print('support hashes, source compilation, recognition resources and native WPF build passed')
        return
    config = json.loads((ROOT/'release-config.json').read_text(encoding='utf8'))
    output = ROOT/'dist'
    assert not (output/'DomainScanner').exists(), '请保留旧构建，使用新的干净源码副本重建'
    payload = ROOT/'.build/payload'
    shutil.copytree(support/'runtime', payload, dirs_exist_ok=True)
    shutil.copytree(ROOT/'Assets', payload/'Assets', dirs_exist_ok=True)
    shutil.copytree(ROOT/'third_party/LICENSES', payload/'发行资料/LICENSES', dirs_exist_ok=True)
    shutil.copytree(ROOT/'third_party/native', payload/'发行资料/native', dirs_exist_ok=True)
    shutil.copytree(ROOT/'src', payload/'发行资料/source', dirs_exist_ok=True, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    shutil.copytree(host, payload/'desktop_host', dirs_exist_ok=True)
    (payload/'desktop_host/preview.json').unlink(missing_ok=True)
    (payload/'发行资料/manifest.json').write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding='utf8')
    command = [sys.executable, '-m', 'PyInstaller', '--clean', '--noconfirm', '--onedir', '--windowed',
        '--uac-admin', '--name', 'DomainScanner', '--contents-directory', '_运行依赖', '--distpath', str(output),
        '--workpath', str(ROOT/'.build/pyinstaller'), '--specpath', str(ROOT/'.build'),
        '--paths', str(ROOT/'src'), '--icon', str(ROOT/'native/desktop_host/brand.ico'),
        '--version-file', str(ROOT/'packaging/app_version.txt'),
        '--manifest', str(ROOT/'packaging/admin.manifest'), '--collect-all', 'maa']
    for path in (ROOT/'src').glob('*.py'):
        if path.stem != 'app':
            command += ['--hidden-import', path.stem]
    for name in ('Assets', '发行资料', '名称对照样本', 'desktop_host', 'overlay', 'diagnostic_trace'):
        if (payload/name).exists():
            command += ['--add-data', str(payload/name)+';'+name]
    subprocess.run(command+[str(ROOT/'src/app.py')], check=True)
    dist = output/'DomainScanner'
    # Restore the checksummed, matching native/stdlib runtime, including the
    # replaceable Maa DLL; discovery must not silently substitute upstream DLLs.
    shutil.copytree(payload, dist/'_运行依赖', dirs_exist_ok=True)
    shutil.copy2(ROOT/'使用说明.txt', dist/'使用说明.txt')
    if args.iscc:
        subprocess.run([str(args.iscc), '/Qp', '/DPayload='+str(dist), '/DReleaseOutput='+str(dist),
            '/DStarterData='+str(support/'starter_data'), '/DReleaseVersion='+config['version'], str(ROOT/'packaging/installer.iss')], check=True)
        sys.path.insert(0, str(ROOT/'packaging'))
        from installer_manifest import require_admin
        require_admin(dist/('DomainScanner_Setup_'+config['version']+'.exe'))
    print(str(dist))


if __name__ == '__main__':
    main()
