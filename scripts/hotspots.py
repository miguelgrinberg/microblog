#!/usr/bin/env python3
"""ЛР7, Завд.3: синергетична матриця Hotspots = складність (radon) x churn (git log).

Використання (з кореня репозиторію, повна Git-історія):
    radon cc -j app > reports/radon_cc.json
    radon hal -j app > reports/radon_hal.json
    python scripts/hotspots.py --cc reports/radon_cc.json --hal reports/radon_hal.json \
        --out-csv reports/hotspots.csv --out-md reports/hotspots.md

Складність файлу = сума CC усіх його функцій (ΣCC) і Halstead Effort (E).
Churn = кількість комітів, що змінювали файл (git log --follow, щоб не губити
історію після перейменувань), для двох вікон: уся історія і останні N днів.
Категорія визначається за ΣCC і churn за всю історію (пороги нижче).
"""
import argparse
import csv
import json
import subprocess
import sys

CC_HIGH = 15      # ΣCC файлу >= 15 вважаємо високою складністю (1.5 x поріг 10 для одного методу)
CHURN_HIGH = 7    # >= 7 комітів на файл — верхня п'ята частина розподілу в цьому репозиторії


def git_count(path, since=None):
    cmd = ['git', 'log', '--follow', '--format=%h', '--']
    if since:
        cmd[2:2] = [f'--since={since} days ago']
    cmd.append(path)
    out = subprocess.run(cmd, capture_output=True, text=True, check=True).stdout
    return len([ln for ln in out.splitlines() if ln.strip()])


def category(cc, churn, cc_high, churn_high):
    high_c, high_h = cc >= cc_high, churn >= churn_high
    if high_c and high_h:
        return 'High Risk (Hotspot)'
    if high_c:
        return 'Sleeping Danger'
    if high_h:
        return 'Active Development'
    return 'Stable Code'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--cc', required=True)
    ap.add_argument('--hal', required=True)
    ap.add_argument('--days', type=int, default=90)
    ap.add_argument('--cc-high', type=int, default=CC_HIGH)
    ap.add_argument('--churn-high', type=int, default=CHURN_HIGH)
    ap.add_argument('--out-csv')
    ap.add_argument('--out-md')
    a = ap.parse_args()

    cc = json.load(open(a.cc, encoding='utf-8'))
    hal = json.load(open(a.hal, encoding='utf-8'))
    rows = []
    for path, blocks in cc.items():
        if not isinstance(blocks, list):
            continue
        values = [b['complexity'] for b in blocks]
        total = hal.get(path, {}).get('total', {})
        effort = total.get('effort', 0) if isinstance(total, dict) else 0
        churn_all = git_count(path)
        churn_win = git_count(path, a.days)
        rows.append({
            'file': path, 'sum_cc': sum(values), 'max_cc': max(values, default=0),
            'halstead_E': round(effort, 1), 'commits_all': churn_all,
            f'commits_{a.days}d': churn_win,
            'category': category(sum(values), churn_all, a.cc_high, a.churn_high)})
    order = {'High Risk (Hotspot)': 0, 'Sleeping Danger': 1,
             'Active Development': 2, 'Stable Code': 3}
    rows.sort(key=lambda r: (order[r['category']], -r['sum_cc'], -r['commits_all']))

    cols = list(rows[0].keys())
    if a.out_csv:
        with open(a.out_csv, 'w', newline='', encoding='utf-8') as f:
            w = csv.DictWriter(f, fieldnames=cols)
            w.writeheader()
            w.writerows(rows)
    md = ['| Файл | ΣCC | max CC | Halstead E | Коміти (вся історія) | '
          f'Коміти ({a.days} днів) | Категорія |', '|---|---|---|---|---|---|---|']
    for r in rows:
        md.append(f"| {r['file']} | {r['sum_cc']} | {r['max_cc']} | {r['halstead_E']} | "
                  f"{r['commits_all']} | {r[f'commits_{a.days}d']} | {r['category']} |")
    md.append(f'\nПороги: ΣCC >= {a.cc_high} (висока складність), '
              f'коміти >= {a.churn_high} (висока мінливість).')
    text = '\n'.join(md)
    if a.out_md:
        open(a.out_md, 'w', encoding='utf-8').write(text + '\n')
    print(text)


if __name__ == '__main__':
    sys.exit(main())
