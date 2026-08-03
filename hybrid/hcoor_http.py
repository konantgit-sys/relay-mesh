#!/usr/bin/env python3
"""
HTTP health wrapper for Hybrid Coordinator.
Starts coordinator on port 9970 (raw TCP) + serves status page on port 9970 via HTTP upgrade.
"""
import asyncio
import json
import os
import sys
import time

# Add relay-mesh to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from hybrid.hcoor import HybridCoordinator, DB_PATH

HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>SNIN Hybrid Coordinator</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:system-ui,-apple-system,sans-serif;background:#0a0a0f;color:#e0e0e0;min-height:100vh;display:flex;align-items:center;justify-content:center}
.card{background:#14141f;border:1px solid #2a2a3a;border-radius:12px;padding:32px;max-width:480px;width:100%}
h1{font-size:24px;margin-bottom:4px}
.green{color:#4ade80}.amber{color:#f59e0b}.red{color:#ef4444}.dim{color:#6b7280}
.status-row{display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid #1e1e2e}
.status-row:last-child{border-bottom:none}
.metric{font-family:monospace;font-size:16px}
.badge{display:inline-block;padding:2px 8px;border-radius:4px;font-size:12px;font-weight:700}
.badge-online{background:#064e3b;color:#4ade80}.badge-offline{background:#4a1c1c;color:#ef4444}
.timestamp{color:#6b7280;font-size:11px;margin-top:16px;text-align:center}
</style>
</head>
<body>
<div class="card">
<h1>🧬 SNIN Hybrid Coordinator</h1>
<p class="dim" style="margin-bottom:20px">Discovery Coordinator for mesh agents</p>
{rows}
<p class="timestamp">Updated: {ts}</p>
</div>
</body>
</html>"""


async def handle_http(reader, writer):
    """Minimal HTTP handler for health/status."""
    try:
        request_line = await asyncio.wait_for(reader.readline(), 5)
        request = request_line.decode()
        
        if not request.startswith("GET"):
            writer.write(b"HTTP/1.1 405 Method Not Allowed\r\n\r\n")
            return
        
        # Build status
        db_stats = {"total_agents": 0, "online": 0, "events_24h": 0}
        try:
            from hybrid.hcoor import HybridDB
            db = HybridDB(DB_PATH)
            db_stats = db.get_stats()
            db.close()
        except Exception as e:
            db_stats["error"] = str(e)
        
        import datetime
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")
        
        # Build rows
        uptime_s = db_stats.get("uptime_sec", 0)
        h, m = int(uptime_s // 3600), int((uptime_s % 3600) // 60)
        
        online = db_stats.get("online", 0)
        total = db_stats.get("total_agents", 0)
        online_cls = "green" if online > 0 else "red"
        badge = "badge-online" if online > 0 else "badge-offline"
        badge_text = "ONLINE" if online > 0 else "OFFLINE"
        
        rows = f"""
<div class="status-row"><span>Status</span><span class="{online_cls}"><span class="badge {badge}">{badge_text}</span></span></div>
<div class="status-row"><span>Agents Online</span><span class="metric {online_cls}">{online}</span></div>
<div class="status-row"><span>Total Agents</span><span class="metric dim">{total}</span></div>
<div class="status-row"><span>Events (24h)</span><span class="metric dim">{db_stats.get('events_24h', 0)}</span></div>
<div class="status-row"><span>Uptime</span><span class="metric dim">{h}h {m}m</span></div>
<div class="status-row"><span>Protocol</span><span class="metric dim">TCP JSON-lines :9970</span></div>
<div class="status-row"><span>NAT Strategies</span><span class="metric dim">5 (direct, reverse, holepunch, relay, broker)</span></div>
"""
        
        body = HTML.format(rows=rows, ts=now).encode()
        resp = b"HTTP/1.1 200 OK\r\nContent-Type: text/html; charset=utf-8\r\n"
        resp += f"Content-Length: {len(body)}\r\n".encode()
        resp += b"Connection: close\r\n\r\n"
        resp += body
        writer.write(resp)
        await writer.drain()
        
    except Exception:
        pass
    finally:
        writer.close()


async def main():
    import argparse
    parser = argparse.ArgumentParser(description="SNIN Hybrid Coordinator + HTTP health")
    parser.add_argument("--port", type=int, default=9970)
    parser.add_argument("--host", type=str, default="0.0.0.0")
    parser.add_argument("--http-only", action="store_true", help="Only serve HTTP, don't start coordinator")
    args = parser.parse_args()
    
    if not args.http_only:
        # Start coordinator in background
        hcoor = HybridCoordinator(port=args.port, host=args.host)
        asyncio.ensure_future(hcoor.start())
        # Give it a moment
        await asyncio.sleep(0.5)
        print(f"[HCOOR-WRAP] Coordinator started on :{args.port}")
    
    # Start HTTP server on same port — coordinator handles raw TCP, HTTP is handled here
    # Actually we can't share a port. Let coordinator run on 9970, HTTP on 9971.
    # For v2.site, use port.txt: 9971
    http_port = int(os.environ.get("HTTP_PORT", "9971"))
    http_host = os.environ.get("HTTP_HOST", "0.0.0.0")
    
    server = await asyncio.start_server(handle_http, http_host, http_port)
    print(f"[HCOOR-WRAP] HTTP health on {http_host}:{http_port}")
    
    # Keep running
    while True:
        await asyncio.sleep(60)


if __name__ == "__main__":
    asyncio.run(main())
