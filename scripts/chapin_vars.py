#!/usr/bin/env python3
"""ЛР7, Завд.1: інвентаризація змінних методу для аудиту за Чепіним.

Використання (з кореня проєкту):
    python scripts/chapin_vars.py app/translate.py translate

Скрипт НЕ призначає класи P/M/C/T. Він лише збирає факти про кожну змінну
(де оголошена, скільки разів їй присвоюють значення, чи стоїть в умові,
чи передається у виклик іншої функції), щоб клас за Чепіним ви обирали
самі за правилами завдання та ієрархією пріоритетів C > M > P > T.
"""
import ast
import sys
from collections import OrderedDict


class Facts:
    def __init__(self, kind, line):
        self.kind = kind          # param / local / loop / global-read
        self.line = line
        self.assigned = 0         # скільки разів значення (пере)записується
        self.in_condition = 0     # скільки разів стоїть в умові if/while/ifexp/and/or/not
        self.passed_to_call = 0   # скільки разів передається аргументом у виклик
        self.other_reads = 0      # інші читання (return, арифметика, атрибути...)


def find_function(tree, name):
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return node
    raise SystemExit(f'функцію {name} не знайдено')


def names_in(node):
    return [n for n in ast.walk(node) if isinstance(n, ast.Name)]


def collect(func):
    facts = OrderedDict()
    args = func.args
    for a in args.posonlyargs + args.args + args.kwonlyargs:
        facts[a.arg] = Facts('param', a.lineno)
    for a in (args.vararg, args.kwarg):
        if a:
            facts[a.arg] = Facts('param', a.lineno)

    def ensure(name, kind, line):
        if name not in facts:
            facts[name] = Facts(kind, line)
        return facts[name]

    # 1. присвоєння (включно з розпакуванням, for-змінними, +=)
    for node in ast.walk(func):
        targets = []
        if isinstance(node, ast.Assign):
            targets = node.targets
        elif isinstance(node, (ast.AugAssign, ast.AnnAssign)):
            targets = [node.target]
        elif isinstance(node, ast.For):
            for n in names_in(node.target):
                ensure(n.id, 'loop', n.lineno).assigned += 1
            continue
        for t in targets:
            for n in names_in(t):
                if isinstance(n.ctx, ast.Store):
                    ensure(n.id, 'local', n.lineno).assigned += 1

    # 2. умови та виклики
    cond_nodes = []
    for node in ast.walk(func):
        if isinstance(node, (ast.If, ast.While, ast.IfExp, ast.Assert)):
            cond_nodes.append(node.test)
        elif isinstance(node, ast.BoolOp):
            cond_nodes.extend(node.values)
        elif isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            cond_nodes.append(node.operand)
    in_cond_ids = set()
    for c in cond_nodes:
        for n in names_in(c):
            if n.id in facts and id(n) not in in_cond_ids:
                facts[n.id].in_condition += 1
                in_cond_ids.add(id(n))
    passed_ids = set()
    for node in ast.walk(func):
        if isinstance(node, ast.Call):
            for arg in list(node.args) + [k.value for k in node.keywords]:
                if isinstance(arg, ast.Starred):
                    arg = arg.value
                if isinstance(arg, ast.Name) and arg.id in facts:
                    facts[arg.id].passed_to_call += 1
                    passed_ids.add(id(arg))

    # 3. решта читань
    for n in names_in(func):
        if isinstance(n.ctx, ast.Load) and n.id in facts \
                and id(n) not in in_cond_ids and id(n) not in passed_ids:
            facts[n.id].other_reads += 1
    return facts


def global_reads(func, facts, module_names):
    """Модульні константи/імпорти, які метод лише читає."""
    found = OrderedDict()
    for n in names_in(func):
        if isinstance(n.ctx, ast.Load) and n.id not in facts and n.id in module_names:
            found.setdefault(n.id, []).append(n.lineno)
    return found


def main():
    path, func_name = sys.argv[1], sys.argv[2]
    src = open(path, encoding='utf-8').read()
    tree = ast.parse(src)
    func = find_function(tree, func_name)
    facts = collect(func)
    module_names = {t.id for n in tree.body if isinstance(n, ast.Assign)
                    for t in n.targets if isinstance(t, ast.Name)}
    print(f'Метод {func_name} ({path}:{func.lineno}-{func.end_lineno})\n')
    head = f'{"змінна":<20}{"звідки":<8}{"присв.":<8}{"в умові":<9}{"у виклик":<10}{"інше":<6}рядок'
    print(head)
    print('-' * len(head))
    for name, f in facts.items():
        print(f'{name:<20}{f.kind:<8}{f.assigned:<8}{f.in_condition:<9}'
              f'{f.passed_to_call:<10}{f.other_reads:<6}{f.line}')
    g = global_reads(func, facts, module_names)
    if g:
        print('\nМодульні константи, які метод читає (вирішіть самі, чи це змінні P):')
        for name, lines in g.items():
            print(f'  {name}: рядки {lines}')
    print('\nСтовпець «присв.» = скільки разів змінній записують значення в тілі методу '
          '(параметр без присвоєнь = 0).')


if __name__ == '__main__':
    main()
