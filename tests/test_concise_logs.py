# Required Notice: Copyright (c) 2026 DrMoMing (https://github.com/DrMoMing/GenshinRewardScanner)
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# AI-generated project code: written and modified with OpenAI Codex.
"""Concise user messages keep errors and the real raw diagnostic stream intact."""
import ast
import copy
import io
import json
from pathlib import Path
import sys
import types
from types import SimpleNamespace

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
import log_view
if '--frozen' in sys.argv:
    from PyInstaller.archive.readers import CArchiveReader
    archive=CArchiveReader(sys.argv[sys.argv.index('--frozen')+1]).open_embedded_archive('PYZ.pyz')
    module=types.ModuleType('log_view_frozen');exec(archive.extract('log_view'),module.__dict__);log_view=module

sample='[端点试验] '+json.dumps(dict(拖动序号=2,新判据='外侧有卡',原判据到端点=False,截图秒=.0416,计算秒=.0077),ensure_ascii=False)
assert log_view.scan_message(sample)=='第2次拖动：外侧仍有卡片。'
for verdict,word in (('外侧无卡','外侧未见卡片'),('不明确','端点尚未确认')):
    assert log_view.scan_message('[端点试验] '+json.dumps(dict(拖动序号=1,新判据=verdict),ensure_ascii=False))=='第1次拖动：'+word+'。'
for text in ('[端点试验] invalid json','[端点试验] []','[端点试验] {"future":1}',
    '[端点试验] {"拖动序号":2,"新判据":[]}',
    '磁盘已满，工作簿未能保存；请清理空间后重试。','错误：保存失败，文件被占用。',
    '[端点试验] 松手前截图失败，继续原方案：timeout'):
    assert log_view.scan_message(text)==text
assert '已自动降为1路' in log_view.scan_message('[资源保护] '+json.dumps(dict(event='worker_budget',requested=4,effective=1)))
for old,new in (
    ('   ⚠️ 上一步滞留 1.20 张 < 2.00 ⇒ 步进缩到 600','   上一步滞留 1.20 张，低于 2.00，步进缩至 600'),
    ('  导出 → result.json','  导出：result.json'),
    ('  契约 → internal.json','  契约：internal.json'),
    ('✅ 读过：3 条 ｜ 分布 {}','读过：3 条 ｜ 分布 {}'),
    ('副本结算页模块（D55/D56）｜ cmd=read','副本结算页模块｜命令=read')):
    assert log_view.scan_message(old) is None and log_view.scan_message(new) is None,(old,new)
assert log_view.scan_message('   已到奖励行末尾：白边位移约为 0，卡位及宽度稳定').startswith('已到奖励行末尾')
assert log_view.scan_message('扫描失败：截图超时')=='扫描失败：截图超时'
assert '锚点未确认' in log_view.scan_message('锚点未确认，停止扫描')

# Run the actual production reader loop, rather than a rewritten log sink.
tree=ast.parse((ROOT/'src/app.py').read_text(encoding='utf8'))
loops=[n for n in ast.walk(tree) if isinstance(n,ast.For) and ast.unparse(n.iter)=='p.stdout'
    and any(isinstance(c,ast.Call) and ast.unparse(c.func)=='trace.write' for c in ast.walk(n))]
assert len(loops)==1
messages=[];trace=io.StringIO()
environment=dict(p=SimpleNamespace(stdout=[(sample+'\n').encode('utf8')]),trace=trace,n=0,json=json,
    self=SimpleNamespace(hotkeys=SimpleNamespace(log=messages.append),report_progress=lambda text:None),
    clean_line=log_view.clean_line,scan_message=log_view.scan_message)
exec(compile(ast.fix_missing_locations(ast.Module(body=[copy.deepcopy(loops[0])],type_ignores=[])),'actual_production_reader','exec'),environment)
assert trace.getvalue()==sample+'\n' and messages==['第2次拖动：外侧仍有卡片。']
app=(ROOT/'src/app.py').read_text(encoding='utf8')
assert "self.hotkeys.log('一路页面识别模型已预备。')" in app
assert '单卡与整趟共用，每趟结束后保留' not in app
assert '不以“全是完整格”宣称整排已全' not in (ROOT/'src/domain_run.py').read_text(encoding='utf8')
print('concise messages, unknown/error preservation and actual raw-diagnostic reader passed')
