# 参与 QuickDrop 贡献

无论你是想修个 bug、加个功能，还是第一次看这个项目，都欢迎。

这份文档假设你**没读过**架构文档也能上手。

---

## 上手三步

**所有代码都在 `quickdrop/` 子目录里。**

```bat
cd quickdrop
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

然后：

```bat
run.bat                    :: 开发启动
build.bat                  :: 打包出 dist\QuickDrop.exe
```

macOS / Linux：

```bash
cd quickdrop
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
python server.py
```

环境要求：**Python 3.10+**，建议 3.12（部分 3.13 发行版不含 `tkinter`）。

---

## 项目结构速览

```
quickdrop/
├── server.py      Flask app 工厂 + 鉴权链 + 路由 + 启动服务    ← 主入口
├── utils.py       配置/口令/文件名清洗/原子落盘/日志/通知     ← 最常改
├── shared.py      共享文件增删查 + file_id 生成
├── gui.py         Tkinter 主窗口
├── mdns.py        mDNS 发布/注销
├── gen_icons.py   一次性工具：生成 PWA 图标
└── static/        手机端页面（index.html / app.js / style.css / manifest / sw）
```

- `server.py` 是入口，也是所有 HTTP 路由所在
- `utils.py` 是工具层，改动影响面最大
- 前端是**原生 JS**，无构建步骤，改完直接刷新手机页面即可

想理解设计意图，读 [`docs/architecture.md`](docs/architecture.md)。

---

## 代码风格

跟随现有代码，不必另立一套：

| 项 | 约定 |
|---|---|
| 缩进 | **4 空格**（不是 Tab） |
| 编码 | UTF-8 |
| 文件头 | `from __future__ import annotations` |
| 类型注解 | 尽量加，尤其是公开函数 |
| docstring | **中文**，模块级 `"""模块说明。"""`，函数级说明职责与返回 |
| 注释 | 只写"为什么"，不写"做了什么" |
| 行宽 | 尽量不超过 100 列 |
| 字符串 | 统一用双引号 |

**几条约定的原因**：
- 中文 docstring 是这个项目一贯的风格，请保持一致
- 类型注解用 `str | None` 这种新式写法（需要 `from __future__ import annotations`）
- 静态资源用 `textContent` 而不是 `innerHTML`（防 XSS），改前端时请保持

---

## 提交信息规范

用 [Conventional Commits](https://www.conventionalcommits.org/zh-hans/)：

```
<类型>: <简短描述>

<正文：为什么改、怎么改、影响什么>
```

**类型**：

| 类型 | 用于 |
|---|---|
| `feat` | 新功能 |
| `fix` | 修 bug |
| `docs` | 只改文档 |
| `refactor` | 重构，不改行为 |
| `perf` | 性能优化 |
| `style` | 格式调整（空格、分号等） |
| `chore` | 构建脚本、依赖更新等杂务 |
| `fix` | **安全问题也用这个**，但请在正文说明威胁与修复 |

**示例**：

```
fix: 并发上传同名文件时不再互相覆盖

unique_path 原来只探测路径是否存在再返回，两个并发请求可能拿到
同一路径导致后写覆盖先写。改为 os.open(O_CREAT|O_EXCL) 原子独占
创建，检查与占位合成一步。
```

标题行控制在 72 字符以内。

---

## PR 流程

1. **Fork** 本仓库到你自己的账号
2. 从 `main` 切出分支：`git checkout -b fix/xxx` 或 `feat/xxx`
3. 提交你的改动
4. push 到你的 fork
5. 在本仓库开Pull Request，**描述里写清改了什么、为什么**

**一个 PR 只做一件事。** 混着修 bug + 加功能 + 改格式的 PR 很难 review。

---

## 测试现状（请注意）

项目开发期使用一套内部验证脚本，**尚未随源码开源**。这意味着：

- 你**不需要**通过"跑通现有测试"来验证自己的改动
- 但请**手动验证**你改动的功能确实能用，别提交未测过的代码
- 欢迎你**补充测试** —— 这是最缺的一环，PR 请优先提在这里

**最低验证清单**（改动后逐条过）：

- [ ] 程序能正常启动，窗口弹出、二维码显示正常
- [ ] 手机能扫码连上，页面加载正常
- [ ] 手机上传文件成功，电脑收到文件
- [ ] 电脑拖拽共享文件后，手机能下载
- [ ] 文本快传能写入电脑剪贴板
- [ ] 关闭窗口后端口释放（`netstat -ano | findstr :8765` 应查不到）

**若你改动了安全相关代码**（`safe_filename`、鉴权、Host/Origin 校验、落盘逻辑），请额外验证：

```bat
REM Host 头应被拒（421，不是 200）
curl --noproxy "*" -H "Host: evil.com" -i http://127.0.0.1:8765/api/health

REM 安全响应头应齐备
curl --noproxy "*" -I http://127.0.0.1:8765/api/health
```

> ⚠️ 加 `--noproxy "*"` 是因为本机 curl 可能走系统代理，会把"网络不通"误报成"502"，干扰判断。

---

## 硬约束（请勿突破）

这是项目的立身之本，改动时必须保持：

| 约束 | 为什么 |
|---|---|
| **不引入重型框架** | 无 React / Vue / 数据库 / Redis。定位是轻量单文件工具 |
| **不依赖外部服务** | 不联网上报、不用云存储、不加遥测 |
| **不做开机自启、不做托盘常驻** | 关窗口即退出是**特性**，不是待修复的缺陷 |
| **依赖必须带版本上界** | `>=x,<y`。仅下界会导致某次升级静默引入破坏性变更或含 CVE 的版本 |
| **不提交 `config.json`** | 含访问口令，已在 `.gitignore` 中。提交前请跑 `git status` 确认 |
| **静态资源用 `textContent`** | 防 XSS。确需插入 HTML 时必须 `html.escape()` |
| **外部命令用 argv 列表** | 禁止 `shell=True` 拼接，防命令注入 |

---

## 需要帮助时

- 架构疑问 → 读 [`docs/architecture.md`](docs/architecture.md)
- 怎么用 → 读 [`docs/usage.md`](docs/usage.md)
- 安全相关 → 读 [`docs/security-design.md`](docs/security-design.md) 与 [`SECURITY.md`](SECURITY.md)
- 卡住太久 → 搜搜有没有已存在的 Issue，没有就开一个问，别硬啃

---

## 发现了安全问题？

**不要开公开 Issue。** 请按 [`SECURITY.md`](SECURITY.md) 里的方式私下报告。

---

*感谢你的贡献。*
