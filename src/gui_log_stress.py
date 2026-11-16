# Required Notice: Copyright (c) 2026 DrMoMing (https://github.com/DrMoMing/GenshinRewardScanner)
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# AI-generated project code: written and modified with OpenAI Codex.
"""Real Tk log flood/control priority and callback exception regression. No game/Office."""
from pathlib import Path
import sys,tempfile,json,time,ctypes
from types import SimpleNamespace
from unittest.mock import Mock,patch
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'portable'),str(ROOT/'debug')]
import tkinter as tk
import scanner_gui,user_controls as U
if '--frozen' in sys.argv:
 from PyInstaller.archive.readers import CArchiveReader
 index=sys.argv.index('--frozen')
 archive=CArchiveReader(sys.argv[index+1]).open_embedded_archive('PYZ.pyz')
 exec(archive.extract('scanner_gui'),scanner_gui.__dict__)

def main():
 with tempfile.TemporaryDirectory() as tmp:
  config=Path(tmp)/'settings.json';config.write_text(json.dumps(U.DEFAULT),encoding='utf-8')
  u=Mock();u.RegisterHotKey.return_value=1;u.PeekMessageW.return_value=0
  class MSG(ctypes.Structure):_fields_=[('message',ctypes.c_uint),('wParam',ctypes.c_size_t)]
  H=SimpleNamespace(SETTINGS_PATH=str(config),log=lambda *a:None,parse_hotkey=lambda v:(0,0),u=u,k32=Mock(),MSG=MSG,ID_SCAN=1,ID_QUIT=2,ID_SINGLE=3,ID_MONTAGE=4,WM_HOTKEY=0x312,PM_REMOVE=1)
  service=SimpleNamespace(auto_target=Path(tmp)/'test.xlsx',target=None,consumer=None,connection_info=None)
  service.reset_cancel=lambda:None;service.check_cancel=lambda:None;service.cancel=lambda:None
  def connect():service.target=service.auto_target;service.connection_info={'path':str(service.target),'mode':'simulation'};service.consumer=SimpleNamespace(poll=lambda:None)
  service.ensure_consumer=connect
  service.close=lambda **kwargs:setattr(service,'connection_info',None)
  ended=[None];done_seen=[None];launched=[False];ticks=[];errors=[];injected=[False];make=tk.Tk;insert=tk.Text.insert
  def flood(check):
   for i in range(100000):H.log('stress %d '%i+'x'*100)
   H.log('long '+'x'*(3*1024*1024));ended[0]=time.monotonic();return 1
  H.trigger=flood
  def nodes(w):
   out=[]
   for c in w.winfo_children():out += [c]+nodes(c)
   return out
  def button(root,label):return next(w for w in nodes(root) if w.winfo_class()=='TButton' and w.cget('text')==label)
  def fail_once(w,*a,**kw):
   if not injected[0]:injected[0]=True;raise RuntimeError('injected Text.insert failure')
   return insert(w,*a,**kw)
  def hidden():
   root=make();root.title('扫描器日志压力测试（自动结束，不操作游戏）')
   def tick():
    ticks.append(time.monotonic())
    if not launched[0] and any(str(w.cget('text')).startswith('正在等待扫描快捷键') for w in nodes(root) if w.winfo_class()=='TLabel'):
     launched[0]=True;button(root,'5秒后扫描一次').invoke()
    if ended[0]:
     labels=[str(w.cget('text')) for w in nodes(root) if w.winfo_class()=='TLabel']
     if any(v.startswith('失败；') for v in labels):
      if done_seen[0] is None:
       assert time.monotonic()-ended[0]<1,'done blocked by logs';done_seen[0]=time.monotonic()
       def recovery(n=0):
        for k in range(20):H.log('recovery %d %d'%(n,k))
        if n<30:root.after(100,lambda:recovery(n+1))
        else:
         H.log('RECOVERY_MARKER')
         root.after(300,verify_recovery)
       def verify_recovery():
        text=next(w for w in nodes(root) if w.winfo_class()=='Text')
        assert 'RECOVERY_MARKER' in text.get('1.0','end'),'log pump never recovered'
        assert int(text.index('end-1c').split('.')[0])<=400,'display line cap missing'
        assert len(text.get('1.0','end'))<802000
        button(root,'退出').invoke()
       recovery()
    root.after(20,tick)
   root.after(20,tick);root.after(100,lambda:button(root,'启动扫描 / 等待快捷键').invoke())
   def timeout():
    print('timeout state',ended,done_seen,injected,[str(w.cget('text')) for w in nodes(root) if w.winfo_class()=='TLabel'],flush=True);errors.append('timeout');root.destroy()
   root.after(20000,timeout);return root
  with patch.object(tk,'Tk',side_effect=hidden),patch.object(tk.Text,'insert',fail_once):scanner_gui.run(service,H)
  assert ended[0] and done_seen[0] and injected[0] and not errors,errors
  gap=max(b-a for a,b in zip(ticks,ticks[1:]));assert gap<1,gap
  print('VISIBLE 100000 lines + 3MB + insert exception: done under 1s; recovery marker/400-line cap/formal exit passed; heartbeat max gap',round(gap,3))
 return 0
if __name__=='__main__':raise SystemExit(main())
