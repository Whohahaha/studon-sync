# StudOn Sync

**English** | [中文](README.zh-CN.md)

> **Unofficial tool.** This project is not affiliated with or endorsed by FAU, RRZE or StudOn.
> Please read the [disclaimer and rules of use](#disclaimer-and-rules-of-use) before using it.

A desktop app that downloads the files of your FAU StudOn courses into a folder on your own computer
(which can be a Google Drive / OneDrive / Dropbox folder), keeps StudOn's folder structure, and can update automatically every day.

- Logs in with your FAU IdM account (FAU SSO + TOTP multi-factor; the 6-digit code is generated for you)
- Username, password and TOTP secret are stored **only on your computer**, in the system keychain (macOS Keychain / Windows Credential Manager). Nothing is uploaded anywhere.
- Several courses, each with its own target folder
- Incremental: only new or changed files are downloaded; **local files are never deleted**
- **Protects your notes**: when a file changes on StudOn and you have not edited your copy, it is replaced (the old version goes to a hidden `.studon-sync/versions/` folder). If you have edited it (e.g. annotated a PDF), it is never overwritten: the new version is saved next to it as `name (StudOn date).pdf` and you get a notice.
- Files you delete yourself are not downloaded again; files deleted on StudOn are kept locally and marked
- A "Files" page lets you pick which files and folders to download, and whether new files download automatically or wait for you
- Files only (no videos, forums, assignments or links); requests are rate-limited
- Download engine: [PFERD](https://github.com/Garmelon/PFERD)

## Install

- **macOS**: download [`StudOn-Sync-macOS.zip`](https://github.com/Whohahaha/studon-sync/releases/latest/download/StudOn-Sync-macOS.zip) from [Releases](https://github.com/Whohahaha/studon-sync/releases) (Apple Silicon only), unzip it and move `StudOn Sync.app` to Applications.
  The app is not notarized by Apple, so the first time right-click it → Open (or click "Open Anyway" in System Settings → Privacy & Security).
- **From source** (macOS / Windows / Linux, Python 3.11+):
  ```bash
  git clone https://github.com/Whohahaha/studon-sync.git
  cd studon-sync
  python3 -m venv .venv
  .venv/bin/pip install -e .        # Windows: .venv\Scripts\pip install -e .
  .venv/bin/studon-sync             # opens the app
  ```
  The app is mainly used on macOS; Windows and Linux have only been tried during development.

## Usage

The app has four pages:

1. **Account**: enter your IdM username, password and TOTP secret, then Save.
   - The TOTP secret is the Base32 string (or `otpauth://` link) shown next to the QR code when you add a "software token / authenticator app" in the IdM portal.
   - IdM asks for one code to confirm the new token: the Account page shows the current 6-digit code live.
   - Click "Test login" to check.
2. **Courses**: paste a StudOn course link and click "Add course"; the name is read automatically. Each course can get its own folder, be paused or removed.
3. **Files**: all files in StudOn's folder structure, with checkboxes and status labels (downloaded / edited by you / new version, notes kept / new, waiting / deleted on StudOn). "Refresh list" reads the listing without downloading.
4. **Sync**: "Sync now", or schedule a daily time or every N hours. Scheduled syncs run in the background through the OS (macOS LaunchAgent / Windows Task Scheduler) without the app open, with a notification for new files or failures.

Language: English, German and Chinese. By default the app follows the system language; change it with the language menu at the bottom of the sidebar (or `studon-sync --lang en|de|zh|auto`). The choice also applies to notifications and sync logs.

### Command line

```bash
studon-sync setup              # store username/password/TOTP secret in the terminal
studon-sync code               # show the current TOTP code
studon-sync test-login
studon-sync add-course URL [--target FOLDER]
studon-sync list
studon-sync sync               # sync all enabled courses
studon-sync scheduled          # used by the OS scheduler: syncs only when due
studon-sync --lang de          # interface language: zh | en | de | auto (follow the system)
```

### Where data is stored

| What | macOS | Windows |
|---|---|---|
| Settings (courses, folders, schedule) | `~/Library/Application Support/StudOn Sync/settings.json` | `%LOCALAPPDATA%\StudOn Sync\` |
| Per-course file state, old versions | hidden `.studon-sync/` in each course folder | same |
| Logs | `~/Library/Logs/StudOn Sync/` | `%LOCALAPPDATA%\StudOn Sync\Logs\` |
| Credentials | one keychain item: service `studon-sync`, account `credentials` | Credential Manager, `studon-sync` |

If the FAU login page changes, a failed login saves the page to the log folder (`login-debug-*.html`). These pages can contain your username, so check them before sharing them in an issue.

## Disclaimer and rules of use

- This is a personal student project, **not official**, and has nothing to do with FAU / RRZE / StudOn. It is provided "as is" under the MIT license, without any warranty. Use it at your own risk.
- **Use only your own IdM account, on your own computer.** FAU's [IT usage rules](https://www.idm.fau.de/bedingungen) forbid giving your credentials to others or storing them on devices other people can use, and you are responsible for everything done with your account. Do not store other people's accounts, and do not turn this tool into a web service that logs in on someone's behalf.
- **Do not redistribute course material.** Course files are copyrighted (§60a UrhG) and meant only for the teachers and students of that course. Do not share your download folder publicly or upload it to GitHub or similar.
- **Be gentle with the server.** By default files are downloaded one at a time with a 1-second delay between requests. A few syncs per day are plenty; please do not schedule it every few minutes. The IT rules require resources to be used sparingly.
- Credentials stay in your local keychain. Keeping the password and the TOTP secret on the same computer weakens two-factor protection, so turn on disk encryption (FileVault / BitLocker) and a screen lock.
- Breaking FAU's rules can get your account suspended. If in doubt, ask RRZE first. StudOn's own terms of use are linked in the StudOn page footer after login.

## Development

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[build]"
.venv/bin/studon-sync                         # run
.venv/bin/python -m studon_sync.ui.devserver  # UI in a browser (http://127.0.0.1:8765)
.venv/bin/python -m pytest                    # tests
packaging/build_mac.sh                        # build and sign dist/StudOn Sync.app
```

`build_mac.sh` signs with a self-signed "StudOn Sync Local Signing" certificate (created on first run in a separate keychain under `~/Library/Application Support/StudOn Sync/signing/`), so rebuilds keep the same signature and macOS Keychain "Always Allow" keeps working. For a notarized build set `SIGN_IDENTITY="Developer ID Application: …"` and notarize with `xcrun notarytool`.

Code layout: `src/studon_sync/core/` (login, settings, sync, file protection; no UI code), `ui/` (HTML/CSS/JS UI and its Python API), `system.py` (OS scheduler, notifications), `__main__.py` (CLI). UI strings live in `i18n.py`; to add a language, add one dict of translations there and its name in `LANGUAGES`.

## License

[MIT](LICENSE). PFERD is also MIT-licensed.
