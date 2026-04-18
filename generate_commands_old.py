#!/usr/bin/env python3
"""
Генератор командного датасета с аугментацией и train/test разделением
"""

import json
import os
import random
import re
import sys

# Синонимы для генерации команд
SYNONYMS = {
    "rus": {
        "actions": {
            "remove": ["удали", "очисти", "сотри", "убери", "уничтожь", "вырежи", "убей", "избавься", "ликвидируй", "дропни", "снеси"],
            "create": ["создай", "начни", "сделай", "добавь", "новый", "сгенерируй", "запили", "организуй", "вставь"],
            "highlight": ["выдели", "подсвети", "отметь", "замаркируй", "акцентируй", "маркируй", "подчеркни"],
            "start": ["начни", "запусти", "старт", "включи", "активируй", "вруби"],
            "stop": ["останови", "прекрати", "стоп", "выключи", "заверши", "выруби", "кончай"],
            "undo": ["отмени", "откати", "верни", "аннулируй", "забудь", "назад"],
            "edit": ["исправь", "отредактируй", "модифицируй", "измени", "поправь"]
        },
        "objects": {
            "text": ["текст", "заметку", "запись", "содержимое", "написанное", "инфу", "контент"],
            "paragraph": ["абзац", "параграф", "блок", "отступ", "кусок"],
            "phrase": ["фразу", "предложение", "высказывание", "строчку", "цитату"],
            "record": ["запись", "протокол", "диктофон", "аудио", "стрим", "эфир"],
            "command": ["команду", "действие", "инструкцию", "запрос"],
            "latex": ["формулу", "латех", "скрипт"]
        }
    },
    "eng": {
        "actions": {
            "remove": ["remove", "delete", "clear", "erase", "wipe", "kill", "drop", "cut"],
            "create": ["create", "start", "make", "add", "new", "generate", "produce"],
            "highlight": ["highlight", "mark", "select", "spotlight", "accentuate", "emphasize"],
            "start": ["start", "launch", "begin", "turn on", "activate", "run"],
            "stop": ["stop", "finish", "end", "turn off", "terminate", "disable"],
            "undo": ["undo", "revert", "roll back", "cancel", "reverse"],
            "edit": ["edit", "modify", "change", "correct", "update"]
        },
        "objects": {
            "text": ["text", "note", "record", "content", "memo", "input", "data"],
            "paragraph": ["paragraph", "block", "para", "section", "part"],
            "phrase": ["phrase", "sentence", "line", "expression", "quote"],
            "record": ["recording", "record", "protocol", "audio", "track"],
            "command": ["command", "action", "instruction", "order"],
            "latex": ["formula", "latex", "script"]
        }
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

# Префиксы для аугментации (русские)
RUS_PREFIXES = [
    # Вежливые
    "пожалуйста", "будь добр", "если не сложно", "будьте добры", "будь любезен",
    "не сочти за труд", "если можно", "прошу тебя", "очень прошу",
    # Срочные/эмоциональные
    "срочно", "немедленно", "быстро", "сейчас же", "немедленно же", "поскорее",
    "торопись", "живо", "мигом", "сию секунду",
    # Разговорные
    "а ну-ка", "давай-ка", "слушай", "эй", "ну-ка", "слушай-ка", "эх",
    # Усилители
    "я тебе говорю", "сделай", "давай", "вот", "на", "ну",
    # Вопросительные
    "можешь", "не мог бы ты", "будь так добр", "не мог бы ты",
    # Грубые/эмоциональные (для разнообразия)
    "гад ты этакий", "безобразник", "ну ты и", "чтоб тебя", "что за",
    "какого черта", "тьфу ты", "вот гад", "ну и дела", "идиот",
    # Ласковые
    "милый", "дорогой", "родной", "любимый", "good boy", "умница",
]

# Суффиксы для аугментации (русские)
RUS_SUFFIXES = [
    "пожалуйста", "срочно", "быстро", "немедленно", "сейчас же", "поскорее",
    "очень прошу", "умоляю", "очень нужно", "кстати", "к слову", "вот",
    "наконец-то", "уже", "надоел", "задолбал", "uff", "pls", "plz",
]

# Префиксы для аугментации (английские)
ENG_PREFIXES = [
    "please", "could you", "would you", "kindly", "if you don't mind",
    "urgently", "quickly", "right now", "immediately", "now", "ASAP",
    "hey", "listen", "come on", "go ahead", "look here",
    "I told you", "just", "go", "for God's sake", "for pity's sake",
    # Emotional
    "dammit", "goddamn", "damn", "bloody hell", "what the hell",
    # Nice
    "dear", "darling", "sweetheart", "my dear",
]

ENG_SUFFIXES = [
    "please", "urgently", "quickly", "now", "immediately", "ASAP",
    "will you", "won't you", "would you", "can you", "please do",
    "for me", "now", "already", "already will ya",
]

def augment_command(text, lang="rus", max_variants=5):
    """
    Генерирует варианты одной команды с префиксами и суффиксами
    """
    if lang == "rus":
        prefixes = RUS_PREFIXES
        suffixes = RUS_SUFFIXES
    else:
        prefixes = ENG_PREFIXES
        suffixes = ENG_SUFFIXES

    variants = [text]  # Оригинал

    # Добавляем префиксы
    for p in random.sample(prefixes, min(max_variants, len(prefixes))):
        variants.append(f"{p} {text}")

    # Добавляем суффиксы
    for s in random.sample(suffixes, min(max_variants, len(suffixes))):
        variants.append(f"{text} {s}")

    # Комбинации (меньше, чтобы не раздувать сильно)
    for p in random.sample(prefixes, min(max_variants // 2, len(prefixes))):
        for s in random.sample(suffixes, min(2, len(suffixes))):
            variants.append(f"{p} {text} {s}")

    # Убираем дубликаты
    return list(set(variants))

def generate_garbage(lang="rus", count=800):
    """Генерирует garbage-фразы — сложные не-команды для обучения"""
    if lang == "rus":
        garbage = [
            # Приветствия
            "привет", "здравствуйте", "добрый день", "доброе утро", "добрый вечер", "приветики",
            # Вопросы
            "как дела", "что нового", "как настроение", "как жизнь", "что случилось", "ты меня слышишь",
            "почему так происходит", "когда это закончится", "зачем ты это делаешь",
            # Погода/время
            "какая погода", "сколько времени", "который час", "будет ли дождь", "солнечно сегодня",
            # О себе /LM
            "кто ты", "что ты умеешь", "расскажи о себе", "откуда ты", "ты живой", "ты меня понимаешь",
            # Высказывания (не команды)
            "мне кажется завтра будет дождь", "ты любишь котиков", "я устал сегодня",
            "это очень интересно", "ну и дела", "вот это поворот",
            "мне нужно подумать", "это сложный вопрос", "давай поговорим о музыке",
            "что ты думаешь о политике", "какой сегодня день недели",
            # Бессмысленные
            "тра-ля-ля", "ля-ля-ля", "ой-ой-ой", "ай-яй-яй", "бамбам", "криминальное чтиво",
            # Эмоциональные
            "ой", "ух", "вау", "ого", "ну и ну", "ничего себе", "ого-го", "ай-ай-ай",
            # Благодарности
            "спасибо", "благодарю", "merci", "thanks", "спасибо большое", "очень признателен",
            # Прощания
            "пока", "до свидания", "удачи", "всего хорошего", "увидимся", "до скорого",
            # Бытовые (не команды)
            "купи молока", "сходи в магазин", "принеси воды", "покорми кота", "позвони маме",
            "сделай домашку", "постирай посуду", "вынеси мусор",
            # Утверждения
            "небо голубое", "трава зеленая", "солнце светит", "зимой холодно",
            "два плюс два четыре", "море синее", "кофе бодрит",
            # Сложные фразы
            "мне нужно поговорить с тобой о важном деле",
            "ты знаешь, как решить эту задачу",
            "расскажи мне что-нибудь интересное",
            "что ты можешь предложить для улучшения",
            "как правильно написать эту программу",
        ]
    else:
        garbage = [
            # Greetings
            "hello", "hi", "good morning", "good evening", "hey", "howdy",
            # Questions
            "how are you", "what's up", "how's it going", "what's new", "do you hear me",
            "why is this happening", "when will this end", "why do you do this",
            # Weather/time
            "what's the weather", "what time is it", "what day is it", "will it rain", "is it sunny",
            # About self
            "who are you", "what can you do", "tell me about yourself", "where are you from", "are you alive",
            # Statements (not commands)
            "i think it will rain tomorrow", "do you like cats", "i am tired today",
            "this is very interesting", "wow", "what a twist",
            "i need to think about this", "that's a tough question", "let's talk about music",
            "what do you think about politics", "what day is it today",
            # Nonsense
            "la la la", "tra la la", "oh my", "wow", "bambam", "oops",
            # Emotional
            "oh", "ah", "ouch", "wow", "no way", "oh no", "gee whiz",
            # Thanks
            "thank you", "thanks", "merci", "gracias", "thank you very much", "i appreciate it",
            # Farewells
            "bye", "goodbye", "see you", "take care", "later", "catch you later",
            # Statements
            "the sky is blue", "grass is green", "the sun is shining", "winter is cold",
            "two plus two is four", "the sea is blue", "coffee gives me energy",
            # Complex phrases
            "i need to talk to you about something important",
            "do you know how to solve this problem",
            "tell me something interesting",
            "what can you suggest for improvement",
            "how do i write this program correctly",
        ]

    # Добавляем случайные повторы и вариации
    result = []
    for _ in range(count):
        phrase = random.choice(garbage)
        # Иногда добавляем восклицательный знак или вопрос
        if random.random() > 0.7:
            phrase = phrase + random.choice(["!", "?", "!!", "??", "...", ";)"])
        result.append(phrase)

    return result

def generate_commands(augment=True, augment_factor=15, garbage_count=800, test_ratio=0.1, seed=42):
    """
    Генерирует датасет команд с аугментацией и train/test разделением
    """
    print("\n" + "="*60)
    print("🎲 ГЕНЕРАЦИЯ КОМАНДНОГО ДАТАСЕТА")
    print("="*60)
    print(f"Аугментация: {'включена' if augment else 'выключена'}")
    print(f"Коэффициент аугментации: {augment_factor}")
    print(f"Garbage-фраз: {garbage_count}")
    print(f"Test ratio: {test_ratio}")
    print("="*60)

    random.seed(seed)

    final_data = []
    keywords = set()

    for lang in ["rus", "eng"]:
        s = SYNONYMS[lang]

        # Собираем ключевые слова
        for cat in s.values():
            for words in cat.values():
                keywords.update(words)

        # 1. Положительные команды (с аугментацией)
        for obj_key, actions in COMMAND_MAPPING.items():
            for act_key, cmd_name in actions.items():
                # Проверяем, есть ли такое действие в синонимах
                if act_key not in s["actions"]:
                    continue
                for a in s["actions"][act_key]:
                    for o in s["objects"][obj_key]:
                        command_text = f"{a} {o}".lower()

                        if augment and lang == "rus":
                            # Только русские команды аугментируем
                            variants = augment_command(command_text, lang, augment_factor)
                            for variant in variants:
                                final_data.append({
                                    "name": cmd_name,
                                    lang: variant
                                })
                        else:
                            final_data.append({
                                "name": cmd_name,
                                lang: command_text
                            })

        # 2. Негативные (мусор)
        garbage = generate_garbage(lang, garbage_count)
        for g in garbage:
            final_data.append({
                "name": "none",
                lang: g
            })

        # 3. Ложные комбинации (объект без действия и наоборот)
        for _ in range(100):
            obj = random.choice(list(s["objects"].values()))[0]
            final_data.append({
                "name": "none",
                lang: f"этот {obj} просто так"
            })
            act = random.choice(list(s["actions"].values()))[0]
            final_data.append({
                "name": "none",
                lang: f"{act} яблоки"
            })

    # Перемешиваем датасет
    random.shuffle(final_data)

    # Статистика
    cmd_count = sum(1 for item in final_data if item.get("name") != "none")
    garbage_count_result = len(final_data) - cmd_count

    print(f"\n📊 Статистика генерации:")
    print(f"   Всего примеров: {len(final_data)}")
    print(f"   Команд: {cmd_count}")
    print(f"   Garbage: {garbage_count_result}")
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
            print(f"   {item.get('rus', 'N/A')} → {item['name']}")
            shown += 1
            if shown >= count:
                break

def generate_dataset(augment=True, augment_factor=15, garbage_count=800, test_ratio=0.1):
    """
    Основная функция генерации датасета
    """
    # Генерируем данные
    train_data, test_data, keywords = generate_commands(
        augment=augment,
        augment_factor=augment_factor,
        garbage_count=garbage_count,
        test_ratio=test_ratio
    )

    # Создаем директории
    output_dir = "result/command"
    os.makedirs(output_dir, exist_ok=True)

    # Сохраняем train датасет
    train_path = os.path.join(output_dir, "dataset.jsonl")
    with open(train_path, "w", encoding="utf-8") as f:
        for item in train_data:
            f.write(json.dumps(item, ensure_ascii=False) + '\n')
    print(f"\n✅ Train датасет сохранен: {train_path}")

    # Сохраняем test датасет
    test_path = os.path.join(output_dir, "test.jsonl")
    with open(test_path, "w", encoding="utf-8") as f:
        for item in test_data:
            f.write(json.dumps(item, ensure_ascii=False) + '\n')
    print(f"✅ Test датасет сохранен: {test_path}")

    # Проверяем валидность
    print("\n🔍 Проверка валидности JSON...")
    train_invalid = validate_json(train_path, "Train")
    test_invalid = validate_json(test_path, "Test")

    if train_invalid == 0 and test_invalid == 0:
        print(f"   ✅ Все строки валидны!")
    else:
        print(f"   ⚠️ Найдено ошибок: Train={train_invalid}, Test={test_invalid}")

    # Сохраняем ключевые слова
    keywords_path = os.path.join(output_dir, "keywords.txt")
    with open(keywords_path, "w", encoding="utf-8") as f:
        f.write("\n".join(keywords))
    print(f"✅ Ключевые слова сохранены: {keywords_path} ({len(keywords)} слов)")

    # Обновляем dataset_info.json
    info_path = update_dataset_info(output_dir)
    print(f"✅ Конфиг сохранен: {info_path}")

    # Показываем примеры
    print_samples(train_data, count=5, name="Примеры команд (train)")
    print_samples(test_data, count=3, name="Примеры команд (test)")

    # Статистика по командам
    print("\n📊 Распределение команд:")
    cmd_stats = {}
    for item in train_data:
        name = item.get("name")
        if name != "none":
            cmd_stats[name] = cmd_stats.get(name, 0) + 1

    for cmd, count in sorted(cmd_stats.items(), key=lambda x: x[1], reverse=True):
        print(f"   {cmd:15} | {count:5} примеров")

    print("\n" + "="*60)
    print("✅ Генерация командного датасета завершена!")
    print("="*60)

    return train_data, test_data, keywords

def generate_dataset_with_custom_params(augment=True, augment_factor=3, garbage_count=500, test_ratio=0.1):
    """
    Генерация с пользовательскими параметрами (алиас для основной функции)
    """
    return generate_dataset(augment, augment_factor, garbage_count, test_ratio)

if __name__ == "__main__":
    # Парсим аргументы командной строки
    augment = True
    augment_factor = 15
    garbage_count = 500
    test_ratio = 0.1

    for arg in sys.argv[1:]:
        if arg == "--no-augment":
            augment = False
        elif arg.startswith("--augment-factor="):
            augment_factor = int(arg.split("=")[1])
        elif arg.startswith("--garbage="):
            garbage_count = int(arg.split("=")[1])
        elif arg.startswith("--test-ratio="):
            test_ratio = float(arg.split("=")[1])
        elif arg == "--help":
            print("""
Использование: python generate_commands.py [опции]

Опции:
  --no-augment              Отключить аугментацию (по умолчанию включена)
  --augment-factor=N        Коэффициент аугментации (по умолчанию: 3)
  --garbage=N               Количество garbage-фраз (по умолчанию: 500)
  --test-ratio=R            Доля тестовой выборки (по умолчанию: 0.1)
  --help                    Показать эту справку

Примеры:
  python generate_commands.py
  python generate_commands.py --no-augment
  python generate_commands.py --augment-factor=5 --garbage=1000
  python generate_commands.py --test-ratio=0.2
            """)
            sys.exit(0)

    # Запускаем генерацию
    generate_dataset_with_custom_params(
        augment=augment,
        augment_factor=augment_factor,
        garbage_count=garbage_count,
        test_ratio=test_ratio
    )
