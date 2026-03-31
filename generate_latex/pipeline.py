import os
import json
import random
import requests
import logging
import sys

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

class DatasetPipeline:
    def __init__(self, model_name="qwen-latex"):
        self.model_name = model_name
        self.ollama_url = "http://localhost:11434/api/generate"
        self.data_dir = "data"
        self.result_dir = "result/latex"
        os.makedirs(self.result_dir, exist_ok=True)

        # Загрузка
        self.templates = self.load_json('templates.json')
        self.variables = self.load_json('variables.json').get('vars', [])
        self.math_rules = self.load_json('math_rules.json')

    def load_json(self, filename):
        path = os.path.join(self.data_dir, filename)
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}

    def get_paraphase(self, text, lang="rus"):
        # Очень короткий промпт
        prompt = f"Convert to spoken {lang}: {text}"

        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "stream": False
        }
        try:
            response = requests.post(self.ollama_url, json=payload, timeout=5)
            result = response.json().get('response', '').strip()

            # Если модель все же добавила "The translation is:", отрезаем всё до двоеточия
            if ":" in result:
                result = result.split(":")[-1].strip()

            # Финальная чистка от спецсимволов
            return re.sub(r'[\$\\\(\)\[\]\{\}]', '', result)
        except:
            return text

    def run(self, target_count=10):
        dataset = []
        logging.info(f"Генерация {target_count} примеров...")

        for i in range(target_count):
            # 1. Выбираем случайное правило и переменные
            rule_key = random.choice(list(self.math_rules.keys()))
            rule = self.math_rules[rule_key]
            v1 = random.choice(self.variables)
            v2 = random.choice(self.variables)

            # 2. Собираем базовые тексты из шаблонов
            pattern_type = rule.get('type', 'simple_noun')
            raw_rus = self.templates['rus'][pattern_type].format(noun=rule['rus'], v1=v1['r'], v2=v2['r'])
            raw_eng = self.templates['eng'][pattern_type].format(noun=rule['eng'], v1=v1['e'], v2=v2['e'])

            # 3. Собираем LaTeX (скрипт делает это надежнее модели)
            if "prefix" in pattern_type:
                latex_formula = f"${rule['op']} {v1['l']}$"
            else:
                latex_formula = f"${v1['l']} {rule['op']} {v2['l']}$"

            # 4. Просим модель сделать текст "человечным" (Опционально)
            # Если 1.5B тормозит, можно оставить raw_rus / raw_eng напрямую
            final_rus = self.get_paraphase(raw_rus, "rus")
            final_eng = self.get_paraphase(raw_eng, "eng")

            # 5. Сами формируем JSON - это 100% надежно
            entry = {
                "sec": rule.get("sec", "arithmetic"),
                "rus": final_rus,
                "eng": final_eng,
                "latex": latex_formula
            }

            dataset.append(entry)
            logging.info(f"[{i+1}/{target_count}] Готово: {latex_formula}")

        output_path = os.path.join(self.result_dir, 'stable_dataset.json')
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(dataset, f, ensure_ascii=False, indent=2)
        logging.info(f"Файл сохранен: {output_path}")

if __name__ == "__main__":
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    DatasetPipeline().run(count)
