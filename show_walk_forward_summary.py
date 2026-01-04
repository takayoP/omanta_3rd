#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Walk-Forward Analysis結果のサマリー表示"""

import json

with open('walk_forward_longterm_12M_roll_evalYear2025.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

print('=' * 80)
print('Walk-Forward Analysis (Roll方式) 結果サマリー')
print('=' * 80)
print(f'\nFold数: {data["n_folds"]}')
print(f'\n各Foldの結果:')
for fold in data['fold_results']:
    label = fold['fold_label']
    ann_excess = fold['test_performance']['ann_excess_mean']
    win_rate = fold['test_performance']['win_rate']
    print(f'  {label}: ann_excess_mean={ann_excess:.2f}%, win_rate={win_rate:.1%}')

print(f'\n全体統計:')
summary = data['summary']['test_ann_excess_mean']
print(f'  平均年率超過リターン: {summary["mean"]:.2f}%')
print(f'  中央値: {summary["median"]:.2f}%')
print(f'  最小: {summary["min"]:.2f}%')
print(f'  最大: {summary["max"]:.2f}%')
print(f'  平均勝率: {data["summary"]["test_win_rate"]["mean"]:.1%}')

print(f'\n最終ホールドアウト (2024年):')
holdout = data['holdout_2025']['test_performance']
print(f'  年率超過リターン: {holdout["ann_excess_mean"]:.2f}%')
print(f'  勝率: {holdout["win_rate"]:.1%}')
print('=' * 80)


