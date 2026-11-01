#!/usr/bin/env python3
"""ЛР6, Завд.1: таблиці Холстеда за формулами методички.

Використання (з кореня проєкту, venv активований):
    python scripts/halstead_report.py app/models.py app/translate.py app/main/forms.py

Первинні міри (η1, η2, N1, N2) бере з Radon (radon.metrics.h_visit), а V, D, E
рахує за формулами завдання і звіряє з тим, що повертає сам Radon.
Додатково рахує ті самі міри "за визначенням методички": оператори = ключові
слова + знаки операцій + роздільники, операнди = імена, числа, рядки
(модуль tokenize зі стандартної бібліотеки).
"""
import io
import keyword
import math
import pathlib
import sys
import tokenize

from radon.metrics import h_visit
from radon.raw import analyze


def derived(h1, h2, n1, n2):
    eta, n = h1 + h2, n1 + n2
    v = n * math.log2(eta) if eta else 0.0
    d = (h1 / 2) * (n2 / h2) if h2 else 0.0
    return eta, n, v, d, v * d


def radon_row(src):
    t = h_visit(src).total
    eta, n, v, d, e = derived(t.h1, t.h2, t.N1, t.N2)
    ok = (math.isclose(v, t.volume, abs_tol=1e-6)
          and math.isclose(d, t.difficulty, abs_tol=1e-6)
          and math.isclose(e, t.effort, abs_tol=1e-6))
    return t.h1, t.h2, t.N1, t.N2, eta, n, v, d, e, ok


def token_counts(src):
    ops, opd = [], []
    skip = {tokenize.NEWLINE, tokenize.NL, tokenize.INDENT, tokenize.DEDENT,
            tokenize.ENDMARKER, tokenize.COMMENT}
    for tok in tokenize.generate_tokens(io.StringIO(src).readline):
        if tok.type in skip:
            continue
        if tok.type == tokenize.NAME and not keyword.iskeyword(tok.string):
            opd.append(tok.string)
        elif tok.type in (tokenize.NUMBER, tokenize.STRING):
            opd.append(tok.string)
        else:
            ops.append(tok.string)
    return len(set(ops)), len(set(opd)), len(ops), len(opd)


def main(paths):
    print('| Файл | LOC | SLOC | η1 | η2 | N1 | N2 | η | N | V | D | E | формули = Radon |')
    print('|---|---|---|---|---|---|---|---|---|---|---|---|---|')
    rows = []
    for p in paths:
        src = pathlib.Path(p).read_text(encoding='utf-8')
        raw = analyze(src)
        h1, h2, n1, n2, eta, n, v, d, e, ok = radon_row(src)
        rows.append((p, raw.loc, h1, h2, n1, n2, eta, n, v, d, e))
        print(f'| {p} | {raw.loc} | {raw.sloc} | {h1} | {h2} | {n1} | {n2} | {eta} | {n} '
              f'| {v:.2f} | {d:.2f} | {e:.1f} | {"так" if ok else "НІ"} |')
    print('\nРанжування за E (від більшого до меншого):')
    for i, r in enumerate(sorted(rows, key=lambda r: -r[10]), 1):
        print(f'{i}. {r[0]}: E = {r[10]:.1f}, V = {r[8]:.1f}, LOC = {r[1]}, E/LOC = {r[10]/r[1]:.2f}')
    print('\nКонтроль за визначенням методички (tokenize): '
          'оператори = ключові слова + знаки + роздільники')
    print('| Файл | η1 | η2 | N1 | N2 | V | D | E |')
    print('|---|---|---|---|---|---|---|---|')
    for p in paths:
        src = pathlib.Path(p).read_text(encoding='utf-8')
        h1, h2, n1, n2 = token_counts(src)
        eta, n, v, d, e = derived(h1, h2, n1, n2)
        print(f'| {p} | {h1} | {h2} | {n1} | {n2} | {v:.1f} | {d:.2f} | {e:.0f} |')


if __name__ == '__main__':
    main(sys.argv[1:])
