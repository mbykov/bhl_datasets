#!/usr/bin/env python3
"""Тест запуска llamafactory"""

import subprocess
import sys

config_path = "config_com_lat_temp.yaml"

print("Тест запуска llamafactory...")
print(f"Конфиг: {config_path}")

try:
    result = subprocess.run(
        ["/home/michael/LLM/bhl_datasets/.venv/bin/llamafactory-cli", "train", config_path],
        capture_output=True,
        text=True,
        timeout=30
    )

    print(f"Return code: {result.returncode}")
    print("STDOUT:")
    print(result.stdout)
    print("STDERR:")
    print(result.stderr)

except subprocess.TimeoutExpired:
    print("❌ Таймаут - команда зависла")
except Exception as e:
    print(f"❌ Ошибка: {e}")
