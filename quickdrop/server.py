"""QuickDrop / 快传 —— 电脑端主程序（Flask + token + 局域网直传）

行为要点
--------
- 所有 API 默认需要 token（URL `?token=` / 头 `X-Token` / Cookie）。
- **电脑本机浏览器**打开 `http://127.0.0.1:8765/`（无 token）→ 显示**引导页**：二维码 + 局域网地址 + 用法。
- **手机**必须访问电脑的**局域网 IP**（如 `http://192.168.x.x:8765/?token=...`）；
  `127.0.0.1` 在手机上指手机自己，会「无法打开页面」。
- 开发期日志：控制台 + `quickdrop/logs/quickdrop.log`；每个请求带 `request_id`；异常记录完整堆栈。

运行：`python server.py`（无 GUI 时自动回落为纯服务模式）
"""

from __future__ import annotations

import html
import ipaddress
import logging
import os
import shutil
import sys
import threading
import time
import traceback
import uuid
from urllib.parse import urlsplit

from flask import (
    Flask,
    abort,
    g,
    jsonify,
    make_response,
    request,
    send_file,
    send_from_directory,
)

import shared as S
import utils as U

COOKIE_NAME = "qd_token"
EXEMPT_PATHS = {"/manifest.json", "/sw.js", "/favicon.ico", "/api/health"}
EXEMPT_PREFIXES = ("/static/",)
LOOPBACK_HOSTS = {"127.0.0.1", "::1", "localhost"}

MAX_CLIPBOARD_BYTES = 1024 * 1024  # 剪贴板文本上限 1 MB

log = logging.getLogger("quickdrop")


def _host_allowed(host: str, cfg: dict) -> bool:
    """Host / Origin 主机名白名单/R3，防 DNS 重绑定与 CSRF）。

    放行：① 任意 **IP 字面量**（IPv4/IPv6，含 127.x 与本机各网卡 IP ——
    兼容多网卡、IP 变化，不写死）；② `localhost`；③ 配置的 mDNS 主机名。
    其余**域名一律拒绝** —— DNS 重绑定攻击必须借助域名，故按"是否 IP 字面量"
    判定即可闭环，且不牺牲局域网可用性。
    """
    host = (host or "").strip().lower().rstrip(".")
    if not host:
        return False
    if host == "localhost":
        return True
    try:
        ipaddress.ip_address(host)
        return True
    except ValueError:
        pass
    mdns = str(cfg.get("mdns_hostname") or "").strip().lower().rstrip(".")
    return bool(mdns) and host == mdns


def security_selfcheck(cfg: dict, base_dir: str | None = None) -> list[tuple[str, str]]:
    """启动期安全自检：把"当前真正生效的安全边界"显式写进日志。

    返回 `[(level, message)]`，由调用方按级别落日志。**只读、不改任何行为** ——
    目的是让问题可定位，
    并把 R6③（token 明文落盘）的 Git 泄露风险做成启动期显式告警。
    """
    base = base_dir or U.BASE_DIR
    out: list[tuple[str, str]] = []

    host = str(cfg.get("host", ""))
    port = cfg.get("port")
    if host in ("0.0.0.0", "::"):
        out.append((
            "warning",
            f"服务绑定 {host}:{port} —— 对**整个局域网**开放：同一 WiFi 下任何持有 token 的"
            "设备都能上传/下载/读写剪贴板。仅建议在可信网络（家里 / 自己手机热点）使用；"
            "公共 WiFi 下请用防火墙限制来源或临时关停。",
        ))
    else:
        out.append(("info", f"服务绑定 {host}:{port}（未对全网卡开放）"))

    mdns = str(cfg.get("mdns_hostname") or "").strip() or "（未配置）"
    out.append((
        "info",
        f"Host 白名单已启用：放行 IP 字面量 / localhost / {mdns}；其余域名 → 421（防 DNS 重绑定）",
    ))
    out.append(("info", "Origin 同源校验已启用：写操作若带跨站来源 → 403（防 CSRF）"))
    up_mb = cfg.get("max_upload_size_mb", 4096)
    out.append((
        "info",
        f"单次上传上限 {up_mb} MB；剪贴板文本上限 {MAX_CLIPBOARD_BYTES // (1024 * 1024)} MB；"
        "上传前校验接收目录剩余空间（预留 10% 余量）",
    ))

    recv = os.path.join(base, str(cfg.get("received_dir", "received")))
    try:
        os.makedirs(recv, exist_ok=True)
        free_mb = shutil.disk_usage(recv).free / (1024 * 1024)
        if os.access(recv, os.W_OK):
            out.append(("info", f"接收目录可写：{recv}（剩余 {free_mb:,.0f} MB）"))
        else:
            out.append(("warning", f"接收目录**不可写**：{recv} —— 上传会失败，请换可写目录"))
    except Exception as e:  # 探测失败不阻断启动
        out.append(("warning", f"接收目录检查失败：{recv}（{e}）"))

    # R6③：token 明文落盘；若处于 Git 工作树则显式告警，防误提交
    cfg_path = os.path.join(base, "config.json")
    if os.path.isfile(cfg_path):
        parent = os.path.dirname(base.rstrip(os.sep))
        in_git = os.path.isdir(os.path.join(base, ".git")) or os.path.isdir(
            os.path.join(parent, ".git")
        )
        if in_git:
            out.append((
                "warning",
                f"检测到 Git 工作树：{cfg_path} 含**明文 token**，请确认已被 .gitignore 忽略"
                "（`git check-ignore -v config.json`），切勿提交入库",
            ))
        else:
            out.append(("info", f"token 存于 {cfg_path}（当前非 Git 工作树，无入库泄露面）"))
    if not cfg.get("token"):
        out.append(("warning", "config.json 尚无 token —— 本次将自动生成并写回"))
    return out


def _is_loopback() -> bool:
    addr = (request.remote_addr or "").strip()
    return addr in LOOPBACK_HOSTS or addr.startswith("127.")


def _presented_token() -> str | None:
    return (
        request.args.get("token")
        or request.headers.get("X-Token")
        or request.cookies.get(COOKIE_NAME)
    )


def _rid() -> str:
    return getattr(g, "qd_rid", "-")


def _safe_path() -> str:
    """日志用路径：把 query 里的 token 脱敏，避免令牌落盘。"""
    try:
        if request.args.get("token"):
            return request.path + "?token=***"
        return request.full_path
    except Exception:
        return request.path


def redact(url: str) -> str:
    """把 URL 里的 token 值替换为 ***，用于日志。"""
    if "token=" not in url:
        return url
    head, _, rest = url.partition("token=")
    tail = rest.split("&", 1)
    suffix = ("&" + tail[1]) if len(tail) > 1 else ""
    return f"{head}token=***{suffix}"


def write_crash(kind: str, exc_type, exc, tb) -> str:
    """把未捕获异常的**完整堆栈**写 logs/crash.log，返回文件路径。

    窗口化 exe（console=False）没有控制台，崩溃时只能靠这里定位。
    """
    crash_path = os.path.join(U.LOG_DIR, "crash.log")
    try:
        os.makedirs(U.LOG_DIR, exist_ok=True)
        with open(crash_path, "a", encoding="utf-8") as f:
            f.write(f"\n===== {time.strftime('%Y-%m-%d %H:%M:%S')} [{kind}] =====\n")
            traceback.print_exception(exc_type, exc, tb, file=f)
    except Exception:
        pass
    return crash_path


def install_crash_logging() -> None:
    """挂上主线程 / 子线程的未捕获异常兜底，全部落到 logs/crash.log。"""
    def _main_hook(exc_type, exc, tb):
        write_crash("main-thread", exc_type, exc, tb)

    sys.excepthook = _main_hook

    def _thread_hook(args):  # Python 3.8+
        name = getattr(getattr(args, "thread", None), "name", "?")
        write_crash(f"thread:{name}", args.exc_type, args.exc_value, args.exc_traceback)

    threading.excepthook = _thread_hook


def _landing_html(lan_url: str, hostname: str, port: int) -> str:
    """本机访问时的引导页：显示二维码 + 局域网地址 + 用法。"""
    return f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>QuickDrop 快传 · 已启动</title>
<style>
 body{{font-family:-apple-system,"PingFang SC","Microsoft YaHei",sans-serif;background:#f5f7fa;color:#1f2733;text-align:center;padding:32px 16px}}
 .card{{background:#fff;max-width:540px;margin:0 auto;padding:28px;border-radius:16px;box-shadow:0 2px 12px rgba(0,0,0,.08)}}
 h1{{color:#4a90d9;margin:0 0 4px}} .ok{{color:#2e9e5b;font-weight:600}}
 img.qr{{width:240px;height:240px;margin:12px 0}}
 .url{{font-size:15px;word-break:break-all;color:#4a90d9;font-weight:600;background:#eef5fc;padding:10px;border-radius:8px}}
 .tip{{color:#7a8699;font-size:14px;line-height:1.8;margin-top:14px;text-align:left}}
 code{{background:#f0f3f7;padding:1px 5px;border-radius:4px}}
</style></head>
<body><div class="card">
  <h1>QuickDrop 快传</h1>
  <p class="ok">服务已启动 ✅</p>
  <img class="qr" src="/api/qr" alt="扫码连接">
  <p class="url">{html.escape(lan_url)}</p>
  <div class="tip">
    手机连<strong>同一个 WiFi</strong>，用手机相机<strong>扫码</strong>，或手动输入上面的地址。<br>
    ⚠️ 手机上<strong>不要用 <code>127.0.0.1</code></strong>（那指手机自己），要用电脑的局域网地址。<br>
    主机名（mDNS）：<code>{html.escape(hostname)}:{port}</code>（局域网支持时可用）。<br>
    电脑端主窗口也会显示同一张二维码。
  </div>
</div></body></html>"""


def create_app(cfg: dict | None = None) -> Flask:
    cfg = cfg or U.load_config()
    if not cfg.get("token"):
        U.load_or_create_token(cfg)

    app = Flask(__name__, static_folder=U.STATIC_DIR, static_url_path="/static")
    app.config["MAX_CONTENT_LENGTH"] = int(cfg.get("max_upload_size_mb", 4096)) * 1024 * 1024

    received_dir = os.path.join(U.BASE_DIR, cfg["received_dir"])
    shared_dir = os.path.join(U.BASE_DIR, cfg["shared_dir"])
    os.makedirs(received_dir, exist_ok=True)
    os.makedirs(shared_dir, exist_ok=True)

    shared = S.SharedFiles()
    if cfg.get("use_shared_dir"):
        for name in os.listdir(shared_dir):
            p = os.path.join(shared_dir, name)
            if os.path.isfile(p):
                shared.add(p)
    for p in cfg.get("shared_files", []):
        shared.add(p)

    clipboard = {"text": ""}

    # ---------- 日志：request_id + 请求记录 + 异常 ----------
    @app.before_request
    def _assign_rid():
        g.qd_rid = uuid.uuid4().hex[:8]
        g.qd_start = time.perf_counter()

    @app.after_request
    def _log_request(resp):
        try:
            dur = (time.perf_counter() - getattr(g, "qd_start", time.perf_counter())) * 1000
            log.info(
                "req=%s %s %s -> %s %s (%.0fms)",
                _rid(), request.method, _safe_path(), resp.status_code,
                request.remote_addr, dur,
            )
        except Exception:
            pass
        resp.headers["X-Request-Id"] = _rid()
        # ---- 安全响应头----
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("Referrer-Policy", "no-referrer")
        resp.headers.setdefault("X-Frame-Options", "DENY")
        if request.path.startswith("/api/"):
            resp.headers.setdefault("Cache-Control", "no-store")
        return resp

    @app.errorhandler(Exception)
    def _handle_exception(e):
        from werkzeug.exceptions import HTTPException

        if isinstance(e, HTTPException):
            if e.code and e.code >= 500:
                log.exception("req=%s 服务端错误 %s: %s", _rid(), request.path, e)
            else:
                log.warning("req=%s 客户端错误 %s: %s", _rid(), request.path, e)
            return jsonify({"error": e.description, "code": e.code, "request_id": _rid()}), e.code
        log.exception("req=%s 未捕获异常 %s: %s", _rid(), request.path, e)  # 完整堆栈进日志
        return jsonify({"error": "internal error", "code": 500, "request_id": _rid()}), 500

    # ---------- 纵深防御：Host 白名单 + Origin 同源/R3） ----------
    @app.before_request
    def _check_host():
        """拒绝非白名单 Host —— 防 DNS 重绑定（恶意域名解析到本机）。"""
        host = urlsplit("//" + (request.host or "")).hostname or ""
        if not _host_allowed(host, cfg):
            log.warning(
                "req=%s 拒绝(421) Host=%s remote=%s", _rid(), request.host, request.remote_addr
            )
            return jsonify({"error": "misdirected request", "code": 421, "request_id": _rid()}), 421
        return None

    @app.before_request
    def _check_origin():
        """写操作校验 Origin/Referer 同源 —— 防 CSRF。

        浏览器跨站请求必带 Origin；非浏览器客户端（curl/真机脚本）通常不带，
        此时交由 token 守卫把关，不破坏脚本化与真机自动化。
        """
        if request.method not in ("POST", "PUT", "PATCH", "DELETE"):
            return None
        origin = request.headers.get("Origin")
        if origin is None:
            origin = request.headers.get("Referer")
        if not origin:
            return None
        if origin.strip().lower() == "null":  # 沙箱 iframe / file:// 一律拒
            ohost = ""
        else:
            ohost = urlsplit(origin).hostname or ""
        if not ohost or not _host_allowed(ohost, cfg):
            log.warning(
                "req=%s 拒绝(403) 跨站来源 origin=%s remote=%s",
                _rid(), origin, request.remote_addr,
            )
            return jsonify(
                {"error": "cross-origin forbidden", "code": 403, "request_id": _rid()}
            ), 403
        return None

    # ---------- token 守卫 ----------
    @app.before_request
    def _guard():
        path = request.path
        if path in EXEMPT_PATHS or any(path.startswith(p) for p in EXEMPT_PREFIXES):
            return None
        if path == "/":
            return None  # index() 自行判断（应用页 / 本机引导页 / 403）
        if path == "/api/qr" and _is_loopback():
            return None  # 本机引导页需要二维码
        if _presented_token() != cfg.get("token"):
            log.warning("req=%s 拒绝(403) %s %s remote=%s", _rid(), request.method, path, request.remote_addr)
            return jsonify({"error": "forbidden", "code": 403, "request_id": _rid()}), 403
        return None

    # ---------- 页面 ----------
    @app.get("/")
    def index():
        # 1) 带正确 token → 手机端应用页 + 种 Cookie
        if _presented_token() == cfg.get("token"):
            resp = make_response(send_from_directory(U.STATIC_DIR, "index.html"))
            resp.set_cookie(COOKIE_NAME, cfg["token"], max_age=365 * 24 * 3600, httponly=True, samesite="Lax")
            return resp
        # 2) 本机（127.0.0.1）→ 引导页，直接显示二维码
        if _is_loopback():
            ip = U.get_lan_ip()
            lan_url = f"http://{ip}:{cfg['port']}/?token={cfg['token']}"
            log.info("req=%s 本机访问 → 引导页（含二维码）", _rid())
            resp = make_response(_landing_html(lan_url, cfg.get("mdns_hostname", ""), cfg["port"]))
            resp.headers["Content-Type"] = "text/html; charset=utf-8"
            return resp
        # 3) 其它机器无 token → 403（不在免鉴权资源里泄露 token）
        log.warning("req=%s 非本机无 token 访问 / → 403 remote=%s", _rid(), request.remote_addr)
        return jsonify({"error": "forbidden", "code": 403, "request_id": _rid()}), 403

    @app.get("/manifest.json")
    def manifest():
        return send_from_directory(
            U.STATIC_DIR, "manifest.json", mimetype="application/manifest+json"
        )

    @app.get("/sw.js")
    def service_worker():
        resp = make_response(send_from_directory(U.STATIC_DIR, "sw.js"))
        resp.headers["Content-Type"] = "application/javascript"
        resp.headers["Service-Worker-Allowed"] = "/"
        return resp

    # ---------- API ----------
    @app.get("/api/health")
    def health():
        return jsonify({"status": "ok"})

    @app.get("/api/files")
    def api_files():
        return jsonify({"files": shared.list()})

    @app.get("/api/download/<fid>")
    def api_download(fid: str):
        path = shared.get_path(fid)
        if not path or not os.path.isfile(path):
            abort(404)
        return send_file(path, as_attachment=True, download_name=os.path.basename(path))

    @app.post("/api/upload")
    def api_upload():
        files = request.files.getlist("file") or request.files.getlist("files")
        base = os.path.abspath(received_dir)
        # ②：写盘前先看剩余空间，避免写满磁盘把系统拖垮
        need = request.content_length or 0
        if not U.has_free_space(base, need):
            try:
                free_mb = shutil.disk_usage(base).free / (1024 * 1024)
            except Exception:
                free_mb = -1.0
            log.warning(
                "req=%s 拒绝(507) 空间不足：需 %d bytes，剩余 %.0f MB", _rid(), need, free_mb
            )
            return jsonify(
                {"error": "insufficient storage", "code": 507, "request_id": _rid()}
            ), 507
        saved: list[str] = []
        for f in files:
            if f is None or not f.filename:
                continue
            raw = f.filename
            if ".." in raw or "/" in raw or "\\" in raw:  # 契约：路径穿越 → 400
                abort(400)
            fname = U.safe_filename(raw)  # ：保留中文文件名
            target = os.path.abspath(U.unique_path(received_dir, fname))
            if not target.startswith(base):
                abort(400)
            f.save(target)
            saved.append(os.path.basename(target))
        log.info("req=%s 收到 %d 个文件 → %s", _rid(), len(saved), received_dir)
        if saved and cfg.get("notify_on_upload", True):
            U.notify_upload(len(saved), received_dir, cfg)
        return jsonify({"saved": saved, "count": len(saved)})

    @app.post("/api/delete/<fid>")
    def api_delete(fid: str):
        shared.remove(fid)
        return jsonify({"ok": True})

    @app.route("/api/clipboard", methods=["GET", "POST"])
    def api_clipboard():
        if request.method == "POST":
            if request.is_json:
                text = (request.get_json(silent=True) or {}).get("text", "")
            else:
                text = request.form.get("text", "")
            if not isinstance(text, str):
                text = str(text)
            nbytes = len(text.encode("utf-8"))
            if nbytes > MAX_CLIPBOARD_BYTES:  # 
                log.warning("req=%s 剪贴板文本超限 %d bytes", _rid(), nbytes)
                return jsonify(
                    {"error": "clipboard too large", "code": 413, "request_id": _rid()}
                ), 413
            clipboard["text"] = text
            U.set_clipboard(text)
            return jsonify({"ok": True, "length": len(text)})
        return jsonify({"text": clipboard["text"]})

    @app.get("/api/qr")
    def api_qr():
        ip = U.get_lan_ip()
        url = f"http://{ip}:{cfg['port']}/?token={cfg['token']}"
        path = os.path.join(U.BASE_DIR, "qrcode.png")
        U.generate_qr(url, path)
        return send_file(path, mimetype="image/png")

    app.extensions["quickdrop"] = {
        "shared": shared,
        "received_dir": received_dir,
        "shared_dir": shared_dir,
        "clipboard": clipboard,
        "config": cfg,
    }
    return app


def main() -> int:
    install_crash_logging()      # 崩溃兜底：堆栈落 logs/crash.log
    U.make_std_streams_safe()    # ★ 控制台编码兜底：GBK 下 emoji 不再崩程序
    cfg = U.load_config()
    if not cfg.get("token"):
        U.load_or_create_token(cfg)
    logger = U.setup_logging()
    logger.info("=== QuickDrop 启动 ===")
    for _lvl, _msg in security_selfcheck(cfg):  # 启动期安全自检
        (logger.warning if _lvl == "warning" else logger.info)("[安全自检] %s", _msg)

    app = create_app(cfg)
    ip = U.get_lan_ip()
    url = f"http://{ip}:{cfg['port']}/?token={cfg['token']}"
    qr_path = os.path.join(U.BASE_DIR, "qrcode.png")
    U.generate_qr(url, qr_path)  # ★ 二维码生成点：quickdrop/qrcode.png

    ext = app.extensions["quickdrop"]
    shared = ext["shared"]
    received_dir = ext["received_dir"]

    from waitress import create_server

    server = create_server(app, host=cfg["host"], port=cfg["port"], threads=8)
    threading.Thread(target=server.run, daemon=True).start()

    mdns_handle = None
    if cfg.get("enable_mdns", True):
        try:
            import mdns

            mdns_handle = mdns.publish(cfg["mdns_hostname"], cfg["port"], ip)
            logger.info("mDNS 已发布 http://%s:%s/", cfg["mdns_hostname"], cfg["port"])
        except Exception as e:
            logger.warning("mDNS 发布失败（%s），用 IP 访问即可", e)

    logger.info("手机访问地址：%s", redact(url))
    logger.info("本机自检页（含二维码）：http://127.0.0.1:%s/", cfg["port"])
    logger.info("二维码文件：%s", qr_path)
    logger.info("日志文件：%s", os.path.join(U.BASE_DIR, "logs", "quickdrop.log"))
    print(f"[QuickDrop] 手机访问：{url}")
    print(f"[QuickDrop] 本机自检页（含二维码）：http://127.0.0.1:{cfg['port']}/")
    print(f"[QuickDrop] ⚠️ 手机上不要用 127.0.0.1，要用上面的局域网 IP")

    def stop():
        try:
            import mdns

            mdns.unpublish(mdns_handle)
        except Exception:
            pass
        try:
            server.close()
        except Exception:
            pass
        logger.info("=== QuickDrop 已停止 ===")

    try:
        if os.environ.get("QUICKDROP_HEADLESS") == "1":
            raise RuntimeError("QUICKDROP_HEADLESS=1（开发/无头模式）")
        import gui

        gui.build_window(url, qr_path, shared, received_dir, cfg, on_close=stop)
    except (SystemExit, KeyboardInterrupt):
        raise
    except BaseException as e:  # 无显示环境（无头）→ 回落为纯服务模式
        logger.warning("GUI 不可用（%s），回落为纯服务模式，按 Ctrl+C 退出", e)
        logger.debug("GUI 异常堆栈：\n%s", traceback.format_exc())
        try:
            if not U.print_ascii_qr(url):
                logger.info("当前终端编码不支持终端二维码，请扫码文件：%s", qr_path)
        except Exception:
            logger.debug("终端二维码打印失败：\n%s", traceback.format_exc())
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            stop()
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except BaseException:  # 最后一道网：完整堆栈落 logs/crash.log
        path = write_crash("entry", *sys.exc_info())
        for _stream in (sys.stderr, sys.__stderr__):
            try:
                if _stream is not None:
                    traceback.print_exc(file=_stream)
                    break
            except Exception:
                pass
        sys.exit(1)
