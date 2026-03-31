import os
import json
import random
import requests
import logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

class DatasetGenerator:
    def __init__(self, model_name="qwen-latex"):
        self.model_name = model_name
        self.ollama_url = "http://localhost:11434/api/generate"
        self.data_dir = "data"
        self.result_dir = "result/latex"
        os.makedirs(self.result_dir, exist_ok=True)

        # ЗАГРУЗКА
        self.templates = self.load_json('templates.json')
        # Извлекаем список из ключа "vars"
        vars_data = self.load_json('variables.json')
        self.variables = vars_data.get('vars', [])

        self.math_rules = self.load_json('math_rules.json')

    def load_json(self, filename):
        path = os.path.join(self.data_dir, filename)
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}

    def get_var(self):
        """Возвращает объект переменной: {'r': 'икс', 'e': 'x', 'l': 'x'}"""
        if not self.variables:
            return {"r": "икс", "e": "x", "l": "x"}
        return random.choice(self.variables)

    def generate_raw_description(self):
        rule_key = random.choice(list(self.math_rules.keys()))
        rule = self.math_rules[rule_key]

        # Берем две разные переменные
        v1 = self.get_var()
        v2 = self.get_var()

        # Выбираем тип шаблона из правила (например simple_noun)
        pattern_type = rule.get('type', 'simple_noun')

        # Собираем русский и английский текст, используя поля r (rus) и e (eng) из переменных
        rus_text = self.templates['rus'][pattern_type].format(
            noun=rule['rus'], v1=v1['r'], v2=v2['r']
        )
        eng_text = self.templates['eng'][pattern_type].format(
            noun=rule['eng'], v1=v1['e'], v2=v2['e']
        )

        # Собираем "сырую" формулу для подсказки модели (используя поле l - latex)
        raw_formula = f"{v1['l']} {rule['op']} {v2['l']}"

        return {
            "sec": rule.get("sec", "arithmetic"),
            "input_hint": f"{rus_text} / {eng_text}",
            "formula_hint": raw_formula
        }

    def call_ollama(self, prompt):
        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.0}
        }
        try:
            response = requests.post(self.ollama_url, json=payload, timeout=10)
            raw = response.json().get('response', '')

            # Добавляем скобку
            full_json_str = "{" + raw

            # ИСПРАВЛЕНИЕ: Экранируем обратные слэши, если модель их не экранировала
            # Ищем одиночные слэши, за которыми НЕ следует еще один слэш или кавычка
            import re
            fixed_json = re.sub(r'(?<!\\)\\(?!["\\/bfnrt]|u[0-9a-fA-F]{4})', r'\\\\', full_json_str)

            return json.loads(fixed_json)
        except Exception as e:
            logging.error(f"Ollama error: {e} | Raw string was: {raw}")
            return None


    def run(self, count=10):
        dataset = []
        logging.info(f"Начинаю генерацию {count} примеров...")

        for i in range(count):
            raw = self.generate_raw_description()

            # Формируем четкий промпт для модели
            prompt = f"Topic: {raw['sec']}. Text: {raw['input_hint']}. Math: {raw['formula_hint']}"

            logging.info(f"[{i+1}/{count}] Processing: {raw['input_hint']}")
            result = self.call_ollama(prompt)

            if result:
                dataset.append(result)

        output_path = os.path.join(self.result_dir, 'final_dataset.json')
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(dataset, f, ensure_ascii=False, indent=2)
        logging.info(f"Сохранено {len(dataset)} объектов в {output_path}")

if __name__ == "__main__":
    gen = DatasetGenerator()
    gen.run(count=20)
