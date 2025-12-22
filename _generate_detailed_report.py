"""
詳細な計算過程レポートを生成（元データ含む）
"""

from src.omanta_3rd.infra.db import connect_db
from src.omanta_3rd.jobs.monthly_run import build_features, _split_multiplier_between
import pandas as pd
import numpy as np
from datetime import datetime

codes = ["1605", "6005", "8136", "9202", "8725", "4507", "8111"]
asof = "2025-12-19"

report_lines = []
report_lines.append("=" * 100)
report_lines.append("PER/PBR/Forward PER計算過程詳細報告書")
report_lines.append("=" * 100)
report_lines.append(f"評価日: {asof}")
report_lines.append(f"対象銘柄: {', '.join(codes)}")
report_lines.append(f"生成日時: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
report_lines.append("=" * 100)
report_lines.append("")

with connect_db() as conn:
    # 計算結果を取得
    feat = build_features(conn, asof)
    
    # 各銘柄の詳細レポートを生成
    for code in codes:
        report_lines.append("")
        report_lines.append("=" * 100)
        report_lines.append(f"【銘柄コード: {code}】")
        report_lines.append("=" * 100)
        report_lines.append("")
        
        # 価格データ
        price_data = pd.read_sql_query(
            """
            SELECT code, date, close, adj_close, adjustment_factor
            FROM prices_daily
            WHERE code = ? AND date = ?
            """,
            conn,
            params=(code, asof),
        )
        
        if price_data.empty:
            report_lines.append("❌ 価格データが見つかりません")
            continue
        
        price_row = price_data.iloc[0]
        price_close = price_row["close"]
        price_adj_close = price_row["adj_close"]
        
        report_lines.append("## 1. 元データ")
        report_lines.append("")
        report_lines.append("### 1.1 価格データ（prices_dailyテーブル）")
        report_lines.append(f"- 評価日: {asof}")
        report_lines.append(f"- `close`（未調整終値）: {price_close:,.2f}円" if pd.notna(price_close) else "- `close`: N/A")
        report_lines.append(f"- `adj_close`（調整後終値）: {price_adj_close:,.2f}円" if pd.notna(price_adj_close) else "- `adj_close`: N/A")
        report_lines.append(f"- **使用する価格**: `close = {price_close:,.2f}円`" if pd.notna(price_close) else "- **使用する価格**: N/A")
        report_lines.append("")
        
        # FY実績データ
        fy_data = pd.read_sql_query(
            """
            WITH ranked AS (
              SELECT
                code, current_period_end, disclosed_date,
                profit, equity, eps, bvps,
                shares_outstanding, treasury_shares,
                ROW_NUMBER() OVER (
                  PARTITION BY code
                  ORDER BY current_period_end DESC, disclosed_date DESC
                ) AS rn
              FROM fins_statements
              WHERE code = ?
                AND disclosed_date <= ?
                AND type_of_current_period = 'FY'
            )
            SELECT *
            FROM ranked
            WHERE rn = 1
            """,
            conn,
            params=(code, asof),
        )
        
        if fy_data.empty:
            report_lines.append("❌ FY実績データが見つかりません")
            continue
        
        fy = fy_data.iloc[0]
        
        report_lines.append("### 1.2 FY実績データ（fins_statementsテーブル）")
        report_lines.append(f"- 期末日（current_period_end）: {fy['current_period_end']}")
        report_lines.append(f"- 開示日（disclosed_date）: {fy['disclosed_date']}")
        report_lines.append(f"- 利益（profit）: {fy['profit']:,.0f}円" if pd.notna(fy['profit']) else "- 利益: N/A")
        report_lines.append(f"- 純資産（equity）: {fy['equity']:,.0f}円" if pd.notna(fy['equity']) else "- 純資産: N/A")
        report_lines.append(f"- 発行済み株式数（shares_outstanding）: {fy['shares_outstanding']:,.0f}株" if pd.notna(fy['shares_outstanding']) else "- 発行済み株式数: N/A")
        report_lines.append(f"- 自己株式数（treasury_shares）: {fy['treasury_shares']:,.0f}株" if pd.notna(fy['treasury_shares']) else "- 自己株式数: N/A")
        report_lines.append(f"- EPS（参考）: {fy['eps']:.2f}円" if pd.notna(fy['eps']) else "- EPS: N/A")
        report_lines.append(f"- BPS（参考）: {fy['bvps']:.2f}円" if pd.notna(fy['bvps']) else "- BPS: N/A")
        report_lines.append("")
        
        # 予想データ
        fc_data = pd.read_sql_query(
            """
            WITH ranked AS (
              SELECT
                code, disclosed_date, type_of_current_period,
                forecast_profit, forecast_eps,
                ROW_NUMBER() OVER (
                  PARTITION BY code
                  ORDER BY disclosed_date DESC,
                           CASE WHEN type_of_current_period = 'FY' THEN 0 ELSE 1 END
                ) AS rn
              FROM fins_statements
              WHERE code = ?
                AND disclosed_date <= ?
                AND (forecast_profit IS NOT NULL OR forecast_eps IS NOT NULL)
            )
            SELECT *
            FROM ranked
            WHERE rn = 1
            """,
            conn,
            params=(code, asof),
        )
        
        report_lines.append("### 1.3 予想データ（fins_statementsテーブル）")
        if fc_data.empty:
            report_lines.append("- 予想データ: なし")
        else:
            fc = fc_data.iloc[0]
            report_lines.append(f"- 開示日（disclosed_date）: {fc['disclosed_date']}")
            report_lines.append(f"- 期間種別（type_of_current_period）: {fc['type_of_current_period']}")
            report_lines.append(f"- 予想利益（forecast_profit）: {fc['forecast_profit']:,.0f}円" if pd.notna(fc['forecast_profit']) else "- 予想利益: N/A")
            report_lines.append(f"- 予想EPS（forecast_eps、参考）: {fc['forecast_eps']:.2f}円" if pd.notna(fc['forecast_eps']) else "- 予想EPS: N/A")
        report_lines.append("")
        
        # 分割情報
        fy_end = fy['current_period_end']
        if pd.notna(fy_end):
            if hasattr(fy_end, 'strftime'):
                fy_end_str = fy_end.strftime("%Y-%m-%d")
            else:
                fy_end_str = str(fy_end)
            
            split_info = pd.read_sql_query(
                """
                SELECT date, adjustment_factor
                FROM prices_daily
                WHERE code = ?
                  AND date > ?
                  AND date <= ?
                  AND adjustment_factor IS NOT NULL
                  AND adjustment_factor != 1.0
                ORDER BY date ASC
                """,
                conn,
                params=(code, fy_end_str, asof),
            )
            
            report_lines.append("### 1.4 分割・併合情報（prices_dailyテーブル）")
            report_lines.append(f"- FY期末: {fy_end_str}")
            report_lines.append(f"- 評価日: {asof}")
            if split_info.empty:
                report_lines.append("- 分割・併合: なし")
            else:
                report_lines.append(f"- 分割・併合の発生回数: {len(split_info)}回")
                report_lines.append("- 分割・併合の詳細:")
                for _, row in split_info.iterrows():
                    adj_factor = row["adjustment_factor"]
                    split_date = row["date"]
                    mult = 1.0 / adj_factor
                    report_lines.append(f"  - {split_date}: `adjustment_factor = {adj_factor:.6f}` → 株数倍率 = 1 / {adj_factor:.6f} = {mult:.6f}")
        report_lines.append("")
        
        # 計算過程
        report_lines.append("## 2. 計算過程")
        report_lines.append("")
        
        # ネット株数
        so = fy['shares_outstanding']
        ts = fy['treasury_shares'] if pd.notna(fy['treasury_shares']) else 0.0
        if ts < 0:
            ts = 0.0
        net_shares_fy = so - ts if pd.notna(so) and so > 0 else np.nan
        
        report_lines.append("### 2.1 FY期末のネット株数計算")
        report_lines.append("```")
        report_lines.append("計算式: net_shares_fy = shares_outstanding - treasury_shares")
        if pd.notna(so):
            report_lines.append(f"      = {so:,.0f} - {ts:,.0f}")
            report_lines.append(f"      = {net_shares_fy:,.0f}株")
        else:
            report_lines.append("      = N/A")
        report_lines.append("```")
        report_lines.append("")
        
        # 分割倍率
        if pd.notna(fy_end):
            split_mult = _split_multiplier_between(conn, code, fy_end_str, asof)
            
            report_lines.append("### 2.2 分割倍率計算（FY期末→評価日）")
            report_lines.append("```")
            report_lines.append("計算式: split_mult = ∏(1 / adjustment_factor)")
            if split_info.empty:
                report_lines.append("分割・併合なし → split_mult = 1.0")
            else:
                for _, row in split_info.iterrows():
                    adj_factor = row["adjustment_factor"]
                    report_lines.append(f"  {row['date']}: 1 / {adj_factor:.6f} = {1.0/adj_factor:.6f}")
                report_lines.append(f"累積: split_mult = {split_mult:.6f}")
            report_lines.append("```")
            report_lines.append("")
        else:
            split_mult = 1.0
        
        # 評価日時点のネット株数
        net_shares_at_price = net_shares_fy * split_mult if pd.notna(net_shares_fy) else np.nan
        
        report_lines.append("### 2.3 評価日時点のネット株数（補正後）")
        report_lines.append("```")
        report_lines.append("計算式: net_shares_at_price = net_shares_fy × split_mult")
        if pd.notna(net_shares_fy):
            report_lines.append(f"      = {net_shares_fy:,.0f} × {split_mult:.6f}")
            report_lines.append(f"      = {net_shares_at_price:,.0f}株")
        else:
            report_lines.append("      = N/A")
        report_lines.append("```")
        report_lines.append("")
        
        # 標準EPS/BPS
        report_lines.append("### 2.4 標準EPS/BPSの計算")
        report_lines.append("```")
        if pd.notna(fy['profit']) and pd.notna(net_shares_at_price) and fy['profit'] > 0 and net_shares_at_price > 0:
            eps_std = fy['profit'] / net_shares_at_price
            report_lines.append("標準EPS = profit / net_shares_at_price")
            report_lines.append(f"       = {fy['profit']:,.0f} / {net_shares_at_price:,.0f}")
            report_lines.append(f"       = {eps_std:.2f}円")
        else:
            eps_std = np.nan
            report_lines.append("標準EPS: 計算不可（profitまたはnet_shares_at_priceが無効）")
        
        if pd.notna(fy['equity']) and pd.notna(net_shares_at_price) and fy['equity'] > 0 and net_shares_at_price > 0:
            bps_std = fy['equity'] / net_shares_at_price
            report_lines.append("")
            report_lines.append("標準BPS = equity / net_shares_at_price")
            report_lines.append(f"       = {fy['equity']:,.0f} / {net_shares_at_price:,.0f}")
            report_lines.append(f"       = {bps_std:.2f}円")
        else:
            bps_std = np.nan
            report_lines.append("")
            report_lines.append("標準BPS: 計算不可（equityまたはnet_shares_at_priceが無効）")
        report_lines.append("```")
        report_lines.append("")
        
        # 標準予想EPS
        report_lines.append("### 2.5 標準予想EPSの計算")
        report_lines.append("```")
        if not fc_data.empty:
            fc = fc_data.iloc[0]
            if pd.notna(fc['forecast_profit']) and pd.notna(net_shares_at_price) and fc['forecast_profit'] > 0 and net_shares_at_price > 0:
                forecast_eps_std = fc['forecast_profit'] / net_shares_at_price
                report_lines.append("標準予想EPS = forecast_profit / net_shares_at_price")
                report_lines.append(f"            = {fc['forecast_profit']:,.0f} / {net_shares_at_price:,.0f}")
                report_lines.append(f"            = {forecast_eps_std:.2f}円（forecast_profitベース）")
            elif pd.notna(fc['forecast_eps']) and fc['forecast_eps'] > 0:
                forecast_eps_std = fc['forecast_eps']
                report_lines.append("標準予想EPS = forecast_eps（フォールバック）")
                report_lines.append(f"            = {forecast_eps_std:.2f}円（forecast_epsベース）")
            else:
                forecast_eps_std = np.nan
                report_lines.append("標準予想EPS: 計算不可")
        else:
            forecast_eps_std = np.nan
            report_lines.append("標準予想EPS: 予想データなし")
        report_lines.append("```")
        report_lines.append("")
        
        # PER/PBR/Forward PER
        report_lines.append("### 2.6 PER/PBR/Forward PERの計算")
        report_lines.append("```")
        if pd.notna(price_close) and pd.notna(eps_std) and eps_std > 0:
            per = price_close / eps_std
            report_lines.append("PER = price / eps_std")
            report_lines.append(f"   = {price_close:,.2f} / {eps_std:.2f}")
            report_lines.append(f"   = {per:.2f}")
        else:
            per = np.nan
            report_lines.append("PER: 計算不可")
        
        if pd.notna(price_close) and pd.notna(bps_std) and bps_std > 0:
            pbr = price_close / bps_std
            report_lines.append("")
            report_lines.append("PBR = price / bps_std")
            report_lines.append(f"   = {price_close:,.2f} / {bps_std:.2f}")
            report_lines.append(f"   = {pbr:.2f}")
        else:
            pbr = np.nan
            report_lines.append("")
            report_lines.append("PBR: 計算不可")
        
        if pd.notna(price_close) and pd.notna(forecast_eps_std) and forecast_eps_std > 0:
            forward_per = price_close / forecast_eps_std
            report_lines.append("")
            report_lines.append("Forward PER = price / forecast_eps_std")
            report_lines.append(f"            = {price_close:,.2f} / {forecast_eps_std:.2f}")
            report_lines.append(f"            = {forward_per:.2f}")
        else:
            forward_per = np.nan
            report_lines.append("")
            report_lines.append("Forward PER: 計算不可")
        report_lines.append("```")
        report_lines.append("")
        
        # 検証
        feat_row = feat[feat["code"] == code]
        if not feat_row.empty:
            feat_data = feat_row.iloc[0]
            report_lines.append("## 3. 計算結果の検証")
            report_lines.append("")
            report_lines.append("| 項目 | システム計算値 | 手動計算値 | 差分 | 結果 |")
            report_lines.append("|------|---------------|-----------|------|------|")
            
            if pd.notna(per) and pd.notna(feat_data.get('per')):
                diff_per = abs(per - feat_data.get('per'))
                status = "✅ 一致" if diff_per < 0.01 else "⚠️ 不一致"
                report_lines.append(f"| PER | {feat_data.get('per'):.2f} | {per:.2f} | {diff_per:.6f} | {status} |")
            
            if pd.notna(pbr) and pd.notna(feat_data.get('pbr')):
                diff_pbr = abs(pbr - feat_data.get('pbr'))
                status = "✅ 一致" if diff_pbr < 0.01 else "⚠️ 不一致"
                report_lines.append(f"| PBR | {feat_data.get('pbr'):.2f} | {pbr:.2f} | {diff_pbr:.6f} | {status} |")
            
            if pd.notna(forward_per) and pd.notna(feat_data.get('forward_per')):
                diff_fper = abs(forward_per - feat_data.get('forward_per'))
                status = "✅ 一致" if diff_fper < 0.01 else "⚠️ 不一致"
                report_lines.append(f"| Forward PER | {feat_data.get('forward_per'):.2f} | {forward_per:.2f} | {diff_fper:.6f} | {status} |")
            report_lines.append("")

# 報告書をファイルに出力
with open("CALCULATION_DETAILED_REPORT.md", "w", encoding="utf-8") as f:
    f.write("\n".join(report_lines))

print("詳細報告書を生成しました: CALCULATION_DETAILED_REPORT.md")
