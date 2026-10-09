"""QuickDrop / 快传 —— Tkinter 主窗口

主窗口：二维码 + 访问地址 + 共享列表(拖拽区) + 接收目录 + 状态栏。
拖拽：tkinterdnd2，把桌面文件拖进窗口即共享，不需要复制进 shared/。
关闭：关闭窗口 = on_close() 停服务 + 退出程序（不做托盘、不做开机自启）。

视觉规范（与手机端 static/style.css 同源，保证两端观感一致）：
- 品牌蓝 #4a90d9 ｜ 页面底 #f5f7fa ｜ 卡片白 #ffffff ｜ 主文字 #1f2733 ｜ 次要 #7a8699 ｜ 危险 #d9534f
- 层级：品牌标题栏 → 连接信息卡（二维码 + 地址）→ 共享文件卡（主操作区）→ 底部状态栏
- 边框：Tkinter 无原生圆角，用 1px 描边卡片（highlightthickness）模拟"卡片浮起"层次

⚠️ 需要真实桌面（有显示）才能运行；无头环境会抛 TclError，由 server.main() 回落处理。
"""

from __future__ import annotations

import os
import tkinter as tk
from tkinter import ttk

try:  # tkinterdnd2 可选：缺失时降级为普通窗口（仍可用“打开目录”手动加文件）
    from tkinterdnd2 import DND_FILES, TkinterDnD

    _HAS_DND = True
except Exception:  # pragma: no cover
    _HAS_DND = False

# ---------------------------- 配色（与 style.css 同源） ----------------------------
BRAND = "#4a90d9"        # 品牌蓝：标题栏 / 主按钮
BRAND_DARK = "#3a7bc0"   # 主按钮按下
BRAND_SOFT = "#eef5fc"   # 品牌浅底：输入框 / 提示条
BG = "#f5f7fa"           # 页面底
CARD = "#ffffff"         # 卡片
BORDER = "#e3e8ef"       # 卡片描边
TEXT = "#1f2733"         # 主文字
MUTED = "#7a8699"        # 次要文字
GHOST = "#eef2f7"        # 次要按钮底
GHOST_HOVER = "#e2e9f2"
OK = "#2e9e5b"           # 运行中指示
DANGER = "#d9534f"


def _pick_font(root):
    """挑一个存在的中文字体族，避免在缺字体机器上排版塌掉。"""
    try:
        import tkinter.font as tkfont

        fams = set(tkfont.families(root))
        for f in ("Microsoft YaHei UI", "Microsoft YaHei", "PingFang SC", "Noto Sans CJK SC", "Segoe UI"):
            if f in fams:
                return f
        return tkfont.nametofont("TkDefaultFont").actual("family")
    except Exception:  # pragma: no cover
        return "Arial"


def _make_root():
    return TkinterDnD.Tk() if _HAS_DND else tk.Tk()


def build_clip_card(parent, font, clipboard_state):
    """构建「文本快传」卡片，返回 (card, refresh)。

    refresh() 检查 clipboard_state['version'] 是否变化，变了就刷新界面，返回是否刷新过。
    **刻意把「渲染」与「调度」分开**：调用方决定多久调一次 refresh（主窗口用
    root.after），测试则可直接调用而不需要 Tk mainloop。

    clipboard_state 由服务端在 waitress 线程里写入；这里只在 Tk 主线程读，
    避免跨线程操作 UI。
    """
    card = tk.Frame(parent, bg=CARD, highlightbackground=BORDER, highlightthickness=1)

    inner = tk.Frame(card, bg=CARD)
    inner.pack(fill="x", padx=16, pady=12)

    head = tk.Frame(inner, bg=CARD)
    head.pack(fill="x")

    tk.Label(head, text="文本快传", bg=CARD, fg=TEXT, font=font(11, "bold")).pack(side="left")

    hint_var = tk.StringVar(value="等待手机发送…")
    tk.Label(head, textvariable=hint_var, bg=CARD, fg=MUTED, font=font(9)).pack(side="right")

    body = tk.Frame(inner, bg=CARD)
    body.pack(fill="x", pady=(8, 0))

    text_box = tk.Text(
        body, height=3, wrap="word", bg="#fbfcfe", fg=MUTED, bd=0,
        highlightthickness=1, highlightbackground=BORDER,
        font=font(10), padx=8, pady=6,
    )
    text_box.pack(side="left", fill="both", expand=True)

    def render(text, hint):
        text_box.configure(state="normal")
        text_box.delete("1.0", tk.END)
        if text:
            text_box.insert("1.0", text)
            text_box.configure(fg=TEXT)
        else:
            text_box.insert("1.0", "（暂无内容）")
            text_box.configure(fg=MUTED)
        text_box.configure(state="disabled")
        hint_var.set(hint)

    def copy():
        """把当前收到的文本再写一次系统剪贴板（剪贴板被占用时的补救手段）。"""
        try:
            text = str((clipboard_state or {}).get("text") or "")
        except Exception:
            text = ""
        if not text:
            hint_var.set("暂无可复制的内容")
            return
        try:
            import utils as U

            if U.set_clipboard(text):
                hint_var.set("已复制到剪贴板，可直接 Ctrl+V ✅")
            else:
                hint_var.set("复制失败：剪贴板被其他程序占用，请稍后重试")
        except Exception as e:
            hint_var.set(f"复制失败：{e}")

    btns = tk.Frame(body, bg=CARD)
    btns.pack(side="right", fill="y", padx=(10, 0))
    copy_btn = ttk.Button(btns, text="复制到剪贴板", style="Brand.TButton", command=copy)
    copy_btn.pack()

    seen = {"version": -1}

    def refresh():
        try:
            version = int((clipboard_state or {}).get("version", 0))
        except Exception:
            version = 0
        if version == seen["version"]:
            return False
        seen["version"] = version
        try:
            text = str((clipboard_state or {}).get("text") or "")
            stamp = str((clipboard_state or {}).get("updated_at") or "")
        except Exception:
            text, stamp = "", ""
        if text:
            render(text, f"已收到手机文本（{stamp}）")
        else:
            render("", "等待手机发送…")
        return True

    return card, refresh


def build_window(url, qr_path, shared, received_dir, cfg, on_close=None, clipboard_state=None):
    """构建并运行主窗口（阻塞在 mainloop）。on_close 为关闭时回调（停服务）。

    clipboard_state：服务端共享的剪贴板状态字典 {"text","version","updated_at"}。
    主窗口用 root.after 轮询 version 变化来刷新显示——服务端在 waitress 线程里
    只写字典，Tkinter 只在主线程读写，避免跨线程操作 UI。
    """
    root = _make_root()
    root.title("QuickDrop 快传")
    root.geometry("760x700")
    root.minsize(700, 620)
    root.configure(bg=BG)

    F = _pick_font(root)

    # ---------- ttk 控件样式（clam 主题才吃这些配色） ----------
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except Exception:  # pragma: no cover
        pass

    def font(size, weight="normal"):
        return (F, size, weight)

    style.configure("Brand.TButton", background=BRAND, foreground="#ffffff",
                    borderwidth=0, focusthickness=0, padding=(16, 8), font=font(10, "bold"))
    style.map("Brand.TButton",
              background=[("pressed", BRAND_DARK), ("active", BRAND_DARK)],
              foreground=[("disabled", "#c9d3e0")])

    style.configure("Ghost.TButton", background=GHOST, foreground=BRAND,
                    borderwidth=0, focusthickness=0, padding=(12, 7), font=font(10))
    style.map("Ghost.TButton", background=[("pressed", GHOST_HOVER), ("active", GHOST_HOVER)])

    style.configure("Url.TEntry", fieldbackground="#ffffff", foreground=TEXT,
                    bordercolor=BORDER, lightcolor=BORDER, darkcolor=BORDER,
                    insertcolor=TEXT, padding=8, font=font(10))

    style.configure("Card.Vertical.TScrollbar", background="#dfe5ee", troughcolor=CARD,
                    bordercolor=CARD, arrowcolor=MUTED, lightcolor="#dfe5ee", darkcolor="#dfe5ee")

    status_var = tk.StringVar(value="运行中")

    # ---------- ① 品牌标题栏 ----------
    header = tk.Frame(root, bg=BRAND, height=68)
    header.pack(fill="x", side="top")
    header.pack_propagate(False)

    left = tk.Frame(header, bg=BRAND)
    left.pack(side="left", padx=18, pady=12)
    tk.Label(left, text="QuickDrop 快传", bg=BRAND, fg="#ffffff",
             font=font(15, "bold")).pack(anchor="w")
    tk.Label(left, text="同一 WiFi 直传 · 不经过任何外部服务器", bg=BRAND, fg="#dcebfa",
             font=font(9)).pack(anchor="w")

    pill = tk.Frame(header, bg=BRAND)
    pill.pack(side="right", padx=18)
    tk.Label(pill, text="● 服务运行中", bg=BRAND, fg="#eafaf0", font=font(10, "bold")).pack()

    # ---------- ② 底部状态栏（先占位，让中间区域正确吃掉剩余高度） ----------
    statusbar = tk.Frame(root, bg="#eef1f6", height=30)
    statusbar.pack(fill="x", side="bottom")
    statusbar.pack_propagate(False)
    tk.Frame(statusbar, bg=BORDER, height=1).pack(fill="x", side="top")
    tk.Label(statusbar, textvariable=status_var, bg="#eef1f6", fg=MUTED,
             font=font(9), anchor="w").pack(fill="x", padx=14, pady=5)

    # ---------- ③ 主体 ----------
    body = tk.Frame(root, bg=BG)
    body.pack(fill="both", expand=True, padx=14, pady=12)

    toprow = tk.Frame(body, bg=BG)
    toprow.pack(fill="x")

    # --- 左：二维码卡片 ---
    qr_card = tk.Frame(toprow, bg=CARD, highlightbackground=BORDER, highlightthickness=1)
    qr_card.pack(side="left", fill="y")

    qr_inner = tk.Frame(qr_card, bg=CARD)
    qr_inner.pack(padx=14, pady=14)

    qr_label = tk.Label(qr_inner, bg=CARD, bd=0)
    qr_label.pack()
    try:
        from PIL import Image, ImageTk

        img = Image.open(qr_path).resize((196, 196))
        qr_img = ImageTk.PhotoImage(img)
        qr_label.configure(image=qr_img)
        qr_label.image = qr_img  # 防 GC
    except Exception as e:  # 无二维码文件时降级
        qr_label.configure(text=f"[二维码]\n{e}", fg=DANGER, font=font(9))

    tk.Label(qr_inner, text="手机扫这张码", bg=CARD, fg=MUTED,
             font=font(9)).pack(pady=(8, 0))

    # --- 右：连接信息卡片 ---
    info_card = tk.Frame(toprow, bg=CARD, highlightbackground=BORDER, highlightthickness=1)
    info_card.pack(side="left", fill="both", expand=True, padx=(12, 0))

    info = tk.Frame(info_card, bg=CARD)
    info.pack(fill="both", expand=True, padx=16, pady=14)

    tk.Label(info, text="手机访问地址", bg=CARD, fg=MUTED,
             font=font(9, "bold")).pack(anchor="w")

    url_var = tk.StringVar(value=url)
    url_entry = ttk.Entry(info, textvariable=url_var, style="Url.TEntry")
    url_entry.pack(fill="x", pady=(4, 8))

    def copy_url():
        root.clipboard_clear()
        root.clipboard_append(url)
        status_var.set("已复制访问地址到剪贴板")

    actions = tk.Frame(info, bg=CARD)
    actions.pack(fill="x")
    ttk.Button(actions, text="复制地址", style="Brand.TButton", command=copy_url).pack(side="left")

    hostname = cfg.get("mdns_hostname", "")
    tk.Label(info, text=f"固定主机名：{hostname}（局域网支持 mDNS 时可用）", bg=CARD, fg=MUTED,
             font=font(9)).pack(anchor="w", pady=(10, 0))

    tip = tk.Frame(info, bg=BRAND_SOFT)
    tip.pack(fill="x", pady=(10, 0))
    tk.Label(
        tip,
        text="提示：手机需连同一个 WiFi；请勿在手机上输入 127.0.0.1（那指手机自己）。",
        bg=BRAND_SOFT, fg="#3f6f9e", font=font(9), justify="left", wraplength=380,
    ).pack(anchor="w", padx=10, pady=8)

    # --- 中：文本快传卡片（显示手机发来的文字） ---
    clip_card, refresh_clip = build_clip_card(body, font, clipboard_state)
    clip_card.pack(fill="x", pady=(12, 0))

    def _poll_clip():
        """轮询服务端 version：只读字典，不跨线程碰 UI。"""
        try:
            refresh_clip()
        except Exception:
            pass
        root.after(700, _poll_clip)

    # --- 下：共享文件卡片（拖拽主操作区） ---
    files_card = tk.Frame(body, bg=CARD, highlightbackground=BORDER, highlightthickness=1)
    files_card.pack(fill="both", expand=True, pady=(12, 0))

    files = tk.Frame(files_card, bg=CARD)
    files.pack(fill="both", expand=True, padx=16, pady=14)

    files_head = tk.Frame(files, bg=CARD)
    files_head.pack(fill="x")

    files_title_var = tk.StringVar(value="共享文件")
    tk.Label(files_head, textvariable=files_title_var, bg=CARD, fg=TEXT,
             font=font(11, "bold")).pack(side="left")
    tk.Label(files_head, text="把文件 / 文件夹拖进下方列表即可共享", bg=CARD, fg=MUTED,
             font=font(9)).pack(side="right")

    list_wrap = tk.Frame(files, bg=CARD, highlightbackground=BORDER, highlightthickness=1)
    list_wrap.pack(fill="both", expand=True, pady=(8, 10))

    listbox = tk.Listbox(
        list_wrap,
        selectmode="extended",
        bg="#fbfcfe", fg=TEXT, bd=0, highlightthickness=0,
        selectbackground=BRAND, selectforeground="#ffffff",
        activestyle="none", font=font(10),
    )
    listbox.pack(fill="both", expand=True, side="left", padx=(8, 0), pady=6)

    sb = ttk.Scrollbar(list_wrap, orient="vertical", command=listbox.yview,
                       style="Card.Vertical.TScrollbar")
    sb.pack(side="right", fill="y")
    listbox.configure(yscrollcommand=sb.set)

    def refresh_list():
        listbox.delete(0, tk.END)
        items = shared.list()
        for item in items:
            size_mb = item["size"] / 1024 / 1024
            listbox.insert(tk.END, f'{item["name"]}   {size_mb:.2f} MB   [{item["id"]}]')
        files_title_var.set(f"共享文件（{len(items)}）")
        update_status()

    def add_paths(paths):
        added = 0
        for p in paths:
            if os.path.isfile(p):
                if shared.add(p):
                    added += 1
            elif os.path.isdir(p):
                for dirpath, _, files_ in os.walk(p):
                    for f in files_:
                        if shared.add(os.path.join(dirpath, f)):
                            added += 1
        refresh_list()
        if added:
            status_var.set(f"已添加 {added} 个共享文件")

    def on_drop(event):
        paths = root.tk.splitlist(event.data)
        add_paths(paths)

    if _HAS_DND:
        listbox.drop_target_register(DND_FILES)
        listbox.dnd_bind("<<Drop>>", on_drop)

    def remove_selected():
        for idx in reversed(listbox.curselection()):
            text = listbox.get(idx)
            fid = text[text.rfind("[") + 1 : text.rfind("]")]
            shared.remove(fid)
        refresh_list()

    def open_received():
        try:
            if os.name == "nt":
                os.startfile(received_dir)  # type: ignore[attr-defined]
            else:
                import subprocess

                subprocess.Popen(["open" if os.uname().sysname == "Darwin" else "xdg-open", received_dir])
        except Exception as e:
            status_var.set(f"打开目录失败：{e}")

    btn_row = tk.Frame(files, bg=CARD)
    btn_row.pack(fill="x")
    ttk.Button(btn_row, text="移除所选", style="Ghost.TButton",
               command=remove_selected).pack(side="left")
    ttk.Button(btn_row, text="刷新", style="Ghost.TButton",
               command=refresh_list).pack(side="left", padx=6)
    ttk.Button(btn_row, text="打开接收目录", style="Brand.TButton",
               command=open_received).pack(side="right")
    tk.Label(btn_row, text=f"接收目录：{os.path.basename(received_dir)}/", bg=CARD, fg=MUTED,
             font=font(9)).pack(side="right", padx=12)

    # ---------- 状态栏刷新 ----------
    def update_status():
        try:
            n = len(os.listdir(received_dir))
        except Exception:
            n = 0
        status_var.set(f"运行中 ｜ 共享 {len(shared.list())} 个 ｜ 已接收 {n} 个文件")

    # ---------- 关闭：停服务 + 退出 ----------
    def on_quit():
        try:
            if on_close:
                on_close()
        finally:
            root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_quit)

    refresh_list()
    refresh_clip()   # 首屏渲染一次
    _poll_clip()     # 启动轮询（自身用 root.after 续期）
    root.mainloop()
    return root
