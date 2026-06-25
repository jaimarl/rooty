import os
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QFrame, QButtonGroup
from PyQt6.QtCore import Qt, pyqtSignal, QSize, QVariantAnimation, QEasingCurve, QPropertyAnimation, pyqtProperty
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor

def get_tinted_pixmap(svg_path: str, color_hex: str) -> QPixmap:
    if not os.path.exists(svg_path):
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
    pixmap = get_tinted_pixmap(svg_path, color_hex)
    return QIcon(pixmap) if not pixmap.isNull() else QIcon()


class Sidebar(QWidget):
    tab_changed = pyqtSignal(str)

    # Управляет шириной панели для анимации расширения
    @pyqtProperty(int)
    def sidebarWidth(self):
        return self.width()

    @sidebarWidth.setter
    def sidebarWidth(self, val):
        self.setFixedWidth(val)

    def __init__(self):
        super().__init__()
        self.setObjectName("Sidebar")
        self.setFixedWidth(240)
        self.is_collapsed = False
        
        self.icon_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'ui', 'assets', 'icons')
        
        # Возвращаем стандартный Layout. 
        # Он заставит кнопки сжиматься в идеальные квадраты при сворачивании.
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(10, 10, 10, 10)
        self.layout.setSpacing(5)

        self.nav_buttons = []
        self.btn_group = QButtonGroup(self)
        self.btn_group.setExclusive(True)
        self.btn_group.buttonToggled.connect(self.on_group_toggled)

        self.btn_chat = self.create_button("message-square.svg", "Чат", target_id="chat")
        self.layout.addSpacing(5)

        divider = QFrame()
        divider.setObjectName("MenuDivider")
        divider.setFixedHeight(1)
        divider.setStyleSheet("background-color: rgba(255, 255, 255, 0.1); margin-left: 10px; margin-right: 10px;")
        self.layout.addWidget(divider)
        self.layout.addSpacing(5)

        self.btn_models = self.create_button("brain-circuit.svg", "Модели", target_id="settings_models")
        self.btn_roles = self.create_button("venetian-mask.svg", "Роли", target_id="settings_roles")
        self.btn_audio = self.create_button("audio-lines.svg", "Звук", target_id="settings_audio")
        self.btn_live2d = self.create_button("user.svg", "Live2D", target_id="settings_live2d")
        self.btn_integrations = self.create_button("workflow.svg", "Интеграции", target_id="settings_integrations")
        self.btn_gui = self.create_button("palette.svg", "Интерфейс", target_id="settings_gui")

        self.layout.addStretch()

        self.toggle_btn = self.create_button("chevron-left.svg", "Свернуть", is_toggle_btn=True)
        self.toggle_btn.clicked.connect(self.toggle_sidebar)
        self.layout.addWidget(self.toggle_btn)

        # --- Подготовка анимаций ---
        self.toggle_base_pixmap = get_tinted_pixmap(os.path.join(self.icon_dir, "chevron-left.svg"), '#cad3f5')
        
        self.width_anim = QPropertyAnimation(self, b"sidebarWidth")
        self.width_anim.setDuration(300)
        self.width_anim.setEasingCurve(QEasingCurve.Type.InOutCubic)

        self.icon_anim = QVariantAnimation(self)
        self.icon_anim.setDuration(300) 
        self.icon_anim.setEasingCurve(QEasingCurve.Type.InOutCubic) 
        self.icon_anim.valueChanged.connect(self.update_toggle_icon)

        # Анимация прозрачности текста
        self.fade_anim = QVariantAnimation(self)
        self.fade_anim.setDuration(200) # Чуть быстрее, чтобы текст исчез до того, как кнопка сильно сожмется
        self.fade_anim.setEasingCurve(QEasingCurve.Type.InOutQuad)
        self.fade_anim.valueChanged.connect(self.update_text_alpha)

        # Инициализация (текст непрозрачный при старте)
        self.update_text_alpha(255)
        self.btn_chat.setChecked(True)

    def create_button(self, icon_name: str, text: str, is_toggle_btn: bool = False, target_id: str = "") -> QPushButton:
        # Возвращаем стандартные QPushButton (Никаких кастомных классов)
        btn = QPushButton(f"  {text}")
        btn.setProperty("class", "SidebarButton")
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        
        icon_path = os.path.join(self.icon_dir, icon_name)
        
        btn.icon_normal = get_tinted_icon(icon_path, '#cad3f5')
        btn.icon_checked = get_tinted_icon(icon_path, '#181825')
        
        btn.setIcon(btn.icon_normal)
        btn.setIconSize(QSize(20, 20))
        
        if not is_toggle_btn:
            btn.setCheckable(True)
            btn.target_id = target_id
            
            self.btn_group.addButton(btn)
            self.layout.addWidget(btn)
            self.nav_buttons.append(btn)
            
        return btn

    def on_group_toggled(self, btn: QPushButton, checked: bool):
        if checked:
            btn.setIcon(btn.icon_checked)
            self.tab_changed.emit(btn.target_id)
        else:
            btn.setIcon(btn.icon_normal)

    def update_text_alpha(self, alpha: int):
        # Применяем CSS ко всем кнопкам в сайдбаре: иконки остаются яркими, 
        # а альфа-канал текста динамически меняется.
        self.setStyleSheet(f"""
            QPushButton.SidebarButton {{
                text-align: left;
                padding: 12px 12px;
                border-radius: 12px;
                background-color: transparent;
                font-size: 15px;
                font-weight: 500;
                border: none;
                color: rgba(202, 211, 245, {alpha});
            }}
            QPushButton.SidebarButton:hover {{
                background-color: #494d64;
            }}
            QPushButton.SidebarButton:checked {{
                background-color: #8aadf4;
                font-weight: bold;
                color: rgba(24, 24, 37, {alpha});
            }}
        """)

    def update_toggle_icon(self, angle: float):
        if self.toggle_base_pixmap.isNull():
            return
        rotated_pixmap = QPixmap(self.toggle_base_pixmap.size())
        rotated_pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(rotated_pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        center_x = rotated_pixmap.width() / 2.0
        center_y = rotated_pixmap.height() / 2.0
        painter.translate(center_x, center_y)
        painter.rotate(angle)
        painter.translate(-center_x, -center_y)
        painter.drawPixmap(0, 0, self.toggle_base_pixmap)
        painter.end()
        self.toggle_btn.setIcon(QIcon(rotated_pixmap))

    def toggle_sidebar(self):
        self.is_collapsed = not self.is_collapsed
        
        current_width = self.width()
        current_angle = self.icon_anim.currentValue() if self.icon_anim.state() == QVariantAnimation.State.Running else (180.0 if not self.is_collapsed else 0.0)
        current_alpha = self.fade_anim.currentValue() if self.fade_anim.state() == QVariantAnimation.State.Running else (0 if not self.is_collapsed else 255)

        self.width_anim.stop()
        self.icon_anim.stop()
        self.fade_anim.stop()

        if self.is_collapsed:
            self.width_anim.setStartValue(current_width)
            self.width_anim.setEndValue(64)
            
            self.icon_anim.setStartValue(current_angle)
            self.icon_anim.setEndValue(180.0)
            
            self.fade_anim.setStartValue(current_alpha)
            self.fade_anim.setEndValue(0) # Текст растворяется
        else:
            self.width_anim.setStartValue(current_width)
            self.width_anim.setEndValue(240)
            
            self.icon_anim.setStartValue(current_angle)
            self.icon_anim.setEndValue(0.0)
            
            self.fade_anim.setStartValue(current_alpha)
            self.fade_anim.setEndValue(255) # Текст проявляется

        self.width_anim.start()
        self.icon_anim.start()
        self.fade_anim.start()
