# StudOn 同步

[English](README.md) | **中文**

> **非官方工具。** 本项目与 FAU、RRZE、StudOn 没有任何关系，也未经其认可。使用前请阅读下方[免责声明与使用规则](#免责声明与使用规则)。

自动把 FAU StudOn 课程里的文件下载到自己电脑上的文件夹（可以是 Google Drive / OneDrive / Dropbox 的同步文件夹），保持 StudOn 的文件夹结构，并可每天自动更新。

- 用 FAU IdM 账号登录（FAU SSO + TOTP 多因素认证，验证码自动生成）
- 账号、密码、TOTP secret 只保存在**本机**的系统钥匙串（macOS 钥匙串 / Windows 凭据管理器），不会上传
- 支持多个课程，每个课程可单独选择下载文件夹
- 增量同步：只下载新文件或服务器上更新过的文件；**从不删除本地文件**
- **保护你的笔记**：服务器上的文件更新时，若本地文件没改过就替换（旧版移到课程文件夹里隐藏的 `.studon-sync/versions/`）；
  若你改过（比如在 PDF 上做了笔记），绝不覆盖，新版另存为 `文件名 (StudOn 日期).pdf` 放在旁边，并提醒你
- 你自己删掉的文件不会被重新下载（除非在“文件”页重新勾选）；StudOn 上删掉的文件本地保留，并在“文件”页标出
- “文件”页可以勾选要下载的文件/文件夹；新文件可选“自动下载”或“等我确认”
- 只下载文件（不含视频、论坛、作业、链接）；请求限速，对 StudOn 友好
- 下载引擎基于 [PFERD](https://github.com/Garmelon/PFERD)

## 安装

- **macOS**：在 [Releases](https://github.com/Whohahaha/studon-sync/releases) 下载 [`StudOn-Sync-macOS.zip`](https://github.com/Whohahaha/studon-sync/releases/latest/download/StudOn-Sync-macOS.zip)（仅 Apple 芯片），解压后把 `StudOn Sync.app` 拖进“应用程序”。
  这个 App 没有 Apple 公证，第一次打开时请右键 → 打开（或在“系统设置 → 隐私与安全性”里点“仍要打开”）。
- **从源码运行**（macOS / Windows / Linux，需要 Python 3.11+）：
  ```bash
  git clone https://github.com/Whohahaha/studon-sync.git
  cd studon-sync
  python3 -m venv .venv
  .venv/bin/pip install -e .        # Windows: .venv\Scripts\pip install -e .
  .venv/bin/studon-sync             # 打开图形界面
  ```
  Windows 和 Linux 目前只在开发中测过，主要在 macOS 上使用。

## 使用（图形界面）

打开 **StudOn Sync.app**（或 `studon-sync` 命令），左侧有四页：

1. **账号**：填写 IdM 用户名、密码、TOTP secret，点“保存”。
   - TOTP secret：在 IdM 门户添加“软件令牌 / Authenticator App”时，二维码旁边显示的 Base32 字符串（或 `otpauth://` 链接）。
   - IdM 要求添加令牌后输入一次验证码确认：本页下方会实时显示当前 6 位验证码，填回 IdM 即可。
   - 点“测试登录”确认能登录。
2. **课程**：粘贴 StudOn 课程链接，点“添加课程”，课程名自动读取。每个课程可“更改文件夹”（比如选 Google Drive 里的文件夹）、暂停或移除。
3. **文件**：按 StudOn 的文件夹结构列出所有文件，勾选要下载的；状态标签显示已下载 / 你改过 / 有新版·笔记已保留 / 新·待确认 / StudOn 已删除 等。“刷新列表”只读取列表、不下载。
4. **同步**：点左下角“立即同步”；“自动同步”可选每天某个时间或每隔 N 小时。
   自动同步由系统在后台执行（macOS LaunchAgent / Windows 任务计划），不需要打开本程序；有新文件或同步失败时弹出通知。

界面语言：中文、English、Deutsch。默认跟随系统语言，可在左侧栏底部的语言菜单切换（或 `studon-sync --lang zh|en|de|auto`），通知和同步日志也会使用所选语言。

## 命令行

```bash
studon-sync setup              # 在终端里保存账号/密码/TOTP secret，并显示验证码供 IdM 确认
studon-sync code               # 显示当前 TOTP 验证码
studon-sync test-login         # 测试登录
studon-sync add-course URL [--target 文件夹]
studon-sync list
studon-sync sync               # 同步所有启用的课程
studon-sync scheduled          # 系统定时任务调用：到了设定时间才同步
studon-sync --lang zh          # 界面语言：zh | en | de | auto（跟随系统）
```

## 数据存放位置

| 内容 | macOS | Windows |
|---|---|---|
| 设置（课程、文件夹、计划） | `~/Library/Application Support/StudOn Sync/settings.json` | `%LOCALAPPDATA%\StudOn Sync\` |
| 每门课的文件记录、旧版本 | 课程文件夹里隐藏的 `.studon-sync/` | 同左 |
| 日志（每次同步一个文件） | `~/Library/Logs/StudOn Sync/` | `%LOCALAPPDATA%\StudOn Sync\Logs\` |
| 账号密码 | 钥匙串里**一个**条目：服务 `studon-sync`、账户 `credentials` | 凭据管理器，`studon-sync` |

## 常见问题

- **登录失败 “TOTP 验证码被拒绝”**：令牌还没在 IdM 里确认激活，或 secret 填错了。用“账号”页（或 `studon-sync code`）显示的验证码在 IdM 里确认；若手机 App 也有同一令牌，两边验证码应一致。为防锁号，每次登录只尝试一次验证码、密码错误不重试。
- **FAU 登录页改版**：登录失败时页面会保存到日志文件夹（`login-debug-*.html`），便于修复。这些页面可能包含你的用户名，在 issue 里分享前请先检查。
- **macOS 询问钥匙串访问**：点“始终允许”，只会问一次。App 有固定的代码签名，以后更新（重新构建）也不会再问。
- **同步到“文稿/桌面”里的文件夹失败（Operation not permitted）**：系统设置 → 隐私与安全性 → 文件与文件夹（或完全磁盘访问权限），允许 StudOn Sync。

## 免责声明与使用规则

- 本工具是学生个人项目，**非官方**，与 FAU / RRZE / StudOn 无关。按 MIT 许可证“按原样”提供，不提供任何担保，使用风险自负。
- **只用你自己的 IdM 账号，在你自己的电脑上运行。** FAU 的 [IT 使用规定](https://www.idm.fau.de/bedingungen) 禁止把账号密码交给别人或存放在别人也能用的设备上；用你账号做的一切操作都由你本人负责。不要替别人保存账号，不要把本工具做成网页或服务器代登录。
- **不要传播课程材料。** 课程文件受版权保护（§60a UrhG），只供本课程的老师和学生使用。下载文件夹不要公开共享，也不要上传到 GitHub 等公开位置。
- **对服务器友好。** 默认串行下载（`tasks = 1`）、每个请求间隔 1 秒；自动同步每天几次就够，请不要改成几分钟一次。IT 规定要求节约使用资源、不影响系统运行。
- 账号、密码和 TOTP secret 只保存在本机系统钥匙串里。密码和 TOTP 放在同一台电脑上会削弱双因素保护，请开启磁盘加密（FileVault / BitLocker）和锁屏密码。
- 违反 FAU 规定可能导致账号被停用。不确定时请先咨询 RRZE。StudOn 自己的使用条款请登录后在页脚查看。

## 开发 / 打包

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[build]"
.venv/bin/studon-sync                         # 运行
.venv/bin/python -m studon_sync.ui.devserver  # 在浏览器里调试界面 (http://127.0.0.1:8765)
.venv/bin/python -m pytest                    # 测试
packaging/build_mac.sh                        # 构建并签名 dist/StudOn Sync.app
```

**代码签名**：macOS 钥匙串的“始终允许”认的是 App 的签名。`build_mac.sh` 默认用一个自签名证书
“StudOn Sync Local Signing”签名（第一次运行时自动生成，放在
`~/Library/Application Support/StudOn Sync/signing/` 里单独的钥匙串中，不动登录钥匙串、不需要管理员密码），
所以重新构建后签名不变、不会重复弹窗。它只在本机有效。
要发给别人用时，换成 Apple Developer ID（每年 99 美元）：把证书装进登录钥匙串后运行
`SIGN_IDENTITY="Developer ID Application: 你的名字 (TEAMID)" packaging/build_mac.sh`，
再用 `xcrun notarytool` 公证，别人打开时就不会有“无法验证开发者”的提示。

macOS 生成 `dist/StudOn Sync.app`（约 30 MB，压缩后约 14 MB）。界面用系统自带的 WebView（pywebview），不打包浏览器内核。

许可证：[MIT](LICENSE)。下载引擎 [PFERD](https://github.com/Garmelon/PFERD) 同样使用 MIT 许可证。

代码结构：`src/studon_sync/core/`（登录、设置、同步、文件保护，不含界面代码）、`ui/`（HTML/CSS/JS 界面 + Python 接口）、`system.py`（系统定时任务、通知）、`__main__.py`（命令行）。界面文字在 `i18n.py`，添加语言只需加一组翻译，并在 `LANGUAGES` 里写上语言名。
