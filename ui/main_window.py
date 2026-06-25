from PyQt6.QtWidgets import QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QStackedWidget, QLabel
from PyQt6.QtCore import Qt
from ui.sidebar import Sidebar
from ui.chat.chat_widget import ChatWidget

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Local AI Assistant")
        self.resize(1100, 750)
        self.setMinimumSize(800, 500)

        # 1. Убираем системные рамки и делаем фон прозрачным (для кастомных скруглений)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # 2. Создаем главный контейнер (Он играет роль "рамки" 10px цвета surface0)
        self.main_container = QWidget()
        self.main_container.setObjectName("MainWindowContainer")
        self.setCentralWidget(self.main_container)

        # Layout главного контейнера
        self.main_layout = QHBoxLayout(self.main_container)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        # 3. Инициализация бокового меню
        self.sidebar = Sidebar()
        self.sidebar.tab_changed.connect(self.switch_tab)
        self.main_layout.addWidget(self.sidebar)

        # 4. Создаем "правую часть" окна (цвет base)
        self.content_area = QWidget()
        self.content_area.setObjectName("MainContentArea")
        self.content_layout = QVBoxLayout(self.content_area)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        
        # Используем QStackedWidget для переключения экранов (Чат, Настройки)
        self.stacked_widget = QStackedWidget()
        self.content_layout.addWidget(self.stacked_widget)
        self.main_layout.addWidget(self.content_area)

        # Добавляем страницы в StackedWidget
        self.chat_view = ChatWidget()
        self.settings_models_view = QLabel("Здесь будут настройки моделей")
        self.settings_models_view.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.stacked_widget.addWidget(self.chat_view)           # Индекс 0
        self.stacked_widget.addWidget(self.settings_models_view) # Индекс 1

    def switch_tab(self, target_id: str):
        """Роутинг вкладок"""
        if target_id == "chat":
            self.stacked_widget.setCurrentIndex(0)
        elif target_id == "settings_models":
            self.stacked_widget.setCurrentIndex(1)
        # TODO: Добавить остальные

    # --- ИНТЕГРАЦИЯ С LINUX / WAYLAND ---
    # Так как окно безрамочное, Wayland не даст его перетаскивать стандартным способом.
    # Мы перехватываем клик по окну и просим оконный менеджер (KWin/Mutter) начать системное перемещение.
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            # Начинаем нативный драг окна
            if self.windowHandle():
                self.windowHandle().startSystemMove()

    def resizeEvent(self, event):
        """Автоматическое сворачивание меню при узком окне (Responsive дизайн)."""
        super().resizeEvent(event)
        if self.width() < 900 and not self.sidebar.is_collapsed:
            self.sidebar.toggle_sidebar()
        elif self.width() >= 900 and self.sidebar.is_collapsed:
            self.sidebar.toggle_sidebar()
