#!/usr/bin/env python3
"""FIP internet-radio now-playing display + MPD control backend (Mycroft Mark II)."""
import json, time, subprocess, urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

LIVEMETA = "https://api.radiofrance.fr/livemeta/pull/7"  # 7 = FIP
PORT = 8080
_cache = {"t": 0, "data": None}


def fetch_meta():
    """Return current FIP track dict, cached ~5s."""
    now = time.time()
    if _cache["data"] and now - _cache["t"] < 5:
        return _cache["data"]
    try:
        req = urllib.request.Request(LIVEMETA, headers={"User-Agent": "Mozilla/5.0"})
        raw = urllib.request.urlopen(req, timeout=8).read()
        d = json.loads(raw)
        steps = d.get("steps", {})
        # Steps overlap: hour-long shows AND ~3min songs are both "current".
        # Prefer the song-level step (most specific) for accurate progress + track.
        current = [s for s in steps.values()
                   if s.get("start", 0) <= now <= s.get("end", 1e12)]
        songs = [s for s in current if s.get("embedType") == "song"]
        pool = songs or current
        cur = min(pool, key=lambda s: s.get("end", 0) - s.get("start", 0)) if pool else None
        if cur is None and steps:  # fall back to most recently started
            cur = max(steps.values(), key=lambda s: s.get("start", 0))
        if cur:
            data = {
                "title": cur.get("title") or "",
                "artist": cur.get("authors") or cur.get("performers") or "",
                "album": cur.get("titreAlbum") or "",
                "year": cur.get("anneeEditionMusique") or "",
                "cover": cur.get("visual") or "",
                "start": cur.get("start", 0),
                "end": cur.get("end", 0),
            }
        else:
            data = {"title": "FIP", "artist": "", "album": "", "year": "",
                    "cover": "", "start": 0, "end": 0}
    except Exception as e:
        data = {"title": "FIP", "artist": "", "album": str(e)[:60], "year": "",
                "cover": "", "start": 0, "end": 0}
    _cache.update(t=now, data=data)
    return data


def mpc(*args):
    try:
        return subprocess.run(["mpc", *args], capture_output=True, text=True,
                              timeout=6).stdout.strip()
    except Exception:
        return ""


def mpd_state():
    out = mpc("status")
    playing = "[playing]" in out
    vol = 0
    for line in out.splitlines():
        if line.startswith("volume:"):
            try:
                vol = int(line.split()[1].rstrip("%"))
            except Exception:
                pass
    return {"playing": playing, "volume": vol}


PAGE = r"""<!doctype html><html><head><meta charset=utf-8>
<meta name=viewport content="width=800,height=480,initial-scale=1">
<title>FIP</title>
<style>
*{margin:0;padding:0;box-sizing:border-box;-webkit-user-select:none;user-select:none}
html,body{width:800px;height:480px;overflow:hidden;background:#000;
  font-family:"Helvetica Neue",Arial,sans-serif;color:#fff;cursor:none}
#bg{position:absolute;inset:0;background-size:cover;background-position:center;
  filter:blur(40px) brightness(.35);transform:scale(1.2);transition:background-image .6s}
#wrap{position:relative;height:100%;display:flex;align-items:center;gap:34px;padding:0 46px}
#art{width:330px;height:330px;border-radius:18px;background:#222 center/cover no-repeat;
  box-shadow:0 14px 50px rgba(0,0,0,.7);flex:none}
#info{flex:1;min-width:0}
#fip{display:inline-block;font-weight:800;letter-spacing:2px;font-size:22px;
  background:#e6005a;color:#fff;padding:5px 14px;border-radius:6px;margin-bottom:22px}
#title{font-size:40px;font-weight:700;line-height:1.12;max-height:140px;overflow:hidden}
#artist{font-size:30px;color:#ff5ca0;margin-top:14px;font-weight:600}
#album{font-size:20px;color:#bbb;margin-top:12px}
#bar{position:absolute;left:0;bottom:0;height:6px;background:#e6005a;width:0;transition:width 1s linear}
#tap{position:absolute;inset:0}
.dim #title,.dim #artist{opacity:.4}
</style></head><body>
<div id=bg></div>
<div id=wrap>
  <div id=art></div>
  <div id=info>
    <span id=fip>FIP</span>
    <div id=title>…</div>
    <div id=artist></div>
    <div id=album></div>
  </div>
</div>
<div id=bar></div>
<div id=tap></div>
<script>
let cur="";
async function tick(){
  try{
    const r=await fetch("/api/now",{cache:"no-store"});const d=await r.json();
    const key=d.title+d.artist;
    if(key!==cur){
      cur=key;
      document.getElementById("title").textContent=d.title||"FIP";
      document.getElementById("artist").textContent=d.artist||"";
      document.getElementById("album").textContent=
        (d.album||"")+(d.year?"  ·  "+d.year:"");
      const art=document.getElementById("art"),bg=document.getElementById("bg");
      if(d.cover){art.style.backgroundImage=`url("${d.cover}")`;
        bg.style.backgroundImage=`url("${d.cover}")`;}
      else{art.style.backgroundImage="";bg.style.backgroundImage="";}
    }
    document.body.classList.toggle("dim",!d.playing);
    // progress bar
    if(d.start&&d.end&&d.end>d.start){
      const now=Date.now()/1000;
      let p=(now-d.start)/(d.end-d.start);p=Math.max(0,Math.min(1,p));
      document.getElementById("bar").style.width=(p*100)+"%";
    }
  }catch(e){}
}
document.getElementById("tap").onclick=()=>fetch("/api/cmd?action=toggle");
setInterval(tick,4000);tick();
</script></body></html>"""


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body if isinstance(body, bytes) else body.encode())

    def do_GET(self):
        u = urlparse(self.path)
        if u.path == "/":
            self._send(200, PAGE, "text/html; charset=utf-8")
        elif u.path == "/api/now":
            d = dict(fetch_meta())
            d.update(mpd_state())
            self._send(200, json.dumps(d), "application/json")
        elif u.path == "/api/cmd":
            q = parse_qs(u.query)
            a = (q.get("action") or [""])[0]
            if a == "toggle": mpc("toggle")
            elif a == "next": mpc("next")
            elif a == "play": mpc("play")
            elif a == "pause": mpc("pause")
            elif a == "volup": mpc("volume", "+5")
            elif a == "voldown": mpc("volume", "-5")
            self._send(200, "ok", "text/plain")
        else:
            self._send(404, "no", "text/plain")


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", PORT), H).serve_forever()
