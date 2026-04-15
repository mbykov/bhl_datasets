#!/usr/bin/env python3
"""
convert_to_alpaca.py - Конвертация датасета в формат LLaMA-Factory
С валидацией и статистикой качества
"""

import json
import os
from pathlib import Path
from collections import Counter


class DatasetConverter:
    def __init__(self, output_dir='results'):
        self.output_dir = Path(output_dir)
        self.stats = {
            'total_records': 0,
            'total_unique_scripts': 0,
            'types': Counter(),
            'sec': Counter(),
            'avg_rus_length': 0,
            'avg_script_length': 0,
            'duplicates': 0
        }

    def validate_record(self, record):
        """Проверка корректности записи"""
        required_fields = ['script', 'rus']
        for field in required_fields:
            if field not in record or not record[field]:
                return False, f"Отсутствует обязательное поле: {field}"
        
        # Проверка на пустые строки
        if not record['script'].strip() or not record['rus'].strip():
            return False, "Пустое значение в script или rus"
        
        return True, None

    def analyze_dataset(self, records):
        """Анализ качества датасета"""
        scripts = set()
        rus_lengths = []
        script_lengths = []
        seen_scripts = set()
        
        for record in records:
            script = record['script']
            rus = record['rus']
            
            scripts.add(script)
            rus_lengths.append(len(rus))
            script_lengths.append(len(script))
            
            if script in seen_scripts:
                self.stats['duplicates'] += 1
            seen_scripts.add(script)
            
            if 'type' in record:
                self.stats['types'][record['type']] += 1
            if 'sec' in record:
                self.stats['sec'][record['sec']] += 1
        
        self.stats['total_records'] = len(records)
        self.stats['total_unique_scripts'] = len(scripts)
        self.stats['avg_rus_length'] = sum(rus_lengths) / len(rus_lengths) if rus_lengths else 0
        self.stats['avg_script_length'] = sum(script_lengths) / len(script_lengths) if script_lengths else 0
        
        return self.stats

    def convert_to_alpaca(self, input_path, output_file, lang='rus'):
        """
        Конвертация в формат Alpaca JSONL
        
        Формат:
        {
            "instruction": "Convert the following description to LaTeX script.",
            "input": "<русское описание>",
            "output": "<LaTeX скрипт>"
        }
        """
        if not os.path.exists(input_path):
            print(f"Ошибка: Файл {input_path} не найден.")
            return None
        
        records = []
        with open(input_path, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    try:
                        data = json.loads(line)
                        valid, error = self.validate_record(data)
                        if valid:
                            records.append(data)
                        else:
                            print(f"Пропущена запись: {error}")
                    except json.JSONDecodeError as e:
                        print(f"Ошибка парсинга JSON: {e}")
                        continue
        
        # Анализ перед конвертацией
        self.analyze_dataset(records)
        
        # Конвертация в Alpaca формат
        alpaca_records = []
        for record in records:
            if lang == 'rus' and record.get('rus'):
                alpaca_record = {
                    "instruction": "Преобразуй описание на русском языке в LaTeX формулу.",
                    "input": record['rus'],
                    "output": record['script']
                }
                alpaca_records.append(alpaca_record)
            elif lang == 'eng' and record.get('eng'):
                alpaca_record = {
                    "instruction": "Convert the following description to LaTeX script.",
                    "input": record['eng'],
                    "output": record['script']
                }
                alpaca_records.append(alpaca_record)
        
        # Запись в JSONL
        output_path = self.output_dir / output_file
        with open(output_path, 'w', encoding='utf-8') as f:
            for record in alpaca_records:
                f.write(json.dumps(record, ensure_ascii=False) + '\n')
        
        return alpaca_records

    def create_dataset_info(self, dataset_name='latex_ds'):
        """Создание файла dataset_info.json для LLaMA-Factory"""
        info_file = self.output_dir / 'dataset_info.json'
        
        dataset_info = {
            dataset_name: {
                "file_name": f"{dataset_name}_alpaca.jsonl",
                "columns": {
                    "instruction": "instruction",
                    "input": "input",
                    "output": "output"
                },
                "formatting": "alpaca",
                "description": "Dataset for LaTeX formula generation from Russian text"
            }
        }
        
        with open(info_file, 'w', encoding='utf-8') as f:
            json.dump(dataset_info, f, ensure_ascii=False, indent=2)
        
        return info_file

    def print_statistics(self):
        """Вывод статистики"""
        print(f"\n{'='*60}")
        print("СТАТИСТИКА ДАТАСЕТА")
        print(f"{'='*60}")
        print(f"Всего записей: {self.stats['total_records']}")
        print(f"Уникальных формул: {self.stats['total_unique_scripts']}")
        print(f"Дубликатов: {self.stats['duplicates']}")
        print(f"Средняя длина текста (симв): {self.stats['avg_rus_length']:.1f}")
        print(f"Средняя длина LaTeX (симв): {self.stats['avg_script_length']:.1f}")
        
        if self.stats['types']:
            print(f"\nРаспределение по типам:")
            for typ, count in self.stats['types'].most_common(10):
                print(f"   {typ}: {count}")
        
        if self.stats['sec']:
            print(f"\nРаспределение по разделам:")
            for sec, count in self.stats['sec'].most_common(10):
                print(f"   {sec}: {count}")
        
        print(f"{'='*60}")


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', default='results/train.json',
                        help='Входной файл (train.json после normalize.py)')
    parser.add_argument('--output-dir', default='results',
                        help='Выходная директория')
    parser.add_argument('--dataset-name', default='latex_ds',
                        help='Имя датасета в dataset_info.json')
    parser.add_argument('--lang', default='rus', choices=['rus', 'eng'],
                        help='Язык описания: rus (русский) или eng (английский)')
    args = parser.parse_args()
    
    # Конвертация JSON -> JSONL
    converter = DatasetConverter(output_dir=args.output_dir)
    
    print(f"\nКонвертация {args.input}...")
    
    # Чтение JSON файла
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Ошибка: Файл {args.input} не найден.")
        return
    
    with open(input_path, 'r', encoding='utf-8') as f:
        records = json.load(f)
    
    # Анализ
    converter.analyze_dataset(records)
    
    # Преобразование в Alpaca формат
    output_file = f"{args.dataset_name}_alpaca.jsonl"
    alpaca_records = []
    
    for record in records:
        if args.lang == 'rus' and record.get('rus'):
            alpaca_record = {
                "instruction": "Преобразуй описание на русском языке в LaTeX формулу.",
                "input": record['rus'],
                "output": record['script']
            }
            alpaca_records.append(alpaca_record)
        elif args.lang == 'eng' and record.get('eng'):
            alpaca_record = {
                "instruction": "Convert the following description to LaTeX script.",
                "input": record['eng'],
                "output": record['script']
            }
            alpaca_records.append(alpaca_record)
    
    # Запись JSONL
    output_path = Path(args.output_dir) / output_file
    with open(output_path, 'w', encoding='utf-8') as f:
        for record in alpaca_records:
            f.write(json.dumps(record, ensure_ascii=False) + '\n')
    
    # Создание dataset_info.json
    info_file = converter.create_dataset_info(args.dataset_name)
    
    # Статистика
    converter.print_statistics()
    
    print(f"\nГотово!")
    print(f"   - JSONL: {output_path} ({len(alpaca_records)} записей)")
    print(f"   - Info:  {info_file}")
    print(f"\nВ YAML используйте: dataset: {args.dataset_name}, dataset_dir: {args.output_dir}")


if __name__ == "__main__":
    main()