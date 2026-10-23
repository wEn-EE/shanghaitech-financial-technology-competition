"""Plot the recorded synthetic run without re-simulating data."""
import argparse
import csv
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np


def main(manifest, output):
    report=json.loads(manifest.read_text(encoding='utf-8'))
    with (manifest.parent/'synthetic_market.csv').open(encoding='utf-8') as stream:
        rows=list(csv.DictReader(stream))
    t=np.array([int(r['event_tick']) for r in rows])
    states=np.array([int(r['oracle_state']) for r in rows])
    fig,axes=plt.subplots(2,1,figsize=(10,6.5),layout='constrained')
    axes[0].step(t,states,where='post',lw=.9,color='#255c99')
    axes[0].axvline(report['model_release_tick'],ls='--',color='#b64b35',label='Model release')
    axes[0].set(yticks=[0,1],yticklabels=['Normal','Stress'],xlabel='Synthetic tick',
                title='SYNTHETIC: oracle state path (not an inferred regime)')
    axes[0].legend(loc='upper right')
    q=report['brownian']['qv'];n=np.array([int(k) for k in q])
    axes[1].loglog(n,[q[str(i)]['rmse'] for i in n],'o-',label='Simulation RMSE')
    axes[1].loglog(n,np.sqrt(2/n),'--',label='Theory: sqrt(2/n)')
    axes[1].set(xlabel='Number of intervals on [0,1]',ylabel='QV error RMSE',
                title='Brownian quadratic variation: 4,000 independent paths')
    axes[1].legend();axes[1].grid(alpha=.2,which='both')
    output.parent.mkdir(parents=True,exist_ok=True)
    fig.savefig(output,dpi=160);plt.close(fig)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest',type=Path);parser.add_argument('output',type=Path)
    args=parser.parse_args();main(args.manifest,args.output)
