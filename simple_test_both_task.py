# test_final_model.py
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM
from peft import PeftModel
import glob

def find_latest_adapter():
    """Находит последний чекпоинт"""
    checkpoints = glob.glob("./saves/qwen_merged_lora/checkpoint-*")
    if checkpoints:
        checkpoints.sort(key=lambda x: int(x.split('-')[-1]))
        return checkpoints[-1]
    return "./saves/qwen_merged_lora"

def test_model():
    print("="*60)
    print("🧪 ТЕСТИРОВАНИЕ ДООБУЧЕННОЙ МОДЕЛИ")
    print("="*60)

    adapter_path = find_latest_adapter()
    print(f"\n📁 Используем адаптер: {adapter_path}")

    base_model_path = "../bhl/Models/Qwen2.5-1.5B-Instruct"

    print("\n📦 Загрузка модели...")
    model = AutoModelForCausalLM.from_pretrained(
        base_model_path,
        torch_dtype=torch.bfloat16,
        device_map="cuda:0",
        trust_remote_code=True
    )

    model = PeftModel.from_pretrained(model, adapter_path)
    model.eval()

    tokenizer = AutoTokenizer.from_pretrained(base_model_path, trust_remote_code=True)

    print("✅ Модель загружена\n")

    # Тестовые примеры
    test_cases = [
        {
            "name": "Команда: маркировка",
            "instruction": "Определи команду в тексте",
            "input": "сделай маркируй высказывание",
            "expected": "hlPhrase"
        },
        {
            "name": "LaTeX: плюс-минус",
            "instruction": "Преобразуй текст в формулу LaTeX",
            "input": "плюс-минус игрек и эф",
            "expected": "$(y \\pm f)$"
        },
        {
            "name": "Команда: удаление фразы",
            "instruction": "Определи команду в тексте",
            "input": "вырежи высказывание пожалуйста",
            "expected": "removePhrase"
        },
        {
            "name": "LaTeX: сумма",
            "instruction": "Преобразуй текст в формулу LaTeX",
            "input": "сумма альфа и икс",
            "expected": "$(\\alpha + x)$"
        },
        {
            "name": "Команда: создать формулу",
            "instruction": "Определи команду в тексте",
            "input": "добавь формулу",
            "expected": "createLatex"
        },
        {
            "name": "LaTeX: тангенс",
            "instruction": "Преобразуй текст в формулу LaTeX",
            "input": "тангенс из эф",
            "expected": "$\\tan(f)$"
        },
        {
            "name": "Команда: удалить текст",
            "instruction": "Определи команду в тексте",
            "input": "снеси заметку пожалуйста",
            "expected": "removeText"
        }
    ]

    print("🔍 Тестирование...")
    print("="*60)

    success_count = 0

    for i, test in enumerate(test_cases, 1):
        prompt = f"<|im_start|>system\nYou are Qwen, created by Alibaba Cloud. You are a helpful assistant.<|im_end|>\n<|im_start|>user\n{test['instruction']}\n{test['input']}<|im_end|>\n<|im_start|>assistant\n"

        inputs = tokenizer(prompt, return_tensors="pt").to("cuda:0")

        with torch.no_grad():
            outputs = model.generate(
                **inputs,
                max_new_tokens=50,
                temperature=0.7,
                do_sample=False,
                pad_token_id=tokenizer.eos_token_id
            )

        response = tokenizer.decode(outputs[0][inputs['input_ids'].shape[1]:], skip_special_tokens=True).strip()

        is_correct = test['expected'] in response or response == test['expected']
        if is_correct:
            success_count += 1

        print(f"\n📝 Тест {i}: {test['name']}")
        print(f"   Вход: {test['input']}")
        print(f"   Ожидаемый: {test['expected']}")
        print(f"   🤖 Ответ: {response}")

        if is_correct:
            print("   ✅ ПРАВИЛЬНО!")
        else:
            print("   ❌ НЕПРАВИЛЬНО")

    print("\n" + "="*60)
    print(f"📊 Результат: {success_count}/{len(test_cases)} правильных ответов")

    if success_count == len(test_cases):
        print("🎉 ОТЛИЧНО! Модель идеально работает!")
    elif success_count >= len(test_cases) * 0.8:
        print("👍 ХОРОШО! Модель в основном работает правильно.")
    else:
        print("⚠️ Результат ниже ожидаемого. Возможно, нужно больше данных или эпох.")

if __name__ == "__main__":
    test_model()
