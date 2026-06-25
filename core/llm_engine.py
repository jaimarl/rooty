import json
import os
import gc
import sys
from llama_cpp import Llama
from core import config

class LocalLLMEngine:
    def __init__(self):
        self.llm = None
        self.current_model_key = None
        self.history = [] 
        self.current_persona = self._load_saved_persona()

        print(f"[SYSTEM] Initializing neuro-router ({config.ROUTER_MODEL_NAME})...")
        if not os.path.exists(config.ROUTER_MODEL_PATH):
            print(f"[ERROR] Router model not found at: {config.ROUTER_MODEL_PATH}")
            sys.exit(1)
        try:
            self.router_llm = Llama(
                model_path=config.ROUTER_MODEL_PATH,
                n_ctx=2048,
                n_threads=4,
                n_gpu_layers=0,
                n_batch=128,
                verbose=False
            )
            print("[SYSTEM] Neuro-router successfully loaded into RAM.")
        except Exception as e:
            print(f"[ERROR] Router initialization failure: {e}")
            sys.exit(1)
        
        self.switch_model("chat")

    def _load_saved_persona(self) -> str:
        if not os.path.exists(config.SETTINGS_PATH):
            try:
                os.makedirs(os.path.dirname(config.SETTINGS_PATH), exist_ok=True)
                
                with open(config.SETTINGS_PATH, 'w', encoding='utf-8') as f:
                    json.dump({"current_persona": config.DEFAULT_PERSONA}, f, indent=4)
                print("[SYSTEM] Created settings.json")
            except Exception as e:
                print(f"[WARNING] Failed to create configuration file: {e}")
            return config.DEFAULT_PERSONA

        try:
            with open(config.SETTINGS_PATH, 'r', encoding='utf-8') as f:
                settings = json.load(f)
                saved_persona = settings.get("current_persona")
                if saved_persona in config.PERSONAS:
                    return saved_persona
        except Exception as e:
            print(f"[WARNING] Error reading settings file: {e}")
                
        return config.DEFAULT_PERSONA

    def set_persona(self, persona_name: str) -> bool:
        if persona_name in config.PERSONAS:
            self.current_persona = persona_name
            
            try:
                with open(config.SETTINGS_PATH, 'w', encoding='utf-8') as f:
                    json.dump({"current_persona": persona_name}, f, indent=4)
            except Exception as e:
                print(f"[WARNING] Failed to save settings: {e}")

            return True
        return False

    def switch_model(self, model_key: str):
        """Динамически переключает рабочую модель на GPU."""
        if self.current_model_key == model_key:
            return 
            
        model_filename = config.MODELS.get(model_key, config.MODELS.get("chat"))
        model_path = os.path.join(config.MODELS_DIR, model_filename)
        
        if not os.path.exists(model_path):
            print(f"[WARNING] Модель '{model_filename}' не найдена. Остаемся на базовой.")
            return

        print(f"\n[SYSTEM] Смена контекста. Загрузка рабочей модели '{model_key}' ({model_filename})...")
        
        # Жесткая очистка видеопамяти
        if self.llm is not None:
            if hasattr(self.llm, 'close'):
                self.llm.close()
            del self.llm 
            self.llm = None
            gc.collect()
            
        try:
            self.llm = Llama(
                model_path=model_path,
                n_ctx=config.CONTEXT_SIZE,
                n_threads=4, 
                n_gpu_layers=-1, 
                n_batch=128,
                verbose=False   
            )
            self.current_model_key = model_key
            print(f"[SYSTEM] Рабочая модель '{model_key}' успешно загружена.")
        except Exception as e:
            print(f"[ERROR] Ошибка переключения модели: {e}")

    def switch_model(self, model_key: str):
        if self.current_model_key == model_key:
            return 
            
        model_filename = config.MODELS.get(model_key, config.MODELS.get("chat"))
        model_path = os.path.join(config.MODELS_DIR, model_filename)
        
        if not os.path.exists(model_path):
            print(f"[WARNING] Model '{model_filename}' not found")
            return

        print(f"\n[SYSTEM] Context switch. Loading model '{model_key}' ({model_filename})...")
        
        if self.llm is not None:
            if hasattr(self.llm, 'close'):
                self.llm.close()
            del self.llm 
            self.llm = None
            gc.collect()
            
        try:
            self.llm = Llama(
                model_path=model_path,
                n_ctx=config.CONTEXT_SIZE,
                n_threads=4, 
                n_gpu_layers=-1, 
                n_batch=128,
                verbose=False   
            )
            self.current_model_key = model_key
            print(f"[SYSTEM] Model '{model_key}' loaded successfully")
        except Exception as e:
            print(f"[ERROR] Model switching error: {e}")

    def clear_history(self):
        self.history = []

    def get_history(self):
        return self.history

    def analyze_prompt(self, user_prompt: str) -> tuple[bool, str]:
        """
        Умный роутер. Определяет сложность и категорию с учетом истории диалога.
        """
        if self.llm is None:
            self.switch_model(config.DEFAULT_TASK_TYPE)

        valid_keys = list(config.ROUTING_RULES.keys())
        keys_str = ", ".join(valid_keys)

        history_text = ""
        recent_history = self.history[-4:] if len(self.history) >= 4 else self.history
        for msg in recent_history:
            role_name = "jaimarl" if msg["role"] == "user" else "Ассистент"
            content_snippet = msg["content"][:200] + "..." if len(msg["content"]) > 200 else msg["content"]
            history_text += f"[{role_name}]: {content_snippet}\n"

        if not history_text:
            history_text = "(Диалог только начался)"

        prompt = f"""Проанализируй последний запрос пользователя с учетом ИСТОРИИ ДИАЛОГА.

        ИСТОРИЯ ДИАЛОГА:
        {history_text}

        ПОСЛЕДНИЙ ЗАПРОС: "{user_prompt}"

        Твоя задача:
        1. Понять смысл. Если последний запрос короткий (например, "еще пример", "объясни", "перепиши"), он относится к предыдущему ответу Ассистента.
        2. Оценить СЛОЖНОСТЬ:
        - "simple": запрос требует ответа в 1-3 предложения (приветствие, факт, простой вопрос).
        - "complex": пользователю нужен длинный ответ, код, решение задачи или подробный анализ (ДАЖЕ ЕСЛИ сам запрос состоит из двух слов, но по контексту подразумевает сложную работу).
        3. Выбрать КАТЕГОРИЮ из списка: {keys_str}.

        ФОРМАТ ОТВЕТА:
        Выведи строго два слова через пробел: [сложность] [категория]. Никаких других символов."""

        messages = [
            {"role": "system", "content": "Ты строгий классификатор. Отвечай только двумя словами."},
            {"role": "user", "content": prompt}
        ]

        try:
            response = self.router_llm.create_chat_completion(
                messages=messages,
                max_tokens=10,       
                temperature=0.0,    
                stream=False
            )
            
            result = response["choices"][0]["message"]["content"].strip().lower()
            
            is_complex = "complex" in result
            
            task_type = config.DEFAULT_TASK_TYPE
            for key in valid_keys:
                if key in result:
                    task_type = key
                    break
                    
            return is_complex, task_type
            
        except Exception as e:
            print(f"[ERROR] Ошибка роутера: {e}")
            return True, config.DEFAULT_TASK_TYPE

    def generate_fast_response(self, user_prompt: str, system_prompt: str) -> str:
        """
        Синхронная генерация. Возвращает готовую строку для уникальных уведомлений в оверлее.
        """
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        response = self.router_llm.create_chat_completion(
            messages, max_tokens=150, temperature=0.8, stream=False
        )
        return response["choices"][0]["message"]["content"].strip()
            
    def stream_fast_response(self, user_prompt: str, system_prompt: str):
        """
        Асинхронная (потоковая) генерация с yield. Для вывода быстрых ответов в консоль.
        """
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        response = self.router_llm.create_chat_completion(
            messages, stream=True, max_tokens=300, temperature=0.7
        )
        for chunk in response:
            if "content" in chunk["choices"][0]["delta"]:
                yield chunk["choices"][0]["delta"]["content"]

    def generate_stream(self, user_prompt: str, long_term_context: str = None, task_type: str = "chat"):
        """
        Потоковая генерация развернутого ответа тяжелой моделью.
        Учитывает характер персонажа, историю диалога и базу воспоминаний.
        """
        # 1. Загружаем нужную модель (например, code или chat)
        if self.llm is None or task_type != getattr(self, 'current_model_key', ''):
            self.switch_model(task_type)

        # 2. Извлекаем описание текущего персонажа из конфига
        persona_prompt = config.PERSONAS.get(self.current_persona, config.PERSONAS.get(config.DEFAULT_PERSONA, ""))
        
        # Инструкция + системное имя пользователя
        system_content = f"{persona_prompt}\n\nИНСТРУКЦИЯ: Твоего собеседника зовут jaimarl. Он ожидает развернутый, подробный ответ. Пиши код, пошаговые инструкции или глубокий анализ, если это необходимо."
        
        # 3. Подмешиваем долгосрочную память (RAG), если она найдена
        if long_term_context:
            system_content += f"\n\nВОСПОМИНАНИЯ ИЗ БАЗЫ ДАННЫХ:\n{long_term_context}"

        # 4. Формируем массив сообщений (Система -> История -> Текущий запрос)
        messages = [{"role": "system", "content": system_content}]
        messages.extend(self.history)
        messages.append({"role": "user", "content": user_prompt})

        try:
            # Запускаем генерацию с увеличенным max_tokens для длинных ответов
            response = self.llm.create_chat_completion(
                messages=messages,
                stream=True,
                max_tokens=2048, 
                temperature=0.7
            )
            
            full_assistant_response = ""
            for chunk in response:
                if "content" in chunk["choices"][0]["delta"]:
                    content = chunk["choices"][0]["delta"]["content"]
                    full_assistant_response += content
                    yield content
                    
        finally:
            # 5. Сохраняем результат в оперативную память для Роутера
            if 'full_assistant_response' in locals() and full_assistant_response.strip():
                self.history.append({"role": "user", "content": user_prompt})
                self.history.append({"role": "assistant", "content": full_assistant_response})
                
                # Защита от переполнения контекстного окна
                max_hist = getattr(config, 'MAX_HISTORY_MESSAGES', 10)
                if len(self.history) > max_hist:
                    self.history = self.history[-max_hist:]
