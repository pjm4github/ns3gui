"""
Grid Node Palette for Electric Grid SCADA Network Simulations.

Provides draggable node type items for grid-specific infrastructure:
- Control Centers (EMS, SCADA Master)
- Substations
- RTUs, IEDs, Data Concentrators
- Communication Infrastructure (Gateways, Routers, Towers)

Uses ShapeRenderer for custom shape icons when USE_SHAPE_RENDERER is True.
"""

from typing import Optional, Dict
from PyQt6.QtCore import Qt, pyqtSignal, QMimeData, QPoint, QSize
from PyQt6.QtGui import QFont, QColor, QDrag, QPainter, QPixmap, QPen, QBrush, QPainterPath
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QSizePolicy, QScrollArea,
    QToolButton, QButtonGroup, QGridLayout, QSpacerItem
)

from models.grid_nodes import GridNodeType
from services.shape_manager import get_shape_manager


class GridNodeTypeButton(QPushButton):
    """
    A button representing a draggable grid node type.
    
    Can be clicked to add or dragged onto canvas.
    Uses ShapeRenderer for icons when USE_SHAPE_RENDERER is True.
    """
    
    clicked_with_type = pyqtSignal(GridNodeType)
    
    # Set to True to use ShapeManager for custom shape icons
    # Set to False to use legacy CSS-styled circles
    USE_SHAPE_RENDERER = True
    
    # Colors for different grid node categories
    COLORS = {
        # Control hierarchy - Blue tones
        GridNodeType.CONTROL_CENTER: "#1E40AF",      # Deep blue
        GridNodeType.BACKUP_CONTROL_CENTER: "#3B82F6", # Medium blue
        
        # Substation equipment - Green/Teal tones
        GridNodeType.SUBSTATION: "#065F46",          # Dark teal
        GridNodeType.RTU: "#059669",                 # Teal
        GridNodeType.IED: "#10B981",                 # Green
        GridNodeType.DATA_CONCENTRATOR: "#34D399",   # Light green
        GridNodeType.RELAY: "#6EE7B7",               # Pale green
        GridNodeType.METER: "#A7F3D0",               # Very light green
        
        # Communication infrastructure - Purple/Orange tones
        GridNodeType.GATEWAY: "#7C3AED",             # Purple
        GridNodeType.COMM_ROUTER: "#8B5CF6",         # Light purple
        GridNodeType.COMM_SWITCH: "#A78BFA",         # Lavender
        GridNodeType.COMM_TOWER: "#F59E0B",          # Amber
        GridNodeType.SATELLITE_TERMINAL: "#D97706",  # Orange
        GridNodeType.CELLULAR_GATEWAY: "#EA580C",    # Deep orange
        
        # Special nodes - Gray/Red tones
        GridNodeType.HISTORIAN: "#6B7280",           # Gray
        GridNodeType.HMI: "#EF4444",                 # Red
    }
    
    # Icons for each node type (Unicode symbols or letters)
    ICONS = {
        GridNodeType.CONTROL_CENTER: "⚡",           # Lightning for control
        GridNodeType.BACKUP_CONTROL_CENTER: "⚡B",
        GridNodeType.SUBSTATION: "⬡",               # Hexagon for substation
        GridNodeType.RTU: "R",
        GridNodeType.IED: "I",
        GridNodeType.DATA_CONCENTRATOR: "DC",
        GridNodeType.RELAY: "⚡",                    # Lightning for protection
        GridNodeType.METER: "M",
        GridNodeType.GATEWAY: "G",
        GridNodeType.COMM_ROUTER: "◈",              # Diamond for routing
        GridNodeType.COMM_SWITCH: "⬢",              # Filled hexagon
        GridNodeType.COMM_TOWER: "📡",              # Tower/antenna
        GridNodeType.SATELLITE_TERMINAL: "🛰",
        GridNodeType.CELLULAR_GATEWAY: "📶",
        GridNodeType.HISTORIAN: "H",
        GridNodeType.HMI: "🖥",
    }
    
    # Descriptions for each node type
    DESCRIPTIONS = {
        GridNodeType.CONTROL_CENTER: "Energy Management System (SCADA Master)",
        GridNodeType.BACKUP_CONTROL_CENTER: "Redundant Control Center",
        GridNodeType.SUBSTATION: "Electrical Substation Container",
        GridNodeType.RTU: "Remote Terminal Unit",
        GridNodeType.IED: "Intelligent Electronic Device",
        GridNodeType.DATA_CONCENTRATOR: "Data Aggregation Point",
        GridNodeType.RELAY: "Protective Relay",
        GridNodeType.METER: "Smart Meter / PMU",
        GridNodeType.GATEWAY: "Protocol Gateway",
        GridNodeType.COMM_ROUTER: "Communication Router",
        GridNodeType.COMM_SWITCH: "Network Switch",
        GridNodeType.COMM_TOWER: "Radio/Microwave Tower",
        GridNodeType.SATELLITE_TERMINAL: "VSAT Terminal",
        GridNodeType.CELLULAR_GATEWAY: "Cellular/LTE Gateway",
        GridNodeType.HISTORIAN: "Data Historian Server",
        GridNodeType.HMI: "Human-Machine Interface",
    }
    
    # Category groupings
    CATEGORIES = {
        "Control": [GridNodeType.CONTROL_CENTER, GridNodeType.BACKUP_CONTROL_CENTER],
        "Field Devices": [GridNodeType.SUBSTATION, GridNodeType.RTU, GridNodeType.IED, 
                         GridNodeType.DATA_CONCENTRATOR, GridNodeType.RELAY, GridNodeType.METER],
        "Communication": [GridNodeType.GATEWAY, GridNodeType.COMM_ROUTER, GridNodeType.COMM_SWITCH,
                         GridNodeType.COMM_TOWER, GridNodeType.SATELLITE_TERMINAL, GridNodeType.CELLULAR_GATEWAY],
        "Support": [GridNodeType.HISTORIAN, GridNodeType.HMI],
    }
    
    def __init__(self, node_type: GridNodeType, compact: bool = False, parent=None):
        super().__init__(parent)
        self.node_type = node_type
        self.compact = compact
        self._icon_label: Optional[QLabel] = None  # Store reference for refresh
        self._icon_size: int = 36 if compact else 40  # Store icon size for refresh
        self._setup_ui()
        
        self.clicked.connect(lambda: self.clicked_with_type.emit(self.node_type))
    
    def _setup_ui(self):
        if self.compact:
            self._setup_compact_ui()
        else:
            self._setup_full_ui()
    
    def _setup_compact_ui(self):
        """Compact button showing just icon and short name."""
        self.setFixedSize(80, 70)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setObjectName(f"GridNodeButton_Compact_{self.node_type.name}")
        
        color = self.COLORS.get(self.node_type, "#6B7280")
        
        self.setStyleSheet(f"""
            QPushButton {{
                background: white;
                border: 2px solid #E5E7EB;
                border-radius: 8px;
                padding: 2px;
            }}
            QPushButton:hover {{
                border-color: {color};
                background: #F9FAFB;
            }}
            QPushButton:pressed {{
                background: #F3F4F6;
            }}
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(2)
        
        # Horizontal container for icon with left spacer
        icon_container = QHBoxLayout()
        icon_container.setSpacing(0)
        
        # 4-point left spacer before icon
        left_spacer = QSpacerItem(4, 0, QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum)
        icon_container.addItem(left_spacer)
        
        # Icon - use ShapeRenderer or fallback to CSS circle
        if self.USE_SHAPE_RENDERER:
            self._icon_label = self._create_shape_icon(36)
            icon_container.addWidget(self._icon_label)
        else:
            # Legacy CSS-styled circle
            icon_frame = QFrame()
            icon_frame.setObjectName(f"GridIconFrame_Compact_{self.node_type.name}")
            icon_frame.setFixedSize(36, 36)
            icon_frame.setStyleSheet(f"""
                QFrame {{
                    background: {color};
                    border-radius: 18px;
                }}
            """)
            
            icon_layout = QVBoxLayout(icon_frame)
            icon_layout.setContentsMargins(0, 0, 0, 0)
            
            icon_text = self.ICONS.get(self.node_type, "?")
            icon_text_label = QLabel(icon_text)
            icon_text_label.setObjectName(f"GridIconLabel_Compact_{self.node_type.name}")
            icon_text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            icon_text_label.setStyleSheet("""
                color: white;
                font-size: 14px;
                font-weight: bold;
            """)
            icon_layout.addWidget(icon_text_label)
            
            icon_container.addWidget(icon_frame)
        
        icon_container.addStretch()
        
        layout.addLayout(icon_container)
        
        # Short name
        short_name = self.node_type.name.replace("_", " ").title()
        if len(short_name) > 12:
            # Abbreviate long names
            short_name = "".join(word[0] for word in short_name.split())
        
        name_label = QLabel(short_name)
        name_label.setObjectName(f"GridNameLabel_Compact_{self.node_type.name}")
        name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name_label.setStyleSheet("""
            color: #374151;
            font-size: 10px;
            font-weight: 500;
        """)
        name_label.setWordWrap(True)
        layout.addWidget(name_label)
    
    def _setup_full_ui(self):
        """Full button with icon, name, and description."""
        self.setFixedHeight(64)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setObjectName(f"GridNodeButton_Full_{self.node_type.name}")
        
        color = self.COLORS.get(self.node_type, "#6B7280")
        
        self.setStyleSheet(f"""
            QPushButton {{
                background: white;
                border: 2px solid #E5E7EB;
                border-radius: 10px;
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
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(2)
        
        # 4-point left spacer before icon
        left_spacer = QSpacerItem(4, 0, QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum)
        layout.addItem(left_spacer)
        
        # Icon - use ShapeRenderer or fallback to CSS circle
        if self.USE_SHAPE_RENDERER:
            self._icon_label = self._create_shape_icon(40)
            layout.addWidget(self._icon_label)
        else:
            # Legacy CSS-styled circle
            icon_frame = QFrame()
            icon_frame.setObjectName(f"GridIconFrame_Full_{self.node_type.name}")
            icon_frame.setFixedSize(40, 40)
            icon_frame.setStyleSheet(f"""
                QFrame {{
                    background: {color};
                    border-radius: 20px;
                }}
            """)
            
            icon_layout = QVBoxLayout(icon_frame)
            icon_layout.setContentsMargins(0, 0, 0, 0)
            
            icon_text = self.ICONS.get(self.node_type, "?")
            icon_text_label = QLabel(icon_text)
            icon_text_label.setObjectName(f"GridIconLabel_Full_{self.node_type.name}")
            icon_text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            icon_text_label.setStyleSheet("""
                color: white;
                font-size: 16px;
                font-weight: bold;
            """)
            icon_layout.addWidget(icon_text_label)
            
            layout.addWidget(icon_frame)
        
        # Text
        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)
        
        name = self.node_type.name.replace("_", " ").title()
        name_label = QLabel(name)
        name_label.setObjectName(f"GridNameLabel_Full_{self.node_type.name}")
        name_label.setStyleSheet("""
            color: #374151;
            font-size: 13px;
            font-weight: 600;
        """)
        text_layout.addWidget(name_label)
        
        desc = self.DESCRIPTIONS.get(self.node_type, "")
        desc_label = QLabel(desc)
        desc_label.setObjectName(f"GridDescLabel_Full_{self.node_type.name}")
        desc_label.setStyleSheet("""
            color: #9CA3AF;
            font-size: 11px;
        """)
        text_layout.addWidget(desc_label)
        
        layout.addLayout(text_layout)
        layout.addStretch()
    
    def _create_shape_icon(self, size: int = 36) -> QLabel:
        """Create a QLabel with the shape rendered as a pixmap."""
        from views.shape_renderer import ShapeRenderer
        
        label = QLabel()
        label.setObjectName(f"GridShapeIcon_{self.node_type.name}")
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
            pixmap = ShapeRenderer.render_preview_by_id(self.node_type.name, self._icon_size)
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
        
        if (event.pos() - self._drag_start_pos).manhattanLength() < 10:
            return
        
        drag = QDrag(self)
        mime_data = QMimeData()
        # Use GRID_ prefix to distinguish from regular node types
        mime_data.setText(f"GRID_{self.node_type.name}")
        drag.setMimeData(mime_data)
        
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
        
        color = QColor(self.COLORS.get(self.node_type, "#6B7280"))
        painter.setBrush(color)
        painter.setPen(Qt.PenStyle.NoPen)
        
        # Draw shape based on node type category
        if self.node_type in (GridNodeType.CONTROL_CENTER, GridNodeType.BACKUP_CONTROL_CENTER):
            # Rectangle for control centers
            painter.drawRoundedRect(5, 10, size - 10, size - 20, 8, 8)
        elif self.node_type == GridNodeType.SUBSTATION:
            # Hexagon for substations
            self._draw_hexagon(painter, size // 2, size // 2, (size - 10) // 2)
        elif self.node_type in (GridNodeType.COMM_TOWER, GridNodeType.SATELLITE_TERMINAL):
            # Triangle for towers
            self._draw_triangle(painter, size // 2, size // 2, (size - 10) // 2)
        else:
            # Circle for others
            painter.drawEllipse(5, 5, size - 10, size - 10)
        
        # Draw icon
        painter.setPen(QColor("white"))
        font = QFont("SF Pro Display", 16)
        font.setWeight(QFont.Weight.Bold)
        painter.setFont(font)
        
        icon_text = self.ICONS.get(self.node_type, "?")
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, icon_text)
        
        painter.end()
        return pixmap
    
    def _draw_hexagon(self, painter: QPainter, cx: int, cy: int, radius: int):
        """Draw a hexagon shape."""
        import math
        path = QPainterPath()
        for i in range(6):
            angle = math.pi / 3 * i - math.pi / 2
            x = cx + radius * math.cos(angle)
            y = cy + radius * math.sin(angle)
            if i == 0:
                path.moveTo(x, y)
            else:
                path.lineTo(x, y)
        path.closeSubpath()
        painter.drawPath(path)
    
    def _draw_triangle(self, painter: QPainter, cx: int, cy: int, radius: int):
        """Draw a triangle shape (tower icon)."""
        import math
        path = QPainterPath()
        for i in range(3):
            angle = math.pi * 2 / 3 * i - math.pi / 2
            x = cx + radius * math.cos(angle)
            y = cy + radius * math.sin(angle)
            if i == 0:
                path.moveTo(x, y)
            else:
                path.lineTo(x, y)
        path.closeSubpath()
        painter.drawPath(path)


class GridNodePalette(QWidget):
    """
    Palette panel containing all available grid node types.
    
    Organized by category with expandable sections.
    Supports both compact (grid) and full (list) view modes.
    """
    
    nodeTypeSelected = pyqtSignal(GridNodeType)
    
    def __init__(self, compact_mode: bool = False, parent=None):
        super().__init__(parent)
        self.compact_mode = compact_mode
        self.setObjectName("GridNodePalette")
        self._buttons: list[GridNodeTypeButton] = []
        self._setup_ui()
    
    def _setup_ui(self):
        self.setMinimumWidth(280 if not self.compact_mode else 200)
        
        main_layout = QVBoxLayout(self)
        main_layout.setObjectName("GridPalette_MainLayout")
        main_layout.setContentsMargins(2, 2, 2, 2)
        main_layout.setSpacing(2)
        
        # Header
        header_layout = QHBoxLayout()
        header_layout.setObjectName("GridPalette_HeaderLayout")
        
        title = QLabel("Grid Components")
        title.setObjectName("GridPalette_Title")
        title_font = QFont("SF Pro Display", 14)
        title_font.setWeight(QFont.Weight.Bold)
        title.setFont(title_font)
        title.setStyleSheet("color: #111827;")
        header_layout.addWidget(title)
        
        header_layout.addStretch()
        
        # View toggle
        self.view_toggle = QToolButton()
        self.view_toggle.setObjectName("GridPalette_ViewToggle")
        self.view_toggle.setText("⊞" if self.compact_mode else "☰")
        self.view_toggle.setStyleSheet("""
            QToolButton {
                border: 1px solid #D1D5DB;
                border-radius: 4px;
                padding: 2px 8px;
                background: white;
            }
            QToolButton:hover {
                background: #F3F4F6;
            }
        """)
        self.view_toggle.clicked.connect(self._toggle_view_mode)
        header_layout.addWidget(self.view_toggle)
        
        main_layout.addLayout(header_layout)
        
        # Subtitle
        subtitle = QLabel("Click to add or drag onto canvas")
        subtitle.setObjectName("GridPalette_Subtitle")
        subtitle.setStyleSheet("color: #6B7280; font-size: 11px; margin-bottom: 4px;")
        main_layout.addWidget(subtitle)
        
        # Scrollable content area
        scroll = QScrollArea()
        scroll.setObjectName("GridPalette_ScrollArea")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; }")
        
        self.content_widget = QWidget()
        self.content_widget.setObjectName("GridPalette_ContentWidget")
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setObjectName("GridPalette_ContentLayout")
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(2)
        
        scroll.setWidget(self.content_widget)
        main_layout.addWidget(scroll)
        
        # Populate categories
        self._populate_categories()
        
        # Help text
        help_text = QLabel("Right-click + drag between\nnodes to create links")
        help_text.setObjectName("GridPalette_HelpText")
        help_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        help_text.setStyleSheet("""
            color: #9CA3AF;
            font-size: 11px;
            padding: 2px;
            background: #F9FAFB;
            border-radius: 6px;
        """)
        main_layout.addWidget(help_text)
    
    def _populate_categories(self):
        """Populate the palette with categorized node types."""
        # Clear existing
        self._buttons.clear()
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        categories = GridNodeTypeButton.CATEGORIES
        
        for category_name, node_types in categories.items():
            # Category header
            cat_frame = QFrame()
            cat_layout = QVBoxLayout(cat_frame)
            cat_layout.setContentsMargins(0, 0, 0, 0)
            cat_layout.setSpacing(2)
            
            cat_label = QLabel(category_name)
            cat_label.setStyleSheet("""
                color: #6B7280;
                font-size: 11px;
                font-weight: 600;
                text-transform: uppercase;
                letter-spacing: 1px;
            """)
            cat_layout.addWidget(cat_label)
            
            if self.compact_mode:
                # Grid layout for compact mode
                grid = QGridLayout()
                grid.setSpacing(2)
                for i, node_type in enumerate(node_types):
                    btn = GridNodeTypeButton(node_type, compact=True)
                    btn.clicked_with_type.connect(self.nodeTypeSelected)
                    self._buttons.append(btn)
                    grid.addWidget(btn, i // 3, i % 3)
                cat_layout.addLayout(grid)
            else:
                # Vertical list for full mode
                for node_type in node_types:
                    btn = GridNodeTypeButton(node_type, compact=False)
                    btn.clicked_with_type.connect(self.nodeTypeSelected)
                    self._buttons.append(btn)
                    cat_layout.addWidget(btn)
            
            self.content_layout.addWidget(cat_frame)
        
        self.content_layout.addStretch()
    
    def _toggle_view_mode(self):
        """Toggle between compact and full view modes."""
        self.compact_mode = not self.compact_mode
        self.view_toggle.setText("⊞" if self.compact_mode else "☰")
        self._populate_categories()
        
        # Adjust minimum width
        self.setMinimumWidth(280 if not self.compact_mode else 200)
    
    def refresh_icons(self):
        """Refresh all button icons after shape changes."""
        for btn in self._buttons:
            btn.refresh_icon()


class CombinedNodePalette(QWidget):
    """
    Combined palette showing both standard ns-3 nodes and grid-specific nodes.
    
    Includes a tab or toggle to switch between views.
    """
    
    nodeTypeSelected = pyqtSignal(str)  # Emits node type name (with GRID_ prefix for grid types)
    gridNodeTypeSelected = pyqtSignal(GridNodeType)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("CombinedNodePalette")
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setObjectName("CombinedPalette_MainLayout")
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Mode selector
        mode_frame = QFrame()
        mode_frame.setObjectName("CombinedPalette_ModeFrame")
        mode_frame.setStyleSheet("""
            QFrame {
                background: #F3F4F6;
                border-bottom: 1px solid #E5E7EB;
            }
        """)
        mode_layout = QHBoxLayout(mode_frame)
        mode_layout.setObjectName("CombinedPalette_ModeLayout")
        mode_layout.setContentsMargins(2, 2, 2, 2)
        mode_layout.setSpacing(2)
        
        self.mode_group = QButtonGroup(self)
        
        self.std_btn = QPushButton("Standard")
        self.std_btn.setObjectName("CombinedPalette_StandardBtn")
        self.std_btn.setCheckable(True)
        self.std_btn.setChecked(True)
        self.std_btn.setStyleSheet(self._get_mode_button_style(True))
        self.std_btn.clicked.connect(lambda: self._set_mode("standard"))
        self.mode_group.addButton(self.std_btn)
        mode_layout.addWidget(self.std_btn)
        
        self.grid_btn = QPushButton("Grid/SCADA")
        self.grid_btn.setObjectName("CombinedPalette_GridBtn")
        self.grid_btn.setCheckable(True)
        self.grid_btn.setStyleSheet(self._get_mode_button_style(False))
        self.grid_btn.clicked.connect(lambda: self._set_mode("grid"))
        self.mode_group.addButton(self.grid_btn)
        mode_layout.addWidget(self.grid_btn)
        
        layout.addWidget(mode_frame)
        
        # Stack for different palettes
        from PyQt6.QtWidgets import QStackedWidget
        self.stack = QStackedWidget()
        self.stack.setObjectName("CombinedPalette_Stack")
        
        # Standard node palette (import from existing)
        from views.node_palette import NodePalette
        self.standard_palette = NodePalette()
        self.standard_palette.nodeTypeSelected.connect(
            lambda nt: self.nodeTypeSelected.emit(nt.name)
        )
        self.stack.addWidget(self.standard_palette)
        
        # Grid node palette
        self.grid_palette = GridNodePalette(compact_mode=False)
        self.grid_palette.nodeTypeSelected.connect(self._on_grid_node_selected)
        self.stack.addWidget(self.grid_palette)
        
        layout.addWidget(self.stack)
    
    def _get_mode_button_style(self, active: bool) -> str:
        if active:
            return """
                QPushButton {
                    background: white;
                    border: 1px solid #D1D5DB;
                    border-radius: 6px;
                    padding: 2px 4px;
                    font-weight: 600;
                    color: #1F2937;
                }
            """
        else:
            return """
                QPushButton {
                    background: transparent;
                    border: 1px solid transparent;
                    border-radius: 6px;
                    padding: 2px 4px;
                    color: #6B7280;
                }
                QPushButton:hover {
                    background: #E5E7EB;
                }
            """
    
    def _set_mode(self, mode: str):
        if mode == "standard":
            self.stack.setCurrentIndex(0)
            self.std_btn.setStyleSheet(self._get_mode_button_style(True))
            self.grid_btn.setStyleSheet(self._get_mode_button_style(False))
        else:
            self.stack.setCurrentIndex(1)
            self.std_btn.setStyleSheet(self._get_mode_button_style(False))
            self.grid_btn.setStyleSheet(self._get_mode_button_style(True))
    
    def _on_grid_node_selected(self, grid_type: GridNodeType):
        self.gridNodeTypeSelected.emit(grid_type)
        self.nodeTypeSelected.emit(f"GRID_{grid_type.name}")
    
    def refresh_icons(self):
        """Refresh all button icons after shape changes."""
        self.standard_palette.refresh_icons()
        self.grid_palette.refresh_icons()
