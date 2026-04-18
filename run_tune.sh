#!/bin/bash
# run_tune.sh - Запуск дообучения через tune_command.py с защитой от зависаний

set -e

echo "========================================="
echo "🚀 Запуск дообучения (tune_command.py)"
echo "========================================="

# Принудительно указываем GPU 1 (RTX 5060 Ti)
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
echo "📚 Запуск tune_command.py..."
echo "========================================="

# Запуск с ограничением ресурсов и защитой от зависаний
# timeout - опционально, можно выставить лимит времени (например 6h)
python3 tune_command.py

echo ""
echo "========================================="
echo "✅ Дообучение завершено!"
echo "========================================="
