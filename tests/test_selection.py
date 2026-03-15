"""ポートフォリオ選定のユニットテスト"""

import sqlite3
import pytest

from omanta_3rd.strategy.select import select_portfolio, apply_replacement_limit
from omanta_3rd.config.strategy import StrategyConfig


@pytest.fixture
def db():
    """インメモリSQLiteのフィクスチャ"""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE features_monthly (
            code TEXT,
            as_of_date TEXT,
            sector33 TEXT,
            core_score REAL,
            entry_score REAL,
            liquidity_60d REAL,
            market_cap REAL,
            per REAL,
            pbr REAL
        );
        CREATE TABLE listed_info (
            code TEXT,
            date TEXT,
            market_name TEXT
        );
        CREATE TABLE portfolio_monthly (
            rebalance_date TEXT,
            code TEXT
        );
    """)
    yield conn
    conn.close()


def _insert_feature(conn, code, as_of_date, sector, core_score, entry_score=0.5,
                    liquidity=500_000_000, market_cap=20_000_000_000,
                    per=15.0, pbr=1.5):
    conn.execute(
        """INSERT INTO features_monthly
           (code, as_of_date, sector33, core_score, entry_score,
            liquidity_60d, market_cap, per, pbr)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (code, as_of_date, sector, core_score, entry_score,
         liquidity, market_cap, per, pbr),
    )
    conn.commit()


# ---------------------------------------------------------------------------
# select_portfolio
# ---------------------------------------------------------------------------

class TestSelectPortfolio:
    def test_returns_list(self, db):
        _insert_feature(db, "1001", "2024-06-01", "銀行業", 0.8)
        result = select_portfolio(db, "2024-06-01")
        assert isinstance(result, list)

    # 市場フィルタなしのデフォルト設定（listed_infoが空でも動く）
    _no_market_filter = StrategyConfig(target_markets=[])

    def test_selects_stocks(self, db):
        for i in range(5):
            _insert_feature(db, f"100{i}", "2024-06-01", f"セクター{i}", 0.9 - i * 0.1)
        result = select_portfolio(db, "2024-06-01", config=self._no_market_filter)
        assert len(result) > 0

    def test_equal_weight(self, db):
        """等加重（各銘柄の重みが等しい）"""
        for i in range(4):
            _insert_feature(db, f"100{i}", "2024-06-01", "銀行業", 0.9 - i * 0.1)
        result = select_portfolio(db, "2024-06-01", config=self._no_market_filter)
        if len(result) > 1:
            weights = [item["weight"] for item in result]
            assert all(abs(w - weights[0]) < 1e-9 for w in weights)

    def test_respects_sector_limit(self, db):
        """同一セクターの銘柄数が上限を超えない"""
        config = StrategyConfig(max_stocks_per_sector=2, target_stock_count=10,
                                target_markets=[])
        for i in range(8):
            _insert_feature(db, f"100{i}", "2024-06-01", "銀行業", 0.9 - i * 0.1)
        result = select_portfolio(db, "2024-06-01", config=config)
        sector_counts = {}
        for item in result:
            s = item["sector33"]
            sector_counts[s] = sector_counts.get(s, 0) + 1
        assert all(v <= 2 for v in sector_counts.values())

    def test_respects_target_count(self, db):
        """target_stock_count を超えない"""
        config = StrategyConfig(target_stock_count=3, max_stocks_per_sector=10,
                                target_markets=[])
        for i in range(10):
            _insert_feature(db, f"10{i:02d}", "2024-06-01", f"セクター{i}", 0.9 - i * 0.05)
        result = select_portfolio(db, "2024-06-01", config=config)
        assert len(result) <= 3

    def test_no_data_returns_empty(self, db):
        result = select_portfolio(db, "2024-06-01", config=self._no_market_filter)
        assert result == []

    def test_filters_by_liquidity(self, db):
        """流動性フィルタを適用する"""
        config = StrategyConfig(min_liquidity_60d=1_000_000_000, target_markets=[])
        _insert_feature(db, "LOW", "2024-06-01", "銀行業", 0.9,
                        liquidity=100_000_000)   # 閾値以下
        _insert_feature(db, "HIGH", "2024-06-01", "証券業", 0.8,
                        liquidity=2_000_000_000)  # 閾値以上
        result = select_portfolio(db, "2024-06-01", config=config)
        codes = [item["code"] for item in result]
        assert "LOW" not in codes
        assert "HIGH" in codes

    def test_sorted_by_score(self, db):
        """スコア降順に選定される"""
        config = StrategyConfig(target_stock_count=2, max_stocks_per_sector=10,
                                target_markets=[])
        _insert_feature(db, "BEST", "2024-06-01", "銀行業", core_score=0.9)
        _insert_feature(db, "MID",  "2024-06-01", "証券業", core_score=0.6)
        _insert_feature(db, "LOW",  "2024-06-01", "保険業", core_score=0.3)
        result = select_portfolio(db, "2024-06-01", config=config)
        codes = [item["code"] for item in result]
        assert "BEST" in codes
        assert "LOW" not in codes


# ---------------------------------------------------------------------------
# apply_replacement_limit
# ---------------------------------------------------------------------------

class TestApplyReplacementLimit:
    def _portfolio(self, codes, base_score=0.8):
        return [
            {"code": c, "sector33": "銀行業", "core_score": base_score,
             "entry_score": 0.5, "weight": 1.0 / len(codes)}
            for c in codes
        ]

    def test_no_previous_no_limit(self, db):
        """前回ポートフォリオなし（全銘柄新規）→ 入替上限が適用されるが前回保有がないため制限される"""
        new = self._portfolio(["A", "B", "C"])
        # max_replacement_ratio=1.0で全入替許可
        config = StrategyConfig(max_replacement_ratio=1.0)
        result = apply_replacement_limit(db, new, "2024-05-01", config=config)
        assert len(result) == 3

    def test_within_limit_unchanged(self, db):
        """入替数が上限以内なら変更なし"""
        db.execute("INSERT INTO portfolio_monthly VALUES ('2024-05-01', 'A')")
        db.execute("INSERT INTO portfolio_monthly VALUES ('2024-05-01', 'B')")
        db.execute("INSERT INTO portfolio_monthly VALUES ('2024-05-01', 'C')")
        db.commit()
        new = self._portfolio(["A", "B", "D"])
        config = StrategyConfig(max_replacement_ratio=0.5)
        result = apply_replacement_limit(db, new, "2024-05-01", config=config)
        codes = {item["code"] for item in result}
        assert "A" in codes and "B" in codes and "D" in codes

    def test_over_limit_reduces_new(self, db):
        """入替数が上限超え → 新規追加を制限"""
        db.execute("INSERT INTO portfolio_monthly VALUES ('2024-05-01', 'A')")
        db.commit()
        new = self._portfolio(["B", "C", "D", "E"])
        config = StrategyConfig(max_replacement_ratio=0.5)
        result = apply_replacement_limit(db, new, "2024-05-01", config=config)
        # 前回保有なし（Aは新ポートフォリオにない）ので全て新規
        # 上限50%=2銘柄以下に制限
        assert len(result) <= 2

    def test_result_has_equal_weights(self, db):
        """結果は等加重に再計算される"""
        db.execute("INSERT INTO portfolio_monthly VALUES ('2024-05-01', 'A')")
        db.commit()
        new = self._portfolio(["A", "B"])
        config = StrategyConfig(max_replacement_ratio=0.9)
        result = apply_replacement_limit(db, new, "2024-05-01", config=config)
        if len(result) > 1:
            weights = [item["weight"] for item in result]
            assert all(abs(w - weights[0]) < 1e-9 for w in weights)
