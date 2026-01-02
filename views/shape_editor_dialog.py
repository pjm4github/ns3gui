"""
Shape Editor Dialog.

A visual editor for customizing node shapes with:
- Interactive canvas for dragging control points and connectors
- Primitive list (add/remove ellipse, rectangle, polygon)
- Style editor (fill, stroke, icon)
- Connector editor (add/remove, position along edge)
- Grid snapping
- Undo/redo support (Phase 7)

Usage:
    dialog = ShapeEditorDialog(shape_definition, parent)
    if dialog.exec() == QDialog.DialogCode.Accepted:
        modified_shape = dialog.get_shape()
"""

import math
from typing import Optional, List, Tuple
from PyQt6.QtCore import Qt, QPointF, QRectF, pyqtSignal, QTimer
from PyQt6.QtGui import (
    QPainter, QPen, QBrush, QColor, QFont, QPainterPath,
    QPixmap, QTransform, QCursor, QKeySequence
)
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QWidget,
    QGraphicsView, QGraphicsScene, QGraphicsItem,
    QGraphicsEllipseItem, QGraphicsPathItem, QGraphicsRectItem,
    QLabel, QPushButton, QFrame, QSplitter,
    QTreeWidget, QTreeWidgetItem, QGroupBox,
    QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox,
    QColorDialog, QSlider, QCheckBox, QFormLayout,
    QMenuBar, QMenu, QToolBar, QStatusBar,
    QDialogButtonBox, QMessageBox, QFileDialog,
    QSizePolicy, QScrollArea, QListWidget, QListWidgetItem
)

from models.shape_definition import (
    ShapeDefinition, ShapePrimitive, ShapeConnector, ShapeStyle,
    ControlPoint, Edge, PrimitiveType, PointType, EdgeType
)
from services.shape_manager import get_shape_manager


# =============================================================================
# Constants
# =============================================================================

CANVAS_SIZE = 400  # Size of the editing canvas
GRID_SIZE = 10     # Grid snap size in pixels
HANDLE_SIZE = 8    # Size of control point handles
CONNECTOR_SIZE = 10  # Size of connector handles
MAX_UNDO_STEPS = 50  # Maximum undo history


# =============================================================================
# Undo/Redo Support
# =============================================================================

class UndoStack:
    """
    Simple undo/redo stack using shape snapshots.
    
    Stores complete shape states rather than individual commands
    for simplicity. Each modification creates a new snapshot.
    """
    
    def __init__(self, max_size: int = MAX_UNDO_STEPS):
        self.max_size = max_size
        self._undo_stack: List[dict] = []  # Stack of shape JSON snapshots
        self._redo_stack: List[dict] = []  # Stack for redo
        self._current_state: Optional[dict] = None
    
    def save_state(self, shape: ShapeDefinition):
        """Save current shape state to undo stack."""
        # Convert shape to dict for storage
        state = shape.to_dict()
        
        # If we have a current state, push it to undo stack
        if self._current_state is not None:
            self._undo_stack.append(self._current_state)
            
            # Trim stack if too large
            while len(self._undo_stack) > self.max_size:
                self._undo_stack.pop(0)
        
        # Clear redo stack on new action
        self._redo_stack.clear()
        
        # Update current state
        self._current_state = state
    
    def initialize(self, shape: ShapeDefinition):
        """Initialize with a shape (doesn't add to undo stack)."""
        self._current_state = shape.to_dict()
        self._undo_stack.clear()
        self._redo_stack.clear()
    
    def undo(self) -> Optional[ShapeDefinition]:
        """
        Undo last change.
        
        Returns the previous shape state, or None if nothing to undo.
        """
        if not self._undo_stack:
            return None
        
        # Push current state to redo stack
        if self._current_state is not None:
            self._redo_stack.append(self._current_state)
        
        # Pop from undo stack
        self._current_state = self._undo_stack.pop()
        
        # Reconstruct shape from state
        return ShapeDefinition.from_dict(self._current_state)
    
    def redo(self) -> Optional[ShapeDefinition]:
        """
        Redo last undone change.
        
        Returns the next shape state, or None if nothing to redo.
        """
        if not self._redo_stack:
            return None
        
        # Push current state to undo stack
        if self._current_state is not None:
            self._undo_stack.append(self._current_state)
        
        # Pop from redo stack
        self._current_state = self._redo_stack.pop()
        
        # Reconstruct shape from state
        return ShapeDefinition.from_dict(self._current_state)
    
    def can_undo(self) -> bool:
        """Check if undo is available."""
        return len(self._undo_stack) > 0
    
    def can_redo(self) -> bool:
        """Check if redo is available."""
        return len(self._redo_stack) > 0
    
    def clear(self):
        """Clear all undo/redo history."""
        self._undo_stack.clear()
        self._redo_stack.clear()
        self._current_state = None
# Graphics Items for Interactive Editing
# =============================================================================

class ControlPointHandle(QGraphicsEllipseItem):
    """
    Draggable handle for a control point.
    
    Emits position changes back to the editor canvas.
    """
    
    def __init__(self, point: ControlPoint, canvas: 'ShapeEditorCanvas', parent=None):
        size = HANDLE_SIZE
        super().__init__(-size/2, -size/2, size, size, parent)
        
        self.point = point
        self.canvas = canvas
        self._updating = False  # Recursion guard
        
        # Position based on normalized coordinates
        self._update_position_from_point()
        
        # Appearance
        self.setBrush(QBrush(QColor("#3B82F6")))  # Blue
        self.setPen(QPen(QColor("#1D4ED8"), 1.5))
        
        # Interaction
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setCursor(QCursor(Qt.CursorShape.SizeAllCursor))
        self.setZValue(100)  # On top
    
    def _update_position_from_point(self):
        """Update graphics position from point's normalized coords."""
        self._updating = True
        x = self.point.x * self.canvas.canvas_size
        y = self.point.y * self.canvas.canvas_size
        self.setPos(x, y)
        self._updating = False
    
    def itemChange(self, change, value):
        """Handle position changes."""
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            # Prevent recursion when we call setPos below
            if self._updating:
                return value
            
            # Update normalized coordinates
            pos = self.pos()
            
            # Apply grid snapping if enabled
            if self.canvas.grid_snap:
                pos = self.canvas.snap_to_grid(pos)
                self._updating = True
                self.setPos(pos)
                self._updating = False
            
            # Clamp to canvas bounds
            x = max(0, min(self.canvas.canvas_size, pos.x()))
            y = max(0, min(self.canvas.canvas_size, pos.y()))
            
            # Update point normalized coordinates
            self.point.x = x / self.canvas.canvas_size
            self.point.y = y / self.canvas.canvas_size
            
            # Notify canvas to redraw
            self.canvas.update_shape_preview()
        
        return value
    
    def hoverEnterEvent(self, event):
        """Highlight on hover."""
        self.setBrush(QBrush(QColor("#60A5FA")))
        super().hoverEnterEvent(event)
    
    def hoverLeaveEvent(self, event):
        """Remove highlight."""
        self.setBrush(QBrush(QColor("#3B82F6")))
        super().hoverLeaveEvent(event)


class ConnectorHandle(QGraphicsEllipseItem):
    """
    Draggable handle for a connector that snaps to the shape edge.
    
    Coordinate system:
    - 0% / 0 rad = right (3 o'clock)
    - 25% / π/2 rad = bottom (6 o'clock)
    - 50% / π rad = left (9 o'clock)
    - 75% / 3π/2 rad = top (12 o'clock)
    - Angles increase clockwise (in screen coordinates)
    
    Uses path_start_offset from shape to convert between our angular
    coordinate system and Qt's path percent.
    """
    
    def __init__(self, connector: ShapeConnector, canvas: 'ShapeEditorCanvas', parent=None):
        size = CONNECTOR_SIZE
        super().__init__(-size/2, -size/2, size, size, parent)
        
        self.connector = connector
        self.canvas = canvas
        self._updating = False  # Recursion guard
        
        # Appearance - triangle/arrow shape would be better, but ellipse for now
        self.setBrush(QBrush(QColor("#F59E0B")))  # Amber
        self.setPen(QPen(QColor("#D97706"), 1.5))
        
        # Interaction
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setCursor(QCursor(Qt.CursorShape.SizeAllCursor))
        self.setZValue(99)
        
        # Initial position will be set by canvas after shape path is computed
    
    def _get_offset(self) -> float:
        """Get the path_start_offset from the shape."""
        if self.canvas.shape:
            return self.canvas.shape.path_start_offset
        return 0.0
    
    def _edge_to_qt_percent(self, edge_position: float) -> float:
        """Convert edge_position to Qt path percent."""
        offset = self._get_offset()
        qt_percent = (edge_position + offset) % 1.0
        if qt_percent < 0:
            qt_percent += 1.0
        return qt_percent
    
    def _qt_percent_to_edge(self, qt_percent: float) -> float:
        """Convert Qt path percent to edge_position."""
        offset = self._get_offset()
        edge_position = (qt_percent - offset) % 1.0
        if edge_position < 0:
            edge_position += 1.0
        return edge_position
    
    def update_position_on_edge(self, path: QPainterPath):
        """Update position based on edge_position along path."""
        if path.isEmpty():
            return
        
        self._updating = True
        # Convert edge_position to Qt path percent using offset
        qt_percent = self._edge_to_qt_percent(self.connector.edge_position)
        pt = path.pointAtPercent(qt_percent)
        self.setPos(pt)
        self._updating = False
    
    def itemChange(self, change, value):
        """Handle position changes - snap to edge."""
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            # Prevent recursion when we call setPos below
            if self._updating:
                return value
            
            # Snap to nearest point on shape edge
            pos = self.pos()
            path = self.canvas.current_path
            
            if path and not path.isEmpty():
                # Find nearest point on path (in Qt percent)
                best_qt_t = 0.0
                best_dist = float('inf')
                
                # Coarse search
                for i in range(101):
                    t = i / 100.0
                    pt = path.pointAtPercent(t)
                    dist = (pt.x() - pos.x())**2 + (pt.y() - pos.y())**2
                    if dist < best_dist:
                        best_dist = dist
                        best_qt_t = t
                
                # Fine search
                for i in range(-10, 11):
                    t = max(0, min(1, best_qt_t + i / 1000.0))
                    pt = path.pointAtPercent(t)
                    dist = (pt.x() - pos.x())**2 + (pt.y() - pos.y())**2
                    if dist < best_dist:
                        best_dist = dist
                        best_qt_t = t
                
                # Convert Qt percent to edge_position using offset
                self.connector.edge_position = self._qt_percent_to_edge(best_qt_t)
                
                # Snap to the edge point (with guard to prevent recursion)
                self._updating = True
                final_pt = path.pointAtPercent(best_qt_t)
                self.setPos(final_pt)
                self._updating = False
                
                # Update label in panel
                self.canvas.connector_moved.emit(self.connector.id)
        
        return value
    
    def hoverEnterEvent(self, event):
        """Highlight on hover."""
        self.setBrush(QBrush(QColor("#FBBF24")))
        super().hoverEnterEvent(event)
    
    def hoverLeaveEvent(self, event):
        """Remove highlight."""
        self.setBrush(QBrush(QColor("#F59E0B")))
        super().hoverLeaveEvent(event)


# =============================================================================
# Shape Editor Canvas
# =============================================================================

class ShapeEditorCanvas(QGraphicsView):
    """
    Interactive canvas for editing shape definitions.
    
    Features:
    - Shape preview with real-time updates
    - Draggable control points for polygons/paths
    - Draggable connectors that snap to edges
    - Grid overlay with optional snapping
    - Zoom and pan
    
    Signals:
        shape_modified: Emitted when shape is changed
        point_selected: Emitted when a control point is selected (point_id)
        connector_selected: Emitted when a connector is selected (connector_id)
        connector_moved: Emitted when a connector position changes (connector_id)
        drag_completed: Emitted when a drag operation completes (for undo)
    """
    
    shape_modified = pyqtSignal()
    point_selected = pyqtSignal(str)
    connector_selected = pyqtSignal(str)
    connector_moved = pyqtSignal(str)
    drag_completed = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.canvas_size = CANVAS_SIZE
        self.grid_snap = True
        self.grid_size = GRID_SIZE
        self.show_grid = True
        self.zoom_level = 1.0
        self._dragging = False  # Track if we're in a drag operation
        
        # Shape being edited
        self.shape: Optional[ShapeDefinition] = None
        self.current_path: Optional[QPainterPath] = None
        
        # Graphics items
        self._point_handles: dict[str, ControlPointHandle] = {}
        self._connector_handles: dict[str, ConnectorHandle] = {}
        self._shape_item: Optional[QGraphicsPathItem] = None
        self._grid_items: List[QGraphicsItem] = []
        
        # Setup
        self._setup_scene()
        self._setup_view()
    
    def _setup_scene(self):
        """Initialize the graphics scene."""
        self.scene = QGraphicsScene(self)
        self.scene.setSceneRect(0, 0, self.canvas_size, self.canvas_size)
        self.setScene(self.scene)
        
        # Background
        self.scene.setBackgroundBrush(QBrush(QColor("#FAFAFA")))
    
    def _setup_view(self):
        """Configure view settings."""
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setMinimumSize(self.canvas_size + 20, self.canvas_size + 20)
        self.setMaximumSize(self.canvas_size + 20, self.canvas_size + 20)
    
    def mousePressEvent(self, event):
        """Track start of potential drag operation."""
        super().mousePressEvent(event)
        # Check if we clicked on a handle
        item = self.itemAt(event.pos())
        if isinstance(item, (ControlPointHandle, ConnectorHandle)):
            self._dragging = True
    
    def mouseReleaseEvent(self, event):
        """Handle end of drag operation - emit signal for undo."""
        super().mouseReleaseEvent(event)
        if self._dragging:
            self._dragging = False
            self.drag_completed.emit()
    
    def set_shape(self, shape: ShapeDefinition):
        """Set the shape to edit."""
        from services.shape_manager import get_shape_manager
        
        self.shape = shape.copy()  # Work on a copy
        
        # Ensure path_start_offset is calculated (for legacy/imported shapes)
        if self.shape.path_start_offset == 0.0 and self.shape.primitives:
            # Check if it's not an ellipse (which naturally has 0 offset)
            is_simple_ellipse = (
                len(self.shape.primitives) == 1 and 
                self.shape.primitives[0].primitive_type.name == 'ELLIPSE'
            )
            if not is_simple_ellipse:
                shape_manager = get_shape_manager()
                self.shape.path_start_offset = shape_manager.calculate_path_start_offset(self.shape)
        
        self._rebuild_scene()
    
    def get_shape(self) -> Optional[ShapeDefinition]:
        """Get the edited shape."""
        return self.shape
    
    def _rebuild_scene(self):
        """Rebuild all scene items from shape definition."""
        # Clear existing items
        self._clear_handles()
        if self._shape_item:
            self.scene.removeItem(self._shape_item)
            self._shape_item = None
        
        if not self.shape:
            return
        
        # Draw grid
        self._draw_grid()
        
        # Create shape path and preview
        self._update_shape_path()
        
        # Create control point handles for polygon/path primitives
        self._create_point_handles()
        
        # Create connector handles
        self._create_connector_handles()
    
    def _clear_handles(self):
        """Remove all handles from scene."""
        for handle in self._point_handles.values():
            self.scene.removeItem(handle)
        self._point_handles.clear()
        
        for handle in self._connector_handles.values():
            self.scene.removeItem(handle)
        self._connector_handles.clear()
    
    def _draw_grid(self):
        """Draw grid overlay."""
        # Remove old grid
        for item in self._grid_items:
            self.scene.removeItem(item)
        self._grid_items.clear()
        
        if not self.show_grid:
            return
        
        # Draw grid lines
        grid_pen = QPen(QColor("#E5E7EB"), 0.5)
        
        for i in range(0, self.canvas_size + 1, self.grid_size):
            # Vertical line
            line_v = self.scene.addLine(i, 0, i, self.canvas_size, grid_pen)
            line_v.setZValue(-10)
            self._grid_items.append(line_v)
            
            # Horizontal line
            line_h = self.scene.addLine(0, i, self.canvas_size, i, grid_pen)
            line_h.setZValue(-10)
            self._grid_items.append(line_h)
        
        # Draw border
        border_pen = QPen(QColor("#9CA3AF"), 1)
        border = self.scene.addRect(0, 0, self.canvas_size, self.canvas_size, border_pen)
        border.setZValue(-9)
        self._grid_items.append(border)
    
    def _update_shape_path(self):
        """Compute and display the shape path."""
        if not self.shape:
            return
        
        # Remove old shape item
        if self._shape_item:
            self.scene.removeItem(self._shape_item)
        
        # Build unified path from primitives
        self.current_path = self._build_path_from_primitives()
        
        if self.current_path and not self.current_path.isEmpty():
            # Create path item
            self._shape_item = QGraphicsPathItem(self.current_path)
            
            # Apply style
            style = self.shape.style
            fill_color = QColor(style.fill_color)
            fill_color.setAlphaF(style.fill_opacity)
            self._shape_item.setBrush(QBrush(fill_color))
            
            stroke_color = QColor(style.stroke_color)
            stroke_color.setAlphaF(style.stroke_opacity)
            pen = QPen(stroke_color, style.stroke_width)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            self._shape_item.setPen(pen)
            
            self._shape_item.setZValue(0)
            self.scene.addItem(self._shape_item)
            
            # Draw icon text
            self._draw_icon_text()
    
    def _build_path_from_primitives(self) -> QPainterPath:
        """Build unified path from all primitives."""
        if not self.shape or not self.shape.primitives:
            return QPainterPath()
        
        paths = []
        for prim in self.shape.primitives:
            path = self._primitive_to_path(prim)
            if not path.isEmpty():
                paths.append(path)
        
        if not paths:
            return QPainterPath()
        
        # Union all paths
        result = paths[0]
        for path in paths[1:]:
            result = result.united(path)
        
        return result
    
    def _primitive_to_path(self, prim: ShapePrimitive) -> QPainterPath:
        """Convert a primitive to QPainterPath."""
        path = QPainterPath()
        s = self.canvas_size  # Scale factor
        
        if prim.primitive_type == PrimitiveType.ELLIPSE:
            x, y, w, h = prim.bounds
            rect = QRectF(x * s, y * s, w * s, h * s)
            
            if prim.rotation != 0:
                temp = QPainterPath()
                temp.addEllipse(QRectF(-w * s / 2, -h * s / 2, w * s, h * s))
                transform = QTransform()
                transform.translate((x + w / 2) * s, (y + h / 2) * s)
                transform.rotate(prim.rotation)
                path = transform.map(temp)
            else:
                path.addEllipse(rect)
                
        elif prim.primitive_type == PrimitiveType.RECTANGLE:
            x, y, w, h = prim.bounds
            rect = QRectF(x * s, y * s, w * s, h * s)
            
            if prim.corner_radius > 0:
                r = prim.corner_radius * min(w * s, h * s)
                path.addRoundedRect(rect, r, r)
            else:
                path.addRect(rect)
                
            if prim.rotation != 0:
                transform = QTransform()
                center = rect.center()
                transform.translate(center.x(), center.y())
                transform.rotate(prim.rotation)
                transform.translate(-center.x(), -center.y())
                path = transform.map(path)
                
        elif prim.primitive_type == PrimitiveType.POLYGON:
            if prim.points:
                path.moveTo(prim.points[0].x * s, prim.points[0].y * s)
                for pt in prim.points[1:]:
                    path.lineTo(pt.x * s, pt.y * s)
                if prim.closed:
                    path.closeSubpath()
                    
        elif prim.primitive_type == PrimitiveType.PATH:
            # Handle bezier curves
            if prim.points:
                points_dict = {p.id: p for p in prim.points}
                
                if not prim.edges:
                    # Auto-connect as lines
                    path.moveTo(prim.points[0].x * s, prim.points[0].y * s)
                    for pt in prim.points[1:]:
                        path.lineTo(pt.x * s, pt.y * s)
                else:
                    # Process edges
                    first_edge = prim.edges[0]
                    start = points_dict.get(first_edge.start_point_id)
                    if start:
                        path.moveTo(start.x * s, start.y * s)
                    
                    for edge in prim.edges:
                        end = points_dict.get(edge.end_point_id)
                        if not end:
                            continue
                        
                        if edge.edge_type == EdgeType.LINE:
                            path.lineTo(end.x * s, end.y * s)
                        elif edge.edge_type == EdgeType.QUADRATIC and edge.control1:
                            cx, cy = edge.control1
                            path.quadTo(cx * s, cy * s, end.x * s, end.y * s)
                        elif edge.edge_type == EdgeType.CUBIC and edge.control1 and edge.control2:
                            c1x, c1y = edge.control1
                            c2x, c2y = edge.control2
                            path.cubicTo(c1x * s, c1y * s, c2x * s, c2y * s, end.x * s, end.y * s)
                        else:
                            path.lineTo(end.x * s, end.y * s)
                
                if prim.closed:
                    path.closeSubpath()
        
        return path
    
    def _draw_icon_text(self):
        """Draw the icon text in the center of the shape."""
        if not self.shape or not self.shape.style.icon_text:
            return
        
        style = self.shape.style
        
        # Create text item
        text_item = self.scene.addText(style.icon_text)
        font = QFont(style.icon_font_family, style.icon_font_size)
        if style.icon_bold:
            font.setBold(True)
        text_item.setFont(font)
        text_item.setDefaultTextColor(QColor(style.icon_color))
        
        # Center in shape
        if self.current_path:
            center = self.current_path.boundingRect().center()
            text_rect = text_item.boundingRect()
            text_item.setPos(
                center.x() - text_rect.width() / 2,
                center.y() - text_rect.height() / 2
            )
        
        text_item.setZValue(50)
    
    def _create_point_handles(self):
        """Create draggable handles for polygon/path control points."""
        if not self.shape:
            return
        
        for prim in self.shape.primitives:
            if prim.primitive_type in (PrimitiveType.POLYGON, PrimitiveType.PATH):
                for point in prim.points:
                    handle = ControlPointHandle(point, self)
                    self.scene.addItem(handle)
                    self._point_handles[point.id] = handle
    
    def _create_connector_handles(self):
        """Create draggable handles for connectors."""
        if not self.shape or not self.current_path:
            return
        
        for conn in self.shape.connectors:
            handle = ConnectorHandle(conn, self)
            handle.update_position_on_edge(self.current_path)
            self.scene.addItem(handle)
            self._connector_handles[conn.id] = handle
    
    def update_shape_preview(self):
        """Refresh the shape preview after changes."""
        self._update_shape_path()
        
        # Update connector positions
        if self.current_path:
            for handle in self._connector_handles.values():
                handle.update_position_on_edge(self.current_path)
        
        self.shape_modified.emit()
    
    def snap_to_grid(self, pos: QPointF) -> QPointF:
        """Snap a position to the grid."""
        if not self.grid_snap:
            return pos
        
        x = round(pos.x() / self.grid_size) * self.grid_size
        y = round(pos.y() / self.grid_size) * self.grid_size
        return QPointF(x, y)
    
    def set_grid_snap(self, enabled: bool):
        """Enable or disable grid snapping."""
        self.grid_snap = enabled
    
    def set_show_grid(self, show: bool):
        """Show or hide the grid."""
        self.show_grid = show
        self._draw_grid()
    
    def add_primitive(self, prim_type: PrimitiveType):
        """Add a new primitive to the shape."""
        if not self.shape:
            return
        
        if prim_type == PrimitiveType.ELLIPSE:
            prim = ShapePrimitive.create_ellipse(0.25, 0.25, 0.5, 0.5)
        elif prim_type == PrimitiveType.RECTANGLE:
            prim = ShapePrimitive.create_rectangle(0.25, 0.25, 0.5, 0.5, 0.1)
        elif prim_type == PrimitiveType.POLYGON:
            # Create a triangle
            prim = ShapePrimitive.create_polygon([
                (0.5, 0.2), (0.8, 0.8), (0.2, 0.8)
            ])
        else:
            return
        
        self.shape.add_primitive(prim)
        self._rebuild_scene()
    
    def add_connector(self):
        """Add a new connector at position 0."""
        if not self.shape:
            return
        
        # Find a position not already used
        positions = [c.edge_position for c in self.shape.connectors]
        new_pos = 0.0
        for p in [0.0, 0.125, 0.25, 0.375, 0.5, 0.625, 0.75, 0.875]:
            if p not in positions:
                new_pos = p
                break
        
        conn = ShapeConnector(edge_position=new_pos, label=f"C{len(self.shape.connectors)+1}")
        self.shape.add_connector(conn)
        self._rebuild_scene()
    
    def remove_selected_items(self):
        """Remove selected control points or connectors."""
        # This is a simplified version - full implementation would track selection
        pass


# =============================================================================
# Style Editor Panel
# =============================================================================

class StyleEditorPanel(QGroupBox):
    """Panel for editing shape style (colors, stroke, icon)."""
    
    style_changed = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__("Style", parent)
        self.shape: Optional[ShapeDefinition] = None
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QFormLayout(self)
        layout.setSpacing(8)
        
        # Fill color
        self.fill_color_btn = QPushButton()
        self.fill_color_btn.setFixedSize(60, 24)
        self.fill_color_btn.clicked.connect(self._pick_fill_color)
        layout.addRow("Fill:", self.fill_color_btn)
        
        # Fill opacity
        self.fill_opacity = QSlider(Qt.Orientation.Horizontal)
        self.fill_opacity.setRange(0, 100)
        self.fill_opacity.setValue(100)
        self.fill_opacity.valueChanged.connect(self._on_fill_opacity_changed)
        layout.addRow("Fill Opacity:", self.fill_opacity)
        
        # Stroke color
        self.stroke_color_btn = QPushButton()
        self.stroke_color_btn.setFixedSize(60, 24)
        self.stroke_color_btn.clicked.connect(self._pick_stroke_color)
        layout.addRow("Stroke:", self.stroke_color_btn)
        
        # Stroke width
        self.stroke_width = QDoubleSpinBox()
        self.stroke_width.setRange(0.5, 10.0)
        self.stroke_width.setSingleStep(0.5)
        self.stroke_width.setValue(2.0)
        self.stroke_width.valueChanged.connect(self._on_stroke_width_changed)
        layout.addRow("Stroke Width:", self.stroke_width)
        
        # Icon text
        self.icon_text = QLineEdit()
        self.icon_text.setMaxLength(4)
        self.icon_text.textChanged.connect(self._on_icon_text_changed)
        layout.addRow("Icon Text:", self.icon_text)
        
        # Icon size
        self.icon_size = QSpinBox()
        self.icon_size.setRange(8, 32)
        self.icon_size.setValue(16)
        self.icon_size.valueChanged.connect(self._on_icon_size_changed)
        layout.addRow("Icon Size:", self.icon_size)
        
        # Icon color
        self.icon_color_btn = QPushButton()
        self.icon_color_btn.setFixedSize(60, 24)
        self.icon_color_btn.clicked.connect(self._pick_icon_color)
        layout.addRow("Icon Color:", self.icon_color_btn)
    
    def set_shape(self, shape: ShapeDefinition):
        """Load shape style into the panel."""
        self.shape = shape
        style = shape.style
        
        self._update_color_button(self.fill_color_btn, style.fill_color)
        self.fill_opacity.setValue(int(style.fill_opacity * 100))
        self._update_color_button(self.stroke_color_btn, style.stroke_color)
        self.stroke_width.setValue(style.stroke_width)
        self.icon_text.setText(style.icon_text)
        self.icon_size.setValue(style.icon_font_size)
        self._update_color_button(self.icon_color_btn, style.icon_color)
    
    def _update_color_button(self, btn: QPushButton, color: str):
        """Update button background to show color."""
        btn.setStyleSheet(f"background-color: {color}; border: 1px solid #ccc;")
        btn.setProperty("color", color)
    
    def _pick_fill_color(self):
        """Open color picker for fill."""
        current = QColor(self.fill_color_btn.property("color") or "#4A90D9")
        color = QColorDialog.getColor(current, self, "Pick Fill Color")
        if color.isValid():
            self._update_color_button(self.fill_color_btn, color.name())
            if self.shape:
                self.shape.style.fill_color = color.name()
                self.style_changed.emit()
    
    def _pick_stroke_color(self):
        """Open color picker for stroke."""
        current = QColor(self.stroke_color_btn.property("color") or "#2563EB")
        color = QColorDialog.getColor(current, self, "Pick Stroke Color")
        if color.isValid():
            self._update_color_button(self.stroke_color_btn, color.name())
            if self.shape:
                self.shape.style.stroke_color = color.name()
                self.style_changed.emit()
    
    def _pick_icon_color(self):
        """Open color picker for icon."""
        current = QColor(self.icon_color_btn.property("color") or "#FFFFFF")
        color = QColorDialog.getColor(current, self, "Pick Icon Color")
        if color.isValid():
            self._update_color_button(self.icon_color_btn, color.name())
            if self.shape:
                self.shape.style.icon_color = color.name()
                self.style_changed.emit()
    
    def _on_fill_opacity_changed(self, value: int):
        if self.shape:
            self.shape.style.fill_opacity = value / 100.0
            self.style_changed.emit()
    
    def _on_stroke_width_changed(self, value: float):
        if self.shape:
            self.shape.style.stroke_width = value
            self.style_changed.emit()
    
    def _on_icon_text_changed(self, text: str):
        if self.shape:
            self.shape.style.icon_text = text
            self.style_changed.emit()
    
    def _on_icon_size_changed(self, value: int):
        if self.shape:
            self.shape.style.icon_font_size = value
            self.style_changed.emit()


# =============================================================================
# Primitives Panel
# =============================================================================

class PrimitivesPanel(QGroupBox):
    """Panel for managing shape primitives."""
    
    primitive_selected = pyqtSignal(str)  # primitive_id
    primitive_add_requested = pyqtSignal(object)  # PrimitiveType
    primitive_remove_requested = pyqtSignal(str)  # primitive_id
    
    def __init__(self, parent=None):
        super().__init__("Primitives", parent)
        self.shape: Optional[ShapeDefinition] = None
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        
        # List of primitives
        self.prim_list = QListWidget()
        self.prim_list.currentItemChanged.connect(self._on_selection_changed)
        layout.addWidget(self.prim_list)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        self.add_ellipse_btn = QPushButton("+ Ellipse")
        self.add_ellipse_btn.clicked.connect(lambda: self.primitive_add_requested.emit(PrimitiveType.ELLIPSE))
        btn_layout.addWidget(self.add_ellipse_btn)
        
        self.add_rect_btn = QPushButton("+ Rect")
        self.add_rect_btn.clicked.connect(lambda: self.primitive_add_requested.emit(PrimitiveType.RECTANGLE))
        btn_layout.addWidget(self.add_rect_btn)
        
        self.add_poly_btn = QPushButton("+ Polygon")
        self.add_poly_btn.clicked.connect(lambda: self.primitive_add_requested.emit(PrimitiveType.POLYGON))
        btn_layout.addWidget(self.add_poly_btn)
        
        layout.addLayout(btn_layout)
        
        # Remove button
        self.remove_btn = QPushButton("Remove Selected")
        self.remove_btn.clicked.connect(self._remove_selected)
        layout.addWidget(self.remove_btn)
    
    def set_shape(self, shape: ShapeDefinition):
        """Load primitives into the list."""
        self.shape = shape
        self._refresh_list()
    
    def _refresh_list(self):
        """Refresh the primitives list."""
        self.prim_list.clear()
        if not self.shape:
            return
        
        for prim in self.shape.primitives:
            icon = {
                PrimitiveType.ELLIPSE: "●",
                PrimitiveType.RECTANGLE: "▢",
                PrimitiveType.POLYGON: "△",
                PrimitiveType.PATH: "〜",
            }.get(prim.primitive_type, "?")
            
            item = QListWidgetItem(f"{icon} {prim.primitive_type.value} ({prim.id[:8]})")
            item.setData(Qt.ItemDataRole.UserRole, prim.id)
            self.prim_list.addItem(item)
    
    def _on_selection_changed(self, current, previous):
        if current:
            prim_id = current.data(Qt.ItemDataRole.UserRole)
            self.primitive_selected.emit(prim_id)
    
    def _remove_selected(self):
        current = self.prim_list.currentItem()
        if current and self.shape:
            prim_id = current.data(Qt.ItemDataRole.UserRole)
            if len(self.shape.primitives) > 1:  # Keep at least one
                self.primitive_remove_requested.emit(prim_id)


# =============================================================================
# Connectors Panel
# =============================================================================

class ConnectorsPanel(QGroupBox):
    """Panel for managing shape connectors."""
    
    connector_selected = pyqtSignal(str)  # connector_id
    connector_add_requested = pyqtSignal()
    connector_remove_requested = pyqtSignal(str)  # connector_id
    connector_label_changed = pyqtSignal(str, str)  # connector_id, new_label
    
    def __init__(self, parent=None):
        super().__init__("Connectors", parent)
        self.shape: Optional[ShapeDefinition] = None
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        
        # List of connectors
        self.conn_list = QListWidget()
        self.conn_list.currentItemChanged.connect(self._on_selection_changed)
        layout.addWidget(self.conn_list)
        
        # Label editor
        label_layout = QHBoxLayout()
        label_layout.addWidget(QLabel("Label:"))
        self.label_edit = QLineEdit()
        self.label_edit.setMaxLength(10)
        self.label_edit.textChanged.connect(self._on_label_changed)
        label_layout.addWidget(self.label_edit)
        layout.addLayout(label_layout)
        
        # Position display
        pos_layout = QHBoxLayout()
        pos_layout.addWidget(QLabel("Position:"))
        self.pos_label = QLabel("0%")
        pos_layout.addWidget(self.pos_label)
        pos_layout.addStretch()
        layout.addLayout(pos_layout)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        self.add_btn = QPushButton("+ Add")
        self.add_btn.clicked.connect(self._add_connector)
        btn_layout.addWidget(self.add_btn)
        
        self.remove_btn = QPushButton("- Remove")
        self.remove_btn.clicked.connect(self._remove_selected)
        btn_layout.addWidget(self.remove_btn)
        
        layout.addLayout(btn_layout)
    
    def set_shape(self, shape: ShapeDefinition):
        """Load connectors into the list."""
        self.shape = shape
        self._refresh_list()
    
    def _refresh_list(self):
        """Refresh the connectors list."""
        self.conn_list.clear()
        if not self.shape:
            return
        
        for conn in self.shape.connectors:
            pos_pct = int(conn.edge_position * 100)
            item = QListWidgetItem(f"▸ {conn.label} @ {pos_pct}%")
            item.setData(Qt.ItemDataRole.UserRole, conn.id)
            self.conn_list.addItem(item)
    
    def _on_selection_changed(self, current, previous):
        if current and self.shape:
            conn_id = current.data(Qt.ItemDataRole.UserRole)
            conn = self.shape.get_connector_by_id(conn_id)
            if conn:
                self.label_edit.blockSignals(True)
                self.label_edit.setText(conn.label)
                self.label_edit.blockSignals(False)
                self.pos_label.setText(f"{int(conn.edge_position * 100)}%")
            self.connector_selected.emit(conn_id)
    
    def _on_label_changed(self, text: str):
        current = self.conn_list.currentItem()
        if current and self.shape:
            conn_id = current.data(Qt.ItemDataRole.UserRole)
            self.connector_label_changed.emit(conn_id, text)
    
    def update_connector_position(self, conn_id: str):
        """Update display when connector is moved."""
        if not self.shape:
            return
        conn = self.shape.get_connector_by_id(conn_id)
        if conn:
            # Update list item
            for i in range(self.conn_list.count()):
                item = self.conn_list.item(i)
                if item.data(Qt.ItemDataRole.UserRole) == conn_id:
                    pos_pct = int(conn.edge_position * 100)
                    item.setText(f"▸ {conn.label} @ {pos_pct}%")
                    break
            
            # Update position label if this is selected
            current = self.conn_list.currentItem()
            if current and current.data(Qt.ItemDataRole.UserRole) == conn_id:
                self.pos_label.setText(f"{int(conn.edge_position * 100)}%")
    
    def _add_connector(self):
        self.connector_add_requested.emit()
    
    def _remove_selected(self):
        current = self.conn_list.currentItem()
        if current and self.shape:
            conn_id = current.data(Qt.ItemDataRole.UserRole)
            if len(self.shape.connectors) > 1:  # Keep at least one
                self.connector_remove_requested.emit(conn_id)


# =============================================================================
# Main Shape Editor Dialog
# =============================================================================

class ShapeEditorDialog(QDialog):
    """
    Dialog for editing node shape definitions.
    
    Layout:
    ┌─────────────────────────────────────────────────────┐
    │ [File▼] [Edit▼] [View▼]    Shape Editor: HOST  [X] │
    ├─────────────────────────────────────────────────────┤
    │ ┌─────────────────────┐ ┌─────────────────────────┐ │
    │ │                     │ │ Primitives      [+] [-] │ │
    │ │  Interactive Canvas │ │ ├─ ● ellipse_1          │ │
    │ │                     │ │ └─ ▢ rect_1             │ │
    │ │  ○ = control point  │ ├─────────────────────────┤ │
    │ │  ◇ = connector      │ │ Style                   │ │
    │ │                     │ │ Fill: [■] [___]         │ │
    │ │                     │ │ Stroke: [■] [2px]       │ │
    │ │                     │ ├─────────────────────────┤ │
    │ │                     │ │ Connectors      [+] [-] │ │
    │ │                     │ │ ├─ ▸ c1 "N" @ 0%       │ │
    │ └─────────────────────┘ └─────────────────────────┘ │
    ├─────────────────────────────────────────────────────┤
    │ ☑ Grid Snap [10px]  │ Zoom: 100% │ [Cancel] [Save] │
    └─────────────────────────────────────────────────────┘
    """
    
    def __init__(self, shape: ShapeDefinition, parent=None):
        super().__init__(parent)
        
        self.original_shape = shape
        self.shape = shape.copy()
        
        # Undo/redo support
        self.undo_stack = UndoStack()
        
        self._setup_ui()
        self._connect_signals()
        self._load_shape()
    
    def _setup_ui(self):
        """Build the dialog UI."""
        self.setWindowTitle(f"Shape Editor: {self.shape.name}")
        self.setMinimumSize(750, 550)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        
        # Create canvas first (needed by menu bar actions)
        self.canvas = ShapeEditorCanvas()
        
        # Menu bar (uses self.canvas)
        self._create_menu_bar(layout)
        
        # Main content: canvas + panels
        content = QHBoxLayout()
        
        # Canvas (left side) - already created above
        content.addWidget(self.canvas)
        
        # Panels (right side)
        panels = QVBoxLayout()
        panels.setSpacing(8)
        
        # Primitives panel
        self.primitives_panel = PrimitivesPanel()
        self.primitives_panel.setMaximumHeight(150)
        panels.addWidget(self.primitives_panel)
        
        # Style panel
        self.style_panel = StyleEditorPanel()
        panels.addWidget(self.style_panel)
        
        # Connectors panel
        self.connectors_panel = ConnectorsPanel()
        self.connectors_panel.setMaximumHeight(180)
        panels.addWidget(self.connectors_panel)
        
        panels.addStretch()
        
        panel_widget = QWidget()
        panel_widget.setLayout(panels)
        panel_widget.setFixedWidth(220)
        content.addWidget(panel_widget)
        
        layout.addLayout(content)
        
        # Bottom bar
        bottom = QHBoxLayout()
        
        # Grid snap checkbox
        self.grid_snap_cb = QCheckBox("Grid Snap")
        self.grid_snap_cb.setChecked(True)
        self.grid_snap_cb.toggled.connect(self.canvas.set_grid_snap)
        bottom.addWidget(self.grid_snap_cb)
        
        # Show grid checkbox
        self.show_grid_cb = QCheckBox("Show Grid")
        self.show_grid_cb.setChecked(True)
        self.show_grid_cb.toggled.connect(self.canvas.set_show_grid)
        bottom.addWidget(self.show_grid_cb)
        
        bottom.addStretch()
        
        # Dialog buttons
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Cancel | 
            QDialogButtonBox.StandardButton.Save
        )
        self.button_box.accepted.connect(self._on_save)
        self.button_box.rejected.connect(self.reject)
        bottom.addWidget(self.button_box)
        
        layout.addLayout(bottom)
    
    def _create_menu_bar(self, layout: QVBoxLayout):
        """Create menu bar."""
        menu_bar = QMenuBar()
        
        # File menu
        file_menu = menu_bar.addMenu("File")
        
        load_action = file_menu.addAction("Load Shape...")
        load_action.triggered.connect(self._load_shape_file)
        
        save_action = file_menu.addAction("Save Shape...")
        save_action.triggered.connect(self._save_shape_file)
        
        file_menu.addSeparator()
        
        reset_action = file_menu.addAction("Reset to Default")
        reset_action.triggered.connect(self._reset_to_default)
        
        # Edit menu
        edit_menu = menu_bar.addMenu("Edit")
        
        # Undo/Redo
        self.undo_action = edit_menu.addAction("Undo")
        self.undo_action.setShortcut(QKeySequence.StandardKey.Undo)
        self.undo_action.triggered.connect(self._on_undo)
        self.undo_action.setEnabled(False)
        
        self.redo_action = edit_menu.addAction("Redo")
        self.redo_action.setShortcut(QKeySequence.StandardKey.Redo)
        self.redo_action.triggered.connect(self._on_redo)
        self.redo_action.setEnabled(False)
        
        edit_menu.addSeparator()
        
        add_ellipse = edit_menu.addAction("Add Ellipse")
        add_ellipse.triggered.connect(lambda: self._on_primitive_add(PrimitiveType.ELLIPSE))
        
        add_rect = edit_menu.addAction("Add Rectangle")
        add_rect.triggered.connect(lambda: self._on_primitive_add(PrimitiveType.RECTANGLE))
        
        add_poly = edit_menu.addAction("Add Polygon")
        add_poly.triggered.connect(lambda: self._on_primitive_add(PrimitiveType.POLYGON))
        
        edit_menu.addSeparator()
        
        add_conn = edit_menu.addAction("Add Connector")
        add_conn.triggered.connect(self._on_connector_add)
        
        # View menu
        view_menu = menu_bar.addMenu("View")
        
        self.grid_action = view_menu.addAction("Show Grid")
        self.grid_action.setCheckable(True)
        self.grid_action.setChecked(True)
        # Connection deferred to _connect_signals
        
        self.snap_action = view_menu.addAction("Snap to Grid")
        self.snap_action.setCheckable(True)
        self.snap_action.setChecked(True)
        # Connection deferred to _connect_signals
        
        layout.setMenuBar(menu_bar)
    
    def _connect_signals(self):
        """Connect all signals."""
        # Canvas signals
        self.canvas.shape_modified.connect(self._on_shape_modified)
        self.canvas.connector_moved.connect(self.connectors_panel.update_connector_position)
        self.canvas.drag_completed.connect(self._on_drag_completed)
        
        # Style panel
        self.style_panel.style_changed.connect(self._on_style_changed)
        
        # Primitives panel
        self.primitives_panel.primitive_add_requested.connect(self._on_primitive_add)
        self.primitives_panel.primitive_remove_requested.connect(self._on_primitive_remove)
        
        # Connectors panel
        self.connectors_panel.connector_add_requested.connect(self._on_connector_add)
        self.connectors_panel.connector_remove_requested.connect(self._on_connector_remove)
        self.connectors_panel.connector_label_changed.connect(self._on_connector_label_changed)
        
        # Menu actions (deferred from _create_menu_bar)
        self.grid_action.triggered.connect(self.show_grid_cb.setChecked)
        self.snap_action.triggered.connect(self.grid_snap_cb.setChecked)
    
    def _load_shape(self):
        """Load the shape into all editors."""
        self.canvas.set_shape(self.shape)
        # Panels share reference to canvas's shape
        canvas_shape = self.canvas.get_shape()
        self.style_panel.set_shape(canvas_shape)
        self.primitives_panel.set_shape(canvas_shape)
        self.connectors_panel.set_shape(canvas_shape)
        
        # Initialize undo stack with current state
        self.undo_stack.initialize(canvas_shape)
        self._update_undo_actions()
    
    def _on_shape_modified(self):
        """Handle shape modification from canvas."""
        # Sync panels with canvas shape
        self.shape = self.canvas.get_shape()
        self.primitives_panel.set_shape(self.shape)
        self.connectors_panel.set_shape(self.shape)
        
        # Note: We don't save undo state here because this is called
        # continuously during drag operations. State is saved on mouse release.
    
    def _on_drag_completed(self):
        """Handle completion of a drag operation - save state for undo."""
        self._save_undo_state()
    
    def _on_style_changed(self):
        """Handle style changes from panel."""
        # Save state for undo before applying change
        self._save_undo_state()
        # Style panel modifies the shape directly, just refresh canvas
        self.canvas.shape = self.style_panel.shape
        self.canvas._rebuild_scene()
    
    def _on_primitive_add(self, prim_type: PrimitiveType):
        """Handle primitive add from panel."""
        self._save_undo_state()
        self.canvas.add_primitive(prim_type)
        # Sync panel with updated canvas shape
        self.primitives_panel.set_shape(self.canvas.get_shape())
    
    def _on_primitive_remove(self, prim_id: str):
        """Handle primitive remove from panel."""
        self._save_undo_state()
        shape = self.canvas.get_shape()
        if shape and len(shape.primitives) > 1:
            shape.remove_primitive(prim_id)
            self.canvas._rebuild_scene()
            self.primitives_panel.set_shape(shape)
    
    def _on_connector_add(self):
        """Handle connector add from panel."""
        self._save_undo_state()
        self.canvas.add_connector()
        # Sync panel with updated canvas shape
        self.connectors_panel.set_shape(self.canvas.get_shape())
    
    def _on_connector_remove(self, conn_id: str):
        """Handle connector remove from panel."""
        self._save_undo_state()
        shape = self.canvas.get_shape()
        if shape and len(shape.connectors) > 1:
            shape.remove_connector(conn_id)
            self.canvas._rebuild_scene()
            self.connectors_panel.set_shape(shape)
    
    def _on_connector_label_changed(self, conn_id: str, new_label: str):
        """Handle connector label change from panel."""
        shape = self.canvas.get_shape()
        if shape:
            conn = shape.get_connector_by_id(conn_id)
            if conn:
                conn.label = new_label
                self.connectors_panel._refresh_list()
    
    # ==================== Undo/Redo ====================
    
    def _save_undo_state(self):
        """Save current shape state to undo stack."""
        if hasattr(self, '_in_undo_redo') and self._in_undo_redo:
            return  # Don't save state during undo/redo
        
        shape = self.canvas.get_shape()
        if shape:
            self.undo_stack.save_state(shape)
            self._update_undo_actions()
    
    def _update_undo_actions(self):
        """Update enabled state of undo/redo menu actions."""
        if hasattr(self, 'undo_action'):
            self.undo_action.setEnabled(self.undo_stack.can_undo())
        if hasattr(self, 'redo_action'):
            self.redo_action.setEnabled(self.undo_stack.can_redo())
    
    def _on_undo(self):
        """Perform undo operation."""
        shape = self.undo_stack.undo()
        if shape:
            self._in_undo_redo = True
            self.shape = shape
            self.canvas.set_shape(shape)
            self.style_panel.set_shape(shape)
            self.primitives_panel.set_shape(shape)
            self.connectors_panel.set_shape(shape)
            self._in_undo_redo = False
            self._update_undo_actions()
    
    def _on_redo(self):
        """Perform redo operation."""
        shape = self.undo_stack.redo()
        if shape:
            self._in_undo_redo = True
            self.shape = shape
            self.canvas.set_shape(shape)
            self.style_panel.set_shape(shape)
            self.primitives_panel.set_shape(shape)
            self.connectors_panel.set_shape(shape)
            self._in_undo_redo = False
            self._update_undo_actions()
    
    def _on_save(self):
        """Save changes and close."""
        # Update the shape manager
        shape_manager = get_shape_manager()
        final_shape = self.canvas.get_shape()
        if final_shape:
            final_shape.modified = True
            final_shape.is_default = False
            # Recalculate path_start_offset in case primitives changed
            shape_manager.update_shape_path_offset(final_shape)
            shape_manager.update_shape(final_shape)
        self.accept()
    
    def _load_shape_file(self):
        """Load a shape from file."""
        filepath, _ = QFileDialog.getOpenFileName(
            self, "Load Shape", "", "JSON Files (*.json)"
        )
        if filepath:
            loaded = ShapeDefinition.load_from_file(filepath)
            if loaded:
                self.shape = loaded
                self._load_shape()
    
    def _save_shape_file(self):
        """Save shape to file."""
        filepath, _ = QFileDialog.getSaveFileName(
            self, "Save Shape", f"{self.shape.id}.json", "JSON Files (*.json)"
        )
        if filepath:
            shape = self.canvas.get_shape()
            if shape:
                shape.save_to_file(filepath)
    
    def _reset_to_default(self):
        """Reset shape to default."""
        reply = QMessageBox.question(
            self, "Reset Shape",
            "Reset this shape to its default? All customizations will be lost.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            shape_manager = get_shape_manager()
            if shape_manager.reset_shape_to_default(self.shape.id):
                self.shape = shape_manager.get_shape(self.shape.id)
                self._load_shape()
    
    def get_shape(self) -> Optional[ShapeDefinition]:
        """Get the edited shape."""
        return self.canvas.get_shape()
