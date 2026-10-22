"""Вимір Cognitive Complexity для всіх функцій файлу.

Запуск: python scripts/measure_complexity.py app/translate.py
Cyclomatic Complexity міряється окремо: radon cc -s app/translate.py
Потрібно: pip install radon cognitive-complexity
"""
import ast
import sys

from cognitive_complexity.api import get_cognitive_complexity

for node in ast.parse(open(sys.argv[1]).read()).body:
    if isinstance(node, ast.FunctionDef):
        print('cognitive', node.name, get_cognitive_complexity(node),
              'lines', node.end_lineno - node.lineno + 1)
