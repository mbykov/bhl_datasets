import json
import random
from pathlib import Path

class MathDatasetGenerator:
    def __init__(self, config_dir="config"):
        self.config_dir = Path(config_dir)
        self.greeks = self._load_jsonl("greeks.jsonl")
        self.latins = self._load_jsonl("latins.jsonl")
        self.symbols = self._load_jsonl("symbols.jsonl")

        # Словари для быстрого доступа
        self.greek_rus = {item["rus"]: item["sym"] for item in self.greeks}
        self.greek_sym = {item["sym"]: item["rus"] for item in self.greeks}
        self.latin_rus = {}
        for item in self.latins:
            for rus in item["rus"]:
                self.latin_rus[rus] = item["sym"]

        self.vars_rus = list(self.greek_rus.keys()) + list(self.latin_rus.keys())
        self.vars_sym = list(self.greek_sym.keys()) + [item["sym"] for item in self.latins]

        # Числа словами
        self.numbers = {
            "0": ["ноль", "нуль", "ноля"],
            "1": ["один", "единица", "раз"],
            "2": ["два", "двух"],
            "3": ["три", "трёх", "трем"],
            "4": ["четыре", "четырёх"],
            "5": ["пять", "пяти"],
            "6": ["шесть", "шести"],
            "7": ["семь", "семи"],
            "8": ["восемь", "восьми"],
            "9": ["девять", "девяти"],
            "10": ["десять", "десяти"]
        }

        # Степени
        self.powers = {
            "2": ["квадрат", "в квадрате", "в степени два", "в степени 2"],
            "3": ["куб", "в кубе", "в степени три", "в степени 3"],
            "n": ["в степени эн", "в степени икс", "в степени игрек", "в степени альфа", "в степени бета"]
        }

        # Список функций для комбинаций
        self.functions = [
            ("синус", "синус"),
            ("косинус", "косинус"),
            ("тангенс", "тангенс"),
            ("котангенс", "котангенс"),
            ("арксинус", "арксинус"),
            ("арккосинус", "арккосинус"),
            ("арктангенс", "арктангенс"),
            ("арккотангенс", "арккотангенс"),
            ("синус гиперболический", "синус_гиперболический"),
            ("косинус гиперболический", "косинус_гиперболический"),
            ("корень", "корень")
        ]

    def _load_jsonl(self, filename):
        items = []
        with open(self.config_dir / filename, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    items.append(json.loads(line))
        return items

    def _random_var(self, use_latin=True, use_greek=True):
        sources = []
        if use_latin:
            sources.extend(list(self.latin_rus.keys()))
        if use_greek:
            sources.extend(list(self.greek_rus.keys()))
        return random.choice(sources)

    def _random_latin(self):
        return random.choice(list(self.latin_rus.keys()))

    def _random_greek(self):
        return random.choice(list(self.greek_rus.keys()))

    def _random_number(self):
        num = str(random.randint(0, 10))
        word = random.choice(self.numbers[num])
        return num, word

    def _random_operator(self):
        ops = [
            ("плюс", "плюс"),
            ("минус", "минус"),
            ("умножить", "умножить"),
            ("делить", "делить")
        ]
        return random.choice(ops)

    def _random_power(self, base):
        """Генерация степени для base"""
        power_type = random.choice(["2", "3", "n"])
        if power_type == "2":
            phrases = self.powers["2"]
            output = f"{base} в степени 2"
        elif power_type == "3":
            phrases = self.powers["3"]
            output = f"{base} в степени 3"
        else:
            phrases = self.powers["n"]
            # Извлекаем переменную из фразы
            var_phrase = random.choice(phrases)
            # "в степени эн" -> "эн"
            var = var_phrase.split()[-1] if "в степени" in var_phrase else "эн"
            output = f"{base} в степени {var}"
            phrases = [var_phrase]

        phrase = random.choice(phrases)
        input_str = f"{base} {phrase}"

        return input_str, output

    # ========== БАЗОВЫЕ ГЕНЕРАТОРЫ ==========

    def generate_arithmetic(self, count=120):
        """+, -, *, /"""
        examples = []
        for _ in range(count):
            var1 = self._random_var()
            var2 = self._random_var()
            op_rus, op_canon = self._random_operator()

            # x + y
            examples.append({
                "input": f"{var1} {op_rus} {var2}",
                "output": f"{var1} {op_canon} {var2}"
            })

            # x + y + z
            var3 = self._random_var()
            op2_rus, op2_canon = self._random_operator()
            examples.append({
                "input": f"{var1} {op_rus} {var2} {op2_rus} {var3}",
                "output": f"{var1} {op_canon} {var2} {op2_canon} {var3}"
            })

            # x + y (с VSE)
            if random.random() < 0.3:
                examples.append({
                    "input": f"{var1} всё {op_rus} {var2}",
                    "output": f"{var1} {op_canon} {var2}"
                })

        return examples

    def generate_comparisons(self, count=150):
        """=, ≠, >, <, ≥, ≤, ≈, ≡, ∝, ∼"""
        comparisons = [
            ("равно", "равно"),
            ("не равно", "не равно"),
            ("больше", "больше"),
            ("меньше", "меньше"),
            ("больше или равно", "больше_или_равно"),
            ("меньше или равно", "меньше_или_равно"),
            ("приблизительно", "приблизительно"),
            ("тождественно", "тождественно"),
            ("пропорционально", "пропорционально"),
            ("подобно", "подобно")
        ]

        examples = []
        for _ in range(count):
            var1 = self._random_var()
            var2 = self._random_var()
            op_rus, op_canon = random.choice(comparisons)

            examples.append({
                "input": f"{var1} {op_rus} {var2}",
                "output": f"{var1} {op_canon} {var2}"
            })

            # С VSE
            if random.random() < 0.3:
                var3 = self._random_var()
                examples.append({
                    "input": f"{var1} {op_rus} {var2} всё плюс {var3}",
                    "output": f"{var1} {op_canon} {var2} плюс {var3}"
                })

        return examples

    def generate_logic(self, count=120):
        """∀, ∃, ∄, ¬, ∧, ∨, →, ↔, ∴"""
        logic_ops = [
            ("для любого", "для_любого"),
            ("существует", "существует"),
            ("не существует", "не_существует"),
            ("не", "не"),
            ("и", "и"),
            ("или", "или"),
            ("следовательно", "следовательно"),
            ("эквивалентно", "эквивалентно")
        ]

        examples = []
        for _ in range(count):
            var = self._random_var()
            op_rus, op_canon = random.choice(logic_ops)

            examples.append({
                "input": f"{op_rus} {var}",
                "output": f"{op_canon} {var}"
            })

            # Бинарные логические операторы
            if op_rus in ["и", "или", "следовательно", "эквивалентно"]:
                var2 = self._random_var()
                examples.append({
                    "input": f"{var} {op_rus} {var2}",
                    "output": f"{var} {op_canon} {var2}"
                })

        return examples

    def generate_sin(self, count=120):
        examples = []
        for _ in range(count):
            var = self._random_var()

            # sin(x)
            if random.random() < 0.5:
                examples.append({
                    "input": f"синус {var}",
                    "output": f"синус({var})"
                })
            else:
                examples.append({
                    "input": f"синус от {var}",
                    "output": f"синус({var})"
                })

            # sin(x + y)
            var2 = self._random_var()
            op_rus, op_canon = self._random_operator()
            examples.append({
                "input": f"синус {var} {op_rus} {var2}",
                "output": f"синус({var} {op_canon} {var2})"
            })

            # sin(x) всё + y
            if random.random() < 0.4:
                examples.append({
                    "input": f"синус {var} всё {op_rus} {var2}",
                    "output": f"синус({var}) {op_canon} {var2}"
                })

            # sin(x в степени 2)
            power_input, power_output = self._random_power(var)
            examples.append({
                "input": f"синус {power_input}",
                "output": f"синус({power_output})"
            })

        return examples

    def generate_cos_tan_cot(self, count=180):
        funcs = [
            ("косинус", "косинус"), ("тангенс", "тангенс"), ("котангенс", "котангенс"),
            ("арксинус", "арксинус"), ("арккосинус", "арккосинус"), ("арктангенс", "арктангенс"),
            ("арккотангенс", "арккотангенс")
        ]

        examples = []
        for _ in range(count):
            func_rus, func_canon = random.choice(funcs)
            var = self._random_var()

            if random.random() < 0.5:
                examples.append({
                    "input": f"{func_rus} {var}",
                    "output": f"{func_canon}({var})"
                })
            else:
                examples.append({
                    "input": f"{func_rus} от {var}",
                    "output": f"{func_canon}({var})"
                })

            var2 = self._random_var()
            op_rus, op_canon = self._random_operator()
            examples.append({
                "input": f"{func_rus} {var} {op_rus} {var2}",
                "output": f"{func_canon}({var} {op_canon} {var2})"
            })

        return examples

    def generate_hyperbolic(self, count=100):
        """sinh, cosh"""
        funcs = [
            ("синус гиперболический", "синус_гиперболический"),
            ("косинус гиперболический", "косинус_гиперболический")
        ]

        examples = []
        for _ in range(count):
            func_rus, func_canon = random.choice(funcs)
            var = self._random_var()

            if random.random() < 0.5:
                examples.append({
                    "input": f"{func_rus} {var}",
                    "output": f"{func_canon}({var})"
                })
            else:
                examples.append({
                    "input": f"{func_rus} от {var}",
                    "output": f"{func_canon}({var})"
                })

        return examples

    def generate_sqrt(self, count=80):
        examples = []
        for _ in range(count):
            var = self._random_var()

            examples.append({
                "input": f"корень из {var}",
                "output": f"корень({var})"
            })

            var2 = self._random_var()
            op_rus, op_canon = self._random_operator()
            examples.append({
                "input": f"корень из {var} {op_rus} {var2}",
                "output": f"корень({var} {op_canon} {var2})"
            })

            degree = random.choice([2, 3, 4, 5])
            degree_words = {2: "два", 3: "три", 4: "четыре", 5: "пять"}
            examples.append({
                "input": f"корень степени {degree_words[degree]} из {var}",
                "output": f"корень степени {degree}({var})"
            })

        return examples

    def generate_power(self, count=100):
        examples = []
        for _ in range(count):
            var = self._random_var()

            power_input, power_output = self._random_power(var)
            examples.append({
                "input": power_input,
                "output": power_output
            })

            var2 = self._random_var()
            op_rus, op_canon = self._random_operator()
            examples.append({
                "input": f"открыть скобку {var} {op_rus} {var2} закрыть скобку в квадрате",
                "output": f"({var} {op_canon} {var2}) в степени 2"
            })

            examples.append({
                "input": f"синус {var} всё в квадрате",
                "output": f"синус({var}) в степени 2"
            })

        return examples

    def generate_integral(self, count=150):
        examples = []
        for _ in range(count):
            var = self._random_latin()

            examples.append({
                "input": f"интеграл {var} де {var}",
                "output": f"интеграл({var} де {var})"
            })

            examples.append({
                "input": f"интеграл от {var} де {var}",
                "output": f"интеграл({var} де {var})"
            })

            low_num, low_word = self._random_number()
            high_num, high_word = self._random_number()
            examples.append({
                "input": f"интеграл от {low_word} до {high_word} от {var} де {var}",
                "output": f"интеграл от {low_num} до {high_num}({var} де {var})"
            })

            var2 = self._random_greek()
            examples.append({
                "input": f"интеграл от {var2} до {var} от {var} в квадрате де {var}",
                "output": f"интеграл от {var2} до {var}({var} в степени 2 де {var})"
            })

            examples.append({
                "input": f"интеграл синус {var} де {var}",
                "output": f"интеграл(синус({var}) де {var})"
            })

        return examples

    def generate_sum_prod(self, count=100):
        ops = [
            ("сумма", "сумма"),
            ("произведение", "произведение"),
            ("двойной интеграл", "двойной_интеграл"),
            ("контурный интеграл", "контурный_интеграл")
        ]

        examples = []
        for _ in range(count):
            op_rus, op_canon = random.choice(ops)
            var = self._random_var()
            low = self._random_var()
            high = self._random_var()

            examples.append({
                "input": f"{op_rus} от {low} до {high} от {var}",
                "output": f"{op_canon} от {low} до {high}({var})"
            })

        return examples

    # ========== СЛОЖНЫЕ КОМБИНАЦИИ ==========

    def generate_nested_functions(self, count=400):
        """f(g(x)) - вложенные функции"""
        examples = []
        for _ in range(count):
            outer_rus, outer_canon = random.choice(self.functions)
            inner_rus, inner_canon = random.choice(self.functions)
            var = self._random_var()

            # f(g(x))
            examples.append({
                "input": f"{outer_rus} от {inner_rus} {var}",
                "output": f"{outer_canon}({inner_canon}({var}))"
            })

            # f(g(x + y))
            var2 = self._random_var()
            op_rus, op_canon = self._random_operator()
            examples.append({
                "input": f"{outer_rus} от {inner_rus} {var} {op_rus} {var2}",
                "output": f"{outer_canon}({inner_canon}({var} {op_canon} {var2}))"
            })

            # f(g(x)) всё + y (VSE)
            if random.random() < 0.3:
                var3 = self._random_var()
                examples.append({
                    "input": f"{outer_rus} от {inner_rus} {var} всё {op_rus} {var3}",
                    "output": f"{outer_canon}({inner_canon}({var})) {op_canon} {var3}"
                })

        return examples

    def generate_function_of_integral(self, count=250):
        """f(∫ ...)"""
        examples = []
        for _ in range(count):
            func_rus, func_canon = random.choice(self.functions[:10])  # без корня
            var = self._random_latin()

            # f(∫ x dx)
            examples.append({
                "input": f"{func_rus} от интеграл {var} де {var}",
                "output": f"{func_canon}(интеграл({var} де {var}))"
            })

            # f(∫ от 0 до 5 от x dx)
            low_num, low_word = self._random_number()
            high_num, high_word = self._random_number()
            examples.append({
                "input": f"{func_rus} от интеграл от {low_word} до {high_word} от {var} де {var}",
                "output": f"{func_canon}(интеграл от {low_num} до {high_num}({var} де {var}))"
            })

            # f(∫ sin(x) dx)
            examples.append({
                "input": f"{func_rus} от интеграл синус {var} де {var}",
                "output": f"{func_canon}(интеграл(синус({var}) де {var}))"
            })

        return examples

    def generate_integral_of_function(self, count=250):
        """∫ f(x) dx"""
        examples = []
        for _ in range(count):
            func_rus, func_canon = random.choice(self.functions)
            var = self._random_latin()

            # ∫ f(x) dx
            examples.append({
                "input": f"интеграл {func_rus} {var} де {var}",
                "output": f"интеграл({func_canon}({var}) де {var})"
            })

            # ∫ от 0 до 5 от f(x) dx
            low_num, low_word = self._random_number()
            high_num, high_word = self._random_number()
            examples.append({
                "input": f"интеграл от {low_word} до {high_word} от {func_rus} {var} де {var}",
                "output": f"интеграл от {low_num} до {high_num}({func_canon}({var}) де {var})"
            })

            # ∫ от a до b от f(x) dx
            low = self._random_latin()
            high = self._random_latin()
            examples.append({
                "input": f"интеграл от {low} до {high} от {func_rus} {var} де {var}",
                "output": f"интеграл от {low} до {high}({func_canon}({var}) де {var})"
            })

        return examples

    def generate_sum_of_functions(self, count=250):
        """f(x) + g(y)"""
        examples = []
        for _ in range(count):
            f_rus, f_canon = random.choice(self.functions)
            g_rus, g_canon = random.choice(self.functions)
            var1 = self._random_var()
            var2 = self._random_var()
            op_rus, op_canon = self._random_operator()

            # f(x) + g(y)
            examples.append({
                "input": f"{f_rus} {var1} {op_rus} {g_rus} {var2}",
                "output": f"{f_canon}({var1}) {op_canon} {g_canon}({var2})"
            })

            # f(x + y) + g(z)
            var3 = self._random_var()
            examples.append({
                "input": f"{f_rus} {var1} {op_rus} {var2} {op_rus} {g_rus} {var3}",
                "output": f"{f_canon}({var1} {op_canon} {var2}) {op_canon} {g_canon}({var3})"
            })

            # (f(x) + g(y)) в квадрате
            if random.random() < 0.3:
                examples.append({
                    "input": f"открыть скобку {f_rus} {var1} {op_rus} {g_rus} {var2} закрыть скобку в квадрате",
                    "output": f"({f_canon}({var1}) {op_canon} {g_canon}({var2})) в степени 2"
                })

        return examples

    def generate_all(self):
        """Генерация всех примеров"""
        all_examples = []

        print("Generating arithmetic...")
        all_examples.extend(self.generate_arithmetic(count=120))

        print("Generating comparisons...")
        all_examples.extend(self.generate_comparisons(count=150))

        print("Generating logic...")
        all_examples.extend(self.generate_logic(count=120))

        print("Generating sin...")
        all_examples.extend(self.generate_sin(count=120))

        print("Generating cos/tan/cot...")
        all_examples.extend(self.generate_cos_tan_cot(count=180))

        print("Generating hyperbolic...")
        all_examples.extend(self.generate_hyperbolic(count=100))

        print("Generating sqrt...")
        all_examples.extend(self.generate_sqrt(count=80))

        print("Generating power...")
        all_examples.extend(self.generate_power(count=100))

        print("Generating integral...")
        all_examples.extend(self.generate_integral(count=150))

        print("Generating sum/prod...")
        all_examples.extend(self.generate_sum_prod(count=100))

        print("Generating nested functions...")
        all_examples.extend(self.generate_nested_functions(count=400))

        print("Generating function of integral...")
        all_examples.extend(self.generate_function_of_integral(count=250))

        print("Generating integral of function...")
        all_examples.extend(self.generate_integral_of_function(count=250))

        print("Generating sum of functions...")
        all_examples.extend(self.generate_sum_of_functions(count=250))

        # Перемешиваем
        random.shuffle(all_examples)

        return all_examples

    def split_and_save(self, examples, train_size=3000, test_size=300):
        """Разделение на train и test"""
        if len(examples) < train_size + test_size:
            print(f"Warning: Only {len(examples)} examples generated, less than requested {train_size + test_size}")
            train_size = len(examples) - test_size

        train_examples = examples[:train_size]
        test_examples = examples[train_size:train_size + test_size]

        # Сохраняем train
        train_path = Path("result/train.jsonl")
        train_path.parent.mkdir(parents=True, exist_ok=True)
        with open(train_path, 'w', encoding='utf-8') as f:
            for ex in train_examples:
                f.write(json.dumps(ex, ensure_ascii=False) + '\n')

        # Сохраняем test
        test_path = Path("result/test.jsonl")
        with open(test_path, 'w', encoding='utf-8') as f:
            for ex in test_examples:
                f.write(json.dumps(ex, ensure_ascii=False) + '\n')

        print(f"\nSaved {len(train_examples)} examples to {train_path}")
        print(f"Saved {len(test_examples)} examples to {test_path}")

        # print("\n--- Sample train examples ---")
        # for ex in random.sample(train_examples, min(5, len(train_examples))):
        #     print(f"  IN: {ex['input']}")
        #     print(f" OUT: {ex['output']}")
        #     print()

        # print("--- Sample test examples ---")
        # for ex in random.sample(test_examples, min(5, len(test_examples))):
        #     print(f"  IN: {ex['input']}")
        #     print(f" OUT: {ex['output']}")
        #     print()

if __name__ == "__main__":
    gen = MathDatasetGenerator()
    all_examples = gen.generate_all()
    print(f"\nTotal generated: {len(all_examples)} examples")
    gen.split_and_save(all_examples, train_size=3500, test_size=350)
