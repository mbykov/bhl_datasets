import os
import subprocess
import yaml

# Настройки GPU
os.environ["CUDA_VISIBLE_DEVICES"] = "0"
os.environ["PYTORCH_ALLOC_CONF"] = "expandable_segments:True"
os.environ["CUDA_LAUNCH_BLOCKING"] = "1"  # Добавляем для отладки CUDA ошибок

def load_config():
    """Загружает базовый конфиг"""
    with open("config.yaml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def tune_com_lat():
    """
    Дообучение на объединенном датасете (команды + LaTeX)
    Стартует от базовой модели (не от командной!)
    """
    print("=" * 60)
    print("Дообучение на объединенном датасете (Команды + LaTeX)")
    print("=" * 60)

    # Проверяем, что объединенный датасет существует
    merged_path = "merged_com_lat/dataset.jsonl"
    if not os.path.exists(merged_path):
        print(f"❌ Ошибка: Файл датасета не найден: {merged_path}")
        print("Сначала запустите merge_command_latex.py")
        return False

    # Загружаем базовый конфиг
    config = load_config()

    # Настраиваем для обучения на объединенном датасете
    config["model_name_or_path"] = config["model_name_or_path"]
    config["dataset"] = "merged_ds"
    config["dataset_dir"] = "merged_com_lat"
    config["output_dir"] = "./saves/qwen_com_lat_lora"

    # УМЕНЬШАЕМ параметры для экономии памяти
    config["cutoff_len"] = 256  # Уменьшаем с 512 до 256 (экономит память)
    config["packing"] = False
    config["per_device_train_batch_size"] = 2  # Уменьшаем с 4 до 2
    config["gradient_accumulation_steps"] = 4  # Оставляем 4 (эффективный batch = 8)
    config["num_train_epochs"] = 5.0
    config["per_device_eval_batch_size"] = 1  # Уменьшаем с 2 до 1

    # Learning rate оставляем
    config["learning_rate"] = 1.5e-4

    # Добавляем оптимизации памяти
    config["gradient_checkpointing"] = True  # Включаем checkpointing для экономии памяти
    config["fp16"] = False  # Отключаем fp16, оставляем bf16
    config["bf16"] = True

    # Сохраняем временный конфиг
    temp_config = "config_com_lat_temp.yaml"
    with open(temp_config, "w", encoding="utf-8") as f:
        yaml.dump(config, f, default_flow_style=False, allow_unicode=True)

    print(f"\n📊 Параметры обучения (оптимизированы для памяти):")
    print(f"   Базовая модель: {config['model_name_or_path']}")
    print(f"   Датасет: {config['dataset']} (из {config['dataset_dir']})")
    print(f"   Эпох: {config['num_train_epochs']}")
    print(f"   Batch size: {config['per_device_train_batch_size']}")
    print(f"   Gradient accumulation: {config['gradient_accumulation_steps']}")
    print(f"   Эффективный batch: {config['per_device_train_batch_size'] * config['gradient_accumulation_steps']}")
    print(f"   Learning rate: {config['learning_rate']}")
    print(f"   Контекст: {config['cutoff_len']} токенов")
    print(f"   Gradient checkpointing: {config['gradient_checkpointing']}")
    print(f"   Выход: {config['output_dir']}")

    # Запускаем обучение
    print("\n🚀 Запуск обучения...")
    try:
        subprocess.run(["llamafactory-cli", "train", temp_config], check=True)
        print("\n✅ Обучение на объединенном датасете успешно завершено!")
        print(f"   Модель сохранена: {config['output_dir']}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"\n❌ Ошибка при обучении: {e}")
        return False
    finally:
        # Удаляем временный конфиг
        if os.path.exists(temp_config):
            os.remove(temp_config)

if __name__ == "__main__":
    # Создаем директорию для сохранения
    os.makedirs("./saves", exist_ok=True)

    # Проверяем наличие объединенного датасета
    if not os.path.exists("./merged_com_lat/dataset.jsonl"):
        print("⚠️ Внимание: файл merged_com_lat/dataset.jsonl не найден")
        print("   Сначала запустите merge_command_latex.py")
        response = input("   Продолжить? (y/n): ")
        if response.lower() != 'y':
            exit(1)

    # Очищаем кэш CUDA перед запуском
    import torch
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
        print(f"🧹 Очищен кэш CUDA. Доступно памяти: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f} GB")

    tune_com_lat()
