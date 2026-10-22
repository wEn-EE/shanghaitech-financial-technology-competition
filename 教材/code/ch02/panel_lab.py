"""第2章：NumPy/pandas多资产面板实验；全部输入为人工数据。"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd


def utc_time(value) -> pd.Timestamp:
    result = pd.Timestamp(value)
    if pd.isna(result) or result.tzinfo is None:
        raise ValueError("as_of must contain a timezone")
    return result.tz_convert("UTC")


def demo_data():
    clock = pd.date_range("2025-01-06T01:30:00Z", periods=4, freq="min")
    prices = {
        "EQ_DEMO": [100.0, 101.0, 99.99, 102.0],
        "BOND_DEMO": [100.0, 100.2, 100.1, 100.3],
        "GOLD_DEMO": [2000.0, 2020.0, None, 2030.0],
        "FX_DEMO": [7.0, 7.007, 7.0, 6.993],
    }
    rows = []
    for j, (symbol, values) in enumerate(prices.items()):
        for i, value in enumerate(values):
            if value is not None:
                rows.append({
                    "source": "SYNTHETIC", "event_id": f"{symbol}-{i}",
                    "symbol": symbol, "price": value,
                    "event_time": clock[i].isoformat(),
                    "published_time": clock[i].isoformat(),
                    "available_time": (clock[i] + pd.Timedelta(seconds=j + 1)).isoformat(),
                })
    rows.append({
        "source": "SYNTHETIC", "event_id": "GOLD_DEMO-2-late",
        "symbol": "GOLD_DEMO", "price": 2025.0,
        "event_time": clock[2].isoformat(), "published_time": clock[2].isoformat(),
        "available_time": "2025-01-06T01:34:10+00:00",
    })
    assets = pd.DataFrame({
        "source": ["SYNTHETIC"] * 4, "symbol": list(prices),
        "asset_class": ["equity", "bond", "commodity", "fx"],
        "monitor_weight": [0.4, 0.3, 0.2, 0.1],
    })
    macro = pd.DataFrame({
        "indicator": ["CPI_DEMO", "CPI_DEMO"],
        "observation_period": ["2024-12", "2024-12"],
        "revision": [0, 1], "value": [1.9, 2.1],
        "published_time": ["2025-01-06T01:31:00Z", "2025-01-06T01:33:00Z"],
        "available_time": ["2025-01-06T01:31:02Z", "2025-01-06T01:33:20Z"],
    })
    return pd.DataFrame(rows), assets, macro, clock


def prepare_quotes(raw, assets, as_of):
    required = {"source", "event_id", "symbol", "price",
                "event_time", "published_time", "available_time"}
    if not required.issubset(raw.columns):
        raise ValueError(f"missing columns: {sorted(required - set(raw.columns))}")
    keys = ["source", "symbol"]
    if assets[keys].isna().any().any() or assets.duplicated(keys).any():
        raise ValueError("asset keys must be non-null and unique")
    cutoff = utc_time(as_of)
    q = raw.copy(deep=True).reset_index(drop=True)
    q["input_row"] = np.arange(len(q))
    bad_id = pd.Series(False, index=q.index)
    for name in ("source", "symbol", "event_id"):
        bad_id |= ~q[name].map(lambda x: isinstance(x, str) and bool(x.strip()))
    bad_time = pd.Series(False, index=q.index)
    for name in ("event_time", "published_time", "available_time"):
        explicit = q[name].astype("string").str.contains(r"(?:Z|[+-]\d{2}:\d{2})$", na=False)
        q[name] = pd.to_datetime(q[name], utc=True, errors="coerce", format="ISO8601")
        bad_time |= ~explicit | q[name].isna()
    q["price_numeric"] = pd.to_numeric(q["price"], errors="coerce").astype("float64")
    bad_price = (~np.isfinite(q["price_numeric"]) | q["price_numeric"].le(0)
                 | q["price"].map(lambda x: isinstance(x, (bool, np.bool_))))
    bad_order = ~(q["event_time"].le(q["published_time"])
                  & q["published_time"].le(q["available_time"]))
    q = q.merge(assets, on=keys, how="left", validate="many_to_one", indicator=True)
    # merge保持左表行序；显式验证后使用与原输入对应的质量掩码。
    if q["input_row"].tolist() != list(range(len(raw))):
        raise RuntimeError("unexpected input row order")
    q["bad_id"], q["bad_time"], q["bad_price"] = bad_id, bad_time, bad_price
    q["bad_time_order"] = bad_order
    q["status"] = np.select(
        [bad_id, bad_time, bad_price, bad_order, q["_merge"].eq("left_only"),
         q["available_time"].gt(cutoff)],
        ["invalid_id", "invalid_time", "invalid_price", "invalid_time_order",
         "unknown_asset", "not_available"], default="accepted")
    accepted = q.loc[q["status"].eq("accepted")].copy()
    for unique_key in (["source", "event_id"], ["source", "symbol", "event_time"]):
        if accepted.duplicated(unique_key).any():
            raise ValueError(f"resolve duplicate/conflicting keys upstream: {unique_key}")
    return accepted, q


def safe_returns(current, previous):
    current = np.asarray(current, dtype="float64")
    previous = np.asarray(previous, dtype="float64")
    if current.shape != previous.shape:
        raise ValueError("price arrays must have identical shapes")
    valid = (np.isfinite(current) & np.isfinite(previous)
             & (current > 0) & (previous > 0))
    result = np.full(current.shape, np.nan, dtype="float64")
    with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
        np.divide(current, previous, out=result, where=valid)
        result -= 1.0
    if np.any(valid & ~np.isfinite(result)):
        raise FloatingPointError("return overflow on valid endpoints")
    return result


def build_panel(quotes, assets, clock, as_of, source="SYNTHETIC"):
    cutoff = utc_time(as_of)
    clock = pd.DatetimeIndex(clock)
    if clock.tz is None or not clock.is_unique or not clock.is_monotonic_increasing:
        raise ValueError("clock must be ordered, unique and timezone-aware")
    clock = clock.tz_convert("UTC")
    # 固定10秒为教学用决策延迟；不代表实测计算延迟。
    grid = clock[clock + pd.Timedelta(seconds=10) <= cutoff]
    decisions = pd.Series(grid + pd.Timedelta(seconds=10), index=grid)
    meta = assets.loc[assets["source"].eq(source)].set_index("symbol")
    if meta.empty or not meta.index.is_unique:
        raise ValueError("source requires unique asset metadata")
    q = quotes.loc[quotes["source"].eq(source)]
    if not q["event_time"].isin(clock).all():
        raise ValueError("off-grid observations require an explicit resampling rule")
    q = q.loc[q["available_time"].le(cutoff)]
    if q.empty:
        price = pd.DataFrame(np.nan, index=grid, columns=meta.index, dtype="float64")
        ready = pd.DataFrame(pd.NaT, index=grid, columns=meta.index, dtype="datetime64[ns, UTC]")
    else:
        price = q.pivot(index="event_time", columns="symbol", values="price_numeric")
        ready = q.pivot(index="event_time", columns="symbol", values="available_time")
    price = price.reindex(index=grid, columns=meta.index)
    ready = ready.reindex(index=grid, columns=meta.index).astype("datetime64[ns, UTC]")
    current_known = ready.le(decisions, axis=0)
    previous_known = ready.shift(1).le(decisions, axis=0)
    result = safe_returns(price.to_numpy(), price.shift(1).to_numpy())
    returns = pd.DataFrame(result, index=grid, columns=meta.index)
    returns = returns.where(current_known & previous_known)
    known_price = price.where(current_known)
    weights = meta["monitor_weight"].reindex(returns.columns).astype("float64")
    if (not np.isfinite(weights).all() or not weights.gt(0).all()
            or not np.isclose(weights.sum(), 1.0, rtol=0, atol=1e-12)):
        raise ValueError("demo weights must be positive and sum to one")
    monitoring = pd.DataFrame({
        "decision_time": decisions,
        "coverage": returns.notna().mul(weights, axis=1).sum(axis=1),
        "weighted_monitor_score": returns.mul(weights, axis=1).sum(
            axis=1, min_count=len(weights)),
    })
    summary = pd.DataFrame({"count": returns.count(), "mean": returns.mean(),
                            "sample_std": returns.std(ddof=1)})
    return {"prices": known_price, "returns": returns, "monitoring": monitoring,
            "summary": summary, "rolling_std": returns.rolling(3, min_periods=3).std(ddof=1)}


def macro_asof(decision_times, macro, as_of):
    cutoff = utc_time(as_of)
    decisions = pd.DatetimeIndex([utc_time(value) for value in decision_times], tz="UTC")
    if decisions.isna().any() or (decisions > cutoff).any():
        raise ValueError("queries must be valid and no later than as_of")
    m = macro.copy(deep=True)
    if (m[["indicator", "observation_period"]].isna().any().any()
            or m["indicator"].nunique() != 1 or m["observation_period"].nunique() != 1):
        raise ValueError("this demo requires one indicator and one observation period")
    for name in ("published_time", "available_time"):
        explicit = m[name].astype("string").str.contains(r"(?:Z|[+-]\d{2}:\d{2})$", na=False)
        m[name] = pd.to_datetime(m[name], utc=True, errors="coerce", format="ISO8601")
        if not explicit.all() or m[name].isna().any():
            raise ValueError("macro timestamps require explicit timezones")
    if (m["published_time"] > m["available_time"]).any():
        raise ValueError("macro acquisition predates publication")
    m["value"] = pd.to_numeric(m["value"], errors="raise")
    if not np.isfinite(m["value"]).all() or m["available_time"].duplicated().any():
        raise ValueError("macro values must be finite; acquisition ties need disambiguation")
    m = m.loc[m["available_time"].le(cutoff)].sort_values("available_time")
    revision = pd.to_numeric(m["revision"], errors="raise")
    if (not np.isfinite(revision).all() or revision.duplicated().any()
            or not revision.is_monotonic_increasing or not revision.mod(1).eq(0).all()):
        raise ValueError("resolve out-of-order or invalid revisions before this demo join")
    queries = pd.DataFrame({"decision_time": decisions, "query_id": np.arange(len(decisions))})
    result = pd.merge_asof(queries.sort_values("decision_time"), m,
                           left_on="decision_time", right_on="available_time",
                           direction="backward", allow_exact_matches=True)
    result["age"] = result["decision_time"] - result["available_time"]
    return result.sort_values("query_id").reset_index(drop=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    output = args.out or Path(__file__).parent / "runs" / datetime.now(
        timezone.utc).strftime("run_%Y%m%dT%H%M%S_%fZ")
    output.mkdir(parents=True, exist_ok=False)
    raw, assets, macro, clock = demo_data()
    for name, frame in {"raw_quotes": raw, "raw_macro": macro, "assets": assets}.items():
        frame.to_json(output / f"{name}.jsonl", orient="records", lines=True, force_ascii=False)
    cutoff = utc_time("2025-01-06T01:34:00Z")
    accepted, audit = prepare_quotes(raw, assets, cutoff)
    frames = build_panel(accepted, assets, clock, cutoff)
    frames["audit"] = audit
    frames["macro_queries"] = macro_asof([
        "2025-01-06T01:31:01Z", "2025-01-06T01:31:03Z",
        "2025-01-06T01:33:10Z", "2025-01-06T01:33:25Z"], macro, cutoff)
    for name, frame in frames.items():
        frame.to_csv(output / f"{name}.csv", encoding="utf-8-sig", index=True)
    report = {"data_kind": "synthetic", "as_of": cutoff.isoformat(),
              "python_note": "existing Anaconda interpreter",
              "numpy": np.__version__, "pandas": pd.__version__,
              "input_rows": len(raw), "status_counts": audit["status"].value_counts().to_dict(),
              "panel_shape": list(frames["returns"].shape),
              "valid_returns": frames["returns"].count().to_dict()}
    (output / "manifest.json").write_text(json.dumps(report, ensure_ascii=False,
                                                     indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False))
    print(f"Artifacts: {output.resolve()}")


if __name__ == "__main__":
    main()
