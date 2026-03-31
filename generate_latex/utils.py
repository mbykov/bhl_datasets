#!/usr/bin/env python3
"""
Основной скрипт для генерации полного датасета
"""

import os
import sys
import subprocess
import argparse

def check_ollama():
    """Проверяет доступность Ollama"""
    try:
        import requests
        response = requests.get("http://localhost:11434/api/tags")
        if response.status_code == 200:
            print("✅ Ollama доступен")
            return True
    except:
        print("❌ Ollama не доступен. Запустите: ollama serve")
        return False
    return False

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--count', type=int, default=50000,
                       help='Количество уникальных формул')
    parser.add_argument('--variants', type=int, default=5,
                       help='Количество вариантов описаний на формулу')
    parser.add_argument('--no-llm', action='store_true',
                       help='Генерировать только скелеты, без LLM')
    args = parser.parse_args()

    print("="*70)
    print("🚀 ГЕНЕРАЦИЯ LATEX ДАТАСЕТА С ЕСТЕСТВЕННЫМИ ОПИСАНИЯМИ")
    print("="*70)

    # Шаг 1: Генерация скелетов
    print("\n📐 Шаг 1: Генерация математических скелетов")
    subprocess.run([
        sys.executable, 'generate_raw_description.py',
        '--count', str(args.count)
    ])

    if not args.no_llm:
        # Шаг 2: Проверка Ollama
        if not check_ollama():
            print("\n⚠️ Пропускаем генерацию описаний. Запустите скрипт позже с --no-llm")
            return

        # Шаг 3: Генерация естественных описаний
        print("\n📝 Шаг 2: Генерация естественных описаний через LLM")
        subprocess.run([
            sys.executable, 'generate_natural_descriptions.py',
            '--variants', str(args.variants)
        ])

    print("\n" + "="*70)
    print("✅ ГЕНЕРАЦИЯ ЗАВЕРШЕНА")
    print("="*70)
    print(f"📊 Итоговый датасет: result/latex/dataset.jsonl")
    print(f"   Ожидаемое количество примеров: ~{args.count * args.variants * 2}")  # *2 для двух языков
    print("="*70)

if __name__ == '__main__':
    main()
