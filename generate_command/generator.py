#!/usr/bin/env python3
"""
Генератор датасета команд на основе commands.json

Каждый пример команды:
- действие + объект (синонимы из synonyms.json)
- порядок слов случайный (действие-объект или объект-действие)
- каждый 4-й пример содержит слово шума из noise.json
- каждый глагол-действие используется в исходной форме и в инфинитиве
"""

import json
import random
import argparse
from pathlib import Path
from itertools import product

try:
    import pymorphy2
    MORPHY = pymorphy2.MorphAnalyzer()
    MORPHY_AVAILABLE = True
except ImportError:
    MORPHY_AVAILABLE = False
    print("⚠️ pymorphy2 не найден, инфинитивы не будут генерироваться")


# Пути к файлам
CONFIG_DIR = Path(__file__).parent / "config"
COMMANDS_FILE = CONFIG_DIR / "commands.json"
SYNONYMS_FILE = CONFIG_DIR / "synonyms.json"
GARBAGE_FILE = CONFIG_DIR / "garbage.json"
NOISE_FILE = CONFIG_DIR / "noise.json"

# Выходные пути
# RESULT_DIR = Path(__file__).parent.parent / "result" / "command"
RESULT_DIR = Path(__file__).parent / "result"



def load_data():
    """Загружает все JSON файлы."""
    with open(COMMANDS_FILE, 'r', encoding='utf-8') as f:
        commands = json.load(f)

    with open(SYNONYMS_FILE, 'r', encoding='utf-8') as f:
        synonyms = json.load(f)

    garbage = []
    if GARBAGE_FILE.exists():
        with open(GARBAGE_FILE, 'r', encoding='utf-8') as f:
            garbage_data = json.load(f)
            garbage = garbage_data.get("rus", [])

    noise = []
    if NOISE_FILE.exists():
        with open(NOISE_FILE, 'r', encoding='utf-8') as f:
            noise = json.load(f)

    return commands, synonyms, garbage, noise


def get_infinitive(word):
    """Пытается преобразовать глагол в инфинитив через pymorphy2."""
    if not MORPHY_AVAILABLE:
        return None

    try:
        parsed = MORPHY.parse(word)
        if parsed:
            # Ищем форму в инфинитиве
            for inf in parsed:
                if 'INFN' in str(inf.tag):
                    return inf.normal_form
            # Если не нашли явно инфинитив, пробуем первую форму глагола
            first = parsed[0]
            if 'VERB' in str(first.tag):
                return first.normal_form
    except Exception:
        pass
    return None


def is_verb(word):
    """Проверяет, является ли слово глаголом через pymorphy2."""
    if not MORPHY_AVAILABLE:
        return False
    try:
        parsed = MORPHY.parse(word)
        return parsed and 'VERB' in str(parsed[0].tag)
    except Exception:
        return False


def generate_command_phrases(action_type, object_type, actions, objects, noise):
    """Генерирует все возможные фразы для команды действие+объект."""
    phrases = []

    for action, obj in product(actions, objects):
        # Вариант 1: чистая фраза "действие объект"
        base_forward = f"{action} {obj}"
        phrases.append(base_forward)

        # Вариант 2: чистая фраза "объект действие"
        base_reverse = f"{obj} {action}"
        phrases.append(base_reverse)

        # Вариант 3: инфинитив действия (если возможно)
        infinitive = get_infinitive(action)
        if infinitive and infinitive != action:
            inf_forward = f"{infinitive} {obj}"
            phrases.append(inf_forward)

            inf_reverse = f"{obj} {infinitive}"
            phrases.append(inf_reverse)

        # Вариант 4: с шумом (добавляем каждые 4-й уникальный паттерн)
        # if False:
        if noise:
            noise_word = random.choice(noise)
            # Шум в начале
            noise_forward = f"{noise_word} {action} {obj}"
            phrases.append(noise_forward)

            # Шум между
            noise_middle = f"{action} {noise_word} {obj}"
            phrases.append(noise_middle)

            # Шум в конце
            noise_end = f"{action} {obj} {noise_word}"
            phrases.append(noise_end)

            # То же с обратным порядком
            noise_reverse = f"{noise_word} {obj} {action}"
            # phrases.append(noise_reverse)

            noise_middle_rev = f"{obj} {noise_word} {action}"
            # phrases.append(noise_middle_rev)

            noise_end_rev = f"{obj} {action} {noise_word}"
            # phrases.append(noise_end_rev)

    return phrases


def generate_dataset(commands, synonyms, garbage, noise, garbage_multiplier=0, seed=42):
    """Генерирует полный датасет."""
    random.seed(seed)
    dataset = []
    keywords = set()

    print("📊 Генерация командных фраз...")
    for cmd_name, cmd_config in commands.items():
        action_type = cmd_config["actions"]
        object_type = cmd_config["objects"]

        actions = synonyms["actions"].get(action_type, [])
        objects = synonyms["objects"].get(object_type, [])

        if not actions or not objects:
            print(f"   ⚠️ {cmd_name}: нет синонимов для {action_type} или {object_type}")
            continue

        keywords.add(cmd_name)
        phrases = generate_command_phrases(action_type, object_type, actions, objects, noise)

        for phrase in phrases:
            dataset.append({"name": cmd_name, "rus": phrase})

    # Подсчёт команд
    from collections import Counter
    cmd_counts = Counter(item["name"] for item in dataset)
    total_commands = len(dataset)
    print(f"   Генерировано команд: {total_commands}")
    for cmd, count in sorted(cmd_counts.items(), key=lambda x: x[1], reverse=True):
        print(f"      {cmd}: {count}")

    # Генерация garbage (none)
    target_garbage = total_commands * garbage_multiplier
    print(f"📊 Генерация garbage: цель={target_garbage}, доступно={len(garbage)}")

    # Убираем дубликаты из garbage
    unique_garbage = list(set(garbage))

    # Расширяем garbage если нужно
    extended_garbage = list(unique_garbage)
    while len(extended_garbage) < target_garbage:
        base = random.choice(unique_garbage)
        # Иногда добавляем шум к garbage
        if noise and random.random() < 0.3:
            noise_word = random.choice(noise)
            if random.random() < 0.5:
                extended_garbage.append(f"{noise_word} {base}")
            else:
                extended_garbage.append(f"{base} {noise_word}")
        else:
            extended_garbage.append(base)

    garbage_data = [{"name": "none", "rus": phrase} for phrase in extended_garbage[:target_garbage]]
    dataset.extend(garbage_data)
    print(f"   Добавлено garbage: {len(garbage_data)}")

    # Перемешивание
    random.shuffle(dataset)

    return dataset, sorted(keywords)


def save_dataset(dataset, keywords, train_ratio=0.8):
    """Сохраняет датасет в result/command/ в формате LLaMA-Factory (Alpaca)."""
    split_idx = int(len(dataset) * train_ratio)
    train_data = dataset[:split_idx]
    test_data = dataset[split_idx:]

    # RESULT_DIR.mkdir(exist_ok=True)

    # Формируем данные в формате Alpaca: instruction, input, output
    # instruction: "Распознай команду"
    # input: сама фраза команды
    # output: имя команды (или "none" для garbage)
    def to_alpaca(item):
        return {
            # "instruction": "Распознай команду",
            "input": item["rus"],
            "output": item["name"]
        }

    # Сохраняем train.jsonl
    train_file = RESULT_DIR / "train.jsonl"
    with open(train_file, 'w', encoding='utf-8') as f:
        for item in train_data:
            alpaca = to_alpaca(item)
            f.write(json.dumps(alpaca, ensure_ascii=False) + '\n')

    # Сохраняем test.jsonl
    test_file = RESULT_DIR / "test.jsonl"
    with open(test_file, 'w', encoding='utf-8') as f:
        for item in test_data:
            alpaca = to_alpaca(item)
            f.write(json.dumps(alpaca, ensure_ascii=False) + '\n')

    # Сохраняем dataset_info.json в формате LLaMA-Factory (как в latex проекте)
    info_file = RESULT_DIR / "dataset_info.json"
    info = {
        "command_ds": {
            "file_name": "train.jsonl",
            "columns": {
                "prompt": "instruction",
                "query": "input",
                "response": "output"
            }
        }
    }
    with open(info_file, 'w', encoding='utf-8') as f:
        json.dump(info, f, ensure_ascii=False, indent=2)

    # Сохраняем keywords.txt
    keywords_file = RESULT_DIR / "keywords.txt"
    with open(keywords_file, 'w', encoding='utf-8') as f:
        for kw in keywords:
            f.write(f"{kw}\n")

    print(f"\n✅ Сохранено:")
    print(f"   Train: {len(train_data)} примеров → {train_file}")
    print(f"   Test: {len(test_data)} примеров → {test_file}")
    print(f"   Info: {info_file} (формат LLaMA-Factory)")
    print(f"   Keywords: {keywords_file}")


def generate_command_prompt():
    """Генерирует содержимое command_prompt.txt на основе commands.json и synonyms.json."""
    commands, synonyms, garbage, noise = load_data()

    # Формируем список всех команд с описанием
    action_descriptions = {
        "create": "создать: создание нового элемента",
        "remove": "удалить: удаление элемента",
        "edit": "изменить: редактирование существующего элемента",
        "highlight": "выделить: визуальное выделение элемента",
        "start": "начать: запуск процесса (записи, воспроизведения)",
        "stop": "остановить: прекращение процесса",
        "undo": "отменить: отмена последнего действия",
        "save": "сохранить: сохранение текущего состояния",
        "send": "отправить: отправка элемента"
    }

    object_descriptions = {
        "text": "текст, заметка, документ, контент",
        "paragraph": "абзац, параграф, блок текста",
        "phrase": "фраза, предложение, строчка",
        "word": "отдельное слово",
        "latex": "формула, математическое выражение, скрипт LaTeX",
        "record": "аудиозапись, стрим, голосовое сообщение",
        "command": "предыдущая команда, действие"
    }

    # Формируем список всех команд (command_name: description)
    command_list = []
    for cmd_name, cmd_config in commands.items():
        action = cmd_config["actions"]
        obj = cmd_config["objects"]
        action_desc = action_descriptions.get(action, action)
        obj_desc = object_descriptions.get(obj, obj)
        command_list.append(f"- **{cmd_name}**: {action_desc} + {obj_desc}")

    # Формируем список всех action-синонимов для каждого действия
    actions_list = []
    for action_type, synonyms_list in synonyms["actions"].items():
        actions_list.append(f"- **{action_type}**: {', '.join(synonyms_list[:8])}{'...' if len(synonyms_list) > 8 else ''}")

    # Формируем список всех object-синонимов
    objects_list = []
    for obj_type, synonyms_list in synonyms["objects"].items():
        objects_list.append(f"- **{obj_type}**: {', '.join(synonyms_list[:6])}{'...' if len(synonyms_list) > 6 else ''}")

    # Генерируем примеры команд на основе реальных данных
    example_commands = []
    action_examples = {
        "create": ["создай", "добавь", "новый"],
        "remove": ["удали", "убери", "сотри"],
        "edit": ["исправь", "отредактируй", "поправь"],
        "highlight": ["выдели", "подсвети", "отметь"],
        "start": ["начни", "запусти", "включи"],
        "stop": ["останови", "стоп", "прекрати"],
        "undo": ["отмени", "откати", "верни"],
        "save": ["сохрани", "запиши", "запомни"],
        "send": ["пошли", "вышли", "отправь"]
    }
    obj_examples = {
        "text": ["текст", "заметку", "документ"],
        "paragraph": ["абзац", "параграф", "блок"],
        "phrase": ["фразу", "предложение", "строчку"],
        "word": ["слово", "лексему"],
        "latex": ["формулу", "латех", "математику"],
        "record": ["запись", "аудио", "голос"],
        "command": ["команду", "действие"]
    }

    # Генерируем примеры для каждой команды
    for cmd_name, cmd_config in list(commands.items())[:10]:
        action_type = cmd_config["actions"]
        obj_type = cmd_config["objects"]
        action_syn = action_examples.get(action_type, ["сделай"])
        obj_syn = obj_examples.get(obj_type, ["это"])
        example_commands.append(f"- {action_syn[0]} {obj_syn[0]}")
        example_commands.append(f"- {obj_syn[0]} {action_syn[0]}")

    # Шумовые слова
    noise_examples = noise[:6] if noise else ["тут", "здесь", "быстро", "срочно", "ну", "давай"]

    prompt_content = f"""# Ты — помощник для определения команд в тексте пользователя.

# Промпт для распознавания команд

## Доступные команды

{chr(10).join(command_list)}

## Описание действий

{chr(10).join(actions_list)}

## Описание объектов

{chr(10).join(objects_list)}

## Правила формирования команд

Команды состоят из **действия** и **объекта**.

1. Минимальная команда: **2 слова** (действие + объект)
   - Примеры: "создай текст", "абзац удали", "удалить фразу"

2. Расширенная команда: **3+ слова** (действие + объект + слово шума)
   - Слово шума может быть в любом месте: начале, середине, конце
   - Примеры: "тут создай абзац", "удали здесь текст", "здесь удали фразу тут"

3. Глаголы могут быть в повелительной форме или инфинитиве:
   - "создай текст" или "создать текст"
   - "удали абзац" или "удалить абзац"

4. Порядок слов может быть любым:
   - "создай текст" или "текст создай"

5. Шумовые слова (0-2 шт) могут появляться в любом месте:
   - Примеры шума: {', '.join(noise_examples)}

## Примеры команд

{chr(10).join(example_commands[:12])}

## Не-команды (для обучения отрицания → "none")

Следующие примеры НЕ являются командами и должны классифицироваться как **"none"**:
- бытовые фразы ("помой кота", "купи молоко", "помой маме")
- описательные фразы ("трава зеленая", "небо голубое")
- бессмысленные сочетания ("покорми мусор", "построй воду")
- приветствия и разговорные фразы ("доброе утро", "как дела", "спасибо")

## Формат ответа

Отвечай **ТОЛЬКО** именем команды из списка выше (например: "newText", "removeText", "recordStart") ИЛИ **"none"**, если команда не распознана. Никаких объяснений, никаких дополнительных символов.
"""

    prompt_file = Path(__file__).parent.parent / "docs" / "command_prompt.txt"
    with open(prompt_file, 'w', encoding='utf-8') as f:
        f.write(prompt_content)

    print(f"✅ Промпт сохранён: {prompt_file}")
    print(f"   Команд: {len(commands)}, Действий: {len(synonyms['actions'])}, Объектов: {len(synonyms['objects'])}")


def main():
    parser = argparse.ArgumentParser(description="Генератор датасета команд")
    parser.add_argument("--train-ratio", type=float, default=0.8, help="Доля train данных")
    parser.add_argument("--seed", type=int, default=42, help="Случайное число")
    parser.add_argument("--garbage-multiplier", type=int, default=0, help="Коэффициент garbage (по умолчанию 1x)")
    parser.add_argument("--generate-prompt", action="store_true", help="Сгенерировать command_prompt.txt")
    args = parser.parse_args()

    print("📂 Загрузка данных...")
    commands, synonyms, garbage, noise = load_data()

    print(f"🚀 Генерация датасета (garbage_multiplier={args.garbage_multiplier})...")
    dataset, keywords = generate_dataset(commands, synonyms, garbage, noise, args.garbage_multiplier, args.seed)

    save_dataset(dataset, keywords, args.train_ratio)

    if args.generate_prompt:
        generate_command_prompt()


if __name__ == "__main__":
    main()
