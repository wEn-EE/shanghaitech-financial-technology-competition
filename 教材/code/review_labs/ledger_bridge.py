"""Replay one versioned synthetic ledger through chapters 17–21."""
from contextlib import closing
from datetime import datetime, timedelta, timezone
import json
import math
from pathlib import Path
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / f"ch{i:02d}") for i in range(17, 22)]
import model_lab
import cleaning_lab
import alignment_lab
import pit_lab
import features_lab

BASE = datetime(2026, 11, 2, 1, 30, tzinfo=timezone.utc)
ASSETS = features_lab.ASSETS


def instant(second):
    return BASE + timedelta(seconds=second)


def ledger(db):
    model_lab.initialize(db)

    def deliver(key, kind, body, t, seen, revision=1):
        timestamp = instant(t).isoformat()
        obj = dict(schema_version=1, event_key=key, revision=revision, kind=kind,
                   event_time=timestamp, published_at=timestamp, body=body)
        assert model_lab.ingest(db,"DEMO",model_lab.dump(obj).encode(),
                                instant(seen).isoformat())=="ACCEPTED"

    for t in range(10):
        for i, asset in enumerate(ASSETS):
            price = (110 if t == 4 else 100+t) if i == 0 else (99+t,2000+t,7+t/100)[i-1]
            body = dict(symbol=asset,unit=cleaning_lab.UNITS[asset],price=str(price),quantity=1)
            deliver(f"{asset}-{t}","quote",body,60*t+10,60*t+11)
        if t in (2, 7):
            body = dict(series_id="CPI_YOY_DEMO",period="2026-10",unit="percent",
                        value="2.30" if t==2 else "2.10")
            deliver("CPI_YOY_DEMO:2026-10","macro",body,60*t+20,60*t+22,1 if t==2 else 2)
    body=dict(symbol="EQ_DEMO",unit=cleaning_lab.UNITS["EQ_DEMO"],price="104",quantity=1)
    # Provider corrects the original observation. Source event clock is unchanged.
    deliver("EQ_DEMO-4","quote",body,250,620,2)


def quote_snapshot(db, cutoff):
    return db.execute("""
        WITH versions AS (
            SELECT e.*, ROW_NUMBER() OVER (
              PARTITION BY source_id,event_key ORDER BY revision DESC) AS rn
            FROM event e WHERE kind='quote' AND available_us<=?
        ) SELECT * FROM versions WHERE rn=1 ORDER BY event_us,event_key
    """,(model_lab.time_us(instant(cutoff).isoformat()),)).fetchall()


def replay(db, cutoff):
    source, rows = {}, []
    for row in quote_snapshot(db, cutoff):
        obj=json.loads(row["canonical_json"])
        b=obj["body"]
        event=datetime.fromtimestamp(row["event_us"]/1e6,timezone.utc)
        available=datetime.fromtimestamp(row["available_us"]/1e6,timezone.utc)
        t=int((event-BASE).total_seconds())//60
        asset=b["instrument_id"]
        # Chapter 18 has an ordered local clock. All inputs already passed cutoff.
        # Historical bucket order here is a replay order, never original availability.
        rows.append(dict(asset=asset,t=t,available=t,price=b["price_atoms"]/10**b["scale"],unit=b["unit"]))
        source[(asset,t)] = dict(id=row["event_uid"], event=event, available=available,
                                seq=row["revision"], volume=b["quantity"], asset=asset)
    cleaned=cleaning_lab.clean(rows)
    trades=[dict(source[(r["asset"],r["t"])],price=r["raw_price"])
            for r in cleaned["output"] if r["raw_price"] is not None]
    alignment_lab.validate(trades)
    calendar=[dict(id="DEMO",start=BASE,end=instant(600))]
    input_bars=[]
    lineage={}
    for asset in ASSETS:
        for t,bar in enumerate(alignment_lab.bars(trades,asset,instant(cutoff),calendar)):
            identifier=f"{asset}:{t}:asof:{cutoff}"
            input_bars.append(dict(id=identifier,asset=asset,t=t,ready=t+1,
                                   price=bar["close"],bid=None,ask=None,notional=0))
            lineage[identifier]=bar["inputs"]
    # ready=t+1 is Engine's local replay index. The published view uses the snapshot cutoff.
    features=[dict(row, snapshot_ready_seconds=cutoff)
              for row in features_lab.panel(input_bars)]
    return {"snapshot_ready_seconds":cutoff, "features":features,
            "bar_to_event":lineage, "clean_audit":cleaned["audit"]}


def macro_versions(db):
    with closing(pit_lab.new_db()) as pit:
        for row in db.execute("SELECT * FROM event WHERE kind='macro' ORDER BY revision"):
            m=json.loads(row["canonical_json"])
            scale=m["body"]["scale"]
            if scale!=2:
                raise ValueError("unexpected scale")
            rel=lambda us: (us-model_lab.time_us(BASE.isoformat()))//1_000_000
            pit_lab.append(pit,pit_lab.Vintage(row["event_uid"],"CPI_DEMO","2026-10",row["revision"],
                            m["body"]["value_atoms"],"OK",rel(row["published_us"]),
                            rel(row["available_us"]),rel(row["available_us"])))
        return {str(t):pit_lab.current_at(pit,t) for t in (141,142,441,442)}


def market_calendar():
    def at(day, clock, zone):
        return alignment_lab.local_instant(f"{day}T{clock}",zone)
    d="2025-11-28"
    tokyo=[dict(id="TSE-AM",start=at(d,"09:00:00","Asia/Tokyo"),end=at(d,"11:30:00","Asia/Tokyo")),
           dict(id="TSE-PM",start=at(d,"12:30:00","Asia/Tokyo"),end=at(d,"15:30:00","Asia/Tokyo"))]
    ny=[dict(id="NYSE-EARLY",start=at(d,"09:30:00","America/New_York"),
             end=at(d,"13:00:00","America/New_York"))]
    rows=[]
    for hm in ("02:45:00","03:30:00","06:30:00","14:30:00","17:59:00","18:00:00"):
        cut=alignment_lab.instant(f"{d}T{hm}Z")
        rows.append([hm,*[(alignment_lab.session_at(cut,cal) or {}).get("id","CLOSED")
                          for cal in (tokyo,ny)]])
    assert rows[0][1]=="CLOSED" and rows[1][1]=="TSE-PM" and rows[-1][-1]=="CLOSED"
    return rows


def run():
    with closing(model_lab.connect(":memory:")) as db:
        ledger(db)
        early,revised=replay(db,600),replay(db,620)
        def selected(result,t):
            return next(r["x"] for r in result["features"] if r["asset"]=="EQ_DEMO" and r["t"]==t)
        assert math.isclose(selected(early,4)["ret1"],110/103-1)
        assert math.isclose(selected(revised,4)["ret1"],104/103-1)
        assert selected(early,4)["spread_bps"] is None
        assert early == replay(db,600)
        assert early["bar_to_event"]["EQ_DEMO:4:asof:600"] != revised["bar_to_event"]["EQ_DEMO:4:asof:620"]
        macro=macro_versions(db)
        assert [row["value"] if row else None for row in macro.values()] == [None,230,230,210]
        return {"data_kind":"SYNTHETIC","calendar":market_calendar(),"macro":macro,
                "ledger_counts":dict(db.execute("SELECT kind,count(*) FROM event GROUP BY kind")),
                "impact":{str(t):[selected(early,t),selected(revised,t)] for t in (4,5,9)},
                "frozen":early,"restated":revised}


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, indent=2, allow_nan=False))
