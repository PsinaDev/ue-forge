"""
Console output widget with syntax highlighting.
"""
import re
import random
import math
from typing import Optional, List
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPlainTextEdit,
    QPushButton,
    QLabel,
    QFrame,
    QApplication,
    QGraphicsOpacityEffect,
)
from PySide6.QtCore import (
    Qt, QTimer, Slot, QPropertyAnimation, 
    QEasingCurve, Property, QPoint, QPointF, QRectF,
)
from PySide6.QtGui import (
    QTextCharFormat,
    QColor,
    QFont,
    QSyntaxHighlighter,
    QTextDocument,
    QPainter,
    QPainterPath,
    QScreen,
)

from framekit.styles import COLORS, FONTS, RADIUS
from framekit.icons import Icons
from framekit.localization import tr
from framekit.types import LogLevel, LogMessage


# Combo messages for copy easter egg
COMBO_MESSAGES = [
    "combo_copy_0",   # Скопировано!
    "combo_copy_1",   # Двойное копирование!
    "combo_copy_2",   # Тройное копирование!
    "combo_copy_3",   # Комбо копирование!
    "combo_copy_4",   # Мега копирование!
    "combo_copy_5",   # Супер копирование!
    "combo_copy_6",   # Ультра копирование!
    "combo_copy_7",   # ГИГА копирование!!!
    "combo_copy_8",   # ☆ ЛЕГЕНДАРНОЕ ☆
    "combo_copy_9",   # ✦ БОЖЕСТВЕННОЕ ✦
    "combo_copy_10",  # ⚡ КОСМИЧЕСКОЕ ⚡
    "combo_copy_11",  # 🔥 АПОКАЛИПСИС 🔥
]

# Post-limit messages (after max combo reached)
POST_LIMIT_MESSAGES = [
    "combo_post_0",   # Может уже хватит?
    "combo_post_1",   # Серьёзно, прекрати
    "combo_post_2",   # Последнее предупреждение!
    "combo_post_3",   # Кнопка будет отобрана через...
]


class ConfettiParticle:
    """A single confetti particle."""
    
    def __init__(self, x: float, y: float):
        self.x = x
        self.y = y
        self.vx = random.uniform(-8, 8)
        self.vy = random.uniform(-15, -8)
        self.rotation = random.uniform(0, 360)
        self.rotation_speed = random.uniform(-10, 10)
        self.size = random.uniform(6, 12)
        self.color = QColor(random.choice([
            "#22d3ee",  # cyan
            "#f472b6",  # pink
            "#a78bfa",  # purple
            "#34d399",  # green
            "#fbbf24",  # yellow
            "#f87171",  # red
            "#60a5fa",  # blue
        ]))
        self.gravity = 0.4
        self.drag = 0.98
        self.life = 1.0
        self.decay = random.uniform(0.008, 0.015)
        # Shape: 0 = rect, 1 = circle, 2 = star
        self.shape = random.randint(0, 2)
    
    def update(self) -> bool:
        """Update particle position. Returns False if particle is dead."""
        self.vy += self.gravity
        self.vx *= self.drag
        self.x += self.vx
        self.y += self.vy
        self.rotation += self.rotation_speed
        self.life -= self.decay
        return self.life > 0
    
    def draw(self, painter: QPainter) -> None:
        """Draw the particle."""
        if self.life <= 0:
            return
        
        painter.save()
        painter.translate(self.x, self.y)
        painter.rotate(self.rotation)
        
        color = QColor(self.color)
        color.setAlphaF(min(1.0, self.life * 2))
        painter.setBrush(color)
        painter.setPen(Qt.PenStyle.NoPen)
        
        half = self.size / 2
        
        if self.shape == 0:
            # Rectangle
            painter.drawRect(QRectF(-half, -half/2, self.size, self.size/2))
        elif self.shape == 1:
            # Circle
            painter.drawEllipse(QPointF(0, 0), half, half)
        else:
            # Star
            path = QPainterPath()
            for i in range(5):
                angle = math.radians(i * 72 - 90)
                outer = QPointF(math.cos(angle) * half, math.sin(angle) * half)
                inner_angle = math.radians(i * 72 - 90 + 36)
                inner = QPointF(math.cos(inner_angle) * half * 0.4, 
                               math.sin(inner_angle) * half * 0.4)
                if i == 0:
                    path.moveTo(outer)
                else:
                    path.lineTo(outer)
                path.lineTo(inner)
            path.closeSubpath()
            painter.drawPath(path)
        
        painter.restore()


class ConfettiWidget(QWidget):
    """Transparent overlay widget for confetti animation."""
    
    def __init__(self):
        super().__init__(None)
        
        # Make it a transparent overlay
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool |
            Qt.WindowType.WindowTransparentForInput
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        
        self.particles: List[ConfettiParticle] = []
        
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._update_particles)
        self._timer.setInterval(16)  # ~60 FPS
    
    def launch(self, global_pos: QPoint) -> None:
        """Launch confetti from a global screen position."""
        # Get the screen containing the point
        screen = QApplication.screenAt(global_pos)
        if not screen:
            screen = QApplication.primaryScreen()
        
        screen_geo = screen.geometry()
        self.setGeometry(screen_geo)
        
        # Convert global pos to local
        local_x = global_pos.x() - screen_geo.x()
        local_y = global_pos.y() - screen_geo.y()
        
        # Create particles
        for _ in range(80):
            self.particles.append(ConfettiParticle(local_x, local_y))
        
        self.show()
        self._timer.start()
    
    def _update_particles(self) -> None:
        """Update all particles."""
        self.particles = [p for p in self.particles if p.update()]
        
        if not self.particles:
            self._timer.stop()
            self.hide()
        else:
            self.update()
    
    def paintEvent(self, event) -> None:
        """Paint all particles."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        for particle in self.particles:
            particle.draw(painter)


class ConsoleHighlighter(QSyntaxHighlighter):
    """
    UE-aware syntax highlighter for console output.

    Processes each text block once, applying formats in priority order.
    Runs incrementally — only re-highlights visible/changed blocks.
    """

    def __init__(self, document: QTextDocument):
        super().__init__(document)

        # Pre-compile all rules: (regex, format) — applied in order
        self._rules: List[tuple] = []

        # --- Dim noise: timestamps, frame numbers ---
        dim_fmt = QTextCharFormat()
        dim_fmt.setForeground(QColor("#52525b"))
        # UE timestamp [YYYY.MM.DD-HH.MM.SS:mmm]
        self._rules.append((re.compile(r'\[\d{4}\.\d{2}\.\d{2}-[\d.]+:\d+\]'), dim_fmt))
        # Frame number [ N]
        self._rules.append((re.compile(r'\[\s*\d+\]'), dim_fmt))
        # Verbosity tags: Display:, Verbose:, VeryVerbose:
        self._rules.append((re.compile(r'\b(?:Display|Verbose|VeryVerbose):'), dim_fmt))
        # Asset paths (/Game/...) or (C:\...)
        self._rules.append((re.compile(r'\(/Game/[^)]+\)'), dim_fmt))
        self._rules.append((re.compile(r'\([A-Z]:\\[^)]+\)'), dim_fmt))

        # --- Log categories: PascalCase word + colon after ] ---
        cat_fmt = QTextCharFormat()
        cat_fmt.setForeground(QColor("#60a5fa"))  # blue
        self._rules.append((re.compile(r'(?<=\])[A-Z]\w+(?=:)'), cat_fmt))
        # Also standalone categories at line start
        self._rules.append((re.compile(r'^[A-Z]\w+(?=:)'), cat_fmt))

        # --- Our prefix tags ---
        tag_success = QTextCharFormat()
        tag_success.setForeground(QColor(COLORS['success']))
        tag_success.setFontWeight(QFont.Bold)
        self._rules.append((re.compile(r'\[SUCCESS\]'), tag_success))

        tag_error = QTextCharFormat()
        tag_error.setForeground(QColor(COLORS['error']))
        tag_error.setFontWeight(QFont.Bold)
        self._rules.append((re.compile(r'\[ERROR\]'), tag_error))

        tag_warning = QTextCharFormat()
        tag_warning.setForeground(QColor(COLORS['warning']))
        tag_warning.setFontWeight(QFont.Bold)
        self._rules.append((re.compile(r'\[WARNING\]'), tag_warning))

        tag_info = QTextCharFormat()
        tag_info.setForeground(QColor(COLORS['accent_primary']))
        tag_info.setFontWeight(QFont.Bold)
        self._rules.append((re.compile(r'\[INFO\]'), tag_info))

        # --- Progress counters ---
        progress_fmt = QTextCharFormat()
        progress_fmt.setForeground(QColor(COLORS['accent_primary']))
        progress_fmt.setFontWeight(QFont.Bold)
        self._rules.append((re.compile(r'\[\d+[,/]\d+\]'), progress_fmt))
        self._rules.append((re.compile(r'\b\d+%\b'), progress_fmt))

        # --- Timing: [in N ms] ---
        time_fmt = QTextCharFormat()
        time_fmt.setForeground(QColor(COLORS['success']))
        self._rules.append((re.compile(r'\[in\s+\d+(?:\.\d+)?\s*(?:ms|s)\]'), time_fmt))

        # --- Success keywords ---
        ok_fmt = QTextCharFormat()
        ok_fmt.setForeground(QColor(COLORS['success']))
        ok_fmt.setFontWeight(QFont.Bold)
        self._rules.append((re.compile(r'(?i)\bsuccessful!?\b'), ok_fmt))
        self._rules.append((re.compile(r'(?i)\b(?:succeeded|completed|finished|done)\b'), ok_fmt))

        # --- Error keywords ---
        err_fmt = QTextCharFormat()
        err_fmt.setForeground(QColor(COLORS['error']))
        err_fmt.setFontWeight(QFont.Bold)
        self._rules.append((re.compile(r'(?i)\b(?:error|failed|failure|fatal|crash(?:ed)?)\b'), err_fmt))
        self._rules.append((re.compile(r'\bLNK\d+\b'), err_fmt))
        self._rules.append((re.compile(r'\bC\d{4}\b'), err_fmt))
        # UE verbosity Error:/Fatal:
        self._rules.append((re.compile(r'\b(?:Error|Fatal):'), err_fmt))

        # --- Warning keywords ---
        warn_fmt = QTextCharFormat()
        warn_fmt.setForeground(QColor(COLORS['warning']))
        self._rules.append((re.compile(r'(?i)\bwarning\b'), warn_fmt))
        self._rules.append((re.compile(r'(?i)\bdeprecated\b'), warn_fmt))
        self._rules.append((re.compile(r'\bWarning:'), warn_fmt))

        # --- Action keywords: cyan ---
        action_fmt = QTextCharFormat()
        action_fmt.setForeground(QColor(COLORS['accent_primary']))
        self._rules.append((re.compile(
            r'\b(?:Loading|Compiling|Compile|Saving|Processing|'
            r'Scanning|Starting|Cooking|Building|Packaging|Initializing)\b'
        ), action_fmt))

        # --- Command-line args: -Flag or -Param=Value ---
        arg_fmt = QTextCharFormat()
        arg_fmt.setForeground(QColor(COLORS['accent_primary']))
        self._rules.append((re.compile(r'(?<=\s)-[A-Za-z_]\w*(?:=[^\s]*)?'), arg_fmt))

    def highlightBlock(self, text: str) -> None:
        """Apply highlighting rules to a single text block."""
        for pattern, fmt in self._rules:
            for match in pattern.finditer(text):
                self.setFormat(match.start(), match.end() - match.start(), fmt)


class CopiedTooltip(QLabel):
    """Animated 'Copied!' tooltip with combo support."""
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(tr("copied"), parent)
        self._base_style = """
            QLabel {{
                background-color: {bg};
                color: {fg};
                font-size: {size};
                font-weight: 600;
                padding: 4px 10px;
                border-radius: 6px;
            }}
        """
        self._set_style(COLORS['success'], COLORS['bg_primary'], FONTS['size_xs'])
        self.setAlignment(Qt.AlignCenter)
        self.hide()
        
        # Opacity effect
        self._opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._opacity_effect)
        self._opacity_effect.setOpacity(1.0)
        
        # Animation
        self._animation = QPropertyAnimation(self._opacity_effect, b"opacity")
        self._animation.setDuration(300)
        self._animation.setEasingCurve(QEasingCurve.OutCubic)
        self._animation.finished.connect(self._on_animation_finished)
        
        # Hide timer
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self._start_fade_out)
    
    def _set_style(self, bg: str, fg: str, size: str) -> None:
        """Set the tooltip style."""
        self.setStyleSheet(self._base_style.format(bg=bg, fg=fg, size=size))
    
    def show_at(self, anchor_right: int, anchor_y: int, text: str = None, combo_level: int = 0) -> None:
        """
        Show tooltip anchored by its RIGHT edge.
        
        Args:
            anchor_right: X position where the RIGHT edge of tooltip should be
            anchor_y: Y position (center)
            text: Text to display
            combo_level: Combo level for styling (negative = special styles)
        """
        if text:
            self.setText(text)
        
        # Style based on combo level
        if combo_level == -3:
            # Final - button gone
            self._set_style("#ef4444", "#000000", "14px")  # Red with black text
        elif combo_level == -2:
            # Countdown
            self._set_style("#f97316", "#000000", "16px")  # Orange with black text
        elif combo_level == -1:
            # Warning messages
            self._set_style("#ef4444", "#000000", "12px")  # Red with black text
        elif combo_level >= 10:
            self._set_style("#f472b6", "#000000", "14px")  # Pink - legendary
        elif combo_level >= 7:
            self._set_style("#a78bfa", "#000000", "13px")  # Purple - epic
        elif combo_level >= 5:
            self._set_style("#fbbf24", "#000000", "13px")  # Gold - rare
        elif combo_level >= 3:
            self._set_style("#22d3ee", "#000000", "12px")  # Cyan - combo
        else:
            self._set_style(COLORS['success'], COLORS['bg_primary'], FONTS['size_xs'])
        
        # IMPORTANT: adjustSize AFTER setting text and style
        self.adjustSize()
        
        # Position so RIGHT edge is at anchor_right
        tooltip_width = self.width()
        tooltip_height = self.height()
        
        pos = QPoint(
            anchor_right - tooltip_width,  # Right edge aligned
            anchor_y - tooltip_height // 2  # Vertically centered
        )
        
        self.move(pos)
        self._opacity_effect.setOpacity(1.0)
        self.show()
        self.raise_()
        
        # Longer display for higher combos, shorter for warnings
        if combo_level < 0:
            display_time = 800
        else:
            display_time = 1000 + (combo_level * 200)
        self._hide_timer.start(min(display_time, 3000))
    
    def _start_fade_out(self) -> None:
        """Start fade out animation."""
        self._animation.setStartValue(1.0)
        self._animation.setEndValue(0.0)
        self._animation.start()
    
    def _on_animation_finished(self) -> None:
        """Hide when animation finishes."""
        if self._opacity_effect.opacity() < 0.1:
            self.hide()


class ConsoleWidget(QWidget):
    """
    Console output widget with header and controls.

    Uses QPlainTextEdit + QSyntaxHighlighter for fast incremental
    rendering.  Line cap prevents unbounded memory growth.

    Features:
    - Smart auto-scroll: pauses when user scrolls up, resumes when at bottom
    - Search with highlighting: Ctrl+F or search button
    - Copy respects search filter
    """

    # Combo timeout in milliseconds
    COMBO_TIMEOUT = 800
    # Combo level that triggers confetti
    CONFETTI_THRESHOLD = 8
    # Max combo level before post-limit messages
    MAX_COMBO = len(COMBO_MESSAGES) - 1
    # How many times to repeat last combo message
    REPEAT_LAST_COMBO = 3
    # Countdown start value
    COUNTDOWN_START = 3
    # Max lines kept in console (trim oldest on overflow)
    MAX_LINES = 5000

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._buffer: List[str] = []
        self._buffer_timer: Optional[QTimer] = None
        self._line_count: int = 0

        # Smart auto-scroll: True when user is at or near bottom
        self._auto_scroll = True
        # Search state
        self._search_text = ""
        self._search_matches: List[int] = []  # List of block numbers with matches
        self._current_match_index = -1

        # Combo tracking
        self._combo_count = 0
        self._post_limit_count = 0
        self._countdown_value = 0
        self._button_hidden = False

        self._combo_timer = QTimer(self)
        self._combo_timer.setSingleShot(True)
        self._combo_timer.timeout.connect(self._reset_combo)

        # Confetti overlay (lazy init)
        self._confetti: Optional[ConfettiWidget] = None

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        header = QFrame()
        header.setStyleSheet(f"""
            QFrame {{
                background-color: rgba(24, 24, 27, 0.5);
                border: none;
                border-bottom: 1px solid {COLORS['border_default']};
            }}
        """)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(16, 8, 16, 8)
        header_layout.setSpacing(8)

        # Title
        title = QLabel(tr("console_output"))
        title.setStyleSheet(f"""
            color: {COLORS['text_muted']};
            font-size: {FONTS['size_sm']};
            font-weight: 500;
            background: transparent;
        """)
        header_layout.addWidget(title)

        header_layout.addStretch()

        _hdr_btn_style = f"""
            QPushButton {{
                background: transparent;
                border: none;
                border-radius: 4px;
            }}
            QPushButton:hover {{
                background-color: {COLORS['bg_tertiary']};
            }}
        """

        # Search button
        self._search_btn = QPushButton()
        self._search_btn.setIcon(Icons.get_icon("SEARCH", 14, COLORS['text_dim']))
        self._search_btn.setFixedSize(28, 24)
        self._search_btn.setToolTip(tr("search_console"))
        self._search_btn.setStyleSheet(_hdr_btn_style)
        self._search_btn.clicked.connect(self._toggle_search)
        self._search_btn.setCursor(Qt.PointingHandCursor)
        header_layout.addWidget(self._search_btn)

        # Clear button
        self._clear_btn = QPushButton()
        self._clear_btn.setIcon(Icons.get_icon("TRASH_2", 14, COLORS['text_dim']))
        self._clear_btn.setFixedSize(28, 24)
        self._clear_btn.setToolTip(tr("clear_console"))
        self._clear_btn.setStyleSheet(_hdr_btn_style)
        self._clear_btn.clicked.connect(self.clear)
        self._clear_btn.setCursor(Qt.PointingHandCursor)
        header_layout.addWidget(self._clear_btn)

        # Copy button
        self._copy_btn = QPushButton()
        self._copy_btn.setIcon(Icons.get_icon("COPY", 14, COLORS['text_dim']))
        self._copy_btn.setFixedSize(28, 24)
        self._copy_btn.setToolTip(tr("copy_tooltip"))
        self._copy_btn.setStyleSheet(_hdr_btn_style)
        self._copy_btn.clicked.connect(self._copy_to_clipboard)
        self._copy_btn.setCursor(Qt.PointingHandCursor)
        header_layout.addWidget(self._copy_btn)

        layout.addWidget(header)

        # Search bar (hidden by default)
        self._search_bar = QFrame()
        self._search_bar.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['bg_secondary']};
                border: none;
                border-bottom: 1px solid {COLORS['border_default']};
            }}
        """)
        self._search_bar.setVisible(False)
        search_layout = QHBoxLayout(self._search_bar)
        search_layout.setContentsMargins(16, 6, 16, 6)
        search_layout.setSpacing(8)

        # Search input
        from PySide6.QtWidgets import QLineEdit
        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText(tr("search_placeholder"))
        self._search_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: {COLORS['bg_tertiary']};
                border: 1px solid {COLORS['border_default']};
                border-radius: 4px;
                padding: 4px 8px;
                color: {COLORS['text_primary']};
                font-size: {FONTS['size_sm']};
            }}
            QLineEdit:focus {{
                border-color: {COLORS['accent_primary']};
            }}
        """)
        self._search_input.textChanged.connect(self._on_search_changed)
        self._search_input.returnPressed.connect(self._find_next)
        search_layout.addWidget(self._search_input, 1)

        # Match count label
        self._match_label = QLabel()
        self._match_label.setStyleSheet(f"""
            color: {COLORS['text_dim']};
            font-size: {FONTS['size_xs']};
            background: transparent;
        """)
        search_layout.addWidget(self._match_label)

        # Navigation buttons
        _nav_btn_style = f"""
            QPushButton {{
                background: transparent;
                border: none;
                border-radius: 4px;
                padding: 2px;
            }}
            QPushButton:hover {{
                background-color: {COLORS['bg_tertiary']};
            }}
            QPushButton:disabled {{
                opacity: 0.3;
            }}
        """

        self._prev_btn = QPushButton()
        self._prev_btn.setIcon(Icons.get_icon("CHEVRON_UP", 14, COLORS['text_dim']))
        self._prev_btn.setFixedSize(24, 24)
        self._prev_btn.setToolTip(tr("previous_match"))
        self._prev_btn.setStyleSheet(_nav_btn_style)
        self._prev_btn.clicked.connect(self._find_prev)
        self._prev_btn.setCursor(Qt.PointingHandCursor)
        search_layout.addWidget(self._prev_btn)

        self._next_btn = QPushButton()
        self._next_btn.setIcon(Icons.get_icon("CHEVRON_DOWN", 14, COLORS['text_dim']))
        self._next_btn.setFixedSize(24, 24)
        self._next_btn.setToolTip(tr("next_match"))
        self._next_btn.setStyleSheet(_nav_btn_style)
        self._next_btn.clicked.connect(self._find_next)
        self._next_btn.setCursor(Qt.PointingHandCursor)
        search_layout.addWidget(self._next_btn)

        # Close search
        self._close_search_btn = QPushButton()
        self._close_search_btn.setIcon(Icons.get_icon("X", 14, COLORS['text_dim']))
        self._close_search_btn.setFixedSize(24, 24)
        self._close_search_btn.setStyleSheet(_nav_btn_style)
        self._close_search_btn.clicked.connect(self._close_search)
        self._close_search_btn.setCursor(Qt.PointingHandCursor)
        search_layout.addWidget(self._close_search_btn)

        layout.addWidget(self._search_bar)

        # Text area — QPlainTextEdit for performance
        self._text_edit = QPlainTextEdit()
        self._text_edit.setReadOnly(True)
        self._text_edit.setFont(QFont(FONTS['family_mono'], 10))
        self._text_edit.setStyleSheet(f"""
            QPlainTextEdit {{
                background-color: {COLORS['bg_primary']};
                border: none;
                color: {COLORS['text_muted']};
                padding: 8px;
            }}
        """)
        self._text_edit.setMaximumBlockCount(self.MAX_LINES)

        # Apply syntax highlighter (incremental, only visible blocks)
        self._highlighter = ConsoleHighlighter(self._text_edit.document())

        # Connect scroll tracking for smart auto-scroll
        scrollbar = self._text_edit.verticalScrollBar()
        scrollbar.valueChanged.connect(self._on_scroll_changed)
        scrollbar.rangeChanged.connect(self._on_scroll_range_changed)

        layout.addWidget(self._text_edit, 1)

        # Copied tooltip
        self._copied_tooltip = CopiedTooltip(self)

        # Buffer timer — 100ms batching for smoother output
        self._buffer_timer = QTimer(self)
        self._buffer_timer.setInterval(100)
        self._buffer_timer.timeout.connect(self._flush_buffer)

    def _reset_combo(self) -> None:
        """Reset the combo counter."""
        self._combo_count = 0
        self._post_limit_count = 0
        self._countdown_value = 0

    def _get_combo_message(self) -> tuple[str, int]:
        """
        Get the message and effective combo level for current state.
        Returns (message_key, combo_level_for_styling)
        """
        if self._combo_count <= self.MAX_COMBO:
            # Normal combo progression
            return tr(COMBO_MESSAGES[self._combo_count]), self._combo_count

        # Post-limit phase
        extra_clicks = self._combo_count - self.MAX_COMBO - 1

        if extra_clicks < self.REPEAT_LAST_COMBO:
            # Repeat last combo message
            return tr(COMBO_MESSAGES[-1]), self.MAX_COMBO

        # Post-limit messages
        post_index = extra_clicks - self.REPEAT_LAST_COMBO

        if post_index < len(POST_LIMIT_MESSAGES) - 1:
            return tr(POST_LIMIT_MESSAGES[post_index]), -1  # -1 = warning style

        # Countdown phase
        countdown_clicks = post_index - (len(POST_LIMIT_MESSAGES) - 1)
        countdown_value = self.COUNTDOWN_START - countdown_clicks

        if countdown_value > 0:
            return f"{countdown_value}...", -2  # -2 = countdown style
        else:
            return tr("combo_button_gone"), -3  # -3 = final style

    def _launch_confetti(self) -> None:
        """Launch confetti animation."""
        if self._confetti is None:
            self._confetti = ConfettiWidget()

        # Launch from button position
        btn_global = self._copy_btn.mapToGlobal(QPoint(
            self._copy_btn.width() // 2,
            self._copy_btn.height() // 2
        ))
        self._confetti.launch(btn_global)

    def append(self, text: str, level: LogLevel = LogLevel.INFO) -> None:
        """Append text to the console."""
        prefix = f"[{level.name}]"
        self._buffer.append(f"{prefix} {text}")

        if not self._buffer_timer.isActive():
            self._buffer_timer.start()

    def append_log(self, message: LogMessage) -> None:
        """Append a LogMessage to the console."""
        self.append(message.text, message.level)

    def append_raw(self, text: str) -> None:
        """Append raw text without prefix."""
        self._buffer.append(text)

        if not self._buffer_timer.isActive():
            self._buffer_timer.start()

    @Slot()
    def _flush_buffer(self) -> None:
        """Flush buffered text to the widget (plain text — highlighter does coloring)."""
        if not self._buffer:
            self._buffer_timer.stop()
            return

        text = "\n".join(self._buffer)
        self._buffer.clear()

        # Append plain text — fast, no HTML parsing
        self._text_edit.appendPlainText(text)

        # Smart auto-scroll: only scroll if user was at bottom
        if self._auto_scroll:
            scrollbar = self._text_edit.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())

        self._buffer_timer.stop()

    @Slot(int)
    def _on_scroll_changed(self, value: int) -> None:
        """Track user scrolling to manage auto-scroll behavior."""
        scrollbar = self._text_edit.verticalScrollBar()
        # User is "at bottom" if within 50px of maximum
        at_bottom = (scrollbar.maximum() - value) < 50
        self._auto_scroll = at_bottom

    @Slot(int, int)
    def _on_scroll_range_changed(self, minimum: int, maximum: int) -> None:
        """When content grows, scroll to bottom if auto-scroll is enabled."""
        if self._auto_scroll:
            scrollbar = self._text_edit.verticalScrollBar()
            scrollbar.setValue(maximum)

    def clear(self) -> None:
        """Clear the console."""
        self._buffer.clear()
        self._text_edit.clear()
        self._line_count = 0
        self._auto_scroll = True
        # Reset search
        self._search_text = ""
        self._search_matches.clear()
        self._current_match_index = -1
        self._update_match_label()
        self._clear_search_highlights()

    # ------------------------------------------------------------------
    # Search functionality
    # ------------------------------------------------------------------

    def _toggle_search(self) -> None:
        """Toggle search bar visibility."""
        visible = not self._search_bar.isVisible()
        self._search_bar.setVisible(visible)
        if visible:
            self._search_input.setFocus()
            self._search_input.selectAll()
        else:
            self._close_search()

    def _close_search(self) -> None:
        """Close search bar and clear highlights."""
        self._search_bar.setVisible(False)
        self._search_text = ""
        self._search_matches.clear()
        self._current_match_index = -1
        self._update_match_label()
        self._clear_search_highlights()
        self._text_edit.setFocus()

    def _on_search_changed(self, text: str) -> None:
        """Handle search text change."""
        self._search_text = text.strip()
        self._perform_search()

    def _perform_search(self) -> None:
        """Search for text and highlight matches."""
        self._clear_search_highlights()
        self._search_matches.clear()
        self._current_match_index = -1

        if not self._search_text:
            self._update_match_label()
            return

        # Search through all blocks
        document = self._text_edit.document()
        search_lower = self._search_text.lower()

        # Highlight format
        highlight_fmt = QTextCharFormat()
        highlight_fmt.setBackground(QColor("#854d0e"))  # amber-900
        highlight_fmt.setForeground(QColor("#fef3c7"))  # amber-100

        cursor = self._text_edit.textCursor()
        cursor.beginEditBlock()

        block = document.begin()
        block_num = 0
        while block.isValid():
            text = block.text().lower()
            if search_lower in text:
                self._search_matches.append(block_num)
                # Highlight all occurrences in this block
                pos = 0
                while True:
                    idx = text.find(search_lower, pos)
                    if idx == -1:
                        break
                    # Create highlight cursor
                    cursor.setPosition(block.position() + idx)
                    cursor.setPosition(
                        block.position() + idx + len(self._search_text),
                        cursor.MoveMode.KeepAnchor
                    )
                    cursor.mergeCharFormat(highlight_fmt)
                    pos = idx + 1

            block = block.next()
            block_num += 1

        cursor.endEditBlock()

        self._update_match_label()

        # Jump to first match
        if self._search_matches:
            self._current_match_index = 0
            self._scroll_to_match(0)

    def _clear_search_highlights(self) -> None:
        """Remove all search highlights."""
        cursor = self._text_edit.textCursor()
        cursor.select(cursor.SelectionType.Document)
        fmt = QTextCharFormat()
        fmt.setBackground(QColor("transparent"))
        cursor.mergeCharFormat(fmt)
        # Re-run highlighter
        self._highlighter.rehighlight()

    def _update_match_label(self) -> None:
        """Update the match count label."""
        if not self._search_text:
            self._match_label.setText("")
        elif not self._search_matches:
            self._match_label.setText(tr("no_matches"))
        else:
            current = self._current_match_index + 1 if self._current_match_index >= 0 else 0
            self._match_label.setText(f"{current}/{len(self._search_matches)}")

        # Enable/disable nav buttons
        has_matches = len(self._search_matches) > 0
        self._prev_btn.setEnabled(has_matches)
        self._next_btn.setEnabled(has_matches)

    def _find_next(self) -> None:
        """Jump to next match."""
        if not self._search_matches:
            return
        self._current_match_index = (self._current_match_index + 1) % len(self._search_matches)
        self._scroll_to_match(self._current_match_index)
        self._update_match_label()

    def _find_prev(self) -> None:
        """Jump to previous match."""
        if not self._search_matches:
            return
        self._current_match_index = (self._current_match_index - 1) % len(self._search_matches)
        self._scroll_to_match(self._current_match_index)
        self._update_match_label()

    def _scroll_to_match(self, match_index: int) -> None:
        """Scroll to show the specified match."""
        if match_index < 0 or match_index >= len(self._search_matches):
            return

        block_num = self._search_matches[match_index]
        document = self._text_edit.document()
        block = document.findBlockByNumber(block_num)
        if block.isValid():
            cursor = self._text_edit.textCursor()
            cursor.setPosition(block.position())
            self._text_edit.setTextCursor(cursor)
            self._text_edit.centerCursor()
            # Disable auto-scroll when navigating search results
            self._auto_scroll = False

    def keyPressEvent(self, event) -> None:
        """Handle keyboard shortcuts."""
        from PySide6.QtCore import QKeyCombination
        # Ctrl+F to open search
        if event.modifiers() == Qt.ControlModifier and event.key() == Qt.Key_F:
            self._toggle_search()
            return
        # Escape to close search
        if event.key() == Qt.Key_Escape and self._search_bar.isVisible():
            self._close_search()
            return
        # F3 / Shift+F3 for next/prev
        if event.key() == Qt.Key_F3:
            if event.modifiers() == Qt.ShiftModifier:
                self._find_prev()
            else:
                self._find_next()
            return
        super().keyPressEvent(event)

    def _copy_to_clipboard(self) -> None:
        """Copy console content to clipboard and show animation."""
        if self._button_hidden:
            return

        clipboard = QApplication.clipboard()

        # If search is active, copy only matching lines
        if self._search_text and self._search_matches:
            document = self._text_edit.document()
            matching_lines = []
            for block_num in self._search_matches:
                block = document.findBlockByNumber(block_num)
                if block.isValid():
                    matching_lines.append(block.text())
            clipboard.setText("\n".join(matching_lines))
        else:
            clipboard.setText(self._text_edit.toPlainText())

        # Update combo
        if self._combo_timer.isActive():
            self._combo_count += 1
        else:
            self._combo_count = 0

        # Restart combo timer
        self._combo_timer.start(self.COMBO_TIMEOUT)

        # Get combo message and style level
        message, style_level = self._get_combo_message()

        # Calculate anchor position (left edge of button with gap)
        btn_pos = self._copy_btn.mapTo(self, QPoint(0, 0))
        anchor_right = btn_pos.x() - 8  # 8px gap to the left of button
        anchor_y = btn_pos.y() + self._copy_btn.height() // 2  # Vertical center

        self._copied_tooltip.show_at(anchor_right, anchor_y, message, style_level)

        # Launch confetti at high combo (but not during warnings)
        if self._combo_count >= self.CONFETTI_THRESHOLD and style_level >= 0:
            self._launch_confetti()

        # Hide button after countdown reaches 0
        if style_level == -3:
            self._button_hidden = True
            self._copy_btn.setVisible(False)

    def get_text(self) -> str:
        """Get all console text."""
        return self._text_edit.toPlainText()