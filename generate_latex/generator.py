import json
import os
import random

# Наборы переменных
GREEK = [r"\alpha", r"\beta", r"\gamma", r"\mu", r"\nu", r"\rho", r"\sigma", r"\psi", r"\phi", r"\omega"]
LATIN = ["x", "y", "z", "p", "q", "k", "t", "L", "f", "g", "A", "B"]

def get_var():
    return random.choice(LATIN + GREEK)

def fill(template):
    """Заменяет метки @ на случайные переменные"""
    res = template
    while "@" in res:
        res = res.replace("@", get_var(), 1)
    return res

def get_unique_list(generator_func, count):
    """Генерирует список уникальных элементов заданной длины"""
    results = set()
    attempts = 0
    # Ограничение попыток, чтобы избежать бесконечного цикла, если вариантов мало
    while len(results) < count and attempts < 100:
        item = generator_func()
        results.add(item)
        attempts += 1
    return list(results)

def run_generator(count=3):
    os.makedirs("results/", exist_ok=True)

    if not os.path.exists("data/structures.json"):
        print("Ошибка: Файл data/structures.json не найден!")
        return

    with open("data/structures.json", "r", encoding="utf-8") as f:
        fields = json.load(f)

    # Собираем все шаблоны для кросс-вставок
    all_templates = []
    for f_data in fields.values():
        all_templates.extend([s["sym"] for s in f_data["structures"].values()])

    final_output = []

    for field_name, content in fields.items():
        field_ops = content["operators"]

        for key, struct in content["structures"].items():
            template = struct["sym"]

            # 1. Простые примеры
            examples = get_unique_list(lambda: fill(template), count)

            # 2. Комбинации (символ + оператор + переменная)
            comb = get_unique_list(
                lambda: f"{fill(template)} {random.choice(field_ops)} {get_var()}",
                count
            )

            # Генерируем вложения и уравнения
            outer = []
            inner = []
            equations = []

            # Для вложений и уравнений используем тот же принцип уникальности
            def gen_outer():
                other = random.choice(all_templates)
                return template.replace("@", fill(other), 1) if "@" in template else f"{template} {fill(other)}"

            def gen_inner():
                other = random.choice(all_templates)
                # Если в 'other' нет @, просто ставим рядом
                return other.replace("@", fill(template), 1) if "@" in other else f"{fill(other)} {template}"

            def gen_eq():
                rhs = f"{get_var()} {random.choice(field_ops)} {fill(random.choice(all_templates))}"
                return f"{fill(template)} = {rhs}"

            outer = get_unique_list(gen_outer, count)
            inner = get_unique_list(gen_inner, count)
            equations = get_unique_list(gen_eq, count)

            entry = {
                "field": field_name,
                "symbol_name": struct["name"],
                "base_cmd": template.replace("@", "x"),
                "examples": examples,
                "comb": comb,
                "outer": outer,
                "inner": inner,
                "equations": equations
            }

            final_output.append(entry)

        print(f"Область {field_name}: обработана.")

    with open("results/scripts.json", "w", encoding="utf-8") as f:
        json.dump(final_output, f, indent=2, ensure_ascii=False)

    print(f"\nГотово! Результаты в results/scripts.json. Всего символов: {len(final_output)}")

if __name__ == "__main__":
    run_generator()
