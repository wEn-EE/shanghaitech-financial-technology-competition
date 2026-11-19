"""Kafka adapter for the chapter 29 synthetic topic (classic consumer groups)."""
import argparse
import sqlite3
import time
from contextlib import closing
from pathlib import Path

from log_lab import PART, SCHEMA, TOPIC, apply, messages


def publish(producer, source):
    failures = []
    def delivered(error, message):
        if error:
            failures.append(str(error))
    count = 0
    for key, raw in messages(source):
        producer.produce(TOPIC,key=key,value=raw,partition=PART[key.decode()],on_delivery=delivered)
        producer.poll(0)
        count += 1
    remaining = producer.flush(30)
    if remaining or failures:
        raise RuntimeError(f"delivery incomplete: {remaining} pending, {failures}")
    return count


def consume(consumer, db, group, count):
    db.executescript(SCHEMA)
    consumer.subscribe([TOPIC])
    done = 0
    deadline = time.monotonic() + 30
    while done < count:
        msg = consumer.poll(1)
        if msg is None:
            if time.monotonic() > deadline:
                raise TimeoutError(f"received {done} of {count}")
            continue
        if msg.error():
            raise RuntimeError(str(msg.error()))
        status = apply(db,group,msg.topic(),msg.partition(),msg.offset(),msg.key(),msg.value())
        committed = consumer.commit(message=msg,asynchronous=False)
        if not committed or any(item.error for item in committed):
            raise RuntimeError(f"offset commit failed: {committed}")
        print(msg.partition(),msg.offset(),status)
        done += 1
        deadline = time.monotonic() + 30


if __name__ == "__main__":
    from confluent_kafka import Consumer, Producer
    parser = argparse.ArgumentParser()
    parser.add_argument("--bootstrap",default="127.0.0.1:9092")
    actions = parser.add_subparsers(dest="action",required=True)
    actions.add_parser("produce").add_argument("source",type=Path)
    read = actions.add_parser("consume")
    read.add_argument("database",type=Path)
    read.add_argument("--group",required=True)
    read.add_argument("--count",type=int,default=10)
    args = parser.parse_args()
    config = {"bootstrap.servers":args.bootstrap,"allow.auto.create.topics":False}
    if args.action == "produce":
        print("delivered",publish(Producer({**config,"enable.idempotence":True,"acks":"all"}),args.source))
    else:
        client = Consumer({**config,"group.id":args.group,"enable.auto.commit":False,
                           "enable.auto.offset.store":False,"auto.offset.reset":"earliest",
                           "isolation.level":"read_committed"})
        try:
            with closing(sqlite3.connect(args.database)) as sink:
                consume(client,sink,args.group,args.count)
        finally:
            client.close()
