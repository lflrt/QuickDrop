# QuickDrop / 快传

> 双击启动，手机扫码 / PWA，**同一 WiFi**，直接传文件。传输只在局域网内直连，**不经过任何外部服务器**。

项目介绍见[仓库根 README](../README.md)，架构说明见 [`docs/architecture.md`](../docs/architecture.md)，安全设计见 [`docs/security-design.md`](../docs/security-design.md)。

## 运行环境
- Python **3.10+**，建议 **3.12**（本项目在 3.12.13 上开发验证；部分 3.13 发行版不含 `tkinter`）。
- **Windows 已验证**（交付 Windows exe）。macOS / Linux 可尝试源码运行 `python server.py`，但未做验证、不提供打包脚本；Linux 需自行安装 `python3-tk`。

完整使用说明见 [`docs/usage.md`](../docs/usage.md)。

## 快速开始（开发）

```bat
cd /d <项目>\quickdrop
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
run.bat                        :: 或手动： .venv\Scripts\python.exe server.py
```

**启动成功的样子**（同时弹出主窗口：左侧二维码、右侧访问地址）：

```
=== QuickDrop 启动 ===
mDNS 已发布 http://quickdrop.local:8765/
手机访问地址：http://192.168.x.x:8765/?token=********
本机自检页（含二维码）：http://127.0.0.1:8765/
二维码文件：...\quickdrop\qrcode.png
日志文件：...\quickdrop\logs\quickdrop.log
```

### 怎么让手机连上（最容易踩的坑）
1. 手机连**同一个 WiFi**（不能一个 WiFi 一个流量）。
2. 用手机**相机扫窗口里的二维码**，或手动输入 `http://<电脑局域网IP>:8765/?token=<token>`。
3. 🚫 **手机上不要输 `127.0.0.1`** —— 那指手机自己，必然"无法打开页面"。要用**电脑的局域网 IP**。
4. 首次运行请在弹出的防火墙对话框点 **允许访问**。

> 电脑本机浏览器打开 `http://127.0.0.1:8765/` 会看到**引导页**（大字 + 二维码 + 用法说明）——这是给"电脑上自检"用的，不是手机页。

### 无头/纯服务模式（只看日志、不开窗）
```bat
set QUICKDROP_HEADLESS=1
.venv\Scripts\python.exe server.py
```

## 开发期日志（排障用）

| 文件 | 内容 |
|---|---|
| `logs/quickdrop.log` | 每次请求一行（含 `req=<8位request_id>`、方法、脱敏路径、状态码、来源IP、耗时） |
| `logs/crash.log` | **未捕获异常完整堆栈**（主线程 + 子线程 + 入口兜底）。正常运行时不会出现该文件 |

- 响应头带 `X-Request-Id`，与日志里的 `req=` **同值**，可双向定位。
- **token 自动脱敏**：日志里只会出现 `token=***`，不会把令牌落到磁盘。
- 看尾部 20 行：
  ```bat
  powershell -NoProfile -Command "Get-Content -Tail 20 'logs\quickdrop.log'"
  ```

## 打包

```bat
cd /d <项目>\quickdrop
build.bat                                      :: 或手动：
.venv\Scripts\python.exe -m PyInstaller --noconfirm QuickDrop.spec
```

产物：**`dist\QuickDrop.exe`**（单文件，约 24MB；双击即用）。

打包要点（见 `QuickDrop.spec`）：
- `tkinterdnd2`（含 tkdnd 原生库）、`plyer`（按平台动态导入）、`zeroconf` → `collect_all`。
- `static/` 作为**只读资源**打进包里；`config.json` / `received/` / `shared/` / `logs/` / `qrcode.png`
  在**首次运行时于 exe 同目录生成**（所以**别把 exe 放在只读目录**，如 `Program Files`）。
- exe 为 GUI 程序（无控制台），**诊断一律看 `logs\`**。

## 目录结构
```
quickdrop/
├── server.py            # 主程序：Flask + token 守卫 + 引导页 + 日志 + 启动服务
├── utils.py             # 配置/token/二维码/日志/剪贴板/通知/打包路径适配
├── shared.py            # 共享文件管理（增删查、id 映射）
├── gui.py               # Tkinter 主窗口（二维码 + 地址 + 拖拽共享区）
├── mdns.py              # mDNS 发布 quickdrop.local
├── gen_icons.py         # 一次性工具：生成 PWA 图标
├── QuickDrop.spec       # PyInstaller 配置
├── run.bat              # 一键启动（开发）
├── build.bat            # 一键打包（出 dist\QuickDrop.exe）
├── config.json          # 配置（含持久化 token；首次运行生成）
├── requirements.txt     # 依赖清单（带兼容上界）
├── requirements.lock    # 精确版本基线（可复现）
├── logs/                # quickdrop.log / crash.log（运行时生成）
├── received/            # 手机上传到电脑的文件（运行时生成）
├── shared/              # 可选共享目录（use_shared_dir=true 时）
└── static/              # 手机端页面与 PWA 资源（index/style/app/manifest/sw/图标）
```

> 上表中 `config.json` / `logs/` / `received/` / `shared/` / `qrcode.png` 均为**运行时生成**，已列入 `.gitignore`，克隆仓库后首次运行会自动创建。

## 已知限制
- 不做开机自启、不做系统托盘常驻（**关闭窗口即退出**）。
- 仅**同一 WiFi / 局域网**可用；跨网络（4G/公网）不可用。
- ⚠️ **仅 HTTP，无 HTTPS**。`config.json` 的 `enable_https` / `cert_file` / `key_file` 是预留字段，**当前代码不读取**。详见 [`docs/security-design.md`](../docs/security-design.md)。
- PWA 鉴权用 `start_url="/"` + 持久 HttpOnly Cookie：**首次仍须扫码一次**以种 Cookie，之后从主屏幕打开免扫码。
- mDNS（`quickdrop.local`）依赖路由器组播，部分网络会被屏蔽 → 此时用 IP 访问。
- 窗口化 exe **没有控制台输出**，找不到问题时看 `logs\quickdrop.log` 与 `logs\crash.log`。
- 官方仅在 **Windows** 上验证；macOS / Linux 未验证且无打包脚本。

## 安全说明
- 所有 API 默认需要 token（URL `?token=` / 头 `X-Token` / Cookie `qd_token`）；token 首次随机生成（12 位）并持久化到 `config.json`。
- 文件名安全过滤 + 路径穿越显式拒绝；上传目录与共享目录分离；限制单文件大小（默认 4096MB）。
- 日志与终端输出均对 token 脱敏；控制台编码兜底（GBK 下 emoji 不会崩程序）。

### 安全加固（详见 [`docs/security-design.md`](../docs/security-design.md)）
- **保留中文文件名**：自研 `utils.safe_filename()` 替代 `werkzeug.secure_filename`（后者会把「会议纪要.docx」剥成「docx」）。仍剔除路径分隔符、控制字符、Windows 非法字符与保留设备名。
- **Host 白名单（防 DNS 重绑定）**：只放行 IP 字面量、`localhost`、配置的 mDNS 主机名；其余域名 → `421`。
- **Origin 同源校验（防 CSRF）**：写操作若带跨站 `Origin`/`Referer` → `403`；不带来源的脚本/真机请求不受影响。
- **原子落盘**：`unique_path` 用 `O_CREAT|O_EXCL` 独占创建，并发同名上传不再互相覆盖。
- **不可预测文件 ID**：`file_id` 由无盐 MD5 改为带进程随机盐的 HMAC-SHA256（保持 8 位）。
- **安全响应头**：统一 `X-Content-Type-Options: nosniff`、`X-Frame-Options: DENY`、`Referrer-Policy: no-referrer`；`/api/*` 追加 `Cache-Control: no-store`。
- **剪贴板限长**：文本超过 1 MB → `413`。
- **依赖加兼容上界**：`requirements.txt` 全部 `>=x,<y`，避免仅下界导致升级引入破坏性变更。
- **磁盘空间预检**：上传前检查接收目录剩余空间（预留 10% 余量），不足返回 `507`，不会写一半就撑爆磁盘。
- **启动期安全自检**：启动时把**生效中的安全边界**逐条写入 `logs/quickdrop.log`（`[安全自检]` 前缀），包括"是否对全网卡开放""接收目录剩余空间""token 存放位置"；若检测到 Git 工作树会**告警勿提交 `config.json`**。
- **可复现基线**：`requirements.lock`（`pip freeze` 全量精确版本）用于精确复现本机已验证的依赖组合；换平台后应重新生成。
