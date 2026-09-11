# Changelog — Relay Mesh (транспортный слой SNIN V5)

Формат: [Keep a Changelog](https://keepachangelog.com/ru/1.1.0/).
Relay Mesh — транспортный слой SNIN V5: приём, маршрутизация и доставка
сообщений между агентами. Единственная точка входа — Smart Router (:9932).

## [5.0.0-relay] — 2026-09-11

Первый тегированный релиз транспортного слоя.

### Added
- **Smart Router (:9932)** — единственная точка входа для сообщений;
  маршрутизация по контентным правилам и приоритетной очереди.
- **Route Engine (:9910)** и **Content Router v2 (:9920)** — связка
  маршрутизации Smart Router → Route Engine → Content Router.
- **Gossip-канал** (`gossip_stream.py`, Gossip Stream V8): TCP writer pool,
  порты 9105–9109, события kind 39004 (gossip_data) / 39005 (gossip_ack).
- **Proof Mesh**: hash-chain журнал, sensor, econ, audit_daemon;
  внешняя проверка сертификата по публичному ключу.
- **README** с таблицей каналов и quick start.

### Fixed
- `verify_chain` в proof-mesh: корректная пересборка подписи вместо
  доверия к записанному хешу (поймано в ходе внешней проверки).
- Удалены ложные утверждения про «101 релей» — приведено к реальным числам.

### Chore
- `.gitignore`: `*.gz`, `*.db-wal`, `*.db-shm`, `*.log-*.*` — снято 19 МБ
  рантайм-мусора из статуса.
- Синхронизация рабочей копии с проектным репозиторием (сверка хешами):
  роутеры, `proof_mesh/`, `mesh_supervisor.py`, docs.

### Notes
- Ветка `main` в этом репозитории — историческая (v1.1, июль 2026);
  рабочая линия — `master`.
