# TradeLab Design

## IB go-live checklist

1. Paper-trade the strategy in TradeLab (`tradelab paper`) until satisfied.
2. Install TWS or IB Gateway **paper** account; enable API (port 7497).
3. `pip install -e ".[ib]"`
4. `session.live_venue: ib` and `ib_enabled: false` in config first — confirm connect rejects.
5. Run with `--ib-enable` on paper port only.
6. Compare fills/commissions to paper CostModel expectations.
7. Only then consider port 7496 with tiny size and tight risk limits.

## Invariants

- Risk before broker.
- IB disabled by default.
- Resume refuses continue if killed.
- Journal is append-only.

## Versions

0.1 scaffold → 0.2 paper → 0.3 session/journal → 0.4 restore/feeds → **0.5 IB adapter**
