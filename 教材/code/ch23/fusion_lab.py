"""Synthetic news-to-feature lab. Requires the existing NumPy installation."""
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import unicodedata

import numpy as np

MODEL_READY = 24
HORIZON = 3
ASSETS = ("EQ_DEMO", "BOND_DEMO", "GOLD_DEMO", "FX_DEMO")
ALIASES = ("示例股票公司", "示例债券基金", "示例黄金基金", "示例外汇组合")
EVENT = re.compile("盈利增长|亏损扩大|业绩改善|盈利下滑|未违约|拟发行")
THRESHOLD = 0.80


def fixture(n=96):
    rng = np.random.default_rng(23115)
    docs, quotes, annotations = [], [], []
    prices = np.full(len(ASSETS), 100.0)
    direction = np.zeros(len(ASSETS))
    for t in range(n + HORIZON):
        prices *= np.exp(0.002 * direction + rng.normal(0, 0.003, len(ASSETS)))
        j = t % len(ASSETS)
        tone = 1 if (t // len(ASSETS)) % 2 == 0 else -1
        direction[j] = tone
        for asset, price in zip(ASSETS, prices):
            quotes.append({"id": f"{asset}-{t}", "asset": asset, "time": t,
                           "ready": t + int(t % 13 == 0), "price": float(price)})
        if t >= n:
            continue
        phrases = ("盈利增长", "业绩改善") if tone > 0 else ("亏损扩大", "盈利下滑")
        phrase = phrases[(t // 8) % 2]
        text = f"{ALIASES[j]}发布季度经营报告，报告显示{phrase}，投资者关注后续经营表现。"
        ready = t + int(t % 7 == 0) * 2
        doc = {"id": f"news-{t}", "source": "wire", "published": t,
               "ready": ready, "text": text}
        docs.append(doc)
        annotations.append({"id": doc["id"], "tone": tone, "ready": ready + 1})
        if t % 5 == 0:
            docs.append(dict(doc, id=f"copy-{t}", source="portal", ready=ready + 1,
                             text=text.replace("报告显示", "报告揭示")))
    return docs, quotes, annotations


def grams(text, width):
    norm = re.sub(r"[\W_]+", "", unicodedata.normalize("NFKC", text).casefold())
    return Counter(norm[i:i + width] for i in range(len(norm) - width + 1))


def span(text, match):
    return {"start": match.start(), "end": match.end(), "text": match.group()}


def resolve(text):
    matches = []
    for asset, alias in zip(ASSETS, ALIASES):
        match = re.search(re.escape(alias), text)
        if match:
            matches.append((asset, span(text, match)))
    return matches[0] if len(matches) == 1 else (None, None)


def cluster(docs):
    """Online assignment to existing anchors, keyed by availability."""
    anchors, audit = [], []
    for doc in sorted(docs, key=lambda d: (d["ready"], d["id"])):
        asset, evidence = resolve(doc["text"])
        row = dict(doc, asset=asset, entity_evidence=evidence,
                   event_evidence=[span(doc["text"], m) for m in EVENT.finditer(doc["text"])])
        if asset is None:
            audit.append(dict(row, status="UNRESOLVED", anchor=None))
            continue
        shingles = set(grams(doc["text"], 3))
        signature = re.findall(r"[0-9]+(?:\.[0-9]+)?|未|否认|拟",
                               unicodedata.normalize("NFKC", doc["text"]))
        matches = []
        for prior, prior_grams, prior_signature in anchors:
            if (prior["asset"] != asset or prior["source"] == doc["source"]
                    or abs(doc["published"] - prior["published"]) > 1
                    or prior_signature != signature):
                continue
            union = shingles | prior_grams
            score = len(shingles & prior_grams) / len(union) if union else 0
            if score >= THRESHOLD:
                matches.append((score, prior["id"]))
        if matches:
            similarity, anchor = min(matches, key=lambda pair: (-pair[0], pair[1]))
            audit.append(dict(row, status="COPY", anchor=anchor, similarity=similarity))
        else:
            row = dict(row, status="ANCHOR", anchor=doc["id"])
            anchors.append((row, shingles, signature))
            audit.append(row)
    return audit


def vector(text, vocabulary, idf):
    counts = grams(text, 2)
    x = np.array([counts[word] * weight for word, weight in zip(vocabulary, idf)])
    norm = np.linalg.norm(x)
    return x / norm if norm else x


def sigmoid(value):
    return 1 / (1 + np.exp(-np.clip(value, -60, 60)))


def fit(audit, annotations):
    labels = {a["id"]: a for a in annotations if a["ready"] < MODEL_READY}
    train = [d for d in audit if d["status"] == "ANCHOR" and d["ready"] < MODEL_READY
             and d["id"] in labels]
    if {labels[d["id"]]["tone"] for d in train} != {-1, 1}:
        raise ValueError("need mature training labels for both classes")
    df = Counter(word for d in train for word in grams(d["text"], 2))
    vocabulary = sorted(df)
    idf = [float(np.log((1 + len(train)) / (1 + df[word])) + 1) for word in vocabulary]
    x = np.stack([vector(d["text"], vocabulary, idf) for d in train])
    y = np.array([int(labels[d["id"]]["tone"] == 1) for d in train])
    weights, bias = np.zeros(x.shape[1]), 0.0
    for _ in range(250):
        residual = sigmoid(x @ weights + bias) - y
        weights -= 0.8 * (x.T @ residual / len(y) + 0.02 * weights)
        bias -= 0.8 * residual.mean()
    return {"ready": MODEL_READY, "vocabulary": vocabulary, "idf": idf,
            "weights": weights.tolist(), "bias": float(bias),
            "train_ids": [d["id"] for d in train]}


def score(model, text):
    x = vector(text, model["vocabulary"], model["idf"])
    if not x.any():
        return None
    return float(2 * sigmoid(x @ model["weights"] + model["bias"]) - 1)


def build(docs, quotes, annotations, end=96):
    audit = cluster(docs)
    model = fit(audit, annotations)
    # Pin the implementation as well as learned parameters in downstream rows.
    model["code_sha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    model_id = hashlib.sha256(json.dumps(model, sort_keys=True).encode()).hexdigest()
    scored = [dict(d, score=score(model, d["text"]), score_ready=d["ready"])
              for d in audit if d["status"] == "ANCHOR" and d["ready"] >= model["ready"]]
    by_asset = {asset: [q for q in quotes if q["asset"] == asset] for asset in ASSETS}
    index = {(q["asset"], q["time"]): q for q in quotes}
    features, labels = [], []
    for t in range(model["ready"], end):
        for asset in ASSETS:
            seen = sorted((q for q in by_asset[asset] if q["ready"] <= t),
                          key=lambda q: q["time"])[-2:]
            news = [d for d in scored if d["asset"] == asset
                    and t - 8 < d["score_ready"] <= t]
            values = [d["score"] for d in news if d["score"] is not None]
            features.append({
                "asset": asset, "decision_time": t, "feature_ready": t,
                "quote_ids": [q["id"] for q in seen],
                "quote_age": t - seen[-1]["time"] if seen else None,
                "return_last": (seen[1]["price"] / seen[0]["price"] - 1
                                if len(seen) == 2 and seen[1]["time"] - seen[0]["time"] == 1
                                else None),
                "news_ids": [d["id"] for d in news], "news_count": len(news),
                "news_scored_count": len(values),
                "news_score": sum(values) / len(values) if values else None,
                "model_id": model_id})
            left, right = index.get((asset, t)), index.get((asset, t + HORIZON))
            if left and right:
                labels.append({"asset": asset, "decision_time": t,
                               "label_start": t, "label_end": t + HORIZON,
                               "label_ready": max(left["ready"], right["ready"]),
                               "future_return": right["price"] / left["price"] - 1,
                               "label_quote_ids": [left["id"], right["id"]]})
    truth = {a["id"]: a["tone"] for a in annotations}
    evaluation = [d for d in scored if 24 <= d["ready"] < 48 and d["id"] in truth]
    confusion = {actual: {pred: 0 for pred in ("negative", "positive", "unknown")}
                 for actual in ("negative", "positive")}
    for d in evaluation:
        actual = "positive" if truth[d["id"]] == 1 else "negative"
        pred = ("unknown" if d["score"] is None else
                "positive" if d["score"] >= 0 else "negative")
        confusion[actual][pred] += 1
    return {"schema": "ch23.fusion.v1", "data_kind": "SYNTHETIC",
            "model_id": model_id, "model": model, "news_audit": audit,
            "news_scored": scored, "features": features, "labels": labels,
            "evaluation_24_47": confusion}


def main():
    docs, quotes, annotations = fixture()
    output = build(docs, quotes, annotations)
    output["raw"] = {"documents": docs, "quotes": quotes, "annotations": annotations}
    directory = Path(__file__).parent / "runs" / datetime.now(timezone.utc).strftime(
        "fusion_%Y%m%dT%H%M%S_%fZ")
    directory.mkdir(parents=True)
    path = directory / "fusion.json"
    path.write_text(json.dumps(output, ensure_ascii=False, indent=2, allow_nan=False),
                    encoding="utf-8")
    print(path)
    print("Train:", len(output["model"]["train_ids"]), "Copies:",
          sum(d["status"] == "COPY" for d in output["news_audit"]))
    print("Features:", len(output["features"]), "Labels:", len(output["labels"]))
    print("Confusion:", output["evaluation_24_47"])


if __name__ == "__main__":
    main()
