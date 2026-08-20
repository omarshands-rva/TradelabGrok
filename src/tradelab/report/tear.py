"""Text and simple HTML tear sheets."""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Union

from tradelab.eval.metrics import PerformanceReport
from tradelab.eval.monte_carlo import PathStats
from tradelab.execution.paper import PaperResult


def print_tear(
    report: PerformanceReport,
    *,
    title: str = "TradeLab Tear Sheet",
    n_fills: Optional[int] = None,
    n_rejected: Optional[int] = None,
    monte_carlo: Optional[PathStats] = None,
) -> None:
    print(f"\n=== {title} ===")
    print(f"Total return:     {report.total_return:>10.2%}")
    print(f"CAGR:             {report.cagr:>10.2%}")
    print(f"Sharpe:           {report.sharpe:>10.3f}")
    if report.deflated_sharpe is not None:
        print(f"Deflated P(SR>0): {report.deflated_sharpe:>10.3f}")
    print(f"Sortino:          {report.sortino:>10.3f}")
    print(f"Max drawdown:     {report.max_drawdown:>10.2%}")
    print(f"Calmar:           {report.calmar:>10.3f}")
    print(f"Win rate:         {report.win_rate:>10.2%}")
    print(f"Profit factor:    {report.profit_factor:>10.2f}")
    print(f"Trades:           {report.n_trades:>10d}")
    print(f"Avg trade PnL:    {report.avg_trade:>10.2f}")
    if n_fills is not None:
        print(f"Fills:            {n_fills:>10d}")
    if n_rejected is not None:
        print(f"Rejected orders:  {n_rejected:>10d}")
    if monte_carlo is not None:
        print("--- Monte Carlo ---")
        print(f"Median final:     {monte_carlo.median_final:>10,.0f}")
        print(f"P5 final:         {monte_carlo.p5_final:>10,.0f}")
        print(f"P95 max DD:       {monte_carlo.p95_max_dd:>10.2%}")
        print(f"P(ruin <50%):     {monte_carlo.prob_ruin:>10.2%}")
    print()


def print_paper_tear(result: PaperResult, *, title: str = "Paper Run") -> None:
    print_tear(
        result.report,
        title=title,
        n_fills=len(result.fills),
        n_rejected=len(result.rejected),
    )
    snap = result.final_state
    print(f"Final cash:       {snap.cash:>10,.2f}")
    print(f"Peak equity:      {snap.peak_equity:>10,.2f}")
    if snap.kills:
        print(f"Kill reasons:     {snap.kills}")
    print()


def write_tear_html(
    report: PerformanceReport,
    path: Union[str, Path],
    *,
    title: str = "TradeLab Tear Sheet",
    equity: Optional[list[float]] = None,
) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    rows = [
        ("Total return", f"{report.total_return:.2%}"),
        ("CAGR", f"{report.cagr:.2%}"),
        ("Sharpe", f"{report.sharpe:.3f}"),
        ("Sortino", f"{report.sortino:.3f}"),
        ("Max drawdown", f"{report.max_drawdown:.2%}"),
        ("Calmar", f"{report.calmar:.3f}"),
        ("Win rate", f"{report.win_rate:.2%}"),
        ("Profit factor", f"{report.profit_factor:.2f}"),
        ("Trades", str(report.n_trades)),
        ("Avg trade", f"{report.avg_trade:.2f}"),
    ]
    if report.deflated_sharpe is not None:
        rows.insert(3, ("Deflated P(SR>0)", f"{report.deflated_sharpe:.3f}"))

    table = "\n".join(f"<tr><td>{k}</td><td style='text-align:right'>{v}</td></tr>" for k, v in rows)
    chart = ""
    if equity and len(equity) > 1:
        n = len(equity)
        mn, mx = min(equity), max(equity)
        span = (mx - mn) or 1.0
        pts = " ".join(
            f"{i * 600 / (n - 1):.1f},{120 - (e - mn) / span * 100:.1f}" for i, e in enumerate(equity)
        )
        chart = f"""
        <h3>Equity</h3>
        <svg width="620" height="140" style="background:#0d1117;border-radius:6px">
          <polyline fill="none" stroke="#3fb950" stroke-width="2" points="{pts}"/>
        </svg>
        """

    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>{title}</title>
<style>
body {{ font-family: ui-sans-serif, system-ui, sans-serif; background:#0d1117; color:#e6edf3; padding:2rem; }}
table {{ border-collapse: collapse; }}
td {{ padding: 0.4rem 1.2rem 0.4rem 0; border-bottom: 1px solid #21262d; }}
h1 {{ color:#58a6ff; }}
</style></head>
<body>
<h1>{title}</h1>
<table>{table}</table>
{chart}
</body></html>
"""
    p.write_text(html)
    return p
