#!/usr/bin/env python3
"""
Phase 3 — LAN Discovery: unit-тесты.

Запуск: cd /home/agent/data/sites/relay-mesh && pytest tests/test_lan_discovery.py -v
"""

import pytest
import json
import time
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Используем сокет для multicast тестов
import socket
import struct


class TestLANDiscoveryCore:

    def test_beacon_format(self):
        """Beacon содержит все обязательные поля."""
        from lan_discovery import LANDicovery, sigs
        sigs.init_signing()

        d = LANDicovery(listen_port=19901)
        beacon_bytes = d._create_beacon()
        beacon = json.loads(beacon_bytes.decode())

        required = {"pubkey", "ip", "port", "nat_type", "version", 
                     "mesh_id", "timestamp", "signature"}
        assert required.issubset(set(beacon.keys()))
        assert len(beacon["pubkey"]) == 64  # hex
        assert len(beacon["signature"]) == 128  # Ed25519
        assert beacon["version"] == "5.0.0.dev1"
        assert beacon["mesh_id"] == "snin-main-1"

    def test_beacon_pubkey(self):
        """Pubkey в beacon совпадает с ключом подписи."""
        from lan_discovery import LANDicovery, sigs
        sigs.init_signing()

        d = LANDicovery(listen_port=19902)
        beacon = json.loads(d._create_beacon())

        vk = sigs.get_verifying_key_hex()
        assert beacon["pubkey"] == vk

    def test_local_ip(self):
        """_get_local_ip возвращает валидный IP."""
        from lan_discovery import LANDicovery
        d = LANDicovery(listen_port=19903)
        ip = d._get_local_ip()
        parts = ip.split(".")
        assert len(parts) == 4
        assert all(0 <= int(p) <= 255 for p in parts)

    def test_peer_structure(self):
        """Пир сохраняет корректную структуру."""
        from lan_discovery import LANDicovery
        d = LANDicovery(listen_port=19904)

        test_peer = {
            "pubkey": "aa" * 32,
            "agent_name": "test_agent",
            "ip": "192.168.1.10",
            "port": 9908,
            "nat_type": "easy",
            "version": "5.0.0.dev1",
            "source": "lan_discovery",
        }

        peer_key = f"{test_peer['pubkey']}:{test_peer['ip']}"
        d._peers[peer_key] = test_peer
        
        peers = d.get_peers()
        assert peer_key in peers
        assert peers[peer_key]["pubkey"] == "aa" * 32
        assert peers[peer_key]["source"] == "lan_discovery"

    def test_cleanup_dead_peers(self):
        """Пир удаляется после TTL."""
        from lan_discovery import LANDicovery, PEER_TTL
        d = LANDicovery(listen_port=19905)

        # Добавляем пира с истёкшим last_seen
        old_peer = {
            "pubkey": "bb" * 32,
            "agent_name": "old_agent",
            "ip": "10.0.0.1",
            "port": 9908,
            "nat_type": "easy",
            "last_seen": time.time() - PEER_TTL - 10,
            "source": "lan_discovery",
        }
        d._peers["bbbb:10.0.0.1"] = old_peer

        # Добавляем живого пира
        live_peer = {
            "pubkey": "cc" * 32,
            "agent_name": "live_agent",
            "ip": "10.0.0.2",
            "port": 9908,
            "nat_type": "easy",
            "last_seen": time.time(),
            "source": "lan_discovery",
        }
        d._peers["cccc:10.0.0.2"] = live_peer

        # Чиним
        import asyncio
        loop = asyncio.new_event_loop()
        loop.run_until_complete(d._cleanup_dead_peers())
        loop.close()

        peers = d.get_peers()
        assert "bbbb:10.0.0.1" not in peers
        assert "cccc:10.0.0.2" in peers
        assert len(peers) == 1

    def test_skip_own_beacon(self):
        """Свой beacon пропускается."""
        from lan_discovery import LANDicovery, sigs
        sigs.init_signing()
        
        d = LANDicovery(listen_port=19906)
        
        # Создаём свой beacon
        beacon_bytes = d._create_beacon()
        beacon = json.loads(beacon_bytes.decode())
        
        # Проверяем что process_beacon пропустит его
        import asyncio
        loop = asyncio.new_event_loop()
        loop.run_until_complete(d._process_beacon(beacon_bytes, ("127.0.0.1", 7777)))
        loop.close()
        
        assert len(d.get_peers()) == 0
        assert d._stats["beacons_rejected"] == 0  # не rejected, а silently skipped

    def test_reject_invalid_beacon(self):
        """Beacon без обязательных полей отклоняется."""
        from lan_discovery import LANDicovery
        d = LANDicovery(listen_port=19907)
        
        # Невалидный beacon
        bad_beacon = json.dumps({"pubkey": "abc"}).encode()
        
        import asyncio
        loop = asyncio.new_event_loop()
        loop.run_until_complete(d._process_beacon(bad_beacon, ("127.0.0.1", 7777)))
        loop.close()
        
        assert d._stats["beacons_rejected"] == 1

    def test_stats(self):
        """Статистика валидна."""
        from lan_discovery import LANDicovery
        d = LANDicovery(listen_port=19908)
        
        stats = d.get_stats()
        assert "beacons_sent" in stats
        assert "beacons_received" in stats
        assert "beacons_verified" in stats
        assert "beacons_rejected" in stats
        assert "peers_active" in stats


class TestLANDiscoveryIntegration:

    def test_two_discoveries_see_each_other(self):
        """Два инстанса LAN Discovery обрабатывают beacon друг друга."""
        from lan_discovery import LANDicovery, sigs
        sigs.init_signing()
        
        import asyncio
        
        d1 = LANDicovery(listen_port=19911)
        d2 = LANDicovery(listen_port=19912)
        
        loop = asyncio.new_event_loop()
        
        # Создаём beacon от d1
        beacon1_bytes = d1._create_beacon()
        beacon1 = json.loads(beacon1_bytes.decode())
        
        # Оба инстанса используют один модуль sigs → одинаковый pubkey
        # Проверяем что свой beacon пропускается
        loop.run_until_complete(d2._process_beacon(beacon1_bytes, ("127.0.0.1", 19911)))
        
        # Свой beacon (одинаковый pubkey) — silently skipped, не rejected
        assert d2._stats["beacons_received"] == 1
        assert d2._stats["beacons_verified"] == 0
        assert d2._stats["beacons_rejected"] == 0
        assert len(d2.get_peers()) == 0
        
        # Создаём beacon с ДРУГИМ pubkey (симуляция другого пира)
        import copy
        altered = copy.deepcopy(beacon1)
        altered["pubkey"] = "ff" * 32
        
        loop.run_until_complete(d2._process_beacon(json.dumps(altered).encode(), ("127.0.0.1", 19911)))
        
        # Фейковая подпись → rejected
        assert d2._stats["beacons_rejected"] == 1
        
        loop.close()


class TestBeaconSignature:

    def test_beacon_signature_format(self):
        """Подпись beacon — 128 hex символов."""
        from lan_discovery import LANDicovery, sigs
        sigs.init_signing()
        
        d = LANDicovery(listen_port=19921)
        beacon = json.loads(d._create_beacon().decode())
        
        sig = beacon["signature"]
        assert len(sig) == 128
        assert all(c in "0123456789abcdef" for c in sig.lower())
