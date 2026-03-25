import os
import subprocess

# Настройки GPU для RTX 5060 Ti
os.environ["CUDA_VISIBLE_DEVICES"] = "0"
os.environ["PYTORCH_ALLOC_CONF"] = "expandable_segments:True"

def run_train():
    config_path = "config.yaml"
    if not os.path.exists(config_path):
        print(f"Error: {config_path} not found!")
        return

    command = ["llamafactory-cli", "train", config_path]
    print("Starting Fine-tuning on NVIDIA GeForce RTX 5060 Ti...")
    try:
        subprocess.run(command, check=True)
        print("Training completed successfully!")
    except subprocess.CalledProcessError as e:
        print(f"Error during training: {e}")

if __name__ == "__main__":
    os.makedirs("./saves", exist_ok=True)
    run_train()
