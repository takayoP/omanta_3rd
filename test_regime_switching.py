#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
レジーム切替機能のテストスクリプト
"""

from src.omanta_3rd.config.params_registry import load_params_by_id_longterm, get_registry_entry
from src.omanta_3rd.market.regime import get_market_regime
from src.omanta_3rd.config.regime_policy import get_params_id_for_regime
from src.omanta_3rd.infra.db import connect_db

def test_params_registry():
    """パラメータ台帳のテスト"""
    print("=" * 80)
    print("パラメータ台帳のテスト")
    print("=" * 80)
    
    try:
        params = load_params_by_id_longterm("operational_24M")
        print(f"✓ operational_24M パラメータ読み込み成功: {len(params)}個のパラメータ")
        
        entry = get_registry_entry("operational_24M")
        print(f"✓ 台帳エントリ取得成功: horizon={entry['horizon_months']}M, mode={entry['mode']}")
        
        return True
    except Exception as e:
        print(f"✗ エラー: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_regime_detection():
    """レジーム判定のテスト"""
    print()
    print("=" * 80)
    print("レジーム判定のテスト")
    print("=" * 80)
    
    try:
        with connect_db() as conn:
            regime_info = get_market_regime(conn, "2023-12-29")
            print(f"✓ レジーム判定成功: {regime_info['regime']}")
            print(f"  MA20: {regime_info.get('ma20')}")
            print(f"  MA60: {regime_info.get('ma60')}")
            print(f"  MA200: {regime_info.get('ma200')}")
            print(f"  Slope200_20: {regime_info.get('slope200_20')}")
            
            params_id = get_params_id_for_regime(regime_info['regime'])
            print(f"✓ パラメータID決定成功: {params_id}")
        
        return True
    except Exception as e:
        print(f"✗ エラー: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """メインテスト"""
    print("レジーム切替機能のテストを開始します...")
    print()
    
    result1 = test_params_registry()
    result2 = test_regime_detection()
    
    print()
    print("=" * 80)
    if result1 and result2:
        print("✓ すべてのテストが成功しました")
    else:
        print("✗ 一部のテストが失敗しました")
    print("=" * 80)

if __name__ == "__main__":
    main()













