#!/usr/bin/env python3
"""Проверка качества стилизации - только для типов, которые требуют стилизации"""

import json
from pathlib import Path
import re

# Типы, которые НУЖНО стилизовать (все, кроме атомарных)
TYPES_THAT_NEED_STYLING = {
    'binary_forward', 'binary_backward',
    'nest_forward', 'nest_backward', 'cnest_forward', 'cnest_backward'
}

# Типы, которые НЕ НУЖНО стилизовать (атомарные - переменные, числа, дифференциалы)
ATOMIC_TYPES = {'atomic_var', 'atomic_num', 'atomic_diff'}

def get_latest_checkpoint(checkpoints_dir='results/checkpoints'):
    """Найти последний чекпоинт"""
    checkpoints_dir = Path(checkpoints_dir)

    if not checkpoints_dir.exists():
        return None

    checkpoint_files = list(checkpoints_dir.glob('checkpoint_*.json'))

    if not checkpoint_files:
        return None

    # Извлекаем номер из имени и сортируем
    def get_num(f):
        match = re.search(r'checkpoint_(\d+)\.json', f.name)
        return int(match.group(1)) if match else 0

    latest = max(checkpoint_files, key=get_num)
    return latest

def check_quality(checkpoint_path=None, sample_size=None):
    """Проверка качества стилизации из файла чекпоинта"""

    if checkpoint_path is None:
        checkpoint_path = get_latest_checkpoint()
        if checkpoint_path is None:
            print("❌ Не найден ни один чекпоинт")
            return
        print(f"📌 Использую последний чекпоинт: {checkpoint_path.name}")

    checkpoint_file = Path(checkpoint_path)

    if not checkpoint_file.exists():
        print(f"❌ {checkpoint_file} не найден")
        return

    with open(checkpoint_file, 'r', encoding='utf-8') as f:
        checkpoint = json.load(f)

    data = checkpoint.get('results', [])

    if not data:
        print("❌ Нет результатов в чекпоинте")
        return

    if sample_size is None:
        sample_size = len(data)

    sample = data[:sample_size]

    # Статистика
    total_need_styling = 0
    total_atomic = 0
    good_styling = 0      # успешно стилизованы
    failed_styling = 0    # не стилизованы (normalized == styled)
    hallucinated = 0      # стилизованы, но неадекватно (позже)

    style_stats = {
        'разговорный': {'need': 0, 'good': 0, 'failed': 0},
        'академический': {'need': 0, 'good': 0, 'failed': 0},
        'формально-логический': {'need': 0, 'good': 0, 'failed': 0},
    }

    # Для анализа галлюцинаций
    bad_examples = []

    for item in sample:
        scheme = item.get('scheme', '')
        styled = item.get('rus', '')
        norm = item.get('normalized_rus', '')
        style = item.get('style', 'unknown')
        script = item.get('script', '')

        # Определяем тип примера
        needs_styling = scheme in TYPES_THAT_NEED_STYLING
        is_atomic = scheme in ATOMIC_TYPES

        if needs_styling:
            total_need_styling += 1
            if style in style_stats:
                style_stats[style]['need'] += 1

            # Успех: styled != normalized и styled не пустой
            if styled and styled != norm and styled not in norm:
                good_styling += 1
                if style in style_stats:
                    style_stats[style]['good'] += 1
            else:
                failed_styling += 1
                if style in style_stats:
                    style_stats[style]['failed'] += 1

                # Запоминаем проблемные для анализа
                if len(bad_examples) < 20:
                    bad_examples.append({
                        'idx': item.get('idx'),
                        'style': style,
                        'scheme': scheme,
                        'script': script,
                        'styled': styled,
                        'norm': norm
                    })

        elif is_atomic:
            total_atomic += 1
            # Для атомарных: корректно, если styled == norm (не пытались стилизовать)

    print(f"\n{'='*70}")
    print(f"📊 Анализ чекпоинта: {checkpoint_file.name}")
    print(f"   Всего примеров: {len(data)}")
    print(f"   Анализируем: {sample_size}")
    print(f"{'='*70}")

    print(f"\n📈 СЛОЖНЫЕ ПРИМЕРЫ (нужна стилизация): {total_need_styling}")
    print(f"   ✅ Успешно стилизованы: {good_styling} ({good_styling/total_need_styling*100:.1f}%)")
    print(f"   ❌ Не стилизованы (normalized == styled): {failed_styling} ({failed_styling/total_need_styling*100:.1f}%)")

    print(f"\n📈 ПРОСТЫЕ/АТОМАРНЫЕ (стилизация не нужна): {total_atomic}")

    print(f"\n📊 ПО СТИЛЯМ (только сложные примеры):")
    for style, stats in style_stats.items():
        if stats['need'] > 0:
            success_rate = stats['good'] / stats['need'] * 100 if stats['need'] > 0 else 0
            print(f"\n   {style}:")
            print(f"      Всего: {stats['need']}")
            print(f"      Успешно: {stats['good']} ({success_rate:.1f}%)")
            print(f"      Не стилизовано: {stats['failed']} ({stats['failed']/stats['need']*100:.1f}%)")

    # Оценка
    if total_need_styling > 0:
        success_rate = good_styling / total_need_styling * 100
        print(f"\n{'='*70}")
        if success_rate >= 70:
            print(f"✅ ОТЛИЧНО: {success_rate:.1f}% сложных примеров успешно стилизованы!")
        elif success_rate >= 50:
            print(f"👍 ХОРОШО: {success_rate:.1f}% сложных примеров стилизованы")
        elif success_rate >= 30:
            print(f"⚠️ СРЕДНЕ: {success_rate:.1f}% сложных примеров стилизованы")
        else:
            print(f"❌ ПЛОХО: только {success_rate:.1f}% сложных примеров стилизованы")
        print(f"{'='*70}")

    # Показать примеры успешных стилизаций
    print(f"\n📝 ПРИМЕРЫ УСПЕШНЫХ СТИЛИЗАЦИЙ:")
    print(f"{'='*70}")

    shown = 0
    for item in sample:
        scheme = item.get('scheme', '')
        if scheme not in TYPES_THAT_NEED_STYLING:
            continue
        norm = item.get('normalized_rus', '')
        styled = item.get('rus', '')

        if styled and styled != norm and styled not in norm:
            print(f"\n[{item.get('idx', '?')}] {item['style']} | {scheme}")
            print(f"   script:     {item['script'][:60]}")
            print(f"   normalized: {norm[:70]}")
            print(f"   styled:     {styled[:70]}")
            shown += 1
            if shown >= 8:
                break

    if shown == 0:
        print("\n❌ Нет успешных стилизаций!")

    # Показать проблемные (не стилизованы)
    print(f"\n⚠️ ПРИМЕРЫ НЕ СТИЛИЗОВАННЫХ (должны быть, но не стилизованы):")
    print(f"{'='*70}")

    shown = 0
    for ex in bad_examples[:10]:
        print(f"\n[{ex['idx']}] {ex['style']} | {ex['scheme']}")
        print(f"   script: {ex['script'][:60]}")
        print(f"   styled: {ex['styled'][:60]}")
        shown += 1

    if shown == 0:
        print("\n✅ Нет проблемных примеров!")

def analyze_all_checkpoints(checkpoints_dir='results/checkpoints'):
    """Анализ всех чекпоинтов"""
    checkpoints_dir = Path(checkpoints_dir)

    if not checkpoints_dir.exists():
        print(f"❌ Директория {checkpoints_dir} не найдена")
        return

    checkpoint_files = sorted(checkpoints_dir.glob('checkpoint_*.json'))

    if not checkpoint_files:
        print(f"❌ Нет чекпоинтов в {checkpoints_dir}")
        return

    # Сортируем по номеру
    def get_num(f):
        match = re.search(r'checkpoint_(\d+)\.json', f.name)
        return int(match.group(1)) if match else 0

    checkpoint_files.sort(key=get_num)

    print(f"\n{'='*70}")
    print(f"📊 ДИНАМИКА КАЧЕСТВА ПО ЧЕКПОИНТАМ")
    print(f"{'='*70}")
    print(f"\n{'Примеров':<10} {'Сложных':<10} {'Успешно':<10} {'%':<8}")
    print(f"{'-'*40}")

    for cp_file in checkpoint_files:
        num = get_num(cp_file)

        with open(cp_file, 'r', encoding='utf-8') as f:
            checkpoint = json.load(f)
            data = checkpoint.get('results', [])

            total_need = 0
            good = 0

            for item in data:
                scheme = item.get('scheme', '')
                if scheme in TYPES_THAT_NEED_STYLING:
                    total_need += 1
                    styled = item.get('rus', '')
                    norm = item.get('normalized_rus', '')
                    if styled and styled != norm and styled not in norm:
                        good += 1

            if total_need > 0:
                pct = good / total_need * 100
                print(f"{num:<10} {total_need:<10} {good:<10} {pct:.1f}%")

if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        if sys.argv[1] == '--all':
            analyze_all_checkpoints()
        elif sys.argv[1] == '--latest':
            check_quality()
        else:
            sample = int(sys.argv[2]) if len(sys.argv) > 2 else None
            check_quality(sys.argv[1], sample)
    else:
        check_quality()  # Автоматически берёт последний чекпоинт
