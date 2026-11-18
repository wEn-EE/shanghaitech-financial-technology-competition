import unittest
from partition_lab import Cluster, experiment


class PartitionTests(unittest.TestCase):
    def test_partition_indistinguishable(self):
        quiet, changed = Cluster(10010), Cluster(10010)
        for cluster in (quiet, changed):
            cluster.reachable.remove("C")
        changed.write(9710, 10)
        self.assertEqual(quiet.read("C", "local", 12), changed.read("C", "local", 12))
        self.assertNotEqual(quiet.log[-1], changed.log[-1])

    def test_strict_during_partition(self):
        c = Cluster(10010)
        c.reachable.remove("C")
        c.write(9710, 10)
        self.assertEqual(c.read("B", "strict", 11)["price_atoms"], 9710)
        self.assertNotIn("price_atoms", c.read("C", "strict", 12))

    def test_no_quorum_preserves_prefix(self):
        c = Cluster(10010)
        c.reachable = {"A"}
        self.assertFalse(c.write(9710, 10))
        self.assertEqual(len(c.log), 1)
        self.assertEqual(set(c.applied.values()), {1})

    def test_session_and_age(self):
        c = Cluster(10010)
        self.assertEqual(c.read("C", "guarded", 20)["status"], "OK")
        self.assertEqual(c.read("C", "guarded", 21)["status"], "EXPIRED")
        self.assertEqual(c.read("C", "guarded", 1, min_version=2)["status"], "BEHIND_SESSION")

    def test_heal_and_replay(self):
        report = experiment(10010)
        self.assertEqual([r["status"] for r in report["delivery"]],
                         ["GAP", "APPLIED", "REPLAY", "APPLIED"])
        self.assertEqual(report["final_prefix"], dict(A=3, B=3, C=3))
        self.assertEqual(report["operations"][-2]["price_atoms"], 9610)

    def test_disconnected_delivery(self):
        c = Cluster(10010)
        c.reachable.remove("C")
        c.write(9710, 10)
        self.assertEqual(c.deliver("C", 2), "DISCONNECTED")
        self.assertEqual(c.applied["C"], 1)
