import sys
import json
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
        while True:
            try:
                user_text = input(f"\n> Вы: ").strip()
                if not user_text:
                    continue

                if user_text.startswith('/'):
                    self.handle_command(user_text)
                    continue

                self.send_overlay("thinking")
                
                # 1. RAG (Поиск контекста в памяти)
                context = self.memory.search_relevant_context(user_text)
                if context:
                    print(f"[SYSTEM] Извлечено воспоминаний из БД: {context.count('Пользователь:')}")

                # 2. Умный роутинг: узнаем сложность и тип
                is_complex, task_type = self.engine.analyze_prompt(user_text)

                # =========================================================
                # ВЕТВЬ 1: ПРОСТОЙ ЗАПРОС (ОБРАБАТЫВАЕТ ЛЕГКАЯ МОДЕЛЬ)
                # =========================================================
                if not is_complex:
                    print(f"[SYSTEM] ⚡ Быстрый ответ (Категория: {task_type.upper()})")
                    print(f"> Fast-Агент: ", end="", flush=True)
                    
                    sys_prompt = "Ты быстрый ИИ-помощник. Отвечай кратко, ёмко и по делу (максимум 1-3 предложения)."
                    if context:
                        sys_prompt += f"\nИспользуй этот контекст памяти: {context}"
                        
                    full_response = ""
                    for token in self.engine.generate_fast_response(user_text, sys_prompt, stream=True):
                        full_response += token
                        print(token, end="", flush=True)
                    print()
                    
                    if full_response.strip():
                        self.memory.save_interaction(user_text, full_response)
                        
                    # Оверлей показывает готовый ответ и сам скрывается
                    self.send_overlay("response", full_response)

                # =========================================================
                # ВЕТВЬ 2: СЛОЖНЫЙ ЗАПРОС (ТЯЖЕЛАЯ МОДЕЛЬ + СЕКРЕТАРЬ)
                # =========================================================
                else:
                    print(f"[SYSTEM] 🧠 Глубокий анализ (Категория: {task_type.upper()})")
                    
                    # А) Секретарь пишет уведомление
                    notify_sys = "Напиши ОДНО короткое предложение. Скажи, что ты приступил к сложной задаче и просишь пользователя немного подождать."
                    notify_msg = self.engine.generate_fast_response(user_text, notify_sys, stream=False)
                    
                    # ИСПРАВЛЕНИЕ 1: Печатаем ответ Fast-Агента в терминал
                    print(f"> Fast-Агент: {notify_msg}")
                    
                    # ИСПРАВЛЕНИЕ 2: Отправляем в оверлей статус thinking, чтобы плашка висела до конца
                    self.send_overlay("thinking", f"⏳ {notify_msg}")
                    
                    # Б) Грузим профильную тяжелую модель, если нужно
                    if task_type != self.engine.current_model_key:
                        print(f"[SYSTEM] Подготовка модели {task_type.upper()}...")
                        
                    print(f"> {self.engine.current_persona.capitalize()}: ", end="", flush=True)
                    
                    # В) Запускаем долгую генерацию в консоль
                    full_response = ""
                    for token in self.engine.generate_stream(user_text, long_term_context=context, task_type=task_type):
                        full_response += token
                        print(token, end="", flush=True)
                    print()
                    
                    if full_response.strip():
                        self.memory.save_interaction(user_text, full_response)
                        
                    # Даем сигнал в оверлей, что тяжелая работа закончена
                    self.send_overlay("response", "✅ Готово! Подробный ответ выведен в терминал.")

            except KeyboardInterrupt:
                print("\n[SYSTEM] Введите /exit для выхода.")
            except Exception as e:
                print(f"\n[ERROR] Ошибка генерации: {e}")
                self.send_overlay("error", f"Ошибка: {e}")

if __name__ == "__main__":
    app = CLIApp()
    app.run()
