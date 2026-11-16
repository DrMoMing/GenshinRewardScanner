"""User progress messages derived from scanner diagnostics; never hide unknown errors."""
import re
import json

def clean_line(value):
    value=value.replace('\x00','')
    return re.sub(r'\x1b\[[0-9;]*[A-Za-z]','',value).strip()

def scan_message(value):
    text=clean_line(value[:4000])
    if not text:return None
    if text.startswith(('[扫描计时]','[收尾时间点]','[双路测量]')):return None
    if text.startswith(('[拼图后台] {','[截图失败] {')):return None
    if text.startswith('[拼图后台] 原始截图存储积压'):
        return '截图存储暂时跟不上，正在等待落盘；不会丢帧，可中止。'
    if text.startswith('[资源保护]'):
        try:data=json.loads(text.split(' ',1)[1])
        except (ValueError,IndexError):return '资源保护状态已记录。'
        if data['event']=='waiting':return '内存或系统提交额度不足，后台识别暂停等待；已截图任务仍保留，可中止。'
        if data['event']=='resumed':return '资源恢复，继续识别（等待%.1f秒）。'%data['wait_seconds']
        if data['event']=='worker_budget':
            requested,effective=data['requested'],data['effective']
            return ('内存余量不足以启用%d路，已自动降为%d路；任务将继续。'%(requested,effective) if 0<effective<requested else '资源预算：请求%d路，允许%d路。'%(requested,effective))
        return None
    if text.startswith('❌'):
        return '扫描失败：'+text.lstrip('❌ ').split('，证据=')[0][:350]
    if any(token in text for token in ('失败','Error','Exception','Traceback','ERROR','错误','异常')):
        return text.replace('**','')
    if text.startswith('[端点试验] '):
        try:
            data=json.loads(text.split(' ',1)[1])
            verdict={'外侧有卡':'外侧仍有卡片','外侧无卡':'外侧未见卡片','不明确':'端点尚未确认'}
            if type(data.get('拖动序号')) is int and isinstance(data.get('新判据'),str) and data['新判据'] in verdict:
                return '第%d次拖动：%s。'%(data['拖动序号'],verdict[data['新判据']])
        except (ValueError,AttributeError):
            pass # Preserve an unfamiliar diagnostic instead of losing it.
    if 'Removing initializer' in text and 'onnxruntime' in text:return None
    if text.startswith(('OCR 引擎加载','[输入]','[耗时]','行首确认：图标','行首材料双图标','本次截图独立保存','走一步：','详情独立缩放')):return None
    if text.startswith(('ℹ️ 上一步滞留','⚠️ 上一步滞留','上一步滞留')):return None
    if text.startswith('副本结算页模块') or re.match(r'^\d+\.',text) or text.startswith(('分布：','共 **','共 ','ℹ️ 视口边缘','视口边缘有','⚠️ 格点')):return None
    match=re.search(r'\[后台OCR\] 索引 (\d+)：(.*?)，副词条(\d+)条',text)
    if match:return '已识别第%s件：%s（%s条副词条）'%match.groups()
    match=re.search(r'\[筛选\] 索引(\d+)：.*?未勾选(\d)星',text)
    if match:return '跳过第%s件：%s星（未选择）'%match.groups()
    match=re.match(r'屏 (\d+)：完整 (\d+) 张.*新卡 (\d+) 张',text)
    if match:return '第%s屏：%s个完整卡位，新增%s件'%match.groups()
    if '门通过：' in text:return '已确认获得页面。'
    if '行首已确认：' in text:return '已到奖励行起点。'
    if '白边δ≈0' in text:return '已到奖励行末尾，正在汇总。'
    if '回行首第' in text:return '正在返回奖励行起点。'
    if text.startswith('⛔ 本次'):
        return '扫描失败，未生成完整JSON；失败状态及诊断已保留。'
    if text.startswith('❌'):
        message=text.lstrip('❌ ').split('，证据=')[0]
        return '扫描失败：'+message[:350]
    if text.startswith('⚠️ 若刚才是'):return '扫描已停止；请确认奖励页面仍在，再重新开始。'
    if text.startswith(('导出 →','契约 →','导出：','契约：','✅ 读过：','读过：')):return None
    return text.replace('**','')
