import json
import os
import random
import shutil
import re


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
    command_path="result_command/commands.jsonl",
    latex_path="result_latex/latex.jsonl",
    output_dir="merged_com_lat",
    balance_ratio=2,  # сколько LaTeX примеров на 1 команду
    max_latex=None,   # максимальное количество LaTeX примеров (None = без ограничения)
    shuffle=True
):
    """
    Объединяет командный и LaTeX датасеты с балансировкой

    Args:
        command_path: путь к файлу команд
        latex_path: путь к файлу LaTeX
        output_dir: выходная директория
        balance_ratio: сколько LaTeX примеров на 1 команду (1 = 1:1, 2 = 1:2, 3 = 1:3)
        max_latex: максимальное количество LaTeX примеров (для ограничения)
        shuffle: перемешивать ли датасет
    """
    print("=" * 60)
    print("Объединение командного и LaTeX датасетов")
    print("=" * 60)

    # Загружаем датасеты
    commands = load_jsonl(command_path)
    latex = load_jsonl(latex_path)

    print(f"\n📊 Исходные данные:")
    print(f"   Команды: {len(commands)}")
    print(f"   LaTeX: {len(latex)}")

    # Фильтруем команды: оставляем только реальные (не none)
    real_commands = [c for c in commands if c.get("name") != "none"]
    garbage_commands = [c for c in commands if c.get("name") == "none"]

    print(f"\n📊 Команды:")
    print(f"   Реальных: {len(real_commands)}")
    print(f"   Garbage: {len(garbage_commands)}")

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

    # Добавляем реальные команды
    for cmd in real_commands:
        merged.append({
            "instruction": "",  # Для команд instruction пустой
            "input": cmd.get("rus", ""),
            "output": cmd.get("name", "")
        })

    # Добавляем LaTeX примеры
    for lat in latex:
        merged.append({
            "instruction": lat.get("instruction", "Преобразуй текст в формулу LaTeX"),
            "input": lat.get("input", lat.get("rus", lat.get("eng", ""))),
            "output": lat.get("output", lat.get("latex", ""))
        })

    # Добавляем garbage (none команды) как отвлекающие примеры
    # Пропорция: garbage не должен превышать 10-20% от общего числа
    max_garbage = int(len(merged) * 0.15)  # 15% garbage
    if len(garbage_commands) > max_garbage:
        garbage_commands = random.sample(garbage_commands, max_garbage)

    for garbage in garbage_commands:
        merged.append({
            "instruction": "",
            "input": garbage.get("rus", ""),
            "output": "none"
        })

    print(f"\n📊 После добавления garbage: +{len(garbage_commands)}")

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

    # Добавляем служебные слова
    extra_words = {
        "преобразуй", "формулу", "латех", "скрипт", "напиши", "создай",
        "удали", "выдели", "начни", "останови", "отмени",
        "convert", "formula", "latex", "script", "write", "create",
        "remove", "highlight", "start", "stop", "undo"
    }
    keywords.update(extra_words)

    # Сохраняем ключевые слова
    keywords_path = os.path.join(output_dir, "keywords.txt")
    with open(keywords_path, "w", encoding="utf-8") as f:
        f.write("\n".join(sorted(keywords)))

    # Статистика
    cmd_in_merged = sum(1 for item in merged if item["output"] not in ["none", ""] and not item["instruction"])
    latex_in_merged = sum(1 for item in merged if item["instruction"] != "")
    garbage_in_merged = sum(1 for item in merged if item["output"] == "none")

    print("\n" + "=" * 60)
    print("✅ Готово!")
    print("=" * 60)
    print(f"\n📊 Итоговый датасет:")
    print(f"   Всего примеров: {len(merged)}")
    print(f"   Команды: {cmd_in_merged}")
    print(f"   LaTeX: {latex_in_merged}")
    print(f"   Garbage: {garbage_in_merged}")
    print(f"\n📁 Файлы сохранены в: {output_dir}/")
    print(f"   - dataset.jsonl ({len(merged)} строк)")
    print(f"   - dataset_info.json")
    print(f"   - keywords.txt ({len(keywords)} слов)")

    # Показываем примеры
    print("\n📝 Примеры из объединенного датасета:")
    for item in merged[:3]:
        print(f"   {json.dumps(item, ensure_ascii=False)}")

def main():
    import sys
    import re  # для извлечения слов

    # Параметры можно передать через аргументы
    balance_ratio = 2  # 1 команда : 2 LaTeX
    max_latex = None   # без ограничения

    # Разбор аргументов
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
        command_path="result_command/commands.jsonl",
        latex_path="result_latex/latex.jsonl",
        output_dir="merged_com_lat",
        balance_ratio=balance_ratio,
        max_latex=max_latex,
        shuffle=True
    )

if __name__ == "__main__":
    main()
