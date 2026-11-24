"""Command line and app entry point. Usage text: i18n key "cli.usage"."""

import argparse
import getpass
import sys
import threading

from .i18n import set_language, t


def _show_live_code(secret: str | None = None) -> None:
    """Shows the current TOTP code with a countdown until Enter. Never prints the secret."""
    from .core import credentials

    done = threading.Event()
    threading.Thread(target=lambda: (sys.stdin.readline(), done.set()), daemon=True).start()
    print(t("cli.code_prompt"))
    while not done.is_set():
        code, left = credentials.current_code(secret)
        print("\r" + t("cli.code_line", code=code, left=left), end="", flush=True)
        done.wait(1)
    print()


def cmd_setup(args: argparse.Namespace) -> int:
    from .core import credentials

    print(t("cli.setup_intro"))
    username = input(t("cli.username", user=credentials.stored_username() or "")).strip()
    password = getpass.getpass(t("cli.password"))
    secret = getpass.getpass(t("cli.secret")).strip()
    if secret:
        try:
            secret = credentials.normalize_secret(secret)
        except ValueError:
            print(t("cli.bad_secret"))
            return 1
    if not (username or credentials.stored_username()) or not (password or credentials.has_password()):
        print(t("cli.empty"))
        return 1
    credentials.save(username or None, password or None, secret or None)
    print(t("cli.saved"))
    if secret:
        _show_live_code()
    return 0


def cmd_code(args: argparse.Namespace) -> int:
    from .core import credentials

    if not credentials.has_totp_secret():
        print(t("cli.no_secret"))
        return 1
    _show_live_code()
    return 0


def cmd_test_login(args: argparse.Namespace) -> int:
    from .core import runner
    from .core.fau_login import LoginError

    try:
        ok = runner.test_login()
    except LoginError as e:
        print(t("acc.test_fail", err=e))
        return 1
    print(t("cli.login_ok") if ok else t("err.not_logged_in") + " ❌")
    return 0 if ok else 1


def cmd_add_course(args: argparse.Namespace) -> int:
    from .core import courses, settings
    from .core.settings import Course

    ref_id = courses.parse_ref_id(args.url)
    if not ref_id:
        print(t("crs.bad_url"))
        return 1
    s = settings.load()
    if s.course(ref_id):
        print(t("crs.exists"))
        return 1
    title = args.title or courses.fetch_title(ref_id) or f"StudOn-{ref_id}"
    target = args.target or courses.default_target(title, s.default_target_dir, {c.target_dir for c in s.courses})
    s.courses.append(Course(ref_id=ref_id, title=title, target_dir=target))
    settings.save(s)
    print(t("cli.added", title=title, target=target))
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    from .core import settings

    s = settings.load()
    if not s.courses:
        print(t("cli.no_courses"))
    for c in s.courses:
        print(f"[{'x' if c.enabled else ' '}] {c.ref_id}  {c.title}  →  {c.target_dir}")
    return 0


def cmd_sync(args: argparse.Namespace) -> int:
    from .core import runner

    result = runner.run_sync(print)
    if result.error:
        print(result.error)
    return 0 if result.ok else 1


def cmd_ui(args: argparse.Namespace) -> int:
    from .ui.app import run

    return run()


def cmd_scheduled(args: argparse.Namespace) -> int:
    """Called by the OS scheduler every 15 minutes: syncs if the configured time has come."""
    from . import system
    from .core import runner, schedule, settings

    if not schedule.is_due(settings.load()) or runner.is_running():
        return 0
    result = runner.run_sync()
    if not result.ok:
        system.notify(t("app.title"), t("notify.failed"))
    elif result.added or result.changed:
        text = t("notify.new", added=result.added, changed=result.changed)
        if result.kept_edited:
            text += " · " + t("notify.kept_edited", n=result.kept_edited)
        system.notify(t("app.title"), text)
    return 0 if result.ok else 1


def main() -> int:
    if len(sys.argv) >= 2 and sys.argv[1] == "_pferd":  # internal: PFERD subprocess
        from .core.runner import pferd_main

        pferd_main(sys.argv[2])
        return 0

    from . import i18n
    from .core import settings

    set_language(settings.load().language)

    parser = argparse.ArgumentParser(prog="studon-sync", description=t("cli.usage"), formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--lang", choices=["auto", *i18n.LANGUAGES], help=argparse.SUPPRESS)
    sub = parser.add_subparsers(dest="cmd")
    sub.add_parser("ui")
    sub.add_parser("scheduled")
    sub.add_parser("setup")
    sub.add_parser("code")
    sub.add_parser("test-login")
    p = sub.add_parser("add-course")
    p.add_argument("url")
    p.add_argument("--target")
    p.add_argument("--title")
    sub.add_parser("list")
    sub.add_parser("sync")
    args = parser.parse_args()

    if args.lang:  # saved, so the app, notifications and scheduled syncs use it too
        s = settings.load()
        s.language = args.lang
        settings.save(s)
        set_language(args.lang)
        print(t("cli.lang_set", lang=i18n.LANGUAGES.get(args.lang, "auto")))
        if args.cmd is None:
            return 0

    commands = {
        None: cmd_ui,
        "ui": cmd_ui,
        "scheduled": cmd_scheduled,
        "setup": cmd_setup,
        "code": cmd_code,
        "test-login": cmd_test_login,
        "add-course": cmd_add_course,
        "list": cmd_list,
        "sync": cmd_sync,
    }
    return commands[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
