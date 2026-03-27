#!/usr/bin/env python3
"""
Дообучение на объединенном датасете (команды + LaTeX)
Стабильная версия с правильной передачей GPU
"""

import os
import sys
import subprocess
import glob
import time

# ============================================================================
# НАСТРОЙКИ
# ============================================================================

# Пути (используем абсолютные для надежности)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config_merged.yaml")
DATASET_PATH = os.path.join(BASE_DIR, "result_com_lat", "dataset.jsonl")
OUTPUT_DIR = os.path.join(BASE_DIR, "saves", "qwen_com_lat_lora")

# GPU настройки
GPU_ID = "1"  # RTX 5060 Ti
POWER_LIMIT = 150  # Ватт

# ============================================================================
# ФУНКЦИИ
# ============================================================================

def set_power_limit():
    """Ограничиваем питание RTX"""
    print("🔧 Настройка питания GPU...")
    try:
        result = subprocess.run(
            ["sudo", "nvidia-smi", "-i", GPU_ID, "-pl", str(POWER_LIMIT)],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            print(f"   ✅ Питание RTX 5060 Ti ограничено до {POWER_LIMIT}W")
            return True
        else:
            print(f"   ⚠️ Не удалось ограничить питание: {result.stderr}")
            return False
    except Exception as e:
        print(f"   ⚠️ Ошибка: {e}")
        return False

def check_gpu():
    """Проверяет доступность RTX 5060 Ti"""
    print("\n🔍 Проверка GPU...")

    # Проверяем через nvidia-smi
    result = subprocess.run(
        ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
        capture_output=True,
        text=True,
        timeout=5
    )

    gpus = [g.strip() for g in result.stdout.strip().split('\n') if g.strip()]
    print(f"   Доступные GPU: {gpus}")

    if "RTX 5060 Ti" not in result.stdout:
        print("   ❌ RTX 5060 Ti не обнаружена!")
        return False

    # Проверяем через PyTorch
    try:
        import torch
        # Временно устанавливаем переменную
        os.environ["CUDA_VISIBLE_DEVICES"] = GPU_ID
        if torch.cuda.is_available():
            device_count = torch.cuda.device_count()
            if device_count > 0:
                device_name = torch.cuda.get_device_name(0)
                print(f"   ✅ PyTorch видит: {device_name}")
                if "RTX 5060 Ti" in device_name:
                    return True
    except Exception as e:
        print(f"   ⚠️ PyTorch check: {e}")

    return True  # nvidia-smi уже подтвердил

def check_dataset():
    """Проверяет наличие датасета"""
    if not os.path.exists(DATASET_PATH):
        print(f"   ❌ Датасет не найден: {DATASET_PATH}")
        return False

    # Подсчитываем строки
    with open(DATASET_PATH, 'r', encoding='utf-8') as f:
        line_count = sum(1 for _ in f)
    print(f"   ✅ Датасет: {line_count} примеров")
    return True

def check_config():
    """Проверяет наличие конфига"""
    if not os.path.exists(CONFIG_PATH):
        print(f"   ❌ Конфиг не найден: {CONFIG_PATH}")
        return False
    print(f"   ✅ Конфиг: {CONFIG_PATH}")
    return True

def find_latest_checkpoint():
    """Находит последний чекпоинт"""
    if not os.path.exists(OUTPUT_DIR):
        return None

    checkpoints = glob.glob(os.path.join(OUTPUT_DIR, "checkpoint-*"))
    if not checkpoints:
        return None

    # Сортируем по номеру шага
    checkpoints.sort(key=lambda x: int(x.split('-')[-1]))
    latest = checkpoints[-1]
    step = int(latest.split('-')[-1])
    return latest, step

def print_training_info():
    """Выводит информацию о предстоящем обучении"""
    print("\n" + "="*60)
    print("📊 ПАРАМЕТРЫ ОБУЧЕНИЯ")
    print("="*60)

    # Читаем конфиг
    import yaml
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)

    print(f"   Модель: {config.get('model_name_or_path', 'N/A')}")
    print(f"   Датасет: {config.get('dataset', 'N/A')}")
    print(f"   Batch size: {config.get('per_device_train_batch_size', 'N/A')}")
    print(f"   Gradient accumulation: {config.get('gradient_accumulation_steps', 'N/A')}")
    print(f"   Эффективный batch: {config.get('per_device_train_batch_size', 1) * config.get('gradient_accumulation_steps', 1)}")
    print(f"   Эпохи: {config.get('num_train_epochs', 'N/A')}")
    print(f"   Learning rate: {config.get('learning_rate', 'N/A')}")
    print(f"   Packing: {config.get('packing', 'N/A')}")
    print("="*60)

def run_training():
    """Запускает обучение с правильными переменными окружения"""

    # Проверяем чекпоинты
    checkpoint_info = find_latest_checkpoint()
    if checkpoint_info:
        checkpoint_path, step = checkpoint_info
        print(f"\n💾 Найден чекпоинт: checkpoint-{step}")
        print(f"   Обучение продолжится с шага {step}")

    # Создаем окружение с правильными переменными
    env = os.environ.copy()
    env["CUDA_VISIBLE_DEVICES"] = GPU_ID
    env["PYTORCH_ALLOC_CONF"] = "expandable_segments:True"
    env["CUDA_LAUNCH_BLOCKING"] = "0"  # Отключаем для скорости

    print(f"\n🚀 Запуск обучения...")
    print(f"   GPU: {GPU_ID} (RTX 5060 Ti)")
    print(f"   Конфиг: {CONFIG_PATH}")
    print("="*60 + "\n")

    try:
        # Запускаем обучение
        process = subprocess.Popen(
            ["llamafactory-cli", "train", CONFIG_PATH],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True
        )

        # Выводим лог в реальном времени
        for line in process.stdout:
            print(line, end='')

        # Ждем завершения
        return_code = process.wait()

        if return_code == 0:
            print("\n✅ Обучение успешно завершено!")
            return True
        else:
            print(f"\n❌ Ошибка обучения (код: {return_code})")
            return False

    except KeyboardInterrupt:
        print("\n\n⚠️ Прервано пользователем")
        print(f"💾 Прогресс сохранен в {OUTPUT_DIR}")
        return False
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        return False

def interactive_confirmation():
    """Запрашивает подтверждение"""
    print("\n" + "="*60)
    print("⚠️  ВНИМАНИЕ! Запуск дообучения")
    print("="*60)
    print(f"   GPU: RTX 5060 Ti (лимит питания: {POWER_LIMIT}W)")
    print(f"   Выходная директория: {OUTPUT_DIR}")
    print("="*60)
    print("⚠️  Во время обучения НЕ трогайте кабель Thunderbolt!")
    print("="*60)

    response = input("\nПродолжить? (y/n): ").lower()
    return response == 'y'

# ============================================================================
# MAIN
# ============================================================================

def main():
    print("\n" + "="*60)
    print("🎯 ДООБУЧЕНИЕ НА ОБЪЕДИНЕННОМ ДАТАСЕТЕ")
    print("="*60)
    print(f"Время: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)

    # 1. Настройка питания
    set_power_limit()

    # 2. Проверки
    print("\n🔍 ПРОВЕРКА ПРЕДУСЛОВИЙ")
    print("-"*40)

    checks = [
        ("GPU", check_gpu),
        ("Датасет", check_dataset),
        ("Конфиг", check_config),
    ]

    all_ok = True
    for name, check_func in checks:
        if not check_func():
            all_ok = False
            break

    if not all_ok:
        print("\n❌ Критические ошибки. Запуск невозможен.")
        sys.exit(1)

    # 3. Показываем параметры
    print_training_info()

    # 4. Подтверждение
    if not interactive_confirmation():
        print("❌ Отменено пользователем")
        sys.exit(0)

    # 5. Запуск обучения
    success = run_training()

    # 6. Финальный вывод
    print("\n" + "="*60)
    if success:
        print("🎉 ОБУЧЕНИЕ УСПЕШНО ЗАВЕРШЕНО!")
        print(f"📁 Результат: {OUTPUT_DIR}")
        print("\n📋 Следующие шаги:")
        print("  1. Запустите тест: uv run test_final_model.py")
        print("  2. Объедините LoRA при необходимости")
    else:
        print("❌ ОБУЧЕНИЕ НЕ УДАЛОСЬ")
        print("\n🔧 Диагностика:")
        print("  1. Проверьте логи ошибок выше")
        print("  2. Убедитесь, что RTX 5060 Ti доступна: nvidia-smi")
        print("  3. Попробуйте запустить вручную:")
        print(f"     CUDA_VISIBLE_DEVICES={GPU_ID} llamafactory-cli train {CONFIG_PATH}")
    print("="*60)

    sys.exit(0 if success else 1)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️ Прервано пользователем")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Необработанная ошибка: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
