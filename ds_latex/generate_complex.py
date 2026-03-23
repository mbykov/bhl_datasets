import json
import random
import os

LAT_CHARS = {
    'a': ('эй', 'a'), 'b': ('би', 'b'), 'c': ('си', 'c'), 'd': ('ди', 'd'),
    'e': ('и', 'e'), 'f': ('эф', 'f'), 'g': ('джи', 'g'), 'h': ('эйч', 'h'),
    'i': ('ай', 'i'), 'j': ('джей', 'j'), 'k': ('кей', 'k'), 'l': ('эль', 'l'),
    'm': ('эм', 'm'), 'n': ('эн', 'n'), 'o': ('оу', 'o'), 'p': ('пи', 'p'),
    'q': ('кью', 'q'), 'r': ('эр', 'r'), 's': ('эс', 's'), 't': ('ти', 't'),
    'u': ('ю', 'u'), 'v': ('ви', 'v'), 'w': ('дабл-ю', 'w'), 'x': ('икс', 'x'),
    'y': ('уай', 'y'), 'z': ('зет', 'z')
}

def get_var(allow_caps=True):
    char = random.choice(list(LAT_CHARS.keys()))
    is_cap = allow_caps and random.random() > 0.5
    rus_base, eng_base = LAT_CHARS[char]
    if is_cap:
        return char.upper(), f"{rus_base} заглавное", f"capital {eng_base}"
    return char, rus_base, eng_base

def gen_comprehensive_formula():
    sections = ['modal_logic', 'set_theory', 'field_theory', 'proof_theory', 'calculus']
    sec = random.choice(sections)
    v1, r1, e1 = get_var()
    v2, r2, e2 = get_var()

    if sec == 'modal_logic':
        ops = [('\\Box', 'необходимо', 'necessarily'), ('\\Diamond', 'возможно', 'possibly')]
        op_sym, op_r, op_e = random.choice(ops)
        return {
            "section": "Модальная логика",
            "formula": f"{op_e} {e1} implies {e2}",
            "latex": f"${op_sym} {v1} \\implies {v2}$",
            "rus": f"{op_r} {r1} следует {r2}",
            "eng": f"{op_e} {e1} implies {e2}"
        }

    elif sec == 'set_theory':
        return {
            "section": "Теория множеств",
            "formula": f"power set of {e1} union {e2}",
            "latex": f"$\\mathcal{{P}}({v1}) \\cup {v2}$",
            "rus": f"булеан {r1} объединение {r2}",
            "eng": f"power set of {e1} union {e2}"
        }

    elif sec == 'field_theory':
        return {
            "section": "Теория поля",
            "formula": f"laplacian of scalar field {e1}",
            "latex": f"$\\Delta {v1}$",
            "rus": f"лапласиан скалярного поля {r1}",
            "eng": f"laplacian of scalar field {e1}"
        }

    elif sec == 'proof_theory':
        # Символы выводимости и следования
        ops = [('\\vdash', 'выводимо', 'proves'), ('\\vDash', 'логически следует', 'entails')]
        op_sym, op_r, op_e = random.choice(ops)
        return {
            "section": "Теория доказательств",
            "formula": f"theory {e1} {op_e} statement {e2}",
            "latex": f"${v1.upper()} {op_sym} {v2}$",
            "rus": f"теория {LAT_CHARS[v1.lower()][0]} заглавное {op_r} утверждение {r2}",
            "eng": f"theory capital {LAT_CHARS[v1.lower()][1]} {op_e} statement {e2}"
        }

    else: # calculus
        return {
            "section": "Математический анализ",
            "formula": f"limit of {e1} over {e2} as {e1} goes to 0",
            "latex": f"$\\lim_{{{v1} \\to 0}} \\frac{{{v1}}}{{{v2}}}$",
            "rus": f"лимит отношения {r1} к {r2} при {r1} стремящемся к нулю",
            "eng": f"limit of {e1} over {e2} as {e1} approaches zero"
        }

def save_entries(count=1000):
    path = 'data/math_dataset_google.json'
    os.makedirs('data', exist_ok=True)

    data = []
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            try: data = json.load(f)
            except: data = []

    for _ in range(count):
        data.append(gen_comprehensive_formula())

    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"Добавлено {count} записей с указанием разделов. Итого: {len(data)}")

if __name__ == "__main__":
    save_entries(1000)
