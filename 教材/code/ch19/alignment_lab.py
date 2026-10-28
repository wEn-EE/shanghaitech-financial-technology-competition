"""SYNTHETIC alignment lab; existing standard library and IANA timezone data."""
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo, TZPATH

UTC = timezone.utc


def instant(text):
    dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError("Timezone required")
    return dt.astimezone(UTC)


def local_candidates(text, zone):
    naive = datetime.fromisoformat(text)
    if naive.tzinfo is not None:
        raise ValueError("Expected local wall time without offset")
    tz = ZoneInfo(zone)
    values = set()
    for fold in (0, 1):
        local = naive.replace(tzinfo=tz, fold=fold)
        utc = local.astimezone(UTC)
        if utc.astimezone(tz).replace(tzinfo=None) == naive:
            values.add(utc)
    return sorted(values)


def local_instant(text, zone, choice=None):
    candidates = local_candidates(text, zone)
    if not candidates:
        raise ValueError("Nonexistent local time")
    if len(candidates) == 2 and choice is None:
        raise ValueError("Ambiguous local time: choose earlier or later")
    if choice not in (None, "earlier", "later"):
        raise ValueError("Invalid choice")
    return candidates[-1] if choice == "later" else candidates[0]


def sessions():
    # Deliberately tiny synthetic calendar, NOT an exchange holiday calendar.
    return [
        dict(id="AM", day="2026-10-29", start=instant("2026-10-29T01:30:00Z"),
             end=instant("2026-10-29T03:30:00Z")),
        dict(id="PM", day="2026-10-29", start=instant("2026-10-29T05:00:00Z"),
             end=instant("2026-10-29T07:00:00Z"))]


def session_at(t, calendar):
    found = [s for s in calendar if s["start"] <= t < s["end"]]
    if len(found) > 1:
        raise ValueError("Overlapping calendar intervals")
    return found[0] if found else None


def validate(rows):
    ids = set()
    for r in rows:
        if r["id"] in ids or r["available"] < r["event"]:
            raise ValueError("Duplicate ID or impossible availability")
        if r["price"] <= 0 or r["volume"] < 0:
            raise ValueError("Invalid synthetic trade")
        ids.add(r["id"])


def snapshot(rows, asset, cutoff, calendar, tolerance):
    if tolerance.total_seconds() < 0:
        raise ValueError("Negative tolerance")
    current = session_at(cutoff, calendar)
    if current is None:
        return dict(status="CLOSED", id=None, price=None, age=None)
    visible = [r for r in rows if r["asset"] == asset
               and r["available"] <= cutoff and r["event"] <= cutoff
               and current["start"] <= r["event"] < current["end"]]
    if not visible:
        return dict(status="MISSING", id=None, price=None, age=None)
    selected = max(visible, key=lambda r: (r["event"], r["seq"], r["id"]))
    age = (cutoff-selected["event"]).total_seconds()
    stale = age > tolerance.total_seconds()
    return dict(status="STALE" if stale else "LIVE", id=selected["id"],
                price=None if stale else selected["price"], age=age)


def bars(rows, asset, cutoff, calendar, width=timedelta(minutes=1)):
    if width.total_seconds() <= 0:
        raise ValueError("Positive width required")
    result = []
    for session in calendar:
        left = session["start"]
        while left < session["end"]:
            right = min(left+width, session["end"])
            if right > cutoff:
                break  # Do not label a still-open bucket as a completed bar.
            eligible = sorted(
                [r for r in rows if r["asset"] == asset and left <= r["event"] < right
                 and r["available"] <= cutoff],
                key=lambda r: (r["event"], r["seq"], r["id"]))
            prices = [r["price"] for r in eligible]
            result.append(dict(session=session["id"], left=left, right=right,
                asof=cutoff, count=len(eligible),
                open=prices[0] if prices else None, close=prices[-1] if prices else None,
                high=max(prices) if prices else None, low=min(prices) if prices else None,
                volume=sum(r["volume"] for r in eligible),
                inputs=[r["id"] for r in eligible]))
            left = right
    return result


def samples():
    base = instant("2026-10-29T01:30:00Z")
    rows = []
    def add(asset, name, event, available, price, volume, seq):
        rows.append(dict(asset=asset, id=name, event=base+timedelta(seconds=event),
                         available=base+timedelta(seconds=available), price=price,
                         volume=volume, seq=seq))
    add("EQ_DEMO", "q1", 10, 11, 100, 2, 1)
    add("EQ_DEMO", "q2", 40, 80, 102, 3, 2)  # Late arrival changes old bar.
    add("EQ_DEMO", "q3", 60, 61, 101, 4, 3)  # Exactly on next bar boundary.
    add("EQ_DEMO", "q4", 70, 71, 103, 1, 4)
    add("BOND_DEMO", "b1", 15, 16, 99, 5, 1)
    add("GOLD_DEMO", "g1", 20, 100, 2000, 1, 1)
    add("FX_DEMO", "f1", 5, 6, 7, 100, 1)
    return rows


def run():
    rows, calendar = samples(), sessions()
    validate(rows)
    base = calendar[0]["start"]
    cuts = [base+timedelta(seconds=t) for t in (60, 75, 90, 120)]
    panels = [dict(at=t, values={a:snapshot(rows,a,t,calendar,timedelta(seconds=60))
                 for a in ("EQ_DEMO","BOND_DEMO","GOLD_DEMO","FX_DEMO")}) for t in cuts]
    dst = {day:local_instant(day+"T09:30:00","America/New_York")
           for day in ("2026-03-06","2026-03-09")}
    return dict(data_kind="SYNTHETIC", input=rows, calendar=calendar,
                dst=dst, panel=panels,
                first_bar=[bars(rows,"EQ_DEMO",t,calendar)[0] for t in (cuts[0],cuts[2])])


def main():
    root=Path(__file__).parent
    out=root/"runs"/datetime.now(UTC).strftime("run_%Y%m%dT%H%M%S_%fZ")
    out.mkdir(parents=True)
    result=run()
    path=out/"results.json"
    path.write_text(json.dumps(result,default=lambda x:x.isoformat(),indent=2)+"\n",encoding="utf-8")
    manifest=dict(calendar_version="DEMO-20261029-v1", timezone_paths=list(TZPATH),
                  code_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  results_sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    # Record installed tzdata package version if the environment provides it.
    from importlib.metadata import version, PackageNotFoundError
    try:
        manifest["tzdata_package"]=version("tzdata")
    except PackageNotFoundError:
        manifest["tzdata_package"]=None
    (out/"manifest.json").write_text(json.dumps(manifest,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(dict(dst=result["dst"],first_bar=result["first_bar"]),default=str,indent=2))
    print(out.resolve())


if __name__=="__main__":
    main()
