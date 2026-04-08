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

        # Арифметические операторы для ?
        self.arithmetic_ops = ['+', '-', '=', '/', '>', '<']

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

    def _get_random_other_symbol(self, current_sym):
        """Получить случайный другой символ (не current_sym)"""
        others = [s for s in self.symbols if s['sym'] != current_sym]
        return random.choice(others)

    def _get_random_op(self):
        """Получить случайный арифметический оператор"""
        return random.choice(self.arithmetic_ops)

    def generate_scripts_for_symbol(self, symbol):
        """Генерация всех скриптов для одного символа"""
        scripts = []

        # 1. Simple: sym(@) - только 1 пример (достаточно)
        var = self._get_random_vars(1)[0]
        scripts.append({
            'sec': symbol['sec'],
            'sym': symbol['sym'],
            'rus': symbol.get('rus', ''),
            'eng': symbol.get('eng', ''),
            'script': f"{symbol['sym']}({var})",
            'scheme': "sym(@)"
        })

        # Для остальных типов генерируем samples_per_type примеров
        for _ in range(self.samples_per_type):
            # Для каждого примера выбираем новый случайный символ
            other = self._get_random_other_symbol(symbol['sym'])

            # 2. Comb вариант 1: sym(@) ? next(@)
            vars_list = self._get_random_vars(2)
            op = self._get_random_op()
            scripts.append({
                'sec': symbol['sec'],
                'sym': symbol['sym'],
                'rus': symbol.get('rus', ''),
                'eng': symbol.get('eng', ''),
                'script': f"{symbol['sym']}({vars_list[0]}) {op} {other['sym']}({vars_list[1]})",
                'scheme': f"sym(@) {op} next(@)"
            })

            # 3. Comb вариант 2: next(@) ? sym(@)
            vars_list = self._get_random_vars(2)
            op = self._get_random_op()
            scripts.append({
                'sec': symbol['sec'],
                'sym': symbol['sym'],
                'rus': symbol.get('rus', ''),
                'eng': symbol.get('eng', ''),
                'script': f"{other['sym']}({vars_list[0]}) {op} {symbol['sym']}({vars_list[1]})",
                'scheme': f"next(@) {op} sym(@)"
            })

            # 4. Nest вариант 1: sym(next(@))
            var = self._get_random_vars(1)[0]
            scripts.append({
                'sec': symbol['sec'],
                'sym': symbol['sym'],
                'rus': symbol.get('rus', ''),
                'eng': symbol.get('eng', ''),
                'script': f"{symbol['sym']}({other['sym']}({var}))",
                'scheme': "sym(next(@))"
            })

            # 5. Nest вариант 2: next(sym(@))
            var = self._get_random_vars(1)[0]
            scripts.append({
                'sec': symbol['sec'],
                'sym': symbol['sym'],
                'rus': symbol.get('rus', ''),
                'eng': symbol.get('eng', ''),
                'script': f"{other['sym']}({symbol['sym']}({var}))",
                'scheme': "next(sym(@))"
            })

            # 6. Cnest вариант 1: sym(next(@)) ? next(sym(@))
            vars_list = self._get_random_vars(2)
            op = self._get_random_op()
            scripts.append({
                'sec': symbol['sec'],
                'sym': symbol['sym'],
                'rus': symbol.get('rus', ''),
                'eng': symbol.get('eng', ''),
                'script': f"{symbol['sym']}({other['sym']}({vars_list[0]})) {op} {other['sym']}({symbol['sym']}({vars_list[1]}))",
                'scheme': f"sym(next(@)) {op} next(sym(@))"
            })

            # 7. Cnest вариант 2: next(sym(@)) ? sym(next(@))
            vars_list = self._get_random_vars(2)
            op = self._get_random_op()
            scripts.append({
                'sec': symbol['sec'],
                'sym': symbol['sym'],
                'rus': symbol.get('rus', ''),
                'eng': symbol.get('eng', ''),
                'script': f"{other['sym']}({symbol['sym']}({vars_list[0]})) {op} {symbol['sym']}({other['sym']}({vars_list[1]}))",
                'scheme': f"next(sym(@)) {op} sym(next(@))"
            })

        return scripts

    def save_scripts(self, output_dir):
        """Сохранить все скрипты в JSONL файл"""
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        output_file = output_path / 'dataset.jsonl'

        with open(output_file, 'w', encoding='utf-8') as f:
            # Ограничение: только sin и int (можно потом убрать)
            # target_symbols = ['\\sin', '\\int']

            for symbol in self.symbols:
                # Временно ограничиваемся только sin и int
                # if symbol['sym'] not in target_symbols:
                #     continue

                # print(f"\nОбработка символа: {symbol['sym']}")
                scripts = self.generate_scripts_for_symbol(symbol)

                for script in scripts:
                    f.write(json.dumps(script, ensure_ascii=False) + '\n')
                    # print(f"  {script['scheme']}: {script['script']}")

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
