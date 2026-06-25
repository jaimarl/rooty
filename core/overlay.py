import sys
import json
import socket
import threading

# Подключаем GTK3 и Layer Shell через GObject Introspection
import gi
gi.require_version('Gtk', '3.0')
gi.require_version('GtkLayerShell', '0.1')
from gi.repository import Gtk, GtkLayerShell, GLib, Gdk

class AssistantOverlay(Gtk.Window):
    def __init__(self):
        super().__init__()
        
        # --- МАГИЯ LAYER SHELL ---
        # Превращаем обычное окно в элемент интерфейса Wayland
        GtkLayerShell.init_for_window(self)
        
        # Размещаем на слое OVERLAY (поверх всех окон, панелей и игр)
        GtkLayerShell.set_layer(self, GtkLayerShell.Layer.OVERLAY)
        
        # Привязываем к верхнему краю экрана (anchor)
        GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.TOP, True)
        # Отступ сверху в 50 пикселей
        GtkLayerShell.set_margin(self, GtkLayerShell.Edge.TOP, 50)
        # Так как мы не привязываем Left и Right, композитор отцентрирует его по горизонтали
        
        self.set_app_paintable(True)

        # --- GTK CSS СТИЛИ (Catppuccin) ---
        self.css_provider = Gtk.CssProvider()
        
        css_data = """
            window {
                background-color: transparent; /* Окно полностью прозрачное */
            }
            #overlay-box {
                background-color: rgba(30, 30, 46, 0.95);
                border: 2px solid #cba6f7;
                border-radius: 12px;
                padding: 15px 25px;
            }
            #overlay-label {
                color: #cdd6f4;
                font-family: monospace;
                font-size: 16px;
            }
            /* Динамические классы для разных состояний */
            #overlay-label.thinking { color: #a6e3a1; }
            #overlay-label.response { color: #f9e2af; }
            #overlay-label.error { color: #f38ba8; }
        """
        self.css_provider.load_from_data(css_data.encode('utf-8'))        

        context = self.get_style_context()
        context.add_provider_for_screen(
            Gdk.Screen.get_default(),
            self.css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
        
        # --- ИНТЕРФЕЙС ---
        self.box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.box.set_name("overlay-box")
        
        self.label = Gtk.Label(label="")
        self.label.set_name("overlay-label")
        self.label.set_line_wrap(True)
        self.label.set_max_width_chars(60)
        self.label.set_justify(Gtk.Justification.CENTER)
        
        self.box.pack_start(self.label, True, True, 0)
        self.add(self.box)
        
        # Переменная таймера скрытия
        self.hide_timer_id = None
        
        # Запуск UDP сервера
        self.server_thread = threading.Thread(target=self.udp_server, daemon=True)
        self.server_thread.start()

    def udp_server(self):
        """Фоновый поток сервера."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.bind(("127.0.0.1", 9999))
        except OSError as e:
            # GLib.idle_add безопасно вызывает метод UI из фонового потока
            GLib.idle_add(self.update_ui, {"state": "error", "text": "Порт 9999 занят!\nСделайте pkill -f overlay.py"})
            return

        while True:
            data, _ = sock.recvfrom(4096)
            try:
                msg = json.loads(data.decode('utf-8'))
                GLib.idle_add(self.update_ui, msg) 
            except Exception:
                pass

    def update_ui(self, msg):
        """Обновление интерфейса."""
        state = msg.get("state")
        text = msg.get("text", "")

        # Сброс старого таймера
        if self.hide_timer_id:
            GLib.source_remove(self.hide_timer_id)
            self.hide_timer_id = None

        # Очистка старых CSS-классов
        context = self.label.get_style_context()
        for cls in ["thinking", "response", "error"]:
            if context.has_class(cls):
                context.remove_class(cls)

        if state == "listening":
            self.label.set_text("🎙️ Слушаю запрос...")
            self.show_all()
            
        elif state == "thinking":
            # Используем текст от Секретаря, если он есть, иначе дефолтный
            display_text = text if text else "⚙️ Нейросеть генерирует ответ..."
            self.label.set_text(display_text)
            context.add_class("thinking")
            self.show_all()            

        elif state == "response":
            short_text = text[:150] + "..." if len(text) > 150 else text
            self.label.set_text(f"✨ Ответ готов:\n\n{short_text}")
            context.add_class("response")
            self.show_all()
            # Таймер на 7 секунд
            self.hide_timer_id = GLib.timeout_add(7000, self.hide_window)
            
        elif state == "error":
            self.label.set_text(text)
            context.add_class("error")
            self.show_all()
            
        elif state == "hide":
            self.hide()
            
    def hide_window(self):
        """Функция, вызываемая таймером GTK."""
        self.hide()
        self.hide_timer_id = None
        return False # False означает, что таймер не будет повторяться

if __name__ == "__main__":
    app = AssistantOverlay()
    # Запускаем главный цикл (Event Loop) GTK
    Gtk.main()
