"""バックテスト指標のユニットテスト（DB不要な純粋関数）"""

import math
import pytest

from omanta_3rd.backtest.metrics import (
    calculate_max_drawdown,
    calculate_sharpe_ratio,
    calculate_cagr,
    calculate_percentile,
    calculate_annualized_return_from_period,
)


# ---------------------------------------------------------------------------
# calculate_max_drawdown
# ---------------------------------------------------------------------------

class TestCalculateMaxDrawdown:
    def test_no_drawdown(self):
        """単調増加はドローダウンなし"""
        curve = [1.0, 1.1, 1.2, 1.3, 1.4]
        assert calculate_max_drawdown(curve) == pytest.approx(0.0, abs=1e-9)

    def test_simple_drawdown(self):
        """1.0 → 1.2 → 0.9 の場合、ドローダウン = (0.9-1.2)/1.2 = -25%"""
        curve = [1.0, 1.2, 0.9]
        dd = calculate_max_drawdown(curve)
        assert dd == pytest.approx(-0.25, rel=1e-4)

    def test_full_loss(self):
        curve = [1.0, 0.5, 0.0]
        dd = calculate_max_drawdown(curve)
        assert dd == pytest.approx(-1.0, rel=1e-4)

    def test_empty_returns_zero(self):
        assert calculate_max_drawdown([]) == pytest.approx(0.0)

    def test_single_element_returns_zero(self):
        assert calculate_max_drawdown([1.0]) == pytest.approx(0.0)

    def test_recovery_takes_max(self):
        """複数のドローダウンのうち最大を返す"""
        curve = [1.0, 0.8, 1.0, 0.7, 1.0]
        dd = calculate_max_drawdown(curve)
        # 最大ドローダウンは 1.0 → 0.7 = -30%
        assert dd == pytest.approx(-0.3, rel=1e-4)


# ---------------------------------------------------------------------------
# calculate_sharpe_ratio
# ---------------------------------------------------------------------------

class TestCalculateSharpeRatio:
    def test_positive_sharpe(self):
        # ばらつきのある正のリターン列
        monthly_returns = [0.01 + (i % 3) * 0.01 for i in range(24)]
        sharpe = calculate_sharpe_ratio(monthly_returns)
        assert sharpe is not None
        assert sharpe > 0

    def test_single_element_returns_none(self):
        """要素1つは計算不能 → None"""
        sharpe = calculate_sharpe_ratio([0.01])
        assert sharpe is None

    def test_negative_returns_negative_sharpe(self):
        monthly_returns = [-0.01] * 24
        sharpe = calculate_sharpe_ratio(monthly_returns)
        if sharpe is not None:
            assert sharpe < 0

    def test_empty_returns_none(self):
        sharpe = calculate_sharpe_ratio([])
        assert sharpe is None


# ---------------------------------------------------------------------------
# calculate_cagr
# ---------------------------------------------------------------------------

class TestCalculateCagr:
    def test_positive_growth(self):
        """24ヶ月で2倍 → CAGR = 2^(12/24) - 1 = sqrt(2) - 1 ≈ 41.4%"""
        curve_24 = [1.0 * (2 ** (i / 24)) for i in range(25)]
        cagr = calculate_cagr(curve_24, num_months=24)
        assert cagr is not None
        assert cagr == pytest.approx(2 ** 0.5 - 1, rel=0.01)  # ≈ 41.4%

    def test_flat_curve_returns_zero(self):
        curve = [1.0] * 25
        cagr = calculate_cagr(curve, num_months=24)
        assert cagr is not None
        assert cagr == pytest.approx(0.0, abs=1e-6)

    def test_empty_curve_returns_none(self):
        assert calculate_cagr([], num_months=12) is None

    def test_zero_months_returns_none(self):
        assert calculate_cagr([1.0, 1.2], num_months=0) is None


# ---------------------------------------------------------------------------
# calculate_percentile
# ---------------------------------------------------------------------------

class TestCalculatePercentile:
    def test_median(self):
        returns = [1.0, 2.0, 3.0, 4.0, 5.0]
        assert calculate_percentile(returns, 50) == pytest.approx(3.0)

    def test_p0_is_min(self):
        returns = [1.0, 2.0, 3.0, 4.0, 5.0]
        assert calculate_percentile(returns, 0) == pytest.approx(1.0)

    def test_p100_is_max(self):
        returns = [1.0, 2.0, 3.0, 4.0, 5.0]
        assert calculate_percentile(returns, 100) == pytest.approx(5.0)

    def test_single_element(self):
        assert calculate_percentile([3.0], 50) == pytest.approx(3.0)


# ---------------------------------------------------------------------------
# calculate_annualized_return_from_period
# ---------------------------------------------------------------------------

class TestCalculateAnnualizedReturnFromPeriod:
    def test_one_year_return(self):
        """1年間で+20% → 年率20%"""
        result = calculate_annualized_return_from_period(
            total_return=0.20,
            start_date="2023-01-01",
            end_date="2024-01-01",
        )
        assert result == pytest.approx(0.20, rel=0.01)

    def test_two_year_return(self):
        """2年間で+44% → 年率約20% (1.44^0.5 - 1 ≈ 0.2)"""
        result = calculate_annualized_return_from_period(
            total_return=0.44,
            start_date="2022-01-01",
            end_date="2024-01-01",
        )
        assert result == pytest.approx(0.20, rel=0.02)

    def test_negative_return(self):
        result = calculate_annualized_return_from_period(
            total_return=-0.10,
            start_date="2023-01-01",
            end_date="2024-01-01",
        )
        assert result < 0
