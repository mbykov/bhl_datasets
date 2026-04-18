#!/usr/bin/env python3
"""
Тестирование Python-инференса (LoRA) на тестовом датасете command/test.jsonl
"""

import json
import torch
import sys
import time
from pathlib import Path
from collections import defaultdict
from transformers import AutoTokenizer, AutoModelForCausalLM
from peft import PeftModel

BASE_MODEL = "../bhl/Models/Qwen2.5-0.5B-Instruct/orig"
LORA_PATH = "./saves/qwen_command_lora/checkpoint-969"  # Или latest checkpoint
TEST_FILE = Path("result/command/test.jsonl")

# Системный промпт
SYSTEM_PROMPT = """Ты — помощник для управления текстом. Определяй, есть ли в сообщении пользователя соответствие одной из команд: "newText", "saveNote", "clearText", "addParagraph", "undoPhrase", "undoParagraph", "undoCommand", "killParagraph", "killPhrase", "recordStop", "recordStart". Если есть — верни имя команды. Если нет — верни пустую строку. Отвечай ТОЛЬКО одним словом: именем команды ИЛИ пустой строкой. Никаких объяснений."""

def load_model():
    """Загружает модель с LoRA адаптером."""
    print(f"📦 Загрузка базовой модели: {BASE_MODEL}")
    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL, trust_remote_code=True)
    model = AutoModelForCausalLM.from_pretrained(
        BASE_MODEL,
        torch_dtype=torch.bfloat16,
        device_map="auto",
        trust_remote_code=True
    )

    print(f"📦 Загрузка LoRA весов: {LORA_PATH}")
    model = PeftModel.from_pretrained(model, LORA_PATH)
    model = model.merge_and_unload()

    print("✅ Модель загружена!")
    return model, tokenizer

def run_query(model, tokenizer, query: str, max_length: int = 64) -> str:
    """Выполняет запрос к модели и возвращает ответ."""
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": query}
    ]

    # Формируем промпт в формате Qwen
    prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)

    inputs = tokenizer(prompt, return_tensors="pt").to(model.device)

    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=max_length,
            temperature=0.1,
            top_p=0.9,
            do_sample=True,
            pad_token_id=tokenizer.eos_token_id
        )

    # Извлекаем сгенерированный текст
    response = tokenizer.decode(outputs[0][inputs['input_ids'].shape[1]:], skip_special_tokens=True).strip()
    return response

def load_test_data(file_path: Path, clean_only: bool = False):
    """Загружает тестовые данные из JSONL файла."""
    tests = []
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                data = json.loads(line)
                # Фильтрация: чистые фразы (только rus, без eng)
                if clean_only:
                    if "rus" in data and "eng" not in data:
                        tests.append(data)
                else:
                    tests.append(data)
    return tests

def evaluate_results(model, tokenizer, tests: list, verbose: bool = False, clean_only: bool = False) -> dict:
    """Оценивает результаты и возвращает статистику."""
    total = len(tests)
    correct = 0
    wrong = 0

    # Статистика по командам
    by_command = defaultdict(lambda: {"total": 0, "correct": 0, "wrong": 0})

    # Чистые vs шумные
    clean_total = 0
    clean_correct = 0
    noisy_total = 0
    noisy_correct = 0

    mistakes = []

    for i, test in enumerate(tests):
        expected = test.get("name", "").strip()
        query = test.get("rus") or test.get("eng") or ""

        # Определяем, чистая это фраза или с шумом
        is_clean = "rus" in test and "eng" not in test

        actual = run_query(model, tokenizer, query)

        # Нормализация
        actual_normalized = actual.strip().lower()
        expected_normalized = expected.strip().lower()

        # Проверка
        is_correct = False
        if expected == "none":
            if actual_normalized in ["", "none", "noneет..."]:
                is_correct = True
        else:
            if actual_normalized == expected_normalized:
                is_correct = True

        if is_correct:
            correct += 1
            if is_clean:
                clean_correct += 1
            else:
                noisy_correct += 1
        else:
            wrong += 1

        # Статистика по командам
        by_command[expected]["total"] += 1
        if is_correct:
            by_command[expected]["correct"] += 1
        else:
            by_command[expected]["wrong"] += 1

        if is_clean:
            clean_total += 1
        else:
            noisy_total += 1

        if verbose and not is_correct:
            mistakes.append({
                "query": query,
                "expected": expected,
                "actual": actual,
                "index": i,
                "is_clean": is_clean
            })

    return {
        "total": total,
        "clean_total": clean_total,
        "noisy_total": noisy_total,
        "correct": correct,
        "wrong": wrong,
        "accuracy": correct / total * 100 if total > 0 else 0,
        "clean_accuracy": clean_correct / clean_total * 100 if clean_total > 0 else 0,
        "noisy_accuracy": noisy_correct / noisy_total * 100 if noisy_total > 0 else 0,
        "by_command": dict(by_command),
        "mistakes": mistakes
    }

def print_results(results: dict, verbose: bool = False):
    """Выводит результаты в виде таблицы."""
    print("\n" + "="*70)
    print("РЕЗУЛЬТАТЫ ТЕСТИРОВАНИЯ PYTHON-INFERENCE (LoRA)")
    print("="*70)
    print(f"Всего тестов: {results['total']}")
    print(f"  └─ Чистых фраз: {results['clean_total']}")
    print(f"  └─ Шумных фраз: {results['noisy_total']}")
    print(f"Верных ответов: {results['correct']}")
    print(f"Ошибок: {results['wrong']}")
    print(f"📊 ОБЩАЯ ТОЧНОСТЬ: {results['accuracy']:.2f}%")
    print(f"📊 ТОЧНОСТЬ НА ЧИСТЫХ: {results['clean_accuracy']:.2f}%")
    print(f"📊 ТОЧНОСТЬ НА ШУМНЫХ: {results['noisy_accuracy']:.2f}%")
    print("="*70)

    # Таблица по командам
    print("\n📊 Статистика по командам:")
    print("-"*70)
    print(f"{'Команда':<20} {'Всего':>8} {'Верно':>8} {'Ошибки':>8} {'Точность':>10}")
    print("-"*70)

    for cmd, stats in sorted(results['by_command'].items(), key=lambda x: x[1]['total'], reverse=True):
        acc = stats['correct'] / stats['total'] * 100 if stats['total'] > 0 else 0
        marker = "" if cmd != "none" else " ⚠️"
        print(f"{cmd:<20} {stats['total']:>8} {stats['correct']:>8} {stats['wrong']:>8} {acc:>9.1f}%{marker}")

    print("-"*70)

    # Ошибки
    if verbose and results['mistakes']:
        print("\n❌ Ошибочные предсказания (первые 20):")
        print("-"*70)
        for i, m in enumerate(results['mistakes'][:20]):
            clean_marker = "[ЧИСТЫЕ]" if m['is_clean'] else "[ШУМ]"
            print(f"{i+1}. {clean_marker} Запрос: '{m['query']}'")
            print(f"   Ожидалось: {m['expected']}, Получено: '{m['actual']}'")
            print()

def main():
    global TEST_FILE

    import argparse
    parser = argparse.ArgumentParser(description="Тестирование Python-инференса (LoRA)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Показывать ошибки подробно")
    parser.add_argument("--file", type=str, default=str(TEST_FILE), help="Путь к тестовому файлу")
    parser.add_argument("--clean-only", action="store_true", help="Тестировать только чистые фразы")
    args = parser.parse_args()

    TEST_FILE = Path(args.file)

    if not TEST_FILE.exists():
        print(f"❌ Файл не найден: {TEST_FILE}")
        sys.exit(1)

    # Загрузка модели
    model, tokenizer = load_model()

    # Загрузка данных
    print(f"📂 Загрузка тестов из: {TEST_FILE}")
    tests = load_test_data(TEST_FILE, clean_only=args.clean_only)
    print(f"✅ Найдено тестовых примеров: {len(tests)}")

    # Тестирование
    start_time = time.time()
    results = evaluate_results(model, tokenizer, tests, verbose=args.verbose, clean_only=args.clean_only)
    elapsed = time.time() - start_time

    print(f"⏱️  Время выполнения: {elapsed:.1f} сек")

    print_results(results, verbose=args.verbose)

    # Сохранение
    suffix = "_clean" if args.clean_only else ""
    output_file = Path(f"result/command/test_python_results{suffix}.txt")
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(f"Всего тестов: {results['total']}\n")
        f.write(f"Чистых фраз: {results['clean_total']}\n")
        f.write(f"Шумных фраз: {results['noisy_total']}\n")
        f.write(f"Общая точность: {results['accuracy']:.2f}%\n")
        f.write(f"Точность на чистых: {results['clean_accuracy']:.2f}%\n")
        f.write(f"Точность на шумных: {results['noisy_accuracy']:.2f}%\n\n")
        f.write("Покомандная статистика:\n")
        for cmd, stats in sorted(results['by_command'].items(), key=lambda x: x[1]['total'], reverse=True):
            acc = stats['correct'] / stats['total'] * 100 if stats['total'] > 0 else 0
            f.write(f"  {cmd}: {stats['correct']}/{stats['total']} ({acc:.1f}%)\n")

    print(f"\n💾 Результаты сохранены в: {output_file}")

if __name__ == "__main__":
    main()
