import sys
import os
from PyQt6.QtWidgets import QApplication
from ui.main_window import MainWindow

def load_stylesheet(app: QApplication):
    """Загрузка стилей Material 3 Expressive из .qss файла."""
    style_path = os.path.join(os.path.dirname(__file__), 'ui', 'assets', 'style.qss')
    if os.path.exists(style_path):
        with open(style_path, "r", encoding="utf-8") as f:
            app.setStyleSheet(f.read())
    else:
        print(f"Внимание: Файл стилей не найден по пути {style_path}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # Применяем CSS
    load_stylesheet(app)
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())
