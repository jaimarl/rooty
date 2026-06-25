import json
import os
import gc
import sys
import getpass
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
            # ОПТИМИЗАЦИЯ 1: Переносим роутер на GPU и ускоряем чтение
            self.router_llm = Llama(
                model_path=config.ROUTER_MODEL_PATH,
                n_ctx=2048,
                n_threads=8,          # Увеличено для многопоточности
                n_gpu_layers=-1,      # Установлено -1 вместо 0 (оффлоад на видеокарту)
                n_batch=512,         # Позволяет нейросети прочитать весь промпт за один такт
                verbose=False
            )
            print("[SYSTEM] Neuro-router successfully loaded into VRAM.")
        except Exception as e:
            print(f"[ERROR] Router initialization failure: {e}")
            sys.exit(1)

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
        if self.current_model_key == model_key and self.llm is not None:
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
                n_threads=8, 
                n_gpu_layers=-1, 
                n_batch=256,
                verbose=False   
            )
            self.current_model_key = model_key
            print(f"[SYSTEM] Рабочая модель '{model_key}' успешно загружена.")
        except Exception as e:
            print(f"[ERROR] Ошибка переключения модели: {e}")

    def unload_heavy_model(self):
        """Принудительно выгружает тяжелую модель из памяти для освобождения VRAM."""
        if getattr(self, 'llm', None) is not None:
            if hasattr(self.llm, 'close'):
                self.llm.close()
            del self.llm
            self.llm = None
            self.current_model_key = None
            gc.collect()
            print("\033[90m[ SYSTEM ] Тяжелая модель выгружена (VRAM очищена).\033[0m")

    def clear_history(self):
        self.history = []

    def get_history(self):
        return self.history

    def analyze_prompt(self, user_prompt: str) -> tuple[bool, str]:
        valid_keys = list(config.ROUTING_RULES.keys())
        keys_str = ", ".join(valid_keys)

        history_text = ""
        recent_history = self.history[-4:] if len(self.history) >= 4 else self.history
        for msg in recent_history:
            role_name = getpass.getuser() if msg["role"] == "user" else "Ассистент"
            content_snippet = msg["content"][:200] + "..." if len(msg["content"]) > 200 else msg["content"]
            history_text += f"[{role_name}]: {content_snippet}\n"

        if not history_text:
            history_text = "(Диалог только начался)"

        prompt = config.ROUTER_USER_PROMPT_TEMPLATE.format(
            history_text=history_text,
            user_prompt=user_prompt,
            keys_str=keys_str
        )

        messages = [
            {"role": "system", "content": config.ROUTER_SYSTEM_PROMPT},
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
        """Синхронная генерация. Возвращает готовую строку для уникальных уведомлений в оверлее."""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        response = self.router_llm.create_chat_completion(
            messages, max_tokens=150, temperature=0.8, stream=False
        )
        return response["choices"][0]["message"]["content"].strip()
            
    def stream_fast_response(self, user_prompt: str, system_prompt: str):
        """Асинхронная (потоковая) генерация с yield. Для вывода быстрых ответов в консоль."""
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
        """Потоковая генерация развернутого ответа тяжелой моделью."""
        if self.llm is None or task_type != getattr(self, 'current_model_key', ''):
            self.switch_model(task_type)

        persona_prompt = config.PERSONAS.get(self.current_persona, config.PERSONAS.get(config.DEFAULT_PERSONA, ""))
        
        system_content = f"{persona_prompt}\n\nИНСТРУКЦИЯ: Твоего собеседника зовут {getpass.getuser()}. Он ожидает развернутый, подробный ответ. Пиши код, пошаговые инструкции или глубокий анализ, если это необходимо."
        
        if long_term_context:
            system_content += f"\n\nВОСПОМИНАНИЯ ИЗ БАЗЫ ДАННЫХ:\n{long_term_context}"

        messages = [{"role": "system", "content": system_content}]
        messages.extend(self.history)
        messages.append({"role": "user", "content": user_prompt})

        try:
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
            if 'full_assistant_response' in locals() and full_assistant_response.strip():
                self.history.append({"role": "user", "content": user_prompt})
                self.history.append({"role": "assistant", "content": full_assistant_response})
                
                max_hist = getattr(config, 'MAX_HISTORY_MESSAGES', 10)
                if len(self.history) > max_hist:
                    self.history = self.history[-max_hist:]
