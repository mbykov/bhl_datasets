#!/usr/bin/env python3
"""
Запуск дообучения с мониторингом GPU и защитой от OOM
"""

import os
import subprocess
import sys
import time
import threading
from pathlib import Path

# Настройки GPU для RTX 5060 Ti
os.environ["CUDA_VISIBLE_DEVICES"] = "0"
os.environ["PYTORCH_ALLOC_CONF"] = "expandable_segments:True"

# Конфигурация защиты
MAX_GPU_MEMORY_PERCENT = 85  # Макс. использование VRAM перед предупреждением
CHECK_INTERVAL = 5  # Секунд между проверками


def get_gpu_memory_usage():
    """Получает использование VRAM в процентах и ГБ"""
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.total,memory.used", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, check=True
        )
        lines = result.stdout.strip().split('\n')
        total, used = 0, 0
        for line in lines:
            parts = line.split(',')
            if len(parts) >= 2:
                total += float(parts[0].strip())
                used += float(parts[1].strip())
        if total > 0:
            percent = (used / total) * 100
            return percent, used / 1024, total / 1024
        return 0, 0, 0
    except Exception as e:
        print(f"⚠️ Не удалось получить GPU статистику: {e}")
        return None, None, None


def monitor_gpu(stop_event):
    """Фоновый мониторинг GPU памяти"""
    print("\n🔍 Мониторинг GPU (нажмите Ctrl+C для остановки):")
    print("-" * 60)
    
    while not stop_event.is_set():
        percent, used, total = get_gpu_memory_usage()
        if percent is not None:
            status = "✅" if percent < MAX_GPU_MEMORY_PERCENT else "🚨"
            print(f"{status} VRAM: {used:.1f} / {total:.1f} GB ({percent:.1f}%)", end='\r')
            if percent > 90:
                print(f"\n⚠️ ВНИМАНИЕ: VRAM > 90%! Риск OOM!")
        time.sleep(CHECK_INTERVAL)
    print("\n" + "-" * 60)


def check_gpu_safety():
    """Проверка доступности GPU перед запуском"""
    print("🔍 Проверка GPU перед запуском...")
    percent, used, total = get_gpu_memory_usage()
    
    if percent is None:
        print("⚠️ Не удалось проверить GPU. Продолжаем с осторожностью...")
        return True
    
    print(f"📊 GPU статус: {used:.1f} / {total:.1f} GB ({percent:.1f}%)")
    
    if percent > 70:
        print(f"⚠️ ВНИМАНИЕ: GPU уже загружен на {percent:.1f}%. Закройте другие приложения!")
        response = input("Продолжить? (y/n): ").strip().lower()
        if response != 'y':
            return False
    
    return True


def adjust_config_for_gpu(config_path):
    """
    Автоматическая корректировка config.yaml под доступную VRAM
    Возвращает путь к скорректированному файлу
    """
    percent, used, total = get_gpu_memory_usage()
    if percent is None:
        print("⚠️ Не удалось определить VRAM. Используем оригинальный конфиг.")
        return config_path
    
    # Эвристика для настройки batch_size под VRAM
    new_config_path = config_path.replace('.yaml', '_auto.yaml')
    
    # Читаем оригинальный конфиг
    with open(config_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # Корректируем параметры на основе VRAM
    new_lines = []
    for line in lines:
        # Для 6-8GB VRAM
        if total <= 8 and line.startswith('per_device_train_batch_size:'):
            old_val = int(line.split(':')[1].strip())
            new_val = max(1, old_val // 2)  # Уменьшаем в 2 раза
            new_lines.append(f"per_device_train_batch_size: {new_val}  # Auto-adjusted from {old_val} for {total:.0f}GB VRAM\n")
            print(f"🔧 Уменьшил batch_size: {old_val} → {new_val}")
        elif total <= 6 and line.startswith('gradient_accumulation_steps:'):
            # Можно оставить, но предупредить
            new_lines.append(line)
            print(f"⚠️ Для 6GB VRAM рекомендуем уменьшить per_device_train_batch_size до 1-2")
        else:
            new_lines.append(line)
    
    # Сохраняем скорректированный конфиг
    with open(new_config_path, 'w', encoding='utf-8') as f:
        f.writelines(new_lines)
    
    print(f"✅ Скорректированный конфиг: {new_config_path}")
    return new_config_path


def run_train():
    config_path = "config_command.yaml"
    dataset_info_path = "result/command/dataset_info.json"
    
    if not os.path.exists(config_path):
        print(f"❌ Error: {config_path} not found!")
        return False
    
    if not os.path.exists(dataset_info_path):
        print(f"❌ Error: {dataset_info_path} not found!")
        return False

    # Проверка GPU
    if not check_gpu_safety():
        print("❌ Запуск отменён пользователем.")
        return False

    # Авто-корректировка конфига
    final_config = adjust_config_for_gpu(config_path)

    # Запуск мониторинга GPU в фоне
    stop_monitor = threading.Event()
    monitor_thread = threading.Thread(target=monitor_gpu, args=(stop_monitor,), daemon=True)
    monitor_thread.start()

    command = ["llamafactory-cli", "train", final_config]
    print("\n" + "=" * 60)
    print("🚀 Запуск Fine-tuning на NVIDIA GeForce RTX 5060 Ti...")
    print(f"📁 Dataset info: {dataset_info_path}")
    print(f"📁 Dataset dir: result/command (указано в config)")
    print("=" * 60)
    
    try:
        result = subprocess.run(command, check=True)
        stop_monitor.set()  # Остановить мониторинг
        print("\n✅ Training completed successfully!")
        return True
    except subprocess.CalledProcessError as e:
        stop_monitor.set()
        print(f"\n❌ Error during training: {e}")
        return False
    except KeyboardInterrupt:
        stop_monitor.set()
        print("\n⚠️ Training interrupted by user.")
        return False


if __name__ == "__main__":
    os.makedirs("./saves", exist_ok=True)
    
    # Дополнительная проверка: есть ли nvidia-smi
    try:
        subprocess.run(["nvidia-smi"], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("❌ NVIDIA GPU не найден или драйвер не установлен!")
        sys.exit(1)
    
    success = run_train()
    sys.exit(0 if success else 1)