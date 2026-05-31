import sys
import os
import getpass
import PySide6.QtSvg # Fixes PyInstaller SVG rendering bug
from PySide6.QtWidgets import QApplication
from gui.login_window import LoginWindow
from gui.main_window import MainWindow
import logger

# Global theme and language state
class AppState:
    is_dark_mode = False
    language = "EN"

app_state = AppState()

def change_theme(dark_mode):
    app_state.is_dark_mode = dark_mode
    from translations import TRANSLATIONS
    t = TRANSLATIONS.get(app_state.language, TRANSLATIONS["IT"])
    logger.info("log_theme_changed", t.get("theme_dark" if dark_mode else "theme_light"))
    # Emit a signal or directly update windows if needed
    # For now we'll just handle it within the windows

def change_language(lang):
    app_state.language = lang
    logger.set_log_language(lang)
    logger.info("log_lang_changed", lang)

def run():
    # Strip all CLI arguments: the exe accepts no external parameters.
    # This prevents Qt argument injection (-platform, -style, -plugin, etc.)
    sys.argv = sys.argv[:1]
    app = QApplication(sys.argv)

    # Enable CJK rendering in menu items and labels
    from PySide6.QtGui import QFont
    f = app.font()
    f.setFamilies(["Segoe UI", "Meiryo", "Yu Gothic", "Noto Sans CJK JP", "MS UI Gothic"])
    app.setFont(f)

    # Set global application icon
    from gui.top_bar import get_resource_path
    from PySide6.QtGui import QIcon, QPixmap, QPalette, QColor
    icon_path = get_resource_path("assets/logo-home.png")
    app.setWindowIcon(QIcon(QPixmap(icon_path)))

    # Replace the platform's default highlight (blue on Windows) with the
    # Claude fruity-orange palette across the whole application.  Per-widget
    # stylesheets can still override these defaults locally.
    try:
        pal = app.palette()
        orange       = QColor("#FF9248")
        orange_dark  = QColor("#A85C42")
        text_on_orange = QColor("#000000")
        for grp in (QPalette.Active, QPalette.Inactive, QPalette.Disabled):
            pal.setColor(grp, QPalette.Highlight,        orange)
            pal.setColor(grp, QPalette.HighlightedText,  text_on_orange)
            pal.setColor(grp, QPalette.Link,             orange_dark)
            pal.setColor(grp, QPalette.LinkVisited,      orange_dark)
        app.setPalette(pal)
        # Global stylesheet: anti-blue layer for selection / focus rings.
        # Per-widget stylesheets layer on top of this and override where needed.
        app.setStyleSheet(
            "* { selection-background-color:#FF9248; selection-color:black; }"
            "QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, "
            "QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus, "
            "QAbstractSpinBox:focus { border:2px solid #FF9248; }"
        )
    except Exception:
        # The orange palette is cosmetic — never block startup if Qt
        # complains about an unknown role on this build.
        pass
    
    logger.info("log_start")
    
    login = LoginWindow(app_state)
    
    def on_login_success():
        login.close()
        main_win = MainWindow(app_state)
        main_win.show()
        try:
            main_win.top_bar.set_logged_in(getpass.getuser())
        except Exception:
            pass
        app.main_win = main_win
        
    login.login_successful.connect(on_login_success)
    login.show()
    
    ret = app.exec()
    logger.info("log_exit")
    sys.exit(ret)

if __name__ == "__main__":
    run()
