import unittest
from copy import deepcopy
from market_lab import Book, Receiver, demo_events, call_auction


def order(seq, oid, side, price, qty, kind="LMT"):
    return {"seq": seq, "action": "NEW", "order_id": oid, "side": side,
            "price": price, "qty": qty, "kind": kind}


class MarketTests(unittest.TestCase):
    def test_price_then_time_priority(self):
        b = Book()
        b.apply(order(1, "expensive", "S", 102, 20))
        b.apply(order(2, "early", "S", 101, 10))
        b.apply(order(3, "late", "S", 101, 20))
        r = b.apply(order(4, "buy", "B", None, 35, "MKT"))
        self.assertEqual([(f['maker'], f['qty']) for f in r['trades']],
                         [('early', 10), ('late', 20), ('expensive', 5)])

    def test_limit_price_and_resting_remainder(self):
        b = Book()
        b.apply(order(1, 'a', 'S', 102, 10))
        r = b.apply(order(2, 'b', 'B', 101, 30))
        self.assertEqual(r['filled'], 0)
        self.assertEqual(r['resting'], 30)
        self.assertEqual(b.quote()['mid'], 101.5)

    def test_market_residual_expires(self):
        b = Book()
        b.apply(order(1, 'a', 'S', 100, 10))
        r = b.apply(order(2, 'b', 'B', None, 25, 'MKT'))
        self.assertEqual((r['filled'], r['resting'], r['expired']), (10, 0, 15))
        self.assertEqual(b.orders, {})

    def test_partial_cancel_preserves_priority(self):
        b = Book()
        b.apply(order(1, 'a', 'S', 100, 20))
        b.apply(order(2, 'b', 'S', 100, 20))
        b.apply({'action': 'CANCEL', 'order_id': 'a', 'qty': 10})
        r = b.apply(order(4, 'c', 'B', None, 15, 'MKT'))
        self.assertEqual([f['maker'] for f in r['trades']], ['a', 'b'])

    def test_invalid_event_has_no_book_effect(self):
        b = Book()
        b.apply(order(1, 'a', 'S', 100, 10))
        original = deepcopy(b.__dict__)
        for bad in [order(2, 'x', 'B', 100.5, 1), order(2, 'x', 'B', 100, True),
                    {'action': 'CANCEL', 'order_id': 'a', 'qty': 11}]:
            with self.assertRaises(ValueError):
                b.apply(bad)
            self.assertEqual(b.__dict__, original)

    def test_filled_order_id_cannot_be_reused(self):
        b = Book()
        b.apply(order(1, 'a', 'S', 100, 10))
        b.apply(order(2, 'b', 'B', None, 10, 'MKT'))
        with self.assertRaises(ValueError):
            b.apply(order(3, 'a', 'S', 100, 10))

    def test_gap_blocks_public_quote_and_preserves_computed_time(self):
        events, r = demo_events(), Receiver()
        r.receive(events[0], 1.1)
        r.receive(events[2], 3.1)
        self.assertEqual(r.snapshot()['feed_status'], 'GAP')
        self.assertIsNone(r.snapshot()['quotes'])
        r.receive(events[1], 3.2)
        self.assertEqual(r.snapshot()['last_contiguous_seq'], 3)
        self.assertEqual(r.applied[-1]['received_at'], 3.1)
        self.assertEqual(r.applied[-1]['computed_at'], 3.2)

    def test_duplicate_and_conflict(self):
        e, r = demo_events()[0], Receiver()
        r.receive(e, 1.1)
        r.receive(e, 1.2)
        self.assertEqual(len(r.applied), 1)
        bad = dict(e, qty=e['qty'] + 1)
        with self.assertRaises(ValueError):
            r.receive(bad, 1.3)

    def test_future_event_not_visible(self):
        e, r = demo_events()[0], Receiver()
        for time in [1.0, float('nan'), float('inf')]:
            with self.assertRaises(ValueError):
                r.receive(e, time)
        self.assertEqual(r.expected, 1)

    def test_replay_and_quantity_conservation(self):
        events, a, b = demo_events(), Receiver(), Receiver()
        for e in events:
            a.receive(e, e['seq'] + .1)
            b.receive(deepcopy(e), e['seq'] + .1)
        self.assertEqual(a.applied, b.applied)
        self.assertEqual(a.snapshot(), b.snapshot())
        for r in a.applied:
            if r['status'] == 'APPLIED' and r['action'] == 'NEW':
                qty = events[r['seq'] - 1]['qty']
                self.assertEqual(qty, r['filled'] + r['resting'] + r['expired'])

    def test_one_sided_is_missing_not_zero_spread(self):
        b = Book()
        b.apply(order(1, 'a', 'B', 100, 10))
        self.assertEqual(b.quote()['status'], 'ONE_SIDED')
        self.assertIsNone(b.quote()['spread_bps'])

    def test_auction_and_no_cross(self):
        result = call_auction([(10002, 80), (10000, 70)], [(9998, 60), (10000, 90)], 10000)
        self.assertEqual((result['price'], result['volume']), (10000, 150))
        self.assertIsNone(call_auction([(99, 10)], [(101, 10)], 100)['price'])


if __name__ == '__main__':
    unittest.main()
