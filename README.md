# QuickDrop · 快传

**电脑上双击启动，手机扫二维码即连，同一个 WiFi 内双向直传文件——不经过任何外部服务器。**

没有注册、没有登录、没有云端、不上传网盘。就像把 U 盘插在两台机器之间，只不过中间是 WiFi。

---

## 这是什么

一个局域网点对点文件传输工具。电脑跑一个小程序，手机扫码连上，然后：

| 你想做的事 | 怎么做 |
|---|---|
| 手机里的照片/视频传到电脑 | 手机选文件 → 上传，文件落到电脑接收目录，弹系统通知 |
| 电脑里的文件发给手机 | 把文件**拖进电脑窗口** → 手机上点一下直接下载 |
| 手机上打的文字发到电脑 | 发送 → 电脑剪贴板直接有了，`Ctrl+V` 粘贴 |

传输在两台设备之间**直接传输**，不进任何第三方服务器。项目不做开机自启、不做后台常驻，**关掉窗口就是彻底退出**。

## 特点

- **扫码即连**，不用装App、不用注册登录
- **中文文件名原样保留** —— 「会议纪要.docx」不会变成「docx」
- **同名文件不覆盖**，自动改成 `xxx(1).txt`、`xxx(2).txt`
- **12 位访问口令**保护，同一 WiFi 下没口令的人打不开你的文件
- **手机页面可"添加到主屏幕"**，之后点桌面图标直接打开
- **关窗口即退出**，不做后台常驻、不做开机自启
- 极轻量：9 个 Python 依赖，打包后单文件 exe 约 24 MB

---

## 30 秒上手

> **所有代码都在 `quickdrop/` 子目录里**，不在仓库根。

### 方式一：用打包好的 exe（Windows）

从 [Releases](https://github.com/lflrt/QuickDrop/releases) 下载 `QuickDrop.exe`，双击运行即可，无需安装 Python。

首次运行时 Windows 防火墙会询问是否允许访问，请点**允许**（勾选"专用网络"），否则手机连不上。

### 方式二：从源码运行

需要 **Python 3.10+**（建议 3.12）。

```bat
cd quickdrop
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
run.bat
```

三行命令，看到窗口弹出二维码就成了。

### 怎么让手机连上

1. 手机和电脑连**同一个 WiFi**
2. 手机用**相机扫窗口里的二维码**
3. 🚫 手机上**不要输 `127.0.0.1`** —— 那指的是手机自己。要用电脑的局域网 IP（窗口里已经显示好了）

---

## 怎么用

### 手机 → 电脑

手机相机扫码 → 选文件（可多选）→ 上传。电脑上弹通知，文件出现在接收目录。

### 电脑 → 手机

把文件或**整个文件夹拖进窗口的共享列表**（文件夹会递归展开）→ 手机上点文件名下载。

不支持拖拽时：把文件放进 `shared/` 目录，在 `config.json` 里设 `use_shared_dir: true`。

### 文本快传

手机输入文字发送 → 电脑剪贴板被写入 → 直接 `Ctrl+V`。

### 装成 App（PWA）

手机浏览器打开后 → 菜单选**添加到主屏幕** → 之后从桌面图标打开，首次仍需扫码一次。

完整的操作步骤、配置说明、常见问题见 **[`docs/usage.md`](docs/usage.md)**。

---

## 界面说明

程序有**三个界面**，别混淆：

| 界面 | 在哪 | 给谁用 |
|---|---|---|
| **电脑主窗口** | 启动后弹出 | 看二维码、拖拽共享、打开接收目录 |
| **手机页面** | 手机扫码后 | 上传、下载、发文本 |
| **本机引导页** | 电脑浏览器开 `http://127.0.0.1:8765/` | 电脑上自检，放大看二维码 |

---

## 项目结构

```
QuickDrop/
├── quickdrop/                    ← 全部代码在这里
│   ├── server.py                 # 入口：Flask + 鉴权链 + 路由 + 启动服务
│   ├── utils.py                  # 配置/口令/文件名清洗/原子落盘/日志/通知
│   ├── shared.py                 # 共享文件管理（HMAC file_id）
│   ├── gui.py                    # Tkinter 主窗口：二维码 + 地址 + 拖拽区
│   ├── mdns.py                   # mDNS 发布 quickdrop.local
│   ├── gen_icons.py              # 一次性工具：生成 PWA 图标
│   ├── static/                   # 手机端页面与 PWA 资源
│   ├── requirements.txt          # 9 个依赖（带版本上界）
│   ├── requirements.lock         # 精确版本基线
│   ├── QuickDrop.spec            # PyInstaller 配置
│   ├── run.bat / build.bat       # 开发启动 / 打包
│   └── README.md                 # 目录内说明
├── docs/
│   ├── usage.md                  # 使用说明（完整）
│   ├── architecture.md           # 架构与技术选型
│   └── security-design.md        # 安全设计
├── SECURITY.md                   # 安全策略与漏洞上报
├── CONTRIBUTING.md               # 参与贡献
└── LICENSE                       # MIT
```

---

## 从源码运行

### 环境要求

- **Python 3.10+**，建议 3.12（部分 3.13 发行版不含 `tkinter`）
- Windows（已验证）；macOS / Linux 可尝试源码运行但**未验证**

### 启动

```bat
cd quickdrop
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
run.bat
```

macOS / Linux 手动执行：

```bash
cd quickdrop
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
python server.py
```

> Linux 需自行安装 `python3-tk`，否则 GUI 报错。无桌面环境会自动回落纯服务模式。

### 无头模式（不开窗口，只看日志）

```bat
set QUICKDROP_HEADLESS=1
.venv\Scripts\python.exe server.py
```

按 `Ctrl+C` 退出。macOS / Linux 用 `export QUICKDROP_HEADLESS=1`。

### 打包成 exe

```bat
cd quickdrop
build.bat
```

产物：`quickdrop/dist/QuickDrop.exe`（单文件，约 24 MB，双击即用）。

> ⚠️ **别把 exe 放在只读目录**（如 `C:\Program Files`）—— 配置文件、日志、接收目录都需要在程序目录旁边生成。放桌面或文档目录即可。

---

## 配置

首次运行自动在程序目录生成 `config.json`，**改完需重启**。

| 字段 | 默认 | 说明 |
|---|---|---|
| `host` | `0.0.0.0` | 监听地址。改成 `127.0.0.1` 则只允许本机访问 |
| `port` | `8765` | 端口，被占用时可改 |
| `token` | 随机 12 位 | 访问口令。**删掉此值会重新生成，手机需重新扫码** |
| `enable_mdns` | `true` | 是否发布 `quickdrop.local` |
| `received_dir` | `received` | 手机上传文件的落盘目录 |
| `use_shared_dir` | `false` | 是否把 `shared/` 整个目录当作共享 |
| `max_upload_size_mb` | `4096` | 单次请求大小上限 |
| `notify_on_upload` | `true` | 收到文件是否弹系统通知 |

完整字段表见 [`docs/usage.md`](docs/usage.md#六配置文件-configjson)。

---

## 安全设计

本项目的传输在**局域网内点对点直连**，不经过任何外部服务器，服务只监听端口不主动外联。在功能之外还做了这些加固：

| 防护 | 说明 |
|---|---|
| 12 位随机口令 | `secrets.choice()` 密码学安全随机源；三通道鉴权（URL / 头 / HttpOnly Cookie） |
| Host 白名单 | 阻断 DNS 重绑定，非 IP 字面量的 `Host` 一律 `421` |
| Origin 同源校验 | 写操作阻断 CSRF，跨站来源 `403` |
| 路径穿越防护 | 显式拒绝 `..` 与分隔符 + `abspath` 前缀包含校验 |
| **保留中文文件名** | 自研 `safe_filename()`，替代会剥掉中文的 `werkzeug.secure_filename` |
| 原子落盘 | `O_CREAT\|O_EXCL` 独占创建，并发同名上传不互相覆盖 |
| 不可预测 file_id | 带进程随机盐的 HMAC-SHA256 |
| 安全响应头 | `nosniff` / `DENY` / `no-referrer` / `no-store` |
| 资源耗尽防护 | 剪贴板 1 MB 上限（`413`）、上传前磁盘预检（`507`） |
| 日志脱敏 | 口令一律显示为 `token=***`，明文不落盘 |
| 依赖可复现 | 9 条依赖带版本上界 + lock 基线；`pip-audit` 扫 22 条依赖 0 条已知漏洞 |

### ⚠️ 已知局限：请认真读

**QuickDrop 只用 HTTP，没有 HTTPS。** `config.json` 里的 `enable_https` / `cert_file` / `key_file` 是**预留字段，当前代码并不读取**。

后果：同一局域网内的其他设备理论上可以嗅探你的传输内容与访问口令。**请只在可信网络下使用，不要在公共 WiFi 下长时间运行。**

另外需要注意：持有口令的人可以访问全部共享文件与上传接口；服务对局域网内所有设备开放（可把 `host` 改为 `127.0.0.1` 限制为本机）。

完整的威胁模型、已实现控制与验证方式见 **[`docs/security-design.md`](docs/security-design.md)**，漏洞上报方式见 **[`SECURITY.md`](SECURITY.md)**。

---

## 常见问题

| 现象 | 原因 | 怎么办 |
|---|---|---|
| 手机打不开页面 | 没连同一 WiFi / 输成 `127.0.0.1` / 防火墙没放行 | 用窗口里那个 `http://192.168.x.x:8765/...` 地址；防火墙点允许 |
| 页面一直转圈 | WiFi 有「AP 隔离」或走了访客网络 | 关掉路由器 AP 隔离，或换主网络 |
| 能开页面但报 403 | 口令不匹配 | 重新扫二维码 |
| 收到的文件不见了 | 程序放在只读目录 | 移到桌面/文档等可写目录重跑 |
| 电脑 IP 变了书签失效 | DHCP 重新分配 | 用 `quickdrop.local` 访问（mDNS），或重扫 |
| 关窗后端口还在听 | 有残留进程 | `netstat -ano \| findstr :8765` 找 PID 后 `taskkill /F /PID <pid>` |
| 传输很慢/中断 | 信号差、2.4G 频段、路由器限速 | 靠近路由器、改用 5G 频段 |
| 杀毒软件报警 | 自编译 exe 常见误报 | 加信任；或改用 `run.bat` 跑源码 |

更多见 [`docs/usage.md`](docs/usage.md#八常见问题)。

---

## 已知限制

- ❌ **不做开机自启、不做系统托盘常驻** —— 关闭窗口即完全退出（这是有意的产品决策）
- ❌ **仅同一 WiFi / 局域网可用** —— 跨网络（4G / 公网）不可用
- ❌ **仅 HTTP，无 HTTPS** —— 见上方「已知局限」
- ⚠️ **官方仅在 Windows 上验证** —— macOS / Linux 可尝试源码运行 `python server.py`，但未做验证、不提供打包脚本
- ⚠️ mDNS（`quickdrop.local`）依赖路由器组播，部分网络会被屏蔽 → 此时用 IP 访问
- ⚠️ PWA **首次仍须扫码一次**以种 Cookie，之后从主屏幕打开免扫码
- ⚠️ 无断点续传、无自动清理接收目录、无开机自启
- ⚠️ 上传的文件**不做查杀**，不要用它接收陌生来源的文件

---

## 参与贡献

欢迎 PR。上手三步（见 [`CONTRIBUTING.md`](CONTRIBUTING.md)）：

```bat
cd quickdrop
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

**改代码时请注意**
- 保持**无数据库、无外部服务依赖**的定位
- 不要引入 React / Vue / Redis 等重型框架
- 依赖新增必须带版本上界
- **不要提交 `config.json`**（含访问口令，已在 `.gitignore` 中）

---

## 许可证

[MIT](LICENSE) © 2026 lflrt

代码全部原创，依赖均为 pip 上的第三方库。MIT 允许商业使用与闭源衍生分发。
