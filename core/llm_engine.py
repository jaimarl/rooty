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

        # 1. Извлекаем историю диалога для понимания контекста
        history_text = ""
        recent_history = self.history[-4:] if len(self.history) >= 4 else self.history
        for msg in recent_history:
            role_name = "User" if msg["role"] == "user" else "Assistant"
            content_snippet = msg["content"][:150] + "..." if len(msg["content"]) > 150 else msg["content"]
            history_text += f"[{role_name}]: {content_snippet}\n"

        if not history_text:
            history_text = "(Диалог только начался)"

        # 2. Формируем умный промпт с учетом памяти
        prompt = f"""Анализируй входящий запрос пользователя по двум критериям, ОБЯЗАТЕЛЬНО УЧИТЫВАЯ КОНТЕКСТ ДИАЛОГА.
        Если текущий запрос короткий, но опирается на сложный контекст (например, "напиши еще один пример", "объясни подробнее"), сложность должна быть 'complex'.

        КОНТЕКСТ ДИАЛОГА:
        {history_text}

        1. СЛОЖНОСТЬ ЗАПРОСА:
        - "simple": на запрос можно ответить коротко (1–3 предложения), без написания кода, длинных списков или вычислений (например: приветствие, дата, короткий факт).
        - "complex": запрос требует развернутого ответа, написания кода, пошаговых инструкций, глубокого анализа или размышлений.

        2. КАТЕГОРИЯ ЗАПРОСА:
        Выбери строго одну категорию, которая лучше всего подходит, из этого списка: {keys_str}.

        ФОРМАТ ОТВЕТА:
        Выведи ровно два слова через один пробел: [сложность] [категория]. 
        Никаких дополнительных пояснений, вводных слов или кавычек.

        Запрос пользователя: {user_prompt}"""

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




    def generate_fast_response(self, user_prompt: str, system_prompt: str, stream: bool = True):
        """
        Генерация текста с помощью микро-модели (роутера). 
        Она всегда загружена в RAM, поэтому отвечает мгновенно.
        """
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        # Если нужен мгновенный целый ответ (для оверлея)
        if not stream:
            response = self.router_llm.create_chat_completion(
                messages, max_tokens=100, temperature=0.7
            )
            return response["choices"][0]["message"]["content"].strip()
            
        # Если нужен стриминг (для ответов в консоль)
        response = self.router_llm.create_chat_completion(
            messages, stream=True, max_tokens=300, temperature=0.7
        )
        for chunk in response:
            if "content" in chunk["choices"][0]["delta"]:
                yield chunk["choices"][0]["delta"]["content"]

    def generate_stream(self, user_prompt: str, long_term_context: str = "", task_type: str = "chat"):
        self.switch_model(task_type)
        
        dynamic_system_prompt = config.PERSONAS[self.current_persona]
        
        task_instructions = config.ROUTING_RULES[task_type].get("system_injection", "")
        if task_instructions:
            dynamic_system_prompt += f"\n\nIMPORTANT RULE FOR THIS REQUEST: {task_instructions}"
        
        if long_term_context:
            dynamic_system_prompt += f"\n\nConsider the context of previous conversations:\n{long_term_context}"

        messages = [{"role": "system", "content": dynamic_system_prompt}]
        messages.extend(self.history)
        messages.append({"role": "user", "content": user_prompt})

        response_generator = self.llm.create_chat_completion(
            messages=messages,
            max_tokens=config.MAX_TOKENS,
            temperature=config.TEMPERATURE,
            top_p=config.TOP_P,
            repeat_penalty=config.REPEAT_PENALTY,
            stream=True 
        )

        full_assistant_response = ""
        
        try:
            for chunk in response_generator:
                delta = chunk["choices"][0]["delta"]
                if "content" in delta:
                    token = delta["content"]
                    full_assistant_response += token 
                    yield token
        finally:
            if full_assistant_response.strip():
                self.history.append({"role": "user", "content": user_prompt})
                self.history.append({"role": "assistant", "content": full_assistant_response})

                if len(self.history) > config.MAX_HISTORY_MESSAGES:
                    self.history = self.history[-config.MAX_HISTORY_MESSAGES:]
