"""User-facing strings. Add a language by adding a dict with the same keys (and a name in LANGUAGES).

The language setting is "auto" (follow the system language) or one of the LANGUAGES codes.
Missing keys fall back to English, then to the key itself.
"""

import locale
import os
import subprocess
import sys
from typing import Optional

LANGUAGES = {"zh": "中文", "en": "English", "de": "Deutsch"}  # shown in their own language
FALLBACK = "en"  # for systems in a language we do not have

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
        "err.not_logged_in": "登录流程走完了，但 StudOn 仍显示未登录。",
        "err.course_login_failed": "登录失败，本课程本次未同步：{err}",
        "err.course_incomplete": "本课程本次没有同步完成（详见日志）。",
        "err.no_courses": "还没有启用的课程。",
        # sync log
        "log.reuse_login": "[studon-sync] 复用已有登录",
        "log.new_login": "[studon-sync] 新登录 FAU SSO + TOTP",
        # sync summary
        "sum.header": "=== 本次汇总 ===",
        "sum.course": "{title} → {target}",
        "sum.counts": "  新增 {added} 个，更新 {changed} 个",
        "sum.errors": "  错误 {n} 个：",
        "sum.kept_edited": "    ★ {path} 在 StudOn 上有新版本，你的笔记版本已保留；新版本另存为 {alt}",
        "sum.pending": "  {n} 个新文件等待你在“文件”页确认",
        "sum.removed_remote": "    − {path} 已从 StudOn 删除（本地保留）",
        "sum.ok": "结果：成功（日志：{log}）",
        "sum.failed": "结果：失败（日志：{log}）",
        # UI
        "nav.sync": "同步",
        "nav.courses": "课程",
        "nav.files": "文件",
        "nav.account": "账号",
        "lang.label": "语言",
        "lang.auto": "跟随系统",
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
        "acc.test_ok": "登录成功 ✓",
        "acc.test_fail": "登录失败：{err}",
        "acc.code_title": "当前验证码",
        "acc.code_help": "在 IdM 添加令牌后，需要把这个验证码填回 IdM 确认。正在输入 secret 时显示的是输入值对应的验证码。",
        "acc.copy": "复制",
        "acc.copied": "已复制验证码",
        "acc.bad_secret": "TOTP secret 格式不对（应为 Base32）。",
        "crs.intro": "粘贴 StudOn 课程链接添加课程。每个课程可以单独选择下载文件夹（例如 Google Drive 里的文件夹）。",
        "crs.url_placeholder": "粘贴课程链接，例如 https://www.studon.fau.de/studon/…ref_id=…",
        "crs.add": "添加课程",
        "crs.adding": "正在读取课程名…",
        "crs.added": "已添加。",
        "crs.bad_url": "没有在链接里找到课程编号（ref_id）。",
        "crs.exists": "这个课程已经添加过了。",
        "crs.enabled": "参与同步",
        "crs.disabled": "已暂停",
        "crs.files": "挑选文件",
        "crs.change_target": "更改文件夹",
        "crs.open": "打开",
        "crs.remove": "移除",
        "crs.remove_confirm": "从列表移除这个课程？已下载的文件会保留。",
        "crs.default_dir": "新课程默认下载到",
        "crs.choose": "选择…",
        "sync.now": "立即同步",
        "sync.running": "正在同步…",
        "sync.last": "上次同步：{when} · {result}",
        "sync.never": "还没有同步过",
        "sync.ok": "成功",
        "sync.failed": "失败",
        "sync.files": "个文件",
        "sync.pending": "个待确认",
        "sync.no_courses": "还没有课程，去“课程”页添加。",
        "sched.title": "自动同步",
        "sched.off": "关闭",
        "sched.daily": "每天",
        "sched.interval": "间隔",
        "sched.at": "时间",
        "sched.every": "每隔",
        "sched.hours": "小时",
        "sched.hint": "由系统在后台执行，不需要打开本程序；电脑睡眠错过的同步会在醒来后补上。",
        "log.title": "日志",
        "log.open": "打开日志文件夹",
        "files.intro": "勾选要下载的文件。取消勾选的文件不会下载；已下载的文件不会被删除。",
        "files.new_policy": "新文件",
        "files.auto": "自动下载",
        "files.review": "等我确认",
        "files.only_new": "只看新文件",
        "files.refresh": "刷新列表",
        "files.refreshing": "正在读取 StudOn 上的文件列表（不下载）…",
        "files.as_of": "列表更新于 {when}，双击文件可打开",
        "files.never": "还没有读取过文件列表，点“刷新列表”。",
        "files.empty": "没有文件。点“刷新列表”从 StudOn 读取。",
        "files.none_new": "最近没有新文件。",
        "st.downloaded": "已下载",
        "st.edited": "你改过",
        "st.kept_edited": "有新版·笔记已保留",
        "st.pending": "新·待确认",
        "st.not_yet": "下次同步下载",
        "st.unselected": "不下载",
        "st.deleted_locally": "你已删除",
        "st.removed_remote": "StudOn 已删除",
        "st.alt_hint": "StudOn 的新版本另存为：{files}",
        "notify.new": "新增 {added} 个、更新 {changed} 个文件",
        "notify.kept_edited": "{n} 个有新版本，你的笔记版本已保留",
        "notify.failed": "同步失败，请查看日志",
        # command line
        "cli.usage": (
            "StudOn 同步\n\n"
            "  studon-sync                    打开图形界面\n"
            "  studon-sync setup              在终端里保存 IdM 账号、密码、TOTP secret\n"
            "  studon-sync code               显示当前 TOTP 验证码（在 IdM 里确认令牌用）\n"
            "  studon-sync test-login         测试登录\n"
            "  studon-sync add-course URL     添加课程（可加 --target 文件夹）\n"
            "  studon-sync list               列出课程\n"
            "  studon-sync sync               同步所有启用的课程\n"
            "  studon-sync scheduled          （系统定时任务调用）到了设定时间就同步\n"
            "  studon-sync --lang zh|en|de|auto  设置界面语言"
        ),
        "cli.code_prompt": "把下面的 6 位验证码填回 IdM 确认令牌；完成后按回车。",
        "cli.code_line": "  当前验证码：{code}   剩余 {left:2d} 秒  ",
        "cli.setup_intro": "保存登录信息到系统钥匙串（服务名 studon-sync）。直接回车 = 保留已保存的值。",
        "cli.username": "FAU IdM 用户名 [{user}]：",
        "cli.password": "IdM 密码（输入时不显示）：",
        "cli.secret": "TOTP secret（Base32 或 otpauth:// 链接，输入时不显示）：",
        "cli.bad_secret": "TOTP secret 格式不对（应为 Base32），未保存任何内容。",
        "cli.empty": "用户名和密码不能为空，未保存任何内容。",
        "cli.saved": "已保存。",
        "cli.no_secret": "还没有保存 TOTP secret，请先运行 setup。",
        "cli.login_ok": "登录成功 ✅",
        "cli.added": "已添加：{title} → {target}",
        "cli.no_courses": "还没有课程。",
        "cli.lang_set": "界面语言已设为：{lang}",
    },
    "en": {
        "app.title": "StudOn Sync",
        "err.no_credentials": "No IdM username and password saved yet.",
        "err.no_totp": "The login asks for a TOTP code, but no TOTP secret is saved.",
        "err.unknown_page": "Unknown FAU login page layout. The page was saved to {path}",
        "err.bad_credentials": "Username or password rejected (not retried, to avoid locking the account). The page was saved to {path}",
        "err.bad_otp": "TOTP code rejected. Check that the token is activated in IdM and the secret is correct. The page was saved to {path}",
        "err.too_many_steps": "Too many login steps. The page was saved to {path}",
        "err.busy": "Another sync is already running.",
        "err.not_logged_in": "The login finished, but StudOn still shows you as logged out.",
        "err.course_login_failed": "Login failed, this course was not synced this time: {err}",
        "err.course_incomplete": "This course did not finish syncing this time (see the log).",
        "err.no_courses": "No enabled courses yet.",
        "log.reuse_login": "[studon-sync] Reusing the existing login",
        "log.new_login": "[studon-sync] New login via FAU SSO + TOTP",
        "sum.header": "=== Summary ===",
        "sum.course": "{title} → {target}",
        "sum.counts": "  {added} new, {changed} updated",
        "sum.errors": "  {n} errors:",
        "sum.kept_edited": "    ★ {path} has a new version on StudOn. Your annotated copy was kept; the new version was saved as {alt}",
        "sum.pending": "  {n} new files are waiting for your approval on the Files page",
        "sum.removed_remote": "    − {path} was deleted on StudOn (local copy kept)",
        "sum.ok": "Result: OK (log: {log})",
        "sum.failed": "Result: failed (log: {log})",
        "nav.sync": "Sync",
        "nav.courses": "Courses",
        "nav.files": "Files",
        "nav.account": "Account",
        "lang.label": "Language",
        "lang.auto": "System default",
        "acc.intro": "Log in to StudOn with your FAU IdM account. Username, password and TOTP secret are stored only in this computer's system keychain.",
        "acc.username": "IdM username",
        "acc.password": "Password",
        "acc.secret": "TOTP secret",
        "acc.saved_placeholder": "Saved (leave empty to keep)",
        "acc.secret_placeholder": "Base32 string or otpauth:// link",
        "acc.save": "Save",
        "acc.saved": "Saved to the keychain.",
        "acc.test": "Test login",
        "acc.testing": "Logging in…",
        "acc.test_ok": "Login successful ✓",
        "acc.test_fail": "Login failed: {err}",
        "acc.code_title": "Current code",
        "acc.code_help": "After adding the token in IdM, enter this code there to confirm it. While you type a secret, the code for the typed value is shown.",
        "acc.copy": "Copy",
        "acc.copied": "Code copied",
        "acc.bad_secret": "The TOTP secret is not valid (it should be Base32).",
        "crs.intro": "Paste a StudOn course link to add a course. Each course can have its own download folder (for example a folder in Google Drive).",
        "crs.url_placeholder": "Paste a course link, e.g. https://www.studon.fau.de/studon/…ref_id=…",
        "crs.add": "Add course",
        "crs.adding": "Reading the course name…",
        "crs.added": "Added.",
        "crs.bad_url": "No course ID (ref_id) found in the link.",
        "crs.exists": "This course has already been added.",
        "crs.enabled": "Include in sync",
        "crs.disabled": "Paused",
        "crs.files": "Choose files",
        "crs.change_target": "Change folder",
        "crs.open": "Open",
        "crs.remove": "Remove",
        "crs.remove_confirm": "Remove this course from the list? Downloaded files are kept.",
        "crs.default_dir": "New courses download to",
        "crs.choose": "Choose…",
        "sync.now": "Sync now",
        "sync.running": "Syncing…",
        "sync.last": "Last sync: {when} · {result}",
        "sync.never": "Not synced yet",
        "sync.ok": "OK",
        "sync.failed": "failed",
        "sync.files": "files",
        "sync.pending": "to review",
        "sync.no_courses": "No courses yet. Add one on the Courses page.",
        "sched.title": "Automatic sync",
        "sched.off": "Off",
        "sched.daily": "Daily",
        "sched.interval": "Interval",
        "sched.at": "At",
        "sched.every": "Every",
        "sched.hours": "hours",
        "sched.hint": "Runs in the background through the system, the app does not need to be open. Syncs missed while the computer slept run after it wakes up.",
        "log.title": "Log",
        "log.open": "Open log folder",
        "files.intro": "Tick the files to download. Unticked files are not downloaded; downloaded files are never deleted.",
        "files.new_policy": "New files",
        "files.auto": "Download automatically",
        "files.review": "Ask me first",
        "files.only_new": "Only new files",
        "files.refresh": "Refresh list",
        "files.refreshing": "Reading the file list from StudOn (no download)…",
        "files.as_of": "List as of {when}. Double-click a file to open it",
        "files.never": "The file list has not been read yet. Click “Refresh list”.",
        "files.empty": "No files. Click “Refresh list” to read them from StudOn.",
        "files.none_new": "No new files recently.",
        "st.downloaded": "Downloaded",
        "st.edited": "Edited by you",
        "st.kept_edited": "New version · notes kept",
        "st.pending": "New · to review",
        "st.not_yet": "Next sync",
        "st.unselected": "Not downloaded",
        "st.deleted_locally": "Deleted by you",
        "st.removed_remote": "Deleted on StudOn",
        "st.alt_hint": "New StudOn version saved as: {files}",
        "notify.new": "{added} new, {changed} updated files",
        "notify.kept_edited": "{n} with a new version, your annotated copies were kept",
        "notify.failed": "Sync failed, see the log",
        "cli.usage": (
            "StudOn Sync\n\n"
            "  studon-sync                    open the app window\n"
            "  studon-sync setup              save IdM username, password and TOTP secret from the terminal\n"
            "  studon-sync code               show the current TOTP code (to confirm the token in IdM)\n"
            "  studon-sync test-login         test the login\n"
            "  studon-sync add-course URL     add a course (optionally --target FOLDER)\n"
            "  studon-sync list               list courses\n"
            "  studon-sync sync               sync all enabled courses\n"
            "  studon-sync scheduled          (called by the system scheduler) sync when it is due\n"
            "  studon-sync --lang zh|en|de|auto  set the interface language"
        ),
        "cli.code_prompt": "Enter the 6-digit code below in IdM to confirm the token, then press Enter.",
        "cli.code_line": "  Current code: {code}   {left:2d} s left  ",
        "cli.setup_intro": "Saving the login to the system keychain (service studon-sync). Press Enter to keep a saved value.",
        "cli.username": "FAU IdM username [{user}]: ",
        "cli.password": "IdM password (hidden): ",
        "cli.secret": "TOTP secret (Base32 or otpauth:// link, hidden): ",
        "cli.bad_secret": "The TOTP secret is not valid (it should be Base32). Nothing was saved.",
        "cli.empty": "Username and password must not be empty. Nothing was saved.",
        "cli.saved": "Saved.",
        "cli.no_secret": "No TOTP secret saved yet. Run setup first.",
        "cli.login_ok": "Login successful ✅",
        "cli.added": "Added: {title} → {target}",
        "cli.no_courses": "No courses yet.",
        "cli.lang_set": "Interface language set to: {lang}",
    },
    "de": {
        "app.title": "StudOn Sync",
        "err.no_credentials": "Noch keine IdM-Benutzerkennung und kein Passwort gespeichert.",
        "err.no_totp": "Die Anmeldung verlangt einen TOTP-Code, aber es ist kein TOTP-Secret gespeichert.",
        "err.unknown_page": "Unbekanntes Format der FAU-Anmeldeseite. Die Seite wurde unter {path} gespeichert",
        "err.bad_credentials": "Benutzerkennung oder Passwort abgelehnt (kein erneuter Versuch, um eine Sperre zu vermeiden). Die Seite wurde unter {path} gespeichert",
        "err.bad_otp": "TOTP-Code abgelehnt. Prüfe, ob das Token im IdM aktiviert und das Secret richtig ist. Die Seite wurde unter {path} gespeichert",
        "err.too_many_steps": "Zu viele Anmeldeschritte. Die Seite wurde unter {path} gespeichert",
        "err.busy": "Es läuft bereits eine andere Synchronisierung.",
        "err.not_logged_in": "Die Anmeldung ist durchgelaufen, aber StudOn zeigt dich weiterhin als abgemeldet.",
        "err.course_login_failed": "Anmeldung fehlgeschlagen, dieser Kurs wurde diesmal nicht synchronisiert: {err}",
        "err.course_incomplete": "Dieser Kurs wurde diesmal nicht vollständig synchronisiert (siehe Protokoll).",
        "err.no_courses": "Noch keine aktiven Kurse.",
        "log.reuse_login": "[studon-sync] Bestehende Anmeldung wird weiterverwendet",
        "log.new_login": "[studon-sync] Neue Anmeldung über FAU SSO + TOTP",
        "sum.header": "=== Zusammenfassung ===",
        "sum.course": "{title} → {target}",
        "sum.counts": "  {added} neu, {changed} aktualisiert",
        "sum.errors": "  {n} Fehler:",
        "sum.kept_edited": "    ★ {path} hat eine neue Version auf StudOn. Deine bearbeitete Fassung wurde behalten; die neue Version wurde als {alt} gespeichert",
        "sum.pending": "  {n} neue Dateien warten auf der Seite „Dateien“ auf deine Bestätigung",
        "sum.removed_remote": "    − {path} wurde auf StudOn gelöscht (lokale Kopie bleibt)",
        "sum.ok": "Ergebnis: erfolgreich (Protokoll: {log})",
        "sum.failed": "Ergebnis: fehlgeschlagen (Protokoll: {log})",
        "nav.sync": "Synchronisieren",
        "nav.courses": "Kurse",
        "nav.files": "Dateien",
        "nav.account": "Konto",
        "lang.label": "Sprache",
        "lang.auto": "Systemsprache",
        "acc.intro": "Mit deiner FAU-IdM-Kennung bei StudOn anmelden. Benutzerkennung, Passwort und TOTP-Secret werden nur im Schlüsselbund dieses Computers gespeichert.",
        "acc.username": "IdM-Benutzerkennung",
        "acc.password": "Passwort",
        "acc.secret": "TOTP-Secret",
        "acc.saved_placeholder": "Gespeichert (leer lassen, um es zu behalten)",
        "acc.secret_placeholder": "Base32-Zeichenkette oder otpauth://-Link",
        "acc.save": "Speichern",
        "acc.saved": "Im Schlüsselbund gespeichert.",
        "acc.test": "Anmeldung testen",
        "acc.testing": "Anmeldung läuft…",
        "acc.test_ok": "Anmeldung erfolgreich ✓",
        "acc.test_fail": "Anmeldung fehlgeschlagen: {err}",
        "acc.code_title": "Aktueller Code",
        "acc.code_help": "Nachdem du das Token im IdM hinzugefügt hast, gib diesen Code dort zur Bestätigung ein. Während du ein Secret eingibst, wird der Code für den eingegebenen Wert angezeigt.",
        "acc.copy": "Kopieren",
        "acc.copied": "Code kopiert",
        "acc.bad_secret": "Das TOTP-Secret ist ungültig (es muss Base32 sein).",
        "crs.intro": "Füge einen StudOn-Kurslink ein, um einen Kurs hinzuzufügen. Jeder Kurs kann einen eigenen Download-Ordner haben (z. B. einen Ordner in Google Drive).",
        "crs.url_placeholder": "Kurslink einfügen, z. B. https://www.studon.fau.de/studon/…ref_id=…",
        "crs.add": "Kurs hinzufügen",
        "crs.adding": "Kursname wird gelesen…",
        "crs.added": "Hinzugefügt.",
        "crs.bad_url": "Im Link wurde keine Kursnummer (ref_id) gefunden.",
        "crs.exists": "Dieser Kurs wurde bereits hinzugefügt.",
        "crs.enabled": "Synchronisieren",
        "crs.disabled": "Pausiert",
        "crs.files": "Dateien auswählen",
        "crs.change_target": "Ordner ändern",
        "crs.open": "Öffnen",
        "crs.remove": "Entfernen",
        "crs.remove_confirm": "Diesen Kurs aus der Liste entfernen? Heruntergeladene Dateien bleiben erhalten.",
        "crs.default_dir": "Neue Kurse werden gespeichert in",
        "crs.choose": "Auswählen…",
        "sync.now": "Jetzt synchronisieren",
        "sync.running": "Synchronisiert…",
        "sync.last": "Letzte Synchronisierung: {when} · {result}",
        "sync.never": "Noch nie synchronisiert",
        "sync.ok": "erfolgreich",
        "sync.failed": "fehlgeschlagen",
        "sync.files": "Dateien",
        "sync.pending": "zu bestätigen",
        "sync.no_courses": "Noch keine Kurse. Füge auf der Seite „Kurse“ einen hinzu.",
        "sched.title": "Automatische Synchronisierung",
        "sched.off": "Aus",
        "sched.daily": "Täglich",
        "sched.interval": "Intervall",
        "sched.at": "Um",
        "sched.every": "Alle",
        "sched.hours": "Stunden",
        "sched.hint": "Läuft im Hintergrund über das System, die App muss nicht geöffnet sein. Im Ruhezustand verpasste Synchronisierungen werden nach dem Aufwachen nachgeholt.",
        "log.title": "Protokoll",
        "log.open": "Protokollordner öffnen",
        "files.intro": "Wähle die Dateien aus, die heruntergeladen werden sollen. Abgewählte Dateien werden nicht heruntergeladen; bereits heruntergeladene Dateien werden nie gelöscht.",
        "files.new_policy": "Neue Dateien",
        "files.auto": "Automatisch laden",
        "files.review": "Erst fragen",
        "files.only_new": "Nur neue Dateien",
        "files.refresh": "Liste aktualisieren",
        "files.refreshing": "Dateiliste wird von StudOn gelesen (ohne Download)…",
        "files.as_of": "Stand der Liste: {when}. Doppelklick öffnet eine Datei",
        "files.never": "Die Dateiliste wurde noch nicht gelesen. Klicke auf „Liste aktualisieren“.",
        "files.empty": "Keine Dateien. Klicke auf „Liste aktualisieren“, um sie von StudOn zu lesen.",
        "files.none_new": "In letzter Zeit keine neuen Dateien.",
        "st.downloaded": "Heruntergeladen",
        "st.edited": "Von dir bearbeitet",
        "st.kept_edited": "Neue Version · Notizen behalten",
        "st.pending": "Neu · zu bestätigen",
        "st.not_yet": "Nächste Synchronisierung",
        "st.unselected": "Nicht laden",
        "st.deleted_locally": "Von dir gelöscht",
        "st.removed_remote": "Auf StudOn gelöscht",
        "st.alt_hint": "Neue StudOn-Version gespeichert als: {files}",
        "notify.new": "{added} neue, {changed} aktualisierte Dateien",
        "notify.kept_edited": "{n} mit neuer Version, deine bearbeiteten Fassungen wurden behalten",
        "notify.failed": "Synchronisierung fehlgeschlagen, siehe Protokoll",
        "cli.usage": (
            "StudOn Sync\n\n"
            "  studon-sync                    App-Fenster öffnen\n"
            "  studon-sync setup              IdM-Kennung, Passwort und TOTP-Secret im Terminal speichern\n"
            "  studon-sync code               aktuellen TOTP-Code anzeigen (zum Bestätigen des Tokens im IdM)\n"
            "  studon-sync test-login         Anmeldung testen\n"
            "  studon-sync add-course URL     Kurs hinzufügen (optional --target ORDNER)\n"
            "  studon-sync list               Kurse auflisten\n"
            "  studon-sync sync               alle aktiven Kurse synchronisieren\n"
            "  studon-sync scheduled          (vom System-Zeitplaner aufgerufen) synchronisiert, wenn es Zeit ist\n"
            "  studon-sync --lang zh|en|de|auto  Sprache der Oberfläche festlegen"
        ),
        "cli.code_prompt": "Gib den 6-stelligen Code unten im IdM ein, um das Token zu bestätigen, und drücke dann Enter.",
        "cli.code_line": "  Aktueller Code: {code}   noch {left:2d} s  ",
        "cli.setup_intro": "Anmeldedaten werden im Schlüsselbund gespeichert (Dienst studon-sync). Enter = gespeicherten Wert behalten.",
        "cli.username": "FAU-IdM-Benutzerkennung [{user}]: ",
        "cli.password": "IdM-Passwort (verborgen): ",
        "cli.secret": "TOTP-Secret (Base32 oder otpauth://-Link, verborgen): ",
        "cli.bad_secret": "Das TOTP-Secret ist ungültig (es muss Base32 sein). Es wurde nichts gespeichert.",
        "cli.empty": "Benutzerkennung und Passwort dürfen nicht leer sein. Es wurde nichts gespeichert.",
        "cli.saved": "Gespeichert.",
        "cli.no_secret": "Noch kein TOTP-Secret gespeichert. Führe zuerst setup aus.",
        "cli.login_ok": "Anmeldung erfolgreich ✅",
        "cli.added": "Hinzugefügt: {title} → {target}",
        "cli.no_courses": "Noch keine Kurse.",
        "cli.lang_set": "Sprache der Oberfläche: {lang}",
    },
}

_lang: Optional[str] = None  # resolved code; None = not set yet (read from settings on first use)


def _match(tag: Optional[str]) -> Optional[str]:
    """'de_DE.UTF-8', 'zh-Hans-CN', 'en-US' -> 'de', 'zh', 'en'; None if we have no such language."""
    if not tag:
        return None
    code = tag.replace("_", "-").split("-")[0].split(".")[0].lower()
    return code if code in STRINGS else None


def system_language() -> str:
    """The first of the user's preferred system languages that we have, else FALLBACK."""
    candidates: list[str] = []
    if sys.platform == "darwin":
        # A GUI app gets no LANG from launchd, so ask the system for the preferred languages.
        try:
            out = subprocess.run(
                ["defaults", "read", "-g", "AppleLanguages"], capture_output=True, text=True, timeout=3
            ).stdout
            candidates += [s.strip().strip('",') for s in out.splitlines() if s.strip() not in ("(", ")")]
        except (OSError, subprocess.SubprocessError):
            pass
    elif sys.platform == "win32":
        try:
            import ctypes

            lcid = ctypes.windll.kernel32.GetUserDefaultUILanguage()  # type: ignore[attr-defined]
            candidates.append(locale.windows_locale.get(lcid, ""))
        except (OSError, AttributeError):
            pass
    for var in ("LC_ALL", "LC_MESSAGES", "LANG", "LANGUAGE"):
        candidates += (os.environ.get(var) or "").split(":")
    try:
        candidates.append(locale.getlocale()[0] or "")
    except ValueError:
        pass
    for tag in candidates:
        if tag and tag not in ("C", "POSIX") and (code := _match(tag)):
            return code
    return FALLBACK


def resolve(setting: Optional[str]) -> str:
    """Setting value ("auto" or a code) -> language code to use."""
    return setting if setting in STRINGS else system_language()


def set_language(setting: Optional[str]) -> None:
    global _lang
    _lang = resolve(setting)


def current() -> str:
    global _lang
    if _lang is None:  # e.g. the PFERD subprocess: follow the saved setting
        try:
            from .core import settings

            set_language(settings.load().language)
        except Exception:
            set_language("auto")
    return _lang  # type: ignore[return-value]


def strings(lang: Optional[str] = None) -> dict[str, str]:
    """All strings of a language, missing keys filled in from English."""
    return {**STRINGS[FALLBACK], **STRINGS[lang or current()]}


def t(key: str, **kwargs: object) -> str:
    lang = current()
    text = STRINGS[lang].get(key) or STRINGS[FALLBACK].get(key, key)
    return text.format(**kwargs) if kwargs else text
