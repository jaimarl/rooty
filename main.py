import sys
import json
import getpass
import socket
import subprocess
import atexit

from core.llm_engine import LocalLLMEngine
from core.memory import SQLiteMemory
from core import config

class CLIApp:
    def __init__(self):
        print("🚀 Инициализация ядра...")
        self.memory = SQLiteMemory()
        self.engine = LocalLLMEngine()

        # Запуск фонового графического оверлея
        self.overlay_process = subprocess.Popen([sys.executable, "core/overlay.py"])
        self.udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        
        # Гарантированное закрытие оверлея при выходе из скрипта
        atexit.register(self.cleanup)

        print(f"✅ Готово! Активная роль: {self.engine.current_persona.upper()}")
        print("💡 Введите /help для списка команд.\n")

    def send_overlay(self, state: str, text: str = ""):
        """Отправка UDP-сигнала оверлею."""
        try:
            msg = json.dumps({"state": state, "text": text}).encode('utf-8')
            self.udp_sock.sendto(msg, ("127.0.0.1", 9999))
        except Exception:
            pass

    def cleanup(self):
        """Очистка процессов при выходе."""
        self.send_overlay("hide")
        if hasattr(self, 'overlay_process'):
            self.overlay_process.terminate()

    def handle_command(self, text: str):
        """Обработчик текстовых команд."""
        parts = text[1:].split(maxsplit=1)
        cmd = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""

        if cmd in ["exit", "quit"]:
            self.cleanup()
            sys.exit(0)
        elif cmd == "clear":
            self.engine.clear_history()
            print("[SYSTEM] Контекст очищен.")
        elif cmd == "history":
            hist = self.engine.get_history()
            print("\n--- ИСТОРИЯ КОНТЕКСТА ---")
            for m in hist:
                print(f"[{m['role'].upper()}]: {m['content'][:60]}...")
            print("-------------------------\n")
        elif cmd == "personas":
            print("[SYSTEM] Доступные роли:", ", ".join(config.PERSONAS.keys()))
        elif cmd == "role":
            if not args:
                print("[SYSTEM] Укажите роль: /role <имя>")
            elif self.engine.set_persona(args.lower()):
                self.engine.clear_history()
                print(f"[SYSTEM] Личность изменена на: {args.upper()}")
            else:
                print(f"[SYSTEM] Роль '{args}' не найдена.")
        elif cmd == "help":
            print("[SYSTEM] Команды: /exit, /clear, /history, /personas, /role <имя>")
        else:
            print(f"[SYSTEM] Неизвестная команда: {cmd}")

    def run(self):
        """Главный цикл приложения."""
        import getpass
        import socket
        from datetime import datetime  # Добавляем импорт для работы со временем
        
        # Динамически получаем имя пользователя и хост системы
        username = getpass.getuser()
        hostname = socket.gethostname()
        
        while True:
            try:
                # 1. Время для запроса пользователя
                current_time = datetime.now().strftime("%H:%M:%S")
                user_text = input(f"\n\033[90m[{current_time}]\033[0m \033[92m[{username}@{hostname}]~>\033[0m ").strip()
                
                if not user_text:
                    continue

                if user_text.startswith('/'):
                    self.handle_command(user_text)
                    continue

                self.send_overlay("thinking")
                
                context = self.memory.search_relevant_context(user_text)
                is_complex, task_type = self.engine.analyze_prompt(user_text)

                # 2. Время для результата роутинга
                current_time = datetime.now().strftime("%H:%M:%S")

                print("\n\033[90m┌── СИСТЕМНЫЙ ЛОГ")
                if context:
                    print(f"│ 🗃️ Извлечено воспоминаний из БД: {context.count(f'{username}:')}")
                print(f"│ [{current_time}] 🧭 Маршрутизация: {task_type.upper()} ({'Сложный' if is_complex else 'Простой'})")
                print("└──────────────────────────────────\033[0m\n")

                # Общие данные
                persona_prompt = config.PERSONAS.get(self.engine.current_persona, config.PERSONAS[config.DEFAULT_PERSONA])

                # =========================================================
                # ВЕТВЬ 1: ПРОСТОЙ ЗАПРОС (ОБРАБАТЫВАЕТ ЛЕГКАЯ МОДЕЛЬ)
                # =========================================================
                if not is_complex:
                    # 3. Время для ответа быстрой модели
                    current_time = datetime.now().strftime("%H:%M:%S")
                    print(f"\033[90m[{current_time}]\033[0m \033[96m[ ⚡ Fast-Агент ]\033[0m")
                    print("\033[36m> \033[0m", end="", flush=True)
                    
                    context_block = f"\nИспользуй контекст:\n{context}" if context else ""
                    sys_prompt = config.FAST_AGENT_SIMPLE_PROMPT.format(
                        persona_prompt=persona_prompt,
                        context_block=context_block
                    )
                        
                    full_response = ""
                    for token in self.engine.stream_fast_response(user_text, sys_prompt):
                        full_response += token
                        print(token, end="", flush=True)
                    print()
                    
                    if full_response.strip():
                        self.memory.save_interaction(user_text, full_response)
                        self.engine.history.append({"role": "user", "content": user_text})
                        self.engine.history.append({"role": "assistant", "content": full_response})
                        
                    self.send_overlay("response", full_response)

                # =========================================================
                # ВЕТВЬ 2: СЛОЖНЫЙ ЗАПРОС (ТЯЖЕЛАЯ МОДЕЛЬ + СЕКРЕТАРЬ)
                # =========================================================
                else:
                    notify_sys = config.FAST_AGENT_NOTIFY_PROMPT.format(
                        persona_prompt=persona_prompt,
                        user_prompt=user_text
                    )
                    
                    dummy_prompt = "Сгенерируй короткое уведомление о том, что ты приступил к задаче."
                    notify_msg = self.engine.generate_fast_response(dummy_prompt, notify_sys)
                    
                    # 4. Время для уведомления Секретаря
                    current_time = datetime.now().strftime("%H:%M:%S")
                    print(f"\033[90m[{current_time}]\033[0m \033[96m[ ⚡ Fast-Агент (Уведомление) ]\033[0m")
                    print(f"\033[36m> {notify_msg}\033[0m\n")
                    self.send_overlay("thinking", f"⏳ {notify_msg}")
                    
                    # ИЗМЕНЕНИЕ: Проверяем, не пустая ли память
                    if task_type != self.engine.current_model_key or getattr(self.engine, 'llm', None) is None:
                        print(f"\033[90m[ SYSTEM ] Загрузка модели {task_type.upper()} в VRAM...\033[0m\n")
                        
                    # 5. Время для развернутого ответа тяжелой модели
                    current_time = datetime.now().strftime("%H:%M:%S")
                    print(f"\033[90m[{current_time}]\033[0m \033[95m[ 🧠 {self.engine.current_persona.capitalize()} (Развернутый ответ) ]\033[0m")
                    print("\033[35m> \033[0m", end="", flush=True)
                    
                    full_response = ""
                    for token in self.engine.generate_stream(user_text, long_term_context=context, task_type=task_type):
                        full_response += token
                        print(token, end="", flush=True)
                    print()
                    
                    if full_response.strip():
                        self.memory.save_interaction(user_text, full_response)
                        
                    self.send_overlay("response", "✅ Готово! Подробный ответ выведен в терминал.")
                    
                    # === НОВОЕ: ВЫГРУЗКА МОДЕЛИ ИЗ VRAM ===
                    self.engine.unload_heavy_model()

            except KeyboardInterrupt:
                print("\n\033[90m[SYSTEM] Введите /exit для выхода.\033[0m")
            except Exception as e:
                print(f"\n\033[91m[ERROR] Ошибка генерации: {e}\033[0m")
                self.send_overlay("error", f"Ошибка: {e}")

if __name__ == "__main__":
    app = CLIApp()
    app.run()
