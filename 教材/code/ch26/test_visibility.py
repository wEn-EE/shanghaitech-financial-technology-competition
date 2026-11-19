from contextlib import closing
import json
from pathlib import Path
import tempfile
import unittest
import stream_lab as lab


def example(path):
    at = lambda ms: "2026-10-28T09:30:00." + ms + "Z"
    with closing(lab.ledger.connect(path)) as db:
        lab.ledger.initialize(db)
    old = lab.ledger.samples()[1][0]
    _, old_uid = lab.persist(path, old, at("010"))
    with closing(lab.ledger.connect(path)) as db:
        lab.setup_visibility(db)
        legacy = db.execute("SELECT visibility FROM consumer_quotes").fetchone()[0]
    lab.observe(path, old_uid, at("020"))
    obj = json.loads(old)
    obj["revision"] = 2
    obj["body"]["price"] = "99.250"
    _, uid = lab.persist(path, lab.ledger.dump(obj).encode(), at("100"))
    lab.observe(path, uid, at("180"))
    with closing(lab.ledger.connect(path)) as db:
        received = db.execute("SELECT price_atoms FROM consumer_quotes WHERE received_us<=? "
                              "ORDER BY received_us DESC LIMIT 1", (lab.ledger.time_us(at("120")),)).fetchone()[0]
        return legacy, received, *(lab.latest_visible(db,"BOND_DEMO",at(t))[0] for t in ("120","181"))


class VisibilityTest(unittest.TestCase):
    def test_cutoffs_and_legacy(self):
        with tempfile.TemporaryDirectory() as temp:
            self.assertEqual(example(Path(temp)/"market.db"), ("UNKNOWN", 99250, 99125, 99250))


if __name__ == "__main__":
    from datetime import datetime, timezone
    directory = Path(__file__).parent/"runs"/datetime.now(timezone.utc).strftime("visibility_%Y%m%dT%H%M%S_%fZ")
    directory.mkdir(parents=True)
    path = directory/"visibility.db"
    print("legacy, receipt@120, model@120, model@181:", example(path))
    print(path)
