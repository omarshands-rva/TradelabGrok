from tradelab.core.config import CostConfig
from tradelab.core.types import Order, Side
from tradelab.cost.model import CostModel


def test_buy_pays_spread_and_commission():
    cfg = CostConfig(spread_bps=10, slippage_bps=0, commission_per_share=0.01, commission_min=0)
    model = CostModel(cfg)
    order = Order(symbol="X", side=Side.BUY, qty=100)
    est = model.estimate(order, mid=100.0)
    assert est.fill_price > 100.0
    assert est.commission == 1.0
    fill = model.execute(order, 100.0)
    assert fill.price == est.fill_price
    assert fill.commission == est.commission


def test_sell_receives_worse_price():
    cfg = CostConfig(spread_bps=10, slippage_bps=0, commission_min=0, commission_per_share=0)
    model = CostModel(cfg)
    order = Order(symbol="X", side=Side.SELL, qty=10)
    est = model.estimate(order, mid=100.0)
    assert est.fill_price < 100.0
