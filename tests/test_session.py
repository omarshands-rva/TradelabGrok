from tradelab.core.config import TradeLabConfig
from tradelab.data.bars import synthetic_ohlc
from tradelab.execution.session import TradingSession
from tradelab.strategy.momentum import MomentumStrategy


def test_paper_session():
    bars = synthetic_ohlc(60, seed=9)
    session = TradingSession(TradeLabConfig(), mode="paper")
    result = session.run(MomentumStrategy(window=10), bars, symbol="ASSET")
    assert result.mode == "paper"
    assert len(result.equity_curve) == 60


def test_live_stub_rejects():
    bars = synthetic_ohlc(30, seed=11)
    session = TradingSession(TradeLabConfig(), mode="live")
    result = session.run(MomentumStrategy(window=10), bars, symbol="ASSET")
    assert result.mode == "live"
    # stub rejects; no fills expected
    assert result.n_fills == 0
