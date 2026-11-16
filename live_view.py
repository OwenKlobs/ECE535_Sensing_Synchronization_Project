"""Live graph of incoming sensor data, served by the Pi to any browser on the network.

receiver.py feeds samples into LiveBuffer and starts the web server; open
http://<pi-hostname>.local:8000 on your laptop to watch. Uses only the Python
standard library and a plain <canvas>, so nothing extra to install.
"""
import json
import socket
import threading
import time
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

MAX_SECONDS = 60


class LiveBuffer:
    def __init__(self, rate_hz=1000):
        self.lock = threading.Lock()
        self.maxlen = MAX_SECONDS * rate_hz
        self.series = {} # (node, channel name) -> deque of (t_us, value)
        self.pps = {} # node -> count of PPS edges seen

    def add_samples(self, node, channel, samples):
        key = (node, channel)
        with self.lock:
            d = self.series.get(key)
            if d is None:
                d = self.series[key] = deque(maxlen=self.maxlen)
            d.extend(samples)

    def add_pps(self, node):
        with self.lock:
            self.pps[node] = self.pps.get(node, 0) + 1

    def snapshot(self, seconds, points=1200):
        """Last `seconds` of each series, reduced to min/max pairs so spikes survive."""
        out = {}
        with self.lock:
            items = [(k, list(d)) for k, d in self.series.items()]
            pps = dict(self.pps)
        for (node, ch), data in items:
            if not data:
                continue
            t_end = data[-1][0]
            t_start = t_end - seconds * 1e6
            sel = [(t, v) for t, v in data if t >= t_start]
            xs, ys = [], []
            nbins = max(1, points // 2)
            if len(sel) <= points:
                xs = [(t - t_end) / 1e6 for t, _ in sel]
                ys = [v for _, v in sel]
            else:
                width = (seconds * 1e6) / nbins
                bins = {}
                for t, v in sel:
                    b = int((t - t_start) / width)
                    lo, hi = bins.get(b, (v, v))
                    bins[b] = (min(lo, v), max(hi, v))
                for b in sorted(bins):
                    lo, hi = bins[b]
                    x = (t_start + (b + 0.5) * width - t_end) / 1e6
                    xs += [x, x]
                    ys += [lo, hi]
            n = len(sel)
            rate = (n - 1) / ((sel[-1][0] - sel[0][0]) / 1e6) if n > 1 and sel[-1][0] > sel[0][0] else 0
            out[f"{node}:{ch}"] = {"node": node, "channel": ch, "x": xs, "y": ys,
                                   "last": data[-1][1], "rate": round(rate, 1),
                                   "pps": pps.get(node, 0)}
        return out


PAGE = """<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Live sensor view</title>
<style>
:root{--bg:#f7f7f5;--fg:#222;--muted:#666;--grid:#ddd;--card:#fff}
@media (prefers-color-scheme:dark){:root{--bg:#1b1b1a;--fg:#eee;--muted:#aaa;--grid:#383836;--card:#252524}}
body{margin:0;padding:16px;background:var(--bg);color:var(--fg);font:15px system-ui,sans-serif}
h1{font-size:18px;font-weight:500;margin:0 0 12px}
.bar{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin-bottom:12px}
button{font:inherit;padding:6px 12px;border-radius:8px;border:1px solid var(--grid);background:var(--card);color:var(--fg);cursor:pointer}
button.on{border-color:var(--fg)}
#stats{display:flex;flex-wrap:wrap;gap:16px;margin:10px 0;color:var(--muted)}
.dot{display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:6px}
canvas{width:100%;height:60vh;background:var(--card);border-radius:12px;display:block}
</style></head><body>
<h1>Live sensor view</h1>
<div class="bar">
  <span>Window</span>
  <button data-s="5">5 s</button><button data-s="10" class="on">10 s</button>
  <button data-s="30">30 s</button><button data-s="60">60 s</button>
  <button id="pause">Pause</button>
</div>
<div id="stats">Waiting for data...</div>
<canvas id="c"></canvas>
<script>
const colors=["#1D9E75","#D85A30","#534AB7","#BA7517"];
let seconds=10, paused=false, last=null;
document.querySelectorAll("button[data-s]").forEach(b=>b.onclick=()=>{
  seconds=+b.dataset.s; document.querySelectorAll("button[data-s]").forEach(x=>x.classList.toggle("on",x===b));});
document.getElementById("pause").onclick=e=>{paused=!paused;e.target.textContent=paused?"Resume":"Pause";};
const cv=document.getElementById("c"), ctx=cv.getContext("2d");
function css(n){return getComputedStyle(document.documentElement).getPropertyValue(n).trim();}
function draw(data){
  const dpr=window.devicePixelRatio||1, W=cv.clientWidth, H=cv.clientHeight;
  cv.width=W*dpr; cv.height=H*dpr; ctx.setTransform(dpr,0,0,dpr,0,0);
  ctx.clearRect(0,0,W,H);
  const L=52,R=12,T=12,B=30, pw=W-L-R, ph=H-T-B;
  ctx.strokeStyle=css("--grid"); ctx.fillStyle=css("--muted"); ctx.font="12px system-ui"; ctx.lineWidth=1;
  for(let v=0; v<=4096; v+=1024){const y=T+ph-(v/4096)*ph; ctx.beginPath(); ctx.moveTo(L,y); ctx.lineTo(L+pw,y); ctx.stroke();
    ctx.textAlign="right"; ctx.fillText(v,L-6,y+4);}
  const step=seconds<=10?1:seconds<=30?5:10;
  for(let s=0; s<=seconds; s+=step){const x=L+pw-(s/seconds)*pw; ctx.textAlign="center"; ctx.fillText(s?("-"+s+" s"):"now",x,H-10);}
  const keys=Object.keys(data).sort();
  keys.forEach((k,i)=>{const d=data[k]; ctx.strokeStyle=colors[i%colors.length]; ctx.lineWidth=1.5; ctx.beginPath();
    let started=false;
    for(let j=0;j<d.x.length;j++){ if(d.x[j]<-seconds) continue;
      const x=L+pw+(d.x[j]/seconds)*pw, y=T+ph-(d.y[j]/4096)*ph;
      if(!started){ctx.moveTo(x,y); started=true;} else ctx.lineTo(x,y);}
    ctx.stroke();});
  document.getElementById("stats").innerHTML = keys.length? keys.map((k,i)=>{const d=data[k];
    return `<span><span class="dot" style="background:${colors[i%colors.length]}"></span>Node ${d.node} ${d.channel}: <b>${d.last}</b> &middot; ${d.rate} samples/s &middot; PPS ${d.pps}</span>`;}).join("")
    : "Waiting for data...";
}
async function tick(){
  if(!paused){ try{ const r=await fetch("/data?s="+seconds); last=await r.json(); }catch(e){} }
  if(last) draw(last);
  setTimeout(tick,200);
}
window.onresize=()=>{ if(last) draw(last); };
tick();
</script></body></html>
"""


def start_server(buffer, port=8000):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            url = urlparse(self.path)
            if url.path == "/data":
                s = float(parse_qs(url.query).get("s", ["10"])[0])
                body = json.dumps(buffer.snapshot(min(max(s, 1), MAX_SECONDS))).encode()
                ctype = "application/json"
            elif url.path == "/":
                body, ctype = PAGE.encode(), "text/html; charset=utf-8"
            else:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    host = socket.gethostname()
    print(f"Live view: open http://{host}.local:{port} in a browser on the same network")
    return server
