"""第5章科学配图：基准率效应与等方差分布尾部。"""
from pathlib import Path
import math
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

fig, axes = plt.subplots(1, 2, figsize=(12, 4.6), layout="constrained")
p = np.logspace(-4, np.log10(.5), 250)
posterior = .9 * p / (.9 * p + .05 * (1 - p))
axes[0].semilogx(p, posterior, color="#166b94")
axes[0].plot(.01, 2 / 13, "o", color="#b34534")
axes[0].annotate("Prior 1% -> posterior 15.38%", (.01, 2 / 13),
                 xytext=(.00035, .48), arrowprops={"arrowstyle": "->"}, fontsize=9)
axes[0].set(xlabel="Prior probability of synthetic stress", ylabel="P(stress | alert)",
            title="Fixed sensitivity 90%, false positive rate 5%", ylim=(0, 1))
axes[0].grid(alpha=.2)
x, nu = np.linspace(-6, 6, 600), 5
scale = np.sqrt((nu - 2) / nu)
log_constant = math.lgamma((nu + 1) / 2) - math.lgamma(nu / 2) - .5 * math.log(nu * np.pi)
student = np.exp(log_constant - ((nu + 1) / 2) * np.log1p((x / scale) ** 2 / nu)) / scale
normal = np.exp(-x * x / 2) / np.sqrt(2 * np.pi)
axes[1].semilogy(x, normal, label="Normal: variance 1", color="#166b94")
axes[1].semilogy(x, student, label="Scaled t(5): variance 1", color="#b34534")
axes[1].set(xlabel="Standardized value", ylabel="Probability density (log scale)",
            title="Equal variance does not imply equal tail probabilities", ylim=(1e-8, 1))
axes[1].grid(alpha=.2)
axes[1].legend(fontsize=9)
target = Path(__file__).resolve().parents[2] / "images" / "ch05_probability.png"
target.parent.mkdir(exist_ok=True)
fig.savefig(target, dpi=150)
plt.close(fig)
print(target)
