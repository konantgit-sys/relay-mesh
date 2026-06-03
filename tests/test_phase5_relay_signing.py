#!/usr/bin/env python3
"""
Phase 2 — Relay Signing: unit-тесты.

Запуск: cd /home/agent/data/sites/relay-mesh && pytest tests/test_phase5_relay_signing.py -v
"""

import pytest
import json
import urllib.request
import urllib.parse

RELAY_SIGNING_URL = "http://127.0.0.1:9125"
IDENTITY_API_URL = "http://127.0.0.1:9940"
TEST_RELAY_URL = "wss://test-relay.snin.io"
TEST_PUBKEY = "1111222233334444555566667777888899990000aaaabbbbccccddddeeeeffff"


def _post(url, data):
    """POST JSON, вернуть dict."""
    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode(),
        headers={"Content-Type": "application/json"}
    )
    return json.loads(urllib.request.urlopen(req).read())


def _get(url):
    """GET, вернуть dict."""
    return json.loads(urllib.request.urlopen(url).read())


class TestRelaySigning:

    def test_health(self):
        """Relay Signing сервис жив."""
        resp = _get(f"{RELAY_SIGNING_URL}/health")
        assert resp["status"] == "ok"
        assert resp["service"] == "Relay Signing (L5)"

    def test_sign_relay(self):
        """POST /verify_relay подписывает релей."""
        resp = _post(f"{RELAY_SIGNING_URL}/verify_relay", {
            "relay_url": TEST_RELAY_URL,
            "pubkey": TEST_PUBKEY,
            "mesh_id": "snin-main-1"
        })
        assert resp["status"] == "signed"
        assert "signature" in resp
        assert len(resp["signature"]) == 128  # Ed25519: 64 bytes = 128 hex
        assert resp["relay_url"] == TEST_RELAY_URL

    def test_verify_signed_relay(self):
        """GET /verify верифицирует подписанный релей."""
        resp = _post(f"{RELAY_SIGNING_URL}/verify_relay", {
            "relay_url": TEST_RELAY_URL,
            "pubkey": TEST_PUBKEY,
            "mesh_id": "snin-main-1"
        })
        sig = resp["signature"]
        ts = resp["timestamp"]
        vk = resp["verifying_key"]

        params = urllib.parse.urlencode({
            "relay_url": TEST_RELAY_URL,
            "signature": sig,
            "timestamp": ts,
            "pubkey": TEST_PUBKEY,
        })
        verify = _get(f"{RELAY_SIGNING_URL}/verify?{params}")
        assert verify["verified"] == True
        assert verify["tier"] == 1

    def test_reject_fake_signature(self):
        """Фейковая подпись отклоняется."""
        params = urllib.parse.urlencode({
            "relay_url": TEST_RELAY_URL,
            "signature": "00" * 64,  # фейковая подпись
            "timestamp": 1000,
            "pubkey": TEST_PUBKEY,
        })
        verify = _get(f"{RELAY_SIGNING_URL}/verify?{params}")
        assert verify["verified"] == False
        assert verify["tier"] == 2

    def test_required_params(self):
        """Без relay_url — 400."""
        with pytest.raises(urllib.error.HTTPError) as exc:
            _get(f"{RELAY_SIGNING_URL}/verify?signature=abc&timestamp=1")
        assert exc.value.code == 400

    def test_invalid_relay_url(self):
        """Невалидный URL релея — 400."""
        with pytest.raises(urllib.error.HTTPError) as exc:
            _post(f"{RELAY_SIGNING_URL}/verify_relay", {
                "relay_url": "not-a-ws-url",
                "pubkey": TEST_PUBKEY,
            })
        assert exc.value.code == 400

    def test_invalid_pubkey(self):
        """Невалидный pubkey — 400."""
        with pytest.raises(urllib.error.HTTPError) as exc:
            _post(f"{RELAY_SIGNING_URL}/verify_relay", {
                "relay_url": "wss://valid.url",
                "pubkey": "short",
            })
        assert exc.value.code == 400

    def test_signed_relays_list(self):
        """GET /signed_relays возвращает список подписанных."""
        resp = _get(f"{RELAY_SIGNING_URL}/signed_relays")
        assert "count" in resp
        assert "relays" in resp
        assert resp["count"] > 0
        # Проверяем структуру записи
        for url, info in resp["relays"].items():
            assert "relay_url" in info
            assert "signature" in info
            assert "timestamp" in info


class TestIdentityProxy:

    def test_identity_verify_proxy(self):
        """Identity API /verify_relay проксирует на relay_signing."""
        # Подписываем новый релей
        resp = _post(f"{RELAY_SIGNING_URL}/verify_relay", {
            "relay_url": "wss://identity-proxy-test.snin.io",
            "pubkey": "2222" * 16,
            "mesh_id": "snin-main-1"
        })
        sig, ts = resp["signature"], resp["timestamp"]

        # Верифицируем через identity API
        params = urllib.parse.urlencode({
            "relay_url": "wss://identity-proxy-test.snin.io",
            "signature": sig,
            "timestamp": ts,
            "pubkey": "2222" * 16,
        })
        verify = _get(f"{IDENTITY_API_URL}/verify_relay?{params}")
        assert verify["verified"] == True
        assert verify["tier"] == 1

    def test_identity_reject_fake(self):
        """Identity API отклоняет фейковую подпись."""
        params = urllib.parse.urlencode({
            "relay_url": "wss://any.url",
            "signature": "ff" * 64,
            "timestamp": 0,
            "pubkey": "3333" * 16,
        })
        verify = _get(f"{IDENTITY_API_URL}/verify_relay?{params}")
        assert verify["verified"] == False
        assert verify["tier"] == 2

    def test_identity_missing_params(self):
        """Identity API без relay_url — 400."""
        with pytest.raises(urllib.error.HTTPError) as exc:
            _get(f"{IDENTITY_API_URL}/verify_relay?signature=abc&timestamp=1")
        assert exc.value.code == 400
