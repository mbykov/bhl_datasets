#!/usr/bin/env python3
"""
inference_latex_lora.py - Инференс дообученной модели для преобразования
русского текста в LaTeX
"""

import sys
import argparse
import warnings
import re
from pathlib import Path

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
from peft import PeftModel

warnings.filterwarnings("ignore")
import logging
logging.getLogger("transformers").setLevel(logging.ERROR)

class LatexInference:
    def __init__(self, model_path, device=None):
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")

        print(f"🚀 Загрузка модели из {model_path} на {self.device}...", flush=True)

        adapter_config_path = Path(model_path) / "adapter_config.json"
        if not adapter_config_path.exists():
            raise FileNotFoundError(f"Не найден adapter_config.json в {model_path}")

        with open(adapter_config_path, 'r') as f:
            import json
            adapter_config = json.load(f)
            base_model_name = adapter_config.get('base_model_name_or_path')

        if not base_model_name:
            raise ValueError("Не удалось определить базовую модель из adapter_config")

        print(f"📦 Базовая модель: {base_model_name}", flush=True)

        bnb_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.bfloat16,
            bnb_4bit_use_double_quant=True,
        )

        self.base_model = AutoModelForCausalLM.from_pretrained(
            base_model_name,
            quantization_config=bnb_config,
            device_map="auto",
            trust_remote_code=True,
            torch_dtype=torch.bfloat16,
        )

        self.tokenizer = AutoTokenizer.from_pretrained(
            base_model_name,
            trust_remote_code=True,
            padding_side="left",
        )

        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token

        print(f"📦 Загрузка LoRA из {model_path}...", flush=True)
        self.model = PeftModel.from_pretrained(self.base_model, model_path)
        self.model = self.model.merge_and_unload()

        self.model.eval()
        print("✅ Модель готова", flush=True)

    def text_to_latex(self, text: str, max_length: int = 512) -> str:
        # Возвращаемся к простому рабочему промпту
        prompt = f"{{'instruction': 'Convert the following description to LaTeX script.', 'input': '{text}'}}"

        inputs = self.tokenizer(prompt, return_tensors="pt", truncation=True, max_length=512).to(self.device)

        with torch.no_grad():
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=max_length,
                do_sample=False,
            )

        result = self.tokenizer.decode(outputs[0], skip_special_tokens=True)

        # Извлекаем ответ после промпта
        if result.startswith(prompt):
            latex = result[len(prompt):].strip()
        else:
            latex = result.strip()

        # Берём только первую строку
        latex = latex.split('\n')[0].strip()

        # Убираем всё, что начинается с "instruction:" в ответе
        if 'instruction:' in latex:
            latex = latex.split('instruction:')[0].strip()

        # Убираем кавычки
        latex = latex.strip('\'"')

        # Если ответ пустой или слишком короткий, возвращаем оригинал
        if len(latex) < 2:
            latex = text

        return latex

    def interactive_mode(self):
        print("\n" + "="*60)
        print("🖥️  Интерактивный режим")
        print("="*60)
        print("Введите математическое описание на русском языке")
        print("Команды:")
        print("  :q - выход")
        print("  :h - история")
        print("="*60 + "\n")

        history = []

        while True:
            try:
                user_input = input(">>> ").strip()
                if not user_input:
                    continue

                if user_input == ':q':
                    print("До свидания!")
                    break

                if user_input == ':h':
                    if not history:
                        print("История пуста\n")
                    else:
                        print("\nИстория:")
                        for i, (inp, out) in enumerate(history[-10:], 1):
                            print(f"{i}. {inp}")
                            print(f"   → {out}\n")
                    continue

                result = self.text_to_latex(user_input)
                print(f"{result}\n")
                history.append((user_input, result))

            except KeyboardInterrupt:
                print("\nДо свидания!")
                break
            except Exception as e:
                print(f"❌ Ошибка: {e}\n")

def main():
    parser = argparse.ArgumentParser(description='Инференс модели LaTeX')
    parser.add_argument('--model', type=str, required=True,
                       help='Путь к дообученной модели')
    parser.add_argument('--input', type=str, default=None,
                       help='Входная строка (однократный запуск)')
    args = parser.parse_args()

    inference = LatexInference(args.model)

    if args.input:
        result = inference.text_to_latex(args.input)
        print(result)
    else:
        inference.interactive_mode()

if __name__ == "__main__":
    main()
