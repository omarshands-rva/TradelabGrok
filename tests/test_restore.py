from pathlib import Path

from tradelab.core.config import TradeLabConfig
from tradelab.data.bars import synthetic_ohlc
from tradelab.execution.session import TradingSession
from tradelab.persistence.journal import Journal
from tradelab.persistence.restore import restore_from_journal
from tradelab.strategy.momentum import MomentumStrategy


def test_restore_from_journal(tmp_path: Path):
    bars = synthetic_ohlc(50, seed=5)
    jpath = tmp_path / "run.jsonl"
    journal = Journal(jpath)
    session = TradingSession(TradeLabConfig(), mode="paper", journal=journal)
    session.run(MomentumStrategy(window=10), bars, symbol="ASSET")

    restored = restore_from_journal(jpath)
    assert restored is not None
    assert restored.mode == "paper"
    assert restored.strategy == "momentum"
    assert restored.symbol == "ASSET"
