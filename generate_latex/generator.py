import json
import random
from pathlib import Path

class LatexFormulaGenerator:
    def __init__(self, config_dir, global_multiplier=1):
        self.config_dir = Path(config_dir)
        self.global_multiplier = global_multiplier

        # Загрузка данных
        self.greeks = self._load_jsonl('greeks.jsonl')
        self.latins = self._load_jsonl('latins.jsonl')
        self.symbols = self._load_jsonl('symbols.jsonl')
        self.arithmetics = self._load_jsonl('arithmetics.jsonl')

        # Переменные (латинские + греческие)
        self.latin_vars = [l['sym'] for l in self.latins if l['sym'] != '@']
        self.greek_vars = [g['sym'] for g in self.greeks]
        self.all_vars = self.latin_vars + self.greek_vars
        self.variable_set = set(self.all_vars)

        # Числа от 1 до 100
        self.numbers = list(range(1, 101))

        # Операторы
        self.operators = []
        self.op_symbols = []
        for op in self.arithmetics:
            sym = op.get('sym', '')
            if sym:
                self.operators.append(op)
                self.op_symbols.append(sym)

        # Схемы символов и их смыслы
        self.symbol_schemes = {}  # sym -> list of schemes
        self.symbol_sense = {}    # sym -> sense
        for s in self.symbols:
            if 'scheme' in s:
                schemes = [sch.strip() for sch in s['scheme'].split(',')]
                self.symbol_schemes[s['sym']] = schemes
            if 'sense' in s:
                self.symbol_sense[s['sym']] = s['sense']

        # Веса типов
        self.example_types = {
            'atomic_var': {'weight': 5, 'generator': self._gen_atomic_var},
            'atomic_num': {'weight': 0, 'generator': self._gen_atomic_num},
            'atomic_diff': {'weight': 5, 'generator': self._gen_atomic_diff},
            'simple': {'weight': 15, 'generator': self._gen_simple},
            'binary_forward': {'weight': 8, 'generator': self._gen_binary_forward},
            'binary_backward': {'weight': 8, 'generator': self._gen_binary_backward},
            'nest_forward': {'weight': 6, 'generator': self._gen_nest_forward},
            'nest_backward': {'weight': 6, 'generator': self._gen_nest_backward},
            'cnest_forward': {'weight': 4, 'generator': self._gen_cnest_forward},
            'cnest_backward': {'weight': 4, 'generator': self._gen_cnest_backward},
        }

    def _load_jsonl(self, filename):
        data = []
        try:
            with open(self.config_dir / filename, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        data.append(json.loads(line))
        except FileNotFoundError:
            print(f"⚠️ Файл не найден: {filename}")
        return data

    def _get_random_vars(self, count):
        return random.sample(self.all_vars, min(count, len(self.all_vars)))

    def _is_variable(self, sym):
        return sym in self.variable_set

    def _get_scheme_for_symbol(self, sym):
        if self._is_variable(sym):
            return "@"
        schemes = self.symbol_schemes.get(sym, [])
        return random.choice(schemes) if schemes else None

    def _get_sense_for_symbol(self, sym):
        if self._is_variable(sym):
            return "var"
        return self.symbol_sense.get(sym, None)

    def _get_scheme_for_operator(self, op_sym):
        for op in self.operators:
            if op['sym'] == op_sym:
                return op.get('scheme', f"@ {op_sym} @")
        return f"@ {op_sym} @"

    def _get_sense_for_operator(self, op_sym):
        for op in self.operators:
            if op['sym'] == op_sym:
                return op.get('rus', op_sym)
        return op_sym

    def _apply_scheme(self, scheme, vars_list):
        result = scheme
        for var in vars_list:
            result = result.replace('@', var, 1)
        return result

    def _build_sense_scheme(self, scheme, args_schemes):
        """Построение sense_scheme из схемы и смыслов аргументов"""
        result = scheme
        for arg_scheme in args_schemes:
            if '@' in result:
                result = result.replace('@', arg_scheme, 1)
            else:
                result = f"{result}({arg_scheme})"
        result = result.replace('@', 'var')
        return result

    def _get_random_other_symbol(self, current_sym, exclude_sym=None):
        candidates = [s for s in self.symbols
                     if s['sym'] != current_sym
                     and not self._is_variable(s['sym'])
                     and s.get('scheme')]
        if exclude_sym:
            candidates = [s for s in candidates if s['sym'] != exclude_sym]
        return random.choice(candidates) if candidates else None

    def _get_random_operator(self):
        return random.choice(self.operators) if self.operators else None

    # ========== Атомарные типы ==========
    def _gen_atomic_var(self):
        examples = []
        for var in self.all_vars:
            examples.append({
                'script': var,
                'type': 'atomic_var',
                'sense_scheme': 'var'
            })
        return examples

    def _gen_atomic_num(self):
        examples = []
        for num in self.numbers:
            examples.append({
                'script': str(num),
                'type': 'atomic_num',
                'sense_scheme': 'num'
            })
        return examples

    def _gen_atomic_diff(self):
        examples = []
        for var in self.all_vars:
            clean_var = var.replace('\\', '')
            examples.append({
                'script': f'd{clean_var}',
                'type': 'atomic_diff',
                'sense_scheme': 'diff'
            })
        return examples

    # ========== Simple тип ==========
    def _gen_simple(self, symbol):
        scheme = self._get_scheme_for_symbol(symbol['sym'])
        sense = self._get_sense_for_symbol(symbol['sym'])
        if not scheme or not sense:
            return None

        at_count = scheme.count('@')
        vars_list = self._get_random_vars(at_count) if at_count > 0 else []
        script = self._apply_scheme(scheme, vars_list)

        # Строим sense_scheme
        args_schemes = ['var'] * at_count
        sense_scheme = self._build_sense_scheme(sense, args_schemes)

        return {
            'script': script,
            'type': 'simple',
            'sense_scheme': sense_scheme
        }

    # ========== Бинарные операции ==========
    def _gen_binary_forward(self, symbol, other, op_sym):
        left_scheme = self._get_scheme_for_symbol(symbol['sym'])
        right_scheme = self._get_scheme_for_symbol(other['sym'])
        left_sense = self._get_sense_for_symbol(symbol['sym'])
        right_sense = self._get_sense_for_symbol(other['sym'])
        op_scheme = self._get_scheme_for_operator(op_sym)
        op_sense = self._get_sense_for_operator(op_sym)

        if not left_scheme or not right_scheme or not left_sense or not right_sense:
            return None

        at_left = left_scheme.count('@')
        at_right = right_scheme.count('@')
        vars_list = self._get_random_vars(at_left + at_right)

        left_script = self._apply_scheme(left_scheme, vars_list[:at_left])
        right_script = self._apply_scheme(right_scheme, vars_list[at_left:])

        left_sense_scheme = self._build_sense_scheme(left_sense, ['var'] * at_left)
        right_sense_scheme = self._build_sense_scheme(right_sense, ['var'] * at_right)

        script = self._apply_scheme(op_scheme, [left_script, right_script])
        sense_scheme = f"{left_sense_scheme} {op_sense} {right_sense_scheme}"

        return {
            'script': script,
            'type': f'binary_forward_{op_sym}',
            'sense_scheme': sense_scheme
        }

    def _gen_binary_backward(self, symbol, other, op_sym):
        left_scheme = self._get_scheme_for_symbol(other['sym'])
        right_scheme = self._get_scheme_for_symbol(symbol['sym'])
        left_sense = self._get_sense_for_symbol(other['sym'])
        right_sense = self._get_sense_for_symbol(symbol['sym'])
        op_scheme = self._get_scheme_for_operator(op_sym)
        op_sense = self._get_sense_for_operator(op_sym)

        if not left_scheme or not right_scheme or not left_sense or not right_sense:
            return None

        at_left = left_scheme.count('@')
        at_right = right_scheme.count('@')
        vars_list = self._get_random_vars(at_left + at_right)

        left_script = self._apply_scheme(left_scheme, vars_list[:at_left])
        right_script = self._apply_scheme(right_scheme, vars_list[at_left:])

        left_sense_scheme = self._build_sense_scheme(left_sense, ['var'] * at_left)
        right_sense_scheme = self._build_sense_scheme(right_sense, ['var'] * at_right)

        script = self._apply_scheme(op_scheme, [left_script, right_script])
        sense_scheme = f"{left_sense_scheme} {op_sense} {right_sense_scheme}"

        return {
            'script': script,
            'type': f'binary_backward_{op_sym}',
            'sense_scheme': sense_scheme
        }

    # ========== Вложенность ==========
    def _gen_nest_forward(self, symbol, other):
        outer_scheme = self._get_scheme_for_symbol(symbol['sym'])
        inner_scheme = self._get_scheme_for_symbol(other['sym'])
        outer_sense = self._get_sense_for_symbol(symbol['sym'])
        inner_sense = self._get_sense_for_symbol(other['sym'])

        if not outer_scheme or not inner_scheme or not outer_sense or not inner_sense:
            return None

        inner_at = inner_scheme.count('@')
        inner_vars = self._get_random_vars(inner_at)
        inner_script = self._apply_scheme(inner_scheme, inner_vars)
        inner_sense_scheme = self._build_sense_scheme(inner_sense, ['var'] * inner_at)

        outer_script = outer_scheme.replace('@', inner_script, 1)
        remaining = outer_script.count('@')
        if remaining > 0:
            outer_vars = self._get_random_vars(remaining)
            outer_script = self._apply_scheme(outer_script, outer_vars)

        outer_sense_scheme = self._build_sense_scheme(outer_sense, [inner_sense_scheme] + ['var'] * remaining)

        return {
            'script': outer_script,
            'type': 'nest_forward',
            'sense_scheme': outer_sense_scheme
        }

    def _gen_nest_backward(self, symbol, other):
        outer_scheme = self._get_scheme_for_symbol(other['sym'])
        inner_scheme = self._get_scheme_for_symbol(symbol['sym'])
        outer_sense = self._get_sense_for_symbol(other['sym'])
        inner_sense = self._get_sense_for_symbol(symbol['sym'])

        if not outer_scheme or not inner_scheme or not outer_sense or not inner_sense:
            return None

        inner_at = inner_scheme.count('@')
        inner_vars = self._get_random_vars(inner_at)
        inner_script = self._apply_scheme(inner_scheme, inner_vars)
        inner_sense_scheme = self._build_sense_scheme(inner_sense, ['var'] * inner_at)

        outer_script = outer_scheme.replace('@', inner_script, 1)
        remaining = outer_script.count('@')
        if remaining > 0:
            outer_vars = self._get_random_vars(remaining)
            outer_script = self._apply_scheme(outer_script, outer_vars)

        outer_sense_scheme = self._build_sense_scheme(outer_sense, [inner_sense_scheme] + ['var'] * remaining)

        return {
            'script': outer_script,
            'type': 'nest_backward',
            'sense_scheme': outer_sense_scheme
        }

    # ========== Сложная вложенность ==========
    def _gen_cnest_forward(self, symbol, other_left, other_right, op_sym):
        sym_scheme = self._get_scheme_for_symbol(symbol['sym'])
        left_scheme = self._get_scheme_for_symbol(other_left['sym'])
        right_scheme = self._get_scheme_for_symbol(other_right['sym'])
        sym_sense = self._get_sense_for_symbol(symbol['sym'])
        left_sense = self._get_sense_for_symbol(other_left['sym'])
        right_sense = self._get_sense_for_symbol(other_right['sym'])
        op_scheme = self._get_scheme_for_operator(op_sym)
        op_sense = self._get_sense_for_operator(op_sym)

        if not all([sym_scheme, left_scheme, right_scheme, sym_sense, left_sense, right_sense]):
            return None

        left_inner_vars = self._get_random_vars(left_scheme.count('@'))
        left_inner = self._apply_scheme(left_scheme, left_inner_vars)
        left_inner_sense = self._build_sense_scheme(left_sense, ['var'] * left_scheme.count('@'))

        left_part = sym_scheme.replace('@', left_inner, 1)
        left_remaining = left_part.count('@')
        if left_remaining > 0:
            left_vars = self._get_random_vars(left_remaining)
            left_part = self._apply_scheme(left_part, left_vars)
        left_sense_part = self._build_sense_scheme(sym_sense, [left_inner_sense] + ['var'] * left_remaining)

        right_inner_scheme = self._get_scheme_for_symbol(symbol['sym'])
        right_inner_vars = self._get_random_vars(right_inner_scheme.count('@'))
        right_inner = self._apply_scheme(right_inner_scheme, right_inner_vars)
        right_inner_sense = self._build_sense_scheme(sym_sense, ['var'] * right_inner_scheme.count('@'))

        right_part = right_scheme.replace('@', right_inner, 1)
        right_remaining = right_part.count('@')
        if right_remaining > 0:
            right_vars = self._get_random_vars(right_remaining)
            right_part = self._apply_scheme(right_part, right_vars)
        right_sense_part = self._build_sense_scheme(right_sense, [right_inner_sense] + ['var'] * right_remaining)

        script = self._apply_scheme(op_scheme, [left_part, right_part])
        sense_scheme = f"{left_sense_part} {op_sense} {right_sense_part}"

        return {
            'script': script,
            'type': f'cnest_forward_{op_sym}',
            'sense_scheme': sense_scheme
        }

    def _gen_cnest_backward(self, symbol, other_left, other_right, op_sym):
        left_scheme = self._get_scheme_for_symbol(other_left['sym'])
        right_scheme = self._get_scheme_for_symbol(other_right['sym'])
        sym_scheme = self._get_scheme_for_symbol(symbol['sym'])
        left_sense = self._get_sense_for_symbol(other_left['sym'])
        right_sense = self._get_sense_for_symbol(other_right['sym'])
        sym_sense = self._get_sense_for_symbol(symbol['sym'])
        op_scheme = self._get_scheme_for_operator(op_sym)
        op_sense = self._get_sense_for_operator(op_sym)

        if not all([left_scheme, right_scheme, sym_scheme, left_sense, right_sense, sym_sense]):
            return None

        left_inner_scheme = self._get_scheme_for_symbol(symbol['sym'])
        left_inner_vars = self._get_random_vars(left_inner_scheme.count('@'))
        left_inner = self._apply_scheme(left_inner_scheme, left_inner_vars)
        left_inner_sense = self._build_sense_scheme(sym_sense, ['var'] * left_inner_scheme.count('@'))

        left_part = left_scheme.replace('@', left_inner, 1)
        left_remaining = left_part.count('@')
        if left_remaining > 0:
            left_vars = self._get_random_vars(left_remaining)
            left_part = self._apply_scheme(left_part, left_vars)
        left_sense_part = self._build_sense_scheme(left_sense, [left_inner_sense] + ['var'] * left_remaining)

        right_inner_vars = self._get_random_vars(right_scheme.count('@'))
        right_inner = self._apply_scheme(right_scheme, right_inner_vars)
        right_inner_sense = self._build_sense_scheme(right_sense, ['var'] * right_scheme.count('@'))

        right_part = sym_scheme.replace('@', right_inner, 1)
        right_remaining = right_part.count('@')
        if right_remaining > 0:
            right_vars = self._get_random_vars(right_remaining)
            right_part = self._apply_scheme(right_part, right_vars)
        right_sense_part = self._build_sense_scheme(sym_sense, [right_inner_sense] + ['var'] * right_remaining)

        script = self._apply_scheme(op_scheme, [left_part, right_part])
        sense_scheme = f"{left_sense_part} {op_sense} {right_sense_part}"

        return {
            'script': script,
            'type': f'cnest_backward_{op_sym}',
            'sense_scheme': sense_scheme
        }

    # ========== Генерация датасета ==========
    def generate_dataset(self):
        all_examples = []

        # Атомарные типы
        print("Генерация атомарных типов...")
        for ex_type in ['atomic_var', 'atomic_num', 'atomic_diff']:
            config = self.example_types[ex_type]
            weight = config['weight']
            if weight == 0:
                print(f"  {ex_type}: SKIPPED")
                continue
            examples = config['generator']()
            count = weight * self.global_multiplier
            for _ in range(count):
                for ex in examples:
                    all_examples.append({
                        'sec': 'atomic',
                        'sym': ex['script'],
                        'script': ex['script'],
                        'type': ex['type'],
                        'sense_scheme': ex['sense_scheme']
                    })
            print(f"  {ex_type}: {len(examples)} × {count} = {len(examples) * count}")

        # Simple тип
        print("\nГенерация simple типов...")
        simple_config = self.example_types['simple']
        simple_weight = simple_config['weight']
        if simple_weight > 0:
            simple_count = simple_weight * self.global_multiplier
            generated = 0
            for symbol in self.symbols:
                if self._is_variable(symbol['sym']):
                    continue
                for _ in range(simple_count):
                    ex = self._gen_simple(symbol)
                    if ex:
                        all_examples.append({
                            'sec': symbol['sec'],
                            'sym': symbol['sym'],
                            'script': ex['script'],
                            'type': ex['type'],
                            'sense_scheme': ex['sense_scheme']
                        })
                        generated += 1
            print(f"  simple: {generated} примеров")

        # Составные типы
        print("\nГенерация составных типов...")
        complex_types = ['binary_forward', 'binary_backward', 'nest_forward',
                         'nest_backward', 'cnest_forward', 'cnest_backward']

        for ex_type in complex_types:
            config = self.example_types[ex_type]
            weight = config['weight']
            if weight == 0:
                print(f"  {ex_type}: SKIPPED")
                continue

            target_count = weight * self.global_multiplier
            generated = 0

            for symbol in self.symbols:
                if self._is_variable(symbol['sym']):
                    continue
                for _ in range(target_count):
                    if 'cnest' in ex_type:
                        other_left = self._get_random_other_symbol(symbol['sym'])
                        if not other_left:
                            continue
                        other_right = self._get_random_other_symbol(symbol['sym'], exclude_sym=other_left['sym'])
                        if not other_right:
                            other_right = other_left
                        op = self._get_random_operator()
                        if not op:
                            continue
                        op_sym = op['sym']
                        ex = config['generator'](symbol, other_left, other_right, op_sym)
                    else:
                        other = self._get_random_other_symbol(symbol['sym'])
                        if not other:
                            continue
                        if 'binary' in ex_type:
                            op = self._get_random_operator()
                            if not op:
                                continue
                            ex = config['generator'](symbol, other, op['sym'])
                        else:
                            ex = config['generator'](symbol, other)

                    if ex:
                        all_examples.append({
                            'sec': symbol['sec'],
                            'sym': symbol['sym'],
                            'script': ex['script'],
                            'type': ex['type'],
                            'sense_scheme': ex['sense_scheme']
                        })
                        generated += 1
            print(f"  {ex_type}: {generated} примеров")

        print("\nПеремешивание...")
        random.shuffle(all_examples)
        return all_examples

    def save_dataset(self, output_dir, filename='dataset.jsonl'):
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        output_file = output_path / filename

        print(f"\n{'='*60}")
        print(f"Генерация датасета с multiplier={self.global_multiplier}")
        print(f"{'='*60}\n")

        dataset = self.generate_dataset()

        with open(output_file, 'w', encoding='utf-8') as f:
            for example in dataset:
                f.write(json.dumps(example, ensure_ascii=False) + '\n')

        print(f"\n{'='*60}")
        print(f"✅ Датасет сохранён: {output_file}")
        print(f"📊 Всего примеров: {len(dataset)}")
        print(f"{'='*60}")


def main():
    config_path = "/home/michael/LLM/datasets_bhl/generate_latex/config"
    output_path = "/home/michael/LLM/datasets_bhl/generate_latex/scripts"

    generator = LatexFormulaGenerator(config_path, global_multiplier=1)
    generator.save_dataset(output_path)


if __name__ == "__main__":
    main()
