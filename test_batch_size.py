# test_batch_size_fixed.py
import os
import subprocess
import time
import signal

os.environ["CUDA_VISIBLE_DEVICES"] = "1"
os.environ["PYTORCH_ALLOC_CONF"] = "expandable_segments:True"

def test_batch(batch_size, accumulation, test_id):
    """Тестирует конкретную конфигурацию с минимальным обучением"""
    print(f"\n{'='*50}")
    print(f"Тест #{test_id}: batch={batch_size}, accum={accumulation}")
    print(f"Эффективный batch: {batch_size * accumulation}")
    print("Загрузка модели и датасета... (это может занять 2-3 минуты)")

    # Исправленный конфиг - убрали eval_strategy
    config = f"""model_name_or_path: ../bhl/Models/Qwen2.5-1.5B-Instruct
trust_remote_code: True

stage: sft
do_train: True
finetuning_type: lora
lora_target: all
lora_rank: 8
lora_alpha: 16

dataset: merged_ds
dataset_dir: result_com_lat
template: qwen
cutoff_len: 256
overwrite_cache: True
preprocessing_num_workers: 4
packing: False

output_dir: ./saves/test_{test_id}
logging_steps: 1
save_steps: 1000
overwrite_output_dir: True

per_device_train_batch_size: {batch_size}
gradient_accumulation_steps: {accumulation}
learning_rate: 1.5e-4
num_train_epochs: 0.01
max_steps: 5

bf16: True
gradient_checkpointing: True
flash_attn: sdpa

quantization_bit: 4
quantization_method: bitsandbytes

val_size: 0.05
per_device_eval_batch_size: 2
"""

    with open(f"test_config_{test_id}.yaml", "w") as f:
        f.write(config)

    try:
        start = time.time()

        process = subprocess.Popen(
            ["llamafactory-cli", "train", f"test_config_{test_id}.yaml"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        try:
            stdout, stderr = process.communicate(timeout=300)
            elapsed = time.time() - start

            if process.returncode == 0:
                print(f"✅ УСПЕШНО! Время: {elapsed:.1f} сек")

                # Ищем скорость
                for line in stdout.split('\n'):
                    if 'it/s' in line or 's/it' in line:
                        print(f"   {line.strip()}")
                return True, None
            else:
                print(f"❌ ОШИБКА! Код: {process.returncode}")

                # Анализируем ошибку
                error_lower = stderr.lower()
                if "out of memory" in error_lower or "oom" in error_lower:
                    print("   Причина: НЕ ХВАТАЕТ ПАМЯТИ (OOM)")
                elif "cuda" in error_lower:
                    print("   Причина: CUDA ОШИБКА")
                else:
                    print("   Причина: другая ошибка")
                    # Показываем последние строки
                    for line in stderr.split('\n')[-10:]:
                        if line.strip():
                            print(f"   {line.strip()}")

                return False, stderr[-500:]

        except subprocess.TimeoutExpired:
            process.kill()
            print("❌ ТАЙМАУТ (5 минут) - процесс завис")
            return False, "Timeout"

    except Exception as e:
        print(f"❌ ОШИБКА: {e}")
        return False, str(e)

def cleanup():
    """Очистка временных файлов"""
    import glob
    for f in glob.glob("test_config_*.yaml"):
        try:
            os.remove(f)
        except:
            pass

if __name__ == "__main__":
    print("🔍 ПОИСК ОПТИМАЛЬНОГО BATCH SIZE")
    print("="*50)
    print("⚠️  Каждый тест займет 2-4 минуты (загрузка модели)")
    print("="*50)

    # Тестируем в порядке возрастания batch size
    tests = [
        (1, 16, "A"),  # Стабильный (контрольный)
        (2, 8,  "B"),  # Балансный
        (2, 4,  "C"),  # Эффективный batch=8
        (3, 5,  "D"),  # Эффективный batch=15
        (4, 4,  "E"),  # Оптимизированный
    ]

    results = []
    working_configs = []

    for batch, accum, test_id in tests:
        success, error = test_batch(batch, accum, test_id)
        results.append((batch, accum, success))

        if success:
            working_configs.append((batch, accum))
            print(f"\n✅ Конфигурация РАБОТАЕТ!")

            # Если нашли работающую, спрашиваем
            if len(working_configs) == 1:
                print(f"\n🎯 Найдена работающая конфигурация!")
                print(f"   batch={batch}, accum={accum} -> эффективный batch={batch*accum}")
                response = input("Продолжить тестирование более быстрых вариантов? (y/n): ")
                if response.lower() != 'y':
                    break
        else:
            print(f"\n❌ Конфигурация НЕ РАБОТАЕТ")

            # Если ошибка OOM, дальше тестировать смысла нет
            if error and ("out of memory" in error.lower() or "oom" in error.lower()):
                print("   Причина: не хватает памяти")
                print("   Дальнейшие тесты с большим batch скорее всего тоже упадут")
                break

        # Пауза между тестами
        if test_id != tests[-1][2]:
            print("\n⏳ Пауза 5 секунд перед следующим тестом...")
            time.sleep(5)

    # Итоги
    print("\n" + "="*50)
    print("📊 ИТОГИ ТЕСТИРОВАНИЯ:")
    print("="*50)

    for batch, accum, success in results:
        status = "✅ РАБОТАЕТ" if success else "❌ НЕ РАБОТАЕТ"
        eff = batch * accum
        print(f"{status:12} | batch={batch:2d}, accum={accum:2d} -> effective={eff:2d}")

    if working_configs:
        print("\n🎯 РЕКОМЕНДАЦИЯ:")
        # Берем самую быструю из работающих
        fastest = max(working_configs, key=lambda x: x[0] * x[1])
        print(f"   Используйте: batch_size={fastest[0]}, gradient_accumulation_steps={fastest[1]}")
        print(f"   Эффективный batch: {fastest[0] * fastest[1]}")
        print(f"   Ожидаемое ускорение: ~{16 / (fastest[0] * fastest[1]):.1f}x")

        # Создаем готовый конфиг
        create_config = input("\nСоздать готовый конфиг для обучения? (y/n): ")
        if create_config.lower() == 'y':
            with open("config_rtx_auto.yaml", "w") as f:
                f.write(f"""model_name_or_path: ../bhl/Models/Qwen2.5-1.5B-Instruct
trust_remote_code: True

stage: sft
do_train: True
finetuning_type: lora
lora_target: all
lora_rank: 8
lora_alpha: 16

dataset: merged_ds
dataset_dir: result_com_lat
template: qwen
cutoff_len: 256
overwrite_cache: True
preprocessing_num_workers: 4
packing: False

output_dir: ./saves/qwen_com_lat_lora
logging_steps: 10
save_steps: 100
save_total_limit: 2
overwrite_output_dir: True

per_device_train_batch_size: {fastest[0]}
gradient_accumulation_steps: {fastest[1]}
learning_rate: 1.5e-4
num_train_epochs: 5.0
lr_scheduler_type: cosine
warmup_ratio: 0.1

bf16: True
gradient_checkpointing: True
flash_attn: sdpa

quantization_bit: 4
quantization_method: bitsandbytes

val_size: 0.05
per_device_eval_batch_size: {min(fastest[0], 4)}
eval_strategy: steps
eval_steps: 100
""")
            print("✅ Конфиг создан: config_rtx_auto.yaml")
            print("🚀 Запустите обучение: llamafactory-cli train config_rtx_auto.yaml")
    else:
        print("\n⚠️ НИ ОДНА КОНФИГУРАЦИЯ НЕ РАБОТАЕТ!")
        print("   Используйте стабильный режим: batch=1, accum=16")
        print("\n   Запустите:")
        print("   CUDA_VISIBLE_DEVICES=1 llamafactory-cli train config_rtx_stable.yaml")

    # Очистка
    cleanup()
    print("\n🧹 Временные файлы удалены")
