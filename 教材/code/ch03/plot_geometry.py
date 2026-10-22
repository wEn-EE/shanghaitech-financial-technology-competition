"""用已安装matplotlib绘制教学示意，不表示实测金融分布。"""
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

fig, axes = plt.subplots(1, 2, figsize=(10, 4.3), constrained_layout=True)
ax = axes[0]
ax.plot([-.4, 2.4], [-.4, 2.4], color="#94a3b8", label="model subspace")
ax.quiver([0, 0, 1], [0, 0, 1], [2, 1, 1], [0, 1, -1],
          angles="xy", scale_units="xy", scale=1,
          color=["#2563eb", "#059669", "#dc2626"], width=.012)
ax.text(1.65, -.24, "y = (2, 0)", color="#2563eb")
ax.text(.27, 1.18, "projection = (1, 1)", color="#059669")
ax.text(1.45, .7, "residual", color="#dc2626")
ax.set(xlim=(-.4, 2.45), ylim=(-.4, 2.45), title="Orthogonal projection",
       xlabel="coordinate 1", ylabel="coordinate 2")
ax.set_aspect("equal")
ax.legend(loc="upper left", fontsize=8)

ax = axes[1]
cov = np.array([[4., 3.], [3., 4.]])
eigenvalues, q = np.linalg.eigh(cov)
theta = np.linspace(0, 2*np.pi, 400)
circle = np.vstack([np.cos(theta), np.sin(theta)])
ellipse = q @ np.diag(np.sqrt(eigenvalues)) @ circle
ax.plot(circle[0], circle[1], "--", color="#94a3b8", label="unit circle")
ax.plot(ellipse[0], ellipse[1], color="#2563eb", label="linear image")
for j in range(2):
    vector = q[:, j] * np.sqrt(eigenvalues[j])
    ax.plot([-vector[0], vector[0]], [-vector[1], vector[1]], color="#059669", linewidth=1)
ax.set(xlim=(-3, 3), ylim=(-3, 3), title="Eigenvectors and axis scales",
       xlabel="asset 1 deviation (percentage points)",
       ylabel="asset 2 deviation (percentage points)")
ax.set_aspect("equal")
ax.legend(loc="upper left", fontsize=8)
for ax in axes:
    ax.axhline(0, color="#cbd5e1", linewidth=.7)
    ax.axvline(0, color="#cbd5e1", linewidth=.7)
    ax.grid(alpha=.2)
target = Path(__file__).resolve().parents[2] / "images" / "ch03_geometry.png"
target.parent.mkdir(parents=True, exist_ok=True)
fig.savefig(target, dpi=150, facecolor="white")
plt.close(fig)
print(target)
