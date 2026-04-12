# LaTeX Formula Dataset Generator

## Что это

Генератор обучающих примеров математических формул в LaTeX для маленьких LLM.

## Как работает

1. Берёт символы из `config/symbols.jsonl` (sin, cos, int, frac...)
2. Для каждого генерирует 7 типов формул:
   - `sym(@)` → sin(x)
   - `sym(@) ? next(@)` → sin(a) + cos(b)
   - `next(@) ? sym(@)` → cos(x) - sin(y)
   - `sym(next(@))` → sin(cos(x))
   - `next(sym(@))` → cos(sin(x))
   - `sym(next(@)) ? next(sym(@))` → sin(cos(a)) = cos(sin(b))
   - `next(sym(@)) ? sym(next(@))` → cos(sin(x)) > sin(cos(y))
3. Каждый пример дублируется с линейным коэффициентом: `3*sin(x)`, `5 + 2*sin(x)`
4. Переменные берут из греческих и латинских букв
5. Операторы: +, -, /

## Конфиги

- `config/symbols.jsonl` — все LaTeX символы
- `config/greeks.jsonl` — греческие буквы
- `config/latins.jsonl` — латинские буквы
- `config/special_symbols.jsonl` — символы с особой обработкой (интегралы, дроби...)
- `config/non_function_symbols.jsonl` — символы, которые не могут быть функциями

## Запуск

```bash
python generator.py

## Настройка
only_symbols = ['\\sin', '\\int']  # Какие символы генерировать
generator = LatexFormulaGenerator(config_path, samples_per_type=3)  # 3 примера на тип

## return
{
  "sec": "trigonometry",
  "sym": "\\sin",
  "rus": "синус",
  "eng": "sine",
  "script": "\\sin(\\alpha)",
  "scheme": "sym(@)"
}

## Важно

Все формулы с круглыми скобками: \sin(x), а не \sin x
Интегралы всегда с дифференциалом: \int x dx
Частные производные допускаются без аргумента (для синтаксиса)
only_symbols ограничивает и sym, и next
