from tradelab.data.bars import synthetic_ohlc
from tradelab.data.feed import HistoricalFeed, SimulatedRealtimeFeed


def test_historical_feed_len():
    bars = synthetic_ohlc(30, seed=1)
    feed = HistoricalFeed(bars, symbol="SPY")
    out = list(feed)
    assert len(out) == 30
    assert out[0].symbol == "SPY"
    assert out[0].close > 0
    assert out[-1].index == 29


def test_feed_start_index():
    bars = synthetic_ohlc(20, seed=2)
    feed = HistoricalFeed(bars, start_index=10)
    out = list(feed)
    assert len(out) == 10
    assert out[0].index == 10


def test_simulated_realtime_zero_delay():
    bars = synthetic_ohlc(5, seed=4)
    feed = SimulatedRealtimeFeed(bars, delay_sec=0.0)
    assert len(list(feed)) == 5
