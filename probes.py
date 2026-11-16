#!/usr/bin/env python3
"""Deliverable 1: measure network delay between the Pi and one node. Soon will be two nodes

Sends timestamped probes; the node echoes them with its own receive and send
times. Round-trip network delay is:
    net_rtt = (Pi receive - Pi send) - (node send - node receive)
which removes the node's processing time. One-way delay is estimated as
net_rtt / 2 (true one-way delay needs synchronized clocks, which is the point).

Usage:  python3 probes.py --node-ip 10.42.0.23 [--count 2000] [--interval 0.05]
"""
import argparse
import csv
import socket
import statistics as st
import time

import config
import packets


def pct(sorted_vals, q):
    if not sorted_vals:
        return float("nan")
    i = min(len(sorted_vals) - 1, int(round(q * (len(sorted_vals) - 1))))
    return sorted_vals[i]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--node-ip", required=True)
    ap.add_argument("--port", type=int, default=config.PROBE_PORT)
    ap.add_argument("--count", type=int, default=2000)
    ap.add_argument("--interval", type=float, default=0.05)
    ap.add_argument("--timeout", type=float, default=0.5)
    ap.add_argument("--out", default=None)
    ap.add_argument("--plot", action="store_true")
    args = ap.parse_args()

    out = args.out or f"probes_{args.node_ip.replace('.', '-')}_{time.strftime('%H%M%S')}.csv"
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(args.timeout)
    rtts, lost = [], 0

    with open(out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["seq", "t_pi_tx_ns", "t_pi_rx_ns", "t_esp_rx_us", "t_esp_tx_us",
                    "rtt_us", "node_proc_us", "net_rtt_us"])
        for seq in range(args.count):
            t_tx = time.monotonic_ns()
            sock.sendto(packets.build_probe(seq, t_tx), (args.node_ip, args.port))
            got = None
            deadline = time.monotonic() + args.timeout
            while time.monotonic() < deadline:
                try:
                    buf, _ = sock.recvfrom(1024)
                except socket.timeout:
                    break
                t_rx = time.monotonic_ns()
                p = packets.parse(buf)
                if p and p["type"] == packets.PKT_ECHO and p["seq"] == seq:
                    got = (p, t_rx)
                    break                           # ignore late echoes of older probes
            if got is None:
                lost += 1
                w.writerow([seq, t_tx, "", "", "", "", "", ""])
            else:
                p, t_rx = got
                rtt = (t_rx - t_tx) / 1000
                proc = p["t_esp_tx_us"] - p["t_esp_rx_us"]
                net = rtt - proc
                rtts.append(net)
                w.writerow([seq, t_tx, t_rx, p["t_esp_rx_us"], p["t_esp_tx_us"],
                            f"{rtt:.1f}", proc, f"{net:.1f}"])
            time.sleep(max(0.0, args.interval - (time.monotonic_ns() - t_tx) / 1e9))

    s = sorted(rtts)
    print(f"\nProbes sent {args.count}, lost {lost} ({100 * lost / args.count:.1f}%)")
    if s:
        print(f"Network RTT (us): min {s[0]:.0f}  median {st.median(s):.0f}  "
              f"mean {st.mean(s):.0f}  p95 {pct(s, .95):.0f}  p99 {pct(s, .99):.0f}  "
              f"max {s[-1]:.0f}  std {st.pstdev(s):.0f}")
        print(f"Estimated one-way delay (median RTT/2): {st.median(s) / 2:.0f} us")
    print(f"Saved {out}")

    if args.plot and s:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(7, 4))
        ax.hist([v / 1000 for v in s], bins=80)
        ax.set_xlabel("Network round-trip delay (ms)")
        ax.set_ylabel("Probes")
        ax.set_title(f"Pi to node {args.node_ip}")
        fig.tight_layout()
        fig.savefig(out.replace(".csv", ".png"), dpi=150)
        print(f"Plot {out.replace('.csv', '.png')}")


if __name__ == "__main__":
    main()
