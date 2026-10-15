#!/usr/bin/env python3
"""Check the lidar pattern mode (settings_gazebo_mid360.json) against the pattern file, vehicle at rest.

Run with Unreal up on the C-Track map and no Gazebo (the vehicle pose is set through the API):
  ./tools/check_mid360_pattern.py [--pattern CTrackSim/Content/Lidar/mid360_pattern_2s.bin] [--seconds 6]
Checks: every output point lies on its pattern shot (order, direction and frame conversion), the
pattern continues across frames, shots and sizes per frame, density per elevation band, 1x1 deg
coverage, hits on a 0.1 m pole at 7 m with the sensor 1.5 m up (Pole_C1 scaled down, restored
afterwards), left/right from two poles beside the vehicle, and the closest return (self hits).
"""
import argparse
import math
import os
import time

import cosysairsim as airsim
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
LIDAR = "RPLIDAR_A3"


def load_pattern(path):
    raw = open(path, "rb").read()
    assert raw[:8] == b"MID360PT", "not a pattern file"
    _, n, pps, _ = np.frombuffer(raw[8:24], dtype="<u4,<u4,<f4,<u4")[0]
    ang = np.radians(np.frombuffer(raw[24:], dtype="<f4").reshape(-1, 2).astype(np.float64))
    az, el = ang[:, 0], ang[:, 1]
    # Livox (x fwd, y left, z up) -> AirSim sensor frame (x fwd, y right, z down)
    dirs = np.stack([np.cos(el) * np.cos(az), -np.cos(el) * np.sin(az), -np.sin(el)], axis=1)
    return dirs, np.degrees(az), np.degrees(el), float(pps)


def match_start(points, dirs):
    """Pattern index of the frame's first shot, from its first hit."""
    hits = np.flatnonzero(~np.isnan(points[:, 0]))
    j = hits[0]
    d = points[j] / np.linalg.norm(points[j])
    k = int(np.argmax(dirs @ d))
    return (k - j) % len(dirs)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pattern", default=os.path.join(HERE, "..", "CTrackSim", "Content", "Lidar", "mid360_pattern_2s.bin"))
    ap.add_argument("--seconds", type=float, default=6.0)
    args = ap.parse_args()
    dirs, az, el, pps = load_pattern(args.pattern)
    N = len(dirs)

    c = airsim.MultirotorClient()
    c.confirmConnection()
    q = airsim.Quaternionr()
    # sensor 0.3 m above the vehicle origin -> 1.5 m above ground; Pole_C1 (66, 26) 7 m ahead
    c.simSetVehiclePose(airsim.Pose(airsim.Vector3r(59.0, 26.0, -1.2), q), True)
    scale0 = c.simGetObjectScale("Pole_C1")
    c.simSetObjectScale("Pole_C1", airsim.Vector3r(0.1, 0.1, scale0.z_val))
    time.sleep(1.5)

    frames, last = [], None
    t_end = time.time() + args.seconds
    while time.time() < t_end:
        d = c.getLidarData(LIDAR)
        if d.time_stamp != last and len(d.point_cloud) >= 3:
            last = d.time_stamp
            frames.append((d.time_stamp, np.array(d.point_cloud, dtype=np.float64).reshape(-1, 3), list(d.groundtruth)))
        time.sleep(0.01)
    c.simSetObjectScale("Pole_C1", scale0)
    frames = frames[1:]  # the first frame may predate the pose change

    n = np.array([len(p) for _, p, _ in frames])
    dt = np.diff([t for t, _, _ in frames]) / 1e9
    print(f"frames {len(frames)}, shots per frame mean {n.mean():.0f} (min {n.min()}, max {n.max()}), "
          f"frame period {dt.mean() * 1e3:.1f} ms (sd {dt.std() * 1e3:.1f}), shots/s {n[1:].sum() / dt.sum():.0f}")
    sizes, counts = np.unique(n, return_counts=True)
    print("frame sizes: " + ", ".join(f"{s_}x{c_}" for s_, c_ in sorted(zip(sizes, counts), key=lambda t: -t[1])[:4]))

    # every hit on its pattern shot, in order; pattern continuous across frames
    max_err, breaks, starts = 0.0, 0, []
    for i, (_, p, _) in enumerate(frames):
        s = match_start(p, dirs)
        starts.append(s)
        idx = (s + np.arange(len(p))) % N
        h = ~np.isnan(p[:, 0])
        u = p[h] / np.linalg.norm(p[h], axis=1, keepdims=True)
        err = np.degrees(np.arccos(np.clip(np.sum(u * dirs[idx[h]], axis=1), -1, 1)))
        max_err = max(max_err, err.max())
        if i and s != (starts[i - 1] + len(frames[i - 1][1])) % N:
            breaks += 1
    nan_frac = np.mean([np.isnan(p[:, 0]).mean() for _, p, _ in frames])
    print(f"direction error vs pattern: max {max_err:.4f} deg; pattern breaks between frames: {breaks}; "
          f"NaN shots {nan_frac * 100:.1f} %")

    # density per elevation band and coverage, from the shots actually fired
    fired = [(s + np.arange(len(p))) % N for s, (_, p, _) in zip(starts, frames)]
    one = fired[0]
    bands = [(-7, 0), (0, 10), (10, 30), (30, 40), (40, 53)]
    # per 0.1 s; area as az x el degrees, and as solid angle (square degrees)
    per = 0.1 * pps / len(one)
    dens = [np.sum((el[one] >= a) & (el[one] < b)) * per / (360.0 * (b - a)) for a, b in bands]
    sa = [np.sum((el[one] >= a) & (el[one] < b)) * per /
          (360.0 * np.degrees(np.sin(np.radians(b)) - np.sin(np.radians(a)))) for a, b in bands]
    print("shots per 0.1 s per deg^2, az x el area: " + ", ".join(f"{a}..{b} {v:.2f}" for (a, b), v in zip(bands, dens)))
    print("shots per 0.1 s per deg^2, solid angle:  " + ", ".join(f"{a}..{b} {v:.2f}" for (a, b), v in zip(bands, sa)))
    for k in (1, 2, 5):
        if len(fired) >= k:
            sel = np.concatenate(fired[:k])
            cells = set(zip(np.floor(az[sel]).astype(int), np.floor(el[sel]).astype(int)))
            total = 360 * 59  # el -7..52
            inside = sum(1 for a, e in cells if -7 <= e < 52)
            print(f"1x1 deg cells covered in {k} frame(s): {inside / total * 100:.0f} %")

    # 0.1 m pole at 7 m
    pole = np.array([sum(1 for g in gt if g == "Pole_C1") for _, _, gt in frames])
    print(f"0.1 m pole at 7 m: hits per frame mean {pole.mean():.1f} (min {pole.min()}, max {pole.max()}), "
          f"frames with 0 hits {np.mean(pole == 0) * 100:.0f} %")

    # closest return: the vehicle's own body would show up inside the prop tips (0.77 m)
    r = np.concatenate([np.linalg.norm(p[~np.isnan(p[:, 0])], axis=1) for _, p, _ in frames])
    print(f"closest return {r.min():.2f} m; returns within 0.77 m: {np.sum(r < 0.77)} of {len(r)}")

    # left/right: Pole_C3 (56, 29) is 3 m behind, 3 m right (+y); Pole_C2 (56, 23) 3 m left
    for name in ("Pole_C3", "Pole_C2"):
        pts = np.concatenate([p[np.array(gt) == name] for _, p, gt in frames])
        if len(pts):
            m = pts.mean(axis=0)
            print(f"{name}: mean point in sensor frame x {m[0]:+.2f}, y {m[1]:+.2f}, z {m[2]:+.2f} ({len(pts)} points)")


if __name__ == "__main__":
    main()
