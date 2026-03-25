import json
import os
import random
import re

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
    "пожалуйста", "будь добр", "если не сложно", "будьте добры",
    # Срочные/эмоциональные
    "срочно", "немедленно", "быстро", "сейчас же", "немедленно же",
    # Разговорные
    "а ну-ка", "давай-ка", "слушай", "эй", "ну-ка",
    # Усилители
    "я тебе говорю", "сделай", "ну-ка", "давай",
    # Вопросительные
    "можешь", "не мог бы ты", "будь так добр",
]

# Суффиксы для аугментации (русские)
RUS_SUFFIXES = [
    "пожалуйста", "срочно", "быстро", "немедленно", "сейчас же",
]

# Префиксы для аугментации (английские)
ENG_PREFIXES = [
    "please", "could you", "would you", "kindly", "if you don't mind",
    "urgently", "quickly", "right now", "immediately", "now",
    "hey", "listen", "come on", "go ahead",
    "I told you", "just", "go",
]

ENG_SUFFIXES = [
    "please", "urgently", "quickly", "now", "immediately",
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

def generate_garbage(lang="rus", count=500):
    """Генерирует garbage-фразы"""
    if lang == "rus":
        garbage = [
            # Приветствия
            "привет", "здравствуйте", "добрый день", "доброе утро", "добрый вечер",
            # Вопросы
            "как дела", "что нового", "как настроение", "как жизнь", "что случилось",
            # Погода
            "какая погода", "сколько времени", "который час",
            # О себе
            "кто ты", "что ты умеешь", "расскажи о себе", "откуда ты",
            # Просьбы
            "помоги", "подскажи", "объясни", "расскажи",
            # Бессмысленные
            "тра-ля-ля", "ля-ля-ля", "ой-ой-ой", "ай-яй-яй",
            # Эмоциональные
            "ой", "ух", "вау", "ого", "ну и ну",
            # Благодарности
            "спасибо", "благодарю", "merci", "thanks",
            # Прощания
            "пока", "до свидания", "удачи", "всего хорошего",
            # Бытовые
            "купи молока", "сходи в магазин", "принеси воды",
        ]
    else:
        garbage = [
            # Greetings
            "hello", "hi", "good morning", "good evening", "hey",
            # Questions
            "how are you", "what's up", "how's it going", "what's new",
            # Weather/time
            "what's the weather", "what time is it", "what day is it",
            # About self
            "who are you", "what can you do", "tell me about yourself",
            # Requests
            "help", "help me", "tell me", "explain",
            # Nonsense
            "la la la", "tra la la", "oh my", "wow",
            # Emotional
            "oh", "ah", "ouch", "wow",
            # Thanks
            "thank you", "thanks", "merci", "gracias",
            # Farewells
            "bye", "goodbye", "see you", "take care",
        ]

    # Добавляем случайные повторы
    result = []
    for _ in range(count):
        phrase = random.choice(garbage)
        # Иногда добавляем восклицательный знак или вопрос
        if random.random() > 0.7:
            phrase = phrase + random.choice(["!", "?", "!!", "??", "..."])
        result.append(phrase)

    return result

def generate_commands(augment=True, augment_factor=3, garbage_count=500):
    """
    Генерирует датасет команд с аугментацией
    """
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

    return final_data, sorted(list(keywords))

def update_dataset_info():
    """Обновляет dataset_info.json"""
    info_path = "./result_command/dataset_info.json"
    os.makedirs("./result_command", exist_ok=True)

    info = {}
    if os.path.exists(info_path):
        with open(info_path, "r", encoding="utf-8") as f:
            info = json.load(f)

    info["command_ds"] = {
        "file_name": "commands.jsonl",
        "columns": {
            "prompt": "rus",
            "query": "eng",
            "response": "name"
        }
    }

    with open(info_path, "w", encoding="utf-8") as f:
        json.dump(info, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    import sys

    # Параметры
    AUGMENT = "--no-augment" not in sys.argv  # по умолчанию аугментация включена
    AUGMENT_FACTOR = 3  # во сколько раз увеличиваем команды
    GARBAGE_COUNT = 500  # количество garbage-фраз

    print("=" * 60)
    print("Генерация командного датасета")
    print("=" * 60)
    print(f"Аугментация: {'включена' if AUGMENT else 'выключена'}")
    print(f"Коэффициент аугментации: {AUGMENT_FACTOR}")
    print(f"Garbage-фраз: {GARBAGE_COUNT}")
    print()

    # Генерируем датасет
    dataset, kw_list = generate_commands(
        augment=AUGMENT,
        augment_factor=AUGMENT_FACTOR,
        garbage_count=GARBAGE_COUNT
    )

    # Сохраняем
    os.makedirs("./result_command", exist_ok=True)
    with open("./result_command/commands.jsonl", "w", encoding="utf-8") as f:
        for item in dataset:
            f.write(json.dumps(item, ensure_ascii=False) + '\n')

    # Сохраняем ключевые слова
    with open("./result_command/keywords.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(kw_list))

    # Обновляем dataset_info.json
    update_dataset_info()

    # Статистика
    cmd_count = sum(1 for item in dataset if item.get("name") != "none")
    garbage_count_result = len(dataset) - cmd_count

    print("✅ Готово!")
    print(f"   Всего примеров: {len(dataset)}")
    print(f"   Команд: {cmd_count}")
    print(f"   Garbage: {garbage_count_result}")
    print(f"   Ключевых слов: {len(kw_list)}")
    print(f"\nПримеры команд с аугментацией:")
    for item in dataset[:5]:
        if item.get("name") != "none":
            print(f"   {item['rus']} → {item['name']}")
