#!/usr/bin/env python3
"""Integration check: fly the C-Track route with PX4 offboard and watch Gazebo/AirSim agree.

Needs pymavlink and cosysairsim (3.5). PX4 offboard MAVLink on udp 14540 (localhost).
Track frame (layout) -> PX4 local NED: north = -Y, east = X.
Reports: PX4 vs AirSim position error, cross-track drift in wind zone B, RC cart mirroring
and lidar hits on it.
"""
import collections
import json
import math
import os
import sys
import time

import cosysairsim as airsim
from pymavlink import mavutil

HERE = os.path.dirname(os.path.abspath(__file__))
LAYOUT = json.load(open(os.path.join(HERE, "..", "layout", "ctrack_layout.json")))
ALT = float(os.environ.get("ALT", 4.0))
SPEED = float(os.environ.get("SPEED", 2.5))

# A lane around the tents, B lane through the wind, C lane between poles/wall/balloon (track XY, m)
ROUTE = [(0, 0), (8, -6), (22, -6), (28, 0), (42, 6), (48, 0), (60, 0), (79, 0), (79, 26), (62, 26),
         (52, 24.7), (42, 26), (26, 23), (19.5, 24.5), (10, 27), (0, 26)]


def ned(x, y):
    return -y, x


def main():
    mav = mavutil.mavlink_connection("udpin:0.0.0.0:14540")
    mav.wait_heartbeat(timeout=30)
    print(f"PX4 heartbeat sys {mav.target_system}")
    sim = airsim.MultirotorClient()
    sim.confirmConnection()

    state = {"pos": None}

    def poll():
        while True:
            m = mav.recv_match(type="LOCAL_POSITION_NED", blocking=False)
            if m is None:
                break
            state["pos"] = (m.x, m.y, m.z)

    def send_sp(n, e, d, yaw=float("nan")):
        mav.mav.set_position_target_local_ned_send(
            0, mav.target_system, mav.target_component, mavutil.mavlink.MAV_FRAME_LOCAL_NED,
            0b100111111000, n, e, d, 0, 0, 0, 0, 0, 0, yaw, 0)

    def cmd(c, *p):
        p = list(p) + [0] * (7 - len(p))
        mav.mav.command_long_send(mav.target_system, mav.target_component, c, 0, *p)

    # stream setpoints before switching to offboard, then arm
    for _ in range(30):
        send_sp(0, 0, -ALT)
        time.sleep(0.05)
    cmd(mavutil.mavlink.MAV_CMD_DO_SET_MODE, 1, 6)  # custom mode: OFFBOARD
    cmd(mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM, 1)

    wind = LAYOUT["wind_zones"][0]
    cart = LAYOUT["moving_obstacles"][0]["name"]
    log = collections.defaultdict(list)
    cart_seen = collections.Counter()
    cart_start = sim.simGetObjectPose(cart).position

    def sample(seg_from, seg_to):
        poll()
        if state["pos"] is None:
            return
        n, e, d = state["pos"]
        x, y = e, -n
        a = sim.simGetVehiclePose().position  # AirSim NED (x=X, y=Y, z down) incl. model origin height
        log["pos_err"].append(math.hypot(a.x_val - x, a.y_val - y))
        # cross-track error to the current segment
        (x0, y0), (x1, y1) = seg_from, seg_to
        L = math.hypot(x1 - x0, y1 - y0) or 1
        xt = abs((x1 - x0) * (y0 - y) - (x0 - x) * (y1 - y0)) / L
        inside = wind["x_range"][0] <= x <= wind["x_range"][1] and wind["y_range"][0] <= y <= wind["y_range"][1]
        log["xt_wind" if inside else "xt_calm"].append(xt)
        c = sim.simGetObjectPose(cart).position
        log["cart_y"].append(c.y_val)
        lab = sim.getLidarData("RPLIDAR_A3").groundtruth
        for k, v in collections.Counter(lab).items():
            if k.startswith(cart):
                cart_seen[k] += v

    # takeoff
    t0 = time.time()
    while time.time() - t0 < 15:
        send_sp(0, 0, -ALT)
        poll()
        if state["pos"] and abs(state["pos"][2] + ALT) < 0.3:
            break
        time.sleep(0.05)
    print(f"takeoff done: {state['pos']}")

    # follow the route with a moving carrot at SPEED
    for (x0, y0), (x1, y1) in zip(ROUTE, ROUTE[1:]):
        L = math.hypot(x1 - x0, y1 - y0)
        steps = max(1, int(L / SPEED / 0.05))
        last_sample = 0
        for i in range(steps + 1):
            f = i / steps
            send_sp(*ned(x0 + f * (x1 - x0), y0 + f * (y1 - y0)), -ALT)
            if time.time() - last_sample > 0.25:
                sample((x0, y0), (x1, y1))
                last_sample = time.time()
            time.sleep(0.05)
        print(f"  reached ({x1}, {y1})  px4 pos {tuple(round(v, 1) for v in state['pos'])}")

    for _ in range(40):
        send_sp(*ned(*ROUTE[-1]), -ALT)
        time.sleep(0.05)
    cmd(mavutil.mavlink.MAV_CMD_NAV_LAND)

    pe = log["pos_err"]
    print(f"\nPX4 vs AirSim horizontal error: mean {sum(pe)/len(pe):.2f} m, max {max(pe):.2f} m ({len(pe)} samples)")
    for k in ("xt_calm", "xt_wind"):
        if log[k]:
            print(f"cross-track {k[3:]:5s}: mean {sum(log[k])/len(log[k]):.2f} m, max {max(log[k]):.2f} m")
    cy = log["cart_y"]
    print(f"RC cart (AirSim) start Y {cart_start.y_val:.1f}, seen Y range [{min(cy):.1f}, {max(cy):.1f}]")
    print(f"lidar points on cart: {dict(cart_seen)}")


if __name__ == "__main__":
    sys.exit(main())
