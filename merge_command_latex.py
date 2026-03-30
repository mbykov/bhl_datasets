import json
import os
import random
import re

# Инструкции для разных типов задач
# Вариативные инструкции для команд
COMMAND_INSTRUCTIONS = [
    "Определи команду в тексте",
    "Распознай команду",
    "Найди команду в тексте",
    "Идентифицируй команду",
    "Какая это команда"
]

# Вариативные инструкции для LaTeX
LATEX_INSTRUCTIONS = [
    "Преобразуй текст в формулу LaTeX",
    "Запиши формулу в LaTeX",
    "Переведи текст в LaTeX",
    "Создай формулу LaTeX",
    "Вырази формулу в LaTeX",
    "Получи формулу LaTeX",
    "Напиши формулу в LaTeX",
    "Сгенерируй LaTeX формулу"
]

GARBAGE_INSTRUCTION = "Это не команда и не формула"

def load_jsonl(path):
    """Загружает JSONL файл"""
    data = []
    if not os.path.exists(path):
        print(f"⚠️ Файл не найден: {path}")
        return data

    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                try:
                    data.append(json.loads(line))
                except json.JSONDecodeError as e:
                    print(f"⚠️ Ошибка в {path}: {e}")
    return data

def save_jsonl(data, path):
    """Сохраняет JSONL файл"""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        for item in data:
            f.write(json.dumps(item, ensure_ascii=False) + '\n')

def merge_and_balance(
    command_path="result/command/dataset.jsonl",
    latex_path="result/latex/dataset.jsonl",
    output_dir="result/merged",
    balance_ratio=2,
    max_latex=None,
    shuffle=True
):
    print("=" * 60)
    print("Объединение командного и LaTeX датасетов")
    print("=" * 60)

    # Загружаем датасеты
    commands = load_jsonl(command_path)
    latex = load_jsonl(latex_path)

    print(f"\n📊 Исходные данные:")
    print(f"   Команды: {len(commands)}")
    print(f"   LaTeX: {len(latex)}")

    # Фильтруем команды
    real_commands = []
    for c in commands:
        if c.get("name") != "none":
            text = c.get("rus", "")
            if text and text.strip():
                real_commands.append(c)

    garbage_commands = []
    for c in commands:
        if c.get("name") == "none":
            text = c.get("rus", "")
            if text and text.strip():
                garbage_commands.append(c)

    print(f"\n📊 Команды:")
    print(f"   Реальных (с текстом): {len(real_commands)}")
    print(f"   Garbage (с текстом): {len(garbage_commands)}")

    # Балансируем LaTeX
    target_latex_count = len(real_commands) * balance_ratio

    if max_latex and max_latex < target_latex_count:
        target_latex_count = max_latex

    if len(latex) > target_latex_count:
        latex = random.sample(latex, target_latex_count)
        print(f"\n📊 LaTeX уменьшен до {len(latex)} (баланс 1:{balance_ratio})")
    else:
        print(f"\n📊 LaTeX используется полностью ({len(latex)})")

    # Объединяем
    merged = []

    # Добавляем реальные команды (с явной инструкцией)
    for cmd in real_commands:
        text = cmd.get("rus", "").strip()
        if text:
            merged.append({
                "instruction": random.choice(COMMAND_INSTRUCTIONS),
                "input": text,
                "output": cmd.get("name", "")
            })

    # Добавляем LaTeX примеры
    for lat in latex:
        input_text = lat.get("input", lat.get("rus", lat.get("eng", ""))).strip()
        if not input_text:
            continue

        merged.append({
            "instruction": random.choice(LATEX_INSTRUCTIONS),
            "input": input_text,
            "output": lat.get("output", lat.get("latex", ""))
        })

    # Добавляем garbage (none команды) — тоже с инструкцией
    max_garbage = int(len(merged) * 0.15)
    if len(garbage_commands) > max_garbage:
        garbage_commands = random.sample(garbage_commands, max_garbage)

    for garbage in garbage_commands:
        text = garbage.get("rus", "").strip()
        if text:
            merged.append({
                "instruction": GARBAGE_INSTRUCTION,
                "input": text,
                "output": "none"
            })

    print(f"\n📊 После добавления garbage: +{len([g for g in merged if g['output'] == 'none'])}")

    # Перемешиваем
    if shuffle:
        random.shuffle(merged)

    # Сохраняем
    output_path = os.path.join(output_dir, "dataset.jsonl")
    save_jsonl(merged, output_path)

    # Создаем dataset_info.json
    info = {
        "merged_ds": {
            "file_name": "dataset.jsonl",
            "columns": {
                "prompt": "instruction",
                "query": "input",
                "response": "output"
            }
        }
    }
    info_path = os.path.join(output_dir, "dataset_info.json")
    with open(info_path, "w", encoding="utf-8") as f:
        json.dump(info, f, ensure_ascii=False, indent=2)

    # Создаем объединенные ключевые слова
    keywords = set()

    # Из команд
    for cmd in real_commands:
        text = cmd.get("rus", "")
        words = re.findall(r'\b[a-zA-Zа-яА-Я]{3,}\b', text.lower())
        keywords.update(words)

    # Из LaTeX
    for lat in latex:
        text = lat.get("input", lat.get("rus", lat.get("eng", "")))
        words = re.findall(r'\b[a-zA-Zа-яА-Я]{3,}\b', text.lower())
        keywords.update(words)

    # Добавляем служебные слова (включая слова из инструкций)
    extra_words = {
        # Русские
        "определи", "команду", "тексте", "преобразуй", "формулу", "латех",
        "скрипт", "напиши", "создай", "удали", "выдели", "начни",
        "останови", "отмени", "распознай", "найди", "выдели",
        # Английские
        "convert", "formula", "latex", "script", "write", "create",
        "remove", "highlight", "start", "stop", "undo", "command",
        "identify", "find", "detect", "recognize"
    }
    keywords.update(extra_words)

    # Сохраняем ключевые слова
    keywords_path = os.path.join(output_dir, "keywords.txt")
    with open(keywords_path, "w", encoding="utf-8") as f:
        f.write("\n".join(sorted(keywords)))

    # Статистика
    cmd_in_merged = sum(1 for item in merged if item["output"] not in ["none", ""] and "команду" in item.get("instruction", ""))
    latex_in_merged = sum(1 for item in merged if "формулу" in item.get("instruction", ""))
    garbage_in_merged = sum(1 for item in merged if item["output"] == "none")
    empty_input = sum(1 for item in merged if not item["input"])

    print("\n" + "=" * 60)
    print("✅ Готово!")
    print("=" * 60)
    print(f"\n📊 Итоговый датасет:")
    print(f"   Всего примеров: {len(merged)}")
    print(f"   Команды (inst: {COMMAND_INSTRUCTIONS[0]}): {cmd_in_merged}")
    print(f"   LaTeX (inst: {LATEX_INSTRUCTIONS[0]}): {latex_in_merged}")
    print(f"   Garbage (inst: {GARBAGE_INSTRUCTION}): {garbage_in_merged}")
    print(f"   Пустой input: {empty_input} (должно быть 0)")
    print(f"\n📁 Файлы сохранены в: {output_dir}/")
    print(f"   - dataset.jsonl ({len(merged)} строк)")
    print(f"   - dataset_info.json")
    print(f"   - keywords.txt ({len(keywords)} слов)")

    # Показываем примеры
    print("\n📝 Примеры из объединенного датасета:")
    for item in merged[:5]:
        print(f"   {json.dumps(item, ensure_ascii=False)}")

def main():
    import sys

    balance_ratio = 2
    max_latex = None

    for arg in sys.argv[1:]:
        if arg.startswith("--ratio="):
            balance_ratio = int(arg.split("=")[1])
        elif arg.startswith("--max-latex="):
            max_latex = int(arg.split("=")[1])

    print(f"Параметры:")
    print(f"  Баланс (команда:LaTeX): 1:{balance_ratio}")
    print(f"  Максимум LaTeX: {max_latex if max_latex else 'без ограничений'}")
    print()

    merge_and_balance(
        command_path="result/command/dataset.jsonl",
        latex_path="result/latex/dataset.jsonl",
        output_dir="result/merged",
        balance_ratio=balance_ratio,
        max_latex=max_latex,
        shuffle=True
    )

def create_test_dataset(command_path, latex_path, output_dir, balance_ratio=2, max_latex=None):
    """Создает тестовый датасет"""
    # Загружаем тестовые данные
    commands_test = load_jsonl(os.path.join(os.path.dirname(command_path), "test.jsonl"))
    latex_test = load_jsonl(os.path.join(os.path.dirname(latex_path), "test.jsonl"))

    # Балансируем
    target_latex_count = len(commands_test) * balance_ratio
    if max_latex and max_latex < target_latex_count:
        target_latex_count = max_latex

    if len(latex_test) > target_latex_count:
        latex_test = random.sample(latex_test, target_latex_count)

    # Объединяем
    test_merged = []

    for cmd in commands_test:
        if cmd.get("name") != "none":
            test_merged.append({
                "instruction": random.choice(COMMAND_INSTRUCTIONS),
                "input": cmd.get("rus", "").strip(),
                "output": cmd.get("name", "")
            })

    for lat in latex_test:
        input_text = lat.get("input", lat.get("rus", lat.get("eng", ""))).strip()
        if input_text:
            test_merged.append({
                "instruction": random.choice(LATEX_INSTRUCTIONS),
                "input": input_text,
                "output": lat.get("output", lat.get("latex", ""))
            })

    # Добавляем garbage
    garbage = [cmd for cmd in commands_test if cmd.get("name") == "none"]
    max_garbage = int(len(test_merged) * 0.15)
    if len(garbage) > max_garbage:
        garbage = random.sample(garbage, max_garbage)

    for g in garbage:
        text = g.get("rus", "").strip()
        if text:
            test_merged.append({
                "instruction": GARBAGE_INSTRUCTION,
                "input": text,
                "output": "none"
            })

    # Сохраняем
    output_path = os.path.join(output_dir, "test.jsonl")
    save_jsonl(test_merged, output_path)

    return test_merged

if __name__ == "__main__":
    main()
    test_data = create_test_dataset(
      command_path="result/command/dataset.jsonl",
      latex_path="result/latex/dataset.jsonl",
      output_dir="result/merged"
    )
    print(f"✅ Тестовый датасет: {len(test_data)} примеров")
