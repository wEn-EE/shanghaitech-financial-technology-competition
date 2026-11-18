import asyncio
import json
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

import stream_lab as lab


class StreamTests(unittest.IsolatedAsyncioTestCase):
    async def test_every_cut_and_two_frames(self):
        # The controlled reader lets us force a split independently of TCP.
        raw = "黄金".encode()
        wire = lab.frame(raw) + lab.frame(b"B") + lab.END
        for cut in range(len(wire) + 1):
            reader = asyncio.StreamReader()
            reader.feed_data(wire[:cut])
            first = asyncio.create_task(lab.read_frame(reader))
            await asyncio.sleep(0)
            reader.feed_data(wire[cut:])
            reader.feed_eof()
            self.assertEqual(await first, raw)
            self.assertEqual(await lab.read_frame(reader), b"B")
            self.assertIsNone(await lab.read_frame(reader))

    async def test_truncation_at_three_boundaries(self):
        for wire, reason in ((b"", "NO_END"), (b"\0", "SHORT_HEADER"),
                             (lab.frame(b"AB")[:-1], "SHORT_BODY")):
            reader = asyncio.StreamReader()
            reader.feed_data(wire)
            reader.feed_eof()
            with self.assertRaisesRegex(EOFError, reason):
                await lab.read_frame(reader)

    async def test_length_checked_before_waiting_for_body(self):
        reader = asyncio.StreamReader()
        reader.feed_data(lab.HEADER.pack(lab.LIMIT + 1))
        with self.assertRaisesRegex(ValueError, "FRAME_LENGTH"):
            await asyncio.wait_for(lab.read_frame(reader), 1)

    async def test_maximum_and_reserved_length(self):
        with self.assertRaises(ValueError):
            lab.frame(b"")
        reader = asyncio.StreamReader()
        reader.feed_data(lab.frame(b"x" * lab.LIMIT))
        self.assertEqual(len(await lab.read_frame(reader)), lab.LIMIT)

    async def test_backpressure_and_replay_in_real_ledger(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "session" / "market.db"
            report = await lab.replay(path, capacity=1, delay_ms=10)
            self.assertEqual(report["connections"], 2)
            self.assertEqual(report["frame_errors"], ["SHORT_BODY"])
            self.assertEqual(report["peak_queue"], 1)
            self.assertGreater(report["put_saw_full"], 0)
            self.assertEqual(report["receipts"], {"ACCEPTED": 4, "DUPLICATE": 1, "QUARANTINED": 1})
            self.assertEqual(report["events"], 4)
            with closing(lab.ledger.connect(path)) as db:
                rows = db.execute("SELECT raw,status,reason FROM receipt ORDER BY receipt_id").fetchall()
                self.assertEqual(json.loads(rows[0][0])["body"]["price"], "100.10")
                self.assertEqual(rows[0][0], rows[1][0])
                self.assertEqual(rows[-1][2], "SAME_KEY_CONFLICT")
                self.assertEqual(db.execute("SELECT price_atoms FROM quote WHERE instrument_id='EQ_DEMO'").fetchone()[0], 10010)
            self.assertTrue(all(r["received_at"] < r["observed_committed_at"] for r in report["timeline"]))

    async def test_writer_failure_terminates_group(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "session" / "market.db"
            with patch.object(lab, "persist", side_effect=RuntimeError("disk offline")):
                with self.assertRaises(ExceptionGroup) as error:
                    await asyncio.wait_for(lab.replay(path, capacity=1), 3)
            self.assertTrue(any(str(exc) == "disk offline" for exc in error.exception.exceptions))

    async def test_preserve_existing_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(FileExistsError):
                await lab.replay(Path(directory) / "existing.db")
