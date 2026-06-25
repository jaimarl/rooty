import sys
import json
import socket
import subprocess
import atexit
import getpass
from datetime import datetime

from core.llm_engine import LocalLLMEngine
from core.memory import SQLiteMemory
from core import config

class CLIApp:
    def __init__(self):
        print("🚀 Инициализация ядра...")
        self.memory = SQLiteMemory()
        self.engine = LocalLLMEngine()

        self.overlay_process = subprocess.Popen([sys.executable, "core/overlay.py"])
        self.udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        atexit.register(self.cleanup)

        self.username = getpass.getuser()
        self.hostname = socket.gethostname()

        print(f"✅ Готово! Активная роль: {self.engine.current_role.upper()}")
        print("💡 Введите /help для списка команд.\n")

    def send_overlay(self, state: str, text: str = ""):
        try:
            msg = json.dumps({"state": state, "text": text}).encode('utf-8')
            self.udp_sock.sendto(msg, ("127.0.0.1", 9999))
        except Exception:
            pass

    def cleanup(self):
        self.send_overlay("hide")
        if hasattr(self, 'overlay_process'):
            self.overlay_process.terminate()

    def handle_command(self, text: str):
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
            print("\n--- ИСТОРИЯ КОНТЕКСТА ---")
            for m in self.engine.get_history():
                print(f"[{m['role'].upper()}]: {m['content'][:60]}...")
            print("-------------------------\n")
        elif cmd == "roles":
            print("[SYSTEM] Доступные роли:", ", ".join(config.ROLES.keys()))
        elif cmd == "role":
            if not args:
                print("[SYSTEM] Укажите роль: /role <имя>")
            elif self.engine.set_role(args.lower()):
                self.engine.clear_history()
                print(f"[SYSTEM] Роль изменена на: {args.upper()}")
            else:
                print(f"[SYSTEM] Роль '{args}' не найдена.")
        elif cmd == "help":
            print("[SYSTEM] Команды: /exit, /clear, /history, /roles, /role <имя>")
        else:
            print(f"[SYSTEM] Неизвестная команда: {cmd}")

    def run(self):
        while True:
            try:
                ctime = datetime.now().strftime("%H:%M:%S")
                user_text = input(f"\n\033[90m[{ctime}]\033[0m \033[92m[{self.username}@{self.hostname}]~>\033[0m ").strip()
                
                if not user_text: continue
                if user_text.startswith('/'):
                    self.handle_command(user_text)
                    continue

                self.send_overlay("thinking")
                
                context = self.memory.search_relevant_context(user_text)
                is_complex, task_type = self.engine.analyze_prompt(user_text)

                ctime = datetime.now().strftime("%H:%M:%S")
                print("\n\033[90m┌── СИСТЕМНЫЙ ЛОГ")
                if context:
                    print(f"│ 🗃️ Извлечено воспоминаний из БД: {context.count(f'{self.username}:')}")
                print(f"│ [{ctime}] 🧭 Маршрутизация: {task_type.upper()} ({'Сложный' if is_complex else 'Простой'})")
                print("└──────────────────────────────────\033[0m\n")

                if not is_complex:
                    ctime = datetime.now().strftime("%H:%M:%S")
                    print(f"\033[90m[{ctime}]\033[0m \033[96m[ ⚡ Fast-Агент ]\033[0m\n\033[36m> \033[0m", end="", flush=True)
                    
                    full_response = ""
                    for token in self.engine.stream_fast_response(user_text, config.FAST_AGENT_SIMPLE_PROMPT, db_context=context):
                        full_response += token
                        print(token, end="", flush=True)
                    print()
                    
                    if full_response.strip():
                        self.memory.save_interaction(user_text, full_response)
                        self.engine.history.append({"role": "user", "content": user_text})
                        self.engine.history.append({"role": "assistant", "content": full_response})
                        
                    self.send_overlay("response", full_response)

                else:
                    notify_msg = self.engine.generate_fast_response(user_text, config.FAST_AGENT_NOTIFY_PROMPT)
                    
                    ctime = datetime.now().strftime("%H:%M:%S")
                    print(f"\033[90m[{ctime}]\033[0m \033[96m[ ⚡ Fast-Агент (Уведомление) ]\033[0m\n\033[36m> {notify_msg}\033[0m\n")
                    self.send_overlay("thinking", f"⏳ {notify_msg}")
                    
                    if task_type != self.engine.current_model_key or getattr(self.engine, 'llm', None) is None:
                        print(f"\033[90m[ SYSTEM ] Загрузка модели {task_type.upper()} в VRAM...\033[0m\n")
                        
                    ctime = datetime.now().strftime("%H:%M:%S")
                    print(f"\033[90m[{ctime}]\033[0m \033[95m[ 🧠 {self.engine.current_role.capitalize()} (Развернутый ответ) ]\033[0m\n\033[35m> \033[0m", end="", flush=True)
                    
                    full_response = ""
                    for token in self.engine.generate_stream(user_text, long_term_context=context, task_type=task_type):
                        full_response += token
                        print(token, end="", flush=True)
                    print()
                    
                    if full_response.strip():
                        self.memory.save_interaction(user_text, full_response)
                        
                    self.send_overlay("response", "✅ Готово! Подробный ответ выведен в терминал.")
                    self.engine.unload_heavy_model()

            except KeyboardInterrupt:
                print("\n\033[90m[SYSTEM] Введите /exit для выхода.\033[0m")
            except Exception as e:
                print(f"\n\033[91m[ERROR] Ошибка генерации: {e}\033[0m")
                self.send_overlay("error", f"Ошибка: {e}")
