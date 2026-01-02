"""最終選定候補の保有銘柄詳細情報を可視化

各リバランス期間の保有銘柄について、以下の情報を表示します：
- 購入日、売却日
- 保有株数、投資額
- 取得価格、売却価格
- 損益率（%）、損益（円）
"""

import json
import sqlite3
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib import font_manager

# 日本語フォントの設定
plt.rcParams['font.family'] = 'DejaVu Sans'

# データベースパス
DB_PATH = Path(r"C:\Users\takay\AppData\Local\omanta_3rd\db\jquants.sqlite")

# 対象のtrial_number
SELECTED_TRIALS = [96, 168, 180, 196]

# 出力ディレクトリ
OUTPUT_DIR = Path("visualizations")
OUTPUT_DIR.mkdir(exist_ok=True)


def load_json(filepath: str) -> Dict[str, Any]:
    """JSONファイルを読み込む"""
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)


def get_company_name(conn: sqlite3.Connection, code: str, date: str) -> str:
    """銘柄コードから会社名を取得"""
    df = pd.read_sql_query("""
        SELECT company_name
        FROM listed_info
        WHERE code = ? AND date <= ?
        ORDER BY date DESC
        LIMIT 1
    """, conn, params=(code, date))
    
    if not df.empty and df['company_name'].iloc[0]:
        return df['company_name'].iloc[0]
    return code


def create_holdings_table(trial_number: int, holdings_data: Dict[str, Any], output_path: Path):
    """保有銘柄の詳細情報を表形式で出力（CSV）"""
    holdings_by_period = holdings_data.get("holdings_by_period", [])
    
    all_stocks = []
    for period in holdings_by_period:
        rebalance_date = period.get("rebalance_date")
        purchase_date = period.get("purchase_date")
        sell_date = period.get("sell_date")
        
        for stock in period.get("stocks", []):
            stock_info = {
                "trial_number": trial_number,
                "rebalance_date": rebalance_date,
                "purchase_date": purchase_date,
                "sell_date": sell_date,
                "code": stock.get("code"),
                "weight": stock.get("weight", 0.0),
                "purchase_price": stock.get("purchase_price"),
                "sell_price": stock.get("sell_price"),
                "shares": stock.get("shares"),
                "investment_amount": stock.get("investment_amount"),
                "return_pct": stock.get("return_pct"),
                "profit_loss": stock.get("profit_loss"),
                "split_multiplier": stock.get("split_multiplier", 1.0),
            }
            all_stocks.append(stock_info)
    
    df = pd.DataFrame(all_stocks)
    
    # CSVとして保存
    csv_path = output_path.with_suffix('.csv')
    df.to_csv(csv_path, index=False, encoding='utf-8-sig')
    print(f"  保有銘柄詳細をCSVに保存: {csv_path}")
    
    return df


def visualize_holdings_transition(trial_number: int, holdings_data: Dict[str, Any], 
                                  conn: sqlite3.Connection, output_path: Path):
    """保有銘柄の推移を可視化（ヒートマップ風）"""
    holdings_by_period = holdings_data.get("holdings_by_period", [])
    
    if not holdings_by_period:
        print(f"  Trial #{trial_number}: データがありません")
        return
    
    # 全期間で使用された銘柄コードを取得
    all_codes = set()
    for period in holdings_by_period:
        for stock in period.get("stocks", []):
            all_codes.add(stock.get("code"))
    
    all_codes = sorted(list(all_codes))
    
    # 期間ごとのデータを構築
    period_dates = [pd.to_datetime(p.get("rebalance_date")) for p in holdings_by_period]
    period_labels = [p.get("rebalance_date") for p in holdings_by_period]
    
    # ウェイトマトリックス（期間 × 銘柄）
    weight_matrix = []
    for period in holdings_by_period:
        period_weights = {}
        for stock in period.get("stocks", []):
            period_weights[stock.get("code")] = stock.get("weight", 0.0)
        
        row = [period_weights.get(code, 0.0) for code in all_codes]
        weight_matrix.append(row)
    
    # プロット
    fig, ax = plt.subplots(figsize=(max(12, len(period_dates) * 0.5), max(8, len(all_codes) * 0.3)))
    
    im = ax.imshow(weight_matrix, aspect='auto', cmap='YlOrRd', interpolation='nearest')
    
    # 軸ラベル
    ax.set_xticks(range(len(all_codes)))
    ax.set_xticklabels(all_codes, rotation=45, ha='right', fontsize=8)
    ax.set_yticks(range(len(period_labels)))
    ax.set_yticklabels(period_labels, fontsize=8)
    
    ax.set_xlabel('銘柄コード', fontsize=10)
    ax.set_ylabel('リバランス日', fontsize=10)
    ax.set_title(f'Trial #{trial_number}: 保有銘柄の推移（ウェイト）', fontsize=12)
    
    # カラーバー
    plt.colorbar(im, ax=ax, label='ウェイト')
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    
    print(f"  保有銘柄推移グラフを保存: {output_path}")


def print_holdings_summary(trial_number: int, holdings_data: Dict[str, Any], conn: sqlite3.Connection):
    """保有銘柄のサマリーを表示"""
    holdings_by_period = holdings_data.get("holdings_by_period", [])
    initial_investment = holdings_data.get("initial_investment", 1000000.0)
    
    print(f"\n{'='*80}")
    print(f"Trial #{trial_number} - 保有銘柄サマリー")
    print(f"{'='*80}")
    print(f"初期投資額: {initial_investment:,.0f}円")
    print(f"リバランス期間数: {len(holdings_by_period)}")
    
    # 全期間の全銘柄を集計
    all_stocks_dict = {}  # {code: {count, total_return, total_profit_loss}}
    
    for period in holdings_by_period:
        for stock in period.get("stocks", []):
            code = stock.get("code")
            if code not in all_stocks_dict:
                all_stocks_dict[code] = {
                    "count": 0,
                    "total_return": 0.0,
                    "total_profit_loss": 0.0,
                    "total_investment": 0.0,
                }
            
            all_stocks_dict[code]["count"] += 1
            all_stocks_dict[code]["total_return"] += stock.get("return_pct", 0.0)
            if stock.get("profit_loss") is not None:
                all_stocks_dict[code]["total_profit_loss"] += stock.get("profit_loss", 0.0)
            if stock.get("investment_amount") is not None:
                all_stocks_dict[code]["total_investment"] += stock.get("investment_amount", 0.0)
    
    # 平均リターンでソート
    sorted_stocks = sorted(
        all_stocks_dict.items(),
        key=lambda x: x[1]["total_return"] / x[1]["count"] if x[1]["count"] > 0 else 0,
        reverse=True
    )
    
    print(f"\n保有回数の多い銘柄（上位10件）:")
    print(f"{'銘柄コード':<10} {'保有回数':<8} {'平均リターン':<12} {'総損益（円）':<15} {'総投資額（円）':<15}")
    print("-" * 80)
    
    for code, stats in sorted_stocks[:10]:
        avg_return = stats["total_return"] / stats["count"] if stats["count"] > 0 else 0.0
        company_name = get_company_name(conn, code, "2024-12-31")
        print(f"{code:<10} {stats['count']:<8} {avg_return:>10.2f}% {stats['total_profit_loss']:>14,.0f} {stats['total_investment']:>14,.0f}  {company_name}")
    
    # 期間ごとの詳細（最初の3期間のみ）
    print(f"\n各リバランス期間の詳細（最初の3期間）:")
    for i, period in enumerate(holdings_by_period[:3]):
        print(f"\n期間 {i+1}: {period.get('rebalance_date')} (購入: {period.get('purchase_date')}, 売却: {period.get('sell_date')})")
        print(f"{'銘柄コード':<10} {'ウェイト':<8} {'購入価格':<10} {'売却価格':<10} {'リターン':<10} {'損益（円）':<12}")
        print("-" * 70)
        
        stocks_sorted = sorted(
            period.get("stocks", []),
            key=lambda x: x.get("return_pct", 0.0),
            reverse=True
        )
        
        for stock in stocks_sorted:
            code = stock.get("code")
            weight = stock.get("weight", 0.0)
            purchase_price = stock.get("purchase_price")
            sell_price = stock.get("sell_price")
            return_pct = stock.get("return_pct", 0.0)
            profit_loss = stock.get("profit_loss")
            
            purchase_str = f"{purchase_price:.0f}" if purchase_price else "N/A"
            sell_str = f"{sell_price:.0f}" if sell_price else "N/A"
            profit_str = f"{profit_loss:,.0f}" if profit_loss is not None else "N/A"
            
            company_name = get_company_name(conn, code, period.get("sell_date", "2024-12-31"))
            print(f"{code:<10} {weight:>7.3f} {purchase_str:>10} {sell_str:>10} {return_pct:>9.2f}% {profit_str:>12}  {company_name}")


def main():
    """メイン処理"""
    print("保有銘柄の詳細情報を可視化します...\n")
    
    # JSONファイルを読み込み（新しいファイルを優先）
    json_files = [
        ("holdout_results_with_holdings.json", "holdout_2023_2024"),
        ("holdout_2025_live_10bps.json", "holdout_2025"),
    ]
    
    # 新しいファイルが存在しない場合は、古いファイルも試す
    import os
    if not os.path.exists("holdout_results_with_holdings.json"):
        json_files.insert(0, ("holdout_results_studyB_20251231_174014.json", "holdout_2023_2024"))
    
    with sqlite3.connect(str(DB_PATH)) as conn:
        for json_file, period_name in json_files:
            json_path = Path(json_file)
            if not json_path.exists():
                print(f"ファイルが見つかりません: {json_file}")
                continue
            
            print(f"\n{'='*80}")
            print(f"期間: {period_name}")
            print(f"ファイル: {json_file}")
            print(f"{'='*80}\n")
            
            data = load_json(str(json_path))
            results = data.get("results", [])
            
            for result in results:
                trial_number = result.get("trial_number")
                if trial_number not in SELECTED_TRIALS:
                    continue
                
                portfolio_holdings = result.get("portfolio_holdings")
                if not portfolio_holdings:
                    print(f"Trial #{trial_number}: portfolio_holdingsデータがありません")
                    continue
                
                # 出力パス
                output_base = OUTPUT_DIR / f"holdings_trial{trial_number}_{period_name}"
                
                # CSVとして保存
                df = create_holdings_table(trial_number, portfolio_holdings, output_base)
                
                # グラフを生成
                graph_path = output_base.with_suffix('.png')
                visualize_holdings_transition(trial_number, portfolio_holdings, conn, graph_path)
                
                # サマリーを表示
                print_holdings_summary(trial_number, portfolio_holdings, conn)
    
    print(f"\n{'='*80}")
    print("可視化が完了しました！")
    print(f"出力ディレクトリ: {OUTPUT_DIR}")
    print(f"{'='*80}\n")


if __name__ == "__main__":
    main()

