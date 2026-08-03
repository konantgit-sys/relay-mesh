#!/usr/bin/env python3
"""
SNIN Agent Connector — подключает реальных агентов к Hybrid Coordinator.
Каждый агент: регистрируется, получает peer list, держит соединение живым.
"""
import asyncio, json, time, os, sys, signal

HCOOR_HOST = os.environ.get("HCOOR_HOST", "127.0.0.1")
HCOOR_PORT = int(os.environ.get("HCOOR_PORT", "9970"))
PING_INTERVAL = 25  # чуток быстрее серверного TTL 30s

# ─── Агенты SNIN (реальные npub из relay_mesh) ───
SNIN_AGENTS = [
    {
        "pubkey": "f9c3a1b2d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0",
        "name": "Cryter",
        "capabilities": ["publish", "analyze", "engage", "forecast"],
        "nat_type": "easy",
    },
    {
        "pubkey": "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1",
        "name": "Forecaster",
        "capabilities": ["forecast", "analyze", "predict"],
        "nat_type": "easy",
    },
    {
        "pubkey": "b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2",
        "name": "Archivist",
        "capabilities": ["archive", "search", "attest", "store"],
        "nat_type": "easy",
    },
]


async def agent_loop(agent_cfg: dict):
    """Persistent agent connection with auto-reconnect."""
    pubkey = agent_cfg["pubkey"]
    name = agent_cfg["name"]
    
    while True:
        try:
            r, w = await asyncio.open_connection(HCOOR_HOST, HCOOR_PORT)
            print(f"[{name}] 🔗 Connected to coordinator")
            
            # Register
            w.write(json.dumps({
                "type": "register",
                "pubkey": pubkey,
                "name": name,
                "npub": f"npub1{pubkey[:20]}",
                "capabilities": agent_cfg["capabilities"],
                "nat_type": agent_cfg["nat_type"],
                "mode": "direct",
                "version": "5.0.0"
            }).encode() + b"\n")
            await w.drain()
            
            resp = json.loads(await asyncio.wait_for(r.readline(), 5))
            peers_online = resp.get("peers_online", 0)
            print(f"[{name}] ✅ Registered — {peers_online} agents online")
            
            # Ping loop
            ping_n = 0
            while True:
                await asyncio.sleep(PING_INTERVAL)
                w.write(json.dumps({"type": "ping", "pubkey": pubkey}).encode() + b"\n")
                await w.drain()
                pong = json.loads(await asyncio.wait_for(r.readline(), 5))
                ping_n += 1
                if ping_n % 6 == 0:  # log every ~2.5 min
                    print(f"[{name}] 💓 ping #{ping_n}")
                
        except (ConnectionRefusedError, OSError) as e:
            print(f"[{name}] ⚠️ Connection failed: {e}. Retry in 10s...")
        except asyncio.TimeoutError:
            print(f"[{name}] ⏰ Timeout — reconnecting...")
        except Exception as e:
            print(f"[{name}] ❌ Error: {type(e).__name__}: {e}")
        finally:
            try:
                w.close()
            except:
                pass
        
        await asyncio.sleep(10)  # reconnection delay


async def main():
    print(f"🚀 SNIN Agent Connector v1.0")
    print(f"   Coordinator: {HCOOR_HOST}:{HCOOR_PORT}")
    print(f"   Agents: {len(SNIN_AGENTS)}")
    
    tasks = [asyncio.create_task(agent_loop(cfg)) for cfg in SNIN_AGENTS]
    stop = asyncio.Event()
    
    def shutdown():
        print("\n⏹️ Shutting down...")
        stop.set()
        for t in tasks:
            t.cancel()
    
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, shutdown)
    
    await stop.wait()

if __name__ == "__main__":
    asyncio.run(main())
