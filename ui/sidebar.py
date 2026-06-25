import os
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QFrame, QButtonGroup
from PyQt6.QtCore import Qt, pyqtSignal, QSize, QVariantAnimation, QEasingCurve, QPropertyAnimation, QRect
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor

def get_tinted_pixmap(svg_path: str, color_hex: str) -> QPixmap:
    """Загружает SVG и возвращает перекрашенный QPixmap."""
    if not os.path.exists(svg_path):
        print(f"[UI ERROR] Иконка не найдена: {svg_path}")
        return QPixmap()

    with open(svg_path, 'r', encoding='utf-8') as f:
        # Превращаем любой исходный цвет в чисто белый
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


class Sidebar(QWidget):
    tab_changed = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.setObjectName("Sidebar")
        self.setFixedWidth(240)
        self.is_collapsed = False
        
        self.icon_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'ui', 'assets', 'icons')
        
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(10, 10, 10, 10)
        self.layout.setSpacing(5)

        self.nav_buttons = []

        self.btn_group = QButtonGroup(self)
        self.btn_group.setExclusive(True)
        self.btn_group.buttonToggled.connect(self.on_group_toggled)

        # --- 1. Кнопка Чата ---
        self.btn_chat = self.create_button("message-square.svg", "Чат", target_id="chat")
        
        self.layout.addSpacing(5)

        # --- 2. Визуальный разделитель ---
        divider = QFrame()
        divider.setObjectName("MenuDivider")
        divider.setFixedHeight(1)
        divider.setStyleSheet("background-color: rgba(255, 255, 255, 0.1);")
        self.layout.addWidget(divider)

        self.layout.addSpacing(5)

        # --- 3. Остальные кнопки меню ---
        self.btn_models = self.create_button("brain-circuit.svg", "Модели", target_id="settings_models")
        self.btn_roles = self.create_button("venetian-mask.svg", "Роли", target_id="settings_roles")
        self.btn_audio = self.create_button("audio-lines.svg", "Звук", target_id="settings_audio")
        self.btn_live2d = self.create_button("user.svg", "Live2D", target_id="settings_live2d")
        self.btn_integrations = self.create_button("workflow.svg", "Интеграции", target_id="settings_integrations")
        self.btn_gui = self.create_button("palette.svg", "Интерфейс", target_id="settings_gui")

        self.layout.addStretch()

        # --- 4. Кнопка сворачивания ---
        self.toggle_btn = self.create_button("chevron-left.svg", "Свернуть", is_toggle_btn=True)
        self.toggle_btn.clicked.connect(self.toggle_sidebar)
        self.layout.addWidget(self.toggle_btn)

        # --- Подготовка анимации иконки ---
        self.toggle_base_pixmap = get_tinted_pixmap(os.path.join(self.icon_dir, "chevron-left.svg"), '#cad3f5')
        
        self.icon_anim = QVariantAnimation(self)
        self.icon_anim.setDuration(300) # Чуть увеличил время для большей заметности плавности (300 мс)
        
        # Задаем нелинейную кривую (плавный старт и плавная остановка)
        self.icon_anim.setEasingCurve(QEasingCurve.Type.InOutCubic) 
        
        self.icon_anim.valueChanged.connect(self.update_toggle_icon)

        # Принудительно выбираем Чат при старте
        self.btn_chat.setChecked(True)

    def create_button(self, icon_name: str, text: str, is_toggle_btn: bool = False, target_id: str = "") -> QPushButton:
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
            btn.full_text = f"  {text}"
            
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
        
        current_angle = self.icon_anim.currentValue() if self.icon_anim.state() == QVariantAnimation.State.Running else (180.0 if not self.is_collapsed else 0.0)

        if self.is_collapsed:
            self.setFixedWidth(64)
            for btn in self.nav_buttons:
                btn.setText("")
            self.toggle_btn.setText("")
            
            self.icon_anim.setStartValue(current_angle)
            self.icon_anim.setEndValue(180.0)
            self.icon_anim.start()
        else:
            self.setFixedWidth(240)
            for btn in self.nav_buttons:
                btn.setText(btn.full_text)
            self.toggle_btn.setText("  Свернуть")
            
            self.icon_anim.setStartValue(current_angle)
            self.icon_anim.setEndValue(0.0)
            self.icon_anim.start()
