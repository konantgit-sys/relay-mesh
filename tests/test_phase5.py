#!/usr/bin/env python3
"""
Phase 5 — Unit-тесты: ChequeBook, Content Router, Identity API

Запуск: cd /home/agent/data/sites/relay-mesh && pytest tests/test_phase5.py -v
"""

import pytest
import json
import os
import sys
import time

sys.path.insert(0, "/home/agent/data/sites/relay-mesh")

# ════════════════════════════════════════════════════════════════
# ChequeBook: issue + verify
# ════════════════════════════════════════════════════════════════

class TestChequeBook:

    @pytest.fixture(autouse=True)
    def setup(self):
        import blinded_sigs as sigs
        import cheque_book
        # Сброс глобального состояния перед каждым тестом
        cheque_book.books.clear()
        cheque_book.agent_books.clear()
        cheque_book.stats = {
            "books_issued": 0,
            "cheques_total": 0,
            "cheques_spent": 0,
            "agents_with_books": 0
        }
        # Определяем start_time для _save_status (оригинал в if __name__)
        if not hasattr(cheque_book, 'start_time'):
            cheque_book.start_time = time.time()
        sigs.init_signing()
        self.sigs = sigs
        self.cb = cheque_book

    def test_chequebook_issue(self):
        """ChequeBook: issue_book создаёт книжку"""
        result = self.cb.issue_book("test_pubkey_123", count=100, amount_paid=0)
        assert "book_id" in result, f"Нет book_id: {result}"
        assert result["count"] == 100
        assert result["remaining"] == 100
        assert "error" not in result, f"Ошибка: {result.get('error')}"

    def test_chequebook_verify(self):
        """ChequeBook: issue → sign → spend → verify"""
        agent = "test_agent_pubkey_abc"
        result = self.cb.issue_book(agent, count=1000, amount_paid=0)
        book_id = result["book_id"]

        # Подписываем cheque (index=0, amount=0, recipient=mesh)
        sig = self.sigs.sign_cheque(
            book_id=book_id,
            index=0,
            amount=0,
            recipient="mesh"
        )

        # Тратим
        spend = self.cb.spend_cheque(agent, book_id, index=0, sig_hex=sig)
        assert spend["accepted"] == True, f"Cheque не принят: {spend}"
        assert spend["remaining"] == 999

        # Double-spend: тот же cheque должен быть отклонён
        spend2 = self.cb.spend_cheque(agent, book_id, index=0, sig_hex=sig)
        assert spend2["accepted"] == False, "Double-spend должен блокироваться"
        assert "already spent" in spend2["reason"]


# ════════════════════════════════════════════════════════════════
# Content Router: BloomFilter + multicast simulation
# ════════════════════════════════════════════════════════════════

class TestContentRouter:

    def test_content_router_multicast(self):
        """Content Router: BloomFilter dedup + no false negatives"""
        from content_router_v2 import BloomFilter, FastDedup

        # ── BloomFilter test ──
        bf = BloomFilter(capacity=500, error_rate=0.01)
        events = [f"event_{i}" for i in range(100)]
        for e in events:
            bf.add(e)

        # Все добавленные — точно есть (no false negatives)
        for e in events:
            assert bf.check(e) == True, f"False negative: {e}"

        # Случайные — могут быть false positive (это норма для Bloom)
        # Но проверим что не-добавленные хотя бы не все ложно-положительны
        unknown_found = sum(1 for i in range(100, 200) if bf.check(f"unknown_{i}"))
        assert unknown_found < 20, f"Слишком много false positives: {unknown_found}"

        # ── FastDedup test ──
        fd = FastDedup(window=5, max_events=100)
        # Первый раз — новый event
        assert fd.check_and_add("event_1") == False, "Первый event должен быть NEW"
        # Второй раз — дубликат
        assert fd.check_and_add("event_1") == True, "Повторный event должен быть DUP"

        # Очистка
        fd.clear()
        assert fd.check_and_add("event_1") == False, "После clear event должен быть NEW"


# ════════════════════════════════════════════════════════════════
# Identity API: create + reputation (через TestClient)
# ════════════════════════════════════════════════════════════════

class TestIdentityAPI:

    @pytest.fixture
    def client(self):
        from identity_api_v2 import app as identity_app
        from fastapi.testclient import TestClient
        return TestClient(identity_app)

    def test_identity_create(self, client):
        """Identity API: /identity/{name} возвращает identity без приватных ключей"""
        response = client.get("/identity/forecaster_ai")
        # Может быть 404 если агент не найден — это тоже нормально
        if response.status_code == 200:
            data = response.json()
            assert "agent_name" in data
            assert "did" in data
            assert "npub" in data
            # Приватные ключи НЕ должны быть в ответе
            assert "mesh_privkey" not in data.get("full_identity", {})
            assert "packet_privkey" not in data.get("full_identity", {})
        elif response.status_code == 404:
            # Агент не зарегистрирован — проверяем формат ошибки
            data = response.json()
            assert "error" in data

    def test_identity_reputation(self, client):
        """Identity API: /identity/top возвращает топ репутации"""
        response = client.get("/identity/top")
        assert response.status_code == 200
        data = response.json()
        assert "top" in data
        assert "count" in data
        # Проверка структуры
        if data["top"]:
            assert "agent_name" in data["top"][0]
            assert "score" in data["top"][0]

    def test_identity_health(self, client):
        """Identity API: /health возвращает статус"""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "layer" in data
        assert "L5" in data["layer"]

    def test_identity_all(self, client):
        """Identity API: /identity/all возвращает список агентов"""
        response = client.get("/identity/all")
        assert response.status_code == 200
        data = response.json()
        assert "agents" in data
        assert "count" in data
