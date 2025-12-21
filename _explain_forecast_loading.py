#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
forecast_operating_profitの取得方法と、FYデータの相互補完について説明
"""

print("=== forecast_operating_profitの取得方法とFYデータの相互補完 ===\n")

print("【現在の実装】\n")

print("1. _load_latest_fy関数（FY実績データの取得）:")
print("   - 同じcurrent_period_endのFYデータ間で相互補完を実施")
print("   - operating_profitが欠損 → forecast_operating_profitから補完")
print("   - forecast_operating_profitが欠損 → operating_profitから補完")
print("   - profit, forecast_profit, forecast_epsについても同様")
print("   - 開示日が最新のレコードをベースに、同じcurrent_period_endの全レコードから補完\n")

print("2. _load_latest_forecast関数（予想データの取得）:")
print("   - fins_statementsテーブルから取得（FYと四半期の両方を含む）")
print("   - FYを優先（period_priority: FY=0, その他=1）")
print("   - 開示日が最新のものを選び、同じ開示日の場合FYを優先")
print("   - 四半期データも含まれている（type_of_current_periodのフィルタなし）\n")

print("3. マージ処理:")
print("   - fy_latest（相互補完済み）とfc_latest（四半期データも含む）をマージ")
print("   - fc_latestのforecast_*が優先される（suffixes=('', '_fc')）\n")

print("【質問への回答】\n")

print("Q1: 現在forecast_operating_profitの取得に四半期データも使っているか？")
print("A1: はい。_load_latest_forecast関数で、FYと四半期の両方から取得しています。")
print("    ただし、FYを優先して選択されます。\n")

print("Q2: その利用するデータの中に開示日の古い上記のFYデータも含まれているか？")
print("A2: はい。_load_latest_forecastは開示日が最新のものを選びますが、")
print("    同じcurrent_period_endのFYデータ間での相互補完は、_load_latest_fyで実施しています。")
print("    つまり、古い開示日のFYデータにforecast_operating_profitがある場合、")
print("    新しい開示日のFYデータのoperating_profitと相互補完されます。\n")

print("【相互補完の例】")
print("  銘柄コード: 6191, 当期末: 2025-09-30")
print("    - 開示日: 2025-07-01 → forecast_operating_profit: 2,000,000,000（実績はNULL）")
print("    - 開示日: 2025-11-14 → operating_profit: 3,159,000,000（予想はNULL）")
print("  → 補完後: operating_profit: 3,159,000,000, forecast_operating_profit: 3,159,000,000")
print("  （開示日が最新のレコードのoperating_profitをベースに、")
print("   古い開示日のforecast_operating_profitで補完）\n")

print("【注意点】")
print("  - 相互補完は同じcurrent_period_endのFYデータ間でのみ実施")
print("  - 開示日が最新のレコードをベースに、同じcurrent_period_endの全レコードから補完")
print("  - 四半期データは_load_latest_forecastで別途取得され、マージ時に使用される")
