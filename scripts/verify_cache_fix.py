"""キャッシュ修正の検証スクリプト

entry_score/core_scoreキャッシュ問題の修正が正しく機能しているかを確認します。
"""

import sys
import pandas as pd
import numpy as np
from pathlib import Path

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from omanta_3rd.backtest.feature_cache import FeatureCache
from omanta_3rd.jobs.optimize import _select_portfolio_with_params, EntryScoreParams
from omanta_3rd.jobs.longterm_run import StrategyParams
from omanta_3rd.infra.db import connect_db


def check_cache_no_scores():
    """チェック1: キャッシュにentry_score/core_scoreが含まれていないことを確認"""
    print("=" * 80)
    print("チェック1: キャッシュにentry_score/core_scoreが含まれていないことを確認")
    print("=" * 80)
    
    cache_dir = "cache/features"
    cache = FeatureCache(cache_dir=cache_dir)
    
    # 既存のキャッシュファイルを確認
    cache_path = cache._get_cache_path("2018-01-31", "2024-12-30")
    
    if not cache_path.exists():
        print(f"⚠️  キャッシュファイルが見つかりません: {cache_path}")
        print("   キャッシュが存在しない場合は、最適化実行時に自動的に構築されます。")
        return True
    
    print(f"キャッシュファイルを確認: {cache_path}")
    
    # キャッシュを読み込み
    try:
        features_dict = cache._load_cache("2018-01-31", "2024-12-30")
        
        if not features_dict:
            print("⚠️  キャッシュが空です")
            return False
        
        # 最初のrebalance_dateの特徴量を確認
        first_date = sorted(features_dict.keys())[0]
        feat = features_dict[first_date]
        
        print(f"\n確認対象: {first_date}")
        print(f"特徴量数: {len(feat)}")
        print(f"カラム: {list(feat.columns)}")
        
        # entry_score/core_scoreが含まれていないことを確認
        has_entry_score = "entry_score" in feat.columns
        has_core_score = "core_score" in feat.columns
        
        if has_entry_score or has_core_score:
            print(f"\n❌ エラー: キャッシュにスコア列が含まれています")
            if has_entry_score:
                print(f"   - entry_score: 含まれている")
            if has_core_score:
                print(f"   - core_score: 含まれている")
            print(f"\n   対策: キャッシュを再構築してください（--force-rebuild-cache またはキャッシュディレクトリの削除）")
            return False
        else:
            print(f"\n✓ OK: キャッシュにスコア列は含まれていません")
            return True
            
    except Exception as e:
        print(f"❌ エラー: キャッシュの読み込みに失敗しました: {e}")
        import traceback
        traceback.print_exc()
        return False


def check_entry_score_recalculation():
    """チェック2: entry_paramsを変えるとentry_scoreが変わることを確認"""
    print("\n" + "=" * 80)
    print("チェック2: entry_paramsを変えるとentry_scoreが変わることを確認")
    print("=" * 80)
    
    # テスト用のrebalance_date
    rebalance_date = "2023-01-31"
    
    # 特徴量を取得（キャッシュから、なければ直接build_featuresを呼ぶ）
    cache = FeatureCache(cache_dir="cache/features")
    try:
        # 既存のキャッシュを探す（複数の日付範囲を試す）
        cache_found = False
        feat = None
        
        # よく使われる日付範囲を試す
        date_ranges = [
            ("2018-01-31", "2024-12-30"),
            ("2020-01-31", "2024-12-30"),
            ("2022-01-31", "2024-12-30"),
            ("2023-01-31", "2024-12-30"),
        ]
        
        for start_date, end_date in date_ranges:
            try:
                features_dict = cache._load_cache(start_date, end_date)
                if rebalance_date in features_dict:
                    feat = features_dict[rebalance_date].copy()
                    cache_found = True
                    print(f"キャッシュを使用: {start_date} ～ {end_date}")
                    break
            except (FileNotFoundError, OSError) as e:
                # キャッシュが見つからない、または破損している場合はスキップ
                if isinstance(e, OSError):
                    print(f"  キャッシュが破損しています（{start_date} ～ {end_date}）: {e}")
                continue
        
        # キャッシュが見つからない場合は、直接build_featuresを呼ぶ
        if not cache_found:
            print(f"キャッシュが見つかりません。直接build_featuresを呼び出します...")
            from omanta_3rd.jobs.longterm_run import build_features
            with connect_db(read_only=True) as conn:
                feat = build_features(conn, rebalance_date)
            if feat is None or feat.empty:
                print(f"⚠️  {rebalance_date}の特徴量を取得できませんでした")
                return False
            print(f"✓ 特徴量を直接取得しました（{len(feat)}銘柄）")
        
        if feat is None or feat.empty:
            print(f"⚠️  {rebalance_date}の特徴量が空です")
            return False
        print(f"\n確認対象: {rebalance_date}")
        print(f"特徴量数: {len(feat)}")
        
        # 2つの異なるentry_paramsを用意
        params1 = EntryScoreParams(
            rsi_base=50.0,
            rsi_max=80.0,
            bb_z_base=0.0,
            bb_z_max=3.0,
            bb_weight=0.5,
            rsi_weight=0.5,
        )
        
        params2 = EntryScoreParams(
            rsi_base=30.0,
            rsi_max=70.0,
            bb_z_base=-2.0,
            bb_z_max=2.0,
            bb_weight=0.8,
            rsi_weight=0.2,
        )
        
        # デフォルトのstrategy_params
        strategy_params = StrategyParams()
        
        # 2つのparamsでentry_scoreを計算
        print("\nparams1でentry_scoreを計算...")
        portfolio1 = _select_portfolio_with_params(feat.copy(), strategy_params, params1)
        
        print("params2でentry_scoreを計算...")
        portfolio2 = _select_portfolio_with_params(feat.copy(), strategy_params, params2)
        
        if portfolio1.empty or portfolio2.empty:
            print("⚠️  ポートフォリオが空です")
            return False
        
        # entry_scoreの分布を比較
        entry_scores1 = portfolio1["entry_score"].dropna()
        entry_scores2 = portfolio2["entry_score"].dropna()
        
        print(f"\nparams1のentry_score:")
        print(f"  平均: {entry_scores1.mean():.4f}")
        print(f"  最小: {entry_scores1.min():.4f}")
        print(f"  最大: {entry_scores1.max():.4f}")
        print(f"  標準偏差: {entry_scores1.std():.4f}")
        
        print(f"\nparams2のentry_score:")
        print(f"  平均: {entry_scores2.mean():.4f}")
        print(f"  最小: {entry_scores2.min():.4f}")
        print(f"  最大: {entry_scores2.max():.4f}")
        print(f"  標準偏差: {entry_scores2.std():.4f}")
        
        # 分布が異なることを確認
        mean_diff = abs(entry_scores1.mean() - entry_scores2.mean())
        if mean_diff < 0.01:
            print(f"\n⚠️  警告: entry_scoreの平均値がほぼ同じです（差分: {mean_diff:.4f}）")
            print("   entry_paramsの違いが反映されていない可能性があります")
            return False
        else:
            print(f"\n✓ OK: entry_scoreの分布が異なります（平均値の差分: {mean_diff:.4f}）")
            print("   entry_paramsの違いが正しく反映されています")
            return True
            
    except Exception as e:
        print(f"❌ エラー: 検証に失敗しました: {e}")
        import traceback
        traceback.print_exc()
        return False


def check_deterministic():
    """チェック3: 同じparamsで再実行すると同じ結果になることを確認"""
    print("\n" + "=" * 80)
    print("チェック3: 同じparamsで再実行すると同じ結果になることを確認")
    print("=" * 80)
    
    rebalance_date = "2023-01-31"
    
    cache = FeatureCache(cache_dir="cache/features")
    try:
        # 既存のキャッシュを探す（複数の日付範囲を試す）
        cache_found = False
        feat = None
        
        date_ranges = [
            ("2018-01-31", "2024-12-30"),
            ("2020-01-31", "2024-12-30"),
            ("2022-01-31", "2024-12-30"),
            ("2023-01-31", "2024-12-30"),
        ]
        
        for start_date, end_date in date_ranges:
            try:
                features_dict = cache._load_cache(start_date, end_date)
                if rebalance_date in features_dict:
                    feat = features_dict[rebalance_date].copy()
                    cache_found = True
                    break
            except (FileNotFoundError, OSError) as e:
                # キャッシュが見つからない、または破損している場合はスキップ
                if isinstance(e, OSError):
                    print(f"  キャッシュが破損しています（{start_date} ～ {end_date}）: {e}")
                continue
        
        # キャッシュが見つからない場合は、直接build_featuresを呼ぶ
        if not cache_found:
            print(f"キャッシュが見つかりません。直接build_featuresを呼び出します...")
            from omanta_3rd.jobs.longterm_run import build_features
            with connect_db(read_only=True) as conn:
                feat = build_features(conn, rebalance_date)
            if feat is None or feat.empty:
                print(f"⚠️  {rebalance_date}の特徴量を取得できませんでした")
                return False
            print(f"✓ 特徴量を直接取得しました（{len(feat)}銘柄）")
        
        if feat is None or feat.empty:
            print(f"⚠️  {rebalance_date}の特徴量が空です")
            return False
        
        entry_params = EntryScoreParams(
            rsi_base=50.0,
            rsi_max=80.0,
            bb_z_base=0.0,
            bb_z_max=3.0,
            bb_weight=0.5,
            rsi_weight=0.5,
        )
        strategy_params = StrategyParams()
        
        # 2回実行
        print("\n1回目の実行...")
        portfolio1 = _select_portfolio_with_params(feat.copy(), strategy_params, entry_params)
        
        print("2回目の実行...")
        portfolio2 = _select_portfolio_with_params(feat.copy(), strategy_params, entry_params)
        
        if portfolio1.empty or portfolio2.empty:
            print("⚠️  ポートフォリオが空です")
            return False
        
        # 選定された銘柄コードを比較
        codes1 = set(portfolio1["code"].tolist())
        codes2 = set(portfolio2["code"].tolist())
        
        if codes1 == codes2:
            print(f"\n✓ OK: 2回の実行で同じ銘柄が選定されました（{len(codes1)}銘柄）")
            
            # entry_scoreも比較
            entry_scores1 = portfolio1.set_index("code")["entry_score"]
            entry_scores2 = portfolio2.set_index("code")["entry_score"]
            
            max_diff = (entry_scores1 - entry_scores2).abs().max()
            if max_diff < 1e-6:
                print(f"✓ OK: entry_scoreも一致しています（最大差分: {max_diff:.2e}）")
                return True
            else:
                print(f"⚠️  警告: entry_scoreに差分があります（最大差分: {max_diff:.4f}）")
                return False
        else:
            diff = codes1.symmetric_difference(codes2)
            print(f"\n❌ エラー: 2回の実行で異なる銘柄が選定されました")
            print(f"   差分: {len(diff)}銘柄")
            print(f"   例: {list(diff)[:5]}")
            return False
            
    except Exception as e:
        print(f"❌ エラー: 検証に失敗しました: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """メイン処理"""
    print("キャッシュ修正の検証を開始します...")
    print()
    
    results = []
    
    # チェック1: キャッシュにスコア列が含まれていない
    results.append(("チェック1: キャッシュにスコア列が含まれていない", check_cache_no_scores()))
    
    # チェック2: entry_paramsを変えるとentry_scoreが変わる
    results.append(("チェック2: entry_paramsを変えるとentry_scoreが変わる", check_entry_score_recalculation()))
    
    # チェック3: 同じparamsで再実行すると同じ結果になる
    results.append(("チェック3: 同じparamsで再実行すると同じ結果になる", check_deterministic()))
    
    # 結果サマリー
    print("\n" + "=" * 80)
    print("検証結果サマリー")
    print("=" * 80)
    
    all_passed = True
    for name, passed in results:
        status = "✓ PASS" if passed else "❌ FAIL"
        print(f"{status}: {name}")
        if not passed:
            all_passed = False
    
    print()
    if all_passed:
        print("✓ すべてのチェックがパスしました。修正は正しく機能しています。")
    else:
        print("❌ 一部のチェックが失敗しました。上記のエラーを確認してください。")
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())

