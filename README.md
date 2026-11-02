# StudOn 同步

自动把 FAU StudOn 课程里的文件下载到自己电脑上的文件夹（可以是 Google Drive / OneDrive / Dropbox 的同步文件夹），保持 StudOn 的文件夹结构，并可每天自动更新。

- 用 FAU IdM 账号登录（FAU SSO + TOTP 多因素认证，验证码自动生成）
- 账号、密码、TOTP secret 只保存在**本机**的系统钥匙串（macOS 钥匙串 / Windows 凭据管理器），不会上传
- 支持多个课程，每个课程可单独选择下载文件夹
- 增量同步：只下载新文件或服务器上更新过的文件；**从不删除本地文件**；本地改过的文件不会被覆盖
- 只下载文件（不含视频、论坛、作业、链接）；请求限速，对 StudOn 友好
- 下载引擎基于 [PFERD](https://github.com/Garmelon/PFERD)

## 使用（图形界面）

打开 **StudOn Sync.app**（或 `studon-sync` 命令），依次：

1. **账号**：填写 IdM 用户名、密码、TOTP secret，点“保存”。
   - TOTP secret：在 IdM 门户添加“软件令牌 / Authenticator App”时，二维码旁边显示的 Base32 字符串（或 `otpauth://` 链接）。
   - IdM 要求添加令牌后输入一次验证码确认：本页下方会实时显示当前 6 位验证码，填回 IdM 即可。
   - 点“测试登录”确认能登录。
2. **课程**：粘贴 StudOn 课程链接，点“添加”。课程名会自动读取。选中课程可“更改文件夹…”（比如选 Google Drive 里的文件夹）。
3. **同步**：点“立即同步”；在“自动同步”里选“每天 HH:MM”或“每隔 N 小时”；勾选“开机登录后自动启动”。
   关闭窗口后程序留在菜单栏继续按计划同步；有新文件或同步失败时会弹出通知。

## 命令行

```bash
studon-sync setup              # 在终端里保存账号/密码/TOTP secret，并显示验证码供 IdM 确认
studon-sync code               # 显示当前 TOTP 验证码
studon-sync test-login         # 测试登录
studon-sync add-course URL [--target 文件夹]
studon-sync list
studon-sync sync               # 同步所有启用的课程
```

## 数据存放位置

| 内容 | macOS | Windows |
|---|---|---|
| 设置（课程、文件夹、计划） | `~/Library/Application Support/StudOn Sync/settings.json` | `%LOCALAPPDATA%\StudOn Sync\` |
| 日志（每次同步一个文件） | `~/Library/Logs/StudOn Sync/` | `%LOCALAPPDATA%\StudOn Sync\Logs\` |
| 账号密码 | 钥匙串，服务名 `studon-sync` | 凭据管理器，`studon-sync` |

## 常见问题

- **登录失败 “TOTP 验证码被拒绝”**：令牌还没在 IdM 里确认激活，或 secret 填错了。用“账号”页（或 `studon-sync code`）显示的验证码在 IdM 里确认；若手机 App 也有同一令牌，两边验证码应一致。为防锁号，每次登录只尝试一次验证码、密码错误不重试。
- **FAU 登录页改版**：登录失败时页面会保存到日志文件夹（`login-debug-*.html`），便于修复。
- **macOS 询问钥匙串访问**：点“始终允许”。
- **同步到“文稿/桌面”里的文件夹失败（Operation not permitted）**：系统设置 → 隐私与安全性 → 文件与文件夹（或完全磁盘访问权限），允许 StudOn Sync。

## 开发 / 打包

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[build]"
.venv/bin/studon-sync                         # 运行
cd packaging && ../.venv/bin/pyinstaller --noconfirm --distpath ../dist --workpath ../build studon-sync.spec
```

macOS 生成 `dist/StudOn Sync.app`。代码结构：`src/studon_sync/core/`（登录、设置、同步，不含界面代码）、`gui/`（PySide6 界面）、`__main__.py`（命令行）。界面文字在 `i18n.py`，添加语言只需加一组翻译。
