#!/usr/bin/env python3
"""
Тестирование дообученной модели на тестовом датасете
"""

import os
import sys
import json
import argparse
import warnings
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM, logging as hf_logging
from peft import PeftModel
from tqdm import tqdm
from collections import defaultdict

# Подавляем предупреждения
hf_logging.set_verbosity_error()
warnings.filterwarnings("ignore", category=UserWarning, module="transformers")
warnings.filterwarnings("ignore", category=UserWarning, module="peft")

def load_model(model_path, base_model_path="../bhl/Models/Qwen2.5-1.5B-Instruct"):
    """Загружает модель и токенизатор"""
    print(f"📦 Загрузка модели из {model_path}...")

    tokenizer = AutoTokenizer.from_pretrained(base_model_path, trust_remote_code=True)

    model = AutoModelForCausalLM.from_pretrained(
        base_model_path,
        torch_dtype=torch.bfloat16,
        device_map="cuda:0",
        trust_remote_code=True
    )

    if os.path.exists(model_path):
        model = PeftModel.from_pretrained(model, model_path)
        print(f"   ✅ LoRA адаптер загружен: {model_path}")
    else:
        print(f"   ⚠️ Адаптер не найден: {model_path}")

    model.eval()
    return tokenizer, model

def load_test_dataset(dataset_path, filter_type=None):
    """Загружает тестовый датасет с возможностью фильтрации по типу"""
    print(f"📂 Загрузка тестового датасета: {dataset_path}")

    data = []
    with open(dataset_path, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                item = json.loads(line)
                # Фильтруем по типу, если указан
                if filter_type:
                    if filter_type == "command" and "Определи команду" in item.get("instruction", ""):
                        data.append(item)
                    elif filter_type == "latex" and "Преобразуй текст" in item.get("instruction", ""):
                        data.append(item)
                else:
                    data.append(item)

    print(f"   Загружено {len(data)} примеров")
    if filter_type:
        print(f"   Тип: {filter_type}")
    return data

def evaluate_sample(tokenizer, model, sample):
    """Оценивает один пример"""

    prompt = f"<|im_start|>system\nYou are Qwen, created by Alibaba Cloud. You are a helpful assistant.<|im_end|>\n<|im_start|>user\n{sample['instruction']}\n{sample['input']}<|im_end|>\n<|im_start|>assistant\n"

    inputs = tokenizer(prompt, return_tensors="pt").to("cuda:0")

    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=100,
            do_sample=False,
            pad_token_id=tokenizer.eos_token_id
        )

    response = tokenizer.decode(outputs[0][inputs['input_ids'].shape[1]:], skip_special_tokens=True).strip()

    expected = sample['output']

    if sample['instruction'] == "Определи команду в тексте":
        predicted = response.split()[0] if response else ""
        is_correct = predicted == expected or expected in response
        return {
            "correct": is_correct,
            "predicted": predicted,
            "expected": expected,
            "full_response": response,
            "type": "command"
        }
    else:
        expected_normalized = expected.strip()
        response_normalized = response.strip()
        is_correct = expected_normalized == response_normalized

        return {
            "correct": is_correct,
            "predicted": response,
            "expected": expected,
            "full_response": response,
            "type": "latex"
        }

def evaluate_dataset(tokenizer, model, dataset, limit=None):
    """Оценивает весь датасет"""

    if limit:
        dataset = dataset[:limit]

    results = {
        "total": len(dataset),
        "correct": 0,
        "by_type": defaultdict(lambda: {"total": 0, "correct": 0}),
        "errors": []
    }

    print("\n🔍 Запуск тестирования...")
    print("="*60)

    for i, sample in enumerate(tqdm(dataset, desc="Тестирование")):
        result = evaluate_sample(tokenizer, model, sample)

        if result["correct"]:
            results["correct"] += 1
            results["by_type"][result["type"]]["correct"] += 1

        results["by_type"][result["type"]]["total"] += 1

        if not result["correct"]:
            results["errors"].append({
                "index": i,
                "instruction": sample['instruction'],
                "input": sample['input'],
                "expected": result["expected"],
                "predicted": result["predicted"],
                "full_response": result["full_response"],
                "type": result["type"]
            })

    return results

def print_results(results):
    """Выводит результаты тестирования"""

    print("\n" + "="*60)
    print("📊 РЕЗУЛЬТАТЫ ТЕСТИРОВАНИЯ")
    print("="*60)

    accuracy = (results["correct"] / results["total"]) * 100
    print(f"\n📈 Общая точность: {accuracy:.2f}% ({results['correct']}/{results['total']})")

    print(f"\n📊 По типам задач:")
    print("-"*40)
    for task_type, stats in results["by_type"].items():
        if stats["total"] > 0:
            task_accuracy = (stats["correct"] / stats["total"]) * 100
            task_name = "Команды" if task_type == "command" else "LaTeX"
            print(f"   {task_name:10} | {task_accuracy:5.2f}% | {stats['correct']:3}/{stats['total']:3}")

    if results["errors"]:
        print(f"\n❌ ОШИБКИ (первые 10 из {len(results['errors'])}):")
        print("="*60)

        for i, err in enumerate(results["errors"][:10], 1):
            print(f"\n{i}. [{err['type'].upper()}]")
            print(f"   Вход: {err['input']}")
            print(f"   Ожидаемый: {err['expected']}")
            print(f"   Получено: {err['predicted']}")
            if err['full_response'] != err['predicted']:
                print(f"   Полный ответ: {err['full_response'][:100]}...")

    if results["errors"]:
        errors_file = "test_errors.json"
        with open(errors_file, "w", encoding="utf-8") as f:
            json.dump(results["errors"], f, ensure_ascii=False, indent=2)
        print(f"\n💾 Полный список ошибок сохранен в {errors_file}")

def main():
    parser = argparse.ArgumentParser(description="Тестирование дообученной модели")
    parser.add_argument("--model", type=str,
                        default="/home/michael/LLM/datasets_bhl/saves/qwen_merged_lora",
                        help="Путь к LoRA адаптеру")
    parser.add_argument("--ds", type=str,
                        default="result/merged/test.jsonl",
                        help="Путь к тестовому датасету")
    parser.add_argument("--base", type=str,
                        default="../bhl/Models/Qwen2.5-1.5B-Instruct",
                        help="Путь к базовой модели")
    parser.add_argument("--limit", type=int, default=None,
                        help="Ограничить количество тестовых примеров")
    parser.add_argument("--type", type=str, choices=["command", "latex", "all"], default="all",
                        help="Тип тестирования: command, latex, all")

    args = parser.parse_args()

    os.environ["CUDA_VISIBLE_DEVICES"] = "1"
    os.environ["PYTORCH_ALLOC_CONF"] = "expandable_segments:True"

    print("\n" + "="*60)
    print("🧪 ТЕСТИРОВАНИЕ ДООБУЧЕННОЙ МОДЕЛИ")
    print("="*60)
    print(f"Модель: {args.model}")
    print(f"Тестовый датасет: {args.ds}")
    print(f"Тип: {args.type}")
    if args.limit:
        print(f"Лимит: {args.limit}")

    if not os.path.exists(args.model):
        print(f"❌ Модель не найдена: {args.model}")
        sys.exit(1)

    if not os.path.exists(args.ds):
        print(f"❌ Тестовый датасет не найден: {args.ds}")
        sys.exit(1)

    tokenizer, model = load_model(args.model, args.base)

    filter_type = None if args.type == "all" else args.type
    dataset = load_test_dataset(args.ds, filter_type)

    results = evaluate_dataset(tokenizer, model, dataset, args.limit)
    print_results(results)

    accuracy = (results["correct"] / results["total"]) * 100
    sys.exit(0 if accuracy >= 80 else 1)

if __name__ == "__main__":
    main()
