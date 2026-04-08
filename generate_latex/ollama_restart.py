#!/bin/bash
# force_gpu1.sh

# Останавливаем Ollama
sudo pkill ollama
sleep 2

# Очищаем кэш GPU
sudo nvidia-smi --gpu-reset -i 1 2>/dev/null || true

# Запускаем Ollama ТОЛЬКО с GPU 1
export CUDA_VISIBLE_DEVICES=1
export OLLAMA_NUM_GPU=1

# Проверяем, что переменные установлены
echo "CUDA_VISIBLE_DEVICES=$CUDA_VISIBLE_DEVICES"
echo "OLLAMA_NUM_GPU=$OLLAMA_NUM_GPU"

# Запускаем
ollama serve &

sleep 5

# Проверяем, что Ollama видит только GPU 1
echo ""
echo "=== Ollama процессы ==="
ps aux | grep ollama | grep -v grep

echo ""
echo "=== GPU память после запуска ==="
nvidia-smi --query-gpu=index,name,memory.used --format=csv
