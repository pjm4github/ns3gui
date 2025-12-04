"""
Node palette for selecting and adding nodes to the canvas.

Provides draggable node type items and quick-add buttons.
"""

from typing import Optional
from PyQt6.QtCore import Qt, pyqtSignal, QMimeData, QPoint
from PyQt6.QtGui import QFont, QColor, QDrag, QPainter, QPixmap
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QFrame, QSizePolicy
)

from models import NodeType


class NodeTypeButton(QPushButton):
    """
    A button representing a draggable node type.
    
    Can be clicked to add or dragged onto canvas.
    """
    
    clicked_with_type = pyqtSignal(NodeType)
    
    # Colors matching the canvas
    COLORS = {
        NodeType.HOST: "#4A90D9",
        NodeType.ROUTER: "#7B68EE",
        NodeType.SWITCH: "#50C878",
        NodeType.STATION: "#FF9500",      # Orange for WiFi station
        NodeType.ACCESS_POINT: "#FF3B30", # Red for access point
    }
    
    ICONS = {
        NodeType.HOST: "H",
        NodeType.ROUTER: "R", 
        NodeType.SWITCH: "S",
        NodeType.STATION: "📶",    # WiFi symbol or W
        NodeType.ACCESS_POINT: "AP",
    }
    
    DESCRIPTIONS = {
        NodeType.HOST: "End device (PC, server)",
        NodeType.ROUTER: "Routes between networks",
        NodeType.SWITCH: "L2 network switch",
        NodeType.STATION: "WiFi client (802.11)",
        NodeType.ACCESS_POINT: "WiFi access point",
    }
    
    def __init__(self, node_type: NodeType, parent=None):
        super().__init__(parent)
        self.node_type = node_type
        self._setup_ui()
        
        self.clicked.connect(lambda: self.clicked_with_type.emit(self.node_type))
    
    def _setup_ui(self):
        self.setFixedHeight(64)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        
        color = self.COLORS[self.node_type]
        
        self.setStyleSheet(f"""
            QPushButton {{
                background: white;
                border: 2px solid #E5E7EB;
                border-radius: 10px;
                text-align: left;
                padding: 10px 12px;
            }}
            QPushButton:hover {{
                border-color: {color};
                background: #F9FAFB;
            }}
            QPushButton:pressed {{
                background: #F3F4F6;
            }}
        """)
        
        # Create custom layout inside button
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(12)
        
        # Icon circle
        icon_frame = QFrame()
        icon_frame.setFixedSize(40, 40)
        icon_frame.setStyleSheet(f"""
            QFrame {{
                background: {color};
                border-radius: 20px;
            }}
        """)
        
        icon_layout = QVBoxLayout(icon_frame)
        icon_layout.setContentsMargins(0, 0, 0, 0)
        
        icon_label = QLabel(self.ICONS[self.node_type])
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setStyleSheet("""
            color: white;
            font-size: 16px;
            font-weight: bold;
        """)
        icon_layout.addWidget(icon_label)
        
        layout.addWidget(icon_frame)
        
        # Text
        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)
        
        name_label = QLabel(self.node_type.name.title())
        name_label.setStyleSheet("""
            color: #374151;
            font-size: 13px;
            font-weight: 600;
        """)
        text_layout.addWidget(name_label)
        
        desc_label = QLabel(self.DESCRIPTIONS[self.node_type])
        desc_label.setStyleSheet("""
            color: #9CA3AF;
            font-size: 11px;
        """)
        text_layout.addWidget(desc_label)
        
        layout.addLayout(text_layout)
        layout.addStretch()
    
    def mousePressEvent(self, event):
        """Start drag on mouse press."""
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start_pos = event.pos()
        super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event):
        """Handle drag motion."""
        if not (event.buttons() & Qt.MouseButton.LeftButton):
            return
        
        if not hasattr(self, '_drag_start_pos'):
            return
            
        # Check if we've moved enough to start a drag
        if (event.pos() - self._drag_start_pos).manhattanLength() < 10:
            return
        
        # Create drag
        drag = QDrag(self)
        mime_data = QMimeData()
        mime_data.setText(self.node_type.name)
        drag.setMimeData(mime_data)
        
        # Create drag pixmap
        pixmap = self._create_drag_pixmap()
        drag.setPixmap(pixmap)
        drag.setHotSpot(QPoint(pixmap.width() // 2, pixmap.height() // 2))
        
        drag.exec(Qt.DropAction.CopyAction)
    
    def _create_drag_pixmap(self) -> QPixmap:
        """Create pixmap for drag preview."""
        size = 60
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Draw circle
        color = QColor(self.COLORS[self.node_type])
        painter.setBrush(color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(5, 5, size - 10, size - 10)
        
        # Draw icon
        painter.setPen(QColor("white"))
        font = QFont("SF Pro Display", 18)
        font.setWeight(QFont.Weight.Bold)
        painter.setFont(font)
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, self.ICONS[self.node_type])
        
        painter.end()
        return pixmap


class NodePalette(QWidget):
    """
    Palette panel containing all available node types.
    """
    
    nodeTypeSelected = pyqtSignal(NodeType)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
    
    def _setup_ui(self):
        self.setMinimumWidth(250)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        
        # Title
        title = QLabel("Node Types")
        title_font = QFont("SF Pro Display", 14)
        title_font.setWeight(QFont.Weight.Bold)
        title.setFont(title_font)
        title.setStyleSheet("color: #111827;")
        layout.addWidget(title)
        
        # Subtitle
        subtitle = QLabel("Click to add or drag onto canvas")
        subtitle.setStyleSheet("color: #6B7280; font-size: 12px; margin-bottom: 8px;")
        layout.addWidget(subtitle)
        
        # Node type buttons
        for node_type in NodeType:
            btn = NodeTypeButton(node_type)
            btn.clicked_with_type.connect(self.nodeTypeSelected)
            layout.addWidget(btn)
        
        layout.addStretch()
        
        # Help text at bottom
        help_text = QLabel("Right-click + drag between\nnodes to create links")
        help_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        help_text.setStyleSheet("""
            color: #9CA3AF;
            font-size: 11px;
            padding: 12px;
            background: #F9FAFB;
            border-radius: 6px;
        """)
        layout.addWidget(help_text)
