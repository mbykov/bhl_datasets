import json
import random
import re
from pathlib import Path

class LatexFormulaGenerator:
    def __init__(self, config_dir, samples_per_type=3, only_symbols=None):
        self.config_dir = Path(config_dir)
        self.samples_per_type = samples_per_type
        self.only_symbols = only_symbols or []

        # Загрузка данных
        self.greeks = self._load_jsonl('greeks.jsonl')
        self.latins = self._load_jsonl('latins.jsonl')
        self.symbols = self._load_jsonl('symbols.jsonl')
        self.special_symbols = self._load_jsonl('special_symbols.jsonl')
        self.non_function_symbols = self._load_jsonl('non_function_symbols.jsonl')

        # Фильтруем символы
        if self.only_symbols:
            self.symbols = [s for s in self.symbols if s['sym'] in self.only_symbols]
            self.special_symbols = [s for s in self.special_symbols if s['sym'] in self.only_symbols]

        # Создаём списки переменных
        self.greek_symbols = [g['sym'] for g in self.greeks]
        self.latin_symbols = [l['sym'] for l in self.latins if l['sym'] != '@']
        self.all_vars = self.greek_symbols + self.latin_symbols

        # Множество не-функций
        self.non_function_set = {item['sym'] for item in self.non_function_symbols}

        # Словарь специальных обработчиков
        self.special_handlers = {}
        for special in self.special_symbols:
            self.special_handlers[special['sym']] = special

        # Арифметические операторы
        self.arithmetic_ops = ['+', '-', '/']
        self.coefficients = list(range(2, 101))

    def _load_jsonl(self, filename):
        data = []
        file_path = self.config_dir / filename
        if not file_path.exists():
            return []
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    data.append(json.loads(line))
        return data

    def _get_random_vars(self, count):
        if count > len(self.all_vars):
            return random.choices(self.all_vars, k=count)
        return random.sample(self.all_vars, count)

    def _is_valid_function_symbol(self, sym):
        if sym in self.non_function_set:
            return False
        if any(x in sym for x in ['{}', '[]', '()']):
            return False
        return True

    def _get_random_other_symbol(self, current_sym):
        if self.only_symbols:
            others = [s for s in self.symbols
                     if s['sym'] != current_sym
                     and s['sym'] in self.only_symbols
                     and self._is_valid_function_symbol(s['sym'])]
        else:
            others = [s for s in self.symbols
                     if s['sym'] != current_sym
                     and self._is_valid_function_symbol(s['sym'])]

        if not others:
            others = [s for s in self.symbols if s['sym'] != current_sym]
        return random.choice(others)

    def _get_random_op(self):
        return random.choice(self.arithmetic_ops)

    def _get_random_coefficient(self):
        return random.choice(self.coefficients)

    def _transform_variable(self, var):
        # 50% - оставляем как есть
        if random.random() < 0.5:
            return var

        has_A = random.random() < 0.5
        B = 1 if random.random() < 0.5 else self._get_random_coefficient()

        # Пробел между числом и переменной
        if B == 1:
            b_part = var
        else:
            b_part = f"{B} {var}"

        if not has_A:
            return b_part

        A = self._get_random_coefficient()
        op = random.choice(['+', '-'])

        # Пробелы вокруг оператора
        if random.random() < 0.5:
            return f"{A} {op} {b_part}"
        else:
            return f"{b_part} {op} {A}"

    def _add_linear_variant(self, script, scheme):
        coeff = self._get_random_coefficient()

        if random.random() < 0.5:
            const = self._get_random_coefficient()
            op = random.choice(['+', '-'])
            # Пробелы
            if random.random() < 0.5:
                linear_script = f"{const} {op} {coeff} {script}"
                linear_scheme = f"a + b*({scheme})"
            else:
                linear_script = f"{coeff} {script} {op} {const}"
                linear_scheme = f"b*({scheme}) + a"
        else:
            linear_script = f"{coeff} {script}"
            linear_scheme = f"b*({scheme})"

        return linear_script, linear_scheme

    def _ensure_integral_differential(self, script: str) -> str:
        """Добавляет дифференциал ко всем интегралам, у которых его нет"""

        # Паттерн: \int(что-то) без последующего d...
        pattern = r'\\int\(([^)]+)\)(?!\s*d\s+[a-zA-Z])'

        def add_diff(match):
            inner = match.group(1)
            vars_in_inner = re.findall(r'[a-zA-Zα-ω]+', inner)
            if vars_in_inner:
                diff_var = vars_in_inner[-1]
            else:
                diff_var = 'x'
            return f'\\int({inner}) d {diff_var}'

        script = re.sub(pattern, add_diff, script)

        # Паттерн: \int что-то без последующего d...
        pattern2 = r'\\int\s+([a-zA-Zα-ω\\]+(?:\([^)]*\))?)(?!\s*d\s+[a-zA-Z])'

        def add_diff2(match):
            inner = match.group(1)
            vars_in_inner = re.findall(r'[a-zA-Zα-ω]+', inner)
            if vars_in_inner:
                diff_var = vars_in_inner[-1]
            else:
                diff_var = 'x'
            return f'\\int {inner} d {diff_var}'

        script = re.sub(pattern2, add_diff2, script)

        # Паттерн: \int_{нижний}^{верхний} что-то без d...
        pattern3 = r'\\int\{([^}]+)\}\{([^}]+)\}\s*([a-zA-Zα-ω\\]+(?:\([^)]*\))?)(?!\s*d\s+[a-zA-Z])'

        def add_diff3(match):
            lower = match.group(1)
            upper = match.group(2)
            inner = match.group(3)
            vars_in_inner = re.findall(r'[a-zA-Zα-ω]+', inner)
            if vars_in_inner:
                diff_var = vars_in_inner[-1]
            else:
                diff_var = 'x'
            return f'\\int_{{{lower}}}^{{{upper}}} {inner} d {diff_var}'

        script = re.sub(pattern3, add_diff3, script)

        return script

    def _handle_integral(self, symbol, special_config):
        """Генерация для интегралов"""
        scripts = []
        forms = special_config.get('forms', [])

        for form in forms:
            for _ in range(self.samples_per_type):
                at_count = form.count('@')
                vars_list = self._get_random_vars(at_count)

                script = form
                for var in vars_list:
                    script = script.replace('@', var, 1)

                # Убеждаемся, что есть дифференциал с пробелом
                if 'd@' in script:
                    script = script.replace('d@', f'd {vars_list[-1] if vars_list else "x"}')
                elif 'd' not in script[-2:]:
                    diff_var = vars_list[-1] if vars_list else 'x'
                    script = f"{script} d {diff_var}"

                scripts.append({
                    'sec': symbol['sec'],
                    'sym': symbol['sym'],
                    'rus': symbol.get('rus', ''),
                    'eng': symbol.get('eng', ''),
                    'script': script,
                    'scheme': form
                })

                # Добавляем вариант с линейной функцией
                linear_script, linear_scheme = self._add_linear_variant(script, form)
                scripts.append({
                    'sec': symbol['sec'],
                    'sym': symbol['sym'],
                    'rus': symbol.get('rus', ''),
                    'eng': symbol.get('eng', ''),
                    'script': linear_script,
                    'scheme': linear_scheme
                })

        return scripts

    def _handle_binary_args(self, symbol, special_config):
        scripts = []
        forms = special_config.get('forms', [])

        for form in forms:
            for _ in range(self.samples_per_type):
                at_count = form.count('@')
                vars_list = self._get_random_vars(at_count)

                script = form
                for var in vars_list:
                    script = script.replace('@', var, 1)

                scripts.append({
                    'sec': symbol['sec'],
                    'sym': symbol['sym'],
                    'rus': symbol.get('rus', ''),
                    'eng': symbol.get('eng', ''),
                    'script': script,
                    'scheme': form
                })

                linear_script, linear_scheme = self._add_linear_variant(script, form)
                scripts.append({
                    'sec': symbol['sec'],
                    'sym': symbol['sym'],
                    'rus': symbol.get('rus', ''),
                    'eng': symbol.get('eng', ''),
                    'script': linear_script,
                    'scheme': linear_scheme
                })

        return scripts

    def _handle_unary_arg(self, symbol, special_config):
        scripts = []
        forms = special_config.get('forms', [])

        for form in forms:
            for _ in range(self.samples_per_type):
                at_count = form.count('@')
                vars_list = self._get_random_vars(at_count)

                script = form
                for var in vars_list:
                    script = script.replace('@', var, 1)

                scripts.append({
                    'sec': symbol['sec'],
                    'sym': symbol['sym'],
                    'rus': symbol.get('rus', ''),
                    'eng': symbol.get('eng', ''),
                    'script': script,
                    'scheme': form
                })

                linear_script, linear_scheme = self._add_linear_variant(script, form)
                scripts.append({
                    'sec': symbol['sec'],
                    'sym': symbol['sym'],
                    'rus': symbol.get('rus', ''),
                    'eng': symbol.get('eng', ''),
                    'script': linear_script,
                    'scheme': linear_scheme
                })

        return scripts

    def _handle_binary_op(self, symbol, special_config):
        scripts = []
        forms = special_config.get('forms', [])

        for form in forms:
            for _ in range(self.samples_per_type):
                at_count = form.count('@')
                vars_list = self._get_random_vars(at_count)

                script = form
                for var in vars_list:
                    script = script.replace('@', var, 1)

                scripts.append({
                    'sec': symbol['sec'],
                    'sym': symbol['sym'],
                    'rus': symbol.get('rus', ''),
                    'eng': symbol.get('eng', ''),
                    'script': script,
                    'scheme': form
                })

                linear_script, linear_scheme = self._add_linear_variant(script, form)
                scripts.append({
                    'sec': symbol['sec'],
                    'sym': symbol['sym'],
                    'rus': symbol.get('rus', ''),
                    'eng': symbol.get('eng', ''),
                    'script': linear_script,
                    'scheme': linear_scheme
                })

        return scripts

    def _handle_sum_prod(self, symbol, special_config):
        scripts = []
        forms = special_config.get('forms', [])

        for form in forms:
            for _ in range(self.samples_per_type):
                at_count = form.count('@')
                vars_list = self._get_random_vars(at_count)

                script = form
                for var in vars_list:
                    script = script.replace('@', var, 1)

                scripts.append({
                    'sec': symbol['sec'],
                    'sym': symbol['sym'],
                    'rus': symbol.get('rus', ''),
                    'eng': symbol.get('eng', ''),
                    'script': script,
                    'scheme': form
                })

                linear_script, linear_scheme = self._add_linear_variant(script, form)
                scripts.append({
                    'sec': symbol['sec'],
                    'sym': symbol['sym'],
                    'rus': symbol.get('rus', ''),
                    'eng': symbol.get('eng', ''),
                    'script': linear_script,
                    'scheme': linear_scheme
                })

        return scripts

    def _handle_limit(self, symbol, special_config):
        scripts = []
        forms = special_config.get('forms', [])

        for form in forms:
            for _ in range(self.samples_per_type):
                at_count = form.count('@')
                vars_list = self._get_random_vars(at_count)

                script = form
                for var in vars_list:
                    script = script.replace('@', var, 1)

                scripts.append({
                    'sec': symbol['sec'],
                    'sym': symbol['sym'],
                    'rus': symbol.get('rus', ''),
                    'eng': symbol.get('eng', ''),
                    'script': script,
                    'scheme': form
                })

                linear_script, linear_scheme = self._add_linear_variant(script, form)
                scripts.append({
                    'sec': symbol['sec'],
                    'sym': symbol['sym'],
                    'rus': symbol.get('rus', ''),
                    'eng': symbol.get('eng', ''),
                    'script': linear_script,
                    'scheme': linear_scheme
                })

        return scripts

    def generate_normal_scripts(self, symbol):
        scripts = []

        # 1. Simple: sym(@)
        var = self._get_random_vars(1)[0]
        transformed_var = self._transform_variable(var)
        script = f"{symbol['sym']}({transformed_var})"
        scripts.append({
            'sec': symbol['sec'],
            'sym': symbol['sym'],
            'rus': symbol.get('rus', ''),
            'eng': symbol.get('eng', ''),
            'script': script,
            'scheme': "sym(@)"
        })

        # Линейный вариант для simple
        linear_script, linear_scheme = self._add_linear_variant(script, "sym(@)")
        scripts.append({
            'sec': symbol['sec'],
            'sym': symbol['sym'],
            'rus': symbol.get('rus', ''),
            'eng': symbol.get('eng', ''),
            'script': linear_script,
            'scheme': linear_scheme
        })

        for _ in range(self.samples_per_type):
            # 2. Comb вариант 1: sym(@) ? next(@)
            other1 = self._get_random_other_symbol(symbol['sym'])
            vars_list = self._get_random_vars(2)
            transformed_vars = [self._transform_variable(v) for v in vars_list]
            op = self._get_random_op()
            script = f"{symbol['sym']}({transformed_vars[0]}) {op} {other1['sym']}({transformed_vars[1]})"
            scheme = f"sym(@) {op} next(@)"
            scripts.append({
                'sec': symbol['sec'],
                'sym': symbol['sym'],
                'rus': symbol.get('rus', ''),
                'eng': symbol.get('eng', ''),
                'script': script,
                'scheme': scheme
            })

            linear_script, linear_scheme = self._add_linear_variant(script, scheme)
            scripts.append({
                'sec': symbol['sec'],
                'sym': symbol['sym'],
                'rus': symbol.get('rus', ''),
                'eng': symbol.get('eng', ''),
                'script': linear_script,
                'scheme': linear_scheme
            })

            # 3. Comb вариант 2: next(@) ? sym(@)
            other2 = self._get_random_other_symbol(symbol['sym'])
            vars_list = self._get_random_vars(2)
            transformed_vars = [self._transform_variable(v) for v in vars_list]
            op = self._get_random_op()
            script = f"{other2['sym']}({transformed_vars[0]}) {op} {symbol['sym']}({transformed_vars[1]})"
            scheme = f"next(@) {op} sym(@)"
            scripts.append({
                'sec': symbol['sec'],
                'sym': symbol['sym'],
                'rus': symbol.get('rus', ''),
                'eng': symbol.get('eng', ''),
                'script': script,
                'scheme': scheme
            })

            linear_script, linear_scheme = self._add_linear_variant(script, scheme)
            scripts.append({
                'sec': symbol['sec'],
                'sym': symbol['sym'],
                'rus': symbol.get('rus', ''),
                'eng': symbol.get('eng', ''),
                'script': linear_script,
                'scheme': linear_scheme
            })

            # 4. Nest вариант 1: sym(next(@))
            other3 = self._get_random_other_symbol(symbol['sym'])
            var = self._get_random_vars(1)[0]
            transformed_var = self._transform_variable(var)
            script = f"{symbol['sym']}({other3['sym']}({transformed_var}))"
            scheme = "sym(next(@))"
            scripts.append({
                'sec': symbol['sec'],
                'sym': symbol['sym'],
                'rus': symbol.get('rus', ''),
                'eng': symbol.get('eng', ''),
                'script': script,
                'scheme': scheme
            })

            linear_script, linear_scheme = self._add_linear_variant(script, scheme)
            scripts.append({
                'sec': symbol['sec'],
                'sym': symbol['sym'],
                'rus': symbol.get('rus', ''),
                'eng': symbol.get('eng', ''),
                'script': linear_script,
                'scheme': linear_scheme
            })

            # 5. Nest вариант 2: next(sym(@))
            other4 = self._get_random_other_symbol(symbol['sym'])
            var = self._get_random_vars(1)[0]
            transformed_var = self._transform_variable(var)
            script = f"{other4['sym']}({symbol['sym']}({transformed_var}))"
            scheme = "next(sym(@))"
            scripts.append({
                'sec': symbol['sec'],
                'sym': symbol['sym'],
                'rus': symbol.get('rus', ''),
                'eng': symbol.get('eng', ''),
                'script': script,
                'scheme': scheme
            })

            linear_script, linear_scheme = self._add_linear_variant(script, scheme)
            scripts.append({
                'sec': symbol['sec'],
                'sym': symbol['sym'],
                'rus': symbol.get('rus', ''),
                'eng': symbol.get('eng', ''),
                'script': linear_script,
                'scheme': linear_scheme
            })

            # 6. Cnest вариант 1: sym(next1(@)) ? next2(sym(@))
            other5 = self._get_random_other_symbol(symbol['sym'])
            other6 = self._get_random_other_symbol(symbol['sym'])
            if other5['sym'] == other6['sym'] and len([s for s in self.symbols if s['sym'] != symbol['sym'] and self._is_valid_function_symbol(s['sym'])]) > 1:
                other6 = self._get_random_other_symbol(symbol['sym'])

            vars_list = self._get_random_vars(2)
            transformed_vars = [self._transform_variable(v) for v in vars_list]
            op = self._get_random_op()
            script = f"{symbol['sym']}({other5['sym']}({transformed_vars[0]})) {op} {other6['sym']}({symbol['sym']}({transformed_vars[1]}))"
            scheme = f"sym(next(@)) {op} next(sym(@))"
            scripts.append({
                'sec': symbol['sec'],
                'sym': symbol['sym'],
                'rus': symbol.get('rus', ''),
                'eng': symbol.get('eng', ''),
                'script': script,
                'scheme': scheme
            })

            linear_script, linear_scheme = self._add_linear_variant(script, scheme)
            scripts.append({
                'sec': symbol['sec'],
                'sym': symbol['sym'],
                'rus': symbol.get('rus', ''),
                'eng': symbol.get('eng', ''),
                'script': linear_script,
                'scheme': linear_scheme
            })

            # 7. Cnest вариант 2: next1(sym(@)) ? sym(next2(@))
            other7 = self._get_random_other_symbol(symbol['sym'])
            other8 = self._get_random_other_symbol(symbol['sym'])
            if other7['sym'] == other8['sym'] and len([s for s in self.symbols if s['sym'] != symbol['sym'] and self._is_valid_function_symbol(s['sym'])]) > 1:
                other8 = self._get_random_other_symbol(symbol['sym'])

            vars_list = self._get_random_vars(2)
            transformed_vars = [self._transform_variable(v) for v in vars_list]
            op = self._get_random_op()
            script = f"{other7['sym']}({symbol['sym']}({transformed_vars[0]})) {op} {symbol['sym']}({other8['sym']}({transformed_vars[1]}))"
            scheme = f"next(sym(@)) {op} sym(next(@))"
            scripts.append({
                'sec': symbol['sec'],
                'sym': symbol['sym'],
                'rus': symbol.get('rus', ''),
                'eng': symbol.get('eng', ''),
                'script': script,
                'scheme': scheme
            })

            linear_script, linear_scheme = self._add_linear_variant(script, scheme)
            scripts.append({
                'sec': symbol['sec'],
                'sym': symbol['sym'],
                'rus': symbol.get('rus', ''),
                'eng': symbol.get('eng', ''),
                'script': linear_script,
                'scheme': linear_scheme
            })

        return scripts

    def generate_scripts_for_symbol(self, symbol):
        if symbol['sym'] in self.special_handlers:
            special_config = self.special_handlers[symbol['sym']]
            handler_type = special_config.get('handler')

            handlers_map = {
                'integral': self._handle_integral,
                'binary_args': self._handle_binary_args,
                'unary_arg': self._handle_unary_arg,
                'binary_op': self._handle_binary_op,
                'sum_prod': self._handle_sum_prod,
                'limit': self._handle_limit,
            }

            if handler_type in handlers_map:
                scripts = handlers_map[handler_type](symbol, special_config)
            else:
                scripts = self.generate_normal_scripts(symbol)
        else:
            scripts = self.generate_normal_scripts(symbol)

        # Пост-обработка: добавляем дифференциалы ко всем интегралам
        for script_obj in scripts:
            script_obj['script'] = self._ensure_integral_differential(script_obj['script'])

        return scripts

    def save_scripts(self, output_dir):
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        output_file = output_path / 'dataset.jsonl'

        all_scripts = []
        total_symbols = len(self.symbols)

        for idx, symbol in enumerate(self.symbols):
            print(f"Обработка символа [{idx+1}/{total_symbols}]: {symbol['sym']}")
            scripts = self.generate_scripts_for_symbol(symbol)
            all_scripts.extend(scripts)

        # Сохраняем финальный файл
        with open(output_file, 'w', encoding='utf-8') as f:
            for script in all_scripts:
                f.write(json.dumps(script, ensure_ascii=False) + '\n')

        print(f"\n✅ Скрипты сохранены в: {output_file}")
        print(f"📊 Всего сгенерировано записей: {len(all_scripts)}")
        return output_file


def main():
    config_path = Path("/home/michael/LLM/datasets_bhl/generate_latex/config")
    output_path = Path("/home/michael/LLM/datasets_bhl/generate_latex/scripts")

    # Только нужные символы для теста
    only_symbols = [
        '\\sin',
        '\\int',
        '\\cos',
        '\\frac{}{}',
    ]

    generator = LatexFormulaGenerator(config_path, samples_per_type=2, only_symbols=only_symbols)
    generator.save_scripts(output_path)


if __name__ == "__main__":
    main()
