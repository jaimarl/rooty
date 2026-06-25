import os
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QScrollArea, 
                             QLineEdit, QPushButton, QLabel, QSpacerItem, QSizePolicy)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor

def get_tinted_pixmap(svg_path: str, color_hex: str) -> QPixmap:
    """Загружает SVG и возвращает перекрашенный QPixmap."""
    if not os.path.exists(svg_path):
        print(f"[UI ERROR] Иконка не найдена: {svg_path}")
        return QPixmap()

    with open(svg_path, 'r', encoding='utf-8') as f:
        svg_content = f.read().replace('currentColor', '#ffffff').replace('#000000', '#ffffff').replace('black', '#ffffff')
        
    base_pixmap = QPixmap()
    base_pixmap.loadFromData(svg_content.encode('utf-8'), "SVG")
    
    if base_pixmap.isNull():
        return QPixmap()

    tinted_pixmap = QPixmap(base_pixmap.size())
    tinted_pixmap.fill(Qt.GlobalColor.transparent)
    
    painter = QPainter(tinted_pixmap)
    painter.drawPixmap(0, 0, base_pixmap)
    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
    painter.fillRect(tinted_pixmap.rect(), QColor(color_hex))
    painter.end()
    
    return tinted_pixmap

def get_tinted_icon(svg_path: str, color_hex: str) -> QIcon:
    """Удобная обертка для получения QIcon."""
    pixmap = get_tinted_pixmap(svg_path, color_hex)
    return QIcon(pixmap) if not pixmap.isNull() else QIcon()


class MessageBubble(QWidget):
    """Виджет отдельного сообщения в чате."""
    def __init__(self, text: str, is_user: bool):
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(7, 7, 7, 7)
        
        self.label = QLabel(text)
        self.label.setWordWrap(True)
        self.label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        
        self.label.setProperty("class", "ChatBubble " + ("UserBubble" if is_user else "AIBubble"))
        
        if is_user:
            layout.addSpacerItem(QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum))
            layout.addWidget(self.label)
        else:
            layout.addWidget(self.label)
            layout.addSpacerItem(QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum))


class ChatWidget(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        # Отступы от краев рабочей зоны до блоков чата и ввода
        layout.setContentsMargins(0, 10, 10, 10)
        layout.setSpacing(8) # Расстояние между блоком сообщений и полем ввода

        # 1. КОНТЕЙНЕР ИСТОРИИ ЧАТА (Цвет base)
        self.log_container = QWidget()
        self.log_container.setObjectName("ChatLogContainer")
        log_layout = QVBoxLayout(self.log_container)
        log_layout.setContentsMargins(5, 5, 5, 5)

        self.scroll_area = QScrollArea()
        self.scroll_area.setObjectName("ChatScrollArea")
        self.scroll_area.setWidgetResizable(True)
        
        self.scroll_content = QWidget()
        self.scroll_content.setObjectName("ChatScrollAreaWidget")
        self.scroll_layout = QVBoxLayout(self.scroll_content)
        self.scroll_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        self.scroll_area.setWidget(self.scroll_content)
        log_layout.addWidget(self.scroll_area)

        # Добавляем историю чата, давая ей stretch=1, чтобы она занимала всё свободное пространство
        layout.addWidget(self.log_container, stretch=1)

        # 2. КОНТЕЙНЕР ВВОДА (Прозрачный, на фоне сайдбара)
        self.input_container = QWidget()
        self.input_container.setObjectName("InputContainer")
        
        input_layout = QHBoxLayout(self.input_container)
        input_layout.setContentsMargins(0, 0, 0, 0)
        input_layout.setSpacing(5)

        self.input_field = QLineEdit()
        self.input_field.setObjectName("ChatInput")
        self.input_field.setPlaceholderText("Напишите сообщение ассистенту...")
        self.input_field.returnPressed.connect(self.send_message)
        
        # Настраиваем кнопку отправки
        self.send_btn = QPushButton()
        self.send_btn.setObjectName("SendButton")
        self.send_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        
        # Загружаем иконку
        icon_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'assets', 'icons')
        icon_path = os.path.join(icon_dir, 'send-horizontal.svg')
        
        # Красим иконку в светлый цвет текста (или можете задать свой акцентный цвет)
        self.send_btn.setIcon(get_tinted_icon(icon_path, '#181825'))
        self.send_btn.setIconSize(QSize(20, 20))
        
        self.send_btn.clicked.connect(self.send_message)
        
        input_layout.addWidget(self.input_field)
        input_layout.addWidget(self.send_btn)
        
        layout.addWidget(self.input_container)

        # Приветственное сообщение
        self.add_message("Привет! Я твой локальный ИИ-ассистент. Чем могу помочь?", is_user=False)

    def send_message(self):
        text = self.input_field.text().strip()
        if not text: return
        
        self.add_message(text, is_user=True)
        self.input_field.clear()
        
        # TODO: Интеграция с LocalLLMEngine
        self.add_message("Думаю над ответом...", is_user=False)

    def add_message(self, text: str, is_user: bool):
        bubble = MessageBubble(text, is_user)
        self.scroll_layout.addWidget(bubble)
        self.scroll_area.verticalScrollBar().setValue(self.scroll_area.verticalScrollBar().maximum())
