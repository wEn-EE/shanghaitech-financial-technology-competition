"""第4章科学配图，使用既有Matplotlib。"""
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from optimization_lab import minimize

q = np.array([[4., 1.], [1., 3.]])
c = np.array([-1., -2.])
fun = lambda x: float(.5 * x @ q @ x + c @ x)
grad = lambda x: q @ x + c
initial = np.array([2., -1.])
# 用同一Armijo规则记录路径；主实验历史另保存目标与残差。
path = [initial.copy()]
x = initial.copy()
for _ in range(12):
    direction = -grad(x)
    step = 1.
    while fun(x + step * direction) > fun(x) + 1e-4 * step * (grad(x) @ direction):
        step *= .5
    x = x + step * direction
    path.append(x.copy())
path = np.array(path)
optimum = np.linalg.solve(q, -c)
a, b = np.meshgrid(np.linspace(-.4, 2.2, 240), np.linspace(-1.3, 1.15, 240))
values = .5 * (4 * a * a + 2 * a * b + 3 * b * b) - a - 2 * b
fig, axes = plt.subplots(1, 2, figsize=(12, 4.8), layout="constrained")
axes[0].contour(a, b, values, levels=[-.95, -.8, -.4, 0, 1, 2, 4, 7, 10], colors="#bac5d1")
axes[0].plot(path[:, 0], path[:, 1], "o-", color="#176b94", ms=3, label="Gradient + backtracking")
axes[0].plot([initial[0], optimum[0]], [initial[1], optimum[1]], "--", color="#b84738", label="Newton: one update")
axes[0].plot(*optimum, "*", color="#183a2e", ms=12, label="Quadratic optimum")
axes[0].set(xlabel="Parameter 1", ylabel="Parameter 2", title="Same objective, different geometry")
axes[0].legend(fontsize=8)
steps = np.logspace(-16, -1, 180)
point, exact = .02, 1 / 1.02
forward = (np.log1p(point + steps) - np.log1p(point)) / steps
central = (np.log1p(point + steps) - np.log1p(point - steps)) / (2 * steps)
axes[1].loglog(steps, np.maximum(np.abs(forward - exact), 1e-18), label="Forward difference", color="#b84738")
axes[1].loglog(steps, np.maximum(np.abs(central - exact), 1e-18), label="Central difference", color="#176b94")
axes[1].set(xlabel="Difference step h", ylabel="Absolute derivative error", title="Smaller h is not always more accurate")
axes[1].legend(fontsize=8)
axes[1].grid(alpha=.2, which="both")
target = Path(__file__).resolve().parents[2] / "images" / "ch04_numerics.png"
target.parent.mkdir(exist_ok=True)
fig.savefig(target, dpi=150)
plt.close(fig)
print(target)

