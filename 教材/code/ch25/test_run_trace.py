from contextlib import closing
import unittest

from dag_lab import ancestors, canonical, connect, put, read, stage, startup, trace_run
import json


def example(db):
    startup(db)
    def classify(values, params):
        return "LOW" if values["sample"]["score"] < 5 else "HIGH"
    def record(values, params):
        return {"state": values["label"]}
    sources, decisions = {}, []
    for name, score in (("A", 1), ("B", 2), ("A", 1)):
        with db:
            key = put(db, canonical({"name": name, "score": score}))
        sources[key] = name
        label = stage(db, "classify", {"sample":key}, {}, __file__, classify)
        decision = stage(db, "decision", {"label":label["output"]}, {}, __file__, record,
                         upstream={"label":label["run"]})
        decisions.append(decision)
    names = []
    for decision in decisions:
        tree = trace_run(db, decision["run"])
        sample = tree["inputs"]["label"]["producer"]["inputs"]["sample"]["artifact"]
        names.append(json.loads(read(db, sample))["name"])
    all_names = sorted(sources[k] for k in ancestors(db,label["output"]) if k in sources)
    return names, all_names, decisions


class TraceTests(unittest.TestCase):
    def test_equal_output_different_history(self):
        with closing(connect(":memory:")) as db:
            names, all_names, decisions = example(db)
            self.assertEqual(names, ["A","B","A"])
            self.assertEqual(all_names, ["A","B"])
            self.assertEqual(decisions[0]["output"], decisions[1]["output"])
            self.assertNotEqual(decisions[0]["run"], decisions[1]["run"])
            self.assertEqual(decisions[0]["run"], decisions[2]["run"])
            self.assertTrue(decisions[2]["cached"])


if __name__ == "__main__":
    with closing(connect(":memory:")) as db:
        names, all_names, decisions = example(db)
        print("decision runs:", names, "LOW content:", all_names)
        print("cache reused first run:", decisions[2]["cached"] and decisions[2]["run"] == decisions[0]["run"])
