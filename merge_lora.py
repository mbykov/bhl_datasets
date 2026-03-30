#!/usr/bin/env python3
"""
Скрипт для объединения LoRA адаптера с базовой моделью
"""

import os
import sys
import argparse
import logging
from pathlib import Path
from datetime import datetime

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

def find_latest_checkpoint(lora_path):
    """Находит последний чекпоинт в папке LoRA"""
    checkpoints = list(Path(lora_path).glob("checkpoint-*"))
    if not checkpoints:
        return lora_path

    checkpoints.sort(key=lambda x: int(x.name.split('-')[-1]))
    latest = checkpoints[-1]
    logger.info(f"Найден чекпоинт: {latest}")
    return str(latest)

def merge_lora(base_model, lora_path, output_path, use_last_checkpoint=True):
    """Объединяет LoRA с базовой моделью"""

    # Проверяем существование путей
    if not os.path.exists(base_model):
        logger.error(f"Базовая модель не найдена: {base_model}")
        return False

    if not os.path.exists(lora_path):
        logger.error(f"LoRA адаптер не найден: {lora_path}")
        return False

    # Используем последний чекпоинт если нужно
    if use_last_checkpoint:
        adapter_path = find_latest_checkpoint(lora_path)
    else:
        adapter_path = lora_path

    logger.info(f"Базовая модель: {base_model}")
    logger.info(f"LoRA адаптер: {adapter_path}")
    logger.info(f"Выходная директория: {output_path}")

    # Создаем директорию
    os.makedirs(output_path, exist_ok=True)

    # Импортируем torch и transformers
    try:
        import torch
        from transformers import AutoTokenizer, AutoModelForCausalLM
        from peft import PeftModel
    except ImportError as e:
        logger.error(f"Ошибка импорта: {e}")
        logger.error("Установите: pip install torch transformers peft")
        return False

    try:
        # Загружаем базовую модель
        logger.info("Загрузка базовой модели...")
        model = AutoModelForCausalLM.from_pretrained(
            base_model,
            torch_dtype=torch.bfloat16,
            device_map="cpu",
            trust_remote_code=True
        )

        # Загружаем LoRA адаптер
        logger.info("Загрузка LoRA адаптера...")
        model = PeftModel.from_pretrained(model, adapter_path)

        # Объединяем веса
        logger.info("Объединение весов...")
        merged_model = model.merge_and_unload()

        # Сохраняем объединенную модель
        logger.info(f"Сохранение объединенной модели в {output_path}...")
        merged_model.save_pretrained(output_path)

        # Сохраняем токенизатор
        logger.info("Сохранение токенизатора...")
        tokenizer = AutoTokenizer.from_pretrained(base_model, trust_remote_code=True)
        tokenizer.save_pretrained(output_path)

        # Считаем размер
        total_size = sum(f.stat().st_size for f in Path(output_path).glob("*") if f.is_file())
        logger.info(f"✅ Модель успешно объединена!")
        logger.info(f"   Размер: {total_size / 1024**3:.2f} GB")
        logger.info(f"   Сохранена в: {output_path}")

        return True

    except Exception as e:
        logger.error(f"Ошибка при объединении: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    parser = argparse.ArgumentParser(description="Объединение LoRA адаптера с базовой моделью")
    parser.add_argument("--base-model", type=str, default="../bhl/Models/Qwen2.5-1.5B-Instruct",
                        help="Путь к базовой модели")
    parser.add_argument("--lora", type=str, default="./saves/qwen_merged_lora",
                        help="Путь к LoRA адаптеру")
    parser.add_argument("--output", type=str, default="./models/qwen_merged",
                        help="Директория для объединенной модели")
    parser.add_argument("--no-last-checkpoint", action="store_true",
                        help="Не использовать последний чекпоинт, использовать корневую папку")

    args = parser.parse_args()

    logger.info("="*60)
    logger.info("ОБЪЕДИНЕНИЕ LORA С БАЗОВОЙ МОДЕЛЬЮ")
    logger.info("="*60)
    logger.info(f"Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("="*60)

    success = merge_lora(
        args.base_model,
        args.lora,
        args.output,
        use_last_checkpoint=not args.no_last_checkpoint
    )

    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
