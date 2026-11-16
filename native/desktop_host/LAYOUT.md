# 原生 WPF 布局交接

preview6补充：许可页改为VersionText（TextBlock）、OpenLicensesFolder按钮及LicenseFilesPanel文件清单，点击条目打开所属文件夹，原始文件不转换。LicenseText、CopyrightText、ComponentsText已移除。功能实现见README.md。

下列为preview5时Harness的布局交接历史，只说明当轮的布局、控件名称和Codex需要接线的字段。当轮只修改：

- MainWindow.xaml
- NativeIllustrations.xaml
- 本 LAYOUT.md

NativeDesktopHost.cs 未改；portable、HTML/CSS/JS、安装代码未改。

## 控件名称变化

### 新增 x:Name

- OverlayLockToggle
  - 类型：ToggleButton
  - 绑定：IsChecked="{Binding Settings.OverlayLocked, Mode=TwoWay}"
  - 用途：设置页“锁定浮窗”的实际开关。
- OverlayAutoLockToggle
  - 类型：ToggleButton
  - 绑定：IsChecked="{Binding Settings.OverlayAutoLock, Mode=TwoWay}"
  - 用途：设置页“任务期间自动临时锁定”的实际开关。
- ShortcutCaptureStatus
  - 类型：TextBlock
  - 用途：本窗口快捷键录入说明和保存回执状态。
- VersionText
  - 类型：TextBox，IsReadOnly
  - 当前绑定：Text="{Binding AppVersion}"
  - 用途：许可页“版本”独立内容区。
- LicenseText
  - 类型：TextBox，IsReadOnly，多行
  - 用途：许可证原文独立内容区，由 Codex 填真实资料。
- CopyrightText
  - 类型：TextBox，IsReadOnly，多行
  - 用途：版权声明独立内容区，由 Codex 填真实资料。
- ComponentsText
  - 类型：TextBox，IsReadOnly，多行
  - 用途：第三方组件清单独立内容区，由 Codex 填真实资料。

### 删除 x:Name

- OpenAbout
  - 旧许可页的“打开许可证与关于”按钮已删除。
  - NativeDesktopHost.cs 目前仍有 Find<Button>("OpenAbout") 和 about 动作，需 Codex 同步删除/调整，否则构造函数会因找不到控件失败。
- GuideScroll
  - 文字教程内部 ScrollViewer 已删除；现在只有外层 PageHelp ScrollViewer 滚动。
  - 教程索引按钮仍保留，定位仍用文章元素的 BringIntoView。
- OpenShortcutEditor
  - “编辑快捷键”旧按钮已删除，不再弹旧 Tk 快捷键窗口。
  - NativeDesktopHost.cs 目前仍有 Find<Button>("OpenShortcutEditor") 事件，需 Codex 同步删除/替换。
- OverlayLockBadge（只是绑定引用，不是 x:Name）
  - 已从设置页浮窗区删除静态状态文本绑定。

### 保留的既有控件

- 六个快捷键输入框：ShortcutFullBox、ShortcutSingleBox、ShortcutPuzzleBox、ShortcutAbortBox、ShortcutStopBox、ShortcutOverlayBox。
  - 全部仍是 readOnly TextBox，作为按键捕获入口。
- ResetShortcuts
  - 保留“恢复默认”按钮。
- AutoKeepBatches、AutoKeepMinus、AutoKeepPlus、AutoKeepDays
  - 批数左右步进、手输和 1/3/7/15/30 下拉保持。
- TabPictures、TabGuide、TabLicense
  - 教程子页保留。

## 绑定变化

### 新增绑定

- OverlayLockToggle.IsChecked -> Settings.OverlayLocked
- OverlayAutoLockToggle.IsChecked -> Settings.OverlayAutoLock

这两个字段目前不在 NativeDesktopHost.cs 的 SettingsViewModel 中；Codex 需补 bool 属性并接设置变更/回执。控件绑定已经写好。

### 删除/调整绑定

- 设置页浮窗区不再显示 OverlayLockBadge。
- 许可页不再使用 AppVersion 的单一占位行；版本改为 VersionText 的 TextBox 绑定 AppVersion。
- 许可证、版权、第三方组件清单不使用绑定，由 Codex 直接设置 TextBox.Text。
- Toast 仍使用 ToastText；仅调整层级和换行。
- ShortcutCaptureStatus 不使用绑定，由 Codex 更新 Text。

## DataContext 字段清单（仅布局所需）

### Settings

- OverlayVisible（已有）
- OverlayPerformance（已有）
- OverlayOpacity（已有）
- OverlayExclude（已有）
- OverlayLocked（新增，bool）
- OverlayAutoLock（新增，bool）
- ShortcutFull/Single/Puzzle/Abort/Stop/Overlay（已有）
- SingleWorkers、RowInfo、WorkbookPath、Sheet、LiveExcel、Sound、AutoCleanup、CleanupMode、KeepBatches、KeepDays 等保持现有字段。

### Host

- AppVersion（已有）
- 许可页文本由 Codex 直接写 VersionText/LicenseText/CopyrightText/ComponentsText。

### 快捷键状态

- ShortcutCaptureStatus 的 Text 由 Codex 在按键捕获、Esc 取消、恢复默认、保存回执时设置。
- 六个 Shortcut*Box 的文本仍由 Settings.Shortcut* 绑定提供；Codex 在捕获后更新对应设置并刷新。

## 布局调整

- 品牌/窗口标题/浮窗预览名称统一为“原神副本扫描器”。
- 标题栏和浮窗预览都使用现有绿色品牌 Logo Path（IconLogo）；没有新增图标资源。
- 设置页右上角“自动保存”徽标删除。
- 教程页右上角“随包教程”徽标删除。
- 许可页拆成四块独立内容卡：
  - 版本
  - 许可证
  - 版权声明
  - 第三方组件清单
- 许可页删除旧“关于”按钮、教程/技术实现解释和“在关于窗口查看”的占位说明。
- 文字教程移除内部 ScrollViewer/固定高度，仅保留 PageHelp 外层滚动；索引仍可 BringIntoView。
- Toast 设 Grid.RowSpan=2，跨标题栏和内容两行；MaxWidth=680、TextWrapping=Wrap，底部居中，不挡标题栏关闭按钮。
- 声音说明：
  - 截图成功：低通快门
  - 任务完成：四音完成提示
  - 失败：四音失败提示
- 天数下拉仍是 1/3/7/15/30；批数左右步进和手工输入保持。

## Codex 接线清单

1. NativeDesktopHost.cs 删除 OpenAbout 的 Find/Click 和 about 动作（或改成新的许可证加载逻辑）。
2. 删除 OpenShortcutEditor 的 Find/Click；改为六个 Shortcut*Box 的本窗口按键捕获。
3. SettingsViewModel 增加 OverlayLocked、OverlayAutoLock，并在设置变更事件中保存/回执。
4. 按键捕获：
   - 点击 Shortcut*Box 进入捕获状态；
   - 按 Esc 取消；
   - 合法组合更新对应设置并显示 ShortcutCaptureStatus 回执；
   - ResetShortcuts 恢复默认；
   - 不再打开旧 Tk 快捷键窗口。
5. 许可页：
   - 读取真实随包资料后设置 VersionText.Text、LicenseText.Text、CopyrightText.Text、ComponentsText.Text；
   - 四个 TextBox 均保持 IsReadOnly。
6. Toast：
   - 根布局两行，Toast 已 Grid.RowSpan=2；
   - Codex 只需设置 ToastText.Text/Visibility。
7. 教程索引仍用文章元素 BringIntoView，不再依赖 GuideScroll。

## 静态检查

- 两份 XAML XML 良构解析通过。
- MainWindow.xaml 使用无显示 XamlReader 装载通过，未启动可见窗口。
- 未编译 NativeDesktopHost.cs：它仍有旧的 OpenAbout/OpenShortcutEditor 引用，按用户职责由 Codex 修复。
- 未启动可见 GUI、UAC、游戏或安装。

## 未验证

- Codex 完成宿主接线后的实际按键捕获、Esc 取消、恢复默认、保存回执。
- 许可文本真实内容与长文本滚动观感。
- 设置页两个新 ToggleButton 的实际设置回执。
- Toast 长文本在 1100/940 下的最终视觉位置；已设置换行和跨行层，仍需真实渲染确认。
