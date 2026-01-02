"""
Node palette for selecting and adding nodes to the canvas.

Provides draggable node type items and quick-add buttons.
Uses ShapeRenderer for custom shape icons when USE_SHAPE_RENDERER is True.
"""

from typing import Optional
from PyQt6.QtCore import Qt, pyqtSignal, QMimeData, QPoint
from PyQt6.QtGui import QFont, QColor, QDrag, QPainter, QPixmap
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QFrame, QSizePolicy, QSpacerItem
)

from models import NodeType
from services.shape_manager import get_shape_manager


class NodeTypeButton(QPushButton):
    """
    A button representing a draggable node type.
    
    Can be clicked to add or dragged onto canvas.
    Uses ShapeRenderer for icons when USE_SHAPE_RENDERER is True.
    """
    
    clicked_with_type = pyqtSignal(NodeType)
    
    # Set to True to use ShapeManager for custom shape icons
    # Set to False to use legacy CSS-styled circles
    USE_SHAPE_RENDERER = True
    
    # Colors matching the canvas (used as fallback)
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
        self.setObjectName(f"NodeTypeButton_{node_type.name}")
        self._icon_label: Optional[QLabel] = None  # Store reference for refresh
        self._setup_ui()
        
        self.clicked.connect(lambda: self.clicked_with_type.emit(self.node_type))
    
    def _setup_ui(self):
        self.setFixedHeight(48)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        
        color = self.COLORS[self.node_type]
        
        self.setStyleSheet(f"""
            QPushButton {{
                background: white;
                border: 1px solid #E5E7EB;
                border-radius: 6px;
                text-align: left;
                padding: 2px 4px;
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
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(6)
        
        # 4-point left spacer before icon
        left_spacer = QSpacerItem(4, 0, QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum)
        layout.addItem(left_spacer)
        
        # Icon - use ShapeRenderer or fallback to CSS circle
        if self.USE_SHAPE_RENDERER:
            self._icon_label = self._create_shape_icon(32)
            layout.addWidget(self._icon_label)
        else:
            # Legacy CSS-styled circle
            icon_frame = QFrame()
            icon_frame.setObjectName(f"IconFrame_{self.node_type.name}")
            icon_frame.setFixedSize(32, 32)
            icon_frame.setStyleSheet(f"""
                QFrame {{
                    background: {color};
                    border-radius: 16px;
                }}
            """)
            
            icon_layout = QVBoxLayout(icon_frame)
            icon_layout.setContentsMargins(0, 0, 0, 0)
            
            icon_text = QLabel(self.ICONS[self.node_type])
            icon_text.setObjectName(f"IconLabel_{self.node_type.name}")
            icon_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
            icon_text.setStyleSheet("""
                color: white;
                font-size: 13px;
                font-weight: bold;
            """)
            icon_layout.addWidget(icon_text)
            
            layout.addWidget(icon_frame)
        
        # Text
        text_layout = QVBoxLayout()
        text_layout.setSpacing(0)
        
        name_label = QLabel(self.node_type.name.title())
        name_label.setObjectName(f"NameLabel_{self.node_type.name}")
        name_label.setStyleSheet("""
            color: #374151;
            font-size: 12px;
            font-weight: 600;
        """)
        text_layout.addWidget(name_label)
        
        desc_label = QLabel(self.DESCRIPTIONS[self.node_type])
        desc_label.setObjectName(f"DescLabel_{self.node_type.name}")
        desc_label.setStyleSheet("""
            color: #9CA3AF;
            font-size: 10px;
        """)
        text_layout.addWidget(desc_label)
        
        layout.addLayout(text_layout)
        layout.addStretch()
    
    def _create_shape_icon(self, size: int = 32) -> QLabel:
        """Create a QLabel with the shape rendered as a pixmap."""
        from views.shape_renderer import ShapeRenderer
        
        label = QLabel()
        label.setObjectName(f"ShapeIcon_{self.node_type.name}")
        label.setFixedSize(size, size)
        
        # Get shape from manager and render
        shape_id = self.node_type.name
        pixmap = ShapeRenderer.render_preview_by_id(shape_id, size)
        label.setPixmap(pixmap)
        
        return label
    
    def refresh_icon(self):
        """Refresh the icon pixmap after shape changes."""
        if self._icon_label is not None and self.USE_SHAPE_RENDERER:
            from views.shape_renderer import ShapeRenderer
            
            # Clear shape cache for this shape
            shape_manager = get_shape_manager()
            shape_manager._invalidate_cache(self.node_type.name)
            
            # Re-render the icon
            pixmap = ShapeRenderer.render_preview_by_id(self.node_type.name, 32)
            self._icon_label.setPixmap(pixmap)
    
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
        size = 50
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Draw circle
        color = QColor(self.COLORS[self.node_type])
        painter.setBrush(color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(4, 4, size - 8, size - 8)
        
        # Draw icon
        painter.setPen(QColor("white"))
        font = QFont("SF Pro Display", 14)
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
        self.setObjectName("NodePalette_Standard")
        self._buttons: list[NodeTypeButton] = []
        self._setup_ui()
    
    def _setup_ui(self):
        self.setMinimumWidth(220)
        
        layout = QVBoxLayout(self)
        layout.setObjectName("NodePalette_MainLayout")
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(2)
        
        # Title
        title = QLabel("Node Types")
        title.setObjectName("NodePalette_Title")
        title_font = QFont("SF Pro Display", 12)
        title_font.setWeight(QFont.Weight.Bold)
        title.setFont(title_font)
        title.setStyleSheet("color: #111827;")
        layout.addWidget(title)
        
        # Subtitle
        subtitle = QLabel("Click to add or drag onto canvas")
        subtitle.setObjectName("NodePalette_Subtitle")
        subtitle.setStyleSheet("color: #6B7280; font-size: 10px;")
        layout.addWidget(subtitle)
        
        # Node type buttons
        for node_type in NodeType:
            btn = NodeTypeButton(node_type)
            btn.clicked_with_type.connect(self.nodeTypeSelected)
            self._buttons.append(btn)
            layout.addWidget(btn)
        
        layout.addStretch()
        
        # Help text at bottom
        help_text = QLabel("Right-click + drag between\nnodes to create links")
        help_text.setObjectName("NodePalette_HelpText")
        help_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        help_text.setStyleSheet("""
            color: #9CA3AF;
            font-size: 10px;
            padding: 4px;
            background: #F9FAFB;
            border-radius: 4px;
        """)
        layout.addWidget(help_text)
    
    def refresh_icons(self):
        """Refresh all button icons after shape changes."""
        for btn in self._buttons:
            btn.refresh_icon()
