#!/usr/bin/env python3 -u
"""
Генератор естественных прочтений LaTeX-скриптов
Сначала нормализация (замена символов из config), затем стилизация (LLM)
"""

import json
import os
import sys
import re
import requests
import random
import time
import signal
import resource
import threading
import queue
import subprocess
from datetime import datetime
from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple

print(f"\n🖥️ CUDA_VISIBLE_DEVICES = {os.environ.get('CUDA_VISIBLE_DEVICES', 'не задана')}", flush=True)

result = subprocess.run(['nvidia-smi', '--query-gpu=name', '--format=csv,noheader'], capture_output=True, text=True); gpus = result.stdout.strip().split('\n'); active = os.environ.get('CUDA_VISIBLE_DEVICES', '0'); idx = int(active) if active.isdigit() else 0; print(f"\n🖥️ Активная GPU: {gpus[idx] if idx < len(gpus) else 'не определена'}", flush=True)

# ========== БЕЗОПАСНОСТЬ ==========
def setup_safety():
    try:
        resource.setrlimit(resource.RLIMIT_AS, (12 * 1024 * 1024 * 1024, 12 * 1024 * 1024 * 1024))
        print("✅ Ограничение памяти: 12 GB", flush=True)
    except Exception as e:
        print(f"⚠️ Не удалось установить ограничение памяти: {e}", flush=True)

    try:
        resource.setrlimit(resource.RLIMIT_CPU, (600, 600))
        print("✅ Ограничение CPU: 600 секунд", flush=True)
    except Exception as e:
        print(f"⚠️ Не удалось установить ограничение CPU: {e}", flush=True)

def timeout_handler(signum, frame):
    print(f"\n❌ Превышен лимит времени ({signum})", flush=True)
    sys.exit(1)

signal.signal(signal.SIGALRM, timeout_handler)
signal.alarm(1800)

setup_safety()
os.environ['OMP_NUM_THREADS'] = '2'
os.environ['MKL_NUM_THREADS'] = '2'
sys.stdout.reconfigure(line_buffering=True)

@dataclass
class ProcessedExample:
    example: Dict
    result: Dict
    memory_used: int
    worker_id: int
    duration: float


class HybridGenerator:
    def __init__(self, model="qwen2.5:7b", ollama_url="http://localhost:11434",
                 config_dir='config', max_workers=2, batch_size=30,
                 memory_threshold=14000, request_delay=0.3):

        self.model = model
        self.ollama_url = ollama_url
        self.max_workers = max_workers
        self.batch_size = batch_size
        self.memory_threshold = memory_threshold
        self.request_delay = request_delay

        self.input_queue = queue.Queue()
        self.output_queue = queue.Queue()

        self.processed_count = 0
        self.failed_count = 0
        self.peak_memory = 0
        self.lock = threading.Lock()
        self.session = requests.Session()

        self._load_dictionaries(config_dir)

        print(f"✅ Гибридный генератор инициализирован", flush=True)
        print(f"   Потоков: {max_workers}, Батч: {batch_size}, Порог памяти: {memory_threshold} MB", flush=True)

    def _load_dictionaries_(self, config_dir):
        """Загружает словари из config файлов"""
        # Загружаем греческие буквы
        self.greeks = self._load_jsonl(os.path.join(config_dir, 'greeks.jsonl'))
        self.greek_rus = {}
        self.greek_eng = {}
        for g in self.greeks:
            self.greek_rus[g['sym']] = g.get('rus', g['sym'])
            self.greek_eng[g['sym']] = g.get('eng', g['sym'])

        # Загружаем латинские буквы
        self.latins = self._load_jsonl(os.path.join(config_dir, 'latins.jsonl'))
        self.latin_rus = {}
        self.latin_eng = {}
        for l in self.latins:
            sym = l['sym']
            rus_list = l.get('rus', [''])
            eng_list = l.get('eng', [''])
            self.latin_rus[sym] = rus_list[0] if rus_list else sym
            self.latin_eng[sym] = eng_list[0] if eng_list else sym

        # Загружаем символы (операторы, функции)
        self.symbols = self._load_jsonl(os.path.join(config_dir, 'symbols.jsonl'))
        self.rus_map = {}
        self.eng_map = {}
        for s in self.symbols:
            # Для русского: сначала rus_a, если нет - rus_t
            rus_val = s.get('rus_a')
            if not rus_val:
                rus_val = s.get('rus_t', s['sym'])
            # Для английского: сначала eng_a, если нет - eng_t
            eng_val = s.get('eng_a')
            if not eng_val:
                eng_val = s.get('eng_t', s['sym'])
            self.rus_map[s['sym']] = rus_val
            self.eng_map[s['sym']] = eng_val

        # Загружаем стили
        self.styles_config = self._load_json(os.path.join(config_dir, 'styles.json'))
        self.styles = {}
        if self.styles_config and 'styles' in self.styles_config:
            for s in self.styles_config['styles']:
                self.styles[s['name']] = s

        if not self.styles:
            self.styles = {
                "разговорный": {"rules_rus": "Кратко", "rules_eng": "Concise",
                               "example_rus": "а плюс бэ", "example_eng": "a plus b"},
                "академический": {"rules_rus": "Правильные термины", "rules_eng": "Proper terms",
                                 "example_rus": "сумма а и бэ", "example_eng": "sum of a and b"}
            }

        print(f"✅ Загружено греческих: {len(self.greek_rus)}", flush=True)
        print(f"✅ Загружено латинских: {len(self.latin_rus)}", flush=True)
        print(f"✅ Загружено символов: {len(self.rus_map)}", flush=True)
        print(f"✅ Загружено стилей: {len(self.styles)}", flush=True)


    def _load_dictionaries(self, config_dir):
      """Загружает словари из config файлов"""
      # Загружаем греческие буквы
      self.greeks = self._load_jsonl(os.path.join(config_dir, 'greeks.jsonl'))
      self.greek_rus = {}
      self.greek_eng = {}
      for g in self.greeks:
        self.greek_rus[g['sym']] = g.get('rus', g['sym'])
        self.greek_eng[g['sym']] = g.get('eng', g['sym'])

        # Загружаем латинские буквы
        self.latins = self._load_jsonl(os.path.join(config_dir, 'latins.jsonl'))
        self.latin_rus = {}
        self.latin_eng = {}
        for l in self.latins:
          sym = l['sym']
          rus_list = l.get('rus', [''])
          eng_list = l.get('eng', [''])
          self.latin_rus[sym] = rus_list[0] if rus_list else sym
          self.latin_eng[sym] = eng_list[0] if eng_list else sym

          # Загружаем символы (операторы, функции) - ИСПРАВЛЕНО
          self.symbols = self._load_jsonl(os.path.join(config_dir, 'symbols.jsonl'))
          self.rus_map = {}
          self.eng_map = {}
          for s in self.symbols:
            # Берем поля 'rus' и 'eng' напрямую
            self.rus_map[s['sym']] = s.get('rus', s['sym'])
            self.eng_map[s['sym']] = s.get('eng', s['sym'])

            # Загружаем стили
            self.styles_config = self._load_json(os.path.join(config_dir, 'styles.json'))
            self.styles = {}
            if self.styles_config and 'styles' in self.styles_config:
              for s in self.styles_config['styles']:
                self.styles[s['name']] = s

                if not self.styles:
                  self.styles = {
                    "разговорный": {"rules_rus": "Кратко", "rules_eng": "Concise",
                                    "example_rus": "а плюс бэ", "example_eng": "a plus b"},
                    "академический": {"rules_rus": "Правильные термины", "rules_eng": "Proper terms",
                                      "example_rus": "сумма а и бэ", "example_eng": "sum of a and b"}
                  }

                  print(f"✅ Загружено греческих: {len(self.greek_rus)}", flush=True)
                  print(f"✅ Загружено латинских: {len(self.latin_rus)}", flush=True)
                  print(f"✅ Загружено символов: {len(self.rus_map)}", flush=True)
                  print(f"✅ Загружено стилей: {len(self.styles)}", flush=True)

    def _load_jsonl(self, path):
        data = []
        try:
            with open(path, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        data.append(json.loads(line))
        except FileNotFoundError:
            print(f"⚠️ Файл {path} не найден", flush=True)
        return data

    def _load_json(self, path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"⚠️ Файл {path} не найден", flush=True)
            return {"styles": []}

    def _load_input_jsonl(self, path: str, limit: int = None) -> List[Dict]:
        examples = []
        try:
            with open(path, 'r', encoding='utf-8') as f:
                for idx, line in enumerate(f):
                    if line.strip():
                        if limit and idx >= limit:
                            break
                        data = json.loads(line)
                        examples.append({
                            'sec': data.get('sec', 'unknown'),
                            'sym': data.get('sym', 'unknown'),
                            'rus_name': data.get('rus', ''),
                            'eng_name': data.get('eng', ''),
                            'script': data.get('script', ''),
                            'scheme': data.get('scheme', ''),
                            'idx': idx
                        })
        except FileNotFoundError:
            print(f"❌ Файл {path} не найден", flush=True)
            sys.exit(1)
        return examples

    def normalize(self, latex: str, lang: str = 'rus') -> str:
        """НОРМАЛИЗАЦИЯ: замена LaTeX команд на слова (только из конфигов)"""
        text = latex.strip('$')

        # Выбираем словари в зависимости от языка
        if lang == 'rus':
            symbol_map = self.rus_map
            greek_map = self.greek_rus
            latin_map = self.latin_rus
        else:
            symbol_map = self.eng_map
            greek_map = self.greek_eng
            latin_map = self.latin_eng

        # 1. Заменяем символы (операторы, функции) - сначала длинные
        for sym, repl in sorted(symbol_map.items(), key=lambda x: -len(x[0])):
            text = text.replace(sym, repl)

        # 2. Заменяем греческие буквы
        for sym, name in greek_map.items():
            text = text.replace(sym, name)

        # 3. Заменяем одиночные латинские буквы (переменные)
        for letter, name in latin_map.items():
            text = re.sub(rf'\b{letter}\b', name, text)
            text = re.sub(rf'\b{letter.upper()}\b', name.capitalize(), text)

        # 4. Убираем оставшиеся LaTeX команды
        text = re.sub(r'\\([a-zA-Z]+)', r'\1', text)

        # 5. Убираем фигурные скобки
        text = text.replace('{', ' ').replace('}', ' ')

        # 6. Очищаем пробелы
        text = re.sub(r'\s+', ' ', text).strip()

        # Предупреждение о незамененных символах
        if '\\' in text:
            unknown = re.findall(r'\\([a-zA-Z]+)', text)
            if unknown:
                print(f"      ⚠️ Неизвестные символы: {unknown}", flush=True)

        return text

    def stylize_one(self, normalized_text: str, style_name: str, lang: str, max_retries: int = 3) -> str:
        """СТИЛИЗАЦИЯ: LLM оформляет нормализованный текст в стиле"""

        time.sleep(self.request_delay)
        style = self.styles.get(style_name, self.styles.get("разговорный"))

        if lang == 'rus':
            rules = style.get('rules_rus', 'Оформи текст естественно.')
            example = style.get('example_rus', 'а плюс бэ')
            prompt = f"""Текст формулы (слова уже заменены): {normalized_text}

Оформи этот текст в стиле "{style_name}".
Правила: {rules}
Пример: {example}

Требования:
- НЕ меняй названия переменных
- Можно склонять переменные по падежам
- Можно использовать синонимы для операторов
- Выведи ТОЛЬКО результат, без пояснений

Результат:"""
        else:
            rules = style.get('rules_eng', 'Format this text naturally.')
            example = style.get('example_eng', 'a plus b')
            prompt = f"""Formula text (words already replaced): {normalized_text}

Format this text in "{style_name}" style.
Rules: {rules}
Example: {example}

Requirements:
- DO NOT change variable names
- You can use synonyms for operators
- Output ONLY the result, no explanations

Result:"""

        for attempt in range(max_retries):
            try:
                response = self.session.post(
                    f"{self.ollama_url}/api/generate",
                    json={
                        "model": self.model,
                        "prompt": prompt,
                        "stream": False,
                        "temperature": 0.2,
                        "keep_alive": 0,
                        "context": [],
                        "options": {"num_predict": 100, "num_ctx": 256}
                    },
                    timeout=25
                )

                if response.status_code == 200:
                    result = response.json().get('response', '').strip()
                    result = result.strip('"\'')
                    result = result.split('\n')[0]
                    result = re.sub(r'\s+', ' ', result).strip()

                    if result and len(result) > 3:
                        return result

            except Exception as e:
                if attempt < max_retries - 1:
                    time.sleep(1)

        return normalized_text

    def process_one_example(self, example: Dict, worker_id: int) -> ProcessedExample:
        start_time = time.time()

        # Определяем need_styling
        scheme = example.get('scheme', '')
        need_styling = '@' in scheme or 'next' in scheme or len(re.findall(r'[()]', scheme)) > 2
        style = random.choice(list(self.styles.keys())) if need_styling else None

        # НОРМАЛИЗАЦИЯ (первый этап)
        rus_normalized = self.normalize(example['script'], 'rus')
        eng_normalized = self.normalize(example['script'], 'eng')

        # ЛОГИРОВАНИЕ
        print(f"\n📝 [Пример {example['idx']}]", flush=True)
        print(f"   Исходный скрипт: {example['script']}", flush=True)
        print(f"   Нормализованный русский: {rus_normalized}", flush=True)
        print(f"   Нормализованный английский: {eng_normalized}", flush=True)

        # СТИЛИЗАЦИЯ (второй этап, только для сложных)
        if need_styling and style:
            rus = self.stylize_one(rus_normalized, style, 'rus')
            eng = self.stylize_one(eng_normalized, style, 'eng')
            style_used = style
            # ЛОГИРОВАНИЕ РЕЗУЛЬТАТА
            print(f"   Стиль: {style}", flush=True)
            print(f"   Результат русский: {rus}", flush=True)
            print(f"   Результат английский: {eng}", flush=True)
        else:
            rus = rus_normalized
            eng = eng_normalized
            style_used = "нормализация"
            print(f"   (без стилизации)", flush=True)

        result = {
            "sec": example['sec'],
            "sym": example['sym'],
            "rus_name": example['rus_name'],
            "eng_name": example['eng_name'],
            "script": example['script'],
            "scheme": example['scheme'],
            "idx": example['idx'],
            "style": style_used,
            "rus": rus,
            "eng": eng
        }

        duration = time.time() - start_time
        memory = self.get_gpu_memory() or 0

        return ProcessedExample(example=example, result=result, memory_used=memory,
                                worker_id=worker_id, duration=duration)

    def get_gpu_memory(self) -> Optional[int]:
        try:
            result = subprocess.run(
                ['nvidia-smi', '--query-gpu=memory.used', '--format=csv,noheader,nounits'],
                capture_output=True, text=True, timeout=2
            )
            if result.returncode == 0:
                mem = int(result.stdout.strip().split('\n')[0])
                with self.lock:
                    self.peak_memory = max(self.peak_memory, mem)
                return mem
        except:
            pass
        return None

    def unload_model(self):
        try:
            self.session.post(
                f"{self.ollama_url}/api/generate",
                json={"model": self.model, "keep_alive": 0},
                timeout=5
            )
        except:
            pass

    def memory_monitor(self, stop_event: threading.Event):
        while not stop_event.is_set():
            mem = self.get_gpu_memory()
            if mem and mem > self.memory_threshold:
                print(f"\n⚠️ Критическая память: {mem} MB, очистка...", flush=True)
                self.unload_model()
                time.sleep(3)
            time.sleep(5)

    def worker_function(self, worker_id: int, stop_event: threading.Event):
        while not stop_event.is_set():
            try:
                example = self.input_queue.get(timeout=1)
                if example is None:
                    break

                processed = self.process_one_example(example, worker_id)
                self.output_queue.put(processed)

                with self.lock:
                    self.processed_count += 1
                    if self.processed_count % self.batch_size == 0:
                        print(f"\n🧹 Батч {self.processed_count} завершен", flush=True)
                        self.unload_model()
                        time.sleep(1)

            except queue.Empty:
                continue
            except Exception as e:
                print(f"❌ Worker {worker_id} ошибка: {e}", flush=True)
                with self.lock:
                    self.failed_count += 1

    def process_scripts(self, input_path: str, output_dir: str, num_examples: int = None):
        print(f"\n📚 Загрузка {input_path}...", flush=True)

        examples = self._load_input_jsonl(input_path, num_examples)
        print(f"📊 Загружено примеров: {len(examples)}", flush=True)

        valid_examples = []
        for ex in examples:
            valid_examples.append(ex)

        print(f"📊 Примеров к обработке: {len(valid_examples)}", flush=True)

        for ex in valid_examples:
            self.input_queue.put(ex)

        stop_event = threading.Event()

        monitor_thread = threading.Thread(target=self.memory_monitor, args=(stop_event,), daemon=True)
        monitor_thread.start()

        workers = []
        for i in range(self.max_workers):
            worker = threading.Thread(target=self.worker_function, args=(i, stop_event))
            worker.start()
            workers.append(worker)

        results = []
        start_time = datetime.now()

        for _ in range(len(valid_examples)):
            try:
                processed = self.output_queue.get(timeout=30)
                results.append(processed.result)

                if len(results) % 10 == 0:
                    elapsed = (datetime.now() - start_time).total_seconds()
                    speed = len(results) / elapsed if elapsed > 0 else 0
                    print(f"📊 [{len(results)}/{len(valid_examples)}] {speed:.2f} экз/сек", flush=True)

                    os.makedirs(output_dir, exist_ok=True)
                    with open(os.path.join(output_dir, 'checkpoint.json'), 'w', encoding='utf-8') as f:
                        json.dump(results, f, ensure_ascii=False, indent=2)

            except queue.Empty:
                print("⚠️ Таймаут ожидания результатов", flush=True)
                break

        stop_event.set()
        for _ in workers:
            self.input_queue.put(None)
        for worker in workers:
            worker.join(timeout=5)

        split_idx = int(len(results) * 0.9)
        train_data = results[:split_idx]
        test_data = results[split_idx:]

        os.makedirs(output_dir, exist_ok=True)

        with open(os.path.join(output_dir, 'train.json'), 'w', encoding='utf-8') as f:
            json.dump(train_data, f, ensure_ascii=False, indent=2)
        with open(os.path.join(output_dir, 'test.json'), 'w', encoding='utf-8') as f:
            json.dump(test_data, f, ensure_ascii=False, indent=2)

        total_time = (datetime.now() - start_time).total_seconds()
        print(f"\n✅ Готово за {total_time:.1f} сек!", flush=True)
        print(f"📊 Train: {len(train_data)}, Test: {len(test_data)}", flush=True)
        print(f"📊 Пик памяти: {self.peak_memory} MB", flush=True)


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', default='scripts/dataset.jsonl')
    parser.add_argument('--output-dir', default='results')
    parser.add_argument('--num-examples', type=int, default=None)
    parser.add_argument('--model', default='qwen2.5:7b')
    parser.add_argument('--max-workers', type=int, default=2)
    parser.add_argument('--batch-size', type=int, default=30)
    parser.add_argument('--memory-threshold', type=int, default=14000)
    parser.add_argument('--delay', type=float, default=0.3)
    args = parser.parse_args()

    generator = HybridGenerator(
        model=args.model,
        max_workers=min(args.max_workers, 3),
        batch_size=args.batch_size,
        memory_threshold=args.memory_threshold,
        request_delay=args.delay
    )
    generator.process_scripts(args.input, args.output_dir, args.num_examples)



if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n⚠️ Прервано пользователем", flush=True)
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Ошибка: {e}", flush=True)
        import traceback
        traceback.print_exc()
        sys.exit(1)
