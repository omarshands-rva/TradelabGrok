# TradeLab

**Systematic trading infrastructure — own capital only.**

## Commands

```bash
export PYTHONPATH=src

python -m tradelab.cli paper --strategy momentum --bars 400
python -m tradelab.cli eval --fast --strategy mean_reversion
python -m tradelab.cli resume --journal runs/paper_momentum_ASSET.jsonl

# Live stub (safe — no orders)
python -m tradelab.cli live --strategy momentum --bars 50

# IB paper (TWS/Gateway on 7497, API enabled)
# 1) pip install -e ".[ib]"
# 2) Start TWS paper, enable API
# 3) Explicitly enable:
python -m tradelab.cli live --venue ib --ib-enable --ib-port 7497 --strategy momentum --data path/to/spy.csv --symbol SPY
```

## Safety

IB orders require **all** of:
1. `ib_insync` installed  
2. `--ib-enable` or `session.ib_enabled: true`  
3. Connected TWS/Gateway  
4. Qualified contract  

Default port **7497 (paper)**. Live (7496) is never assumed.

## Architecture

```
BarFeed → Strategy → RiskEngine → BrokerAdapter → apply_fill → Journal
                         PaperBroker | LiveStub | IBBroker
```

## Status (v0.5)

Full paper system + resume + feeds + **complete IB adapter with safety gates**.

## License

Private — personal use only.
