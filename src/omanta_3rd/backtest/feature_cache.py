"""特徴量キャッシュシステム

最適化の各trialで同じ特徴量計算を繰り返さないように、
事前に全rebalance_dateの特徴量を計算してキャッシュします。
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import pandas as pd
import numpy as np
from concurrent.futures import ProcessPoolExecutor, as_completed

from ..infra.db import connect_db
from ..jobs.monthly_run import build_features


class FeatureCache:
    """特徴量キャッシュ
    
    全rebalance_dateの生特徴量を事前計算してparquetファイルに保存し、
    最適化中はキャッシュから読み込むことで高速化します。
    """
    
    def __init__(
        self,
        cache_dir: str = "cache/features",
        data_version: Optional[str] = None,
    ):
        """
        Args:
            cache_dir: キャッシュディレクトリ
            data_version: データバージョン（Noneの場合は自動計算）
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.data_version = data_version or self._compute_data_version()
    
    def _compute_data_version(self) -> str:
        """データバージョンを計算（DBの最新データのハッシュ）"""
        # 簡易版: 現在の日時ベース（実際にはDBのデータハッシュを計算すべき）
        # 本実装では、start_date/end_dateと組み合わせて一意性を確保
        return "v1"
    
    def _get_cache_path(self, start_date: str, end_date: str) -> Path:
        """キャッシュファイルのパスを取得"""
        cache_name = f"features_{start_date}_{end_date}_{self.data_version}.parquet"
        return self.cache_dir / cache_name
    
    def _get_prices_cache_path(self, start_date: str, end_date: str) -> Path:
        """価格データキャッシュのパスを取得"""
        cache_name = f"prices_{start_date}_{end_date}_{self.data_version}.parquet"
        return self.cache_dir / cache_name
    
    def _get_metadata_path(self, start_date: str, end_date: str) -> Path:
        """メタデータファイルのパスを取得"""
        cache_name = f"metadata_{start_date}_{end_date}_{self.data_version}.json"
        return self.cache_dir / cache_name
    
    def warm(
        self,
        rebalance_dates: List[str],
        n_jobs: int = -1,
        force_rebuild: bool = False,
    ) -> Tuple[Dict[str, pd.DataFrame], Dict[str, Dict[str, List[float]]]]:
        """
        全rebalance_dateの特徴量を計算してキャッシュに保存
        
        Args:
            rebalance_dates: リバランス日のリスト
            n_jobs: 並列実行数（-1でCPU数）
            force_rebuild: 既存キャッシュを無視して再構築するか
        
        Returns:
            {rebalance_date: features_df} の辞書
        """
        if not rebalance_dates:
            return {}
        
        start_date = rebalance_dates[0]
        end_date = rebalance_dates[-1]
        
        cache_path = self._get_cache_path(start_date, end_date)
        prices_cache_path = self._get_prices_cache_path(start_date, end_date)
        metadata_path = self._get_metadata_path(start_date, end_date)
        
        # 既存キャッシュを確認
        if not force_rebuild and cache_path.exists() and prices_cache_path.exists():
            print(f"[FeatureCache] 既存のキャッシュを読み込みます: {cache_path}")
            features_dict = self._load_cache(start_date, end_date)
            # 価格データも一括読み込み（効率化）
            print(f"[FeatureCache] 価格データキャッシュを読み込みます...")
            import json
            with open(prices_cache_path, "r", encoding="utf-8") as f:
                all_prices_dict = json.load(f)
            # 必要なrebalance_dateだけ抽出
            prices_dict = {
                rd: all_prices_dict[rd]
                for rd in rebalance_dates
                if rd in all_prices_dict
            }
            print(f"[FeatureCache] 価格データ読み込み完了: {len(prices_dict)}日分")
            return features_dict, prices_dict
        
        print(f"[FeatureCache] 特徴量キャッシュを構築します（{len(rebalance_dates)}日分）...")
        
        # 並列実行数の決定
        import multiprocessing as mp
        if n_jobs == -1:
            n_jobs = min(len(rebalance_dates), mp.cpu_count())
        elif n_jobs <= 0:
            n_jobs = 1
        
        # 特徴量を計算（並列化可能）
        features_dict = {}
        prices_dict = {}
        
        if n_jobs > 1 and len(rebalance_dates) > 1:
            # 並列実行
            with ProcessPoolExecutor(max_workers=n_jobs) as executor:
                futures = {
                    executor.submit(self._build_features_single, rebalance_date): rebalance_date
                    for rebalance_date in rebalance_dates
                }
                
                for future in as_completed(futures):
                    rebalance_date = futures[future]
                    try:
                        result = future.result()
                        if result is not None:
                            feat, prices = result
                            if feat is not None and not feat.empty:
                                features_dict[rebalance_date] = feat
                                prices_dict[rebalance_date] = prices
                    except Exception as e:
                        print(f"[FeatureCache] エラー ({rebalance_date}): {e}")
                        import traceback
                        traceback.print_exc()
        else:
            # 逐次実行
            for rebalance_date in rebalance_dates:
                try:
                    result = self._build_features_single(rebalance_date)
                    if result is not None:
                        feat, prices = result
                        if feat is not None and not feat.empty:
                            features_dict[rebalance_date] = feat
                            prices_dict[rebalance_date] = prices
                except Exception as e:
                    print(f"[FeatureCache] エラー ({rebalance_date}): {e}")
                    import traceback
                    traceback.print_exc()
        
        if not features_dict:
            raise RuntimeError("特徴量の計算に失敗しました")
        
        # キャッシュに保存
        print(f"[FeatureCache] キャッシュを保存します...")
        self._save_cache(features_dict, prices_dict, start_date, end_date)
        
        print(f"[FeatureCache] キャッシュ構築完了: {len(features_dict)}日分")
        
        return features_dict, prices_dict
    
    @staticmethod
    def _build_features_single(rebalance_date: str) -> Optional[tuple]:
        """単一のrebalance_dateの特徴量を計算（並列化用）"""
        try:
            with connect_db(read_only=True) as conn:
                feat = build_features(conn, rebalance_date)
            
            if feat is None or feat.empty:
                return None
            
            # 価格データも取得（entry_score計算用）
            # build_features内で使用される価格データを再取得
            price_date = feat["as_of_date"].iloc[0]
            with connect_db(read_only=True) as conn:
                prices_win = pd.read_sql_query(
                    """
                    SELECT code, date, adj_close
                    FROM prices_daily
                    WHERE date <= ?
                    ORDER BY code, date
                    """,
                    conn,
                    params=(price_date,),
                )
            
            # 各銘柄の終値系列を辞書形式で保存
            prices_dict = {}
            for code, g in prices_win.groupby("code"):
                prices_dict[code] = g["adj_close"].reset_index(drop=True).tolist()
            
            return feat, prices_dict
        except Exception as e:
            print(f"[FeatureCache._build_features_single] エラー ({rebalance_date}): {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _save_cache(
        self,
        features_dict: Dict[str, pd.DataFrame],
        prices_dict: Dict[str, Dict[str, List[float]]],
        start_date: str,
        end_date: str,
    ):
        """キャッシュを保存"""
        cache_path = self._get_cache_path(start_date, end_date)
        prices_cache_path = self._get_prices_cache_path(start_date, end_date)
        metadata_path = self._get_metadata_path(start_date, end_date)
        
        # 特徴量データを結合して保存
        all_features = []
        for rebalance_date, feat in features_dict.items():
            feat_copy = feat.copy()
            feat_copy["rebalance_date"] = rebalance_date
            all_features.append(feat_copy)
        
        if all_features:
            combined_features = pd.concat(all_features, ignore_index=True)
            # parquet保存を試行（pyarrow優先、なければfastparquet、それもなければpickle）
            try:
                combined_features.to_parquet(cache_path, index=False, engine="pyarrow")
                print(f"[FeatureCache] 特徴量キャッシュを保存（pyarrow）: {cache_path}")
            except (ImportError, ValueError):
                try:
                    combined_features.to_parquet(cache_path, index=False, engine="fastparquet")
                    print(f"[FeatureCache] 特徴量キャッシュを保存（fastparquet）: {cache_path}")
                except (ImportError, ValueError):
                    # pickle形式で保存（フォールバック）
                    import pickle
                    pickle_path = cache_path.with_suffix(".pkl")
                    with open(pickle_path, "wb") as f:
                        pickle.dump(combined_features, f)
                    print(f"[FeatureCache] 特徴量キャッシュを保存（pickle）: {pickle_path}")
                    # parquetファイルも作成（空のDataFrameで）
                    cache_path.touch()
        
        # 価格データを保存（JSON形式、圧縮なしで高速化）
        import json
        with open(prices_cache_path, "w", encoding="utf-8") as f:
            json.dump(prices_dict, f, ensure_ascii=False, separators=(',', ':'))  # コンパクト化
        print(f"[FeatureCache] 価格データキャッシュを保存: {prices_cache_path} ({len(prices_dict)}日分)")
        
        # メタデータを保存
        metadata = {
            "start_date": start_date,
            "end_date": end_date,
            "data_version": self.data_version,
            "rebalance_dates": list(features_dict.keys()),
            "num_features": len(combined_features) if all_features else 0,
        }
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
    
    def _load_cache(self, start_date: str, end_date: str) -> Dict[str, pd.DataFrame]:
        """キャッシュを読み込み"""
        cache_path = self._get_cache_path(start_date, end_date)
        pickle_path = cache_path.with_suffix(".pkl")
        
        # pickleファイルを優先（フォールバック用）
        if pickle_path.exists():
            print(f"[FeatureCache] キャッシュを読み込みます（pickle）: {pickle_path}")
            import pickle
            with open(pickle_path, "rb") as f:
                combined_features = pickle.load(f)
        elif cache_path.exists():
            print(f"[FeatureCache] キャッシュを読み込みます: {cache_path}")
            # parquet読み込みを試行
            try:
                combined_features = pd.read_parquet(cache_path, engine="pyarrow")
            except (ImportError, ValueError):
                try:
                    combined_features = pd.read_parquet(cache_path, engine="fastparquet")
                except (ImportError, ValueError):
                    raise ImportError(
                        "parquetファイルを読み込むにはpyarrowまたはfastparquetが必要です。"
                        "インストール: pip install pyarrow または pip install fastparquet"
                    )
        else:
            raise FileNotFoundError(f"キャッシュが見つかりません: {cache_path} または {pickle_path}")
        
        # rebalance_dateごとに分割
        features_dict = {}
        for rebalance_date, group in combined_features.groupby("rebalance_date"):
            feat = group.drop(columns=["rebalance_date"]).copy()
            features_dict[rebalance_date] = feat
        
        print(f"[FeatureCache] キャッシュ読み込み完了: {len(features_dict)}日分")
        
        return features_dict
    
    def get(self, rebalance_date: str, start_date: str, end_date: str) -> Optional[pd.DataFrame]:
        """
        指定日付の特徴量DataFrameを取得
        
        Args:
            rebalance_date: リバランス日
            start_date: 開始日（キャッシュファイル特定用）
            end_date: 終了日（キャッシュファイル特定用）
        
        Returns:
            特徴量DataFrame（見つからない場合はNone）
        """
        cache_path = self._get_cache_path(start_date, end_date)
        pickle_path = cache_path.with_suffix(".pkl")
        
        # pickleファイルを優先（フォールバック用）
        if pickle_path.exists():
            import pickle
            with open(pickle_path, "rb") as f:
                combined_features = pickle.load(f)
        elif cache_path.exists():
            # parquet読み込みを試行
            try:
                combined_features = pd.read_parquet(cache_path, engine="pyarrow")
            except (ImportError, ValueError):
                try:
                    combined_features = pd.read_parquet(cache_path, engine="fastparquet")
                except (ImportError, ValueError):
                    return None
        else:
            return None
        
        # 指定日付のデータを抽出
        if "rebalance_date" in combined_features.columns:
            feat = combined_features[combined_features["rebalance_date"] == rebalance_date].copy()
            if not feat.empty:
                feat = feat.drop(columns=["rebalance_date"])
                return feat
        
        return None
    
    def get_prices(self, rebalance_date: str, start_date: str, end_date: str) -> Optional[Dict[str, List[float]]]:
        """
        指定日付の価格データを取得（entry_score計算用）
        
        Args:
            rebalance_date: リバランス日
            start_date: 開始日（キャッシュファイル特定用）
            end_date: 終了日（キャッシュファイル特定用）
        
        Returns:
            {code: [adj_close, ...]} の辞書（見つからない場合はNone）
        """
        prices_cache_path = self._get_prices_cache_path(start_date, end_date)
        
        if not prices_cache_path.exists():
            return None
        
        with open(prices_cache_path, "r", encoding="utf-8") as f:
            prices_dict = json.load(f)
        
        return prices_dict.get(rebalance_date)

