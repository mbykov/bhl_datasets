#!/usr/bin/env python3
"""Тест скорости Ollama"""

import requests
import time

model = "qwen2.5:7b"
url = "http://localhost:11434/api/generate"

# Простой тест
prompt = "Ответь 'да' одним словом"

start = time.time()
response = requests.post(url, json={
    "model": model,
    "prompt": prompt,
    "stream": False,
    "temperature": 0.1,
    "options": {"num_predict": 10}
}, timeout=30)
duration = time.time() - start

print(f"Время ответа: {duration:.2f} сек")
print(f"Ответ: {response.json().get('response', '')[:100]}")
