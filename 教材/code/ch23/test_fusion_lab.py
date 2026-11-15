import unittest

from fusion_lab import build, cluster, fixture, resolve, score


class FusionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.docs, cls.quotes, cls.annotations = fixture()
        cls.out = build(cls.docs, cls.quotes, cls.annotations)

    def test_reprints_do_not_add_feature_evidence(self):
        copies = [d for d in self.out["news_audit"] if d["status"] == "COPY"]
        self.assertEqual(len(copies), 20)
        used = {i for row in self.out["features"] for i in row["news_ids"]}
        self.assertTrue(used.isdisjoint(d["id"] for d in copies))

    def test_ambiguity_and_offsets(self):
        text = "🌐示例股票公司发布报告。"
        asset, evidence = resolve(text)
        self.assertEqual(asset, "EQ_DEMO")
        self.assertEqual(text[evidence["start"]:evidence["end"]], evidence["text"])
        self.assertIsNone(resolve(text + "示例债券基金")[0])
        for doc in self.out["news_audit"]:
            for evidence in doc["event_evidence"]:
                self.assertEqual(doc["text"][evidence["start"]:evidence["end"]], evidence["text"])

    def test_numbers_and_negation_change_the_claim(self):
        a = {"id": "a", "source": "A", "published": 4, "ready": 4,
             "text": "示例股票公司正式发布季度经营报告，预计拟发行债券10亿元。"}
        for changed in ("11亿元", "未发行"):
            text = (a["text"].replace("10亿元", changed) if changed.endswith("亿元")
                    else a["text"].replace("拟发行", changed))
            b = dict(a, id="b", source="B", ready=5, text=text)
            self.assertEqual(cluster([a, b])[1]["status"], "ANCHOR")

    def test_no_future_vocabulary_or_labels(self):
        model = self.out["model"]
        by_id = {d["id"]: d for d in self.docs}
        labels = {a["id"]: a for a in self.annotations}
        for identifier in model["train_ids"]:
            self.assertLess(by_id[identifier]["ready"], model["ready"])
            self.assertLess(labels[identifier]["ready"], model["ready"])
        self.assertIsNone(score(model, "燚龘麤"))

    def test_all_feature_dependencies_ready(self):
        available = {r["id"]: r["ready"] for r in self.quotes + self.docs}
        for row in self.out["features"]:
            for identifier in row["quote_ids"] + row["news_ids"]:
                self.assertLessEqual(available[identifier], row["decision_time"])
        eq26 = next(row for row in self.out["features"]
                    if row["asset"] == "EQ_DEMO" and row["decision_time"] == 26)
        self.assertEqual(eq26["quote_ids"], ["EQ_DEMO-24", "EQ_DEMO-25"])
        self.assertEqual(eq26["quote_age"], 1)
        self.assertTrue(all(row["label_ready"] >= row["label_end"] for row in self.out["labels"]))

    def test_future_change_preserves_feature_prefix(self):
        cut = 37
        docs = [dict(row, text="未来新文本") if row["ready"] > cut else row for row in self.docs]
        quotes = [dict(row, price=99) if row["ready"] > cut else row for row in self.quotes]
        anno = [dict(row, tone=-row["tone"]) if row["ready"] > cut else row for row in self.annotations]
        rerun = build(docs, quotes, anno, end=cut + 1)
        self.assertEqual(rerun["model"], self.out["model"])
        self.assertEqual(rerun["features"],
                         [row for row in self.out["features"] if row["decision_time"] <= cut])


if __name__ == "__main__":
    unittest.main()
