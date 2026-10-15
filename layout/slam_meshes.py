"""Surface meshes from SLAM points, numpy/scipy only (used by slam_to_layout.py --meshes).

voxel_mesh(): occupancy grid -> close/dilate/fill -> boundary quads -> Taubin smoothing.
Writers: OBJ (+MTL) for Gazebo, binary glTF (.glb) for Unreal (Interchange).

Frames: meshes are built in the levelled SLAM frame, right-handed, Z up, metres. That is the
Gazebo ENU frame of the layout (track frame = same X, Y mirrored; see ctrack_layout.json).
glTF is right-handed Y up, so the .glb gets (x, z, -y); Unreal's importer turns that into its
own left-handed Z-up frame, which is the track frame.
"""
import json
import struct

import numpy as np
from scipy import ndimage, sparse


def voxel_mesh(pts, res, close=1, dilate=0, fill=True, smooth=10):
    """Watertight-ish surface around points. Returns (V [n,3] float, F [m,3] int)."""
    if len(pts) == 0:
        return np.zeros((0, 3)), np.zeros((0, 3), int)
    pad = 2 + close + dilate
    lo = pts.min(0) - pad * res
    ijk = np.floor((pts - lo) / res).astype(int)
    occ = np.zeros(ijk.max(0) + pad + 1, bool)
    occ[ijk[:, 0], ijk[:, 1], ijk[:, 2]] = True
    if close:
        occ = ndimage.binary_closing(occ, iterations=close)
    if dilate:
        occ = ndimage.binary_dilation(occ, iterations=dilate)
    if fill:
        occ = ndimage.binary_fill_holes(occ)
    dims = np.array(occ.shape) + 1                      # corner grid
    cid = lambda c: (c[:, 0] * dims[1] + c[:, 1]) * dims[2] + c[:, 2]
    quads = []
    for a in range(3):
        b, c = (a + 1) % 3, (a + 2) % 3
        lo_s = [slice(None)] * 3; hi_s = [slice(None)] * 3
        lo_s[a] = slice(0, -1); hi_s[a] = slice(1, None)
        A, B = occ[tuple(lo_s)], occ[tuple(hi_s)]
        for mask, outward in ((A & ~B, +1), (~A & B, -1)):
            idx = np.argwhere(mask)
            if not len(idx):
                continue
            base = idx.copy(); base[:, a] += 1          # face plane between cell i and i+1
            eb = np.zeros(3, int); eb[b] = 1
            ec = np.zeros(3, int); ec[c] = 1
            q = np.stack([base, base + eb, base + eb + ec, base + ec], 1)   # normal = +e_a
            if outward < 0:
                q = q[:, ::-1]
            quads.append(q)
    q = np.concatenate(quads)
    ids = cid(q.reshape(-1, 3))
    uniq, inv = np.unique(ids, return_inverse=True)
    corners = np.stack(np.unravel_index(uniq, dims), 1).astype(float)
    V = lo + corners * res
    Q = inv.reshape(-1, 4)
    F = np.concatenate([Q[:, [0, 1, 2]], Q[:, [0, 2, 3]]])
    if smooth:
        V = taubin(V, F, smooth)
    return V, F


def taubin(V, F, iters, lam=0.5, mu=-0.53):
    n = len(V)
    e = np.concatenate([F[:, [0, 1]], F[:, [1, 2]], F[:, [2, 0]]])
    e = np.concatenate([e, e[:, ::-1]])
    W = sparse.coo_matrix((np.ones(len(e)), (e[:, 0], e[:, 1])), shape=(n, n)).tocsr()
    W.data[:] = 1.0
    deg = np.asarray(W.sum(1)).ravel()
    deg[deg == 0] = 1
    for _ in range(iters):
        for f in (lam, mu):
            V = V + f * (W @ V / deg[:, None] - V)
    return V


def cylinder_mesh(cx, cy, d, z0, h, seg=12):
    t = np.linspace(0, 2 * np.pi, seg, endpoint=False)
    ring = np.c_[cx + d / 2 * np.cos(t), cy + d / 2 * np.sin(t)]
    V = np.vstack([np.c_[ring, np.full(seg, z0)], np.c_[ring, np.full(seg, z0 + h)],
                   [[cx, cy, z0], [cx, cy, z0 + h]]])
    i = np.arange(seg); j = (i + 1) % seg
    F = np.concatenate([np.c_[i, j, j + seg], np.c_[i, j + seg, i + seg],          # side
                        np.c_[np.full(seg, 2 * seg + 1), i + seg, j + seg],         # top
                        np.c_[np.full(seg, 2 * seg), j, i]])                         # bottom
    return V, F


def heightfield_mesh(xy, z, cell, mask_dilate=2, clamp=0.5, lift=0.03):
    """Ground relief: median height per cell, holes filled from the nearest cell, data area only."""
    lo = xy.min(0)
    ij = np.floor((xy - lo) / cell).astype(int)
    shape = ij.max(0) + 1
    lin = ij[:, 0] * shape[1] + ij[:, 1]
    o = np.argsort(lin); lin_s = lin[o]
    u, st = np.unique(lin_s, return_index=True)
    med = np.array([np.median(z[o[a:b]]) for a, b in zip(st, list(st[1:]) + [len(o)])])
    H = np.full(shape, np.nan); H.flat[u] = np.clip(med, -clamp, clamp)
    have = ~np.isnan(H)
    area = ndimage.binary_fill_holes(ndimage.binary_dilation(have, iterations=mask_dilate))
    _, (ni, nj) = ndimage.distance_transform_edt(~have, return_indices=True)
    H = H[ni, nj]
    H = ndimage.gaussian_filter(H, 1.0)
    H = np.maximum(H, 0.0) + lift      # keep it on top of the flat collider / ground plane
    vid = -np.ones((shape[0] + 1, shape[1] + 1), int)   # vertices at cell corners
    cells = np.argwhere(area)
    corners = np.unique(np.concatenate([cells + d for d in ((0, 0), (1, 0), (1, 1), (0, 1))]), axis=0)
    vid[corners[:, 0], corners[:, 1]] = np.arange(len(corners))
    Hc = np.pad(H, ((0, 1), (0, 1)), mode="edge")
    V = np.c_[lo + corners * cell, Hc[corners[:, 0], corners[:, 1]]]
    a, b = vid[cells[:, 0], cells[:, 1]], vid[cells[:, 0] + 1, cells[:, 1]]
    c, d = vid[cells[:, 0] + 1, cells[:, 1] + 1], vid[cells[:, 0], cells[:, 1] + 1]
    F = np.concatenate([np.c_[a, b, c], np.c_[a, c, d]])
    return V, F


def merge(parts):
    Vs, Fs, n = [], [], 0
    for V, F in parts:
        Vs.append(V); Fs.append(F + n); n += len(V)
    return (np.concatenate(Vs), np.concatenate(Fs)) if Vs else (np.zeros((0, 3)), np.zeros((0, 3), int))


def normals(V, F):
    fn = np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]])
    N = np.zeros_like(V)
    for k in range(3):
        np.add.at(N, F[:, k], fn)
    ln = np.linalg.norm(N, axis=1, keepdims=True); ln[ln == 0] = 1
    return N / ln


def write_obj(path, V, F, rgb, name):
    mtl = path[:-4] + ".mtl"
    with open(mtl, "w") as f:
        f.write(f"newmtl {name}\nKd {rgb[0]:.3f} {rgb[1]:.3f} {rgb[2]:.3f}\nKa 0 0 0\nKs 0.05 0.05 0.05\nNs 10\n")
    N = normals(V, F)
    with open(path, "w") as f:
        f.write(f"mtllib {mtl.split('/')[-1]}\no {name}\n")
        f.write("".join(f"v {x:.3f} {y:.3f} {z:.3f}\n" for x, y, z in V))
        f.write("".join(f"vn {x:.3f} {y:.3f} {z:.3f}\n" for x, y, z in N))
        f.write(f"usemtl {name}\n")
        f.write("".join(f"f {a}//{a} {b}//{b} {c}//{c}\n" for a, b, c in F + 1))


def write_glb(path, V, F, rgb, name):
    """Single-mesh binary glTF 2.0, metres, Y up: vertex (x, y, z)_ENU -> (x, z, -y)."""
    P = np.c_[V[:, 0], V[:, 2], -V[:, 1]].astype("<f4")
    N = normals(V, F); N = np.c_[N[:, 0], N[:, 2], -N[:, 1]].astype("<f4")
    I = F.astype("<u4").ravel()
    blobs = [P.tobytes(), N.tobytes(), I.tobytes()]
    offs = np.cumsum([0] + [len(b) for b in blobs])
    bin_ = b"".join(blobs)
    gl = {
        "asset": {"version": "2.0", "generator": "slam_meshes.py"},
        "scene": 0, "scenes": [{"nodes": [0]}], "nodes": [{"mesh": 0, "name": name}],
        "materials": [{"name": name, "pbrMetallicRoughness": {
            "baseColorFactor": [*rgb, 1.0], "metallicFactor": 0.0, "roughnessFactor": 0.9}}],
        "meshes": [{"name": name, "primitives": [{"attributes": {"POSITION": 0, "NORMAL": 1},
                                                  "indices": 2, "material": 0}]}],
        "buffers": [{"byteLength": len(bin_)}],
        "bufferViews": [{"buffer": 0, "byteOffset": int(offs[0]), "byteLength": len(blobs[0]), "target": 34962},
                        {"buffer": 0, "byteOffset": int(offs[1]), "byteLength": len(blobs[1]), "target": 34962},
                        {"buffer": 0, "byteOffset": int(offs[2]), "byteLength": len(blobs[2]), "target": 34963}],
        "accessors": [{"bufferView": 0, "componentType": 5126, "count": len(P), "type": "VEC3",
                       "min": P.min(0).tolist(), "max": P.max(0).tolist()},
                      {"bufferView": 1, "componentType": 5126, "count": len(N), "type": "VEC3"},
                      {"bufferView": 2, "componentType": 5125, "count": len(I), "type": "SCALAR"}],
    }
    js = json.dumps(gl).encode()
    js += b" " * (-len(js) % 4)
    bin_ += b"\0" * (-len(bin_) % 4)
    with open(path, "wb") as f:
        f.write(struct.pack("<III", 0x46546C67, 2, 12 + 8 + len(js) + 8 + len(bin_)))
        f.write(struct.pack("<II", len(js), 0x4E4F534A) + js)
        f.write(struct.pack("<II", len(bin_), 0x004E4942) + bin_)
