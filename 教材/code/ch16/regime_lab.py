"""SYNTHETIC regime labels: causal filtering, retrospective smoothing and evidence."""
from __future__ import annotations
import hashlib
import json
import platform
from datetime import datetime, timezone
from pathlib import Path
import numpy as np

SEED, TRAIN, WINDOW = 20261028, 240, 20
ASSETS = ["EQ_DEMO", "BOND_DEMO", "GOLD_DEMO", "FX_DEMO"]
P = np.array([[.97, .03], [.10, .90]])  # row: previous; column: next
SD = np.array([[.006, .003, .005, .004], [.024, .012, .020, .016]])
PRIOR = np.array([10/13, 3/13])


def generate(n=720):
    rng = np.random.default_rng(SEED)
    states, returns, spreads = [], [], []
    state = int(rng.choice(2, p=PRIOR))
    for t in range(n):
        if t:
            state = int(rng.choice(2, p=P[state]))
        states.append(state)
        returns.append(rng.normal(size=4) * SD[state])
        spreads.append(max(.1, 2 + 10*state + rng.normal()))
    return np.array(states), np.array(returns), np.array(spreads)


def infer(returns, transition=P, scales=SD, prior=PRIOR):
    """Known DGP parameters for a mechanism experiment, NOT fitted estimates."""
    x = np.asarray(returns, float)
    a, sd, initial = map(lambda v: np.asarray(v, float), (transition, scales, prior))
    if (x.ndim != 2 or not len(x) or a.shape != (2, 2)
            or sd.shape != (2, x.shape[1]) or initial.shape != (2,)):
        raise ValueError("SHAPE")
    if (np.isinf(x).any() or not np.isfinite(a).all() or np.any(a <= 0)
            or not np.allclose(a.sum(axis=1), 1, rtol=0, atol=1e-12)
            or not np.isfinite(sd).all() or np.any(sd <= 0)
            or not np.isfinite(initial).all() or np.any(initial <= 0)
            or not np.isclose(initial.sum(), 1, rtol=0, atol=1e-12)):
        raise ValueError("PARAMETERS")
    predicted, filtered, log_evidence = [], [], []
    previous = initial.copy()
    for t, row in enumerate(x):
        pred = initial.copy() if t == 0 else previous @ a
        observed = np.isfinite(row)
        with np.errstate(over="raise", invalid="raise"):
            log_density = -.5 * np.sum(
                np.log(2*np.pi*sd[:, observed]**2)
                + (row[observed]/sd[:, observed])**2, axis=1)
        log_weight = np.log(pred) + log_density
        shift = np.max(log_weight)
        weight = np.exp(log_weight-shift)
        posterior = weight/weight.sum()
        predicted.append(pred)
        filtered.append(posterior)
        log_evidence.append(float(shift+np.log(weight.sum())))
        previous = posterior
    pred, filt = np.array(predicted), np.array(filtered)
    smooth = filt.copy()
    for t in range(len(x)-2, -1, -1):
        smooth[t] = filt[t] * (a @ (smooth[t+1]/pred[t+1]))
        smooth[t] /= smooth[t].sum()
    return pred, filt, smooth, np.array(log_evidence)


def features(returns, spreads):
    x, spread = np.asarray(returns, float), np.asarray(spreads, float)
    if x.ndim != 2 or x.shape[1] != 4 or spread.shape != (len(x),):
        raise ValueError("FEATURE_SHAPE")
    if np.isinf(x).any() or np.isinf(spread).any() or np.any(spread < 0):
        raise ValueError("FEATURE_DOMAIN")
    out = []
    for t in range(len(x)):
        window = x[max(0, t-WINDOW+1):t+1, 0]
        ready = len(window) == WINDOW and np.isfinite(window).all()
        out.append({"step": t,
                    "momentum": float(window.sum()) if ready else None,
                    "volatility": float(window.std(ddof=1)*np.sqrt(252)) if ready else None,
                    "spread_bps": float(spread[t]) if np.isfinite(spread[t]) else None})
    return out


def calibrate(rows, cutoff=TRAIN):
    if cutoff <= WINDOW or cutoff > len(rows):
        raise ValueError("CALIBRATION_RANGE")
    history = rows[:cutoff]
    vols = [r["volatility"] for r in history if r["volatility"] is not None]
    spreads = [r["spread_bps"] for r in history if r["spread_bps"] is not None]
    if len(vols) < WINDOW or len(spreads) < WINDOW:
        raise ValueError("INSUFFICIENT_CALIBRATION")
    exit_level, enter = np.quantile(vols, [.6, .8], method="linear")
    if not enter > exit_level:
        raise ValueError("DEGENERATE_THRESHOLDS")
    return {"available_step": cutoff-1, "vol_enter": float(enter),
            "vol_exit": float(exit_level), "spread_high": float(np.quantile(spreads, .9)),
            "momentum_band": .02, "window": WINDOW, "annualization": 252,
            "valid_vol_windows": len(vols), "valid_spreads": len(spreads),
            "version": "rule-v1", "quantile_method": "linear"}


def label_rows(rows, cfg):
    high, output = False, []
    for r in rows:
        t, vol, mom, spread = r["step"], r["volatility"], r["momentum"], r["spread_bps"]
        if t <= cfg["available_step"]:
            continue  # No pretending that full calibration was available earlier.
        if vol is not None:
            if not high and vol >= cfg["vol_enter"]:
                high = True
            elif high and vol <= cfg["vol_exit"]:
                high = False
        output.append({"step": t, "rule_version": cfg["version"],
                       "trend": "UNKNOWN" if mom is None else
                           ("UP" if mom > cfg["momentum_band"] else
                            "DOWN" if mom < -cfg["momentum_band"] else "SIDEWAYS"),
                       "volatility": "UNKNOWN" if vol is None else ("HIGH" if high else "LOW"),
                       "liquidity": "UNKNOWN" if spread is None else
                           ("TIGHT" if spread > cfg["spread_high"] else "NORMAL")})
    return output


def evidence_asof(records, decision):
    """Artificial integer clock; retain publication and availability separately."""
    unique, selected, versions = {}, {}, {}
    for r in records:
        if not r["reference_step"] <= r["published_step"] <= r["available_step"]:
            raise ValueError("EVIDENCE_TIME")
        if r["id"] in unique and unique[r["id"]] != r:
            raise ValueError("ID_CONFLICT")
        unique[r["id"]] = r
        key = (r["reference_step"], r["version"])
        if key in versions and versions[key] != r:
            raise ValueError("VERSION_CONFLICT")
        versions[key] = r
    for r in unique.values():
        if r["available_step"] > decision:
            continue
        key = r["reference_step"]
        if key not in selected or r["version"] > selected[key]["version"]:
            selected[key] = r
        elif r["version"] == selected[key]["version"] and r != selected[key]:
            raise ValueError("VERSION_CONFLICT")
    return [dict(selected[k]) for k in sorted(selected)]


def score(probability, truth):
    p, y = np.asarray(probability), np.asarray(truth)
    if (p.shape != y.shape or not len(y) or not np.isfinite(p).all()
            or np.any((p < 0) | (p > 1)) or not np.isin(y, [0, 1]).all()):
        raise ValueError("SCORE_DOMAIN")
    clipped = np.clip(p, 1e-12, 1-1e-12)
    return {"brier": float(np.mean((p-y)**2)),
            "log_loss": float(-np.mean(y*np.log(clipped)+(1-y)*np.log(1-clipped))),
            "n": len(y)}


def main():
    truth, x, spread = generate()
    x[310] = np.nan
    x[420, 2] = np.nan
    spread[310] = np.nan
    rows = features(x, spread)
    cfg = calibrate(rows)
    labels = label_rows(rows, cfg)
    pred, filt, smooth, log_ev = infer(x)
    evidence = [
        {"id": "E1", "reference_step": 200, "published_step": 268,
         "available_step": 270, "version": 1, "label": "SLOWDOWN",
         "source": "SYNTHETIC"},
        {"id": "E2", "reference_step": 200, "published_step": 338,
         "available_step": 340, "version": 2, "label": "CONTRACTION",
         "source": "SYNTHETIC"}]
    mask = (np.arange(len(x)) >= TRAIN) & np.isfinite(x).any(axis=1)
    n = int(mask.sum())
    summary = {"data_kind": "SYNTHETIC", "known_parameter_oracle": True,
               "filter": score(filt[mask, 1], truth[mask]),
               "constant_prior": score(np.full(n, PRIOR[1]), truth[mask]),
               "smooth_vs_filter_map_changes": int(np.sum(
                   smooth[mask].argmax(1) != filt[mask].argmax(1))),
               "uncertain_observed_steps": int(np.sum(filt[mask].max(1) < .8)),
               "unknown_vol_steps": sum(r["volatility"] == "UNKNOWN" for r in labels),
               "high_vol_up_steps": sum(r["volatility"] == "HIGH" and r["trend"] == "UP"
                                        for r in labels),
               "evidence_snapshots": {str(t): evidence_asof(evidence, t)
                                      for t in (269, 270, 339, 340)}}
    out = Path(__file__).parent/"runs"/datetime.now(timezone.utc).strftime("run_%Y%m%dT%H%M%S_%fZ")
    out.mkdir(parents=True, exist_ok=False)
    np.savez_compressed(out/"samples.npz", truth=truth, returns=x, spreads=spread,
                        predicted=pred, filtered=filt, smoothed=smooth, log_evidence=log_ev)
    configs = {"rule": cfg, "transition": P.tolist(), "scales": SD.tolist(),
               "prior": PRIOR.tolist(), "seed": SEED, "train": TRAIN,
               "missing_injections": {"all_returns": [310], "gold_return": [420], "spread": [310]}}
    for name, value in (("configuration.json", configs), ("labels.json", labels),
                        ("evidence.json", evidence), ("results.json", summary)):
        (out/name).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+"\n",
                              encoding="utf-8")
    manifest = {"python": platform.python_version(), "numpy": np.__version__,
                "data_kind": "SYNTHETIC", "code_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                "sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in out.iterdir()}}
    (out/"manifest.json").write_text(json.dumps(manifest, indent=2)+"\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(out.resolve())


if __name__ == "__main__":
    main()
