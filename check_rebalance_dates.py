"""リバランス日の確認スクリプト"""
from omanta_3rd.jobs.batch_monthly_run import get_monthly_rebalance_dates

dates = get_monthly_rebalance_dates('2021-01-01', '2025-12-31')
print(f'リバランス日数: {len(dates)}')
if dates:
    print(f'最初: {dates[0]}')
    print(f'最後: {dates[-1]}')
else:
    print('リバランス日が見つかりませんでした')







