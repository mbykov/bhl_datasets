#!/usr/bin/env python3
"""
Интерактивный тест Ollama модели для отладки промптов
Поддерживает историю ввода (arrow-up/down) и редактирование (control-arrow)
"""

import requests
import sys
import argparse
import readline
from pathlib import Path

MODEL_NAME = "qwen_command"
OLLAMA_API = "http://localhost:11434/api/generate"

# Путь к файлу с системным промптом (единый источник)
SYSTEM_PROMPT_FILE = Path(__file__).parent / "docs" / "command_prompt.txt"

# Дефолтный промпт (используется если файл не найден)
DEFAULT_SYSTEM_PROMPT = "Ты — помощник для определения команд в тексте."


def load_system_prompt(file_path: Path = SYSTEM_PROMPT_FILE) -> str:
    """Загружает системный промпт из файла."""
    if file_path.exists():
        return file_path.read_text(encoding="utf-8").strip()
    return DEFAULT_SYSTEM_PROMPT


def setup_readline():
    """Настраивает историю ввода."""
    history_file = Path(".inference_history")

    # Загрузка истории
    if history_file.exists():
        readline.read_history_file(history_file)

    # Сохранение при выходе
    import atexit
    atexit.register(readline.write_history_file, history_file)

    # Настройка длины истории
    readline.set_history_length(1000)


def run_ollama_query(query: str, system_prompt: str, model: str, timeout: int = 30) -> str:
    """Выполняет запрос к модели Ollama через API."""
    try:
        payload = {
            "model": model,
            "prompt": query,
            "system": system_prompt,
            "stream": False,
            "options": {
                "temperature": 0.3,
                "top_p": 0.9,
                "top_k": 40
            }
        }
        response = requests.post(OLLAMA_API, json=payload, timeout=timeout)
        response.raise_for_status()
        result = response.json()
        # print(f"RRR: {result}")
        return result.get("response", "").strip()
    except requests.exceptions.Timeout:
        return "TIMEOUT"
    except requests.exceptions.ConnectionError:
        return "ERROR: Ollama API недоступен (проверьте: ollama serve)"
    except Exception as e:
        return f"ERROR: {e}"


def interactive_loop(system_prompt: str, model: str):
    """Интерактивный цикл ввода/вывода."""
    print("\n" + "="*70)
    print("🤖 ИНТЕРАКТИВНЫЙ ТЕСТ OLLAMA МОДЕЛИ")
    print("="*70)
    print(f"Модель: {model}")
    print(f"System prompt: {system_prompt[:50]}...")
    print("\n📝 Введите фразу для тестирования (или 'exit'/'quit' для выхода)")
    print("   • Arrow-up/down: история ввода")
    print("   • Ctrl+Arrow: перемещение по словам")
    print("   • Ctrl+A/E: начало/конец строки")
    print("   • Ctrl+U/K: удаление до начала/конца строки")
    print("="*70 + "\n")

    while True:
        try:
            # Ввод с историей
            query = input("👤 Ввод: ").strip()

            if not query:
                continue

            if query.lower() in ["exit", "quit", "q", "выход", "выйти"]:
                print("👋 До свидания!")
                break

            if query.lower() in ["system", "show_system"]:
                print(f"\n📋 Текущий system prompt:\n{system_prompt}\n")
                continue

            if query.lower() in ["help", "h", "?"]:
                print("\nКоманды:")
                print("  exit/quit/q  — выйти")
                print("  system       — показать system prompt")
                print("  help         — показать эту справку")
                print("  <любой текст> — отправить модели\n")
                continue

            # Запрос к модели
            print("🤔 Обработка...", end=" ", flush=True)
            response = run_ollama_query(query, system_prompt, model)

            if response.startswith("ERROR") or response == "TIMEOUT":
                print(f"\n❌ {response}")
            else:
                if response:
                    print(f"\n✅ Команда: {response}")
                else:
                    print(f"\n✅ (пустой ответ — команда не распознана)")

        except KeyboardInterrupt:
            print("\n\n👋 До свидания!")
            break
        except EOFError:
            print("\n👋 До свидания!")
            break


def main():
    parser = argparse.ArgumentParser(description="Интерактивный тест Ollama модели")
    parser.add_argument("--model", type=str, default=MODEL_NAME, help="Имя модели Ollama")
    parser.add_argument("--system", type=str, default=None,
                       help="Системный промпт (по умолчанию берётся из docs/command_prompt.txt)")
    parser.add_argument("--system-file", type=str, default=None, help="Путь к файлу с system prompt")
    args = parser.parse_args()

    # Обработка system prompt
    if args.system_file:
        system_file = Path(args.system_file)
        if system_file.exists():
            system_prompt = system_file.read_text(encoding="utf-8").strip()
        else:
            print(f"❌ Файл не найден: {system_file}")
            sys.exit(1)
    elif args.system:
        # Если промпт начинается с @, считываем из файла
        if args.system.startswith("@"):
            system_file = Path(args.system[1:])
            if system_file.exists():
                system_prompt = system_file.read_text(encoding="utf-8").strip()
            else:
                print(f"❌ Файл не найден: {system_file}")
                sys.exit(1)
        else:
            system_prompt = args.system
    else:
        # По умолчанию загружаем из docs/command_prompt.txt
        system_prompt = load_system_prompt()

    # Проверка доступности Ollama API
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=5)
        if response.status_code != 200:
            print("❌ Ollama API недоступен. Запустите: ollama serve")
            sys.exit(1)
    except requests.exceptions.ConnectionError:
        print("❌ Ollama API недоступен. Запустите: ollama serve")
        sys.exit(1)

    # Настройка истории ввода
    setup_readline()

    # Запуск интерактивного цикла
    interactive_loop(system_prompt, args.model)


if __name__ == "__main__":
    main()
