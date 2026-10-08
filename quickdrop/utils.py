"""QuickDrop 后端工具函数。

- get_lan_ip()           取本机局域网 IP
- load_config/save_config 读写 config.json
- load_or_create_token()  持久化 token
- generate_qr()          生成二维码 PNG
- safe_filename()        清洗上传文件名（**保留中文**，见 docs/security-design.md）
- unique_path()          重名处理 (1)(2)
- notify_upload()        上传完成系统通知
- set_clipboard()        写系统剪贴板（文本快传）
- setup_logging()        开发期日志：控制台 + 文件
- make_std_streams_safe() 控制台编码兜底（GBK 下的 emoji 不再崩程序）
"""

from __future__ import annotations

import json
import logging
import logging.handlers
import os
import secrets
import shutil
import socket
import string
import subprocess
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
LOG_DIR = os.path.join(BASE_DIR, "logs")
LOG_PATH = os.path.join(LOG_DIR, "quickdrop.log")

# ---- 打包（PyInstaller）适配：区分「可写数据目录」与「只读资源目录」 ----
# onefile 模式下 static/ 等被解到临时目录 sys._MEIPASS（退出即删），
# 而 config.json / received / shared / logs / qrcode.png 必须落在 **exe 所在目录**，
# 否则用户收到的文件会随临时目录一起消失。
IS_FROZEN = getattr(sys, "frozen", False)
if IS_FROZEN:
    BASE_DIR = os.path.dirname(os.path.abspath(sys.executable))  # 可写数据：exe 旁
    RESOURCE_DIR = getattr(sys, "_MEIPASS", BASE_DIR)            # 只读资源：解包目录
    CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
    LOG_DIR = os.path.join(BASE_DIR, "logs")
    LOG_PATH = os.path.join(LOG_DIR, "quickdrop.log")
else:
    RESOURCE_DIR = BASE_DIR

STATIC_DIR = os.path.join(RESOURCE_DIR, "static")

DEFAULT_CONFIG = {
    "host": "0.0.0.0",
    "port": 8765,
    "token": "",
    "mdns_hostname": "quickdrop.local",
    "enable_mdns": True,
    "shared_dir": "shared",
    "received_dir": "received",
    "use_shared_dir": False,
    "shared_files": [],
    "max_upload_size_mb": 4096,
    "enable_https": False,
    "cert_file": "cert.pem",
    "key_file": "key.pem",
    "notify_on_upload": True,
    "open_folder_on_notify_click": True,
    "qr_display_mode": "tkinter",
}


def make_std_streams_safe() -> None:
    """让 stdout/stderr 遇到无法编码的字符时降级为 '?'，而不是抛异常。

    打包成窗口化 exe 后，控制台编码常为 GBK(cp936)，`print("⚠️ …")` 会抛
    UnicodeEncodeError 并**直接终止程序**（真机事故）。把 errors 设为 replace 后
    整个程序对 emoji/方块字免疫。
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            if stream is not None and hasattr(stream, "reconfigure"):
                stream.reconfigure(errors="replace")
        except Exception:
            pass


def setup_logging(level: int = logging.DEBUG) -> logging.Logger:
    """初始化开发期日志。

    - 控制台：INFO 及以上，人可读。
    - 文件：DEBUG 及以上，写入 `quickdrop/logs/quickdrop.log`，滚动 2MB×3。
    - 幂等：重复调用不会重复加 handler（避免日志重复刷屏）。
    返回名为 "quickdrop" 的 logger。
    """
    logger = logging.getLogger("quickdrop")
    logger.setLevel(level)
    logger.propagate = False
    if getattr(logger, "_qd_configured", False):
        return logger

    os.makedirs(LOG_DIR, exist_ok=True)
    fmt = logging.Formatter(
        "%(asctime)s %(levelname)-7s [%(threadName)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    # 注意：PyInstaller --windowed(console=False) 时 sys.stdout/stderr 为 None，
    # 此时不能挂 StreamHandler（emit 会报 logging error），只保留文件日志。
    if sys.stdout is not None:
        console = logging.StreamHandler(sys.stdout)
        console.setLevel(logging.INFO)
        console.setFormatter(fmt)
        logger.addHandler(console)

    fileh = logging.handlers.RotatingFileHandler(
        LOG_PATH, maxBytes=2 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    fileh.setLevel(logging.DEBUG)
    fileh.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)-7s [%(threadName)s] %(message)s")
    )

    logger.addHandler(fileh)
    logger._qd_configured = True  # type: ignore[attr-defined]
    logger.debug("日志初始化完成：%s", LOG_PATH)
    return logger


def load_config(path: str = CONFIG_PATH) -> dict:
    """读取 config.json；缺失字段用默认值补齐。文件不存在则写默认。"""
    if not os.path.isfile(path):
        save_config(DEFAULT_CONFIG, path)
        return dict(DEFAULT_CONFIG)
    with open(path, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    merged = dict(DEFAULT_CONFIG)
    merged.update(cfg)
    return merged


def save_config(cfg: dict, path: str = CONFIG_PATH) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def get_lan_ip() -> str:
    """取本机对外的局域网 IP；失败回落 127.0.0.1。"""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip


def load_or_create_token(cfg: dict, path: str = CONFIG_PATH) -> str:
    """token 首次生成（≥12 位）写回配置文件，之后复用。"""
    if cfg.get("token"):
        return cfg["token"]
    alphabet = string.ascii_letters + string.digits
    token = "".join(secrets.choice(alphabet) for _ in range(12))
    cfg["token"] = token
    save_config(cfg, path)
    return token


def generate_qr(url: str, save_path: str = "qrcode.png") -> str:
    """生成二维码 PNG，返回路径。惰性导入 qrcode。"""
    import qrcode  # 惰性导入，避免无依赖时 import 本模块失败

    img = qrcode.make(url)
    img.save(save_path)
    return save_path


def print_ascii_qr(url: str) -> bool:
    """在终端打印 ASCII 二维码，供无 GUI/无桌面时扫码。

    控制台编码不支持半方块字符（如 GBK）时**直接跳过**并返回 False ——
    宁可不出图，也不要打一堆乱码或抛异常。调用方应提示二维码 PNG 路径。
    """
    import qrcode

    out = sys.stdout
    enc = (getattr(out, "encoding", None) or "utf-8") if out is not None else "utf-8"
    try:
        "▀".encode(enc)  # 探测：GBK 等编码无法表示 ▀
    except (UnicodeEncodeError, LookupError):
        return False
    if out is None:
        return False

    qr = qrcode.QRCode()
    qr.add_data(url)
    qr.make()
    qr.print_ascii(out=out)
    return True


# ---- 文件名清洗 --------------------------------------------
# werkzeug.secure_filename() 为跨平台安全会**丢弃所有非 ASCII 字符**，
# 导致中文文件名被剥成扩展名（"会议纪要.docx" -> "docx"），真实故障。
# 下面这版**保留 Unicode**，只剔除真正危险的字符。
_ILLEGAL_CHARS = '<>:"/\\|?*'          # Windows 非法字符 + 路径分隔符
_WIN_RESERVED = {                       # Windows 保留设备名（不分大小写）
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}
_FILENAME_MAX = 200


def safe_filename(name: str) -> str:
    """把上传文件名清洗成「安全且保留中文」的名字。

    与 `werkzeug.utils.secure_filename` 的关键差异：**保留 Unicode**
    （中文 / 日文 / emoji 都原样保留），避免用户文件名被静默丢弃。

    仍会剔除：路径分隔符 `/ \\`、空字节与控制字符、Windows 非法字符
    `<>:"|?*`；并规避 Windows 保留设备名（CON/PRN/AUX/NUL/COM1-9/LPT1-9）。
    结果为空时回落 `unnamed`；超长按 200 字符截断且保留扩展名。
    """
    if not name:
        return "unnamed"
    # 1) 只取最后一段（防御性兜底；上游 server 已显式拒 `..`/分隔符）
    name = name.replace("\\", "/").split("/")[-1]
    # 2) 非法字符 / 控制字符 → 下划线
    cleaned = [
        "_" if (ch in _ILLEGAL_CHARS or ord(ch) < 32 or ord(ch) == 127) else ch
        for ch in name
    ]
    name = "".join(cleaned).strip().strip(".").strip()
    # 3) 空 / 纯点 → 回落
    if not name or name in (".", ".."):
        return "unnamed"
    # 4) Windows 保留设备名（含带扩展名的情况）
    if name.split(".")[0].upper() in _WIN_RESERVED:
        name = "_" + name
    # 5) 长度截断（保留扩展名）
    if len(name) > _FILENAME_MAX:
        base, ext = os.path.splitext(name)
        keep = max(1, _FILENAME_MAX - len(ext))
        name = base[:keep] + ext
    return name


def unique_path(directory: str, filename: str, *, reserve: bool = True) -> str:
    """目标文件已存在时追加 (1)(2)…。

    实现上默认用 `O_CREAT|O_EXCL` **原子独占创建**占位文件，
    把「检查可用性」与「占位」合成一步，消除 TOCTOU 竞态
    （并发同名上传不再互相覆盖）。`reserve=False` 时退回纯探测（不创建文件）。
    """
    base, ext = os.path.splitext(filename)
    candidate = os.path.join(directory, filename)
    i = 1
    while True:
        if not reserve:
            if not os.path.exists(candidate):
                return candidate
        else:
            try:
                fd = os.open(candidate, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.close(fd)
                return candidate
            except FileExistsError:
                pass  # 已被占用（含并发抢占）→ 试下一个序号
        candidate = os.path.join(directory, f"{base}({i}){ext}")
        i += 1


def has_free_space(directory: str, needed_bytes: int, margin: float = 0.1) -> bool:
    """目标目录剩余空间是否足够写入 needed_bytes②）。

    预留 margin 比例余量（默认 10%），避免把磁盘写满拖垮系统。
    探测失败时**返回 True** —— 宁可放行，也不要因探测异常误拦正常上传。
    """
    if needed_bytes <= 0:
        return True
    try:
        free = shutil.disk_usage(directory).free
    except Exception:
        return True
    return free >= needed_bytes * (1.0 + margin)


def set_clipboard(text: str) -> bool:
    """写系统剪贴板，尽力而为；失败返回 False，不抛异常。"""
    try:
        import tkinter  # 3.12 运行时含 tkinter

        r = tkinter.Tk()
        r.withdraw()
        r.clipboard_clear()
        r.clipboard_append(text)
        r.update()
        r.destroy()
        return True
    except Exception:
        pass
    try:
        if sys.platform.startswith("win"):
            subprocess.run(["clip"], input=text.encode("utf-16le"), check=False)
        elif sys.platform == "darwin":
            subprocess.run(["pbcopy"], input=text.encode("utf-8"), check=False)
        else:
            subprocess.run(
                ["xclip", "-selection", "clipboard"], input=text.encode("utf-8"), check=False
            )
        return True
    except Exception:
        return False


def notify_upload(count: int, folder: str, cfg: dict | None = None) -> None:
    """上传完成后弹系统通知；失败静默。"""
    try:
        from plyer import notification

        notification.notify(
            title="QuickDrop 收到文件",
            message=f"收到 {count} 个文件，点击查看目录",
            timeout=8,
        )
    except Exception:
        return
    if cfg and cfg.get("open_folder_on_notify_click", True):
        try:
            if sys.platform.startswith("win"):
                os.startfile(folder)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", folder])
            else:
                subprocess.Popen(["xdg-open", folder])
        except Exception:
            pass
