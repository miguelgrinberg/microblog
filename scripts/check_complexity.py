#!/usr/bin/env python3
"""ЛР6, Завд.3: "воротар якості" для git pre-commit.

Приймає список файлів (pre-commit передає лише ті, що йдуть у коміт, тобто
staged), прогоняє їх через Radon CLI і блокує коміт, якщо хоча б один
метод має цикломатичну складність CC > 10 (за замовчуванням).

Код виходу: 0 - усе гаразд, 1 - ліміт перевищено (коміт скасовано).
"""
import json
import subprocess
import sys

LIMIT = 10
RED, BOLD, RESET = '\033[91m', '\033[1m', '\033[0m'


def staged_python_files(argv):
    if argv:
        return [a for a in argv if a.endswith('.py')]
    out = subprocess.run(
        ['git', 'diff', '--cached', '--name-only', '--diff-filter=ACM'],
        capture_output=True, text=True, check=True).stdout.split()
    return [f for f in out if f.endswith('.py')]


def main(argv):
    files = staged_python_files(argv)
    if not files:
        print('complexity gate: немає Python-файлів у коміті, пропускаю')
        return 0
    # radon cc -j -n C  =>  JSON лише для блоків рангу C і гірше (CC >= 11)
    res = subprocess.run(
        [sys.executable, '-m', 'radon', 'cc', '-j', '-n', 'C', *files],
        capture_output=True, text=True)
    if res.returncode != 0:
        print(f'{RED}complexity gate: radon не запустився. '
              f'Встанови його: pip install radon{RESET}\n{res.stderr}')
        return 1
    report = json.loads(res.stdout or '{}')
    violations = [
        (path, b) for path, blocks in report.items()
        if isinstance(blocks, list)
        for b in blocks if b['complexity'] > LIMIT]
    if not violations:
        print(f'complexity gate: OK, усі методи мають CC <= {LIMIT}')
        return 0
    print(f'{RED}{BOLD}КОМІТ ЗАБЛОКОВАНО: перевищено ліміт складності CC > {LIMIT}{RESET}')
    for path, b in violations:
        print(f'{RED}  {path}:{b["lineno"]}  {b["name"]}()  '
              f'CC = {b["complexity"]} (ранг {b["rank"]}){RESET}')
    print(f'{RED}Спрости метод (наприклад, таблицею пошуку) і повтори git add + git commit.{RESET}')
    return 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
