import torch
import json
import os
import yaml
import re
import readline
import sys
import argparse
from transformers import AutoTokenizer, AutoModelForCausalLM
from peft import PeftModel
from rapidfuzz import process, fuzz

CONFIG_FILE = "config.yaml"
HISTORY_FILE = ".inference_history"

def load_config():
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def load_keywords():
    """Загружает ключевые слова для команд и LaTeX"""
    cmd_path = "./data/keywords.txt"
    latex_path = "./data/latex_keywords.txt"

    cmd_keywords = []
    latex_keywords = []

    if os.path.exists(cmd_path):
        with open(cmd_path, "r", encoding="utf-8") as f:
            cmd_keywords = [line.strip().lower() for line in f if line.strip()]

    if os.path.exists(latex_path):
        with open(latex_path, "r", encoding="utf-8") as f:
            latex_keywords = [line.strip().lower() for line in f if line.strip()]

    return cmd_keywords, latex_keywords

def load_model(config, lora_path=None):
    """Загружает базовую модель и опционально LoRA адаптер"""
    base_path = config["model_name_or_path"]

    # Если не указан конкретный адаптер, ищем в config
    if lora_path is None:
        lora_path = config.get("adapter_name_or_path", config["output_dir"])

    print(f"📦 Загрузка базовой модели: {base_path}")
    tokenizer = AutoTokenizer.from_pretrained(base_path, trust_remote_code=True)
    model = AutoModelForCausalLM.from_pretrained(
        base_path, torch_dtype=torch.bfloat16, device_map={"": 0}, trust_remote_code=True
    )

    if lora_path and os.path.exists(lora_path):
        print(f"🔧 Загрузка LoRA адаптера: {lora_path}")
        model = PeftModel.from_pretrained(model, lora_path)
        model.eval()
    else:
        print(f"⚠️ LoRA адаптер не найден: {lora_path}")
        print("   Используется только базовая модель")

    return tokenizer, model

def detect_task_type(text, cmd_keywords, latex_keywords, threshold=75):
    """Определяет тип запроса: command или latex"""
    text_lower = text.lower()
    words = re.findall(r'\b[a-zA-Zа-яА-Я]{3,}\b', text_lower)

    # Проверяем команды
    for word in words:
        res = process.extractOne(word, cmd_keywords, scorer=fuzz.WRatio)
        if res and res[1] >= threshold:
            return "command"

    # Проверяем LaTeX
    for word in words:
        res = process.extractOne(word, latex_keywords, scorer=fuzz.WRatio)
        if res and res[1] >= threshold:
            return "latex"

    return "unknown"

def process_input(text, tokenizer, model, cmd_keywords, latex_keywords):
    """Обрабатывает пользовательский ввод"""
    # 1. Определяем тип задачи
    task = detect_task_type(text, cmd_keywords, latex_keywords)

    # 2. Выбираем системный промпт и параметры генерации
    if task == "command":
        messages = [{"role": "user", "content": text}]
        max_new_tokens = 10
        do_sample = False
    elif task == "latex":
        messages = [
            {"role": "system", "content": "Ты помощник, который преобразует текст в LaTeX формулы."},
            {"role": "user", "content": text}
        ]
        max_new_tokens = 200
        do_sample = False
    else:
        # Если не распознали, просто возвращаем текст
        return {"type": "final", "text": text, "task": task}

    # 3. Генерация
    prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = tokenizer(prompt, return_tensors="pt").to(model.device)

    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            do_sample=do_sample,
            pad_token_id=tokenizer.eos_token_id
        )

    # 4. Декодирование
    prompt_len = inputs["input_ids"].shape[-1]
    full_output = tokenizer.decode(outputs[0][prompt_len:], skip_special_tokens=True).strip()

    if task == "command":
        # Для команд берем первое слово
        prediction = full_output.split()[0] if full_output else ""
        if prediction.lower() in ["none", "system", "user", "assistant", ""]:
            return {"type": "final", "text": text, "task": task}
        return {"type": "command", "command": prediction, "text": text, "task": task}
    else:
        # Для LaTeX возвращаем сгенерированную формулу
        return {"type": "latex", "formula": full_output, "text": text, "task": task}

def setup_history():
    """Настраивает историю команд, создавая файл если нужно"""
    try:
        if os.path.exists(HISTORY_FILE):
            # Проверяем, что файл не пустой и читаемый
            if os.path.getsize(HISTORY_FILE) > 0:
                readline.read_history_file(HISTORY_FILE)
            else:
                # Пустой файл - создаем заново
                os.remove(HISTORY_FILE)
                open(HISTORY_FILE, 'a').close()
        else:
            # Создаем пустой файл истории
            open(HISTORY_FILE, 'a').close()
    except Exception as e:
        print(f"⚠️ Не удалось загрузить историю: {e}")
        # Продолжаем без истории

def save_history():
    """Сохраняет историю команд"""
    try:
        readline.set_history_length(100)
        readline.write_history_file(HISTORY_FILE)
    except Exception as e:
        pass  # Игнорируем ошибки сохранения истории

def print_help():
    """Выводит справку по использованию"""
    print("""
📖 Справка:
   Команды: удали текст, создай абзац, выдели фразу, начни запись, отмени команду
   LaTeX:   limit of x over y as x goes to 0, power set of A union B, laplacian of scalar field F

   Специальные команды:
   /help     - показать справку
   /model    - показать информацию о модели
   /exit     - выйти
    """)

def print_model_info(lora_path):
    """Выводит информацию о загруженной модели"""
    print(f"""
🤖 Информация о модели:
   LoRA адаптер: {lora_path if lora_path else 'не используется'}
   Дообученные навыки:
     - Команды: удаление, создание, выделение, запись, отмена
     - LaTeX: преобразование текста в математические формулы
    """)

def main():
    parser = argparse.ArgumentParser(description="Инференс для дообученной модели")
    parser.add_argument("--model", type=str, default=None,
                        help="Путь к LoRA адаптеру (например, saves/qwen_latex_lora)")
    parser.add_argument("--base", type=str, default=None,
                        help="Путь к базовой модели (по умолчанию из config.yaml)")
    args = parser.parse_args()

    # Настройки GPU
    os.environ["CUDA_VISIBLE_DEVICES"] = "0"
    os.environ["PYTORCH_ALLOC_CONF"] = "expandable_segments:True"

    # Загружаем конфиг
    config = load_config()

    # Если указан адаптер через аргумент, используем его
    lora_path = args.model
    if lora_path is None:
        # Проверяем наличие обученных моделей
        if os.path.exists("./saves/qwen_latex_lora"):
            lora_path = "./saves/qwen_latex_lora"
            print("✅ Найден адаптер qwen_latex_lora (команды + LaTeX)")
        elif os.path.exists("./saves/qwen_command_lora"):
            lora_path = "./saves/qwen_command_lora"
            print("✅ Найден адаптер qwen_command_lora (только команды)")
        else:
            lora_path = None
            print("⚠️ Обученные адаптеры не найдены, используется базовая модель")

    # Загружаем модель
    tokenizer, model = load_model(config, lora_path)

    # Загружаем ключевые слова
    cmd_keywords, latex_keywords = load_keywords()
    print(f"📝 Загружено ключевых слов: команд={len(cmd_keywords)}, LaTeX={len(latex_keywords)}")

    # Настраиваем историю
    setup_history()

    print("\n" + "=" * 60)
    print("🤖 Система готова (Команды + LaTeX)")
    print("=" * 60)
    print_model_info(lora_path)
    print_help()
    print()

    while True:
        try:
            user_input = input("> ").strip()
            if user_input.lower() in ["exit", "quit", "/exit"]:
                break
            if user_input.lower() in ["help", "/help"]:
                print_help()
                continue
            if user_input.lower() == "/model":
                print_model_info(lora_path)
                continue
            if not user_input:
                continue

            result = process_input(user_input, tokenizer, model, cmd_keywords, latex_keywords)

            if result["type"] == "command":
                color = "\033[92m"  # зеленый
                print(f"{color}🔧 Команда: {result['command']}\033[0m")
            elif result["type"] == "latex":
                # color = "\033[93m"  # желтый
                color = "\033[91m"  # ярко-красный
                print(f"{color}📐 Формула: {result['formula']}\033[0m")
            else:
                color = "\033[94m"  # синий
                print(f"{color}💬 Обычный текст: {result['text']}\033[0m")

            # Сохраняем историю
            save_history()

        except (EOFError, KeyboardInterrupt):
            break
        except Exception as e:
            print(f"\033[91m❌ Ошибка: {e}\033[0m")

if __name__ == "__main__":
    main()
