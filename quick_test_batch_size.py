# quick_test.py
import os
import subprocess

os.environ["CUDA_VISIBLE_DEVICES"] = "1"

# Тестируем batch=4 на 100 шагах
config_test = """
model_name_or_path: ../bhl/Models/Qwen2.5-1.5B-Instruct
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

output_dir: ./saves/test_batch4
logging_steps: 5
save_steps: 1000
overwrite_output_dir: True

per_device_train_batch_size: 4
gradient_accumulation_steps: 4
learning_rate: 1.5e-4
num_train_epochs: 0.01
max_steps: 100  # Всего 100 шагов для теста

bf16: True
gradient_checkpointing: True
flash_attn: sdpa

quantization_bit: 4
quantization_method: bitsandbytes

val_size: 0.05
per_device_eval_batch_size: 4
eval_strategy: steps
eval_steps: 1000
"""

with open("config_test_batch4.yaml", "w") as f:
    f.write(config_test)

print("🧪 Тестируем batch=4 (100 шагов)...")
print("Если пройдет успешно - можно использовать batch=4")
print("="*50)

try:
    subprocess.run(["sudo", "nvidia-smi", "-i", "1", "-pl", "150"], capture_output=True)
    result = subprocess.run(
        ["llamafactory-cli", "train", "config_test_batch4.yaml"],
        timeout=600  # 10 минут на тест
    )

    if result.returncode == 0:
        print("\n✅ batch=4 РАБОТАЕТ! Можно использовать быстрый режим!")
        print("   Время обучения сократится до ~4 часов")
    else:
        print("\n❌ batch=4 не прошел, используем batch=2")

except subprocess.TimeoutExpired:
    print("\n❌ Тест завис, batch=4 не стабилен")
except Exception as e:
    print(f"\n❌ Ошибка: {e}")# quick_test.py
import os
import subprocess

os.environ["CUDA_VISIBLE_DEVICES"] = "1"

# Тестируем batch=4 на 100 шагах
config_test = """
model_name_or_path: ../bhl/Models/Qwen2.5-1.5B-Instruct
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

output_dir: ./saves/test_batch4
logging_steps: 5
save_steps: 1000
overwrite_output_dir: True

per_device_train_batch_size: 4
gradient_accumulation_steps: 4
learning_rate: 1.5e-4
num_train_epochs: 0.01
max_steps: 100  # Всего 100 шагов для теста

bf16: True
gradient_checkpointing: True
flash_attn: sdpa

quantization_bit: 4
quantization_method: bitsandbytes

val_size: 0.05
per_device_eval_batch_size: 4
eval_strategy: steps
eval_steps: 1000
"""

with open("config_test_batch4.yaml", "w") as f:
    f.write(config_test)

print("🧪 Тестируем batch=4 (100 шагов)...")
print("Если пройдет успешно - можно использовать batch=4")
print("="*50)

try:
    subprocess.run(["sudo", "nvidia-smi", "-i", "1", "-pl", "150"], capture_output=True)
    result = subprocess.run(
        ["llamafactory-cli", "train", "config_test_batch4.yaml"],
        timeout=600  # 10 минут на тест
    )

    if result.returncode == 0:
        print("\n✅ batch=4 РАБОТАЕТ! Можно использовать быстрый режим!")
        print("   Время обучения сократится до ~4 часов")
    else:
        print("\n❌ batch=4 не прошел, используем batch=2")

except subprocess.TimeoutExpired:
    print("\n❌ Тест завис, batch=4 не стабилен")
except Exception as e:
    print(f"\n❌ Ошибка: {e}")
