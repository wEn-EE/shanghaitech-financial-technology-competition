"""SYNTHETIC multi-source contract lab; standard library only, no network."""
from __future__ import annotations
import hashlib
import json
import re
import sqlite3
import platform
from datetime import datetime, timezone
from decimal import Decimal, localcontext
from pathlib import Path

BASE = Path(__file__).parent
EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


class ContractError(ValueError):
    pass


def time_us(text):
    pattern = r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})"
    if not isinstance(text, str) or not re.fullmatch(pattern, text):
        raise ContractError("TIME_FORMAT")
    try:
        delta = datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(timezone.utc)-EPOCH
    except ValueError as exc:
        raise ContractError("TIME_VALUE") from exc
    return (delta.days*86400+delta.seconds)*1000000+delta.microseconds


def atoms(text, scale):
    if (not isinstance(text, str) or len(text) > 80
            or not re.fullmatch(r"[+-]?\d+(?:\.\d+)?", text)):
        raise ContractError("DECIMAL_STRING")
    with localcontext() as ctx:
        ctx.prec = max(100, len(text)+scale+2)
        value = Decimal(text)*(Decimal(10)**scale)
        if value != value.to_integral_value():
            raise ContractError("EXCESS_PRECISION")
        if not -(2**63) <= value <= 2**63-1:
            raise ContractError("INT64_RANGE")
        return int(value)


def dump(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise ContractError("DUPLICATE_JSON_KEY")
        result[key] = value
    return result


def reject_constant(value):
    raise ContractError("NONFINITE_JSON")


def require_fields(obj, required, optional=()):
    if not isinstance(obj, dict) or not set(required) <= obj.keys():
        raise ContractError("MISSING_FIELDS")
    if obj.keys()-set(required)-set(optional):
        raise ContractError("UNKNOWN_FIELDS")


def connect(path):
    db = sqlite3.connect(path, autocommit=sqlite3.LEGACY_TRANSACTION_CONTROL)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    if db.execute("PRAGMA foreign_keys").fetchone()[0] != 1:
        raise RuntimeError("FOREIGN_KEYS_DISABLED")
    return db


def initialize(db):
    db.executescript((BASE/"schema.sql").read_text(encoding="utf-8"))
    with db:
        db.execute("INSERT INTO source VALUES (?,?)", ("DEMO", "SYNTHETIC teaching input"))
        assets = [
            ("EQ_DEMO", "EQUITY", "CNY/share", 2, "share"),
            ("BOND_DEMO", "BOND", "percent_of_par_clean", 3, "100_CNY_face_lot"),
            ("GOLD_DEMO", "COMMODITY_SPOT", "USD/troy_ounce", 2, "troy_ounce"),
            ("FX_DEMO", "FX_SPOT", "CNY/USD", 4, "USD")]
        db.executemany("INSERT INTO instrument VALUES (?,?,?,?,?)", assets)
        for asset in assets:
            db.execute("INSERT INTO alias VALUES (?,?,?,?,?,?)",
                       ("DEMO", asset[0], time_us("2020-01-01T00:00:00Z"),
                        time_us("2030-01-01T00:00:00Z"),
                        time_us("2020-01-01T00:00:00Z"), asset[0]))
        db.execute("INSERT INTO series VALUES (?,?,?)", ("CPI_YOY_DEMO", "percent", 2))


def resolve(db, source, code, event_us, available_us):
    rows = db.execute(
        """SELECT i.* FROM alias a JOIN instrument i USING(instrument_id)
           WHERE source_id=? AND external_code=? AND valid_from_us<=?
           AND ?<valid_to_us AND known_at_us<=?""",
        (source, code, event_us, event_us, available_us)).fetchall()
    if len(rows) != 1:
        raise ContractError("ALIAS_MISSING_OR_AMBIGUOUS")
    return rows[0]


def normalize(db, source, raw, received_us):
    if not db.execute("SELECT 1 FROM source WHERE source_id=?", (source,)).fetchone():
        raise ContractError("UNKNOWN_SOURCE")
    try:
        obj = json.loads(raw.decode("utf-8"), object_pairs_hook=pairs,
                         parse_constant=reject_constant)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ContractError("INVALID_JSON_UTF8") from exc
    require_fields(obj, ("schema_version", "event_key", "revision", "kind",
                         "event_time", "published_at", "body"))
    version, revision, kind = obj["schema_version"], obj["revision"], obj["kind"]
    if type(version) is not int or version not in (1, 2):
        raise ContractError("SCHEMA_VERSION")
    if type(revision) is not int or not 1 <= revision <= 2**31-1:
        raise ContractError("REVISION")
    if not isinstance(obj["event_key"], str) or not 1 <= len(obj["event_key"]) <= 100:
        raise ContractError("EVENT_KEY")
    if not isinstance(kind, str) or kind not in ("quote", "macro", "news"):
        raise ContractError("KIND")
    if version == 2 and kind != "quote":
        raise ContractError("VERSION_KIND")
    event, published = time_us(obj["event_time"]), time_us(obj["published_at"])
    if not event <= published <= received_us:
        raise ContractError("TIME_ORDER")
    b = obj["body"]
    if kind == "quote":
        require_fields(b, ("symbol", "unit", "price", "quantity"),
                       ("quality",) if version == 2 else ())
        if not isinstance(b["symbol"], str):
            raise ContractError("SYMBOL")
        inst = resolve(db, source, b["symbol"], event, received_us)
        if b["unit"] != inst["quote_unit"]:
            raise ContractError("UNIT_MISMATCH")
        price = atoms(b["price"], inst["price_scale"])
        if price <= 0 or type(b["quantity"]) is not int or not 0 <= b["quantity"] < 2**63:
            raise ContractError("QUOTE_DOMAIN")
        quality = b.get("quality", "UNSPECIFIED")
        if quality not in ("UNSPECIFIED", "INDICATIVE", "FIRM"):
            raise ContractError("QUALITY")
        body = {"instrument_id": inst["instrument_id"], "price_atoms": price,
                "quantity": b["quantity"], "quality": quality,
                "unit": inst["quote_unit"], "scale": inst["price_scale"]}
    elif kind == "macro":
        require_fields(b, ("series_id", "period", "unit", "value"))
        if not isinstance(b["series_id"], str) or not isinstance(b["period"], str):
            raise ContractError("SERIES_PERIOD")
        series = db.execute("SELECT * FROM series WHERE series_id=?", (b["series_id"],)).fetchone()
        if not series or b["unit"] != series["unit"]:
            raise ContractError("SERIES_UNIT")
        if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", b["period"]):
            raise ContractError("PERIOD")
        if obj["event_key"] != b["series_id"]+":"+b["period"]:
            raise ContractError("MACRO_BUSINESS_KEY")
        body = {"series_id": b["series_id"], "period": b["period"], "unit": b["unit"],
                "scale": series["value_scale"], "value_atoms": atoms(b["value"], series["value_scale"])}
    else:
        require_fields(b, ("headline", "symbols"))
        if not isinstance(b["headline"], str) or not 1 <= len(b["headline"]) <= 500:
            raise ContractError("HEADLINE")
        if not isinstance(b["symbols"], list) or not all(isinstance(s, str) for s in b["symbols"]):
            raise ContractError("NEWS_SYMBOLS")
        ids = [resolve(db, source, s, event, received_us)["instrument_id"] for s in b["symbols"]]
        body = {"headline": b["headline"], "instrument_ids": sorted(set(ids))}
    return {"source_id": source, "event_key": obj["event_key"], "revision": revision,
            "kind": kind, "event_us": event, "published_us": published,
            "body": body}, version


def ingest(db, source, raw, received_at):
    received = time_us(received_at)  # Trusted adapter clock, not provider JSON.
    with db:
        rid = db.execute(
            "INSERT INTO receipt(source_id,received_us,raw,raw_sha256,status) VALUES (?,?,?,?,?)",
            (source, received, raw, digest(raw), "PENDING")).lastrowid
    try:
        canonical, schema_version = normalize(db, source, raw, received)
        text = dump(canonical)
        sha = digest(text.encode("utf-8"))
        key = (source, canonical["event_key"], canonical["revision"])
        uid = digest(dump(key).encode("utf-8"))
        with db:
            previous = db.execute("SELECT canonical_json FROM event WHERE event_uid=?", (uid,)).fetchone()
            if previous and previous[0] != text:
                raise ContractError("SAME_KEY_CONFLICT")
            status = "DUPLICATE" if previous else "ACCEPTED"
            if not previous:
                db.execute("INSERT INTO event VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                           (uid, source, key[1], key[2], canonical["kind"], schema_version,
                            canonical["event_us"], canonical["published_us"], received, text, sha, rid))
                b = canonical["body"]
                if canonical["kind"] == "quote":
                    db.execute("INSERT INTO quote VALUES (?,?,?,?,?)",
                               (uid, b["instrument_id"], b["price_atoms"], b["quantity"], b["quality"]))
                elif canonical["kind"] == "macro":
                    db.execute("INSERT INTO macro VALUES (?,?,?,?)",
                               (uid, b["series_id"], b["period"], b["value_atoms"]))
                else:
                    db.execute("INSERT INTO news VALUES (?,?)", (uid, b["headline"]))
                    db.executemany("INSERT INTO news_asset VALUES (?,?)",
                                   [(uid, i) for i in b["instrument_ids"]])
            db.execute("UPDATE receipt SET status=? WHERE receipt_id=?", (status, rid))
        return status
    except ContractError as exc:
        with db:
            db.execute("UPDATE receipt SET status='QUARANTINED',reason=? WHERE receipt_id=?",
                       (str(exc), rid))
        return "QUARANTINED"
    # Infrastructure/SQL failures propagate; committed raw receipt remains PENDING.


def macro_asof(db, cutoff):
    return [dict(row) for row in db.execute(
        """WITH visible AS (
             SELECT e.source_id,e.event_key,e.revision,m.*,
               ROW_NUMBER() OVER(PARTITION BY e.source_id,m.series_id,m.period
                 ORDER BY e.revision DESC,e.event_uid) AS rn
             FROM event e JOIN macro m USING(event_uid) WHERE e.available_us<=?)
           SELECT source_id,series_id,period,revision,value_atoms
           FROM visible WHERE rn=1 ORDER BY source_id,series_id,period""", (time_us(cutoff),))]


def samples():
    stamp = "2026-10-28T01:00:00Z"
    def wrap(key, kind, body, revision=1, version=1):
        return dict(schema_version=version, event_key=key, revision=revision,
                    kind=kind, event_time=stamp, published_at=stamp, body=body)
    messages = []
    for symbol, unit, price in [
            ("EQ_DEMO", "CNY/share", "100.10"),
            ("BOND_DEMO", "percent_of_par_clean", "99.125"),
            ("GOLD_DEMO", "USD/troy_ounce", "2000.00"),
            ("FX_DEMO", "CNY/USD", "7.1234")]:
        messages.append(wrap(symbol+"-q1", "quote",
                             dict(symbol=symbol, unit=unit, price=price, quantity=10)))
    messages.append(wrap("CPI_YOY_DEMO:2026-09", "macro",
                         dict(series_id="CPI_YOY_DEMO", period="2026-09", unit="percent", value="2.30")))
    revised = json.loads(dump(messages[-1]))
    revised["revision"] = 2
    revised["published_at"] = revised["event_time"] = "2026-10-28T02:00:00Z"
    revised["body"]["value"] = "2.10"
    news = wrap("news1", "news", dict(headline="SYNTHETIC: policy discussion",
                                    symbols=["EQ_DEMO", "BOND_DEMO"]))
    messages.extend([news, json.loads(dump(messages[0]))])
    messages[-1]["body"]["price"] = "100.100"  # Same semantic decimal, different bytes.
    conflict = json.loads(dump(messages[0])); conflict["body"]["price"] = "100.11"
    bad_unit = json.loads(dump(messages[1])); bad_unit["event_key"] = "bad-unit"
    bad_unit["body"]["unit"] = "CNY"
    v2 = wrap("q-v2", "quote", dict(symbol="EQ_DEMO", unit="CNY/share",
                                  price="100.12", quantity=20, quality="FIRM"), version=2)
    rows = [(dump(m).encode("utf-8"), "2026-10-28T01:00:01Z") for m in messages]
    rows += [(dump(m).encode("utf-8"), "2026-10-28T01:00:02Z") for m in (conflict, bad_unit, v2)]
    rows += [(b'{"broken":', "2026-10-28T01:00:03Z"),
             (dump(revised).encode("utf-8"), "2026-10-28T02:00:01Z")]
    return rows


def main():
    out = BASE/"runs"/datetime.now(timezone.utc).strftime("run_%Y%m%dT%H%M%S_%fZ")
    out.mkdir(parents=True, exist_ok=False)
    db = connect(out/"market.db")
    initialize(db)
    deliveries = samples()
    for raw, received in deliveries:
        ingest(db, "DEMO", raw, received)
    counts = dict(db.execute("SELECT status,COUNT(*) FROM receipt GROUP BY status"))
    report = {"data_kind": "SYNTHETIC", "receipts": len(deliveries), "status_counts": counts,
              "events": db.execute("SELECT COUNT(*) FROM event").fetchone()[0],
              "before_revision": macro_asof(db, "2026-10-28T01:30:00Z"),
              "after_revision": macro_asof(db, "2026-10-28T02:30:00Z"),
              "foreign_key_errors": [list(r) for r in db.execute("PRAGMA foreign_key_check")]}
    db.close()
    (out/"results.json").write_text(json.dumps(report, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    manifest = {"adapter_version": "ch17-v1", "python": platform.python_version(), "sqlite": sqlite3.sqlite_version,
                "data_kind": "SYNTHETIC", "files_sha256": {
                    str(p.name): digest(p.read_bytes()) for p in
                    [BASE/"schema.sql", Path(__file__), out/"market.db", out/"results.json"]}}
    (out/"manifest.json").write_text(json.dumps(manifest, indent=2)+"\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(out.resolve())


if __name__ == "__main__":
    main()
