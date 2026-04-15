import json
import os

# Пути к вашим файлам
input_file = "scripts/train.json"
output_dir = "scripts"
output_file = os.path.join(output_dir, "latex_alpaca.jsonl")
info_file = os.path.join(output_dir, "dataset_info.json")

def main():
    if not os.path.exists(input_file):
        print(f"Ошибка: Файл {input_file} не найден.")
        return

    # 1. Читаем исходный файл и конвертируем в Alpaca JSONL
    with open(input_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    with open(output_file, "w", encoding="utf-8") as f:
        count = 0
        for item in data:
            # Обработка русского варианта
            if item.get("rus"):
                res_rus = {
                    "instruction": "Convert the following description to LaTeX script.",
                    "input": item["rus"],
                    "output": item["script"]
                }
                f.write(json.dumps(res_rus, ensure_ascii=False) + "\n")
                count += 1

            # Обработка английского варианта
            if item.get("eng"):
                res_eng = {
                    "instruction": "Convert the following description to LaTeX script.",
                    "input": item["eng"],
                    "output": item["script"]
                }
                f.write(json.dumps(res_eng, ensure_ascii=False) + "\n")
                count += 1

    # 2. Создаем файл dataset_info.json
    dataset_info = {
        "latex_ds": {
            "file_name": "latex_alpaca.jsonl",
            "columns": {
                "prompt": "instruction",
                "query": "input",
                "response": "output"
            }
        }
    }

    with open(info_file, "w", encoding="utf-8") as f:
        json.dump(dataset_info, f, ensure_ascii=False, indent=2)

    print(f"Успешно!")
    print(f"- Создано записей в JSONL: {count}")
    print(f"- Файл настроек: {info_file}")
    print(f"- Теперь в YAML используйте dataset: latex_ds и dataset_dir: {output_dir}")

if __name__ == "__main__":
    main()
