"""第1章：标准库行情监控器。全部演示行情均为人工构造。"""
from __future__ import annotations

import argparse
import json
import math
from collections import Counter, deque
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable


def parse_time(value: object) -> datetime:
    if not isinstance(value, str):
        raise ValueError("timestamp must be a string")
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None or result.utcoffset() is None:
        raise ValueError("timestamp must contain a UTC offset")
    return result.astimezone(timezone.utc)


@dataclass(frozen=True)
class Quote:
    source: str
    event_id: str
    symbol: str
    event_time: datetime
    published_time: datetime
    available_time: datetime
    price: float

    def identity(self) -> tuple:
        # 重投时本次到达时间可以不同，业务内容不能改变。
        return (self.symbol, self.event_time, self.published_time, self.price)


def parse_quote(raw: str) -> Quote:
    row = json.loads(raw)
    if not isinstance(row, dict):
        raise ValueError("JSON must be an object")
    for name in ("source", "event_id", "symbol"):
        if not isinstance(row.get(name), str) or not row[name].strip():
            raise ValueError(f"{name} must be a nonempty string")
    value = row["price"]
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("price must be a JSON number")
    price = float(value)
    if not math.isfinite(price) or price <= 0:
        raise ValueError("this demo requires finite positive prices")
    event, published, available = (
        parse_time(row[name])
        for name in ("event_time", "published_time", "available_time")
    )
    if not event <= published <= available:
        raise ValueError("quote timestamps violate event <= published <= available")
    return Quote(row["source"], row["event_id"], row["symbol"],
                 event, published, available, price)


class Monitor:
    def __init__(self, window: int = 3, threshold: float = 0.015):
        if isinstance(window, bool) or not isinstance(window, int) or window < 2:
            raise ValueError("window must be an integer >= 2")
        if not math.isfinite(threshold) or threshold <= 0:
            raise ValueError("threshold must be finite and positive")
        self.window = window
        self.threshold = threshold
        self.seen: dict[tuple[str, str], tuple] = {}
        self.latest: dict[tuple[str, str], Quote] = {}
        self.returns: dict[tuple[str, str], deque[float]] = {}
        self.last_available: datetime | None = None

    def process(self, q: Quote) -> tuple[str, str, dict | None]:
        if self.last_available is not None and q.available_time < self.last_available:
            return "invalid", "input is not ordered by available_time", None
        self.last_available = q.available_time
        message_key = (q.source, q.event_id)
        old_identity = self.seen.get(message_key)
        if old_identity is not None:
            status = "duplicate" if old_identity == q.identity() else "conflict"
            return status, "existing message key", None
        asset_key = (q.source, q.symbol)
        previous = self.latest.get(asset_key)
        if previous is not None and q.event_time <= previous.event_time:
            self.seen[message_key] = q.identity()
            return "late", "event time does not advance; retained for replay", None

        r = None if previous is None else (q.price - previous.price) / previous.price
        if r is not None and not math.isfinite(r):
            return "invalid", "return overflow", None
        values = list(self.returns.get(asset_key, ()))
        if r is not None:
            values.append(r)
        values = values[-self.window:]
        n = len(values)
        mean = math.fsum(values) / n if n else None
        variance = math.fsum((x - mean) ** 2 for x in values) / (n - 1) if n >= 2 else None
        # 全部数值计算成功后再改变本资产状态。
        self.seen[message_key] = q.identity()
        self.latest[asset_key] = q
        self.returns[asset_key] = deque(values, maxlen=self.window)
        feature = {
            "source": q.source, "symbol": q.symbol, "event_id": q.event_id,
            "event_time": q.event_time.isoformat(),
            "input_available_time": q.available_time.isoformat(),
            "price": q.price, "return": r, "count": n,
            "mean": mean, "sample_std": math.sqrt(variance) if variance is not None else None,
            "warmup": n < self.window,
            "jump_alert": r is not None and abs(r) >= self.threshold,
            "rule_version": "jump-v1-demo",
        }
        return "accepted", "validated and applied", feature


def demo_lines() -> list[str]:
    base = datetime(2025, 1, 6, 1, 30, tzinfo=timezone.utc)

    def row(event_id: str, symbol: str, second: int,
            arrival: int, price: float) -> str:
        return json.dumps({
            "source": "SYNTHETIC", "event_id": event_id, "symbol": symbol,
            "event_time": (base + timedelta(seconds=second)).isoformat(),
            "published_time": (base + timedelta(seconds=second)).isoformat(),
            "available_time": (base + timedelta(seconds=arrival)).isoformat(),
            "price": price,
        }, allow_nan=False)

    return [
        row("e1", "EQ_DEMO", 0, 1, 100.0),
        row("b1", "BOND_DEMO", 0, 2, 100.0),
        row("g1", "GOLD_DEMO", 0, 3, 2000.0),
        row("f1", "FX_DEMO", 0, 4, 7.0),
        row("e2", "EQ_DEMO", 60, 61, 101.0),
        row("b2", "BOND_DEMO", 60, 62, 100.2),
        row("g2", "GOLD_DEMO", 60, 63, 2020.0),
        row("f2", "FX_DEMO", 60, 64, 7.007),
        row("e3", "EQ_DEMO", 120, 121, 99.99),
        row("e4", "EQ_DEMO", 180, 181, 102.0),
        row("e2", "EQ_DEMO", 60, 182, 101.0),
        row("e_late", "EQ_DEMO", 30, 183, 98.0),
        row("e_bad", "EQ_DEMO", 240, 241, 0.0),
        row("e2", "EQ_DEMO", 60, 242, 101.5),
        "{broken json",
    ]


def run(lines: Iterable[str], output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=False)
    monitor = Monitor()
    counts: Counter = Counter()
    latest_feature: dict[tuple[str, str], dict] = {}
    # 一个输入行对应一条审计记录；原文保留在 raw 字段中。
    with (output / "audit.jsonl").open("w", encoding="utf-8") as audit:
        for line_no, line in enumerate(lines, start=1):
            raw = line.rstrip("\r\n")
            feature = None
            try:
                q = parse_quote(raw)
                status, reason, feature = monitor.process(q)
            except (ValueError, KeyError, TypeError, OverflowError) as exc:
                status, reason = "invalid", f"{type(exc).__name__}: {exc}"
            record = {"line": line_no, "raw": raw, "status": status,
                      "reason": reason, "feature": feature}
            audit.write(json.dumps(record, ensure_ascii=False, allow_nan=False) + "\n")
            counts[status] += 1
            if feature is not None:
                latest_feature[(q.source, q.symbol)] = feature
    summary = {"data_kind": "synthetic_or_user_supplied", "counts": dict(counts),
               "latest": [latest_feature[k] for k in sorted(latest_feature)]}
    (output / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    output = args.out or Path(__file__).parent / "runs" / datetime.now(
        timezone.utc).strftime("run_%Y%m%dT%H%M%S_%fZ")
    if args.input is None:
        summary = run(demo_lines(), output)
    else:
        with args.input.open(encoding="utf-8-sig") as stream:
            summary = run(stream, output)
    print(json.dumps(summary["counts"], ensure_ascii=False, sort_keys=True))
    print(f"Artifacts: {output.resolve()}")


if __name__ == "__main__":
    main()
