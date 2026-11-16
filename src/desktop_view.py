# Required Notice: Copyright (c) 2026 DrMoMing (https://github.com/DrMoMing/GenshinRewardScanner)
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# AI-generated project code: written and modified with OpenAI Codex.
"""Native Tk/ttk desktop view for the Domain Scanner.

This module is UI-only. It does not scan, read or write files, clean data,
build archives, start processes/threads, register global keys or load models.
The existing application owns task state and supplies Tk variables, the
existing log/progress widgets, and callbacks through bindings/actions."""

import tkinter as tk
from tkinter import ttk


BG = "#eef1ec"
PAPER = "#fbfcfa"
WHITE = "#ffffff"
DARK = "#14211d"
DARK_ACTIVE = "#1d2e27"
BRAND = "#126b56"
BRAND_DARK = "#0d5544"
BRAND_SOFT = "#e4f1eb"
INK = "#17231e"
BODY = "#3e4d46"
MUTED = "#738079"
FAINT = "#98a49d"
BORDER = "#dce3dc"
SOFT = "#f3f6f1"
AMBER = "#9a7426"
AMBER_SOFT = "#fbf2de"
RED = "#b24d3d"
RED_SOFT = "#fbece8"
SIDEBAR_TEXT = "#dbe6df"
SIDEBAR_MUTED = "#8fa197"
FONT_FAMILY = "Microsoft YaHei UI"


class _ScrollPage:
    """A narrow page shell with a normal vertical scrollbar."""

    def __init__(self, parent, bg):
        self.outer = tk.Frame(parent, bg=bg)
        self.outer.grid_rowconfigure(0, weight=1)
        self.outer.grid_columnconfigure(0, weight=1)

        self.canvas = tk.Canvas(
            self.outer,
            bg=bg,
            highlightthickness=0,
            borderwidth=0,
            yscrollincrement=18,
        )
        self.scrollbar = ttk.Scrollbar(
            self.outer, orient="vertical", command=self.canvas.yview
        )
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.scrollbar.grid(row=0, column=1, sticky="ns")

        self.body = tk.Frame(self.canvas, bg=bg)
        self.window = self.canvas.create_window((0, 0), window=self.body, anchor="nw")
        self.body.bind("<Configure>", self._update_scrollregion)
        self.canvas.bind("<Configure>", self._match_width)

        self.content = tk.Frame(self.body, bg=bg)
        self.content.pack(fill="both", expand=True, padx=18, pady=16)

    def _update_scrollregion(self, _event=None):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _match_width(self, event):
        self.canvas.itemconfigure(self.window, width=max(1, event.width))


class DesktopView:
    """The native desktop shell used by the real scanner application."""

    PAGE_NAMES = (
        ("scan", "扫描主页"),
        ("space", "产出 / 空间"),
        ("settings", "设置"),
        ("help", "教程 / 许可"),
    )

    def __init__(self, root, parent, bindings, actions):
        self.root = root
        self.parent = parent
        self.bindings = bindings
        self.actions = actions or {}

        self._traces = []
        self._closed = False
        self._waiting = False
        self._busy = False
        self._selected_batch_names = set()
        self._selected_issue_id = ""
        self._batches = []
        self._issues = []
        self._batch_rows = {}
        self._issue_rows = {}
        self._syncing_batch_selection = False
        self._syncing_issue_selection = False
        self._syncing_opacity = False

        self.log_widget = self._required_widget("log_widget")
        self.progress_widget = self._required_widget("progress_widget")

        self._last_keep_batches = self._parse_positive(
            self._get("keep_batches").get(), fallback=1
        )
        self._summary_var = tk.StringVar(
            master=root,
            value="尚未读取空间数据，点击“刷新空间”查看。",
        )
        self._workbook_mode_var = tk.StringVar(master=root, value="当前：自动新建")
        self._actual_workers_var = tk.StringVar(master=root, value="实际并行：—")
        self._batch_selection_var = tk.StringVar(master=root, value="未选择可清理批次")
        self._batch_hint_var = tk.StringVar(
            master=root, value="受保护批次不可清理；仅可清理批次可被选中。"
        )
        self._issue_detail_var = tk.StringVar(master=root, value="暂无错误记录。")
        self._opacity_display = tk.StringVar(master=root, value="72%")
        self._opacity_proxy = tk.DoubleVar(
            master=root, value=float(self._safe_int(self._get("overlay_opacity").get(), 72))
        )

        self._prepare_btn = None
        self._stop_btn = None
        self._workers_buttons = []
        self._workbook_controls = []
        self._busy_controls = []
        self._star_checks = []
        self._sound_preview_buttons = []
        self._auto_settings = None
        self._auto_batches_row = None
        self._auto_days_row = None
        self._auto_batch_entry = None
        self._batch_tree = None
        self._issue_tree = None
        self._cleanup_btn = None
        self._export_btn = None
        self._tutorial_canvas = None
        self._nav_buttons = {}
        self._pages = {}

        self._build_styles()
        self._build_shell()
        self._build_pages()
        self._install_traces()
        self._sync_workbook_mode()
        self._sync_opacity_from_binding()
        self._sync_auto_controls()
        self._sync_sound_preview_state()
        self._show_page("scan")
        self._apply_runtime_state()

    # ------------------------------------------------------------------
    # Interface and small helpers
    # ------------------------------------------------------------------

    def _required_widget(self, name):
        widget = self.bindings.get(name)
        if widget is None:
            raise ValueError(
                "bindings['%s'] must be the existing widget; "
                "DesktopView does not create a replacement." % name
            )
        return widget

    def _get(self, name):
        if name not in self.bindings:
            raise KeyError("bindings['%s'] is required" % name)
        return self.bindings[name]

    def _act(self, name, *args):
        callback = None
        try:
            callback = self.actions.get(name)
        except AttributeError:
            callback = getattr(self.actions, name, None)
        if callable(callback):
            callback(*args)

    def _font(self, size=9, bold=False):
        return (FONT_FAMILY, size, "bold" if bold else "normal")

    def _safe_int(self, value, fallback=0):
        try:
            return int(str(value).strip())
        except (TypeError, ValueError):
            return fallback

    def _parse_positive(self, value, fallback=1):
        try:
            number = int(str(value).strip())
        except (TypeError, ValueError):
            return fallback
        return number if number > 0 else fallback

    def _normalize_keep_batches(self):
        raw = str(self._get("keep_batches").get()).strip()
        value = self._parse_positive(raw, 0)
        if value <= 0:
            value = self._last_keep_batches
        self._last_keep_batches = value
        try:
            if str(self._get("keep_batches").get()).strip() != str(value):
                self._get("keep_batches").set(str(value))
        except tk.TclError:
            pass

    def _save_preferences(self):
        # Every preference save carries a valid positive batch count. This
        # also protects saves triggered by sound/overlay changes while the
        # auto-clean card is hidden.
        self._normalize_keep_batches()
        self._act("save_preferences")

    def _build_styles(self):
        style = ttk.Style(self.root)
        style.configure(
            "Desktop.Treeview",
            background=WHITE,
            fieldbackground=WHITE,
            foreground=INK,
            rowheight=25,
            borderwidth=0,
            font=self._font(9),
        )
        style.configure(
            "Desktop.Treeview.Heading",
            background=SOFT,
            foreground=BODY,
            font=self._font(9, True),
            relief="flat",
            padding=(6, 4),
        )
        style.map(
            "Desktop.Treeview",
            background=[("selected", BRAND_SOFT)],
            foreground=[("selected", INK)],
        )
        style.configure("Desktop.TEntry", padding=4)
        style.configure("Desktop.TCombobox", padding=2)

    def _label(
        self,
        parent,
        text="",
        variable=None,
        size=9,
        color=BODY,
        bg=None,
        bold=False,
        wrap=0,
        justify="left",
        anchor="w",
    ):
        options = {
            "text": text,
            "font": self._font(size, bold),
            "fg": color,
            "bg": bg or parent.cget("bg"),
            "anchor": anchor,
            "justify": justify,
        }
        if variable is not None:
            options["textvariable"] = variable
        if wrap:
            options["wraplength"] = wrap
        return tk.Label(parent, **options)

    def _button(self, parent, text, command, kind="quiet", small=False, width=None):
        palettes = {
            "primary": (BRAND, WHITE, BRAND_DARK, WHITE),
            "quiet": (SOFT, BODY, "#e8eee9", INK),
            "danger": (RED_SOFT, RED, "#f5ddd6", RED),
            "dark": (DARK_ACTIVE, "#eef7f2", "#263c33", WHITE),
        }
        bg, fg, active_bg, active_fg = palettes.get(kind, palettes["quiet"])
        options = {
            "text": text,
            "command": command,
            "font": self._font(8 if small else 9, True),
            "bg": bg,
            "fg": fg,
            "activebackground": active_bg,
            "activeforeground": active_fg,
            "disabledforeground": FAINT,
            "relief": tk.FLAT,
            "bd": 0,
            "highlightthickness": 0,
            "padx": 8 if small else 11,
            "pady": 3 if small else 5,
            "cursor": "hand2",
        }
        if width is not None:
            options["width"] = width
        return tk.Button(parent, **options)

    def _check(self, parent, text, variable, command=None, bg=None, size=9):
        background = bg or parent.cget("bg")
        options = {
            "text": text,
            "variable": variable,
            "font": self._font(size),
            "bg": background,
            "fg": BODY,
            "activebackground": background,
            "activeforeground": INK,
            "selectcolor": background,
            "anchor": "w",
            "justify": "left",
            "bd": 0,
            "highlightthickness": 0,
        }
        if command is not None:
            options["command"] = command
        return tk.Checkbutton(parent, **options)

    def _hline(self, parent, pady=(7, 7)):
        line = tk.Frame(parent, bg=BORDER, height=1)
        line.pack(fill="x", pady=pady)
        return line

    def _page_header(self, content, eyebrow, title, subtitle, actions=None):
        header = tk.Frame(content, bg=BG)
        header.pack(fill="x", pady=(0, 12))

        left = tk.Frame(header, bg=BG)
        left.pack(side="left", fill="x", expand=True)
        self._label(
            left,
            text=eyebrow,
            size=8,
            color=BRAND,
            bold=True,
        ).pack(anchor="w")
        self._label(left, text=title, size=16, color=INK, bold=True).pack(
            anchor="w", pady=(1, 1)
        )
        self._label(left, text=subtitle, size=9, color=MUTED, wrap=560).pack(
            anchor="w"
        )

        if actions:
            right = tk.Frame(header, bg=BG)
            right.pack(side="right", anchor="n", padx=(12, 0))
            for label, callback, kind in actions:
                self._button(right, label, callback, kind=kind, small=True).pack(
                    side="left", padx=(0, 6)
                )
        return header

    def _panel(self, parent, title, subtitle="", subtitle_wrap=600):
        panel = tk.Frame(
            parent,
            bg=PAPER,
            highlightbackground=BORDER,
            highlightcolor=BORDER,
            highlightthickness=1,
            bd=0,
        )
        inner = tk.Frame(panel, bg=PAPER)
        inner.pack(fill="both", expand=True, padx=14, pady=12)
        self._label(inner, text=title, size=11, color=INK, bold=True).pack(anchor="w")
        if subtitle:
            self._label(inner, text=subtitle, size=8, color=MUTED, wrap=subtitle_wrap).pack(
                anchor="w", pady=(2, 0)
            )
        body = tk.Frame(inner, bg=PAPER)
        body.pack(fill="both", expand=True, pady=(8, 0))
        return panel, body

    # ------------------------------------------------------------------
    # Shell, navigation and page lifecycle, all inside parent
    # ------------------------------------------------------------------

    def _build_shell(self):
        self.parent.grid_rowconfigure(0, weight=1)
        self.parent.grid_columnconfigure(0, weight=1)

        self.shell = tk.Frame(self.parent, bg=BG)
        try:
            self.shell.grid(row=0, column=0, sticky="nsew")
        except tk.TclError:
            # The owner normally clears a grid-based parent. Keep a pack
            # fallback for integrations where the old container used pack.
            self.shell.pack(fill="both", expand=True)
        self.shell.grid_rowconfigure(1, weight=1)
        self.shell.grid_columnconfigure(0, minsize=184, weight=0)
        self.shell.grid_columnconfigure(1, weight=1)

        topbar = tk.Frame(self.shell, bg=DARK, height=44)
        topbar.grid(row=0, column=0, columnspan=2, sticky="ew")
        topbar.grid_propagate(False)

        brand = tk.Frame(topbar, bg=DARK)
        brand.pack(side="left", padx=(14, 0), fill="y")
        tk.Label(
            brand,
            text="原境扫描器",
            bg=DARK,
            fg="#f2f8f4",
            font=self._font(12, True),
        ).pack(side="left", pady=10)
        tk.Label(
            brand,
            text="素材识别与工作簿记录",
            bg=DARK,
            fg=SIDEBAR_MUTED,
            font=self._font(8),
        ).pack(side="left", padx=(10, 0), pady=(13, 10))

        tk.Label(
            topbar,
            text="Windows 桌面工具",
            bg=DARK,
            fg=SIDEBAR_MUTED,
            font=self._font(8),
        ).pack(side="right", padx=(0, 16), pady=13)

        self.sidebar = tk.Frame(self.shell, bg=DARK)
        self.sidebar.grid(row=1, column=0, sticky="nsew")
        self.sidebar.pack_propagate(False)

        tk.Label(
            self.sidebar,
            text="工作台",
            bg=DARK,
            fg="#647a70",
            font=self._font(8, True),
        ).pack(anchor="w", padx=18, pady=(18, 8))

        nav_host = tk.Frame(self.sidebar, bg=DARK)
        nav_host.pack(fill="x", padx=10)
        for key, text in self.PAGE_NAMES:
            row = tk.Frame(nav_host, bg=DARK)
            row.pack(fill="x", pady=2)
            accent = tk.Frame(row, bg=DARK, width=3)
            accent.pack(side="left", fill="y")
            button = tk.Button(
                row,
                text=text,
                command=lambda page=key: self._show_page(page),
                bg=DARK,
                fg=SIDEBAR_TEXT,
                activebackground=DARK_ACTIVE,
                activeforeground="#f1faf5",
                font=self._font(10),
                anchor="w",
                justify="left",
                padx=13,
                pady=9,
                bd=0,
                relief=tk.FLAT,
                highlightthickness=0,
                cursor="hand2",
            )
            button.pack(side="left", fill="x", expand=True)
            self._nav_buttons[key] = (row, accent, button)

        sidebar_footer = tk.Frame(self.sidebar, bg=DARK)
        sidebar_footer.pack(side="bottom", fill="x", padx=16, pady=14)
        tk.Frame(sidebar_footer, bg="#2b3d35", height=1).pack(fill="x", pady=(0, 9))
        self._label(
            sidebar_footer,
            text="任务由游戏内快捷键触发。\n停止监听不会退出程序。",
            size=8,
            color=SIDEBAR_MUTED,
            bg=DARK,
            wrap=148,
        ).pack(anchor="w")

        self.content = tk.Frame(self.shell, bg=BG)
        self.content.grid(row=1, column=1, sticky="nsew")
        self.content.grid_rowconfigure(0, weight=1)
        self.content.grid_columnconfigure(0, weight=1)

        self.page_host = tk.Frame(self.content, bg=BG)
        self.page_host.grid(row=0, column=0, sticky="nsew")
        self.page_host.grid_rowconfigure(0, weight=1)
        self.page_host.grid_columnconfigure(0, weight=1)

    def _build_pages(self):
        for key, _text in self.PAGE_NAMES:
            page = _ScrollPage(self.page_host, BG)
            page.outer.grid(row=0, column=0, sticky="nsew")
            self._pages[key] = page

        self._build_scan_page(self._pages["scan"].content)
        self._build_space_page(self._pages["space"].content)
        self._build_settings_page(self._pages["settings"].content)
        self._build_help_page(self._pages["help"].content)

    def _show_page(self, key):
        for page_key, page in self._pages.items():
            if page_key == key:
                page.outer.grid()
            else:
                page.outer.grid_remove()

        for nav_key, (_row, accent, button) in self._nav_buttons.items():
            if nav_key == key:
                accent.configure(bg=BRAND)
                button.configure(
                    bg=DARK_ACTIVE,
                    fg="#f1faf5",
                    activebackground=DARK_ACTIVE,
                    activeforeground="#f1faf5",
                )
            else:
                accent.configure(bg=DARK)
                button.configure(
                    bg=DARK,
                    fg=SIDEBAR_TEXT,
                    activebackground=DARK_ACTIVE,
                    activeforeground="#f1faf5",
                )
        if key == "help" and self._tutorial_canvas is not None:
            self._draw_tutorial()

    # ------------------------------------------------------------------
    # Scan page
    # ------------------------------------------------------------------

    def _build_scan_page(self, content):
        self._page_header(
            content,
            "扫描工作台",
            "扫描主页",
            "设置识别环境并启动准备；任务由游戏内快捷键触发，界面不预选任务类型。",
        )

        status_panel, status_body = self._panel(
            content,
            "准备与运行状态",
            "准备完成后切回游戏，按对应快捷键开始任务。",
        )
        status_panel.pack(fill="x", pady=(0, 10))

        toolbar = tk.Frame(status_body, bg=PAPER)
        toolbar.pack(fill="x", pady=(0, 8))
        self._label(toolbar, text="会话控制", size=8, color=MUTED).pack(side="left")
        check_memory = self._button(
            toolbar, "检测内存", lambda: self._act("check_memory"), small=True
        )
        check_memory.pack(side="right")
        self._stop_btn = self._button(
            toolbar, "停止监听", lambda: self._act("stop"), kind="quiet"
        )
        self._stop_btn.pack(side="right", padx=(0, 6))
        self._prepare_btn = self._button(
            toolbar, "启动准备", lambda: self._act("prepare"), kind="primary"
        )
        self._prepare_btn.pack(side="right", padx=(0, 6))

        self._status_label = self._label(
            status_body,
            variable=self._get("status"),
            size=11,
            color=INK,
            bold=True,
            wrap=640,
            justify="left",
        )
        self._status_label.pack(fill="x", anchor="w")

        progress_line = tk.Frame(status_body, bg=PAPER)
        progress_line.pack(fill="x", pady=(9, 0))
        self._label(progress_line, text="加载进度", size=8, color=MUTED).pack(
            side="left"
        )
        progress_host = tk.Frame(progress_line, bg=PAPER)
        progress_host.pack(side="left", fill="x", expand=True, padx=(9, 0))
        progress_host.grid_columnconfigure(0, weight=1)
        progress_host.grid_rowconfigure(0, weight=1)
        try:
            self.progress_widget.grid_remove()
        except tk.TclError:
            pass
        try:
            self.progress_widget.pack_forget()
        except tk.TclError:
            pass
        try:
            # Grid once inside the new panel, then hide. The backend's later
            # grid() call restores this remembered placement.
            self.progress_widget.grid(
                in_=progress_host, row=0, column=0, sticky="ew"
            )
            self.progress_widget.grid_remove()
        except tk.TclError:
            pass

        info = tk.Frame(status_body, bg=PAPER)
        info.pack(fill="x", pady=(10, 0))
        info.grid_columnconfigure(1, weight=1)

        self._label(info, text="当前捕获窗口", size=8, color=MUTED).grid(
            row=0, column=0, sticky="nw", pady=2
        )
        self._label(
            info,
            variable=self._get("capture_target"),
            size=9,
            color=BODY,
            wrap=470,
        ).grid(row=0, column=1, sticky="w", padx=(10, 8), pady=2)
        refresh_target = self._button(
            info,
            "刷新捕获窗口",
            lambda: self._act("refresh_target"),
            small=True,
        )
        refresh_target.grid(row=0, column=2, sticky="ne", pady=1)

        self._label(info, text="工作簿连接", size=8, color=MUTED).grid(
            row=1, column=0, sticky="nw", pady=2
        )
        self._label(
            info,
            variable=self._get("connection"),
            size=9,
            color=BODY,
            wrap=580,
        ).grid(row=1, column=1, columnspan=2, sticky="w", padx=(10, 0), pady=2)

        self._label(info, text="单卡计数", size=8, color=MUTED).grid(
            row=2, column=0, sticky="nw", pady=2
        )
        self._label(
            info,
            variable=self._get("single_status"),
            size=9,
            color=BODY,
            wrap=580,
        ).grid(row=2, column=1, columnspan=2, sticky="w", padx=(10, 0), pady=2)

        settings_row = tk.Frame(content, bg=BG)
        settings_row.pack(fill="x", pady=(0, 10))
        settings_row.grid_columnconfigure(0, weight=1, uniform="scan_panel")
        settings_row.grid_columnconfigure(1, weight=1, uniform="scan_panel")

        settings_panel, settings_body = self._panel(
            settings_row,
            "识别设置",
            "用于下一次准备；请求路数与星级会显示在任务状态中。",
            subtitle_wrap=300,
        )
        settings_panel.grid(row=0, column=0, sticky="new", padx=(0, 5))

        workers_row = tk.Frame(settings_body, bg=PAPER)
        workers_row.pack(fill="x")
        self._label(workers_row, text="请求路数", size=9, color=BODY).pack(
            side="left"
        )
        minus = self._button(
            workers_row,
            "−",
            lambda: self._step_workers(-1),
            kind="quiet",
            small=True,
            width=2,
        )
        minus.pack(side="left", padx=(10, 2))
        self._label(
            workers_row,
            variable=self._get("workers"),
            size=11,
            color=INK,
            bold=True,
        ).pack(side="left", padx=4)
        plus = self._button(
            workers_row,
            "+",
            lambda: self._step_workers(1),
            kind="quiet",
            small=True,
            width=2,
        )
        plus.pack(side="left", padx=(2, 8))
        self._label(
            workers_row,
            variable=self._actual_workers_var,
            size=8,
            color=MUTED,
        ).pack(side="left")
        self._workers_buttons = [minus, plus]

        self._label(
            settings_body,
            text="1–4 路；准备时会按可用内存调整实际路数。",
            size=8,
            color=FAINT,
            wrap=300,
        ).pack(anchor="w", pady=(4, 8))

        self._hline(settings_body, pady=(0, 8))
        stars_row = tk.Frame(settings_body, bg=PAPER)
        stars_row.pack(fill="x")
        self._label(stars_row, text="星级筛选", size=9, color=BODY).pack(
            side="left", padx=(0, 8)
        )
        stars = self._get("stars")
        for grade in (5, 4, 3, 2):
            var = stars.get(grade)
            if var is None:
                continue
            check = self._check(stars_row, "%d★" % grade, var, size=9)
            check.pack(side="left", padx=(0, 6))
            self._busy_controls.append(check)
            self._star_checks.append(check)

        self._hline(settings_body, pady=(8, 8))
        row_info_check = self._check(
            settings_body,
            "横排读字",
            self._get("row_info"),
            size=9,
        )
        row_info_check.pack(anchor="w")
        self._busy_controls.append(row_info_check)
        self._label(
            settings_body,
            text="拼图任务读取横排文字信息；关闭时不识别文字。",
            size=8,
            color=FAINT,
            wrap=300,
        ).pack(anchor="w", pady=(2, 0))

        workbook_panel, workbook_body = self._panel(
            settings_row,
            "工作簿与输出",
            "工作簿路径留空时自动新建；指定已有工作簿时沿用该文件。",
            subtitle_wrap=300,
        )
        workbook_panel.grid(row=0, column=1, sticky="new", padx=(5, 0))

        self._label(
            workbook_body, text="工作簿路径", size=8, color=MUTED
        ).pack(anchor="w")
        target_entry = ttk.Entry(
            workbook_body,
            textvariable=self._get("target"),
            font=self._font(9),
            style="Desktop.TEntry",
        )
        target_entry.pack(fill="x", pady=(3, 4))
        self._workbook_controls.append(target_entry)

        choose_row = tk.Frame(workbook_body, bg=PAPER)
        choose_row.pack(fill="x", pady=(0, 5))
        choose_btn = self._button(
            choose_row,
            "选择已有工作簿",
            lambda: self._act("choose"),
            small=True,
        )
        choose_btn.pack(side="left")
        auto_new_btn = self._button(
            choose_row,
            "自动新建（清空路径）",
            self._clear_target,
            small=True,
        )
        auto_new_btn.pack(side="left", padx=(6, 0))
        self._workbook_controls.extend([choose_btn, auto_new_btn])

        self._label(
            workbook_body,
            variable=self._workbook_mode_var,
            size=8,
            color=BRAND,
            wrap=300,
        ).pack(anchor="w", pady=(0, 6))

        sheet_row = tk.Frame(workbook_body, bg=PAPER)
        sheet_row.pack(fill="x", pady=(0, 6))
        self._label(sheet_row, text="工作表名", size=8, color=MUTED).pack(
            side="left"
        )
        sheet_entry = ttk.Entry(
            sheet_row,
            textvariable=self._get("sheet"),
            font=self._font(9),
            width=16,
            style="Desktop.TEntry",
        )
        sheet_entry.pack(side="left", padx=(8, 0))
        self._workbook_controls.append(sheet_entry)

        live_check = self._check(
            workbook_body,
            "桌面 Excel/WPS 实时显示",
            self._get("live"),
            size=9,
        )
        live_check.pack(anchor="w")
        self._workbook_controls.append(live_check)
        self._label(
            workbook_body,
            text="工作表不存在时会按名称新建。",
            size=8,
            color=FAINT,
            wrap=300,
        ).pack(anchor="w", pady=(2, 0))

        shortcuts_panel, shortcuts_body = self._panel(
            content,
            "任务快捷键",
            "任务由游戏内快捷键触发；此处只显示当前设置。",
        )
        shortcuts_panel.pack(fill="x", pady=(0, 10))
        self._label(
            shortcuts_body,
            variable=self._get("keys"),
            size=9,
            color=BODY,
            wrap=640,
        ).pack(fill="x", anchor="w")
        self._label(
            shortcuts_body,
            text="中止当前任务后可继续使用快捷键；停止监听会结束本次扫描会话。",
            size=8,
            color=FAINT,
            wrap=640,
        ).pack(anchor="w", pady=(6, 0))

        log_panel, log_body = self._panel(
            content,
            "运行日志",
            "显示任务进度、处理结果及异常信息。",
        )
        log_panel.pack(fill="x")
        log_host = tk.Frame(log_body, bg=WHITE)
        log_host.pack(fill="x")
        log_host.grid_columnconfigure(0, weight=1)
        log_host.grid_rowconfigure(0, weight=1)

        try:
            self.log_widget.configure(
                height=8,
                wrap="word",
                font=self._font(9),
                background=WHITE,
                foreground=BODY,
                insertbackground=INK,
                relief=tk.FLAT,
                borderwidth=0,
                highlightthickness=0,
            )
        except tk.TclError:
            pass
        try:
            self.log_widget.grid_remove()
        except tk.TclError:
            pass
        try:
            self.log_widget.pack_forget()
        except tk.TclError:
            pass
        log_scroll = ttk.Scrollbar(log_host, orient="vertical", command=self.log_widget.yview)
        log_scroll.grid(row=0, column=1, sticky="ns")
        try:
            self.log_widget.configure(yscrollcommand=log_scroll.set)
        except tk.TclError:
            pass
        try:
            self.log_widget.grid(
                in_=log_host, row=0, column=0, sticky="nsew"
            )
        except tk.TclError:
            pass

    def _clear_target(self):
        try:
            self._get("target").set("")
            self._sync_workbook_mode()
        except tk.TclError:
            pass

    def _step_workers(self, delta):
        current = self._safe_int(self._get("workers").get(), 2)
        value = max(1, min(4, current + delta))
        self._get("workers").set(str(value))

    # ------------------------------------------------------------------

    def _install_traces(self):
        target = self._get("target")
        opacity = self._get("overlay_opacity")
        auto_enabled = self._get("auto_enabled")
        auto_mode = self._get("auto_mode")
        keep_batches = self._get("keep_batches")
        sound = self._get("sound")
        self._traces.append(
            ("target", target.trace_add("write", self._on_target_trace))
        )
        self._traces.append(
            ("overlay_opacity", opacity.trace_add("write", self._on_opacity_trace))
        )
        self._traces.append(
            ("keep_batches", keep_batches.trace_add("write", self._on_keep_batches_trace))
        )
        self._traces.append(
            ("sound", sound.trace_add("write", self._on_sound_trace))
        )
        self._traces.append(
            ("auto_enabled", auto_enabled.trace_add("write", self._on_auto_trace))
        )
        self._traces.append(
            ("auto_mode", auto_mode.trace_add("write", self._on_auto_trace))
        )
        self._traces.append(("status", self._get("status").trace_add("write", self._on_status_trace)))
        self._on_status_trace()

    def _on_status_trace(self, *_args):
        message = self._get("status").get()
        color = RED if any(word in message for word in ("内存不足", "资源保护", "提交额度", "降为", "失败")) else INK
        self._status_label.configure(fg=color)

    def _on_target_trace(self, *_args):
        self._sync_workbook_mode()

    def _sync_workbook_mode(self):
        try:
            value = str(self._get("target").get()).strip()
        except tk.TclError:
            value = ""
        if value:
            self._workbook_mode_var.set("当前：指定已有工作簿")
        else:
            self._workbook_mode_var.set("当前：自动新建（本次会话连续追加）")

    def _on_opacity_trace(self, *_args):
        self._sync_opacity_from_binding()

    def _sync_opacity_from_binding(self):
        if self._syncing_opacity:
            return
        raw_value = self._safe_int(self._get("overlay_opacity").get(), 72)
        value = max(20, min(95, raw_value))
        self._syncing_opacity = True
        try:
            self._opacity_proxy.set(float(value))
            self._opacity_display.set("%d%%" % value)
            if raw_value != value:
                self._get("overlay_opacity").set(value)
        finally:
            self._syncing_opacity = False

    def _on_opacity_scale(self, raw):
        try:
            value = int(round(float(raw)))
        except (TypeError, ValueError):
            return
        value = max(20, min(95, value))
        self._opacity_display.set("%d%%" % value)
        try:
            if self._safe_int(self._get("overlay_opacity").get(), -1) != value:
                self._get("overlay_opacity").set(value)
        except tk.TclError:
            pass

    def _on_keep_batches_trace(self, *_args):
        try:
            raw = str(self._get("keep_batches").get()).strip()
        except tk.TclError:
            return
        value = self._parse_positive(raw, 0)
        if value > 0:
            self._last_keep_batches = value

    def _on_sound_trace(self, *_args):
        self._sync_sound_preview_state()

    def _sync_sound_preview_state(self):
        try:
            enabled = bool(self._get("sound").get())
        except tk.TclError:
            enabled = True
        for button in self._sound_preview_buttons:
            try:
                button.configure(state=(tk.NORMAL if enabled else tk.DISABLED))
            except tk.TclError:
                pass

    def _on_sound_toggle(self):
        self._sync_sound_preview_state()
        self._save_preferences()

    def _on_auto_trace(self, *_args):
        self._sync_auto_controls()

    def _sync_auto_controls(self):
        if self._auto_settings is None:
            return
        enabled = bool(self._get("auto_enabled").get())
        mode = str(self._get("auto_mode").get() or "batches")
        if enabled:
            if self._auto_settings.winfo_manager() != "pack":
                self._auto_settings.pack(fill="x", pady=(4, 0))
        else:
            self._auto_settings.pack_forget()

        if mode == "days":
            if self._auto_batches_row is not None:
                self._auto_batches_row.grid_remove()
            if self._auto_days_row is not None:
                self._auto_days_row.grid()
        else:
            if self._auto_days_row is not None:
                self._auto_days_row.grid_remove()
            if self._auto_batches_row is not None:
                self._auto_batches_row.grid()

    # ------------------------------------------------------------------
    # Space page
    # ------------------------------------------------------------------

    def _build_space_page(self, content):
        self._page_header(
            content,
            "产出与存储",
            "产出 / 空间管理",
            "按批次管理截图和日志，也可导出指定错误任务的资料。",
            actions=[("刷新空间", lambda: self._act("refresh_space"), "quiet")],
        )

        summary_panel, summary_body = self._panel(
            content,
            "空间总览",
            "刷新可查看最新批次和可清理空间。",
        )
        summary_panel.pack(fill="x", pady=(0, 10))
        self._label(
            summary_body,
            variable=self._summary_var,
            size=9,
            color=BODY,
            wrap=640,
        ).pack(fill="x", anchor="w")
        summary_actions = tk.Frame(summary_body, bg=PAPER)
        summary_actions.pack(fill="x", pady=(8, 0))
        self._button(
            summary_actions,
            "打开输出目录",
            lambda: self._act("open_output"),
            small=True,
        ).pack(side="left")
        self._button(
            summary_actions,
            "JSON 转 Excel",
            lambda: self._act("convert_json"),
            small=True,
        ).pack(side="left", padx=(7, 0))

        batch_panel, batch_body = self._panel(
            content,
            "批次与容量",
            "任务或学习仍在使用的资料会自动保护。",
        )
        batch_panel.pack(fill="x", pady=(0, 10))

        batch_tree_host = tk.Frame(batch_body, bg=WHITE)
        batch_tree_host.pack(fill="x")
        batch_tree_host.grid_columnconfigure(0, weight=1)
        batch_tree_host.grid_rowconfigure(0, weight=1)
        self._batch_tree = ttk.Treeview(
            batch_tree_host,
            columns=("name", "size", "status"),
            show="headings",
            selectmode="extended",
            height=7,
            style="Desktop.Treeview",
        )
        self._batch_tree.heading("name", text="批次 / 任务", anchor="w")
        self._batch_tree.heading("size", text="容量", anchor="e")
        self._batch_tree.heading("status", text="状态 / 保护原因", anchor="w")
        self._batch_tree.column("name", width=300, minwidth=150, stretch=True)
        self._batch_tree.column("size", width=80, minwidth=65, stretch=False, anchor="e")
        self._batch_tree.column("status", width=220, minwidth=120, stretch=True)
        self._batch_tree.grid(row=0, column=0, sticky="nsew")
        batch_scroll = ttk.Scrollbar(
            batch_tree_host, orient="vertical", command=self._batch_tree.yview
        )
        batch_scroll.grid(row=0, column=1, sticky="ns")
        self._batch_tree.configure(yscrollcommand=batch_scroll.set)
        self._batch_tree.tag_configure("protected", foreground=AMBER)
        self._batch_tree.bind("<<TreeviewSelect>>", self._on_batch_select)

        self._label(
            batch_body,
            variable=self._batch_selection_var,
            size=8,
            color=MUTED,
        ).pack(anchor="w", pady=(7, 1))
        self._label(
            batch_body,
            variable=self._batch_hint_var,
            size=8,
            color=FAINT,
            wrap=640,
        ).pack(anchor="w", pady=(0, 7))

        batch_footer = tk.Frame(batch_body, bg=PAPER)
        batch_footer.pack(fill="x")
        self._cleanup_btn = self._button(
            batch_footer,
            "清理选中批次",
            self._cleanup_selected,
            kind="danger",
        )
        self._cleanup_btn.pack(side="right")
        self._cleanup_btn.configure(state=tk.DISABLED)

        error_panel, error_body = self._panel(
            content,
            "错误记录",
            "显示失败与异常任务，自动选中最新一条，并关联本次截图及日志。",
        )
        error_panel.pack(fill="x", pady=(0, 10))
        issue_tree_host = tk.Frame(error_body, bg=WHITE)
        issue_tree_host.pack(fill="x")
        issue_tree_host.grid_columnconfigure(0, weight=1)
        issue_tree_host.grid_rowconfigure(0, weight=1)
        self._issue_tree = ttk.Treeview(
            issue_tree_host,
            columns=("time", "task", "message"),
            show="headings",
            selectmode="browse",
            height=5,
            style="Desktop.Treeview",
        )
        self._issue_tree.heading("time", text="任务时间", anchor="w")
        self._issue_tree.heading("task", text="任务", anchor="w")
        self._issue_tree.heading("message", text="原因", anchor="w")
        self._issue_tree.column("time", width=125, minwidth=100, stretch=False)
        self._issue_tree.column("task", width=150, minwidth=100, stretch=False)
        self._issue_tree.column("message", width=360, minwidth=160, stretch=True)
        self._issue_tree.grid(row=0, column=0, sticky="nsew")
        issue_scroll = ttk.Scrollbar(
            issue_tree_host, orient="vertical", command=self._issue_tree.yview
        )
        issue_scroll.grid(row=0, column=1, sticky="ns")
        self._issue_tree.configure(yscrollcommand=issue_scroll.set)
        self._issue_tree.bind("<<TreeviewSelect>>", self._on_issue_select)

        self._label(
            error_body,
            variable=self._issue_detail_var,
            size=8,
            color=MUTED,
            wrap=640,
        ).pack(anchor="w", pady=(7, 7))
        error_actions = tk.Frame(error_body, bg=PAPER)
        error_actions.pack(fill="x")
        self._export_btn = self._button(
            error_actions,
            "导出该错误资料",
            self._export_selected,
            kind="quiet",
        )
        self._export_btn.pack(side="right")
        self._export_btn.configure(state=tk.DISABLED)

        auto_panel, auto_body = self._panel(
            content,
            "自动清理",
            "按批次数或天数保留资料，停止监听且空闲时自动清理。",
        )
        auto_panel.pack(fill="x", pady=(0, 4))
        self._check(
            auto_body,
            "启用自动清理",
            self._get("auto_enabled"),
            command=self._on_auto_toggle,
            size=9,
        ).pack(anchor="w")
        self._label(
            auto_body,
            text="JSON、工作簿与学习成果会保留。",
            size=8,
            color=FAINT,
            wrap=640,
        ).pack(anchor="w", pady=(2, 0))

        self._auto_settings = tk.Frame(auto_body, bg=PAPER)
        self._auto_settings.pack(fill="x", pady=(4, 0))
        mode_row = tk.Frame(self._auto_settings, bg=PAPER)
        mode_row.pack(fill="x", pady=(0, 4))
        self._label(mode_row, text="策略", size=8, color=MUTED).pack(
            side="left", padx=(0, 8)
        )
        self._radio(
            mode_row,
            "按批次数",
            self._get("auto_mode"),
            "batches",
            self._on_auto_mode,
        ).pack(side="left", padx=(0, 8))
        self._radio(
            mode_row,
            "按保留天数",
            self._get("auto_mode"),
            "days",
            self._on_auto_mode,
        ).pack(side="left")

        self._auto_mode_host = tk.Frame(self._auto_settings, bg=PAPER)
        self._auto_mode_host.pack(fill="x", pady=(4, 0))
        self._auto_mode_host.grid_columnconfigure(0, weight=1)

        self._auto_batches_row = tk.Frame(self._auto_mode_host, bg=PAPER)
        self._auto_batches_row.grid(row=0, column=0, sticky="ew")
        self._label(self._auto_batches_row, text="保留最近", size=9, color=BODY).pack(
            side="left"
        )
        self._button(
            self._auto_batches_row,
            "−",
            lambda: self._step_keep_batches(-1),
            small=True,
            width=2,
        ).pack(side="left", padx=(8, 2))
        self._auto_batch_entry = ttk.Entry(
            self._auto_batches_row,
            textvariable=self._get("keep_batches"),
            width=5,
            font=self._font(9),
            justify="center",
            style="Desktop.TEntry",
        )
        self._auto_batch_entry.pack(side="left")
        self._auto_batch_entry.bind("<FocusOut>", lambda _event: self._commit_keep_batches())
        self._auto_batch_entry.bind("<Return>", lambda _event: self._commit_keep_batches())
        self._auto_batch_entry.bind(
            "<FocusIn>",
            lambda _event: self._auto_batch_entry.selection_range(0, tk.END),
        )
        self._button(
            self._auto_batches_row,
            "+",
            lambda: self._step_keep_batches(1),
            small=True,
            width=2,
        ).pack(side="left", padx=(2, 6))
        self._label(
            self._auto_batches_row, text="个可清理批次", size=8, color=MUTED
        ).pack(side="left")
        self._label(
            self._auto_batches_row,
            text="必须为正整数，非法输入会恢复最近合法值。",
            size=8,
            color=FAINT,
        ).pack(side="left", padx=(8, 0))

        self._auto_days_row = tk.Frame(self._auto_mode_host, bg=PAPER)
        self._auto_days_row.grid(row=0, column=0, sticky="ew")
        self._auto_days_row.grid_remove()
        self._label(self._auto_days_row, text="保留最近", size=9, color=BODY).pack(
            side="left"
        )
        days_box = ttk.Combobox(
            self._auto_days_row,
            textvariable=self._get("keep_days"),
            values=("1", "3", "7", "15", "30"),
            state="readonly",
            width=5,
            font=self._font(9),
            style="Desktop.TCombobox",
        )
        days_box.pack(side="left", padx=(8, 5))
        days_box.bind("<<ComboboxSelected>>", self._on_days_changed)
        self._label(self._auto_days_row, text="天", size=8, color=MUTED).pack(
            side="left"
        )

        self._label(
            self._auto_settings,
            text="所有策略始终跳过工作簿、JSON、学习成果及正在使用/待识别/待学习批次。",
            size=8,
            color=FAINT,
            wrap=640,
        ).pack(anchor="w", pady=(6, 0))
        self._label(
            self._auto_settings,
            text="自动清理会等待停止监听及任务、学习队列空闲。",
            size=8,
            color=BRAND,
            wrap=640,
        ).pack(anchor="w", pady=(2, 0))

    def _radio(self, parent, text, variable, value, command):
        return tk.Radiobutton(
            parent,
            text=text,
            variable=variable,
            value=value,
            command=command,
            font=self._font(8),
            bg=PAPER,
            fg=BODY,
            activebackground=PAPER,
            activeforeground=INK,
            selectcolor=PAPER,
            bd=0,
            highlightthickness=0,
            anchor="w",
        )

    # ------------------------------------------------------------------
    # Settings page
    # ------------------------------------------------------------------

    def _build_settings_page(self, content):
        self._page_header(
            content,
            "偏好设置",
            "设置",
            "设置快捷键、浮窗、声音和自动清理偏好。",
        )

        shortcut_panel, shortcut_body = self._panel(
            content,
            "快捷键",
            "点击录入后按下按键或组合键，修改后同步到主页与浮窗。",
        )
        shortcut_panel.pack(fill="x", pady=(0, 10))
        self._label(
            shortcut_body,
            variable=self._get("keys"),
            size=9,
            color=BODY,
            wrap=640,
        ).pack(fill="x", anchor="w")
        configure_row = tk.Frame(shortcut_body, bg=PAPER)
        configure_row.pack(fill="x", pady=(8, 0))
        self._button(
            configure_row,
            "打开快捷键录入",
            lambda: self._act("configure_keys"),
            kind="primary",
        ).pack(side="left")
        self._label(
            configure_row,
            text="支持单键和组合键。",
            size=8,
            color=FAINT,
        ).pack(side="left", padx=(10, 0))

        sound_panel, sound_body = self._panel(
            content,
            "声音",
            "单卡拍摄、任务成功和失败分别使用不同提示音。",
        )
        sound_panel.pack(fill="x", pady=(0, 10))
        self._check(
            sound_body,
            "启用提示音",
            self._get("sound"),
            command=self._on_sound_toggle,
            size=9,
        ).pack(anchor="w")
        preview_row = tk.Frame(sound_body, bg=PAPER)
        preview_row.pack(fill="x", pady=(7, 0))
        for label, kind in (
            ("截图快门", "capture"),
            ("成功提示（四音）", "success"),
            ("失败提示（四音）", "failure"),
        ):
            preview_button = self._button(
                preview_row,
                label,
                lambda sound_kind=kind: self._act("preview_sound", sound_kind),
                small=True,
            )
            preview_button.pack(side="left", padx=(0, 7))
            self._sound_preview_buttons.append(preview_button)
        self._label(
            sound_body,
            text="快门声已削弱高频，适合连续拍摄。",
            size=8,
            color=FAINT,
            wrap=640,
        ).pack(anchor="w", pady=(6, 0))

        overlay_panel, overlay_body = self._panel(
            content,
            "浮窗与性能",
            "显示状态、性能数字和截屏排除均为独立开关；任务期间会自动临时锁定。",
        )
        overlay_panel.pack(fill="x", pady=(0, 10))
        overlay_checks = tk.Frame(overlay_body, bg=PAPER)
        overlay_checks.pack(fill="x")
        self._check(
            overlay_checks,
            "显示浮窗",
            self._get("overlay_visible"),
            command=self._save_preferences,
            size=9,
        ).pack(side="left", padx=(0, 18))
        self._check(
            overlay_checks,
            "显示 CPU / GPU / 内存",
            self._get("overlay_performance"),
            command=self._save_preferences,
            size=9,
        ).pack(side="left")

        opacity_header = tk.Frame(overlay_body, bg=PAPER)
        opacity_header.pack(fill="x", pady=(10, 0))
        self._label(
            opacity_header, text="背景不透明度", size=9, color=BODY
        ).pack(side="left")
        self._label(
            opacity_header,
            variable=self._opacity_display,
            size=8,
            color=BRAND,
            bold=True,
        ).pack(side="right")
        opacity_scale = ttk.Scale(
            overlay_body,
            from_=20,
            to=95,
            orient="horizontal",
            variable=self._opacity_proxy,
            command=self._on_opacity_scale,
        )
        opacity_scale.pack(fill="x", pady=(4, 0))
        opacity_scale.bind("<ButtonRelease-1>", lambda _event: self._save_preferences())
        opacity_scale.bind("<KeyRelease>", lambda _event: self._save_preferences())
        self._label(
            overlay_body,
            text="范围 20%–95%；只影响浮窗背景，文字保持不透明。",
            size=8,
            color=FAINT,
        ).pack(anchor="w", pady=(2, 0))

        self._hline(overlay_body, pady=(9, 8))
        self._check(
            overlay_body,
            "从截屏/录屏中排除（默认开启）",
            self._get("overlay_exclude"),
            command=self._save_preferences,
            size=9,
        ).pack(anchor="w")
        self._label(
            overlay_body,
            text="开启后，支持此设置的截屏和录屏会排除浮窗。",
            size=8,
            color=FAINT,
            wrap=640,
        ).pack(anchor="w", pady=(2, 0))
        self._label(
            overlay_body,
            text="任务期间浮窗会自动临时锁定，任务结束后恢复原来的锁定状态。",
            size=8,
            color=MUTED,
            wrap=640,
        ).pack(anchor="w", pady=(7, 0))

        self._label(
            content,
            text="声音、浮窗和自动清理设置会自动保存。",
            size=8,
            color=FAINT,
            wrap=640,
        ).pack(anchor="w", pady=(0, 8))

    # ------------------------------------------------------------------
    # Tutorial page
    # ------------------------------------------------------------------

    def _build_help_page(self, content):
        self._page_header(
            content,
            "离线文档",
            "教程 / 许可",
            "先看图解，再按文字步骤使用；快捷键以设置页当前值为准。",
        )

        canvas_panel, canvas_body = self._panel(
            content,
            "操作顺序与画面关系",
            "按图中顺序准备，然后在游戏中使用对应快捷键。",
        )
        canvas_panel.pack(fill="x", pady=(0, 10))
        self._tutorial_canvas = tk.Canvas(
            canvas_body,
            bg=WHITE,
            height=292,
            highlightthickness=0,
            bd=0,
        )
        self._tutorial_canvas.pack(fill="x")
        self._tutorial_canvas.bind("<Configure>", self._draw_tutorial)

        text_panel, text_body = self._panel(
            content,
            "使用说明",
            "图解说明操作顺序，文字说明补充输出、中止及异常处理。",
        )
        text_panel.pack(fill="x", pady=(0, 10))
        self._tutorial_section(
            text_body,
            "首次使用",
            "双击安装包选择安装位置，启动扫描器时确认 Windows UAC。"
            "选择已有工作簿，或让路径留空自动新建；确认工作表名与实时显示选项。"
            "点击“启动准备”，等模型与监听就绪后切回游戏，按任务快捷键触发。",
        )
        self._tutorial_section(
            text_body,
            "三种任务",
            "整趟扫描按所选星级读取；单卡识别只读取当前详情；横排拼图合成横排画面。"
            "任务类型不在主页预选，统一由游戏内快捷键触发。",
        )
        self._tutorial_section(
            text_body,
            "中止任务与停止监听",
            "中止任务使用游戏内快捷键，完成当前输入动作后保留监听与模型。"
            "停止监听会在当前输入动作完成后停止扫描，并释放本次加载的多路模型。",
        )
        self._tutorial_section(
            text_body,
            "工作簿与输出",
            "指定工作簿会连续追加到目标文件和工作表；留空时本次会话自动新建一个工作簿。"
            "截图、JSON、日志和学习缓存集中保存在安装目录中。",
        )
        self._tutorial_section(
            text_body,
            "空间、自动清理与错误导出",
            "受保护批次会保留。自动清理在停止监听、任务与学习队列空闲时执行，"
            "按批次数或保留天数设置。错误导出只针对失败/异常记录，"
            "自动关联该任务的截图和日志，导出为 ZIP。",
        )
        self._tutorial_section(
            text_body,
            "浮窗与声音",
            "浮窗默认从截屏/录屏中排除，可单独关闭；任务期间自动临时锁定。"
            "单卡拍摄用快门声，任务成功和失败使用各自的四音提示。",
        )

        current_panel, current_body = self._panel(
            content,
            "当前快捷键",
            "在设置页录入按键或组合键，修改后会同步更新。",
        )
        current_panel.pack(fill="x", pady=(0, 10))
        self._label(
            current_body,
            variable=self._get("keys"),
            size=9,
            color=BODY,
            wrap=640,
        ).pack(fill="x", anchor="w")

        about_panel, about_body = self._panel(
            content,
            "关于与许可",
            "查看第三方组件许可，也可导出源码与资源。",
        )
        about_panel.pack(fill="x")
        about_row = tk.Frame(about_body, bg=PAPER)
        about_row.pack(fill="x")
        self._button(
            about_row,
            "打开许可证与关于",
            lambda: self._act("about"),
            kind="quiet",
        ).pack(side="left")
        self._label(
            about_row,
            text="许可窗口包含第三方组件说明和授权原文。",
            size=8,
            color=FAINT,
        ).pack(side="left", padx=(10, 0))

    def _tutorial_section(self, parent, title, text):
        self._label(parent, text=title, size=9, color=INK, bold=True).pack(
            anchor="w", pady=(0, 2)
        )
        self._label(parent, text=text, size=9, color=BODY, wrap=640).pack(
            anchor="w", pady=(0, 8)
        )

    def _draw_tutorial(self, event=None):
        canvas = self._tutorial_canvas
        if canvas is None:
            return
        width = canvas.winfo_width()
        if width <= 1:
            width = 680
        width = max(560, width)
        canvas.delete("all")
        pad = 10
        gap = 18
        box_w = max(100, (width - pad * 2 - gap * 3) / 4)
        box_h = 58
        top = 34

        canvas.create_text(
            pad,
            6,
            anchor="nw",
            text="准备与任务触发顺序",
            font=self._font(9, True),
            fill=INK,
        )
        steps = (
            ("01", "设置输出", "工作簿 / 路数 / 星级"),
            ("02", "启动准备", "检查环境并加载模型"),
            ("03", "等待快捷键", "监听就绪后切回游戏"),
            ("04", "游戏内按键", "自动执行当前任务"),
        )
        boxes = []
        for index, (number, title, subtitle) in enumerate(steps):
            x = pad + index * (box_w + gap)
            fill = BRAND_SOFT if index == 3 else SOFT
            outline = "#b9d6c7" if index == 3 else BORDER
            canvas.create_rectangle(
                x,
                top,
                x + box_w,
                top + box_h,
                fill=fill,
                outline=outline,
            )
            canvas.create_text(
                x + 9,
                top + 9,
                anchor="nw",
                text=number,
                font=self._font(7, True),
                fill=BRAND,
            )
            canvas.create_text(
                x + box_w / 2,
                top + 23,
                text=title,
                font=self._font(9, True),
                fill=INK,
                width=box_w - 16,
                anchor="n",
            )
            canvas.create_text(
                x + box_w / 2,
                top + 41,
                text=subtitle,
                font=self._font(7),
                fill=MUTED,
                width=box_w - 12,
                anchor="n",
                justify="center",
            )
            boxes.append(x)
            if index < 3:
                y = top + box_h / 2
                canvas.create_line(
                    x + box_w + 3,
                    y,
                    x + box_w + gap - 3,
                    y,
                    arrow=tk.LAST,
                    fill=BRAND,
                    width=2,
                )

        row2_title_y = 116
        canvas.create_text(
            pad,
            row2_title_y,
            anchor="nw",
            text="画面与任务的对应",
            font=self._font(9, True),
            fill=INK,
        )
        panel_top = 139
        panel_h = 118
        panel_gap = 12
        panel_w = (width - pad * 2 - panel_gap) / 2
        left_x = pad
        right_x = pad + panel_w + panel_gap

        canvas.create_rectangle(
            left_x,
            panel_top,
            left_x + panel_w,
            panel_top + panel_h,
            fill="#263b45",
            outline="#263b45",
        )
        canvas.create_text(
            left_x + 14,
            panel_top + 14,
            anchor="nw",
            text="获得横排完整可见",
            font=self._font(9, True),
            fill="#f3faf6",
            width=panel_w - 28,
        )
        canvas.create_text(
            left_x + 14,
            panel_top + 38,
            anchor="nw",
            text="对应整趟扫描 / 横排拼图",
            font=self._font(8),
            fill="#f0c77d",
            width=panel_w - 28,
        )
        for index, color in enumerate(("#7391ad", "#7391ad", "#ba854d", "#9a7cc4", "#7391ad")):
            x = left_x + 14 + index * 32
            canvas.create_rectangle(x, panel_top + 65, x + 25, panel_top + 94, fill=color, outline="")
            canvas.create_oval(x + 7, panel_top + 70, x + 18, panel_top + 81, fill="#e5ddbd", outline="")
            canvas.create_rectangle(x, panel_top + 88, x + 25, panel_top + 97, fill="#ece7df", outline="")
            canvas.create_text(x + 12, panel_top + 92, text="1", font=self._font(6), fill=INK)

        canvas.create_rectangle(
            right_x,
            panel_top,
            right_x + panel_w,
            panel_top + panel_h,
            fill="#263b45",
            outline="#263b45",
        )
        canvas.create_text(
            right_x + 14,
            panel_top + 14,
            anchor="nw",
            text="已打开圣遗物详情",
            font=self._font(9, True),
            fill="#f3faf6",
            width=panel_w - 28,
        )
        canvas.create_text(
            right_x + 14,
            panel_top + 38,
            anchor="nw",
            text="对应单卡识别",
            font=self._font(8),
            fill="#f0c77d",
            width=panel_w - 28,
        )
        card_x = right_x + 14
        canvas.create_rectangle(card_x, panel_top + 63, card_x + 180, panel_top + 106, fill="#eee9e0", outline="")
        canvas.create_rectangle(card_x, panel_top + 63, card_x + 180, panel_top + 77, fill="#ba854d", outline="")
        canvas.create_text(card_x + 8, panel_top + 70, anchor="w", text="圣遗物 · 主词条", font=self._font(6), fill="white")
        canvas.create_rectangle(card_x + 7, panel_top + 82, card_x + 32, panel_top + 94, fill="#3a3a3a", outline="")
        canvas.create_text(card_x + 20, panel_top + 88, text="+0", font=self._font(6), fill="white")
        canvas.create_text(card_x + 40, panel_top + 88, anchor="w", text="· 副词条 + 数值", font=self._font(6), fill=BODY)

        canvas.create_text(
            width / 2,
            278,
            text="快捷键在设置页录入；中止当前任务后仍可继续接收下一次指令。",
            font=self._font(7),
            fill=FAINT,
        )

    # ------------------------------------------------------------------
    # Runtime and storage public methods
    # ------------------------------------------------------------------

    def set_runtime(self, waiting, busy, actual_workers):
        current = (waiting, busy, actual_workers)
        if getattr(self, '_runtime_signature', None) == current:
            return
        self._runtime_signature = current
        self._waiting = bool(waiting)
        self._busy = bool(busy)
        try:
            self._actual_workers_var.set("实际并行：%d" % int(actual_workers))
        except (TypeError, ValueError):
            self._actual_workers_var.set("实际并行：—")
        self._apply_runtime_state()

    def _apply_runtime_state(self):
        if self._prepare_btn is not None:
            state = tk.DISABLED if (self._waiting or self._busy) else tk.NORMAL
            self._prepare_btn.configure(state=state)
        if self._stop_btn is not None:
            state = tk.NORMAL if (self._waiting or self._busy) else tk.DISABLED
            self._stop_btn.configure(state=state)

        worker_state = "disabled" if (self._waiting or self._busy) else "normal"
        for button in self._workers_buttons:
            button.configure(state=worker_state)

        workbook_state = "disabled" if (self._waiting or self._busy) else "normal"
        for control in self._workbook_controls:
            try:
                control.configure(state=workbook_state)
            except tk.TclError:
                pass

        busy_state = tk.DISABLED if self._busy else tk.NORMAL
        for control in self._busy_controls:
            try:
                control.configure(state=busy_state)
            except tk.TclError:
                pass

    def set_storage(self, batches, issues, summary):
        self._batches = list(batches or [])
        self._issues = list(issues or [])
        try:
            self._summary_var.set(str(summary or "尚无空间数据。"))
        except tk.TclError:
            pass
        self._rebuild_batch_tree()
        self._rebuild_issue_tree()

    def _batch_is_protected(self, batch):
        protected = batch.get("protected", False)
        reclaimable = batch.get("reclaimable", True)
        if isinstance(protected, str):
            if protected.strip():
                return True, protected.strip()
        elif bool(protected):
            return True, "受保护"
        if not bool(reclaimable):
            return True, "不可清理"
        return False, ""

    def _format_bytes(self, value):
        try:
            number = float(value)
        except (TypeError, ValueError):
            return "—"
        units = ("B", "KB", "MB", "GB", "TB")
        index = 0
        while number >= 1024 and index < len(units) - 1:
            number /= 1024
            index += 1
        if index == 0:
            return "%d %s" % (int(number), units[index])
        return "%.1f %s" % (number, units[index])

    def _rebuild_batch_tree(self):
        if self._batch_tree is None:
            return
        previous = set(self._selected_batch_names)
        self._batch_rows.clear()
        self._syncing_batch_selection = True
        try:
            children = self._batch_tree.get_children()
            if children:
                self._batch_tree.delete(*children)
            select_iids = []
            for index, batch in enumerate(self._batches):
                name = str(batch.get("name", "未命名批次"))
                size = batch.get("bytes", 0)
                protected, reason = self._batch_is_protected(batch)
                iid = "batch-%d" % index
                self._batch_rows[iid] = {
                    "name": name,
                    "size": self._format_bytes(size),
                    "bytes": size,
                    "protected": protected,
                    "reason": reason,
                }
                if protected:
                    status = "受保护" + (("：" + reason) if reason else "")
                    tags = ("protected",)
                else:
                    status = "可清理"
                    tags = ()
                self._batch_tree.insert(
                    "",
                    "end",
                    iid=iid,
                    values=(name, self._format_bytes(size), status),
                    tags=tags,
                )
                if name in previous and not protected:
                    select_iids.append(iid)
            if select_iids:
                self._batch_tree.selection_set(select_iids)
        finally:
            self._syncing_batch_selection = False
        self._batch_hint_var.set(
            "受保护批次不可清理；仅可清理批次可被选中。"
        )
        self._update_batch_selection_state()

    def _batch_selection(self):
        if self._batch_tree is None:
            return []
        return [
            self._batch_rows[iid]
            for iid in self._batch_tree.selection()
            if iid in self._batch_rows and not self._batch_rows[iid]["protected"]
        ]

    def _update_batch_selection_state(self):
        selected = self._batch_selection()
        self._selected_batch_names = {item["name"] for item in selected}
        if self._cleanup_btn is not None:
            self._cleanup_btn.configure(
                state=(tk.NORMAL if selected else tk.DISABLED)
            )
        if selected:
            total = sum(
                self._safe_int(item.get("bytes"), 0) for item in selected
            )
            self._batch_selection_var.set(
                "已选 %d 个批次 · %s" % (len(selected), self._format_bytes(total))
            )
        else:
            self._batch_selection_var.set("未选择可清理批次")

    def _on_batch_select(self, _event=None):
        if self._syncing_batch_selection or self._batch_tree is None:
            return
        blocked = []
        for iid in self._batch_tree.selection():
            info = self._batch_rows.get(iid)
            if info is not None and info["protected"]:
                blocked.append(iid)
        if blocked:
            self._syncing_batch_selection = True
            try:
                for iid in blocked:
                    self._batch_tree.selection_remove(iid)
            finally:
                self._syncing_batch_selection = False
            reason = self._batch_rows.get(blocked[-1], {}).get("reason", "")
            self._batch_hint_var.set(
                "受保护批次不可清理" + (("：" + reason) if reason else "。")
            )
        else:
            self._batch_hint_var.set(
                "受保护批次不可清理；仅可清理批次可被选中。"
            )
        self._update_batch_selection_state()

    def _cleanup_selected(self):
        selected = self._batch_selection()
        if not selected:
            return
        names = [str(item["name"]) for item in selected]
        self._act("cleanup_batches", names)

    def _rebuild_issue_tree(self):
        if self._issue_tree is None:
            return
        previous = self._selected_issue_id
        self._issue_rows.clear()
        self._syncing_issue_selection = True
        try:
            children = self._issue_tree.get_children()
            if children:
                self._issue_tree.delete(*children)
            for index, issue in enumerate(self._issues):
                issue_id = str(issue.get("id", ""))
                task = str(issue.get("task", ""))
                occurred_at = str(issue.get("occurred_at", ""))
                message = str(issue.get("message", ""))
                iid = "issue-%d" % index
                self._issue_rows[iid] = {
                    "id": issue_id,
                    "task": task,
                    "occurred_at": occurred_at,
                    "message": message,
                }
                self._issue_tree.insert(
                    "",
                    "end",
                    iid=iid,
                    values=(occurred_at, task, message.replace("\n", " ")),
                )
            if not self._issues:
                self._selected_issue_id = ""
                self._issue_detail_var.set("暂无错误记录。")
            else:
                target_iid = None
                for iid, info in self._issue_rows.items():
                    if info["id"] == previous:
                        target_iid = iid
                        break
                if target_iid is None:
                    target_iid = "issue-0"
                self._issue_tree.selection_set(target_iid)
                self._selected_issue_id = self._issue_rows[target_iid]["id"]
                self._update_issue_detail(target_iid)
        finally:
            self._syncing_issue_selection = False
        self._update_export_button()

    def _on_issue_select(self, _event=None):
        if self._syncing_issue_selection or self._issue_tree is None:
            return
        selection = self._issue_tree.selection()
        if selection:
            self._update_issue_detail(selection[0])
        else:
            self._selected_issue_id = ""
            self._issue_detail_var.set(
                "请选择一条错误记录。" if self._issues else "暂无错误记录。"
            )
        self._update_export_button()

    def _update_issue_detail(self, iid):
        info = self._issue_rows.get(iid)
        if info is None:
            self._selected_issue_id = ""
            self._issue_detail_var.set(
                "请选择一条错误记录。" if self._issues else "暂无错误记录。"
            )
            return
        self._selected_issue_id = info["id"]
        detail = "%s · %s" % (info["occurred_at"], info["task"])
        if info["message"]:
            detail += "\n" + info["message"]
        self._issue_detail_var.set(detail)

    def _update_export_button(self):
        if self._export_btn is not None:
            self._export_btn.configure(
                state=(tk.NORMAL if self._selected_issue_id else tk.DISABLED)
            )

    def _export_selected(self):
        if not self._selected_issue_id:
            return
        self._act("export_error", str(self._selected_issue_id))

    # ------------------------------------------------------------------
    # Preference handlers
    # ------------------------------------------------------------------

    def _step_keep_batches(self, delta):
        current = self._parse_positive(
            self._get("keep_batches").get(), self._last_keep_batches
        )
        value = max(1, current + delta)
        self._last_keep_batches = value
        self._get("keep_batches").set(str(value))
        self._sync_auto_controls()
        self._save_preferences()

    def _commit_keep_batches(self):
        raw = str(self._get("keep_batches").get()).strip()
        value = self._parse_positive(raw, 0)
        if value <= 0:
            value = self._last_keep_batches
        self._last_keep_batches = value
        self._get("keep_batches").set(str(value))
        self._sync_auto_controls()
        self._save_preferences()

    def _on_auto_toggle(self):
        self._sync_auto_controls()
        self._save_preferences()

    def _on_auto_mode(self):
        self._sync_auto_controls()
        self._save_preferences()

    def _on_days_changed(self, _event=None):
        self._sync_auto_controls()
        self._save_preferences()

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def close(self):
        if self._closed:
            return
        self._closed = True
        for variable_name, trace_id in self._traces:
            try:
                self._get(variable_name).trace_remove("write", trace_id)
            except (KeyError, tk.TclError):
                pass
        self._traces.clear()
