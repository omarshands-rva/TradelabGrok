from tradelab.core.config import RiskConfig
from tradelab.core.types import Order, PortfolioState, Side
from tradelab.risk.engine import RiskEngine, RiskVerdict


def test_blocks_oversized_position():
    cfg = RiskConfig(max_position_pct=0.05)
    eng = RiskEngine(cfg)
    state = PortfolioState(cash=100_000.0, peak_equity=100_000.0, day_start_equity=100_000.0)
    order = Order(symbol="X", side=Side.BUY, qty=1000)  # 10% at $100
    d = eng.check(order, state, marks={"X": 100.0})
    assert d.verdict == RiskVerdict.REJECT


def test_allows_small_order():
    cfg = RiskConfig(max_position_pct=0.10)
    eng = RiskEngine(cfg)
    state = PortfolioState(cash=100_000.0, peak_equity=100_000.0, day_start_equity=100_000.0)
    order = Order(symbol="X", side=Side.BUY, qty=10)
    d = eng.check(order, state, marks={"X": 100.0})
    assert d.verdict == RiskVerdict.ALLOW
