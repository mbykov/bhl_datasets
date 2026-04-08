# LaTeX Formula Dataset Generator

Генератор обучающего датасета математических формул в формате LaTeX.

## 📁 Структура проекта

generate_latex/
├── config/
│ ├── symbols.jsonl # Символы LaTeX с метаданными
│ ├── greeks.jsonl # Греческие буквы
│ └── latins.jsonl # Латинские буквы
├── scripts/
│ └── dataset.jsonl # Сгенерированный датасет
└── generate.py # Основной скрипт генерации
text


## 🚀 Быстрый старт

1. **Установка зависимостей**
```bash
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# или .venv\Scripts\activate  # Windows
pip install -r requirements.txt  # если есть, иначе только стандартная библиотека

    Запуск генерации

bash

python generate.py

📊 Формат данных
Входные файлы (config/)

symbols.jsonl - определение математических символов:
json

{"sec": "trigonometry", "sym": "\\sin", "rus": "синус", "eng": "sine"}

greeks.jsonl / latins.jsonl - переменные для подстановки:
json

{"sym": "\\alpha", "rus": "альфа", "eng": "alpha"}
{"sym": "a", "rus": ["эй"], "eng": ["ay"]}

Выходной файл (scripts/dataset.jsonl)

Каждая запись содержит:
json

{
  "sec": "trigonometry",     # Секция символа
  "sym": "\\sin",            # LaTeX команда
  "rus": "синус",            # Русское название
  "eng": "sine",             # Английское название
  "script": "\\sin(\\alpha)", # Сгенерированная формула
  "scheme": "sym(@)"         # Шаблон формулы
}

🎯 Типы генерируемых формул
Тип	Шаблон	Пример
sym(@)	Простой символ	\sin(x)
sym(@) ? next(@)	Бинарная операция	\sin(a) + \int(b)
next(@) ? sym(@)	Обратная бинарная операция	\int(x) - \sin(y)
sym(next(@))	Прямая вложенность	\sin(\int(x))
next(sym(@))	Обратная вложенность	\int(\sin(x))
sym(next(@)) ? next(sym(@))	Комбинация (прямой порядок)	\sin(\int(a)) = \int(\sin(b))
next(sym(@)) ? sym(next(@))	Комбинация (обратный порядок)	\int(\sin(a)) > \sin(\int(b))

Операторы: +, -, =, /, >, <
⚙️ Настройка
Количество примеров

В файле generate.py измените параметр samples_per_type:
python

generator = LatexFormulaGenerator(config_path, samples_per_type=3)

    samples_per_type=1 → 1 пример на тип (всего ~650 записей)

    samples_per_type=3 → 3 примера на тип (всего ~1,750 записей)

    samples_per_type=5 → 5 примеров на тип (всего ~2,800 записей)

Ограничение символов

Для тестирования используйте target_symbols:
python

target_symbols = ['\\sin', '\\int']  # Только эти символы
# target_symbols = []  # Все символы

📈 Масштабирование датасета

При samples_per_type=3:

    1 символ: 19 формул

    92 символа: 1,748 формул

    С 3 вариантами переводов: ~5,244 формул

🔧 Особенности

    ✅ Корректный LaTeX синтаксис (круглые скобки)

    ✅ Случайные переменные (греческие и латинские буквы)

    ✅ Уникальный next символ для каждого примера

    ✅ Случайные операторы для каждой бинарной операции

    ✅ Поддержка всех символов из symbols.jsonl

📝 Пример использования датасета
python

import json

# Загрузка датасета
with open('scripts/dataset.jsonl', 'r') as f:
    dataset = [json.loads(line) for line in f]

# Фильтрация по секции
trig_formulas = [item for item in dataset if item['sec'] == 'trigonometry']

# Группировка по типу
from collections import defaultdict
by_type = defaultdict(list)
for item in dataset:
    by_type[item['scheme']].append(item['script'])
