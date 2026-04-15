#!/usr/bin/env python3
"""
normalize.py - Добавление русского текста к LaTeX примерам
"""

import json
import re
import random
from pathlib import Path

class Normalizer:
    def __init__(self, config_dir='config', train_ratio=0.9, seed=42):
        self.config_dir = Path(config_dir)
        self.train_ratio = train_ratio
        self.seed = seed
        random.seed(seed)
        self._load_dictionaries()

        self.op_map = {}
        self._load_operators()

    def _load_operators(self):
        arithmetics = self._load_jsonl('arithmetics.jsonl')
        for op in arithmetics:
            sym = op.get('sym', '')
            rus = op.get('rus', '')
            if sym and rus:
                self.op_map[sym] = rus
        # Сортируем по длине ключа (от длинных к коротким)
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
            self.latin_rus[sym] = rus_list[0] if rus_list else sym

        self.symbols = self._load_jsonl('symbols.jsonl')
        self.rus_map = {}
        for s in self.symbols:
            self.rus_map[s['sym']] = s.get('rus', s['sym'])

        print(f"✅ Загружено словарей", flush=True)

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

    def latex_to_russian(self, latex: str) -> str:
        """Преобразование LaTeX в русский текст (без скобок)"""
        text = latex.strip('$')

        # 1. Замена символов
        for sym, repl in sorted(self.rus_map.items(), key=lambda x: -len(x[0])):
            text = text.replace(sym, f' {repl} ')

        # 2. Замена греческих букв
        for sym, name in self.greek_rus.items():
            text = text.replace(sym, f' {name} ')

        # 3. Замена латинских букв
        for letter, name in self.latin_rus.items():
            text = re.sub(rf'\b{re.escape(letter)}\b', f' {name} ', text)

        # 4. Убираем оставшиеся LaTeX команды
        text = re.sub(r'\\([a-zA-Z]+)', r' \1 ', text)

        # 5. Убираем фигурные скобки
        text = text.replace('{', ' ').replace('}', ' ')

        # 6. Обработка специальных символов
        text = text.replace('_', ' _ ')
        text = text.replace('^', ' ^ ')

        # 7. Замена операторов (сортируем по длине)
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

        # 11. Очищаем лишние пробелы
        text = re.sub(r'\s+', ' ', text).strip()

        # 12. Убираем оставшиеся скобки
        text = text.replace('(', ' ').replace(')', ' ')
        text = re.sub(r'\s+', ' ', text).strip()

        return text

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
                        'sense_scheme': data.get('sense_scheme', '')
                    })

        print(f"📊 Загружено: {len(examples)} примеров", flush=True)

        records = []
        skipped = 0

        for example in examples:
            script = example['script']

            try:
                rus = self.latex_to_russian(script)
                eng = self.latex_to_english(script)
            except Exception as e:
                print(f"⚠️ Ошибка при обработке #{example['idx']}: {e}", flush=True)
                skipped += 1
                continue

            records.append({
                "sec": example['sec'],
                "sym": example['sym'],
                "script": script,
                "type": example['type'],
                "sense_scheme": example['sense_scheme'],
                "rus": rus,
                "eng": eng
            })

            if example['idx'] < 5:
                print(f"\n[{example['idx']}] {script[:50]}...")
                print(f"   rus: {rus[:80]}")
                print(f"   sense_scheme: {example['sense_scheme']}")

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
        print(f"   Train: {train_path} ({len(train_records)} записей)")
        print(f"   Test:  {test_path} ({len(test_records)} записей)")
        print(f"⏭️ Пропущено: {skipped}")
        print(f"{'='*60}")


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', default='scripts/dataset.jsonl')
    parser.add_argument('--output-dir', default='data')
    parser.add_argument('--limit', type=int, default=None)
    parser.add_argument('--config', default='config')
    parser.add_argument('--train-ratio', type=float, default=0.9)
    parser.add_argument('--seed', type=int, default=42)
    args = parser.parse_args()

    normalizer = Normalizer(config_dir=args.config, train_ratio=args.train_ratio, seed=args.seed)
    normalizer.process_dataset(args.input, args.output_dir, args.limit)


if __name__ == "__main__":
    main()
