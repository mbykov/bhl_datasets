#!/usr/bin/env python3
"""
normalize.py - Добавление русского текста к LaTeX примерам
С поддержкой синонимов и вариаций порядка слов
"""

import json
import re
import random
from pathlib import Path
from functools import lru_cache


class Normalizer:
    def __init__(self, config_dir='config', train_ratio=0.9, seed=42, num_variants=2):
        self.config_dir = Path(config_dir)
        self.train_ratio = train_ratio
        self.seed = seed
        self.num_variants = num_variants  # Количество вариантов на каждый пример
        self.op_map = {}  # Инициализация перед загрузкой
        random.seed(seed)
        
        self._load_dictionaries()
        self._load_synonyms()
        self._load_templates()
        self._load_operators()

        print(f"✅ Загружено: {len(self.synonyms)} синонимов, {len(self.templates)} шаблонов", flush=True)

    def _load_operators(self):
        arithmetics = self._load_jsonl('arithmetics.jsonl')
        for op in arithmetics:
            sym = op.get('sym', '')
            rus = op.get('rus', '')
            if sym and rus:
                self.op_map[sym] = rus
        self.op_map = dict(sorted(self.op_map.items(), key=lambda x: -len(x[0])))
        print(f"✅ Загружено операторов: {len(self.op_map)}", flush=True)

    def _load_dictionaries(self):
        self.greeks = self._load_jsonl('greeks.jsonl')
        self.greek_rus = {}
        self.greek_set = set()
        for g in self.greeks:
            self.greek_rus[g['sym']] = g.get('rus', g['sym'])
            self.greek_set.add(g['sym'])

        self.greek_upper_rus = {
            'Гамма': 'гамма', 'Дельта': 'дельта', 'Тета': 'тета',
            'Лямбда': 'лямбда', 'Кси': 'кси', 'Пи': 'пи',
            'Сигма': 'сигма', 'Ипсилон': 'ипсилон', 'Фи': 'фи',
            'Пси': 'пси', 'Омега': 'омега',
        }

        self.latins = self._load_jsonl('latins.jsonl')
        self.latin_rus = {}
        self.latin_set = set()
        for l in self.latins:
            sym = l['sym']
            if sym == '@':
                continue
            self.latin_set.add(sym)
            rus_list = l.get('rus', [''])
            self.latin_rus[sym] = rus_list if isinstance(rus_list, list) else [rus_list]

        self.symbols = self._load_jsonl('symbols.jsonl')
        self.rus_map = {}
        for s in self.symbols:
            self.rus_map[s['sym']] = s.get('rus', s['sym'])

    def _load_synonyms(self):
        """Загрузка синонимов из файла"""
        self.synonyms = {}
        synonym_data = self._load_jsonl('synonyms.jsonl')
        for item in synonym_data:
            term = item.get('term', '')
            syns = item.get('synonyms', [term])
            if term:
                self.synonyms[term] = syns
        print(f"✅ Загружено синонимов для {len(self.synonyms)} терминов", flush=True)

    def _load_templates(self):
        """Загрузка шаблонов порядка слов"""
        template_file = self.config_dir / 'word_order_templates.json'
        try:
            with open(template_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.templates = {t['type']: t for t in data.get('templates', [])}
            print(f"✅ Загружено шаблонов: {len(self.templates)}", flush=True)
        except FileNotFoundError:
            self.templates = {}
            print("⚠️ Файл шаблонов не найден, работа без шаблонов", flush=True)

    def _load_jsonl(self, filename):
        data = []
        try:
            with open(self.config_dir / filename, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        data.append(json.loads(line))
        except FileNotFoundError:
            pass
        return data

    def _apply_synonyms(self, text):
        """Заменяет термины на случайные синонимы"""
        result = text
        # Сортируем по длине, чтобы сначала заменять длинные термины
        for term in sorted(self.synonyms.keys(), key=len, reverse=True):
            if term in result:
                syns = self.synonyms[term]
                if len(syns) > 1:
                    replacement = random.choice(syns)
                    # Заменяем все вхождения (случайно выбираем синоним для каждого)
                    result = re.sub(
                        rf'\b{re.escape(term)}\b',
                        lambda m: random.choice(syns),
                        result
                    )
        return result

    def _apply_template(self, text, template_type):
        """Применяет шаблон порядка слов, если есть подходящий"""
        if template_type not in self.templates:
            return text
        
        template = self.templates[template_type]
        patterns = template.get('patterns_rus', [])
        
        if not patterns:
            return text
        
        # Выбираем случайный шаблон
        pattern = random.choice(patterns)
        
        # Проверяем, содержит ли шаблон плейсхолдеры
        if '{' in pattern:
            # Если шаблон требует подстановки, но мы не можем её сделать точно,
            # возвращаем исходный текст вместо кривого шаблона
            return text
        
        return pattern

    def _detect_type_from_scheme(self, scheme):
        """Определяет тип конструкции по sense_scheme"""
        scheme_lower = scheme.lower()
        
        if 'int(' in scheme_lower or 'sqrt(' in scheme_lower or 'sin(' in scheme_lower:
            if scheme_lower.count('(') >= 2:
                return 'complex_nest'
            return 'unary_function'
        elif 'pow' in scheme_lower or '^' in scheme:
            return 'power'
        elif 'sqrt' in scheme_lower:
            return 'root'
        elif 'sum' in scheme_lower:
            return 'sum'
        elif 'limit' in scheme_lower or 'lim' in scheme_lower:
            return 'limit'
        elif 'integral' in scheme_lower:
            if 'from' in scheme_lower or 'до' in scheme_lower:
                return 'integral_bounded'
            return 'integral'
        elif '(' in scheme and ')' in scheme:
            return 'parentheses'
        elif 'eq' in scheme_lower or 'gt' in scheme_lower or 'lt' in scheme_lower:
            return 'relation'
        elif '+' in scheme or '-' in scheme:
            return 'binary_function'
        
        return None

    def _latex_to_russian_base(self, latex: str) -> str:
        """Базовое преобразование LaTeX в русский текст"""
        text = latex.strip('$')

        # 1. Замена символов
        for sym, repl in sorted(self.rus_map.items(), key=lambda x: -len(x[0])):
            text = text.replace(sym, f' {repl} ')

        # 2. Замена греческих букв
        for sym, name in self.greek_rus.items():
            text = text.replace(sym, f' {name} ')

        # 3. Замена латинских букв
        for letter, names in self.latin_rus.items():
            name = random.choice(names) if isinstance(names, list) else names
            text = re.sub(rf'\b{re.escape(letter)}\b', f' {name} ', text)

        # 4. Убираем оставшиеся LaTeX команды
        text = re.sub(r'\\([a-zA-Z]+)', r' \1 ', text)

        # 5. Убираем фигурные скобки
        text = text.replace('{', ' ').replace('}', ' ')

        # 6. Обработка специальных символов
        text = text.replace('_', ' _ ')
        text = text.replace('^', ' ^ ')

        # 7. Замена операторов
        for op, word in self.op_map.items():
            escaped_op = re.escape(op)
            text = re.sub(rf'\s*{escaped_op}\s*', f' {word} ', text)

        # 8. Обработка дифференциала
        text = re.sub(r'd\s+([a-zA-Zа-яё]+)', r'дэ \1', text)
        text = re.sub(r'd([a-zA-Zа-яё]+)', r'дэ \1', text)
        text = re.sub(r'\bd\b', 'дэ', text)

        # 9. Обработка индексов интегралов
        text = re.sub(r'нижний индекс\s+(\S+)\s+степень\s+(\S+)', r'от \1 до \2', text)
        text = re.sub(r'нижний индекс\s+(\S+)', r'от \1', text)

        # 10. Заглавные греческие в строчные
        for upper, lower in self.greek_upper_rus.items():
            text = text.replace(upper, lower)
        text = text.replace('заглавная', '')

        # 11. Убираем скобки
        text = text.replace('(', ' ').replace(')', ' ')

        # 12. Очищаем лишние пробелы
        text = re.sub(r'\s+', ' ', text).strip()

        return text

    def latex_to_russian_variants(self, latex: str, sense_scheme: str = None) -> list:
        """
        Генерирует несколько вариантов русского текста для одного LaTeX
        """
        base_text = self._latex_to_russian_base(latex)
        
        # Определяем тип конструкции
        template_type = None
        if sense_scheme:
            template_type = self._detect_type_from_scheme(sense_scheme)
        
        variants = []
        
        for i in range(self.num_variants):
            # Создаём копию текста
            text = base_text
            
            # Применяем синонимы
            text = self._apply_synonyms(text)
            
            # Применяем шаблон если есть
            if template_type and random.random() > 0.3:  # 70% шанс применения шаблона
                text = self._apply_template(text, template_type)
            
            variants.append(text)
        
        return variants

    def latex_to_english(self, latex: str) -> str:
        """Преобразование LaTeX в английский текст (заглушка)"""
        text = latex.strip('$')
        text = re.sub(r'\\([a-zA-Z]+)', r'\1 ', text)
        text = re.sub(r'[{}_^]', ' ', text)
        text = re.sub(r'\s+', ' ', text).strip()
        return text if text else latex

    def process_dataset(self, input_path: str, output_dir: str, limit: int = None):
        print(f"\n📚 Загрузка {input_path}...", flush=True)

        examples = []
        with open(input_path, 'r', encoding='utf-8') as f:
            for idx, line in enumerate(f):
                if line.strip():
                    if limit and idx >= limit:
                        break
                    data = json.loads(line)
                    examples.append({
                        'idx': idx,
                        'sec': data.get('sec', ''),
                        'sym': data.get('sym', ''),
                        'script': data.get('script', ''),
                        'type': data.get('type', ''),
                        'scheme': data.get('scheme', '')
                    })

        print(f"📊 Загружено: {len(examples)} примеров", flush=True)
        print(f"🎯 Генерация {self.num_variants} вариантов на каждый пример...", flush=True)

        records = []
        skipped = 0

        for example in examples:
            script = example['script']
            scheme = example.get('scheme', '')

            try:
                # Генерируем несколько вариантов русского текста
                rus_variants = self.latex_to_russian_variants(script, scheme)
                eng = self.latex_to_english(script)
            except Exception as e:
                print(f"⚠️ Ошибка при обработке #{example['idx']}: {e}", flush=True)
                skipped += 1
                continue

            # Создаём отдельную запись для каждого варианта
            for idx_variant, rus in enumerate(rus_variants):
                records.append({
                    "sec": example['sec'],
                    "sym": example['sym'],
                    "script": script,
                    "type": example['type'],
                    "scheme": scheme,
                    "variant": idx_variant,
                    "rus": rus,
                    "eng": eng
                })

            if example['idx'] < 3:
                print(f"\n[{example['idx']}] {script[:50]}...")
                for i, rus in enumerate(rus_variants):
                    print(f"   variant {i}: {rus[:80]}")
                print(f"   scheme: {scheme[:60]}")

        random.shuffle(records)
        split_idx = int(len(records) * self.train_ratio)
        train_records = records[:split_idx]
        test_records = records[split_idx:]

        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        train_path = output_dir / 'train.json'
        test_path = output_dir / 'test.json'

        with open(train_path, 'w', encoding='utf-8') as f:
            json.dump(train_records, f, ensure_ascii=False, indent=2)

        with open(test_path, 'w', encoding='utf-8') as f:
            json.dump(test_records, f, ensure_ascii=False, indent=2)

        print(f"\n{'='*60}")
        print(f"✅ Сохранено:")
        print(f"   Train: {train_path} ({len(train_records)} записей, {len(train_records)//self.num_variants} уникальных примеров)")
        print(f"   Test:  {test_path} ({len(test_records)} записей)")
        print(f"⏭️ Пропущено: {skipped}")
        print(f"📈 Увеличение датасета в {self.num_variants} раза за счёт вариаций")
        print(f"{'='*60}")


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', default='results/dataset.jsonl')
    parser.add_argument('--output-dir', default='results')
    parser.add_argument('--limit', type=int, default=None)
    parser.add_argument('--config', default='config')
    parser.add_argument('--train-ratio', type=float, default=0.9)
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--num-variants', type=int, default=2, 
                        help='Количество вариантов русского текста на каждый пример (2-3 оптимально)')
    args = parser.parse_args()

    normalizer = Normalizer(
        config_dir=args.config, 
        train_ratio=args.train_ratio, 
        seed=args.seed,
        num_variants=args.num_variants
    )
    normalizer.process_dataset(args.input, args.output_dir, args.limit)


if __name__ == "__main__":
    main()