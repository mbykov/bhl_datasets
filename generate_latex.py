import json
import random
import os
import re

class MathFactory:
    def __init__(self, data_dir='data'):
        dict_path = os.path.join(data_dir, 'dictionary.json')
        if not os.path.exists(dict_path):
            dict_path = os.path.join(data_dir, 'dictonary.json')

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
    words = re.findall(r'\b[a-zA-Zа-яА-Я]{' + str(min_length) + r',}\b', text.lower())
    return set(words)


def generate_keywords(data, output_path):
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


def generate_dataset():
    """Генерация датасета - НИКАКОГО РУЧНОГО ЭКРАНИРОВАНИЯ!"""

    factory = MathFactory()

    N_BASE = 5
    N_NESTED = 10
    N_EQ = 10

    all_sections = sorted(list(set(v.get('sec') for v in factory.atoms.values() if v.get('sec'))))
    print(f"Найдено секций: {all_sections}")

    all_new_data = []
    for sec in all_sections:
        data = factory.produce_structured(sec, n_base=N_BASE, n_nested=N_NESTED, n_eq=N_EQ)
        print(f"[{sec}] Generated {len(data)} samples")
        all_new_data.extend(data)

    output_dir = 'result_latex'
    file_path = os.path.join(output_dir, 'latex.jsonl')
    os.makedirs(output_dir, exist_ok=True)

    total_count = 0

    # Просто записываем, json.dumps() сам сделает правильное экранирование
    with open(file_path, 'w', encoding='utf-8') as f:
        for entry in all_new_data:
            total_count += 1
            # json.dumps() автоматически экранирует все специальные символы
            f.write(json.dumps(entry, ensure_ascii=False) + '\n')

    print(f"\n📊 Генерация завершена:")
    print(f"   Всего записей: {total_count}")

    # Проверка валидности
    print("\n🔍 Проверка валидности JSON...")
    invalid_count = 0
    with open(file_path, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            try:
                data = json.loads(line)
                # Дополнительно проверяем, что LaTeX содержит \ а не \\
                if 'latex' in data and '\\\\' in data['latex']:
                    print(f"   ⚠️ Строка {line_num}: найдено двойное экранирование")
            except json.JSONDecodeError as e:
                invalid_count += 1
                print(f"   ❌ Ошибка в строке {line_num}: {e}")

    if invalid_count == 0:
        print(f"   ✅ Все {total_count} строк валидны!")

    # Создаем dataset_info.json
    info = {
        "latex_ds": {
            "file_name": "latex.jsonl",
            "columns": {
                "prompt": "rus",
                "query": "eng",
                "response": "latex"
            }
        }
    }
    info_path = os.path.join(output_dir, "dataset_info.json")
    with open(info_path, 'w', encoding='utf-8') as f:
        json.dump(info, f, ensure_ascii=False, indent=2)

    keywords_path = os.path.join(output_dir, "keywords.txt")
    keywords_count = generate_keywords(all_new_data, keywords_path)

    print(f"\n✅ Готово!")
    print(f"   Датасет: {file_path} ({total_count} строк)")
    print(f"   Конфиг: {info_path}")
    print(f"   Ключевые слова: {keywords_path} ({keywords_count} слов)")
    print(f"\n📝 Пример записи:")
    if all_new_data:
        print(json.dumps(all_new_data[0], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    generate_dataset()
