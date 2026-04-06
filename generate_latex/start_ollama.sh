#!/bin/bash
echo "Останавливаем Ollama..."
sudo pkill -9 ollama

echo "Очищаем кэш GPU..."
sudo nvidia-smi --gpu-reset -i 1

echo "Запускаем Ollama на RTX 5060 Ti (GPU 1)..."
CUDA_VISIBLE_DEVICES=1 ollama serve &

sleep 3

echo "Проверяем, что Ollama работает..."
curl http://localhost:11434/api/tags

echo "Проверяем использование GPU:"
nvidia-smi

echo "Готово! Теперь запускайте скрипт."
