import json
import os
import random

SYNONYMS = {
    "rus": {
        "actions": {
            "remove": ["удали", "очисти", "сотри", "убери", "уничтожь", "вырежи", "убей", "избавься", "ликвидируй", "дропни", "снеси"],
            "create": ["создай", "начни", "сделай", "добавь", "новый", "сгенерируй", "запили", "организуй", "вставь"],
            "highlight": ["выдели", "подсвети", "отметь", "замаркируй", "акцентируй", "маркируй", "подчеркни"],
            "start": ["начни", "запусти", "старт", "включи", "активируй", "вруби"],
            "stop": ["останови", "прекрати", "стоп", "выключи", "заверши", "выруби", "кончай"],
            "undo": ["отмени", "откати", "верни", "аннулируй", "забудь", "назад"],
            "edit": ["исправь", "добавь", "удали", "модифицируй", "отредактируй"]
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
            "edit": ["correct", "add", "delete", "modify", "edit"]
        },
  "objects": {
            "text": ["text", "note", "record", "content", "memo", "input", "data"],
            "paragraph": ["paragraph", "block", "para", "section", "part"],
            "phrase": ["phrase", "sentence", "line", "expression", "quote"],
            "record": ["recording", "record", "protocol", "audio", "track"],
            "command": ["command", "action", "instruction", "order"],
            "latex": ["formula", "latex",  "script"]
        }
    }
}

COMMAND_MAPPING = {
    "text": {"remove": "removeText"},
    "paragraph": {"create": "newPar", "remove": "removePar", "highlight": "hlPar"},
    "phrase": {"remove": "removePhrase", "highlight": "hlPhrase"},
    "record": {"start": "startRecord", "stop": "stopRecord"},
    "command": {"undo": "undoCommand"},
    "latex": {"create": "createLatex", "edit": "editLatex"}
}

def generate():
    final_data = []
    keywords = set()

    for lang in ["rus", "eng"]:
        s = SYNONYMS[lang]
        # Собираем слова для фильтра
        for cat in s.values():
            for words in cat.values():
                keywords.update(words)

        # 1. Положительные команды
        for obj_key, actions in COMMAND_MAPPING.items():
            for act_key, cmd_name in actions.items():
                for a in s["actions"][act_key]:
                    for o in s["objects"][obj_key]:
                        final_data.append({"name": cmd_name, lang: f"{a} {o}".lower()})

        # 2. Негативные (Мусор)
        garbage = ["привет", "как дела", "погода", "кто ты", "купи молока", "system", "assistant"]
        for g in garbage:
            final_data.append({"name": "none", lang: g})

        # 3. Ложные комбинации (Объект без действия и наоборот)
        for _ in range(100):
            obj = random.choice(list(s["objects"].values()))[0]
            final_data.append({"name": "none", lang: f"этот {obj} просто так"})
            act = random.choice(list(s["actions"].values()))[0]
            final_data.append({"name": "none", lang: f"{act} яблоки"})

    return final_data, sorted(list(keywords))

if __name__ == "__main__":
    os.makedirs("./result_commands", exist_ok=True)
    dataset, kw_list = generate()

    with open("./result_commands/commands.jsonl", 'w', encoding='utf-8') as f:
        for item in dataset:
            f.write(json.dumps(item, ensure_ascii=False) + '\n')

    with open("./result_commands/keywords.txt", 'w', encoding='utf-8') as f:
        f.write("\n".join(kw_list))

    info = {"command_ds": {"file_name": "commands.jsonl", "columns": {"prompt": "rus", "query": "eng", "response": "name"}}}
    with open("./result_commands/dataset_info.json", 'w', encoding='utf-8') as f:
        json.dump(info, f, ensure_ascii=False, indent=2)
    print(f"Готово. {len(dataset)} строк.")
