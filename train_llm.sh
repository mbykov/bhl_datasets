#!/bin/bash
# train_llm.sh - Запуск обучения на RTX 5060 Ti

set -e

echo "========================================="
echo "🚀 Запуск обучения на RTX 5060 Ti"
echo "========================================="

# Принудительно указываем только GPU 1 (RTX 5060 Ti)
export CUDA_VISIBLE_DEVICES=1
export CUDA_DEVICE_ORDER=PCI_BUS_ID

echo ""
echo "🎮 Проверка GPU:"
python -c "
import torch
if torch.cuda.is_available():
    print(f'   ✅ CUDA доступен')
    print(f'   📊 Видимых GPU: {torch.cuda.device_count()}')
    print(f'   🖥️  Имя: {torch.cuda.get_device_name(0)}')
    free_mem = torch.cuda.mem_get_info()[0] / 1024**3
    print(f'   💾 Free memory: {free_mem:.1f} GB')
else:
    print('   ❌ CUDA НЕ доступен')
    exit(1)
"

echo ""
echo "📚 Запуск обучения..."
echo "========================================="

# Запуск обучения с указанием конфига
llamafactory-cli train config_bhl.yaml

echo ""
echo "========================================="
echo "✅ Обучение завершено!"
echo "========================================="
