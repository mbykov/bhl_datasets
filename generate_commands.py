#!/usr/bin/env python3
"""
Генератор командного датасета с аугментацией и train/test разделением

Структура команд:
- Ядро: глагол + объект (2 слова) — "останови запись", "создай абзац"
- Варианты без глагола: только объект с подразумеваемым действием — "новый параграф"
- Шум: 1 слово префикс ИЛИ 1 слово суффикс — "пожалуйста", "немедленно"

Garbage:
- Сбалансировано 1:1 с командами
- Исключены фразы с ключевыми словами команд
"""

import json
import os
import random
import sys

# Синонимы для генерации команд
SYNONYMS = {
    "rus": {
        "actions": {
            "remove": ["удали", "очисти", "сотри", "убери", "уничтожь", "вырежи", "убери", "избавься", "выкинь", "снеси", "ликвидируй", "дропни", "делитни", "скипни", "выпили", "грохни"],
            "create": ["создай", "начни", "сделай", "добавь", "сгенерируй", "вставь", "запили", "сформулируй", "организуй", "пропиши", "замути", "запиши", "накидай", "сваргань", "новый"],
            "highlight": ["выдели", "подсвети", "отметь", "маркируй", "подчеркни", "обозначь", "акцентируй", "чекай", "выцепи", "замаркай"],
            "start": ["начни", "запусти", "включи", "активируй", "погнали", "давай", "открой", "стартуй", "юзай", "раскручивай"],
            "stop": ["останови", "прекрати", "стоп", "выключи", "заверши", "хватит", "хорош", "пауза", "прерви", "офни", "завязывай", "застопори", "выруби"],
            "undo": ["отмени", "откати", "верни", "назад", "верни как было", "анду", "отмена", "откат"],
            "edit": ["исправь", "отредактируй", "измени", "поправь", "обнови", "переделай", "корректируй", "преобразуй", "редачь", "зачекай", "твикни", "зафикси", "перепиши"]
        },
        "objects": {
            "text": ["текст", "заметка", "запись", "содержимое", "инфа", "контент", "материал", "документ", "статья", "буквы", "текстура", "тело", "инпут"],
            "paragraph": ["абзац", "параграф", "блок", "кусок", "фрагмент", "часть", "абзацик", "раздел"],
            "phrase": ["фраза", "предложение", "строчка", "слово", "выражение"],
            "word": ["слово", "словечко", "лексема"],
            "record": ["запись", "аудио", "стрим", "голос", "голосовуха", "звук", "трек", "войс", "аудиодорожка"],
            "command": ["команда", "действие", "инструкция", "запрос", "задача", "промпт", "директива"],
            "latex": ["формула", "латех", "скрипт", "математика", "выражение", "уравнение"]
        },
        # Короткие слова шума (префиксы)
        "prefixes": ["пожалуйста", "немедленно", "срочно", "быстро", "живо", "ну", "давай", "эх"],
        # "prefixes": ["пожалуйста", "немедленно", "срочно", "быстро", "живо", "ну", "давай", "эх", "слушай", "слышь", "алло", "короче", "плиз", "просто", "в общем", "тут"],
        # Короткие слова шума (суффиксы)
        "suffixes": ["пожалуйста", "срочно", "быстро", "уже", "кстати", "ну"]
        # "suffixes": ["пожалуйста", "срочно", "быстро", "уже", "кстати", "ну", "ок", "ok", "плиз", "плизрез", "да", "ага", "сейчас", "щас", "чекай", "глянь", "плизик"]
    },
    "eng": {
        "actions": {
            "remove": ["remove", "delete", "clear", "erase", "kill", "drop", "cut"],
            "create": ["create", "start", "make", "add", "generate", "insert"],
            "highlight": ["highlight", "mark", "select", "emphasize"],
            "start": ["start", "launch", "begin", "activate", "run"],
            "stop": ["stop", "finish", "end", "terminate", "disable"],
            "undo": ["undo", "revert", "cancel", "reverse"],
            "edit": ["edit", "modify", "change", "update", "correct"]
        },
        "objects": {
            "text": ["text", "note", "record", "content", "input", "data"],
            "paragraph": ["paragraph", "block", "para", "section"],
            "phrase": ["phrase", "sentence", "line"],
            "record": ["recording", "record", "audio", "track"],
            "command": ["command", "action", "instruction"],
            "latex": ["formula", "latex", "script"]
        },
        "prefixes": ["please", "quickly", "now", "immediately", "just", "hey"],
        "suffixes": ["please", "quickly", "now", "already", "ok", "pls"]
    }
}

# Маппинг команд
COMMAND_MAPPING = {
    "text": {"remove": "removeText"},
    "paragraph": {"create": "newPar", "remove": "removePar", "highlight": "hlPar"},
    "phrase": {"remove": "removePhrase", "highlight": "hlPhrase"},
    "record": {"start": "startRecord", "stop": "stopRecord"},
    "command": {"undo": "undoCommand"},
    "latex": {"create": "createLatex", "edit": "editLatex"}
}

# Ядро объектов (для фраз без явного действия)
OBJECT_CORE = {
    "paragraph": ["новый абзац", "новый параграф", "новый блок", "новый отступ"],
    "text": ["новый текст", "новый контент"],
    "latex": ["новая формула", "новый латех"]
}

# Глаголы для garbage (нерелевантные действия)
GARBAGE_VERBS_RUS = ["купи", "сходи", "принеси", "покорми", "позвони", "сделай", "помой", "убери"]
GARBAGE_OBJECTS_RUS = ["молока", "в магазин", "воды", "кота", "маме", "домашку", "посуду", "мусор"]

GARBAGE_VERBS_ENG = ["buy", "go", "bring", "feed", "call", "do", "wash", "clean"]
GARBAGE_OBJECTS_ENG = ["milk", "to the store", "water", "the cat", "mom", "homework", "dishes", "trash"]

# Garbage шаблоны (без ключевых слов команд!)
GARBAGE_PATTERNS_RUS = [
    # Приветствия
    "привет", "здравствуйте", "добрый день", "доброе утро", "добрый вечер", "приветики",
    # Вопросы
    "как дела", "что нового", "как настроение", "что случилось", "ты меня слышишь",
    "почему так", "когда это будет", "зачем ты это", "что происходит",
    # Погода/время
    "какая погода", "сколько времени", "который час", "будет ли дождь", "солнечно сегодня",
    # О себе
    "кто ты", "что ты умеешь", "расскажи о себе", "откуда ты", "ты меня понимаешь",
    # Высказывания
    "мне кажется", "я думаю", "ты любишь котиков", "я устал", "это интересно",
    "мне нужно подумать", "это сложный вопрос", "давай поговорим",
    # Эмоциональные
    "ой", "ух", "вау", "ого", "ну и ну", "спасибо", "благодарю", "пока", "до свидания",
    # Утверждения
    "небо голубое", "трава зеленая", "солнце светит", "зимой холодно", "два плюс два",
    # Бытовые (с нерелевантными глаголами)
]

GARBAGE_PATTERNS_ENG = [
    # Greetings
    "hello", "hi", "good morning", "good evening", "hey", "howdy",
    # Questions
    "how are you", "what's up", "how's it going", "what's new", "do you hear me",
    "why is this", "when will this", "why do you", "what's happening",
    # Weather/time
    "what's the weather", "what time is it", "will it rain", "is it sunny",
    # About self
    "who are you", "what can you do", "tell me about yourself", "where are you from",
    # Statements
    "i think", "i believe", "do you like cats", "i am tired", "this is interesting",
    "i need to think", "that's a question", "let's talk",
    # Emotional
    "oh", "ah", "wow", "oh my", "thank you", "thanks", "bye", "goodbye",
    # Statements
    "the sky is blue", "grass is green", "the sun shines", "winter is cold",
]


def generate_command_core(synonyms, act_key, obj_key, cmd_name):
    """Генерирует ядро команд: глагол + объект"""
    commands = []
    actions = synonyms["actions"][act_key]
    objects = synonyms["objects"][obj_key]

    for action in actions:
        for obj in objects:
            commands.append((f"{action} {obj}", cmd_name))

    return commands


def generate_object_only(synonyms, obj_core):
    """Генерирует команды без явного глагола: только объект с подразумеваемым действием"""
    commands = []
    for phrases in obj_core.values():
        for phrase in phrases:
            # Маппинг по ключевому слову
            if "абзац" in phrase or "параграф" in phrase or "блок" in phrase:
                cmd = "newPar"
            elif "текст" in phrase or "контент" in phrase:
                cmd = "removeText"  # или новая команда
            elif "формула" in phrase or "латех" in phrase:
                cmd = "createLatex"
            else:
                cmd = "none"
            commands.append((phrase, cmd))
    return commands


def augment_command(command_text, synonyms, max_variants=3):
    """
    Упрощённая аугментация: максимум 1 префикс ИЛИ 1 суффикс
    """
    prefixes = synonyms.get("prefixes", [])
    suffixes = synonyms.get("suffixes", [])

    variants = [command_text]  # Оригинал

    # Добавляем префиксы (максимум N)
    for p in random.sample(prefixes, min(max_variants, len(prefixes))):
        variants.append(f"{p} {command_text}")

    # Добавляем суффиксы (максимум N)
    for s in random.sample(suffixes, min(max_variants, len(suffixes))):
        variants.append(f"{command_text} {s}")

    return list(set(variants))


def generate_garbage(synonyms, patterns, count, lang):
    """Генерирует garbage-фразы (не команды)"""
    garbage = list(patterns)

    # Добавляем бытовые фразы с нерелевантными глаголами
    if lang == "rus":
        for _ in range(count // 3):
            verb = random.choice(GARBAGE_VERBS_RUS)
            obj = random.choice(GARBAGE_OBJECTS_RUS)
            garbage.append(f"{verb} {obj}")
    else:
        for _ in range(count // 3):
            verb = random.choice(GARBAGE_VERBS_ENG)
            obj = random.choice(GARBAGE_OBJECTS_ENG)
            garbage.append(f"{verb} {obj}")

    # Добавляем случайные повторы и вариации
    result = []
    for _ in range(count):
        phrase = random.choice(garbage)
        if random.random() > 0.7:
            phrase = phrase + random.choice(["!", "?", "!!", "..."])
        result.append(phrase)

    return result


def generate_commands(augment=True, augment_factor=3, garbage_ratio=1.0, test_ratio=0.1, seed=42):
    """
    Генерирует датасет команд с аугментацией и train/test разделением

    garbage_ratio: соотношение garbage к командам (1.0 = 1:1)
    """
    print("\n" + "="*60)
    print("🎲 ГЕНЕРАЦИЯ КОМАНДНОГО ДАТАСЕТА")
    print("="*60)
    print(f"Аугментация: {'включена' if augment else 'выключена'}")
    print(f"Коэффициент аугментации: {augment_factor}")
    print(f"Garbage ratio: {garbage_ratio} (1.0 = баланс 1:1)")
    print(f"Test ratio: {test_ratio}")
    print("="*60)

    random.seed(seed)

    final_data = []
    keywords = set()

    for lang in ["rus", "eng"]:
        s = SYNONYMS[lang]
        patterns = GARBAGE_PATTERNS_RUS if lang == "rus" else GARBAGE_PATTERNS_ENG

        # Собираем ключевые слова
        for cat in s.values():
            if isinstance(cat, dict):
                for words in cat.values():
                    if isinstance(words, list):
                        keywords.update(words)

        # 1. Ядро команд (глагол + объект)
        all_commands = []
        for obj_key, actions in COMMAND_MAPPING.items():
            for act_key, cmd_name in actions.items():
                if act_key not in s["actions"]:
                    continue
                commands = generate_command_core(s, act_key, obj_key, cmd_name)
                all_commands.extend(commands)

        # 2. Объект без глагола (подразумеваемое действие)
        object_only = generate_object_only(s, OBJECT_CORE)
        all_commands.extend(object_only)

        # Аугментация и сохранение
        for cmd_text, cmd_name in all_commands:
            if augment and lang == "rus":
                variants = augment_command(cmd_text, s, augment_factor)
                for variant in variants:
                    final_data.append({"name": cmd_name, lang: variant})
            else:
                final_data.append({"name": cmd_name, lang: cmd_text})

        # 3. Garbage (сбалансированное количество)
        cmd_count_for_lang = sum(1 for item in final_data if item.get("name") != "none" and item.get(lang))
        garbage_count = int(cmd_count_for_lang * garbage_ratio)

        garbage = generate_garbage(s, patterns, garbage_count, lang)
        for g in garbage:
            final_data.append({"name": "none", lang: g})

    # Перемешиваем
    random.shuffle(final_data)

    # Статистика
    cmd_count = sum(1 for item in final_data if item.get("name") != "none")
    garbage_count_result = len(final_data) - cmd_count

    print(f"\n📊 Статистика генерации:")
    print(f"   Всего примеров: {len(final_data)}")
    print(f"   Команд: {cmd_count}")
    print(f"   Garbage: {garbage_count_result}")
    print(f"   Соотношение: {cmd_count}:{garbage_count_result} ≈ {cmd_count/garbage_count_result if garbage_count_result else 0:.2f}:1")
    print(f"   Ключевых слов: {len(keywords)}")

    # Разделяем на train и test
    random.seed(seed)
    random.shuffle(final_data)
    test_size = int(len(final_data) * test_ratio)
    test_data = final_data[:test_size]
    train_data = final_data[test_size:]

    print(f"\n📁 Разделение данных:")
    print(f"   Train: {len(train_data)} примеров ({int((1-test_ratio)*100)}%)")
    print(f"   Test:  {len(test_data)} примеров ({int(test_ratio*100)}%)")

    return train_data, test_data, sorted(list(keywords))


def update_dataset_info(output_dir="result/command"):
    """Обновляет dataset_info.json"""
    info_path = os.path.join(output_dir, "dataset_info.json")
    os.makedirs(output_dir, exist_ok=True)

    info = {}
    if os.path.exists(info_path):
        with open(info_path, "r", encoding="utf-8") as f:
            info = json.load(f)

    info["command_ds"] = {
        "file_name": "dataset.jsonl",
        "columns": {
            "prompt": "rus",
            "query": "eng",
            "response": "name"
        }
    }

    with open(info_path, "w", encoding="utf-8") as f:
        json.dump(info, f, ensure_ascii=False, indent=2)

    return info_path


def validate_json(filepath, name):
    """Проверяет валидность JSON файла"""
    invalid_count = 0
    with open(filepath, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            try:
                json.loads(line)
            except json.JSONDecodeError as e:
                invalid_count += 1
                print(f"   ❌ {name} строка {line_num}: {e}")
    return invalid_count


def print_samples(data, count=5, name="Примеры"):
    """Показывает примеры из датасета"""
    print(f"\n📝 {name}:")
    shown = 0
    for item in data:
        if item.get("name") != "none":
            lang_key = "rus" if "rus" in item else "eng"
            print(f"   {item.get(lang_key, 'N/A')} → {item['name']}")
            shown += 1
            if shown >= count:
                break
    # Показать несколько garbage
    print(f"   ... (garbage примеры с name='none')")


def generate_dataset(augment=True, augment_factor=3, garbage_ratio=1.0, test_ratio=0.1):
    """
    Основная функция генерации датасета
    """
    train_data, test_data, keywords = generate_commands(
        augment=augment,
        augment_factor=augment_factor,
        garbage_ratio=garbage_ratio,
        test_ratio=test_ratio
    )

    output_dir = "result/command"
    os.makedirs(output_dir, exist_ok=True)

    # Train
    train_path = os.path.join(output_dir, "dataset.jsonl")
    with open(train_path, "w", encoding="utf-8") as f:
        for item in train_data:
            f.write(json.dumps(item, ensure_ascii=False) + '\n')
    print(f"\n✅ Train датасет сохранен: {train_path}")

    # Test
    test_path = os.path.join(output_dir, "test.jsonl")
    with open(test_path, "w", encoding="utf-8") as f:
        for item in test_data:
            f.write(json.dumps(item, ensure_ascii=False) + '\n')
    print(f"✅ Test датасет сохранен: {test_path}")

    # Валидация
    print("\n🔍 Проверка валидности JSON...")
    train_invalid = validate_json(train_path, "Train")
    test_invalid = validate_json(test_path, "Test")

    if train_invalid == 0 and test_invalid == 0:
        print(f"   ✅ Все строки валидны!")
    else:
        print(f"   ⚠️ Ошибок: Train={train_invalid}, Test={test_invalid}")

    # Ключевые слова
    keywords_path = os.path.join(output_dir, "keywords.txt")
    with open(keywords_path, "w", encoding="utf-8") as f:
        f.write("\n".join(keywords))
    print(f"✅ Ключевые слова: {keywords_path} ({len(keywords)} слов)")

    # Конфиг
    info_path = update_dataset_info(output_dir)
    print(f"✅ Конфиг: {info_path}")

    # Примеры
    print_samples(train_data, count=5, name="Примеры (train)")
    print_samples(test_data, count=3, name="Примеры (test)")

    # Статистика по командам
    print("\n📊 Распределение команд:")
    cmd_stats = {}
    for item in train_data:
        name = item.get("name")
        cmd_stats[name] = cmd_stats.get(name, 0) + 1

    for cmd, count in sorted(cmd_stats.items(), key=lambda x: x[1], reverse=True):
        print(f"   {cmd:15} | {count:5}")

    print("\n" + "="*60)
    print("✅ Генерация завершена!")
    print("="*60)

    return train_data, test_data, keywords


if __name__ == "__main__":
    augment = True
    augment_factor = 3
    garbage_ratio = 1.0
    test_ratio = 0.1

    for arg in sys.argv[1:]:
        if arg == "--no-augment":
            augment = False
        elif arg.startswith("--augment-factor="):
            augment_factor = int(arg.split("=")[1])
        elif arg.startswith("--garbage-ratio="):
            garbage_ratio = float(arg.split("=")[1])
        elif arg.startswith("--test-ratio="):
            test_ratio = float(arg.split("=")[1])
        elif arg == "--help":
            print("""
Использование: python generate_commands.py [опции]

Опции:
  --no-augment           Отключить аугментацию
  --augment-factor=N     Коэффициент аугментации (по умолчанию: 3)
  --garbage-ratio=R      Соотношение garbage к командам (по умолчанию: 1.0 = 1:1)
  --test-ratio=R         Доля тестовой выборки (по умолчанию: 0.1)
  --help                 Справка

Примеры:
  python generate_commands.py
  python generate_commands.py --no-augment --garbage-ratio=1.5
  python generate_commands.py --augment-factor=5 --test-ratio=0.2
            """)
            sys.exit(0)

    generate_dataset(
        augment=augment,
        augment_factor=augment_factor,
        garbage_ratio=garbage_ratio,
        test_ratio=test_ratio
    )
