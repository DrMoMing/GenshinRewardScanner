# Required Notice: Copyright (c) 2026 DrMoMing (https://github.com/DrMoMing/GenshinRewardScanner)
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# AI-generated project code: written and modified with OpenAI Codex.
"""逐件事件追加到同一工作簿；XLSX 文件与桌面 Excel 使用同一表格布局。"""
import argparse
from datetime import datetime, timezone, timedelta
from functools import lru_cache
from decimal import Decimal
import json
import os
from pathlib import Path
import sys
if not getattr(sys,'frozen',False):sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'agent'))
import re
import time
import hashlib
import uuid

def local_time(at_ns=None):
    return datetime.fromtimestamp(at_ns/1e9).astimezone() if at_ns is not None else datetime.now().astimezone()
from functools import wraps
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font

BASE_HEADERS=['序号','种类','数量','数量可信','名称','星级','部位','等级','主词条名称','主词条数值','副词条数',None]
HEADERS=BASE_HEADERS+sum(([f'副词条{i}名称',f'副词条{i}数值',f'副词条{i}档位']+([f'副词条{i}待激活'] if i==4 else []) for i in range(1,5)),[])+['套装']
STATE_HEADERS=['扫描次数','会话ID','开始时间','结束时间','状态','物品数']
VERSION_HEADERS=BASE_HEADERS+sum(([f'副词条{i}名称',f'副词条{i}档位']+([f'副词条{i}待激活'] if i==4 else []) for i in range(1,5)),[])+['套装']
MAIN_COLUMN=HEADERS.index('主词条数值')+1
LEVEL_INDEX=HEADERS.index('等级')

def version_values(item):
    result=base_values(item)
    for i in range(4):
        detail=item.get('副词条明细',[]);q=detail[i] if i<len(detail) else None
        result += [q['名称'],tier(item,q)] if q else ['','']
        if i==3:result += [q.get('待激活',False) if q and str(item.get('星级','')).startswith('5') else '']
    return result+[item.get('套装','')]


@lru_cache(maxsize=1)
def table():
    root=Path(os.environ.get('DOMAIN_RESOURCE_ROOT',Path(__file__).resolve().parents[1]))
    return json.loads((root/'Assets/原神/圣遗物数值/用户数值表.json').read_text(encoding='utf-8'))['副词条单档']


def tier(item,q):
    if item.get('等级')!='+0':return '强化累计值'
    match=re.search(r'[1-5]',str(item.get('星级','')))
    if not match:return ''
    raw=q['数值'];key=q['名称']+('%' if raw.endswith('%') else '')
    slots=table().get(match[0],{}).get(key,[])
    hits=[str(i+1) for i,v in enumerate(slots) if v is not None and v.endswith('%')==raw.endswith('%') and Decimal(v.rstrip('%'))==Decimal(raw.rstrip('%'))]
    return '/'.join(hits)+'档' if hits else '未匹配'


def main_stat(item):
    if '主词条名称' in item:return item['主词条名称'],item.get('主词条数值','')
    raw=item.get('主词条','');match=re.fullmatch(r'(.*?)\s+(\d+(?:\.\d+)?%?)',raw)
    if match:return match[1],match[2]
    if raw:raise ValueError('主词条不能拆分名称与数值：'+raw)
    return '',''


def number(raw):
    if not raw:return ''
    return float(raw[:-1])/100 if raw.endswith('%') else float(raw)


def base_values(item):
    name,value=main_stat(item)
    fields=dict(item,主词条名称=name,主词条数值=number(value))
    return [fields.get(key,'') for key in BASE_HEADERS]


def values(item):
    result=base_values(item)
    for i in range(4):
        detail=item.get('副词条明细',[]);q=detail[i] if i<len(detail) else None
        result += [q['名称'],number(q['数值']),tier(item,q)] if q else ['','','']
        if i==3:result += [q.get('待激活',False) if q and str(item.get('星级','')).startswith('5') else '']
    return result+[item.get('套装','')]


def formats(item):
    result={MAIN_COLUMN:'0.0%' if main_stat(item)[1].endswith('%') else '0.##'}
    for i,q in enumerate(item.get('副词条明细',[])):
        result[HEADERS.index(f'副词条{i+1}数值')+1]='0.0%' if q['数值'].endswith('%') else '0.##'
    return result


def version_formats(item):
    return {MAIN_COLUMN:formats(item)[MAIN_COLUMN]}


class FileSink:
    def __init__(self,path):
        self.path=Path(path)
        if self.path.suffix.lower()!='.xlsx':raise ValueError('目标必须为 .xlsx 文件')
        self.path.parent.mkdir(parents=True,exist_ok=True)
        self.saved_signature=self.signature()
        self.book=load_workbook(self.path) if self.path.exists() else Workbook()
        self.check_unchanged()
        if not self.path.exists():self.book.active.title='获得物'
    def ensure(self,name):
        return self.book[name] if name in self.book.sheetnames else self.book.create_sheet(name)
    def last(self,sheet):
        # 从后往前找有内容的行，忽略仅格式化的尾行；不填补中间空洞。
        for r in range(sheet.max_row,0,-1):
            if any(sheet.cell(r,c).value is not None for c in range(1,sheet.max_column+1)):return r
        return 0
    def rename(self,sheet,name):sheet.title=name
    def picture(self,sheet,row,path,reserve=False):
        from openpyxl.drawing.image import Image
        previous=sheet.row_dimensions[row].height if reserve else None
        image=Image(path);image.width=image.width*min(1,120/image.height);image.height=min(image.height,120)
        sheet.add_image(image,'A%d'%row);sheet.row_dimensions[row].height=image.height*.75+8
        return dict(object=image,row=row,previous_height=previous)
    def reposition_picture(self,sheet,picture,row):
        if picture['row']==row:return
        sheet.row_dimensions[picture['row']].height=picture['previous_height']
        picture['previous_height']=sheet.row_dimensions[row].height
        picture['object'].anchor='A%d'%row
        sheet.row_dimensions[row].height=picture['object'].height*.75+8
        picture['row']=row
    def read(self,sheet,row,col):return sheet.cell(row,col).value
    def read_rows(self,sheet,row,count,width):
        return [list(r) for r in sheet.iter_rows(min_row=row,max_row=row+count-1,max_col=width,values_only=True)]
    def write(self,sheet,row,data,fmt=None):
        for col,value in enumerate(data,1):sheet.cell(row,col).value=value
        self.format_row(sheet,row,fmt)
    def write_cells(self,sheet,row,col,data,fmt=None):
        for offset,value in enumerate(data):sheet.cell(row,col+offset).value=value
        self.format_row(sheet,row,fmt)
    def write_cell_block(self,sheet,row,col,data,fmt=None):
        for offset,values in enumerate(data):self.write_cells(sheet,row+offset,col,values,fmt)
    def format_row(self,sheet,row,fmt):
        for col,value in (fmt or {}).items():sheet.cell(row,col).number_format=value
    def format_block(self,sheet,row,formats):
        for offset,fmt in enumerate(formats):self.format_row(sheet,row+offset,fmt)
    def write_block(self,sheet,row,data):
        for offset,values in enumerate(data):self.write(sheet,row+offset,values)
    def style(self,sheet,row):
        for cell in sheet[row]:cell.font=Font(bold=True)
        from openpyxl.utils import get_column_letter
        for col,cell in enumerate(sheet[row],1):
            name=cell.value
            sheet.column_dimensions[get_column_letter(col)].width=4 if name is None else 26 if name in ('名称','套装','主词条名称') else 18
        sheet.freeze_panes='A2'
    def signature(self):
        if not self.path.exists():return None
        stat=self.path.stat()
        return stat.st_mtime_ns,stat.st_size,hashlib.sha256(self.path.read_bytes()).digest()
    def check_unchanged(self):
        if self.signature()!=self.saved_signature:
            raise RuntimeError('工作簿在外部被修改，请停止等待并重新连接，避免覆盖修改')
    def probe(self):
        self.check_unchanged()
        # 检查可写性而不重写工作簿。
        import win32file,win32con
        handle=win32file.CreateFile(str(self.path),win32con.GENERIC_READ|win32con.GENERIC_WRITE,0,None,win32con.OPEN_EXISTING,win32con.FILE_ATTRIBUTE_NORMAL,None)
        handle.Close()
    def save(self):
        self.check_unchanged()
        # openpyxl closes image streams loaded from existing XLSX after saving.
        # Refresh those streams on every save so later sessions can append.
        import io
        for sheet in self.book:
            for image in sheet._images:
                if not isinstance(image.ref,(str,Path)):
                    if not hasattr(image,'_scanner_bytes'):image._scanner_bytes=image._data()
                    image.ref=io.BytesIO(image._scanner_bytes)
        temp=self.path.with_name(self.path.stem+'.'+uuid.uuid4().hex+'.tmp.xlsx')
        try:
            self.book.save(temp)
            self.check_unchanged()
            os.replace(temp,self.path)
            self.saved_signature=self.signature();self.saved_stamp=self.path.stat().st_mtime_ns
            self.last_saved_at_ns=time.time_ns()
        finally:temp.unlink(missing_ok=True)


def com_retry(method):
    """Retry only explicitly rejected calls on idempotent cell operations."""
    @wraps(method)
    def call(*args,**kwargs):
        import pywintypes,pythoncom
        deadline=time.monotonic()+5;reported=False
        while True:
            try:return method(*args,**kwargs)
            except pywintypes.com_error as error:
                if error.hresult not in (-2147418111,-2147417846) or time.monotonic()>=deadline:raise
                if not reported:print('[表格忙] Excel/WPS暂时拒绝调用，最多等待5秒；未确认保存。',flush=True);reported=True
                pythoncom.PumpWaitingMessages();time.sleep(.1)
    return call

class ComSink:
    def __init__(self,path):
        import win32com.client as client
        self.path=Path(path).resolve()
        if self.path.suffix.lower()!='.xlsx':raise ValueError('目标必须为 .xlsx 文件')
        self.path.parent.mkdir(parents=True,exist_ok=True)
        self.book=None
        if self.path.exists():
            # 文件moniker GetObject(path)可能隐式打开隐藏窗口；只接入已有实例。
            for progid in ('Excel.Application','ket.Application','et.Application'):
                try:
                    app=client.GetActiveObject(progid)
                    for candidate in app.Workbooks:
                        if str(Path(candidate.FullName).resolve()).casefold()==str(self.path).casefold():
                            self.book=candidate;break
                except Exception:pass
                if self.book is not None:break
            if self.book is None:
                # 管理员扫描器可能无法访问普通权限Office的ROT；锁定则拒绝，不能另开只读副本。
                import win32file, win32con
                handle=win32file.CreateFile(str(self.path),win32con.GENERIC_READ|win32con.GENERIC_WRITE,
                    0,None,win32con.OPEN_EXISTING,win32con.FILE_ATTRIBUTE_NORMAL,None)
                handle.Close()
        if self.book is None:
            import winreg
            registered=[]
            for progid in ('Excel.Application','ket.Application','et.Application'):
                try:
                    with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT,progid):registered.append(progid)
                except FileNotFoundError:pass
            if not registered:
                raise RuntimeError('未找到可用的 Excel/WPS 桌面自动化接口。')
            errors=[]
            for progid in registered:
                try:
                    self.excel=client.DispatchEx(progid);break
                except Exception as error:errors.append(str(error))
            else:raise RuntimeError('已找到 Excel/WPS，但无法启动：'+'；'.join(errors))
            if self.path.exists():self.book=self.excel.Workbooks.Open(str(self.path))
            else:
                self.book=self.excel.Workbooks.Add()
                self.book.Worksheets(1).Name='获得物'
                self.book.SaveAs(str(self.path),FileFormat=51)
        self.excel=self.book.Application
        if self.book.ReadOnly:raise PermissionError('指定工作簿为只读或已被另一 Excel/WPS 实例锁定')
        self.show_target()
    @com_retry
    def show_target(self):
        if not self.excel.Visible:self.excel.Visible=True
        visible=False
        for window in self.book.Windows:
            if not window.Visible:
                window.Visible=True
                if not window.Visible:continue
            visible=True
        if not visible:
            raise RuntimeError('目标工作簿没有可见窗口，连接失败')
    def ensure(self,name):
        for sheet in self.book.Worksheets:
            if sheet.Name==name:return sheet
        sheet=self.book.Worksheets.Add(After=self.book.Worksheets(self.book.Worksheets.Count));sheet.Name=name;return sheet
    @com_retry
    def last(self,sheet):
        # Full-row formatting may extend UsedRange to 16,384 columns. Find
        # content inside Excel instead of transferring that rectangle over COM.
        # All options are explicit; no saved search state is inherited.
        cell=sheet.Cells.Find(What='*',After=sheet.Cells(1,1),LookIn=-4123,
            LookAt=2,SearchOrder=1,SearchDirection=2,MatchCase=False,
            MatchByte=False,SearchFormat=False)
        return int(cell.Row) if cell is not None else 0
    def rename(self,sheet,name):sheet.Name=name
    def picture(self,sheet,row,path,reserve=False):
        started=time.perf_counter()
        from PIL import Image
        with Image.open(path) as image:w,h=image.size
        decoded=time.perf_counter()
        scale=min(1,120/h);width=w*scale*.75;height=h*scale*.75
        target=sheet.Rows(row)
        previous=target.RowHeight if reserve else None
        target.RowHeight=height+8
        cell=sheet.Cells(row,1)
        left,top=float(cell.Left),float(cell.Top)
        positioned=time.perf_counter()
        shape=sheet.Shapes.AddPicture(str(Path(path).resolve()),False,True,left,top,width,height)
        print('[表格插图细分] '+json.dumps({'row':row,'at_ns':time.time_ns(),
            'image_info_seconds':round(decoded-started,4),'position_seconds':round(positioned-decoded,4),
            'add_picture_seconds':round(time.perf_counter()-positioned,4)},ensure_ascii=False),flush=True)
        return dict(object=shape,row=row,previous_height=previous)
    def reposition_picture(self,sheet,picture,row):
        if picture['row']==row:return
        source_row=picture['row'];source_height=picture['previous_height']
        shape=picture['object']
        @com_retry
        def read_target_height():return sheet.Rows(row).RowHeight
        target_height=read_target_height()
        @com_retry
        def apply_position():
            # Every retry uses the same pre-move heights. Commit the Python
            # anchor state only after all idempotent COM writes succeed.
            sheet.Rows(source_row).RowHeight=source_height
            cell=sheet.Cells(row,1)
            shape.Left=float(cell.Left);shape.Top=float(cell.Top)
            sheet.Rows(row).RowHeight=float(shape.Height)+8
        apply_position()
        picture.update(row=row,previous_height=target_height)
    @com_retry
    def read(self,sheet,row,col):return sheet.Cells(row,col).Value
    @com_retry
    def read_rows(self,sheet,row,count,width):
        return [list(r) for r in sheet.Range(sheet.Cells(row,1),sheet.Cells(row+count-1,width)).Value]
    @com_retry
    def write(self,sheet,row,data,fmt=None):
        sheet.Range(sheet.Cells(row,1),sheet.Cells(row,len(data))).Value=(tuple(data),)
        self.format_row(sheet,row,fmt)
    @com_retry
    def write_cells(self,sheet,row,col,data,fmt=None):
        sheet.Range(sheet.Cells(row,col),sheet.Cells(row,col+len(data)-1)).Value=(tuple(data),)
        self.format_row(sheet,row,fmt)
    @com_retry
    def write_cell_block(self,sheet,row,col,data,fmt=None):
        sheet.Range(sheet.Cells(row,col),sheet.Cells(row+len(data)-1,col+len(data[0])-1)).Value=tuple(tuple(r) for r in data)
        for offset in range(len(data)):self.format_row(sheet,row+offset,fmt)
    @com_retry
    def format_row(self,sheet,row,fmt):
        for col,value in (fmt or {}).items():sheet.Cells(row,col).NumberFormat=value
    @com_retry
    def format_block(self,sheet,row,formats):
        # Adjacent rows with the same number format share a single COM call.
        # Missing format entries break a run; never format unrelated cells.
        columns=sorted({col for fmt in formats for col in fmt})
        for col in columns:
            start=0
            while start<len(formats):
                value=formats[start].get(col)
                end=start+1
                while end<len(formats) and formats[end].get(col)==value:end+=1
                if value is not None:
                    sheet.Range(sheet.Cells(row+start,col),sheet.Cells(row+end-1,col)).NumberFormat=value
                start=end
    @com_retry
    def write_block(self,sheet,row,data):
        width=max(map(len,data));block=tuple(tuple(values)+('',)*(width-len(values)) for values in data)
        sheet.Range(sheet.Cells(row,1),sheet.Cells(row+len(data)-1,width)).Value=block
    @com_retry
    def style(self,sheet,row):
        header=sheet.Range(sheet.Cells(row,1),sheet.Cells(row,len(HEADERS)))
        header.Font.Bold=True;header.Columns.ColumnWidth=18
        sheet.Cells(row,12).EntireColumn.ColumnWidth=4
    @com_retry
    def probe(self):
        # 读取真实工作簿集合，不能只看消费进程是否还活着。
        names=[str(book.FullName).casefold() for book in self.excel.Workbooks]
        if str(self.path).casefold() not in names:raise RuntimeError('工作簿已关闭，连接已失效')
        if self.book.ReadOnly:raise PermissionError('工作簿已变为只读')
        if str(Path(self.book.FullName).resolve()).casefold()!=str(self.path).casefold():raise RuntimeError('工作簿路径改变，请重新连接')
        self.show_target()
    @com_retry
    def save(self):
        started=time.perf_counter();self.show_target();visible=time.perf_counter()
        self.book.Save()
        self.last_saved_at_ns=time.time_ns()
        print('[表格持久化] '+json.dumps({'seconds':round(time.perf_counter()-started,4),
            'visible_seconds':round(visible-started,4),'save_seconds':round(time.perf_counter()-visible,4),
            'at_ns':time.time_ns()},ensure_ascii=False),flush=True)


class JournalBook:
    def __init__(self,sink,sheet='获得物'):
        self.sink=sink;self.sheet=sink.ensure(sheet);self.state=sink.ensure('扫描状态');self.tiers=sink.ensure('档位版本')
        if sink.last(self.state)==0:sink.write(self.state,1,STATE_HEADERS)
        elif [sink.read(self.state,1,c) for c in range(1,7)]!=STATE_HEADERS:
            old=sink.read(self.state,1,1)
            if sink.last(self.state)==1 and isinstance(old,str) and old.startswith(('完整扫描','扫描失败','扫描中')):
                name='扫描状态_旧版_'+datetime.now().strftime('%H%M%S')
                sink.rename(self.state,name);self.state=sink.ensure('扫描状态');sink.write(self.state,1,STATE_HEADERS)
            else:raise ValueError('原工作簿的“扫描状态”工作表不是本工具格式，请选择其他工作簿')
        self.count=max([int(sink.read(self.state,r,1) or 0) for r in range(2,sink.last(self.state)+1)]+[0])
        self.active=None;sink.save()
    def single(self,session,success,items=None,save=True,started_at_ns=None,ended_at_ns=None):
        if self.active:raise ValueError('单卡会话与未完成整趟重叠')
        items=items or []
        if len(items)>1 or (success and len(items)!=1):raise ValueError('单卡结果必须恰好一件')
        self.count+=1;start_time=local_time(started_at_ns);end_time=local_time(ended_at_ns);started=start_time.isoformat(timespec='seconds')
        label=f'扫描第{self.count}次，开始（{start_time:%Y-%m-%d %H:%M:%S}）';end=f'扫描第{self.count}次，结束'+('' if success else '（失败，残表）')+f'（{end_time:%Y-%m-%d %H:%M:%S}）'
        first=self.sink.last(self.sheet)+1;tier_first=self.sink.last(self.tiers)+1
        self.sink.write_block(self.sheet,first,[[label],HEADERS]+[values(item) for item in items]+[[end]])
        self.sink.style(self.sheet,first+1)
        for offset,item in enumerate(items):self.sink.format_row(self.sheet,first+2+offset,formats(item))
        artifacts=[item for item in items if item.get('种类')=='圣遗物']
        self.sink.write_block(self.tiers,tier_first,[[label],VERSION_HEADERS]+[version_values(item) for item in artifacts]+[[end]])
        self.sink.style(self.tiers,tier_first+1)
        for offset,item in enumerate(artifacts):self.sink.format_row(self.tiers,tier_first+2+offset,version_formats(item))
        self.sink.write(self.state,self.sink.last(self.state)+1,[self.count,session,started,end_time.isoformat(timespec='seconds'),'完整扫描已通过校验' if success else '扫描失败：残表不可作为完整结果',len(items)])
        if save:self.sink.save()
    def begin(self,session,save=True,started_at_ns=None):
        if self.active:raise ValueError('上一趟尚未结束，不能交错追加扫描')
        self.count+=1;row=self.sink.last(self.sheet)+1;start_time=local_time(started_at_ns)
        self.sink.write(self.sheet,row,[f'扫描第{self.count}次，开始（{start_time:%Y-%m-%d %H:%M:%S}）'])
        self.sink.write(self.sheet,row+1,HEADERS);self.sink.style(self.sheet,row+1)
        tier_start=self.sink.last(self.tiers)+1
        self.sink.write(self.tiers,tier_start,[f'扫描第{self.count}次，开始（{start_time:%Y-%m-%d %H:%M:%S}）'])
        self.sink.write(self.tiers,tier_start+1,VERSION_HEADERS);self.sink.style(self.tiers,tier_start+1)
        status_row=self.sink.last(self.state)+1
        self.sink.write(self.state,status_row,[self.count,session,start_time.isoformat(timespec='seconds'),'','扫描中',0])
        self.active={'session':session,'start':row+2,'rows':{},'tier_rows':{},'status':status_row,'montage':None}
        if save:self.sink.save()
    def item(self,item,save=True):
        if not self.active:raise ValueError('没有扫描开始事件')
        index=int(item['序号'])
        if index not in self.active['rows']:
            self.active['rows'][index]=self.sink.last(self.sheet)+1
        self.sink.write(self.sheet,self.active['rows'][index],values(item),formats(item))
        self.version_item(item)
        if save:self.sink.save()
    def version_item(self,item):
        if item.get('种类')!='圣遗物':return
        index=int(item['序号'])
        if index not in self.active['tier_rows']:self.active['tier_rows'][index]=self.sink.last(self.tiers)+1
        self.sink.write(self.tiers,self.active['tier_rows'][index],version_values(item),version_formats(item))

    def prepare_montage(self,path,complete,expected_items):
        """Place one provisional picture without reserving data/marker cells."""
        if not self.active:raise ValueError('预置拼图没有对应的扫描会话')
        if type(expected_items)!=int or expected_items<0:raise ValueError('预置拼图物品数量无效')
        resolved=str(Path(path).resolve())
        prepared=self.active.get('prepared_montage')
        if prepared:
            if prepared['path']!=resolved:raise ValueError('同趟预置拼图路径发生变化')
            return
        row=self.active['start']+expected_items
        picture=self.sink.picture(self.sheet,row,resolved,reserve=True)
        self.active['prepared_montage']={'path':resolved,'picture':picture,'expected_items':expected_items}
        self.active['montage']=(resolved,complete)
        print('[表格拼图预置] '+json.dumps({'scan':self.count,'row':row,'expected_items':expected_items,
            'written_items':len(self.active['rows']),'at_ns':time.time_ns()},ensure_ascii=False),flush=True)

    def reconcile(self,sheet,rows,items,version=False):
        # Read actual workbook cells in contiguous blocks. Skip only unchanged
        # values, retaining final ordering and correcting changed/missing rows.
        width=len(VERSION_HEADERS if version else HEADERS);actual={};start=0
        while start<len(rows):
            end=start+1
            while end<len(rows) and rows[end]==rows[end-1]+1:end+=1
            block=self.sink.read_rows(sheet,rows[start],end-start,width)
            actual.update(zip(rows[start:end],block));start=end
        def normalized(values):return [('bool',v) if isinstance(v,bool) else None if v=='' else v for v in values]
        patches={}
        for row,item in zip(rows,items):
            desired=version_values(item) if version else values(item)
            observed=list(actual[row])
            # Excel coerces an assigned '+0' level to numeric 0. Only this
            # schema column accepts that equivalence; names/digits still compare
            # exactly, and a changed level must still trigger reconciliation.
            level=desired[LEVEL_INDEX]
            if isinstance(level,str) and re.fullmatch(r'\+\d+',level) and type(observed[LEVEL_INDEX]) in (int,float) and observed[LEVEL_INDEX]==int(level):
                observed[LEVEL_INDEX]=level
            if normalized(observed)!=normalized(desired):
                fmt=version_formats(item) if version else formats(item)
                changed=[i for i,(a,b) in enumerate(zip(normalized(observed),normalized(desired))) if a!=b]
                for start in changed:
                    if start and start-1 in changed:continue
                    end=start+1
                    while end in changed:end+=1
                    selected=tuple((c,v) for c,v in fmt.items() if start<c<=end)
                    patches.setdefault((start+1,end,selected),[]).append((row,desired[start:end]))
        for (col,_,fmt),changes in patches.items():
            start=0
            while start<len(changes):
                end=start+1
                while end<len(changes) and changes[end][0]==changes[end-1][0]+1:end+=1
                self.sink.write_cell_block(sheet,changes[start][0],col,[v for _,v in changes[start:end]],dict(fmt))
                start=end

    def end(self,success,items=None,ended_at_ns=None):
        if not self.active:raise ValueError('没有扫描开始事件')
        phases={};stamp=time.perf_counter()
        def phase(name):
            nonlocal stamp
            now=time.perf_counter();phases[name]=round(now-stamp,4);stamp=now
        if items is not None:
            ordered=sorted(items,key=lambda q:q['序号'])
            # 终态批量回填后只保存一次，避免对每件再执行一轮慢Save。
            for sheet,key,selected,version in (
                (self.sheet,'rows',ordered,False),
                (self.tiers,'tier_rows',[q for q in ordered if q.get('种类')=='圣遗物'],True)):
                missing=[q for q in selected if int(q['序号']) not in self.active[key]]
                if not missing:continue
                first=self.sink.last(sheet)+1
                data=[version_values(q) if version else values(q) for q in missing]
                fmts=[version_formats(q) if version else formats(q) for q in missing]
                self.sink.write_block(sheet,first,data)
                self.sink.format_block(sheet,first,fmts)
                self.active[key].update({int(q['序号']):first+i for i,q in enumerate(missing)})
            phase('补齐缺失条目')
            tier_items=[item for item in ordered if item.get('种类')=='圣遗物']
            tier_owned=sorted(self.active['tier_rows'].values())
            if len(tier_owned)!=len(tier_items):raise ValueError('档位版本与最终圣遗物数量不一致')
            self.reconcile(self.tiers,tier_owned,tier_items,version=True)
            phase('档位终态核对回填')
            owned=sorted(self.active['rows'].values())
            if len(owned)!=len(ordered):raise ValueError('逐件事件与最终结果物品数不一致')
            self.reconcile(self.sheet,owned,ordered)
            self.active['rows']={int(item['序号']):row for row,item in zip(owned,ordered)}
            phase('原值终态核对回填')
        label=f'扫描第{self.count}次，结束'+('' if success else '（失败，残表）')+f'（{local_time(ended_at_ns):%Y-%m-%d %H:%M:%S}）'
        if self.active.get('montage'):
            path,complete=self.active['montage'];picture_row=self.sink.last(self.sheet)+1
            # The image owns a blank row; captions and end markers follow it.
            self.sink.write_block(self.sheet,picture_row+1,[['横排截图拼图'+('' if complete else '（未扫完整）')],[label]])
            prepared=self.active.get('prepared_montage')
            if prepared:
                if prepared['path']!=str(Path(path).resolve()):raise ValueError('最终拼图与预置路径不一致')
                original_row=prepared['picture']['row']
                self.sink.reposition_picture(self.sheet,prepared['picture'],picture_row)
                print('[表格拼图定位复核] '+json.dumps({'scan':self.count,'predicted_row':original_row,
                    'final_row':picture_row,'moved':original_row!=picture_row,'items':len(self.active['rows'])},ensure_ascii=False),flush=True)
            else:self.sink.picture(self.sheet,picture_row,path)
        else:self.sink.write(self.sheet,self.sink.last(self.sheet)+1,[label])
        phase('拼图插入')
        self.sink.write(self.tiers,self.sink.last(self.tiers)+1,[label])
        row=self.active['status']
        self.sink.write(self.state,row,[self.count,self.active['session'],self.sink.read(self.state,row,3),local_time(ended_at_ns).isoformat(timespec='seconds'),'完整扫描已通过校验' if success else '扫描失败：残表不可作为完整结果',len(self.active['rows'])])
        self.active=None
        phase('结束标记及状态')
        self.sink.save()
        phase('工作簿持久化')
        print('[表格收尾细分] '+json.dumps({'scan':self.count,'at_ns':time.time_ns(),'phases':phases},ensure_ascii=False),flush=True)


def write_xlsx(items,path,status='完整扫描已通过校验',sheet='获得物',montage=None):
    book=JournalBook(FileSink(path),sheet);book.begin(datetime.now().astimezone().isoformat())
    if montage:book.active['montage']=(montage,True)
    book.end('失败' not in status,items)


def closing_event_pending(stream,limit=4,max_line=256*1024):
    """Bounded lookahead, without consuming or reordering journal events.

    An already-published closing event owns the next durable save. Avoid saving
    the partial rows immediately before that event's save. Never wait for a
    future event, cross a new session/probe, or suppress an idle periodic save."""
    position=stream.tell()
    try:
        for _ in range(limit):
            line=stream.readline(max_line+1)
            if len(line)>max_line or not line.endswith('\n'):return False
            try:kind=json.loads(line)['event']
            except (ValueError,KeyError,TypeError):return False
            if kind in ('complete','failed'):return True
            if kind not in ('item','montage'):return False
        return False
    finally:stream.seek(position)


def watch(events,output,live=False,sheet='获得物',persistent=False):
    # Observe the exact owning GUI process handle, not a reusable PID.
    owner_handle=None
    if os.name=='nt' and os.environ.get('DOMAIN_OWNER_PID'):
        import ctypes
        kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        kernel.OpenProcess.restype=ctypes.c_void_p
        kernel.WaitForSingleObject.argtypes=[ctypes.c_void_p,ctypes.c_ulong]
        owner_handle=kernel.OpenProcess(0x100000,False,int(os.environ['DOMAIN_OWNER_PID']))
        if not owner_handle:raise RuntimeError('无法监测扫描器主进程；未打开工作簿')
    sink=None
    if live:
        try:sink=ComSink(output)
        except Exception:
            # 桌面连接失败不能静默切换文件写入，避免错误覆盖用户文件。
            raise
    if sink is None:sink=FileSink(output)
    book=JournalBook(sink,sheet);offset=0;dirty_since=None
    Path(str(events)+'.ready').write_text(json.dumps({'scan':book.count,'path':str(sink.path),'mode':'桌面Excel/WPS' if isinstance(sink,ComSink) else 'XLSX文件（不要打开锁定）'},ensure_ascii=False),encoding='utf-8')
    while True:
        if owner_handle and kernel.WaitForSingleObject(owner_handle,0)!=0x102:
            if book.active:book.end(False)
            print('扫描器主进程已退出，表格消费者退出；不关闭用户Excel/WPS。',flush=True)
            return 0
        if Path(events).exists():
            with open(events,encoding='utf-8') as f:
                f.seek(offset)
                while True:
                    start=f.tell();line=f.readline()
                    if not line:break
                    if not line.endswith('\n'):f.seek(start);break
                    event=json.loads(line);kind=event['event'];event_started=time.perf_counter();received_at_ns=time.time_ns()
                    if kind=='probe':
                        reply={'id':event['id'],'ok':False,'path':str(sink.path),'mode':'桌面Excel/WPS' if isinstance(sink,ComSink) else 'XLSX文件写入（目标必须关闭）'}
                        try:
                            sink.probe();reply['ok']=True
                        except Exception as error:reply['error']=str(error)
                        Path(str(events)+'.probe').write_text(json.dumps(reply,ensure_ascii=False),encoding='utf-8')
                        continue
                    if kind=='shutdown':
                        if book.active:book.end(False)
                        return 0
                    if kind=='single_batch':
                        try:
                            if book.active:raise RuntimeError('批量单卡与未完成整趟重叠')
                            scans=event['scans']
                            if not scans or len(scans)>20:raise ValueError('批量单卡须为1至20件')
                            for scan in scans:book.single(scan['session'],scan['success'],scan.get('items'),save=False,started_at_ns=scan.get('started_at_ns'),ended_at_ns=scan.get('ended_at_ns'))
                            sink.save()
                            dirty_since=None
                        except Exception as error:
                            Path(str(events)+'.ack').write_text(json.dumps({'id':event['id'],'event':kind,'ok':False,'error':str(error)},ensure_ascii=False),encoding='utf-8');raise
                        Path(str(events)+'.ack').write_text(json.dumps({'id':event['id'],'event':kind,'ok':True,'count':len(scans)}),encoding='utf-8')
                        print('[表格事件] '+json.dumps({'event':kind,'count':len(scans),'seconds':round(time.perf_counter()-event_started,4)},ensure_ascii=False),flush=True)
                        continue
                    if kind=='begin':
                        book.begin(event['session'],started_at_ns=event.get('started_at_ns'))
                        Path(str(events)+'.started').write_text(json.dumps({'session':event['session']}),encoding='utf-8')
                    elif kind=='item':
                        if not book.active:book.begin(event.get('session','单次扫描'))
                        book.item(event['item'],save=False)
                        published=event.get('published_at_ns')
                        print('[表格条目消费] '+json.dumps({'session':event.get('session'),
                            'index':event['item']['序号'],'received_at_ns':received_at_ns,
                            'published_at_ns':published,'ready_at_ns':event.get('ready_at_ns'),
                            'queue_seconds':(received_at_ns-published)/1e9 if published is not None else None,
                            'write_seconds':time.perf_counter()-event_started},ensure_ascii=False),flush=True)
                        if dirty_since is None:dirty_since=time.monotonic()
                    elif kind=='montage_prepare':
                        book.prepare_montage(event['path'],bool(event.get('完整')),event['expected_items'])
                    elif kind=='montage':
                        if not book.active:raise RuntimeError('拼图没有对应的扫描会话')
                        book.active['montage']=(event['path'],bool(event.get('完整')))
                    elif kind in ('complete','failed','single_complete','single_failed'):
                        atomic_single=kind.startswith('single_')
                        if atomic_single and book.active:raise RuntimeError('单卡会话与未完成整趟重叠；拒绝交错写入')
                        try:
                            if atomic_single:book.single(event['session'],kind=='single_complete',event.get('items'),started_at_ns=event.get('started_at_ns'),ended_at_ns=event.get('ended_at_ns',event.get('queued_at_ns')))
                            else:
                                if not book.active:book.begin(event.get('session','单次扫描'))
                                book.end(kind=='complete',event.get('items'),ended_at_ns=event.get('ended_at_ns',event.get('queued_at_ns')))
                            dirty_since=None
                        except Exception as error:
                            Path(str(events)+'.ack').write_text(json.dumps({'id':event.get('id'),'event':kind,'ok':False,'error':str(error)},ensure_ascii=False),encoding='utf-8')
                            raise
                        Path(str(events)+'.ack').write_text(json.dumps({'id':event.get('id'),'scan':book.count,'event':kind,'ok':True,
                            'saved_at_ns':getattr(sink,'last_saved_at_ns',None),'ack_emitted_at_ns':time.time_ns()}),encoding='utf-8')
                        queued=event.get('queued_at_ns')
                        print('[表格事件] '+json.dumps({'event':kind,'seconds':round(time.perf_counter()-event_started,4),'scan':book.count,
                            'received_at_ns':received_at_ns,'queue_seconds':(received_at_ns-queued)/1e9 if queued is not None else None},ensure_ascii=False),flush=True)
                        if not persistent:return 0 if kind in ('complete','single_complete') else 1
                    if (dirty_since is not None and time.monotonic()-dirty_since>=.5
                            and not closing_event_pending(f)):
                        sink.save();dirty_since=None
                offset=f.tell()
        if dirty_since is not None and time.monotonic()-dirty_since>=.5:
            sink.save();dirty_since=None
        time.sleep(.01 if book.active else .05)


from scan_timing import instrument_class as _instrument_class
_instrument_class(ComSink,['last','picture','reposition_picture','read','read_rows','write','write_cells',
    'write_cell_block','format_row','format_block','write_block','style','probe','show_target','save'])
_instrument_class(FileSink,['picture','reposition_picture','read_rows','write_cell_block','save'])
_instrument_class(JournalBook,['begin','item','reconcile','end','single','prepare_montage'])

def main():
    ap=argparse.ArgumentParser();ap.add_argument('json',nargs='?');ap.add_argument('--output');ap.add_argument('--watch');ap.add_argument('--live-excel',action='store_true');ap.add_argument('--sheet',default='获得物');ap.add_argument('--persistent',action='store_true');a=ap.parse_args()
    if a.watch:return watch(a.watch,a.output,a.live_excel,a.sheet,a.persistent)
    if not a.json:ap.error('请提供格式化JSON')
    source=Path(a.json);data=json.loads(source.read_text(encoding='utf-8'));write_xlsx(data['获得物'],a.output or source.with_suffix('.xlsx'),sheet=a.sheet,montage=data.get('横排拼图'));return 0
if __name__=='__main__':raise SystemExit(main())
