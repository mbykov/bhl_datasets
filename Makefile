# Makefile для управления процессом экспорта модели

# Пути
BASE_MODEL ?= ../bhl/Models/Qwen2.5-1.5B-Instruct
LORA_PATH ?= ./saves/qwen_merged_lora
MERGED_PATH ?= ./models/qwen_merged
GGUF_DIR ?= ./models/gguf
LLAMA_PATH ?= ./llama.cpp

# Типы квантования
QUANT_TYPES ?= q4_0 q8_0

# Python (используем uv run)
PYTHON = uv run python

# Файл-флаг для проверки сборки (создаем в текущей директории)
LLAMA_BUILT_FLAG = .llama_built

# Цвета
GREEN = \033[0;32m
RED = \033[0;31m
YELLOW = \033[1;33m
NC = \033[0m

.PHONY: help merge quantize test clean all setup-llama check-llama

help:
	@echo "========================================="
	@echo "Управление экспортом модели"
	@echo "========================================="
	@echo "make merge        - Объединить LoRA с базовой моделью"
	@echo "make quantize     - Квантовать модель в GGUF"
	@echo "make test         - Тестировать GGUF модель"
	@echo "make all          - Выполнить все шаги"
	@echo "make clean        - Очистить временные файлы"
	@echo "make setup-llama  - Скачать и собрать llama.cpp (принудительно)"
	@echo "make rebuild-llama - Принудительная пересборка llama.cpp"
	@echo "make clean-all    - Полная очистка"
	@echo "========================================="

# Проверка, собран ли llama.cpp
check-llama:
	@if [ ! -f "$(LLAMA_BUILT_FLAG)" ]; then \
		echo "$(YELLOW)⚠️  llama.cpp не собран. Запускаю сборку...$(NC)"; \
		$(MAKE) setup-llama; \
	else \
		echo "$(GREEN)✅ llama.cpp уже собран$(NC)"; \
	fi

# Сборка llama.cpp (только если нужно)
setup-llama:
	@echo "$(GREEN)🔧 Установка llama.cpp...$(NC)"
	@if [ ! -d "$(LLAMA_PATH)" ]; then \
		echo "   Клонирование репозитория..."; \
		git clone https://github.com/ggml-org/llama.cpp.git $(LLAMA_PATH); \
	fi
	@echo "   Сборка проекта..."
	@cd $(LLAMA_PATH) && \
		cmake -B build -DCMAKE_BUILD_TYPE=Release && \
		cmake --build build --config Release -j 4
	@if [ -d "$(LLAMA_PATH)/build/bin" ]; then \
		echo "   ✅ Сборка завершена"; \
		touch $(LLAMA_BUILT_FLAG); \
		echo "   Создан флаг: $(LLAMA_BUILT_FLAG)"; \
	else \
		echo "   ❌ Ошибка: не найдена папка build/bin"; \
		exit 1; \
	fi
	@echo "$(GREEN)✅ llama.cpp готов$(NC)"

# Объединение LoRA (без лишних зависимостей)
merge:
	@echo "$(GREEN)🔧 Объединение LoRA...$(NC)"
	@mkdir -p $(dir $(MERGED_PATH))
	@$(PYTHON) merge_lora.py \
		--base-model $(BASE_MODEL) \
		--lora $(LORA_PATH) \
		--output $(MERGED_PATH)
	@echo "$(GREEN)✅ Объединение завершено$(NC)"

# Квантование (проверяет сборку, но не пересобирает без необходимости)
quantize: check-llama
	@echo "$(GREEN)🔧 Квантование модели...$(NC)"
	@mkdir -p $(GGUF_DIR)
	@for type in $(QUANT_TYPES); do \
		echo "  Обработка $$type..."; \
		$(PYTHON) quantize_model.py \
			--model $(MERGED_PATH) \
			--output $(GGUF_DIR) \
			--type $$type \
			--llama-path $(LLAMA_PATH); \
	done
	@echo "$(GREEN)✅ Квантование завершено$(NC)"

# Тестирование
# test:
# 	@echo "$(GREEN)🔧 Тестирование GGUF модели...$(NC)"
# 	@for file in $(GGUF_DIR)/*.gguf; do \
# 		if [ -f "$$file" ]; then \
# 			echo "  Тестирование $$file"; \
# 			$(PYTHON) test_gguf.py --model "$$file" || true; \
# 		fi \
# 	done
# 	@echo "$(GREEN)✅ Тестирование завершено$(NC)"

test:
	@echo "$(GREEN)🔧 Тестирование GGUF модели...$(NC)"
	@for file in $(GGUF_DIR)/*.gguf; do \
		if [ -f "$$file" ]; then \
			echo "  Тестирование $$file"; \
			$(PYTHON) test_gguf.py --model "$$file" --llama-path $(LLAMA_PATH) || true; \
		fi \
	done
	@echo "$(GREEN)✅ Тестирование завершено$(NC)"



# Очистка только моделей
clean:
	@echo "$(YELLOW)🧹 Очистка моделей...$(NC)"
	@rm -rf $(MERGED_PATH)
	@rm -rf $(GGUF_DIR)
	@rm -f $(LLAMA_BUILT_FLAG)
	@echo "$(GREEN)✅ Очистка завершена$(NC)"

# Полная очистка включая llama.cpp
clean-all: clean
	@echo "$(YELLOW)🧹 Полная очистка (включая llama.cpp)...$(NC)"
	@rm -rf $(LLAMA_PATH)
	@echo "$(GREEN)✅ Полная очистка завершена$(NC)"

# Полный цикл
all: merge quantize test
	@echo "$(GREEN)🎉 Все шаги выполнены успешно!$(NC)"

# Быстрые варианты
merge-q4: merge
	@$(MAKE) quantize QUANT_TYPES="q4_0"

merge-q8: merge
	@$(MAKE) quantize QUANT_TYPES="q8_0"

merge-all: merge
	@$(MAKE) quantize QUANT_TYPES="q4_0 q4_1 q5_0 q5_1 q8_0 f16"

# Принудительная пересборка llama.cpp
rebuild-llama:
	@echo "$(YELLOW)🔧 Принудительная пересборка llama.cpp...$(NC)"
	@rm -f $(LLAMA_BUILT_FLAG)
	@rm -rf $(LLAMA_PATH)/build
	@$(MAKE) setup-llama

# Показать статус сборки
status:
	@if [ -f "$(LLAMA_BUILT_FLAG)" ]; then \
		echo "$(GREEN)✅ llama.cpp собран$(NC)"; \
	else \
		echo "$(RED)❌ llama.cpp не собран$(NC)"; \
	fi
	@if [ -d "$(MERGED_PATH)" ]; then \
		echo "$(GREEN)✅ Объединенная модель существует$(NC)"; \
	else \
		echo "$(RED)❌ Объединенная модель не найдена$(NC)"; \
	fi
	@if [ -d "$(GGUF_DIR)" ]; then \
		echo "$(GREEN)✅ GGUF файлы: $(shell ls $(GGUF_DIR)/*.gguf 2>/dev/null | wc -l) штук$(NC)"; \
	else \
		echo "$(RED)❌ GGUF файлы не найдены$(NC)"; \
	fi
