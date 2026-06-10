import sys
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout,
                               QLabel, QLineEdit, QPushButton, QFrame)
from PySide6.QtCore import Qt, Signal, QPropertyAnimation, QPoint, QEasingCurve, QSequentialAnimationGroup, QTimer
from PySide6.QtGui import QIcon

from gui.top_bar import TopBar
from translations import TRANSLATIONS
import auth
import logger

class LoginWindow(QWidget):
    login_successful = Signal()

    def __init__(self, app_state):
        """Initialise the login window with the shared application state."""
        super().__init__()
        self.app_state = app_state
        # Source of truth for the counter is the persisted auth state, so the
        # number shown survives application restarts instead of resetting to 3.
        self.attempts_remaining = auth.attempts_remaining()
        self._locked = False

        # Ticks once a second while a lockout is active to update the countdown
        # and re-enable the form when the window elapses.
        self._lock_timer = QTimer(self)
        self._lock_timer.setInterval(1000)
        self._lock_timer.timeout.connect(self._tick_lockout)

        self.setWindowTitle(TRANSLATIONS[self.app_state.language]["title_login"])
        self.resize(1000, 600)
        self.setMinimumSize(1000, 600)

        self.setup_ui()
        self.apply_theme()
        self._apply_tooltips()
        self._refresh_lock_state()

    def setup_ui(self):
        """Build the login window's widgets (logo, password field, buttons, footer)."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Top Bar
        self.top_bar = TopBar(self.app_state)
        self.top_bar.theme_toggled.connect(self.on_theme_toggled)
        self.top_bar.language_changed.connect(self.on_language_changed)
        main_layout.addWidget(self.top_bar)
        
        # Content Area
        self.content_frame = QFrame()
        content_layout = QVBoxLayout(self.content_frame)
        content_layout.setContentsMargins(40, 40, 40, 20)
        
        # Center container to match the screenshot (bordered box)
        self.center_box = QFrame()
        self.center_box.setObjectName("CenterBox")
        box_layout = QVBoxLayout(self.center_box)
        box_layout.setContentsMargins(40, 40, 40, 40)
        box_layout.setSpacing(20)
        box_layout.setAlignment(Qt.AlignCenter)
        
        # Password Prompt
        self.lbl_prompt = QLabel(TRANSLATIONS[self.app_state.language]["password_prompt"])
        self.lbl_prompt.setAlignment(Qt.AlignCenter)
        self.lbl_prompt.setStyleSheet("font-size: 18px;")
        box_layout.addWidget(self.lbl_prompt)
        
        # Password Input
        self.txt_password = QLineEdit()
        self.txt_password.setObjectName("txt_password")
        self.txt_password.setEchoMode(QLineEdit.Password)
        self.txt_password.setAlignment(Qt.AlignCenter)
        self.txt_password.setFixedHeight(40)
        self.txt_password.setStyleSheet("font-size: 18px;")
        self.txt_password.returnPressed.connect(self.attempt_login)
        box_layout.addWidget(self.txt_password)
        
        # Attempts remaining
        self.lbl_attempts = QLabel(TRANSLATIONS[self.app_state.language]["attempts"].format(self.attempts_remaining))
        self.lbl_attempts.setAlignment(Qt.AlignCenter)
        box_layout.addWidget(self.lbl_attempts)
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)
        
        self.btn_login = QPushButton(TRANSLATIONS[self.app_state.language]["btn_login"])
        self.btn_login.setObjectName("btn_login")
        self.btn_login.setFixedHeight(40)
        self.btn_login.setCursor(Qt.PointingHandCursor)
        self.btn_login.clicked.connect(lambda: logger.info("log_btn_pressed", self.btn_login.text()))
        self.btn_login.clicked.connect(self.attempt_login)
        btn_layout.addWidget(self.btn_login)

        self.btn_exit = QPushButton(TRANSLATIONS[self.app_state.language]["btn_exit"])
        self.btn_exit.setObjectName("btn_exit")
        self.btn_exit.setFixedHeight(40)
        self.btn_exit.setCursor(Qt.PointingHandCursor)
        self.btn_exit.clicked.connect(lambda: logger.info("log_btn_pressed", self.btn_exit.text()))
        self.btn_exit.clicked.connect(self.close)
        btn_layout.addWidget(self.btn_exit)
        
        box_layout.addLayout(btn_layout)
        
        # Footer inside center box to align properly
        self.lbl_footer = QLabel("v1.1.6 build 2 — Creator 0THack1A")
        self.lbl_footer.setAlignment(Qt.AlignCenter)
        self.lbl_footer.setStyleSheet("color: gray; margin-top: 20px;")
        box_layout.addWidget(self.lbl_footer)
        
        content_layout.addWidget(self.center_box)
        main_layout.addWidget(self.content_frame)

    def apply_theme(self):
        """Apply the current light/dark theme styling to the login window."""
        if self.app_state.is_dark_mode:
            # Dark theme
            self.setStyleSheet("background-color: #231811; color: white;")
            self.center_box.setStyleSheet("""
                QFrame#CenterBox {
                    border: 1px solid #5C4938;
                    background-color: #3A2D26;
                }
            """)
            self.txt_password.setStyleSheet("""
                QLineEdit {
                    border: 2px solid #D97757;
                    background-color: #231811;
                    color: white;
                    font-size: 18px;
                }
            """)
            self.btn_login.setStyleSheet("""
                QPushButton {
                    background-color: #D97757;
                    color: white;
                    border: none;
                    font-size: 16px;
                    font-weight: bold;
                }
                QPushButton:hover { background-color: #A85C42; }
            """)
            self.btn_exit.setStyleSheet("""
                QPushButton {
                    background-color: #5C4938;
                    color: white;
                    border: none;
                    font-size: 16px;
                }
                QPushButton:hover { background-color: #3A2D26; }
            """)
        else:
            # Light theme
            self.setStyleSheet("background-color: #f0f0f0; color: #333;")
            self.center_box.setStyleSheet("""
                QFrame#CenterBox {
                    border: 1px solid #ccc;
                    background-color: white;
                }
            """)
            self.txt_password.setStyleSheet("""
                QLineEdit {
                    border: 2px solid #D97757;
                    background-color: white;
                    color: black;
                    font-size: 18px;
                }
            """)
            self.btn_login.setStyleSheet("""
                QPushButton {
                    background-color: #D97757;
                    color: white;
                    border: none;
                    font-size: 16px;
                    font-weight: bold;
                }
                QPushButton:hover { background-color: #A85C42; }
            """)
            self.btn_exit.setStyleSheet("""
                QPushButton {
                    background-color: #d0d0d0;
                    color: black;
                    border: none;
                    font-size: 16px;
                }
                QPushButton:hover { background-color: #b0b0b0; }
            """)

    def showEvent(self, event):
        """On show, reflect any active lockout and move focus to the password field."""
        super().showEvent(event)
        self._refresh_lock_state()
        try:
            if not self._locked:
                QTimer.singleShot(0, self.txt_password.setFocus)
        except Exception:
            pass

    def on_theme_toggled(self, is_dark):
        """Handle the theme toggle: restyle the window and log the change."""
        self.apply_theme()
        t = TRANSLATIONS[self.app_state.language]
        theme_name = t["theme_dark"] if is_dark else t["theme_light"]
        logger.info("log_theme_changed", theme_name)

    def on_language_changed(self, lang):
        """Handle a language change: re-translate the window's labels."""
        t = TRANSLATIONS[lang]
        logger.set_log_language(lang)
        logger.info("log_lang_changed", lang)
        self.setWindowTitle(t["title_login"])
        self.lbl_prompt.setText(t["password_prompt"])
        self._render_status_label()
        self.btn_login.setText(t["btn_login"])
        self.btn_exit.setText(t["btn_exit"])
        self._apply_tooltips()

    def _apply_tooltips(self):
        """Set descriptive tooltips on login fields in the current language."""
        try:
            import tooltips as _tips
            lang = getattr(self.app_state, "language", "IT")
            self.txt_password.setToolTip(_tips.get("txt_password", lang))
            self.btn_login.setToolTip(_tips.get("btn_login", lang))
            self.btn_exit.setToolTip(_tips.get("btn_exit", lang))
        except Exception:
            pass

    def attempt_login(self):
        # Persistent lockout: a restart no longer resets the failure counter,
        # so an attacker that hit the threshold must wait the cooldown out
        # regardless of how many times the app is relaunched.  A failed or
        # locked-out attempt no longer closes the application — it shows a
        # clear, self-healing countdown — so the lockout can never be mistaken
        # for a crash.
        """Verify the entered password; on success emit login, otherwise count the failure and lock out (without quitting) at the limit."""
        if auth.lockout_remaining_seconds() > 0:
            self._enter_lockout()
            return

        password = self.txt_password.text()

        if auth.verify_password(password):
            self.app_state.login_attempts = auth._MAX_ATTEMPTS - self.attempts_remaining + 1
            auth.record_success()
            logger.info("log_login_success")
            self._lock_timer.stop()
            self.login_successful.emit()
        else:
            auth.record_failure()
            self.attempts_remaining = auth.attempts_remaining()
            logger.warning("log_login_failed", self.attempts_remaining)

            if auth.lockout_remaining_seconds() > 0:
                # Threshold reached → arm the visible countdown, but keep the
                # window open so the user can retry once it expires.
                logger.error("log_max_attempts")
                self._enter_lockout()
            else:
                self.txt_password.clear()
                self._render_status_label()
                self.vibrate()

    # ── Lockout presentation ──────────────────────────────────────────────────
    @staticmethod
    def _fmt_remaining(secs):
        """Format a seconds count as ``m:ss`` for the countdown label."""
        m, s = divmod(max(0, int(secs)), 60)
        return f"{m}:{s:02d}"

    def _render_status_label(self):
        """Show either the lockout countdown or the remaining-attempts count."""
        t = TRANSLATIONS[self.app_state.language]
        secs = auth.lockout_remaining_seconds()
        if secs > 0:
            self.lbl_attempts.setText(t["locked_retry"].format(self._fmt_remaining(secs)))
        else:
            self.lbl_attempts.setText(t["attempts"].format(self.attempts_remaining))

    def _enter_lockout(self):
        """Disable the form and show a live countdown until the lockout expires."""
        self._locked = True
        self.txt_password.clear()
        self.txt_password.setEnabled(False)
        self.btn_login.setEnabled(False)
        self._render_status_label()
        if not self._lock_timer.isActive():
            self._lock_timer.start()
        if self.isVisible():
            self.vibrate()

    def _tick_lockout(self):
        """Per-second tick: refresh the countdown or release the lockout."""
        if auth.lockout_remaining_seconds() > 0:
            self._render_status_label()
        else:
            self._lock_timer.stop()
            self._exit_lockout()

    def _exit_lockout(self):
        """Re-enable the form once the lockout window has elapsed."""
        self._locked = False
        self.attempts_remaining = auth.attempts_remaining()
        self.txt_password.setEnabled(True)
        self.btn_login.setEnabled(True)
        self._render_status_label()
        try:
            self.txt_password.setFocus()
        except Exception:
            pass

    def _refresh_lock_state(self):
        """Reflect any persisted lockout on launch/show instead of letting the user type into a form that would otherwise close the app."""
        if auth.lockout_remaining_seconds() > 0:
            self._enter_lockout()
        else:
            if self._locked:
                self._exit_lockout()
            else:
                self.attempts_remaining = auth.attempts_remaining()
                self._render_status_label()

    def closeEvent(self, event):
        """Handle the window close event (default behaviour)."""
        super().closeEvent(event)

    def vibrate(self):
        """Shake the window briefly to signal a failed login."""
        self.animation_group = QSequentialAnimationGroup()
        
        # Save original geometry
        geo = self.geometry()
        x, y = geo.x(), geo.y()
        
        # Create small shifts left and right
        offsets = [10, -10, 10, -10, 5, -5, 0]
        
        for offset in offsets:
            anim = QPropertyAnimation(self, b"pos")
            anim.setDuration(40)
            anim.setStartValue(QPoint(x, y))
            anim.setEndValue(QPoint(x + offset, y))
            self.animation_group.addAnimation(anim)
            # update x for next start value
            x += offset
            
        self.animation_group.start()
