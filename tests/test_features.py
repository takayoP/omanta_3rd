"""特徴量計算のユニットテスト（DB不要な純粋関数）"""

import math
import pytest
import numpy as np
import pandas as pd

from omanta_3rd.features.fundamentals import calculate_roe, calculate_growth_rate
from omanta_3rd.features.valuation import calculate_per, calculate_pbr, calculate_forward_per
from omanta_3rd.features.technicals import rsi_from_series, bb_zscore
from omanta_3rd.features.utils import _safe_div, _clip01, _pct_rank, _log_safe, _calc_slope


# ---------------------------------------------------------------------------
# calculate_roe
# ---------------------------------------------------------------------------

class TestCalculateRoe:
    def test_normal(self):
        assert calculate_roe(100.0, 1000.0) == pytest.approx(0.10)

    def test_negative_profit(self):
        assert calculate_roe(-50.0, 1000.0) == pytest.approx(-0.05)

    def test_zero_equity_returns_none(self):
        assert calculate_roe(100.0, 0.0) is None

    def test_none_profit_returns_none(self):
        assert calculate_roe(None, 1000.0) is None

    def test_none_equity_returns_none(self):
        assert calculate_roe(100.0, None) is None

    def test_both_none_returns_none(self):
        assert calculate_roe(None, None) is None


# ---------------------------------------------------------------------------
# calculate_growth_rate
# ---------------------------------------------------------------------------

class TestCalculateGrowthRate:
    def test_positive_growth(self):
        assert calculate_growth_rate(120.0, 100.0) == pytest.approx(0.20)

    def test_negative_growth(self):
        assert calculate_growth_rate(80.0, 100.0) == pytest.approx(-0.20)

    def test_zero_previous_returns_none(self):
        assert calculate_growth_rate(100.0, 0.0) is None

    def test_none_current_returns_none(self):
        assert calculate_growth_rate(None, 100.0) is None

    def test_none_previous_returns_none(self):
        assert calculate_growth_rate(100.0, None) is None

    def test_negative_previous_uses_abs(self):
        # (100 - (-80)) / abs(-80) = 180/80 = 2.25
        assert calculate_growth_rate(100.0, -80.0) == pytest.approx(2.25)


# ---------------------------------------------------------------------------
# calculate_per / calculate_pbr / calculate_forward_per
# ---------------------------------------------------------------------------

class TestCalculatePer:
    def test_normal(self):
        assert calculate_per(1000.0, 100.0) == pytest.approx(10.0)

    def test_zero_eps_returns_none(self):
        assert calculate_per(1000.0, 0.0) is None

    def test_none_eps_returns_none(self):
        assert calculate_per(1000.0, None) is None

    def test_negative_eps_returns_value(self):
        # 赤字でもPERは計算する
        result = calculate_per(1000.0, -50.0)
        assert result == pytest.approx(-20.0)


class TestCalculatePbr:
    def test_normal(self):
        assert calculate_pbr(500.0, 250.0) == pytest.approx(2.0)

    def test_zero_bvps_returns_none(self):
        assert calculate_pbr(500.0, 0.0) is None

    def test_none_bvps_returns_none(self):
        assert calculate_pbr(500.0, None) is None


class TestCalculateForwardPer:
    def test_normal(self):
        assert calculate_forward_per(1000.0, 80.0) == pytest.approx(12.5)

    def test_zero_forecast_eps_returns_none(self):
        assert calculate_forward_per(1000.0, 0.0) is None


# ---------------------------------------------------------------------------
# rsi_from_series / bb_zscore
# ---------------------------------------------------------------------------

class TestRsiFromSeries:
    def _make_trend(self, n=100, step=1.0):
        """単調増加の価格系列"""
        return pd.Series([100.0 + i * step for i in range(n)])

    def test_uptrend_rsi_above_50(self):
        close = self._make_trend(100, step=1.0)
        rsi = rsi_from_series(close, 14)
        assert not math.isnan(rsi)
        assert rsi > 50

    def test_flat_rsi_is_nan_or_50(self):
        """横ばいは計算不能またはNaN"""
        close = pd.Series([100.0] * 50)
        rsi = rsi_from_series(close, 14)
        # 全ての変化がゼロの場合はNaNまたは特定値
        assert math.isnan(rsi) or 0 <= rsi <= 100

    def test_rsi_bounds(self):
        close = self._make_trend(100, step=2.0)
        rsi = rsi_from_series(close, 14)
        if not math.isnan(rsi):
            assert 0 <= rsi <= 100

    def test_insufficient_data_returns_nan(self):
        close = pd.Series([100.0, 101.0, 102.0])  # n=14に対して短すぎる
        rsi = rsi_from_series(close, 14)
        assert math.isnan(rsi)


class TestBbZscore:
    def _make_series(self, n=100):
        np.random.seed(42)
        return pd.Series(100.0 + np.random.randn(n).cumsum())

    def test_returns_float(self):
        close = self._make_series(100)
        z = bb_zscore(close, 20)
        assert isinstance(z, float)

    def test_insufficient_data_returns_nan(self):
        close = pd.Series([100.0] * 5)
        z = bb_zscore(close, 20)
        assert math.isnan(z)

    def test_flat_series_returns_nan(self):
        """標準偏差ゼロの場合はNaN"""
        close = pd.Series([100.0] * 50)
        z = bb_zscore(close, 20)
        assert math.isnan(z)


# ---------------------------------------------------------------------------
# utils
# ---------------------------------------------------------------------------

class TestSafeDiv:
    def test_normal(self):
        assert _safe_div(10.0, 2.0) == pytest.approx(5.0)

    def test_zero_denominator_returns_nan(self):
        assert math.isnan(_safe_div(10.0, 0.0))

    def test_none_numerator_returns_nan(self):
        assert math.isnan(_safe_div(None, 2.0))

    def test_none_denominator_returns_nan(self):
        assert math.isnan(_safe_div(10.0, None))

    def test_nan_input_returns_nan(self):
        assert math.isnan(_safe_div(float("nan"), 2.0))


class TestClip01:
    def test_within_range(self):
        assert _clip01(0.5) == pytest.approx(0.5)

    def test_below_zero_clips_to_zero(self):
        assert _clip01(-1.0) == pytest.approx(0.0)

    def test_above_one_clips_to_one(self):
        assert _clip01(2.0) == pytest.approx(1.0)

    def test_nan_returns_nan(self):
        assert math.isnan(_clip01(float("nan")))


class TestLogSafe:
    def test_normal(self):
        assert _log_safe(math.e) == pytest.approx(1.0)

    def test_zero_returns_nan(self):
        assert math.isnan(_log_safe(0.0))

    def test_negative_returns_nan(self):
        assert math.isnan(_log_safe(-1.0))

    def test_none_returns_nan(self):
        assert math.isnan(_log_safe(None))


class TestCalcSlope:
    def test_uptrend_positive_slope(self):
        values = [1.0, 2.0, 3.0, 4.0, 5.0]
        slope = _calc_slope(values)
        assert slope > 0

    def test_downtrend_negative_slope(self):
        values = [5.0, 4.0, 3.0, 2.0, 1.0]
        slope = _calc_slope(values)
        assert slope < 0

    def test_too_few_points_returns_nan(self):
        assert math.isnan(_calc_slope([1.0, 2.0]))

    def test_with_nan_skips_nans(self):
        values = [1.0, float("nan"), 2.0, float("nan"), 3.0]
        slope = _calc_slope(values)
        assert slope > 0


class TestPctRank:
    def test_rank_order(self):
        s = pd.Series([10.0, 30.0, 20.0])
        ranks = _pct_rank(s, ascending=True)
        # 10 < 20 < 30 → ranks should be 1/3, 3/3, 2/3
        assert ranks[0] < ranks[2] < ranks[1]

    def test_descending(self):
        s = pd.Series([10.0, 30.0, 20.0])
        ranks = _pct_rank(s, ascending=False)
        assert ranks[1] < ranks[2] < ranks[0]
