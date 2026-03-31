import os, json, random, requests, logging, re, sys

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

class DatasetPipeline:
    def __init__(self, model_name="qwen2.5:7b"):
        self.model_name = model_name
        self.ollama_url = "http://localhost:11434/api/generate"
        self.data_dir = "data"
        self.result_dir = "result/latex"
        self.output_file = os.path.join(self.result_dir, 'final_math_dataset.json')
        os.makedirs(self.result_dir, exist_ok=True)

        self.templates = self.load_json('templates.json')
        self.variables = self.load_json('variables.json').get('vars', [])
        self.math_rules = self.load_json('math_rules.json')

        self.styles = {
            "concise": "Minimalist math. Just variables and operators.",
            "academic": "Textbook style. Use formal terms like 'variables', 'summation'.",
            "action": "Command style. Start with 'Add', 'Multiply', 'Write'.",
            "descriptive": "Explain the result. E.g. 'The result of X after Y'.",
            "question": "Assistant style. Ask: 'What is...?', 'Can you compute...?'"
        }

    def load_json(self, filename):
        path = os.path.join(self.data_dir, filename)
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f: return json.load(f)
        return {}

    def save_batch(self, batch):
        """Дозапись пачки в файл (Checkpointing)."""
        existing_data = []
        if os.path.exists(self.output_file):
            with open(self.output_file, 'r', encoding='utf-8') as f:
                try: existing_data = json.load(f)
                except: existing_data = []

        with open(self.output_file, 'w', encoding='utf-8') as f:
            json.dump(existing_data + batch, f, ensure_ascii=False, indent=2)
        logging.info(f"--- ЧЕКПОИНТ: Всего сохранено {len(existing_data + batch)} ---")

    def get_llm_descriptions(self, rule, vars_list, style_key, latex_ref, rus_base, eng_base):
        system_rules = (
            "You are a math-to-speech engine. Output ONLY JSON. "
            f"STYLE: {self.styles[style_key]}. RULES: "
            "1. Fields: 'rus', 'eng'. 2. No symbols, no LaTeX, only plain text. "
            "3. Variable names MUST match the provided names exactly. 4. Use natural speech."
        )

        v_rus = ", ".join([v['r'] for v in vars_list])
        v_eng = ", ".join([v['e'] for v in vars_list])

        prompt = (
            f"Formula: {latex_ref}\n"
            f"Names to use: Rus({v_rus}), Eng({v_eng})\n"
            f"Draft: Rus({rus_base}), Eng({eng_base})"
        )

        payload = {
            "model": self.model_name,
            "system": system_rules,
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "options": {"temperature": 0.7, "num_predict": 80}
        }

        try:
            r = requests.post(self.ollama_url, json=payload, timeout=25).json()
            res = json.loads(r['response'])
            rus = re.sub(r'[\$\\\(\)\[\]\{\}]', '', res.get('rus', '')).lower().strip()
            eng = re.sub(r'[\$\\\(\)\[\]\{\}]', '', res.get('eng', '')).lower().strip()
            # Чистка галлюцинаций префиксов
            rus = re.sub(r'^(russian|rus|результат|перевод):\s*', '', rus)
            eng = re.sub(r'^(english|eng|result|translation):\s*', '', eng)
            return rus, eng
        except: return None, None

    def run(self, count_per_rule=10):
        checkpoint_size = 50 # Сохраняем каждые 50 примеров
        current_batch = []

        for rule_key, rule in self.math_rules.items():
            logging.info(f">>> Группа: {rule_key}")
            for _ in range(count_per_rule):
                v = random.sample(self.variables, 3)
                p_type = rule.get('type', 'simple_noun')

                # 1. Выбор случайного шаблона из списка
                t_rus = random.choice(self.templates['rus'].get(p_type, self.templates['rus']['simple_noun']))
                t_eng = random.choice(self.templates['eng'].get(p_type, self.templates['eng']['simple_noun']))

                # 2. Сборка базы
                rus_base = t_rus.format(noun=rule['rus'], op_word=rule.get('rus_op', ''), v1=v[0]['r'], v2=v[1]['r'], v3=v[2]['r'])
                eng_base = t_eng.format(noun=rule['eng'], op_word=rule.get('eng_op', ''), v1=v[0]['e'], v2=v[1]['e'], v3=v[2]['e'])

                # 3. Сборка LaTeX
                f = rule['op'].replace("VAR1", v[0]['l']).replace("VAR2", v[1]['l']).replace("VAR3", v[2]['l'])
                f = re.sub(r'VAR\d+', '', f).strip()
                f = re.sub(r'(\\[a-z]+)([a-zA-Z])', r'\1 \2', f) # Пробелы в LaTeX
                latex_ref = f"${f}$"

                # 4. LLM перефраз
                style_key = random.choice(list(self.styles.keys()))
                rus, eng = self.get_llm_descriptions(rule, v, style_key, latex_ref, rus_base, eng_base)

                if rus and eng:
                    current_batch.append({
                        "sec": rule['sec'], "style": style_key,
                        "rus": rus, "eng": eng, "latex": latex_ref
                    })
                    logging.info(f"   [+] {latex_ref} | Style: {style_key}")

                    if len(current_batch) >= checkpoint_size:
                        self.save_batch(current_batch)
                        current_batch = []

        if current_batch:
            self.save_batch(current_batch)
        logging.info("Генерация полностью завершена!")

if __name__ == "__main__":
    # Вызов: uv run pipeline.py 100 (сделает 100 примеров на каждое правило)
    try: count = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    except: count = 10
    DatasetPipeline().run(count)
