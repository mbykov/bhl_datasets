#!/usr/bin/env python3
import requests
import json

print("Тест 1: Простой GET запрос к /api/tags")
try:
    r = requests.get("http://localhost:11434/api/tags", timeout=5)
    print(f"✅ Статус: {r.status_code}")
    print(f"Ответ: {r.json()}")
except Exception as e:
    print(f"❌ Ошибка: {e}")

print("\nТест 2: POST запрос к /api/generate")
try:
    payload = {
        "model": "qwen2.5:7b",
        "prompt": "Say 'hello'",
        "stream": False,
        "options": {
            "num_predict": 10
        }
    }

    print(f"Отправляем запрос: {json.dumps(payload, indent=2)}")

    r = requests.post(
        "http://localhost:11434/api/generate",
        json=payload,
        timeout=30,
        headers={"Content-Type": "application/json"}
    )

    print(f"✅ Статус: {r.status_code}")
    result = r.json()
    print(f"Ответ: {result.get('response', 'NO RESPONSE')}")

except requests.exceptions.Timeout:
    print("❌ Таймаут 30 секунд - запрос завис")
except Exception as e:
    print(f"❌ Ошибка: {e}")

print("\nТест 3: Проверка с stream=True")
try:
    r = requests.post(
        "http://localhost:11434/api/generate",
        json={
            "model": "qwen2.5:7b",
            "prompt": "Hi",
            "stream": True
        },
        timeout=30,
        stream=True
    )

    print("✅ Получаем потоковый ответ:")
    for line in r.iter_lines():
        if line:
            print(f"  {line[:100]}")
            break  # Только первый chunk

except Exception as e:
    print(f"❌ Ошибка: {e}")
