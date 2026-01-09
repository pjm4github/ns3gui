"""
Shape Editor Dialog.

A visual editor for customizing node shapes with:
- Interactive canvas with enhanced editing (boolean ops, bezier curves, rotation)
- Primitive list with 8-character IDs and perimeter selection
- Style editor with color buttons for fill, stroke, and text
- Connector editor with direction selection (In/Out/InOut)
- Grid and rotation snapping (Ctrl+drag)
- Grouping and ungrouping
- Vertex editing with bezier handles
- Boolean operations (union, intersect, subtract, combine, fragment)
- Undo/redo support

Usage:
    dialog = ShapeEditorDialog(shape_definition, parent)
    if dialog.exec() == QDialog.DialogCode.Accepted:
        modified_shape = dialog.get_shape()
"""

import math
import uuid
import traceback
from typing import Optional, List, Tuple, Dict, Set
from dataclasses import dataclass, field
from enum import Enum

from PyQt6.QtCore import Qt, QPointF, QRectF, pyqtSignal, QTimer, QPoint, QRect, QSize
from PyQt6.QtGui import (
    QPainter, QPen, QBrush, QColor, QFont, QPainterPath,
    QPixmap, QTransform, QCursor, QKeySequence, QPolygonF
)
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QWidget,
    QGraphicsView, QGraphicsScene, QGraphicsItem,
    QGraphicsEllipseItem, QGraphicsPathItem, QGraphicsRectItem,
    QGraphicsLineItem, QGraphicsPolygonItem,
    QLabel, QPushButton, QFrame, QSplitter,
    QTreeWidget, QTreeWidgetItem, QGroupBox,
    QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox,
    QColorDialog, QSlider, QCheckBox, QFormLayout,
    QMenuBar, QMenu, QToolBar, QStatusBar,
    QDialogButtonBox, QMessageBox, QFileDialog,
    QSizePolicy, QScrollArea, QListWidget, QListWidgetItem,
    QFontComboBox, QApplication, QInputDialog, QRubberBand
)

from models.shape_definition import (
    ShapeDefinition, ShapePrimitive, ShapeConnector, ShapeStyle,
    ControlPoint, Edge, PrimitiveType, PointType, EdgeType,
    ConnectorDirection
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

DEBUG = False  # Set to True for debug output

def debug_print(msg: str):
    """Print debug message if DEBUG is True."""
    if DEBUG:
        print(f"[ShapeEditor] {msg}")


# =============================================================================
# Primitive Group (for grouping multiple primitives)
# =============================================================================

@dataclass
class PrimitiveGroup:
    """A group of primitives that can be transformed together."""
    id: str
    member_ids: List[str] = field(default_factory=list)
    rotation: float = 0.0


# =============================================================================
# Undo/Redo Support
# =============================================================================

class UndoStack:
    """
    Simple undo/redo stack using shape snapshots.
    """

    def __init__(self, max_size: int = MAX_UNDO_STEPS):
        self.max_size = max_size
        self._undo_stack: List[dict] = []
        self._redo_stack: List[dict] = []
        self._current_state: Optional[dict] = None

    def save_state(self, shape: ShapeDefinition):
        """Save current shape state to undo stack."""
        state = shape.to_dict()

        if self._current_state is not None:
            self._undo_stack.append(self._current_state)
            while len(self._undo_stack) > self.max_size:
                self._undo_stack.pop(0)

        self._redo_stack.clear()
        self._current_state = state

    def initialize(self, shape: ShapeDefinition):
        """Initialize with a shape (doesn't add to undo stack)."""
        self._current_state = shape.to_dict()
        self._undo_stack.clear()
        self._redo_stack.clear()

    def undo(self) -> Optional[ShapeDefinition]:
        """Undo last change."""
        if not self._undo_stack:
            return None

        if self._current_state is not None:
            self._redo_stack.append(self._current_state)

        self._current_state = self._undo_stack.pop()
        return ShapeDefinition.from_dict(self._current_state)

    def redo(self) -> Optional[ShapeDefinition]:
        """Redo last undone change."""
        if not self._redo_stack:
            return None

        if self._current_state is not None:
            self._undo_stack.append(self._current_state)

        self._current_state = self._redo_stack.pop()
        return ShapeDefinition.from_dict(self._current_state)

    def can_undo(self) -> bool:
        return len(self._undo_stack) > 0

    def can_redo(self) -> bool:
        return len(self._redo_stack) > 0

    def clear(self):
        self._undo_stack.clear()
        self._redo_stack.clear()
        self._current_state = None


# =============================================================================
# Color Button Widget
# =============================================================================

class ColorButton(QPushButton):
    """A button that displays a color and opens a color picker when clicked."""

    colorChanged = pyqtSignal(QColor)

    def __init__(self, color: QColor = None, parent=None):
        super().__init__(parent)
        self._color = color if isinstance(color, QColor) else QColor(color or "#CCCCFF")
        self.setFixedSize(60, 25)
        self.clicked.connect(self._pick_color)
        self._update_style()

    def _update_style(self):
        """Update button appearance to show current color."""
        self.setStyleSheet(
            f"background-color: {self._color.name()}; "
            f"border: 2px solid #555; "
            f"border-radius: 3px;"
        )

    def _pick_color(self):
        """Open color picker dialog."""
        # Note: Using default constructor + setCurrentColor() because
        # QColorDialog(color, parent) has a bug that changes window background
        dialog = QColorDialog()
        dialog.setCurrentColor(self._color)
        dialog.setOption(QColorDialog.ColorDialogOption.DontUseNativeDialog, False)
        if dialog.exec() == QColorDialog.DialogCode.Accepted:
            color = dialog.currentColor()
            if color.isValid():
                self._color = color
                self._update_style()
                self.colorChanged.emit(color)

    def color(self) -> QColor:
        return self._color

    def setColor(self, color):
        if isinstance(color, str):
            color = QColor(color)
        self._color = color
        self._update_style()


# =============================================================================
# Utility Functions
# =============================================================================

def get_short_id(full_id: str) -> str:
    """Get 8-character alphanumeric ID from full UUID."""
    return full_id.replace('-', '')[:8].upper()


def get_primitive_type_abbrev(prim_type: PrimitiveType) -> str:
    """Get 3-letter abbreviation for primitive type."""
    abbrevs = {
        PrimitiveType.ELLIPSE: 'ELP',
        PrimitiveType.RECTANGLE: 'RCT',
        PrimitiveType.POLYGON: 'PLY',
        PrimitiveType.PATH: 'PTH',
    }
    return abbrevs.get(prim_type, '???')


def normalized_to_pixel(value: float, canvas_size: float = CANVAS_SIZE) -> float:
    """Convert normalized (0-1) coordinate to pixel coordinate."""
    return value * canvas_size


def pixel_to_normalized(value: float, canvas_size: float = CANVAS_SIZE) -> float:
    """Convert pixel coordinate to normalized (0-1) coordinate."""
    return value / canvas_size


# =============================================================================
# Bezier Handle Item
# =============================================================================

class BezierHandleItem(QGraphicsEllipseItem):
    """
    A bezier control handle that can be dragged to adjust curves.
    """

    def __init__(self, vertex_handle, is_in_handle: bool, parent_item=None):
        super().__init__(-4, -4, 8, 8, parent_item)
        self.vertex_handle = vertex_handle
        self.is_in_handle = is_in_handle
        self._updating = False
        self._dragging = False

        # Styling
        self.setBrush(QBrush(QColor(200, 100, 200)))
        self.setPen(QPen(QColor(150, 50, 150), 1.5))

        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, False)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setZValue(102)
        self.setAcceptedMouseButtons(Qt.MouseButton.LeftButton)

        # Control line
        self.control_line = QGraphicsLineItem()
        self.control_line.setPen(QPen(QColor(200, 100, 200), 1, Qt.PenStyle.DashLine))
        self.control_line.setZValue(97)
        self.control_line.setAcceptedMouseButtons(Qt.MouseButton.NoButton)

    def finalize_init(self):
        """Call after positioning to set up handle distance."""
        pass

    def _update_control_line(self):
        """Update the line connecting handle to vertex."""
        if not self.vertex_handle:
            return
        vertex_scene = self.vertex_handle.scenePos()
        handle_scene = self.scenePos()
        self.control_line.setLine(vertex_scene.x(), vertex_scene.y(),
                                   handle_scene.x(), handle_scene.y())

    def mousePressEvent(self, event):
        self._dragging = True
        if self.vertex_handle and self.vertex_handle.canvas:
            self.vertex_handle.canvas._active_handle = self
        event.accept()

    def mouseReleaseEvent(self, event):
        if self._dragging:
            self._dragging = False
            if self.vertex_handle and self.vertex_handle.canvas:
                self.vertex_handle.canvas._active_handle = None
        event.accept()

    def handle_drag(self, scene_pos: QPointF):
        """Called by canvas with scene coordinates during drag."""
        if not self.vertex_handle:
            return

        parent_item = self.vertex_handle.parent_item
        if not parent_item:
            return

        # Get the vertex's scene position (where it visually appears after rotation)
        vertex_scene = self.vertex_handle.scenePos()

        # Calculate offset in scene coordinates
        dx = scene_pos.x() - vertex_scene.x()
        dy = scene_pos.y() - vertex_scene.y()

        # Un-rotate to get offset in local/data space
        # The handle data is stored in unrotated space (same as vertex data)
        rotation = parent_item.primitive.rotation
        if rotation != 0:
            angle_rad = math.radians(-rotation)
            cos_a = math.cos(angle_rad)
            sin_a = math.sin(angle_rad)
            unrotated_dx = dx * cos_a - dy * sin_a
            unrotated_dy = dx * sin_a + dy * cos_a
        else:
            unrotated_dx = dx
            unrotated_dy = dy

        # Update position (in local space, will be rotated by parent hierarchy)
        self.setPos(unrotated_dx, unrotated_dy)

        # Update the control point handle data (in unrotated/data coordinates)
        cp = self.vertex_handle.control_point
        if self.is_in_handle:
            cp.handle_in = (unrotated_dx, unrotated_dy)
        else:
            cp.handle_out = (unrotated_dx, unrotated_dy)

        # Handle symmetric mode
        if cp.point_type == PointType.SYMMETRIC:
            if self.is_in_handle and self.vertex_handle.handle_out:
                self.vertex_handle.handle_out.setPos(-unrotated_dx, -unrotated_dy)
                cp.handle_out = (-unrotated_dx, -unrotated_dy)
            elif not self.is_in_handle and self.vertex_handle.handle_in:
                self.vertex_handle.handle_in.setPos(-unrotated_dx, -unrotated_dy)
                cp.handle_in = (-unrotated_dx, -unrotated_dy)

        self._update_control_line()
        if self.vertex_handle.handle_in and self.vertex_handle.handle_in != self:
            self.vertex_handle.handle_in._update_control_line()
        if self.vertex_handle.handle_out and self.vertex_handle.handle_out != self:
            self.vertex_handle.handle_out._update_control_line()

        # Update parent path
        if parent_item:
            parent_item._create_path()
            parent_item.update()


# =============================================================================
# Vertex Handle
# =============================================================================

class VertexHandle(QGraphicsEllipseItem):
    """
    Draggable handle for a polygon vertex with optional bezier controls.
    """

    def __init__(self, control_point: ControlPoint, parent_item, canvas, parent_gfx=None):
        super().__init__(-HANDLE_SIZE/2, -HANDLE_SIZE/2, HANDLE_SIZE, HANDLE_SIZE, parent_gfx)
        self.control_point = control_point
        self.parent_item = parent_item
        self.canvas = canvas
        self._updating = False
        self._dragging = False
        self._selected = False

        # Bezier handles
        self.handle_in: Optional[BezierHandleItem] = None
        self.handle_out: Optional[BezierHandleItem] = None

        # Appearance based on point type
        self._update_appearance()

        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, False)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)
        self.setCursor(Qt.CursorShape.SizeAllCursor)
        self.setZValue(100)
        self.setAcceptedMouseButtons(Qt.MouseButton.LeftButton)

    def _update_appearance(self):
        """Update appearance based on point type."""
        colors = {
            PointType.CORNER: (QColor("#3B82F6"), QColor("#1D4ED8")),
            PointType.SMOOTH: (QColor("#EC4899"), QColor("#BE185D")),
            PointType.SYMMETRIC: (QColor("#06B6D4"), QColor("#0891B2")),
        }
        fill, stroke = colors.get(self.control_point.point_type, colors[PointType.CORNER])
        self.setBrush(QBrush(fill))
        self.setPen(QPen(stroke, 1.5))

    def set_selected(self, selected: bool):
        """Set selection state."""
        self._selected = selected
        if selected:
            self.setPen(QPen(QColor("#FFFF00"), 2.5))
        else:
            self._update_appearance()

    def mousePressEvent(self, event):
        self._dragging = True
        if self.canvas:
            self.canvas._active_handle = self
            self.canvas._select_vertex(self)
        event.accept()

    def mouseReleaseEvent(self, event):
        if self._dragging:
            self._dragging = False
            if self.canvas:
                self.canvas._active_handle = None
        event.accept()

    def handle_drag(self, scene_pos: QPointF):
        """Called by canvas with scene coordinates during drag."""
        if not self.parent_item:
            return

        # Grid snapping with Ctrl (snap in scene coordinates)
        modifiers = QApplication.keyboardModifiers()
        if modifiers & Qt.KeyboardModifier.ControlModifier and self.canvas:
            snap_size = self.canvas.grid_snap_size
            scene_pos = QPointF(
                round(scene_pos.x() / snap_size) * snap_size,
                round(scene_pos.y() / snap_size) * snap_size
            )

        # Get current center and rotation
        center = self.parent_item._center
        rotation = self.parent_item.primitive.rotation

        # Calculate offset from center in scene coordinates
        offset_x = scene_pos.x() - center.x()
        offset_y = scene_pos.y() - center.y()

        # Un-rotate to get the "data" offset
        # The path is drawn with (cp - center) as local coords, then rotated by item
        # So to have vertex appear at scene_pos, we need:
        # cp - center = rotate(scene_pos - center, -rotation)
        if rotation != 0:
            angle_rad = math.radians(-rotation)
            cos_a = math.cos(angle_rad)
            sin_a = math.sin(angle_rad)
            unrotated_x = offset_x * cos_a - offset_y * sin_a
            unrotated_y = offset_x * sin_a + offset_y * cos_a
        else:
            unrotated_x = offset_x
            unrotated_y = offset_y

        # Update control point data (unrotated scene coordinates)
        self.control_point.x = center.x() + unrotated_x
        self.control_point.y = center.y() + unrotated_y

        # Recalculate center based on new vertex positions
        new_center = self.parent_item._calculate_center()

        # Update parent item's center and position
        self.parent_item._center = new_center
        self.parent_item._updating = True
        self.parent_item.setPos(new_center)
        self.parent_item._last_pos = new_center
        self.parent_item._updating = False

        # Recreate path with new center
        self.parent_item._create_path()

        # Update ALL vertex handle positions (local coords = cp - center)
        # These are in local/unrotated space, the item rotation displays them correctly
        if self.canvas:
            for handle in self.canvas._vertex_handles.values():
                if handle.parent_item == self.parent_item:
                    cp = handle.control_point
                    handle.setPos(cp.x - new_center.x(), cp.y - new_center.y())

        # Update bezier handle lines
        if self.handle_in:
            self.handle_in._update_control_line()
        if self.handle_out:
            self.handle_out._update_control_line()

        # Update rotation handle connector line
        if self.canvas and self.canvas.rotate_handle:
            self.canvas.rotate_handle._update_connector_line()

        self.parent_item.update()

    def _show_bezier_handles(self):
        """Show bezier control handles."""
        if self.control_point.point_type == PointType.CORNER:
            return

        try:
            if self.control_point.handle_in:
                self.handle_in = BezierHandleItem(self, True, parent_item=self)
                dx, dy = self.control_point.handle_in
                self.handle_in.setPos(dx, dy)
                self.handle_in.finalize_init()
                self.canvas.scene().addItem(self.handle_in.control_line)
                self.handle_in._update_control_line()

            if self.control_point.handle_out:
                self.handle_out = BezierHandleItem(self, False, parent_item=self)
                dx, dy = self.control_point.handle_out
                self.handle_out.setPos(dx, dy)
                self.handle_out.finalize_init()
                self.canvas.scene().addItem(self.handle_out.control_line)
                self.handle_out._update_control_line()
        except Exception as e:
            print(f"Error showing bezier handles: {e}")
            self._hide_bezier_handles()

    def _hide_bezier_handles(self):
        """Remove bezier control handles."""
        if self.handle_in:
            try:
                if self.handle_in.control_line.scene():
                    self.canvas.scene().removeItem(self.handle_in.control_line)
                self.handle_in.setParentItem(None)
                if self.handle_in.scene():
                    self.canvas.scene().removeItem(self.handle_in)
            except RuntimeError:
                pass
            self.handle_in = None

        if self.handle_out:
            try:
                if self.handle_out.control_line.scene():
                    self.canvas.scene().removeItem(self.handle_out.control_line)
                self.handle_out.setParentItem(None)
                if self.handle_out.scene():
                    self.canvas.scene().removeItem(self.handle_out)
            except RuntimeError:
                pass
            self.handle_out = None


# =============================================================================
# Resize Handle
# =============================================================================

class ResizeHandle(QGraphicsEllipseItem):
    """Handle for resizing ellipse/rectangle primitives.

    This handle is a child of the SelectablePrimitiveItem, so it automatically
    moves with the item. Positions are in local coordinates relative to the
    item's center.
    """

    def __init__(self, parent_item, position: str, canvas=None):
        super().__init__(-5, -5, 10, 10)
        self.parent_item = parent_item
        self.position = position  # 'top-left', 'top-right', 'bottom-left', 'bottom-right'
        self.canvas = canvas
        self._dragging = False
        self._anchor_scene = QPointF()  # Anchor in scene coordinates
        self._start_bounds = None

        self.setBrush(QBrush(QColor(255, 100, 100)))
        self.setPen(QPen(QColor(200, 0, 0), 2))
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, False)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)
        self.setCursor(Qt.CursorShape.SizeFDiagCursor)
        self.setZValue(101)
        self.setAcceptedMouseButtons(Qt.MouseButton.LeftButton)

    def _get_opposite_position(self) -> str:
        """Get the position name of the opposite corner."""
        opposites = {
            'top-left': 'bottom-right',
            'top-right': 'bottom-left',
            'bottom-left': 'top-right',
            'bottom-right': 'top-left',
        }
        return opposites[self.position]

    def mousePressEvent(self, event):
        debug_print(f"ResizeHandle.mousePressEvent({self.position})")
        self._dragging = True

        # Store current bounds
        self._start_bounds = tuple(self.parent_item.primitive.bounds)

        # Find the opposite handle and get its scene position as anchor
        # This correctly handles rotation since handles are children of the rotated item
        opposite_pos = self._get_opposite_position()
        if self.canvas:
            for handle in self.canvas._resize_handles:
                if handle.position == opposite_pos:
                    self._anchor_scene = handle.scenePos()
                    debug_print(f"  Found opposite handle at scene pos: {self._anchor_scene}")
                    break

        debug_print(f"  My scene pos: {self.scenePos()}, anchor: {self._anchor_scene}")

        if self.canvas:
            self.canvas._active_handle = self
        event.accept()

    def mouseReleaseEvent(self, event):
        debug_print(f"ResizeHandle.mouseReleaseEvent({self.position})")
        if self._dragging:
            self._dragging = False
            if self.canvas:
                self.canvas._active_handle = None
        event.accept()

    def handle_drag(self, scene_pos: QPointF):
        """Handle resize drag - works correctly with rotated items."""
        if not self.parent_item:
            return

        # Grid snapping with Ctrl
        modifiers = QApplication.keyboardModifiers()
        if modifiers & Qt.KeyboardModifier.ControlModifier and self.canvas:
            snap_size = self.canvas.grid_snap_size
            scene_pos = QPointF(
                round(scene_pos.x() / snap_size) * snap_size,
                round(scene_pos.y() / snap_size) * snap_size
            )

        # Convert both positions to local coordinates using mapFromScene
        # This correctly handles rotation
        anchor_local = self.parent_item.mapFromScene(self._anchor_scene)
        current_local = self.parent_item.mapFromScene(scene_pos)

        # Calculate new half-dimensions in local space
        new_half_w = abs(current_local.x() - anchor_local.x()) / 2
        new_half_h = abs(current_local.y() - anchor_local.y()) / 2

        # Enforce minimum size
        new_half_w = max(5, new_half_w)
        new_half_h = max(5, new_half_h)

        # New local center is midpoint between anchor and current
        new_center_local_x = (current_local.x() + anchor_local.x()) / 2
        new_center_local_y = (current_local.y() + anchor_local.y()) / 2

        # Convert local center offset back to scene coordinates
        new_center_scene = self.parent_item.mapToScene(QPointF(new_center_local_x, new_center_local_y))

        new_w = new_half_w * 2
        new_h = new_half_h * 2

        # Update primitive bounds (stored in unrotated coordinates)
        self.parent_item.primitive.bounds = (
            new_center_scene.x() - new_w/2,
            new_center_scene.y() - new_h/2,
            new_w,
            new_h
        )

        # Update item center and position
        self.parent_item._center = new_center_scene
        self.parent_item._updating = True
        self.parent_item.setPos(new_center_scene)
        self.parent_item._last_pos = new_center_scene
        self.parent_item._updating = False

        # Recreate path with new dimensions
        self.parent_item._create_path()
        self.parent_item.update()

        # Update all handle positions (local coords relative to center)
        if self.canvas:
            self.canvas._update_resize_handle_positions()
            if self.canvas.rotate_handle:
                self.canvas.rotate_handle._update_connector_line()


# =============================================================================
# Rotate Handle
# =============================================================================

class RotateHandle(QGraphicsEllipseItem):
    """Handle for rotating primitives."""

    def __init__(self, parent_item, canvas=None, parent_gfx=None):
        super().__init__(-6, -6, 12, 12, parent_gfx)
        self.parent_item = parent_item
        self.canvas = canvas
        self._rotating = False
        self._handle_distance = 70.0
        self._start_angle = 0.0
        self._start_rotation = 0.0

        self.setBrush(QBrush(QColor(100, 255, 100)))
        self.setPen(QPen(QColor(0, 150, 0), 2))
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, False)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setZValue(103)
        self.setAcceptedMouseButtons(Qt.MouseButton.LeftButton)

        # Connector line
        self.connector_line = QGraphicsLineItem()
        self.connector_line.setPen(QPen(QColor(100, 255, 100), 1, Qt.PenStyle.DashLine))
        self.connector_line.setZValue(98)
        self.connector_line.setAcceptedMouseButtons(Qt.MouseButton.NoButton)

    def finalize_init(self):
        """Record handle distance after positioning."""
        pos = self.pos()
        self._handle_distance = math.sqrt(pos.x()**2 + pos.y()**2)
        if self._handle_distance < 20:
            self._handle_distance = 70.0

    def _update_connector_line(self):
        """Update line connecting handle to center."""
        center_scene = self.parent_item.pos()
        handle_scene = self.scenePos()
        self.connector_line.setLine(center_scene.x(), center_scene.y(),
                                     handle_scene.x(), handle_scene.y())

    def mousePressEvent(self, event):
        self._rotating = True

        center_scene = self.parent_item.pos()
        handle_scene = self.scenePos()
        dx = handle_scene.x() - center_scene.x()
        dy = handle_scene.y() - center_scene.y()
        self._start_angle = math.degrees(math.atan2(dy, dx))
        self._start_rotation = self.parent_item.primitive.rotation

        if self.canvas:
            self.canvas._active_handle = self
        event.accept()

    def mouseReleaseEvent(self, event):
        if self._rotating:
            self._rotating = False
            if self.canvas:
                self.canvas._active_handle = None
        event.accept()

    def handle_drag(self, scene_pos: QPointF):
        """Handle rotation drag."""
        center_scene = self.parent_item.pos()

        dx = scene_pos.x() - center_scene.x()
        dy = scene_pos.y() - center_scene.y()
        current_angle = math.degrees(math.atan2(dy, dx))

        delta_angle = current_angle - self._start_angle
        new_rotation = self._start_rotation + delta_angle

        # Snap with Ctrl
        modifiers = QApplication.keyboardModifiers()
        if modifiers & Qt.KeyboardModifier.ControlModifier and self.canvas:
            snap_angle = self.canvas.rotation_snap_angle
            new_rotation = round(new_rotation / snap_angle) * snap_angle

        # Apply rotation
        self.parent_item.primitive.rotation = new_rotation
        self.parent_item.setRotation(new_rotation)

        # Handle stays at top in local coords
        self.setPos(0, -self._handle_distance)
        self._update_connector_line()


# =============================================================================
# Group Resize Handle
# =============================================================================

class GroupResizeHandle(QGraphicsEllipseItem):
    """A handle for resizing groups."""

    def __init__(self, group_item, position: str, canvas=None):
        super().__init__(-5, -5, 10, 10)
        self.group_item = group_item
        self.position = position
        self.canvas = canvas
        self._dragging = False

        self.setBrush(QBrush(QColor(255, 200, 100)))
        self.setPen(QPen(QColor(200, 100, 0), 2))
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, False)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)
        self.setCursor(Qt.CursorShape.SizeFDiagCursor)
        self.setZValue(200)
        self.setAcceptedMouseButtons(Qt.MouseButton.LeftButton)

    def mousePressEvent(self, event):
        debug_print(f"GroupResizeHandle.mousePressEvent({self.position})")
        self._dragging = True
        self._start_local_bounds = QRectF(self.group_item._local_bounds)
        self._start_center = QPointF(self.group_item.pos())
        self._start_rotation = self.group_item.group.rotation
        # Store original member states
        self._start_member_states = []
        for item in self.group_item.member_items:
            prim = item.primitive
            state = {
                'pos': QPointF(item.pos()),
                'center': QPointF(item._center),
            }
            if prim.primitive_type == PrimitiveType.POLYGON:
                state['points'] = [(p.x, p.y, p.handle_in, p.handle_out) for p in prim.control_points]
            else:
                state['bounds'] = prim.bounds
            self._start_member_states.append(state)
        if self.canvas:
            self.canvas._active_handle = self
        event.accept()

    def mouseReleaseEvent(self, event):
        debug_print(f"GroupResizeHandle.mouseReleaseEvent({self.position})")
        if self._dragging:
            self._dragging = False
            if self.canvas:
                self.canvas._active_handle = None
        event.accept()

    def handle_drag(self, scene_pos: QPointF):
        """Called by canvas with scene coordinates during drag."""
        if not self._dragging:
            return

        group_center = self._start_center
        local_bounds = self._start_local_bounds
        rotation = self._start_rotation

        old_half_w = local_bounds.width() / 2
        old_half_h = local_bounds.height() / 2

        scene_offset_x = scene_pos.x() - group_center.x()
        scene_offset_y = scene_pos.y() - group_center.y()

        if rotation != 0:
            angle_rad = math.radians(-rotation)
            cos_a = math.cos(angle_rad)
            sin_a = math.sin(angle_rad)
            local_offset_x = scene_offset_x * cos_a - scene_offset_y * sin_a
            local_offset_y = scene_offset_x * sin_a + scene_offset_y * cos_a
        else:
            local_offset_x = scene_offset_x
            local_offset_y = scene_offset_y

        dx = abs(local_offset_x)
        dy = abs(local_offset_y)

        scale_x = 1.0
        scale_y = 1.0

        if 'e' in self.position or 'w' in self.position:
            if old_half_w > 5:
                scale_x = dx / old_half_w
        if 'n' in self.position or 's' in self.position:
            if old_half_h > 5:
                scale_y = dy / old_half_h

        scale_x = max(0.1, min(10.0, scale_x))
        scale_y = max(0.1, min(10.0, scale_y))

        self.group_item.scale_members_from_states(
            scale_x, scale_y, group_center, self._start_member_states,
            self._start_local_bounds, self._start_rotation
        )


# =============================================================================
# Group Rotate Handle
# =============================================================================

class GroupRotateHandle(QGraphicsEllipseItem):
    """A handle for rotating groups."""

    def __init__(self, group_item, canvas=None):
        super().__init__(-6, -6, 12, 12)
        self.group_item = group_item
        self.canvas = canvas
        self._rotating = False
        self._handle_distance = 50.0
        self._start_angle = 0.0
        self._start_rotation = 0.0

        self.setBrush(QBrush(QColor(100, 255, 100)))
        self.setPen(QPen(QColor(0, 150, 0), 2))
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, False)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setZValue(201)
        self.setAcceptedMouseButtons(Qt.MouseButton.LeftButton)

        self.connector_line = QGraphicsLineItem()
        self.connector_line.setPen(QPen(QColor(100, 255, 100), 1, Qt.PenStyle.DashLine))
        self.connector_line.setZValue(198)
        self.connector_line.setAcceptedMouseButtons(Qt.MouseButton.NoButton)

    def _update_connector_line(self):
        """Update connector line in local coordinates."""
        handle_pos = self.pos()
        self.connector_line.setLine(0, 0, handle_pos.x(), handle_pos.y())

    def mousePressEvent(self, event):
        debug_print("GroupRotateHandle.mousePressEvent()")
        self._rotating = True
        center = self.group_item.pos()
        mouse_scene = self.mapToScene(event.pos())
        dx = mouse_scene.x() - center.x()
        dy = mouse_scene.y() - center.y()
        self._start_angle = math.degrees(math.atan2(dy, dx))
        self._start_rotation = self.group_item.group.rotation
        if self.canvas:
            self.canvas._active_handle = self
        event.accept()

    def mouseReleaseEvent(self, event):
        debug_print("GroupRotateHandle.mouseReleaseEvent()")
        if self._rotating:
            self._rotating = False
            if self.canvas:
                self.canvas._active_handle = None
        event.accept()

    def handle_drag(self, scene_pos: QPointF):
        """Called by canvas with scene coordinates during drag."""
        center = self.group_item.pos()
        dx = scene_pos.x() - center.x()
        dy = scene_pos.y() - center.y()
        current_angle = math.degrees(math.atan2(dy, dx))

        delta_angle = current_angle - self._start_angle

        modifiers = QApplication.keyboardModifiers()
        if modifiers & Qt.KeyboardModifier.ControlModifier and self.canvas:
            snap_angle = self.canvas.rotation_snap_angle
            total_rotation = self._start_rotation + delta_angle
            snapped_rotation = round(total_rotation / snap_angle) * snap_angle
            delta_angle = snapped_rotation - self.group_item.group.rotation

        if abs(delta_angle) > 0.001:
            self.group_item.rotate_members(delta_angle)
        self._start_angle = current_angle
        self._start_rotation = self.group_item.group.rotation

        self._update_connector_line()


# =============================================================================
# Group Item
# =============================================================================

class GroupItem(QGraphicsPathItem):
    """
    Visual representation of a group of primitives.
    Shows a bounding rectangle and provides resize/rotate handles.
    """

    def __init__(self, group: PrimitiveGroup, canvas=None):
        super().__init__()
        self.group = group
        self.canvas = canvas
        self.member_items: List[SelectablePrimitiveItem] = []
        self.group_bounds = QRectF()
        self._local_bounds = QRectF()
        self._member_offsets: List[QPointF] = []

        self.resize_handles: List[GroupResizeHandle] = []
        self.rotate_handle: Optional[GroupRotateHandle] = None

        self.setPen(QPen(QColor(100, 100, 255), 2, Qt.PenStyle.DashLine))
        self.setBrush(QBrush(Qt.BrushStyle.NoBrush))

        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setZValue(50)
        self.setTransformOriginPoint(0, 0)

        self._updating = False
        self._last_pos = QPointF()

    def set_members(self, items: List['SelectablePrimitiveItem']):
        """Set the member items and calculate bounds."""
        self.member_items = items
        self._calculate_initial_bounds()
        self._create_path()
        self._last_pos = self.pos()

        if self.group.rotation != 0:
            self.setRotation(self.group.rotation)

    def _calculate_initial_bounds(self):
        """Calculate the initial bounding rectangle and member offsets."""
        if not self.member_items:
            self.group_bounds = QRectF()
            self._local_bounds = QRectF()
            return

        first = True
        for item in self.member_items:
            item_bounds = item.sceneBoundingRect()
            if first:
                self.group_bounds = QRectF(item_bounds)
                first = False
            else:
                self.group_bounds = self.group_bounds.united(item_bounds)

        center = self.group_bounds.center()
        self._updating = True
        self.setPos(center)
        self._last_pos = center
        self._updating = False

        self._local_bounds = QRectF(
            self.group_bounds.left() - center.x(),
            self.group_bounds.top() - center.y(),
            self.group_bounds.width(),
            self.group_bounds.height()
        )

        self._member_offsets = []
        for item in self.member_items:
            offset = item.pos() - center
            self._member_offsets.append(offset)

    def _create_path(self):
        """Create the selection rectangle path in local coordinates."""
        path = QPainterPath()
        if not self._local_bounds.isEmpty():
            padded = QRectF(self._local_bounds)
            padded.adjust(-5, -5, 5, 5)
            path.addRect(padded)
        self.setPath(path)

    def set_group_selected(self, selected: bool):
        """Show or hide the group bounding box."""
        self.setVisible(selected)

    def create_handles(self, scene: QGraphicsScene):
        """Create resize and rotate handles as children of the group."""
        self.clear_handles(scene)

        if self._local_bounds.isEmpty():
            return

        bounds = self._local_bounds

        positions = {
            'nw': QPointF(bounds.left() - 5, bounds.top() - 5),
            'ne': QPointF(bounds.right() + 5, bounds.top() - 5),
            'se': QPointF(bounds.right() + 5, bounds.bottom() + 5),
            'sw': QPointF(bounds.left() - 5, bounds.bottom() + 5),
        }

        for pos_name, pos in positions.items():
            handle = GroupResizeHandle(self, pos_name, self.canvas)
            handle.setParentItem(self)
            handle.setPos(pos)
            self.resize_handles.append(handle)

        self.rotate_handle = GroupRotateHandle(self, self.canvas)
        handle_distance = (bounds.height() / 2) + 30
        self.rotate_handle._handle_distance = handle_distance
        self.rotate_handle.setParentItem(self)
        self.rotate_handle.setPos(0, bounds.top() - 35)
        self.rotate_handle.connector_line.setParentItem(self)
        self.rotate_handle._update_connector_line()

    def clear_handles(self, scene: QGraphicsScene):
        """Remove all handles."""
        for handle in self.resize_handles:
            handle.setParentItem(None)
        self.resize_handles.clear()

        if self.rotate_handle:
            self.rotate_handle.connector_line.setParentItem(None)
            self.rotate_handle.setParentItem(None)
            self.rotate_handle = None

    def itemChange(self, change, value):
        """Handle position changes - move all members."""
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange and not self._updating:
            modifiers = QApplication.keyboardModifiers()
            if modifiers & Qt.KeyboardModifier.ControlModifier and self.canvas:
                snap_size = self.canvas.grid_snap_size
                snapped_x = round(value.x() / snap_size) * snap_size
                snapped_y = round(value.y() / snap_size) * snap_size
                value = QPointF(snapped_x, snapped_y)

            self._updating = True
            try:
                delta = value - self._last_pos

                for item in self.member_items:
                    old_pos = item.pos()
                    item.setPos(old_pos + delta)
                    item._last_pos = item.pos()

                self._last_pos = value
                self.group_bounds.translate(delta.x(), delta.y())
            finally:
                self._updating = False

            return value

        return super().itemChange(change, value)

    def scale_members_from_states(self, scale_x: float, scale_y: float, center: QPointF,
                                   start_states: list, start_local_bounds: QRectF = None,
                                   rotation: float = 0.0):
        """Scale all member items from their original states."""
        if abs(scale_x) < 0.1 or abs(scale_y) < 0.1:
            return

        if rotation != 0:
            angle_rad = math.radians(-rotation)
            cos_unrot = math.cos(angle_rad)
            sin_unrot = math.sin(angle_rad)
            angle_rad = math.radians(rotation)
            cos_rot = math.cos(angle_rad)
            sin_rot = math.sin(angle_rad)

        for i, item in enumerate(self.member_items):
            if i >= len(start_states):
                continue

            primitive = item.primitive
            state = start_states[i]
            orig_pos = state['pos']

            scene_dx = orig_pos.x() - center.x()
            scene_dy = orig_pos.y() - center.y()

            if rotation != 0:
                local_dx = scene_dx * cos_unrot - scene_dy * sin_unrot
                local_dy = scene_dx * sin_unrot + scene_dy * cos_unrot
                scaled_local_dx = local_dx * scale_x
                scaled_local_dy = local_dy * scale_y
                new_dx = scaled_local_dx * cos_rot - scaled_local_dy * sin_rot
                new_dy = scaled_local_dx * sin_rot + scaled_local_dy * cos_rot
            else:
                new_dx = scene_dx * scale_x
                new_dy = scene_dy * scale_y

            new_pos = QPointF(center.x() + new_dx, center.y() + new_dy)

            if primitive.primitive_type == PrimitiveType.POLYGON:
                orig_item_center = state['center']
                orig_points = state['points']

                for j, point in enumerate(primitive.control_points):
                    if j < len(orig_points):
                        orig_x, orig_y, orig_h_in, orig_h_out = orig_points[j]
                        px = orig_x - orig_item_center.x()
                        py = orig_y - orig_item_center.y()
                        scaled_x = orig_item_center.x() + px * scale_x
                        scaled_y = orig_item_center.y() + py * scale_y
                        point.x = scaled_x + (new_pos.x() - orig_item_center.x())
                        point.y = scaled_y + (new_pos.y() - orig_item_center.y())
                        if orig_h_in:
                            point.handle_in = (orig_h_in[0] * scale_x, orig_h_in[1] * scale_y)
                        if orig_h_out:
                            point.handle_out = (orig_h_out[0] * scale_x, orig_h_out[1] * scale_y)
            else:
                orig_bounds = state['bounds']
                if isinstance(orig_bounds, QRectF):
                    new_w = orig_bounds.width() * scale_x
                    new_h = orig_bounds.height() * scale_y
                    primitive.bounds = (new_pos.x() - new_w / 2, new_pos.y() - new_h / 2, new_w, new_h)
                else:
                    ox, oy, ow, oh = orig_bounds
                    new_w = ow * scale_x
                    new_h = oh * scale_y
                    primitive.bounds = (new_pos.x() - new_w / 2, new_pos.y() - new_h / 2, new_w, new_h)

            item._center = item._calculate_center()
            item.setPos(new_pos)
            item._last_pos = new_pos
            item._create_path()

        if start_local_bounds:
            self._local_bounds = QRectF(
                start_local_bounds.left() * scale_x,
                start_local_bounds.top() * scale_y,
                start_local_bounds.width() * scale_x,
                start_local_bounds.height() * scale_y
            )
        self._create_path()
        self._update_handle_positions()

    def rotate_members(self, delta_angle: float):
        """Rotate all member items around the group center."""
        center = self.pos()
        angle_rad = math.radians(delta_angle)
        cos_a = math.cos(angle_rad)
        sin_a = math.sin(angle_rad)

        for item in self.member_items:
            old_pos = item.pos()
            dx = old_pos.x() - center.x()
            dy = old_pos.y() - center.y()
            new_x = center.x() + dx * cos_a - dy * sin_a
            new_y = center.y() + dx * sin_a + dy * cos_a
            item.setPos(new_x, new_y)
            item._last_pos = item.pos()

            item.primitive.rotation += delta_angle
            item.setRotation(item.primitive.rotation)

        self.group.rotation += delta_angle
        self.setRotation(self.group.rotation)

    def _update_handle_positions(self):
        """Update handle positions after bounds change."""
        if not self._local_bounds.isEmpty():
            bounds = self._local_bounds

            positions = {
                'nw': QPointF(bounds.left() - 5, bounds.top() - 5),
                'ne': QPointF(bounds.right() + 5, bounds.top() - 5),
                'se': QPointF(bounds.right() + 5, bounds.bottom() + 5),
                'sw': QPointF(bounds.left() - 5, bounds.bottom() + 5),
            }

            for handle in self.resize_handles:
                if handle.position in positions:
                    handle.setPos(positions[handle.position])

            if self.rotate_handle:
                handle_distance = (bounds.height() / 2) + 30
                self.rotate_handle._handle_distance = handle_distance
                self.rotate_handle.setPos(0, bounds.top() - 35)
                self.rotate_handle._update_connector_line()


# =============================================================================
# Connector Handle
# =============================================================================

class ConnectorHandle(QGraphicsEllipseItem):
    """Draggable handle for a connector that snaps to the shape edge."""

    def __init__(self, connector: ShapeConnector, canvas, parent=None):
        super().__init__(-CONNECTOR_SIZE/2, -CONNECTOR_SIZE/2, CONNECTOR_SIZE, CONNECTOR_SIZE, parent)

        self.connector = connector
        self.canvas = canvas
        self._updating = False
        self._dragging = False

        # Orange appearance
        self.setBrush(QBrush(QColor("#F59E0B")))
        self.setPen(QPen(QColor("#D97706"), 1.5))

        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setCursor(QCursor(Qt.CursorShape.SizeAllCursor))
        self.setZValue(99)
        self.setAcceptHoverEvents(True)

        # Create label text item as child
        from PyQt6.QtWidgets import QGraphicsSimpleTextItem
        self._label_item = QGraphicsSimpleTextItem(self)
        self._label_item.setBrush(QBrush(QColor("#1F2937")))
        font = QFont("SF Pro Display", 9)
        font.setBold(True)
        self._label_item.setFont(font)
        self._label_item.setZValue(100)

        self._update_label()
        self._update_tooltip()

    def _update_label(self):
        """Update the label text display."""
        self._label_item.setText(self.connector.label)
        # Position label offset from connector center
        bounds = self._label_item.boundingRect()
        # Offset to the right and slightly up
        self._label_item.setPos(CONNECTOR_SIZE/2 + 2, -bounds.height()/2)

    def _update_tooltip(self):
        """Update tooltip with connector info."""
        direction = getattr(self.connector, 'direction', ConnectorDirection.INOUT)
        if isinstance(direction, ConnectorDirection):
            dir_symbol = {"In": "←", "Out": "→", "InOut": "↔"}[direction.value]
        else:
            dir_symbol = "↔"
        pos_pct = int(self.connector.edge_position * 100)
        self.setToolTip(f"{self.connector.label}\n{pos_pct}%\n{dir_symbol}")

    def update_display(self):
        """Update both label and tooltip from connector data."""
        self._update_label()
        self._update_tooltip()

    def update_position_on_edge(self, path: QPainterPath):
        """Update position based on edge_position along path."""
        if path.isEmpty():
            return

        self._updating = True
        qt_percent = self.connector.edge_position
        pt = path.pointAtPercent(qt_percent)
        self.setPos(pt)
        self._updating = False

    def mousePressEvent(self, event):
        """Handle mouse press - set as active handle and emit selection."""
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self.canvas._active_handle = self
            # Emit connector selected signal
            self.canvas.connector_selected.emit(self.connector.id)
            debug_print(f"ConnectorHandle.mousePressEvent: {self.connector.label}")
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        """Handle mouse release - clear active handle."""
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = False
            if self.canvas._active_handle == self:
                self.canvas._active_handle = None
            # Emit drag completed signal
            self.canvas.drag_completed.emit()
            debug_print(f"ConnectorHandle.mouseReleaseEvent: {self.connector.label}")
        super().mouseReleaseEvent(event)

    def handle_drag(self, scene_pos: QPointF):
        """Handle drag to new position - snap to edge."""
        path = self.canvas.current_path
        if not path or path.isEmpty():
            return

        # Find nearest point on path
        best_t = 0.0
        best_dist = float('inf')

        for i in range(101):
            t = i / 100.0
            pt = path.pointAtPercent(t)
            dist = (pt.x() - scene_pos.x())**2 + (pt.y() - scene_pos.y())**2
            if dist < best_dist:
                best_dist = dist
                best_t = t

        # Fine search
        for i in range(-10, 11):
            t = max(0, min(1, best_t + i / 1000.0))
            pt = path.pointAtPercent(t)
            dist = (pt.x() - scene_pos.x())**2 + (pt.y() - scene_pos.y())**2
            if dist < best_dist:
                best_dist = dist
                best_t = t

        self.connector.edge_position = best_t

        self._updating = True
        final_pt = path.pointAtPercent(best_t)
        self.setPos(final_pt)
        self._updating = False
        self._update_tooltip()

        self.canvas.connector_moved.emit(self.connector.id)

    def itemChange(self, change, value):
        """Handle position changes - snap to edge."""
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            if self._updating:
                return value

            # Only process if we're being dragged by Qt's built-in mechanism
            # (This handles cases where itemChange is triggered but handle_drag isn't called)
            if not self._dragging:
                return value

            pos = self.pos()
            path = self.canvas.current_path

            if path and not path.isEmpty():
                # Find nearest point on path
                best_t = 0.0
                best_dist = float('inf')

                for i in range(101):
                    t = i / 100.0
                    pt = path.pointAtPercent(t)
                    dist = (pt.x() - pos.x())**2 + (pt.y() - pos.y())**2
                    if dist < best_dist:
                        best_dist = dist
                        best_t = t

                # Fine search
                for i in range(-10, 11):
                    t = max(0, min(1, best_t + i / 1000.0))
                    pt = path.pointAtPercent(t)
                    dist = (pt.x() - pos.x())**2 + (pt.y() - pos.y())**2
                    if dist < best_dist:
                        best_dist = dist
                        best_t = t

                self.connector.edge_position = best_t

                self._updating = True
                final_pt = path.pointAtPercent(best_t)
                self.setPos(final_pt)
                self._updating = False
                self._update_tooltip()

                self.canvas.connector_moved.emit(self.connector.id)

        return value

    def hoverEnterEvent(self, event):
        self.setBrush(QBrush(QColor("#FBBF24")))
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        self.setBrush(QBrush(QColor("#F59E0B")))
        super().hoverLeaveEvent(event)


# =============================================================================
# Selectable Primitive Item
# =============================================================================

class SelectablePrimitiveItem(QGraphicsPathItem):
    """
    Graphics item for a shape primitive with selection, resize, and rotate handles.
    Works with pixel coordinates internally.
    """

    def __init__(self, primitive: ShapePrimitive, style: ShapeStyle, canvas=None):
        super().__init__()
        self.primitive = primitive
        self.style = style
        self.canvas = canvas
        self._selected = False
        self._updating = False

        # Calculate center and position
        self._center = self._calculate_center()
        self.setPos(self._center)
        self._last_pos = QPointF(self._center)

        # Create the path
        self._create_path()

        # Apply style
        self._apply_style()

        # Interaction flags
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setAcceptHoverEvents(True)
        self.setCursor(Qt.CursorShape.SizeAllCursor)
        self.setZValue(10)

        # Apply rotation
        self.setRotation(primitive.rotation)

    def _calculate_center(self) -> QPointF:
        """Calculate center point from primitive data."""
        if self.primitive.primitive_type in (PrimitiveType.ELLIPSE, PrimitiveType.RECTANGLE):
            x, y, w, h = self.primitive.bounds
            return QPointF(x + w/2, y + h/2)
        elif self.primitive.primitive_type in (PrimitiveType.POLYGON, PrimitiveType.PATH):
            if self.primitive.control_points:
                xs = [p.x for p in self.primitive.control_points]
                ys = [p.y for p in self.primitive.control_points]
                return QPointF(sum(xs)/len(xs), sum(ys)/len(ys))
        return QPointF(CANVAS_SIZE/2, CANVAS_SIZE/2)

    def _create_path(self):
        """Create QPainterPath from primitive data."""
        path = QPainterPath()
        center = self._center

        if self.primitive.primitive_type == PrimitiveType.ELLIPSE:
            x, y, w, h = self.primitive.bounds
            # Draw relative to center
            path.addEllipse(QRectF(-w/2, -h/2, w, h))

        elif self.primitive.primitive_type == PrimitiveType.RECTANGLE:
            x, y, w, h = self.primitive.bounds
            corner_radius = getattr(self.primitive, 'corner_radius', 0)
            rect = QRectF(-w/2, -h/2, w, h)
            if corner_radius > 0:
                r = corner_radius * min(w, h)
                path.addRoundedRect(rect, r, r)
            else:
                path.addRect(rect)

        elif self.primitive.primitive_type in (PrimitiveType.POLYGON, PrimitiveType.PATH):
            points = self.primitive.control_points
            if points:
                # First point
                p0 = points[0]
                path.moveTo(p0.x - center.x(), p0.y - center.y())

                # Check for bezier curves
                has_curves = any(p.point_type != PointType.CORNER for p in points)

                if has_curves:
                    # Draw with bezier curves
                    n = len(points)
                    for i in range(n):
                        curr = points[i]
                        next_pt = points[(i + 1) % n]

                        # Get control points
                        cp1 = None
                        cp2 = None
                        if curr.handle_out:
                            cp1 = (curr.x + curr.handle_out[0] - center.x(),
                                   curr.y + curr.handle_out[1] - center.y())
                        if next_pt.handle_in:
                            cp2 = (next_pt.x + next_pt.handle_in[0] - center.x(),
                                   next_pt.y + next_pt.handle_in[1] - center.y())

                        end_x = next_pt.x - center.x()
                        end_y = next_pt.y - center.y()

                        if cp1 and cp2:
                            path.cubicTo(cp1[0], cp1[1], cp2[0], cp2[1], end_x, end_y)
                        elif cp1:
                            path.quadTo(cp1[0], cp1[1], end_x, end_y)
                        elif cp2:
                            path.quadTo(cp2[0], cp2[1], end_x, end_y)
                        else:
                            path.lineTo(end_x, end_y)
                else:
                    # Simple polygon
                    for p in points[1:]:
                        path.lineTo(p.x - center.x(), p.y - center.y())

                if getattr(self.primitive, 'closed', True):
                    path.closeSubpath()

        self.setPath(path)

    def _apply_style(self):
        """Apply style colors and stroke."""
        fill_color = QColor(self.style.fill_color)
        fill_color.setAlphaF(self.style.fill_opacity)
        self.setBrush(QBrush(fill_color))

        stroke_color = QColor(self.style.stroke_color)
        stroke_color.setAlphaF(self.style.stroke_opacity)
        pen = QPen(stroke_color, self.style.stroke_width)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        self.setPen(pen)

    def set_selected(self, selected: bool):
        """Set selection state with visual feedback."""
        self._selected = selected
        if selected:
            pen = self.pen()
            pen.setColor(QColor(255, 165, 0))
            pen.setStyle(Qt.PenStyle.DashLine)
            pen.setWidth(2)
            self.setPen(pen)
        else:
            self._apply_style()

    def itemChange(self, change, value):
        """Handle position changes."""
        # Grid snapping
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange:
            modifiers = QApplication.keyboardModifiers()
            if modifiers & Qt.KeyboardModifier.ControlModifier and self.canvas:
                snap_size = self.canvas.grid_snap_size
                snapped_x = round(value.x() / snap_size) * snap_size
                snapped_y = round(value.y() / snap_size) * snap_size
                return QPointF(snapped_x, snapped_y)

        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged and not self._updating:
            self._updating = True
            try:
                delta = value - self._last_pos
                debug_print(f"itemChange: delta=({delta.x():.1f}, {delta.y():.1f}), new pos={value}")
                self._last_pos = QPointF(value)

                # Update primitive data based on movement
                if self.primitive.primitive_type in (PrimitiveType.ELLIPSE, PrimitiveType.RECTANGLE):
                    x, y, w, h = self.primitive.bounds
                    self.primitive.bounds = (x + delta.x(), y + delta.y(), w, h)
                    debug_print(f"  Updated bounds to {self.primitive.bounds}")
                elif self.primitive.primitive_type in (PrimitiveType.POLYGON, PrimitiveType.PATH):
                    for cp in self.primitive.control_points:
                        cp.x += delta.x()
                        cp.y += delta.y()

                self._center = value

                # Log child handle positions
                if self.canvas and self.canvas._resize_handles:
                    for h in self.canvas._resize_handles:
                        debug_print(f"  Handle {h.position}: local={h.pos()}, scene={h.scenePos()}")

                # Update rotate handle connector line
                # (resize/vertex handles are children, so they move automatically)
                if self.canvas and self.canvas.rotate_handle:
                    self.canvas.rotate_handle._update_connector_line()
            finally:
                self._updating = False

        return super().itemChange(change, value)


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
    - Resize and rotate handles
    - Grid overlay with Ctrl+drag snapping
    - Boolean operations via context menu
    """

    shape_modified = pyqtSignal()
    point_selected = pyqtSignal(str)
    connector_selected = pyqtSignal(str)
    connector_deselected = pyqtSignal()
    connector_moved = pyqtSignal(str)
    drag_completed = pyqtSignal()
    primitive_selected = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.canvas_size = CANVAS_SIZE
        self.grid_snap = True
        self.grid_size = GRID_SIZE
        self.show_grid = True
        self.zoom_level = 1.0
        self._dragging = False

        # Snap settings
        self.grid_snap_size = 20.0
        self.rotation_snap_angle = 10.0

        # Shape being edited
        self.shape: Optional[ShapeDefinition] = None
        self.current_path: Optional[QPainterPath] = None

        # Graphics items
        self._primitive_items: Dict[str, SelectablePrimitiveItem] = {}
        self._vertex_handles: Dict[str, VertexHandle] = {}
        self._connector_handles: Dict[str, ConnectorHandle] = {}
        self._resize_handles: List[ResizeHandle] = []
        self.rotate_handle: Optional[RotateHandle] = None
        self._grid_items: List[QGraphicsItem] = []

        # Selection state
        self.selected_primitive_id: Optional[str] = None
        self.selected_vertex_id: Optional[str] = None

        # Multi-selection (ordered list for boolean operations)
        self.selected_primitive_ids: List[str] = []

        # Groups
        self.groups: Dict[str, PrimitiveGroup] = {}
        self.group_items: Dict[str, GroupItem] = {}
        self.selected_group_id: Optional[str] = None

        # Active handle being dragged
        self._active_handle = None

        # Rubberband selection
        self._rubberband_active = False
        self._rubberband_origin = QPoint()
        self._rubberband = None

        # Setup
        self._setup_scene()
        self._setup_view()

    def _setup_scene(self):
        """Initialize the graphics scene."""
        self._scene = QGraphicsScene(self)
        self._scene.setSceneRect(0, 0, self.canvas_size, self.canvas_size)
        self.setScene(self._scene)
        self._scene.setBackgroundBrush(QBrush(QColor("#FAFAFA")))

    def _setup_view(self):
        """Configure view settings."""
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setMinimumSize(self.canvas_size + 20, self.canvas_size + 20)
        self.setMaximumSize(self.canvas_size + 20, self.canvas_size + 20)
        # Enable context menu
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.DefaultContextMenu)
        # No built-in drag mode - we handle selection ourselves
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        # Enable keyboard focus
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def scene(self):
        """Return the graphics scene."""
        return self._scene

    def set_shape(self, shape: ShapeDefinition):
        """Set the shape to edit."""
        self.shape = shape.copy()

        # Convert normalized coordinates to pixel coordinates
        self._normalize_to_pixel()

        # Use shape's perimeter_id or default to first primitive
        if self.shape.perimeter_id is None and self.shape.primitives:
            self.shape.perimeter_id = self.shape.primitives[0].id

        self._rebuild_scene()

    def _normalize_to_pixel(self):
        """Convert all normalized coordinates to pixel coordinates."""
        if not self.shape:
            return

        s = self.canvas_size

        for prim in self.shape.primitives:
            if prim.primitive_type in (PrimitiveType.ELLIPSE, PrimitiveType.RECTANGLE):
                if prim.bounds:
                    x, y, w, h = prim.bounds
                    prim.bounds = (x * s, y * s, w * s, h * s)

            if prim.control_points:
                for cp in prim.control_points:
                    cp.x *= s
                    cp.y *= s
                    if hasattr(cp, 'handle_in') and cp.handle_in:
                        cp.handle_in = (cp.handle_in[0] * s, cp.handle_in[1] * s)
                    if hasattr(cp, 'handle_out') and cp.handle_out:
                        cp.handle_out = (cp.handle_out[0] * s, cp.handle_out[1] * s)

    def _pixel_to_normalize(self):
        """Convert all pixel coordinates to normalized coordinates."""
        if not self.shape:
            return

        s = self.canvas_size

        for prim in self.shape.primitives:
            if prim.primitive_type in (PrimitiveType.ELLIPSE, PrimitiveType.RECTANGLE):
                if prim.bounds:
                    x, y, w, h = prim.bounds
                    prim.bounds = (x / s, y / s, w / s, h / s)

            if prim.control_points:
                for cp in prim.control_points:
                    cp.x /= s
                    cp.y /= s
                    if hasattr(cp, 'handle_in') and cp.handle_in:
                        cp.handle_in = (cp.handle_in[0] / s, cp.handle_in[1] / s)
                    if hasattr(cp, 'handle_out') and cp.handle_out:
                        cp.handle_out = (cp.handle_out[0] / s, cp.handle_out[1] / s)

    def get_shape(self) -> Optional[ShapeDefinition]:
        """Get the edited shape with normalized coordinates."""
        if not self.shape:
            return None

        # Create a copy and normalize
        result = self.shape.copy()

        s = self.canvas_size

        for prim in result.primitives:
            if prim.primitive_type in (PrimitiveType.ELLIPSE, PrimitiveType.RECTANGLE):
                if prim.bounds:
                    x, y, w, h = prim.bounds
                    prim.bounds = (x / s, y / s, w / s, h / s)

            if prim.control_points:
                for cp in prim.control_points:
                    cp.x /= s
                    cp.y /= s
                    if hasattr(cp, 'handle_in') and cp.handle_in:
                        cp.handle_in = (cp.handle_in[0] / s, cp.handle_in[1] / s)
                    if hasattr(cp, 'handle_out') and cp.handle_out:
                        cp.handle_out = (cp.handle_out[0] / s, cp.handle_out[1] / s)

        return result

    def get_internal_shape(self) -> Optional[ShapeDefinition]:
        """Get direct reference to the internal shape (no copy, for real-time updates)."""
        return self.shape

    def _rebuild_scene(self):
        """Rebuild all scene items from shape definition."""
        self._clear_all_handles()

        # Clear primitive items
        for item in self._primitive_items.values():
            self._scene.removeItem(item)
        self._primitive_items.clear()

        if not self.shape:
            return

        # Draw grid
        self._draw_grid()

        # Create primitive items
        for prim in self.shape.primitives:
            item = SelectablePrimitiveItem(prim, self.shape.style, canvas=self)
            self._scene.addItem(item)
            self._primitive_items[prim.id] = item

        # Update current path for connectors
        self._update_current_path()

        # Create connector handles
        self._create_connector_handles()

    def _clear_all_handles(self):
        """Remove all handles from scene."""
        # Vertex handles
        for handle in self._vertex_handles.values():
            handle._hide_bezier_handles()
            if handle.scene():
                self._scene.removeItem(handle)
        self._vertex_handles.clear()

        # Connector handles
        for handle in self._connector_handles.values():
            if handle.scene():
                self._scene.removeItem(handle)
        self._connector_handles.clear()

        # Resize handles
        for handle in self._resize_handles:
            if handle.scene():
                self._scene.removeItem(handle)
        self._resize_handles.clear()

        # Rotate handle
        if self.rotate_handle:
            if self.rotate_handle.connector_line.scene():
                self._scene.removeItem(self.rotate_handle.connector_line)
            if self.rotate_handle.scene():
                self._scene.removeItem(self.rotate_handle)
            self.rotate_handle = None

    def _draw_grid(self):
        """Draw grid overlay."""
        for item in self._grid_items:
            self._scene.removeItem(item)
        self._grid_items.clear()

        if not self.show_grid:
            return

        grid_pen = QPen(QColor("#E5E7EB"), 0.5)

        for i in range(0, self.canvas_size + 1, self.grid_size):
            line_v = self._scene.addLine(i, 0, i, self.canvas_size, grid_pen)
            line_v.setZValue(-10)
            self._grid_items.append(line_v)

            line_h = self._scene.addLine(0, i, self.canvas_size, i, grid_pen)
            line_h.setZValue(-10)
            self._grid_items.append(line_h)

        border_pen = QPen(QColor("#9CA3AF"), 1)
        border = self._scene.addRect(0, 0, self.canvas_size, self.canvas_size, border_pen)
        border.setZValue(-9)
        self._grid_items.append(border)

    def _update_current_path(self):
        """Compute unified path from all primitives."""
        if not self.shape or not self.shape.primitives:
            self.current_path = None
            return

        paths = []
        for prim_id, item in self._primitive_items.items():
            path = item.mapToScene(item.path())
            if not path.isEmpty():
                paths.append(path)

        if not paths:
            self.current_path = None
            return

        result = paths[0]
        for path in paths[1:]:
            result = result.united(path)

        self.current_path = result

    def _create_connector_handles(self):
        """Create connector handles on shape edge."""
        if not self.shape or not self.current_path:
            return

        for conn in self.shape.connectors:
            handle = ConnectorHandle(conn, self)
            handle.update_position_on_edge(self.current_path)
            self._scene.addItem(handle)
            self._connector_handles[conn.id] = handle

    def _create_vertex_handles(self, prim: ShapePrimitive):
        """Create vertex handles for a polygon/path primitive."""
        if prim.primitive_type not in (PrimitiveType.POLYGON, PrimitiveType.PATH):
            return

        item = self._primitive_items.get(prim.id)
        if not item:
            return

        center = item._center

        for cp in prim.control_points:
            handle = VertexHandle(cp, item, self, parent_gfx=item)
            # Position in local coordinates (same formula as path drawing)
            handle.setPos(cp.x - center.x(), cp.y - center.y())
            self._vertex_handles[cp.id] = handle

    def _clear_vertex_handles(self):
        """Remove vertex handles."""
        for handle in self._vertex_handles.values():
            handle._hide_bezier_handles()
            handle.setParentItem(None)
            if handle.scene():
                self._scene.removeItem(handle)
        self._vertex_handles.clear()

    def _create_resize_handles(self, prim: ShapePrimitive):
        """Create resize handles for ellipse/rectangle as children of the item."""
        if prim.primitive_type not in (PrimitiveType.ELLIPSE, PrimitiveType.RECTANGLE):
            return

        item = self._primitive_items.get(prim.id)
        if not item:
            return

        # Get bounds to calculate local corner positions
        x, y, w, h = prim.bounds
        debug_print(f"_create_resize_handles: bounds=({x:.1f}, {y:.1f}, {w:.1f}, {h:.1f})")
        debug_print(f"  item pos={item.pos()}, center={item._center}")
        debug_print(f"  item in scene: {item.scene() is not None}")

        # Local positions (relative to center)
        local_positions = {
            'top-left': (-w/2, -h/2),
            'top-right': (w/2, -h/2),
            'bottom-left': (-w/2, h/2),
            'bottom-right': (w/2, h/2),
        }

        for pos_name, local_pos in local_positions.items():
            handle = ResizeHandle(item, pos_name, canvas=self)
            handle.setParentItem(item)  # Make it a child of the item
            handle.setPos(local_pos[0], local_pos[1])
            self._resize_handles.append(handle)
            debug_print(f"  {pos_name}: local=({local_pos[0]:.1f}, {local_pos[1]:.1f}), "
                       f"scene={handle.scenePos()}, parent={handle.parentItem() is item}, "
                       f"in_scene={handle.scene() is not None}")

    def _update_resize_handle_positions(self):
        """Update resize handle positions based on primitive bounds (local coords)."""
        if not self._resize_handles:
            return

        prim = self._resize_handles[0].parent_item.primitive
        x, y, w, h = prim.bounds

        # Local positions (relative to center)
        positions = {
            'top-left': (-w/2, -h/2),
            'top-right': (w/2, -h/2),
            'bottom-left': (-w/2, h/2),
            'bottom-right': (w/2, h/2),
        }

        for handle in self._resize_handles:
            pos = positions.get(handle.position)
            if pos:
                handle.setPos(pos[0], pos[1])

    def _clear_resize_handles(self):
        """Remove resize handles."""
        for handle in self._resize_handles:
            handle.setParentItem(None)
            if handle.scene():
                self._scene.removeItem(handle)
        self._resize_handles.clear()

    def _create_rotate_handle(self, prim: ShapePrimitive):
        """Create rotate handle for a primitive."""
        item = self._primitive_items.get(prim.id)
        if not item:
            return

        self.rotate_handle = RotateHandle(item, canvas=self, parent_gfx=item)
        self.rotate_handle.setPos(0, -70)  # Above center
        self.rotate_handle.finalize_init()
        self._scene.addItem(self.rotate_handle.connector_line)
        self.rotate_handle._update_connector_line()

    def _clear_rotate_handle(self):
        """Remove rotate handle."""
        if self.rotate_handle:
            if self.rotate_handle.connector_line.scene():
                self._scene.removeItem(self.rotate_handle.connector_line)
            self.rotate_handle.setParentItem(None)
            if self.rotate_handle.scene():
                self._scene.removeItem(self.rotate_handle)
            self.rotate_handle = None

    def _select_primitive(self, prim_id: str):
        """Select a primitive and show appropriate handles."""
        # Clear previous selection
        if self.selected_primitive_id and self.selected_primitive_id in self._primitive_items:
            self._primitive_items[self.selected_primitive_id].set_selected(False)

        self._clear_vertex_handles()
        self._clear_resize_handles()
        self._clear_rotate_handle()
        self.selected_vertex_id = None

        self.selected_primitive_id = prim_id

        if prim_id and prim_id in self._primitive_items:
            item = self._primitive_items[prim_id]
            item.set_selected(True)

            prim = None
            for p in self.shape.primitives:
                if p.id == prim_id:
                    prim = p
                    break

            if prim:
                if prim.primitive_type in (PrimitiveType.POLYGON, PrimitiveType.PATH):
                    self._create_vertex_handles(prim)
                elif prim.primitive_type in (PrimitiveType.ELLIPSE, PrimitiveType.RECTANGLE):
                    self._create_resize_handles(prim)

                self._create_rotate_handle(prim)

            self.primitive_selected.emit(prim_id)

    def _select_vertex(self, vertex_handle: VertexHandle):
        """Select a vertex."""
        # Deselect previous
        if self.selected_vertex_id and self.selected_vertex_id in self._vertex_handles:
            self._vertex_handles[self.selected_vertex_id].set_selected(False)
            self._vertex_handles[self.selected_vertex_id]._hide_bezier_handles()

        self.selected_vertex_id = vertex_handle.control_point.id
        vertex_handle.set_selected(True)

        # Show bezier handles if not corner
        if vertex_handle.control_point.point_type != PointType.CORNER:
            vertex_handle._show_bezier_handles()

        self.point_selected.emit(vertex_handle.control_point.id)

    def mousePressEvent(self, event):
        """Handle mouse press with support for multi-selection and rubberband."""
        # Grab keyboard focus
        self.setFocus()

        debug_print(f"mousePressEvent: button={event.button()}, selected_ids={len(self.selected_primitive_ids)}")

        # Only handle left button for selection, let right button through for context menu
        if event.button() == Qt.MouseButton.RightButton:
            # Don't process right-click here - let contextMenuEvent handle it
            debug_print(f"  Right-click - not clearing selection, current selection: {self.selected_primitive_ids}")
            # Don't call super - just ignore and let contextMenuEvent handle it
            return

        item = self.itemAt(event.pos())
        debug_print(f"  item at pos: {type(item).__name__ if item else 'None'}")
        modifiers = event.modifiers()
        multi_select = bool(modifiers & (Qt.KeyboardModifier.ShiftModifier | Qt.KeyboardModifier.ControlModifier))

        # Deselect connector when clicking on anything other than a ConnectorHandle
        if not isinstance(item, ConnectorHandle):
            self.connector_deselected.emit()

        # Check if clicked on a GroupItem
        if isinstance(item, GroupItem):
            self._clear_group_selection()
            self.selected_group_id = item.group.id
            item.set_group_selected(True)
            item.create_handles(self._scene)
            super().mousePressEvent(event)
            return

        # Check if clicked on a SelectablePrimitiveItem
        if isinstance(item, SelectablePrimitiveItem):
            prim_id = item.primitive.id
            debug_print(f"  Clicked on primitive: {prim_id[:8]}..., multi_select={multi_select}")

            if multi_select:
                # Toggle selection for this primitive
                if prim_id in self.selected_primitive_ids:
                    self.selected_primitive_ids.remove(prim_id)
                    item.set_selected(False)
                    debug_print(f"    Removed from selection, now {len(self.selected_primitive_ids)} selected")
                    # Clear handles if no longer in selection
                    if self.selected_primitive_id == prim_id:
                        self._clear_resize_handles()
                        self._clear_vertex_handles()
                        self._clear_rotate_handle()
                        self.selected_primitive_id = None
                else:
                    self.selected_primitive_ids.append(prim_id)
                    item.set_selected(True)
                    debug_print(f"    Added to selection, now {len(self.selected_primitive_ids)} selected")
                    # Set as primary selection if first one
                    if not self.selected_primitive_id:
                        self._select_primitive(prim_id)

                # Update highlight borders for multi-selection
                self._update_multi_selection_highlights()
            else:
                # Single selection - clear previous and select this one
                self._clear_multi_selection()
                self._clear_group_selection()
                self._select_primitive(prim_id)
                self.selected_primitive_ids = [prim_id]
                debug_print(f"    Single selection")

            self._dragging = True
            super().mousePressEvent(event)
            return

        # Check other handle types
        if isinstance(item, VertexHandle):
            super().mousePressEvent(event)
            return  # Handled by VertexHandle
        if isinstance(item, (ResizeHandle, RotateHandle, BezierHandleItem, GroupResizeHandle, GroupRotateHandle)):
            super().mousePressEvent(event)
            return  # Handled by respective classes
        if isinstance(item, ConnectorHandle):
            super().mousePressEvent(event)
            return  # Handled by ConnectorHandle

        # Clicked on empty space - start rubberband selection
        if item is None:
            if not multi_select:
                # Clear all selections
                self._clear_multi_selection()
                self._clear_group_selection()
                self._select_primitive(None)

            # Start rubberband
            self._rubberband_active = True
            self._rubberband_origin = event.pos()
            if not hasattr(self, '_rubberband') or self._rubberband is None:
                self._rubberband = QRubberBand(QRubberBand.Shape.Rectangle, self)
            self._rubberband.setGeometry(QRect(self._rubberband_origin, QSize()))
            self._rubberband.show()

        super().mousePressEvent(event)

    def _clear_multi_selection(self):
        """Clear multi-selection state."""
        for prim_id in self.selected_primitive_ids:
            if prim_id in self._primitive_items:
                self._primitive_items[prim_id].set_selected(False)
        self.selected_primitive_ids.clear()

    def _update_multi_selection_highlights(self):
        """Update visual highlights for multi-selected primitives."""
        for prim_id in self.selected_primitive_ids:
            if prim_id in self._primitive_items:
                self._primitive_items[prim_id].set_selected(True)

    def mouseReleaseEvent(self, event):
        """Handle mouse release."""
        if self._rubberband_active:
            self._rubberband_active = False
            if hasattr(self, '_rubberband') and self._rubberband:
                self._rubberband.hide()

            # Get rubberband rect in scene coordinates
            rubberband_rect = QRect(self._rubberband_origin, event.pos()).normalized()
            scene_rect = self.mapToScene(rubberband_rect).boundingRect()

            debug_print(f"Rubberband release: rect={rubberband_rect}, scene_rect={scene_rect}")

            # Find all primitives within the rubberband
            for prim_id, item in self._primitive_items.items():
                item_rect = item.sceneBoundingRect()
                if scene_rect.intersects(item_rect):
                    if prim_id not in self.selected_primitive_ids:
                        self.selected_primitive_ids.append(prim_id)
                        item.set_selected(True)
                        debug_print(f"  Selected primitive: {prim_id[:8]}...")

            # Set primary selection if we have items
            if self.selected_primitive_ids and not self.selected_primitive_id:
                self.selected_primitive_id = self.selected_primitive_ids[0]
                # Don't call _select_primitive here as it clears handles

            debug_print(f"Rubberband selected {len(self.selected_primitive_ids)} primitives")

        super().mouseReleaseEvent(event)
        if self._dragging:
            self._dragging = False
            self._update_current_path()
            self._update_connector_positions()
            self.drag_completed.emit()
            self.shape_modified.emit()

    def mouseMoveEvent(self, event):
        """Handle mouse move for active handle dragging or rubberband."""
        if self._rubberband_active and hasattr(self, '_rubberband') and self._rubberband:
            self._rubberband.setGeometry(QRect(self._rubberband_origin, event.pos()).normalized())
        elif self._active_handle:
            scene_pos = self.mapToScene(event.pos())
            self._active_handle.handle_drag(scene_pos)
            self._update_current_path()
            self._update_connector_positions()
            self.shape_modified.emit()
        else:
            super().mouseMoveEvent(event)

    def keyPressEvent(self, event):
        """Handle keyboard shortcuts."""
        key = event.key()

        # Delete selected primitive(s)
        if key in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            if self.selected_primitive_ids:
                debug_print(f"Delete key pressed, deleting {len(self.selected_primitive_ids)} primitives")
                # Clear handles first
                self._clear_resize_handles()
                self._clear_vertex_handles()
                self._clear_rotate_handle()
                # Make a copy since we'll be modifying the list
                ids_to_delete = list(self.selected_primitive_ids)
                for prim_id in ids_to_delete:
                    self._remove_primitive(prim_id)
                # Clear selection
                self.selected_primitive_ids.clear()
                self.selected_primitive_id = None
                self._update_current_path()
                self.shape_modified.emit()
                event.accept()
                return

        # Escape to deselect
        elif key == Qt.Key.Key_Escape:
            self._clear_multi_selection()
            self._clear_group_selection()
            self._select_primitive(None)
            event.accept()
            return

        super().keyPressEvent(event)

    def _update_connector_positions(self):
        """Update all connector positions and displays."""
        if not self.current_path:
            return
        for handle in self._connector_handles.values():
            handle.update_position_on_edge(self.current_path)
            handle.update_display()

    def update_connector_handles(self):
        """Public method to update connector handle positions and displays."""
        self._update_connector_positions()

    def contextMenuEvent(self, event):
        """Show context menu."""
        self._show_context_menu(event.pos())

    def _show_context_menu(self, pos):
        """Show context menu based on selection."""
        debug_print(f"Context menu: selected_primitive_ids={self.selected_primitive_ids}, "
                   f"selected_vertex_id={self.selected_vertex_id}, "
                   f"selected_group_id={self.selected_group_id}")

        menu = QMenu(self)
        items_added = []

        # Vertex type selection (when a vertex is selected)
        if self.selected_vertex_id and self.selected_vertex_id in self._vertex_handles:
            handle = self._vertex_handles[self.selected_vertex_id]
            cp = handle.control_point

            menu.addSection("Vertex Type")
            items_added.append("vertex type options")

            corner_action = menu.addAction("Corner")
            corner_action.setCheckable(True)
            corner_action.setChecked(cp.point_type == PointType.CORNER)
            corner_action.triggered.connect(lambda: self._set_vertex_type(PointType.CORNER))

            smooth_action = menu.addAction("Smooth")
            smooth_action.setCheckable(True)
            smooth_action.setChecked(cp.point_type == PointType.SMOOTH)
            smooth_action.triggered.connect(lambda: self._set_vertex_type(PointType.SMOOTH))

            symmetric_action = menu.addAction("Symmetric")
            symmetric_action.setCheckable(True)
            symmetric_action.setChecked(cp.point_type == PointType.SYMMETRIC)
            symmetric_action.triggered.connect(lambda: self._set_vertex_type(PointType.SYMMETRIC))

            menu.addSeparator()

        # Sparsify - available when a single polygon is selected and no vertex selected
        elif len(self.selected_primitive_ids) == 1 and not self.selected_vertex_id:
            prim_id = self.selected_primitive_ids[0]
            prim = self._get_primitive_by_id(prim_id)
            if prim and prim.primitive_type == PrimitiveType.POLYGON:
                num_points = len(prim.control_points)
                if num_points > 4:
                    sparsify_action = menu.addAction(f"Sparsify ({num_points} vertices)")
                    sparsify_action.triggered.connect(self._sparsify_polygon)
                    items_added.append("sparsify")
                    menu.addSeparator()

        # Boolean operations - available when exactly 2 primitives selected
        if len(self.selected_primitive_ids) == 2:
            menu.addSection("Boolean Operations (A=1st, B=2nd)")
            items_added.append("boolean operations")

            union_action = menu.addAction("Union (A ∪ B)")
            union_action.triggered.connect(lambda: self._boolean_operation('union'))

            combine_action = menu.addAction("Combine/XOR (A ⊕ B)")
            combine_action.triggered.connect(lambda: self._boolean_operation('combine'))

            intersect_action = menu.addAction("Intersect (A ∩ B)")
            intersect_action.triggered.connect(lambda: self._boolean_operation('intersect'))

            subtract_action = menu.addAction("Subtract (A − B)")
            subtract_action.triggered.connect(lambda: self._boolean_operation('subtract'))

            fragment_action = menu.addAction("Fragment")
            fragment_action.triggered.connect(lambda: self._boolean_operation('fragment'))

            menu.addSeparator()

        # Group action - available when multiple primitives selected
        if len(self.selected_primitive_ids) > 1:
            group_action = menu.addAction("Group")
            group_action.triggered.connect(self._group_selected)
            items_added.append("group")

        # Ungroup action - available when a group is selected
        if self.selected_group_id:
            ungroup_action = menu.addAction("Ungroup")
            ungroup_action.triggered.connect(self._ungroup_selected)
            items_added.append("ungroup (group selected)")

        # Also check if a grouped primitive is selected
        if self.selected_primitive_id:
            group_id = self._find_group_for_primitive(self.selected_primitive_id)
            if group_id:
                ungroup_action = menu.addAction("Ungroup")
                ungroup_action.triggered.connect(lambda gid=group_id: self._ungroup(gid))
                items_added.append("ungroup (primitive in group)")

        # Snap settings - always available
        menu.addSeparator()
        snap_menu = menu.addMenu("Snap Settings (Ctrl+drag)")
        items_added.append("snap settings")

        grid_action = snap_menu.addAction(f"Grid Snap: {self.grid_snap_size:.0f} px")
        grid_action.triggered.connect(self._set_grid_snap_dialog)

        angle_action = snap_menu.addAction(f"Rotation Snap: {self.rotation_snap_angle:.0f}°")
        angle_action.triggered.connect(self._set_rotation_snap_dialog)

        debug_print(f"  Menu items added: {items_added}")

        if not menu.isEmpty():
            menu.exec(self.mapToGlobal(pos))

    def _set_vertex_type(self, point_type: PointType):
        """Set vertex type for selected vertex."""
        if not self.selected_vertex_id or self.selected_vertex_id not in self._vertex_handles:
            return

        handle = self._vertex_handles[self.selected_vertex_id]
        cp = handle.control_point

        old_type = cp.point_type
        cp.point_type = point_type

        if point_type == PointType.CORNER:
            cp.handle_in = None
            cp.handle_out = None
            handle._hide_bezier_handles()
        elif point_type in (PointType.SMOOTH, PointType.SYMMETRIC):
            if not cp.handle_in and not cp.handle_out:
                # Create default handles
                cp.handle_in = (-20, 0)
                cp.handle_out = (20, 0)
            handle._hide_bezier_handles()
            handle._show_bezier_handles()

        handle._update_appearance()
        handle.parent_item._create_path()
        handle.parent_item.update()
        self.shape_modified.emit()

    def _set_grid_snap_dialog(self):
        """Show dialog to set grid snap size."""
        value, ok = QInputDialog.getDouble(
            self, "Grid Snap Size",
            "Snap to grid size (pixels):",
            self.grid_snap_size, 1.0, 500.0, 0
        )
        if ok:
            self.grid_snap_size = value

    def _set_rotation_snap_dialog(self):
        """Show dialog to set rotation snap angle."""
        value, ok = QInputDialog.getDouble(
            self, "Rotation Snap Angle",
            "Snap to rotation angle (degrees):",
            self.rotation_snap_angle, 1.0, 90.0, 0
        )
        if ok:
            self.rotation_snap_angle = value

    def _get_primitive_by_id(self, prim_id: str) -> Optional[ShapePrimitive]:
        """Get a primitive by ID."""
        if self.shape:
            for prim in self.shape.primitives:
                if prim.id == prim_id:
                    return prim
        return None

    def _find_group_for_primitive(self, prim_id: str) -> Optional[str]:
        """Find the group ID that contains a primitive, or None."""
        for group_id, group in self.groups.items():
            if prim_id in group.member_ids:
                return group_id
        return None

    # =========================================================================
    # Group Operations
    # =========================================================================

    def _group_selected(self):
        """Group all selected primitives."""
        if len(self.selected_primitive_ids) < 2:
            return

        debug_print(f"Grouping {len(self.selected_primitive_ids)} primitives")

        group_id = str(uuid.uuid4())
        group = PrimitiveGroup(
            id=group_id,
            member_ids=list(self.selected_primitive_ids)
        )
        self.groups[group_id] = group

        # Turn off selection highlight on members
        for prim_id in self.selected_primitive_ids:
            if prim_id in self._primitive_items:
                self._primitive_items[prim_id].set_selected(False)

        # Create group item
        group_item = GroupItem(group, canvas=self)
        member_items = [self._primitive_items[pid] for pid in self.selected_primitive_ids if pid in self._primitive_items]
        group_item.set_members(member_items)
        self._scene.addItem(group_item)
        group_item.create_handles(self._scene)
        self.group_items[group_id] = group_item

        # Clear individual selection, select group
        self._clear_resize_handles()
        self._clear_vertex_handles()
        self._clear_rotate_handle()
        self.selected_primitive_ids.clear()
        self.selected_primitive_id = None
        self.selected_group_id = group_id

        self.shape_modified.emit()

    def _ungroup_selected(self):
        """Ungroup the selected group."""
        if self.selected_group_id:
            self._ungroup(self.selected_group_id)

    def _ungroup(self, group_id: str):
        """Ungroup a specific group."""
        if group_id not in self.groups:
            return

        debug_print(f"Ungrouping {group_id[:8]}...")

        group = self.groups[group_id]
        group_item = self.group_items.get(group_id)

        # Remove group item
        if group_item:
            group_item.clear_handles(self._scene)
            if group_item.scene():
                self._scene.removeItem(group_item)
            del self.group_items[group_id]

        # Remove group
        del self.groups[group_id]

        if self.selected_group_id == group_id:
            self.selected_group_id = None

        self.shape_modified.emit()

    def _clear_group_selection(self):
        """Clear group selection and hide the bounding box."""
        if self.selected_group_id and self.selected_group_id in self.group_items:
            group_item = self.group_items[self.selected_group_id]
            group_item.clear_handles(self._scene)
            group_item.set_group_selected(False)
        self.selected_group_id = None

    # =========================================================================
    # Boolean Operations
    # =========================================================================

    def _get_primitive_path(self, prim_id: str) -> QPainterPath:
        """Get the QPainterPath for a primitive in scene coordinates."""
        if prim_id not in self._primitive_items:
            return QPainterPath()

        prim = self._get_primitive_by_id(prim_id)
        item = self._primitive_items[prim_id]

        local_path = item.path()

        transform = QTransform()
        transform.translate(item.pos().x(), item.pos().y())
        if prim and prim.rotation != 0:
            transform.rotate(prim.rotation)

        return transform.map(local_path)

    def _boolean_operation(self, operation: str):
        """Perform a boolean operation on selected primitives."""
        if len(self.selected_primitive_ids) != 2:
            debug_print(f"Boolean operation requires exactly 2 primitives")
            return

        prim1_id, prim2_id = self.selected_primitive_ids[0], self.selected_primitive_ids[1]

        debug_print(f"Boolean operation: {operation}")
        debug_print(f"  A (1st selected): {prim1_id[:8]}...")
        debug_print(f"  B (2nd selected): {prim2_id[:8]}...")

        path1 = self._get_primitive_path(prim1_id)
        path2 = self._get_primitive_path(prim2_id)

        if path1.isEmpty() or path2.isEmpty():
            debug_print("  One or both paths are empty")
            return

        prim1 = self._get_primitive_by_id(prim1_id)
        prim2 = self._get_primitive_by_id(prim2_id)

        result_paths = []
        path_colors = []

        if operation == 'union':
            result_path = path1.united(path2)
            result_paths = [result_path]
            path_colors = [self.shape.style.fill_color]

        elif operation == 'combine':
            union_path = path1.united(path2)
            intersect_path = path1.intersected(path2)
            result_path = union_path.subtracted(intersect_path)
            result_paths = [result_path]
            path_colors = [self.shape.style.fill_color]

        elif operation == 'intersect':
            result_path = path1.intersected(path2)
            result_paths = [result_path]
            path_colors = [self.shape.style.fill_color]

        elif operation == 'subtract':
            result_path = path1.subtracted(path2)
            result_paths = [result_path]
            path_colors = [self.shape.style.fill_color]

        elif operation == 'fragment':
            intersect_path = path1.intersected(path2)
            a_only = path1.subtracted(path2)
            b_only = path2.subtracted(path1)

            if not a_only.isEmpty():
                result_paths.append(a_only)
                path_colors.append(self.shape.style.fill_color)
            if not intersect_path.isEmpty():
                result_paths.append(intersect_path)
                path_colors.append(self.shape.style.fill_color)
            if not b_only.isEmpty():
                result_paths.append(b_only)
                path_colors.append(self.shape.style.fill_color)

        if not result_paths:
            debug_print("  No result paths generated")
            return

        # Remove original primitives
        self._remove_primitive(prim1_id)
        self._remove_primitive(prim2_id)

        # Clear selection
        self.selected_primitive_ids.clear()
        self.selected_primitive_id = None
        self._clear_resize_handles()
        self._clear_vertex_handles()
        self._clear_rotate_handle()

        # Create new primitives from result paths
        new_prim_ids = []
        for i, result_path in enumerate(result_paths):
            if result_path.isEmpty():
                continue

            new_prims = self._path_to_polygon_primitives(result_path)

            for new_prim in new_prims:
                self.shape.add_primitive(new_prim)
                item = SelectablePrimitiveItem(new_prim, self.shape.style, canvas=self)
                self._scene.addItem(item)
                self._primitive_items[new_prim.id] = item
                new_prim_ids.append(new_prim.id)
                debug_print(f"  Created new primitive: {new_prim.id[:8]}...")

        # Select the first new primitive
        if new_prim_ids:
            self._select_primitive(new_prim_ids[0])

        self._update_current_path()
        self._update_connector_positions()
        self.shape_modified.emit()
        debug_print(f"  Boolean operation complete: created {len(new_prim_ids)} primitive(s)")

    def _remove_primitive(self, prim_id: str):
        """Remove a primitive from the canvas."""
        prim = self._get_primitive_by_id(prim_id)
        if not prim:
            return

        debug_print(f"Removing primitive: {prim_id[:8]}...")

        # Remove from shape
        self.shape.remove_primitive(prim_id)

        # Remove graphics item
        if prim_id in self._primitive_items:
            item = self._primitive_items[prim_id]
            if item.scene():
                self._scene.removeItem(item)
            del self._primitive_items[prim_id]

        # Clear selection if this was selected
        if self.selected_primitive_id == prim_id:
            self.selected_primitive_id = None
        if prim_id in self.selected_primitive_ids:
            self.selected_primitive_ids.remove(prim_id)

    def _path_to_polygon_primitives(self, path: QPainterPath) -> List[ShapePrimitive]:
        """Convert a QPainterPath to multiple polygon ShapePrimitives."""
        polygons = path.toSubpathPolygons()

        if not polygons:
            return []

        primitives = []
        min_area = 100

        for poly in polygons:
            if len(poly) < 3:
                continue

            area = self._polygon_area(poly)
            if area < min_area:
                continue

            # Create control points from polygon vertices
            point_tuples = []
            for point in poly:
                point_tuples.append((point.x() / self.canvas_size, point.y() / self.canvas_size))

            # Remove last point if it's the same as first
            if len(point_tuples) > 1:
                first = point_tuples[0]
                last = point_tuples[-1]
                if abs(first[0] - last[0]) < 0.001 and abs(first[1] - last[1]) < 0.001:
                    point_tuples.pop()

            if len(point_tuples) < 3:
                continue

            # Create primitive with normalized coordinates
            prim = ShapePrimitive.create_polygon(point_tuples)

            # Convert back to pixel coordinates
            for cp in prim.control_points:
                cp.x *= self.canvas_size
                cp.y *= self.canvas_size

            primitives.append(prim)

        return primitives

    def _polygon_area(self, polygon) -> float:
        """Calculate the area of a polygon using the shoelace formula."""
        n = len(polygon)
        if n < 3:
            return 0

        area = 0
        for i in range(n):
            j = (i + 1) % n
            area += polygon[i].x() * polygon[j].y()
            area -= polygon[j].x() * polygon[i].y()

        return abs(area) / 2

    # =========================================================================
    # Sparsify Operation
    # =========================================================================

    def _sparsify_polygon(self):
        """Remove extra vertices from a polygon using adjustable tolerance."""
        if not self.selected_primitive_ids:
            return

        prim_id = self.selected_primitive_ids[0]
        prim = self._get_primitive_by_id(prim_id)

        if not prim or prim.primitive_type != PrimitiveType.POLYGON:
            debug_print("Sparsify: Not a polygon")
            return

        if len(prim.control_points) <= 4:
            debug_print("Sparsify: Too few vertices to sparsify")
            return

        original_count = len(prim.control_points)
        n = original_count

        # Calculate edge length statistics
        edge_lengths = []
        for i in range(n):
            p1 = prim.control_points[i]
            p2 = prim.control_points[(i + 1) % n]
            dist = math.sqrt((p2.x - p1.x)**2 + (p2.y - p1.y)**2)
            edge_lengths.append(dist)

        avg_edge = sum(edge_lengths) / len(edge_lengths)
        min_edge = min(edge_lengths)
        max_edge = max(edge_lengths)

        # Calculate perpendicular distances
        perp_distances = []
        for i in range(n):
            prev_idx = (i - 1) % n
            next_idx = (i + 1) % n

            p_prev = prim.control_points[prev_idx]
            p_curr = prim.control_points[i]
            p_next = prim.control_points[next_idx]

            line_dx = p_next.x - p_prev.x
            line_dy = p_next.y - p_prev.y
            line_len = math.sqrt(line_dx**2 + line_dy**2)

            if line_len > 0.001:
                perp_dist = abs((p_curr.x - p_prev.x) * line_dy -
                               (p_curr.y - p_prev.y) * line_dx) / line_len
            else:
                perp_dist = 0

            perp_distances.append(perp_dist)

        sorted_perp = sorted(perp_distances)
        min_perp = sorted_perp[0]
        max_perp = sorted_perp[-1]
        median_perp = sorted_perp[len(sorted_perp) // 2]
        percentile_75 = sorted_perp[int(len(sorted_perp) * 0.75)]

        default_tolerance = percentile_75

        tolerance, ok = QInputDialog.getDouble(
            self,
            "Sparsify Polygon",
            f"Vertices: {original_count}\n\n"
            f"Edge lengths: min={min_edge:.1f}, avg={avg_edge:.1f}, max={max_edge:.1f}\n"
            f"Vertex deviations: min={min_perp:.1f}, median={median_perp:.1f}, max={max_perp:.1f}\n\n"
            f"Tolerance (vertices with deviation below this will be removed):\n"
            f"(Higher value = more vertices removed)",
            default_tolerance,
            0.1,
            max_perp + 1,
            1
        )

        if not ok:
            return

        debug_print(f"Sparsify: tolerance={tolerance:.1f}, starting with {original_count} vertices")

        total_removed = self._sparsify_with_tolerance(prim, tolerance)

        final_count = len(prim.control_points)
        debug_print(f"Sparsify complete: {original_count} → {final_count} vertices "
                   f"(removed {total_removed})")

        if total_removed == 0:
            QMessageBox.information(
                self,
                "Sparsify",
                f"No vertices removed.\nTry increasing the tolerance value."
            )
            return

        # Update the graphics item
        if prim_id in self._primitive_items:
            item = self._primitive_items[prim_id]
            item._center = item._calculate_center()
            item.setPos(item._center)
            item._last_pos = item._center
            item._create_path()
            item.prepareGeometryChange()
            item.update()
            self._scene.update()

            # Recreate vertex handles
            self._clear_vertex_handles()
            self._create_vertex_handles(prim)

        QMessageBox.information(
            self,
            "Sparsify Complete",
            f"Removed {total_removed} vertices.\nVertices: {original_count} → {final_count}"
        )

        self.shape_modified.emit()

    def _sparsify_with_tolerance(self, prim: ShapePrimitive, tolerance: float) -> int:
        """Remove vertices that don't contribute more than tolerance to the shape."""
        total_removed = 0
        max_passes = 20

        for pass_num in range(max_passes):
            if len(prim.control_points) <= 3:
                break

            n = len(prim.control_points)

            perp_distances = []
            for i in range(n):
                prev_idx = (i - 1) % n
                next_idx = (i + 1) % n

                p_prev = prim.control_points[prev_idx]
                p_curr = prim.control_points[i]
                p_next = prim.control_points[next_idx]

                line_dx = p_next.x - p_prev.x
                line_dy = p_next.y - p_prev.y
                line_len = math.sqrt(line_dx**2 + line_dy**2)

                if line_len > 0.001:
                    perp_dist = abs((p_curr.x - p_prev.x) * line_dy -
                                   (p_curr.y - p_prev.y) * line_dx) / line_len
                else:
                    perp_dist = 0

                perp_distances.append((i, perp_dist))

            removable = [(i, d) for i, d in perp_distances if d < tolerance]

            if not removable:
                break

            removable.sort(key=lambda x: x[1])

            to_remove = set()
            removed_indices = set()

            for idx, dist in removable:
                prev_idx = (idx - 1) % n
                next_idx = (idx + 1) % n

                if prev_idx in removed_indices or next_idx in removed_indices:
                    continue

                if n - len(to_remove) <= 3:
                    break

                to_remove.add(idx)
                removed_indices.add(idx)

            if not to_remove:
                break

            prim.control_points = [p for i, p in enumerate(prim.control_points) if i not in to_remove]
            total_removed += len(to_remove)

            debug_print(f"  Pass {pass_num + 1}: removed {len(to_remove)} vertices")

        return total_removed

    def add_primitive(self, prim_type: PrimitiveType):
        """Add a new primitive to the shape."""
        if not self.shape:
            return

        s = self.canvas_size

        if prim_type == PrimitiveType.ELLIPSE:
            prim = ShapePrimitive.create_ellipse(0.25, 0.25, 0.5, 0.5)
        elif prim_type == PrimitiveType.RECTANGLE:
            prim = ShapePrimitive.create_rectangle(0.25, 0.25, 0.5, 0.5, 0.1)
        elif prim_type == PrimitiveType.POLYGON:
            prim = ShapePrimitive.create_polygon([
                (0.5, 0.2), (0.8, 0.8), (0.2, 0.8)
            ])
        else:
            return

        # Convert to pixel coordinates
        if prim.bounds:
            x, y, w, h = prim.bounds
            prim.bounds = (x * s, y * s, w * s, h * s)
        if prim.control_points:
            for cp in prim.control_points:
                cp.x *= s
                cp.y *= s

        self.shape.add_primitive(prim)

        # Create graphics item
        item = SelectablePrimitiveItem(prim, self.shape.style, canvas=self)
        self._scene.addItem(item)
        self._primitive_items[prim.id] = item

        self._update_current_path()
        self._update_connector_positions()
        self.shape_modified.emit()

    def add_connector(self):
        """Add a new connector."""
        if not self.shape:
            return

        positions = [c.edge_position for c in self.shape.connectors]
        new_pos = 0.0
        for p in [0.0, 0.125, 0.25, 0.375, 0.5, 0.625, 0.75, 0.875]:
            if p not in positions:
                new_pos = p
                break

        conn = ShapeConnector(edge_position=new_pos, label=f"C{len(self.shape.connectors)+1}")
        conn.direction = ConnectorDirection.INOUT
        self.shape.add_connector(conn)

        if self.current_path:
            handle = ConnectorHandle(conn, self)
            handle.update_position_on_edge(self.current_path)
            self._scene.addItem(handle)
            self._connector_handles[conn.id] = handle

        self.shape_modified.emit()

    def set_show_grid(self, show: bool):
        """Show or hide the grid."""
        self.show_grid = show
        self._draw_grid()

    def set_grid_snap(self, enabled: bool):
        """Enable or disable grid snap (for compatibility)."""
        self.grid_snap = enabled

    def set_perimeter_id(self, prim_id: Optional[str]):
        """Set the perimeter primitive."""
        if self.shape:
            self.shape.perimeter_id = prim_id

    def get_perimeter_id(self) -> Optional[str]:
        """Get the perimeter primitive ID."""
        if self.shape:
            return self.shape.perimeter_id
        return None


# =============================================================================
# Style Editor Panel
# =============================================================================

class StyleEditorPanel(QGroupBox):
    """Panel for editing style of selected primitive with color buttons."""

    style_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__("Style", parent)
        self.shape: Optional[ShapeDefinition] = None
        self.canvas: Optional['ShapeEditorCanvas'] = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QFormLayout(self)
        layout.setSpacing(8)

        # Shape section
        shape_label = QLabel("<b>Selected Primitive</b>")
        layout.addRow(shape_label)

        # Fill color
        self.fill_color_btn = ColorButton(QColor("#4A90D9"))
        self.fill_color_btn.colorChanged.connect(self._on_fill_color_changed)
        layout.addRow("Fill:", self.fill_color_btn)

        # Fill opacity
        self.fill_opacity = QSlider(Qt.Orientation.Horizontal)
        self.fill_opacity.setRange(0, 100)
        self.fill_opacity.setValue(100)
        self.fill_opacity.valueChanged.connect(self._on_fill_opacity_changed)
        layout.addRow("Fill Opacity:", self.fill_opacity)

        # Stroke color
        self.stroke_color_btn = ColorButton(QColor("#2563EB"))
        self.stroke_color_btn.colorChanged.connect(self._on_stroke_color_changed)
        layout.addRow("Stroke:", self.stroke_color_btn)

        # Stroke width
        self.stroke_width = QDoubleSpinBox()
        self.stroke_width.setRange(0.5, 10.0)
        self.stroke_width.setSingleStep(0.5)
        self.stroke_width.setValue(2.0)
        self.stroke_width.valueChanged.connect(self._on_stroke_width_changed)
        layout.addRow("Stroke Width:", self.stroke_width)

        # Text section
        text_label = QLabel("<b>Text</b>")
        layout.addRow(text_label)

        # Font
        self.font_combo = QFontComboBox()
        self.font_combo.setCurrentFont(QFont("Arial"))
        self.font_combo.currentFontChanged.connect(self._on_font_changed)
        layout.addRow("Font:", self.font_combo)

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
        layout.addRow("Text Size:", self.icon_size)

        # Icon color
        self.icon_color_btn = ColorButton(QColor("#FFFFFF"))
        self.icon_color_btn.colorChanged.connect(self._on_icon_color_changed)
        layout.addRow("Text Color:", self.icon_color_btn)

    def set_canvas(self, canvas: 'ShapeEditorCanvas'):
        """Set reference to canvas for accessing selected primitive."""
        self.canvas = canvas

    def set_shape(self, shape: ShapeDefinition):
        """Load shape style into panel."""
        self.shape = shape
        self._load_style_from_shape()

    def _load_style_from_shape(self):
        """Load style from shape into UI."""
        if not self.shape:
            return
        style = self.shape.style
        self._load_style(style)

    def _load_style(self, style: ShapeStyle):
        """Load style values into UI widgets."""
        # Block signals
        for widget in [self.fill_color_btn, self.stroke_color_btn, self.icon_color_btn,
                       self.fill_opacity, self.stroke_width, self.icon_text, self.icon_size]:
            widget.blockSignals(True)

        self.fill_color_btn.setColor(style.fill_color)
        self.fill_opacity.setValue(int(style.fill_opacity * 100))
        self.stroke_color_btn.setColor(style.stroke_color)
        self.stroke_width.setValue(style.stroke_width)
        self.icon_text.setText(style.icon_text)
        self.icon_size.setValue(style.icon_font_size)
        self.icon_color_btn.setColor(style.icon_color)

        # Unblock signals
        for widget in [self.fill_color_btn, self.stroke_color_btn, self.icon_color_btn,
                       self.fill_opacity, self.stroke_width, self.icon_text, self.icon_size]:
            widget.blockSignals(False)

    def _get_selected_item(self) -> Optional['SelectablePrimitiveItem']:
        """Get currently selected primitive item from canvas."""
        if self.canvas and self.canvas.selected_primitive_id:
            return self.canvas._primitive_items.get(self.canvas.selected_primitive_id)
        return None

    def _on_fill_color_changed(self, color: QColor):
        if self.shape:
            self.shape.style.fill_color = color.name()
        # Update selected primitive's visual
        item = self._get_selected_item()
        if item:
            item.style.fill_color = color.name()
            item._apply_style()
        self.style_changed.emit()

    def _on_fill_opacity_changed(self, value: int):
        if self.shape:
            self.shape.style.fill_opacity = value / 100.0
        item = self._get_selected_item()
        if item:
            item.style.fill_opacity = value / 100.0
            item._apply_style()
        self.style_changed.emit()

    def _on_stroke_color_changed(self, color: QColor):
        if self.shape:
            self.shape.style.stroke_color = color.name()
        item = self._get_selected_item()
        if item:
            item.style.stroke_color = color.name()
            item._apply_style()
        self.style_changed.emit()

    def _on_stroke_width_changed(self, value: float):
        if self.shape:
            self.shape.style.stroke_width = value
        item = self._get_selected_item()
        if item:
            item.style.stroke_width = value
            item._apply_style()
        self.style_changed.emit()

    def _on_font_changed(self, font: QFont):
        if self.shape:
            self.shape.style.icon_font_family = font.family()
            self.style_changed.emit()

    def _on_icon_text_changed(self, text: str):
        if self.shape:
            self.shape.style.icon_text = text
            self.style_changed.emit()

    def _on_icon_size_changed(self, value: int):
        if self.shape:
            self.shape.style.icon_font_size = value
            self.style_changed.emit()

    def _on_icon_color_changed(self, color: QColor):
        if self.shape:
            self.shape.style.icon_color = color.name()
            self.style_changed.emit()


# =============================================================================
# Primitives Panel
# =============================================================================

class PrimitivesPanel(QGroupBox):
    """Panel for managing shape primitives with 8-char IDs and perimeter flag."""

    primitive_selected = pyqtSignal(str)
    primitive_add_requested = pyqtSignal(object)
    primitive_remove_requested = pyqtSignal(str)
    perimeter_changed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__("Primitives", parent)
        self.shape: Optional[ShapeDefinition] = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # List
        self.prim_list = QListWidget()
        self.prim_list.currentItemChanged.connect(self._on_selection_changed)
        self.prim_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.prim_list.customContextMenuRequested.connect(self._show_context_menu)
        layout.addWidget(self.prim_list)

        # Add buttons
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
        """Load primitives into list."""
        self.shape = shape

        # Set default perimeter if not set
        if shape.perimeter_id is None and shape.primitives:
            shape.perimeter_id = shape.primitives[0].id

        self._refresh_list()

    def _refresh_list(self):
        """Refresh the primitives list."""
        self.prim_list.clear()
        if not self.shape:
            return

        perimeter_id = self.shape.perimeter_id

        for prim in self.shape.primitives:
            short_id = get_short_id(prim.id)
            type_abbrev = get_primitive_type_abbrev(prim.primitive_type)
            perimeter_mark = " [P]" if prim.id == perimeter_id else ""

            text = f"{short_id} - {type_abbrev}{perimeter_mark}"

            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, prim.id)
            self.prim_list.addItem(item)

    def _on_selection_changed(self, current, previous):
        if current:
            prim_id = current.data(Qt.ItemDataRole.UserRole)
            self.primitive_selected.emit(prim_id)

    def _show_context_menu(self, pos):
        """Context menu for perimeter selection."""
        item = self.prim_list.itemAt(pos)
        if not item:
            return

        prim_id = item.data(Qt.ItemDataRole.UserRole)
        if not prim_id:
            return

        menu = QMenu(self)

        is_perimeter = self.shape and prim_id == self.shape.perimeter_id
        if is_perimeter:
            action = menu.addAction("✓ Perimeter (clear)")
            action.triggered.connect(lambda: self._set_perimeter(None))
        else:
            action = menu.addAction("Set as Perimeter")
            action.triggered.connect(lambda: self._set_perimeter(prim_id))

        menu.exec(self.prim_list.mapToGlobal(pos))

    def _set_perimeter(self, prim_id: Optional[str]):
        """Set perimeter primitive."""
        if self.shape:
            self.shape.perimeter_id = prim_id
        self._refresh_list()
        self.perimeter_changed.emit(prim_id or "")

    def get_perimeter_id(self) -> Optional[str]:
        if self.shape:
            return self.shape.perimeter_id
        return None

    def set_perimeter_id(self, prim_id: Optional[str]):
        """Set perimeter ID (used when loading shape)."""
        if self.shape:
            self.shape.perimeter_id = prim_id
        self._refresh_list()

    def _remove_selected(self):
        current = self.prim_list.currentItem()
        if current and self.shape:
            prim_id = current.data(Qt.ItemDataRole.UserRole)
            if len(self.shape.primitives) > 1:
                self.primitive_remove_requested.emit(prim_id)


# =============================================================================
# Connectors Panel
# =============================================================================

class ConnectorsPanel(QGroupBox):
    """Panel for managing shape connectors with direction selection."""

    connector_selected = pyqtSignal(str)
    connector_deselected = pyqtSignal()
    connector_add_requested = pyqtSignal()
    connector_remove_requested = pyqtSignal(str)
    connector_label_changed = pyqtSignal(str, str)
    connector_position_changed = pyqtSignal(str, float)  # conn_id, new_position
    connector_direction_changed = pyqtSignal(str)  # conn_id (direction already updated in connector)

    def __init__(self, parent=None):
        super().__init__("Connectors", parent)
        self.shape: Optional[ShapeDefinition] = None
        self._updating_selection = False
        self._setup_ui()
        self._update_controls_enabled()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # List
        self.conn_list = QListWidget()
        self.conn_list.currentItemChanged.connect(self._on_selection_changed)
        layout.addWidget(self.conn_list)

        # Label editor
        label_layout = QHBoxLayout()
        self.label_label = QLabel("Label:")
        label_layout.addWidget(self.label_label)
        self.label_edit = QLineEdit()
        self.label_edit.setMaxLength(10)
        self.label_edit.textChanged.connect(self._on_label_changed)
        label_layout.addWidget(self.label_edit)
        layout.addLayout(label_layout)

        # Position display
        pos_layout = QHBoxLayout()
        self.pos_label = QLabel("Position:")
        pos_layout.addWidget(self.pos_label)
        self.pos_spin = QSpinBox()
        self.pos_spin.setRange(0, 100)
        self.pos_spin.setSuffix("%")
        self.pos_spin.valueChanged.connect(self._on_position_changed)
        pos_layout.addWidget(self.pos_spin)
        pos_layout.addStretch()
        layout.addLayout(pos_layout)

        # Direction selector
        dir_layout = QHBoxLayout()
        self.dir_label = QLabel("Direction:")
        dir_layout.addWidget(self.dir_label)
        self.direction_combo = QComboBox()
        self.direction_combo.addItem("← In", ConnectorDirection.IN)
        self.direction_combo.addItem("→ Out", ConnectorDirection.OUT)
        self.direction_combo.addItem("↔ InOut", ConnectorDirection.INOUT)
        self.direction_combo.setCurrentIndex(2)
        self.direction_combo.currentIndexChanged.connect(self._on_direction_changed)
        dir_layout.addWidget(self.direction_combo)
        layout.addLayout(dir_layout)

        # Buttons
        btn_layout = QHBoxLayout()

        self.add_btn = QPushButton("+ Add")
        self.add_btn.clicked.connect(self._add_connector)
        btn_layout.addWidget(self.add_btn)

        self.remove_btn = QPushButton("- Remove")
        self.remove_btn.clicked.connect(self._remove_selected)
        btn_layout.addWidget(self.remove_btn)

        layout.addLayout(btn_layout)

    def _update_controls_enabled(self):
        """Enable/disable controls based on whether a connector is selected."""
        has_selection = self.conn_list.currentItem() is not None
        self.label_label.setEnabled(has_selection)
        self.label_edit.setEnabled(has_selection)
        self.pos_label.setEnabled(has_selection)
        self.pos_spin.setEnabled(has_selection)
        self.dir_label.setEnabled(has_selection)
        self.direction_combo.setEnabled(has_selection)
        self.remove_btn.setEnabled(has_selection and self.shape and len(self.shape.connectors) > 1)

        if not has_selection:
            self.label_edit.blockSignals(True)
            self.label_edit.clear()
            self.label_edit.blockSignals(False)
            self.pos_spin.blockSignals(True)
            self.pos_spin.setValue(0)
            self.pos_spin.blockSignals(False)

    def set_shape(self, shape: ShapeDefinition):
        """Load connectors into list."""
        self.shape = shape
        self._refresh_list()
        self._update_controls_enabled()

    def _get_direction_symbol(self, direction) -> str:
        """Get the arrow symbol for a direction."""
        if isinstance(direction, ConnectorDirection):
            return {"In": "←", "Out": "→", "InOut": "↔"}[direction.value]
        elif direction in ("In", "Out", "InOut"):
            return {"In": "←", "Out": "→", "InOut": "↔"}[direction]
        return "↔"

    def _format_item_text(self, conn: ShapeConnector) -> str:
        """Format the list item text for a connector."""
        pos_pct = int(conn.edge_position * 100)
        direction = getattr(conn, 'direction', ConnectorDirection.INOUT)
        dir_symbol = self._get_direction_symbol(direction)
        return f"{dir_symbol} {conn.label} @ {pos_pct}%"

    def _refresh_list(self):
        """Refresh connectors list."""
        # Save current selection
        current_id = None
        current = self.conn_list.currentItem()
        if current:
            current_id = current.data(Qt.ItemDataRole.UserRole)

        self.conn_list.blockSignals(True)
        self.conn_list.clear()
        if not self.shape:
            self.conn_list.blockSignals(False)
            return

        select_index = -1
        for i, conn in enumerate(self.shape.connectors):
            item = QListWidgetItem(self._format_item_text(conn))
            item.setData(Qt.ItemDataRole.UserRole, conn.id)
            self.conn_list.addItem(item)
            if conn.id == current_id:
                select_index = i

        # Restore selection
        if select_index >= 0:
            self.conn_list.setCurrentRow(select_index)
        self.conn_list.blockSignals(False)

    def _update_current_item_text(self):
        """Update just the current item's text without refreshing entire list."""
        current = self.conn_list.currentItem()
        if current and self.shape:
            conn_id = current.data(Qt.ItemDataRole.UserRole)
            conn = self.shape.get_connector_by_id(conn_id)
            if conn:
                current.setText(self._format_item_text(conn))

    def select_connector_by_id(self, conn_id: str):
        """Select a connector in the list by its ID (called when canvas selects a connector)."""
        if self._updating_selection:
            return
        self._updating_selection = True
        
        found = False
        for i in range(self.conn_list.count()):
            item = self.conn_list.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == conn_id:
                self.conn_list.setCurrentItem(item)
                found = True
                break
        
        # Update controls with connector data
        if found and self.shape:
            conn = self.shape.get_connector_by_id(conn_id)
            if conn:
                self._update_controls_enabled()
                
                # Update label edit
                self.label_edit.blockSignals(True)
                self.label_edit.setText(conn.label)
                self.label_edit.blockSignals(False)

                # Update position spinbox
                self.pos_spin.blockSignals(True)
                self.pos_spin.setValue(int(conn.edge_position * 100))
                self.pos_spin.blockSignals(False)

                # Update direction combo
                direction = getattr(conn, 'direction', ConnectorDirection.INOUT)
                if isinstance(direction, ConnectorDirection):
                    for i in range(self.direction_combo.count()):
                        if self.direction_combo.itemData(i) == direction:
                            self.direction_combo.blockSignals(True)
                            self.direction_combo.setCurrentIndex(i)
                            self.direction_combo.blockSignals(False)
                            break
        
        self._updating_selection = False

    def clear_selection(self):
        """Clear the current selection and deselect all items."""
        if self._updating_selection:
            return
        self._updating_selection = True
        
        # Clear selection in list widget
        self.conn_list.blockSignals(True)
        self.conn_list.clearSelection()
        self.conn_list.setCurrentRow(-1)  # Deselect all rows
        self.conn_list.blockSignals(False)
        
        # Update controls (disable them)
        self._update_controls_enabled()
        
        self._updating_selection = False

    def _on_selection_changed(self, current, previous):
        if self._updating_selection:
            return

        self._update_controls_enabled()

        if current and self.shape:
            conn_id = current.data(Qt.ItemDataRole.UserRole)
            conn = self.shape.get_connector_by_id(conn_id)
            if conn:
                # Update label edit
                self.label_edit.blockSignals(True)
                self.label_edit.setText(conn.label)
                self.label_edit.blockSignals(False)

                # Update position spinbox
                self.pos_spin.blockSignals(True)
                self.pos_spin.setValue(int(conn.edge_position * 100))
                self.pos_spin.blockSignals(False)

                # Update direction combo
                direction = getattr(conn, 'direction', ConnectorDirection.INOUT)
                if isinstance(direction, ConnectorDirection):
                    for i in range(self.direction_combo.count()):
                        if self.direction_combo.itemData(i) == direction:
                            self.direction_combo.blockSignals(True)
                            self.direction_combo.setCurrentIndex(i)
                            self.direction_combo.blockSignals(False)
                            break

                self.connector_selected.emit(conn_id)
        else:
            self.connector_deselected.emit()

    def _on_label_changed(self, text: str):
        current = self.conn_list.currentItem()
        if current and self.shape:
            conn_id = current.data(Qt.ItemDataRole.UserRole)
            conn = self.shape.get_connector_by_id(conn_id)
            if conn:
                conn.label = text
                self._update_current_item_text()
            self.connector_label_changed.emit(conn_id, text)

    def _on_position_changed(self, value: int):
        """Handle position spinbox change."""
        current = self.conn_list.currentItem()
        if current and self.shape:
            conn_id = current.data(Qt.ItemDataRole.UserRole)
            conn = self.shape.get_connector_by_id(conn_id)
            if conn:
                conn.edge_position = value / 100.0
                self._update_current_item_text()
                # Emit signal to update canvas
                self.connector_position_changed.emit(conn_id, conn.edge_position)

    def _on_direction_changed(self, index: int):
        current = self.conn_list.currentItem()
        if current and self.shape:
            conn_id = current.data(Qt.ItemDataRole.UserRole)
            direction = self.direction_combo.currentData()

            conn = self.shape.get_connector_by_id(conn_id)
            if conn:
                conn.direction = direction
                # Update the current item text
                self._update_current_item_text()
                # Emit signal to update canvas
                self.connector_direction_changed.emit(conn_id)

    def update_connector_position(self, conn_id: str):
        """Update display when connector is moved on canvas."""
        if not self.shape:
            return
        conn = self.shape.get_connector_by_id(conn_id)
        if conn:
            # Update list item text
            for i in range(self.conn_list.count()):
                item = self.conn_list.item(i)
                if item.data(Qt.ItemDataRole.UserRole) == conn_id:
                    item.setText(self._format_item_text(conn))
                    break

            # Update position spinbox if this is the selected connector
            current = self.conn_list.currentItem()
            if current and current.data(Qt.ItemDataRole.UserRole) == conn_id:
                self.pos_spin.blockSignals(True)
                self.pos_spin.setValue(int(conn.edge_position * 100))
                self.pos_spin.blockSignals(False)

    def _add_connector(self):
        self.connector_add_requested.emit()

    def _remove_selected(self):
        current = self.conn_list.currentItem()
        if current and self.shape:
            conn_id = current.data(Qt.ItemDataRole.UserRole)
            if len(self.shape.connectors) > 1:
                self.connector_remove_requested.emit(conn_id)


# =============================================================================
# Main Shape Editor Dialog
# =============================================================================

class ShapeEditorDialog(QDialog):
    """
    Dialog for editing node shape definitions.

    Features:
    - Interactive canvas with vertex/resize/rotate handles
    - Primitives panel with 8-char IDs and perimeter selection
    - Style panel with color buttons
    - Connectors panel with direction selection
    - Ctrl+drag for grid/angle snapping
    - Undo/redo support
    """

    def __init__(self, shape: ShapeDefinition, parent=None):
        super().__init__(parent)

        self.original_shape = shape
        self.shape = shape.copy()

        self.undo_stack = UndoStack()

        self._setup_ui()
        self._connect_signals()
        self._load_shape()

    def _setup_ui(self):
        """Build the dialog UI."""
        self.setWindowTitle(f"Shape Editor: {self.shape.name}")
        self.setMinimumSize(800, 600)

        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        # Menu bar
        self._create_menu_bar(layout)

        # Main content
        content = QHBoxLayout()
        content.setSpacing(8)

        # Canvas - expanding to fill available space
        self.canvas = ShapeEditorCanvas()
        self.canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        content.addWidget(self.canvas)

        # Panels - fixed width, pushed to the right
        panels_widget = QWidget()
        panels_widget.setFixedWidth(220)
        panels_widget.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
        panels = QVBoxLayout(panels_widget)
        panels.setContentsMargins(0, 0, 0, 0)
        panels.setSpacing(8)

        self.primitives_panel = PrimitivesPanel()
        self.primitives_panel.setMaximumHeight(180)
        panels.addWidget(self.primitives_panel)

        self.style_panel = StyleEditorPanel()
        panels.addWidget(self.style_panel)

        self.connectors_panel = ConnectorsPanel()
        panels.addWidget(self.connectors_panel)

        content.addWidget(panels_widget)
        layout.addLayout(content)

        # Bottom toolbar
        toolbar = QHBoxLayout()

        self.show_grid_cb = QCheckBox("Show Grid")
        self.show_grid_cb.setChecked(True)
        self.show_grid_cb.toggled.connect(self.canvas.set_show_grid)
        toolbar.addWidget(self.show_grid_cb)

        self.grid_snap_cb = QCheckBox("Snap to Grid (Ctrl+drag)")
        self.grid_snap_cb.setChecked(True)
        self.grid_snap_cb.toggled.connect(self.canvas.set_grid_snap)
        toolbar.addWidget(self.grid_snap_cb)

        toolbar.addStretch()

        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Cancel |
            QDialogButtonBox.StandardButton.Save
        )
        button_box.rejected.connect(self.reject)
        button_box.accepted.connect(self._on_save)
        toolbar.addWidget(button_box)

        layout.addLayout(toolbar)

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

        self.undo_action = edit_menu.addAction("Undo")
        self.undo_action.setShortcut(QKeySequence.StandardKey.Undo)
        self.undo_action.triggered.connect(self._on_undo)
        self.undo_action.setEnabled(False)

        self.redo_action = edit_menu.addAction("Redo")
        self.redo_action.setShortcut(QKeySequence.StandardKey.Redo)
        self.redo_action.triggered.connect(self._on_redo)
        self.redo_action.setEnabled(False)

        edit_menu.addSeparator()

        add_prim_menu = edit_menu.addMenu("Add Primitive")
        add_ellipse = add_prim_menu.addAction("Ellipse")
        add_ellipse.triggered.connect(lambda: self._on_primitive_add(PrimitiveType.ELLIPSE))
        add_rect = add_prim_menu.addAction("Rectangle")
        add_rect.triggered.connect(lambda: self._on_primitive_add(PrimitiveType.RECTANGLE))
        add_poly = add_prim_menu.addAction("Polygon")
        add_poly.triggered.connect(lambda: self._on_primitive_add(PrimitiveType.POLYGON))

        add_conn = edit_menu.addAction("Add Connector")
        add_conn.triggered.connect(self._on_connector_add)

        # View menu
        view_menu = menu_bar.addMenu("View")

        self.grid_action = view_menu.addAction("Show Grid")
        self.grid_action.setCheckable(True)
        self.grid_action.setChecked(True)

        self.snap_action = view_menu.addAction("Snap to Grid")
        self.snap_action.setCheckable(True)
        self.snap_action.setChecked(True)

        layout.setMenuBar(menu_bar)

    def _connect_signals(self):
        """Connect signals."""
        self.canvas.shape_modified.connect(self._on_shape_modified)
        self.canvas.connector_moved.connect(self.connectors_panel.update_connector_position)
        self.canvas.connector_moved.connect(self._on_canvas_connector_selected)  # Also select when moved
        self.canvas.connector_selected.connect(self._on_canvas_connector_selected)
        self.canvas.connector_deselected.connect(self.connectors_panel.clear_selection)
        self.canvas.drag_completed.connect(self._on_drag_completed)
        self.canvas.primitive_selected.connect(self._on_canvas_primitive_selected)

        self.style_panel.style_changed.connect(self._on_style_changed)

        self.primitives_panel.primitive_selected.connect(self._on_panel_primitive_selected)
        self.primitives_panel.primitive_add_requested.connect(self._on_primitive_add)
        self.primitives_panel.primitive_remove_requested.connect(self._on_primitive_remove)
        self.primitives_panel.perimeter_changed.connect(self._on_perimeter_changed)

        self.connectors_panel.connector_selected.connect(self._on_panel_connector_selected)
        self.connectors_panel.connector_add_requested.connect(self._on_connector_add)
        self.connectors_panel.connector_remove_requested.connect(self._on_connector_remove)
        self.connectors_panel.connector_label_changed.connect(self._on_connector_label_changed)
        self.connectors_panel.connector_position_changed.connect(self._on_connector_position_changed)
        self.connectors_panel.connector_direction_changed.connect(self._on_connector_direction_changed)

        self.grid_action.triggered.connect(self.show_grid_cb.setChecked)
        self.snap_action.triggered.connect(self.grid_snap_cb.setChecked)

    def _on_canvas_connector_selected(self, conn_id: str):
        """Handle connector selection from canvas - update panel."""
        self.connectors_panel.select_connector_by_id(conn_id)

    def _on_panel_connector_selected(self, conn_id: str):
        """Handle connector selection from panel - highlight on canvas."""
        # Highlight the connector handle on canvas
        for handle_id, handle in self.canvas._connector_handles.items():
            if handle_id == conn_id:
                handle.setSelected(True)
                handle.setBrush(QBrush(QColor("#FBBF24")))  # Highlighted color
            else:
                handle.setSelected(False)
                handle.setBrush(QBrush(QColor("#F59E0B")))  # Normal color

    def _load_shape(self):
        """Load shape into editors."""
        self.canvas.set_shape(self.shape)

        canvas_shape = self.canvas.get_shape()
        internal_shape = self.canvas.get_internal_shape()
        if canvas_shape and internal_shape:
            self.style_panel.set_canvas(self.canvas)
            # Style panel needs internal shape for direct style updates
            self.style_panel.set_shape(internal_shape)
            self.primitives_panel.set_shape(canvas_shape)
            # ConnectorsPanel needs the internal shape for real-time updates
            self.connectors_panel.set_shape(internal_shape)

        self.undo_stack.initialize(self.shape)
        self._update_undo_actions()

    def _on_shape_modified(self):
        """Handle shape modification."""
        pass  # Handled by drag_completed

    def _on_drag_completed(self):
        """Handle drag completion."""
        self._save_undo_state()
        shape = self.canvas.get_shape()
        internal_shape = self.canvas.get_internal_shape()
        if shape and internal_shape:
            self.style_panel.set_shape(internal_shape)
            self.primitives_panel.set_shape(shape)
            # ConnectorsPanel needs the internal shape for real-time updates
            self.connectors_panel.set_shape(internal_shape)

    def _on_canvas_primitive_selected(self, prim_id: str):
        """Handle selection from canvas."""
        # Select in panel list
        for i in range(self.primitives_panel.prim_list.count()):
            item = self.primitives_panel.prim_list.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == prim_id:
                self.primitives_panel.prim_list.setCurrentItem(item)
                break

    def _on_panel_primitive_selected(self, prim_id: str):
        """Handle selection from panel."""
        self.canvas._select_primitive(prim_id)

    def _on_style_changed(self):
        """Handle style changes - style panel already updates internal shape directly."""
        self._save_undo_state()
        # Style panel has internal shape reference, so style is already updated
        # Visual updates happen via item._apply_style() in the style panel handlers

    def _on_primitive_add(self, prim_type: PrimitiveType):
        """Handle primitive add."""
        self._save_undo_state()
        self.canvas.add_primitive(prim_type)
        shape = self.canvas.get_shape()
        if shape:
            self.primitives_panel.set_shape(shape)

    def _on_primitive_remove(self, prim_id: str):
        """Handle primitive remove."""
        self._save_undo_state()
        shape = self.canvas.get_shape()
        if shape and len(shape.primitives) > 1:
            shape.remove_primitive(prim_id)
            self.canvas.set_shape(shape)
            self.primitives_panel.set_shape(shape)

    def _on_perimeter_changed(self, prim_id: str):
        """Handle perimeter change."""
        self.canvas.set_perimeter_id(prim_id if prim_id else None)

    def _on_connector_add(self):
        """Handle connector add."""
        self._save_undo_state()
        self.canvas.add_connector()
        internal_shape = self.canvas.get_internal_shape()
        if internal_shape:
            self.connectors_panel.set_shape(internal_shape)

    def _on_connector_remove(self, conn_id: str):
        """Handle connector remove."""
        self._save_undo_state()
        internal_shape = self.canvas.get_internal_shape()
        if internal_shape and len(internal_shape.connectors) > 1:
            internal_shape.remove_connector(conn_id)
            # Rebuild canvas to reflect removal
            self.canvas._rebuild_scene()
            self.connectors_panel.set_shape(internal_shape)

    def _on_connector_label_changed(self, conn_id: str, new_label: str):
        """Handle connector label change."""
        internal_shape = self.canvas.get_internal_shape()
        if internal_shape:
            conn = internal_shape.get_connector_by_id(conn_id)
            if conn:
                conn.label = new_label
                # Update the canvas connector handle display
                self.canvas.update_connector_handles()

    def _on_connector_position_changed(self, conn_id: str, new_position: float):
        """Handle connector position change from panel spinbox."""
        self._save_undo_state()
        internal_shape = self.canvas.get_internal_shape()
        if internal_shape:
            conn = internal_shape.get_connector_by_id(conn_id)
            if conn:
                conn.edge_position = new_position
                # Update the canvas to move the connector handle
                self.canvas.update_connector_handles()

    def _on_connector_direction_changed(self, conn_id: str):
        """Handle connector direction change from panel combo."""
        # Direction already updated in connector by the panel (which has internal shape)
        # Just update the canvas display
        self.canvas.update_connector_handles()

    def _save_undo_state(self):
        """Save state for undo."""
        if hasattr(self, '_in_undo_redo') and self._in_undo_redo:
            return

        shape = self.canvas.get_shape()
        if shape:
            self.undo_stack.save_state(shape)
            self._update_undo_actions()

    def _update_undo_actions(self):
        """Update undo/redo action states."""
        if hasattr(self, 'undo_action'):
            self.undo_action.setEnabled(self.undo_stack.can_undo())
        if hasattr(self, 'redo_action'):
            self.redo_action.setEnabled(self.undo_stack.can_redo())

    def _on_undo(self):
        """Perform undo."""
        shape = self.undo_stack.undo()
        if shape:
            self._in_undo_redo = True
            self.shape = shape
            self.canvas.set_shape(shape)
            canvas_shape = self.canvas.get_shape()
            internal_shape = self.canvas.get_internal_shape()
            self.style_panel.set_shape(internal_shape)
            self.primitives_panel.set_shape(canvas_shape)
            self.connectors_panel.set_shape(internal_shape)
            self._in_undo_redo = False
            self._update_undo_actions()

    def _on_redo(self):
        """Perform redo."""
        shape = self.undo_stack.redo()
        if shape:
            self._in_undo_redo = True
            self.shape = shape
            self.canvas.set_shape(shape)
            canvas_shape = self.canvas.get_shape()
            internal_shape = self.canvas.get_internal_shape()
            self.style_panel.set_shape(internal_shape)
            self.primitives_panel.set_shape(canvas_shape)
            self.connectors_panel.set_shape(internal_shape)
            self._in_undo_redo = False
            self._update_undo_actions()

    def _on_save(self):
        """Save and close."""
        shape_manager = get_shape_manager()
        final_shape = self.canvas.get_shape()
        if final_shape:
            final_shape.modified = True
            final_shape.is_default = False
            shape_manager.update_shape_path_offset(final_shape)
            shape_manager.update_shape(final_shape)
        self.accept()

    def _load_shape_file(self):
        """Load shape from file."""
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
        """Reset to default shape."""
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
