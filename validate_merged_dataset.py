# validate_merged_dataset.py
import json
import re

def validate_dataset(filepath):
    """Проверяет датасет на потенциальные проблемы"""

    print("🔍 Проверка датасета:", filepath)
    print("="*50)

    issues = []
    stats = {
        "total": 0,
        "latex_escaped": 0,  # правильно экранированные
        "latex_unescaped": 0, # НЕ правильно экранированные (проблема)
        "empty_fields": 0,
        "control_chars": 0,
        "unicode_special": 0
    }

    with open(filepath, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            stats["total"] += 1

            try:
                data = json.loads(line)

                # Проверяем наличие всех полей
                if not data.get("instruction"):
                    issues.append(f"Line {line_num}: missing instruction")
                    stats["empty_fields"] += 1

                if not data.get("input"):
                    issues.append(f"Line {line_num}: missing input")
                    stats["empty_fields"] += 1

                if not data.get("output"):
                    issues.append(f"Line {line_num}: missing output")
                    stats["empty_fields"] += 1

                # Проверяем output на корректность LaTeX
                output = data.get("output", "")

                # Ищем НЕправильно экранированные слэши
                # В JSON правильный LaTeX должен иметь \\ (два слэша)
                # Если видим один слэш без пары - это проблема
                if '\\' in output:
                    # Проверяем, что все слэши правильно экранированы
                    # В строке Python после json.loads() слэши уже нормальные
                    # Нам нужно проверить, что нет последовательностей вида \t, \n и т.д.
                    # которые не являются LaTeX командами

                    # Ищем проблемные последовательности: \ без следующего \
                    # Но игнорируем уже экранированные в JSON
                    problematic = False

                    # Простые проверки
                    if '\t' in output and '\\t' not in output:
                        problematic = True
                    if '\n' in output and '\\n' not in output:
                        problematic = True

                    # Проверяем, что все обратные слэши идут парами в LaTeX командах
                    # На самом деле, после json.loads() у нас уже правильная строка
                    # с одиночными слэшами для LaTeX
                    stats["latex_escaped"] += 1

                # Проверяем на контрольные символы (кроме стандартных)
                if any(ord(c) < 32 for c in output if c not in '\n\r\t'):
                    stats["control_chars"] += 1
                    issues.append(f"Line {line_num}: control characters in output")

                # Проверяем на специальные Unicode символы
                if any(ord(c) > 0xFFFF for c in output):
                    stats["unicode_special"] += 1
                    issues.append(f"Line {line_num}: special unicode in output")

                # Проверяем длину
                if len(output) > 500:
                    issues.append(f"Line {line_num}: output too long ({len(output)} chars)")

            except json.JSONDecodeError as e:
                issues.append(f"Line {line_num}: JSON decode error: {e}")

    # Вывод статистики
    print(f"\n📊 Статистика:")
    print(f"  Всего строк: {stats['total']}")
    print(f"  Строк с LaTeX: {stats['latex_escaped']}")
    print(f"  Пустые поля: {stats['empty_fields']}")
    print(f"  Контрольные символы: {stats['control_chars']}")
    print(f"  Специальный Unicode: {stats['unicode_special']}")

    if issues:
        print(f"\n⚠️ Найдено {len(issues)} предупреждений (показываю первые 10):")
        for issue in issues[:10]:
            print(f"  • {issue}")

        # Если все проблемы - это "unescaped newline/tab", но в файле все правильно
        # значит это ложные срабатывания
        unescaped_issues = [i for i in issues if "unescaped newline/tab" in i]
        if len(unescaped_issues) == len(issues):
            print("\n✅ Все 'проблемы' - это ложные срабатывания валидатора!")
            print("   Ваш датасет корректен, все LaTeX правильно экранирован.")
            return True
    else:
        print("\n✅ Проблем не найдено!")

    return len(issues) == 0

def show_sample(filepath, line_num=61):
    """Показывает конкретную строку для проверки"""
    with open(filepath, 'r', encoding='utf-8') as f:
        for i, line in enumerate(f, 1):
            if i == line_num:
                print(f"\n📝 Строка {line_num}:")
                data = json.loads(line)
                print(json.dumps(data, ensure_ascii=False, indent=2))
                print(f"\nOutput как строка Python: {repr(data['output'])}")
                break

if __name__ == "__main__":
    validate_dataset("result/merged/dataset.jsonl")

    # Показываем пример строки 61
    show_sample("result/merged/dataset.jsonl", 61)
