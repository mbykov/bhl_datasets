#!/usr/bin/env python3 -u
"""
Генератор естественных прочтений LaTeX-скриптов
Версия 5.0 - с правильным произношением дифференциала "дэ"
"""

import json
import os
import sys
import re
import requests
import random
import time
import subprocess
from datetime import datetime
from typing import List, Dict, Optional

# ========== ЖЁСТКИЙ ВЫБОР GPU ==========
def select_gpu():
    result = subprocess.run(
        ['nvidia-smi', '--query-gpu=name,index', '--format=csv,noheader'],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print("❌ NVIDIA GPU не обнаружена!", flush=True)
        sys.exit(1)

    gpus = []
    for line in result.stdout.strip().split('\n'):
        if line:
            name, idx = line.rsplit(',', 1)
            gpus.append({'name': name.strip(), 'index': int(idx.strip())})

    target_gpu = None
    for gpu in gpus:
        if '5060' in gpu['name']:
            target_gpu = gpu
            break

    if not target_gpu:
        print("❌ RTX 5060 Ti не найдена!", flush=True)
        sys.exit(1)

    os.environ['CUDA_VISIBLE_DEVICES'] = str(target_gpu['index'])
    print(f"✅ Выбрана GPU: {target_gpu['name']}", flush=True)
    return target_gpu

select_gpu()


class TextGenerator:
    def __init__(self, model="qwen2.5:7b", ollama_url="http://localhost:11434", config_dir='config'):
        self.model = model
        self.ollama_url = ollama_url
        self.session = requests.Session()
        self._load_dictionaries(config_dir)

    def _load_dictionaries(self, config_dir):
        # Загружаем греческие буквы
        self.greeks = self._load_jsonl(os.path.join(config_dir, 'greeks.jsonl'))
        self.greek_rus = {}
        self.greek_eng = {}
        for g in self.greeks:
            self.greek_rus[g['sym']] = g.get('rus', g['sym'])
            self.greek_eng[g['sym']] = g.get('eng', g['sym'])

        # Заглавные греческие для русского (должны быть строчными)
        self.greek_upper_rus = {
            'Гамма': 'гамма',
            'Дельта': 'дельта',
            'Тета': 'тета',
            'Лямбда': 'лямбда',
            'Кси': 'кси',
            'Пи': 'пи',
            'Сигма': 'сигма',
            'Ипсилон': 'ипсилон',
            'Фи': 'фи',
            'Пси': 'пси',
            'Омега': 'омега',
        }

        # Загружаем латинские буквы
        self.latins = self._load_jsonl(os.path.join(config_dir, 'latins.jsonl'))
        self.latin_rus = {}
        self.latin_eng = {}
        for l in self.latins:
            sym = l['sym']
            if sym == '@':
                continue
            rus_list = l.get('rus', [''])
            eng_list = l.get('eng', [''])
            self.latin_rus[sym] = rus_list[0] if rus_list else sym
            self.latin_eng[sym] = eng_list[0] if eng_list else sym

        # Загружаем символы
        self.symbols = self._load_jsonl(os.path.join(config_dir, 'symbols.jsonl'))
        self.rus_map = {}
        self.eng_map = {}
        for s in self.symbols:
            self.rus_map[s['sym']] = s.get('rus', s['sym'])
            self.eng_map[s['sym']] = s.get('eng', s['sym'])

        print(f"✅ Загружено словарей", flush=True)

    def _load_jsonl(self, path):
        data = []
        try:
            with open(path, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        data.append(json.loads(line))
        except FileNotFoundError:
            pass
        return data

    def normalize(self, latex: str, lang: str) -> str:
        """Нормализация LaTeX в текст"""
        text = latex.strip('$')

        symbol_map = self.rus_map if lang == 'rus' else self.eng_map
        greek_map = self.greek_rus if lang == 'rus' else self.greek_eng
        latin_map = self.latin_rus if lang == 'rus' else self.latin_eng

        # 1. Замена символов (длинные команды сначала)
        for sym, repl in sorted(symbol_map.items(), key=lambda x: -len(x[0])):
            text = text.replace(sym, repl)

        # 2. Замена греческих букв
        for sym, name in greek_map.items():
            text = text.replace(sym, name)

        # 3. Замена латинских букв
        for letter, name in latin_map.items():
            text = re.sub(rf'\b{re.escape(letter)}\b', name, text)

        # 4. Убираем оставшиеся LaTeX команды
        text = re.sub(r'\\([a-zA-Z]+)', r'\1', text)

        # 5. Убираем фигурные скобки
        text = text.replace('{', ' ').replace('}', ' ')

        # 6. Обработка дифференциала d x
        if lang == 'rus':
            # d x → дэ икс (с пробелом)
            text = re.sub(r'd\s+([a-zA-Zα-ω]+)', r'дэ \1', text)
            # dX → дэ икс (без пробела)
            text = re.sub(r'd([a-zA-Zα-ω]+)', r'дэ \1', text)
            # Одиночное d
            text = re.sub(r'\bd\b', 'дэ', text)
        else:
            # d x → d x (читается как "ди икс")
            text = re.sub(r'd\s+([a-zA-Zα-ω]+)', r'd \1', text)
            text = re.sub(r'd([a-zA-Zα-ω]+)', r'd \1', text)
            text = re.sub(r'\bd\b', 'd', text)

        # 7. Обработка индексов интегралов: \int_{a}^{b} → "от a до b"
        text = re.sub(r'нижний индекс\s+(\S+)\s+степень\s+(\S+)', r'от \1 до \2', text)
        text = re.sub(r'нижний индекс\s+(\S+)', r'от \1', text)

        # 8. Для русского - заглавные греческие в строчные
        if lang == 'rus':
            for upper, lower in self.greek_upper_rus.items():
                text = text.replace(upper, lower)
            # Убираем слово "заглавная"
            text = text.replace('заглавная', '').strip()

        # 9. Очищаем пробелы
        text = re.sub(r'\s+', ' ', text).strip()

        return text

    def stylize(self, normalized_text: str, style_name: str, lang: str) -> str:
        """Стилизация через LLM с жёсткими правилами"""

        if lang == 'rus':
            # Запрещённые символы для русского
            forbidden_chars = r'[a-zA-Z\\$_{}]'

            prompt = f"""Ты - стилизатор математических формул для голосового чтения.

Исходный текст (уже нормализован): {normalized_text}

Стиль: {style_name}

ПРАВИЛА ДЛЯ СТИЛЯ "{style_name}":
- разговорный: кратко, как в устной речи. "плюс", "минус", "на". НЕ использовать скобки.
  Для интеграла: "интеграл икс дэ икс" (без "от")
- академический: точно, формально. "сумма", "частное", "определенный интеграл".
  Для интеграла: "интеграл от икс дэ икс" (с "от")
- формально-логический: проговаривать каждую скобку, уточнять "переменная", "константа".
  Для интеграла: "интеграл в пределах от а до бэ функции эф от икс дэ икс"

ЖЁСТКИЕ ЗАПРЕТЫ (НАРУШЕНИЯ НЕДОПУСТИМЫ):
- НЕ используй LaTeX-команды (\\, $, \\(, \\), _, ^, {{, }})
- НЕ используй латинские буквы - только русские
- НЕ добавляй "равно", "дает", "значение", "результат"
- НЕ вычисляй интегралы, производные или выражения
- НЕ меняй порядок слов
- НЕ добавляй комментарии
- НЕ заменяй "дэ" на "по" - "дэ" это правильное произношение дифференциала

РАЗРЕШЕНО ТОЛЬКО:
- Изменять падежи (синус → синуса)
- Использовать синонимы (плюс → сложить)
- Для формально-логического: добавлять "открывается скобка"/"закрывается скобка"
- Для академического: добавлять "от" перед интегралом

Твой ответ (ТОЛЬКО стилизованный текст на русском, без пояснений):
"""
        else:  # english
            forbidden_chars = r'[а-яё\\$_{}]'

            prompt = f"""You are a formula stylizer for voice reading.

Input text (already normalized): {normalized_text}

Style: {style_name}

RULES FOR "{style_name}":
- conversational: short, spoken style. "plus", "minus", "over". NO parentheses.
  For integral: "integral x d x" (no "of")
- academic: precise, formal. "sum", "quotient", "definite integral".
  For integral: "integral of x d x" (with "of")
- formal-logical: articulate every parenthesis, specify "variable", "constant".
  For integral: "integral ranging from a to b of function f of x d x"

STRICT FORBIDDEN:
- NO LaTeX commands (\\, $, \\(, \\), _, ^, {{, }})
- NO Cyrillic letters - only English
- NO "equals", "gives", "value", "result"
- NO computing integrals, derivatives, or expressions
- NO changing word order
- NO comments

ALLOWED ONLY:
- Change word cases (sine → sine's)
- Use synonyms (plus → add)
- For formal-logical: add "open parenthesis"/"close parenthesis"
- For academic: add "of" before integral

Your answer (ONLY styled English text, no explanations):
"""

        for attempt in range(3):
            try:
                response = self.session.post(
                    f"{self.ollama_url}/api/generate",
                    json={
                        "model": self.model,
                        "prompt": prompt,
                        "stream": False,
                        "temperature": 0.1,
                        "options": {
                            "num_predict": 150,
                            "num_ctx": 512
                        }
                    },
                    timeout=20
                )

                if response.status_code == 200:
                    result = response.json().get('response', '').strip()

                    # Очистка от LaTeX
                    result = re.sub(r'\\[a-zA-Z]+', '', result)
                    result = re.sub(r'[$_{}]', '', result)
                    result = re.sub(r'\\\(|\\\)', '', result)

                    # Проверка на запрещённые символы
                    if re.search(forbidden_chars, result):
                        if attempt < 2:
                            continue
                        result = re.sub(forbidden_chars, '', result)

                    result = result.split('\n')[0]
                    result = re.sub(r'\s+', ' ', result).strip()

                    if result and len(result) > 3 and len(result) < len(normalized_text) * 2:
                        return result

            except Exception as e:
                if attempt < 2:
                    time.sleep(1)

        return normalized_text

    def process_file(self, input_path: str, output_dir: str, num_examples: int = None):
        print(f"\n📚 Загрузка {input_path}...", flush=True)

        examples = []
        with open(input_path, 'r', encoding='utf-8') as f:
            for idx, line in enumerate(f):
                if line.strip():
                    if num_examples and idx >= num_examples:
                        break
                    data = json.loads(line)
                    examples.append({
                        'idx': idx,
                        'sec': data.get('sec', ''),
                        'sym': data.get('sym', ''),
                        'rus_name': data.get('rus', ''),
                        'eng_name': data.get('eng', ''),
                        'script': data.get('script', ''),
                        'scheme': data.get('scheme', ''),
                    })

        print(f"📊 Загружено: {len(examples)} примеров", flush=True)

        all_results = []
        start_time = datetime.now()

        styles = ['разговорный', 'академический', 'формально-логический']

        for i, example in enumerate(examples):
            print(f"\n📝 [{i+1}/{len(examples)}] {example['script'][:50]}...", flush=True)

            # Нормализация
            rus_norm = self.normalize(example['script'], 'rus')
            eng_norm = self.normalize(example['script'], 'eng')

            print(f"   rus_norm: {rus_norm[:80]}", flush=True)

            # Генерация трёх стилей для каждого языка
            for style in styles:
                rus_styled = self.stylize(rus_norm, style, 'rus')
                eng_styled = self.stylize(eng_norm, style, 'eng')

                all_results.append({
                    "sec": example['sec'],
                    "sym": example['sym'],
                    "rus_name": example['rus_name'],
                    "eng_name": example['eng_name'],
                    "script": example['script'],
                    "scheme": example['scheme'],
                    "idx": example['idx'],
                    "style": style,
                    "normalized_rus": rus_norm,
                    "normalized_eng": eng_norm,
                    "rus": rus_styled,
                    "eng": eng_styled
                })

            # Прогресс
            elapsed = (datetime.now() - start_time).total_seconds()
            speed = (i + 1) / elapsed if elapsed > 0 else 0
            eta = (len(examples) - i - 1) / speed if speed > 0 else 0
            print(f"   ⚡ {speed:.2f} экз/сек, ETA: {eta:.0f} сек", flush=True)

        # Сохраняем результаты
        os.makedirs(output_dir, exist_ok=True)

        split_idx = int(len(all_results) * 0.9)

        with open(os.path.join(output_dir, 'train.json'), 'w', encoding='utf-8') as f:
            json.dump(all_results[:split_idx], f, ensure_ascii=False, indent=2)
        with open(os.path.join(output_dir, 'test.json'), 'w', encoding='utf-8') as f:
            json.dump(all_results[split_idx:], f, ensure_ascii=False, indent=2)

        total_time = (datetime.now() - start_time).total_seconds()
        print(f"\n✅ Готово за {total_time:.1f} сек!", flush=True)
        print(f"📊 Всего записей: {len(all_results)} (по 3 стиля на пример)", flush=True)


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', default='scripts/dataset.jsonl')
    parser.add_argument('--output-dir', default='results')
    parser.add_argument('--num-examples', type=int, default=None)
    parser.add_argument('--model', default='qwen2.5:7b')
    args = parser.parse_args()

    generator = TextGenerator(model=args.model)
    generator.process_file(args.input, args.output_dir, args.num_examples)


if __name__ == '__main__':
    main()
