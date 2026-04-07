#!/usr/bin/env python3 -u
"""
Генератор естественных прочтений LaTeX-скриптов
Гибридный вариант с многопоточностью и контролем памяти
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

# ========== БЕЗОПАСНОСТЬ ==========
def setup_safety():
    """Настройка безопасности для предотвращения зависаний"""
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
signal.alarm(1800)  # 30 минут

setup_safety()

# Ограничения через переменные окружения
os.environ['OMP_NUM_THREADS'] = '2'
os.environ['MKL_NUM_THREADS'] = '2'

sys.stdout.reconfigure(line_buffering=True)

# ========== ДАТАКЛАССЫ ==========
@dataclass
class ProcessedExample:
    """Результат обработки примера"""
    example: Dict
    result: Dict
    memory_used: int
    worker_id: int
    duration: float

# ========== ОСНОВНОЙ КЛАСС ==========
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

        # Очереди для пайплайна
        self.input_queue = queue.Queue()
        self.output_queue = queue.Queue()

        # Статистика
        self.processed_count = 0
        self.failed_count = 0
        self.peak_memory = 0
        self.lock = threading.Lock()

        # Загружаем словари
        self._load_dictionaries(config_dir)

        print(f"✅ Гибридный генератор инициализирован", flush=True)
        print(f"   Потоков: {max_workers}, Батч: {batch_size}, Порог памяти: {memory_threshold} MB", flush=True)

    def _load_dictionaries(self, config_dir):
        """Загружает словари из config файлов"""
        self.greeks = self._load_jsonl(os.path.join(config_dir, 'greeks.jsonl'))
        self.latins = self._load_jsonl(os.path.join(config_dir, 'latins.jsonl'))
        self.symbols = self._load_jsonl(os.path.join(config_dir, 'symbols.jsonl'))
        self.styles_config = self._load_json(os.path.join(config_dir, 'styles.json'))

        # Создаем словари замены
        self.rus_map = {}
        self.eng_map = {}

        for g in self.greeks:
            self.rus_map[g['sym']] = g['rus']
            self.eng_map[g['sym']] = g['eng']

        for s in self.symbols:
            self.rus_map[s['sym']] = s.get('rus_a', s['sym'])
            self.eng_map[s['sym']] = s.get('eng_a', s['sym'])

        self.latin_rus = {l['sym']: l['rus'][0] for l in self.latins}
        self.latin_eng = {l['sym']: l['eng'][0] for l in self.latins}

        self.styles = {}
        for s in self.styles_config.get('styles', []):
            self.styles[s['name']] = s

        print(f"✅ Загружено символов: rus={len(self.rus_map)}, eng={len(self.eng_map)}", flush=True)

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

    def get_gpu_memory(self) -> Optional[int]:
        """Получает текущее использование GPU памяти в MB"""
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
        """Принудительная выгрузка модели из GPU"""
        try:
            session = requests.Session()
            session.post(
                f"{self.ollama_url}/api/generate",
                json={"model": self.model, "keep_alive": 0},
                timeout=5
            )
            session.close()
        except:
            pass

    def check_unknown_symbols(self, latex: str) -> List[str]:
        """Проверяет неизвестные символы"""
        known_symbols = set(self.rus_map.keys()) | set(self.eng_map.keys())
        known_symbols.update([l['sym'] for l in self.latins])
        known_symbols.update([g['sym'] for g in self.greeks])
        known_symbols.update(['\\text', '\\text{rot}', '\\text{div}', '\\frac', '\\Box'])

        commands = re.findall(r'\\([a-zA-Z]+|\W)', latex)
        commands = [f'\\{c}' for c in commands if c]
        single_chars = set(re.findall(r'(?<!\\)([a-zA-Z@])\b', latex))

        unknown = []
        for cmd in commands:
            if cmd not in known_symbols and not cmd.startswith('\\text'):
                unknown.append(cmd)
        for ch in single_chars:
            if ch not in [l['sym'] for l in self.latins]:
                unknown.append(ch)
        return unknown

    def normalize(self, latex: str, lang: str = 'rus') -> str:
        """Нормализация LaTeX в текст"""
        text = latex.strip('$')

        # Обработка \text{rot} и \text{div}
        if '\\text{rot}' in text or '\\text{rot }' in text:
            text = text.replace('\\text{rot}', 'ротор' if lang == 'rus' else 'rotor')
            text = text.replace('\\text{rot }', 'ротор ' if lang == 'rus' else 'rotor ')
        if '\\text{div}' in text or '\\text{div }' in text:
            text = text.replace('\\text{div}', 'дивергенция' if lang == 'rus' else 'divergence')
            text = text.replace('\\text{div }', 'дивергенция ' if lang == 'rus' else 'divergence ')

        text = re.sub(r'\\text\{[^}]*\}', '', text)
        text = text.replace('@', 'эт' if lang == 'rus' else 'at')

        replacements = self.rus_map if lang == 'rus' else self.eng_map
        latin_map = self.latin_rus if lang == 'rus' else self.latin_eng

        for sym, repl in sorted(replacements.items(), key=lambda x: -len(x[0])):
            text = text.replace(sym, repl)

        text = re.sub(r'\\([a-zA-Z]+)', r'\1', text)

        def replace_latin(match):
            letter = match.group(1)
            if letter == '@':
                return 'эт' if lang == 'rus' else 'at'
            return latin_map.get(letter, letter)

        text = re.sub(r'\b([a-zA-Z@])\b', replace_latin, text)
        text = text.replace('{', ' ').replace('}', ' ')
        text = re.sub(r'\s+', ' ', text).strip()
        text = text.replace('( )', '').replace('()', '')

        return text

    def validate_text(self, text: str, language: str) -> bool:
        """Проверяет соответствие языка"""
        if not text or len(text) < 2:
            return False
        if language == 'rus':
            return bool(re.search(r'[а-яА-ЯёЁ]', text)) and not bool(re.search(r'[a-zA-Z]', text))
        else:
            return bool(re.search(r'[a-zA-Z]', text)) and not bool(re.search(r'[а-яА-ЯёЁ]', text))

    def clean_reading(self, text: str, language: str) -> str:
        """Очищает результат от мусора"""
        text = text.strip('"\'')
        prefixes = ["Reading:", "Произношение:", "Ответ:", "Result:", "Output:", "Pronunciation:", "Read:", "Formula:"]
        for prefix in prefixes:
            if text.startswith(prefix):
                text = text[len(prefix):].strip()
        text = text.split('\n')[0]
        return re.sub(r'\s+', ' ', text).strip()

    def stylize_one(self, normalized_text: str, style_name: str, lang: str, max_retries: int = 3) -> str:
        """Стилизация одного текста"""
        time.sleep(self.request_delay)

        style = self.styles.get(style_name, self.styles.get("разговорный"))

        if lang == 'rus':
            rules = style.get('rules_rus', 'Прочитай формулу естественно.')
            example = style.get('example_rus', 'а плюс бэ')
            prompt = f"""Ты помогаешь создать датасет для озвучивания математических формул.

Стиль: {style_name}

Правила стиля:
{rules}

Пример:
Формула: a + b
Произношение: {example}

Твоя задача:
Примени этот стиль к следующей формуле (все символы уже заменены на слова):

Формула: {normalized_text}

Требования:
1. НЕ меняй имена переменных
2. НЕ добавляй пояснений
3. Выведи ТОЛЬКО произношение на русском языке

Произношение:"""
        else:
            rules = style.get('rules_eng', 'Read the formula naturally.')
            example = style.get('example_eng', 'a plus b')
            prompt = f"""You are helping to create a dataset for math formula speech synthesis.

Style: {style_name}

Rules:
{rules}

Example:
Formula: a + b
Reading: {example}

Your task:
Apply this style to the following formula:

Formula: {normalized_text}

Requirements:
1. DO NOT change variable names
2. DO NOT add explanations
3. Output ONLY the reading in English

Reading:"""

        session = requests.Session()
        for attempt in range(max_retries):
            try:
                response = session.post(
                    f"{self.ollama_url}/api/generate",
                    json={
                        "model": self.model,
                        "prompt": prompt,
                        "stream": False,
                        "temperature": 0,
                        "keep_alive": 0,
                        "options": {"num_predict": 100, "num_ctx": 512,
                                   "stop": ["\n\n", "Объяснение", "Пояснение", "Разберем",
                                           "Давайте", "Explanation", "Note:", "Warning:"]}
                    },
                    timeout=30
                )
                if response.status_code == 200:
                    result = response.json().get('response', '').strip()
                    result = self.clean_reading(result, lang)
                    if self.validate_text(result, lang):
                        session.close()
                        return result
            except Exception as e:
                if attempt < max_retries - 1:
                    time.sleep(1)
        session.close()
        return normalized_text

    def process_one_example(self, example: Dict, worker_id: int) -> ProcessedExample:
        """Обрабатывает один пример"""
        start_time = time.time()

        rus_normalized = self.normalize(example['script'], 'rus')
        eng_normalized = self.normalize(example['script'], 'eng')

        if example.get('need_styling') and example.get('style'):
            rus = self.stylize_one(rus_normalized, example['style'], 'rus')
            eng = self.stylize_one(eng_normalized, example['style'], 'eng')
            style_used = example['style']
        else:
            rus = rus_normalized
            eng = eng_normalized
            style_used = "нормализация"

        result = {
            "field": example['field'], "name": example['name'], "type": example['type'],
            "script": example['script'], "idx": example['idx'], "style": style_used,
            "rus": rus, "eng": eng
        }

        duration = time.time() - start_time
        memory = self.get_gpu_memory() or 0

        return ProcessedExample(example=example, result=result, memory_used=memory,
                                worker_id=worker_id, duration=duration)

    def memory_monitor(self, stop_event: threading.Event):
        """Фоновый мониторинг памяти"""
        while not stop_event.is_set():
            mem = self.get_gpu_memory()
            if mem and mem > self.memory_threshold:
                print(f"\n⚠️ Критическая память: {mem} MB, очистка...", flush=True)
                self.unload_model()
                time.sleep(3)
            time.sleep(5)

    def worker_function(self, worker_id: int, stop_event: threading.Event):
        """Рабочий поток"""
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
                        print(f"\n🧹 Батч {self.processed_count} завершен, очистка...", flush=True)
                        self.unload_model()
                        time.sleep(1)

            except queue.Empty:
                continue
            except Exception as e:
                print(f"❌ Worker {worker_id} ошибка: {e}", flush=True)
                with self.lock:
                    self.failed_count += 1

    def process_scripts(self, input_path: str, output_dir: str, num_symbols: int = 20):
        """Главный метод обработки"""
        print(f"\n📚 Загрузка {input_path}...", flush=True)

        with open(input_path, 'r', encoding='utf-8') as f:
            scripts_data = json.load(f)

        scripts_data = scripts_data[:num_symbols]

        # Собираем примеры
        examples = []
        skipped = []

        for entry in scripts_data:
            field = entry.get('field', 'unknown')
            name = entry.get('symbol_name', entry.get('name', 'unknown'))
            for ex_type in ['simple', 'combination', 'outer', 'inner', 'equations']:
                scripts = entry.get(ex_type, [])
                for idx, script in enumerate(scripts):
                    unknown = self.check_unknown_symbols(script)
                    if unknown:
                        skipped.append({'field': field, 'name': name, 'type': ex_type,
                                       'script': script, 'reason': f'unknown: {unknown}'})
                        continue

                    need_styling = ex_type != 'simple'
                    style = random.choice(list(self.styles.keys())) if need_styling else None
                    examples.append({
                        'field': field, 'name': name, 'type': ex_type,
                        'script': script, 'idx': idx, 'style': style,
                        'need_styling': need_styling
                    })

        if skipped:
            os.makedirs(output_dir, exist_ok=True)
            with open(os.path.join(output_dir, 'skipped.json'), 'w') as f:
                json.dump(skipped, f, ensure_ascii=False, indent=2)
            print(f"⚠️ Пропущено: {len(skipped)}", flush=True)

        print(f"📊 Примеров к обработке: {len(examples)}", flush=True)

        # Заполняем очередь
        for ex in examples:
            self.input_queue.put(ex)

        # Стоп-событие
        stop_event = threading.Event()

        # Запускаем монитор памяти
        monitor_thread = threading.Thread(target=self.memory_monitor, args=(stop_event,), daemon=True)
        monitor_thread.start()

        # Запускаем рабочих
        workers = []
        for i in range(self.max_workers):
            worker = threading.Thread(target=self.worker_function, args=(i, stop_event))
            worker.start()
            workers.append(worker)

        # Собираем результаты
        results = []
        start_time = datetime.now()

        for _ in range(len(examples)):
            try:
                processed = self.output_queue.get(timeout=30)
                results.append(processed.result)

                if len(results) % 10 == 0:
                    mem = self.get_gpu_memory()
                    elapsed = (datetime.now() - start_time).total_seconds()
                    speed = len(results) / elapsed
                    print(f"📊 [{len(results)}/{len(examples)}] память: {mem} MB, пик: {self.peak_memory} MB, {speed:.2f} экз/сек", flush=True)

                    # Сохраняем чекпоинт
                    os.makedirs(output_dir, exist_ok=True)
                    with open(os.path.join(output_dir, 'checkpoint.json'), 'w') as f:
                        json.dump([r for r in results], f, ensure_ascii=False, indent=2)

            except queue.Empty:
                print("⚠️ Таймаут ожидания результатов", flush=True)
                break

        # Останавливаем рабочих
        stop_event.set()
        for _ in workers:
            self.input_queue.put(None)
        for worker in workers:
            worker.join(timeout=5)

        # Разделяем на train/test
        groups = {}
        for r in results:
            key = (r['field'], r['name'], r['type'])
            if key not in groups:
                groups[key] = []
            groups[key].append(r)

        train_data = []
        test_data = []
        for group_examples in groups.values():
            group_examples.sort(key=lambda x: x['idx'])
            for idx, ex in enumerate(group_examples):
                if idx < 9:
                    train_data.append(ex)
                else:
                    test_data.append(ex)

        # Сохраняем
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
    parser.add_argument('--input', default='result/scripts.json')
    parser.add_argument('--output-dir', default='result/latex')
    parser.add_argument('--num-symbols', type=int, default=20)
    parser.add_argument('--model', default='qwen2.5:7b')
    parser.add_argument('--max-workers', type=int, default=2, help='Количество потоков (1-3)')
    parser.add_argument('--batch-size', type=int, default=30, help='Очистка памяти каждые N примеров')
    parser.add_argument('--memory-threshold', type=int, default=14000, help='Порог памяти в MB')
    parser.add_argument('--delay', type=float, default=0.3, help='Задержка между запросами')
    args = parser.parse_args()

    generator = HybridGenerator(
        model=args.model,
        max_workers=min(args.max_workers, 3),
        batch_size=args.batch_size,
        memory_threshold=args.memory_threshold,
        request_delay=args.delay
    )
    generator.process_scripts(args.input, args.output_dir, args.num_symbols)

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
