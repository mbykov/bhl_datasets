#!/bin/bash
# run_safe.sh - Безопасный запуск гибридного генератора для JSONL формата
# Без параметров обрабатывает ВСЕ примеры

set -e

echo "========================================="
echo "🚀 Гибридный генератор LaTeX озвучек"
echo "========================================="

# ========== ОПРЕДЕЛЯЕМ РЕАЛЬНОЕ КОЛИЧЕСТВО ПРИМЕРОВ ==========
get_total_examples() {
    if [ -f "scripts/dataset.jsonl" ]; then
        wc -l < scripts/dataset.jsonl 2>/dev/null | tr -d ' ' || echo "0"
    else
        echo "0"
    fi
}

TOTAL_EXAMPLES=$(get_total_examples)

# ========== ПАРАМЕТРЫ ==========
# Если параметр не указан или указан "all" - берем все примеры
if [ -z "$1" ] || [ "$1" = "all" ] || [ "$1" = "ALL" ]; then
    NUM_EXAMPLES=$TOTAL_EXAMPLES
    if [ "$NUM_EXAMPLES" -eq 0 ]; then
        echo "❌ Файл scripts/dataset.jsonl не найден или пуст"
        exit 1
    fi
    echo "📊 Режим: ВСЕ примеры (найдено: $NUM_EXAMPLES)"
else
    NUM_EXAMPLES=$1
    echo "📊 Режим: первые $NUM_EXAMPLES примеров"
fi

MAX_WORKERS=${2:-2}
BATCH_SIZE=${3:-30}
MEMORY_THRESHOLD=${4:-14000}
DELAY=${5:-0.3}
MODEL=${6:-"qwen2.5:7b"}

echo ""
echo "📊 Параметры запуска:"
echo "   Примеров: $NUM_EXAMPLES (всего в файле: $TOTAL_EXAMPLES)"
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
if [ ! -f "scripts/dataset.jsonl" ]; then
    echo "❌ Файл scripts/dataset.jsonl не найден"
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
if [ "$NUM_EXAMPLES" -eq "$TOTAL_EXAMPLES" ] && [ "$TOTAL_EXAMPLES" -gt 100 ]; then
    echo "⚠️ ВНИМАНИЕ: Будет обработано $TOTAL_EXAMPLES примеров"
    echo "   Это займет ~$((TOTAL_EXAMPLES / 10)) минут (примерно)"
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
mkdir -p results
mkdir -p logs

# Запускаем с низким приоритетом
START_TIME=$(date +%s)

taskset -c 0-3 nice -n 19 uv run aloud.py \
    --num-examples $NUM_EXAMPLES \
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
if [ -f "results/train.json" ]; then
    TRAIN_COUNT=$(cat results/train.json | python3 -c "import sys,json; print(len(json.load(sys.stdin)))")
    TEST_COUNT=$(cat results/test.json | python3 -c "import sys,json; print(len(json.load(sys.stdin)))")
    echo "📊 Результаты:"
    echo "   Train: $TRAIN_COUNT примеров"
    echo "   Test: $TEST_COUNT примеров"
    echo "   Путь: results/"
fi

if [ -f "results/skipped.json" ]; then
    SKIPPED=$(cat results/skipped.json | python3 -c "import sys,json; print(len(json.load(sys.stdin)))")
    echo "   Пропущено: $SKIPPED примеров (см. skipped.json)"
fi

echo ""
echo "📁 Логи: logs/"
