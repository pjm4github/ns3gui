"""
Layout Debugger Utility.

Provides Ctrl+hover identification of widgets for layout adjustments.
When enabled, holding Ctrl and hovering over any widget shows its
identifier in a tooltip overlay.
"""

from typing import Optional, Dict, Set
from PyQt6.QtCore import Qt, QObject, QEvent, QPoint, QTimer
from PyQt6.QtGui import QFont, QColor, QPainter, QPen, QBrush
from PyQt6.QtWidgets import (
    QWidget, QApplication, QToolTip, QLabel, QFrame,
    QLayout, QHBoxLayout, QVBoxLayout, QGridLayout,
    QPushButton, QScrollArea, QSplitter, QTabWidget
)


class LayoutDebugOverlay(QLabel):
    """Overlay label showing widget identification."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.ToolTip | 
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setStyleSheet("""
            QLabel {
                background: rgba(0, 0, 0, 0.85);
                color: #00FF00;
                font-family: 'Consolas', 'Monaco', monospace;
                font-size: 11px;
                padding: 4px 6px;
                border: 1px solid #00FF00;
                border-radius: 3px;
            }
        """)
        self.hide()


class LayoutDebugger(QObject):
    """
    Global layout debugger that shows widget identifiers on Ctrl+hover.
    
    Usage:
        debugger = LayoutDebugger.instance()
        debugger.register_widget(widget, "MyWidget.button_save")
        
    Or auto-register all children:
        debugger.auto_register(parent_widget, "ParentWidget")
    """
    
    _instance: Optional['LayoutDebugger'] = None
    
    @classmethod
    def instance(cls) -> 'LayoutDebugger':
        """Get or create the singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def __init__(self):
        super().__init__()
        self._widget_ids: Dict[int, str] = {}  # widget id() -> identifier string
        self._overlay = LayoutDebugOverlay()
        self._current_widget: Optional[QWidget] = None
        self._ctrl_pressed = False
        
        # Install global event filter
        app = QApplication.instance()
        if app:
            app.installEventFilter(self)
    
    def register_widget(self, widget: QWidget, identifier: str):
        """Register a widget with an identifier for debugging."""
        self._widget_ids[id(widget)] = identifier
        widget.setMouseTracking(True)
    
    def auto_register(self, parent: QWidget, prefix: str, max_depth: int = 10):
        """
        Automatically register all child widgets with generated identifiers.
        
        Args:
            parent: Parent widget to scan
            prefix: Prefix for all identifiers (e.g., "NodePalette")
            max_depth: Maximum recursion depth
        """
        self._auto_register_recursive(parent, prefix, 0, max_depth)
    
    def _auto_register_recursive(self, widget: QWidget, prefix: str, depth: int, max_depth: int):
        """Recursively register widgets."""
        if depth > max_depth:
            return
        
        # Generate identifier for this widget
        widget_type = widget.__class__.__name__
        widget_name = widget.objectName() or ""
        
        if widget_name:
            identifier = f"{prefix}.{widget_name}"
        else:
            identifier = f"{prefix}.{widget_type}"
        
        # Add additional info for common widget types
        if isinstance(widget, QPushButton):
            text = widget.text()[:20] if widget.text() else ""
            if text:
                identifier += f"[{text}]"
        elif isinstance(widget, QLabel):
            text = widget.text()[:20] if widget.text() else ""
            if text:
                identifier += f"[{text}]"
        
        self.register_widget(widget, identifier)
        
        # Recurse into children
        for child in widget.findChildren(QWidget):
            if child.parent() == widget:  # Only direct children
                child_prefix = identifier
                self._auto_register_recursive(child, child_prefix, depth + 1, max_depth)
    
    def get_widget_info(self, widget: QWidget) -> str:
        """Get detailed info about a widget."""
        lines = []
        
        # Basic identification
        widget_id = self._widget_ids.get(id(widget), "")
        widget_type = widget.__class__.__name__
        widget_name = widget.objectName() or "(no name)"
        
        lines.append(f"ID: {widget_id}" if widget_id else f"Type: {widget_type}")
        lines.append(f"Class: {widget_type}")
        lines.append(f"Name: {widget_name}")
        
        # Geometry info
        geom = widget.geometry()
        lines.append(f"Pos: ({geom.x()}, {geom.y()})")
        lines.append(f"Size: {geom.width()} x {geom.height()}")
        
        # Margins info
        layout = widget.layout()
        if layout:
            margins = layout.contentsMargins()
            lines.append(f"Margins: L={margins.left()} T={margins.top()} R={margins.right()} B={margins.bottom()}")
            lines.append(f"Spacing: {layout.spacing()}")
        
        # Style info - check for padding in stylesheet
        style = widget.styleSheet()
        if style and "padding" in style.lower():
            # Extract padding value if present
            import re
            padding_match = re.search(r'padding:\s*([^;]+)', style, re.IGNORECASE)
            if padding_match:
                lines.append(f"CSS Padding: {padding_match.group(1)}")
        
        return "\n".join(lines)
    
    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        """Global event filter for Ctrl+hover detection."""
        
        # Track Ctrl key state
        if event.type() == QEvent.Type.KeyPress:
            if event.key() == Qt.Key.Key_Control:
                self._ctrl_pressed = True
                # If already hovering over a widget, show overlay
                if self._current_widget:
                    self._show_overlay(self._current_widget)
        
        elif event.type() == QEvent.Type.KeyRelease:
            if event.key() == Qt.Key.Key_Control:
                self._ctrl_pressed = False
                self._overlay.hide()
        
        # Track mouse movement over widgets
        elif event.type() == QEvent.Type.Enter:
            if isinstance(obj, QWidget):
                self._current_widget = obj
                if self._ctrl_pressed:
                    self._show_overlay(obj)
        
        elif event.type() == QEvent.Type.Leave:
            if isinstance(obj, QWidget) and obj == self._current_widget:
                self._current_widget = None
                if not self._ctrl_pressed:
                    self._overlay.hide()
        
        elif event.type() == QEvent.Type.MouseMove:
            if self._ctrl_pressed and isinstance(obj, QWidget):
                # Find the deepest widget under cursor
                if hasattr(event, 'globalPosition'):
                    global_pos = event.globalPosition().toPoint()
                else:
                    global_pos = event.globalPos()
                
                widget_at = QApplication.widgetAt(global_pos)
                if widget_at and widget_at != self._current_widget:
                    self._current_widget = widget_at
                    self._show_overlay(widget_at)
        
        return False  # Don't consume the event
    
    def _show_overlay(self, widget: QWidget):
        """Show the debug overlay for a widget."""
        info = self.get_widget_info(widget)
        self._overlay.setText(info)
        self._overlay.adjustSize()
        
        # Position near the widget
        global_pos = widget.mapToGlobal(QPoint(0, 0))
        
        # Offset to not cover the widget
        overlay_x = global_pos.x() + widget.width() + 5
        overlay_y = global_pos.y()
        
        # Keep on screen
        screen = QApplication.primaryScreen()
        if screen:
            screen_geom = screen.availableGeometry()
            if overlay_x + self._overlay.width() > screen_geom.right():
                overlay_x = global_pos.x() - self._overlay.width() - 5
            if overlay_y + self._overlay.height() > screen_geom.bottom():
                overlay_y = screen_geom.bottom() - self._overlay.height()
        
        self._overlay.move(overlay_x, overlay_y)
        self._overlay.show()
        self._overlay.raise_()


def enable_layout_debugging(root_widget: QWidget, prefix: str = "Root"):
    """
    Convenience function to enable layout debugging on a widget tree.
    
    Args:
        root_widget: The root widget to debug
        prefix: Prefix for widget identifiers
    """
    debugger = LayoutDebugger.instance()
    debugger.auto_register(root_widget, prefix)
