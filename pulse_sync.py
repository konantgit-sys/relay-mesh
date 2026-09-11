#!/usr/bin/env python3
"""
SNIN Pulse Sync v2.4 — запущен 2026-06-27

Простой heartbeat: каждые 5 секунд TCP-коннектится ко всем mesh-сервисам.
Фиксирует: latency, alive/dead, время последнего ответа.
Записывает /home/agent/data/sites/relay-mesh/pulse_status.json для хаба.

Без ntplib, без aiohttp — только raw socket.
"""

import asyncio, json, os, socket, time
from datetime import datetime

STATUS_FILE = "/home/agent/data/sites/relay-mesh/pulse_status.json"
LOG_FILE = "/home/agent/data/logs/pulse_sync.log"

# Конфиг узлов: имя → порт
NODES = {
    "smart_router":    9932,
    "route_engine":    9910,
    "content_router":  9920,
    "nostr_bridge_0":  9941,
    "nostr_bridge_1":  9942,
    "nostr_bridge_2":  9943,
    "nostr_bridge_3":  9944,
    "nostr_bridge_4":  9945,
    "external_gateway": 9931,
    "identity_api":    9940,
    "relay_server":    8198,
    "snin_adapter":    8199,
}

class PulseSync:
    def __init__(self):
        self.seq = 0
        self.nodes = {
            name: {"port": port, "alive": False, "latency_ms": 0, "last_seen": None, "dead_since": None}
            for name, port in NODES.items()
        }
        self.start_time = time.time()

    def log(self, msg):
        ts = datetime.now().strftime("%H:%M:%S")
        with open(LOG_FILE, "a") as f:
            f.write(f"{ts} {msg}\n")

    async def check_node(self, name: str, port: int) -> tuple[bool, float]:
        """TCP connect → возвращает (alive, latency_ms)"""
        try:
            start = time.monotonic()
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection("127.0.0.1", port),
                timeout=1.5
            )
            latency = (time.monotonic() - start) * 1000
            writer.close()
            await writer.wait_closed()
            return True, round(latency, 2)
        except:
            return False, 0

    async def pulse_cycle(self):
        """Один цикл: проверить всех → записать статус"""
        self.seq += 1
        now = datetime.utcnow().isoformat()

        checks = []
        for name, info in self.nodes.items():
            checks.append(self.check_node(name, info["port"]))

        results = await asyncio.gather(*checks)

        alive_count = 0
        dead_count = 0
        for (name, info), (alive, latency) in zip(self.nodes.items(), results):
            was_alive = info["alive"]
            info["alive"] = alive
            info["latency_ms"] = latency
            if alive:
                alive_count += 1
                info["last_seen"] = now
                info["dead_since"] = None
                if not was_alive:
                    self.log(f"RECOVERED {name} :{info['port']}")
            else:
                dead_count += 1
                if was_alive:
                    info["dead_since"] = now
                    self.log(f"⚠ DEAD {name} :{info['port']}")
                elif info.get("dead_since") is None:
                    info["dead_since"] = now

        # Запись статуса
        status = {
            "timestamp": now,
            "sequence": self.seq,
            "uptime_seconds": int(time.time() - self.start_time),
            "alive": alive_count,
            "dead": dead_count,
            "total": len(self.nodes),
            "nodes": {
                name: {
                    "port": info["port"],
                    "alive": info["alive"],
                    "latency_ms": info["latency_ms"],
                    "last_seen": info["last_seen"],
                    "dead_since": info["dead_since"],
                }
                for name, info in self.nodes.items()
            },
        }

        with open(STATUS_FILE, "w") as f:
            json.dump(status, f, indent=2)

    async def run(self):
        self.log(f"STARTED — {len(self.nodes)} nodes")
        # Первый замер сразу
        await self.pulse_cycle()
        self.log(f"INITIAL: {sum(1 for n in self.nodes.values() if n['alive'])}/{len(self.nodes)} alive")

        while True:
            try:
                await asyncio.sleep(5)
                await self.pulse_cycle()
            except Exception as e:
                self.log(f"ERROR: {e}")
                await asyncio.sleep(5)


async def main():
    pulse = PulseSync()

    # HTTP server на :9930 для /api/pulse/status
    from aiohttp import web

    async def status_handler(request):
        if os.path.exists(STATUS_FILE):
            with open(STATUS_FILE) as f:
                return web.json_response(json.load(f))
        return web.json_response({"error": "no data yet"}, status=503)

    async def health_handler(request):
        return web.json_response({"ok": True})

    app = web.Application()
    app.router.add_get("/api/pulse/status", status_handler)
    app.router.add_get("/health", health_handler)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 9930)
    await site.start()
    pulse.log("HTTP server on :9930")

    # Запуск pulse loop
    asyncio.create_task(pulse.run())

    # Keep alive
    while True:
        await asyncio.sleep(600)

if __name__ == "__main__":
    asyncio.run(main())
