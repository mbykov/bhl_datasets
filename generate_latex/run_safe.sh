#!/bin/bash
# run_safe.sh - Безопасный запуск генератора с защитой от OOM

set -e

echo "========================================="
echo "🚀 Гибридный генератор LaTeX озвучек"
echo "========================================="

# ========== ОБРАБОТКА ПРЕРЫВАНИЙ ==========
trap 'echo ""; echo "🛑 Прерывание..."; exit 130' INT TERM

# ========== ПАРАМЕТРЫ ПО УМОЛЧАНИЮ ==========
DEFAULT_NUM_EXAMPLES="all"  # all = все примеры
DEFAULT_MODEL="qwen2.5:7b"
DEFAULT_WORKERS="5"
DEFAULT_BATCH_SIZE="100"
DEFAULT_RESUME=""

# ========== РАЗБОР АРГУМЕНТОВ ==========
# Использование: ./run_safe.sh [num_examples] [model] [workers] [batch_size] [resume_path]
# Пример: ./run_safe.sh 100 qwen2.5:7b 3 10
# Пример: ./run_safe.sh all llama3.2 2 5
# Пример: ./run_safe.sh 500 qwen2.5:7b 4 20 results/checkpoints/checkpoint_50.json

NUM_EXAMPLES=${1:-$DEFAULT_NUM_EXAMPLES}
MODEL=${2:-$DEFAULT_MODEL}
WORKERS=${3:-$DEFAULT_WORKERS}
BATCH_SIZE=${4:-$DEFAULT_BATCH_SIZE}
RESUME_PATH=${5:-$DEFAULT_RESUME}

echo "📊 Параметры запуска:"
echo "   Примеры: $NUM_EXAMPLES"
echo "   Модель: $MODEL"
echo "   Параллельных запросов: $WORKERS"
echo "   Размер батча: $BATCH_SIZE"
if [ -n "$RESUME_PATH" ]; then
    echo "   Возобновление: $RESUME_PATH"
fi
echo ""

# ========== ОПРЕДЕЛЯЕМ КОЛИЧЕСТВО ПРИМЕРОВ ==========
get_total_examples() {
    if [ -f "scripts/dataset.jsonl" ]; then
        wc -l < scripts/dataset.jsonl 2>/dev/null | tr -d ' ' || echo "0"
    else
        echo "0"
    fi
}

TOTAL_EXAMPLES=$(get_total_examples)

# Конвертируем "all" в числовое значение
if [ "$NUM_EXAMPLES" = "all" ]; then
    NUM_EXAMPLES=$TOTAL_EXAMPLES
    echo "📊 Режим: ВСЕ примеры (найдено: $NUM_EXAMPLES)"
else
    echo "📊 Режим: первые $NUM_EXAMPLES примеров (из $TOTAL_EXAMPLES)"
fi

# ========== ПРОВЕРКА ОКРУЖЕНИЯ ==========
echo ""
echo "🔍 Проверка окружения..."

if ! command -v nvidia-smi &> /dev/null; then
    echo "❌ nvidia-smi не найден!"
    exit 1
fi

if ! command -v python3 &> /dev/null; then
    echo "❌ python3 не найден!"
    exit 1
fi

if ! command -v curl &> /dev/null; then
    echo "❌ curl не найден!"
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

# ========== ПРОВЕРКА VRAM ==========
echo ""
echo "💾 Проверка VRAM..."

FREE_VRAM=$(nvidia-smi --query-gpu=memory.free --format=csv,noheader -i $GPU_INDEX | head -1 | xargs | cut -d' ' -f1)
TOTAL_VRAM=$(nvidia-smi --query-gpu=memory.total --format=csv,noheader -i $GPU_INDEX | head -1 | xargs | cut -d' ' -f1)

echo "   Всего VRAM: ${TOTAL_VRAM} MB"
echo "   Свободно VRAM: ${FREE_VRAM} MB"

if [ $FREE_VRAM -lt 4096 ]; then
    echo "⚠️ КРИТИЧЕСКИ МАЛО VRAM: ${FREE_VRAM}MB (нужно минимум 4GB)"
    echo "   Попытка очистить память..."

    # Очистка кэша (требует sudo)
    echo 3 | sudo tee /proc/sys/vm/drop_caches 2>/dev/null || true

    FREE_VRAM_AFTER=$(nvidia-smi --query-gpu=memory.free --format=csv,noheader -i $GPU_INDEX | head -1 | xargs | cut -d' ' -f1)

    if [ $FREE_VRAM_AFTER -lt 4096 ]; then
        echo "❌ Недостаточно VRAM даже после очистки"
        echo "   Завершите другие процессы на GPU:"
        nvidia-smi -i $GPU_INDEX
        exit 1
    else
        echo "   ✅ После очистки: ${FREE_VRAM_AFTER} MB свободно"
    fi
fi

# ========== УСТАНОВКА ПЕРЕМЕННЫХ ==========
export CUDA_VISIBLE_DEVICES="$GPU_INDEX"
export OLLAMA_NUM_GPU=1
export OLLAMA_GPU_OVERHEAD=0.3
export OLLAMA_HOST=0.0.0.0
export OLLAMA_KEEP_ALIVE=30

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

# ========== ПРОВЕРКА Ollama ==========
echo ""
echo "🔄 Проверка доступности Ollama..."

if ! curl -s http://localhost:11434/api/generate -d "{\"model\":\"$MODEL\",\"stream\":false}" &>/dev/null; then
    echo "⚠️ Ollama не отвечает или модель не загружена"
    echo "   Попытка предзагрузки модели..."
    curl -s http://localhost:11434/api/generate -d "{\"model\":\"$MODEL\",\"stream\":false,\"keep_alive\":30}" > /dev/null 2>&1 &
    sleep 5
fi
echo "✅ Ollama готов"

# ========== ПРОВЕРКА ВХОДНОГО ФАЙЛА ==========
if [ ! -f "scripts/dataset.jsonl" ]; then
    echo "❌ Файл scripts/dataset.jsonl не найден"
    echo "   Сначала запустите: python generator.py"
    exit 1
fi
echo "✅ Входной файл найден ($TOTAL_EXAMPLES примеров)"

# ========== ПРОВЕРКА СВОБОДНОГО МЕСТА ==========
echo ""
echo "💿 Проверка дискового пространства..."

FREE_SPACE=$(df . | tail -1 | awk '{print $4}')
if [ $FREE_SPACE -lt 1048576 ]; then  # 1GB в KB
    echo "⚠️ Мало места на диске: $((FREE_SPACE / 1024)) MB"
    echo "   Нужно минимум 1GB свободного места"
    exit 1
fi
echo "✅ Достаточно места: $((FREE_SPACE / 1024 / 1024)) GB"

# ========== ЗАПУСК ==========
echo ""
echo "========================================="
echo "🏃 Запуск генератора на $GPU_NAME..."
echo "========================================="

mkdir -p results
mkdir -p logs
mkdir -p results/checkpoints

LOG_FILE="logs/run_$(date +%Y%m%d_%H%M%S).log"

START_TIME=$(date +%s)

# Сборка команды
CMD="python3 aloud.py --num-examples $NUM_EXAMPLES --model \"$MODEL\" --input scripts/dataset.jsonl --output-dir results --workers $WORKERS --batch-size $BATCH_SIZE"

# Добавляем возобновление если указано
if [ -n "$RESUME_PATH" ]; then
    CMD="$CMD --resume \"$RESUME_PATH\""
fi

echo "📝 Команда: $CMD"
echo ""

# Запуск с ограничением памяти через ulimit
ulimit -v 30000000  # 30GB виртуальной памяти максимум

eval $CMD 2>&1 | tee "$LOG_FILE"

EXIT_CODE=$?

END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))

# ========== ФИНАЛЬНЫЙ ОТЧЁТ ==========
echo ""
echo "========================================="
if [ $EXIT_CODE -eq 0 ]; then
    echo "✅ УСПЕШНО завершено за $((DURATION / 60)) мин $((DURATION % 60)) сек"
else
    echo "❌ ОШИБКА (код $EXIT_CODE) после $((DURATION / 60)) мин $((DURATION % 60)) сек"
fi
echo "========================================="

# Статистика
if [ -f "results/train.json" ]; then
    TRAIN_COUNT=$(python3 -c "import json; print(len(json.load(open('results/train.json'))))" 2>/dev/null || echo "0")
    TEST_COUNT=$(python3 -c "import json; print(len(json.load(open('results/test.json'))))" 2>/dev/null || echo "0")
    echo "📊 Результаты: Train: $TRAIN_COUNT, Test: $TEST_COUNT"
fi

echo "📁 Логи: $LOG_FILE"

# Очистка
unset CUDA_VISIBLE_DEVICES

exit $EXIT_CODE
