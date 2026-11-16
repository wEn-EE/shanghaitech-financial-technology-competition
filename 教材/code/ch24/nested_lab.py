"""Nested forward validation of a chapter 23 fusion.json artifact."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path

import numpy as np

MARKET = ("return_last", "quote_age")
NEWS = ("news_score", "news_count", "news_scored_count")
GROUPS = {"market": MARKET, "market_news": MARKET + NEWS}
OUTER_STARTS = (48, 64, 80)
OUTER_WIDTH = 16
INNER_WIDTH = 6
PENALTIES = (0.1, 1.0, 10.0)


def row_index(records):
    indexed = {}
    for row in records:
        key = (row["asset"], row["decision_time"])
        if key in indexed:
            raise ValueError(f"duplicate row key: {key}")
        indexed[key] = row
    return indexed


def prepare(payload):
    if payload["schema"] != "ch23.fusion.v1" or payload["data_kind"] != "SYNTHETIC":
        raise ValueError("expected a chapter 23 synthetic fusion artifact")
    features, labels = map(row_index, (payload["features"], payload["labels"]))
    if features.keys() != labels.keys():
        raise ValueError("feature and label keys must match")
    rows = []
    for key in sorted(features, key=lambda key: (key[1], key[0])):
        asset, t = key
        feature, label = features[key], labels[key]
        if not payload["model"]["ready"] <= feature["feature_ready"] <= t:
            raise ValueError(f"feature unavailable at decision: {key}")
        if feature["model_id"] != payload["model_id"]:
            raise ValueError(f"unexpected text model: {key}")
        if not label["label_start"] == t < label["label_end"] <= label["label_ready"]:
            raise ValueError(f"invalid label chronology: {key}")
        x = {column: feature[column] for column in MARKET + NEWS}
        if any(v is not None and not math.isfinite(v) for v in x.values()):
            raise ValueError(f"nonfinite feature: {key}")
        if not math.isfinite(label["future_return"]):
            raise ValueError(f"nonfinite target: {key}")
        rows.append({"key": [asset, t], "t": t, "ready": label["label_ready"],
                     "x": x, "y": label["future_return"]})
    return rows


def eligible(rows, cutoff):
    # Strict inequality models a fit completed before the decision.
    return [row for row in rows if row["t"] < cutoff and row["ready"] < cutoff]


def period(rows, start, width):
    window = [row for row in rows if start <= row["t"] < start + width]
    panel_assets = {row["key"][0] for row in rows}
    if not panel_assets or len(window) != width * len(panel_assets):
        raise ValueError(f"incomplete panel in window starting at {start}")
    return window


def matrix(rows, columns):
    return np.array([[row["x"][name] for name in columns] for row in rows], dtype=float)


def target(rows):
    return np.array([row["y"] for row in rows])


def fit(rows, columns, count, penalty):
    x = matrix(rows, columns)
    y = target(rows)
    if len(y) < 2:
        raise ValueError("need at least two mature training rows")
    # Zero is an explicit policy for unknown news score, with counts retained.
    fill = np.array([0.0 if name == "news_score" or np.isnan(col).all()
                     else np.nanmedian(col) for name, col in zip(columns, x.T)])
    x = np.where(np.isnan(x), fill, x)
    mean, std = x.mean(axis=0), x.std(axis=0)
    scale = np.where(std > 1e-12, std, 1.0)
    z = (x - mean) / scale
    centered = y - y.mean()
    # Nonconstant columns have equal training norm after standardization.
    rank = sorted(np.flatnonzero(std > 1e-12),
                  key=lambda j: (-abs(z[:, j] @ centered), columns[j]))
    selected = rank[:count]
    design = z[:, selected]
    # Mean squared loss plus L2 penalty. Divide by n in both normal-equation terms.
    n = len(y)
    w = np.linalg.solve(design.T @ design / n + penalty * np.eye(len(selected)),
                        design.T @ centered / n)
    return {"columns": list(columns), "fill": fill.tolist(), "mean": mean.tolist(),
            "scale": scale.tolist(), "selected": [int(j) for j in selected],
            "weights": w.tolist(), "target_mean": float(y.mean())}


def predict(model, rows):
    x = matrix(rows, model["columns"])
    z = (np.where(np.isnan(x), model["fill"], x) - model["mean"]) / model["scale"]
    return z[:, model["selected"]] @ model["weights"] + model["target_mean"]


def tune(rows, outer_start, columns):
    inner = []
    for start in (outer_start - 20, outer_start - 12):
        training = eligible(rows, start)
        validation = period(rows, start, INNER_WIDTH)
        if any(row["ready"] >= outer_start for row in validation):
            raise ValueError("inner validation outcome unavailable at outer fit")
        inner.append((start, training, validation))

    trials = []
    for count in (1, 2):
        for penalty in PENALTIES:
            scores = []
            for _, training, validation in inner:
                model = fit(training, columns, count, penalty)
                mse = float(np.mean((target(validation) - predict(model, validation)) ** 2))
                scores.append(mse)
            trials.append({"count": count, "penalty": penalty, "mse": scores,
                           "mean_mse": float(np.mean(scores))})
    winner = min(trials, key=lambda trial: (trial["mean_mse"], trial["count"], trial["penalty"]))
    audit = [{"start": start, "training_keys": [r["key"] for r in training],
              "validation_keys": [r["key"] for r in validation],
              "last_label_ready": max(r["ready"] for r in validation)}
             for start, training, validation in inner]
    return winner, trials, audit


def outer_fold(rows, start):
    test = period(rows, start, OUTER_WIDTH)
    training = eligible(rows, start)
    y = target(test)
    report = {"start": start, "test_keys": [r["key"] for r in test],
              "training_keys": [r["key"] for r in training],
              "last_training_label_ready": max(r["ready"] for r in training),
              "zero_mse": float(np.mean(y**2)), "actual": y.tolist(), "groups": {}}
    for name, columns in GROUPS.items():
        choice, trials, audit = tune(rows, start, columns)
        model = fit(training, columns, choice["count"], choice["penalty"])
        forecast = predict(model, test)
        coefficients = {columns[j]: w / model["scale"][j]
                        for j, w in zip(model["selected"], model["weights"])}
        report["groups"][name] = {
            "choice": choice, "trials": trials, "inner": audit, "model": model,
            "mse": float(np.mean((forecast-y)**2)), "prediction": forecast.tolist(),
            "coefficients_original_scale": coefficients}
    report["delta_mse"] = report["groups"]["market_news"]["mse"] - report["groups"]["market"]["mse"]
    return report


def stability(folds, name):
    coefficients = [f["groups"][name]["coefficients_original_scale"] for f in folds]
    sets = [set(c) for c in coefficients]
    return {
        "selected_by_fold": [sorted(s) for s in sets],
        "frequency": {column: sum(column in s for s in sets) / len(sets)
                      for column in GROUPS[name]},
        "signs_by_fold": {column: [int(np.sign(c[column])) if column in c else None
                                    for c in coefficients] for column in GROUPS[name]},
        "adjacent_jaccard": [len(a & b) / len(a | b) if a | b else None
                             for a, b in zip(sets, sets[1:])],
    }


def evaluate(payload, starts=OUTER_STARTS):
    rows = prepare(payload)
    folds = [outer_fold(rows, start) for start in starts]
    return {"schema": "ch24.nested.v1", "data_kind": "SYNTHETIC",
            "input_model_id": payload["model_id"], "folds": folds,
            "mean_delta_mse": float(np.mean([f["delta_mse"] for f in folds])),
            "stability": {name: stability(folds, name) for name in GROUPS}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("fusion", type=Path, help="explicit chapter 23 fusion.json")
    args = parser.parse_args()
    body = args.fusion.read_bytes()
    report = evaluate(json.loads(body))
    report["input_sha256"] = hashlib.sha256(body).hexdigest()
    report["code_sha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    report["numpy"] = np.__version__
    directory = Path(__file__).parent / "runs" / datetime.now(timezone.utc).strftime(
        "nested_%Y%m%dT%H%M%S_%fZ")
    directory.mkdir(parents=True)
    path = directory / "nested.json"
    path.write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    print(path)
    for f in report["folds"]:
        print(f["start"], len(f["training_keys"]), len(f["test_keys"]),
              f["zero_mse"], *(g["mse"] for g in f["groups"].values()), f["delta_mse"])
    print("Mean delta:", report["mean_delta_mse"])
    print("Stability:", report["stability"])


if __name__ == "__main__":
    main()
