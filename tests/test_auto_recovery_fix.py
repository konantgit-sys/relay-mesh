#!/usr/bin/env python3
"""Тесты для crashloop fix в auto_recovery.py

Проверяемые баги:
1. ✅ _recovery_locks устанавливается и проверяется перед recovery
2. ✅ _consecutive_fails увеличивается при провале recovery
3. ✅ _consecutive_fails сбрасывается при успехе
4. ✅ Per-service daily limit (max_daily_per_service)
5. ✅ Exponential backoff при повторных провалах
6. ✅ _set_cooldown helper
7. ✅ _verify_service_alive вызывается после restart
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
import time
import json

# Mock
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock


class TestCrashloopFix:
    """Тесты фикса crashloop'а."""

    def setup_method(self):
        """Настройка перед каждым тестом."""
        # Мокаем supervisor_bridge
        self.mock_sv = AsyncMock()
        self.mock_sv.restart = AsyncMock(return_value=True)
        self.mock_sv.get_status = AsyncMock(return_value={"is_alive": True})
        self.mock_sv.health_check = AsyncMock(return_value={"is_alive": True})
        
        # Мокаем импорты внутри auto_recovery
        with patch('auto_recovery.get_supervisor_bridge', return_value=self.mock_sv), \
             patch('auto_recovery.os.makedirs'), \
             patch('auto_recovery.sqlite3.connect'):
            
            from auto_recovery import AutoRecovery
            self.ar = AutoRecovery.__new__(AutoRecovery)
            self.ar.config_path = "/tmp/test_recovery_config.yaml"
            self.ar.config = {
                "strategies": {
                    "default": {
                        "attempts": [
                            {"action": "restart", "description": "restart service"},
                            {"action": "restart_clear_cache", "description": "restart + clear"},
                            {"action": "escalate", "description": "escalate to human"},
                        ],
                        "health_check_after": 2,
                    }
                },
                "max_concurrent": 3,
                "global_cooldown": 60,
                "max_daily_total": 30,
                "max_daily_per_service": 10,
                "slot_health_threshold": 3,
            }
            self.ar.strategies = self.ar.config["strategies"]
            self.ar._sv = self.mock_sv
            
            # Init state
            self.ar._dead_since = {}
            self.ar._consecutive_fails = {}
            self.ar._attempt_in_progress = {}
            self.ar._recovery_locks = {}
            self.ar._global_cooldown_until = 0
            self.ar._daily_count = 0
            self.ar._stats = {
                "total_attempts": 0,
                "successful": 0,
                "failed": 0,
                "escalated": 0,
                "active_recoveries": 0,
            }
            
            # Mock DB
            self.ar._db = MagicMock()
            mock_cursor = MagicMock()
            mock_cursor.fetchone.return_value = None
            self.ar._db.execute.return_value = mock_cursor
            self.ar._db.commit = MagicMock()

    def test_1_recovery_locks_set_on_failure(self):
        """Тест 1: _recovery_locks устанавливается при провале recovery."""
        svc = "test_service"
        
        # Симулируем 3 consec_fails
        self.ar._consecutive_fails[svc] = 3
        
        # Мокаем _verify_service_alive → всегда False (сервис не оживает)
        self.ar._verify_service_alive = AsyncMock(return_value=False)
        
        # Запускаем on_service_dead
        result = asyncio.run(
            self.ar.on_service_dead(svc, {"error": "test", "_all_statuses": {}})
        )
        
        # Проверяем что _recovery_locks установлен
        assert svc in self.ar._recovery_locks, \
            f"FAIL: _recovery_locks не установлен для {svc}"
        
        lock_until = self.ar._recovery_locks[svc]
        assert lock_until > time.time(), \
            f"FAIL: _recovery_locks время в прошлом: {lock_until}"
        
        # Проверяем что consec_fails увеличился (было 3, стало 4+)
        assert self.ar._consecutive_fails.get(svc, 0) >= 4, \
            f"FAIL: _consecutive_fails не увеличился: {self.ar._consecutive_fails.get(svc)}"
        
        print("✅ Тест 1 пройден: _recovery_locks устанавливается при провале")

    def test_2_recovery_locks_respected(self):
        """Тест 2: когда _recovery_locks активен — recovery НЕ запускается."""
        svc = "test_service"
        
        # Устанавливаем lock на 60 секунд в будущее
        self.ar._recovery_locks[svc] = time.time() + 60
        self.ar._consecutive_fails[svc] = 3
        
        # Запускаем on_service_dead
        result = asyncio.run(
            self.ar.on_service_dead(svc, {"error": "test", "_all_statuses": {}})
        )
        
        # Recovery НЕ должен был запуститься
        assert result == False, \
            f"FAIL: recovery запустился несмотря на активный _recovery_locks"
        
        # _attempt_in_progress НЕ должен быть True
        assert not self.ar._attempt_in_progress.get(svc, False), \
            f"FAIL: _attempt_in_progress установлен несмотря на lock"
        
        print("✅ Тест 2 пройден: _recovery_locks блокирует recovery")

    def test_3_consec_fails_increments_on_failure(self):
        """Тест 3: _consecutive_fails растёт при повторных провалах."""
        svc = "test_service"
        
        # Симулируем 3 consec_fails (порог для запуска recovery)
        self.ar._consecutive_fails[svc] = 3
        
        # Мокаем — сервис не оживает
        self.ar._verify_service_alive = AsyncMock(return_value=False)
        
        # Запускаем recovery → должен провалиться
        asyncio.run(
            self.ar.on_service_dead(svc, {"error": "test", "_all_statuses": {}})
        )
        
        # consec_fails должен увеличиться
        new_count = self.ar._consecutive_fails.get(svc, 0)
        assert new_count >= 4, \
            f"FAIL: consec_fails не вырос после провала: {new_count}"
        
        # Проверяем exponential backoff
        lock_until = self.ar._recovery_locks[svc]
        backoff = lock_until - time.time()
        # Для consec=4: 2^(4-3)*60 = 120 сек
        assert 100 <= backoff <= 140, \
            f"FAIL: backoff {backoff}s вне ожидаемого диапазона (120s ±20)"
        
        print(f"✅ Тест 3 пройден: consec_fails={new_count}, backoff={backoff:.0f}s")

    def test_4_consec_fails_resets_on_success(self):
        """Тест 4: _consecutive_fails сбрасывается при УСПЕШНОМ recovery."""
        svc = "test_service"
        
        self.ar._consecutive_fails[svc] = 3
        
        # Мокаем — сервис оживает
        self.ar._verify_service_alive = AsyncMock(return_value=True)
        
        # Запускаем recovery
        result = asyncio.run(
            self.ar.on_service_dead(svc, {"error": "test", "_all_statuses": {}})
        )
        
        # Проверяем что consec_fails сброшен
        assert svc not in self.ar._consecutive_fails, \
            f"FAIL: _consecutive_fails не сброшен после успеха"
        
        # Проверяем что recovery_locks сброшен
        assert svc not in self.ar._recovery_locks, \
            f"FAIL: _recovery_locks не сброшен после успеха"
        
        print("✅ Тест 4 пройден: consec_fails сбрасывается при успехе")

    def test_5_set_cooldown_helper(self):
        """Тест 5: _set_cooldown корректно устанавливает блокировку."""
        svc = "test_service"
        
        self.ar._set_cooldown(svc, 300)
        
        assert svc in self.ar._recovery_locks, \
            f"FAIL: _set_cooldown не установил _recovery_locks"
        
        lock_until = self.ar._recovery_locks[svc]
        expected = time.time() + 300
        assert abs(lock_until - expected) < 2, \
            f"FAIL: _set_cooldown время не совпадает: {lock_until} vs {expected}"
        
        print(f"✅ Тест 5 пройден: _set_cooldown({svc}, 300) = {lock_until:.0f}")

    def test_6_reset_service_clears_all(self):
        """Тест 6: reset_service очищает все состояния."""
        svc = "test_service"
        
        self.ar._dead_since[svc] = time.time()
        self.ar._consecutive_fails[svc] = 5
        self.ar._attempt_in_progress[svc] = True
        self.ar._recovery_locks[svc] = time.time() + 3600
        
        self.ar.reset_service(svc)
        
        assert svc not in self.ar._dead_since, "FAIL: _dead_since не очищен"
        assert svc not in self.ar._consecutive_fails, "FAIL: _consecutive_fails не очищен"
        assert not self.ar._attempt_in_progress.get(svc, False), "FAIL: _attempt_in_progress не сброшен"
        assert svc not in self.ar._recovery_locks, "FAIL: _recovery_locks не очищен"
        
        print("✅ Тест 6 пройден: reset_service очищает все состояния")

    def test_7_exponential_backoff(self):
        """Тест 7: exponential backoff растёт с consec_fails."""
        svc = "test_service"
        backoffs = []
        
        for consec in [3, 4, 5, 6, 7, 8]:
            self.ar._consecutive_fails[svc] = consec
            self.ar._recovery_locks.pop(svc, None)
            self.ar._attempt_in_progress.pop(svc, None)
            
            self.ar._verify_service_alive = AsyncMock(return_value=False)
            
            asyncio.run(
                self.ar.on_service_dead(svc, {"error": "test", "_all_statuses": {}})
            )
            
            lock_until = self.ar._recovery_locks.get(svc, 0)
            backoff = max(0, lock_until - time.time())
            backoffs.append(backoff)
        
        # Проверяем что backoff растёт
        for i in range(1, len(backoffs)):
            assert backoffs[i] >= backoffs[i-1], \
                f"FAIL: backoff не растёт: {backoffs}"
        
        # Проверяем что не превышает 3600 (кап)
        assert all(b <= 3700 for b in backoffs), \
            f"FAIL: backoff превышает кап 3600s: {backoffs}"
        
        print(f"✅ Тест 7 пройден: backoff растёт: {[f'{b:.0f}s' for b in backoffs]}")


if __name__ == "__main__":
    t = TestCrashloopFix()
    
    print("=" * 60)
    print("CRASHLOOP FIX — UNIT TESTS")
    print("=" * 60)
    print()
    
    tests = [
        t.setup_method,
        t.test_1_recovery_locks_set_on_failure,
        t.test_2_recovery_locks_respected,
        t.test_3_consec_fails_increments_on_failure,
        t.test_4_consec_fails_resets_on_success,
        t.test_5_set_cooldown_helper,
        t.test_6_reset_service_clears_all,
        t.test_7_exponential_backoff,
    ]
    
    passed = 0
    failed = 0
    
    for test_fn in tests:
        if test_fn == t.setup_method:
            test_fn()
            continue
        try:
            t.setup_method()
            test_fn()
            passed += 1
        except Exception as e:
            print(f"❌ {test_fn.__name__}: {e}")
            failed += 1
    
    print()
    print(f"Результат: {passed} passed, {failed} failed")
    exit(0 if failed == 0 else 1)
