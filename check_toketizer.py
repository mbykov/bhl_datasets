from transformers import AutoTokenizer

tokenizer = AutoTokenizer.from_pretrained("../bhl/Models/Qwen2.5-1.5B-Instruct/orig", trust_remote_code=True)
print(f"Vocab size: {len(tokenizer)}")
print(f"CMD token ID: {tokenizer.convert_tokens_to_ids('[CMD]')}")
print(f"Special tokens: {tokenizer.add_special_tokens}")
