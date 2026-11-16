# Required Notice: Copyright (c) 2026 DrMoMing (https://github.com/DrMoMing/GenshinRewardScanner)
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# AI-generated project code: written and modified with OpenAI Codex.
"""Authenticated local pipes share the prepared OCR actors with whole-row jobs."""
import json,os,threading,contextlib
import full_diagnostics as diag
from pathlib import Path

def start_server(domain,lock):
    address=os.environ.get('DOMAIN_ACTOR_ADDRESS')
    if not address:return None
    from multiprocessing.connection import Listener
    listener=Listener(address,family='AF_PIPE',authkey=bytes.fromhex(os.environ['DOMAIN_ACTOR_KEY']))
    def serve():
        while True:
            try:connection=listener.accept()
            except (OSError,EOFError):return
            try:
                request=json.loads(connection.recv_bytes().decode('utf-8'))
                diag.emit('actor_received',request_kind=request.get('kind','detail'),index=request.get('index'))
                with lock:
                    diag.emit('actor_lock_acquired',request_kind=request.get('kind','detail'),index=request.get('index'))
                    marker=request.get('cancel')
                    if marker and Path(marker).exists():raise RuntimeError('用户已中止识别')
                    class Progress:
                        def __init__(self):self.buffer='';self.write_lock=threading.RLock()
                        def write(self,value):
                            # Optional image preparation emits timing records
                            # from a second thread. AF_PIPE send_bytes and the
                            # shared line buffer must stay serialized.
                            with self.write_lock:
                                self.buffer+=value
                                while '\n' in self.buffer:
                                    line,self.buffer=self.buffer.split('\n',1)
                                    connection.send_bytes(json.dumps({'progress':line},ensure_ascii=False).encode('utf-8'))
                            return len(value)
                        def flush(self):pass
                    if request.get('kind') in ('amounts','row-info'):
                        # Loading/calibration are instrumented too. Forward the
                        # entire operation, not just inference, over this RPC.
                        with contextlib.redirect_stdout(Progress()):
                            from native_frame import load_frame
                            image=load_frame(request['paths'][0]);domain.configure_geometry(image)
                            cards=request['cards']
                            if request.get('kind')=='row-info':cards=domain.read_row_info(image,cards)
                            else:domain.attach_amounts(image,cards)
                        connection.send_bytes(json.dumps({'ok':True,'cards':cards},ensure_ascii=False).encode('utf-8'))
                        continue
                    with contextlib.redirect_stdout(Progress()):
                        lane=domain.SlowLane.__new__(domain.SlowLane)
                        lane.inline=True;lane.remote=None;lane.actor_context=True;lane.lock=threading.Lock()
                        lane.res={};lane.err=[];lane.stars={};lane.local=threading.local()
                        if request.get('star') in (2,3,4,5):lane.stars[request['index']]=request['star']
                        lane.local.engine=domain.ocr()
                        lane._work(request['index'],request['paths'],request.get('name',''))
                    if lane.err:raise RuntimeError('；'.join(lane.err))
                    result=lane.res[request['index']]
                    reply={'ok':True,'result':result,'history':getattr(lane.local.engine,'_detail_selection_history',[]),
                           'pid':os.getpid(),'engine_id':id(lane.local.engine)}
                connection.send_bytes(json.dumps(reply,ensure_ascii=False).encode('utf-8'))
            except Exception as error:
                try:connection.send_bytes(json.dumps({'ok':False,'error':str(error)},ensure_ascii=False).encode('utf-8'))
                except (OSError,EOFError):pass
            finally:connection.close()
    threading.Thread(target=serve,daemon=True,name='prepared-ocr-pipe').start()
    return listener

class SharedActors:
    def __init__(self,endpoints,reply_timeout=60.0):
        from queue import Queue
        self.available=Queue();self.reply_timeout=reply_timeout
        for endpoint in endpoints:self.available.put(endpoint)
    def read_pair(self,index,paths,name,star=None):
        return self.request({'index':index,'paths':paths,'name':name,'star':star})
    def read_amounts(self,path,cards):
        return self.request({'kind':'amounts','paths':[path],'cards':cards})['cards']
    def read_row_info(self,path,cards):
        return self.request({'kind':'row-info','paths':[path],'cards':cards})['cards']
    def request(self,request):
        from multiprocessing.connection import Client
        import time
        marker=os.environ.get('DOMAIN_CANCEL_FILE')
        def cancelled():
            if marker and Path(marker).exists():raise RuntimeError('用户已中止识别')
        diag.emit('actor_queue_begin',request_kind=request.get('kind','detail'),index=request.get('index'),available=self.available.qsize())
        cancelled();endpoint=self.available.get()
        diag.emit('actor_queue_acquired',request_kind=request.get('kind','detail'),index=request.get('index'),available=self.available.qsize())
        try:
            cancelled()
            with Client(endpoint['address'],family='AF_PIPE',authkey=bytes.fromhex(endpoint['key'])) as connection:
                connection.send_bytes(json.dumps(dict(request,cancel=marker)).encode('utf-8'))
                last_activity=time.monotonic()
                while True:
                    while not connection.poll(.2):
                        cancelled()
                        if time.monotonic()-last_activity>self.reply_timeout:
                            raise RuntimeError('后台识别连续%.1f秒无响应；已停止等待，原始截图保留。请中止后重新启动扫描。'%self.reply_timeout)
                    reply=json.loads(connection.recv_bytes().decode('utf-8'))
                    last_activity=time.monotonic()
                    if 'progress' not in reply:break
                    if '[后台OCR]' not in reply['progress']:print(reply['progress'],flush=True)
            if not reply['ok']:raise RuntimeError(reply['error'])
            diag.emit('actor_reply',request_kind=request.get('kind','detail'),index=request.get('index'),ok=True)
            return reply
        finally:self.available.put(endpoint)
