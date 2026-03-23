import torch
import json
import os
import yaml
import re
import readline
from transformers import AutoTokenizer, AutoModelForCausalLM
from peft import PeftModel
from rapidfuzz import process, fuzz

CONFIG_FILE = "config.yaml"
HISTORY_FILE = ".inference_history"

def load_config():
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def load_keywords():
    path = "./data/keywords.txt"
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return [line.strip().lower() for line in f if line.strip()]
    return []

def load_model(config):
    base_path = config["model_name_or_path"]
    lora_path = config["output_dir"]
    print(f"Загрузка модели {base_path}...")
    tokenizer = AutoTokenizer.from_pretrained(base_path, trust_remote_code=True)
    model = AutoModelForCausalLM.from_pretrained(
        base_path, torch_dtype=torch.bfloat16, device_map={"": 0}, trust_remote_code=True
    )
    model = PeftModel.from_pretrained(model, lora_path)
    model.eval()
    return tokenizer, model

def has_command_potential(text, keywords, threshold=75):
    if not keywords: return True
    words = re.findall(r'\w+', text.lower())
    for word in words:
        # Нечеткое сравнение слова с базой ключевых слов
        res = process.extractOne(word, keywords, scorer=fuzz.WRatio)
        if res and res[1] >= threshold:
            return True
    return False

def process_input(text, tokenizer, model, keywords):
    # 1. Фильтр (нечеткий поиск)
    if not has_command_potential(text, keywords):
        return {"type": "final", "text": text}

    # 2. Промпт
    messages = [{"role": "user", "content": text}]
    prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = tokenizer(prompt, return_tensors="pt").to(model.device)

    # 3. Генерация
    with torch.no_grad():
        outputs = model.generate(
            **inputs, max_new_tokens=10, do_sample=False,
            pad_token_id=tokenizer.eos_token_id
        )

    # 4. Декодирование и очистка
    prompt_len = inputs["input_ids"].shape[-1]
    full_output = tokenizer.decode(outputs[0][prompt_len:], skip_special_tokens=True).strip()

    # Берем первую строку и первое слово
  # 5. Извлечение первого слова (безопасно)
    lines = full_output.split('\n')
    first_line = lines[0] if lines else ""
    parts = first_line.split(' ')
    prediction = parts[0].strip() if parts else ""

    if prediction.lower() in ["none", "system", "user", "assistant", ""] or not prediction:
        return {"type": "final", "text": text}

    return {"type": "command", "command": prediction, "text": text}

if __name__ == "__main__":
    os.environ["CUDA_VISIBLE_DEVICES"] = "0"
    config = load_config()
    keywords = load_keywords()
    tokenizer, model = load_model(config)

    if os.path.exists(HISTORY_FILE):
        readline.read_history_file(HISTORY_FILE)

    print("\nСистема готова (Fuzzy Search + Qwen). 'exit' для выхода.")
    while True:
        try:
            user_input = input("\n> ").strip()
            if user_input.lower() in ["exit", "quit"]: break
            if not user_input: continue

            result = process_input(user_input, tokenizer, model, keywords)
            color = "\033[92m" if result["type"] == "command" else "\033[94m"
            print(f"{color}{json.dumps(result, ensure_ascii=False, indent=2)}\033[0m")

            readline.set_history_length(100)
            readline.write_history_file(HISTORY_FILE)
        except (EOFError, KeyboardInterrupt):
            break
