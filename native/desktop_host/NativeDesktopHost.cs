// Required Notice: Copyright (c) 2026 DrMoMing (https://github.com/DrMoMing/GenshinRewardScanner)
// SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
// AI-generated project code: written and modified with OpenAI Codex.
using System;
using System.Collections;
using System.Collections.Generic;
using System.Collections.ObjectModel;
using System.ComponentModel;
using System.IO;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading;
using System.Web.Script.Serialization;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Controls.Primitives;
using System.Windows.Data;
using System.Windows.Input;
using System.Windows.Markup;
using System.Windows.Media;
using System.Windows.Media.Imaging;
using System.Windows.Threading;

[assembly: System.Runtime.Versioning.TargetFramework(".NETFramework,Version=v4.8", FrameworkDisplayName = ".NET Framework 4.8")]
[assembly: AssemblyTitle("原神副本扫描器")]
[assembly: AssemblyDescription("原神副本扫描器")]

namespace NativeWpf
{
    public static class NativeDesktopProgram
    {
        [STAThread]
        public static void Main(string[] args)
        {
            try
            {
                try { Console.OutputEncoding = new UTF8Encoding(false); } catch { }
                string directory = AppDomain.CurrentDomain.BaseDirectory;
                bool preview=Array.IndexOf(args,"--preview")>=0 || Path.GetFileNameWithoutExtension(Environment.GetCommandLineArgs()[0])=="界面演示";
                if (!File.Exists(Path.Combine(directory,"MainWindow.xaml"))) directory=Path.Combine(directory,"_运行依赖","desktop_host");
                Application application = new Application();
                application.ShutdownMode = ShutdownMode.OnMainWindowClose;
                ResourceDictionary illustrations = LoadDictionary(Path.Combine(directory, "NativeIllustrations.xaml"));
                Window window = (Window)LoadXaml(Path.Combine(directory, "MainWindow.xaml"));
                window.Icon=BitmapFrame.Create(new Uri(Path.Combine(directory,"brand.ico")));
                HostViewModel model = new HostViewModel();
                window.DataContext = model;
                NativeDesktopHost host = new NativeDesktopHost(window, model, illustrations,preview);
                if (preview) window.Title="原神副本扫描器 · 演示数据";
                application.Run(window);
            }
            catch (Exception error)
            {
                try { Console.Error.WriteLine("native WPF startup failed: " + error); } catch { }
                Environment.ExitCode = 1;
            }
        }

        static ResourceDictionary LoadDictionary(string path)
        {
            using (FileStream stream = File.OpenRead(path))
            {
                ParserContext context = new ParserContext();
                context.BaseUri = new Uri(Path.GetDirectoryName(path) + Path.DirectorySeparatorChar);
                return (ResourceDictionary)XamlReader.Load(stream, context);
            }
        }

        static object LoadXaml(string path)
        {
            using (FileStream stream = File.OpenRead(path))
            {
                ParserContext context = new ParserContext();
                context.BaseUri = new Uri(Path.GetDirectoryName(path) + Path.DirectorySeparatorChar);
                return XamlReader.Load(stream, context);
            }
        }
    }

    public abstract class NotifyBase : INotifyPropertyChanged
    {
        public event PropertyChangedEventHandler PropertyChanged;
        protected bool Set<T>(ref T field, T value, string name)
        {
            if (EqualityComparer<T>.Default.Equals(field, value)) return false;
            field = value;
            Raise(name);
            return true;
        }
        protected void Raise(string name)
        {
            PropertyChangedEventHandler handler = PropertyChanged;
            if (handler != null) handler(this, new PropertyChangedEventArgs(name));
        }
    }

    public sealed class SettingChangedEventArgs : EventArgs
    {
        public string Name { get; private set; }
        public object Value { get; private set; }
        public SettingChangedEventArgs(string name, object value) { Name = name; Value = value; }
    }

    public sealed class RuntimeViewModel : NotifyBase
    {
        string _title = "尚未启动", _chip = "空闲", _tone = "idle", _detail, _hint;
        string _primaryLabel = "启动准备";
        bool _primaryEnabled, _abortVisible, _abortEnabled, _stopEnabled, _checkEnabled;
        bool _progressVisible, _progressIndeterminate;
        double _progressValue;
        string _progressText = "0%", _progressLabel = "";
        string _listening = "已关闭", _listeningSub = "尚未启动", _models = "— / —";
        string _lanes = "— / —", _laneSub = "启动时按内存预算调整";
        string _window = "检测中", _windowSub = "正在读取窗口";
        string _captureName = "等待检测", _captureMeta = "正在读取窗口信息", _captureStatus = "未知";
        string _laneFeatureText = "启动时按可用内存调整 · 本次实际 — 路";
        string _taskSummary = "未选星级";
        string _shortcutFull = "Ctrl+Alt+S", _shortcutSingle = "Ctrl+Alt+D", _shortcutPuzzle = "Ctrl+Alt+P";
        string _shortcutAbort = "Ctrl+Alt+X", _shortcutStop = "Ctrl+Alt+Q", _shortcutOverlay = "Ctrl+Alt+O";
        string _latestLog = "暂无运行日志", _logCount = "0 条记录", _logToggleLabel = "展开日志";
        Brush _toneBrush = Brushes.Gray, _toneSoftBrush = Brushes.WhiteSmoke, _logDotBrush = Brushes.Gray;
        Geometry _stateGlyph;

        public string Title { get { return _title; } set { Set(ref _title, value, "Title"); } }
        public string Chip { get { return _chip; } set { Set(ref _chip, value, "Chip"); } }
        public string StateName { get; set; }
        public string Tone { get { return _tone; } set { Set(ref _tone, value, "Tone"); } }
        public string Detail { get { return _detail; } set { Set(ref _detail, value, "Detail"); } }
        public string Hint { get { return _hint; } set { Set(ref _hint, value, "Hint"); } }
        public string PrimaryLabel { get { return _primaryLabel; } set { Set(ref _primaryLabel, value, "PrimaryLabel"); } }
        public bool PrimaryEnabled { get { return _primaryEnabled; } set { Set(ref _primaryEnabled, value, "PrimaryEnabled"); } }
        public bool AbortVisible { get { return _abortVisible; } set { Set(ref _abortVisible, value, "AbortVisible"); } }
        public bool AbortEnabled { get { return _abortEnabled; } set { Set(ref _abortEnabled, value, "AbortEnabled"); } }
        public bool StopEnabled { get { return _stopEnabled; } set { Set(ref _stopEnabled, value, "StopEnabled"); } }
        public bool CheckEnabled { get { return _checkEnabled; } set { Set(ref _checkEnabled, value, "CheckEnabled"); } }
        public bool ProgressVisible { get { return _progressVisible; } set { Set(ref _progressVisible, value, "ProgressVisible"); } }
        public bool ProgressIndeterminate { get { return _progressIndeterminate; } set { Set(ref _progressIndeterminate, value, "ProgressIndeterminate"); } }
        public double ProgressValue { get { return _progressValue; } set { Set(ref _progressValue, value, "ProgressValue"); } }
        public string ProgressText { get { return _progressText; } set { Set(ref _progressText, value, "ProgressText"); } }
        public string ProgressLabel { get { return _progressLabel; } set { Set(ref _progressLabel, value, "ProgressLabel"); } }
        public string Listening { get { return _listening; } set { Set(ref _listening, value, "Listening"); } }
        public string ListeningSub { get { return _listeningSub; } set { Set(ref _listeningSub, value, "ListeningSub"); } }
        public string Models { get { return _models; } set { Set(ref _models, value, "Models"); } }
        public string Lanes { get { return _lanes; } set { Set(ref _lanes, value, "Lanes"); } }
        public string LaneSub { get { return _laneSub; } set { Set(ref _laneSub, value, "LaneSub"); } }
        public string Window { get { return _window; } set { Set(ref _window, value, "Window"); } }
        public string WindowSub { get { return _windowSub; } set { Set(ref _windowSub, value, "WindowSub"); } }
        public string CaptureName { get { return _captureName; } set { Set(ref _captureName, value, "CaptureName"); } }
        public string CaptureMeta { get { return _captureMeta; } set { Set(ref _captureMeta, value, "CaptureMeta"); } }
        public string CaptureStatus { get { return _captureStatus; } set { Set(ref _captureStatus, value, "CaptureStatus"); } }
        public string LaneFeatureText { get { return _laneFeatureText; } set { Set(ref _laneFeatureText, value, "LaneFeatureText"); } }
        public string TaskSummary { get { return _taskSummary; } set { Set(ref _taskSummary, value, "TaskSummary"); } }
        public string ShortcutFull { get { return _shortcutFull; } set { Set(ref _shortcutFull, value, "ShortcutFull"); } }
        public string ShortcutSingle { get { return _shortcutSingle; } set { Set(ref _shortcutSingle, value, "ShortcutSingle"); } }
        public string ShortcutPuzzle { get { return _shortcutPuzzle; } set { Set(ref _shortcutPuzzle, value, "ShortcutPuzzle"); } }
        public string ShortcutAbort { get { return _shortcutAbort; } set { Set(ref _shortcutAbort, value, "ShortcutAbort"); } }
        public string ShortcutStop { get { return _shortcutStop; } set { Set(ref _shortcutStop, value, "ShortcutStop"); } }
        public string ShortcutOverlay { get { return _shortcutOverlay; } set { Set(ref _shortcutOverlay, value, "ShortcutOverlay"); } }
        public string LatestLog { get { return _latestLog; } set { Set(ref _latestLog, value, "LatestLog"); } }
        public string LogCount { get { return _logCount; } set { Set(ref _logCount, value, "LogCount"); } }
        public string LogToggleLabel { get { return _logToggleLabel; } set { Set(ref _logToggleLabel, value, "LogToggleLabel"); } }
        public Brush ToneBrush { get { return _toneBrush; } set { Set(ref _toneBrush, value, "ToneBrush"); } }
        public Brush ToneSoftBrush { get { return _toneSoftBrush; } set { Set(ref _toneSoftBrush, value, "ToneSoftBrush"); } }
        public Brush LogDotBrush { get { return _logDotBrush; } set { Set(ref _logDotBrush, value, "LogDotBrush"); } }
        public Geometry StateGlyph { get { return _stateGlyph; } set { Set(ref _stateGlyph, value, "StateGlyph"); } }
    }

    public sealed class SettingsViewModel : NotifyBase
    {
        int _singleWorkers = 2, _keepBatches = 3, _keepDays = 7;
        bool _rowInfo, _liveExcel = true, _sound = true, _overlayVisible = true;
        bool _overlayPerformance, _overlayExclude = true, _autoCleanup;
        bool _overlayLocked, _overlayAutoLock = true;
        double _overlayOpacity = 72;
        string _workbookPath = "", _sheet = "获得物", _cleanupMode = "batches";
        string _workbookModeLabel = "自动新建", _workbookMeta = "留空时本次会话自动新建；指定时追加到已有文件。";
        bool _pickVisible;
        string _shortcutFull = "Ctrl+Alt+S", _shortcutSingle = "Ctrl+Alt+D", _shortcutPuzzle = "Ctrl+Alt+P";
        string _shortcutAbort = "Ctrl+Alt+X", _shortcutStop = "Ctrl+Alt+Q", _shortcutOverlay = "Ctrl+Alt+O";
        bool _suppress;

        public event EventHandler<SettingChangedEventArgs> Changed;

        public void SuppressEvents(bool value) { _suppress = value; }
        void ChangedValue(string name, object value) { if (!_suppress && Changed != null) Changed(this, new SettingChangedEventArgs(name, value)); }

        public int SingleWorkers { get { return _singleWorkers; } set { int v = Math.Max(1, Math.Min(4, value)); if (Set(ref _singleWorkers, v, "SingleWorkers")) ChangedValue("single_workers", v); } }
        public bool RowInfo { get { return _rowInfo; } set { if (Set(ref _rowInfo, value, "RowInfo")) ChangedValue("row_info", value); } }
        public bool LiveExcel { get { return _liveExcel; } set { if (Set(ref _liveExcel, value, "LiveExcel")) ChangedValue("live_excel", value); } }
        public bool Sound { get { return _sound; } set { if (Set(ref _sound, value, "Sound")) ChangedValue("sound", value); } }
        public bool OverlayVisible { get { return _overlayVisible; } set { if (Set(ref _overlayVisible, value, "OverlayVisible")) ChangedValue("overlay_visible", value); } }
        public bool OverlayPerformance { get { return _overlayPerformance; } set { if (Set(ref _overlayPerformance, value, "OverlayPerformance")) ChangedValue("overlay_performance", value); } }
        public bool OverlayExclude { get { return _overlayExclude; } set { if (Set(ref _overlayExclude, value, "OverlayExclude")) ChangedValue("overlay_exclude", value); } }
        public bool OverlayLocked { get { return _overlayLocked; } set { if (Set(ref _overlayLocked, value, "OverlayLocked")) ChangedValue("overlay_locked", value); } }
        public bool OverlayAutoLock { get { return _overlayAutoLock; } set { if (Set(ref _overlayAutoLock, value, "OverlayAutoLock")) ChangedValue("overlay_auto_lock", value); } }
        public bool AutoCleanup { get { return _autoCleanup; } set { if (Set(ref _autoCleanup, value, "AutoCleanup")) ChangedValue("auto_cleanup", value); } }
        public double OverlayOpacity { get { return _overlayOpacity; } set { int v = (int)Math.Round(Math.Max(20, Math.Min(95, value))); if (Set(ref _overlayOpacity, v, "OverlayOpacity")) { Raise("OverlayOpacityText"); ChangedValue("overlay_opacity", v); } } }
        public string OverlayOpacityText { get { return ((int)Math.Round(_overlayOpacity)) + "%"; } }
        public string WorkbookPath { get { return _workbookPath; } set { if (Set(ref _workbookPath, value == null ? "" : value, "WorkbookPath")) ChangedValue("xlsx_target", _workbookPath); } }
        public string Sheet { get { return _sheet; } set { string v = string.IsNullOrEmpty(value) ? "获得物" : value; if (Set(ref _sheet, v, "Sheet")) ChangedValue("xlsx_sheet", v); } }
        public string CleanupMode { get { return _cleanupMode; } set { string v = value == "days" ? "days" : "batches"; if (Set(ref _cleanupMode, v, "CleanupMode")) ChangedValue("cleanup_mode", v); } }
        public int KeepBatches { get { return _keepBatches; } set { int v = Math.Max(1, value); if (Set(ref _keepBatches, v, "KeepBatches")) ChangedValue("keep_batches", v); } }
        public int KeepDays { get { return _keepDays; } set { int v = value > 0 ? value : 7; if (Set(ref _keepDays, v, "KeepDays")) ChangedValue("keep_days", v); } }
        public string WorkbookModeLabel { get { return _workbookModeLabel; } set { Set(ref _workbookModeLabel, value, "WorkbookModeLabel"); } }
        public string WorkbookMeta { get { return _workbookMeta; } set { Set(ref _workbookMeta, value, "WorkbookMeta"); } }
        public bool PickVisible { get { return _pickVisible; } set { Set(ref _pickVisible, value, "PickVisible"); } }
        public string ShortcutFull { get { return _shortcutFull; } set { Set(ref _shortcutFull, value, "ShortcutFull"); } }
        public string ShortcutSingle { get { return _shortcutSingle; } set { Set(ref _shortcutSingle, value, "ShortcutSingle"); } }
        public string ShortcutPuzzle { get { return _shortcutPuzzle; } set { Set(ref _shortcutPuzzle, value, "ShortcutPuzzle"); } }
        public string ShortcutAbort { get { return _shortcutAbort; } set { Set(ref _shortcutAbort, value, "ShortcutAbort"); } }
        public string ShortcutStop { get { return _shortcutStop; } set { Set(ref _shortcutStop, value, "ShortcutStop"); } }
        public string ShortcutOverlay { get { return _shortcutOverlay; } set { Set(ref _shortcutOverlay, value, "ShortcutOverlay"); } }
    }

    public sealed class SpaceViewModel : NotifyBase
    {
        string _path = "正在读取…", _used = "—", _cleanable = "—", _protected = "—", _free = "—";
        string _protectWorkbook = "", _protectJson = "", _protectLearning = "";
        public ObservableCollection<SegmentItem> Segments { get; private set; }
        public SpaceViewModel() { Segments = new ObservableCollection<SegmentItem>(); }
        public string Path { get { return _path; } set { Set(ref _path, value, "Path"); } }
        public string Used { get { return _used; } set { Set(ref _used, value, "Used"); } }
        public string Cleanable { get { return _cleanable; } set { Set(ref _cleanable, value, "Cleanable"); } }
        public string Protected { get { return _protected; } set { Set(ref _protected, value, "Protected"); } }
        public string Free { get { return _free; } set { Set(ref _free, value, "Free"); } }
        public string ProtectWorkbook { get { return _protectWorkbook; } set { Set(ref _protectWorkbook, value, "ProtectWorkbook"); } }
        public string ProtectJson { get { return _protectJson; } set { Set(ref _protectJson, value, "ProtectJson"); } }
        public string ProtectLearning { get { return _protectLearning; } set { Set(ref _protectLearning, value, "ProtectLearning"); } }
    }

    public sealed class PerformanceViewModel : NotifyBase
    {
        string _cpuApp = "—", _cpuSys = "—", _gpuApp = "—", _gpuSys = "—", _memApp = "—", _memSys = "—";
        public string CpuApp { get { return _cpuApp; } set { Set(ref _cpuApp, value, "CpuApp"); } }
        public string CpuSys { get { return _cpuSys; } set { Set(ref _cpuSys, value, "CpuSys"); } }
        public string GpuApp { get { return _gpuApp; } set { Set(ref _gpuApp, value, "GpuApp"); } }
        public string GpuSys { get { return _gpuSys; } set { Set(ref _gpuSys, value, "GpuSys"); } }
        public string MemApp { get { return _memApp; } set { Set(ref _memApp, value, "MemApp"); } }
        public string MemSys { get { return _memSys; } set { Set(ref _memSys, value, "MemSys"); } }
    }

    public sealed class HostViewModel : NotifyBase
    {
        string _hostBadge = "正在读取", _hostCardState = "正在连接", _hostCardDetail = "正在等待扫描器状态。";
        string _hostFooter = "正在读取状态", _currentPageTitle = "扫描主页", _appVersion = "由应用提供";
        string _selectionSummary = "尚未选择批次", _selectionHint = "仅可勾选未受保护的批次";
        bool _selectionCanClean, _exportEnabled;
        string _exportSelectionNote = "正在读取错误记录。";
        string _autoStateText = "已关闭 · 默认手动按批清理";
        string _autoHint = "按数量保留最近 3 个可清理批次；更早批次视为候选。";
        string _overlayModeChip = "未监听", _overlayStateTitle = "等待快捷键";
        string _overlayLaneLine = "请求 — · 实际 — · 模型 —/—", _overlayPerfLine = "等待性能数据";
        string _overlayLock = "可编辑 · 可拖动缩放", _overlayLockBadge = "读取中";
        string _overlayExcludeNote = "默认开启。此项调整其他软件捕获浮窗的可见性；扫描器始终依照游戏窗口取图。";
        Brush _hostDotBrush = Brushes.Gray;
        IssueItem _selectedIssue;
        int[] _keepDays = new int[] { 1, 3, 7, 15, 30 };

        public HostViewModel()
        {
            Runtime = new RuntimeViewModel();
            Settings = new SettingsViewModel();
            Space = new SpaceViewModel();
            Performance = new PerformanceViewModel();
            Batches = new ObservableCollection<BatchItem>();
            Issues = new ObservableCollection<IssueItem>();
            Logs = new ObservableCollection<LogItem>();
        }

        public RuntimeViewModel Runtime { get; private set; }
        public SettingsViewModel Settings { get; private set; }
        public SpaceViewModel Space { get; private set; }
        public PerformanceViewModel Performance { get; private set; }
        public ObservableCollection<BatchItem> Batches { get; private set; }
        public ObservableCollection<IssueItem> Issues { get; private set; }
        public ObservableCollection<LogItem> Logs { get; private set; }
        public int[] KeepDayOptions { get { return _keepDays; } }
        public string HostBadge { get { return _hostBadge; } set { Set(ref _hostBadge, value, "HostBadge"); } }
        public string HostCardState { get { return _hostCardState; } set { Set(ref _hostCardState, value, "HostCardState"); } }
        public string HostCardDetail { get { return _hostCardDetail; } set { Set(ref _hostCardDetail, value, "HostCardDetail"); } }
        public string HostFooter { get { return _hostFooter; } set { Set(ref _hostFooter, value, "HostFooter"); } }
        public string CurrentPageTitle { get { return _currentPageTitle; } set { Set(ref _currentPageTitle, value, "CurrentPageTitle"); } }
        public string AppVersion { get { return _appVersion; } set { Set(ref _appVersion, value, "AppVersion"); } }
        public Brush HostDotBrush { get { return _hostDotBrush; } set { Set(ref _hostDotBrush, value, "HostDotBrush"); } }
        public string SelectionSummary { get { return _selectionSummary; } set { Set(ref _selectionSummary, value, "SelectionSummary"); } }
        public string SelectionHint { get { return _selectionHint; } set { Set(ref _selectionHint, value, "SelectionHint"); } }
        public bool SelectionCanClean { get { return _selectionCanClean; } set { Set(ref _selectionCanClean, value, "SelectionCanClean"); } }
        public bool ExportEnabled { get { return _exportEnabled; } set { Set(ref _exportEnabled, value, "ExportEnabled"); } }
        public string ExportSelectionNote { get { return _exportSelectionNote; } set { Set(ref _exportSelectionNote, value, "ExportSelectionNote"); } }
        public string AutoStateText { get { return _autoStateText; } set { Set(ref _autoStateText, value, "AutoStateText"); } }
        public string AutoHint { get { return _autoHint; } set { Set(ref _autoHint, value, "AutoHint"); } }
        public string OverlayModeChip { get { return _overlayModeChip; } set { Set(ref _overlayModeChip, value, "OverlayModeChip"); } }
        public string OverlayStateTitle { get { return _overlayStateTitle; } set { Set(ref _overlayStateTitle, value, "OverlayStateTitle"); } }
        public string OverlayLaneLine { get { return _overlayLaneLine; } set { Set(ref _overlayLaneLine, value, "OverlayLaneLine"); } }
        public string OverlayPerfLine { get { return _overlayPerfLine; } set { Set(ref _overlayPerfLine, value, "OverlayPerfLine"); } }
        public string OverlayLock { get { return _overlayLock; } set { Set(ref _overlayLock, value, "OverlayLock"); } }
        public string OverlayLockBadge { get { return _overlayLockBadge; } set { Set(ref _overlayLockBadge, value, "OverlayLockBadge"); } }
        public string OverlayExcludeNote { get { return _overlayExcludeNote; } set { Set(ref _overlayExcludeNote, value, "OverlayExcludeNote"); } }
        public IssueItem SelectedIssue { get { return _selectedIssue; } set { Set(ref _selectedIssue, value, "SelectedIssue"); } }
    }

    public sealed class BatchItem : NotifyBase
    {
        string _statusText="";
        public string StatusText { get { return _statusText; } set { Set(ref _statusText,value,"StatusText"); } }
        string _name = "", _title = "", _stars = "", _meta = "", _sizeText = "0 B", _stateText = "可清理", _reason = "";
        int _files;
        long _bytes;
        bool _protected, _canSelect = true, _isSelected;
        Brush _rowBackground = Brushes.Transparent;
        public Brush NormalBackground { get; set; }
        public Brush SelectedBackground { get; set; }
        public string Name { get { return _name; } set { Set(ref _name, value, "Name"); } }
        public string Title { get { return _title; } set { Set(ref _title, value, "Title"); } }
        public string Stars { get { return _stars; } set { Set(ref _stars, value, "Stars"); } }
        public string Meta { get { return _meta; } set { Set(ref _meta, value, "Meta"); } }
        public string SizeText { get { return _sizeText; } set { Set(ref _sizeText, value, "SizeText"); } }
        public string StateText { get { return _stateText; } set { Set(ref _stateText, value, "StateText"); } }
        public string Reason { get { return _reason; } set { Set(ref _reason, value, "Reason"); } }
        public int Files { get { return _files; } set { Set(ref _files, value, "Files"); } }
        public long Bytes { get { return _bytes; } set { Set(ref _bytes, value, "Bytes"); } }
        public bool Protected { get { return _protected; } set { Set(ref _protected, value, "Protected"); } }
        public bool CanSelect { get { return _canSelect; } set { Set(ref _canSelect, value, "CanSelect"); } }
        public bool IsSelected { get { return _isSelected; } set { if (Set(ref _isSelected, value && _canSelect, "IsSelected")) { Raise("RowBackground"); } } }
        public Brush RowBackground { get { return _isSelected ? SelectedBackground : NormalBackground; } }
    }

    public sealed class IssueItem : NotifyBase
    {
        string _id = "", _display = "", _task = "", _occurredAt = "", _message = "", _batchName = "";
        public string Id { get { return _id; } set { Set(ref _id, value, "Id"); } }
        public string Display { get { return _display; } set { Set(ref _display, value, "Display"); } }
        public string Task { get { return _task; } set { Set(ref _task, value, "Task"); } }
        public string OccurredAt { get { return _occurredAt; } set { Set(ref _occurredAt, value, "OccurredAt"); } }
        public string Message { get { return _message; } set { Set(ref _message, value, "Message"); } }
        public string BatchName { get { return _batchName; } set { Set(ref _batchName, value, "BatchName"); } }
    }

    public sealed class SegmentItem : NotifyBase
    {
        string _label = "", _sizeText = "0 B";
        long _bytes;
        Brush _brush = Brushes.Gray;
        public long Bytes { get { return _bytes; } set { Set(ref _bytes, value, "Bytes"); } }
        public string Label { get { return _label; } set { Set(ref _label, value, "Label"); } }
        public string SizeText { get { return _sizeText; } set { Set(ref _sizeText, value, "SizeText"); } }
        public Brush Brush { get { return _brush; } set { Set(ref _brush, value, "Brush"); } }
    }

    public sealed class LogItem : NotifyBase
    {
        string _time = "", _text = "";
        Brush _toneBrush = Brushes.Gray;
        public string Time { get { return _time; } set { Set(ref _time, value, "Time"); } }
        public string Text { get { return _text; } set { Set(ref _text, value, "Text"); } }
        public Brush ToneBrush { get { return _toneBrush; } set { Set(ref _toneBrush, value, "ToneBrush"); } }
    }

    public sealed class NativeDesktopHost
    {
        readonly Window _window;
        readonly HostViewModel _vm;
        readonly ResourceDictionary _illustrations;
        readonly JavaScriptSerializer _json = new JavaScriptSerializer();
        readonly object _writeLock = new object();
        readonly Dictionary<string, Button> _pending = new Dictionary<string, Button>();
        readonly Dictionary<string, string> _pendingNames = new Dictionary<string, string>();
        string _capturingShortcut;
        readonly bool _preview;
        NativeLayoutDemo _demo;
        readonly HashSet<int> _stars = new HashSet<int>();
        readonly DispatcherTimer _toastTimer;
        readonly DispatcherTimer _saveTimer;
        readonly DispatcherTimer _closeTimer;
        ICollectionView _batchView;
        Dictionary<string, object> _raw = new Dictionary<string, object>();
        string _settingsSignature = "", _runtimeSignature = "", _spaceSignature = "";
        string _batchesSignature = "", _issuesSignature = "", _logsSignature = "", _performanceSignature = "";
        bool _connected, _applying, _allowClose, _closeSent, _switching;
        bool _workbookExisting, _workbookExplicit, _overlayLocked;
        readonly Dictionary<string,string> _settingRequests=new Dictionary<string,string>();
        long _settingsRevision=0;
        int _filter = 0;
        Thread _reader;
        Action _modalAction;

        public NativeDesktopHost(Window window, HostViewModel model, ResourceDictionary illustrations,bool preview=false)
        {
            _window = window;
            _vm = model;
            _illustrations = illustrations;
            _preview=preview;
            _json.MaxJsonLength = 8 * 1024 * 1024;
            _json.RecursionLimit = 100;
            _toastTimer = new DispatcherTimer { Interval = TimeSpan.FromSeconds(3.5) };
            _toastTimer.Tick += delegate { _toastTimer.Stop(); Find<Border>("Toast").Visibility = Visibility.Collapsed; };
            _saveTimer = new DispatcherTimer { Interval = TimeSpan.FromMilliseconds(320) };
            _saveTimer.Tick += delegate { _saveTimer.Stop(); SendAction("save_preferences", null, null); };
            _closeTimer = new DispatcherTimer { Interval = TimeSpan.FromSeconds(2) };
            _closeTimer.Tick += delegate { _closeTimer.Stop(); _closeSent = false; };
            Wire();
            _window.Loaded += Window_Loaded;
            _window.SizeChanged += Window_SizeChanged;
            _window.Closing += Window_Closing;
            _vm.Settings.Changed += Settings_Changed;
            _vm.PropertyChanged += ViewModel_PropertyChanged;
            _batchView = CollectionViewSource.GetDefaultView(_vm.Batches);
            _batchView.Filter = BatchFilter;
            Find<ItemsControl>("BatchList").ItemsSource = _batchView;
            Find<ItemsControl>("LogList").ItemsSource = _vm.Logs;
            SetPage("scan");
            UpdateAutoUI();
            UpdateWorkbookUI();
            UpdateOverlayUI();
        }

        T Find<T>(string name) where T : class
        {
            object value = _window.FindName(name);
            T result = value as T;
            if (result == null) throw new InvalidOperationException("缺少原生控件：" + name);
            return result;
        }

        void Wire()
        {
            _window.PreviewMouseWheel += NestedScroll;
            foreach (string name in new string[] { "WorkbookPathInput", "SheetInput", "AutoKeepBatches" })
                Find<TextBox>(name).LostKeyboardFocus += delegate { ReapplyOwnerSettings(); };
            Find<Slider>("OverlayOpacitySlider").LostMouseCapture += delegate { ReapplyOwnerSettings(); };
            Find<Button>("WindowMinimize").Click += delegate { _window.WindowState = WindowState.Minimized; };
            Find<Button>("WindowMaximize").Click += delegate
            {
                _window.WindowState = _window.WindowState == WindowState.Maximized ? WindowState.Normal : WindowState.Maximized;
            };
            Find<Button>("WindowClose").Click += delegate { _window.Close(); };
            Find<RadioButton>("NavScan").Checked += delegate { if (!_switching) SetPage("scan"); };
            Find<RadioButton>("NavSpace").Checked += delegate { if (!_switching) SetPage("space"); };
            Find<RadioButton>("NavSettings").Checked += delegate { if (!_switching) SetPage("settings"); };
            Find<RadioButton>("NavHelp").Checked += delegate { if (!_switching) SetPage("help"); };

            Find<Button>("PrimaryAction").Click += delegate
            {
                if (_vm.Runtime.StateName == "nogame") SendAction("refresh_target", null, Find<Button>("PrimaryAction"));
                else SendAction("prepare", null, Find<Button>("PrimaryAction"));
            };
            Find<Button>("AbortAction").Click += delegate { SendAction("cancel", null, Find<Button>("AbortAction")); };
            Find<Button>("StopAction").Click += delegate { SendAction("stop", null, Find<Button>("StopAction")); };
            Find<Button>("CheckMemory").Click += delegate { SendAction("check_memory", null, Find<Button>("CheckMemory")); };
            Find<Button>("JumpToLog").Click += delegate { ToggleLog(true); };
            Find<Button>("LogToggle").Click += delegate { ToggleLog(Find<Border>("LogBody").Visibility != Visibility.Visible); };
            Find<Button>("LaneMinus").Click += delegate { ChangeLanes(-1); };
            Find<Button>("LanePlus").Click += delegate { ChangeLanes(1); };
            Find<ToggleButton>("Star5").Click += delegate { ToggleStar(5, Find<ToggleButton>("Star5")); };
            Find<ToggleButton>("Star4").Click += delegate { ToggleStar(4, Find<ToggleButton>("Star4")); };
            Find<ToggleButton>("Star3").Click += delegate { ToggleStar(3, Find<ToggleButton>("Star3")); };
            Find<ToggleButton>("Star2").Click += delegate { ToggleStar(2, Find<ToggleButton>("Star2")); };
            Find<Button>("WorkbookAuto").Click += delegate
            {
                _workbookExisting = false; _workbookExplicit = false;
                _vm.Settings.WorkbookPath = "";
                UpdateWorkbookUI();
            };
            Find<Button>("WorkbookExisting").Click += delegate
            {
                _workbookExisting = true; _workbookExplicit = true;
                UpdateWorkbookUI();
            };
            Find<Button>("PickWorkbook").Click += delegate { PickWorkbook(); };
            Find<Button>("RefreshWindow").Click += delegate { SendAction("refresh_target", null, Find<Button>("RefreshWindow")); };
            Find<Button>("RefreshSpace").Click += delegate { SendAction("refresh_space", null, Find<Button>("RefreshSpace")); };
            Find<Button>("OpenOutput").Click += delegate { SendAction("open_output", null, null); };
            Find<Button>("ConvertJson").Click += delegate { ConvertJson(); };
            Find<Button>("FilterAll").Click += delegate { SetFilter(0); };
            Find<Button>("FilterCleanable").Click += delegate { SetFilter(1); };
            Find<Button>("FilterProtected").Click += delegate { SetFilter(2); };
            Find<Button>("SelectAllCleanable").Click += delegate { ToggleAllCleanable(); };
            Find<Button>("PreviewCleanup").Click += delegate { ShowCleanupModal(); };
            Find<Button>("PreviewExport").Click += delegate { ShowExportModal(); };
            Find<Button>("AutoBatches").Click += delegate { _vm.Settings.CleanupMode = "batches"; UpdateAutoUI(); };
            Find<Button>("AutoDays").Click += delegate { _vm.Settings.CleanupMode = "days"; UpdateAutoUI(); };
            Find<Button>("AutoKeepMinus").Click += delegate { ChangeKeepBatches(-1); };
            Find<Button>("AutoKeepPlus").Click += delegate { ChangeKeepBatches(1); };
            Find<Button>("TabPictures").Click += delegate { SetHelpTab("pictures"); };
            Find<Button>("TabGuide").Click += delegate { SetHelpTab("guide"); };
            Find<Button>("TabLicense").Click += delegate { SetHelpTab("license"); };
            Find<Button>("TabAbout").Click += delegate { SetHelpTab("about"); };
            Find<Button>("OpenProjectHome").Click += delegate {
                try { System.Diagnostics.Process.Start(new System.Diagnostics.ProcessStartInfo("https://github.com/DrMoMing/GenshinRewardScanner") { UseShellExecute = true }); }
                catch (Exception error) { ShowToast("无法打开项目主页：" + error.Message); }
            };
            Find<Button>("TutFirst").Click += delegate { ScrollTo("TutFirstArticle"); };
            Find<Button>("TutStart").Click += delegate { ScrollTo("TutStartArticle"); };
            Find<Button>("TutTasks").Click += delegate { ScrollTo("TutTasksArticle"); };
            Find<Button>("TutExcel").Click += delegate { ScrollTo("TutExcelArticle"); };
            Find<Button>("TutControl").Click += delegate { ScrollTo("TutControlArticle"); };
            Find<Button>("TutOverlay").Click += delegate { ScrollTo("TutOverlayArticle"); };
            Find<Button>("TutSpace").Click += delegate { ScrollTo("TutSpaceArticle"); };
            Find<Button>("TutFaq").Click += delegate { ScrollTo("TutFaqArticle"); };
            Find<Button>("PreviewScreenshot").Click += delegate { SendAction("preview_sound", SoundArgs("capture"), Find<Button>("PreviewScreenshot")); };
            Find<Button>("PreviewComplete").Click += delegate { SendAction("preview_sound", SoundArgs("success"), Find<Button>("PreviewComplete")); };
            Find<Button>("PreviewFailure").Click += delegate { SendAction("preview_sound", SoundArgs("failure"), Find<Button>("PreviewFailure")); };
            Find<Button>("ResetShortcuts").Click += delegate { ResetShortcuts(); };
            Find<Button>("UninstallApp").Click += delegate {
                if (_preview) { ShowToast("界面演示不会启动实际卸载。"); return; }
                ShowModal("应用管理", "卸载原神副本扫描器", "将先退出扫描器，再打开卸载程序。", "卸载时可以选择保留或清除安装目录内的数据；外部工作簿不受影响。", "退出并卸载", true,
                    delegate { SendAction("uninstall",null,Find<Button>("UninstallApp")); });
            };
            Find<Button>("OpenLicensesFolder").Click += delegate { SendAction("open_licenses",null,null); };
            TextBox[] shortcuts = new TextBox[] {
                Find<TextBox>("ShortcutFullBox"), Find<TextBox>("ShortcutSingleBox"), Find<TextBox>("ShortcutPuzzleBox"),
                Find<TextBox>("ShortcutAbortBox"), Find<TextBox>("ShortcutStopBox"), Find<TextBox>("ShortcutOverlayBox") };
            foreach (TextBox box in shortcuts)
            {
                TextBox captured = box;
                captured.PreviewMouseLeftButtonDown += delegate { BeginShortcut(captured); };
                captured.PreviewKeyDown += CaptureShortcut;
                captured.LostKeyboardFocus += delegate
                {
                    if (_capturingShortcut==captured.Name)
                    {
                        _capturingShortcut=null;
                        Find<TextBlock>("ShortcutCaptureStatus").Text="已取消录入。";
                    }
                };
            }

            Find<Button>("ModalClose").Click += delegate { HideModal(); };
            Find<Button>("ModalCancel").Click += delegate { HideModal(); };
            Find<Button>("ModalConfirm").Click += delegate
            {
                Action action = _modalAction;
                HideModal();
                if (action != null) action();
            };
            Find<ToggleButton>("AutoCleanToggle").Checked += delegate { UpdateAutoUI(); };
            Find<ToggleButton>("AutoCleanToggle").Unchecked += delegate { UpdateAutoUI(); };
            Find<ToggleButton>("ShowOverlayToggle").Checked += delegate { UpdateOverlayUI(); };
            Find<ToggleButton>("ShowOverlayToggle").Unchecked += delegate { UpdateOverlayUI(); };
            Find<ToggleButton>("ShowPerformanceToggle").Checked += delegate { UpdateOverlayUI(); };
            Find<ToggleButton>("ShowPerformanceToggle").Unchecked += delegate { UpdateOverlayUI(); };
            Find<ToggleButton>("ExcludeCaptureToggle").Checked += delegate { UpdateOverlayUI(); };
            Find<ToggleButton>("ExcludeCaptureToggle").Unchecked += delegate { UpdateOverlayUI(); };
        }

        void Window_Loaded(object sender, RoutedEventArgs e)
        {
            if (_illustrations != null)
            {
                AssignDiagram("SetupDiagramHost", "SetupDiagram");
                AssignDiagram("GameDiagramHost", "GameDiagram");
                AssignDiagram("ResultDiagramHost", "ResultDiagram");
            }
            if (_preview)
            {
                string directory=AppDomain.CurrentDomain.BaseDirectory;
                if (!File.Exists(Path.Combine(directory,"preview.json"))) directory=Path.Combine(directory,"_运行依赖","desktop_host");
                _demo=new NativeLayoutDemo(Path.Combine(directory,"preview.json"),HandleLine);
                _demo.Publish();
            }
            else
            {
                StartReader();
                SendReady();
                SetConnected(false);
            }
            ApplyResponsive(_window.ActualWidth > 0 ? _window.ActualWidth : _window.Width, _window.ActualHeight > 0 ? _window.ActualHeight : _window.Height);
        }

        void Window_SizeChanged(object sender, SizeChangedEventArgs e)
        {
            ApplyResponsive(e.NewSize.Width, e.NewSize.Height);
        }

        void ApplyResponsive(double width, double height)
        {
            bool compact = width <= 1040.0;
            bool narrow = width <= 940.0;
            bool shortHeight = height <= 760.0;
            Find<Grid>("BodyGrid").ColumnDefinitions[0].Width = new GridLength(compact ? 194 : 214);
            Find<StackPanel>("TitlebarContext").Visibility = compact ? Visibility.Collapsed : Visibility.Visible;
            Thickness pagePadding = shortHeight ? new Thickness(compact ? 17 : 24, 14, compact ? 17 : 24, 18) : (compact ? new Thickness(17, 17, 17, 20) : new Thickness(24, 20, 24, 24));
            Find<ScrollViewer>("PageScan").Padding = pagePadding;
            Find<ScrollViewer>("PageSpace").Padding = pagePadding;
            Find<ScrollViewer>("PageSettings").Padding = pagePadding;
            Find<ScrollViewer>("PageHelp").Padding = pagePadding;
            double h1 = (narrow || shortHeight) ? 23 : 25;
            Find<TextBlock>("ScanPageTitle").FontSize = h1;
            Find<TextBlock>("SpacePageTitle").FontSize = h1;
            Find<TextBlock>("SettingsPageTitle").FontSize = h1;
            Find<TextBlock>("HelpPageTitle").FontSize = h1;
            Find<StackPanel>("StatusContent").Margin = shortHeight ? new Thickness(16, 13, 16, 11) : (compact ? new Thickness(18, 16, 18, 13) : new Thickness(20, 18, 20, 14));
            Find<Border>("StatusBoard").Margin = new Thickness(0, shortHeight ? 10 : 16, 0, 0);
            Find<TextBlock>("StatusDetailText").Margin = new Thickness(0, shortHeight ? 7 : 10, 0, 0);
            Find<Border>("StatusStatsLine").Margin = new Thickness(0, shortHeight ? 10 : 13, 0, 0);
            Find<Grid>("StatusStatsGrid").Margin = new Thickness(0, shortHeight ? 8 : 11, 0, 0);
            Find<Grid>("StatusFoot").Margin = new Thickness(0, shortHeight ? 7 : 10, 0, 0);
            Find<Grid>("ScanGrid").Margin = new Thickness(0, shortHeight ? 10 : 12, 0, 0);
            Thickness panelPadding = shortHeight ? new Thickness(14) : new Thickness(16);
            string[] panelNames = new string[] { "ScanTaskPanel", "SetupPanel", "BatchPanel", "SpaceSummaryPanel", "ProtectionPanel", "AutoPanel", "ExportPanel", "ShortcutsPanel", "SoundPanel", "OverlayPanel", "PerformancePanel" };
            foreach (string panelName in panelNames) Find<Border>(panelName).Padding = panelPadding;
            Border stateIcon = Find<Border>("StateIconBorder");
            double iconSize = (narrow || shortHeight) ? 42 : 46;
            stateIcon.Width = iconSize;
            stateIcon.Height = iconSize;
            System.Windows.Shapes.Path statePath = Find<System.Windows.Shapes.Path>("StateIconPath");
            statePath.Width = (narrow || shortHeight) ? 21 : 23;
            statePath.Height = (narrow || shortHeight) ? 21 : 23;
            Find<TextBlock>("StatusTitleText").FontSize = shortHeight ? 22 : (narrow ? 23 : 25);
            Find<Grid>("ScanGrid").ColumnDefinitions[0].Width = new GridLength(narrow ? 1.35 : 1.55, GridUnitType.Star);
            Find<Grid>("ScanGrid").ColumnDefinitions[1].Width = new GridLength(narrow ? 0.90 : 0.92, GridUnitType.Star);
            Find<Grid>("SettingsGrid").ColumnDefinitions[0].Width = new GridLength(narrow ? 1.05 : 1.02, GridUnitType.Star);
            Find<Grid>("SettingsGrid").ColumnDefinitions[1].Width = new GridLength(narrow ? 0.95 : 0.98, GridUnitType.Star);
            Find<Grid>("SpaceGrid").ColumnDefinitions[0].Width = new GridLength(narrow ? 1.38 : 1.52, GridUnitType.Star);
            Find<Grid>("SpaceGrid").ColumnDefinitions[1].Width = new GridLength(narrow ? 0.86 : 0.95, GridUnitType.Star);
            Find<StackPanel>("SpaceFreeKpi").Visibility = narrow ? Visibility.Collapsed : Visibility.Visible;
            TextBox[] shortcuts = new TextBox[] {
                Find<TextBox>("ShortcutFullBox"), Find<TextBox>("ShortcutSingleBox"), Find<TextBox>("ShortcutPuzzleBox"),
                Find<TextBox>("ShortcutAbortBox"), Find<TextBox>("ShortcutStopBox"), Find<TextBox>("ShortcutOverlayBox") };
            foreach (TextBox box in shortcuts)
            {
                box.Width = narrow ? 126 : 142;
                box.FontSize = narrow ? 8.8 : 9.5;
            }
            WrapPanel home = Find<WrapPanel>("HomeShortcutsPanel");
            foreach (UIElement child in home.Children)
            {
                TextBlock label = child as TextBlock;
                StackPanel group = child as StackPanel;
                if (label != null) label.Margin = new Thickness(0, 0, narrow ? 10 : 16, 6);
                if (group != null)
                {
                    group.Margin = new Thickness(0, 0, narrow ? 8 : 16, 6);
                    TextBlock groupLabel = group.Children.Count > 0 ? group.Children[0] as TextBlock : null;
                    if (groupLabel != null) groupLabel.Margin = new Thickness(0, 0, narrow ? 5 : 7, 0);
                    Border key = group.Children.Count > 1 ? group.Children[1] as Border : null;
                    if (key != null) key.Padding = narrow ? new Thickness(5, 2, 5, 2) : new Thickness(6, 3, 6, 3);
                }
            }
            Button primary = Find<Button>("PrimaryAction");
            Button abort = Find<Button>("AbortAction");
            Button memory = Find<Button>("CheckMemory");
            Button stop = Find<Button>("StopAction");
            if (compact)
            {
                primary.Height = 35; abort.Height = 35; memory.Height = 35; stop.Height = 35;
                primary.FontSize = 11; abort.FontSize = 11; memory.FontSize = 11; stop.FontSize = 11;
            }
            else
            {
                primary.ClearValue(FrameworkElement.HeightProperty);
                abort.ClearValue(FrameworkElement.HeightProperty);
                memory.ClearValue(FrameworkElement.HeightProperty);
                stop.ClearValue(FrameworkElement.HeightProperty);
                primary.ClearValue(Control.FontSizeProperty);
                abort.ClearValue(Control.FontSizeProperty);
                memory.ClearValue(Control.FontSizeProperty);
                stop.ClearValue(Control.FontSizeProperty);
            }
        }

        void AssignDiagram(string hostName, string key)
        {
            ContentControl host = Find<ContentControl>(hostName);
            DataTemplate template = _illustrations[key] as DataTemplate;
            if (template == null) return;
            host.Content = " ";
            host.ContentTemplate = template;
        }

        void StartReader()
        {
            if (_reader != null) return;
            _reader = new Thread(ReadLoop);
            _reader.IsBackground = true;
            _reader.Name = "native-stdin";
            _reader.Start();
        }

        void ReadLoop()
        {
            try
            {
                using (StreamReader reader = new StreamReader(Console.OpenStandardInput(), new UTF8Encoding(false)))
                {
                    string line;
                    while ((line = reader.ReadLine()) != null)
                    {
                        if (line.Trim().Length == 0) continue;
                        string captured = line;
                        try { _window.Dispatcher.BeginInvoke(new Action(delegate { HandleLine(captured); })); }
                        catch (InvalidOperationException) { break; }
                    }
                }
            }
            catch (Exception error)
            {
                try { Console.Error.WriteLine("native stdin: " + error.Message); } catch { }
            }
            try { _window.Dispatcher.BeginInvoke(new Action(CloseApproved)); }
            catch (InvalidOperationException) { }
        }

        void CloseApproved()
        {
            _allowClose = true;
            _window.Close();
        }

        void Window_Closing(object sender, CancelEventArgs e)
        {
            if (_preview) return;
            if (_allowClose) return;
            e.Cancel = true;
            if (_closeSent) return;
            _closeSent = true;
            SendWindowClose();
            _closeTimer.Start();
        }

        void SendReady()
        {
            Dictionary<string, object> message = new Dictionary<string, object>();
            message["v"] = 1;
            message["type"] = "ready";
            message["capabilities"] = new string[] { "snapshot", "partial", "set", "action", "action_result", "window" };
            message["page"] = "scan";
            Send(message);
        }

        void SendWindowClose()
        {
            AllowOwnerForeground();
            Dictionary<string, object> message = new Dictionary<string, object>();
            message["v"] = 1;
            message["type"] = "window";
            message["action"] = "close";
            Send(message);
        }

        void SendSet(string name, object value)
        {
            if (!_connected) return;
            Dictionary<string, object> message = new Dictionary<string, object>();
            message["v"] = 1;
            message["type"] = "set";
            message["name"] = name;
            message["value"] = value;
            if(!_preview && (name=="scan_stars" || name=="row_info")) {
                string id="set-"+Interlocked.Increment(ref _actionSequence).ToString();
                message["request_id"]=id;
                _pendingNames[id]="set:"+name;
                _settingRequests[name]=id;
            }
            Send(message);
        }

        bool SendAction(string name, Dictionary<string, object> args, Button button)
        {
            if (!_connected)
            {
                ShowToast("尚未连接扫描器，动作未发送。");
                return false;
            }
            AllowOwnerForeground();
            string requestId = "act-" + DateTime.UtcNow.Ticks.ToString() + "-" + Interlocked.Increment(ref _actionSequence).ToString();
            _pendingNames[requestId] = name;
            Dictionary<string, object> message = new Dictionary<string, object>();
            message["v"] = 1;
            message["type"] = "action";
            message["name"] = name;
            message["args"] = args == null ? new Dictionary<string, object>() : args;
            message["request_id"] = requestId;
            if (button != null)
            {
                _pending[requestId] = button;
                button.IsHitTestVisible = false;
                button.Opacity = 0.55;
            }
            Send(message);
            return true;
        }

        int _actionSequence;

        [DllImport("user32.dll")]
        static extern bool AllowSetForegroundWindow(uint processId);

        void AllowOwnerForeground()
        {
            // File/key dialogs belong to the Python owner of this foreground UI.
            uint owner;
            if (UInt32.TryParse(Environment.GetEnvironmentVariable("DOMAIN_DESKTOP_OWNER_PID"), out owner))
                AllowSetForegroundWindow(owner);
        }

        void ReapplyOwnerSettings()
        {
            _window.Dispatcher.BeginInvoke(DispatcherPriority.ContextIdle, new Action(delegate
            {
                Dictionary<string, object> settings = AsDict(_raw, "settings");
                if (settings != null)
                {
                    _settingsSignature = "";
                    ApplySettings(settings);
                }
            }));
        }

        void Send(Dictionary<string, object> message)
        {
            if (_preview)
            {
                if (_demo!=null) _demo.Handle(message);
                return;
            }
            try
            {
                // GUI-subsystem processes may retain an ANSI Console writer.
                // JSON Unicode escapes keep the pipe ASCII on every code page.
                string serialized = _json.Serialize(message);
                StringBuilder wire = new StringBuilder(serialized.Length);
                foreach (char character in serialized)
                    if (character > 127) wire.Append("\\u").Append(((int)character).ToString("x4"));
                    else wire.Append(character);
                string line = wire.ToString();
                lock (_writeLock)
                {
                    Console.Out.WriteLine(line);
                    Console.Out.Flush();
                }
            }
            catch (Exception error)
            {
                try { Console.Error.WriteLine("native stdout: " + error.Message); } catch { }
            }
        }

        void HandleLine(string line)
        {
            try
            {
                Dictionary<string, object> message = _json.Deserialize<Dictionary<string, object>>(line);
                if (message == null) return;
                string type = S(message, "type");
                if (type.Length == 0)
                {
                    if (message.ContainsKey("runtime") || message.ContainsKey("settings") || message.ContainsKey("space"))
                        ApplySnapshot(message, false);
                    return;
                }
                if (type == "snapshot" || type == "update" || type == "patch")
                {
                    object payload;
                    if (message.TryGetValue("snapshot", out payload) || message.TryGetValue("patch", out payload) || message.TryGetValue("data", out payload) || message.TryGetValue("state", out payload))
                        ApplySnapshot(AsDict(payload), type != "snapshot");
                    return;
                }
                if (type == "action_result")
                {
                    string requestId = S(message, "request_id");
                    string actionName;
                    _pendingNames.TryGetValue(requestId,out actionName);
                    _pendingNames.Remove(requestId);
                    if(actionName!=null && actionName.StartsWith("set:")) {
                        string name=actionName.Substring(4),latest;
                        if(!_settingRequests.TryGetValue(name,out latest) || latest!=requestId)return;
                        _settingRequests.Remove(name);
                        Dictionary<string,object> reply=AsDict(message,"data");
                        if(reply!=null && reply.ContainsKey("value")) {
                            _settingsRevision=Math.Max(_settingsRevision,L(reply,"revision"));
                            Dictionary<string,object> canonical=new Dictionary<string,object>();
                            canonical[name]=reply["value"];
                            _settingsSignature="";ApplySettings(canonical);UpdateTaskSummary();
                        }
                        if(!B(message,"ok"))ShowToast(S(message,"error"));
                        return;
                    }
                    Button button;
                    if (requestId.Length > 0 && _pending.TryGetValue(requestId, out button))
                    {
                        _pending.Remove(requestId);
                        button.ClearValue(UIElement.OpacityProperty);
                        button.IsHitTestVisible = true;
                    }
                    if (actionName == "update_shortcuts")
                    {
                        Find<TextBlock>("ShortcutCaptureStatus").Text = B(message,"ok") ? "快捷键已保存。" : S(message,"error");
                        _runtimeSignature = "";
                    }
                    if (actionName == "documents" && B(message,"ok"))
                    {
                        Dictionary<string,object> data=AsDict(message,"data");
                        StackPanel files=Find<StackPanel>("LicenseFilesPanel");
                        files.Children.Clear();
                        object entries;
                        if (data.TryGetValue("files",out entries) && entries is System.Collections.IEnumerable)
                        {
                            foreach (object entry in (System.Collections.IEnumerable)entries)
                            {
                                Dictionary<string,object> item=AsDict(entry);
                                string relative=S(item,"folder");
                                Button row=new Button { HorizontalContentAlignment=HorizontalAlignment.Left,
                                    Margin=new Thickness(0,0,0,5),Style=(Style)_window.FindResource("QuietButton"),
                                    Content=new TextBlock { Text=S(item,"name"),TextWrapping=TextWrapping.Wrap },
                                    ToolTip="打开该许可文件所在文件夹" };
                                row.Click+=delegate
                                {
                                    Dictionary<string,object> arguments=new Dictionary<string,object>();
                                    arguments["relative"]=relative;
                                    SendAction("open_license_folder",arguments,null);
                                };
                                files.Children.Add(row);
                            }
                        }
                    }
                    if (!B(message, "ok")) ShowToast(S(message, "error").Length > 0 ? S(message, "error") : "动作未完成。");
                    return;
                }
                if (type == "toast" || type == "error")
                {
                    ShowToast(S(message, "text").Length > 0 ? S(message, "text") : S(message, "error"));
                    return;
                }
                if (type == "hello") return;
            }
            catch (Exception error)
            {
                try { Console.Error.WriteLine("native protocol: " + error.Message); } catch { }
            }
        }

        void ApplySnapshot(Dictionary<string, object> snapshot, bool partial)
        {
            if (snapshot == null || snapshot.Count == 0) return;
            if (partial) _raw = Merge(_raw, snapshot);
            else _raw = snapshot;

            SetConnected(true);
            Dictionary<string, object> app = AsDict(_raw, "app");
            if (app != null) _vm.AppVersion = S(app, "version").Length > 0 ? S(app, "version") : "由应用提供";

            Dictionary<string, object> settings = AsDict(_raw, "settings");
            long revision=L(_raw,"settings_revision");
            if (settings != null && revision>=_settingsRevision) {
                _settingsRevision=revision;ApplySettings(settings);
            }
            Dictionary<string, object> runtime = AsDict(_raw, "runtime");
            if (runtime != null) ApplyRuntime(runtime);

            Dictionary<string, object> space = AsDict(_raw, "space");
            if (space != null) ApplySpace(space);
            List<object> batches = AsList(_raw, "batches");
            if (batches != null) ApplyBatches(batches);
            List<object> issues = AsList(_raw, "issues");
            if (issues != null) ApplyIssues(issues);
            Dictionary<string, object> performance = AsDict(_raw, "performance");
            if (performance != null) ApplyPerformance(performance);
            List<object> logs = AsList(_raw, "logs");
            if (logs == null && runtime != null) logs = AsList(runtime,"logs");
            if (logs != null) ApplyLogs(logs);
            Dictionary<string, object> overlay = AsDict(_raw, "overlay");
            if (overlay != null) ApplyOverlay(overlay);
            UpdateOverlayUI();
            UpdateExportNote();
        }

        void ApplySettings(Dictionary<string, object> settings)
        {
            string signature = _json.Serialize(settings);
            if (signature == _settingsSignature) return;
            // Focused edits are deferred, so the full snapshot is not consumed yet.
            bool deferred = IsFocused(Find<TextBox>("WorkbookPathInput")) || IsFocused(Find<TextBox>("SheetInput"))
                || IsFocused(Find<TextBox>("AutoKeepBatches")) || Find<Slider>("OverlayOpacitySlider").IsMouseCaptureWithin;
            _settingsSignature = deferred ? "" : signature;
            _applying = true;
            _vm.Settings.SuppressEvents(true);
            try
            {
                if (settings.ContainsKey("single_workers")) _vm.Settings.SingleWorkers = I(settings, "single_workers", 2);
                if (settings.ContainsKey("row_info") && !_settingRequests.ContainsKey("row_info")) _vm.Settings.RowInfo = B(settings, "row_info");
                if (settings.ContainsKey("xlsx_target"))
                {
                    string target = S(settings, "xlsx_target");
                    if (!IsFocused(Find<TextBox>("WorkbookPathInput")))
                    {
                        _vm.Settings.WorkbookPath = target;
                    }
                    if (target.Length > 0) _workbookExisting = true;
                    else if (!_workbookExplicit) _workbookExisting = false;
                }
                if (settings.ContainsKey("xlsx_sheet") && !IsFocused(Find<TextBox>("SheetInput")))
                    _vm.Settings.Sheet = S(settings, "xlsx_sheet");
                if (settings.ContainsKey("live_excel")) _vm.Settings.LiveExcel = B(settings, "live_excel");
                if (settings.ContainsKey("sound")) _vm.Settings.Sound = B(settings, "sound");
                if (settings.ContainsKey("overlay_visible")) _vm.Settings.OverlayVisible = B(settings, "overlay_visible");
                if (settings.ContainsKey("overlay_performance")) _vm.Settings.OverlayPerformance = B(settings, "overlay_performance");
                if (settings.ContainsKey("overlay_exclude")) _vm.Settings.OverlayExclude = B(settings, "overlay_exclude");
                if (settings.ContainsKey("overlay_locked")) _vm.Settings.OverlayLocked = B(settings,"overlay_locked");
                if (settings.ContainsKey("overlay_auto_lock")) _vm.Settings.OverlayAutoLock = B(settings,"overlay_auto_lock");
                if (settings.ContainsKey("overlay_opacity") && !Find<Slider>("OverlayOpacitySlider").IsMouseCaptureWithin)
                    _vm.Settings.OverlayOpacity = D(settings, "overlay_opacity", 72);
                if (settings.ContainsKey("auto_cleanup")) _vm.Settings.AutoCleanup = B(settings, "auto_cleanup");
                if (settings.ContainsKey("cleanup_mode")) _vm.Settings.CleanupMode = S(settings, "cleanup_mode") == "days" ? "days" : "batches";
                if (settings.ContainsKey("keep_batches") && !IsFocused(Find<TextBox>("AutoKeepBatches")))
                    _vm.Settings.KeepBatches = I(settings, "keep_batches", 3);
                if (settings.ContainsKey("keep_days")) _vm.Settings.KeepDays = I(settings, "keep_days", 7);

                List<object> stars = AsList(settings, "scan_stars");
                if (stars == null) stars = AsList(settings, "stars");
                if (stars != null && !_settingRequests.ContainsKey("scan_stars"))
                {
                    _stars.Clear();
                    foreach (object star in stars)
                    {
                        int value = ToInt(star, 0);
                        if (value >= 2 && value <= 5) _stars.Add(value);
                    }
                }
            }
            finally
            {
                _vm.Settings.SuppressEvents(false);
                _applying = false;
            }
            UpdateStars();
            UpdateWorkbookUI();
            UpdateAutoUI();
            UpdateOverlayUI();
            UpdateTaskSummary();
        }

        string _lastDiskError="";
        string _pendingDiskError="";
        void ShowPendingDiskError()
        {
            if(_pendingDiskError.Length==0 || Find<Grid>("ModalLayer").Visibility==Visibility.Visible) return;
            string detail=_pendingDiskError;_pendingDiskError="";_lastDiskError=detail;
            ShowModal("文件保存失败","磁盘空间不足",detail,"请清理目标盘与系统临时目录所在盘，再重新准备。未确认保存成功的任务不能视为完成。","知道了",false,delegate {});
        }
        void ApplyRuntime(Dictionary<string, object> runtime)
        {
            string signature = _json.Serialize(runtime);
            if (signature == _runtimeSignature) return;
            _runtimeSignature = signature;
            string state = S(runtime, "state");
            bool waiting = B(runtime, "waiting");
            bool busy = B(runtime, "busy");
            if (state.Length == 0) state = busy ? "preparing" : (waiting ? "waiting" : "idle");
            _vm.Runtime.StateName = state;
            string title = "尚未启动", chip = "空闲", tone = "idle", glyph = "IconPower", primary = "启动准备";
            bool primaryEnabled = _connected, abortVisible = false, abortEnabled = false;
            bool stopEnabled = _connected && (waiting || busy);
            bool progressVisible = false, indeterminate = false;
            string detail = S(runtime, "detail");
            if (detail.Length == 0) detail = S(runtime, "status_text");
            if (detail.Length == 0) detail = "设置工作簿与识别环境，启动准备后等待快捷键。";
            if (detail.Contains("磁盘已满") || detail.Contains("磁盘空间不足")) {
                if(detail!=_lastDiskError) _pendingDiskError=detail;
                ShowPendingDiskError();
            } else if(_pendingDiskError.Length==0) _lastDiskError="";
            string hint = S(runtime, "hint");

            if (state == "preparing")
            {
                title = "正在准备…"; chip = "准备中"; tone = "progress"; glyph = "IconRefresh";
                primary = "正在准备"; primaryEnabled = false; progressVisible = true;
                if (hint.Length == 0) hint = "准备完成后进入等待快捷键；不会自动开始任务。";
            }
            else if (state == "waiting")
            {
                title = "等待快捷键"; chip = "监听中"; tone = "ready"; glyph = "IconRadio";
                primary = "监听中"; primaryEnabled = false;
                if (detail.Length == 0) detail = "模型已就绪，切回游戏后按对应快捷键执行任务。";
                if (hint.Length == 0) hint = "三种任务分别由快捷键触发，无需在主页预选任务。";
            }
            else if (state == "running")
            {
                string task = TaskName(runtime);
                title = task + "进行中"; chip = "扫描中"; tone = "running"; glyph = "IconScan";
                primary = "任务进行中"; primaryEnabled = false; abortVisible = true; abortEnabled = _connected;
                progressVisible = true;
                if (detail.Length == 0) detail = "正在执行任务，请按需使用中止快捷键。";
                if (hint.Length == 0) hint = "中止会先完成当前输入动作并释放鼠标，随后保留监听与已加载模型。";
            }
            else if (state == "stopping")
            {
                title = "正在中止…"; chip = "中止中"; tone = "stopping"; glyph = "IconStop";
                primary = "正在中止"; primaryEnabled = false; abortVisible = true; abortEnabled = false;
                progressVisible = true; indeterminate = true;
                if (detail.Length == 0) detail = "正在完成当前输入动作并释放鼠标；快捷键监听与模型将在中止后保留。";
                if (hint.Length == 0) hint = "请等待当前动作收尾，无需关闭程序。";
            }
            else if (state == "success")
            {
                title = "任务完成"; chip = "已完成"; tone = "success"; glyph = "IconCheckCircle";
                primary = waiting ? "监听中" : "启动准备"; primaryEnabled = !waiting;
                if (detail.Length == 0) detail = "任务完成；快捷键监听与识别模型保持就绪。";
                if (hint.Length == 0) hint = "可直接开始下一次任务；停止监听不会退出程序。";
            }
            else if (state == "failure")
            {
                title = "任务失败"; chip = "需处理"; tone = "failure"; glyph = "IconAlert";
                primary = waiting ? "监听中" : "重新准备"; primaryEnabled = !waiting;
                if (detail.Length == 0) detail = "任务未完成，请查看日志并处理异常后重试。";
                if (hint.Length == 0) hint = "失败终态已记录；必要时导出错误资料。";
            }
            else if (state == "nogame")
            {
                title = "未找到游戏窗口"; chip = "需要处理"; tone = "nogame"; glyph = "IconGamepad";
                primary = "重新检测窗口"; primaryEnabled = _connected;
                if (detail.Length == 0) detail = "没有找到可捕获的原神窗口。请确认游戏已启动，再刷新捕获窗口。";
                if (hint.Length == 0) hint = "重新检测只刷新窗口状态，不会自动开始任务。";
            }
            if (hint.Length == 0) hint = "启动准备完成后进入等待快捷键；停止监听不会退出程序。";

            Dictionary<string, object> progress = AsDict(runtime, "progress");
            string progressLabel = "正在执行";
            if (progress != null)
            {
                if (B(progress, "visible")) progressVisible = true;
                if (B(progress, "indeterminate")) indeterminate = true;
                if (S(progress, "label").Length > 0) progressLabel = S(progress, "label");
                object pv;
                if (progress.TryGetValue("value", out pv) && pv != null)
                {
                    double value = ToDouble(pv, -1);
                    if (value >= 0) { _vm.Runtime.ProgressValue = Math.Max(0, Math.Min(100, value)); _vm.Runtime.ProgressText = ((int)Math.Round(value)) + "%"; indeterminate = false; }
                }
            }
            if (indeterminate) _vm.Runtime.ProgressText = "处理中";
            _vm.Runtime.Title = title;
            _vm.Runtime.Chip = chip;
            _vm.Runtime.Tone = tone;
            _vm.Runtime.Detail = detail;
            _vm.Runtime.Hint = hint;
            _vm.Runtime.PrimaryLabel = primary;
            _vm.Runtime.PrimaryEnabled = primaryEnabled;
            _vm.Runtime.AbortVisible = abortVisible;
            _vm.Runtime.AbortEnabled = abortEnabled;
            _vm.Runtime.StopEnabled = stopEnabled;
            _vm.Runtime.CheckEnabled = _connected;
            _vm.Runtime.ProgressVisible = progressVisible;
            _vm.Runtime.ProgressIndeterminate = indeterminate;
            _vm.Runtime.ProgressLabel = progressLabel;
            SetTone(tone, glyph);

            _vm.Runtime.Listening = waiting ? "监听中" : (busy ? "准备中" : "已关闭");
            int shortcutCount = CountShortcuts();
            _vm.Runtime.ListeningSub = waiting ? shortcutCount + " 组快捷键" : (busy ? "准备完成后开启" : "尚未启动");
            int loaded = I(runtime, "models_loaded", -1), total = I(runtime, "models_total", -1);
            _vm.Runtime.Models = loaded >= 0 || total >= 0 ? (loaded >= 0 ? loaded.ToString() : "—") + " / " + (total >= 0 ? total.ToString() : "—") : "— / —";
            int actual = I(runtime, "actual_workers", -1);
            _vm.Runtime.Lanes = _vm.Settings.SingleWorkers + " / " + (actual >= 0 ? actual.ToString() : "—");
            _vm.Runtime.LaneSub = actual >= 0 && actual < _vm.Settings.SingleWorkers ? "受内存预算限制" : "启动时按内存预算调整";
            _vm.Runtime.LaneFeatureText = "启动时按可用内存调整 · 本次实际 " + (actual >= 0 ? actual.ToString() : "—") + " 路";
            _vm.Runtime.TaskSummary = StarSummary();

            Dictionary<string, object> capture = AsDict(runtime, "capture");
            string captureName = capture != null ? S(capture, "name") : "";
            string captureMeta = capture != null ? S(capture, "meta") : "";
            string captureText = capture != null ? S(capture, "text") : "";
            bool found = capture != null ? B(capture, "found") : (captureName.Length > 0);
            if (captureName.Length == 0 && captureText.Length > 0)
            {
                string cleaned = captureText.StartsWith("当前捕获窗口") ? captureText.Substring(captureText.IndexOfAny(new char[] { '：', ':' }) + 1).Trim() : captureText;
                string[] parts = cleaned.Split(new char[] { '·' }, StringSplitOptions.RemoveEmptyEntries);
                if (parts.Length > 0) { captureName = parts[0].Trim(); captureMeta = parts.Length > 1 ? parts[1].Trim() : ""; }
            }
            _vm.Runtime.CaptureName = found ? (captureName.Length > 0 ? captureName : "已检测") : "未检测到游戏窗口";
            _vm.Runtime.CaptureMeta = found ? (captureMeta.Length > 0 ? captureMeta : "窗口捕获") : "请确认游戏已启动后刷新";
            _vm.Runtime.CaptureStatus = capture != null && S(capture, "status").Length > 0 ? S(capture, "status") : (found ? "已检测" : "未找到");
            _vm.Runtime.Window = found ? _vm.Runtime.CaptureName : "未找到";
            _vm.Runtime.WindowSub = found ? _vm.Runtime.CaptureMeta : "请刷新捕获窗口";

            Dictionary<string, object> shortcuts = AsDict(runtime, "shortcuts");
            if (shortcuts != null) ApplyShortcuts(shortcuts);
            UpdateOverlayUI();
        }

        int CountShortcuts()
        {
            int count = 0;
            if (_vm.Settings.ShortcutFull.Length > 0) count++;
            if (_vm.Settings.ShortcutSingle.Length > 0) count++;
            if (_vm.Settings.ShortcutPuzzle.Length > 0) count++;
            if (_vm.Settings.ShortcutAbort.Length > 0) count++;
            if (_vm.Settings.ShortcutStop.Length > 0) count++;
            if (_vm.Settings.ShortcutOverlay.Length > 0) count++;
            return count;
        }

        void ApplyShortcuts(Dictionary<string, object> shortcuts)
        {
            string full = S(shortcuts, "full"), single = S(shortcuts, "single"), puzzle = S(shortcuts, "puzzle");
            string abort = S(shortcuts, "abort"), stop = S(shortcuts, "stop"), overlay = S(shortcuts, "overlay");
            if (full.Length > 0) { _vm.Runtime.ShortcutFull = full; _vm.Settings.ShortcutFull = full; }
            if (single.Length > 0) { _vm.Runtime.ShortcutSingle = single; _vm.Settings.ShortcutSingle = single; }
            if (puzzle.Length > 0) { _vm.Runtime.ShortcutPuzzle = puzzle; _vm.Settings.ShortcutPuzzle = puzzle; }
            if (abort.Length > 0) { _vm.Runtime.ShortcutAbort = abort; _vm.Settings.ShortcutAbort = abort; }
            if (stop.Length > 0) { _vm.Runtime.ShortcutStop = stop; _vm.Settings.ShortcutStop = stop; }
            if (overlay.Length > 0) { _vm.Runtime.ShortcutOverlay = overlay; _vm.Settings.ShortcutOverlay = overlay; }
        }

        void ApplySpace(Dictionary<string, object> space)
        {
            Find<Border>("SpaceUpdateNotice").Visibility = B(space,"update_pending") ? Visibility.Visible : Visibility.Collapsed;
            string readError=S(space,"refresh_error");
            Find<TextBlock>("SpaceRefreshProgress").Text=readError.Length>0 ? "读取失败，请重试" : "正在刷新…";
            Find<TextBlock>("SpaceRefreshProgress").ToolTip=readError;
            Find<TextBlock>("SpaceRefreshProgress").Visibility = B(space,"refreshing") || readError.Length>0 ? Visibility.Visible : Visibility.Collapsed;
            string signature = _json.Serialize(space);
            if (signature == _spaceSignature) return;
            _spaceSignature = signature;
            List<object> segments = AsList(space, "segments");
            long sum = 0;
            List<SegmentItem> list = new List<SegmentItem>();
            if (segments != null)
            {
                foreach (object item in segments)
                {
                    Dictionary<string, object> d = item as Dictionary<string, object>;
                    if (d == null) continue;
                    long bytes = L(d, "bytes");
                    sum += Math.Max(0, bytes);
                    list.Add(new SegmentItem { Label = S(d, "label"), Bytes = bytes, SizeText = FormatBytes(bytes), Brush = MakeBrush(S(d, "color").Length > 0 ? S(d, "color") : "#8E9B92") });
                }
            }
            if (list.Count == 0)
            {
                long screenshots = 0, diagnostics = 0;
                List<object> rawBatches = AsList(_raw, "batches");
                if (rawBatches != null)
                {
                    foreach (object item in rawBatches)
                    {
                        Dictionary<string, object> batch = item as Dictionary<string, object>;
                        if (batch == null) continue;
                        long bytes = L(batch, "bytes");
                        if (S(batch, "kind") == "diagnostics") diagnostics += bytes; else screenshots += bytes;
                    }
                }
                long jsonBytes = L(space, "json_bytes");
                long workbookBytes = L(space, "workbook_bytes");
                long learningBytes = L(space, "learning_bytes");
                if (screenshots > 0) list.Add(new SegmentItem { Label = "截图批次", Bytes = screenshots, SizeText = FormatBytes(screenshots), Brush = MakeBrush("#1D7961") });
                if (diagnostics > 0) list.Add(new SegmentItem { Label = "诊断摘要", Bytes = diagnostics, SizeText = FormatBytes(diagnostics), Brush = MakeBrush("#4E7F99") });
                if (jsonBytes > 0) list.Add(new SegmentItem { Label = "格式化 JSON", Bytes = jsonBytes, SizeText = FormatBytes(jsonBytes), Brush = MakeBrush("#C19343") });
                if (workbookBytes > 0) list.Add(new SegmentItem { Label = "工作簿", Bytes = workbookBytes, SizeText = FormatBytes(workbookBytes), Brush = MakeBrush("#8E9B92") });
                if (learningBytes > 0) list.Add(new SegmentItem { Label = "学习成果", Bytes = learningBytes, SizeText = FormatBytes(learningBytes), Brush = MakeBrush("#7C719B") });
                sum = 0;
                foreach (SegmentItem segment in list) sum += segment.Bytes;
            }
            long used = L(space, "used_bytes");
            if (used <= 0) used = sum;
            long cleanable = L(space, "cleanable_bytes");
            long protectedBytes = L(space, "protected_bytes");
            long free = L(space, "free_bytes");
            _vm.Space.Path = S(space, "path").Length > 0 ? S(space, "path") : "正在读取…";
            _vm.Space.Used = used > 0 || list.Count > 0 ? FormatBytes(used) : "—";
            _vm.Space.Cleanable = FormatBytes(cleanable);
            _vm.Space.Protected = FormatBytes(protectedBytes);
            _vm.Space.Free = space.ContainsKey("free_bytes") ? FormatBytes(free) : "—";
            _vm.Space.Segments.Clear();
            foreach (SegmentItem segment in list) _vm.Space.Segments.Add(segment);
            _vm.Space.ProtectWorkbook = SegmentSize(list, "工作簿");
            _vm.Space.ProtectJson = SegmentSize(list, "格式化 JSON");
            _vm.Space.ProtectLearning = SegmentSize(list, "学习成果");
            BuildStorageBar(list, used > 0 ? used : sum);
        }

        void BuildStorageBar(List<SegmentItem> segments, long total)
        {
            Grid track = Find<Grid>("StorageTrack");
            track.Children.Clear();
            track.ColumnDefinitions.Clear();
            if (segments.Count == 0 || total <= 0) return;
            for (int i = 0; i < segments.Count; ++i)
            {
                ColumnDefinition column = new ColumnDefinition();
                column.Width = new GridLength(Math.Max(0.01, (double)segments[i].Bytes / total), GridUnitType.Star);
                track.ColumnDefinitions.Add(column);
                Border bar = new Border();
                bar.Background = segments[i].Brush;
                bar.Margin = new Thickness(0, 0, 1, 0);
                bar.ToolTip = segments[i].Label + " " + segments[i].SizeText;
                Grid.SetColumn(bar, i);
                track.Children.Add(bar);
            }
        }

        long SegmentBytes(List<SegmentItem> segments, int index)
        {
            if (index < 0 || index >= segments.Count) return 0;
            string text = segments[index].SizeText;
            return ParseSize(text);
        }

        static List<object> ChronologicalBatches(List<object> batches)
        {
            List<object> ordered = new List<object>();
            foreach (object item in batches) if (item is Dictionary<string,object>) ordered.Add(item);
            ordered.Sort(delegate(object left, object right) {
                Dictionary<string,object> a=(Dictionary<string,object>)left, b=(Dictionary<string,object>)right;
                int time=L(b,"modified_ns").CompareTo(L(a,"modified_ns"));
                return time!=0 ? time : string.Compare(S(b,"name"),S(a,"name"),StringComparison.Ordinal);
            });
            return ordered;
        }

        void ApplyBatches(List<object> batches)
        {
            batches = ChronologicalBatches(batches);
            string signature = _json.Serialize(batches);
            if (signature == _batchesSignature) return;
            _batchesSignature = signature;
            HashSet<string> selected = new HashSet<string>();
            foreach (BatchItem old in _vm.Batches) if (old.IsSelected) selected.Add(old.Name);
            _vm.Batches.Clear();
            Brush normal = MakeBrush("#FBFCFA");
            Brush active = MakeBrush("#F1F8F4");
            foreach (object item in batches)
            {
                Dictionary<string, object> d = item as Dictionary<string, object>;
                if (d == null) continue;
                string name = S(d, "name");
                object protectedValue;
                d.TryGetValue("protected", out protectedValue);
                string protectedReason = protectedValue is string ? (string)protectedValue : (protectedValue is bool && (bool)protectedValue ? "受保护" : "");
                bool isProtected = protectedReason.Length > 0;
                bool reclaimable = d.ContainsKey("reclaimable") ? B(d, "reclaimable") : !isProtected;
                bool recordOnly=B(d,"record_only");
                if (!reclaimable && protectedReason.Length == 0) protectedReason = "资料暂不可清理";
                BatchItem batch = new BatchItem();
                batch.Name = name;
                batch.Title = S(d, "task").Length > 0 ? S(d, "task") : (S(d, "kind") == "diagnostics" ? "诊断摘要" : "扫描批次");
                batch.Stars = S(d, "stars");
                batch.StatusText = S(d,"status_text");
                batch.Meta = BatchMeta(d, name);
                batch.Bytes = L(d, "bytes");
                batch.Files = I(d, "files", 0);
                batch.SizeText = FormatBytes(batch.Bytes);
                batch.Reason = protectedReason;
                batch.Protected = isProtected || !reclaimable;
                batch.CanSelect = !batch.Protected;
                batch.StateText = batch.Protected ? "受保护" : "可清理";
                if(recordOnly)batch.Meta+=" · 仅任务日志，无截图";
                batch.NormalBackground = normal;
                batch.SelectedBackground = active;
                batch.IsSelected = selected.Contains(name);
                batch.PropertyChanged += Batch_PropertyChanged;
                _vm.Batches.Add(batch);
            }
            _batchView.Refresh();
            UpdateFilterCounts();
            UpdateSelection();
        }

        void Batch_PropertyChanged(object sender, PropertyChangedEventArgs e)
        {
            if (e.PropertyName == "IsSelected" || e.PropertyName == "RowBackground") UpdateSelection();
        }

        bool BatchFilter(object item)
        {
            BatchItem batch = item as BatchItem;
            if (batch == null) return false;
            if (_filter == 1) return batch.CanSelect;
            if (_filter == 2) return batch.Protected;
            return true;
        }

        void SetFilter(int filter)
        {
            _filter = filter;
            _batchView.Refresh();
            UpdateFilterCounts();
            UpdateSelection();
        }

        void UpdateFilterCounts()
        {
            int cleanable = 0, protectedCount = 0;
            foreach (BatchItem batch in _vm.Batches)
            {
                if (batch.Protected) protectedCount++; else if(batch.CanSelect) cleanable++;
            }
            Find<Button>("FilterAll").Content = "全部 " + _vm.Batches.Count;
            Find<Button>("FilterCleanable").Content = "可清理 " + cleanable;
            Find<Button>("FilterProtected").Content = "受保护 " + protectedCount;
            SetFilterLook(Find<Button>("FilterAll"), _filter == 0);
            SetFilterLook(Find<Button>("FilterCleanable"), _filter == 1);
            SetFilterLook(Find<Button>("FilterProtected"), _filter == 2);
        }

        void SetFilterLook(Button button, bool active)
        {
            button.Background = active ? MakeBrush("#E4F1EB") : MakeBrush("#F3F6F1");
            button.Foreground = active ? MakeBrush("#0D5544") : MakeBrush("#738079");
        }

        void UpdateSelection()
        {
            int count = 0;
            long bytes = 0;
            bool allCleanable = true;
            int cleanableCount = 0;
            foreach (BatchItem batch in _vm.Batches)
            {
                if (batch.Protected) continue;
                cleanableCount++;
                if (batch.IsSelected) { count++; bytes += batch.Bytes; }
                else allCleanable = false;
            }
            if (count == 0)
            {
                _vm.SelectionSummary = "尚未选择批次";
                _vm.SelectionHint = "仅可勾选未受保护的批次";
                _vm.SelectionCanClean = false;
            }
            else
            {
                _vm.SelectionSummary = "已选 " + count + " 个批次 · " + FormatBytes(bytes);
                _vm.SelectionHint = "清理前会展示具体范围与容量";
                _vm.SelectionCanClean = true;
            }
            Find<Button>("SelectAllCleanable").Content = cleanableCount > 0 && allCleanable ? "取消全选" : "全选可清理";
        }

        void ToggleAllCleanable()
        {
            bool all = true;
            foreach (BatchItem batch in _vm.Batches) if (batch.CanSelect && !batch.IsSelected) { all = false; break; }
            foreach (BatchItem batch in _vm.Batches) if (batch.CanSelect) batch.IsSelected = !all;
            UpdateSelection();
        }

        void ApplyIssues(List<object> issues)
        {
            string signature = _json.Serialize(issues);
            if (signature == _issuesSignature) return;
            _issuesSignature = signature;
            string selectedId = _vm.SelectedIssue == null ? "" : _vm.SelectedIssue.Id;
            _vm.Issues.Clear();
            foreach (object item in issues)
            {
                Dictionary<string, object> d = item as Dictionary<string, object>;
                if (d == null) continue;
                IssueItem issue = new IssueItem();
                issue.Id = S(d, "id");
                issue.Task = S(d, "task");
                issue.OccurredAt = S(d, "occurred_at");
                issue.Message = S(d, "message");
                issue.BatchName = S(d, "batch_name");
                issue.Display = issue.OccurredAt + " · " + issue.Task + " · " + issue.Message;
                _vm.Issues.Add(issue);
            }
            IssueItem selected = null;
            foreach (IssueItem issue in _vm.Issues) if (issue.Id == selectedId) { selected = issue; break; }
            _vm.SelectedIssue = selected != null ? selected : (_vm.Issues.Count > 0 ? _vm.Issues[0] : null);
            UpdateExportNote();
        }

        void UpdateExportNote()
        {
            IssueItem issue = _vm.SelectedIssue;
            _vm.ExportEnabled = _connected && issue != null;
            if (issue == null)
            {
                _vm.ExportSelectionNote = _connected ? "暂无可导出的错误记录。失败或异常任务会自动出现在这里。" : "正在读取错误记录。";
                return;
            }
            string scope = issue.BatchName.Length > 0 ? "已关联本任务批次 " + issue.BatchName + "。" : "尚未关联扫描批次，可导出已有错误日志。";
            _vm.ExportSelectionNote = issue.OccurredAt + " · " + issue.Task + " · " + issue.Message + "。" + scope;
        }

        void ApplyPerformance(Dictionary<string, object> performance)
        {
            string signature = _json.Serialize(performance);
            if (signature == _performanceSignature) return;
            _performanceSignature = signature;
            _vm.Performance.CpuApp = Metric(performance, "cpu", "app");
            _vm.Performance.CpuSys = Metric(performance, "cpu", "sys");
            _vm.Performance.GpuApp = Metric(performance, "gpu", "app");
            _vm.Performance.GpuSys = Metric(performance, "gpu", "sys");
            _vm.Performance.MemApp = Metric(performance, "memory", "app");
            _vm.Performance.MemSys = Metric(performance, "memory", "sys");
        }

        string Metric(Dictionary<string, object> performance, string name, string key)
        {
            Dictionary<string, object> metric = AsDict(performance, name);
            if (metric == null) return "—";
            string text = S(metric, key + "_text");
            if (text.Length > 0) return text;
            object value;
            if (metric.TryGetValue(key, out value) && value != null) return ToDouble(value, 0).ToString("0.##") + "%";
            return "—";
        }

        void ApplyLogs(List<object> logs)
        {
            string signature = _json.Serialize(logs);
            if (signature == _logsSignature) return;
            _logsSignature = signature;
            _vm.Logs.Clear();
            int count = 0;
            foreach (object item in logs)
            {
                if (count++ >= 80) break;
                Dictionary<string, object> d = item as Dictionary<string, object>;
                if (d == null) continue;
                LogItem log = new LogItem();
                log.Time = S(d, "time");
                log.Text = S(d, "text");
                log.ToneBrush = ToneBrush(S(d, "tone"));
                _vm.Logs.Add(log);
            }
            _vm.Runtime.LatestLog = _vm.Logs.Count > 0 ? _vm.Logs[0].Text : "暂无运行日志";
            _vm.Runtime.LogCount = _vm.Logs.Count + " 条记录";
            _vm.Runtime.LogDotBrush = _vm.Logs.Count > 0 ? _vm.Logs[0].ToneBrush : MakeBrush("#9AA69F");
        }

        void ApplyOverlay(Dictionary<string, object> overlay)
        {
            bool locked = B(overlay, "locked") || B(overlay, "auto_locked");
            _overlayLocked = locked;
            _vm.OverlayLock = locked ? "已锁定 · 鼠标穿透" : "可编辑 · 可拖动缩放";
            _vm.OverlayLockBadge = locked ? "已锁定" : "可编辑";
        }

        void Settings_Changed(object sender, SettingChangedEventArgs e)
        {
            if (_applying) return;
            // A rejected local edit must still accept the unchanged owner snapshot.
            _settingsSignature = "";
            SendSet(e.Name, e.Value);
            if (e.Name == "cleanup_mode" || e.Name == "auto_cleanup" || e.Name == "keep_batches" || e.Name == "keep_days") UpdateAutoUI();
            if (e.Name == "xlsx_target") UpdateWorkbookUI();
            if (e.Name == "overlay_visible" || e.Name == "overlay_performance" || e.Name == "overlay_exclude" || e.Name == "overlay_opacity") UpdateOverlayUI();
            if (e.Name == "single_workers" || e.Name == "scan_stars" || e.Name == "row_info") UpdateTaskSummary();
            _saveTimer.Stop();
            _saveTimer.Start();
        }

        void ViewModel_PropertyChanged(object sender, PropertyChangedEventArgs e)
        {
            if (e.PropertyName == "SelectedIssue") UpdateExportNote();
        }

        void ChangeLanes(int delta)
        {
            _vm.Settings.SingleWorkers = Math.Max(1, Math.Min(4, _vm.Settings.SingleWorkers + delta));
            UpdateTaskSummary();
        }

        void ChangeKeepBatches(int delta)
        {
            _vm.Settings.KeepBatches = Math.Max(1, _vm.Settings.KeepBatches + delta);
            UpdateAutoUI();
        }

        void ToggleStar(int star, ToggleButton button)
        {
            if (button.IsChecked == true)
            {
                _stars.Add(star);
            }
            else
            {
                if (_stars.Count <= 1)
                {
                    button.IsChecked = true;
                    ShowToast("星级筛选至少保留一项。");
                    return;
                }
                _stars.Remove(star);
            }
            UpdateStars();
            UpdateTaskSummary();
            SendSet("scan_stars", new List<int>(_stars));
            _saveTimer.Stop();
            _saveTimer.Start();
        }

        void UpdateStars()
        {
            Find<ToggleButton>("Star5").IsChecked = _stars.Contains(5);
            Find<ToggleButton>("Star4").IsChecked = _stars.Contains(4);
            Find<ToggleButton>("Star3").IsChecked = _stars.Contains(3);
            Find<ToggleButton>("Star2").IsChecked = _stars.Contains(2);
        }

        void UpdateTaskSummary()
        {
            _vm.Runtime.TaskSummary = StarSummary();
            _vm.Runtime.Lanes = _vm.Settings.SingleWorkers + " / " + (_vm.Runtime.Lanes.Contains("/") ? _vm.Runtime.Lanes.Split('/')[1].Trim() : "—");
            _vm.Runtime.LaneFeatureText = "启动时按可用内存调整 · 本次实际 " + (_vm.Runtime.Lanes.Contains("/") ? _vm.Runtime.Lanes.Split('/')[1].Trim() : "—") + " 路";
        }

        string StarSummary()
        {
            List<int> values = new List<int>(_stars);
            values.Sort();
            values.Reverse();
            if (values.Count == 0) return "未选星级";
            StringBuilder builder = new StringBuilder();
            for (int i = 0; i < values.Count; ++i)
            {
                if (i > 0) builder.Append(" / ");
                builder.Append(values[i]).Append("★");
            }
            return builder.ToString();
        }

        void UpdateWorkbookUI()
        {
            _vm.Settings.WorkbookModeLabel = _workbookExisting ? "指定工作簿" : "自动新建";
            _vm.Settings.WorkbookMeta = _workbookExisting
                ? "指定工作簿；启动准备时校验可写性。"
                : "留空时本次会话自动新建；指定时追加到已有文件。";
            _vm.Settings.PickVisible = _workbookExisting;
            SetSegmentLook(Find<Button>("WorkbookAuto"), !_workbookExisting);
            SetSegmentLook(Find<Button>("WorkbookExisting"), _workbookExisting);
        }

        void SetSegmentLook(Button button, bool active)
        {
            button.Background = active ? MakeBrush("#E4F1EB") : MakeBrush("#F3F6F1");
            button.BorderBrush = active ? MakeBrush("#9CC4B0") : MakeBrush("#DDE4DD");
            button.Foreground = active ? MakeBrush("#0D5544") : MakeBrush("#3E4D46");
        }

        void UpdateAutoUI()
        {
            bool enabled = _vm.Settings.AutoCleanup;
            bool days = _vm.Settings.CleanupMode == "days";
            _vm.AutoStateText = !enabled ? "已关闭 · 默认手动按批清理"
                : (days ? "已开启 · 按保留天数清理" : "已开启 · 按保留批次清理");
            _vm.AutoHint = days
                ? "按时间保留最近 " + _vm.Settings.KeepDays + " 天内的可清理批次；更早批次视为候选。"
                : "按数量保留最近 " + _vm.Settings.KeepBatches + " 个可清理批次；更早批次视为候选。";
            Find<StackPanel>("AutoBatchesOption").Visibility = enabled && !days ? Visibility.Visible : Visibility.Collapsed;
            Find<StackPanel>("AutoDaysOption").Visibility = enabled && days ? Visibility.Visible : Visibility.Collapsed;
            SetSegmentLook(Find<Button>("AutoBatches"), !days);
            SetSegmentLook(Find<Button>("AutoDays"), days);
        }

        void UpdateOverlayUI()
        {
            bool visible = _vm.Settings.OverlayVisible;
            bool locked = _overlayLocked;
            _vm.OverlayModeChip = !visible ? "已隐藏" : (_vm.Runtime.Listening == "监听中" ? "监听中" : "未监听");
            _vm.OverlayStateTitle = !visible ? "浮窗已隐藏" : _vm.Runtime.Title;
            _vm.OverlayLaneLine = "请求 " + _vm.Settings.SingleWorkers + " · 实际 " + ActualLanes() + " · 模型 " + _vm.Runtime.Models;
            _vm.OverlayPerfLine = _vm.Settings.OverlayPerformance
                ? "CPU " + _vm.Performance.CpuApp + " · GPU " + _vm.Performance.GpuApp + " · 内存 " + _vm.Performance.MemApp
                : "性能显示已关闭";
            _vm.OverlayLockBadge = locked ? "已锁定" : "可编辑";
            _vm.OverlayLock = locked ? "已锁定 · 鼠标穿透" : "可编辑 · 可拖动缩放";
            _vm.OverlayExcludeNote = _vm.Settings.OverlayExclude
                ? "默认开启。此项调整其他软件捕获浮窗的可见性；扫描器始终依照游戏窗口取图。"
                : "已关闭。其他软件捕获画面时可能包含浮窗；扫描器仍只读取游戏窗口。";
        }

        string ActualLanes()
        {
            if (_vm.Runtime.Lanes.Contains("/")) return _vm.Runtime.Lanes.Split('/')[1].Trim();
            return "—";
        }

        void SetPage(string page)
        {
            _switching = true;
            Find<ScrollViewer>("PageScan").Visibility = page == "scan" ? Visibility.Visible : Visibility.Collapsed;
            Find<ScrollViewer>("PageSpace").Visibility = page == "space" ? Visibility.Visible : Visibility.Collapsed;
            Find<ScrollViewer>("PageSettings").Visibility = page == "settings" ? Visibility.Visible : Visibility.Collapsed;
            Find<ScrollViewer>("PageHelp").Visibility = page == "help" ? Visibility.Visible : Visibility.Collapsed;
            Find<RadioButton>("NavScan").IsChecked = page == "scan";
            Find<RadioButton>("NavSpace").IsChecked = page == "space";
            Find<RadioButton>("NavSettings").IsChecked = page == "settings";
            Find<RadioButton>("NavHelp").IsChecked = page == "help";
            _vm.CurrentPageTitle = page == "scan" ? "扫描主页" : page == "space" ? "产出 / 空间" : page == "settings" ? "设置" : "教程 / 许可 / 关于";
            _switching = false;
            Dictionary<string,object> notice=new Dictionary<string,object>();
            notice["type"]="page";notice["page"]=page;
            Send(notice);
        }

        void SetHelpTab(string tab)
        {
            if (tab == "license") SendAction("documents",null,null);
            Find<StackPanel>("PictureGuidePanel").Visibility = tab == "pictures" ? Visibility.Visible : Visibility.Collapsed;
            Find<Grid>("GuidePanel").Visibility = tab == "guide" ? Visibility.Visible : Visibility.Collapsed;
            Find<Border>("LicensePanel").Visibility = tab == "license" ? Visibility.Visible : Visibility.Collapsed;
            Find<Border>("AboutPanel").Visibility = tab == "about" ? Visibility.Visible : Visibility.Collapsed;
            SetSubTab(Find<Button>("TabPictures"), tab == "pictures");
            SetSubTab(Find<Button>("TabGuide"), tab == "guide");
            SetSubTab(Find<Button>("TabLicense"), tab == "license");
            SetSubTab(Find<Button>("TabAbout"), tab == "about");
        }

        void SetSubTab(Button button, bool active)
        {
            button.Background = active ? MakeBrush("#E4F1EB") : Brushes.Transparent;
            button.Foreground = active ? MakeBrush("#0D5544") : MakeBrush("#738079");
        }

        void ScrollTo(string name)
        {
            FrameworkElement element = Find<FrameworkElement>(name);
            element.BringIntoView();
            element.BringIntoView();
        }

        void ToggleLog(bool expanded)
        {
            Find<Border>("LogBody").Visibility = expanded ? Visibility.Visible : Visibility.Collapsed;
            _vm.Runtime.LogToggleLabel = expanded ? "收起日志" : "展开日志";
            if (expanded) Find<Border>("LogPanel").BringIntoView();
        }

        bool CanEditShortcuts()
        {
            Dictionary<string,object> runtime=AsDict(_raw,"runtime");
            if (!_connected || B(runtime,"waiting") || B(runtime,"busy"))
            {
                Find<TextBlock>("ShortcutCaptureStatus").Text="请先停止监听，再录入快捷键。";
                return false;
            }
            return true;
        }

        void BeginShortcut(TextBox box)
        {
            if (!CanEditShortcuts()) return;
            _capturingShortcut=box.Name;
            box.Focus();
            Find<TextBlock>("ShortcutCaptureStatus").Text="请按下按键或组合键，Esc取消。";
        }

        void CaptureShortcut(object sender,KeyEventArgs e)
        {
            if (_capturingShortcut == null) return;
            e.Handled=true;
            Key key=e.Key==Key.System ? e.SystemKey : e.Key;
            if (key==Key.Escape)
            {
                _capturingShortcut=null;
                Find<TextBlock>("ShortcutCaptureStatus").Text="已取消录入。";
                return;
            }
            int vk=KeyInterop.VirtualKeyFromKey(key);
            if (vk==0 || vk==16 || vk==17 || vk==18 || vk==91 || vk==92 || (vk>=160 && vk<=165)) return;
            ModifierKeys modifiers=Keyboard.Modifiers;
            string specification="";
            if ((modifiers & ModifierKeys.Control)!=0) specification+="ctrl+";
            if ((modifiers & ModifierKeys.Alt)!=0) specification+="alt+";
            if ((modifiers & ModifierKeys.Shift)!=0) specification+="shift+";
            if ((modifiers & ModifierKeys.Windows)!=0) specification+="win+";
            if ((vk>=48 && vk<=57) || (vk>=65 && vk<=90)) specification+=((char)vk).ToString().ToLowerInvariant();
            else if (vk>=112 && vk<=135) specification+="f"+(vk-111).ToString();
            else specification+="vk"+vk.ToString("x2");
            string[] boxes={"ShortcutFullBox","ShortcutSingleBox","ShortcutPuzzleBox","ShortcutAbortBox","ShortcutStopBox","ShortcutOverlayBox"};
            string[] names={"hotkey","single_hotkey","montage_hotkey","cancel_hotkey","quit_hotkey","overlay_hotkey"};
            int index=Array.IndexOf(boxes,_capturingShortcut);
            _capturingShortcut=null;
            Dictionary<string,object> values=new Dictionary<string,object>();
            values[names[index]]=specification;
            SubmitShortcuts(values);
        }

        void SubmitShortcuts(Dictionary<string,object> values)
        {
            Dictionary<string,object> arguments=new Dictionary<string,object>();
            arguments["values"]=values;
            Find<TextBlock>("ShortcutCaptureStatus").Text="正在保存快捷键…";
            SendAction("update_shortcuts",arguments,null);
        }

        void ResetShortcuts()
        {
            if (!CanEditShortcuts()) return;
            string[] names={"hotkey","single_hotkey","montage_hotkey","cancel_hotkey","quit_hotkey","overlay_hotkey"};
            string[] keys={"s","d","p","x","q","o"};
            Dictionary<string,object> values=new Dictionary<string,object>();
            for (int index=0;index<names.Length;index++) values[names[index]]="ctrl+alt+"+keys[index];
            SubmitShortcuts(values);
        }

        void PickWorkbook()
        {
            if (!CanOpenFileAction()) return;
            Microsoft.Win32.OpenFileDialog picker=new Microsoft.Win32.OpenFileDialog();
            picker.Filter="Excel工作簿 (*.xlsx)|*.xlsx";
            if (picker.ShowDialog(_window)==true) _vm.Settings.WorkbookPath=picker.FileName;
        }

        void NestedScroll(object sender,MouseWheelEventArgs e)
        {
            DependencyObject element=e.OriginalSource as DependencyObject;
            ScrollViewer inner=null,outer=null;
            while (element!=null)
            {
                ScrollViewer scroll=element as ScrollViewer;
                if (scroll!=null)
                {
                    if (inner==null) inner=scroll;
                    else { outer=scroll;break; }
                }
                element=element is Visual ? VisualTreeHelper.GetParent(element) : LogicalTreeHelper.GetParent(element);
            }
            if (inner==null || outer==null) return;
            bool edge=e.Delta>0 ? inner.VerticalOffset<=0 : inner.VerticalOffset>=inner.ScrollableHeight;
            if (!edge) return;
            int lines=SystemParameters.WheelScrollLines;
            if (lines<0) { if (e.Delta>0) outer.PageUp();else outer.PageDown(); }
            else for (int index=0;index<lines;index++) { if (e.Delta>0) outer.LineUp();else outer.LineDown(); }
            e.Handled=true;
        }

        void ConvertJson()
        {
            if (!CanOpenFileAction()) return;
            Microsoft.Win32.OpenFileDialog source=new Microsoft.Win32.OpenFileDialog();
            source.Filter="格式化JSON (*.json)|*.json";
            if (source.ShowDialog(_window)!=true) return;
            Microsoft.Win32.SaveFileDialog target=new Microsoft.Win32.SaveFileDialog();
            target.Filter="Excel工作簿 (*.xlsx)|*.xlsx";
            target.DefaultExt=".xlsx";
            if (target.ShowDialog(_window)!=true) return;
            Dictionary<string,object> arguments=new Dictionary<string,object>();
            arguments["source"]=source.FileName;
            arguments["output"]=target.FileName;
            SendAction("convert_json",arguments,Find<Button>("ConvertJson"));
        }

        bool CanOpenFileAction()
        {
            Dictionary<string,object> runtime=AsDict(_raw,"runtime");
            if (!_connected || B(runtime,"waiting") || B(runtime,"busy"))
            {
                ShowToast("请停止监听并等待当前任务完成。 ");
                return false;
            }
            return true;
        }

        void ShowCleanupModal()
        {
            List<BatchItem> selected = new List<BatchItem>();
            long total = 0;
            foreach (BatchItem batch in _vm.Batches) if (batch.IsSelected && !batch.Protected) { selected.Add(batch); total += batch.Bytes; }
            if (selected.Count == 0) { ShowToast("请先选择至少一个可清理批次。"); return; }
            StringBuilder body = new StringBuilder();
            body.AppendLine("清理前请核对本次范围。删除在任务与学习队列空闲时执行。");
            body.AppendLine();
            body.AppendLine("批次数量：" + selected.Count + " 个");
            body.AppendLine("预计释放：" + FormatBytes(total));
            body.AppendLine("保留内容：工作簿 / JSON / 学习");
            body.AppendLine();
            foreach (BatchItem batch in selected) body.AppendLine("· " + batch.Title + " · " + batch.Meta + " · " + batch.SizeText);
            body.AppendLine();
            body.AppendLine("以下内容保持不变：用户Excel、学习成果以及仍在使用的资料。已结束任务的结果 JSON 会一起清理。");
            List<string> names = new List<string>();
            foreach (BatchItem batch in selected) names.Add(batch.Name);
            ShowModal("空间管理", "确认清理 " + selected.Count + " 个批次？", "确认后执行清理，页面不直接删除文件。", body.ToString(), "确认清理", true, delegate
            {
                Dictionary<string, object> args = new Dictionary<string, object>();
                args["names"] = names;
                SendAction("cleanup_batches", args, null);
                ShowToast("已提交清理，等待完成并刷新空间。");
            });
        }

        void ShowExportModal()
        {
            IssueItem issue = _vm.SelectedIssue;
            if (issue == null) { ShowToast("暂无可导出的错误记录。"); return; }
            StringBuilder body = new StringBuilder();
            body.AppendLine(issue.OccurredAt + " · " + issue.Task);
            body.AppendLine();
            body.AppendLine(issue.Message);
            body.AppendLine();
            body.AppendLine(issue.BatchName.Length > 0
                ? "已关联本任务批次 " + issue.BatchName + "；其他任务、工作簿、全局学习库与运行依赖保留原位。"
                : "该错误没有可用批次，仅导出已有错误记录与任务日志。");
            ShowModal("错误导出", "导出这次错误的相关资料", "已自动定位错误所属任务，无需从全部批次中查找。", body.ToString(), "选择位置并导出", false, delegate
            {
                Dictionary<string, object> args = new Dictionary<string, object>();
                args["id"] = issue.Id;
                Microsoft.Win32.SaveFileDialog picker=new Microsoft.Win32.SaveFileDialog();
                picker.Filter="错误资料包 (*.zip)|*.zip";
                picker.FileName="错误_"+issue.Id+".zip";
                if (picker.ShowDialog(_window)!=true) return;
                args["output"]=picker.FileName;
                SendAction("export_error", args, null);
                ShowToast("正在导出错误资料。");
            });
        }

        void ShowModal(string kicker, string title, string description, string body, string confirmLabel, bool danger, Action action)
        {
            Find<TextBlock>("ModalKicker").Text = kicker;
            Find<TextBlock>("ModalTitle").Text = title;
            Find<TextBlock>("ModalDescription").Text = description;
            Find<TextBlock>("ModalBody").Text = body;
            Button confirm = Find<Button>("ModalConfirm");
            confirm.Content = confirmLabel;
            confirm.Style = (Style)_window.FindResource(danger ? "DangerButton" : "PrimaryButton");
            _modalAction = action;
            Find<Grid>("ModalLayer").Visibility = Visibility.Visible;
        }

        void HideModal()
        {
            Find<Grid>("ModalLayer").Visibility = Visibility.Collapsed;
            _modalAction = null;
            ShowPendingDiskError();
        }

        void ShowToast(string text)
        {
            if (string.IsNullOrEmpty(text)) return;
            Find<TextBlock>("ToastText").Text = text;
            Find<Border>("Toast").Visibility = Visibility.Visible;
            _toastTimer.Stop();
            _toastTimer.Start();
        }

        void SetConnected(bool connected)
        {
            _connected = connected;
            _vm.HostBadge = connected ? "本地运行" : "正在读取";
            _vm.HostCardState = connected ? "已连接" : "正在连接";
            _vm.HostCardDetail = connected
                ? "状态更新于 " + DateTime.Now.ToString("HH:mm:ss") + "；文件与操作由扫描器执行。"
                : "正在等待扫描器状态。";
            _vm.HostFooter = connected ? "本地运行 · 已连接" : "正在读取状态";
            _vm.HostDotBrush = connected ? MakeBrush("#5BC49E") : MakeBrush("#8FA197");
            _vm.Runtime.CheckEnabled = connected;
            if (!connected)
            {
                _vm.Runtime.PrimaryEnabled = false;
                _vm.Runtime.StopEnabled = false;
                _vm.Runtime.AbortEnabled = false;
                _vm.ExportEnabled = false;
            }
        }

        void SetTone(string tone, string glyph)
        {
            string solid = "#738079", soft = "#F3F6F1";
            if (tone == "progress") { solid = "#3E7390"; soft = "#E8F1F5"; }
            else if (tone == "ready") { solid = "#126B56"; soft = "#E4F1EB"; }
            else if (tone == "running") { solid = "#1D7961"; soft = "#E4F1EB"; }
            else if (tone == "stopping") { solid = "#B57A22"; soft = "#FBF1DD"; }
            else if (tone == "success") { solid = "#2E7C63"; soft = "#E8F3ED"; }
            else if (tone == "failure") { solid = "#B24D3D"; soft = "#FBECE8"; }
            else if (tone == "nogame") { solid = "#B57A22"; soft = "#FBF1DD"; }
            _vm.Runtime.ToneBrush = MakeBrush(solid);
            _vm.Runtime.ToneSoftBrush = MakeBrush(soft);
            _vm.Runtime.StateGlyph = _window.TryFindResource(glyph) as Geometry;
        }

        static Dictionary<string, object> Merge(Dictionary<string, object> baseValue, Dictionary<string, object> patch)
        {
            Dictionary<string, object> result = new Dictionary<string, object>();
            if (baseValue != null) foreach (KeyValuePair<string, object> pair in baseValue) result[pair.Key] = pair.Value;
            if (patch != null)
            {
                foreach (KeyValuePair<string, object> pair in patch)
                {
                    Dictionary<string, object> oldDict = null, newDict = pair.Value as Dictionary<string, object>;
                    if (newDict != null) oldDict = result.ContainsKey(pair.Key) ? result[pair.Key] as Dictionary<string, object> : null;
                    result[pair.Key] = newDict != null && oldDict != null ? Merge(oldDict, newDict) : pair.Value;
                }
            }
            return result;
        }

        static Dictionary<string, object> AsDict(Dictionary<string, object> source, string key)
        {
            if (source == null || !source.ContainsKey(key)) return null;
            return source[key] as Dictionary<string, object>;
        }

        static Dictionary<string, object> AsDict(object value)
        {
            return value as Dictionary<string, object>;
        }

        static List<object> AsList(Dictionary<string, object> source, string key)
        {
            if (source == null || !source.ContainsKey(key)) return null;
            return AsList(source[key]);
        }

        static List<object> AsList(object value)
        {
            if (value == null) return null;
            object[] array = value as object[];
            if (array != null) return new List<object>(array);
            IList list = value as IList;
            if (list != null) { List<object> result = new List<object>(); foreach (object item in list) result.Add(item); return result; }
            return null;
        }

        static string S(Dictionary<string, object> source, string key)
        {
            if (source == null || !source.ContainsKey(key) || source[key] == null) return "";
            return Convert.ToString(source[key], System.Globalization.CultureInfo.InvariantCulture);
        }

        static int I(Dictionary<string, object> source, string key, int fallback)
        {
            if (source == null || !source.ContainsKey(key)) return fallback;
            return ToInt(source[key], fallback);
        }

        static long L(Dictionary<string, object> source, string key)
        {
            if (source == null || !source.ContainsKey(key)) return 0;
            object value = source[key];
            if (value == null) return 0;
            long parsed;
            if (value is long) return (long)value;
            if (value is int) return (long)(int)value;
            if (value is double) return (long)(double)value;
            if (long.TryParse(Convert.ToString(value, System.Globalization.CultureInfo.InvariantCulture), out parsed)) return parsed;
            return 0;
        }

        static double D(Dictionary<string, object> source, string key, double fallback)
        {
            if (source == null || !source.ContainsKey(key)) return fallback;
            return ToDouble(source[key], fallback);
        }

        static bool B(Dictionary<string, object> source, string key)
        {
            if (source == null || !source.ContainsKey(key) || source[key] == null) return false;
            object value = source[key];
            if (value is bool) return (bool)value;
            bool parsed;
            return bool.TryParse(Convert.ToString(value, System.Globalization.CultureInfo.InvariantCulture), out parsed) && parsed;
        }

        static int ToInt(object value, int fallback)
        {
            if (value == null) return fallback;
            try { return Convert.ToInt32(value, System.Globalization.CultureInfo.InvariantCulture); }
            catch { return fallback; }
        }

        static double ToDouble(object value, double fallback)
        {
            if (value == null) return fallback;
            try { return Convert.ToDouble(value, System.Globalization.CultureInfo.InvariantCulture); }
            catch { return fallback; }
        }

        static string TaskName(Dictionary<string, object> runtime)
        {
            Dictionary<string, object> task = AsDict(runtime, "task");
            if (task != null && S(task, "label").Length > 0) return S(task, "label");
            string mode = task != null ? S(task, "mode") : "";
            if (mode == "full") return "整趟扫描";
            if (mode == "single") return "单卡识别";
            if (mode == "puzzle") return "拼图识别";
            return "扫描任务";
        }

        string BatchMeta(Dictionary<string, object> batch, string name)
        {
            List<string> parts = new List<string>();
            long modified = L(batch, "modified_ns");
            if (modified > 0)
            {
                try { parts.Add(new DateTime(1970, 1, 1, 0, 0, 0, DateTimeKind.Utc).AddTicks(modified / 100).ToLocalTime().ToString("yyyy-MM-dd HH:mm")); }
                catch { }
            }
            int files = I(batch, "files", 0);
            if (files > 0) parts.Add(files + " 个文件");
            parts.Add(name);
            return string.Join(" · ", parts.ToArray());
        }

        string SegmentSize(List<SegmentItem> segments, string label)
        {
            foreach (SegmentItem segment in segments) if (segment.Label == label) return segment.SizeText;
            return "";
        }

        long ParseSize(string text)
        {
            if (string.IsNullOrEmpty(text)) return 0;
            string[] parts = text.Split(' ');
            double number;
            if (!double.TryParse(parts[0], out number)) return 0;
            string unit = parts.Length > 1 ? parts[1] : "B";
            if (unit == "KiB") return (long)(number * 1024);
            if (unit == "MiB") return (long)(number * 1024 * 1024);
            if (unit == "GiB") return (long)(number * 1024 * 1024 * 1024);
            if (unit == "TiB") return (long)(number * 1024 * 1024 * 1024 * 1024);
            return (long)number;
        }

        static string FormatBytes(long bytes)
        {
            string[] units = new string[] { "B", "KiB", "MiB", "GiB", "TiB" };
            double value = Math.Max(0, bytes);
            int index = 0;
            while (value >= 1024 && index < units.Length - 1) { value /= 1024; index++; }
            return value.ToString(value >= 100 || index == 0 ? "0" : "0.#", System.Globalization.CultureInfo.InvariantCulture) + " " + units[index];
        }

        static bool IsFocused(FrameworkElement element)
        {
            return element != null && element.IsKeyboardFocusWithin;
        }

        static Brush MakeBrush(string color)
        {
            try
            {
                SolidColorBrush brush = new SolidColorBrush((Color)ColorConverter.ConvertFromString(color));
                brush.Freeze();
                return brush;
            }
            catch { return Brushes.Gray; }
        }

        static Brush ToneBrush(string tone)
        {
            if (tone == "success") return MakeBrush("#2E7C63");
            if (tone == "danger") return MakeBrush("#B24D3D");
            if (tone == "warn") return MakeBrush("#B57A22");
            if (tone == "info") return MakeBrush("#3E7390");
            return MakeBrush("#9AA69F");
        }

        static Dictionary<string, object> SoundArgs(string kind)
        {
            Dictionary<string, object> args = new Dictionary<string, object>();
            args["kind"] = kind;
            return args;
        }
    }
}
