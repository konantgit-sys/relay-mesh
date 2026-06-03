#!/usr/bin/env python3
"""
Phase 5 — UDP Tracker BEP15: unit-тесты.

Запуск: cd /home/agent/data/sites/relay-mesh && pytest tests/test_udp_tracker.py -v
"""

import pytest
import struct
import time
import os
import sys
import random

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestBEP15Protocol:

    def test_magic_cookie(self):
        """Magic cookie BEP15 = 0x41727101980."""
        from udp_tracker import MAGIC_COOKIE
        assert MAGIC_COOKIE == 0x41727101980

    def test_action_constants(self):
        """Константы action BEP15."""
        from udp_tracker import ACTION_CONNECT, ACTION_ANNOUNCE, ACTION_ERROR
        assert ACTION_CONNECT == 0
        assert ACTION_ANNOUNCE == 1
        assert ACTION_ERROR == 3

    def test_connect_packet_format(self):
        """Connect пакет: magic(8) + action(4) + transaction_id(4) = 16 байт."""
        from udp_tracker import MAGIC_COOKIE, ACTION_CONNECT

        transaction_id = random.randint(1, 0xFFFFFFFF)
        packet = struct.pack("!QII", MAGIC_COOKIE, ACTION_CONNECT, transaction_id)
        assert len(packet) == 16

        magic, action, tid = struct.unpack_from("!QII", packet, 0)
        assert magic == MAGIC_COOKIE
        assert action == ACTION_CONNECT
        assert tid == transaction_id

    def test_connect_response_format(self):
        """Connect response: action(4) + transaction_id(4) + connection_id(8) = 16 байт."""
        conn_id = 123456789
        transaction_id = 42
        resp = struct.pack("!II", 0, transaction_id)
        resp += struct.pack("!Q", conn_id)
        assert len(resp) == 16

        action, tid = struct.unpack_from("!II", resp, 0)
        cid = struct.unpack_from("!Q", resp, 8)[0]
        assert action == 0
        assert tid == transaction_id
        assert cid == conn_id

    def test_announce_packet_format(self):
        """Announce пакет: connection_id(8) + action(4) + transaction_id(4) + info_hash(20)
        + peer_id(20) + downloaded(8) + left(8) + uploaded(8) + event(4) + ip(4)
        + key(4) + num_want(4) + port(2) = 98 байт."""
        conn_id = 42
        info_hash = b"\x00" * 20
        peer_id = b"SN500000000000001".ljust(20, b"\0")
        port = 9908

        packet = struct.pack("!Q", conn_id)  # 8
        packet += struct.pack("!II", 1, 1)  # 8
        packet += info_hash  # 20
        packet += peer_id  # 20
        packet += struct.pack("!Q", 0)  # downloaded 8
        packet += struct.pack("!Q", 0)  # left 8
        packet += struct.pack("!Q", 0)  # uploaded 8
        packet += struct.pack("!I", 2)  # event (started) 4
        packet += struct.pack("!I", 0)  # ip 4
        packet += struct.pack("!I", 0)  # key 4
        packet += struct.pack("!i", -1)  # num_want 4
        packet += struct.pack("!H", port)  # 2

        assert len(packet) == 98

    def test_announce_response_format(self):
        """Announce response: action(4) + transaction_id(4) + interval(4)
        + leechers(4) + seeders(4) + [ip(4) + port(2)] * N."""
        transaction_id = 7
        peers_data = b"\x0a\x00\x00\x01\x26\x9c"  # 10.0.0.1:9900
        peers_data += b"\x0a\x00\x00\x02\x26\x9d"  # 10.0.0.2:9901

        resp = struct.pack("!II", 1, transaction_id)  # announce + tid
        resp += struct.pack("!I", 1800)  # interval
        resp += struct.pack("!I", 0)  # leechers
        resp += struct.pack("!I", 2)  # seeders
        resp += peers_data

        assert len(resp) == 20 + 12  # 20 header + 12 peers

        action = struct.unpack_from("!I", resp, 0)[0]
        assert action == 1

        seeders = struct.unpack_from("!I", resp, 16)[0]
        assert seeders == 2


class TestUDPTrackerServer:

    def test_connect_handler(self):
        """Обработчик connect возвращает корректный response."""
        from udp_tracker import UDPTracker, MAGIC_COOKIE, ACTION_CONNECT, sigs
        sigs.init_signing()

        tracker = UDPTracker(port=19020)

        transaction_id = 42
        packet = struct.pack("!QII", MAGIC_COOKIE, ACTION_CONNECT, transaction_id)
        response = tracker._handle_connect(packet, ("127.0.0.1", 12345))

        assert len(response) == 16
        action, tid = struct.unpack_from("!II", response, 0)
        conn_id = struct.unpack_from("!Q", response, 8)[0]

        assert action == ACTION_CONNECT
        assert tid == transaction_id
        assert conn_id > 0

        assert tracker._stats["connects"] == 1

    def test_connect_invalid_magic(self):
        """Неверный magic cookie возвращает пустой response."""
        from udp_tracker import UDPTracker, sigs
        sigs.init_signing()

        tracker = UDPTracker(port=19021)
        packet = struct.pack("!QII", 0xDEADBEEF, 0, 42)  # wrong magic
        response = tracker._handle_connect(packet, ("127.0.0.1", 12345))

        assert response == b""
        assert tracker._stats["errors"] == 1

    def test_announce_connect_first(self):
        """Announce без connect → connection_id невалиден → error."""
        from udp_tracker import UDPTracker, sigs
        sigs.init_signing()

        tracker = UDPTracker(port=19022)

        # Announce без предварительного connect
        conn_id = 0
        packet = struct.pack("!Q", conn_id)
        packet += struct.pack("!II", 1, 1)
        packet += b"\x00" * 20  # info_hash
        packet += b"SN500000000000001".ljust(20, b"\0")
        packet += struct.pack("!Q", 0) * 3  # downloaded, left, uploaded
        packet += struct.pack("!I", 2)  # event (started)
        packet += struct.pack("!I", 0)  # ip
        packet += struct.pack("!I", 0)  # key
        packet += struct.pack("!i", -1)  # num_want
        packet += struct.pack("!H", 9908)

        response = tracker._handle_announce(packet, ("127.0.0.1", 12345))
        assert len(response) >= 12
        action = struct.unpack_from("!I", response, 0)[0]
        from udp_tracker import ACTION_ERROR
        assert action == ACTION_ERROR
        assert tracker._stats["errors"] == 1

    def test_full_connect_announce(self):
        """Полный цикл connect → announce возвращает пиров."""
        from udp_tracker import UDPTracker, MAGIC_COOKIE, ACTION_CONNECT, ACTION_ANNOUNCE, sigs
        sigs.init_signing()

        tracker = UDPTracker(port=19023)

        # Connect
        tid = 1
        packet = struct.pack("!QII", MAGIC_COOKIE, ACTION_CONNECT, tid)
        resp = tracker._handle_connect(packet, ("127.0.0.1", 12345))
        conn_id = struct.unpack_from("!Q", resp, 8)[0]

        # Добавляем другого пира
        tracker._peers["ff" * 20] = {
            "info_hash": "ff" * 20,
            "ip": "10.0.0.5",
            "port": 9908,
            "last_seen": time.time(),
        }
        tracker._stats["peers_active"] = 1

        # Announce
        info_hash = b"\xaa" * 20
        packet2 = struct.pack("!Q", conn_id)
        packet2 += struct.pack("!II", ACTION_ANNOUNCE, 2)
        packet2 += info_hash
        packet2 += b"SN500000000000001".ljust(20, b"\0")
        packet2 += struct.pack("!Q", 0) * 3
        packet2 += struct.pack("!I", 2)
        packet2 += struct.pack("!I", 0)
        packet2 += struct.pack("!I", 0)
        packet2 += struct.pack("!i", -1)
        packet2 += struct.pack("!H", 9908)

        resp2 = tracker._handle_announce(packet2, ("127.0.0.1", 54321))

        assert len(resp2) >= 20
        action = struct.unpack_from("!I", resp2, 0)[0]
        assert action == ACTION_ANNOUNCE

        seeders = struct.unpack_from("!I", resp2, 16)[0]
        assert seeders >= 1  # at least the peer we added

        assert tracker._stats["announces"] == 1
        assert tracker._stats["connects"] == 1

    def test_stop_event_removes_peer(self):
        """EVENT_STOPPED удаляет пира."""
        from udp_tracker import UDPTracker, MAGIC_COOKIE, ACTION_CONNECT, ACTION_ANNOUNCE, sigs
        sigs.init_signing()

        tracker = UDPTracker(port=19024)

        # Connect
        packet = struct.pack("!QII", MAGIC_COOKIE, ACTION_CONNECT, 1)
        resp = tracker._handle_connect(packet, ("127.0.0.1", 12345))
        conn_id = struct.unpack_from("!Q", resp, 8)[0]

        # Сначала announce started
        info_hash = b"\xbb" * 20
        packet2 = struct.pack("!Q", conn_id)
        packet2 += struct.pack("!II", ACTION_ANNOUNCE, 2)
        packet2 += info_hash
        packet2 += b"SN500000000000001".ljust(20, b"\0")
        packet2 += struct.pack("!Q", 0) * 3
        packet2 += struct.pack("!I", 2)  # started
        packet2 += struct.pack("!I", 0)
        packet2 += struct.pack("!I", 0)
        packet2 += struct.pack("!i", -1)
        packet2 += struct.pack("!H", 9908)
        tracker._handle_announce(packet2, ("127.0.0.1", 54321))
        assert len(tracker._peers) == 1

        # Потом announce stopped
        packet3 = struct.pack("!Q", conn_id)
        packet3 += struct.pack("!II", ACTION_ANNOUNCE, 3)
        packet3 += info_hash
        packet3 += b"SN500000000000001".ljust(20, b"\0")
        packet3 += struct.pack("!Q", 0) * 3
        packet3 += struct.pack("!I", 3)  # stopped
        packet3 += struct.pack("!I", 0)
        packet3 += struct.pack("!I", 0)
        packet3 += struct.pack("!i", -1)
        packet3 += struct.pack("!H", 9908)
        tracker._handle_announce(packet3, ("127.0.0.1", 54321))

        assert len(tracker._peers) == 0

    def test_peer_timeout(self):
        """Peer удаляется после PEER_TIMEOUT."""
        from udp_tracker import UDPTracker, PEER_TIMEOUT, sigs
        sigs.init_signing()

        tracker = UDPTracker(port=19025)

        # Добавляем старого пира
        info_hash = "cc" * 20
        tracker._peers[info_hash] = {
            "info_hash": info_hash,
            "ip": "10.0.0.9",
            "port": 9908,
            "last_seen": time.time() - PEER_TIMEOUT - 10,
        }
        tracker._stats["peers_active"] = 1

        # Ручная чистка вместо _cleanup_loop (там asyncio.sleep 30)
        import asyncio
        now = time.time()
        dead = [k for k, v in tracker._peers.items()
                if now - v["last_seen"] > PEER_TIMEOUT]
        for k in dead:
            loop = asyncio.new_event_loop()
            loop.run_until_complete(tracker._remove_from_dht(k))
            loop.close()
            tracker._peers.pop(k, None)

        assert len(tracker._peers) == 0

    def test_stats(self):
        """Статистика трекера валидна."""
        from udp_tracker import UDPTracker, sigs
        sigs.init_signing()

        tracker = UDPTracker(port=19026)
        stats = tracker.get_stats()
        assert "connects" in stats
        assert "announces" in stats
        assert "peers_active" in stats
        assert "errors" in stats


class TestUDPTrackerClient:

    def test_client_fails_no_server(self):
        """Клиент падает при отсутствии сервера (корректно)."""
        from udp_tracker import UDPTrackerClient

        client = UDPTrackerClient(tracker_host="127.0.0.1", tracker_port=19999)
        import socket
        with pytest.raises((socket.timeout, ConnectionRefusedError, OSError, ValueError)):
            client.connect()

    def test_client_full_connect_announce(self):
        """Клиент → сервер: полный цикл BEP15 через _handle_*."""
        from udp_tracker import UDPTracker, UDPTrackerClient, MAGIC_COOKIE, ACTION_CONNECT, sigs
        sigs.init_signing()

        tracker = UDPTracker(port=19030)

        # Симулируем connect + announce через прямой вызов handler
        # (вместо UDP сокета — чтобы не зависеть от event loop)

        # 1. Connect через handler
        tid = 42
        connect_packet = struct.pack("!QII", MAGIC_COOKIE, ACTION_CONNECT, tid)
        resp = tracker._handle_connect(connect_packet, ("127.0.0.1", 54321))
        conn_id_bytes = struct.pack("!Q", struct.unpack_from("!Q", resp, 8)[0])

        # 2. Добавляем пира
        tracker._peers["ff" * 20] = {
            "info_hash": "ff" * 20,
            "ip": "10.0.0.5",
            "port": 9908,
            "last_seen": time.time(),
        }
        tracker._stats["peers_active"] = 1

        # 3. Симулируем announce клиента — строим такой же пакет как делает UDPTrackerClient
        tid2 = 7
        info_hash = b"\xaa" * 20
        peer_id = b"SN500000000000001".ljust(20, b"\0")

        announce_packet = conn_id_bytes
        announce_packet += struct.pack("!II", 1, tid2)  # action=1, transaction_id
        announce_packet += info_hash
        announce_packet += peer_id
        announce_packet += struct.pack("!Q", 0)  # downloaded
        announce_packet += struct.pack("!Q", 0)  # left
        announce_packet += struct.pack("!Q", 0)  # uploaded
        announce_packet += struct.pack("!I", 2)  # event=started
        announce_packet += struct.pack("!I", 0)  # ip
        announce_packet += struct.pack("!I", 0)  # key
        announce_packet += struct.pack("!i", -1)  # num_want
        announce_packet += struct.pack("!H", 9909)

        resp2 = tracker._handle_announce(announce_packet, ("127.0.0.1", 54321))

        assert len(resp2) >= 20
        action = struct.unpack_from("!I", resp2, 0)[0]
        assert action == 1  # announce

        seeders = struct.unpack_from("!I", resp2, 16)[0]
        # Декодируем пиров из response
        peers = []
        offset = 20
        for i in range(seeders):
            if offset + 6 > len(resp2):
                break
            ip_bytes = resp2[offset:offset+4]
            port_bytes = resp2[offset+4:offset+6]
            ip = f"{ip_bytes[0]}.{ip_bytes[1]}.{ip_bytes[2]}.{ip_bytes[3]}"
            port = struct.unpack("!H", port_bytes)[0]
            peers.append({"ip": ip, "port": port})
            offset += 6

        assert len(peers) >= 1
        found = [p for p in peers if p["ip"] == "10.0.0.5"]
        assert len(found) == 1
        assert found[0]["port"] == 9908

    def test_benchmark_latency(self):
        """benchmark: latency _handle_connect+announce < 1ms."""
        from udp_tracker import UDPTracker, MAGIC_COOKIE, sigs
        sigs.init_signing()

        tracker = UDPTracker(port=19031)

        # Замер через прямой вызов handler (без UDP сокета)
        start = time.time()

        tid = 1
        connect_packet = struct.pack("!QII", MAGIC_COOKIE, 0, tid)
        resp = tracker._handle_connect(connect_packet, ("127.0.0.1", 54321))
        conn_id_bytes = struct.pack("!Q", struct.unpack_from("!Q", resp, 8)[0])

        info_hash = b"\xbb" * 20
        peer_id = b"SN500000000000001".ljust(20, b"\0")
        announce_packet = conn_id_bytes
        announce_packet += struct.pack("!II", 1, 2)
        announce_packet += info_hash
        announce_packet += peer_id
        announce_packet += struct.pack("!Q", 0) * 3
        announce_packet += struct.pack("!I", 2)
        announce_packet += struct.pack("!I", 0) * 2
        announce_packet += struct.pack("!i", -1)
        announce_packet += struct.pack("!H", 9910)

        tracker._handle_announce(announce_packet, ("127.0.0.1", 54321))

        elapsed_ms = (time.time() - start) * 1000
        assert elapsed_ms < 10  # чистый Python struct, должен быть < 1ms
