# 架构说明

本文档说明 QuickDrop 的技术选型、整体架构、数据流与关键实现取舍。

> 面向想读源码或参与开发的人。普通使用者请看 [usage.md](usage.md)。

---

## 一、设计目标与约束

QuickDrop 的形态由一组硬约束决定，理解这些约束才能理解为什么代码长这样。

| 约束 | 内容 |
|---|---|
| 不经过外部服务器 | 传输必须局域网直连，无云服务、无外部 API |
| 不引入重型框架 | 无 React / Vue / 数据库 / Redis / 消息队列 |
| 不常驻 | 不做开机自启、不做系统托盘，**关窗口即退出** |
| 零配置 | 双击即用，不要求用户装数据库、注册账号、填 IP |
| 依赖尽量少 | 只用 pip 上能装到的纯 Python 库，尽量不需编译 |

最后一条是 `requirements.txt` 只有 9 项的原因。

---

## 二、技术选型

| 领域 | 选择 | 理由 |
|---|---|---|
| 语言 | Python 3.10+ | 桌面临床脚本语言，打包成 exe 门槛低 |
| Web 框架 | **Flask 3.x** | 路由少（约 10 个），Werkzeug 提供了 `send_from_directory` 等实用能力 |
| WSGI | **waitress**（8 线程） | 比 Flask 自带的 dev server 稳；纯 Python 无编译依赖；多线程足够局域网场景 |
| 桌面 GUI | **Tkinter**（标准库） | 零额外依赖，Python 自带 |
| 拖拽 | **tkinterdnd2** | Tkinter 拖拽的事实标准，附带 tkdnd 原生库 |
| 二维码 | **qrcode + Pillow** | 纯 Python 生成 PNG；无 GUI 时可降级打印 ASCII |
| 系统通知 | **plyer** | 跨平台通知，Windows 下走 win10toast |
| mDNS | **zeroconf** | 让 `quickdrop.local` 免 IP 访问 |
| 前端 | **原生 HTML/CSS/JS** | 无构建步骤，手机端页面 ≤ 几百行 |
| PWA | manifest.json + sw.js | 手机可"添加到主屏幕"，免重复扫码 |
| 打包 | **PyInstaller 6.x** | onefile 单文件，target 面向 Windows |

**为什么不用 Electron / Tauri**：那会把一个几百 KB 的脚本变成几十 MB 的安装包，与"轻量直传工具"的定位冲突。

**为什么服务端是纯 HTTP**：见 [security-design.md](security-design.md#31-http-明文传输影响最大) —— HTTPS 是预留字段，当前未实现。

---

## 三、整体架构

```
┌─────────────────────────── 电脑 ────────────────────────────┐
│                                                             │
│  ┌─────────────┐                                           │
│  │  gui.py     │  Tkinter 主窗口                           │
│  │  (二维码/   │  · 展示二维码与访问地址                     │
│  │   拖拽区)   │  · 接收拖拽的文件                           │
│  └──────┬──────┘                                           │
│         │ SharedFiles.add()                                │
│         ▼                                                   │
│  ┌─────────────────────────────────────────────┐            │
│  │  server.py      Flask app 工厂 + 路由        │            │
│  │                                              │            │
│  │  before_request 链：                        │            │
│  │    _assign_rid  → 分配 req id              │            │
│  │    _check_host  → Host 白名单（防 DNS 重绑定）│            │
│  │    _check_origin→ Origin 同源（防 CSRF）      │            │
│  │    _guard       → token 鉴权                │            │
│  │  after_request：                             │            │
│  │    _log_request → 统一日志 + 安全响应头       │            │
│  └──────┬───────────────────────────┬───────────┘            │
│         │                           │                        │
│         ▼                           ▼                        │
│  ┌──────────────┐           ┌──────────────────┐            │
│  │  shared.py   │           │  static/         │            │
│  │  SharedFiles │           │  index.html      │            │
│  │  内存态共享  │           │  app.js          │            │
│  │  HMAC file_id│           │  style.css       │            │
│  └──────────────┘           │  manifest.json   │            │
│                             │  sw.js           │            │
│  ┌──────────────┐           │  icon-192/512.png│            │
│  │  utils.py    │           └──────────────────┘            │
│  │  配置/token  │                     │                    │
│  │  文件名清洗  │                     │                    │
│  │  日志/通知   │                     │                    │
│  └──────┬───────┘                     │                    │
│         │                             │                    │
│         ▼                             ▼                    │
│  ┌──────────────────────────────────────────────┐          │
│  │  waitress (0.0.0.0:8765, 8 threads)          │          │
│  └──────────────────┬───────────────────────────┘          │
│                     │ HTTP                                   │
└─────────────────────┼───────────────────────────────────────┘
                      │
┌─────────────────────┼───────────────────────────────────────┐
│  ┌──────────────┐   │   ┌──────────────────────────────┐   │
│  │  mdns.py     │   │   │  手机浏览器                   │   │
│  │  zeroconf    │───┼──▶│  quickdrop.local:8765         │   │
│  │  发布/注销   │   │   │  上传 / 下载 / 文本           │   │
│  └──────────────┘   │   └──────────────────────────────┘   │
└─────────────────────┴──────────────────────────────────────┘
                      │
              ┌───────┴────────┐
              ▼                ▼
        received/          shared/
      (手机上传落盘)      (可选共享目录)
```

**运行时的磁盘布局**（全部相对程序目录）：

```
<程序目录>/
├── config.json        配置 + 持久化 token
├── received/          手机上传的文件落这里
├── shared/            可选共享目录
├── logs/              quickdrop.log / crash.log
├── qrcode.png         本次运行生成
└── static/            只读前端资源（打包时嵌入）
```

用 `BASE_DIR`（`utils.py`）基于 `__file__` 计算，因此源码运行与 exe 运行**布局一致** —— 打包出的 `dist/QuickDrop.exe` 旁边同样会生成这些目录。

---

## 四、关键实现

### 4.1 鉴权链：before_request 四段

每个请求依次经过四个钩子（`server.py`）：

| 顺序 | 钩子 | 职责 |
|---|---|---|
| 1 | `_assign_rid` | 生成 8 位 request id，存入 `g`，并回写 `X-Request-Id` 头 |
| 2 | `_check_host` | Host 白名单，不匹配 → `421` |
| 3 | `_check_origin` | 写操作校验 Origin，跨站 → `403` |
| 4 | `_guard` | token 校验，不匹配 → `403` |

顺序有讲究：Host / Origin 是**廉价的前置过滤**，先挡掉明显异常，再做相对贵的 token 比对。

### 4.2 token 三通道与免鉴权白名单

```python
# 概念示意
def _presented_token():
    return (request.args.get("token")        # ① URL 参数（扫码直连）
            or request.headers.get("X-Token") # ② 请求头（程序化调用）
            or request.cookies.get("qd_token")) # ③ Cookie（免重复输入）
```

免鉴权的路径被压到最小（`EXEMPT_PATHS` / `EXEMPT_PREFIXES`）：

| 路径 | 为什么免鉴权 |
|---|---|
| `/api/health` | 健康检查，不返回任何数据 |
| `/manifest.json`、`/sw.js` | PWA 静态资源。**必须免鉴权**，否则带 token 的入口与 PWA 的 `start_url="/"` 不一致会导致 Service Worker 注册失败 |
| `/` | 由 `index()` 自行判断（见下） |
| `/api/qr` | 仅**本机 loopback** 才放行，给引导页显示二维码 |

`/` 的三段判断值得注意：

1. 带正确 token → 返回手机端应用页，**同时种 Cookie**（`HttpOnly` + `SameSite=Lax` + 1 年）
2. 无 token 但来自 `127.0.0.1` → 返回本机引导页（含二维码）
3. 无 token 且来自其他机器 → `403`

这样 token 不会出现在任何免鉴权资源里，避免泄漏面扩大。

### 4.3 文件名安全：自己实现而不用 `secure_filename`

Werkzeug 的 `secure_filename()` 为跨平台安全会**丢弃所有非 ASCII 字符**：

```
'会议纪要.docx'   -> 'docx'      ← 文件名丢失
'a b.jpg'         -> 'a_b.jpg'
'../../evil.txt'  -> 'evil.txt'  ← 穿越防护仍生效
```

对中文用户这是致命的功能缺陷 —— 手机传一张「照片.jpg」，落盘变成「jpg」。

因此自研 `utils.safe_filename()`，策略是**保留 Unicode，只剔除真正危险的东西**：

- 路径分隔符 `/ \`、空字节、控制字符 `\x00-\x1f`
- Windows 非法字符 `< > : " | ? *`
- Windows 保留设备名 `CON` / `PRN` / `AUX` / `NUL` / `COM1-9` / `LPT1-9`
- 长度截断 200 字符；结果为空回落 `unnamed`

路径穿越防护另外走两道：显式拒绝 `..` 与分隔符，再做 `abspath` 前缀包含校验。

### 4.4 原子落盘：消除并发竞态

朴素做法"检查文件不存在 → 返回路径 → 调用方写入"存在 TOCTOU 竞态：两个并发上传同名文件可能都拿到同一路径，后写覆盖先写。

```python
# 概念示意
while True:
    try:
        fd = os.open(candidate, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        return fd   # 句柄已独占占位
    except FileExistsError:
        i += 1      # 换下一个序号重试
```

`O_CREAT | O_EXCL` 保证创建与占位是**一个原子操作**，检查与使用合一。waitress 是 8 线程，因此这个防护是必要的。

### 4.5 不可预测的文件 ID

共享文件用 8 位 ID 作 URL 路径（`/api/download/<fid>`）。早期版本用无盐 MD5（`md5(abspath)[:8]`），但输入是**可猜的绝对路径**，ID 可离线推算。

现改为带进程随机盐的 HMAC-SHA256：

```python
salt = secrets.token_bytes(16)                                   # 进程启动时随机
fid = hmac.new(salt, path.encode(), hashlib.sha256).hexdigest()[:8]
```

进程内不可预测，长度仍保持 8 位以兼容既有 API 契约。

### 4.6 日志与崩溃兜底

每条请求一行，含 `req=` 编号、状态码、来源 IP、耗时；token 一律替换为 `token=***`。

崩溃兜底装了三层：主线程 `sys.excepthook`、子线程 `threading.excepthook`、以及全局错误处理器，堆栈写入 `crash.log`。

**控制台编码兜底**：Windows 中文环境下 stdout 可能是 GBK，直接输出 emoji 会抛 `UnicodeEncodeError` 导致程序崩溃。启动时检测并降级编码。

### 4.7 拖拽的实现

`tkinterdnd2` 的拖放事件把路径交给 `SharedFiles.add()`：

- 文件夹**递归展开**，里面所有文件加入共享
- 源文件被删除/移动时，下次 `refresh()` 自动剔除（`SharedFiles` 每次刷新都会检查存在性）

`use_shared_dir=true` 时，`shared/` 目录整个作为共享源，供不方便拖拽的场景使用。

### 4.8 打包要点

`QuickDrop.spec` 里的关键配置：

| 配置 | 原因 |
|---|---|
| `console=False` | GUI 程序不弹黑窗口 |
| `collect_all("tkinterdnd2")` | 拖拽依赖 tkdnd 原生库，PyInstaller 静态分析抓不到 |
| `collect_all("plyer")` | 通知后端按平台动态导入 |
| `collect_all("zeroconf")` | 同上 |
| `static/` 作 `datas` | 只读资源原样嵌入 |
| 排除 `pytest` / `unittest` / `pydoc` / `doctest` | 减小体积 |

产物为单文件 exe（约 24 MB），`config.json` / `received/` / `shared/` / `logs/` / `qrcode.png` **不打包**，首次运行时在 exe 同目录生成 —— 这也是"别把 exe 放在只读目录"的原因。

---

## 五、API 一览

| 方法 | 路径 | 鉴权 | 说明 |
|---|---|---|---|
| GET | `/` | 条件免鉴权 | 带 token → 应用页 + 种 Cookie；本机 → 引导页；否则 403 |
| GET | `/api/health` | 免 | 健康检查，不返回数据 |
| GET | `/api/files` | 需 | 共享文件列表 |
| GET | `/api/download/<fid>` | 需 | 下载共享文件 |
| POST | `/api/upload` | 需 | 手机上传文件（多文件） |
| POST | `/api/delete/<fid>` | 需 | 移除共享 |
| GET/POST | `/api/clipboard` | GET 条件免 / POST 需 | 读/写剪贴板，写入上限 1 MB |
| GET | `/api/qr` | 仅本机 | 返回二维码 PNG |
| GET | `/manifest.json` | 免 | PWA 清单 |
| GET | `/sw.js` | 免 | Service Worker |

---

## 六、目录结构

```
quickdrop/
├── server.py           # 入口：Flask app 工厂 + 鉴权链 + 路由 + 启动
├── utils.py            # 配置/token/文件名清洗/原子落盘/日志/剪贴板/通知
├── shared.py           # SharedFiles：共享文件增删查 + HMAC file_id
├── gui.py              # Tkinter 主窗口：二维码 + 地址 + 拖拽区
├── mdns.py             # mDNS 发布/注销 quickdrop.local
├── gen_icons.py        # 一次性工具：生成 PWA 图标
├── static/             # 手机端页面与 PWA 资源
│   ├── index.html      # 应用页
│   ├── app.js          # 全部交互逻辑
│   ├── style.css
│   ├── manifest.json   # PWA 清单
│   ├── sw.js           # Service Worker
│   ├── icon-192.png
│   └── icon-512.png
├── requirements.txt    # 9 项依赖，全部带兼容上界
├── requirements.lock   # 22 条精确版本，可复现基线
├── QuickDrop.spec      # PyInstaller 配置
├── run.bat             # 开发启动
├── build.bat           # 打包出 dist/QuickDrop.exe
└── README.md           # 目录内说明
```

代码在 `quickdrop/` 子目录而非仓库根，这不是随意选择：

1. `server.py` 用 `import shared as S` / `import utils as U` 平铺导入，无包前缀也无 `sys.path` 操作 → **源码必须在同目录**
2. `BASE_DIR` 基于 `__file__` → 运行产物必须与源码同级，提根会让 `config.json` / `logs/` 落在仓库根与文档混在一起
3. 忽略规则需精确绑定子树

---

## 七、为什么这些"缺失"是有意的

| 缺失 | 原因 |
|---|---|
| HTTPS | 局域网点对点场景下，先做功能再考虑；`config.json` 已预留字段 |
| 断点续传 | 局域网吞吐足够，传一半失败重传成本可接受 |
| 开机自启 | 明确的产品决策：不想让用户电脑被一个传输工具长期驻留 |
| 系统托盘常驻 | 同上，关窗口即退出是特性 |
| 数据库 | 无需持久化用户数据，`config.json` + 内存态足够 |
| 单元测试框架 | 项目内使用独立探针脚本验证（未开源），非 pytest |

---

## 八、扩展方向

若要继续开发，几个可能的方向与它们的权衡：

| 方向 | 收益 | 代价 |
|---|---|---|
| **实现 HTTPS**（自签证书） | 消除公共 WiFi 嗅探风险 | 证书分发体验差；自签证书手机端需手动信任 |
| 断点续传 | 大文件弱网体验 | 需引入分片协议，前端复杂度上升 |
| 目录级访问控制 | 共享更细粒度 | 破坏"简单"的产品定位 |
| 二维码有效期 | 缩小口令暴露窗口 | 用户频繁重扫会烦 |
| 移动端原生壳 | 免浏览器、可后台 | 需引入 App 构建链，与"零构建"冲突 |
| 更多语言 | 可及性 | 需国际化框架与翻译流程 |

**建议的下一步是实现 HTTPS**，其余都属锦上添花。理由见 [security-design.md](security-design.md#31-http-明文传输影响最大) —— 明文传输是当前唯一影响"能否在非可信网络使用"的短板。

---

*相关文档：[usage.md](usage.md) 使用说明 · [security-design.md](security-design.md) 安全设计*
