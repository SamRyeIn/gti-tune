"""Derive HP and TQ from R14 datalogs with physics (F = m*a), not the ECU's
Calc HP / Calc TQ channels.

Method
------
- Speed v from the undriven rear wheel speeds (mean of RL/RR) — immune to
  front-wheel slip. Falls back to `Vehicle Speed (km/h)` if rears read zero.
- Acceleration a = dv/dt via a centered local linear-regression slope over a
  ~0.6 s window (noise-robust derivative, no scipy needed).
- Force balance on the car during a pull:
      F_wheel = m_eff * a + F_aero + F_roll
      F_aero  = 0.5 * rho * Cd * A * v^2   (rho from logged ambient P and T)
      F_roll  = Crr * m * g
  m_eff = m * MASS_FACTOR accounts for rotating inertia (wheels, driveline,
  engine reflected through the 3rd-gear ratio).
- Wheel power P_wheel = F_wheel * v; crank estimate P_crank = P_wheel / ETA_DL.
- Crank torque TQ = P_crank / (rpm * 2*pi / 60).

Pulls are detected as sustained pedal > 90% spans, then trimmed to rows where
the gear channel equals the pull's gear (CLAUDE.md in-gear trim rule; the R14
PID list logs `Gear (gear)` = actual gear, no offset). The ECU's Calc HP,
identically trimmed, is overlaid purely as a cross-check.

Outputs to plots/fma_hp_tq/.
"""

import glob
import os

import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

# ---------------------------------------------------------------- constants
MASS_LB = 3400.0                    # car + driver, per Sam
MASS_KG = MASS_LB * 0.45359237      # 1542.2 kg
MASS_FACTOR = 1.05                  # rotating-inertia factor, 3rd gear
CD = 0.31                           # Mk7 GTI drag coefficient
FRONTAL_AREA = 2.21                 # m^2, Mk7 GTI
CRR = 0.011                         # rolling-resistance coefficient
ETA_DRIVELINE = 0.90                # DSG FWD wheel->crank correction
G = 9.80665
R_AIR = 287.05
W_TO_HP = 1.0 / 745.699872

PEDAL_WOT = 90.0                    # % pedal to call it a pull
MIN_PULL_S = 2.0
DERIV_WIN_S = 0.6                   # slope-fit window for dv/dt

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "plots", "fma_hp_tq")


def col(df, prefix):
    for c in df.columns:
        if c.startswith(prefix):
            return c
    raise KeyError(prefix)


def local_slope(t, y, win_s):
    """Centered local linear-regression slope dy/dt at each sample."""
    n = len(t)
    out = np.full(n, np.nan)
    half = win_s / 2.0
    j0, j1 = 0, 0
    for i in range(n):
        while t[j0] < t[i] - half:
            j0 += 1
        while j1 < n and t[j1] <= t[i] + half:
            j1 += 1
        tt, yy = t[j0:j1], y[j0:j1]
        if len(tt) >= 4:
            tm, ym = tt.mean(), yy.mean()
            denom = np.sum((tt - tm) ** 2)
            if denom > 0:
                out[i] = np.sum((tt - tm) * (yy - ym)) / denom
    return out


def find_pulls(t, pedal, rpm):
    """Contiguous spans of pedal > PEDAL_WOT lasting >= MIN_PULL_S with rpm rise."""
    wot = pedal > PEDAL_WOT
    pulls = []
    i = 0
    n = len(t)
    while i < n:
        if wot[i]:
            j = i
            while j + 1 < n and wot[j + 1]:
                j += 1
            if t[j] - t[i] >= MIN_PULL_S and rpm[j] - rpm[i] > 500:
                pulls.append((i, j))
            i = j + 1
        else:
            i += 1
    return pulls


def process_log(path):
    df = pd.read_csv(path)
    # The `Time` channel is in seconds but quantised to ~0.2 s (float32
    # precision at ~2.25e6 s uptime) while sampling is a uniform ~40 ms, so
    # reconstruct time from the sample index (same as plot_upshift_overboost).
    raw = df[col(df, "Time")].to_numpy()
    raw = raw - raw[0]
    t = np.arange(len(raw)) * (raw[-1] / (len(raw) - 1))
    pedal = df[col(df, "Pedal Pos")].to_numpy()
    rpm = df[col(df, "Engine Speed")].to_numpy()
    gear = df[col(df, "Gear")].to_numpy()
    vveh = df[col(df, "Vehicle Speed")].to_numpy() / 3.6
    vrl = df[col(df, "Wheel Speed RL")].to_numpy() / 3.6
    vrr = df[col(df, "Wheel Speed RR")].to_numpy() / 3.6
    p_amb = df[col(df, "Ambient Press")].to_numpy() * 1000.0   # kPa -> Pa
    t_amb = df[col(df, "Ambient Temp")].to_numpy() + 273.15
    calc_hp = df[col(df, "Calc HP")].to_numpy()
    calc_tq = df[col(df, "Calc TQ")].to_numpy()

    v_rear = 0.5 * (vrl + vrr)
    v = np.where(v_rear > 1.0, v_rear, vveh)             # rears read 0 at standstill

    a = local_slope(t, v, DERIV_WIN_S)
    rho = p_amb / (R_AIR * t_amb)

    f_aero = 0.5 * rho * CD * FRONTAL_AREA * v ** 2
    f_roll = CRR * MASS_KG * G
    f_wheel = MASS_KG * MASS_FACTOR * a + f_aero + f_roll
    p_wheel_hp = f_wheel * v * W_TO_HP
    p_crank_hp = p_wheel_hp / ETA_DRIVELINE
    omega = rpm * 2.0 * np.pi / 60.0
    with np.errstate(divide="ignore", invalid="ignore"):
        tq_crank_nm = np.where(omega > 50.0, p_crank_hp / W_TO_HP / omega, np.nan)

    results = []
    for (i0, i1) in find_pulls(t, pedal, rpm):
        # Split the WOT span into contiguous constant-gear runs (in-gear trim),
        # and start each run at its rpm minimum: the gear channel flips to the
        # next gear several samples before the shift lands, so a run's leading
        # rows can still be the old ratio's shift transient.
        gr = np.round(gear[i0:i1 + 1]).astype(int)
        idx_span = np.arange(i0, i1 + 1)
        runs = np.split(idx_span, np.where(np.diff(gr) != 0)[0] + 1)
        segs = []
        for run in runs:
            run = run[np.argmin(rpm[run]):]
            if len(run) >= 10 and rpm[run[-1]] - rpm[run[0]] > 500:
                segs.append(run)
        for idx in segs:
            g_attr = int(gr[idx[0] - i0])
            results.append(dict(
                file=os.path.basename(path), gear=g_attr, idx=idx,
                t=t[idx] - t[idx[0]], rpm=rpm[idx], v=v[idx],
                hp_wheel=p_wheel_hp[idx], hp_crank=p_crank_hp[idx],
                tq_crank=tq_crank_nm[idx],
                hp_aero=(f_aero * v * W_TO_HP)[idx],
                calc_hp=calc_hp[idx], calc_tq=calc_tq[idx],
            ))
    return results


def main():
    os.makedirs(OUT, exist_ok=True)
    pulls = []
    for path in sorted(glob.glob(os.path.join(HERE, "simostools-*.csv"))):
        pulls.extend(process_log(path))

    print(f"{len(pulls)} WOT pulls found")
    lines = ["| log | gear | rpm span | peak wheel HP | peak crank HP | "
             "peak crank TQ (Nm) | peak Calc HP (trimmed) |",
             "|---|---|---|---|---|---|---|"]
    for p in pulls:
        lines.append(
            f"| {p['file']} | {p['gear']} | {p['rpm'][0]:.0f}-{p['rpm'][-1]:.0f}"
            f" | {np.nanmax(p['hp_wheel']):.0f} | {np.nanmax(p['hp_crank']):.0f}"
            f" | {np.nanmax(p['tq_crank']):.0f} | {np.nanmax(p['calc_hp']):.0f} |")
    summary = "\n".join(lines)
    print(summary)
    with open(os.path.join(OUT, "summary.md"), "w") as f:
        f.write(summary + "\n")

    colors = plt.cm.tab10(np.linspace(0, 1, 10))

    # ---- figure 1: HP and TQ vs time, one column per pull
    npull = len(pulls)
    fig, axes = plt.subplots(2, npull, figsize=(4.2 * npull, 7.5),
                             sharey="row", squeeze=False)
    for k, p in enumerate(pulls):
        lab = f"{p['file'].split('-')[-1][:-4]} g{p['gear']}"
        ax = axes[0][k]
        ax.plot(p["t"], p["hp_crank"], color=colors[k], lw=2,
                label="F=ma crank HP")
        ax.plot(p["t"], p["hp_wheel"], color=colors[k], lw=1.2, ls="--",
                label="F=ma wheel HP")
        ax.plot(p["t"], p["calc_hp"], color="0.5", lw=1, ls=":",
                label="ECU Calc HP (trimmed)")
        ax.set_title(lab, fontsize=10)
        ax.grid(True, alpha=0.4)
        if k == 0:
            ax.set_ylabel("Power (hp)", fontweight="bold")
            ax.legend(fontsize=8)
        ax = axes[1][k]
        ax.plot(p["t"], p["tq_crank"], color=colors[k], lw=2,
                label="F=ma crank TQ")
        ax.plot(p["t"], p["calc_tq"], color="0.5", lw=1, ls=":",
                label="ECU Calc TQ (trimmed)")
        ax.set_xlabel("Time in pull (s)", fontweight="bold")
        ax.grid(True, alpha=0.4)
        if k == 0:
            ax.set_ylabel("Torque (Nm)", fontweight="bold")
            ax.legend(fontsize=8)
    fig.suptitle("R14 WOT pulls — physics-derived (F = m·a + drag + rolling) "
                 "HP and TQ vs time", fontweight="bold")
    fig.tight_layout(rect=[0, 0, 1, 0.95])
    fig.savefig(os.path.join(OUT, "hp_tq_vs_time.png"), dpi=140)

    # ---- figure 2: HP and TQ vs RPM, pulls overlaid
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 6))
    for k, p in enumerate(pulls):
        lab = f"{p['file'].split('-')[-1][:-4]} g{p['gear']}"
        order = np.argsort(p["rpm"])
        ax1.plot(p["rpm"][order], p["hp_crank"][order], color=colors[k],
                 lw=2, label=lab)
        ax1.plot(p["rpm"][order], p["hp_wheel"][order], color=colors[k],
                 lw=1, ls="--", alpha=0.7)
        ax2.plot(p["rpm"][order], p["tq_crank"][order], color=colors[k],
                 lw=2, label=lab)
    ax1.set_xlabel("Engine speed (rpm)", fontweight="bold")
    ax1.set_ylabel("Power (hp)", fontweight="bold")
    ax1.set_title("Crank HP (solid) and wheel HP (dashed)")
    ax1.grid(True, alpha=0.4)
    ax1.legend(fontsize=8)
    ax2.set_xlabel("Engine speed (rpm)", fontweight="bold")
    ax2.set_ylabel("Crank torque (Nm)", fontweight="bold")
    ax2.set_title("Crank torque")
    ax2.grid(True, alpha=0.4)
    ax2.legend(fontsize=8)
    fig.suptitle("R14 WOT pulls — physics-derived HP and TQ vs RPM "
                 f"(m = {MASS_LB:.0f} lb, Cd·A = {CD * FRONTAL_AREA:.2f} m², "
                 f"Crr = {CRR}, driveline η = {ETA_DRIVELINE})",
                 fontweight="bold")
    fig.tight_layout(rect=[0, 0, 1, 0.94])
    fig.savefig(os.path.join(OUT, "hp_tq_vs_rpm.png"), dpi=140)
    print(f"plots written to {OUT}")


if __name__ == "__main__":
    main()
