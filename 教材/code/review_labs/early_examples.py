"""Worked examples for chapters 1–16. Run with an existing Anaconda."""
import argparse
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import json
import math
from pathlib import Path
import sys
from zoneinfo import ZoneInfo

import numpy as np
from scipy.stats import chi2

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / f"ch{i:02d}") for i in range(1, 22)]

from monitor import Monitor, demo_lines, parse_quote
from panel_lab import demo_data, prepare_quotes, build_panel, macro_asof
from market_lab import call_auction
from cashflow_lab import Bond
import derivatives_lab
import risk_lab
from contagion_lab import linear_network
from regime_lab import evidence_asof, label_rows


def ch01():
    src = [line for line in demo_lines()[:5] if json.loads(line)["event_id"] in {"e1", "e2"}]
    one, two = map(parse_quote, src)
    # Start with one asset and a scalar state before using the general monitor.
    previous = None
    baseline = []
    for quote in (one, two):
        baseline.append(None if previous is None else (quote.price-previous)/previous)
        previous = quote.price
    assert baseline == [None, .01]
    engine = Monitor(window=2, threshold=.009)
    results = [engine.process(q) for q in (one, two, two, replace(two, price=102))]
    assert [line[0] for line in results] == ["accepted", "accepted", "duplicate", "conflict"]
    assert engine.latest[(one.source,one.symbol)].price == 101
    assert results[0][2]["return"] is None and results[1][2]["jump_alert"]
    return {"return": results[1][2]["return"], "count_after_duplicate": len(engine.returns[(one.source,one.symbol)])}


def ch02():
    raw, assets, macro, clock = demo_data()
    decisions = clock[1:3] + timedelta(seconds=10)
    q, _ = prepare_quotes(raw, assets, decisions[-1])
    result = build_panel(q, assets, clock, decisions[-1])
    returns = result["returns"].loc[clock[1:3], ["EQ_DEMO", "GOLD_DEMO"]]
    assert np.allclose(returns["EQ_DEMO"], [.01,-.01])
    assert math.isnan(returns.iloc[1]["GOLD_DEMO"])
    assert math.isclose(result["monitoring"].loc[clock[2], "coverage"], .8)
    result_macro = macro_asof(decisions, macro, decisions[-1])
    late = clock[3] + timedelta(seconds=20)
    assert macro_asof([late-timedelta(seconds=10),late],macro,late)["value"].tolist() == [1.9,2.1]
    return {"equity": returns["EQ_DEMO"].tolist(),
            "gold": [float(returns.iloc[0]["GOLD_DEMO"]), None],
            "coverage": result["monitoring"].loc[clock[1:3],"coverage"].tolist(),
            "macro": result_macro["value"].tolist()}


def ch03():
    a = np.arange(1., 7.)
    x = np.column_stack((a, a + 1e-8*np.array([1,-1,1,-1,1,-1])))
    y = x @ [3.,-2.]
    stable = np.linalg.lstsq(x,y,rcond=None)[0]
    try:
        normal = np.linalg.solve(x.T @ x,x.T @ y)
        normal_error = float(np.linalg.norm(normal-[3,-2]))
    except np.linalg.LinAlgError:
        normal, normal_error = None, None
    assert np.linalg.norm(stable-[3,-2]) < 1e-5
    return {"cond_X": np.linalg.cond(x), "cond_XtX": np.linalg.cond(x.T @ x),
            "svd": stable.tolist(), "normal": None if normal is None else normal.tolist(),
            "normal_coefficient_error": normal_error}


def ch04():
    # V = diag(1,4), sum(w)=1. Stationarity requires equal marginal gradients.
    v = np.diag([1.,4.])
    result = []
    for w in [np.array([.8,.2]),np.array([.5,.5]),np.array([1.01,-.01])]:
        g = v @ w
        result.append({"w": w.tolist(), "objective": float(.5*w@g),
                       "sum_residual": abs(float(w.sum())-1), "minimum": float(w.min()),
                       "interior_kkt_gap": abs(float(g[0]-g[1]))})
    assert result[0]["interior_kkt_gap"] == 0 and result[1]["interior_kkt_gap"] == 1.5
    return result


def ch05():
    # Columns = alerts, no alerts. Rows = event, no event.
    a,b,c,d = 80,20,495,9405
    observed = a/(a+c)
    base = (a+b)/(a+b+c+d)
    predicted = (a/(a+b)*base) / (a/(a+b)*base+c/(c+d)*(1-base))
    assert math.isclose(observed,predicted)
    return {"posterior": observed, "false_positive_rate": c/(c+d),
            "model_group_claim": .8, "calibration_gap": .8-observed}


def ch06():
    rng=np.random.default_rng(613)
    n=100_000
    z=np.cumsum(rng.normal(size=(n,10)),axis=1)/np.sqrt(np.arange(1,11))
    fixed=np.mean(abs(z[:,-1])>1.95996398454)
    repeated=np.mean(np.any(abs(z)>1.95996398454,axis=1))
    bonf=np.mean(np.any(abs(z)>2.80703376834,axis=1))
    assert repeated>fixed and bonf<.05
    return {"paths":n,"fixed":float(fixed),"any_look":float(repeated),"bonferroni":float(bonf)}


def ch08():
    rng=np.random.default_rng(808)
    innovation=rng.normal(size=321)
    changes=np.zeros(321)
    for t in range(1,len(changes)):
        changes[t]=.7*changes[t-1]+innovation[t]
    levels=100+np.cumsum(changes)
    diff=np.diff(levels)
    x=diff[:199]
    slope=float(x[:-1]@x[1:]/(x[:-1]@x[:-1]))
    # Frozen slope, each next residual uses only the preceding observed difference.
    actual=diff[199:]
    residual=actual-slope*diff[198:-1]
    def diagnostic(e):
        e=e-e.mean()
        n=len(e)
        rho=np.array([e[k:]@e[:-k]/(e@e) for k in range(1,7)])
        q=n*(n+2)*np.sum(rho**2/(n-np.arange(1,7)))
        return {"lag1":float(rho[0]),"Q6":float(q),"reference_p":float(chi2.sf(q,6))}
    assert abs(diagnostic(residual)["lag1"])<abs(diagnostic(actual)["lag1"])
    return {"slope":slope,"random_walk_residual":diagnostic(actual),
            "arima_110_residual":diagnostic(residual)}


def ch09():
    buys=[("b1",102,3),("b2",101,5),("b3",101,4)]
    sells=[("s1",100,5),("s2",101,2),("s3",102,3)]
    book=call_auction([(p,q) for _,p,q in buys],[(p,q) for _,p,q in sells],101)
    p, volume=book["price"],book["volume"]
    def allocate(orders, buy):
        remaining=volume
        fills={}
        for i, price, qty in sorted(orders,key=lambda r: -r[1] if buy else r[1]):
            if (price>=p if buy else price<=p):
                fills[i]=min(remaining,qty)
                remaining-=fills[i]
        assert remaining==0
        return fills
    bid,ask=allocate(buys,True),allocate(sells,False)
    assert p==101 and bid=={"b1":3,"b2":4,"b3":0}
    return {"price":p,"volume":volume,"buy_fills":bid,"sell_fills":ask}


def ch10():
    bond=Bond(face=100,coupon=.04,periods=3,frequency=1)
    dated=[]
    for year,(t,cash) in zip(range(2027,2030),bond.flows()):
        dated.append({"date":f"{year}-11-16","periods":t,"cash":cash,"pv":cash/1.05**t})
    pv=sum(r["pv"] for r in dated)
    assert math.isclose(pv,bond.metrics(.05)["dirty"])
    return {"dated_flows":dated,"price":pv}


def ch11():
    fixture=derivatives_lab.synthetic_inputs()
    args={k:fixture[k] for k in ("rows","schedule","capital","multiplier","fee_per_leg","schedule_available")}
    rows=derivatives_lab.roll_ledger(**args)
    splice=[10*(r["mark_after"]-rows[0]["mark_after"]) for r in rows]
    for i,row in enumerate(rows[1:],1):
        assert math.isclose(row["equity"]-rows[i-1]["equity"],row["variation"]-row["fee"])
    assert rows[1]["equity"]-rows[0]["equity"]==6
    return [{"t":r["event_at"],"held_after":r["held_after"],"variation":r["variation"],
             "fee":r["fee"],"account_pnl":r["equity"]-rows[0]["equity"],"splice":g}
            for r,g in zip(rows,splice)]


def ch12():
    rows=risk_lab.sampling_experiment(np.random.default_rng(1208))
    cfg=risk_lab.CONFIG
    true_var=cfg["daily_sigma"]**2
    eta2=cfg["noise_sigma"]**2
    def mse(row):
        m=row["increments"]
        bias=2*m*eta2
        variance=2*(m*(true_var/m+2*eta2)**2+2*(m-1)*eta2**2)
        return bias**2+variance
    chosen=min(rows,key=mse)
    threshold=true_var*1.5
    return {"threshold":threshold,"min_mse_stride":chosen["stride"],
            "results":[{"stride":r["stride"],"rv":r["noisy_mean"],"theory_mse":mse(r),
                        "mean_above_threshold":r["noisy_mean"]>threshold} for r in rows]}


def ch13():
    market=np.array([-.02,-.01,0,.01,.02,.015,-.005,.01,-.02])
    noise=np.array([.001,-.002,.002,-.002,.001,0,0,0,0])
    abnormal=np.array([0,0,0,0,0,0,.02,.01,-.005])
    asset=.001+1.2*market+noise+abnormal
    def design(x): return np.column_stack((np.ones(len(x)),x))
    coef=np.linalg.lstsq(design(market[:5]),asset[:5],rcond=None)[0]
    expected=design(market[6:])@coef
    ar=asset[6:]-expected
    assert np.allclose(ar,[.02,.01,-.005])
    return {"training":list(range(5)),"excluded":5,"event_window":[6,7,8],
            "market":market[6:].tolist(),"returns":asset[6:].tolist(),"expected":expected.tolist(),
            "ar":ar.tolist(),"car":float(ar.sum()),"model":coef.tolist()}


def ch14():
    release=datetime(2022,12,13,8,30,tzinfo=ZoneInfo("America/New_York")).astimezone(timezone.utc)
    ready=release+timedelta(seconds=20)
    observations=[]
    for delta in (-1,5,20):
        decision=release+timedelta(seconds=delta)
        observations.append({"utc":decision.isoformat(),"yoy_percent":7.1 if decision>=ready else None,
                             "mom_sa_percent":.1 if decision>=ready else None})
    assert [r["yoy_percent"] for r in observations]==[None,None,7.1]
    return observations


def ch15():
    rows=[]
    for s in [.5,1.,1.5,2.]:
        h=s*np.array([[0.,.8],[.4,0.]])
        try:
            rows.append({"scale":s, **linear_network(h,[1.,0.])})
        except ValueError as exc:
            rows.append({"scale":s,"status":str(exc)})
    assert rows[-1]["status"]=="UNSTABLE_LINEARIZATION"
    return rows


def ch16():
    release=datetime(2020,3,15,17,tzinfo=ZoneInfo("America/New_York")).astimezone(timezone.utc)
    sec=int(release.timestamp())
    proof={"id":"FOMC-20200315","reference_step":sec,"published_step":sec,
           "available_step":sec+60,"version":1,"target_low_pct":0,"target_high_pct":.25}
    old=datetime(2020,3,3,10,tzinfo=ZoneInfo("America/New_York"))
    old_sec=int(old.timestamp())
    prior={"id":"FOMC-20200303","reference_step":old_sec,"published_step":old_sec,
           "available_step":old_sec+60,"version":1,"target_low_pct":1,"target_high_pct":1.25}
    cfg={"available_step":sec-300,"vol_enter":.025,"vol_exit":.018,
         "momentum_band":.01,"spread_high":25,"version":"TEACHING-v1"}
    cuts=[sec-1,sec,sec+60]
    unknown=[{"step":t,"volatility":None,"momentum":None,"spread_bps":None} for t in cuts]
    labels=label_rows(unknown,cfg)
    result=[]
    for i,t in enumerate(cuts):
        visible=evidence_asof([prior,proof],t)
        current=visible[-1]
        easing=len(visible)==2 and current["target_high_pct"] < visible[0]["target_high_pct"]
        result.append({"utc":datetime.fromtimestamp(t,timezone.utc).isoformat(),
                       "policy":"EASING_ANNOUNCED" if easing else "PREVIOUS_TARGET",
                       "range_pct":[current["target_low_pct"],current["target_high_pct"]],
                       "evidence":[p["id"] for p in visible],"market_axes":labels[i]})
    assert result[-1]["policy"]=="EASING_ANNOUNCED" and labels[-1]["volatility"]=="UNKNOWN"
    return result


CASES = {i: globals()[f"ch{i:02d}"] for i in [1,2,3,4,5,6,8,9,10,11,12,13,14,15,16]}

if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("chapter", type=int, nargs="?", choices=CASES)
    args=parser.parse_args()
    selected=[args.chapter] if args.chapter else CASES
    print(json.dumps({i: CASES[i]() for i in selected},indent=2,ensure_ascii=False,allow_nan=False))
