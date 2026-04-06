import json
import os
import random

# Наборы переменных
GREEK = [r"\alpha", r"\beta", r"\gamma", r"\mu", r"\nu", r"\rho", r"\sigma", r"\psi", r"\phi", r"\omega"]
LATIN = ["x", "y", "z", "p", "q", "k", "t", "L", "f", "g", "A", "B"]

def get_var():
    return random.choice(LATIN + GREEK)

def fill(template):
    res = template
    while "@" in res:
        res = res.replace("@", get_var(), 1)
    return res

def get_unique_list(generator_func, count):
    results = set()
    attempts = 0
    while len(results) < count and attempts < 100:
        item = generator_func()
        results.add(item)
        attempts += 1
    return list(results)

def run_generator(count=3):
    os.makedirs("result", exist_ok=True)

    if not os.path.exists("data/structures.json"):
        print("Ошибка: Файл data/structures.json не найден!")
        return

    with open("data/structures.json", "r", encoding="utf-8") as f:
        fields = json.load(f)

    all_templates = []
    for f_data in fields.values():
        all_templates.extend([s["sym"] for s in f_data["structures"].values()])

    final_output = []
    total_all_examples = 0

    for field_name, content in fields.items():
        field_examples_count = 0
        field_structs = content["structures"]
        field_ops = content["operators"]

        for key, struct in field_structs.items():
            template = struct["sym"]

            # Генерация всех типов данных
            examples = get_unique_list(lambda: fill(template), count)
            comb = get_unique_list(
                lambda: f"{fill(template)} {random.choice(field_ops)} {get_var()}",
                count
            )

            def gen_outer():
                other = random.choice(all_templates)
                return template.replace("@", fill(other), 1) if "@" in template else f"{template} {fill(other)}"

            def gen_inner():
                other = random.choice(all_templates)
                return other.replace("@", fill(template), 1) if "@" in other else f"{fill(other)} {template}"

            def gen_eq():
                rhs = f"{get_var()} {random.choice(field_ops)} {fill(random.choice(all_templates))}"
                return f"{fill(template)} = {rhs}"

            outer = get_unique_list(gen_outer, count)
            inner = get_unique_list(gen_inner, count)
            equations = get_unique_list(gen_eq, count)

            # Считаем количество сгенерированных строк для этого символа
            symbol_total = len(examples) + len(comb) + len(outer) + len(inner) + len(equations)
            field_examples_count += symbol_total

            entry = {
                "field": field_name,
                "name": struct["name"],
                # "symbol_name": key,
                "base_cmd": template.replace("@", "x"),
                "simple": examples,
                "combination": comb,
                "outer": outer,
                "inner": inner,
                "equations": equations
            }
            final_output.append(entry)

        total_all_examples += field_examples_count
        print(f"Область {field_name}: обработана: {field_examples_count}")

    # Сохранение JSON
    with open("result/scripts.json", "w", encoding="utf-8") as f:
        json.dump(final_output, f, indent=2, ensure_ascii=False)

    print(f"\nГенерация завершена!")
    print(f"Всего символов: {len(final_output)}")
    print(f"Всего примеров во всех областях: {total_all_examples}")

if __name__ == "__main__":
    run_generator(2)
