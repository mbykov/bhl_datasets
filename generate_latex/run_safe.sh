#!/bin/bash
# run_safe.sh - Безопасный запуск генератора

set -e

echo "========================================="
echo "🚀 Гибридный генератор LaTeX озвучек"
echo "========================================="

# ========== ОПРЕДЕЛЯЕМ КОЛИЧЕСТВО ПРИМЕРОВ ==========
get_total_examples() {
    if [ -f "scripts/dataset.jsonl" ]; then
        wc -l < scripts/dataset.jsonl 2>/dev/null | tr -d ' ' || echo "0"
    else
        echo "0"
    fi
}

TOTAL_EXAMPLES=$(get_total_examples)

# ========== ПАРАМЕТРЫ ==========
# По умолчанию - все примеры
if [ -z "$1" ]; then
    NUM_EXAMPLES=$TOTAL_EXAMPLES
    echo "📊 Режим: ВСЕ примеры (найдено: $NUM_EXAMPLES)"
else
    # Проверяем, является ли первый параметр числом
    if [[ "$1" =~ ^[0-9]+$ ]]; then
        NUM_EXAMPLES=$1
        echo "📊 Режим: первые $NUM_EXAMPLES примеров"
    else
        NUM_EXAMPLES=$TOTAL_EXAMPLES
        echo "📊 Режим: ВСЕ примеры (найдено: $NUM_EXAMPLES)"
    fi
fi

MODEL=${2:-"qwen2.5:7b"}

echo "   Модель: $MODEL"
echo ""

# ========== ПРОВЕРКА ОКРУЖЕНИЯ ==========
echo "🔍 Проверка окружения..."

if ! command -v nvidia-smi &> /dev/null; then
    echo "❌ nvidia-smi не найден!"
    exit 1
fi

# ========== ВЫБОР RTX 5060 Ti ==========
echo ""
echo "🎮 Поиск GPU RTX 5060 Ti..."

GPU_LIST=$(nvidia-smi --query-gpu=name,index --format=csv,noheader 2>/dev/null)

GPU_INDEX=""
GPU_NAME=""
while IFS=',' read -r name index; do
    name_clean=$(echo "$name" | xargs)
    index_clean=$(echo "$index" | xargs)

    if echo "$name_clean" | grep -qi "5060"; then
        GPU_INDEX="$index_clean"
        GPU_NAME="$name_clean"
        break
    fi
done <<< "$GPU_LIST"

if [ -z "$GPU_INDEX" ]; then
    echo "❌ RTX 5060 Ti не найдена!"
    echo "   Доступные GPU:"
    nvidia-smi --query-gpu=name,index --format=csv,noheader
    exit 1
fi

echo "✅ Найдена: $GPU_NAME (index $GPU_INDEX)"

# Устанавливаем переменные
export CUDA_VISIBLE_DEVICES="$GPU_INDEX"
export OLLAMA_NUM_GPU=1

# ========== ПРОВЕРКА МОДЕЛИ ==========
echo ""
echo "📦 Проверка модели $MODEL..."

if ! curl -s http://localhost:11434/api/tags 2>/dev/null | grep -q "\"name\":\"$MODEL\""; then
    echo "⚠️ Модель $MODEL не найдена в Ollama"
    echo "   Доступные модели:"
    curl -s http://localhost:11434/api/tags | grep -o '"name":"[^"]*"' || echo "   (нет моделей)"
    echo ""
    echo "   Загрузите модель: ollama pull $MODEL"
    exit 1
fi
echo "✅ Модель $MODEL найдена"

# ========== ПРОВЕРКА ВХОДНОГО ФАЙЛА ==========
if [ ! -f "scripts/dataset.jsonl" ]; then
    echo "❌ Файл scripts/dataset.jsonl не найден"
    echo "   Сначала запустите: python generator.py"
    exit 1
fi
echo "✅ Входной файл найден ($TOTAL_EXAMPLES примеров)"

# ========== ЗАПУСК ==========
echo ""
echo "========================================="
echo "🏃 Запуск генератора на $GPU_NAME..."
echo "========================================="

mkdir -p results
mkdir -p logs

LOG_FILE="logs/run_$(date +%Y%m%d_%H%M%S).log"

START_TIME=$(date +%s)

# Запуск с числовым значением (никогда не 'all')
python3 aloud.py \
    --num-examples $NUM_EXAMPLES \
    --model "$MODEL" \
    --input scripts/dataset.jsonl \
    --output-dir results \
    2>&1 | tee "$LOG_FILE"

END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))

echo ""
echo "========================================="
echo "✅ Завершено за $((DURATION / 60)) мин $((DURATION % 60)) сек"
echo "========================================="

# Статистика
if [ -f "results/train.json" ]; then
    TRAIN_COUNT=$(python3 -c "import json; print(len(json.load(open('results/train.json'))))" 2>/dev/null || echo "0")
    TEST_COUNT=$(python3 -c "import json; print(len(json.load(open('results/test.json'))))" 2>/dev/null || echo "0")
    echo "📊 Результаты: Train: $TRAIN_COUNT, Test: $TEST_COUNT"
fi

echo "📁 Логи: $LOG_FILE"
