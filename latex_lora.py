#!/usr/bin/env python3
"""
latex_lora.py - Интерактивный инференс для модели Qwen2.5-1.5B-Instruct + LoRA
Преобразует русское описание математических формул в LaTeX скрипты
"""

import torch
import re
import readline
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
from peft import PeftModel
import argparse

# Настройка истории ввода
readline.parse_and_bind('bind ^[[A history-search-backward')  # Стрелка вверх
readline.parse_and_bind('bind ^[[B history-search-forward')  # Стрелка вниз
readline.parse_and_bind('set editing-mode emacs')  # Режим редактирования


def validate_latex(response):
    """
    Проверка валидности LaTeX скрипта
    Возвращает True если ответ похож на LaTeX формулу
    """
    if not response or not response.strip():
        return False
    
    # Должен содержать хотя бы одну команду LaTeX (обратный слеш)
    if not re.search(r'\\[a-zA-Z]+|\\[a-zA-Z]+\{', response):
        return False
    
    # Не должен содержать текст "конечно", "вот", "формула" и т.п.
    if re.search(r'конечно|вот|формула|latex:', response, re.IGNORECASE):
        return False
    
    # Не должен быть слишком длинным (более 200 символов — вероятно мусор)
    if len(response) > 200:
        return False
    
    # Не должен содержать кириллицу (если есть — модель "болтает")
    if re.search(r'[а-яА-ЯёЁ]', response):
        return False
    
    return True



def main():
    parser = argparse.ArgumentParser(description='Инференс LaTeX модели')
    parser.add_argument('--base_model', type=str, 
                       default='../bhl/Models/Qwen2.5-1.5B-Instruct/orig',
                       help='Базовая модель Qwen2.5-1.5B-Instruct')
    parser.add_argument('--lora_path', type=str,
                       default='saves/qwen_latex_lora',
                       help='Путь к LoRA адаптеру')
    parser.add_argument('--device', type=str, default='cuda',
                       help='Устройство: cuda или cpu')
    parser.add_argument('--max_length', type=int, default=256,
                       help='Максимальная длина ответа')
    args = parser.parse_args()

    print("=" * 60)
    print("🧮 LaTeX Formula Generator")
    print("=" * 60)
    print(f"   Базовая модель: {args.base_model}")
    print(f"   LoRA адаптер: {args.lora_path}")
    print(f"   Устройство: {args.device}")
    print("=" * 60)

    # Настройки квантизации (опционально)
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16,
        bnb_4bit_use_double_quant=True,
    )

    # Загрузка токенизатора
    print("\n📥 Загрузка токенизатора...")
    tokenizer = AutoTokenizer.from_pretrained(
        args.base_model,
        trust_remote_code=True,
        padding_side="right",
    )
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    # Загрузка базовой модели
    print("📥 Загрузка базовой модели...")
    base_model = AutoModelForCausalLM.from_pretrained(
        args.base_model,
        quantization_config=bnb_config,
        device_map="auto",
        trust_remote_code=True,
        torch_dtype=torch.bfloat16,
    )

    # Загрузка LoRA адаптера
    print("📥 Загрузка LoRA адаптера...")
    model = PeftModel.from_pretrained(base_model, args.lora_path)
    model.eval()

    print(f"\n✅ Модель готова!")
    print("\n" + "=" * 60)
    print("Вводите русские описания формул (или 'quit' для выхода):")
    print("  ↑ / ↓ — история, Enter — отправка, Ctrl+C — выход")
    print("=" * 60)

    # Интерактивный цикл
    history = []
    while True:
        try:
            # Ввод пользователя с историей
            user_input = input("\n📝 Описание: ").strip()
            
            if user_input.lower() in ['quit', 'exit', 'q']:
                print("\n👋 До свидания!")
                break
            
            # Добавляем в историю (если не дубль)
            if user_input and (not history or history[-1] != user_input):
                history.append(user_input)
                if len(history) > 50:  # Храним последние 50
                    history.pop(0)

            # Форматирование промпта в стиле Alpaca
            prompt = f"""Below is an instruction that describes a task, paired with an input that provides further context. Write a response that appropriately completes the request.

### Instruction:
Преобразуй описание на русском языке в LaTeX формулу.

### Input:
{user_input}

### Response:
"""

            # Генерация с проверкой (до 3 попыток)
            response = None
            for attempt in range(3):
                # Токенизация
                inputs = tokenizer(prompt, return_tensors="pt").to(args.device)
                
                # Генерация
                with torch.no_grad():
                    outputs = model.generate(
                        **inputs,
                        max_new_tokens=args.max_length,
                        temperature=0.1 + (attempt * 0.05),  # Немного увеличиваем температуру при повторах
                        top_p=0.9,
                        top_k=50,
                        repetition_penalty=1.1,
                        do_sample=True,
                        pad_token_id=tokenizer.eos_token_id,
                    )
                
                # Парсинг ответа
                full_response = tokenizer.decode(outputs[0], skip_special_tokens=True)
                
                # Извлекаем только часть после "### Response:"
                if "### Response:" in full_response:
                    candidate = full_response.split("### Response:")[1].strip()
                else:
                    candidate = full_response.split(prompt)[-1].strip()
                
                # Очистка от лишнего текста
                cleanup_patterns = [
                    "конечно,",
                    "вот латекс:",
                    "latex:",
                    "формула:",
                ]
                for pattern in cleanup_patterns:
                    if candidate.lower().startswith(pattern):
                        candidate = candidate[len(pattern):].strip()
                
                # Берём только первую строку
                candidate = candidate.split('\n')[0].strip()
                
                # Удаляем лишние кавычки и точки в конце
                candidate = candidate.rstrip('.,;:')
                
                # Проверка валидности
                if validate_latex(candidate):
                    response = candidate
                    break
                elif attempt < 2:
                    print(f"   (Попытка {attempt + 1} не валидна, пробуем ещё раз...)")

            if response:
                print(f"📋 LaTeX: {response}")
            else:
                print(f"❌ Не удалось сгенерировать валидный LaTeX после 3 попыток.")
                print(f"   Попробуйте перефразировать запрос.")

        except KeyboardInterrupt:
            print("\n\n👋 До свидания!")
            break
        except Exception as e:
            print(f"\n❌ Ошибка: {e}")
            continue


if __name__ == "__main__":
    main()