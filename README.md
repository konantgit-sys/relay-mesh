# Relay Mesh — P2P Transport & Routing for AI Agents

Decentralized transport layer for autonomous AI agents on Nostr.

Smart Router distributes agent traffic across 4 channels: Direct (TCP), Gossip (PubSub), Mesh (P2P), Nostr (Relay).

## Channels

| Channel | Protocol | Latency | Use |
|---------|----------|---------|-----|
| Direct | TCP (:9932) | <5ms | Same-machine agents |
| Gossip | IPFS PubSub | ~50ms | LAN/cluster |
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
