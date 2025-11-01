import argparse
import curses
import io
import locale
import os
import re
import shlex
import subprocess
import sys

TYPES = ["feat", "fix", "chore"]


def ensure_utf8_stdio():
    if sys.flags.utf8_mode:
        return

    try:
        if hasattr(sys.stdin, "buffer"):
            sys.stdin = io.TextIOWrapper(sys.stdin.buffer, encoding="utf-8", errors="replace", newline=None)
        if hasattr(sys.stdout, "buffer"):
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", newline=None)
        if hasattr(sys.stderr, "buffer"):
            sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace", newline=None)
    except Exception:
        pass


def to_kebab(text: str) -> str:
    s = text.lower().strip()
    s = re.sub(r"\s+", "-", s)
    s = re.sub(r"[^\w\-]+", "-", s)
    s = re.sub(r"-{2,}", "-", s).strip("-")
    return s or "change"


def git_cr():
    try:
        locale.setlocale(locale.LC_ALL, "")
    except Exception:
        pass

    parser = argparse.ArgumentParser(
        description="CR: тип -> сообщение -> ветка -> пуш (авто-MR для GitLab)."
    )
    parser.add_argument("--remote", default="origin", help="remote (default: origin)")
    parser.add_argument("--base", default="main", help="base branch (default: main)")
    parser.add_argument("--name", default="ad-user", help="git user.name (local)")
    parser.add_argument("--email", default="ad.dev@arbat.dev", help="git user.email (local)")
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="подробный вывод команд"
    )
    args = parser.parse_args()
    try:
        os.chdir(os.getcwd())
    except Exception:
        pass
    def say_and_run(cmd, check=True, capture=False):
        if args.verbose:
            print(f"$ {cmd}")
        try:
            res = subprocess.run(
                cmd,
                shell=True,
                check=check,
                stdout=(subprocess.PIPE if capture else None),
                stderr=(subprocess.STDOUT if capture else None),
                text=True,
            )
            if args.verbose and capture and res.stdout:
                # stdout уже в UTF-8 из ensure_utf8_stdio(); печатаем как есть
                print(res.stdout.strip())
            return res.returncode, (res.stdout.strip() if res.stdout else "")
        except subprocess.CalledProcessError as e:
            out = (getattr(e, "stdout", "") or "").strip()
            if out:
                print(out)
            else:
                print(f"error: {e}")
            return e.returncode, out

    # текущая ветка
    _, current = say_and_run("git rev-parse --abbrev-ref HEAD", check=False, capture=True)
    original_branch = (current or "").strip()

    # локальные конфиги
    say_and_run(f"git config --local user.name {shlex.quote(args.name)}", check=True)
    say_and_run(f"git config --local user.email {shlex.quote(args.email)}", check=True)

    # выбор типа
    def select_type_curses(options):
        def _inner(stdscr):
            curses.curs_set(0)
            try:
                curses.use_default_colors()
            except Exception:
                pass
            idx = 0
            while True:
                stdscr.erase()
                stdscr.addstr(0, 0, "Тип (↑/↓, Enter):")
                for i, opt in enumerate(options):
                    if i == idx:
                        stdscr.addstr(2 + i, 0, f"> {opt}", curses.A_REVERSE)
                    else:
                        stdscr.addstr(2 + i, 0, f"  {opt}")
                key = stdscr.getch()
                if key in (curses.KEY_UP, ord("k")):
                    idx = (idx - 1) % len(options)
                elif key in (curses.KEY_DOWN, ord("j")):
                    idx = (idx + 1) % len(options)
                elif key in (curses.KEY_ENTER, 10, 13):
                    return options[idx]
        return curses.wrapper(_inner)

    def select_type_fallback(options):
        while True:
            v = input(f"type [{'/'.join(options)}]: ").strip().lower()
            if v in options:
                return v
            print("->", ", ".join(options))

    use_tty = sys.stdin.isatty() and sys.stdout.isatty()
    if use_tty:
        try:
            ctype = select_type_curses(TYPES)
        except Exception:
            ctype = select_type_fallback(TYPES)
    else:
        ctype = select_type_fallback(TYPES)

    # сообщение + короткое подтверждение
    while True:
        raw_subject = input("msg: ").strip()
        kebab = to_kebab(raw_subject)
        commit_msg = f"{ctype}:{kebab}"
        ok = input(f"ok '{commit_msg}'? [Y/n]: ").strip().lower()
        if ok in ("", "y", "yes", "д", "да"):
            break

    # ветка по сообщению
    branch_name = f"{ctype}/{kebab}"

    # коммит
    _, status = say_and_run("git status --porcelain", check=False, capture=True)
    if (status or "").strip():
        say_and_run("git add -A", check=True)
        say_and_run("git rm --cached git_cr.py", check=False)
        say_and_run(f"git commit -m {shlex.quote(commit_msg)}", check=True)
    else:
        say_and_run(f"git commit --allow-empty -m {shlex.quote(commit_msg)}", check=True)

    # ветка
    say_and_run(f"git checkout -b {shlex.quote(branch_name)}", check=True)

    # push
    push_cmd = f"git push -u {shlex.quote(args.remote)} {shlex.quote(branch_name)}"
    _, remote_url = say_and_run(
        f"git remote get-url {shlex.quote(args.remote)}", check=False, capture=True
    )
    if "gitlab" in (remote_url or "").lower():
        push_cmd += " -o merge_request.create"
    say_and_run(push_cmd, check=True)

    # вернуться ли назад
    back = input(f"back to '{original_branch}'? [Y/n]: ").strip().lower()
    if back in ("", "y", "yes", "д", "да"):
        say_and_run(f"git checkout {shlex.quote(original_branch)}", check=True)

    # финал
    print("done.")


if __name__ == "__main__":
    ensure_utf8_stdio()
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")

    git_cr()
