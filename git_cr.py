#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import shlex
import subprocess
import sys

def git_cr():
    # --- Парсим аргументы командной строки ---
    parser = argparse.ArgumentParser(description="Автоматизация создания Merge Request (всё в одной функции).")
    parser.add_argument("--yes", action="store_true", help="Автоматически подтверждать все шаги.")
    parser.add_argument("--no-alias", action="store_true", help="Не создавать глобальный алиас 'git cr'.")
    parser.add_argument("--remote", default="origin", help="Имя удалённого репозитория (по умолчанию origin).")
    args = parser.parse_args()

    FIXED_USER_NAME = "ad-user"
    FIXED_USER_EMAIL = "ad.dev@arbat.dev"

    # --- Функция для запуска команд ---
    def say_and_run(cmd, check=True, capture=False):
        print(f"\n$ {cmd}")  # показываем команду
        try:
            res = subprocess.run(
                cmd, shell=True, check=check,
                stdout=(subprocess.PIPE if capture else None),
                stderr=(subprocess.STDOUT if capture else None),
                text=True
            )
            if capture and res.stdout:
                print(res.stdout.strip())
            return res.returncode, res.stdout.strip() if res.stdout else ""
        except subprocess.CalledProcessError as e:
            out = getattr(e, "stdout", "") or ""
            if out:
                print(out.strip())
            return e.returncode, out.strip()

    # --- Функция подтверждения ---
    def confirm(prompt, default_yes=True):
        if args.yes:
            print(f"{prompt} [auto-yes]")
            return True
        suffix = "Y/n" if default_yes else "y/N"
        ans = input(f"{prompt} ({suffix}): ").strip().lower()
        if ans == "":
            return default_yes
        return ans in ("y", "yes", "д", "да")

    # --- Проверяем что мы внутри git-репозитория ---
    code, out = say_and_run("git rev-parse --is-inside-work-tree", check=False, capture=True)
    if code != 0 or out.strip() != "true":
        print("❌ Здесь нет git-репозитория. Запусти скрипт внутри проекта.")
        sys.exit(1)

    # --- Определяем текущую ветку ---
    code, branch = say_and_run("git rev-parse --abbrev-ref HEAD", check=False, capture=True)
    if code != 0:
        print("❌ Не удалось определить текущую ветку.")
        sys.exit(2)
    print(f"➡️ Текущая ветка: {branch}")

    # --- Проверяем наличие remote ---
    code, _ = say_and_run(f"git remote get-url {shlex.quote(args.remote)}", check=False, capture=True)
    if code != 0:
        print(f"❌ Remote '{args.remote}' не настроен. Добавь его:\n   git remote add {args.remote} <URL>")
        sys.exit(3)

    # --- Ставим локальные user.name / user.email ---
    if confirm(f"Поставить локально user.name = '{FIXED_USER_NAME}'?", True):
        say_and_run(f"git config --local user.name {shlex.quote(FIXED_USER_NAME)}", check=True)
    if confirm(f"Поставить локально user.email = '{FIXED_USER_EMAIL}'?", True):
        say_and_run(f"git config --local user.email {shlex.quote(FIXED_USER_EMAIL)}", check=True)

    # --- Создаём алиас git cr (опционально) ---
    if not args.no_alias and confirm("Создать глобальный алиас 'git cr' для пустого коммита 'CR request'?", True):
        say_and_run("git config --global alias.cr 'commit --allow-empty -m \"CR request\"'", check=False)

    # --- Проверяем настроен ли upstream ---
    code, _ = say_and_run("git rev-parse --symbolic-full-name @{u}", check=False, capture=True)
    upstream_set = (code == 0)

    # --- Проверяем есть ли непушеные коммиты ---
    def has_unpushed():
        if not upstream_set:
            return True
        c, out = say_and_run("git rev-list --left-only --count @{u}...HEAD", check=False, capture=True)
        if c != 0:
            return True
        try:
            return int(out.strip()) > 0
        except Exception:
            return True

    # --- Если пушить нечего — предлагаем сделать пустой коммит CR ---
    if not has_unpushed() and confirm("Нет изменений для пуша. Сделать пустой коммит 'CR'?", True):
        say_and_run('git commit --allow-empty -m "CR"', check=False)

    # --- Проверяем есть ли ветка на remote ---
    code, _ = say_and_run(
        f"git ls-remote --exit-code --heads {shlex.quote(args.remote)} {shlex.quote(branch)}",
        check=False, capture=True
    )
    exists_on_remote = (code == 0)

    # --- Формируем команду push ---
    if not upstream_set:
        if exists_on_remote:
            push_cmd = f"git push --set-upstream {shlex.quote(args.remote)} {shlex.quote(branch)} -o merge_request.create"
        else:
            push_cmd = f"git push -u {shlex.quote(args.remote)} {shlex.quote(branch)} -o merge_request.create"
    else:
        push_cmd = "git push -o merge_request.create"

    print(f"Запланирован пуш: {push_cmd}")

    # --- Выполняем push с подтверждением ---
    if confirm("Выполнить push и создать Merge Request в GitLab?", True):
        code, _ = say_and_run(push_cmd, check=True)
        if code != 0:
            print("❌ Push завершился ошибкой.")
            sys.exit(code)

    print("\n✅ Готово! Merge Request создан.")


if __name__ == "__main__":
    git_cr()