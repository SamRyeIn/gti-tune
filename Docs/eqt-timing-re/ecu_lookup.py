"""
The ECU-side model of the base ignition lookup, and the sparse design matrices
that invert it.

What the ECU does (and what `Ignition Table Output (Degrees)` reports):

    iga_tab = SUM_i SUM_e  w_in[i](cam_in) * w_ex[e](cam_ex)
                           * bilinear( M[vls][i][e], rpm, airmass )

where `M[vls][i][e]` is

    `IP_IGA_BAS_IVVT_VVL_PORT_L[vls][i][e]`  -- Basic Ignition Angle,
        low port-flap position, valve-lift state vls, intake cam index i,
        exhaust cam index e; f(RPM, airmass), 16x16, uint8,
        deg = (raw - 95) / 2.666667  ->  0.375 degCRK per LSB

and `w_in` / `w_ex` are 3-node piecewise-linear partitions of unity over the
cam phaser positions. The support points for those partitions are NOT exposed
in the XDF, so they are fitted from data alongside the cells.

Everything here is linear in the map cells once the cam support points are
fixed, which is what makes the inversion a (large, sparse) least-squares
problem rather than a general nonlinear fit.
"""

import numpy as np
from scipy import sparse

# 0.375 degCRK per LSB -- deg = (raw - 95) / 2.666667, uint8 store.
LSB_DEG = 1.0 / (8.0 / 3.0)
RAW_OFFSET, RAW_SCALE = 95.0, 8.0 / 3.0

NX = NY = 16  # every IP_IGA_BAS map is 16 (rpm) x 16 (airmass)


def quantize(deg):
    """Snap a physical angle onto the uint8 store's representable grid."""
    return np.clip(np.round(deg * RAW_SCALE + RAW_OFFSET), 0, 255) / RAW_SCALE \
        - RAW_OFFSET / RAW_SCALE


def interp_weights(axis, v):
    """Clamped linear-interpolation weights on a monotone breakpoint axis.

    Returns (lo_index, hi_index, hi_fraction). Outside the axis the ECU holds
    the end value, so the fraction saturates at 0 or 1 rather than extrapolating.
    """
    axis = np.asarray(axis, dtype=float)
    v = np.asarray(v, dtype=float)
    idx = np.clip(np.searchsorted(axis, v, side="right") - 1, 0, len(axis) - 2)
    lo, hi = axis[idx], axis[idx + 1]
    frac = np.clip((v - lo) / (hi - lo), 0.0, 1.0)
    return idx, idx + 1, frac


def bilinear_terms(x_axis, y_axis, x, y):
    """The 4 corner (flat_cell_index, weight) pairs for each sample.

    Cell layout is row-major over (y=airmass, x=rpm) to match `TableView.values`.
    """
    xi0, xi1, xf = interp_weights(x_axis, x)
    yi0, yi1, yf = interp_weights(y_axis, y)
    cells = np.stack([yi0 * NX + xi0, yi0 * NX + xi1,
                      yi1 * NX + xi0, yi1 * NX + xi1], axis=1)
    w = np.stack([(1 - yf) * (1 - xf), (1 - yf) * xf,
                  yf * (1 - xf), yf * xf], axis=1)
    return cells, w


def cam_weights(support, v):
    """3-node piecewise-linear partition of unity over a cam phaser position.

    `support` is the ascending triple of cam positions at which map indices
    0, 1 and 2 are exact. Between them the ECU blends linearly; outside them it
    holds the end map. Rows sum to 1 by construction.
    """
    s = np.asarray(support, dtype=float)
    v = np.asarray(v, dtype=float)
    w = np.zeros((v.size, 3))
    lower = v <= s[1]
    f = np.clip((v - s[0]) / (s[1] - s[0]), 0.0, 1.0)
    w[lower, 0] = 1 - f[lower]
    w[lower, 1] = f[lower]
    upper = ~lower
    g = np.clip((v - s[1]) / (s[2] - s[1]), 0.0, 1.0)
    w[upper, 1] = 1 - g[upper]
    w[upper, 2] = g[upper]
    return w


def design_matrix(x_axis, y_axis, rpm, maf, cam_in, cam_ex, group,
                  n_groups, sup_in=None, sup_ex=None):
    """Sparse A with  A @ theta = predicted iga_tab.

    `group` selects which *set* of maps a sample uses (valve-lift state, and
    optionally port-flap state). With `sup_in`/`sup_ex` given, each group owns
    a full 3x3 cam-indexed map stack; with them None, each group owns a single
    surface and the cam blend is dropped (the M0 hypothesis).

    Parameter vector layout: group-major, then cam index (i*3+e), then cell.
    """
    n = len(rpm)
    cells, wxy = bilinear_terms(x_axis, y_axis, rpm, maf)

    if sup_in is None:
        n_maps, cam_w = 1, np.ones((n, 1))
    else:
        n_maps = 9
        cam_w = (cam_weights(sup_in, cam_in)[:, :, None]
                 * cam_weights(sup_ex, cam_ex)[:, None, :]).reshape(n, 9)

    per_group = n_maps * NX * NY
    base = group.astype(np.int64) * per_group

    rows = np.repeat(np.arange(n), 4 * n_maps)
    cols = (base[:, None, None] + (np.arange(n_maps) * NX * NY)[None, :, None]
            + cells[:, None, :]).reshape(-1)
    vals = (cam_w[:, :, None] * wxy[:, None, :]).reshape(-1)

    keep = vals != 0.0
    A = sparse.csr_matrix((vals[keep], (rows[keep], cols[keep])),
                          shape=(n, n_groups * per_group))
    return A, per_group, n_maps


def smoothness_operator(n_groups, n_maps, lam_smooth, lam_agree):
    """Regularization rows appended below A.

    Two priors, both defensible from the stock calibration:
      * `lam_smooth` -- second differences along rpm and along airmass are
        small. Base timing maps are smooth surfaces; this is what lets a cell
        with thin coverage borrow from its neighbours instead of blowing up.
      * `lam_agree`  -- the 9 cam-indexed maps of a group resemble each other.
        In the stock 5G0906259L bin all 9 are byte-identical, so "they differ
        only where the data says so" is the correct prior, and the amount the
        fit pushes them apart is itself a finding.
    """
    blocks, per_group = [], n_maps * NX * NY
    total = n_groups * per_group

    def cell(g, m, r, c):
        return g * per_group + m * NX * NY + r * NX + c

    rows, cols, vals, nr = [], [], [], 0
    for g in range(n_groups):
        for m in range(n_maps):
            for r in range(NY):
                for c in range(1, NX - 1):
                    for cc, vv in ((cell(g, m, r, c - 1), 1.0), (cell(g, m, r, c), -2.0),
                                   (cell(g, m, r, c + 1), 1.0)):
                        rows.append(nr); cols.append(cc); vals.append(lam_smooth * vv)
                    nr += 1
            for c in range(NX):
                for r in range(1, NY - 1):
                    for cc, vv in ((cell(g, m, r - 1, c), 1.0), (cell(g, m, r, c), -2.0),
                                   (cell(g, m, r + 1, c), 1.0)):
                        rows.append(nr); cols.append(cc); vals.append(lam_smooth * vv)
                    nr += 1
    if n_maps > 1 and lam_agree > 0:
        for g in range(n_groups):
            for m in range(1, n_maps):
                for r in range(NY):
                    for c in range(NX):
                        rows.append(nr); cols.append(cell(g, 0, r, c)); vals.append(lam_agree)
                        rows.append(nr); cols.append(cell(g, m, r, c)); vals.append(-lam_agree)
                        nr += 1
    blocks.append(sparse.csr_matrix((vals, (rows, cols)), shape=(nr, total)))
    return sparse.vstack(blocks).tocsr()
