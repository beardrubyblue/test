#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations
import argparse
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

def sh(args: list[str], cwd: Path, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=str(cwd), text=True, capture_output=True, check=check)

def inside_git(cwd: Path) -> bool:
    p = subprocess.run(["git", "rev-parse", "--is-inside-work-tree"],
                       cwd=str(cwd), text=True, capture_output=True)
    return p.returncode == 0 and p.stdout.strip() == "true"

def repo_root(cwd: Path) -> Path:
    p = sh(["git", "rev-parse", "--show-toplevel"], cwd)
    return Path(p.stdout.strip())

def current_branch(cwd: Path) -> str:
    p = sh(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd)
    return p.stdout.strip()

def main() -> None:
    # Где пользователь "сидит" сейчас — это и есть рабочая область
    inv_dir = Path.cwd().resolve()
    os.chdir(inv_dir)  # по совету "сменить диру на рабочую" — фиксируем cwd

    if not inside_git(inv_dir):
        print(f"❌ Текущая папка не является частью Git-репозитория: {inv_dir}", file=sys.stderr)
        sys.exit(1)

    parser = argparse.ArgumentParser(
        description="Коммитит ТОЛЬКО изменения из текущей папки (и её подкаталогов)."
    )
    parser.add_argument("-m", "--message", help="Сообщение коммита")
    parser.add_argument("--push", action="store_true", help="Сделать git push после коммита")
    args = parser.parse_args()

    # Индексируем только текущую директорию
    sh(["git", "add", "-A", "."], inv_dir)

    # Проверяем, есть ли что коммитить именно тут
    status = sh(["git", "status", "--porcelain"], inv_dir, check=False).stdout.strip()
    if not status:
        print("✔ Нет изменений в текущей папке — коммит не требуется.")
        return

    msg = args.message or f"update: {inv_dir} @ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    sh(["git", "commit", "-m", msg], inv_dir)
    print(f"✔ Коммит выполнен в репозитории {repo_root(inv_dir)} из папки {inv_dir}")

    if args.push:
        br = current_branch(inv_dir)
        # Пытаемся настроить upstream, если его нет
        push = subprocess.run(["git", "push", "-u", "origin", br],
                              cwd=str(inv_dir), text=True, capture_output=True)
        if push.returncode != 0:
            # fallback: обычный push (например, если detached HEAD)
            sh(["git", "push"], inv_dir, check=False)
        print(f"⬆️  Изменения отправлены (ветка: {br})")

if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as e:
        # аккуратно выводим stdout/stderr гита
        if e.stdout:
            print(e.stdout, end="")
        if e.stderr:
            print(e.stderr, end="", file=sys.stderr)
        sys.exit(e.returncode)
