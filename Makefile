# Makefile для загрузки модели в Ollama

# Пути
GGUF_DIR ?= ./models/bhl_gguf
MODEL_NAME ?= qwen_bhl
GGUF_FILE ?= $(GGUF_DIR)/qwen_bhl_q8_0.gguf

# Ollama команды
OLLAMA ?= ollama

# Цвета
GREEN = \033[0;32m
RED = \033[0;31m
YELLOW = \033[1;33m
NC = \033[0m

.PHONY: help create-modelfile import test list clean check merge quantize

help:
	@echo "========================================="
	@echo "Ollama Model Management"
	@echo "========================================="
	@echo "make merge             - Объединить LoRA с базовой моделью"
	@echo "make quantize          - Квантовать модель в GGUF"
	@echo "make create-modelfile  - Создать Modelfile"
	@echo "make import            - Импортировать модель в Ollama"
	@echo "make test              - Протестировать модель"
	@echo "make list              - Показать модели в Ollama"
	@echo "make clean             - Удалить модель из Ollama"
	@echo "make check             - Проверить статус"
	@echo "========================================="

# Проверка наличия Ollama
check-ollama:
	@$(OLLAMA) --version > /dev/null 2>&1 || { \
		echo "$(RED)❌ Ollama не найден!$(NC)"; \
		echo "Установите: https://ollama.ai/download"; \
		exit 1; \
	}
	@echo "$(GREEN)✅ Ollama найден: $($(OLLAMA) --version)$(NC)"

# Проверка наличия GGUF файла
check-gguf:
	@if [ ! -f "$(GGUF_FILE)" ]; then \
		echo "$(RED)❌ GGUF файл не найден: $(GGUF_FILE)$(NC)"; \
		echo "Доступные файлы:"; \
		ls -lh $(GGUF_DIR)/*.gguf 2>/dev/null || echo "   Нет GGUF файлов"; \
		exit 1; \
	fi
	@echo "$(GREEN)✅ GGUF файл найден: $(GGUF_FILE)$(NC)"

# Создание Modelfile
create-modelfile: check-ollama check-gguf
	@echo "$(GREEN)📝 Создание Modelfile...$(NC)"
	@echo "FROM $(GGUF_FILE)" > Modelfile
	@echo "" >> Modelfile
	@echo "PARAMETER temperature 0.3" >> Modelfile
	@echo "PARAMETER top_p 0.9" >> Modelfile
	@echo "PARAMETER top_k 40" >> Modelfile
	@echo "" >> Modelfile
	@printf 'SYSTEM "'
	@cat docs/bhl_prompt.txt | sed 's/"/\\"/g' | tr '\n' ' ' >> Modelfile
	@echo '"\n' >> Modelfile
	@echo "" >> Modelfile
	@echo 'TEMPLATE """{{- if .System }}system' >> Modelfile
	@echo '{{ .System }}' >> Modelfile
	@echo '' >> Modelfile
	@echo '{{- end }}{{- if .Prompt }}<|im_start|>user' >> Modelfile
	@echo '{{ .Prompt }}' >> Modelfile
	@echo '' >> Modelfile
	@echo '{{- end }}<|im_start|>assistant' >> Modelfile
	@echo '"""' >> Modelfile
	@echo "$(GREEN)✅ Создан Modelfile$(NC)"
	@cat Modelfile

# Импорт модели в Ollama
import: create-modelfile
	@echo "$(GREEN)📦 Импорт модели в Ollama...$(NC)"
	@$(OLLAMA) create $(MODEL_NAME) -f Modelfile
	@echo "$(GREEN)✅ Модель '$(MODEL_NAME)' импортирована!$(NC)"
	@echo "   Запуск: $(OLLAMA) run $(MODEL_NAME) 'твой запрос'"

# Тестирование модели
test:
	@echo "$(GREEN)🧪 Тестирование модели...$(NC)"
	@echo "-------------------------------------------"
	@echo "Тест 1: 'добавь новый абзац'"
	@$(OLLAMA) run $(MODEL_NAME) "добавь новый абзац" || true
	@echo ""
	@echo "Тест 2: 'доброе утро' (garbage)"
	@$(OLLAMA) run $(MODEL_NAME) "доброе утро" || true
	@echo ""
	@echo "Тест 3: 'удали этот текст'"
	@$(OLLAMA) run $(MODEL_NAME) "удали этот текст" || true
	@echo "-------------------------------------------"

# Список моделей
list: check-ollama
	@echo "$(GREEN)📋 Модели в Ollama:$(NC)"
	@$(OLLAMA) list | grep $(MODEL_NAME) || echo "   Модель '$(MODEL_NAME)' не найдена"

# Удаление модели
clean: check-ollama
	@echo "$(YELLOW)🗑️  Удаление модели $(MODEL_NAME)...$(NC)"
	@$(OLLAMA) rm $(MODEL_NAME) 2>/dev/null || echo "   Модель не найдена"
	@rm -f Modelfile
	@echo "$(GREEN)✅ Очистка завершена$(NC)"

# Объединение LoRA с базовой моделью
merge:
	@echo "$(GREEN)🔗 Объединение LoRA с базовой моделью...$(NC)"
	python3 merge_lora.py \
		--base-model "../bhl/Models/Qwen2.5-1.5B-Instruct/orig" \
		--lora "./saves/qwen_bhl_lora" \
		--output "./models/qwen_bhl"

# Квантование модели в GGUF
quantize:
	@echo "$(GREEN)📦 Квантование модели в GGUF...$(NC)"
	python3 quantize_model.py     \
		--model "./models/qwen_bhl" \
		--output "$(GGUF_DIR)" \
		--type "q4_0,q8_0" \
		--llama-path "./llama.cpp"

# Проверка статуса
check: check-ollama
	@echo "========================================="
	@echo "Статус:"
	@echo "========================================="
	@echo "GGUF файл: $(GGUF_FILE)"
	@if [ -f "$(GGUF_FILE)" ]; then \
		echo "$(GREEN)✅ Существует$(NC)"; \
		ls -lh $(GGUF_FILE); \
	else \
		echo "$(RED)❌ Не найден$(NC)"; \
	fi
	@echo ""
	@echo "Модель в Ollama: $(MODEL_NAME)"
	@if $(OLLAMA) list | grep -q $(MODEL_NAME); then \
		echo "$(GREEN)✅ Имортирована$(NC)"; \
	else \
		echo "$(RED)❌ Не импортирована$(NC)"; \
	fi
	@echo "========================================="
