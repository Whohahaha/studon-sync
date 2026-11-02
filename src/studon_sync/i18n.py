"""User-facing strings. Add a language by adding a dict with the same keys."""

STRINGS: dict[str, dict[str, str]] = {
    "zh": {
        "app.title": "StudOn 同步",
        # errors from core
        "err.no_credentials": "还没有保存 IdM 账号和密码。",
        "err.no_totp": "登录要求 TOTP 验证码，但没有保存 TOTP secret。",
        "err.unknown_page": "FAU 登录页面格式未知，页面已保存到 {path}",
        "err.bad_credentials": "用户名或密码被拒绝（为避免锁号不再重试）。页面已保存到 {path}",
        "err.bad_otp": "TOTP 验证码被拒绝。请确认令牌已在 IdM 里激活、secret 正确。页面已保存到 {path}",
        "err.too_many_steps": "登录步骤过多，页面已保存到 {path}",
        "err.busy": "另一个同步正在进行。",
        "err.no_courses": "还没有启用的课程。",
        # sync summary
        "sum.header": "=== 本次汇总 ===",
        "sum.course": "{title} → {target}",
        "sum.counts": "  新增 {added} 个，更新 {changed} 个",
        "sum.errors": "  错误 {n} 个：",
        "sum.ok": "结果：成功（日志：{log}）",
        "sum.failed": "结果：失败（日志：{log}）",
        # GUI
        "tab.account": "账号",
        "tab.courses": "课程",
        "tab.sync": "同步",
        "acc.intro": "使用 FAU IdM 账号登录 StudOn。账号、密码和 TOTP secret 只保存在本机的系统钥匙串里。",
        "acc.username": "IdM 用户名",
        "acc.password": "密码",
        "acc.secret": "TOTP secret",
        "acc.saved_placeholder": "已保存（留空则不修改）",
        "acc.secret_placeholder": "Base32 字符串或 otpauth:// 链接",
        "acc.save": "保存",
        "acc.saved": "已保存到钥匙串。",
        "acc.test": "测试登录",
        "acc.testing": "正在登录…",
        "acc.test_ok": "登录成功 ✅",
        "acc.test_fail": "登录失败：{err}",
        "acc.code_title": "当前验证码",
        "acc.code_help": "在 IdM 添加令牌后，需要把这个验证码填回 IdM 确认。",
        "acc.code_left": "剩余 {s} 秒",
        "acc.code_none": "（输入或保存 TOTP secret 后显示）",
        "acc.bad_secret": "TOTP secret 格式不对（应为 Base32）。",
        "crs.intro": "粘贴 StudOn 课程链接添加课程。每个课程可以单独选择下载文件夹（例如 Google Drive 文件夹）。",
        "crs.url_placeholder": "https://www.studon.fau.de/studon/…ref_id=…",
        "crs.add": "添加",
        "crs.adding": "正在读取课程名…",
        "crs.bad_url": "没有在链接里找到课程编号（ref_id）。",
        "crs.exists": "这个课程已经添加过了。",
        "crs.no_title": "无法自动读取课程名，请输入：",
        "crs.col_enabled": "同步",
        "crs.col_title": "课程",
        "crs.col_target": "下载到",
        "crs.change_target": "更改文件夹…",
        "crs.remove": "移除",
        "crs.open": "打开文件夹",
        "crs.default_dir": "新课程默认下载到：",
        "crs.choose": "选择…",
        "sync.now": "立即同步",
        "sync.running": "正在同步…",
        "sync.last": "上次同步：{when}（{result}）",
        "sync.never": "还没有同步过",
        "sync.ok": "成功",
        "sync.failed": "失败",
        "sync.schedule": "自动同步",
        "sync.mode_off": "关闭",
        "sync.mode_daily": "每天",
        "sync.mode_interval": "每隔",
        "sync.hours": "小时",
        "sync.start_at_login": "开机登录后自动启动（在菜单栏后台运行）",
        "sync.open_logs": "打开日志文件夹",
        "sync.note": "自动同步由本程序在后台执行；关闭窗口后程序仍在菜单栏运行。",
        "tray.open": "打开窗口",
        "tray.sync": "立即同步",
        "tray.quit": "退出",
        "notify.new": "新增 {added} 个、更新 {changed} 个文件",
        "notify.failed": "同步失败，请查看日志",
    },
}

_lang = "zh"


def set_language(lang: str) -> None:
    global _lang
    _lang = lang if lang in STRINGS else "zh"


def t(key: str, **kwargs: object) -> str:
    text = STRINGS[_lang].get(key) or STRINGS["zh"].get(key, key)
    return text.format(**kwargs) if kwargs else text
