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
        self.current_role = self._load_saved_role()

        print(f"[SYSTEM] Инициализация нейро-роутера ({config.ROUTER_MODEL_NAME})...")
        if not os.path.exists(config.ROUTER_MODEL_PATH):
            print(f"[ERROR] Модель роутера не найдена: {config.ROUTER_MODEL_PATH}")
            sys.exit(1)
            
        try:
            self.router_llm = Llama(
                model_path=config.ROUTER_MODEL_PATH,
                verbose=False,
                **config.LLM_INIT_PARAMS.get("router", {})
            )
            print("[SYSTEM] Нейро-роутер загружен в VRAM.")
        except Exception as e:
            print(f"[ERROR] Ошибка инициализации роутера: {e}")
            sys.exit(1)

    def _load_saved_role(self) -> str:
        if not os.path.exists(config.SETTINGS_PATH):
            os.makedirs(os.path.dirname(config.SETTINGS_PATH), exist_ok=True)
            self._save_role(config.DEFAULT_ROLE)
            return config.DEFAULT_ROLE

        try:
            with open(config.SETTINGS_PATH, 'r', encoding='utf-8') as f:
                settings = json.load(f)
                # Поддержка старого ключа current_persona для миграции
                saved_role = settings.get("current_role", settings.get("current_persona"))
                if saved_role in config.ROLES:
                    return saved_role
        except Exception:
            pass
        return config.DEFAULT_ROLE

    def _save_role(self, role_name: str):
        try:
            with open(config.SETTINGS_PATH, 'w', encoding='utf-8') as f:
                json.dump({"current_role": role_name}, f, indent=4)
        except Exception as e:
            print(f"[WARNING] Ошибка сохранения настроек: {e}")

    def set_role(self, role_name: str) -> bool:
        if role_name in config.ROLES:
            self.current_role = role_name
            self._save_role(role_name)
            return True
        return False

    def switch_model(self, model_key: str):
        """Динамически переключает рабочую модель на GPU."""
        if self.current_model_key == model_key and self.llm is not None:
            return 
            
        model_filename = config.MODELS.get(model_key, config.MODELS.get(config.DEFAULT_TASK_TYPE))
        model_path = os.path.join(config.MODELS_DIR, model_filename)
        
        if not os.path.exists(model_path):
            print(f"[WARNING] Модель '{model_filename}' не найдена.")
            return
            
        self.unload_heavy_model()
        print(f"\n[SYSTEM] Загрузка модели '{model_key}' ({model_filename})...")
            
        try:
            init_params = config.LLM_INIT_PARAMS.get(model_key, config.LLM_INIT_PARAMS.get("default", {}))
            self.llm = Llama(
                model_path=model_path,
                verbose=False,
                **init_params
            )
            self.current_model_key = model_key
            print(f"[SYSTEM] Рабочая модель '{model_key}' успешно загружена.")
        except Exception as e:
            print(f"[ERROR] Ошибка переключения модели: {e}")

    def unload_heavy_model(self):
        """Принудительно выгружает тяжелую модель для освобождения VRAM."""
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
        """Умный роутер. Определяет сложность и категорию с учетом диалога."""
        valid_keys = list(config.ROUTING_RULES.keys())
        
        history_text = "(Диалог только начался)"
        recent_history = self.history[-4:]
        if recent_history:
            history_text = "\n".join([f"[{getpass.getuser() if msg['role'] == 'user' else 'Ассистент'}]: {msg['content'][:200]}" for msg in recent_history])

        # Динамическая сборка системного промпта
        full_prompt = f"{config.ROUTER_PROMPT}\n\nДОСТУПНЫЕ КАТЕГОРИИ:\n{', '.join(valid_keys)}\n\nИСТОРИЯ ДИАЛОГА:\n{history_text}\n\nПОСЛЕДНИЙ ЗАПРОС: {user_prompt}"

        messages = [
            {"role": "system", "content": "Ты классификатор. Отвечай только двумя словами."},
            {"role": "user", "content": full_prompt}
        ]

        try:
            response = self.router_llm.create_chat_completion(
                messages=messages, stream=False, **config.LLM_GEN_PARAMS.get("router", {})
            )
            result = response["choices"][0]["message"]["content"].strip().lower()
            
            is_complex = "complex" in result
            task_type = config.DEFAULT_TASK_TYPE
            
            for key in valid_keys:
                if key in result:
                    task_type = key
                    break
                    
            return is_complex, task_type
        except Exception:
            return True, config.DEFAULT_TASK_TYPE

    def _get_system_block(self, instruction: str, user_prompt: str = "", context: str = "") -> str:
        """Утилита для сборки системного промпта с учетом роли."""
        role_prompt = config.ROLES.get(self.current_role, config.ROLES[config.DEFAULT_ROLE])
        block = f"{role_prompt}\n\nИНСТРУКЦИЯ: {instruction}"
        if user_prompt:
            block += f"\n\nТЕКУЩИЙ ЗАПРОС ПОЛЬЗОВАТЕЛЯ: {user_prompt}"
        if context:
            block += f"\n\nВОСПОМИНАНИЯ ИЗ БАЗЫ:\n{context}"
        return block

    def generate_fast_response(self, user_prompt: str, instruction: str) -> str:
        """Синхронная генерация (уведомления)."""
        sys_prompt = self._get_system_block(instruction, user_prompt=user_prompt)
        messages = [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": "Сгенерируй уведомление."}
        ]
        response = self.router_llm.create_chat_completion(
            messages, stream=False, **config.LLM_GEN_PARAMS.get("fast_agent", {})
        )
        return response["choices"][0]["message"]["content"].strip()
            
    def stream_fast_response(self, user_prompt: str, instruction: str, db_context: str = ""):
        """Асинхронная потоковая генерация (простые ответы)."""
        sys_prompt = self._get_system_block(instruction, context=db_context)
        messages = [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": user_prompt}
        ]
        response = self.router_llm.create_chat_completion(
            messages, stream=True, **config.LLM_GEN_PARAMS.get("fast_agent", {})
        )
        for chunk in response:
            if "content" in chunk["choices"][0]["delta"]:
                yield chunk["choices"][0]["delta"]["content"]

    def generate_stream(self, user_prompt: str, long_term_context: str = None, task_type: str = "default"):
        """Потоковая генерация развернутого ответа тяжелой моделью."""
        if self.llm is None or task_type != getattr(self, 'current_model_key', ''):
            self.switch_model(task_type)

        sys_prompt = self._get_system_block(
            config.HEAVY_AGENT_SYSTEM_PROMPT + f" Имя пользователя: {getpass.getuser()}.", 
            context=long_term_context
        )

        messages = [{"role": "system", "content": sys_prompt}]
        messages.extend(self.history)
        messages.append({"role": "user", "content": user_prompt})

        try:
            gen_params = config.LLM_GEN_PARAMS.get(task_type, config.LLM_GEN_PARAMS.get("default", {}))
            response = self.llm.create_chat_completion(
                messages=messages, stream=True, **gen_params
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
                if len(self.history) > config.MAX_HISTORY_MESSAGES:
                    self.history = self.history[-config.MAX_HISTORY_MESSAGES:]
