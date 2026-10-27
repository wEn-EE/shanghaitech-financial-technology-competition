PRAGMA foreign_keys = ON;

CREATE TABLE source (
  source_id TEXT PRIMARY KEY, license_note TEXT NOT NULL
) STRICT;

CREATE TABLE instrument (
  instrument_id TEXT PRIMARY KEY,
  asset_class TEXT NOT NULL, quote_unit TEXT NOT NULL,
  price_scale INTEGER NOT NULL CHECK(price_scale BETWEEN 0 AND 8),
  quantity_unit TEXT NOT NULL
) STRICT;

CREATE TABLE alias (
  source_id TEXT NOT NULL REFERENCES source(source_id),
  external_code TEXT NOT NULL,
  valid_from_us INTEGER NOT NULL, valid_to_us INTEGER NOT NULL,
  known_at_us INTEGER NOT NULL,
  instrument_id TEXT NOT NULL REFERENCES instrument(instrument_id),
  CHECK(valid_from_us < valid_to_us),
  PRIMARY KEY(source_id, external_code, valid_from_us)
) STRICT;

CREATE TABLE series (
  series_id TEXT PRIMARY KEY, unit TEXT NOT NULL,
  value_scale INTEGER NOT NULL CHECK(value_scale BETWEEN 0 AND 8)
) STRICT;

CREATE TABLE receipt (
  receipt_id INTEGER PRIMARY KEY, source_id TEXT NOT NULL,
  received_us INTEGER NOT NULL, raw BLOB NOT NULL, raw_sha256 TEXT NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('PENDING','ACCEPTED','DUPLICATE','QUARANTINED')),
  reason TEXT
) STRICT;

CREATE TABLE event (
  event_uid TEXT PRIMARY KEY, source_id TEXT NOT NULL REFERENCES source(source_id),
  event_key TEXT NOT NULL, revision INTEGER NOT NULL CHECK(revision >= 1),
  kind TEXT NOT NULL CHECK(kind IN ('quote','macro','news')),
  schema_version INTEGER NOT NULL CHECK(schema_version IN (1,2)),
  event_us INTEGER NOT NULL, published_us INTEGER NOT NULL,
  available_us INTEGER NOT NULL,
  canonical_json TEXT NOT NULL, semantic_sha256 TEXT NOT NULL,
  first_receipt_id INTEGER NOT NULL REFERENCES receipt(receipt_id),
  CHECK(event_us <= published_us AND published_us <= available_us),
  UNIQUE(source_id, event_key, revision)
) STRICT;

CREATE TABLE quote (
  event_uid TEXT PRIMARY KEY REFERENCES event(event_uid),
  instrument_id TEXT NOT NULL REFERENCES instrument(instrument_id),
  price_atoms INTEGER NOT NULL CHECK(price_atoms > 0),
  quantity INTEGER NOT NULL CHECK(quantity >= 0), quality TEXT NOT NULL
) STRICT;

CREATE TABLE macro (
  event_uid TEXT PRIMARY KEY REFERENCES event(event_uid),
  series_id TEXT NOT NULL REFERENCES series(series_id),
  period TEXT NOT NULL, value_atoms INTEGER NOT NULL
) STRICT;

CREATE TABLE news (
  event_uid TEXT PRIMARY KEY REFERENCES event(event_uid),
  headline TEXT NOT NULL
) STRICT;

CREATE TABLE news_asset (
  event_uid TEXT NOT NULL REFERENCES news(event_uid),
  instrument_id TEXT NOT NULL REFERENCES instrument(instrument_id),
  PRIMARY KEY(event_uid, instrument_id)
) STRICT;

CREATE INDEX event_asof ON event(source_id, event_key, available_us, revision);
CREATE INDEX alias_lookup ON alias(source_id, external_code, known_at_us);
