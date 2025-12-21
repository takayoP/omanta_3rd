#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
個別企業の財務データをAPIから取得して、欠損値の状況を確認するスクリプト
"""

import sys
from typing import Dict, Any, Optional
from datetime import datetime

from src.omanta_3rd.infra.jquants import JQuantsClient
from src.omanta_3rd.ingest.fins import fetch_financial_statements, _map_row_to_db, _normalize_code, _filter_by_disclosed_date


def _to_float(value: Any) -> Optional[float]:
    """値をfloatに変換（None/空文字はNone）"""
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def format_value(value: Any, is_float: bool = False) -> str:
    """値を表示用にフォーマット"""
    if value is None:
        return "❌ NULL"
    if is_float:
        try:
            return f"{float(value):,.0f}"
        except (ValueError, TypeError):
            return str(value)
    return str(value)


def display_row(row: Dict[str, Any], api_row: Dict[str, Any], index: int):
    """1行のデータを表示"""
    print(f"\n{'='*80}")
    print(f"【レコード {index + 1}】")
    print(f"{'='*80}")
    
    # 主キー情報
    print("\n【主キー情報】")
    print(f"  開示日 (DisclosedDate):     {format_value(api_row.get('DisclosedDate'))}")
    print(f"  銘柄コード (LocalCode):     {format_value(api_row.get('LocalCode'))} → 正規化後: {format_value(row.get('code'))}")
    print(f"  期間タイプ (TypeOfCurrentPeriod): {format_value(api_row.get('TypeOfCurrentPeriod'))}")
    print(f"  当期末 (CurrentPeriodEndDate):    {format_value(api_row.get('CurrentPeriodEndDate'))}")
    
    # 実績データ
    print("\n【実績データ】")
    print(f"  営業利益 (OperatingProfit):           {format_value(api_row.get('OperatingProfit'), is_float=True)}")
    print(f"  当期純利益 (Profit):                  {format_value(api_row.get('Profit'), is_float=True)}")
    print(f"  純資産 (Equity):                      {format_value(api_row.get('Equity'), is_float=True)}")
    print(f"  EPS (EarningsPerShare):               {format_value(api_row.get('EarningsPerShare'), is_float=True)}")
    print(f"  BVPS (BookValuePerShare):             {format_value(api_row.get('BookValuePerShare'), is_float=True)}")
    
    # 予想データ
    print("\n【予想データ（当年度）】")
    print(f"  予想営業利益 (ForecastOperatingProfit):     {format_value(api_row.get('ForecastOperatingProfit'), is_float=True)}")
    print(f"  予想利益 (ForecastProfit):                  {format_value(api_row.get('ForecastProfit'), is_float=True)}")
    print(f"  予想EPS (ForecastEarningsPerShare):         {format_value(api_row.get('ForecastEarningsPerShare'), is_float=True)}")
    
    # 次年度予想データ
    print("\n【予想データ（次年度）】")
    print(f"  次年度予想営業利益 (NextYearForecastOperatingProfit): {format_value(api_row.get('NextYearForecastOperatingProfit'), is_float=True)}")
    print(f"  次年度予想利益 (NextYearForecastProfit):              {format_value(api_row.get('NextYearForecastProfit'), is_float=True)}")
    print(f"  次年度予想EPS (NextYearForecastEarningsPerShare):     {format_value(api_row.get('NextYearForecastEarningsPerShare'), is_float=True)}")
    
    # 株数データ
    print("\n【株数データ】")
    shares_outstanding_key = "NumberOfIssuedAndOutstandingSharesAtTheEndOfFiscalYearIncludingTreasuryStock"
    treasury_key = "NumberOfTreasuryStockAtTheEndOfFiscalYear"
    print(f"  発行済株式数 ({shares_outstanding_key[:30]}...): {format_value(api_row.get(shares_outstanding_key), is_float=True)}")
    print(f"  自己株式数 ({treasury_key}): {format_value(api_row.get(treasury_key), is_float=True)}")


def display_summary(api_rows: list):
    """全体のサマリーを表示"""
    if not api_rows:
        print("\nデータが見つかりませんでした。")
        return
    
    print(f"\n{'='*80}")
    print(f"【サマリー】")
    print(f"{'='*80}")
    print(f"取得件数: {len(api_rows)}件")
    
    # 各フィールドの欠損状況を集計
    fields = {
        "主キー": [
            ("DisclosedDate", "開示日"),
            ("LocalCode", "銘柄コード"),
            ("TypeOfCurrentPeriod", "期間タイプ"),
            ("CurrentPeriodEndDate", "当期末"),
        ],
        "実績": [
            ("OperatingProfit", "営業利益"),
            ("Profit", "当期純利益"),
            ("Equity", "純資産"),
            ("EarningsPerShare", "EPS"),
            ("BookValuePerShare", "BVPS"),
        ],
        "予想（当年度）": [
            ("ForecastOperatingProfit", "予想営業利益"),
            ("ForecastProfit", "予想利益"),
            ("ForecastEarningsPerShare", "予想EPS"),
        ],
        "予想（次年度）": [
            ("NextYearForecastOperatingProfit", "次年度予想営業利益"),
            ("NextYearForecastProfit", "次年度予想利益"),
            ("NextYearForecastEarningsPerShare", "次年度予想EPS"),
        ],
    }
    
    for category, field_list in fields.items():
        print(f"\n【{category}】")
        for api_key, jp_name in field_list:
            null_count = sum(1 for row in api_rows if row.get(api_key) is None or row.get(api_key) == "")
            null_pct = (null_count / len(api_rows) * 100) if api_rows else 0
            status = "❌" if null_count > 0 else "✅"
            print(f"  {status} {jp_name}: {null_count}/{len(api_rows)}件が欠損 ({null_pct:.1f}%)")


def main():
    """メイン処理"""
    print("="*80)
    print("財務データ API 取得・欠損値確認ツール")
    print("="*80)
    
    # 企業コード入力
    code_input = input("\n企業コードを入力してください（4桁または5桁）: ").strip()
    if not code_input:
        print("エラー: 企業コードが入力されていません。")
        sys.exit(1)
    
    # コードを正規化
    normalized_code = _normalize_code(code_input)
    if not normalized_code:
        print(f"エラー: コード '{code_input}' を正規化できませんでした。")
        sys.exit(1)
    
    print(f"\n正規化後のコード: {normalized_code}")
    
    # 日付範囲の入力（オプション）
    date_from_input = input("開始日を入力してください（YYYY-MM-DD、空欄で全期間）: ").strip()
    date_to_input = input("終了日を入力してください（YYYY-MM-DD、空欄で全期間）: ").strip()
    
    date_from = date_from_input if date_from_input else None
    date_to = date_to_input if date_to_input else None
    
    if date_from:
        try:
            datetime.strptime(date_from, "%Y-%m-%d")
        except ValueError:
            print(f"エラー: 開始日の形式が正しくありません: {date_from}")
            sys.exit(1)
    
    if date_to:
        try:
            datetime.strptime(date_to, "%Y-%m-%d")
        except ValueError:
            print(f"エラー: 終了日の形式が正しくありません: {date_to}")
            sys.exit(1)
    
    print(f"\nAPIからデータを取得中...")
    print(f"  コード: {normalized_code}")
    if date_from:
        print(f"  開始日: {date_from}")
    if date_to:
        print(f"  終了日: {date_to}")
    
    try:
        client = JQuantsClient()
        
        # APIからデータを取得（フィルタリング前の生データも保持）
        api_rows = client.get_all_pages("/fins/statements", params={"code": normalized_code})
        
        if not api_rows:
            print("\n❌ データが見つかりませんでした。")
            print("  可能性のある原因:")
            print("    - 企業コードが正しくない")
            print("    - APIにデータが存在しない")
            print("    - API認証に問題がある")
            sys.exit(1)
        
        # 日付フィルタリング
        filtered_api_rows = _filter_by_disclosed_date(api_rows, date_from, date_to)
        
        if not filtered_api_rows:
            print(f"\n❌ 指定された日付範囲にデータが見つかりませんでした。")
            print(f"  全期間のデータ件数: {len(api_rows)}件")
            sys.exit(1)
        
        # サマリー表示
        display_summary(filtered_api_rows)
        
        # 詳細表示
        print(f"\n{'='*80}")
        detail_input = input(f"\n詳細を表示しますか？ (y/n, デフォルト: y): ").strip().lower()
        if detail_input != 'n':
            # データをマッピング
            mapped_rows = [_map_row_to_db(row) for row in filtered_api_rows]
            
            for i, (api_row, mapped_row) in enumerate(zip(filtered_api_rows, mapped_rows)):
                display_row(mapped_row, api_row, i)
                
                # 複数件ある場合は確認
                if i < len(filtered_api_rows) - 1:
                    continue_input = input(f"\n次のレコードを表示しますか？ (y/n, デフォルト: y): ").strip().lower()
                    if continue_input == 'n':
                        break
        
        print(f"\n{'='*80}")
        print("処理が完了しました。")
        print(f"{'='*80}")
        
    except Exception as e:
        print(f"\n❌ エラーが発生しました: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
