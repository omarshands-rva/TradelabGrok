from tradelab.core.config import TradeLabConfig
from tradelab.data.bars import synthetic_ohlc
from tradelab.execution.paper import PaperEngine
from tradelab.strategy.momentum import MomentumStrategy


def test_paper_engine_runs():
    bars = synthetic_ohlc(80, seed=3)
    engine = PaperEngine(TradeLabConfig())
    result = engine.run(MomentumStrategy(window=10), bars, symbol="ASSET")
    assert result.session_id
    assert len(result.equity_curve) == 80
    assert result.metrics is not None
