#!/usr/bin/env python3
"""
Слияние датасетов Alpaca command + math + garbage.
"""

import json
import os
import random
from itertools import islice, cycle

random.seed(42)  # Для воспроизводимости

# Пути
BASE_DIR = "/home/michael/LLM/datasets_bhl"
CMD_TRAIN = os.path.join(BASE_DIR, "generate_command/result/train.jsonl")
CMD_TEST = os.path.join(BASE_DIR, "generate_command/result/test.jsonl")
MATH_TRAIN = os.path.join(BASE_DIR, "generate_latex_text/result/train.jsonl")
MATH_TEST = os.path.join(BASE_DIR, "generate_latex_text/result/test.jsonl")
GARBAGE_CONFIG = os.path.join(BASE_DIR, "generate_command/config/garbage.json")
OUTPUT_DIR = os.path.join(BASE_DIR, "result")

def read_jsonl(path):
    """Читает JSONL файл и возвращает список словарей."""
    data = []
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                data.append(json.loads(line))
    return data

def load_garbage_phrases(path):
    """Загружает фразы помойки из JSON config."""
    with open(path, 'r', encoding='utf-8') as f:
        config = json.load(f)
    return config.get('rus', [])

def generate_garbage_entries(phrases, count_cmd_math):
    """
    Генерирует garbage-записи {"input": "[GRB] <фраза>", "output": "none"}.
    Количество garbage = сумме command + math (чтобы было 1:1:1).
    Если фраз не хватает, комбинирует их.
    """
    entries = []
    if not phrases:
        return entries
    
    count = count_cmd_math  # garbage = cmd + math
    
    # Если фраз меньше чем нужно, генерируем комбинации
    if len(phrases) < count:
        # Комбинируем по две фразы
        extended_phrases = []
        for i in range(count):
            p1 = phrases[i % len(phrases)]
            p2 = phrases[(i + 1) % len(phrases)]
            # Чередование: одна фраза, две фразы, снова одна
            if i % 3 == 0:
                extended_phrases.append(p1)
            elif i % 3 == 1:
                extended_phrases.append(p2)
            else:
                extended_phrases.append(f"{p1} {p2}")
        phrases_to_use = extended_phrases[:count]
    else:
        phrases_to_use = phrases[:count]
    
    for phrase in phrases_to_use:
        entries.append({
            "input": f"[GRB] {phrase}",
            "output": "none"
        })
    
    return entries

def transform_cmd_entries(entries, prefix="[CMD]"):
    """Добавляет префикс к полю input в command записях."""
    transformed = []
    for entry in entries:
        transformed.append({
            "input": f"{prefix} {entry['input']}",
            "output": entry['output']
        })
    return transformed

def transform_math_entries(entries, prefix="[MATH]"):
    """Добавляет префикс к полю input в math записях."""
    transformed = []
    for entry in entries:
        transformed.append({
            "input": f"{prefix} {entry['input']}",
            "output": entry['output']
        })
    return transformed

def write_jsonl(path, entries):
    """Записывает список словарей в JSONL файл."""
    with open(path, 'w', encoding='utf-8') as f:
        for entry in entries:
            f.write(json.dumps(entry, ensure_ascii=False) + '\n')

def create_dataset_info(train_count, test_count, output_dir):
    """Создает файл dataset_info.json в формате для LLaMA-Factory."""
    info = {
        "bhl_ds": {
            "file_name": "train.jsonl",
            "columns": {
                "query": "input",
                "response": "output"
            }
        },
        "statistics": {
            "train_samples": train_count,
            "test_samples": test_count
        },
        "special_tokens": ["[CMD]", "[MATH]", "[GRB]"]
    }
    info_path = os.path.join(output_dir, "dataset_info.json")
    with open(info_path, 'w', encoding='utf-8') as f:
        json.dump(info, f, ensure_ascii=False, indent=2)
    print(f"Создан файл: {info_path}")

def main():
    # Создаем выходную директорию
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # Читаем исходные данные
    print("Чтение исходных файлов...")
    cmd_train = read_jsonl(CMD_TRAIN)
    cmd_test = read_jsonl(CMD_TEST)
    math_train = read_jsonl(MATH_TRAIN)
    math_test = read_jsonl(MATH_TEST)
    garbage_phrases = load_garbage_phrases(GARBAGE_CONFIG)
    
    print(f"Command train: {len(cmd_train)}")
    print(f"Command test: {len(cmd_test)}")
    print(f"Math train: {len(math_train)}")
    print(f"Math test: {len(math_test)}")
    print(f"Garbage phrases available: {len(garbage_phrases)}")
    
    # Вычисляем нужное количество garbage (равно сумме command + math)
    train_cmd_math = len(cmd_train) + len(math_train)
    test_cmd_math = len(cmd_test) + len(math_test)
    
    print(f"\nНужно garbage для train (равно cmd+math): {train_cmd_math}")
    print(f"\nНужно garbage для test (равно cmd+math): {test_cmd_math}")
    
    # Трансформируем command и math записи
    cmd_train_t = transform_cmd_entries(cmd_train)
    math_train_t = transform_math_entries(math_train)
    cmd_test_t = transform_cmd_entries(cmd_test)
    math_test_t = transform_math_entries(math_test)
    
    # Генерируем garbage записи (равно сумме command + math)
    garbage_train = generate_garbage_entries(garbage_phrases, train_cmd_math)
    garbage_test = generate_garbage_entries(garbage_phrases, test_cmd_math)
    
    print(f"Сгенерировано garbage train: {len(garbage_train)}")
    print(f"Сгенерировано garbage test: {len(garbage_test)}")
    
    # Объединяем и перемешиваем все записи
    train_merged = cmd_train_t + math_train_t + garbage_train
    test_merged = cmd_test_t + math_test_t + garbage_test
    
    random.shuffle(train_merged)
    random.shuffle(test_merged)
    
    print(f"\nИтого train: {len(train_merged)}")
    print(f"Итого test: {len(test_merged)}")
    
    # Записываем результаты
    train_out = os.path.join(OUTPUT_DIR, "train.jsonl")
    test_out = os.path.join(OUTPUT_DIR, "test.jsonl")
    
    write_jsonl(train_out, train_merged)
    write_jsonl(test_out, test_merged)
    
    print(f"Записано: {train_out}")
    print(f"Записано: {test_out}")
    
    # Создаем dataset_info
    create_dataset_info(len(train_merged), len(test_merged), OUTPUT_DIR)
    
    print("\nГотово!")

if __name__ == "__main__":
    main()