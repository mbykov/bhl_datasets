#!/usr/bin/env python3
"""
Скрипт для тестирования GGUF модели через llama.cpp
"""

import os
import sys
import argparse
import subprocess
import logging
import signal
from pathlib import Path
from datetime import datetime

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Флаг для обработки прерывания
interrupted = False

def signal_handler(signum, frame):
    """Обработчик Ctrl+C"""
    global interrupted
    interrupted = True
    print("\n\n⚠️  Прервано пользователем")
    sys.exit(0)

# Устанавливаем обработчик
signal.signal(signal.SIGINT, signal_handler)

def find_llama_main(llama_path="./llama.cpp"):
    """Находит исполняемый файл llama-cli"""

    # Проверяем в build/bin
    candidates = [
        os.path.join(llama_path, "build", "bin", "llama-cli"),
        os.path.join(llama_path, "build", "bin", "llama"),
        os.path.join(llama_path, "main"),
        os.path.join(llama_path, "llama-cli"),
        shutil.which("llama-cli"),
        shutil.which("llama"),
    ]

    for path in candidates:
        if path and os.path.exists(path):
            return path

    # Если не нашли, пробуем собрать
    logger.warning("llama-cli не найден, пробуем собрать...")
    try:
        subprocess.run(["make", "-C", llama_path, "llama-cli"], check=True, capture_output=True)
        return os.path.join(llama_path, "llama-cli")
    except:
        pass

    return None

def test_gguf(model_path, prompts, max_tokens=100, temperature=0.7, llama_path="./llama.cpp"):
    """Тестирует GGUF модель"""
    global interrupted

    # Ищем llama-cli
    llama_cli = find_llama_main(llama_path)
    if not llama_cli:
        logger.error("❌ llama-cli не найден!")
        logger.info("   Убедитесь, что llama.cpp собран:")
        logger.info(f"   cd {llama_path} && cmake -B build && cmake --build build --config Release -j 4")
        return False

    logger.info(f"Используем: {llama_cli}")

    results = []

    for i, prompt in enumerate(prompts, 1):
        if interrupted:
            logger.info("\n⚠️ Прерывание тестирования")
            break

        logger.info(f"\n📝 Тест {i}/{len(prompts)}: {prompt[:60]}...")
        logger.info("-"*40)

        cmd = [
            llama_cli,
            "-m", model_path,
            "-p", prompt,
            "-n", str(max_tokens),
            "-t", "4",
            "--temp", str(temperature),
            "--repeat-penalty", "1.1",
            "--no-display-prompt",
        ]

        try:
            # Запускаем с обработкой прерывания
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )

            # Ждем с возможностью прерывания
            try:
                stdout, stderr = process.communicate(timeout=60)

                if process.returncode == 0:
                    response = stdout.strip()
                    # Показываем первые 200 символов ответа
                    preview = response[:200] + "..." if len(response) > 200 else response
                    logger.info(f"   ✅ Ответ: {preview}")
                    results.append({"prompt": prompt, "response": response, "success": True})
                else:
                    logger.error(f"   ❌ Ошибка: {stderr[:200]}")
                    results.append({"prompt": prompt, "response": None, "success": False})

            except subprocess.TimeoutExpired:
                process.kill()
                logger.error(f"   ❌ Таймаут (60 сек)")
                results.append({"prompt": prompt, "response": None, "success": False})

        except Exception as e:
            logger.error(f"   ❌ Ошибка: {e}")
            results.append({"prompt": prompt, "response": None, "success": False})

    # Итоги
    if not interrupted:
        success_count = sum(1 for r in results if r["success"])
        logger.info("\n" + "="*60)
        logger.info("ИТОГИ ТЕСТИРОВАНИЯ")
        logger.info("="*60)
        logger.info(f"Успешно: {success_count}/{len(results)}")
        return success_count == len(results)
    else:
        return False

def main():
    parser = argparse.ArgumentParser(description="Тестирование GGUF модели")
    parser.add_argument("--model", type=str, required=True,
                        help="Путь к GGUF файлу")
    parser.add_argument("--prompt", type=str, default=None,
                        help="Один промпт для тестирования")
    parser.add_argument("--prompts-file", type=str, default=None,
                        help="Файл с промптами (по одному на строку)")
    parser.add_argument("--max-tokens", type=int, default=100,
                        help="Максимум токенов в ответе")
    parser.add_argument("--temperature", type=float, default=0.7,
                        help="Температура генерации")
    parser.add_argument("--llama-path", type=str, default="./llama.cpp",
                        help="Путь к llama.cpp")
    parser.add_argument("--quiet", action="store_true",
                        help="Тихий режим (меньше вывода)")

    args = parser.parse_args()

    if not args.quiet:
        logger.info("="*60)
        logger.info("ТЕСТИРОВАНИЕ GGUF МОДЕЛИ")
        logger.info("="*60)
        logger.info(f"Модель: {args.model}")
        logger.info(f"Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("="*60)

    # Проверяем модель
    if not os.path.exists(args.model):
        logger.error(f"Модель не найдена: {args.model}")
        sys.exit(1)

    # Определяем промпты
    if args.prompt:
        prompts = [args.prompt]
    elif args.prompts_file:
        try:
            with open(args.prompts_file, 'r', encoding='utf-8') as f:
                prompts = [line.strip() for line in f if line.strip()]
        except Exception as e:
            logger.error(f"Ошибка чтения файла: {e}")
            sys.exit(1)
    else:
        # Стандартные тестовые промпты
        prompts = [
            "Определи команду в тексте: сделай маркируй высказывание",
            "Преобразуй текст в формулу LaTeX: плюс-минус игрек и эф",
            "Определи команду в тексте: удали заметку пожалуйста",
            "Преобразуй текст в формулу LaTeX: сумма альфа и икс"
        ]

    if not args.quiet:
        logger.info(f"Всего тестов: {len(prompts)}")

    # Запускаем тестирование
    try:
        success = test_gguf(
            args.model, prompts,
            args.max_tokens, args.temperature,
            args.llama_path
        )
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️ Прервано пользователем")
        sys.exit(0)

if __name__ == "__main__":
    import shutil
    main()
