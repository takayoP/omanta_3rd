"""Coreスコアの欠損値分析スクリプト"""

from src.omanta_3rd.jobs.monthly_run import build_features
from src.omanta_3rd.infra.db import connect_db
import pandas as pd
import numpy as np

as_of_date = "2025-12-26"

print("=" * 80)
print("Coreスコアの欠損値分析")
print("=" * 80)
print(f"評価日: {as_of_date}")
print()

with connect_db() as conn:
    # 特徴量を構築
    print("特徴量を構築中...")
    feat = build_features(conn, as_of_date)
    print(f"特徴量構築完了: {len(feat)}銘柄")
    print()
    
    # 欠損値がある銘柄を特定
    print("=" * 80)
    print("欠損値分析")
    print("=" * 80)
    
    # Coreスコアが欠損している銘柄（fillna前の状態を確認するため、計算ロジックを再現）
    # 各サブスコアの欠損状況を確認
    missing_analysis = []
    
    for idx, row in feat.iterrows():
        code = row["code"]
        missing_info = {
            "code": code,
            "company_name": row.get("company_name", "N/A"),
            "roe": row.get("roe"),
            "roe_missing": pd.isna(row.get("roe")),
            "forward_per": row.get("forward_per"),
            "forward_per_missing": pd.isna(row.get("forward_per")),
            "pbr": row.get("pbr"),
            "pbr_missing": pd.isna(row.get("pbr")),
            "op_growth": row.get("op_growth"),
            "op_growth_missing": pd.isna(row.get("op_growth")),
            "profit_growth": row.get("profit_growth"),
            "profit_growth_missing": pd.isna(row.get("profit_growth")),
            "market_cap": row.get("market_cap"),
            "market_cap_missing": pd.isna(row.get("market_cap")),
            "core_score": row.get("core_score"),
            # 計算に必要な元データも記録
            "profit": row.get("profit"),
            "equity": row.get("equity"),
            "forecast_profit": row.get("forecast_profit"),
            "forecast_eps": row.get("forecast_eps"),
            "operating_profit": row.get("operating_profit"),
            "forecast_operating_profit": row.get("forecast_operating_profit"),
            "shares_outstanding": row.get("shares_outstanding"),
            "treasury_shares": row.get("treasury_shares"),
            "net_shares_at_price": row.get("net_shares_at_price"),
            "price": row.get("price"),
        }
        
        # 欠損値があるかチェック
        has_missing = (
            missing_info["roe_missing"] or
            missing_info["forward_per_missing"] or
            missing_info["pbr_missing"] or
            missing_info["op_growth_missing"] or
            missing_info["profit_growth_missing"] or
            missing_info["market_cap_missing"]
        )
        
        if has_missing:
            missing_analysis.append(missing_info)
    
    print(f"欠損値がある銘柄数: {len(missing_analysis)}")
    print()
    
    if missing_analysis:
        print("=" * 80)
        print("欠損値がある銘柄の詳細分析")
        print("=" * 80)
        
        # 各銘柄について、FYデータを確認
        for info in missing_analysis:
            code = info["code"]
            print(f"\n銘柄コード: {code} ({info['company_name']})")
            print("-" * 80)
            
            # FYデータを取得
            fy_data = pd.read_sql_query(
                """
                SELECT 
                    disclosed_date,
                    type_of_current_period,
                    current_period_end,
                    operating_profit,
                    profit,
                    equity,
                    eps,
                    bvps,
                    forecast_operating_profit,
                    forecast_profit,
                    forecast_eps,
                    shares_outstanding,
                    treasury_shares
                FROM fins_statements
                WHERE code = ? 
                  AND type_of_current_period = 'FY'
                  AND current_period_end <= ?
                ORDER BY current_period_end DESC, disclosed_date DESC
                LIMIT 5
                """,
                conn,
                params=(code, as_of_date),
            )
            
            # 価格データも確認
            try:
                price_data = pd.read_sql_query(
                    """
                    SELECT date, close
                    FROM prices_daily
                    WHERE code = ? AND date <= ?
                    ORDER BY date DESC
                    LIMIT 1
                    """,
                    conn,
                    params=(code, as_of_date),
                )
                
                if price_data.empty:
                    print("  ❌ 価格データが見つかりません")
                else:
                    print(f"  ✅ 価格データ: {price_data.iloc[0]['date']}, 終値={price_data.iloc[0]['close']}")
            except Exception as e:
                print(f"  ⚠️ 価格データ取得エラー: {e}")
            
            if fy_data.empty:
                print("  ❌ FYデータが見つかりません")
            else:
                print(f"  ✅ FYデータ: {len(fy_data)}件")
                print("\n  最新のFYデータ:")
                latest = fy_data.iloc[0]
                print(f"    開示日: {latest['disclosed_date']}")
                print(f"    当期末: {latest['current_period_end']}")
                print(f"    営業利益: {latest['operating_profit']}")
                print(f"    当期純利益: {latest['profit']}")
                print(f"    純資産: {latest['equity']}")
                print(f"    EPS: {latest['eps']}")
                print(f"    BVPS: {latest['bvps']}")
                print(f"    予想営業利益: {latest['forecast_operating_profit']}")
                print(f"    予想当期純利益: {latest['forecast_profit']}")
                print(f"    予想EPS: {latest['forecast_eps']}")
                print(f"    発行済株式数: {latest['shares_outstanding']}")
                print(f"    自己株式数: {latest['treasury_shares']}")
            
            # 欠損値の原因を分析（計算ロジックに基づく詳細分析）
            print("\n  欠損値の原因分析:")
            
            # ROE欠損の原因
            if info["roe_missing"]:
                print(f"    ❌ ROE欠損")
                profit = info.get("profit")
                equity = info.get("equity")
                if pd.isna(profit):
                    print(f"      → 原因: profitが欠損 (feat内のprofit={profit})")
                    if not fy_data.empty:
                        latest = fy_data.iloc[0]
                        print(f"      → FYデータのprofit: {latest['profit']}")
                elif pd.isna(equity):
                    print(f"      → 原因: equityが欠損 (feat内のequity={equity})")
                    if not fy_data.empty:
                        latest = fy_data.iloc[0]
                        print(f"      → FYデータのequity: {latest['equity']}")
                elif equity is not None and (equity == 0 or equity <= 0):
                    print(f"      → 原因: equityが0以下 (equity={equity})")
                elif profit is not None and profit <= 0:
                    print(f"      → 原因: profitが0以下 (profit={profit})")
                else:
                    print(f"      → 原因: 不明 (profit={profit}, equity={equity})")
                    # ROE計算を試行
                    if profit is not None and equity is not None and equity > 0:
                        roe_calc = profit / equity
                        print(f"      → 計算結果: ROE = {roe_calc:.4f} (計算可能なはず)")
            
            # forward_per欠損の原因
            if info["forward_per_missing"]:
                print(f"    ❌ forward_per欠損")
                forecast_eps_std = info.get("forecast_eps")
                price = info.get("price")
                forecast_profit = info.get("forecast_profit")
                net_shares = info.get("net_shares_at_price")
                
                if pd.isna(forecast_eps_std):
                    print(f"      → 原因: forecast_eps_stdが欠損")
                    if pd.isna(forecast_profit):
                        print(f"        → forecast_profitが欠損 (forecast_profit={forecast_profit})")
                    elif pd.isna(net_shares) or net_shares <= 0:
                        print(f"        → net_shares_at_priceが欠損または0以下 (net_shares={net_shares})")
                    elif forecast_profit is not None and forecast_profit <= 0:
                        print(f"        → forecast_profitが0以下 (forecast_profit={forecast_profit})")
                    else:
                        # forecast_eps_stdを計算してみる
                        if forecast_profit is not None and net_shares is not None and net_shares > 0:
                            calc_eps = forecast_profit / net_shares
                            print(f"        → 計算可能: forecast_eps_std = {calc_eps:.2f}")
                elif pd.isna(price):
                    print(f"      → 原因: priceが欠損 (price={price})")
                elif forecast_eps_std is not None and forecast_eps_std <= 0:
                    print(f"      → 原因: forecast_eps_stdが0以下 (forecast_eps_std={forecast_eps_std})")
                else:
                    print(f"      → 原因: 不明 (forecast_eps_std={forecast_eps_std}, price={price})")
            
            # PBR欠損の原因
            if info["pbr_missing"]:
                print(f"    ❌ PBR欠損")
                # featからbps_stdを取得（featの行を直接参照）
                feat_row = feat[feat["code"] == code]
                bps_std = feat_row["bps_std"].iloc[0] if not feat_row.empty and "bps_std" in feat_row.columns else None
                price = info.get("price")
                equity = info.get("equity")
                net_shares = info.get("net_shares_at_price")
                
                if pd.isna(bps_std):
                    print(f"      → 原因: bps_stdが欠損")
                    if pd.isna(equity):
                        print(f"        → equityが欠損 (equity={equity})")
                    elif pd.isna(net_shares) or net_shares <= 0:
                        print(f"        → net_shares_at_priceが欠損または0以下 (net_shares={net_shares})")
                    elif equity is not None and equity <= 0:
                        print(f"        → equityが0以下 (equity={equity})")
                    else:
                        # bps_stdを計算してみる
                        if equity is not None and net_shares is not None and net_shares > 0:
                            calc_bps = equity / net_shares
                            print(f"        → 計算可能: bps_std = {calc_bps:.2f}")
                elif pd.isna(price):
                    print(f"      → 原因: priceが欠損 (price={price})")
                elif bps_std is not None and bps_std <= 0:
                    print(f"      → 原因: bps_stdが0以下 (bps_std={bps_std})")
                else:
                    print(f"      → 原因: 不明 (bps_std={bps_std}, price={price})")
            
            # op_growth欠損の原因
            if info["op_growth_missing"]:
                print(f"    ❌ op_growth欠損")
                operating_profit = info.get("operating_profit")
                forecast_operating_profit = info.get("forecast_operating_profit")
                if pd.isna(operating_profit):
                    print(f"      → 原因: operating_profitが欠損 (operating_profit={operating_profit})")
                elif pd.isna(forecast_operating_profit):
                    print(f"      → 原因: forecast_operating_profitが欠損 (forecast_operating_profit={forecast_operating_profit})")
                elif operating_profit is not None and operating_profit == 0:
                    print(f"      → 原因: operating_profitが0 (operating_profit={operating_profit})")
                else:
                    print(f"      → 原因: 不明 (operating_profit={operating_profit}, forecast_operating_profit={forecast_operating_profit})")
            
            # profit_growth欠損の原因
            if info["profit_growth_missing"]:
                print(f"    ❌ profit_growth欠損")
                profit = info.get("profit")
                forecast_profit = info.get("forecast_profit")
                if pd.isna(profit):
                    print(f"      → 原因: profitが欠損 (profit={profit})")
                elif pd.isna(forecast_profit):
                    print(f"      → 原因: forecast_profitが欠損 (forecast_profit={forecast_profit})")
                elif profit is not None and profit == 0:
                    print(f"      → 原因: profitが0 (profit={profit})")
                else:
                    print(f"      → 原因: 不明 (profit={profit}, forecast_profit={forecast_profit})")
            
            # market_cap欠損の原因
            if info["market_cap_missing"]:
                print(f"    ❌ market_cap欠損")
                price = info.get("price")
                net_shares = info.get("net_shares_at_price")
                shares_outstanding = info.get("shares_outstanding")
                treasury_shares = info.get("treasury_shares")
                
                if pd.isna(price):
                    print(f"      → 原因: priceが欠損 (price={price})")
                elif pd.isna(net_shares) or net_shares <= 0:
                    print(f"      → 原因: net_shares_at_priceが欠損または0以下 (net_shares={net_shares})")
                    print(f"        → shares_outstanding: {shares_outstanding}")
                    print(f"        → treasury_shares: {treasury_shares}")
                else:
                    # market_capを計算してみる
                    if price is not None and net_shares is not None and net_shares > 0:
                        calc_mcap = price * net_shares
                        print(f"        → 計算可能: market_cap = {calc_mcap:,.0f}")
                    print(f"      → 原因: 不明 (price={price}, net_shares={net_shares})")
        
        print("\n" + "=" * 80)
        print("欠損値サマリー")
        print("=" * 80)
        missing_df = pd.DataFrame(missing_analysis)
        print(f"\nROE欠損: {missing_df['roe_missing'].sum()}銘柄")
        print(f"forward_per欠損: {missing_df['forward_per_missing'].sum()}銘柄")
        print(f"PBR欠損: {missing_df['pbr_missing'].sum()}銘柄")
        print(f"op_growth欠損: {missing_df['op_growth_missing'].sum()}銘柄")
        print(f"profit_growth欠損: {missing_df['profit_growth_missing'].sum()}銘柄")
        print(f"market_cap欠損: {missing_df['market_cap_missing'].sum()}銘柄")
    else:
        print("欠損値がある銘柄はありませんでした。")

