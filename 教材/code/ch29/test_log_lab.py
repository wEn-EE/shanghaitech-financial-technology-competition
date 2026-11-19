import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import Mock

from kafka_adapter import consume, publish
from log_lab import SCHEMA, TOPIC, apply, experiment, messages


class LogTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.source = Path(temp.name)/"quotes.db"
        with closing(sqlite3.connect(self.source)) as db:
            db.execute("CREATE TABLE quotes(asset,event_s,revision,ready_s,price_atoms,scale,seed_uid)")
            with db:
                db.executemany("INSERT INTO quotes VALUES (?,0,1,1,10,2,'seed')",
                               [("BOND_DEMO",),("EQ_DEMO",),("FX_DEMO",),("GOLD_DEMO",)])
        self.key,self.raw = next(messages(self.source))
        self.db = sqlite3.connect(":memory:")
        self.db.executescript(SCHEMA)
        self.addCleanup(self.db.close)

    def apply(self,o,raw):
        return apply(self.db,"g",TOPIC,0,o,self.key,raw)

    def test_replay_and_source_duplicate(self):
        self.assertEqual(self.apply(0,self.raw),"ACCEPTED")
        self.assertEqual(self.apply(0,self.raw),"REPLAY")
        self.assertEqual(self.apply(1,self.raw),"DUPLICATE")

    def test_conflict_preserves_original(self):
        self.apply(0,self.raw)
        changed = json.dumps(dict(json.loads(self.raw),price_atoms=11)).encode()
        self.assertEqual(self.apply(1,changed),"CONFLICT")
        self.assertEqual(json.loads(self.db.execute("SELECT body FROM event").fetchone()[0])["price_atoms"],10)
        with self.assertRaises(ValueError):
            self.apply(0,changed)

    def test_bad_message_has_durable_receipt(self):
        self.assertEqual(self.apply(0,b"?"),"INVALID")
        self.assertEqual(self.db.execute("SELECT raw FROM receipt").fetchone()[0],b"?")

    def test_subprocess_recovery(self):
        report = experiment(self.source,self.source.parent/"log.db")
        self.assertEqual(report["ends"],[3,2])
        self.assertEqual(report["skipped"],[(0,0)])
        self.assertIn(("features","ACCEPTED",4),report["receipts"])
        self.assertIn(("unsafe","ACCEPTED",3),report["receipts"])

    def test_client_commits_after_sink(self):
        msg = Mock()
        for name,value in dict(topic=TOPIC,partition=0,offset=0,key=self.key,value=self.raw,error=None).items():
            getattr(msg,name).return_value = value
        client = Mock()
        client.poll.return_value = msg
        def confirm(**kwargs):
            self.assertEqual(kwargs,dict(message=msg,asynchronous=False))
            self.assertEqual(self.db.execute("SELECT count(*) FROM receipt").fetchone()[0],1)
            return [Mock(error=None)]
        client.commit.side_effect = confirm
        consume(client,self.db,"g",1)
        client.commit.assert_called_once()

    def test_unconfirmed_delivery_fails(self):
        producer = Mock()
        producer.flush.return_value = 1
        with self.assertRaises(RuntimeError):
            publish(producer,self.source)
