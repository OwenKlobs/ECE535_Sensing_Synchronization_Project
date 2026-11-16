"""Packet layout shared with firmware/include/packets.h (little-endian, packed)."""
import struct

PROTO_VERSION = 1
PKT_DATA, PKT_PPS, PKT_PROBE, PKT_ECHO = 1, 2, 3, 4
CHANNELS = {0: "none", 1: "light", 2: "imu", 3: "mic", 4: "piezo"}

HEADER = struct.Struct("<BBBBI") # type, version, node_id, channel, seq
DATA_HDR = struct.Struct("<BBBBIHI") # header + n + dropped
SAMPLE = struct.Struct("<QH") # t_us, value
PPS = struct.Struct("<BBBBIQ") # header + t_us
PROBE = struct.Struct("<BBBBIQ") # header + t_pi_tx_ns
ECHO = struct.Struct("<BBBBIQQQ") # header + t_pi_tx_ns, t_esp_rx_us, t_esp_tx_us


def parse(buf):
    """Return a dict for one received packet, or None if it is malformed."""
    if len(buf) < HEADER.size:
        return None
    ptype, ver, node, ch, seq = HEADER.unpack_from(buf)
    if ver != PROTO_VERSION:
        return None
    base = {"type": ptype, "node": node, "channel": ch, "seq": seq}

    if ptype == PKT_DATA and len(buf) >= DATA_HDR.size:
        *_, n, dropped = DATA_HDR.unpack_from(buf)
        end = DATA_HDR.size + n * SAMPLE.size
        if len(buf) < end:
            return None
        base["dropped"] = dropped
        base["samples"] = list(SAMPLE.iter_unpack(buf[DATA_HDR.size:end]))
        return base
    if ptype == PKT_PPS and len(buf) >= PPS.size:
        base["t_us"] = PPS.unpack_from(buf)[5]
        return base
    if ptype == PKT_ECHO and len(buf) >= ECHO.size:
        _, _, _, _, _, t_pi_tx, t_rx, t_tx = ECHO.unpack_from(buf)
        base.update(t_pi_tx_ns=t_pi_tx, t_esp_rx_us=t_rx, t_esp_tx_us=t_tx)
        return base
    if ptype == PKT_PROBE and len(buf) >= PROBE.size:
        base["t_pi_tx_ns"] = PROBE.unpack_from(buf)[5]
        return base
    return None


def build_data(node, channel, seq, samples, dropped=0):
    hdr = DATA_HDR.pack(PKT_DATA, PROTO_VERSION, node, channel, seq, len(samples), dropped)
    return hdr + b"".join(SAMPLE.pack(t, v) for t, v in samples)


def build_pps(node, seq, t_us):
    return PPS.pack(PKT_PPS, PROTO_VERSION, node, 0, seq, t_us)


def build_probe(seq, t_pi_tx_ns):
    return PROBE.pack(PKT_PROBE, PROTO_VERSION, 0, 0, seq, t_pi_tx_ns)


def build_echo(node, seq, t_pi_tx_ns, t_rx_us, t_tx_us):
    return ECHO.pack(PKT_ECHO, PROTO_VERSION, node, 0, seq, t_pi_tx_ns, t_rx_us, t_tx_us)
