import os
import gc
import torch
import subprocess
import yaml

# ========== НАСТРОЙКИ ПАМЯТИ ==========
# Не ограничиваем, а оптимизируем
os.environ["CUDA_VISIBLE_DEVICES"] = "0"
os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True,max_split_size_mb:512"
os.environ["CUDA_LAUNCH_BLOCKING"] = "1"  # Только для отладки, после можно убрать

# Очистка перед запуском
if torch.cuda.is_available():
    torch.cuda.empty_cache()
    torch.cuda.reset_peak_memory_stats()
    print(f"🎮 GPU: {torch.cuda.get_device_name(0)}")
    print(f"   Всего памяти: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f} GB")
gc.collect()
# ======================================

def load_config():
    with open("config.yaml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def tune_com_lat():
    print("=" * 60)
    print("Дообучение на объединенном датасете (Команды + LaTeX)")
    print("=" * 60)

    merged_path = "result_com_lat/dataset.jsonl"
    if not os.path.exists(merged_path):
        print(f"❌ Ошибка: Файл датасета не найден: {merged_path}")
        return False

    config = load_config()

    # Оптимизированные параметры (без лишних ограничений)
    config["model_name_or_path"] = config["model_name_or_path"]
    config["dataset"] = "merged_ds"
    config["dataset_dir"] = "result_com_lat"
    config["output_dir"] = "./saves/qwen_com_lat_lora"

    # Стартовые безопасные параметры
    config["per_device_train_batch_size"] = 1
    config["gradient_accumulation_steps"] = 8  # Эффективный batch = 8
    config["cutoff_len"] = 256
    config["gradient_checkpointing"] = True
    config["bf16"] = False
    config["fp16"] = True
    config["lora_rank"] = 8
    config["lora_alpha"] = 16

    # Остальные параметры
    config["num_train_epochs"] = 5.0
    config["per_device_eval_batch_size"] = 1
    config["learning_rate"] = 1.5e-4
    config["warmup_ratio"] = 0.1
    config["lr_scheduler_type"] = "cosine"
    config["logging_steps"] = 10
    config["save_steps"] = 100
    config["eval_steps"] = 100
    config["save_total_limit"] = 2
    config["dataloader_pin_memory"] = False
    config["preprocessing_num_workers"] = 2

    temp_config = "config_com_lat_temp.yaml"
    with open(temp_config, "w", encoding="utf-8") as f:
        yaml.dump(config, f, default_flow_style=False, allow_unicode=True)

    print(f"\n📊 Параметры обучения:")
    print(f"   Batch size: {config['per_device_train_batch_size']}")
    print(f"   Gradient accumulation: {config['gradient_accumulation_steps']}")
    print(f"   Эффективный batch: {config['per_device_train_batch_size'] * config['gradient_accumulation_steps']}")
    print(f"   Контекст: {config['cutoff_len']} токенов")
    print(f"   LoRA rank: {config['lora_rank']}")
    print(f"   Выход: {config['output_dir']}")

    print("\n🚀 Запуск обучения...")
    try:
        subprocess.run(["llamafactory-cli", "train", temp_config], check=True)
        print("\n✅ Обучение успешно завершено!")
        return True
    except subprocess.CalledProcessError as e:
        print(f"\n❌ Ошибка: {e}")
        return False
    finally:
        if os.path.exists(temp_config):
            os.remove(temp_config)

if __name__ == "__main__":
    tune_com_lat()
