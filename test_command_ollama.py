#!/usr/bin/env python3
"""
Тестирование модели Ollama (через API) на тестовом датасете command/test.jsonl
"""

import json
import requests
import sys
import time
from pathlib import Path
from collections import defaultdict

MODEL_NAME = "qwen_command"
TEST_FILE = Path("result/command/test.jsonl")
OLLAMA_API = "http://localhost:11434/api/generate"

# Путь к файлу с системным промптом (единый источник)
SYSTEM_PROMPT_FILE = Path(__file__).parent / "docs" / "command_prompt.txt"

# Дефолтный промпт (используется если файл не найден)
DEFAULT_SYSTEM_PROMPT = "Ты — помощник для определения команд в тексте."


def load_system_prompt(file_path: Path = SYSTEM_PROMPT_FILE) -> str:
    """Загружает системный промпт из файла."""
    if file_path.exists():
        return file_path.read_text(encoding="utf-8").strip()
    return DEFAULT_SYSTEM_PROMPT

SYSTEM_PROMPT = load_system_prompt()


def run_ollama_query(query: str, timeout: int = 30) -> str:
    """Выполняет запрос к модели Ollama через API."""
    try:
        payload = {
            "model": MODEL_NAME,
            "prompt": query,
            "system": SYSTEM_PROMPT,
            "stream": False,
            "options": {
                "temperature": 0.3,
                "top_p": 0.9,
                "top_k": 40
            }
        }
        response = requests.post(OLLAMA_API, json=payload, timeout=timeout)
        response.raise_for_status()
        result = response.json()
        return result.get("response", "").strip()
    except requests.exceptions.Timeout:
        return "TIMEOUT"
    except Exception as e:
        return f"ERROR: {e}"

def load_test_data(file_path: Path):
    """Загружает тестовые данные из JSONL файла."""
    tests = []
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                tests.append(json.loads(line))
    return tests

def evaluate_results(model_func, tests: list, verbose: bool = False) -> dict:
    """Оценивает результаты и возвращает статистику."""
    total = len(tests)
    correct = 0
    wrong = 0

    # Общая статистика по командам
    by_command = defaultdict(lambda: {"total": 0, "correct": 0, "wrong": 0})

    # Разделение на чистые и шумные
    clean_total = 0
    clean_correct = 0
    clean_by_command = defaultdict(lambda: {"total": 0, "correct": 0, "wrong": 0})

    noisy_total = 0
    noisy_correct = 0
    noisy_by_command = defaultdict(lambda: {"total": 0, "correct": 0, "wrong": 0})

    mistakes = []

    for i, test in enumerate(tests):
        expected = test.get("name", "").strip()
        query = test.get("rus") or test.get("eng") or ""

        # Определяем, чистая это фраза или с шумом
        is_clean = "rus" in test and "eng" not in test

        actual = model_func(query)

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
        else:
            wrong += 1

        # Общая статистика по командам
        by_command[expected]["total"] += 1
        if is_correct:
            by_command[expected]["correct"] += 1
        else:
            by_command[expected]["wrong"] += 1

        # Разделение на чистые и шумные
        if is_clean:
            clean_total += 1
            clean_by_command[expected]["total"] += 1
            if is_correct:
                clean_correct += 1
                clean_by_command[expected]["correct"] += 1
            else:
                clean_by_command[expected]["wrong"] += 1
        else:
            noisy_total += 1
            noisy_by_command[expected]["total"] += 1
            if is_correct:
                noisy_correct += 1
                noisy_by_command[expected]["correct"] += 1
            else:
                noisy_by_command[expected]["wrong"] += 1

        if verbose and not is_correct:
            clean_marker = "[ЧИСТЫЕ]" if is_clean else "[ШУМ]"
            mistakes.append({
                "query": query,
                "expected": expected,
                "actual": actual,
                "index": i,
                "is_clean": is_clean,
                "clean_marker": clean_marker
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
        "clean_by_command": dict(clean_by_command),
        "noisy_by_command": dict(noisy_by_command),
        "mistakes": mistakes
    }

def print_results(results: dict, verbose: bool = False):
    """Выводит результаты в виде таблицы."""
    print("\n" + "="*80)
    print("РЕЗУЛЬТАТЫ ТЕСТИРОВАНИЯ OLLAMA (API)")
    print("="*80)
    print(f"Всего тестов: {results['total']}")
    print(f"  ├─ Чистых фраз: {results['clean_total']} → Точность: {results['clean_accuracy']:.2f}%")
    print(f"  └─ Шумных фраз: {results['noisy_total']} → Точность: {results['noisy_accuracy']:.2f}%")
    print(f"Верных ответов: {results['correct']}")
    print(f"Ошибок: {results['wrong']}")
    print(f"📊 ОБЩАЯ ТОЧНОСТЬ: {results['accuracy']:.2f}%")
    print("="*80)

    # Таблица по командам: всего / чистые / с шумом
    print("\n📊 Статистика по командам (всего / чистые / с шумом):")
    print("-"*90)
    print(f"{'Команда':<18} {'Всего':>8} {'Точн.':>9} | {'Чист.':>8} {'Точн.':>9} | {'Шум.':>8} {'Точн.':>9}")
    print("-"*90)

    all_commands = sorted(results['by_command'].keys(), key=lambda x: results['by_command'][x]['total'], reverse=True)

    for cmd in all_commands:
        total_stats = results['by_command'][cmd]
        clean_stats = results['clean_by_command'].get(cmd, {"total": 0, "correct": 0, "wrong": 0})
        noisy_stats = results['noisy_by_command'].get(cmd, {"total": 0, "correct": 0, "wrong": 0})

        total_acc = total_stats['correct'] / total_stats['total'] * 100 if total_stats['total'] > 0 else 0
        clean_acc = clean_stats['correct'] / clean_stats['total'] * 100 if clean_stats['total'] > 0 else 0
        noisy_acc = noisy_stats['correct'] / noisy_stats['total'] * 100 if noisy_stats['total'] > 0 else 0

        marker = " ⚠️" if cmd == "none" else ""
        print(f"{cmd:<18} {total_stats['total']:>8} {total_acc:>8.1f}%{marker} | {clean_stats['total']:>8} {clean_acc:>8.1f}% | {noisy_stats['total']:>8} {noisy_acc:>8.1f}%")

    print("-"*90)

    # Ошибки
    if verbose and results['mistakes']:
        print("\n❌ Ошибочные предсказания (первые 20):")
        print("-"*70)
        for i, m in enumerate(results['mistakes'][:20]):
            print(f"{i+1}. {m['clean_marker']} Запрос: '{m['query']}'")
            print(f"   Ожидалось: {m['expected']}, Получено: '{m['actual']}'")
            print()

def main():
    global MODEL_NAME, TEST_FILE

    import argparse
    parser = argparse.ArgumentParser(description="Тестирование модели Ollama через API")
    parser.add_argument("--verbose", "-v", action="store_true", help="Показывать ошибки подробно")
    parser.add_argument("--file", type=str, default=str(TEST_FILE), help="Путь к тестовому файлу")
    parser.add_argument("--model", type=str, default=MODEL_NAME, help="Имя модели Ollama")
    args = parser.parse_args()

    MODEL_NAME = args.model
    TEST_FILE = Path(args.file)

    if not TEST_FILE.exists():
        print(f"❌ Файл не найден: {TEST_FILE}")
        sys.exit(1)

    # Проверка доступности Ollama API
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=5)
        if response.status_code != 200:
            print("❌ Ollama API недоступен. Запустите: ollama serve")
            sys.exit(1)
    except requests.exceptions.ConnectionError:
        print("❌ Ollama API недоступен. Запустите: ollama serve")
        sys.exit(1)

    print(f"📂 Загрузка тестов из: {TEST_FILE}")
    tests = load_test_data(TEST_FILE)
    print(f"✅ Найдено тестовых примеров: {len(tests)}")

    print(f"🤖 Тестирование модели: {MODEL_NAME} (через API)")
    start_time = time.time()
    results = evaluate_results(run_ollama_query, tests, verbose=args.verbose)
    elapsed = time.time() - start_time

    print(f"⏱️  Время выполнения: {elapsed:.1f} сек ({elapsed/len(tests):.2f} сек/запрос)")

    print_results(results, verbose=args.verbose)

    # Сохранение результатов
    output_file = Path(f"result/command/test_ollama_api_results_{MODEL_NAME}.txt")
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(f"Модель: {MODEL_NAME}\n")
        f.write(f"Всего тестов: {results['total']}\n")
        f.write(f"Чистых фраз: {results['clean_total']} (точность: {results['clean_accuracy']:.2f}%)\n")
        f.write(f"Шумных фраз: {results['noisy_total']} (точность: {results['noisy_accuracy']:.2f}%)\n")
        f.write(f"Общая точность: {results['accuracy']:.2f}%\n\n")
        f.write("Покомандная статистика (всего / чистые / шум):\n")
        for cmd in sorted(results['by_command'].keys(), key=lambda x: results['by_command'][x]['total'], reverse=True):
            total_stats = results['by_command'][cmd]
            clean_stats = results['clean_by_command'].get(cmd, {"total": 0, "correct": 0})
            noisy_stats = results['noisy_by_command'].get(cmd, {"total": 0, "correct": 0})

            total_acc = total_stats['correct'] / total_stats['total'] * 100 if total_stats['total'] > 0 else 0
            clean_acc = clean_stats['correct'] / clean_stats['total'] * 100 if clean_stats['total'] > 0 else 0
            noisy_acc = noisy_stats['correct'] / noisy_stats['total'] * 100 if noisy_stats['total'] > 0 else 0

            f.write(f"  {cmd}: {total_stats['correct']}/{total_stats['total']} ({total_acc:.1f}%) | чистые: {clean_stats['correct']}/{clean_stats['total']} ({clean_acc:.1f}%) | шум: {noisy_stats['correct']}/{noisy_stats['total']} ({noisy_acc:.1f}%)\n")

    print(f"\n💾 Результаты сохранены в: {output_file}")

if __name__ == "__main__":
    main()
