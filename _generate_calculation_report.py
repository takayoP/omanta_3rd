"""
計算過程の詳細レポートを生成
"""

from src.omanta_3rd.infra.db import connect_db
from src.omanta_3rd.jobs.monthly_run import build_features, _split_multiplier_between
import pandas as pd
import numpy as np
from datetime import datetime

codes = ["1605", "6005", "8136", "9202", "8725", "4507", "8111"]
asof = "2025-12-19"

print("=" * 100)
print("PER/PBR/Forward PER計算過程レポート")
print("=" * 100)
print(f"評価日: {asof}")
print(f"対象銘柄: {', '.join(codes)}")
print(f"生成日時: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("=" * 100)

with connect_db() as conn:
    # 価格データを取得
    price_date = asof
    prices_data = pd.read_sql_query(
        """
        SELECT code, date, close, adj_close, adjustment_factor
        FROM prices_daily
        WHERE code IN ({})
          AND date = ?
        """.format(','.join(['?' for _ in codes])),
        conn,
        params=list(codes) + [price_date],
    )
    
    # FY実績データを取得
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
          WHERE code IN ({})
            AND disclosed_date <= ?
            AND type_of_current_period = 'FY'
        )
        SELECT *
        FROM ranked
        WHERE rn = 1
        """.format(','.join(['?' for _ in codes])),
        conn,
        params=list(codes) + [asof],
    )
    
    # 予想データを取得
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
          WHERE code IN ({})
            AND disclosed_date <= ?
            AND (forecast_profit IS NOT NULL OR forecast_eps IS NOT NULL)
        )
        SELECT *
        FROM ranked
        WHERE rn = 1
        """.format(','.join(['?' for _ in codes])),
        conn,
        params=list(codes) + [asof],
    )
    
    # 分割情報を取得（FY期末から評価日まで）
    split_data = {}
    for code in codes:
        fy_row = fy_data[fy_data["code"] == code]
        if not fy_row.empty:
            fy_end = fy_row.iloc[0]["current_period_end"]
            if pd.notna(fy_end):
                if hasattr(fy_end, 'strftime'):
                    fy_end_str = fy_end.strftime("%Y-%m-%d")
                else:
                    fy_end_str = str(fy_end)
                
                # 分割情報を取得
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
                    params=(code, fy_end_str, price_date),
                )
                split_data[code] = split_info
    
    # 計算結果を取得
    feat = build_features(conn, asof)
    
    # 各銘柄の詳細レポートを生成
    for code in codes:
        print(f"\n\n{'=' * 100}")
        print(f"【銘柄コード: {code}】")
        print(f"{'=' * 100}\n")
        
        # 価格データ
        price_row = prices_data[prices_data["code"] == code]
        if price_row.empty:
            print("❌ 価格データが見つかりません")
            continue
        
        price_close = price_row.iloc[0]["close"]
        price_adj_close = price_row.iloc[0]["adj_close"]
        print(f"【1. 価格データ（評価日: {price_date}）】")
        print(f"  close（未調整終値）: {price_close:,.2f}円" if pd.notna(price_close) else "  close: N/A")
        print(f"  adj_close（調整後終値）: {price_adj_close:,.2f}円" if pd.notna(price_adj_close) else "  adj_close: N/A")
        print(f"  → 使用する価格: close = {price_close:,.2f}円" if pd.notna(price_close) else "  → 使用する価格: N/A")
        
        # FY実績データ
        fy_row = fy_data[fy_data["code"] == code]
        if fy_row.empty:
            print("\n❌ FY実績データが見つかりません")
            continue
        
        fy = fy_row.iloc[0]
        print(f"\n【2. FY実績データ】")
        print(f"  期末日: {fy['current_period_end']}")
        print(f"  開示日: {fy['disclosed_date']}")
        print(f"  利益（profit）: {fy['profit']:,.0f}円" if pd.notna(fy['profit']) else "  利益: N/A")
        print(f"  純資産（equity）: {fy['equity']:,.0f}円" if pd.notna(fy['equity']) else "  純資産: N/A")
        print(f"  発行済み株式数（shares_outstanding）: {fy['shares_outstanding']:,.0f}株" if pd.notna(fy['shares_outstanding']) else "  発行済み株式数: N/A")
        print(f"  自己株式数（treasury_shares）: {fy['treasury_shares']:,.0f}株" if pd.notna(fy['treasury_shares']) else "  自己株式数: N/A")
        
        # ネット株数（FY期末）
        so = fy['shares_outstanding']
        ts = fy['treasury_shares'] if pd.notna(fy['treasury_shares']) else 0.0
        if ts < 0:
            ts = 0.0
        net_shares_fy = so - ts if pd.notna(so) and so > 0 else np.nan
        print(f"\n【3. FY期末のネット株数計算】")
        print(f"  計算式: net_shares_fy = shares_outstanding - treasury_shares")
        print(f"  = {so:,.0f} - {ts:,.0f}" if pd.notna(so) else "  = N/A")
        print(f"  = {net_shares_fy:,.0f}株" if pd.notna(net_shares_fy) else "  = N/A")
        
        # 分割倍率
        fy_end = fy['current_period_end']
        if pd.notna(fy_end):
            if hasattr(fy_end, 'strftime'):
                fy_end_str = fy_end.strftime("%Y-%m-%d")
            else:
                fy_end_str = str(fy_end)
            
            split_mult = _split_multiplier_between(conn, code, fy_end_str, price_date)
            
            print(f"\n【4. 分割倍率計算（FY期末→評価日）】")
            print(f"  FY期末: {fy_end_str}")
            print(f"  評価日: {price_date}")
            
            split_info = split_data.get(code)
            if split_info is not None and not split_info.empty:
                print(f"  分割・併合の発生回数: {len(split_info)}回")
                print(f"  分割・併合の詳細:")
                for _, row in split_info.iterrows():
                    adj_factor = row["adjustment_factor"]
                    split_date = row["date"]
                    mult = 1.0 / adj_factor
                    print(f"    - {split_date}: adjustment_factor = {adj_factor:.6f} → 株数倍率 = 1 / {adj_factor:.6f} = {mult:.6f}")
                print(f"  累積分割倍率: {split_mult:.6f}")
            else:
                print(f"  分割・併合: なし")
                print(f"  累積分割倍率: {split_mult:.6f}")
        else:
            split_mult = 1.0
            print(f"\n【4. 分割倍率計算】")
            print(f"  FY期末が不明のため、分割倍率 = 1.0（分割なしとして扱う）")
        
        # 評価日時点のネット株数
        net_shares_at_price = net_shares_fy * split_mult if pd.notna(net_shares_fy) else np.nan
        print(f"\n【5. 評価日時点のネット株数（補正後）】")
        print(f"  計算式: net_shares_at_price = net_shares_fy × split_mult")
        print(f"  = {net_shares_fy:,.0f} × {split_mult:.6f}" if pd.notna(net_shares_fy) else "  = N/A")
        print(f"  = {net_shares_at_price:,.0f}株" if pd.notna(net_shares_at_price) else "  = N/A")
        
        # 標準EPS/BPS
        print(f"\n【6. 標準EPS/BPSの計算】")
        if pd.notna(fy['profit']) and pd.notna(net_shares_at_price) and fy['profit'] > 0 and net_shares_at_price > 0:
            eps_std = fy['profit'] / net_shares_at_price
            print(f"  標準EPS = profit / net_shares_at_price")
            print(f"  = {fy['profit']:,.0f} / {net_shares_at_price:,.0f}")
            print(f"  = {eps_std:.2f}円")
        else:
            eps_std = np.nan
            print(f"  標準EPS: 計算不可（profitまたはnet_shares_at_priceが無効）")
        
        if pd.notna(fy['equity']) and pd.notna(net_shares_at_price) and fy['equity'] > 0 and net_shares_at_price > 0:
            bps_std = fy['equity'] / net_shares_at_price
            print(f"  標準BPS = equity / net_shares_at_price")
            print(f"  = {fy['equity']:,.0f} / {net_shares_at_price:,.0f}")
            print(f"  = {bps_std:.2f}円")
        else:
            bps_std = np.nan
            print(f"  標準BPS: 計算不可（equityまたはnet_shares_at_priceが無効）")
        
        # 予想データ
        fc_row = fc_data[fc_data["code"] == code]
        print(f"\n【7. 予想データ】")
        if fc_row.empty:
            print("  予想データ: なし")
            forecast_eps_std = np.nan
        else:
            fc = fc_row.iloc[0]
            print(f"  開示日: {fc['disclosed_date']}")
            print(f"  期間種別: {fc['type_of_current_period']}")
            print(f"  予想利益（forecast_profit）: {fc['forecast_profit']:,.0f}円" if pd.notna(fc['forecast_profit']) else "  予想利益: N/A")
            print(f"  予想EPS（forecast_eps）: {fc['forecast_eps']:.2f}円" if pd.notna(fc['forecast_eps']) else "  予想EPS: N/A")
            
            # 標準予想EPS
            if pd.notna(fc['forecast_profit']) and pd.notna(net_shares_at_price) and fc['forecast_profit'] > 0 and net_shares_at_price > 0:
                forecast_eps_std = fc['forecast_profit'] / net_shares_at_price
                print(f"\n  標準予想EPS = forecast_profit / net_shares_at_price")
                print(f"  = {fc['forecast_profit']:,.0f} / {net_shares_at_price:,.0f}")
                print(f"  = {forecast_eps_std:.2f}円（forecast_profitベース）")
            elif pd.notna(fc['forecast_eps']) and fc['forecast_eps'] > 0:
                forecast_eps_std = fc['forecast_eps']
                print(f"\n  標準予想EPS = forecast_eps（フォールバック）")
                print(f"  = {forecast_eps_std:.2f}円（forecast_epsベース）")
            else:
                forecast_eps_std = np.nan
                print(f"\n  標準予想EPS: 計算不可")
        
        # PER/PBR/Forward PER
        print(f"\n【8. PER/PBR/Forward PERの計算】")
        if pd.notna(price_close) and pd.notna(eps_std) and eps_std > 0:
            per = price_close / eps_std
            print(f"  PER = price / eps_std")
            print(f"  = {price_close:,.2f} / {eps_std:.2f}")
            print(f"  = {per:.2f}")
        else:
            per = np.nan
            print(f"  PER: 計算不可")
        
        if pd.notna(price_close) and pd.notna(bps_std) and bps_std > 0:
            pbr = price_close / bps_std
            print(f"  PBR = price / bps_std")
            print(f"  = {price_close:,.2f} / {bps_std:.2f}")
            print(f"  = {pbr:.2f}")
        else:
            pbr = np.nan
            print(f"  PBR: 計算不可")
        
        if pd.notna(price_close) and pd.notna(forecast_eps_std) and forecast_eps_std > 0:
            forward_per = price_close / forecast_eps_std
            print(f"  Forward PER = price / forecast_eps_std")
            print(f"  = {price_close:,.2f} / {forecast_eps_std:.2f}")
            print(f"  = {forward_per:.2f}")
        else:
            forward_per = np.nan
            print(f"  Forward PER: 計算不可")
        
        # 計算結果の検証
        feat_row = feat[feat["code"] == code]
        if not feat_row.empty:
            feat_data = feat_row.iloc[0]
            print(f"\n【9. 計算結果の検証】")
            print(f"  システム計算値:")
            print(f"    PER: {feat_data.get('per'):.2f}" if pd.notna(feat_data.get('per')) else "    PER: N/A")
            print(f"    PBR: {feat_data.get('pbr'):.2f}" if pd.notna(feat_data.get('pbr')) else "    PBR: N/A")
            print(f"    Forward PER: {feat_data.get('forward_per'):.2f}" if pd.notna(feat_data.get('forward_per')) else "    Forward PER: N/A")
            print(f"  手動計算値:")
            print(f"    PER: {per:.2f}" if pd.notna(per) else "    PER: N/A")
            print(f"    PBR: {pbr:.2f}" if pd.notna(pbr) else "    PBR: N/A")
            print(f"    Forward PER: {forward_per:.2f}" if pd.notna(forward_per) else "    Forward PER: N/A")
            
            # 差分チェック
            if pd.notna(per) and pd.notna(feat_data.get('per')):
                diff_per = abs(per - feat_data.get('per'))
                if diff_per < 0.01:
                    print(f"  ✅ PER: 一致（差分: {diff_per:.6f}）")
                else:
                    print(f"  ⚠️ PER: 不一致（差分: {diff_per:.6f}）")
            
            if pd.notna(pbr) and pd.notna(feat_data.get('pbr')):
                diff_pbr = abs(pbr - feat_data.get('pbr'))
                if diff_pbr < 0.01:
                    print(f"  ✅ PBR: 一致（差分: {diff_pbr:.6f}）")
                else:
                    print(f"  ⚠️ PBR: 不一致（差分: {diff_pbr:.6f}）")
            
            if pd.notna(forward_per) and pd.notna(feat_data.get('forward_per')):
                diff_fper = abs(forward_per - feat_data.get('forward_per'))
                if diff_fper < 0.01:
                    print(f"  ✅ Forward PER: 一致（差分: {diff_fper:.6f}）")
                else:
                    print(f"  ⚠️ Forward PER: 不一致（差分: {diff_fper:.6f}）")

print(f"\n\n{'=' * 100}")
print("レポート生成完了")
print(f"{'=' * 100}")
