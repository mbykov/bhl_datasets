#!/usr/bin/env python3 -u
"""
Генератор естественных прочтений LaTeX-скриптов
С использованием config файлов и проверкой корректности
С безопасными ограничениями для предотвращения зависаний
"""

import json
import os
import sys
import re
import requests
import random
import time
import signal
import resource
from datetime import datetime

# ========== БЕЗОПАСНОСТЬ ==========
def setup_safety():
    """Настройка безопасности для предотвращения зависаний"""

    # Ограничение памяти (8 GB для безопасности)
    try:
        resource.setrlimit(resource.RLIMIT_AS, (8 * 1024 * 1024 * 1024, 8 * 1024 * 1024 * 1024))
        print("✅ Ограничение памяти: 8 GB", flush=True)
    except Exception as e:
        print(f"⚠️ Не удалось установить ограничение памяти: {e}", flush=True)

    # Ограничение CPU времени (5 минут на запрос)
    try:
        resource.setrlimit(resource.RLIMIT_CPU, (300, 300))
        print("✅ Ограничение CPU: 300 секунд", flush=True)
    except Exception as e:
        print(f"⚠️ Не удалось установить ограничение CPU: {e}", flush=True)

def timeout_handler(signum, frame):
    """Обработчик таймаута"""
    print(f"\n❌ Превышен лимит времени ({signum})", flush=True)
    sys.exit(1)

# Устанавливаем глобальный таймаут (15 минут)
signal.signal(signal.SIGALRM, timeout_handler)
signal.alarm(900)  # 15 минут

# Устанавливаем безопасные лимиты
setup_safety()

# Ограничения через переменные окружения
os.environ['OMP_NUM_THREADS'] = '2'
os.environ['MKL_NUM_THREADS'] = '2'

# Отключаем буферизацию вывода
sys.stdout.reconfigure(line_buffering=True)

# ========== ОСНОВНОЙ КОД ==========

class SimpleGenerator:
    def __init__(self, model="qwen2.5:7b", ollama_url="http://localhost:11434", config_dir='config'):
        self.model = model
        self.ollama_url = ollama_url
        self.session = requests.Session()

        # Загружаем словари из config файлов
        self.greeks = self._load_jsonl(os.path.join(config_dir, 'greeks.jsonl'))
        self.latins = self._load_jsonl(os.path.join(config_dir, 'latins.jsonl'))
        self.symbols = self._load_jsonl(os.path.join(config_dir, 'symbols.jsonl'))
        self.styles_config = self._load_json(os.path.join(config_dir, 'styles.json'))

        # Создаем простые словари замены
        self.rus_map = {}
        self.eng_map = {}

        # Добавляем греческие буквы
        for g in self.greeks:
            self.rus_map[g['sym']] = g['rus']
            self.eng_map[g['sym']] = g['eng']

        # Добавляем символы (используем rus_a/eng_a - академические варианты)
        for s in self.symbols:
            self.rus_map[s['sym']] = s.get('rus_a', s['sym'])
            self.eng_map[s['sym']] = s.get('eng_a', s['sym'])

        # Латинские буквы - берем первый вариант
        self.latin_rus = {l['sym']: l['rus'][0] for l in self.latins}
        self.latin_eng = {l['sym']: l['eng'][0] for l in self.latins}

        # Создаем словарь стилей
        self.styles = {}
        for s in self.styles_config.get('styles', []):
            self.styles[s['name']] = s

        print(f"✅ Загружено символов: rus={len(self.rus_map)}, eng={len(self.eng_map)}", flush=True)
        print(f"✅ Загружено стилей: {len(self.styles)}", flush=True)

    def _load_jsonl(self, path):
        """Загружает JSONL файл"""
        data = []
        try:
            with open(path, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        data.append(json.loads(line))
        except FileNotFoundError:
            print(f"⚠️ Файл {path} не найден", flush=True)
        return data

    def _load_json(self, path):
        """Загружает JSON файл"""
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"⚠️ Файл {path} не найден", flush=True)
            return {"styles": []}

    def check_unknown_symbols(self, latex):
        """Проверяет, есть ли в формуле неизвестные символы"""
        # Собираем все известные символы
        known_symbols = set(self.rus_map.keys()) | set(self.eng_map.keys())
        known_symbols.update([l['sym'] for l in self.latins])
        known_symbols.update([g['sym'] for g in self.greeks])

        # Добавляем специальные случаи, которые обрабатываются отдельно
        known_symbols.add('\\text')
        known_symbols.add('\\text{rot}')
        known_symbols.add('\\text{div}')
        known_symbols.add('\\frac')
        known_symbols.add('\\Box')

        # Находим все LaTeX команды
        commands = re.findall(r'\\([a-zA-Z]+|\W)', latex)
        commands = [f'\\{c}' for c in commands if c]

        # Находим одиночные символы (включая заглавные)
        single_chars = set(re.findall(r'(?<!\\)([a-zA-Z@])\b', latex))

        unknown = []
        for cmd in commands:
            if cmd not in known_symbols and not cmd.startswith('\\text'):
                unknown.append(cmd)

        for ch in single_chars:
            if ch not in [l['sym'] for l in self.latins]:
                unknown.append(ch)

        return unknown

    def normalize(self, latex, lang='rus'):
        """Простая нормализация - замена символов по словарю"""
        text = latex.strip('$')

        # Специальная обработка для \text{rot} и \text{div}
        if '\\text{rot}' in text or '\\text{rot }' in text:
            if lang == 'rus':
                text = text.replace('\\text{rot}', 'ротор')
                text = text.replace('\\text{rot }', 'ротор ')
            else:
                text = text.replace('\\text{rot}', 'rotor')
                text = text.replace('\\text{rot }', 'rotor ')

        if '\\text{div}' in text or '\\text{div }' in text:
            if lang == 'rus':
                text = text.replace('\\text{div}', 'дивергенция')
                text = text.replace('\\text{div }', 'дивергенция ')
            else:
                text = text.replace('\\text{div}', 'divergence')
                text = text.replace('\\text{div }', 'divergence ')

        # Удаляем другие \text команды
        text = re.sub(r'\\text\{[^}]*\}', '', text)

        # Специальная обработка для @
        if lang == 'rus':
            text = text.replace('@', 'эт')
        else:
            text = text.replace('@', 'at')

        if lang == 'rus':
            replacements = self.rus_map
            latin_map = self.latin_rus
        else:
            replacements = self.eng_map
            latin_map = self.latin_eng

        # Заменяем символы (сначала длинные)
        for sym, repl in sorted(replacements.items(), key=lambda x: -len(x[0])):
            text = text.replace(sym, repl)

        # Убираем оставшиеся LaTeX команды
        text = re.sub(r'\\([a-zA-Z]+)', r'\1', text)

        # Заменяем латинские буквы (одиночные, включая заглавные)
        def replace_latin(match):
            letter = match.group(1)
            if letter == '@':
                return 'эт' if lang == 'rus' else 'at'
            return latin_map.get(letter, letter)

        text = re.sub(r'\b([a-zA-Z@])\b', replace_latin, text)

        # Убираем фигурные скобки и лишние пробелы
        text = text.replace('{', ' ').replace('}', ' ')
        text = re.sub(r'\s+', ' ', text).strip()
        text = text.replace('( )', '').replace('()', '')

        return text

    def validate_text(self, text, language):
        """Проверяет, что текст соответствует языку"""
        if not text or len(text) < 2:
            return False

        if language == 'rus':
            # Должны быть русские буквы
            has_cyrillic = bool(re.search(r'[а-яА-ЯёЁ]', text))
            # Не должно быть английских букв
            has_latin = bool(re.search(r'[a-zA-Z]', text))
            return has_cyrillic and not has_latin
        else:  # english
            # Должны быть английские буквы
            has_latin = bool(re.search(r'[a-zA-Z]', text))
            # Не должно быть русских букв
            has_cyrillic = bool(re.search(r'[а-яА-ЯёЁ]', text))
            return has_latin and not has_cyrillic

    def clean_reading(self, text, language):
        """Очищает чтение от лишних символов"""
        # Убираем кавычки в начале и конце
        text = text.strip('"\'')

        # Убираем префиксы
        prefixes = ["Reading:", "Произношение:", "Ответ:", "Result:", "Output:",
                   "Pronunciation:", "Read:", "Formula:"]
        for prefix in prefixes:
            if text.startswith(prefix):
                text = text[len(prefix):].strip()

        # Берем только первую строку
        text = text.split('\n')[0]

        # Убираем лишние пробелы
        text = re.sub(r'\s+', ' ', text).strip()

        return text

    def stylize(self, normalized_text, style_name, lang, max_retries=3):
        """Применяет стиль через LLM с правильным языком промпта"""

        # Задержка перед запросом для предотвращения перегрузки
        time.sleep(0.3)

        style = self.styles.get(style_name, self.styles.get("разговорный"))

        if lang == 'rus':
            rules = style.get('rules_rus', 'Прочитай формулу естественно.')
            example = style.get('example_rus', 'а плюс бэ')

            prompt = f"""Ты помогаешь создать датасет для озвучивания математических формул.

Стиль: {style_name}

Правила стиля:
{rules}

Пример:
Формула: a + b
Произношение: {example}

Твоя задача:
Примени этот стиль к следующей формуле (все символы уже заменены на слова):

Формула: {normalized_text}

Требования:
1. НЕ меняй имена переменных (они уже правильные)
2. НЕ добавляй пояснений, рассуждений, комментариев
3. Выведи ТОЛЬКО произношение на русском языке, без кавычек

Произношение:"""
        else:
            rules = style.get('rules_eng', 'Read the formula naturally.')
            example = style.get('example_eng', 'a plus b')

            prompt = f"""You are helping to create a dataset for math formula speech synthesis.

Style: {style_name}

Rules:
{rules}

Example:
Formula: a + b
Reading: {example}

Your task:
Apply this style to the following formula (all symbols are already replaced with words):

Formula: {normalized_text}

Requirements:
1. DO NOT change variable names (they are already correct)
2. DO NOT add explanations, reasoning, or comments
3. Output ONLY the reading in English, without quotes

Reading:"""

        for attempt in range(max_retries):
            try:
                response = self.session.post(
                    f"{self.ollama_url}/api/generate",
                    json={
                        "model": self.model,
                        "prompt": prompt,
                        "stream": False,
                        "temperature": 0,
                        "keep_alive": 0,
                        "options": {
                            "num_predict": 100,
                            "num_ctx": 512,
                            "stop": ["\n\n", "Объяснение", "Пояснение", "Разберем",
                                    "Давайте", "Explanation", "Note:", "Warning:"]
                        }
                    },
                    timeout=30
                )

                if response.status_code == 200:
                    result = response.json().get('response', '').strip()
                    result = self.clean_reading(result, lang)

                    if self.validate_text(result, lang):
                        return result
                    else:
                        print(f"      ⚠️ Попытка {attempt+1}: некорректный {lang} текст: {result[:50]}...", flush=True)
                        if attempt < max_retries - 1:
                            continue
                        else:
                            return normalized_text
                else:
                    print(f"      ⚠️ Попытка {attempt+1}: ошибка API {response.status_code}", flush=True)

            except Exception as e:
                print(f"      ⚠️ Попытка {attempt+1}: ошибка {e}", flush=True)

            if attempt < max_retries - 1:
                time.sleep(1)

        return normalized_text

    def process_scripts(self, input_path, output_dir, num_symbols=20, checkpoint_every=10):
        """Основной метод обработки скриптов"""
        print(f"📚 Загрузка {input_path}...", flush=True)

        with open(input_path, 'r', encoding='utf-8') as f:
            scripts_data = json.load(f)

        scripts_data = scripts_data[:num_symbols]

        examples = []
        skipped_examples = []

        for entry in scripts_data:
            field = entry.get('field', 'unknown')
            name = entry.get('symbol_name', entry.get('name', 'unknown'))
            for ex_type in ['simple', 'combination', 'outer', 'inner', 'equations']:
                scripts = entry.get(ex_type, [])
                for idx, script in enumerate(scripts):

                    # Проверяем неизвестные символы
                    unknown = self.check_unknown_symbols(script)
                    if unknown:
                        print(f"   ⏭️ Пропуск: {script[:50]}... (неизвестные символы: {unknown})", flush=True)
                        skipped_examples.append({
                            'field': field, 'name': name, 'type': ex_type,
                            'script': script, 'idx': idx, 'reason': f'unknown symbols: {unknown}'
                        })
                        continue

                    need_styling = ex_type != 'simple'
                    style = random.choice(list(self.styles.keys())) if need_styling else None
                    examples.append({
                        'field': field, 'name': name, 'type': ex_type,
                        'script': script, 'idx': idx, 'style': style,
                        'need_styling': need_styling
                    })

        # Сохраняем пропущенные примеры
        if skipped_examples:
            os.makedirs(output_dir, exist_ok=True)
            skipped_path = os.path.join(output_dir, 'skipped.json')
            with open(skipped_path, 'w', encoding='utf-8') as f:
                json.dump(skipped_examples, f, ensure_ascii=False, indent=2)
            print(f"\n⚠️ Пропущено примеров: {len(skipped_examples)} → {skipped_path}", flush=True)

        print(f"📊 Всего примеров к обработке: {len(examples)}", flush=True)

        results = []
        start_time = datetime.now()

        for i, ex in enumerate(examples):
            print(f"\n[{i+1}/{len(examples)}] {ex['name']} ({ex['type']})", flush=True)
            print(f"   Формула: {ex['script'][:60]}", flush=True)

            rus_normalized = self.normalize(ex['script'], 'rus')
            eng_normalized = self.normalize(ex['script'], 'eng')

            print(f"   Норм рус: {rus_normalized[:60]}", flush=True)
            print(f"   Норм eng: {eng_normalized[:60]}", flush=True)

            if ex['need_styling'] and ex['style']:
                rus = self.stylize(rus_normalized, ex['style'], 'rus')
                eng = self.stylize(eng_normalized, ex['style'], 'eng')
                style_used = ex['style']
            else:
                rus = rus_normalized
                eng = eng_normalized
                style_used = "нормализация"

            result = {
                "field": ex['field'], "name": ex['name'], "type": ex['type'],
                "script": ex['script'], "idx": ex['idx'], "style": style_used,
                "rus": rus, "eng": eng
            }
            results.append(result)

            print(f"   → рус: {rus[:80]}", flush=True)
            print(f"   → eng: {eng[:80]}", flush=True)

            if (i + 1) % checkpoint_every == 0:
                os.makedirs(output_dir, exist_ok=True)
                checkpoint_path = os.path.join(output_dir, f'checkpoint_{i+1}.json')
                with open(checkpoint_path, 'w', encoding='utf-8') as f:
                    json.dump(results, f, ensure_ascii=False, indent=2)
                elapsed = (datetime.now() - start_time).total_seconds()
                speed = (i + 1) / elapsed
                print(f"\n💾 Чекпоинт: {i+1} примеров, {speed:.2f} экз/сек", flush=True)

        # Разделяем на train/test
        groups = {}
        for r in results:
            key = (r['field'], r['name'], r['type'])
            if key not in groups:
                groups[key] = []
            groups[key].append(r)

        train_data = []
        test_data = []
        for group_examples in groups.values():
            group_examples.sort(key=lambda x: x['idx'])
            for idx, ex in enumerate(group_examples):
                if idx < 9:
                    train_data.append(ex)
                else:
                    test_data.append(ex)

        # Сохраняем
        os.makedirs(output_dir, exist_ok=True)

        train_path = os.path.join(output_dir, 'train.json')
        test_path = os.path.join(output_dir, 'test.json')

        with open(train_path, 'w', encoding='utf-8') as f:
            json.dump(train_data, f, ensure_ascii=False, indent=2)

        with open(test_path, 'w', encoding='utf-8') as f:
            json.dump(test_data, f, ensure_ascii=False, indent=2)

        total_time = (datetime.now() - start_time).total_seconds()
        print(f"\n✅ Готово за {total_time:.1f} сек!", flush=True)
        print(f"📊 Train: {len(train_data)} → {train_path}", flush=True)
        print(f"📊 Test: {len(test_data)} → {test_path}", flush=True)

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', default='result/scripts.json')
    parser.add_argument('--output-dir', default='result/latex')
    parser.add_argument('--num-symbols', type=int, default=20)
    parser.add_argument('--model', default='qwen2.5:7b')
    parser.add_argument('--checkpoint-every', type=int, default=10)
    args = parser.parse_args()

    generator = SimpleGenerator(model=args.model)
    generator.process_scripts(args.input, args.output_dir, args.num_symbols, args.checkpoint_every)

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n⚠️ Прервано пользователем", flush=True)
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Ошибка: {e}", flush=True)
        import traceback
        traceback.print_exc()
        sys.exit(1)
