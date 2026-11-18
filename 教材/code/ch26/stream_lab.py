"""Bounded TCP replay into the chapter 17 ledger. All payloads are SYNTHETIC."""
import argparse
import asyncio
import json
import struct
import sys
from time import perf_counter_ns
from collections import Counter
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ch17"))
import model_lab as ledger

LIMIT = 8192
HEADER = struct.Struct("!I")
END = HEADER.pack(0)


def frame(raw):
    if not 0 < len(raw) <= LIMIT:
        raise ValueError("FRAME_LENGTH")
    return HEADER.pack(len(raw)) + raw


async def read_frame(reader):
    try:
        header = await reader.readexactly(HEADER.size)
    except asyncio.IncompleteReadError as exc:
        raise EOFError("SHORT_HEADER" if exc.partial else "NO_END") from exc
    size = HEADER.unpack(header)[0]
    if size == 0:
        return None
    if size > LIMIT:
        raise ValueError("FRAME_LENGTH")
    try:
        return await reader.readexactly(size)
    except asyncio.IncompleteReadError as exc:
        raise EOFError("SHORT_BODY") from exc


def persist(path, raw, received_at):
    with closing(ledger.connect(path)) as db:
        return ledger.ingest(db, "DEMO", raw, received_at)


async def replay(path, capacity=2, delay_ms=5):
    if capacity < 1 or delay_ms < 0:
        raise ValueError("invalid capacity or delay")
    # Each run owns a fresh directory. Opening an old ledger for replay is a
    # separate exercise, since its counts include earlier deliveries.
    path.parent.mkdir(parents=True, exist_ok=False)
    with closing(ledger.connect(path)) as db:
        ledger.initialize(db)
    rows = ledger.samples()
    stock, bond, gold, fx = [row[0] for row in rows[:4]]
    changed_stock = json.loads(stock)
    changed_stock["body"]["price"] = "100.11"
    conflict = ledger.dump(changed_stock).encode()
    batch = b"".join(frame(r) for r in (stock, bond, gold, fx, conflict)) + END
    queue = asyncio.Queue(maxsize=capacity)
    errors, handled = [], []
    connections = full = peak = tick = 0
    start = datetime(2026, 10, 28, 1, 0, 1, tzinfo=timezone.utc)

    def teaching_clock():
        nonlocal tick
        tick += 1
        return (start + timedelta(microseconds=tick)).isoformat()

    async def serve(reader, writer):
        nonlocal connections
        connections += 1
        first = connections == 1
        try:
            payload = frame(stock) + frame(bond)[:11] if first else batch
            writer.write(payload[:2])
            await writer.drain()
            writer.write(payload[2:])
            await writer.drain()
        finally:
            writer.close()
            await writer.wait_closed()

    async def receive(port):
        nonlocal full, peak
        for attempt in range(2):
            writer = None
            try:
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection("127.0.0.1", port), timeout=3)
                while True:
                    raw = await asyncio.wait_for(read_frame(reader), timeout=3)
                    if raw is None:
                        await queue.put(None)
                        return
                    stamp, started = teaching_clock(), perf_counter_ns()
                    if queue.full():
                        full += 1
                    await queue.put((raw, stamp, started))
                    peak = max(peak, queue.qsize())
            except (EOFError, OSError) as exc:
                errors.append(str(exc) or type(exc).__name__)
                if attempt == 1:
                    raise
            finally:
                if writer is not None:
                    writer.close()
                    await writer.wait_closed()
            await asyncio.sleep(0.01)

    async def consume():
        while True:
            item = await queue.get()
            if item is None:
                return
            raw, stamp, started = item
            dequeued = perf_counter_ns()
            await asyncio.sleep(delay_ms / 1000)
            status = await asyncio.to_thread(persist, path, raw, stamp)
            handled.append(dict(received_at=stamp, observed_committed_at=teaching_clock(),
                                admission_and_queue_ns=dequeued - started,
                                service_observed_ns=perf_counter_ns() - dequeued,
                                status=status))

    server = await asyncio.start_server(serve, "127.0.0.1", 0)
    async with server:
        port = server.sockets[0].getsockname()[1]
        async with asyncio.TaskGroup() as tasks:
            tasks.create_task(receive(port))
            tasks.create_task(consume())
    with closing(ledger.connect(path)) as db:
        receipts = dict(db.execute("SELECT status,COUNT(*) FROM receipt GROUP BY status"))
        events = db.execute("SELECT COUNT(*) FROM event").fetchone()[0]
    if receipts != dict(Counter(row["status"] for row in handled)):
        raise RuntimeError("ledger and consumer disagree")
    return dict(data="SYNTHETIC", connections=connections, frame_errors=errors,
                peak_queue=peak, put_saw_full=full, receipts=receipts, events=events,
                timeline=handled)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--capacity", type=int, default=2)
    parser.add_argument("--delay-ms", type=int, default=5)
    args = parser.parse_args()
    run = datetime.now(timezone.utc).strftime("run_%Y%m%dT%H%M%S_%fZ")
    directory = Path(__file__).resolve().parent / "runs" / run
    report = asyncio.run(replay(directory / "market.db", args.capacity, args.delay_ms))
    result = json.dumps(report, ensure_ascii=False, indent=2)
    (directory / "results.json").write_text(result + "\n", encoding="utf-8")
    print(result, directory, sep="\n")
