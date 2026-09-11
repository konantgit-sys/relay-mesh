# Relay Mesh — P2P Transport & Routing for AI Agents

Decentralized transport layer for autonomous AI agents on Nostr.

Smart Router (единственная точка входа, :9932) distributes agent traffic across 4 channels: Direct (TCP), Gossip (TCP stream), Mesh (P2P), Nostr (L0 coordination).

## Channels

| Channel | Protocol | Latency | Use |
|---------|----------|---------|-----|
| Direct | TCP (via Smart Router :9932) | <5ms | Same-machine agents |
| Gossip | TCP writer pool (:9105–9109) | ~50ms | LAN/cluster |
| Mesh | P2P DHT | ~200ms | WAN discovery |
| Nostr | Relay (:9910) | 1-3s | Global broadcast |

## Quick Start

```bash
make run
```

## Architecture

See [ARCHITECTURE.md](./ARCHITECTURE.md) for full details.

## License

MIT © 2026 Anton
