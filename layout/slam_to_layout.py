#!/usr/bin/env python3
"""Turn a SLAM point cloud (map_points.ply from sbox_export.py) into a layout JSON of simple shapes.

Ground plane is fitted and levelled to Z=0, the points above it are split into clusters on a 2D
grid, and each cluster becomes a primitive the existing pipeline understands:
  - tall or long clusters (building facades) -> thin boxes along RANSAC line segments
  - other long low clusters (hedges, rows)    -> oriented box
  - trees -> trunk cylinder (ground .. canopy bottom) + canopy cylinder (canopy bottom .. top),
    so the space under the canopy next to the trunk stays free; bushes stay one cylinder
  - other compact clusters (poles, objects)   -> cylinder on the ground
Shapes may carry "z" (bottom height, default 0) for parts that float, like canopies.

--meshes DIR also writes surface meshes made from the points (slam_meshes.py): tree canopies,
trunks, small objects and the ground relief, as .obj (Gazebo) and .glb (Unreal), listed under
"meshes" in the layout. Buildings stay the wall boxes (flat facades look better than a voxel
surface of a facade scan). --collision mesh (default with --meshes) makes the meshes the
colliders too (the lidar then sees the real shapes) and keeps the primitives they replace only
for reference ("obstacles_primitive"); --collision primitive keeps those primitives as invisible
colliders under the meshes ("visual": false on each).
The ground relief is a collider as well: vehicles stand and land on it (Gazebo: as a <heightmap>
from <meshes>/ground_height.png), and its heights go to <meshes>/ground_height.json for spawning
on it. The waypoints get flat pads (--pad-radius, plus a
blend ring): START at the ground plane level, the others at their median relief height.
--only-ground rebuilds just the ground mesh and its layout entry in an existing out.json.

  slam_to_layout.py map_points.ply out.json [--start X Y] [--goal X Y] [--preview out.png]
                    [--meshes DIR] [--collision mesh|primitive] [--pad-radius R] [--only-ground]
Frames: --start/--goal and the preview are in the SLAM frame (as map.png: origin = where SLAM was
started, right-handed, Z levelled). The layout is in the track frame of ctrack_layout.json, which
is left-handed like Unreal: X = SLAM x, Y = -SLAM y (so Gazebo ENU = the SLAM frame).
"""
import os
import argparse
import json

import numpy as np
from scipy import ndimage

import slam_meshes as sm

CELL = 0.25          # 2D grid for clustering [m]
GROUND_CLEAR = 0.4   # points this far above the ground plane are obstacles [m]
MIN_POINTS = 40      # smaller clusters are noise
WALL_HEIGHT = 10.0   # clusters taller than this are buildings
LONG = 10.0          # clusters longer than this (and not buildings) become oriented boxes
WALL_THICK = 1.0     # facade box thickness [m]
TREE_SEP = 3.0       # canopy tops closer than this are one tree [m]
TREE_MIN = 2.5       # clusters lower than this are objects, not trees [m]
CANOPY_MIN = 1.5     # canopy bottom lower than this: one shape down to the ground (bush) [m]
UNDER_MIN = 1.5      # undergrowth lower than this is grass, not an obstacle [m]
TRUNK_D = (0.25, 0.8)  # trunk diameter clamp [m]; ground lidar sees one side only
GROUND_CELL = 0.5    # ground relief grid [m]
PAD_BLEND = 1.5      # waypoint pads blend back into the relief over this distance [m]


def load_ply(path):
    b = open(path, "rb").read()
    i = b.index(b"end_header\n") + len(b"end_header\n")
    return np.frombuffer(b[i:], dtype="<f4").reshape(-1, 4)[:, :3].astype(float)


def fit_ground(P, grid=2.0):
    k = np.floor(P[:, :2] / grid).astype(np.int64)
    _, inv = np.unique(k, axis=0, return_inverse=True)
    inv = inv.ravel()
    order = np.argsort(inv)
    bounds = np.flatnonzero(np.diff(inv[order])) + 1
    cells = [c for c in np.split(order, bounds) if len(c) >= 15]
    g = np.array([[P[c, 0].mean(), P[c, 1].mean(), np.percentile(P[c, 2], 5)] for c in cells])
    m = np.ones(len(g), bool)
    for _ in range(5):
        A = np.c_[g[m, :2], np.ones(m.sum())]
        coef, *_ = np.linalg.lstsq(A, g[m, 2], rcond=None)
        r = g[:, 2] - (g[:, :2] @ coef[:2] + coef[2])
        m = np.abs(r) < max(0.15, 2.5 * r[m].std())
    return coef  # z = a x + b y + c


def level(P, coef):
    """Rotate so the fitted plane normal is +Z, then shift the plane to Z=0 at the origin."""
    a, b, c = coef
    n = np.array([-a, -b, 1.0]); n /= np.linalg.norm(n)
    z = np.array([0, 0, 1.0]); v = np.cross(n, z); s = np.linalg.norm(v); cth = n @ z
    if s < 1e-9:
        R = np.eye(3)
    else:
        vx = np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]])
        R = np.eye(3) + vx + vx @ vx * ((1 - cth) / s**2)
    Q = P @ R.T
    Q[:, 2] -= (np.array([0, 0, c]) @ R.T)[2]
    return Q


def ransac_lines(xy, thresh=0.5, min_pts=150, iters=400, rng=np.random.default_rng(0)):
    """Greedy RANSAC line segments: returns (p0, p1, inlier_idx) for each segment."""
    left = np.arange(len(xy)); out = []
    while len(left) >= min_pts:
        best = None
        for _ in range(iters):
            i, j = rng.choice(len(left), 2, replace=False)
            d = xy[left[j]] - xy[left[i]]; L = np.linalg.norm(d)
            if L < 1.0:
                continue
            nrm = np.array([-d[1], d[0]]) / L
            inl = np.abs((xy[left] - xy[left[i]]) @ nrm) < thresh
            if best is None or inl.sum() > best[1].sum():
                best = (d / L, inl, xy[left[i]])
        if best is None or best[1].sum() < min_pts:
            break
        u, inl, p = best
        idx = left[inl]
        t = (xy[idx] - p) @ u
        # keep the longest run without gaps > 2 m so one line does not bridge two buildings
        o = np.argsort(t); ts = t[o]; cut = np.flatnonzero(np.diff(ts) > 2.0)
        runs = np.split(o, cut + 1)
        run = max(runs, key=len)
        if len(run) < min_pts:
            left = left[~inl]
            continue
        tr = t[run]
        out.append((p + u * tr.min(), p + u * tr.max(), idx[run]))
        left = np.setdiff1d(left, idx[run])
    return out


def split_canopies(q, cell=0.5):
    """Split merged canopies: one seed per local height maximum, points go to the nearest seed."""
    lo = q[:, :2].min(0)
    ij = np.floor((q[:, :2] - lo) / cell).astype(int)
    hmap = np.zeros(ij.max(0) + 1)
    np.maximum.at(hmap, (ij[:, 0], ij[:, 1]), q[:, 2])
    hs = ndimage.gaussian_filter(hmap, 1.0)
    size = int(round(TREE_SEP / cell)) | 1
    peaks = np.argwhere((hs == ndimage.maximum_filter(hs, size=size)) & (hmap > TREE_MIN))
    if len(peaks) < 2:
        return [q]
    seeds = lo + (peaks + 0.5) * cell
    near = np.argmin(((q[:, None, :2] - seeds[None]) ** 2).sum(-1), axis=1)
    return [q[near == i] for i in range(len(seeds)) if (near == i).sum() >= MIN_POINTS // 2]


MESH_STYLE = {   # name: (rgb, collides)
    "buildings": ((0.72, 0.70, 0.66), True),
    "canopy": ((0.20, 0.36, 0.13), True),
    "trunks": ((0.36, 0.25, 0.16), True),
    "objects": ((0.48, 0.42, 0.36), True),
    "ground": ((0.36, 0.35, 0.24), True),    # the relief is the ground (the flat plane stays under it)
}


def ground_mesh(P, pads):
    g = P[np.abs(P[:, 2]) < GROUND_CLEAR]
    return sm.heightfield_mesh(g[:, :2], g[:, 2], GROUND_CELL, pads=pads)


def waypoint_pads(wps_slam, radius):
    """Flat take-off / landing pads: START at the ground plane, the others at their relief."""
    return [(x, y, radius, PAD_BLEND, 0.0 if name == "START" else None) for name, (x, y) in wps_slam.items()]


def write_mesh(name, V, F, out_dir, layout_dir, collide):
    """Write one mesh (.obj, .glb; the ground also its heightmap); returns its layout entry."""
    rgb, coll = MESH_STYLE[name]
    stem = os.path.join(out_dir, name)
    sm.write_obj(stem + ".obj", V, F, rgb, f"Yard_{name}")
    sm.write_glb(stem + ".glb", V, F, rgb, f"Yard_{name}")
    lo, hi = V.min(0), V.max(0)
    entry = {"name": f"Yard_{name}", "file": os.path.relpath(stem, layout_dir),
             "rgb": list(rgb), "collision": bool(collide and coll), "triangles": int(len(F)),
             # track-frame bounds [m], for the Unreal import check
             "bounds": [[round(lo[0], 2), round(-hi[1], 2), round(lo[2], 2)],
                        [round(hi[0], 2), round(-lo[1], 2), round(hi[2], 2)]]}
    if name == "ground":
        sm.write_heightmap(stem + "_height.json", V, GROUND_CELL)
        entry["heightmap"] = os.path.relpath(stem + "_height.json", layout_dir)
        # Gazebo collides with the relief as a <heightmap> (ODE's box/trimesh contacts on the sloped
        # triangles flipped vehicles that landed on it); the mesh stays the visual and Unreal's collider
        hm = sm.write_heightmap_png(stem + "_height.png", V, GROUND_CELL)
        entry["gazebo_heightmap"] = dict(file=os.path.relpath(stem + "_height.png", layout_dir), **hm)
    print(f"  mesh {name}: {len(F):,} triangles")
    return entry


def build_meshes(P, mesh_pts, trunks, out_dir, layout_dir, collide, pads=()):
    """Surface meshes in the SLAM frame (= Gazebo ENU). Returns the layout "meshes" entries."""
    os.makedirs(out_dir, exist_ok=True)
    parts = {
        "canopy": [sm.voxel_mesh(q, 0.15, close=2, dilate=1, smooth=15) for q in mesh_pts["canopy"]],
        "trunks": [sm.cylinder_mesh(x, y, d, 0.0, h) for x, y, d, h in trunks],
        "objects": [sm.voxel_mesh(q, 0.15, close=1, dilate=1, smooth=8) for q in mesh_pts["objects"]],
    }
    parts["ground"] = [ground_mesh(P, pads)]
    out = []
    for name, ps in parts.items():
        V, F = sm.merge(ps)
        if len(F):
            out.append(write_mesh(name, V, F, out_dir, layout_dir, collide))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ply"); ap.add_argument("out")
    ap.add_argument("--start", type=float, nargs=2, default=[0.0, 0.0])
    ap.add_argument("--goal", type=float, nargs=2, default=None)
    ap.add_argument("--preview")
    ap.add_argument("--meshes", help="directory for the surface meshes")
    ap.add_argument("--collision", choices=("mesh", "primitive"), default="mesh")
    ap.add_argument("--pad-radius", type=float, default=2.0, help="flat pad radius at each waypoint [m]")
    ap.add_argument("--only-ground", action="store_true",
                    help="rebuild only the ground mesh (pads at the layout's waypoints) and its entry in OUT")
    a = ap.parse_args()

    if a.only_ground:
        if not a.meshes:
            ap.error("--only-ground needs --meshes")
        P = load_ply(a.ply)
        P = level(P, fit_ground(P))
        with open(a.out) as f:
            lay = json.load(f)
        wps = {k: (x, -y) for k, (x, y) in lay["waypoints"].items()}   # track -> SLAM frame
        V, F = ground_mesh(P, waypoint_pads(wps, a.pad_radius))
        entry = write_mesh("ground", V, F, a.meshes, os.path.dirname(os.path.abspath(a.out)),
                           collide=a.collision == "mesh")
        lay["meshes"] = [entry if m["name"] == entry["name"] else m for m in lay["meshes"]]
        with open(a.out, "w") as f:
            json.dump(lay, f, indent=1)
        return
    mesh_pts = {"buildings": [], "canopy": [], "objects": []}
    trunks = []

    P = load_ply(a.ply)
    coef = fit_ground(P)
    P = level(P, coef)
    obs = P[(P[:, 2] > GROUND_CLEAR) & (P[:, 2] < 40)]

    lo = obs[:, :2].min(0)
    ij = np.floor((obs[:, :2] - lo) / CELL).astype(int)
    occ = np.zeros(ij.max(0) + 1, np.int32)
    np.add.at(occ, (ij[:, 0], ij[:, 1]), 1)
    lab, n = ndimage.label(ndimage.binary_dilation(occ > 0, iterations=1), structure=np.ones((3, 3)))
    pl = lab[ij[:, 0], ij[:, 1]]

    shapes = []
    def add(kind, shape, pos, size, yaw, color, z=0.0, name=None):
        s = {"name": name or f"{kind}_{sum(s['name'].startswith(kind + '_') for s in shapes) + 1:02d}",
             "shape": shape, "pos": [round(pos[0], 2), round(pos[1], 2)],
             "size": [round(v, 2) for v in size], "yaw_deg": round(yaw, 1), "color": color}
        if z > 0:
            s["z"] = round(z, 2)
        shapes.append(s)

    ntree = 0
    def add_tree(q2, c2, top):
        """Vertical profile in 0.25 m slices (above the grass): spread around each slice's own centre.
        Trunk = first run of >= 2 narrow slices; canopy bottom = first 2 wide slices above it.
        Wide slices below the trunk are undergrowth, kept as a separate low cylinder."""
        nonlocal ntree
        ntree += 1
        name = f"Tree_{ntree:02d}"
        rad = np.linalg.norm(q2[:, :2] - c2, axis=1)
        R = np.percentile(rad, 95)
        thr = max(0.6, 0.35 * R)

        def spread(v):
            if len(v) < 5:
                return 0.0
            return np.percentile(np.linalg.norm(v[:, :2] - np.median(v[:, :2], 0), axis=1), 90)

        zs = np.arange(0.5, top - 1.0, 0.25)
        wide = np.array([spread(q2[(q2[:, 2] >= z) & (q2[:, 2] < z + 0.25)]) > thr for z in zs])
        narrow_run = [i for i in range(len(zs) - 1) if not wide[i] and not wide[i + 1]]
        bottom, trunk_lo = 0.0, 0.0
        if narrow_run:
            i0 = narrow_run[0]
            j = next((j for j in range(i0 + 2, len(zs) - 1) if wide[j] and wide[j + 1]), None)
            if j is not None:
                bottom, trunk_lo = zs[j], zs[i0]
        if bottom < CANOPY_MIN:
            d = max(2 * R, 0.3)
            add("Tree", "cylinder", c2, [d, d, top], 0.0, "green", name=name)
            mesh_pts["canopy"].append(q2)
            return
        if trunk_lo >= UNDER_MIN and wide[zs < trunk_lo].any():
            under = q2[q2[:, 2] < trunk_lo]
            uc = under[:, :2].mean(0)
            ud = max(2 * np.percentile(np.linalg.norm(under[:, :2] - uc, axis=1), 90), 0.5)
            add("Tree", "cylinder", uc, [ud, ud, trunk_lo], 0.0, "green", name=f"{name}_under")
            mesh_pts["canopy"].append(under)
        trunk = q2[(q2[:, 2] >= trunk_lo) & (q2[:, 2] < bottom) & (rad < 1.5)]
        tc = trunk[:, :2].mean(0) if len(trunk) >= 10 else c2
        td = 2 * np.percentile(np.linalg.norm(trunk[:, :2] - tc, axis=1), 90) if len(trunk) >= 10 else 0.3
        td = float(np.clip(td, *TRUNK_D))
        canopy = q2[q2[:, 2] >= bottom]
        cc = canopy[:, :2].mean(0)
        cd = max(2 * np.percentile(np.linalg.norm(canopy[:, :2] - cc, axis=1), 95), 0.5)
        add("Tree", "cylinder", tc, [td, td, bottom], 0.0, "brown", name=f"{name}_trunk")
        add("Tree", "cylinder", cc, [cd, cd, top - bottom], 0.0, "green", z=bottom,
            name=f"{name}_canopy")
        mesh_pts["canopy"].append(canopy)
        trunks.append((tc[0], tc[1], td, bottom + 0.3))   # into the canopy, no visible gap

    for L in range(1, n + 1):
        q = obs[pl == L]
        if len(q) < MIN_POINTS:
            continue
        top = np.percentile(q[:, 2], 98)
        xy = q[:, :2]; ctr = xy.mean(0)
        ev, evec = np.linalg.eigh(np.cov((xy - ctr).T))
        u = evec[:, 1]; t = (xy - ctr) @ u; w = (xy - ctr) @ evec[:, 0]
        length = np.percentile(t, 99) - np.percentile(t, 1)
        if top > WALL_HEIGHT:
            mesh_pts["buildings"].append(q)
            for p0, p1, idx in ransac_lines(xy):
                seg = p1 - p0; Lg = np.linalg.norm(seg)
                if Lg < 2.0:
                    continue
                h = np.percentile(q[idx, 2], 98)
                yaw = np.degrees(np.arctan2(seg[1], seg[0]))
                add("Wall", "box", (p0 + p1) / 2, [Lg, WALL_THICK, h], yaw, "gray")
        else:
            parts = split_canopies(q) if np.percentile(q[:, 2], 98) > TREE_MIN else [q]
            for q2 in parts:
                xy2 = q2[:, :2]; c2 = xy2.mean(0)
                ev2, evec2 = np.linalg.eigh(np.cov((xy2 - c2).T))
                u2 = evec2[:, 1]; t2 = (xy2 - c2) @ u2; w2 = (xy2 - c2) @ evec2[:, 0]
                top2 = np.percentile(q2[:, 2], 98)
                len2 = np.percentile(t2, 99) - np.percentile(t2, 1)
                wid2 = np.percentile(w2, 99) - np.percentile(w2, 1)
                if len2 > LONG and wid2 < len2 / 3:
                    tm = (np.percentile(t2, 99) + np.percentile(t2, 1)) / 2
                    wm = (np.percentile(w2, 99) + np.percentile(w2, 1)) / 2
                    add("Row", "box", c2 + u2 * tm + evec2[:, 0] * wm, [len2, max(wid2, 0.5), top2],
                        np.degrees(np.arctan2(u2[1], u2[0])), "green")
                    mesh_pts["objects"].append(q2)
                    continue
                d = max(2 * np.percentile(np.linalg.norm(xy2 - c2, axis=1), 95), 0.3)
                if top2 > TREE_MIN:
                    add_tree(q2, c2, top2)
                else:
                    add("Obj", "cylinder", c2, [d, d, top2], 0.0, "brown")
                    mesh_pts["objects"].append(q2)

    sx, sy = a.start
    wps = {"START": [sx, sy]}
    if a.goal:
        wps["GOAL"] = list(a.goal)

    # SLAM (right-handed) -> track frame (left-handed, Unreal axes): Y and yaw change sign
    def to_track(s):
        t = dict(s, pos=[s["pos"][0], round(-s["pos"][1], 2)], yaw_deg=round(-s["yaw_deg"], 1) + 0.0)
        return t
    track = [to_track(s) for s in shapes]
    wps_t = {k: [x, -y + 0.0] for k, (x, y) in wps.items()}
    xs = [s["pos"][0] for s in track]; ys = [s["pos"][1] for s in track]
    lay = {
        "_doc": ["Generated by slam_to_layout.py from " + a.ply,
                 "Ground plane z = %.4f x + %.4f y + %.3f in the SLAM frame, levelled to Z=0." % tuple(coef),
                 "Trees: trunk cylinder + canopy cylinder lifted by 'z' (bottom height); bushes one cylinder."],
        "field": {"x_range": [round(min(xs) - 5), round(max(xs) + 5)],
                  "y_range": [round(min(ys) - 5), round(max(ys) + 5)], "ground": "dirt"},
        "waypoints": wps_t,
        "obstacles": track,
        "moving_obstacles": [], "wind_zones": [],
    }
    if a.meshes:
        lay["meshes"] = build_meshes(P, mesh_pts, trunks, a.meshes, os.path.dirname(os.path.abspath(a.out)),
                                     collide=a.collision == "mesh", pads=waypoint_pads(wps, a.pad_radius))
        walls = [o for o in track if o["name"].startswith("Wall_")]
        rest = [o for o in track if not o["name"].startswith("Wall_")]
        if a.collision == "mesh":
            lay["obstacles"], lay["obstacles_primitive"] = walls, rest
        else:
            lay["obstacles"] = walls + [dict(o, visual=False) for o in rest]
        # Gazebo start view: above the start, looking along +y (SLAM frame = Gazebo ENU)
        lay["gui_camera"] = [10.0, -6.0, 18.0, 0.0, 0.5, 1.5708]
    with open(a.out, "w") as f:
        json.dump(lay, f, indent=1)
    kinds = {}
    for s in shapes:
        k = s["name"].split("_")[0]; kinds[k] = kinds.get(k, 0) + 1
    kinds["Tree"] = ntree; kinds["with_trunk"] = sum(s["name"].endswith("_trunk") for s in shapes)
    print(f"ground tilt {np.degrees(np.arctan(np.hypot(*coef[:2]))):.2f} deg; shapes: {kinds}")

    if a.preview:
        import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
        from matplotlib.patches import Circle, Rectangle
        from matplotlib.transforms import Affine2D
        fig, ax = plt.subplots(figsize=(10, 13))
        ax.scatter(obs[:, 0], obs[:, 1], s=0.05, c="0.6")
        for s in shapes:
            (x, y), (sx_, sy_, h) = s["pos"], s["size"]
            col = {"gray": "tab:blue", "green": "tab:green", "brown": "tab:orange"}[s["color"]]
            if s["name"].endswith("_trunk"):
                ax.add_patch(Circle((x, y), sx_ / 2, fc="saddlebrown", ec="saddlebrown"))
                continue
            if s["shape"] == "cylinder":
                ax.add_patch(Circle((x, y), sx_ / 2, fill=False, ec=col, lw=1.2,
                                    ls="--" if "z" in s else "-"))
            else:
                ax.add_patch(Rectangle((x - sx_ / 2, y - sy_ / 2), sx_, sy_, fill=False, ec=col, lw=1.2,
                                       transform=Affine2D().rotate_deg_around(x, y, s["yaw_deg"]) + ax.transData))
            ax.text(x, y, f"{s['z']:.0f}-{s['z'] + h:.0f}" if "z" in s else f"{h:.0f}", fontsize=6, ha="center", va="center")
        for k, (x, y) in wps.items():
            ax.plot(x, y, "r*", ms=12); ax.text(x + 1, y + 1, k, color="r")
        ax.set_aspect("equal"); ax.grid(alpha=0.3)
        ax.set_title("SLAM frame (as map.png); numbers = top height m"); ax.set_xlabel("x [m]"); ax.set_ylabel("y [m]")
        plt.tight_layout(); plt.savefig(a.preview, dpi=90)


if __name__ == "__main__":
    main()
