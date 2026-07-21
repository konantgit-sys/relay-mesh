"""Mesh Fabric Status Page — порт 8085"""
from http.server import HTTPServer, BaseHTTPRequestHandler
import json, subprocess, time

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        procs = subprocess.run(
            "ps aux | grep -E 'content_router_v2|route_engine|smart_router|external_gateway|nostr_bridge|cross_mesh' | grep -v grep | awk '{print $11,$12,$13}'",
            shell=True, capture_output=True, text=True
        ).stdout.strip().split('\n')
        
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.end_headers()
        html = f"""<!DOCTYPE html><html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>SNIN V5 · Mesh Fabric</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{background:radial-gradient(ellipse at top,#0a0f1e,#02040a);color:#e0e6f0;font:16px/1.6 system-ui,sans-serif;min-height:100vh;display:flex;justify-content:center;align-items:center;padding:20px}}
.card{{background:rgba(15,20,40,.85);border:1px solid rgba(100,140,255,.15);border-radius:16px;padding:32px;max-width:600px;width:100%}}
h1{{font-size:22px;color:#7eb8ff;margin-bottom:4px}}
.sub{{color:#5a6a8a;font-size:13px;margin-bottom:20px}}
.row{{display:flex;justify-content:space-between;padding:8px 12px;border-radius:8px;margin:2px 0}}
.row:nth-child(odd){{background:rgba(255,255,255,.03)}}
.name{{font-family:monospace;font-size:13px;color:#a0c4ff}}
.port{{font-family:monospace;font-size:13px;color:#5a8a6a}}
.badge{{display:inline-block;padding:2px 10px;border-radius:12px;font-size:11px;font-weight:600}}
.alive{{background:rgba(72,199,142,.15);color:#48c78e}}
.footer{{margin-top:20px;color:#4a5a7a;font-size:12px;text-align:center}}
a{{color:#7eb8ff}}
</style></head><body>
<div class="card">
<h1>⚡ SNIN V5 Mesh Fabric</h1>
<div class="sub">Gateway:9931 · SmartRouter:9932 · ContentRouter:9920 · RouteEngine:9910 · NostrBridge:9941 · CrossMesh:9946</div>
{''.join(f'<div class="row"><span class="name">{p}</span><span class="badge alive">● LIVE</span></div>' for p in procs if p)}
<div class="footer">
{len(procs)}/6 процессов · {time.strftime('%H:%M:%S MSK')}<br>
<a href="https://relay-dash.v2.site">→ Дашборд</a> &nbsp;|&nbsp; <a href="https://snin-relay.v2.site">→ Релей</a>
</div></div></body></html>"""
        self.wfile.write(html.encode())

if __name__ == '__main__':
    HTTPServer(('0.0.0.0', 8085), Handler).serve_forever()
