"""JSONL journal for fills, equity ticks, and session events.

Own-capital audit trail. Append-only; safe to tail from ops scripts.
Write failures are logged and swallowed so trading is never aborted by I/O.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Optional, Union

from tradelab.core.types import Fill, Side

log = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class SessionRecord:
    session_id: str
    mode: str  # paper | live
    strategy: str
    symbol: str
    started_at: str
    starting_cash: float
    config_snapshot: dict[str, Any] = field(default_factory=dict)


class Journal:
    def __init__(self, path: Union[str, Path]) -> None:
        self.path = Path(path)
        self._disabled = False
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            if not self.path.exists():
                self.path.touch()
        except OSError as exc:
            log.warning("Journal path unusable (%s): %s — journaling disabled", self.path, exc)
            self._disabled = True

    def _write(self, event: str, payload: dict[str, Any]) -> None:
        if self._disabled:
            return
        row = {"ts": _now(), "event": event, **payload}
        try:
            with self.path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(row, default=str) + "\n")
        except OSError as exc:
            log.warning("Journal write failed (%s): %s — disabling further writes", self.path, exc)
            self._disabled = True

    def session_start(self, rec: SessionRecord) -> None:
        self._write("session_start", asdict(rec))

    def session_end(self, session_id: str, *, equity: float, reason: str = "completed") -> None:
        self._write(
            "session_end",
            {"session_id": session_id, "equity": equity, "reason": reason},
        )

    def fill(self, session_id: str, fill: Fill) -> None:
        self._write(
            "fill",
            {
                "session_id": session_id,
                "symbol": fill.symbol,
                "side": fill.side.value if isinstance(fill.side, Side) else str(fill.side),
                "qty": fill.qty,
                "price": fill.price,
                "commission": fill.commission,
                "slippage_bps": fill.slippage_bps,
                "order_tag": fill.order_tag,
                "fill_ts": fill.ts.isoformat() if fill.ts else None,
            },
        )

    def reject(self, session_id: str, *, reasons: list[str], side: str, qty: float) -> None:
        self._write(
            "reject",
            {"session_id": session_id, "reasons": reasons, "side": side, "qty": qty},
        )

    def equity_tick(self, session_id: str, equity: float, *, bar_i: int) -> None:
        self._write(
            "equity",
            {"session_id": session_id, "equity": equity, "bar_i": bar_i},
        )

    def kill(self, session_id: str, reason: str) -> None:
        self._write("kill", {"session_id": session_id, "reason": reason})

    def heartbeat(self, session_id: str, *, equity: float, connected: bool) -> None:
        self._write(
            "heartbeat",
            {"session_id": session_id, "equity": equity, "connected": connected},
        )

    def iter_events(self) -> Iterator[dict[str, Any]]:
        if self._disabled or not self.path.exists():
            return
        try:
            with self.path.open(encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        yield json.loads(line)
        except OSError as exc:
            log.warning("Journal read failed: %s", exc)
            return

    def last_session_id(self) -> Optional[str]:
        sid = None
        for ev in self.iter_events():
            if ev.get("event") == "session_start":
                sid = ev.get("session_id")
        return sid
