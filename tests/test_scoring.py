"""スコアリングのユニットテスト"""

import sqlite3
import pytest

from omanta_3rd.strategy.scoring import calculate_core_score, calculate_entry_score


@pytest.fixture
def db():
    """インメモリSQLiteのフィクスチャ"""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE fins_statements (
            code TEXT,
            type_of_current_period TEXT,
            current_period_end TEXT,
            disclosed_date TEXT,
            profit REAL,
            forecast_profit REAL,
            equity REAL,
            eps REAL,
            forecast_eps REAL,
            bvps REAL
        );
        CREATE TABLE prices_daily (
            code TEXT,
            date TEXT,
            adj_close REAL
        );
    """)
    yield conn
    conn.close()


def _insert_fins(conn, code, period_end, disclosed_date, profit, equity,
                 forecast_profit=None, eps=None, forecast_eps=None, bvps=None):
    conn.execute(
        """INSERT INTO fins_statements
           (code, type_of_current_period, current_period_end, disclosed_date,
            profit, equity, forecast_profit, eps, forecast_eps, bvps)
           VALUES (?, 'FY', ?, ?, ?, ?, ?, ?, ?, ?)""",
        (code, period_end, disclosed_date, profit, equity,
         forecast_profit, eps, forecast_eps, bvps),
    )
    conn.commit()


def _insert_price(conn, code, date, adj_close):
    conn.execute(
        "INSERT INTO prices_daily (code, date, adj_close) VALUES (?, ?, ?)",
        (code, date, adj_close),
    )
    conn.commit()


# ---------------------------------------------------------------------------
# calculate_core_score
# ---------------------------------------------------------------------------

class TestCalculateCoreScore:
    def test_returns_positive_score(self, db):
        """正常なデータが与えられた場合、0以上のスコアを返す"""
        _insert_fins(db, "1234", "2024-03-31", "2024-05-10",
                     profit=200.0, equity=1000.0)
        _insert_fins(db, "1234", "2023-03-31", "2023-05-10",
                     profit=150.0, equity=950.0)
        score = calculate_core_score(db, "1234", "2024-06-01")
        assert score is not None
        assert score >= 0.0

    def test_high_roe_scores_higher(self, db):
        """高ROE銘柄は低ROE銘柄よりスコアが高い"""
        # 高ROE銘柄
        _insert_fins(db, "HIGH", "2024-03-31", "2024-05-10",
                     profit=400.0, equity=1000.0)  # ROE=40%
        # 低ROE銘柄
        _insert_fins(db, "LOW", "2024-03-31", "2024-05-10",
                     profit=50.0, equity=1000.0)   # ROE=5%

        score_high = calculate_core_score(db, "HIGH", "2024-06-01")
        score_low = calculate_core_score(db, "LOW", "2024-06-01")

        assert score_high is not None and score_low is not None
        assert score_high > score_low

    def test_no_data_returns_none(self, db):
        """データなしはNoneを返す"""
        score = calculate_core_score(db, "9999", "2024-06-01")
        assert score is None

    def test_zero_equity_returns_none(self, db):
        """純資産ゼロはNoneを返す"""
        _insert_fins(db, "ZERO", "2024-03-31", "2024-05-10",
                     profit=100.0, equity=0.0)
        score = calculate_core_score(db, "ZERO", "2024-06-01")
        assert score is None

    def test_score_in_valid_range(self, db):
        """スコアは0以上"""
        _insert_fins(db, "5678", "2024-03-31", "2024-05-10",
                     profit=150.0, equity=1000.0)
        score = calculate_core_score(db, "5678", "2024-06-01")
        assert score is not None
        assert score >= 0.0


# ---------------------------------------------------------------------------
# calculate_entry_score
# ---------------------------------------------------------------------------

class TestCalculateEntryScore:
    def test_returns_nonnegative_score(self, db):
        """正常データでは0以上のスコアを返す"""
        _insert_price(db, "1234", "2024-05-31", 1000.0)
        _insert_fins(db, "1234", "2024-03-31", "2024-05-10",
                     profit=100.0, equity=1000.0,
                     eps=50.0, bvps=500.0, forecast_eps=60.0)
        score = calculate_entry_score(db, "1234", "2024-06-01")
        assert score is not None
        assert score >= 0.0

    def test_no_price_returns_none(self, db):
        """株価データなしはNoneを返す"""
        _insert_fins(db, "1234", "2024-03-31", "2024-05-10",
                     profit=100.0, equity=1000.0, eps=50.0, bvps=500.0)
        score = calculate_entry_score(db, "1234", "2024-06-01")
        assert score is None

    def test_no_fins_returns_none(self, db):
        """財務データなしはNoneを返す"""
        _insert_price(db, "1234", "2024-05-31", 1000.0)
        score = calculate_entry_score(db, "1234", "2024-06-01")
        assert score is None
