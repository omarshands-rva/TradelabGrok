from tradelab.data.bars import synthetic_ohlc
from tradelab.eval.harness import EvaluationHarness
from tradelab.eval.metrics import compute_metrics
from tradelab.strategy.momentum import MomentumStrategy


def test_compute_metrics_flat():
    import pandas as pd
    eq = pd.Series([100.0, 100.0, 100.0, 100.0])
    m = compute_metrics(eq)
    assert m.total_return == 0.0


def test_harness_runs():
    bars = synthetic_ohlc(120, seed=7)
    h = EvaluationHarness(train_days=40, test_days=20, purge_days=2, embargo_days=1, n_monte_carlo=50)
    result = h.run(MomentumStrategy(window=10), bars, symbol="ASSET")
    assert result.n_folds >= 1
    assert result.aggregate is not None
