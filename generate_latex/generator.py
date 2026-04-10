import json
import random
from pathlib import Path

class LatexFormulaGenerator:
    def __init__(self, config_dir, samples_per_type=3):
        self.config_dir = Path(config_dir)
        self.samples_per_type = samples_per_type  # Количество примеров на каждый тип
        self.greeks = self._load_jsonl('greeks.jsonl')
        self.latins = self._load_jsonl('latins.jsonl')
        self.symbols = self._load_jsonl('symbols.jsonl')

        # Создаём списки символов для подстановки
        self.greek_symbols = [g['sym'] for g in self.greeks]
        self.latin_symbols = [l['sym'] for l in self.latins if l['sym'] != '@']
        self.all_vars = self.greek_symbols + self.latin_symbols

        # Арифметические операторы для ? (только +, -, /)
        self.arithmetic_ops = ['+', '-', '/']

        # Символы, которые нельзя использовать как функции (константы, специальные символы)
        self.non_function_symbols = {
            '\\infty',      # бесконечность
            '\\emptyset',   # пустое множество
            '\\ell',        # эль (обычно константа)
            '\\nabla',      # набла (оператор)
            '\\Delta',      # дельта (может быть константой)
            '\\partial',    # частная производная (оператор)
            '\\hbar',       # постоянная Дирака
            '\\dots',       # многоточие
            '\\cdots',      # многоточие
            '!',            # факториал (постфиксный оператор)
            '^',            # степень (бинарный оператор)
            '_',            # индекс (бинарный оператор)
        }

    def _load_jsonl(self, filename):
        """Загрузка JSONL файла"""
        data = []
        with open(self.config_dir / filename, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    data.append(json.loads(line))
        return data

    def _get_random_vars(self, count):
        """Получить случайные переменные (греческие или латинские)"""
        return random.sample(self.all_vars, min(count, len(self.all_vars)))

    def _is_valid_function_symbol(self, sym):
        """Проверка, может ли символ использоваться как функция"""
        if sym in self.non_function_symbols:
            return False
        # Исключаем бинарные операторы и символы с особым синтаксисом
        if sym in ['+', '-', '=', '/', '>', '<', '\\cdot', '\\times', '\\div', '\\pm', '\\mp']:
            return False
        # Исключаем степени и индексы
        if sym in ['^', '_']:
            return False
        return True

    def _get_random_other_symbol(self, current_sym):
        """Получить случайный другой символ (не current_sym), который может быть функцией"""
        others = [s for s in self.symbols
                 if s['sym'] != current_sym
                 and self._is_valid_function_symbol(s['sym'])]
        if not others:
            # Если нет подходящих символов, возвращаем первый попавшийся
            others = [s for s in self.symbols if s['sym'] != current_sym]
        return random.choice(others)

    def _get_random_op(self):
        """Получить случайный арифметический оператор"""
        return random.choice(self.arithmetic_ops)

    def _transform_variable(self, var):
        """Преобразовать переменную в линейное выражение

        Правила:
        - 50% случаев оставляем как есть (B=1, A нет)
        - 50% случаев преобразуем:
          - A (константа): 50% есть, 50% нет (от 1 до 100)
          - B (коэффициент): 50% =1, 50% от 2 до 100
          - Оператор: случайный из ['+', '-'] если A и B оба есть
          - Порядок: 50% A + Bx, 50% Bx + A
        """
        # 50% - оставляем как есть
        if random.random() < 0.5:
            return var

        # Определяем коэффициенты
        has_A = random.random() < 0.5
        B = 1 if random.random() < 0.5 else random.randint(2, 100)

        # Формируем B×var часть
        if B == 1:
            b_part = var
        else:
            b_part = f"{B}{var}"

        # Если нет A, возвращаем только B×var
        if not has_A:
            return b_part

        # Есть A - добавляем константу
        A = random.randint(1, 100)
        op = random.choice(['+', '-'])

        # 50% вероятность для каждого порядка
        if random.random() < 0.5:
            # Порядок 1: A op Bx
            return f"{A} {op} {b_part}"
        else:
            # Порядок 2: Bx op A
            return f"{b_part} {op} {A}"

    def generate_scripts_for_symbol(self, symbol):
        """Генерация всех скриптов для одного символа"""
        scripts = []

        # 1. Simple: sym(@) - только 1 пример (достаточно)
        var = self._get_random_vars(1)[0]
        transformed_var = self._transform_variable(var)
        scripts.append({
            'sec': symbol['sec'],
            'sym': symbol['sym'],
            'rus': symbol.get('rus', ''),
            'eng': symbol.get('eng', ''),
            'script': f"{symbol['sym']}({transformed_var})",
            'scheme': "sym(@)"
        })

        # Для остальных типов генерируем samples_per_type примеров
        for _ in range(self.samples_per_type):
            # Для каждого примера выбираем новый случайный символ
            other = self._get_random_other_symbol(symbol['sym'])

            # 2. Comb вариант 1: sym(@) ? next(@)
            vars_list = self._get_random_vars(2)
            transformed_vars = [self._transform_variable(v) for v in vars_list]
            op = self._get_random_op()
            scripts.append({
                'sec': symbol['sec'],
                'sym': symbol['sym'],
                'rus': symbol.get('rus', ''),
                'eng': symbol.get('eng', ''),
                'script': f"{symbol['sym']}({transformed_vars[0]}) {op} {other['sym']}({transformed_vars[1]})",
                'scheme': f"sym(@) {op} next(@)"
            })

            other = self._get_random_other_symbol(symbol['sym'])
            # 3. Comb вариант 2: next(@) ? sym(@)
            vars_list = self._get_random_vars(2)
            transformed_vars = [self._transform_variable(v) for v in vars_list]
            op = self._get_random_op()
            scripts.append({
                'sec': symbol['sec'],
                'sym': symbol['sym'],
                'rus': symbol.get('rus', ''),
                'eng': symbol.get('eng', ''),
                'script': f"{other['sym']}({transformed_vars[0]}) {op} {symbol['sym']}({transformed_vars[1]})",
                'scheme': f"next(@) {op} sym(@)"
            })

            other = self._get_random_other_symbol(symbol['sym'])
            # 4. Nest вариант 1: sym(next(@))
            var = self._get_random_vars(1)[0]
            transformed_var = self._transform_variable(var)
            scripts.append({
                'sec': symbol['sec'],
                'sym': symbol['sym'],
                'rus': symbol.get('rus', ''),
                'eng': symbol.get('eng', ''),
                'script': f"{symbol['sym']}({other['sym']}({transformed_var}))",
                'scheme': "sym(next(@))"
            })

            other = self._get_random_other_symbol(symbol['sym'])
            # 5. Nest вариант 2: next(sym(@))
            var = self._get_random_vars(1)[0]
            transformed_var = self._transform_variable(var)
            scripts.append({
                'sec': symbol['sec'],
                'sym': symbol['sym'],
                'rus': symbol.get('rus', ''),
                'eng': symbol.get('eng', ''),
                'script': f"{other['sym']}({symbol['sym']}({transformed_var}))",
                'scheme': "next(sym(@))"
            })

            other = self._get_random_other_symbol(symbol['sym'])
            # 6. Cnest вариант 1: sym(next(@)) ? next(sym(@))
            vars_list = self._get_random_vars(2)
            transformed_vars = [self._transform_variable(v) for v in vars_list]
            op = self._get_random_op()
            scripts.append({
                'sec': symbol['sec'],
                'sym': symbol['sym'],
                'rus': symbol.get('rus', ''),
                'eng': symbol.get('eng', ''),
                'script': f"{symbol['sym']}({other['sym']}({transformed_vars[0]})) {op} {other['sym']}({symbol['sym']}({transformed_vars[1]}))",
                'scheme': f"sym(next(@)) {op} next(sym(@))"
            })

            other = self._get_random_other_symbol(symbol['sym'])
            # 7. Cnest вариант 2: next(sym(@)) ? sym(next(@))
            vars_list = self._get_random_vars(2)
            transformed_vars = [self._transform_variable(v) for v in vars_list]
            op = self._get_random_op()
            scripts.append({
                'sec': symbol['sec'],
                'sym': symbol['sym'],
                'rus': symbol.get('rus', ''),
                'eng': symbol.get('eng', ''),
                'script': f"{other['sym']}({symbol['sym']}({transformed_vars[0]})) {op} {symbol['sym']}({other['sym']}({transformed_vars[1]}))",
                'scheme': f"next(sym(@)) {op} sym(next(@))"
            })

        return scripts

    def save_scripts(self, output_dir):
        """Сохранить все скрипты в JSONL файл"""
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        output_file = output_path / 'dataset.jsonl'

        with open(output_file, 'w', encoding='utf-8') as f:
            # Убрать ограничение для полной генерации
            target_symbols = ['\\sin', '\\int']  # Для тестирования
            # target_symbols = [s['sym'] for s in self.symbols]  # Для полной генерации

            for symbol in self.symbols:
                # Временно ограничиваемся только sin и int
                if symbol['sym'] not in target_symbols:
                    continue

                scripts = self.generate_scripts_for_symbol(symbol)

                for script in scripts:
                    f.write(json.dumps(script, ensure_ascii=False) + '\n')

        print(f"\n\nСкрипты сохранены в: {output_file}")
        total = sum(1 for _ in open(output_file, 'r', encoding='utf-8'))
        print(f"Всего сгенерировано записей: {total}")
        return output_file


def main():
    config_path = "/home/michael/LLM/datasets_bhl/generate_latex/config"
    output_path = "/home/michael/LLM/datasets_bhl/generate_latex/scripts"

    # samples_per_type=3 означает 3 примера на каждый тип (кроме simple)
    generator = LatexFormulaGenerator(config_path, samples_per_type=3)
    generator.save_scripts(output_path)


if __name__ == "__main__":
    main()
