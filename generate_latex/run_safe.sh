#!/bin/bash
# run_safe.sh - Безопасный запуск гибридного генератора
# Без параметров обрабатывает ВСЕ символы

set -e

echo "========================================="
echo "🚀 Гибридный генератор LaTeX озвучек"
echo "========================================="

# ========== ОПРЕДЕЛЯЕМ РЕАЛЬНОЕ КОЛИЧЕСТВО СИМВОЛОВ ==========
get_total_symbols() {
    if [ -f "result/scripts.json" ]; then
        python3 -c "import json; print(len(json.load(open('result/scripts.json'))))" 2>/dev/null || echo "72"
    else
        echo "72"
    fi
}

TOTAL_SYMBOLS=$(get_total_symbols)

# ========== ПАРАМЕТРЫ ==========
# Если параметр не указан или указан "all" - берем все символы
if [ -z "$1" ] || [ "$1" = "all" ] || [ "$1" = "ALL" ]; then
    NUM_SYMBOLS=$TOTAL_SYMBOLS
    echo "📊 Режим: ВСЕ символы (найдено: $NUM_SYMBOLS)"
else
    NUM_SYMBOLS=$1
    echo "📊 Режим: первые $NUM_SYMBOLS символов"
fi

MAX_WORKERS=${2:-2}
BATCH_SIZE=${3:-30}
MEMORY_THRESHOLD=${4:-14000}
DELAY=${5:-0.3}
MODEL=${6:-"qwen2.5:7b"}

echo ""
echo "📊 Параметры запуска:"
echo "   Символов: $NUM_SYMBOLS (всего в файле: $TOTAL_SYMBOLS)"
echo "   Потоков: $MAX_WORKERS"
echo "   Батч: $BATCH_SIZE"
echo "   Порог памяти: $MEMORY_THRESHOLD MB"
echo "   Задержка: $DELAY сек"
echo "   Модель: $MODEL"
echo ""

# ========== ПРОВЕРКА ОКРУЖЕНИЯ ==========
echo "🔍 Проверка окружения..."

# Проверяем Ollama
if ! curl -s http://localhost:11434/api/tags > /dev/null; then
    echo "❌ Ollama не запущен! Запустите: ollama serve"
    exit 1
fi
echo "✅ Ollama работает"

# Проверяем GPU
if command -v nvidia-smi &> /dev/null; then
    GPU_INFO=$(nvidia-smi --query-gpu=name,memory.total --format=csv,noheader | head -1)
    echo "✅ GPU: $GPU_INFO"
else
    echo "⚠️ nvidia-smi не найден"
fi

# Проверяем входной файл
if [ ! -f "result/scripts.json" ]; then
    echo "❌ Файл result/scripts.json не найден"
    exit 1
fi
echo "✅ Входной файл найден"

# ========== НАСТРОЙКА ОГРАНИЧЕНИЙ ==========
# Ограничения памяти и CPU
ulimit -v 16000000 2>/dev/null || echo "⚠️ Невозможно установить лимит виртуальной памяти"
ulimit -m 16000000 2>/dev/null || echo "⚠️ Невозможно установить лимит физической памяти"
ulimit -t 600 2>/dev/null || echo "⚠️ Невозможно установить лимит CPU"

# Переменные окружения для стабильности
export CUDA_VISIBLE_DEVICES=1
export OLLAMA_NUM_GPU=1
export OLLAMA_GPU_OVERHEAD=0.5
export OLLAMA_KEEP_ALIVE=0
export OMP_NUM_THREADS=2
export MKL_NUM_THREADS=2

echo ""
echo "🔧 Ограничения:"
echo "   CUDA_VISIBLE_DEVICES=$CUDA_VISIBLE_DEVICES"
echo "   OLLAMA_NUM_GPU=$OLLAMA_NUM_GPU"
echo "   OMP_NUM_THREADS=$OMP_NUM_THREADS"
echo ""

# ========== ПОДТВЕРЖДЕНИЕ ДЛЯ БОЛЬШИХ ЗАПУСКОВ ==========
if [ "$NUM_SYMBOLS" -eq "$TOTAL_SYMBOLS" ] && [ "$TOTAL_SYMBOLS" -gt 30 ]; then
    echo "⚠️ ВНИМАНИЕ: Будет обработано $TOTAL_SYMBOLS символов"
    echo "   Это займет ~$((TOTAL_SYMBOLS * 2)) минут"
    echo ""
    read -p "Продолжить? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Отменено"
        exit 0
    fi
fi

# ========== ЗАПУСК ==========
echo "========================================="
echo "🏃 Запуск генератора..."
echo "========================================="

# Создаем директорию для результатов
mkdir -p result/latex
mkdir -p logs

# Запускаем с низким приоритетом
START_TIME=$(date +%s)

taskset -c 0-3 nice -n 19 uv run aloud.py \
    --num-symbols $NUM_SYMBOLS \
    --model "$MODEL" \
    --max-workers $MAX_WORKERS \
    --batch-size $BATCH_SIZE \
    --memory-threshold $MEMORY_THRESHOLD \
    --delay $DELAY \
    2>&1 | tee logs/run_$(date +%Y%m%d_%H%M%S).log

END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))

echo ""
echo "========================================="
echo "✅ Завершено за $((DURATION / 60)) мин $((DURATION % 60)) сек"
echo "========================================="

# ========== СТАТИСТИКА ==========
if [ -f "result/latex/train.json" ]; then
    TRAIN_COUNT=$(cat result/latex/train.json | python3 -c "import sys,json; print(len(json.load(sys.stdin)))")
    TEST_COUNT=$(cat result/latex/test.json | python3 -c "import sys,json; print(len(json.load(sys.stdin)))")
    echo "📊 Результаты:"
    echo "   Train: $TRAIN_COUNT примеров"
    echo "   Test: $TEST_COUNT примеров"
    echo "   Путь: result/latex/"
fi

if [ -f "result/latex/skipped.json" ]; then
    SKIPPED=$(cat result/latex/skipped.json | python3 -c "import sys,json; print(len(json.load(sys.stdin)))")
    echo "   Пропущено: $SKIPPED примеров (см. skipped.json)"
fi

echo ""
echo "📁 Логи: logs/"
