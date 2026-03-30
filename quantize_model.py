#!/usr/bin/env python3
"""
Квантование модели в GGUF для новой версии llama.cpp
"""

import os
import sys
import subprocess
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def find_convert_script(llama_path):
    """Ищет скрипт конвертации в новых местах"""
    candidates = [
        os.path.join(llama_path, "convert", "convert_hf_to_gguf.py"),
        os.path.join(llama_path, "convert_hf_to_gguf.py"),
        os.path.join(llama_path, "convert-hf-to-gguf.py"),
        os.path.join(llama_path, "convert", "convert.py"),
        os.path.join(llama_path, "convert.py"),
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    return None

def quantize_model(model_path, output_dir, quant_types=["q4_0", "q8_0"], llama_path="./llama.cpp"):
    """Квантует модель в GGUF"""

    os.makedirs(output_dir, exist_ok=True)
    model_name = Path(model_path).name

    # 1. Находим скрипт конвертации
    convert_script = find_convert_script(llama_path)
    if not convert_script:
        logger.error("❌ Скрипт конвертации не найден!")
        logger.info("Скачайте его вручную:")
        logger.info(f"  cd {llama_path}")
        logger.info("  wget https://raw.githubusercontent.com/ggerganov/llama.cpp/master/convert_hf_to_gguf.py")
        logger.info("  # или")
        logger.info("  wget https://raw.githubusercontent.com/ggerganov/llama.cpp/master/convert/convert_hf_to_gguf.py")
        return False

    logger.info(f"✅ Найден скрипт конвертации: {convert_script}")

    # 2. Находим утилиту квантования
    quantize_tool = os.path.join(llama_path, "build", "bin", "llama-quantize")
    if not os.path.exists(quantize_tool):
        logger.error(f"❌ llama-quantize не найден: {quantize_tool}")
        return False

    # 3. Конвертируем в FP16 GGUF
    fp16_file = os.path.join(output_dir, f"{model_name}_f16.gguf")

    if not os.path.exists(fp16_file):
        logger.info("📦 Конвертация в FP16 GGUF...")
        cmd = [
            "python", convert_script,
            model_path,
            "--outfile", fp16_file,
            "--outtype", "f16"
        ]
        logger.info(f"   {' '.join(cmd)}")

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            logger.error(f"Ошибка: {result.stderr}")
            return False
        logger.info(f"✅ Создан: {fp16_file}")
    else:
        logger.info(f"ℹ️ FP16 файл уже существует: {fp16_file}")

    # 4. Квантуем в указанные типы
    for quant_type in quant_types:
        output_file = os.path.join(output_dir, f"{model_name}_{quant_type}.gguf")

        if os.path.exists(output_file):
            logger.info(f"ℹ️ {quant_type} файл уже существует, пропускаем")
            continue

        logger.info(f"📦 Квантование в {quant_type.upper()}...")
        cmd = [quantize_tool, fp16_file, output_file, quant_type.upper()]
        logger.info(f"   {' '.join(cmd)}")

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            logger.error(f"Ошибка: {result.stderr}")
            continue

        size = os.path.getsize(output_file) / 1024**3
        logger.info(f"✅ Создан: {output_file} ({size:.2f} GB)")

    return True

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="./models/qwen_merged")
    parser.add_argument("--output", default="./models/gguf")
    parser.add_argument("--type", default="q4_0,q8_0", help="Типы через запятую")
    parser.add_argument("--llama-path", default="./llama.cpp")
    args = parser.parse_args()

    quant_types = [t.strip() for t in args.type.split(",")]

    logger.info("="*60)
    logger.info("КВАНТОВАНИЕ МОДЕЛИ В GGUF")
    logger.info(f"Модель: {args.model}")
    logger.info(f"Типы: {quant_types}")
    logger.info("="*60)

    success = quantize_model(args.model, args.output, quant_types, args.llama_path)
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
