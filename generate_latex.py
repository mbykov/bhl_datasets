#!/usr/bin/env python3
"""
Генератор LaTeX датасета с train/test разделением
Поддержка добавления новых данных к существующим (append mode)
"""

import json
import random
import os
import re
import sys

class MathFactory:
    def __init__(self, data_dir='data'):
        dict_path = os.path.join(data_dir, 'dictionary.json')

        self.atoms = self._load_json(os.path.join(data_dir, 'atoms.json'))
        self.dict = self._load_json(dict_path)
        self.variables = self._load_json(os.path.join(data_dir, 'variables.json'))
        self.templates = self._load_json(os.path.join(data_dir, 'templates.json'))

    def _load_json(self, path):
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def get_random_var(self):
        v = random.choice(self.variables['vars'])
        return {"r": v['r'], "e": v['e'], "l": v['l']}

    def get_random_const(self):
        c = random.choice(self.variables['constants'])
        return {"r": c['r'], "e": c['e'], "l": c['l']}

    def generate_unit(self, atom_key, depth=0, force_mode=None):
        atom = self.atoms.get(atom_key)
        entry = self.dict.get(atom_key)

        if not atom or not entry:
            return self.get_random_var()

        if depth < 1 and random.random() < 0.4:
            inner_key = random.choice(list(self.atoms.keys()))
            v1_data = self.generate_unit(inner_key, depth + 1)
        else:
            v1_data = self.get_random_var()

        v2_d = self.get_random_var()
        v3_d = self.get_random_var()
        v4_d = self.get_random_var()

        res = {"r": "", "e": "", "l": ""}

        available_modes = list(entry['rus'].keys())
        if force_mode and force_mode in available_modes:
            mode = force_mode
        elif depth > 0 and 'short' in available_modes:
            mode = 'short'
        else:
            if len(available_modes) > 1 and 'short' in available_modes:
                available_modes.remove('short')
            mode = random.choice(available_modes)

        w_r = random.choice(entry['rus'][mode])
        eng_modes = list(entry['eng'].keys())
        w_e = random.choice(entry['eng'][mode] if mode in eng_modes else entry['eng'][eng_modes[0]])

        fmt_l = {'v1': v1_data['l'], 'v2': v2_d['l'], 'v3': v3_d['l'], 'v4': v4_d['l']}
        fmt_r = {'v1': v1_data['r'], 'v2': v2_d['r'], 'v3': v3_d['r'], 'v4': v4_d['r'], 'action': w_r, 'noun': w_r}
        fmt_e = {'v1': v1_data['e'], 'v2': v2_d['e'], 'v3': v3_d['e'], 'v4': v4_d['e'], 'action': w_e, 'noun': w_e}

        if atom['type'] == 'infix':
            if mode == 'verbs_directed':
                t_r, t_e = self.templates['rus']['directed_verb'], self.templates['eng']['directed_verb']
            elif mode == 'short':
                t_r, t_e = "{v1} {action} {v2}", "{v1} {action} {v2}"
            elif mode == 'nouns':
                t_r, t_e = self.templates['rus']['simple_noun'], self.templates['eng']['simple_noun']
            else:
                t_r, t_e = self.templates['rus']['simple_verb'], self.templates['eng']['simple_verb']

            res['r'] = t_r.format(**fmt_r)
            res['e'] = t_e.format(**fmt_e)
            res['l'] = atom['latex'].format(**fmt_l)
            if depth > 0:
                res['l'] = f"({res['l']})"
        else:
            use_noun = (mode == 'nouns')
            t_r = self.templates['rus']['prefix_noun' if use_noun else 'prefix_verb']
            t_e = self.templates['eng']['prefix_noun' if use_noun else 'prefix_verb']

            res['r'] = t_r.format(**fmt_r)
            res['e'] = t_e.format(**fmt_e)
            res['l'] = atom['latex'].format(**fmt_l)

        return res

    def produce_structured(self, target_sec, n_base=2, n_nested=15, n_eq=10):
        output = []
        section_atoms = [k for k, v in self.atoms.items() if v.get('sec') == target_sec]
        if not section_atoms:
            return []

        for key in section_atoms:
            entry = self.dict.get(key)
            if not entry:
                continue
            for mode in entry['rus'].keys():
                for _ in range(n_base):
                    sample = self.generate_unit(key, depth=10, force_mode=mode)
                    output.append({
                        "sec": target_sec,
                        "rus": sample['r'],
                        "eng": sample['e'],
                        "latex": f"${sample['l']}$"
                    })

        for _ in range(n_nested):
            key = random.choice(section_atoms)
            sample = self.generate_unit(key, depth=0)
            output.append({
                "sec": target_sec,
                "rus": sample['r'],
                "eng": sample['e'],
                "latex": f"${sample['l']}$"
            })

        for _ in range(n_eq // 2):
            k1 = random.choice(section_atoms)
            s1 = self.generate_unit(k1)
            c = self.get_random_const()
            output.append({
                "sec": target_sec,
                "rus": self.templates['rus']['equation'].format(expr=s1['r'], v3=c['r']),
                "eng": self.templates['eng']['equation'].format(expr=s1['e'], v3=c['e']),
                "latex": f"${s1['l'].strip('()')} = {c['l']}$"
            })

            k2, k3 = random.choice(section_atoms), random.choice(section_atoms)
            s2, s3 = self.generate_unit(k2), self.generate_unit(k3)
            output.append({
                "sec": target_sec,
                "rus": f"{s2['r']} равно {s3['r']}",
                "eng": f"{s2['e']} equals {s3['e']}",
                "latex": f"${s2['l'].strip('()')} = {s3['l'].strip('()')}$"
            })

        return output


def extract_meaningful_words(text, min_length=3):
    """Извлекает осмысленные слова"""
    if not text:
        return set()
    words = re.findall(r'\b[a-zA-Zа-яА-Я]{' + str(min_length) + r',}\b', text.lower())
    return set(words)


def generate_keywords(data, output_path):
    """Генерирует keywords.txt"""
    keywords = set()

    for item in data:
        keywords.update(extract_meaningful_words(item.get("rus", "")))
        keywords.update(extract_meaningful_words(item.get("eng", "")))

    extra_words = {
        "преобразуй", "формулу", "латех", "скрипт", "напиши", "создай", "получи",
        "convert", "formula", "latex", "script", "write", "create", "get"
    }
    keywords.update(extra_words)

    filtered = sorted(keywords)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(filtered))

    return len(filtered)


def split_train_test(data, test_ratio=0.1, seed=42):
    """Разделяет данные на train и test"""
    random.seed(seed)
    random.shuffle(data)
    test_size = int(len(data) * test_ratio)
    test_data = data[:test_size]
    train_data = data[test_size:]
    return train_data, test_data


def count_lines(filepath):
    """Подсчитывает количество строк в файле"""
    if not os.path.exists(filepath):
        return 0
    with open(filepath, 'r', encoding='utf-8') as f:
        return sum(1 for _ in f)


def save_dataset(data, filepath, mode='w', show_stats=True):
    """Сохраняет датасет с возможностью append"""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)

    old_count = count_lines(filepath) if mode == 'a' else 0

    with open(filepath, mode, encoding='utf-8') as f:
        for entry in data:
            f.write(json.dumps(entry, ensure_ascii=False) + '\n')

    new_count = count_lines(filepath)
    added = new_count - old_count

    if show_stats:
        if mode == 'a':
            print(f"   Добавлено {added} строк. Всего в файле: {new_count} строк")
        else:
            print(f"   Сохранено {len(data)} строк")


def validate_json(filepath, name):
    """Проверяет валидность JSON файла"""
    if not os.path.exists(filepath):
        print(f"   ⚠️ Файл {filepath} не найден")
        return -1

    invalid_count = 0
    with open(filepath, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            if line.strip():
                try:
                    json.loads(line)
                except json.JSONDecodeError as e:
                    invalid_count += 1
                    print(f"   ❌ {name} строка {line_num}: {e}")
    return invalid_count


def print_statistics_by_section(data, title="Статистика по секциям"):
    """Выводит статистику по секциям"""
    section_counts = {}
    for item in data:
        sec = item.get('sec', 'unknown')
        section_counts[sec] = section_counts.get(sec, 0) + 1

    print(f"\n📊 {title}:")
    for sec, count in sorted(section_counts.items()):
        print(f"   {sec:20} | {count:5} примеров")

    return section_counts


def generate_dataset(n_base=5, n_nested=10, n_eq=10, test_ratio=0.1, seed=42, append_train=True, count=None):
    """
    Основная функция генерации датасета с train/test разделением

    Args:
        n_base: количество базовых примеров на атом (для старого режима)
        n_nested: количество вложенных примеров (для старого режима)
        n_eq: количество уравнений (для старого режима)
        test_ratio: доля тестовой выборки
        seed: seed для воспроизводимости
        append_train: если True, добавляет train данные к существующим, иначе перезаписывает
        count: целевое количество примеров (для нового режима с уникальностью)
    """
    print("\n" + "="*70)
    print("🎲 ГЕНЕРАЦИЯ LATEX ДАТАСЕТА")
    print("="*70)

    # Устанавливаем seed для воспроизводимости
    random.seed(seed)

    factory = MathFactory()
    all_sections = sorted(list(set(v.get('sec') for v in factory.atoms.values() if v.get('sec'))))
    all_atom_keys = list(factory.atoms.keys())

    # Режим с уникальностью и конкретным count
    if count is not None and count > 0:
        print(f"Параметры генерации:")
        print(f"   count       = {count}  (целевое количество уникальных примеров)")
        print(f"   test_ratio  = {test_ratio}")
        print(f"   seed        = {seed}")
        print(f"   append_train= {append_train}")
        print("="*70)

        print(f"\n📚 Найдено секций: {len(all_sections)}")
        print(f"   {', '.join(all_sections)}")

        # Генерируем уникальные примеры
        seen_latex = set()
        all_new_data = []
        duplicates_skipped = 0
        max_attempts = count * 10  # защита от бесконечного цикла

        print(f"\n🔄 Генерация уникальных примеров...")

        for attempt in range(max_attempts):
            if len(all_new_data) >= count:
                break

            # Случайный атом и режим
            key = random.choice(all_atom_keys)
            entry = factory.dict.get(key)
            if not entry:
                continue

            modes = list(entry['rus'].keys())
            mode = random.choice(modes)
            depth = random.choice([0, 1, 2, 3, 5, 10])

            sample = factory.generate_unit(key, depth=depth, force_mode=mode)
            latex = f"${sample['l']}$"

            # Проверяем уникальность по LaTeX
            if latex in seen_latex:
                duplicates_skipped += 1
                continue

            seen_latex.add(latex)
            all_new_data.append({
                "sec": factory.atoms[key].get('sec', 'unknown'),
                "rus": sample['r'],
                "eng": sample['e'],
                "latex": latex
            })

            if len(all_new_data) % 5000 == 0:
                print(f"   Сгенерировано: {len(all_new_data)} / {count}")

        print(f"\n📊 Сгенерировано: {len(all_new_data)} примеров")
        print(f"   Пропущено дубликатов: {duplicates_skipped}")

        total_generated = len(all_new_data)

    else:
        # Старый режим (без count)
        print(f"Параметры генерации:")
        print(f"   n_base      = {n_base}  (базовые примеры на атом)")
        print(f"   n_nested    = {n_nested} (вложенные примеры)")
        print(f"   n_eq        = {n_eq}    (уравнения)")
        print(f"   test_ratio  = {test_ratio} (доля тестовой выборки)")
        print(f"   seed        = {seed}    (для воспроизводимости)")
        print(f"   append_train= {append_train} (добавлять к существующим train данным)")
        print("="*70)

        print(f"\n📚 Найдено секций: {len(all_sections)}")
        print(f"   {', '.join(all_sections)}")

        # Генерируем данные
        all_new_data = []
        for sec in all_sections:
            data = factory.produce_structured(sec, n_base=n_base, n_nested=n_nested, n_eq=n_eq)
            print(f"   [{sec:20}] Сгенерировано {len(data):4} примеров")
            all_new_data.extend(data)

        total_generated = len(all_new_data)
        print(f"\n📊 Всего сгенерировано: {total_generated} примеров")

    # Разделяем на train и test
    train_data, test_data = split_train_test(all_new_data, test_ratio, seed)

    train_count = len(train_data)
    test_count = len(test_data)

    print(f"\n📁 Разделение данных:")
    print(f"   Train: {train_count:5} примеров ({int((1-test_ratio)*100)}%)")
    print(f"   Test:  {test_count:5} примеров ({int(test_ratio*100)}%)")

    # Создаем директорию
    output_dir = 'result/latex'
    os.makedirs(output_dir, exist_ok=True)

    # Сохраняем train датасет (с возможностью append)
    train_path = os.path.join(output_dir, 'dataset.jsonl')
    train_mode = 'a' if append_train else 'w'
    save_dataset(train_data, train_path, mode=train_mode)

    # Сохраняем test датасет (всегда перезаписываем для чистоты тестов)
    test_path = os.path.join(output_dir, 'test.jsonl')
    save_dataset(test_data, test_path, mode='w')

    # Подсчитываем общее количество строк после добавления
    final_train_count = count_lines(train_path)
    final_test_count = count_lines(test_path)

    print(f"\n📊 Итоговое количество строк:")
    print(f"   Train: {final_train_count} строк (добавлено {train_count})")
    print(f"   Test:  {final_test_count} строк (перезаписано)")

    # Проверка валидности JSON
    print("\n🔍 Проверка валидности JSON...")
    train_invalid = validate_json(train_path, "Train")
    test_invalid = validate_json(test_path, "Test")

    if train_invalid == 0 and test_invalid == 0:
        print(f"   ✅ Все строки валидны!")
    else:
        print(f"   ⚠️ Найдено ошибок: Train={train_invalid}, Test={test_invalid}")

    # Создаем dataset_info.json (только если файла нет или нужно обновить)
    info_path = os.path.join(output_dir, "dataset_info.json")
    if not os.path.exists(info_path) or not append_train:
        info = {
            "latex_ds": {
                "file_name": "dataset.jsonl",
                "columns": {
                    "prompt": "rus",
                    "query": "eng",
                    "response": "latex"
                }
            }
        }
        with open(info_path, 'w', encoding='utf-8') as f:
            json.dump(info, f, ensure_ascii=False, indent=2)
        print(f"✅ Конфиг сохранен: {info_path}")
    else:
        print(f"ℹ️ Конфиг уже существует: {info_path}")

    # Генерируем ключевые слова (всегда обновляем)
    all_data = []
    if os.path.exists(train_path):
        with open(train_path, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    all_data.append(json.loads(line))
    if os.path.exists(test_path):
        with open(test_path, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    all_data.append(json.loads(line))

    keywords_path = os.path.join(output_dir, "keywords.txt")
    keywords_count = generate_keywords(all_data, keywords_path)
    print(f"✅ Ключевые слова обновлены: {keywords_path} ({keywords_count} слов)")

    # Статистика по секциям (по новым данным)
    print_statistics_by_section(all_new_data, "Распределение новых примеров по секциям")

    # Показываем примеры
    print("\n📝 Примеры новых данных:")
    for i, item in enumerate(all_new_data[:3]):
        rus_preview = item['rus'][:70] + "..." if len(item['rus']) > 70 else item['rus']
        latex_preview = item['latex'][:60] + "..." if len(item['latex']) > 60 else item['latex']
        print(f"   {i+1}. {rus_preview}")
        print(f"      → {latex_preview}")

    # ИТОГОВАЯ СТАТИСТИКА
    print("\n" + "="*70)
    print("📊 ИТОГОВАЯ СТАТИСТИКА")
    print("="*70)
    print(f"   Сгенерировано новых примеров: {total_generated}")
    print(f"   Добавлено в Train:            {train_count} строк")
    print(f"   Перезаписано Test:            {test_count} строк")
    print(f"   Всего в Train после добавления: {final_train_count} строк")
    print(f"   Всего в Test:                 {final_test_count} строк")
    print(f"   Ключевых слов:                {keywords_count}")
    print("="*70)

    return train_data, test_data


if __name__ == "__main__":
    # Параметры по умолчанию
    n_base = 5
    n_nested = 10
    n_eq = 10
    test_ratio = 0.1
    append_train = True  # По умолчанию добавляем к существующим train данным
    count = 100000  # По умолчанию 100k уникальных примеров

    # Парсим аргументы командной строки
    for arg in sys.argv[1:]:
        if arg.startswith("--n-base="):
            n_base = int(arg.split("=")[1])
        elif arg.startswith("--n-nested="):
            n_nested = int(arg.split("=")[1])
        elif arg.startswith("--n-eq="):
            n_eq = int(arg.split("=")[1])
        elif arg.startswith("--test-ratio="):
            test_ratio = float(arg.split("=")[1])
        elif arg.startswith("--count="):
            count = int(arg.split("=")[1])
        elif arg == "--no-append":
            append_train = False
        elif arg == "--help":
            print("""
Использование: python generate_latex.py [опции]

Опции:
  --count=N       Количество уникальных примеров (по умолчанию: 100000)
  --n-base=N      Количество базовых примеров на атом (для старого режима)
  --n-nested=N    Количество вложенных примеров (для старого режима)
  --n-eq=N        Количество уравнений (для старого режима)
  --test-ratio=R  Доля тестовой выборки (по умолчанию: 0.1)
  --no-append     Не добавлять, а перезаписать train датасет
  --help          Показать эту справку

Примеры:
  python generate_latex.py                           # 100k уникальных (по умолчанию)
  python generate_latex.py --count=50000             # 50k уникальных
  python generate_latex.py --count=0                 # Старый режим (n_base/n_nested/n_eq)
  python generate_latex.py --no-append --count=50000
            """)
            sys.exit(0)

    # Запускаем генерацию
    generate_dataset(
        n_base=n_base,
        n_nested=n_nested,
        n_eq=n_eq,
        test_ratio=test_ratio,
        append_train=append_train,
        count=count if count > 0 else None
    )
