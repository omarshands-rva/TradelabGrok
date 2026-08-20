from tradelab.strategy.registry import get_strategy, list_strategies


def test_registry_lists_both():
    names = list_strategies()
    assert "momentum" in names
    assert "mean_reversion" in names


def test_get_strategy():
    s = get_strategy("momentum", window=15)
    assert s.name == "momentum"
    assert s.window == 15
    s2 = get_strategy("mean_reversion")
    assert s2.name == "mean_reversion"
