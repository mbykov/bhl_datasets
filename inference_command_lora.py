#!/usr/bin/env python3
"""
Инференс для LoRA-модели команд
"""

import os
import sys
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

# Настройки GPU
os.environ["CUDA_VISIBLE_DEVICES"] = "0"

# Пути
BASE_MODEL = "../bhl/Models/Qwen2.5-0.5B-Instruct/orig"
LORA_PATH = "./saves/qwen_command_lora/checkpoint-969"  # Или latest checkpoint

# Допустимые ответы (команды + none)
VALID_COMMANDS = {
   "newText", "saveNote", "clearText", "addParagraph", "undoPhrase", "undoParagraph", "undoCommand", "killParagraph", "killPhrase", "recordStop", "recordStart"
}

def load_model():
    """Загружает базовую модель + LoRA веса"""
    print(f"📦 Загрузка базовой модели: {BASE_MODEL}")
    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL, trust_remote_code=True)

    print(f"📦 Загрузка LoRA весов: {LORA_PATH}")
    model = AutoModelForCausalLM.from_pretrained(
        BASE_MODEL,
        torch_dtype=torch.float16,
        device_map="auto",
        trust_remote_code=True
    )

    # Подгрузка LoRA
    from peft import PeftModel
    model = PeftModel.from_pretrained(model, LORA_PATH)

    model.eval()
    print("✅ Модель загружена!")
    return model, tokenizer


def generate_response(model, tokenizer, prompt, lang="rus"):
    """Генерирует ответ для команды"""
    # Форматируем промпт для Qwen
    if lang == "rus":
        full_prompt = f"<|im_start|>user\n{prompt}<|im_end|>\n<|im_start|>assistant\n"
    else:
        full_prompt = f"<|im_start|>user\n{prompt}<|im_end|>\n<|im_start|>assistant\n"

    inputs = tokenizer(full_prompt, return_tensors="pt").to(model.device)

    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=32,
            temperature=0.7,
            top_p=0.9,
            do_sample=True,
            pad_token_id=tokenizer.eos_token_id
        )

    response = tokenizer.decode(outputs[0], skip_special_tokens=True)
    # Извлекаем только генерацию
    response = response.split("assistant\n")[-1].strip()

    # Берём только первое слово (команда не содержит пробелов)
    response = response.split()[0] if response.split() else ""
    return response


def interactive_mode(model, tokenizer):
    """Интерактивный режим"""
    print("\n" + "=" * 60)
    print("🎮 Интерактивный режим (Ctrl+C для выхода)")
    print("=" * 60)
    print("💡 Garbage-фразы вернут: null")
    print("=" * 60)

    while True:
        try:
            prompt = input("\n📝 Введите команду: ").strip()
            if not prompt:
                continue

            # Определение языка
            lang = "rus" if any(c in prompt for c in 'абвгдеёжзийклмнопрстуфхцчшщъыьэюя') else "eng"

            # print(f"🤖 Модель думает...", end="\r")
            raw_response = generate_response(model, tokenizer, prompt, lang).strip()
            print(f"🎯 raw_response: {raw_response}")

            # Валидация ответа: если не команда — возвращаем null
            if raw_response in VALID_COMMANDS:
                display_response = raw_response if raw_response != "none" else "null"
            else:
                # Ответ не распознан как команда
                display_response = "null"

            print(f"🎯 Ответ: {display_response}")

        except KeyboardInterrupt:
            print("\n\n👋 До свидания!")
            break


def batch_test(model, tokenizer, test_file="result/command/test.jsonl"):
    """Тестирование на тестовом датасете"""
    if not os.path.exists(test_file):
        print(f"❌ Файл {test_file} не найден!")
        return

    print(f"\n📊 Тестирование на {test_file}")
    print("=" * 60)

    correct = 0
    total = 0

    with open(test_file, 'r', encoding='utf-8') as f:
        for line in f:
            import json
            data = json.loads(line)

            # Пропускаем garbage
            if data.get("name") == "none":
                continue

            prompt = data.get("rus") or data.get("eng")
            expected = data.get("name")
            lang = "rus" if "rus" in data else "eng"

            response = generate_response(model, tokenizer, prompt, lang)

            # Простая проверка совпадения
            is_correct = expected.lower() in response.lower()
            if is_correct:
                correct += 1

            total += 1
            if total <= 10:  # Показать первые 10
                status = "✅" if is_correct else "❌"
                print(f"{status} '{prompt}' → {response} (ожидал: {expected})")

            if total >= 20:  # Ограничить вывод
                break

    if total > 0:
        accuracy = correct / total * 100
        print(f"\n📈 Точность: {accuracy:.1f}% ({correct}/{total})")


def main():
    # Загрузка модели
    model, tokenizer = load_model()

    # Режимы
    print("\n" + "=" * 60)
    print("🔧 Режимы работы:")
    print("  1 - Интерактивный тест")
    print("  2 - Тест на тестовом датасете")
    print("=" * 60)

    choice = input("Выберите режим (1/2): ").strip()

    if choice == "1":
        interactive_mode(model, tokenizer)
    elif choice == "2":
        batch_test(model, tokenizer)
    else:
        print("❌ Неверный выбор")


if __name__ == "__main__":
    main()
