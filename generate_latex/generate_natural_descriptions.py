import os
import json
import random
import requests
import logging
import re

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

class NaturalDescriptionGenerator:
    def __init__(self, model_name="qwen-latex"):
        self.model_name = model_name
        self.ollama_url = "http://localhost:11434/api/generate"
        self.data_dir = "data"
        self.result_dir = "result/latex"
        os.makedirs(self.result_dir, exist_ok=True)

        # Загружаем справочники
        self.variables = self.load_json('variables.json')  # Ожидаем список ["alpha", "beta", "x", "y"...]
        self.templates = self.load_json('templates.json')  # Ожидаем [{"skeleton": "VAR1 + VAR2", "topic": "algebra"}]

    def load_json(self, filename):
        path = os.path.join(self.data_dir, filename)
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return []

    def inject_variables(self, skeleton):
        """Заменяет плейсхолдеры типа VAR1, VAR2 на случайные переменные из variables.json."""
        if not self.variables:
            return skeleton

        # Ищем все VAR1, VAR2 и т.д.
        placeholders = re.findall(r'VAR\d+', skeleton)
        new_skeleton = skeleton

        # Выбираем уникальный набор переменных для этого примера
        sampled_vars = random.sample(self.variables, min(len(placeholders), len(self.variables)))

        for i, placeholder in enumerate(placeholders):
            if i < len(sampled_vars):
                # Если переменная текстовая (например 'alpha'), оборачиваем в обратный слэш для LaTeX
                var_val = sampled_vars[i]
                if var_val in ["alpha", "beta", "gamma", "theta", "zeta"]: # расширьте список греческих букв
                    var_val = f"\\{var_val}"
                new_skeleton = new_skeleton.replace(placeholder, var_val)

        return f"${new_skeleton}$"

    def call_ollama(self, prompt):
        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.3} # Чуть выше 0 для разнообразия синонимов
        }
        try:
            response = requests.post(self.ollama_url, json=payload, timeout=30)
            raw_text = response.json().get('response', '')
            # Очистка и восстановление JSON (так как в Modelfile стоит принудительный '{')
            clean_text = raw_text.strip()
            if not clean_text.startswith('{'):
                clean_text = "{" + clean_text
            return json.loads(clean_text)
        except Exception as e:
            logging.error(f"Ollama error: {e} | Raw text: {raw_text if 'raw_text' in locals() else 'None'}")
            return None

    def run(self, num_variants=3):
        """Генерирует по N вариантов для каждого шаблона."""
        results = []
        for item in self.templates:
            base_skeleton = item.get('skeleton', '')
            topic = item.get('topic', 'general')

            for _ in range(num_variants):
                final_math = self.inject_variables(base_skeleton)
                prompt = f"Topic: {topic}, Formula: {final_math}"

                logging.info(f"Generating for: {final_math}")
                data = self.call_ollama(prompt)

                if data:
                    results.append(data)

        # Сохранение
        output_path = os.path.join(self.result_dir, 'synthetic_math_dataset.json')
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        logging.info(f"Saved {len(results)} examples to {output_path}")

if __name__ == "__main__":
    gen = NaturalDescriptionGenerator()
    # Генерируем по 5 разных описаний/переменных для каждой формулы
    gen.run(num_variants=5)
