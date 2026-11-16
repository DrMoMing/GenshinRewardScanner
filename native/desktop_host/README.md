# 原生WPF桌面前端

当前为0.3.0-preview.9。HTML/CSS作为视觉规格，由MainWindow.xaml和NativeIllustrations.xaml实现原生布局、字体、控件及图解。没有浏览器运行库。

## 组成

- NativeDesktopHost.cs负责WPF窗口、状态绑定、快捷键录入、文件选择及消息往返。
- NativeLayoutDemo.cs负责独立演示数据，和正式窗口使用同一套控件。
- MainWindow.xaml包含主页、空间、设置、教程与许可四页。
- NativeIllustrations.xaml包含三幅矢量图解。
- brand.ico由既有IconLogo几何生成，各程序使用同一图标。
- preview.json包含12个批次、4类错误与性能样例。
- LAYOUT.md记录布局元素和控件名称。

## 运行边界

正式入口由portable/scanner_session.py建立无窗口SessionLoop，复用既有扫描、识别、工作簿服务与动作边界中止。生产入口不创建Tk根窗口，不调用旧快捷键/关于/文件选择对话框。

WPF通过标准输入输出发送白名单消息。状态快照合并，动作回执保留请求编号。文件和任务操作由Python服务执行。文件选择框属于WPF窗口，快捷键直接在设置页输入，Esc取消，失焦取消；保存时检查重复和系统占用。

任务快捷键必须全部注册成功且线程消息自检通过才进入等待。失败由注册线程先释放本次成功项再发失败回执，包含具体键、Win32错误码和线程编号。监听期间异常按监听实例判归属，不因扫描任务编号更新而漏掉。相关事件同时记录到程序日志与扫描日志。

声音参数为capture/success/failure。Python保留screenshot/complete兼容别名。三个独立播放通道避免截图音等待识别音。

## 布局

- 默认1100×800 DIP，最小940×710 DIP。
- 标题栏46 DIP，侧栏214 DIP，基础字体Microsoft YaHei UI。
- 自定义WindowChrome支持拖动、缩放、最小化、最大化和关闭。
- 教程使用页面外层滚动，不再嵌套正文滚动。
- Toast在窗口底部，自动换行；窗口内确认层覆盖全部内容。
- 六组快捷键集中在设置页，没有额外“编辑快捷键”入口。
- 浮窗显示、锁定、任务期间自动锁定均有真实开关。
- 许可页显示版本和原始许可文件清单。点击项打开所属文件夹，原文件独立保留，不在页面拼接或转换原文。

## 状态与动作

设置包括路数、星级、横排读字、工作簿、提示音、浮窗显示/性能/透明度/捕获排除/锁定/自动锁定、清理策略。编辑期间保留本地输入，失焦后应用后端值。

prepare/cancel/stop/check_memory/refresh_target/refresh_space/open_output/cleanup_batches/export_error/convert_json/preview_sound/update_shortcuts/documents/open_licenses/open_license_folder/save_preferences为后端动作。convert_json和export_error由WPF先取得路径，再交后端处理。动作以action_result回执解除pending，documents通过回执data返回实际文件清单；打开文件夹只能位于随包LICENSES内部。

关闭交回任务所有者，在动作边界安全结束。前端意外断开时先中止任务、等待单卡和文件IO收口，再回收监听、模型和浮窗。没有前端时清理失败会记录原因并退出，不保留孤立窗口。

## 演示

双击发行目录的界面演示.exe。它不启动Python，不连接游戏或Excel。批次清理等操作只改变内存中的示例。关闭重开恢复原演示数据。

## 构建与验证

执行experiments/game_overlay/build_native_host.py，使用系统.NET Framework 4.8工具链编译所有本目录C#源文件，目标winexe，并嵌入brand.ico。运行资产包括两份XAML、图标和preview.json。

实际隐藏桌面验证包含四页两档渲染、真实控件回执、焦点恢复、WPF文件选择归属与取消、原位快捷键捕获与Esc、独立演示的保护批次及提示框尺寸。产品EXE另做冻结回归和安装验证，证据见docs/STATUS.md。

源码/隐藏桌面验证不代替用户可见体验、跨屏DPI、真实游戏和Office联动验收。
