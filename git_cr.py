#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import os
import shlex
import subprocess
import sys

def git_cr():
    parser = argparse.ArgumentParser(description="Пошаговое создание коммита, ветки и пуша (GitLab MR опционально).")
    parser.add_argument("--remote", default="origin", help="Имя удалённого (по умолчанию origin).")
    parser.add_argument("--base", default="main", help="От какой ветки ответвляться (по умолчанию main).")
    parser.add_argument("--yes", action="store_true", help="Автоподтверждение всех шагов.")
    parser.add_argument("--mr", action="store_true", help="Добавить -o merge_request.create (актуально для GitLab).")
    parser.add_argument("--name", default="ad-user", help="Локальный user.name (по умолчанию ad-user).")
    parser.add_argument("--email", default="ad.dev@arbat.dev", help="Локальный user.email (по умолчанию ad.dev@arbat.dev).")
    args = parser.parse_args()

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

    def confirm(prompt, default_yes=True):
        if args.yes:
            print(f"{prompt} [auto-yes]")
            return True
        suffix = "Y/n" if default_yes else "y/N"
        ans = input(f"{prompt} ({suffix}): ").strip().lower()
        if ans == "":
            return default_yes
        return ans in ("y", "yes", "д", "да")

    # 0) Проверки окружения
    code, out = say_and_run("git rev-parse --is-inside-work-tree", check=False, capture=True)
    if code != 0 or out.strip() != "true":
        print("❌ Здесь нет git-репозитория. Запусти скрипт внутри проекта.")
        sys.exit(1)

    code, current = say_and_run("git rev-parse --abbrev-ref HEAD", check=False, capture=True)
    if code != 0:
        print("❌ Не удалось определить текущую ветку.")
        sys.exit(2)
    print(f"➡️ Текущая ветка: {current}")

    code, _ = say_and_run(f"git remote get-url {shlex.quote(args.remote)}", check=False, capture=True)
    if code != 0:
        print(f"❌ Remote '{args.remote}' не настроен. Пример:\n   git remote add {args.remote} <URL>")
        sys.exit(3)

    # 1) Локальные конфиги
    if confirm(f"Поставить локально user.name = '{args.name}'?", True):
        say_and_run(f"git config --local user.name {shlex.quote(args.name)}", check=True)
    if confirm(f"Поставить локально user.email = '{args.email}'?", True):
        say_and_run(f"git config --local user.email {shlex.quote(args.email)}", check=True)

    # 2) Коммит с твоим сообщением (или пустой)
    commit_msg = input("Сообщение коммита (например, 'CR request: OAuth2 support'): ").strip()
    if not commit_msg:
        commit_msg = "CR request"

    # проверим, есть ли изменения в рабочем дереве
    code, status = say_and_run("git status --porcelain", check=False, capture=True)
    dirty = bool(status.strip())

    if dirty:
        print("Обнаружены незакоммиченные изменения.")
        if confirm("Добавить все изменения и сделать коммит?", True):
            say_and_run("git add -A", check=True)
            say_and_run(f'git commit -m {shlex.quote(commit_msg)}', check=True)
    else:
        print("Изменений нет.")
        if confirm("Создать ПУСТОЙ коммит с твоим сообщением?", True):
            say_and_run(f'git commit --allow-empty -m {shlex.quote(commit_msg)}', check=True)

    # 3) Создание новой ветки с заданным именем
    # убедимся, что база актуальна

    branch_name = input("Имя новой ветки (например, 'feature/123-support-oauth-2.0'): ").strip()
    if not branch_name:
        print("❌ Имя ветки пустое.")
        sys.exit(4)

    # создаём ветку от текущей рабочей (обычно это base или твоя фича-точка)
    if confirm(f"Создать новую ветку '{branch_name}' от текущей '{current}'?", True):
        say_and_run(f"git checkout -b {shlex.quote(branch_name)}", check=True)

    # 4) Пуш новой ветки (и MR для GitLab)
    # если MR включён и remote указывает на gitlab — добавим опцию
    push_cmd = f"git push -u {shlex.quote(args.remote)} {shlex.quote(branch_name)}"
    code, remote_url = say_and_run(f"git remote get-url {shlex.quote(args.remote)}", check=False, capture=True)
    is_gitlab = ("gitlab" in (remote_url or "").lower())

    if args.mr and is_gitlab:
        push_cmd += " -o merge_request.create"

    print(f"Запланирован пуш: {push_cmd}")
    if confirm("Выполнить пуш?", True):
        code, _ = say_and_run(push_cmd, check=True)
        if code != 0:
            print("❌ Push завершился ошибкой.")
            sys.exit(code)

    print("\n✅ Готово. Конфиг установлен, коммит создан, ветка создана и запушена.")
    if args.mr and is_gitlab:
        print("📝 Для GitLab должен быть создан Merge Request автоматически.")
    elif args.mr and not is_gitlab:
        print("ℹ️ Внимание: -o merge_request.create поддерживается только GitLab. На GitHub MR не создастся.")

if __name__ == "__main__":
    git_cr()