
import os
import sys
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QPushButton, QSizePolicy
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QPixmap, QIcon, QFont
from translations import TRANSLATIONS
import logger

def get_resource_path(relative_path):
    """Resolve a resource path, working both in development and in a PyInstaller bundle."""
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), relative_path)

class TopBar(QWidget):
    theme_toggled = Signal(bool)
    language_changed = Signal(str)

    # Claude orange palette for light/dark themes
    _ORANGE_LIGHT = "#D97757"
    _ORANGE_DARK  = "#8A4533"   # darker tone for dark mode

    def __init__(self, app_state, parent=None):
        """Build the top bar: logo, title, theme toggle, and language buttons."""
        super().__init__(parent)
        self.app_state = app_state
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setFixedHeight(80)
        self._apply_bar_theme()
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 10, 20, 10)
        layout.setSpacing(15)
        
        # Logo — try png → bmp → svg in order
        self.logo_label = QLabel()
        pixmap = QPixmap()
        for _ext in ("assets/logo-home.png", "assets/logo-home.bmp", "assets/logo-home.svg"):
            _p = get_resource_path(_ext)
            pixmap = QPixmap(_p)
            if not pixmap.isNull():
                break
        if not pixmap.isNull():
            pixmap = pixmap.scaledToHeight(55, Qt.SmoothTransformation)
            self.logo_label.setPixmap(pixmap)
        else:
            self.logo_label.setText("0THack1A")
            self.logo_label.setStyleSheet("font-weight: bold; font-size: 20px;")
        
        layout.addWidget(self.logo_label)
        
        # Title
        self.title_label = QLabel(TRANSLATIONS[self.app_state.language]["title_main"])
        self.title_label.setStyleSheet("font-size: 16px; font-weight: 700; font-family: 'Inter', sans-serif; margin-left: 15px;")
        layout.addWidget(self.title_label)
        
        # Subtitle (e.g. Accesso)
        self.subtitle_label = QLabel(TRANSLATIONS[self.app_state.language]["top_bar_login"])
        self.subtitle_label.setStyleSheet("font-size: 16px; font-weight: 300; margin-top: 5px;")
        layout.addWidget(self.subtitle_label)
        
        layout.addStretch()
        
        # Theme toggle button
        self.theme_btn = QPushButton("🌙" if not self.app_state.is_dark_mode else "☀")
        self.theme_btn.setFixedSize(45, 45)
        self.theme_btn.setCursor(Qt.PointingHandCursor)
        # Mouse-only: keep the bar's buttons out of the keyboard focus chain so
        # Tab/arrow navigation can never toggle the theme accidentally.
        self.theme_btn.setFocusPolicy(Qt.NoFocus)
        self.theme_btn.setStyleSheet("""
            QPushButton {
                border: 2px solid rgba(255, 255, 255, 0.8);
                border-radius: 22px;
                color: white;
                font-size: 22px;
                background-color: transparent;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.2);
                border: 2px solid white;
            }
        """)
        self.theme_btn.clicked.connect(self.toggle_theme)
        layout.addWidget(self.theme_btn)
        self._refresh_theme_tooltip()

        # Separator
        sep = QLabel("|")
        sep.setStyleSheet("font-size: 24px; color: rgba(255, 255, 255, 0.5); margin: 0 5px;")
        layout.addWidget(sep)

        # Language buttons
        _LANG_NAMES = {
            "IT": "Italiano", "EN": "English", "FR": "Français",
            "DE": "Deutsch",  "ES": "Español", "UA": "Українська", "JA": "日本語",
        }
        self.lang_buttons = {}
        for lang in ["IT", "EN", "FR", "DE", "ES", "UA", "JA"]:
            btn = QPushButton(lang)
            btn.setFixedSize(45, 45)
            btn.setCursor(Qt.PointingHandCursor)
            # Mouse-only: arrow keys between sibling buttons would otherwise
            # switch the UI language without any confirmation (see v1.1.7 QA).
            btn.setFocusPolicy(Qt.NoFocus)
            btn.setToolTip(_LANG_NAMES.get(lang, lang))
            btn.clicked.connect(lambda checked, l=lang: self.set_language(l))
            layout.addWidget(btn)
            self.lang_buttons[lang] = btn

        self._logged_in_user = None
        self.update_ui()

    def _apply_bar_theme(self):
        """Apply the appropriate orange variant for the current theme."""
        is_dark = bool(getattr(self.app_state, "is_dark_mode", False))
        bg = self._ORANGE_DARK if is_dark else self._ORANGE_LIGHT
        self.setStyleSheet(f"background-color: {bg}; color: white; border: none;")

    def toggle_theme(self):
        """Toggle between light and dark theme and notify the application."""
        self.app_state.is_dark_mode = not self.app_state.is_dark_mode
        self.theme_btn.setText("🌙" if not self.app_state.is_dark_mode else "☀")
        self._apply_bar_theme()
        self.update_ui()
        self._refresh_theme_tooltip()
        self.theme_toggled.emit(self.app_state.is_dark_mode)

    def _refresh_theme_tooltip(self):
        """Update the theme button's tooltip to match the current theme."""
        try:
            t = TRANSLATIONS.get(self.app_state.language, TRANSLATIONS["IT"])
            if self.app_state.is_dark_mode:
                self.theme_btn.setToolTip(t.get("theme_light", "Tema chiaro"))
            else:
                self.theme_btn.setToolTip(t.get("theme_dark", "Tema scuro"))
        except Exception:
            pass

    def set_language(self, lang):
        """Switch the active language and refresh the bar's labels."""
        if lang not in TRANSLATIONS:
            return
        if self.app_state.language != lang:
            self.app_state.language = lang
            self.update_ui()
            self.language_changed.emit(lang)

    def set_logged_in(self, username):
        """Display the given username as the logged-in user."""
        self._logged_in_user = username
        self.subtitle_label.setText(username or "")

    def update_ui(self):
        """Refresh the bar's texts and styling for the current language and theme."""
        is_dark = bool(getattr(self.app_state, "is_dark_mode", False))
        active_text = self._ORANGE_DARK if is_dark else self._ORANGE_LIGHT
        for lang, btn in self.lang_buttons.items():
            if lang == self.app_state.language:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        border: 2px solid white;
                        border-radius: 22px;
                        background-color: white;
                        color: {active_text};
                        font-weight: bold;
                        font-size: 14px;
                    }}
                """)
            else:
                btn.setStyleSheet("""
                    QPushButton {
                        border: 2px solid rgba(255, 255, 255, 0.6);
                        border-radius: 22px;
                        background-color: transparent;
                        color: white;
                        font-weight: bold;
                        font-size: 14px;
                    }
                    QPushButton:hover {
                        background-color: rgba(255, 255, 255, 0.2);
                        border: 2px solid white;
                    }
                """)

        t = TRANSLATIONS.get(self.app_state.language, TRANSLATIONS["IT"])
        if self._logged_in_user:
            self.subtitle_label.setText(self._logged_in_user)
        else:
            self.subtitle_label.setText(t["top_bar_login"])
        self.title_label.setText(t["title_main"])
