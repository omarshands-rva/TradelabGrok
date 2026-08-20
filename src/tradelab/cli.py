"""TradeLab CLI — paper, live, eval, resume."""

from __future__ import annotations

import argparse
from pathlib import Path

from tradelab.core.config import load_config
from tradelab.data.loader import load_bars
from tradelab.eval.harness import EvaluationHarness
from tradelab.execution.session import TradingSession
from tradelab.persistence.journal import Journal
from tradelab.persistence.restore import restore_from_journal
from tradelab.report.tear import print_tear, write_tear_html
from tradelab.strategy.registry import get_strategy, list_strategies


def _add_common(p: argparse.ArgumentParser) -> None:
    p.add_argument("--config", type=Path, default=None, help="YAML config path")
    p.add_argument("--data", type=Path, default=None, help="CSV/Parquet OHLC (omit = synthetic)")
    p.add_argument("--symbol", default="ASSET", help="Symbol label")
    p.add_argument(
        "--strategy",
        default="momentum",
        choices=list_strategies(),
        help="Strategy name",
    )
    p.add_argument("--bars", type=int, default=500, help="Synthetic bar count if --data omitted")


def _load(args: argparse.Namespace):
    if getattr(args, "config", None):
        return load_config(args.config)
    for c in (
        Path("configs/default.yaml"),
        Path(__file__).resolve().parents[2] / "configs" / "default.yaml",
    ):
        if c.exists():
            return load_config(c)
    return load_config()


def _print_session(result, title: str) -> None:
    print_tear(
        result.report,
        title=title,
        n_fills=len(result.fills),
        n_rejected=len(result.rejected),
    )
    print(f"Session id:       {result.session_id}")
    print(f"Mode:             {result.mode}")
    print(f"Final cash:       {result.final_state.cash:>10,.2f}")
    print(f"Peak equity:      {result.final_state.peak_equity:>10,.2f}")
    if result.kill_reason:
        print(f"Kill reason:      {result.kill_reason}")
    if result.journal_path:
        print(f"Journal:          {result.journal_path}")
    print()


def cmd_session(args: argparse.Namespace) -> None:
    cfg = _load(args)
    mode = args.mode
    if mode == "live":
        venue = getattr(args, "venue", None) or cfg.session.live_venue
        cfg.session.live_venue = venue
        if getattr(args, "ib_enable", False):
            cfg.session.ib_enabled = True
        if getattr(args, "ib_port", None):
            cfg.session.ib_port = args.ib_port
        if getattr(args, "ib_host", None):
            cfg.session.ib_host = args.ib_host
    bars = load_bars(args.data, symbol=args.symbol, n_synthetic=args.bars)
    strategy = get_strategy(args.strategy)

    journal = None
    if not args.no_journal:
        import tempfile
        jdir = Path(args.journal_dir or cfg.session.journal_dir)
        try:
            jdir.mkdir(parents=True, exist_ok=True)
            probe = jdir / ".write_test"
            probe.write_text("ok")
            probe.unlink(missing_ok=True)
        except OSError:
            jdir = Path(tempfile.gettempdir()) / "tradelab_runs"
            jdir.mkdir(parents=True, exist_ok=True)
        journal = Journal(jdir / f"{mode}_{args.strategy}_{args.symbol}.jsonl")

    session = TradingSession(
        cfg,
        mode=mode,
        journal=journal,
        heartbeat_every=cfg.session.heartbeat_every,
    )
    result = session.run(strategy, bars, symbol=args.symbol)
    _print_session(result, title=f"{mode.upper()} · {args.strategy} · {args.symbol}")
    if args.html:
        out = Path(args.html)
        write_tear_html(result.report, out, title=f"{mode} · {args.strategy}", equity=result.equity)
        print(f"Wrote {out}")


def cmd_paper(args: argparse.Namespace) -> None:
    args.mode = "paper"
    cmd_session(args)


def cmd_live(args: argparse.Namespace) -> None:
    args.mode = "live"
    cmd_session(args)


def cmd_resume(args: argparse.Namespace) -> None:
    """Restore portfolio from journal and optionally continue from last bar."""
    restored = restore_from_journal(args.journal, session_id=args.session_id)
    print(f"Restored session {restored.session_id}")
    print(f"  mode={restored.mode} strategy={restored.strategy} symbol={restored.symbol}")
    print(f"  fills={restored.n_fills} last_bar_i={restored.last_bar_i}")
    print(f"  cash={restored.state.cash:,.2f}")
    print(f"  positions={ {s: p.qty for s, p in restored.state.positions.items() if not p.is_flat} }")
    print(f"  killed={restored.killed} ended={restored.ended}")
    if restored.kill_reason:
        print(f"  kill_reason={restored.kill_reason}")

    if not args.continue_run:
        return

    if restored.killed:
        print("Refusing to continue: session was killed. Review and reset risk manually.")
        return

    cfg = _load(args)
    symbol = args.symbol or restored.symbol or "ASSET"
    strategy_name = restored.strategy or args.strategy
    bars = load_bars(args.data, symbol=symbol, n_synthetic=args.bars)
    start = (restored.last_bar_i or 0) + 1
    if start >= len(bars):
        print(f"Nothing to continue: start_index={start} >= len(bars)={len(bars)}")
        return

    journal = Journal(args.journal)
    session = TradingSession(
        cfg,
        mode=restored.mode or "paper",
        journal=journal,
        heartbeat_every=cfg.session.heartbeat_every,
        initial_state=restored.state,
        session_id=restored.session_id,
    )
    strategy = get_strategy(strategy_name)
    result = session.run(strategy, bars, symbol=symbol, start_index=start)
    _print_session(result, title=f"RESUME · {strategy_name} · {symbol}")


def cmd_eval(args: argparse.Namespace) -> None:
    cfg = _load(args)
    if args.fast:
        cfg.eval.train_days = 120
        cfg.eval.test_days = 40
        cfg.eval.purge_days = 2
        cfg.eval.embargo_days = 2
        cfg.eval.n_monte_carlo = 200
    bars = load_bars(args.data, symbol=args.symbol, n_synthetic=args.bars)
    strategy = get_strategy(args.strategy)
    harness = EvaluationHarness(cfg)
    result = harness.run(
        strategy,
        bars,
        symbol=args.symbol,
        walk_forward=not args.no_wf,
        monte_carlo=not args.no_mc,
    )
    print(f"Folds: {len(result.folds)}")
    if result.aggregate:
        print_tear(
            result.aggregate,
            title=f"Eval · {args.strategy} · {args.symbol}",
            monte_carlo=result.monte_carlo,
        )
    if args.html and result.aggregate:
        out = Path(args.html)
        eq = result.folds[-1].equity if result.folds else None
        write_tear_html(result.aggregate, out, title=f"Eval · {args.strategy}", equity=eq)
        print(f"Wrote {out}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="tradelab",
        description="TradeLab — own capital systematic infra",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    def _session_flags(p: argparse.ArgumentParser) -> None:
        _add_common(p)
        p.add_argument("--html", type=str, default=None, help="HTML tear sheet path")
        p.add_argument("--journal-dir", type=str, default=None, help="Journal directory")
        p.add_argument("--no-journal", action="store_true", help="Disable JSONL journal")

    p_paper = sub.add_parser("paper", help="Paper session (CostModel fills)")
    _session_flags(p_paper)
    p_paper.set_defaults(func=cmd_paper)

    p_live = sub.add_parser(
        "live",
        help="Live session (stub or IB; IB requires --ib-enable + TWS)",
    )
    _session_flags(p_live)
    p_live.add_argument("--venue", choices=["stub", "ib", "unset"], default=None)
    p_live.add_argument("--ib-enable", action="store_true", help="Allow IB orders (paper port default)")
    p_live.add_argument("--ib-host", type=str, default=None)
    p_live.add_argument("--ib-port", type=int, default=None, help="7497 paper, 7496 live")
    p_live.set_defaults(func=cmd_live)

    p_resume = sub.add_parser("resume", help="Restore state from journal; optional continue")
    p_resume.add_argument("--journal", type=Path, required=True, help="Path to JSONL journal")
    p_resume.add_argument("--session-id", type=str, default=None, help="Session id (default: last)")
    p_resume.add_argument(
        "--continue",
        dest="continue_run",
        action="store_true",
        help="Continue trading from last_bar_i+1",
    )
    _add_common(p_resume)
    p_resume.set_defaults(func=cmd_resume)

    p_eval = sub.add_parser("eval", help="Walk-forward evaluation")
    _add_common(p_eval)
    p_eval.add_argument("--html", type=str, default=None)
    p_eval.add_argument("--fast", action="store_true")
    p_eval.add_argument("--no-wf", action="store_true")
    p_eval.add_argument("--no-mc", action="store_true")
    p_eval.set_defaults(func=cmd_eval)

    p_list = sub.add_parser("strategies", help="List strategies")
    p_list.set_defaults(func=lambda a: print("\n".join(list_strategies())))

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
