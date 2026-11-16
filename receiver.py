#!/usr/bin/env python3
"""Receive data and PPS packets from every node and log them to CSV.

Record first, analyze later: this script does no processing, it just writes
  data/<session>/node<N>_<channel>.csv   t_esp_us,value,seq,t_pi_rx_ns
  data/<session>/node<N>_pps.csv         t_esp_us,seq,t_pi_rx_ns

t_pi_rx_ns is the Pi's arrival time (CLOCK_MONOTONIC). Keeping it lets you show
later how much worse arrival-time stamping is than stamping at the sensor.

Usage:  python3 receiver.py [--out data] [--port 5005]
Stop with Ctrl+C.
"""
import argparse
import csv
import os
import socket
import time
from collections import defaultdict

import config
import packets


class Logger:
    def __init__(self, out_dir):
        self.out_dir = out_dir
        self.files = {}
        self.writers = {}

    def writer(self, name, header):
        if name not in self.writers:
            f = open(os.path.join(self.out_dir, name), "w", newline="")
            w = csv.writer(f)
            w.writerow(header)
            self.files[name], self.writers[name] = f, w
        return self.writers[name]

    def flush(self):
        for f in self.files.values():
            f.flush()

    def close(self):
        for f in self.files.values():
            f.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data")
    ap.add_argument("--port", type=int, default=config.DATA_PORT)
    args = ap.parse_args()

    session = os.path.join(args.out, time.strftime("%Y%m%d_%H%M%S"))
    os.makedirs(session, exist_ok=True)
    log = Logger(session)

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4 * 1024 * 1024)
    sock.bind(("0.0.0.0", args.port))
    sock.settimeout(0.5)
    print(f"Listening on UDP {args.port}, logging to {session}")

    last_seq = {}                         # (node, type, channel) -> seq
    lost = defaultdict(int)
    count = defaultdict(int)              # samples or edges since last status
    dropped = {}
    t_status = time.monotonic()

    try:
        while True:
            try:
                buf, addr = sock.recvfrom(4096)
            except socket.timeout:
                buf = None
            now_ns = time.monotonic_ns()

            if buf:
                p = packets.parse(buf)
                if p is None:
                    continue
                key = (p["node"], p["type"], p["channel"])
                if key in last_seq and p["seq"] > last_seq[key] + 1:
                    lost[key] += p["seq"] - last_seq[key] - 1
                last_seq[key] = p["seq"]

                if p["type"] == packets.PKT_DATA:
                    ch = packets.CHANNELS.get(p["channel"], f"ch{p['channel']}")
                    w = log.writer(f"node{p['node']}_{ch}.csv",
                                   ["t_esp_us", "value", "seq", "t_pi_rx_ns"])
                    for t_us, v in p["samples"]:
                        w.writerow([t_us, v, p["seq"], now_ns])
                    count[key] += len(p["samples"])
                    dropped[p["node"]] = p["dropped"]
                elif p["type"] == packets.PKT_PPS:
                    w = log.writer(f"node{p['node']}_pps.csv",
                                   ["t_esp_us", "seq", "t_pi_rx_ns"])
                    w.writerow([p["t_us"], p["seq"], now_ns])
                    count[key] += 1

            if time.monotonic() - t_status >= 5.0:
                dt = time.monotonic() - t_status
                for key in sorted(count):
                    node, ptype, ch = key
                    kind = "pps edges" if ptype == packets.PKT_PPS else \
                        packets.CHANNELS.get(ch, ch) + " samples"
                    print(f"  node {node}: {count[key] / dt:7.1f} {kind}/s   "
                          f"lost packets={lost[key]}   node drops={dropped.get(node, 0)}")
                count.clear()
                log.flush()
                t_status = time.monotonic()
    except KeyboardInterrupt:
        pass
    finally:
        log.close()
        print(f"Saved to {session}")


if __name__ == "__main__":
    main()
