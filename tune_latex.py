import os
import subprocess
import yaml

# Настройки GPU
os.environ["CUDA_VISIBLE_DEVICES"] = "0"
os.environ["PYTORCH_ALLOC_CONF"] = "expandable_segments:True"

def load_config():
    """Загружает базовый конфиг"""
    with open("config_latex.yaml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def tune_latex():
    """
    Дообучение на LaTeX датасете поверх уже обученной командной модели.
    Команды являются обязательной базой.
    """
    print("=" * 60)
    print("Дообучение на LaTeX (поверх командной модели)")
    print("=" * 60)

    # Проверяем, что командная модель существует
    # command_adapter_path = "./saves/qwen_command_lora"
    # if not os.path.exists(command_adapter_path):
    #     print(f"❌ Ошибка: Командная модель (LoRA) не найдена по пути {command_adapter_path}")
    #     print("Сначала запустите tune_command.py для обучения команд")
    #     return False

    # Загружаем базовый конфиг
    config = load_config()

    # Важно: загружаем БАЗОВУЮ модель + адаптер
    # model_name_or_path должен указывать на базовую модель Qwen
    # adapter_name_or_path указывает на LoRA веса
    config["model_name_or_path"] = config["model_name_or_path"]  # Базовая модель
    # config["adapter_name_or_path"] = command_adapter_path        # LoRA после команд
    config["finetuning_type"] = "lora"                           # Продолжаем LoRA
    config["dataset"] = "latex_ds"                               # LaTeX датасет
    config["output_dir"] = "./saves/qwen_latex_lora"             # Новый адаптер

    # Корректируем параметры для LaTeX
    config["cutoff_len"] = 512
    config["packing"] = False
    config["per_device_train_batch_size"] = 4
    config["gradient_accumulation_steps"] = 4
    config["num_train_epochs"] = 3.0
    config["per_device_eval_batch_size"] = 2

    # Сохраняем временный конфиг
    temp_config = "config_latex.yaml"
    with open(temp_config, "w", encoding="utf-8") as f:
        yaml.dump(config, f, default_flow_style=False, allow_unicode=True)

    print(f"\n📊 Параметры обучения:")
    print(f"   Базовая модель: {config['model_name_or_path']}")
    # print(f"   Стартовый адаптер: {command_adapter_path}")
    print(f"   Датасет: {config['dataset']}")
    print(f"   Эпох: {config['num_train_epochs']}")
    print(f"   Batch size: {config['per_device_train_batch_size']}")
    print(f"   Контекст: {config['cutoff_len']} токенов")
    print(f"   Выход: {config['output_dir']}")

    # Запускаем обучение
    print("\n🚀 Запуск обучения...")
    try:
        subprocess.run(["llamafactory-cli", "train", temp_config], check=True)
        print("\n✅ Обучение на LaTeX успешно завершено!")
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
    os.makedirs("./saves", exist_ok=True)

    if not os.path.exists("./generate_latex/scripts/train.json"):
        print("⚠️  Внимание: файл generate_latex/scripts/train.json не найден")
        print("   Сначала запустите aloud.py")
        response = input("   Продолжить? (y/n): ")
        if response.lower() != 'y':
            exit(1)

    tune_latex()
