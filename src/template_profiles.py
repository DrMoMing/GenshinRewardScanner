# Required Notice: Copyright (c) 2026 DrMoMing (https://github.com/DrMoMing/GenshinRewardScanner)
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# AI-generated project code: written and modified with OpenAI Codex.
# Required Notice: Copyright (c) 2026 DrMoMing (https://github.com/DrMoMing/GenshinRewardScanner)
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# AI-generated project code: written and modified with OpenAI Codex.
"""A6 test libraries: isolated natural generations and explicit seeded samples.

Selection takes effect on application restart so retained OCR workers never mix
libraries. Reset creates a new generation; no old database is deleted."""
import hashlib,json,os,re,shutil,sqlite3,uuid
from contextlib import closing
from pathlib import Path

LABELS={'natural':'自然积累库','seeded':'预置已学样本库'}

def save_choice(base,profile,*,new_empty=False):
    if profile not in LABELS:raise ValueError('未知名称库状态')
    path=Path(base)/'模板实验设置.json'
    try:settings=json.loads(path.read_text(encoding='utf8'))
    except (OSError,ValueError):settings={}
    if not isinstance(settings,dict):settings={}
    settings['name_profile']=profile
    if new_empty:settings['natural_generation']=uuid.uuid4().hex
    temp=path.with_suffix('.profile.tmp')
    temp.write_text(json.dumps(settings,ensure_ascii=False,indent=2),encoding='utf8');os.replace(temp,path)
    return settings

def activate(base,resource,settings):
    profile=settings.get('name_profile','natural')
    if profile not in LABELS:profile='natural'
    generation=settings.get('natural_generation','default')
    if generation!='default' and not re.fullmatch('[0-9a-f]{32}',str(generation)):generation='default'
    seed_generation=settings.get('seed_generation','a6-v1')
    if seed_generation!='a6-v1' and not re.fullmatch('[0-9a-f]{32}',str(seed_generation)):seed_generation='a6-v1'
    folder=Path(base)/'缓存/详情模板实验'/profile/(generation if profile=='natural' else seed_generation)
    folder.mkdir(parents=True,exist_ok=True)
    if profile=='seeded':
        source=Path(resource)/'名称对照样本'
        manifest=json.loads((source/'manifest.json').read_text(encoding='utf8'))
        marker=folder/'seed_origin.json'
        if not marker.is_file():
            if seed_generation!='a6-v1':raise ValueError('自建对照库未完成，请从自然积累库重新生成')
            for name,digest in manifest['files'].items():
                if Path(name).name!=name or not name.endswith('.sqlite3'):raise ValueError('样本库文件名无效')
                incoming=source/name
                if hashlib.sha256(incoming.read_bytes()).hexdigest()!=digest:raise ValueError('预置样本库校验失败')
                # Leave previously installed/learned files intact after an
                # interrupted install; missing files alone are copied.
                destination=folder/name
                if not destination.exists():
                    temp=destination.with_suffix('.install.tmp');shutil.copyfile(incoming,temp);os.replace(temp,destination)
            temp=marker.with_suffix('.tmp');temp.write_text(json.dumps(manifest,ensure_ascii=False),encoding='utf8');os.replace(temp,marker)
    os.environ['DOMAIN_TEMPLATE_CACHE']=str(folder)
    os.environ['DOMAIN_TEMPLATE_PROFILE']=profile
    os.environ['DOMAIN_NAME_PRIORITY']='1'
    return dict(profile=profile,label=LABELS[profile],cache=str(folder),generation=folder.name,test_seed=profile=='seeded')

def snapshot_natural(base,source):
    """Called only at an idle/stopped GUI boundary; SQLite backup, no images.

    Qualifying data is copied. Test maturity never updates the natural policy.
    An interrupted build cannot become active before the final marker/settings."""
    base=Path(base).resolve();source=Path(source).resolve()
    if not source.is_relative_to(base/'缓存/详情模板实验/natural'):raise ValueError('只能从当前自然积累库生成对照')
    if next((source/'learning/pending').glob('*.json'),None):raise RuntimeError('学习尚有待办，请等待空闲学习完成后再生成')
    names=source/'rectangles_v3.sqlite3'
    if not names.is_file():raise RuntimeError('尚无已入库样本，请先扫描并等待空闲学习完成')
    with closing(sqlite3.connect(names.as_uri()+'?mode=ro',uri=True)) as db:
        labels=db.execute('SELECT DISTINCT g,label FROM rectangles WHERE active=1').fetchall()
    if not labels:raise RuntimeError('尚无已入库样本，请先扫描并等待空闲学习完成')
    generation=uuid.uuid4().hex;target=base/'缓存/详情模板实验/seeded'/generation;target.mkdir(parents=True)
    for name in ('rectangles_v3.sqlite3','field_policy_v3.sqlite3'):
        with closing(sqlite3.connect((source/name).as_uri()+'?mode=ro',uri=True)) as src,closing(sqlite3.connect(target/name)) as dst:
            src.backup(dst)
            if dst.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise RuntimeError('对照库快照校验失败')
    with closing(sqlite3.connect(target/'field_policy_v3.sqlite3')) as db:
        with db:
            for table in ('confirmations','reservations','demotions'):db.execute('DELETE FROM '+table)
            for key,label in labels:db.execute('INSERT OR REPLACE INTO fields VALUES (?,?,24,0,0)',(key,label))
    manifest=dict(version=generation,test_only=True,forced_maturity=True,source=str(source),label_groups=len(labels),
        files={name:hashlib.sha256((target/name).read_bytes()).hexdigest() for name in ('rectangles_v3.sqlite3','field_policy_v3.sqlite3')})
    (target/'seed_origin.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf8')
    path=base/'模板实验设置.json'
    try:settings=json.loads(path.read_text(encoding='utf8'))
    except (OSError,ValueError):settings={}
    if not isinstance(settings,dict):settings={}
    settings.update(name_profile='seeded',seed_generation=generation)
    temp=path.with_suffix('.profile.tmp');temp.write_text(json.dumps(settings,ensure_ascii=False,indent=2),encoding='utf8');os.replace(temp,path)
    return manifest
