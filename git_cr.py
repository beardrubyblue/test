#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import curses
import re
import shlex
import subprocess
import sys

TYPES = ["feat", "fix", "chore"]  # только первые три, как просил

def git_cr():
    parser = argparse.ArgumentParser(description="Удобный CR: стрелками выбираешь тип -> сообщение -> ветка -> пуш (+MR).")
    parser.add_argument("--remote", default="origin", help="Имя удалённого (по умолчанию origin).")
    parser.add_argument("--base", default="main", help="От какой ветки ответвляться (по умолчанию main).")
    parser.add_argument("--yes", action="store_true", help="Автоподтверждение всех шагов.")
    parser.add_argument("--mr", action="store_true", help="Добавить -о merge_request.create (для GitLab).")
    parser.add_argument("--name", default="ad-user", help="Локальный user.name (по умолчанию ad-user).")
    parser.add_argument("--email", default="ad.dev@arbat.dev", help="Локальный user.email (по умолчанию ad.dev@arbat.dev).")
    args = parser.parse_args()

    # --- helper: запуск команды с выводом (рус. комментарии) ---
    def say_and_run(cmd, check=True, capture=False):
        print(f"\n$ {cmd}")
        try:
            res = subprocess.run(
                cmd, shell=True, check=check,
                stdout=(subprocess.PIPE if capture else None),
                stderr=(subprocess.STDOUT if capture else None),
                text=True
            )
            if capture and res.stdout:
                print(res.stdout.strip())
            return res.returncode, (res.stdout.strip() if res.stdout else "")
        except subprocess.CalledProcessError as e:
            out = getattr(e, "stdout", "") or ""
            if out:
                print(out.strip())
            return e.returncode, out.strip()

    # --- helper: подтверждение шага ---
    def confirm(prompt, default_yes=True):
        if args.yes:
            print(f"{prompt} [auto-yes]")
            return True
        suffix = "Y/n" if default_yes else "y/N"
        ans = input(f"{prompt} ({suffix}): ").strip().lower()
        if ans == "":
            return default_yes
        return ans in ("y", "yes", "д", "да")

    # --- стрелочное меню через curses ---
    def select_type_curses(options):
        def _inner(stdscr):
            curses.curs_set(0)  # скрыть курсор
            idx = 0
            while True:
                stdscr.erase()
                stdscr.addstr(0, 0, "Выбери тип коммита (↑/↓, Enter):")
                for i, opt in enumerate(options):
                    if i == idx:
                        stdscr.addstr(2 + i, 0, f"> {opt}", curses.A_REVERSE)
                    else:
                        stdscr.addstr(2 + i, 0, f"  {opt}")
                key = stdscr.getch()
                if key in (curses.KEY_UP, ord('k')):
                    idx = (idx - 1) % len(options)
                elif key in (curses.KEY_DOWN, ord('j')):
                    idx = (idx + 1) % len(options)
                elif key in (curses.KEY_ENTER, 10, 13):
                    return options[idx]
        return curses.wrapper(_inner)

    # --- fallback, если curses недоступен/нет TTY ---
    def select_type_fallback(options):
        while True:
            v = input(f"Тип коммита [{'/'.join(options)}]: ").strip().lower()
            if v in options:
                return v
            print("⛔ Введи ровно один из:", ", ".join(options))

    code, current = say_and_run("git rev-parse --abbrev-ref HEAD", check=False, capture=True)
    print(f"➡️ Текущая ветка: {current}")

    # 1) Локальные конфиги (user.name/email)
    if confirm(f"Поставить локально user.name = '{args.name}'?", True):
        say_and_run(f"git config --local user.name {shlex.quote(args.name)}", check=True)
    if confirm(f"Поставить локально user.email = '{args.email}'?", True):
        say_and_run(f"git config --local user.email {shlex.quote(args.email)}", check=True)

    # 2) Выбор типа коммита стрелками
    print()
    if sys.stdin.isatty() and sys.stdout.isatty():
        try:
            ctype = select_type_curses(TYPES)
        except Exception:
            # если curses не сработал (например, IDE) — fallback
            ctype = select_type_fallback(TYPES)
    else:
        ctype = select_type_fallback(TYPES)
    print(f"Выбран тип: {ctype}")



    # 5) короткое сообщение (subject)
    subject = ""
    while not subject:
        subject = input("Cообщение: ").strip()

    # 6) формируем conventional commit сообщение
    commit_msg = f"{ctype}:{subject}"
    print(f"\n📝 Commit message: {commit_msg}")

    # 7) формируем имя ветки: type/slug(subject)
    slug = subject.lower()
    slug = re.sub(r"[^\w\-]+", "-", slug)
    slug = re.sub(r"-{2,}", "-", slug).strip("-")
    if not slug:
        slug = "change"
    branch_name = f"{ctype}/{slug}"
    print(f"🧭 Branch: {branch_name}")

    # 8) делаем коммит (или пустой)
    code, status = say_and_run("git status --porcelain", check=False, capture=True)
    dirty = bool(status.strip())
    if dirty:
        if confirm("Добавить все изменения и сделать коммит?", True):
            say_and_run("git add -A", check=True)
            say_and_run(f'git commit -m {shlex.quote(commit_msg)}', check=True)
    else:
        if confirm("Изменений нет. Создать ПУСТОЙ коммит?", True):
            say_and_run(f'git commit --allow-empty -m {shlex.quote(commit_msg)}', check=True)

    # 9) обновляем базовую ветку и создаём новую
    if confirm(f"Обновить базовую ветку '{args.base}' (fetch + rebase)?", True):
        say_and_run(f"git fetch {shlex.quote(args.remote)}", check=False)
        say_and_run(f"git pull --rebase {shlex.quote(args.remote)} {shlex.quote(args.base)}", check=False)

    if confirm(f"Создать ветку '{branch_name}'?", True):
        say_and_run(f"git checkout -b {shlex.quote(branch_name)}", check=True)

    # 10) пуш (+ MR для GitLab)
    push_cmd = f"git push -u {shlex.quote(args.remote)} {shlex.quote(branch_name)}"
    code, remote_url = say_and_run(f"git remote get-url {shlex.quote(args.remote)}", check=False, capture=True)
    is_gitlab = ("gitlab" in (remote_url or "").lower())
    if args.mr and is_gitlab:
        push_cmd += " -o merge_request.create"

    if confirm(f"Выполнить пуш? ({push_cmd})", True):
        say_and_run(push_cmd, check=True)

    print("\n✅ Готово. Коммит по conventional commits создан, ветка сформирована и запушена.")
    if args.mr and is_gitlab:
        print("📝 Для GitLab MR должен быть создан автоматически.")

if __name__ == "__main__":
    git_cr()