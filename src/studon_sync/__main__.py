"""
StudOn 同步

  studon-sync                    打开图形界面
  studon-sync setup              在终端里保存 IdM 账号、密码、TOTP secret
  studon-sync code               显示当前 TOTP 验证码（在 IdM 里确认令牌用）
  studon-sync test-login         测试登录
  studon-sync add-course URL     添加课程（可加 --target 文件夹）
  studon-sync list               列出课程
  studon-sync sync               同步所有启用的课程
"""

import argparse
import getpass
import sys
import threading

from .i18n import set_language


def _show_live_code(secret: str | None = None) -> None:
    """Shows the current TOTP code with a countdown until Enter. Never prints the secret."""
    from .core import credentials

    done = threading.Event()
    threading.Thread(target=lambda: (sys.stdin.readline(), done.set()), daemon=True).start()
    print("把下面的 6 位验证码填回 IdM 确认令牌；完成后按回车。")
    while not done.is_set():
        code, left = credentials.current_code(secret)
        print(f"\r  当前验证码：{code}   剩余 {left:2d} 秒  ", end="", flush=True)
        done.wait(1)
    print()


def cmd_setup(args: argparse.Namespace) -> int:
    from .core import credentials

    print("保存登录信息到系统钥匙串（服务名 studon-sync）。直接回车 = 保留已保存的值。")
    username = input(f"FAU IdM 用户名 [{credentials.stored_username()}]：").strip()
    password = getpass.getpass("IdM 密码（输入时不显示）：")
    secret = getpass.getpass("TOTP secret（Base32 或 otpauth:// 链接，输入时不显示）：").strip()
    if secret:
        try:
            secret = credentials.normalize_secret(secret)
        except ValueError:
            print("TOTP secret 格式不对（应为 Base32），未保存任何内容。")
            return 1
    if not (username or credentials.stored_username()) or not (password or credentials.has_password()):
        print("用户名和密码不能为空，未保存任何内容。")
        return 1
    credentials.save(username or None, password or None, secret or None)
    print("已保存。")
    if secret:
        _show_live_code()
    return 0


def cmd_code(args: argparse.Namespace) -> int:
    from .core import credentials

    if not credentials.has_totp_secret():
        print("还没有保存 TOTP secret，请先运行 setup。")
        return 1
    _show_live_code()
    return 0


def cmd_test_login(args: argparse.Namespace) -> int:
    from .core import runner
    from .core.fau_login import LoginError

    try:
        ok = runner.test_login()
    except LoginError as e:
        print(f"登录失败：{e}")
        return 1
    print("登录成功 ✅" if ok else "登录流程走完了，但 StudOn 仍显示未登录 ❌")
    return 0 if ok else 1


def cmd_add_course(args: argparse.Namespace) -> int:
    from .core import courses, settings
    from .core.settings import Course

    ref_id = courses.parse_ref_id(args.url)
    if not ref_id:
        print("没有在链接里找到课程编号（ref_id）。")
        return 1
    s = settings.load()
    if s.course(ref_id):
        print("这个课程已经添加过了。")
        return 1
    title = args.title or courses.fetch_title(ref_id) or f"StudOn-{ref_id}"
    target = args.target or courses.default_target(title, s.default_target_dir, {c.target_dir for c in s.courses})
    s.courses.append(Course(ref_id=ref_id, title=title, target_dir=target))
    settings.save(s)
    print(f"已添加：{title} → {target}")
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    from .core import settings

    s = settings.load()
    if not s.courses:
        print("还没有课程。")
    for c in s.courses:
        print(f"[{'x' if c.enabled else ' '}] {c.ref_id}  {c.title}  →  {c.target_dir}")
    return 0


def cmd_sync(args: argparse.Namespace) -> int:
    from .core import runner

    result = runner.run_sync(print)
    if result.error:
        print(result.error)
    return 0 if result.ok else 1


def cmd_gui(args: argparse.Namespace) -> int:
    from .gui.app import run

    return run(background="--background" in sys.argv)


def main() -> int:
    if len(sys.argv) >= 2 and sys.argv[1] == "_pferd":  # internal: PFERD subprocess
        from .core.runner import pferd_main

        pferd_main(sys.argv[2])
        return 0

    from .core import settings

    set_language(settings.load().language)

    parser = argparse.ArgumentParser(prog="studon-sync", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd")
    sub.add_parser("gui").add_argument("--background", action="store_true")
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

    commands = {
        None: cmd_gui,
        "gui": cmd_gui,
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
