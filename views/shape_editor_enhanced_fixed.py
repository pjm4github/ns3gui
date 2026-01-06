"""
Enhanced Shape Editor Canvas with Polygon Point Editing and Bezier Curves
Compatible with existing shape_editor_dialog.py structure

FIXED: Changed self.scene to self._scene to avoid shadowing inherited scene() method
DEBUG: Set DEBUG_ENABLED = True to see console output
"""

from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import *
from typing import Optional, List, Dict, Tuple
from dataclasses import dataclass, field
from enum import Enum
import uuid
import math
import sys
import traceback
from functools import wraps


# =============================================================================
# DEBUG CONFIGURATION - Set to True to enable debug output
# =============================================================================
DEBUG_ENABLED = True


# =============================================================================
# DEBUG UTILITIES
# =============================================================================

class RecursionTracker:
    """Tracks call depth for methods to detect infinite recursion."""

    def __init__(self, max_depth: int = 50):
        self.call_stacks: Dict[str, int] = {}
        self.max_depth = max_depth
        self.enabled = True

    def enter(self, method_name: str) -> int:
        """Enter a method, returns current depth."""
        if not self.enabled or not DEBUG_ENABLED:
            return 0

        if method_name not in self.call_stacks:
            self.call_stacks[method_name] = 0

        self.call_stacks[method_name] += 1
        depth = self.call_stacks[method_name]

        if depth > self.max_depth:
            print(f"\n{'='*60}")
            print(f"RECURSION DETECTED in {method_name}!")
            print(f"Depth: {depth}")
            print(f"{'='*60}")
            print("Current call stacks:")
            for name, d in sorted(self.call_stacks.items(), key=lambda x: -x[1]):
                if d > 0:
                    print(f"  {name}: {d}")
            print(f"{'='*60}")
            print("Stack trace:")
            traceback.print_stack()
            print(f"{'='*60}\n")

            # Raise exception to stop and allow debugger to catch it
            raise RecursionError(f"Infinite recursion detected in {method_name} at depth {depth}")

        return depth

    def exit(self, method_name: str):
        """Exit a method."""
        if not self.enabled or not DEBUG_ENABLED:
            return
        if method_name in self.call_stacks:
            self.call_stacks[method_name] = max(0, self.call_stacks[method_name] - 1)

    def reset(self):
        """Reset all counters."""
        self.call_stacks.clear()


# Global tracker instance
TRACKER = RecursionTracker(max_depth=30)


def track_recursion(func):
    """Decorator to track method calls for recursion detection."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not DEBUG_ENABLED:
            return func(*args, **kwargs)

        try:
            # Get class name if this is a method
            if args and hasattr(args[0], '__class__'):
                method_name = f"{args[0].__class__.__name__}.{func.__name__}"
            else:
                method_name = func.__name__

            depth = TRACKER.enter(method_name)

            # Log entry at certain depths
            if depth > 5:
                print(f"[DEPTH {depth}] Entering {method_name}")

            try:
                result = func(*args, **kwargs)
                return result
            finally:
                TRACKER.exit(method_name)
        except RecursionError:
            raise  # Re-raise recursion errors
        except Exception as e:
            # Log but don't crash on decorator errors
            print(f"[DEBUG ERROR] Exception in {func.__name__}: {e}")
            # Fall back to calling function without tracking
            return func(*args, **kwargs)

    return wrapper


def debug_print(msg: str, level: int = 0):
    """Print debug message with indentation. Only prints if DEBUG_ENABLED is True."""
    if not DEBUG_ENABLED:
        return
    indent = "  " * level
    print(f"[DEBUG] {indent}{msg}")


# =============================================================================
# Data Models (Compatible with existing structure)
# =============================================================================

class PrimitiveType(Enum):
    """Types of primitives that can be added to shapes."""
    ELLIPSE = "ellipse"
    RECTANGLE = "rectangle"
    POLYGON = "polygon"


class PointType(Enum):
    """Types of control points for polygon editing."""
    CORNER = "corner"        # Sharp corner
    SMOOTH = "smooth"        # Smooth bezier point
    SYMMETRIC = "symmetric"  # Symmetric bezier handles


@dataclass
class ControlPoint:
    """A control point in a polygon with optional bezier handles."""
    id: str
    x: float
    y: float
    point_type: PointType = PointType.CORNER
    # Bezier handles (offset from point)
    handle_in: Optional[Tuple[float, float]] = None   # (dx, dy)
    handle_out: Optional[Tuple[float, float]] = None  # (dx, dy)


@dataclass
class Primitive:
    """A shape primitive (ellipse, rectangle, or polygon)."""
    id: str
    type: PrimitiveType
    bounds: QRectF = field(default_factory=QRectF)  # For ellipse and rectangle
    points: List[ControlPoint] = field(default_factory=list)  # For polygon
    fill_color: QColor = field(default_factory=lambda: QColor(200, 200, 255))
    stroke_color: QColor = field(default_factory=lambda: QColor(0, 0, 0))
    stroke_width: float = 2.0
    rotation: float = 0.0  # Rotation angle in degrees
    group_id: Optional[str] = None  # ID of parent group, if any


@dataclass
class PrimitiveGroup:
    """A group of primitives that can be transformed together."""
    id: str
    member_ids: List[str] = field(default_factory=list)  # IDs of primitives in this group
    rotation: float = 0.0  # Group rotation in degrees


# =============================================================================
# Graphics Items for Interactive Editing
# =============================================================================

class BezierHandleItem(QGraphicsEllipseItem):
    """
    A bezier control handle that can be dragged to adjust curves.
    Connected to a vertex with a control line.

    Does NOT use ItemIsMovable - mouse tracking is handled by the canvas.
    """

    def __init__(self, vertex_handle, is_in_handle: bool, parent_item=None):
        debug_print(f"BezierHandleItem.__init__(is_in_handle={is_in_handle})")
        super().__init__(-4, -4, 8, 8, parent_item)
        self.vertex_handle = vertex_handle
        self.is_in_handle = is_in_handle
        self._updating = False
        self._dragging = False

        # Styling
        self.setBrush(QBrush(QColor(100, 200, 255)))
        self.setPen(QPen(QColor(0, 100, 200), 1))

        # NOT movable - canvas handles mouse tracking
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, False)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)
        self.setCursor(Qt.CursorShape.CrossCursor)

        self.setZValue(105)  # Higher than primitive and other handles

        self.setAcceptedMouseButtons(Qt.MouseButton.LeftButton)

        # Control line connecting to vertex (added to scene separately)
        self.control_line = QGraphicsLineItem()
        self.control_line.setPen(QPen(QColor(100, 200, 255), 1, Qt.PenStyle.DashLine))
        self.control_line.setZValue(99)
        self.control_line.setAcceptedMouseButtons(Qt.MouseButton.NoButton)

    def finalize_init(self):
        """API compatibility - no longer needed."""
        pass

    def mousePressEvent(self, event):
        """Start bezier handle drag - canvas will handle the rest."""
        debug_print(f"BezierHandleItem.mousePressEvent(is_in={self.is_in_handle})")
        self._dragging = True
        if self.vertex_handle and self.vertex_handle.canvas:
            self.vertex_handle.canvas._active_handle = self
        event.accept()

    def mouseReleaseEvent(self, event):
        """End bezier drag."""
        debug_print(f"BezierHandleItem.mouseReleaseEvent(is_in={self.is_in_handle})")
        if self._dragging:
            self._dragging = False
            if self.vertex_handle and self.vertex_handle.canvas:
                self.vertex_handle.canvas._active_handle = None
        event.accept()

    def handle_drag(self, scene_pos: QPointF):
        """Called by canvas with scene coordinates during drag."""
        if not self.vertex_handle:
            return

        # Get vertex scene position
        vertex_scene = self.vertex_handle.scenePos()

        # Calculate offset from vertex in scene coordinates
        scene_offset_x = scene_pos.x() - vertex_scene.x()
        scene_offset_y = scene_pos.y() - vertex_scene.y()

        # Get primitive's rotation to convert scene offset to data offset
        rotation = 0.0
        if self.vertex_handle.parent_item and hasattr(self.vertex_handle.parent_item, 'primitive'):
            rotation = self.vertex_handle.parent_item.primitive.rotation

        # Convert scene offset to data offset by un-rotating
        if rotation != 0:
            angle_rad = math.radians(-rotation)
            cos_a = math.cos(angle_rad)
            sin_a = math.sin(angle_rad)
            data_offset_x = scene_offset_x * cos_a - scene_offset_y * sin_a
            data_offset_y = scene_offset_x * sin_a + scene_offset_y * cos_a
        else:
            data_offset_x = scene_offset_x
            data_offset_y = scene_offset_y

        debug_print(f"BezierHandleItem.handle_drag: scene_offset=({scene_offset_x:.1f}, {scene_offset_y:.1f}), data=({data_offset_x:.1f}, {data_offset_y:.1f})")

        # Update position - data offset IS local position for bezier handles
        self.setPos(data_offset_x, data_offset_y)

        # Update connector line
        self._update_control_line()

        # Notify vertex with data offset
        self.vertex_handle.on_bezier_handle_moved(self.is_in_handle, QPointF(data_offset_x, data_offset_y))

    def _update_control_line(self):
        """Update the line connecting this handle to its vertex (in scene coordinates)."""
        try:
            if not hasattr(self, 'vertex_handle') or self.vertex_handle is None:
                return
            vertex_pos = self.vertex_handle.scenePos()
            handle_pos = self.scenePos()
            self.control_line.setLine(
                vertex_pos.x(), vertex_pos.y(),
                handle_pos.x(), handle_pos.y()
            )
        except (RuntimeError, AttributeError):
            pass


class VertexHandle(QGraphicsEllipseItem):
    """
    A draggable vertex handle for polygon editing.
    Shows bezier handles when selected.

    Does NOT use ItemIsMovable - mouse tracking is handled by the canvas.
    """

    def __init__(self, control_point: ControlPoint, canvas, parent_item=None):
        debug_print(f"VertexHandle.__init__(point_id={control_point.id[:8]}...)")
        super().__init__(-5, -5, 10, 10, parent_item)
        self.control_point = control_point
        self.canvas = canvas
        self.parent_item = parent_item
        self.is_selected = False
        self._dragging = False

        # Recursion guards
        self._updating_handles = False
        self._changing_type = False

        # Bezier handles (created when selected)
        self.handle_in: Optional[BezierHandleItem] = None
        self.handle_out: Optional[BezierHandleItem] = None

        # Styling
        self.setBrush(QBrush(QColor(255, 100, 100)))
        self.setPen(QPen(QColor(200, 0, 0), 2))

        # NOT movable - canvas handles mouse tracking
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, False)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self.setZValue(101)

        debug_print("VertexHandle.__init__ complete")

        # Context menu
        self.setAcceptedMouseButtons(Qt.MouseButton.LeftButton | Qt.MouseButton.RightButton)

    @track_recursion
    def set_selected(self, selected: bool):
        """Set selection state and show/hide bezier handles."""
        debug_print(f"VertexHandle.set_selected({selected}), current={self.is_selected}")
        self.is_selected = selected

        if selected:
            # Highlight
            self.setBrush(QBrush(QColor(255, 200, 0)))
            self.setPen(QPen(QColor(200, 100, 0), 3))

            # Show bezier handles
            self._show_bezier_handles()
        else:
            # Normal appearance
            self.setBrush(QBrush(QColor(255, 100, 100)))
            self.setPen(QPen(QColor(200, 0, 0), 2))

            # Hide bezier handles
            self._hide_bezier_handles()

    @track_recursion
    def _show_bezier_handles(self):
        """Create and show bezier control handles as children of this vertex."""
        debug_print(f"VertexHandle._show_bezier_handles(), point_type={self.control_point.point_type}")

        self._hide_bezier_handles()

        if self.control_point.point_type == PointType.CORNER:
            debug_print("  Point is CORNER, no bezier handles needed")
            return

        try:
            # Create in-handle as child of vertex
            # Position uses data coordinates - Qt applies rotation via transform chain
            if self.control_point.handle_in:
                debug_print(f"  Creating handle_in at offset {self.control_point.handle_in}")
                self.handle_in = BezierHandleItem(self, True, parent_item=self)
                dx, dy = self.control_point.handle_in
                self.handle_in.setPos(dx, dy)
                self.handle_in.finalize_init()
                self.canvas.scene().addItem(self.handle_in.control_line)
                self.handle_in._update_control_line()

            # Create out-handle as child of vertex
            if self.control_point.handle_out:
                debug_print(f"  Creating handle_out at offset {self.control_point.handle_out}")
                self.handle_out = BezierHandleItem(self, False, parent_item=self)
                dx, dy = self.control_point.handle_out
                self.handle_out.setPos(dx, dy)
                self.handle_out.finalize_init()
                self.canvas.scene().addItem(self.handle_out.control_line)
                self.handle_out._update_control_line()
        except Exception as e:
            print(f"Error showing bezier handles: {e}")
            traceback.print_exc()
            self._hide_bezier_handles()

    def _hide_bezier_handles(self):
        """Remove bezier control handles."""
        debug_print("VertexHandle._hide_bezier_handles()")

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

    @track_recursion
    def on_bezier_handle_moved(self, is_in_handle: bool, new_pos: QPointF):
        """Called when a bezier handle is moved.

        new_pos is the offset in data coordinates (already un-rotated).
        """
        debug_print(f"VertexHandle.on_bezier_handle_moved(is_in={is_in_handle})")
        debug_print(f"  new_pos (data coords)=({new_pos.x():.1f}, {new_pos.y():.1f})")
        debug_print(f"  _changing_type={self._changing_type}, _updating_handles={self._updating_handles}")

        if self._changing_type or (hasattr(self, '_updating_handles') and self._updating_handles):
            debug_print("  Skipping - guard flag set")
            return

        self._updating_handles = True

        try:
            dx = new_pos.x()
            dy = new_pos.y()

            if is_in_handle:
                self.control_point.handle_in = (dx, dy)

                # For symmetric handles, mirror the out handle
                if self.control_point.point_type == PointType.SYMMETRIC and self.handle_out:
                    self.control_point.handle_out = (-dx, -dy)
                    self.handle_out._updating = True
                    self.handle_out.setPos(-dx, -dy)
                    self.handle_out._updating = False
                    self.handle_out._update_control_line()
            else:
                self.control_point.handle_out = (dx, dy)

                # For symmetric handles, mirror the in handle
                if self.control_point.point_type == PointType.SYMMETRIC and self.handle_in:
                    self.control_point.handle_in = (-dx, -dy)
                    self.handle_in._updating = True
                    self.handle_in.setPos(-dx, -dy)
                    self.handle_in._updating = False
                    self.handle_in._update_control_line()

            debug_print("  Calling canvas.on_vertex_modified()")
            self.canvas.on_vertex_modified()
        finally:
            self._updating_handles = False

    def _update_position(self, local_pos: QPointF):
        """Update vertex position from local coordinates."""
        # Update visual position
        self.setPos(local_pos)

        # Convert local position to data coordinates
        if self.parent_item:
            center = self.parent_item._center
            data_x = local_pos.x() + center.x()
            data_y = local_pos.y() + center.y()
        else:
            data_x = local_pos.x()
            data_y = local_pos.y()

        # Update control point with data coordinates
        self.control_point.x = data_x
        self.control_point.y = data_y
        debug_print(f"  Updated control_point to data ({data_x:.1f}, {data_y:.1f})")

        # Update bezier connector lines
        if self.handle_in:
            self.handle_in._update_control_line()
        if self.handle_out:
            self.handle_out._update_control_line()

        # Notify canvas
        self.canvas.on_vertex_modified()

    @track_recursion
    def mousePressEvent(self, event):
        """Handle mouse press for selection and drag start."""
        debug_print(f"VertexHandle.mousePressEvent()")

        if self._changing_type:
            debug_print("  Ignoring - changing type")
            event.ignore()
            return

        if event.button() == Qt.MouseButton.LeftButton:
            debug_print(f"  Calling canvas.select_vertex({self.control_point.id[:8]}...)")
            self.canvas.select_vertex(self.control_point.id)
            self._dragging = True
            if self.canvas:
                self.canvas._active_handle = self
            event.accept()
        elif event.button() == Qt.MouseButton.RightButton:
            # Let context menu handle it
            event.ignore()

    def mouseReleaseEvent(self, event):
        """End vertex drag and recenter the item."""
        debug_print(f"VertexHandle.mouseReleaseEvent()")
        if self._dragging:
            self._dragging = False
            if self.canvas:
                self.canvas._active_handle = None
                self.canvas._recenter_selected_primitive()
        event.accept()

    def handle_drag(self, scene_pos: QPointF):
        """Called by canvas with scene coordinates during drag."""
        if not self.parent_item:
            return

        # Convert scene position to data coordinates
        item_pos = self.parent_item.pos()
        rotation = self.parent_item.primitive.rotation
        center = self.parent_item._center

        # Offset from item position in scene
        scene_offset = scene_pos - item_pos

        # Un-rotate to get local/data offset
        if rotation != 0:
            angle_rad = math.radians(-rotation)
            cos_a = math.cos(angle_rad)
            sin_a = math.sin(angle_rad)
            local_x = scene_offset.x() * cos_a - scene_offset.y() * sin_a
            local_y = scene_offset.x() * sin_a + scene_offset.y() * cos_a
        else:
            local_x = scene_offset.x()
            local_y = scene_offset.y()

        # Convert to absolute data coordinates
        data_x = local_x + center.x()
        data_y = local_y + center.y()

        debug_print(f"VertexHandle.handle_drag: scene=({scene_pos.x():.1f}, {scene_pos.y():.1f}), data=({data_x:.1f}, {data_y:.1f})")

        # Update control point
        self.control_point.x = data_x
        self.control_point.y = data_y

        # Update visual position
        self.setPos(local_x, local_y)

        # Update bezier connector lines
        if self.handle_in:
            self.handle_in._update_control_line()
        if self.handle_out:
            self.handle_out._update_control_line()

        # Notify canvas (rebuilds path without recentering)
        self.canvas.on_vertex_modified()

    def contextMenuEvent(self, event):
        """Show context menu for vertex operations."""
        menu = QMenu()

        # Point type submenu
        type_menu = menu.addMenu("Point Type")

        corner_action = type_menu.addAction("Corner")
        corner_action.setCheckable(True)
        corner_action.setChecked(self.control_point.point_type == PointType.CORNER)

        smooth_action = type_menu.addAction("Smooth")
        smooth_action.setCheckable(True)
        smooth_action.setChecked(self.control_point.point_type == PointType.SMOOTH)

        symmetric_action = type_menu.addAction("Symmetric")
        symmetric_action.setCheckable(True)
        symmetric_action.setChecked(self.control_point.point_type == PointType.SYMMETRIC)

        menu.addSeparator()
        delete_action = menu.addAction("Delete Vertex")

        # Execute menu
        action = menu.exec(event.screenPos())

        if action == corner_action:
            self._change_type(PointType.CORNER)
        elif action == smooth_action:
            self._change_type(PointType.SMOOTH)
        elif action == symmetric_action:
            self._change_type(PointType.SYMMETRIC)
        elif action == delete_action:
            self.canvas.delete_vertex(self.control_point.id)

    @track_recursion
    def _change_type(self, new_type: PointType):
        """Change the vertex type."""
        debug_print(f"VertexHandle._change_type({new_type})")

        # Set flag to prevent operations during type change
        self._changing_type = True

        try:
            old_type = self.control_point.point_type
            self.control_point.point_type = new_type
            debug_print(f"  Changed from {old_type} to {new_type}")

            # Initialize bezier handles if changing to smooth/symmetric
            if old_type == PointType.CORNER and new_type in [PointType.SMOOTH, PointType.SYMMETRIC]:
                # Create default handles
                self.control_point.handle_in = (-30, 0)
                self.control_point.handle_out = (30, 0)

            # Clear handles if changing to corner
            if new_type == PointType.CORNER:
                self.control_point.handle_in = None
                self.control_point.handle_out = None

            # Refresh display - always hide first
            self._hide_bezier_handles()

            # Only show if still selected
            if self.is_selected:
                self._show_bezier_handles()

            self.canvas.on_vertex_modified()
        finally:
            self._changing_type = False


class SelectablePrimitiveItem(QGraphicsPathItem):
    """A primitive shape that can be selected and edited on the canvas."""

    def __init__(self, primitive: Primitive, canvas=None, parent=None):
        debug_print(f"SelectablePrimitiveItem.__init__(type={primitive.type})")
        super().__init__(parent)
        self.primitive = primitive
        self.canvas = canvas
        self.is_selected = False
        self._updating = False  # Guard against recursion

        # Calculate the center for this primitive
        self._center = self._calculate_center()

        # Position item at center - path will be in local coords relative to this
        self.setPos(self._center)
        self._last_pos = QPointF(self._center)

        # Create the path in local coordinates
        self._create_path()

        # Set appearance
        self.setPen(QPen(primitive.stroke_color, primitive.stroke_width))
        self.setBrush(QBrush(primitive.fill_color))

        # Make selectable
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges)

        # Transform origin at local (0,0) which is the center
        self.setTransformOriginPoint(0, 0)

        # Apply existing rotation
        if primitive.rotation != 0:
            self.setRotation(primitive.rotation)

    def _calculate_center(self) -> QPointF:
        """Calculate the center point of the primitive in scene coordinates."""
        if self.primitive.type == PrimitiveType.POLYGON:
            if self.primitive.points:
                cx = sum(p.x for p in self.primitive.points) / len(self.primitive.points)
                cy = sum(p.y for p in self.primitive.points) / len(self.primitive.points)
                return QPointF(cx, cy)
            return QPointF(300, 300)  # Default center
        else:
            return self.primitive.bounds.center()

    def _create_path(self):
        """Create the QPainterPath in local coordinates (relative to center)."""
        path = QPainterPath()
        center = self._center

        if self.primitive.type == PrimitiveType.ELLIPSE:
            bounds = self.primitive.bounds
            local_bounds = QRectF(
                bounds.left() - center.x(),
                bounds.top() - center.y(),
                bounds.width(),
                bounds.height()
            )
            path.addEllipse(local_bounds)

        elif self.primitive.type == PrimitiveType.RECTANGLE:
            bounds = self.primitive.bounds
            local_bounds = QRectF(
                bounds.left() - center.x(),
                bounds.top() - center.y(),
                bounds.width(),
                bounds.height()
            )
            path.addRect(local_bounds)

        elif self.primitive.type == PrimitiveType.POLYGON:
            if self.primitive.points:
                self._create_polygon_path(path, center)

        self.setPath(path)

    def _create_polygon_path(self, path: QPainterPath, center: QPointF):
        """Create a polygon path with bezier curves in local coordinates."""
        if not self.primitive.points:
            return

        points = self.primitive.points
        n = len(points)

        # Start at first point (local coordinates)
        path.moveTo(points[0].x - center.x(), points[0].y - center.y())

        for i in range(n):
            current = points[i]
            next_point = points[(i + 1) % n]

            if current.handle_out or next_point.handle_in:
                # Cubic bezier
                start = QPointF(current.x - center.x(), current.y - center.y())
                end = QPointF(next_point.x - center.x(), next_point.y - center.y())

                if current.handle_out:
                    dx, dy = current.handle_out
                    ctrl1 = QPointF(current.x + dx - center.x(), current.y + dy - center.y())
                else:
                    ctrl1 = start

                if next_point.handle_in:
                    dx, dy = next_point.handle_in
                    ctrl2 = QPointF(next_point.x + dx - center.x(), next_point.y + dy - center.y())
                else:
                    ctrl2 = end

                path.cubicTo(ctrl1, ctrl2, end)
            else:
                path.lineTo(next_point.x - center.x(), next_point.y - center.y())

        path.closeSubpath()

    def scene_to_local(self, scene_point: QPointF) -> QPointF:
        """Convert scene coordinates to local coordinates (handles rotation)."""
        return self.mapFromScene(scene_point)

    def local_to_scene(self, local_point: QPointF) -> QPointF:
        """Convert local coordinates to scene coordinates (handles rotation)."""
        return self.mapToScene(local_point)

    def data_to_local(self, data_point: QPointF) -> QPointF:
        """Convert data coordinates (absolute) to local coordinates."""
        return QPointF(data_point.x() - self._center.x(), data_point.y() - self._center.y())

    def local_to_data(self, local_point: QPointF) -> QPointF:
        """Convert local coordinates to data coordinates (absolute)."""
        return QPointF(local_point.x() + self._center.x(), local_point.y() + self._center.y())

    @track_recursion
    def set_selected(self, selected: bool):
        """Set selection state with visual feedback."""
        debug_print(f"SelectablePrimitiveItem.set_selected({selected})")
        self.is_selected = selected

        if selected:
            pen = QPen(QColor(255, 100, 0), self.primitive.stroke_width + 2)
            pen.setStyle(Qt.PenStyle.DashLine)
            self.setPen(pen)
        else:
            self.setPen(QPen(self.primitive.stroke_color, self.primitive.stroke_width))

    @track_recursion
    def itemChange(self, change, value):
        """Handle position changes."""
        # Grid snapping - modify position before it's applied
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
                self._last_pos = QPointF(value)

                if delta.x() != 0 or delta.y() != 0:
                    debug_print(f"SelectablePrimitiveItem.itemChange: delta=({delta.x():.1f}, {delta.y():.1f})")
                    # Child handles move automatically with parent
                    # But connector lines are separate scene items, so update them
                    if self.canvas:
                        # Update rotation handle connector line
                        if self.canvas.rotate_handle:
                            self.canvas.rotate_handle._update_connector_line()
                        # Update bezier connector lines
                        for handle in self.canvas.vertex_handles.values():
                            if handle.handle_in:
                                handle.handle_in._update_control_line()
                            if handle.handle_out:
                                handle.handle_out._update_control_line()
            finally:
                self._updating = False

        return super().itemChange(change, value)

    @track_recursion
    def commit_position(self):
        """Commit the current position to underlying data."""
        current_pos = self.pos()
        expected_center = self._calculate_center()
        delta = current_pos - expected_center

        if abs(delta.x()) < 0.01 and abs(delta.y()) < 0.01:
            return

        debug_print(f"SelectablePrimitiveItem.commit_position(): delta=({delta.x():.1f}, {delta.y():.1f})")

        self._updating = True
        try:
            if self.primitive.type == PrimitiveType.POLYGON:
                for point in self.primitive.points:
                    point.x += delta.x()
                    point.y += delta.y()
            elif self.primitive.type in [PrimitiveType.ELLIPSE, PrimitiveType.RECTANGLE]:
                self.primitive.bounds.translate(delta)

            # Recalculate center and update
            self._center = self._calculate_center()
            self._last_pos = QPointF(self._center)
            self.setPos(self._center)
            self._create_path()
            debug_print("  Position committed")
        finally:
            self._updating = False

    def rebuild(self):
        """Rebuild the path after changes, preserving visual offset."""
        old_center = self._center
        visual_offset = self.pos() - old_center  # How far we've been dragged

        self._center = self._calculate_center()

        # Preserve the visual offset (don't snap back to data position)
        new_pos = self._center + visual_offset
        self._last_pos = QPointF(new_pos)
        self.setPos(new_pos)

        self._create_path()


class ResizeHandle(QGraphicsEllipseItem):
    """A handle for resizing primitives (ellipse/rectangle only).

    Does NOT use ItemIsMovable - mouse tracking is handled by the canvas.
    """

    def __init__(self, primitive_item: SelectablePrimitiveItem, position: str, canvas=None, parent_item=None):
        super().__init__(-5, -5, 10, 10, parent_item)
        self.parent_item = primitive_item
        self.position = position
        self.canvas = canvas
        self._dragging = False

        self.setBrush(QBrush(QColor(255, 255, 255)))
        self.setPen(QPen(QColor(0, 0, 255), 2))

        # NOT movable - canvas handles mouse tracking
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, False)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)
        self.setCursor(Qt.CursorShape.SizeFDiagCursor)
        self.setZValue(100)

        self.setAcceptedMouseButtons(Qt.MouseButton.LeftButton)

    def finalize_init(self):
        """API compatibility - no longer needed."""
        pass

    def mousePressEvent(self, event):
        """Start resize tracking - canvas will handle the rest."""
        debug_print(f"ResizeHandle.mousePressEvent({self.position})")
        self._dragging = True
        if self.canvas:
            self.canvas._active_handle = self
        event.accept()

    def mouseReleaseEvent(self, event):
        """End resize tracking."""
        debug_print(f"ResizeHandle.mouseReleaseEvent({self.position})")
        if self._dragging:
            self._dragging = False
            if self.canvas:
                self.canvas._active_handle = None
                self.canvas._recenter_selected_primitive()
        event.accept()

    def handle_drag(self, scene_pos: QPointF):
        """Called by canvas with scene coordinates during drag."""
        # Convert scene position to data coordinates
        item_pos = self.parent_item.pos()
        rotation = self.parent_item.primitive.rotation
        center = self.parent_item._center

        # Offset from item position in scene
        scene_offset = scene_pos - item_pos

        # Un-rotate to get local/data offset
        if rotation != 0:
            angle_rad = math.radians(-rotation)
            cos_a = math.cos(angle_rad)
            sin_a = math.sin(angle_rad)
            data_offset_x = scene_offset.x() * cos_a - scene_offset.y() * sin_a
            data_offset_y = scene_offset.x() * sin_a + scene_offset.y() * cos_a
        else:
            data_offset_x = scene_offset.x()
            data_offset_y = scene_offset.y()

        # Convert to absolute data coordinates
        data_x = data_offset_x + center.x()
        data_y = data_offset_y + center.y()

        debug_print(f"ResizeHandle.handle_drag({self.position}): scene=({scene_pos.x():.1f}, {scene_pos.y():.1f}), data=({data_x:.1f}, {data_y:.1f})")

        # Update bounds based on which edge we're dragging
        bounds = self.parent_item.primitive.bounds

        if 'n' in self.position:
            bounds.setTop(data_y)
        if 's' in self.position:
            bounds.setBottom(data_y)
        if 'w' in self.position:
            bounds.setLeft(data_x)
        if 'e' in self.position:
            bounds.setRight(data_x)

        # Rebuild path only (don't recenter during drag)
        self.parent_item._create_path()

        # Update all resize handles
        if self.canvas:
            self.canvas.update_resize_handle_positions_from_bounds()
            if self.canvas.rotate_handle:
                self.canvas.rotate_handle._update_connector_line()


class RotateHandle(QGraphicsEllipseItem):
    """A handle for rotating primitives.

    Does NOT use ItemIsMovable - mouse tracking is handled by the canvas.
    """

    def __init__(self, parent_item: SelectablePrimitiveItem, canvas=None, parent_item_gfx=None):
        super().__init__(-6, -6, 12, 12, parent_item_gfx)
        self.parent_item = parent_item
        self.canvas = canvas
        self._rotating = False
        self._handle_distance = 70.0  # Distance from center
        self._start_angle = 0.0  # Starting angle for delta rotation
        self._start_rotation = 0.0  # Starting rotation for delta rotation

        # Distinct styling - green for rotation
        self.setBrush(QBrush(QColor(100, 255, 100)))
        self.setPen(QPen(QColor(0, 150, 0), 2))

        # NOT movable - canvas handles mouse tracking
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, False)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setZValue(103)

        self.setAcceptedMouseButtons(Qt.MouseButton.LeftButton)

        # Line connecting to center (added to scene separately)
        self.connector_line = QGraphicsLineItem()
        self.connector_line.setPen(QPen(QColor(100, 255, 100), 1, Qt.PenStyle.DashLine))
        self.connector_line.setZValue(98)
        self.connector_line.setAcceptedMouseButtons(Qt.MouseButton.NoButton)

    def finalize_init(self):
        """Call after initial positioning to record handle distance."""
        pos = self.pos()
        self._handle_distance = math.sqrt(pos.x()**2 + pos.y()**2)
        if self._handle_distance < 20:
            self._handle_distance = 70.0

    def _update_connector_line(self):
        """Update the line connecting the handle to the center."""
        center_scene = self.parent_item.pos()
        handle_scene = self.scenePos()
        self.connector_line.setLine(center_scene.x(), center_scene.y(),
                                     handle_scene.x(), handle_scene.y())

    def mousePressEvent(self, event):
        """Start rotation tracking - canvas will handle the rest."""
        debug_print(f"RotateHandle.mousePressEvent()")
        self._rotating = True

        # Record starting state for delta-based rotation
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
        """End rotation tracking."""
        debug_print(f"RotateHandle.mouseReleaseEvent()")
        if self._rotating:
            self._rotating = False
            if self.canvas:
                self.canvas._active_handle = None
        event.accept()

    def handle_drag(self, scene_pos: QPointF):
        """Called by canvas with scene coordinates during drag."""
        # Get center in scene coordinates
        center_scene = self.parent_item.pos()

        # Calculate current angle from center to mouse in scene coordinates
        dx = scene_pos.x() - center_scene.x()
        dy = scene_pos.y() - center_scene.y()
        current_angle = math.degrees(math.atan2(dy, dx))

        # Calculate delta from starting angle
        delta_angle = current_angle - self._start_angle

        # Apply delta to starting rotation
        new_rotation = self._start_rotation + delta_angle

        # Check for Ctrl key to snap to angle increments
        modifiers = QApplication.keyboardModifiers()
        if modifiers & Qt.KeyboardModifier.ControlModifier and self.canvas:
            snap_angle = self.canvas.rotation_snap_angle
            new_rotation = round(new_rotation / snap_angle) * snap_angle
            debug_print(f"RotateHandle.handle_drag: SNAP to {new_rotation:.1f}°")
        else:
            debug_print(f"RotateHandle.handle_drag: current={current_angle:.1f}, delta={delta_angle:.1f}, rotation={new_rotation:.1f}")

        # Apply rotation to primitive
        self.parent_item.primitive.rotation = new_rotation
        self.parent_item.setRotation(new_rotation)

        # The handle is a CHILD of the rotated primitive.
        # Its local position should always be at "top" (0, -distance).
        # The parent's rotation transform will place it at the correct scene position.
        self.setPos(0, -self._handle_distance)

        # Update connector line
        self._update_connector_line()

        # Notify canvas
        if self.canvas:
            self.canvas.on_rotation_modified()


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
        # Store initial state for proportional scaling
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
            if prim.type == PrimitiveType.POLYGON:
                state['points'] = [(p.x, p.y, p.handle_in, p.handle_out) for p in prim.points]
            else:
                state['bounds'] = QRectF(prim.bounds)
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

        # Calculate half-widths/heights from local bounds
        old_half_w = local_bounds.width() / 2
        old_half_h = local_bounds.height() / 2

        # Get offset from group center in scene coords
        scene_offset_x = scene_pos.x() - group_center.x()
        scene_offset_y = scene_pos.y() - group_center.y()

        # Un-rotate to get local offset (if group is rotated)
        if rotation != 0:
            angle_rad = math.radians(-rotation)
            cos_a = math.cos(angle_rad)
            sin_a = math.sin(angle_rad)
            local_offset_x = scene_offset_x * cos_a - scene_offset_y * sin_a
            local_offset_y = scene_offset_x * sin_a + scene_offset_y * cos_a
        else:
            local_offset_x = scene_offset_x
            local_offset_y = scene_offset_y

        # Calculate scale based on distance from center in local coords
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

        # Clamp to reasonable bounds
        scale_x = max(0.1, min(10.0, scale_x))
        scale_y = max(0.1, min(10.0, scale_y))

        # Apply scaling from original states (pass rotation for correct coordinate transforms)
        self.group_item.scale_members_from_states(
            scale_x, scale_y, group_center, self._start_member_states,
            self._start_local_bounds, self._start_rotation
        )


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

        # Connector line
        self.connector_line = QGraphicsLineItem()
        self.connector_line.setPen(QPen(QColor(100, 255, 100), 1, Qt.PenStyle.DashLine))
        self.connector_line.setZValue(198)
        self.connector_line.setAcceptedMouseButtons(Qt.MouseButton.NoButton)

    def _update_connector_line(self):
        """Update connector line in local coordinates (from center to handle)."""
        # Both connector and handle are children of the group, so use local coords
        # Center is at (0, 0) in local coords
        handle_pos = self.pos()
        self.connector_line.setLine(0, 0, handle_pos.x(), handle_pos.y())

    def mousePressEvent(self, event):
        debug_print("GroupRotateHandle.mousePressEvent()")
        self._rotating = True
        # Get angle from group center to mouse in scene coords
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

        # Check for Ctrl key to snap to angle increments
        modifiers = QApplication.keyboardModifiers()
        if modifiers & Qt.KeyboardModifier.ControlModifier and self.canvas:
            snap_angle = self.canvas.rotation_snap_angle
            # Calculate what the total rotation would be
            total_rotation = self._start_rotation + delta_angle
            # Snap the total rotation
            snapped_rotation = round(total_rotation / snap_angle) * snap_angle
            # Calculate the actual delta needed
            delta_angle = snapped_rotation - self.group_item.group.rotation
            debug_print(f"GroupRotateHandle.handle_drag: SNAP to {snapped_rotation:.1f}°")
        else:
            debug_print(f"GroupRotateHandle.handle_drag: delta={delta_angle:.1f}")

        # Apply rotation to group (this rotates the GroupItem and its children)
        if abs(delta_angle) > 0.001:
            self.group_item.rotate_members(delta_angle)
        self._start_angle = current_angle
        self._start_rotation = self.group_item.group.rotation

        # Handle position stays fixed in local coords - the group's rotation transform
        # handles the visual rotation. Just update connector line.
        self._update_connector_line()


class GroupItem(QGraphicsPathItem):
    """
    Visual representation of a group of primitives.
    Shows a bounding rectangle and provides resize/rotate handles.
    The bounding box rotates with the group.
    """

    def __init__(self, group: PrimitiveGroup, canvas=None):
        super().__init__()
        self.group = group
        self.canvas = canvas
        self.member_items: List[SelectablePrimitiveItem] = []
        self.group_bounds = QRectF()  # Bounds in scene coords (before group rotation)
        self._local_bounds = QRectF()  # Bounds relative to group center

        # Store member offsets relative to group center (in group's local coords)
        self._member_offsets: List[QPointF] = []

        # Handles
        self.resize_handles: List[GroupResizeHandle] = []
        self.rotate_handle: Optional[GroupRotateHandle] = None

        # Styling - dashed border
        self.setPen(QPen(QColor(100, 100, 255), 2, Qt.PenStyle.DashLine))
        self.setBrush(QBrush(Qt.BrushStyle.NoBrush))

        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setZValue(50)

        # Set transform origin to center (0,0 in local coords)
        self.setTransformOriginPoint(0, 0)

        self._updating = False
        self._last_pos = QPointF()

    def set_members(self, items: List[SelectablePrimitiveItem]):
        """Set the member items and calculate bounds."""
        self.member_items = items
        self._calculate_initial_bounds()
        self._create_path()
        self._last_pos = self.pos()

        # Apply any existing group rotation
        if self.group.rotation != 0:
            self.setRotation(self.group.rotation)

    def _calculate_initial_bounds(self):
        """Calculate the initial bounding rectangle and member offsets."""
        if not self.member_items:
            self.group_bounds = QRectF()
            self._local_bounds = QRectF()
            return

        # Get union of all member bounding rects in scene coordinates
        first = True
        for item in self.member_items:
            item_bounds = item.sceneBoundingRect()
            if first:
                self.group_bounds = QRectF(item_bounds)
                first = False
            else:
                self.group_bounds = self.group_bounds.united(item_bounds)

        # Position at center
        center = self.group_bounds.center()
        self._updating = True
        self.setPos(center)
        self._last_pos = center
        self._updating = False

        # Calculate local bounds (relative to center)
        self._local_bounds = QRectF(
            self.group_bounds.left() - center.x(),
            self.group_bounds.top() - center.y(),
            self.group_bounds.width(),
            self.group_bounds.height()
        )

        # Store member offsets relative to group center
        self._member_offsets = []
        for item in self.member_items:
            offset = item.pos() - center
            self._member_offsets.append(offset)

    def _create_path(self):
        """Create the selection rectangle path in local coordinates."""
        path = QPainterPath()
        if not self._local_bounds.isEmpty():
            # Add some padding
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

        # Resize handles at corners (in local coordinates)
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

        # Rotate handle above the group (also as child so it rotates with group)
        self.rotate_handle = GroupRotateHandle(self, self.canvas)
        handle_distance = (bounds.height() / 2) + 30
        self.rotate_handle._handle_distance = handle_distance
        self.rotate_handle.setParentItem(self)
        self.rotate_handle.setPos(0, bounds.top() - 35)  # Above the top edge
        # Connector line is also a child
        self.rotate_handle.connector_line.setParentItem(self)
        self.rotate_handle._update_connector_line()

    def clear_handles(self, scene: QGraphicsScene):
        """Remove all handles (they are children of the group)."""
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
            # Grid snapping
            modifiers = QApplication.keyboardModifiers()
            if modifiers & Qt.KeyboardModifier.ControlModifier and self.canvas:
                snap_size = self.canvas.grid_snap_size
                snapped_x = round(value.x() / snap_size) * snap_size
                snapped_y = round(value.y() / snap_size) * snap_size
                value = QPointF(snapped_x, snapped_y)

            self._updating = True
            try:
                # Calculate movement delta
                delta = value - self._last_pos

                # Move all member items
                for item in self.member_items:
                    old_pos = item.pos()
                    item.setPos(old_pos + delta)
                    item._last_pos = item.pos()

                self._last_pos = value

                # Update group bounds to reflect new positions
                self.group_bounds.translate(delta.x(), delta.y())

                # Handles are children, they move automatically
            finally:
                self._updating = False

            return value

        return super().itemChange(change, value)

    def scale_members(self, scale_x: float, scale_y: float, center: QPointF):
        """Scale all member items around the group center.

        WARNING: This compounds scaling on each call. For drag operations,
        use scale_members_from_states instead.
        """
        if abs(scale_x) < 0.1 or abs(scale_y) < 0.1:
            return  # Prevent too small

        rotation = self.group.rotation

        # Precompute rotation transforms if needed
        if rotation != 0:
            angle_rad = math.radians(-rotation)
            cos_unrot = math.cos(angle_rad)
            sin_unrot = math.sin(angle_rad)
            angle_rad = math.radians(rotation)
            cos_rot = math.cos(angle_rad)
            sin_rot = math.sin(angle_rad)

        for item in self.member_items:
            primitive = item.primitive
            old_pos = item.pos()

            # Get offset from group center in scene coords
            scene_dx = old_pos.x() - center.x()
            scene_dy = old_pos.y() - center.y()

            if rotation != 0:
                # Un-rotate to get local offset
                local_dx = scene_dx * cos_unrot - scene_dy * sin_unrot
                local_dy = scene_dx * sin_unrot + scene_dy * cos_unrot

                # Scale in local coordinates
                scaled_local_dx = local_dx * scale_x
                scaled_local_dy = local_dy * scale_y

                # Re-rotate back to scene coordinates
                new_dx = scaled_local_dx * cos_rot - scaled_local_dy * sin_rot
                new_dy = scaled_local_dx * sin_rot + scaled_local_dy * cos_rot
            else:
                new_dx = scene_dx * scale_x
                new_dy = scene_dy * scale_y

            new_pos = QPointF(center.x() + new_dx, center.y() + new_dy)

            # Scale the primitive itself
            # The data coordinates must be updated so that _center matches new_pos
            if primitive.type == PrimitiveType.POLYGON:
                item_center = item._center
                # First scale points around current center, then translate to new_pos
                for point in primitive.points:
                    px = point.x - item_center.x()
                    py = point.y - item_center.y()
                    scaled_x = item_center.x() + px * scale_x
                    scaled_y = item_center.y() + py * scale_y
                    # Translate to new position
                    point.x = scaled_x + (new_pos.x() - item_center.x())
                    point.y = scaled_y + (new_pos.y() - item_center.y())
                    # Scale bezier handles too
                    if point.handle_in:
                        hx, hy = point.handle_in
                        point.handle_in = (hx * scale_x, hy * scale_y)
                    if point.handle_out:
                        hx, hy = point.handle_out
                        point.handle_out = (hx * scale_x, hy * scale_y)
            else:
                # Ellipse/Rectangle: set bounds centered at new_pos with scaled size
                bounds = primitive.bounds
                new_w = bounds.width() * scale_x
                new_h = bounds.height() * scale_y
                primitive.bounds = QRectF(
                    new_pos.x() - new_w / 2,
                    new_pos.y() - new_h / 2,
                    new_w,
                    new_h
                )

            # Update item
            item._center = item._calculate_center()
            item.setPos(new_pos)
            item._last_pos = new_pos
            item._create_path()

        # Scale local bounds
        self._local_bounds = QRectF(
            self._local_bounds.left() * scale_x,
            self._local_bounds.top() * scale_y,
            self._local_bounds.width() * scale_x,
            self._local_bounds.height() * scale_y
        )
        self._create_path()

        # Update handle positions
        self._update_handle_positions()

    def scale_members_from_states(self, scale_x: float, scale_y: float, center: QPointF, start_states: list, start_local_bounds: QRectF = None, rotation: float = 0.0):
        """Scale all member items from their original states.

        This prevents compounding scale on each mouse move.
        When the group is rotated, scaling happens in the group's local coordinate system.
        """
        if abs(scale_x) < 0.1 or abs(scale_y) < 0.1:
            return

        # Precompute rotation transforms
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

            # Get offset from group center in scene coords
            scene_dx = orig_pos.x() - center.x()
            scene_dy = orig_pos.y() - center.y()

            if rotation != 0:
                # Un-rotate to get local offset
                local_dx = scene_dx * cos_unrot - scene_dy * sin_unrot
                local_dy = scene_dx * sin_unrot + scene_dy * cos_unrot

                # Scale in local coordinates
                scaled_local_dx = local_dx * scale_x
                scaled_local_dy = local_dy * scale_y

                # Re-rotate back to scene coordinates
                new_dx = scaled_local_dx * cos_rot - scaled_local_dy * sin_rot
                new_dy = scaled_local_dx * sin_rot + scaled_local_dy * cos_rot
            else:
                # No rotation - scale directly
                new_dx = scene_dx * scale_x
                new_dy = scene_dy * scale_y

            new_pos = QPointF(center.x() + new_dx, center.y() + new_dy)

            # Scale the primitive itself from original state
            # The data coordinates must be updated so that _center matches new_pos
            if primitive.type == PrimitiveType.POLYGON:
                orig_item_center = state['center']
                orig_points = state['points']

                # First scale points around original center
                # Then translate so the new center matches new_pos
                for j, point in enumerate(primitive.points):
                    if j < len(orig_points):
                        orig_x, orig_y, orig_h_in, orig_h_out = orig_points[j]
                        # Scale around original center
                        px = orig_x - orig_item_center.x()
                        py = orig_y - orig_item_center.y()
                        scaled_x = orig_item_center.x() + px * scale_x
                        scaled_y = orig_item_center.y() + py * scale_y
                        # Translate to new position
                        point.x = scaled_x + (new_pos.x() - orig_item_center.x())
                        point.y = scaled_y + (new_pos.y() - orig_item_center.y())
                        # Scale bezier handles from original
                        if orig_h_in:
                            point.handle_in = (orig_h_in[0] * scale_x, orig_h_in[1] * scale_y)
                        if orig_h_out:
                            point.handle_out = (orig_h_out[0] * scale_x, orig_h_out[1] * scale_y)
            else:
                # Ellipse/Rectangle: set bounds centered at new_pos with scaled size
                orig_bounds = state['bounds']
                new_w = orig_bounds.width() * scale_x
                new_h = orig_bounds.height() * scale_y
                # Center the bounds at new_pos
                primitive.bounds = QRectF(
                    new_pos.x() - new_w / 2,
                    new_pos.y() - new_h / 2,
                    new_w,
                    new_h
                )

            # Update item
            item._center = item._calculate_center()
            item.setPos(new_pos)
            item._last_pos = new_pos
            item._create_path()

        # Scale local bounds from starting bounds (prevents compounding)
        if start_local_bounds:
            self._local_bounds = QRectF(
                start_local_bounds.left() * scale_x,
                start_local_bounds.top() * scale_y,
                start_local_bounds.width() * scale_x,
                start_local_bounds.height() * scale_y
            )
        self._create_path()

        # Update handle positions
        self._update_handle_positions()

    def rotate_members(self, delta_angle: float):
        """Rotate all member items around the group center.

        The GroupItem itself rotates to show rotated bounding box.
        Member items also rotate around the group center.
        """
        center = self.pos()
        angle_rad = math.radians(delta_angle)
        cos_a = math.cos(angle_rad)
        sin_a = math.sin(angle_rad)

        for item in self.member_items:
            # Rotate position around group center
            old_pos = item.pos()
            dx = old_pos.x() - center.x()
            dy = old_pos.y() - center.y()
            new_x = center.x() + dx * cos_a - dy * sin_a
            new_y = center.y() + dx * sin_a + dy * cos_a
            item.setPos(new_x, new_y)
            item._last_pos = item.pos()

            # Add rotation to primitive
            item.primitive.rotation += delta_angle
            item.setRotation(item.primitive.rotation)

        # Update group rotation and apply to GroupItem
        self.group.rotation += delta_angle
        self.setRotation(self.group.rotation)

        # Local bounds stay fixed - the rotation transform handles the visual

    def _update_handle_positions(self):
        """Update handle positions after bounds change (in local coordinates)."""
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
                # Rotate handle is a child, position in local coords
                self.rotate_handle.setPos(0, bounds.top() - 35)
                self.rotate_handle._update_connector_line()


# =============================================================================
# Enhanced Canvas
# =============================================================================

class EnhancedShapeEditorCanvas(QGraphicsView):
    """
    Enhanced canvas with polygon point editing and bezier curve support.

    Signals:
        primitive_selected: Emitted when a primitive is selected
        primitive_modified: Emitted when a primitive is modified
        vertex_selected: Emitted when a vertex is selected
        shape_modified: Emitted when the overall shape changes
    """

    # Define signals at class level
    primitive_selected = pyqtSignal(str)
    primitive_modified = pyqtSignal()
    vertex_selected = pyqtSignal(str)
    shape_modified = pyqtSignal()

    def __init__(self, parent=None):
        debug_print("EnhancedShapeEditorCanvas.__init__()")
        super().__init__(parent)

        # Verify signals are properly initialized
        if not hasattr(self, 'primitive_selected'):
            raise RuntimeError("Signals not properly initialized - check class definition")

        self.canvas_size = 600
        self.grid_size = 20
        self.grid_snap = True
        self.show_grid = True

        # Storage
        self.primitives: Dict[str, Primitive] = {}
        self.primitive_items: Dict[str, SelectablePrimitiveItem] = {}
        self.vertex_handles: Dict[str, VertexHandle] = {}
        self.resize_handles: List[ResizeHandle] = []
        self.rotate_handle: Optional[RotateHandle] = None

        # Groups
        self.groups: Dict[str, PrimitiveGroup] = {}
        self.group_items: Dict[str, GroupItem] = {}
        self.selected_group_id: Optional[str] = None

        self.selected_primitive_id: Optional[str] = None
        self.selected_primitive_ids: List[str] = []  # For multi-selection (ordered)
        self.selected_vertex_id: Optional[str] = None

        # Active handle being dragged (for canvas-level mouse tracking)
        self._active_handle = None

        # Rubberband selection state
        self._rubberband_active = False
        self._rubberband_origin = QPoint()

        # Snap settings (Ctrl+drag to snap)
        self.grid_snap_size = 20.0  # Snap to grid units when Ctrl+dragging
        self.rotation_snap_angle = 10.0  # Snap to angle increments when Ctrl+rotating

        # Initialize scene and view
        self._setup_scene()
        self._setup_view()
        debug_print("EnhancedShapeEditorCanvas.__init__ complete")

    def _emit_safe(self, signal, *args):
        """Safely emit a signal with error handling."""
        try:
            debug_print(f"_emit_safe: Emitting signal with args {args}")
            signal.emit(*args)
            debug_print(f"_emit_safe: Signal emitted successfully")
        except Exception as e:
            print(f"Signal emission error: {e}")
            traceback.print_exc()

    def _setup_scene(self):
        """Initialize the graphics scene."""
        debug_print("EnhancedShapeEditorCanvas._setup_scene()")
        # Use _scene to avoid shadowing the inherited scene() method from QGraphicsView
        self._scene = QGraphicsScene(self)
        self._scene.setSceneRect(0, 0, self.canvas_size, self.canvas_size)
        self.setScene(self._scene)
        self._draw_grid()

    def _setup_view(self):
        """Configure the view."""
        debug_print("EnhancedShapeEditorCanvas._setup_view()")
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setFixedSize(self.canvas_size + 4, self.canvas_size + 4)
        self.centerOn(self.canvas_size / 2, self.canvas_size / 2)

    def _draw_grid(self):
        """Draw the background grid."""
        if not self.show_grid:
            return

        pen = QPen(QColor(220, 220, 220), 0.5)

        for x in range(0, self.canvas_size + 1, self.grid_size):
            line = self._scene.addLine(x, 0, x, self.canvas_size, pen)
            line.setZValue(-1000)

        for y in range(0, self.canvas_size + 1, self.grid_size):
            line = self._scene.addLine(0, y, self.canvas_size, y, pen)
            line.setZValue(-1000)

    @track_recursion
    def add_primitive(self, prim_type: PrimitiveType) -> str:
        """Add a new primitive to the canvas."""
        debug_print(f"EnhancedShapeEditorCanvas.add_primitive({prim_type})")

        prim_id = str(uuid.uuid4())
        center = QPointF(self.canvas_size / 2, self.canvas_size / 2)

        if prim_type == PrimitiveType.ELLIPSE:
            bounds = QRectF(center.x() - 50, center.y() - 30, 100, 60)
            primitive = Primitive(id=prim_id, type=prim_type, bounds=bounds, points=[])

        elif prim_type == PrimitiveType.RECTANGLE:
            bounds = QRectF(center.x() - 50, center.y() - 40, 100, 80)
            primitive = Primitive(id=prim_id, type=prim_type, bounds=bounds, points=[])

        elif prim_type == PrimitiveType.POLYGON:
            # Create default triangle with bezier capability
            points = [
                ControlPoint(id=str(uuid.uuid4()), x=center.x() - 40, y=center.y() + 30),
                ControlPoint(id=str(uuid.uuid4()), x=center.x(), y=center.y() - 40),
                ControlPoint(id=str(uuid.uuid4()), x=center.x() + 40, y=center.y() + 30)
            ]
            primitive = Primitive(id=prim_id, type=prim_type, bounds=QRectF(), points=points)
            debug_print(f"  Created POLYGON with {len(points)} points")

        self.primitives[prim_id] = primitive

        # Create graphics item
        debug_print("  Creating SelectablePrimitiveItem")
        item = SelectablePrimitiveItem(primitive, canvas=self)
        self.primitive_items[prim_id] = item
        self._scene.addItem(item)

        # Auto-select
        debug_print(f"  Auto-selecting primitive {prim_id[:8]}...")
        self.select_primitive(prim_id)
        self._emit_safe(self.shape_modified)

        debug_print(f"add_primitive complete, returning {prim_id[:8]}...")
        return prim_id

    @track_recursion
    def remove_primitive(self, prim_id: str):
        """Remove a primitive."""
        debug_print(f"EnhancedShapeEditorCanvas.remove_primitive({prim_id[:8]}...)")

        if prim_id in self.primitive_items:
            # Commit any pending position changes before removing
            self.primitive_items[prim_id].commit_position()

            self._clear_vertex_handles()

            item = self.primitive_items[prim_id]
            self._scene.removeItem(item)
            del self.primitive_items[prim_id]
            del self.primitives[prim_id]

            if self.selected_primitive_id == prim_id:
                self.selected_primitive_id = None
                self._clear_resize_handles()

            self._emit_safe(self.shape_modified)

    @track_recursion
    def select_primitive(self, prim_id: Optional[str]):
        """Select a primitive."""
        debug_print(f"EnhancedShapeEditorCanvas.select_primitive({prim_id[:8] if prim_id else None})")
        debug_print(f"  Current selected: {self.selected_primitive_id[:8] if self.selected_primitive_id else None}")

        # Skip if already selected (prevents interrupting handle drag operations)
        if prim_id is not None and prim_id == self.selected_primitive_id:
            debug_print("  Already selected, skipping re-selection")
            return

        # Commit position of previously selected primitive before deselecting
        if self.selected_primitive_id and self.selected_primitive_id in self.primitive_items:
            debug_print("  Committing position of previous primitive")
            self.primitive_items[self.selected_primitive_id].commit_position()
            self.primitive_items[self.selected_primitive_id].set_selected(False)

        debug_print("  Clearing handles")
        self._clear_resize_handles()
        self._clear_vertex_handles()
        self._clear_rotate_handle()

        # Select new
        self.selected_primitive_id = prim_id

        if prim_id and prim_id in self.primitive_items:
            debug_print(f"  Selecting new primitive")
            item = self.primitive_items[prim_id]
            item.set_selected(True)

            # Also add to selected_primitive_ids for consistency
            if prim_id not in self.selected_primitive_ids:
                self.selected_primitive_ids.append(prim_id)

            primitive = self.primitives[prim_id]

            if primitive.type == PrimitiveType.POLYGON:
                # Show vertex handles for editing
                debug_print("  Creating vertex handles for polygon")
                self._create_vertex_handles(primitive)
            else:
                # Show resize handles
                debug_print("  Creating resize handles")
                self._create_resize_handles(item)

            # Create rotation handle for all primitive types
            debug_print("  Creating rotation handle")
            self._create_rotate_handle(item)

            self._emit_safe(self.primitive_selected, prim_id)

        debug_print("select_primitive complete")

    @track_recursion
    def _create_vertex_handles(self, primitive: Primitive):
        """Create vertex handles for polygon editing as children of the primitive item."""
        debug_print(f"_create_vertex_handles() - {len(primitive.points)} points")

        item = self.primitive_items[primitive.id]
        center = item._center

        for point in primitive.points:
            # Create handle as child of the primitive item
            handle = VertexHandle(point, self, parent_item=item)
            self.vertex_handles[point.id] = handle

            # Position in local coordinates (relative to center)
            local_x = point.x - center.x()
            local_y = point.y - center.y()
            handle.setPos(local_x, local_y)

            debug_print(f"  Created vertex handle at local ({local_x:.1f}, {local_y:.1f})")

        debug_print("_create_vertex_handles complete")

    def _clear_vertex_handles(self):
        """Remove all vertex handles."""
        debug_print(f"_clear_vertex_handles() - {len(self.vertex_handles)} handles")
        for handle in self.vertex_handles.values():
            handle._hide_bezier_handles()
            # Remove from parent (handles are children of primitive item)
            handle.setParentItem(None)
            if handle.scene():
                self._scene.removeItem(handle)
        self.vertex_handles.clear()
        self.selected_vertex_id = None

    def _create_resize_handles(self, item: SelectablePrimitiveItem):
        """Create resize handles for ellipse/rectangle as children of the primitive item."""
        debug_print("_create_resize_handles()")

        # IMPORTANT: Clear Qt's internal selection on the primitive
        # and disable movability while resize handles are active.
        item.setSelected(False)
        item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)
        debug_print("  Disabled primitive movability for resize mode")

        primitive = item.primitive
        bounds = primitive.bounds
        center = item._center  # Center in data coordinates

        # Calculate local positions (relative to center)
        positions = {
            'nw': QPointF(bounds.left() - center.x(), bounds.top() - center.y()),
            'n': QPointF(bounds.center().x() - center.x(), bounds.top() - center.y()),
            'ne': QPointF(bounds.right() - center.x(), bounds.top() - center.y()),
            'e': QPointF(bounds.right() - center.x(), bounds.center().y() - center.y()),
            'se': QPointF(bounds.right() - center.x(), bounds.bottom() - center.y()),
            's': QPointF(bounds.center().x() - center.x(), bounds.bottom() - center.y()),
            'sw': QPointF(bounds.left() - center.x(), bounds.bottom() - center.y()),
            'w': QPointF(bounds.left() - center.x(), bounds.center().y() - center.y()),
        }

        for pos_name, local_pos in positions.items():
            # Create handle as child of primitive item
            handle = ResizeHandle(item, pos_name, canvas=self, parent_item=item)
            handle.setPos(local_pos)
            handle.finalize_init()
            self.resize_handles.append(handle)
            debug_print(f"  Created resize handle '{pos_name}' at local ({local_pos.x():.1f}, {local_pos.y():.1f})")

    def _clear_resize_handles(self):
        """Remove all resize handles."""
        debug_print(f"_clear_resize_handles() - {len(self.resize_handles)} handles")

        # Re-enable movability on the primitive
        if self.selected_primitive_id and self.selected_primitive_id in self.primitive_items:
            self.primitive_items[self.selected_primitive_id].setFlag(
                QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
            debug_print("  Re-enabled primitive movability")

        for handle in self.resize_handles:
            handle.setParentItem(None)
            if handle.scene():
                self._scene.removeItem(handle)
        self.resize_handles.clear()

    def _create_rotate_handle(self, item: SelectablePrimitiveItem):
        """Create rotation handle as a child of the primitive item."""
        debug_print("_create_rotate_handle()")

        self._clear_rotate_handle()

        primitive = item.primitive
        center = item._center

        # Calculate handle distance from center
        if primitive.type == PrimitiveType.POLYGON:
            if primitive.points:
                # Find top of bounding box (relative to center)
                min_y = min(p.y for p in primitive.points)
                handle_distance = (center.y() - min_y) + 40
            else:
                return
        else:
            handle_distance = (primitive.bounds.height() / 2) + 40

        # Handle position in local coordinates (directly above center at local 0,0)
        # Y is negative because it's above the center
        local_handle_pos = QPointF(0, -handle_distance)

        debug_print(f"  Handle distance: {handle_distance:.1f}")
        debug_print(f"  Local handle pos: ({local_handle_pos.x():.1f}, {local_handle_pos.y():.1f})")

        # Create handle as child of primitive item
        self.rotate_handle = RotateHandle(item, canvas=self, parent_item_gfx=item)
        self.rotate_handle.setPos(local_handle_pos)
        self.rotate_handle.finalize_init()
        # Connector line is added separately to scene (not as child)
        self._scene.addItem(self.rotate_handle.connector_line)
        self.rotate_handle._update_connector_line()

    def _clear_rotate_handle(self):
        """Remove the rotation handle."""
        debug_print("_clear_rotate_handle()")
        if self.rotate_handle:
            try:
                if self.rotate_handle.connector_line.scene():
                    self._scene.removeItem(self.rotate_handle.connector_line)
                # Remove from parent
                self.rotate_handle.setParentItem(None)
                if self.rotate_handle.scene():
                    self._scene.removeItem(self.rotate_handle)
            except RuntimeError:
                pass
            self.rotate_handle = None

    def on_rotation_modified(self):
        """Called when rotation changes."""
        debug_print("on_rotation_modified()")
        # Update connector line for rotate handle
        if self.rotate_handle:
            self.rotate_handle._update_connector_line()
        # Update bezier connector lines (they are separate scene items)
        for handle in self.vertex_handles.values():
            if handle.handle_in:
                handle.handle_in._update_control_line()
            if handle.handle_out:
                handle.handle_out._update_control_line()
        self._emit_safe(self.primitive_modified)

    def _rotate_point_around_center(self, point: QPointF, center: QPointF, angle_degrees: float) -> QPointF:
        """Rotate a point around a center by given angle in degrees."""
        angle_rad = math.radians(angle_degrees)
        dx = point.x() - center.x()
        dy = point.y() - center.y()

        rotated_x = center.x() + dx * math.cos(angle_rad) - dy * math.sin(angle_rad)
        rotated_y = center.y() + dx * math.sin(angle_rad) + dy * math.cos(angle_rad)

        return QPointF(rotated_x, rotated_y)

    # Note: move_vertex_handles_by_delta, move_resize_handles_by_delta, and
    # rotate_handles_around_center are no longer needed since handles are
    # children of the primitive item and inherit its transform automatically.

    def update_vertex_handle_positions(self):
        """Update vertex handle positions to match control point data (in local coordinates)."""
        debug_print(f"update_vertex_handle_positions() - {len(self.vertex_handles)} handles")

        if not self.selected_primitive_id:
            return

        item = self.primitive_items[self.selected_primitive_id]
        center = item._center

        for point_id, handle in self.vertex_handles.items():
            point = handle.control_point

            # Position in local coordinates (relative to center)
            local_x = point.x - center.x()
            local_y = point.y - center.y()
            handle.setPos(local_x, local_y)

            # Bezier handles - their position is the data offset (Qt applies rotation)
            if handle.handle_in and handle.control_point.handle_in:
                dx, dy = handle.control_point.handle_in
                handle.handle_in.setPos(dx, dy)
                handle.handle_in._update_control_line()

            if handle.handle_out and handle.control_point.handle_out:
                dx, dy = handle.control_point.handle_out
                handle.handle_out.setPos(dx, dy)
                handle.handle_out._update_control_line()

    def update_resize_handle_positions(self):
        """Update resize handle positions to match bounds data (in local coordinates)."""
        debug_print("update_resize_handle_positions()")
        if not self.selected_primitive_id:
            return

        primitive = self.primitives[self.selected_primitive_id]
        item = self.primitive_items[self.selected_primitive_id]
        bounds = primitive.bounds
        center = item._center

        positions = {
            'nw': QPointF(bounds.left() - center.x(), bounds.top() - center.y()),
            'n': QPointF(bounds.center().x() - center.x(), bounds.top() - center.y()),
            'ne': QPointF(bounds.right() - center.x(), bounds.top() - center.y()),
            'e': QPointF(bounds.right() - center.x(), bounds.center().y() - center.y()),
            'se': QPointF(bounds.right() - center.x(), bounds.bottom() - center.y()),
            's': QPointF(bounds.center().x() - center.x(), bounds.bottom() - center.y()),
            'sw': QPointF(bounds.left() - center.x(), bounds.bottom() - center.y()),
            'w': QPointF(bounds.left() - center.x(), bounds.center().y() - center.y()),
        }

        for handle in self.resize_handles:
            if handle.position in positions:
                handle.setPos(positions[handle.position])

    def update_resize_handle_positions_from_bounds(self):
        """Update all resize handle positions after a resize operation.

        Handles are children of the primitive, so positions are in local coordinates.
        """
        debug_print("update_resize_handle_positions_from_bounds()")
        if not self.selected_primitive_id:
            return

        primitive = self.primitives[self.selected_primitive_id]
        item = self.primitive_items[self.selected_primitive_id]
        bounds = primitive.bounds
        center = item._center

        positions = {
            'nw': QPointF(bounds.left() - center.x(), bounds.top() - center.y()),
            'n': QPointF(bounds.center().x() - center.x(), bounds.top() - center.y()),
            'ne': QPointF(bounds.right() - center.x(), bounds.top() - center.y()),
            'e': QPointF(bounds.right() - center.x(), bounds.center().y() - center.y()),
            'se': QPointF(bounds.right() - center.x(), bounds.bottom() - center.y()),
            's': QPointF(bounds.center().x() - center.x(), bounds.bottom() - center.y()),
            'sw': QPointF(bounds.left() - center.x(), bounds.bottom() - center.y()),
            'w': QPointF(bounds.left() - center.x(), bounds.center().y() - center.y()),
        }

        for handle in self.resize_handles:
            if handle.position in positions:
                handle.setPos(positions[handle.position])

    @track_recursion
    def select_vertex(self, vertex_id: str):
        """Select a specific vertex."""
        debug_print(f"select_vertex({vertex_id[:8]}...)")
        debug_print(f"  Current selected_vertex_id: {self.selected_vertex_id[:8] if self.selected_vertex_id else None}")

        # Prevent infinite recursion - if already selected, do nothing
        if vertex_id == self.selected_vertex_id:
            debug_print("  Already selected, returning early")
            return

        # Commit any pending primitive position changes before vertex editing
        if self.selected_primitive_id and self.selected_primitive_id in self.primitive_items:
            debug_print("  Committing primitive position")
            self.primitive_items[self.selected_primitive_id].commit_position()
            # Update vertex handles to match committed data
            self.update_vertex_handle_positions()

        # Deselect previous
        if self.selected_vertex_id and self.selected_vertex_id in self.vertex_handles:
            debug_print("  Deselecting previous vertex")
            self.vertex_handles[self.selected_vertex_id].set_selected(False)

        # Select new
        self.selected_vertex_id = vertex_id
        if vertex_id in self.vertex_handles:
            debug_print("  Selecting new vertex")
            self.vertex_handles[vertex_id].set_selected(True)
            self._emit_safe(self.vertex_selected, vertex_id)

        debug_print("select_vertex complete")

    @track_recursion
    def delete_vertex(self, vertex_id: str):
        """Delete a vertex from the selected polygon."""
        debug_print(f"delete_vertex({vertex_id[:8]}...)")
        if not self.selected_primitive_id:
            return

        primitive = self.primitives[self.selected_primitive_id]
        if primitive.type != PrimitiveType.POLYGON or len(primitive.points) <= 3:
            return  # Can't delete if less than 3 points

        # Remove the vertex
        primitive.points = [p for p in primitive.points if p.id != vertex_id]

        # Rebuild
        self._refresh_polygon_display()

    @track_recursion
    def add_vertex_at_midpoint(self):
        """Add a vertex at the midpoint of selected edge."""
        debug_print("add_vertex_at_midpoint()")
        if not self.selected_vertex_id or not self.selected_primitive_id:
            return

        primitive = self.primitives[self.selected_primitive_id]
        if primitive.type != PrimitiveType.POLYGON:
            return

        # Find the selected vertex index
        idx = next((i for i, p in enumerate(primitive.points) if p.id == self.selected_vertex_id), None)
        if idx is None:
            return

        # Calculate midpoint to next vertex
        current = primitive.points[idx]
        next_point = primitive.points[(idx + 1) % len(primitive.points)]

        mid_x = (current.x + next_point.x) / 2
        mid_y = (current.y + next_point.y) / 2

        # Insert new point
        new_point = ControlPoint(id=str(uuid.uuid4()), x=mid_x, y=mid_y)
        primitive.points.insert(idx + 1, new_point)

        # Rebuild
        self._refresh_polygon_display()

    @track_recursion
    def on_vertex_modified(self):
        """Called when a vertex or bezier handle is modified.

        Does NOT recalculate the center during dragging - this keeps other vertices
        stable in screen space. The center will be corrected when selection changes.
        """
        debug_print("on_vertex_modified()")
        if self.selected_primitive_id:
            item = self.primitive_items[self.selected_primitive_id]

            # Just recreate the path without changing center or item position
            # This keeps non-dragged vertices at their exact screen positions
            item._create_path()

            # Reposition all vertex handles relative to current center
            center = item._center
            for handle in self.vertex_handles.values():
                local_x = handle.control_point.x - center.x()
                local_y = handle.control_point.y - center.y()
                handle.setPos(local_x, local_y)

                # Update bezier handle connector lines
                if handle.handle_in:
                    handle.handle_in._update_control_line()
                if handle.handle_out:
                    handle.handle_out._update_control_line()

            # Update rotation handle connector line
            if self.rotate_handle:
                self.rotate_handle._update_connector_line()

            self._emit_safe(self.primitive_modified)

    def _recenter_selected_primitive(self):
        """Recenter the selected primitive after editing is complete.

        This updates the item's center and position while keeping vertices
        at their current screen positions.
        """
        debug_print("_recenter_selected_primitive()")
        if not self.selected_primitive_id:
            return

        item = self.primitive_items[self.selected_primitive_id]
        primitive = item.primitive
        rotation = primitive.rotation

        old_center = item._center
        old_item_pos = item.pos()

        # Calculate new center
        new_center = item._calculate_center()

        if old_center == new_center:
            return  # No change needed

        debug_print(f"  Recentering: old_center=({old_center.x():.1f}, {old_center.y():.1f}), new_center=({new_center.x():.1f}, {new_center.y():.1f})")

        # Calculate the offset between old and new center in data coords
        center_offset_x = new_center.x() - old_center.x()
        center_offset_y = new_center.y() - old_center.y()

        # Rotate this offset to get the scene offset
        if rotation != 0:
            angle_rad = math.radians(rotation)
            cos_a = math.cos(angle_rad)
            sin_a = math.sin(angle_rad)
            scene_offset_x = center_offset_x * cos_a - center_offset_y * sin_a
            scene_offset_y = center_offset_x * sin_a + center_offset_y * cos_a
        else:
            scene_offset_x = center_offset_x
            scene_offset_y = center_offset_y

        # Update center and item position
        item._center = new_center
        new_item_pos = QPointF(old_item_pos.x() + scene_offset_x, old_item_pos.y() + scene_offset_y)
        item._last_pos = new_item_pos
        item.setPos(new_item_pos)

        # Recreate path with new center
        item._create_path()

        # Update all vertex handle positions (for polygons)
        for handle in self.vertex_handles.values():
            local_x = handle.control_point.x - new_center.x()
            local_y = handle.control_point.y - new_center.y()
            handle.setPos(local_x, local_y)

            if handle.handle_in:
                handle.handle_in._update_control_line()
            if handle.handle_out:
                handle.handle_out._update_control_line()

        # Update all resize handle positions (for ellipse/rectangle)
        self.update_resize_handle_positions_from_bounds()

        # Update rotation handle
        if self.rotate_handle:
            self.rotate_handle._update_connector_line()

        debug_print(f"  New item pos: ({new_item_pos.x():.1f}, {new_item_pos.y():.1f})")

    @track_recursion
    def _refresh_polygon_display(self):
        """Refresh the polygon display after vertex changes."""
        debug_print("_refresh_polygon_display()")
        if not self.selected_primitive_id:
            return

        primitive = self.primitives[self.selected_primitive_id]
        item = self.primitive_items[self.selected_primitive_id]
        item.rebuild()

        # Refresh vertex handles
        self._clear_vertex_handles()
        self._create_vertex_handles(primitive)

        self._emit_safe(self.shape_modified)

    @track_recursion
    def mousePressEvent(self, event):
        """Handle mouse press."""
        debug_print("EnhancedShapeEditorCanvas.mousePressEvent()")

        # Right-click for context menu
        if event.button() == Qt.MouseButton.RightButton:
            self._show_context_menu(event.pos())
            return

        # Get ALL items at click position using a small rectangle for better hit detection
        scene_pos = self.mapToScene(event.pos())
        hit_rect = QRectF(scene_pos.x() - 5, scene_pos.y() - 5, 10, 10)
        items_at_pos = self._scene.items(hit_rect)

        debug_print(f"  Scene pos: ({scene_pos.x():.1f}, {scene_pos.y():.1f}), found {len(items_at_pos)} items")

        # Check for Ctrl or Shift modifier for multi-selection
        ctrl_pressed = event.modifiers() & Qt.KeyboardModifier.ControlModifier
        shift_pressed = event.modifiers() & Qt.KeyboardModifier.ShiftModifier
        multi_select = ctrl_pressed or shift_pressed

        # Find the highest priority item (group handles > handles > groups > primitives)
        item = None
        for candidate in items_at_pos:
            if isinstance(candidate, QGraphicsLineItem):
                continue
            debug_print(f"    Candidate: {type(candidate).__name__}")

            # Group handles have highest priority
            if isinstance(candidate, (GroupResizeHandle, GroupRotateHandle)):
                item = candidate
                debug_print(f"    -> Selected {type(candidate).__name__}")
                break
            elif isinstance(candidate, BezierHandleItem):
                item = candidate
                debug_print(f"    -> Selected BezierHandleItem")
                break
            elif isinstance(candidate, (ResizeHandle, RotateHandle)):
                if item is None or not isinstance(item, BezierHandleItem):
                    item = candidate
                    debug_print(f"    -> Selected {type(candidate).__name__}")
            elif isinstance(candidate, VertexHandle):
                if item is None or not isinstance(item, (BezierHandleItem, ResizeHandle, RotateHandle)):
                    item = candidate
                    debug_print(f"    -> Selected VertexHandle")
            elif isinstance(candidate, GroupItem):
                if item is None or not isinstance(item, (BezierHandleItem, ResizeHandle, RotateHandle, VertexHandle)):
                    item = candidate
                    debug_print(f"    -> Selected GroupItem")
            elif isinstance(candidate, SelectablePrimitiveItem):
                if item is None:
                    item = candidate

        debug_print(f"  Final item: {type(item).__name__ if item else None}")

        # Handle group handles
        if isinstance(item, (GroupResizeHandle, GroupRotateHandle)):
            debug_print(f"  Clicking on group handle")
            super().mousePressEvent(event)
            return

        # Handle primitive handles
        if isinstance(item, (BezierHandleItem, ResizeHandle, RotateHandle, VertexHandle)):
            debug_print(f"  Clicking on handle, disabling primitive movability")
            if self.selected_primitive_id and self.selected_primitive_id in self.primitive_items:
                prim_item = self.primitive_items[self.selected_primitive_id]
                prim_item.setSelected(False)
                prim_item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)
            super().mousePressEvent(event)
            return

        # Handle clicking on GroupItem
        if isinstance(item, GroupItem):
            debug_print(f"  Clicking on group: {item.group.id[:8]}...")
            self._clear_single_selection()
            self._clear_group_selection()  # Clear any previous group's handles
            self.selected_group_id = item.group.id
            item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
            item.set_group_selected(True)  # Show bounding box
            item.create_handles(self._scene)  # Create handles for this group
            super().mousePressEvent(event)
            return

        # Handle clicking on a primitive
        if isinstance(item, SelectablePrimitiveItem):
            prim_id = item.primitive.id
            debug_print(f"  Clicking on primitive: {prim_id[:8]}...")

            # Check if this primitive is part of a group
            prim = self.primitives.get(prim_id)
            if prim and prim.group_id and prim.group_id in self.group_items:
                # Select the group instead
                debug_print(f"  Primitive is in group, selecting group instead")
                group_item = self.group_items[prim.group_id]
                self._clear_single_selection()
                self._clear_group_selection()
                self.selected_group_id = prim.group_id
                group_item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
                group_item.set_group_selected(True)
                group_item.create_handles(self._scene)
                super().mousePressEvent(event)
                return

            # Clear any group selection
            self._clear_group_selection()

            if multi_select:
                # Toggle selection of this primitive (Ctrl+Click or Shift+Click)
                if prim_id in self.selected_primitive_ids:
                    self.selected_primitive_ids.remove(prim_id)
                    item.set_selected(False)
                    debug_print(f"  Multi-select click: Removed from selection")
                else:
                    self.selected_primitive_ids.append(prim_id)
                    item.set_selected(True)
                    debug_print(f"  Multi-select click: Added to selection")

                # Update primary selection
                if self.selected_primitive_ids:
                    self.selected_primitive_id = prim_id
                else:
                    self.selected_primitive_id = None
                return
            else:
                # Single click without multi-select modifier
                if prim_id != self.selected_primitive_id:
                    debug_print("  Different primitive - selecting it")
                    self._scene.clearSelection()
                    # Clear highlights on all previously selected items
                    for prev_id in self.selected_primitive_ids:
                        if prev_id in self.primitive_items:
                            self.primitive_items[prev_id].set_selected(False)
                    self.selected_primitive_ids.clear()
                    self.select_primitive(prim_id)
                    return
                else:
                    # Clicking on ALREADY selected primitive body - allow drag to start
                    debug_print("  Same primitive body - enabling move mode")
                    item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
                    super().mousePressEvent(event)
                    return

        # Clicking on empty space - start rubberband selection
        debug_print("  Clicking on empty space - starting rubberband")
        self._rubberband_active = True
        self._rubberband_origin = event.pos()
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)

        if not multi_select:
            # Clear selection if not using multi-select modifier
            self._clear_all_selection()

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """Handle mouse move - track active handle dragging or rubberband."""
        if self._active_handle and hasattr(self._active_handle, 'handle_drag'):
            scene_pos = self.mapToScene(event.pos())
            self._active_handle.handle_drag(scene_pos)
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        """Handle mouse release - end active handle drag or rubberband selection."""
        if self._active_handle:
            super().mouseReleaseEvent(event)
            self._active_handle = None
        elif self._rubberband_active:
            self._rubberband_active = False
            self.setDragMode(QGraphicsView.DragMode.NoDrag)

            # Get selected items from rubberband
            selected_items = self._scene.selectedItems()
            debug_print(f"  Rubberband selected {len(selected_items)} items")

            for item in selected_items:
                if isinstance(item, SelectablePrimitiveItem):
                    prim_id = item.primitive.id
                    if prim_id not in self.selected_primitive_ids:
                        self.selected_primitive_ids.append(prim_id)
                    item.set_selected(True)
                    debug_print(f"    Added primitive {prim_id[:8]}...")

            # Set primary selection to first if any
            if self.selected_primitive_ids and not self.selected_primitive_id:
                self.selected_primitive_id = self.selected_primitive_ids[0]

            # Create handles for single selection, or show multi-select UI
            if len(self.selected_primitive_ids) == 1:
                self.select_primitive(self.selected_primitive_id)
            elif len(self.selected_primitive_ids) > 1:
                debug_print(f"  Multi-selection: {len(self.selected_primitive_ids)} primitives")
                self._clear_resize_handles()
                self._clear_vertex_handles()
                self._clear_rotate_handle()

            super().mouseReleaseEvent(event)
        else:
            super().mouseReleaseEvent(event)

    def _show_context_menu(self, pos):
        """Show context menu for group/ungroup and boolean operations."""
        menu = QMenu(self)

        # Vertex type selection - available when a vertex is selected
        if self.selected_vertex_id:
            # Find the control point
            cp = None
            prim = None
            if self.selected_primitive_id:
                prim = self.primitives.get(self.selected_primitive_id)
                if prim and prim.type == PrimitiveType.POLYGON:
                    for point in prim.points:
                        if point.id == self.selected_vertex_id:
                            cp = point
                            break

            if cp:
                menu.addSection("Vertex Type")

                corner_action = menu.addAction("Corner")
                corner_action.setCheckable(True)
                corner_action.setChecked(cp.point_type == PointType.CORNER)
                corner_action.triggered.connect(lambda checked, t=PointType.CORNER: self._set_vertex_type(t))

                smooth_action = menu.addAction("Smooth")
                smooth_action.setCheckable(True)
                smooth_action.setChecked(cp.point_type == PointType.SMOOTH)
                smooth_action.triggered.connect(lambda checked, t=PointType.SMOOTH: self._set_vertex_type(t))

                symmetric_action = menu.addAction("Symmetric")
                symmetric_action.setCheckable(True)
                symmetric_action.setChecked(cp.point_type == PointType.SYMMETRIC)
                symmetric_action.triggered.connect(lambda checked, t=PointType.SYMMETRIC: self._set_vertex_type(t))

                menu.addSeparator()

        # Sparsify - available when a single polygon is selected AND no vertex is selected
        elif len(self.selected_primitive_ids) == 1 and not self.selected_vertex_id:
            prim = self.primitives.get(self.selected_primitive_ids[0])
            if prim and prim.type == PrimitiveType.POLYGON and len(prim.points) > 4:
                sparsify_action = menu.addAction(f"Sparsify ({len(prim.points)} vertices)")
                sparsify_action.triggered.connect(self._sparsify_polygon)
                menu.addSeparator()

        # Boolean operations - available when exactly 2 primitives selected
        if len(self.selected_primitive_ids) == 2:
            menu.addSection("Boolean Operations (A=1st, B=2nd)")

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

        # Ungroup action - available when a group is selected
        if self.selected_group_id:
            ungroup_action = menu.addAction("Ungroup")
            ungroup_action.triggered.connect(self._ungroup_selected)

        # Also check if a grouped primitive is selected
        if self.selected_primitive_id:
            prim = self.primitives.get(self.selected_primitive_id)
            if prim and prim.group_id:
                ungroup_action = menu.addAction("Ungroup")
                ungroup_action.triggered.connect(lambda: self._ungroup(prim.group_id))

        # Snap settings - always available
        menu.addSeparator()
        snap_menu = menu.addMenu("Snap Settings (Ctrl+drag)")

        grid_action = snap_menu.addAction(f"Grid Snap: {self.grid_snap_size:.0f} px")
        grid_action.triggered.connect(self._set_grid_snap)

        angle_action = snap_menu.addAction(f"Rotation Snap: {self.rotation_snap_angle:.0f}°")
        angle_action.triggered.connect(self._set_rotation_snap)

        if not menu.isEmpty():
            menu.exec(self.mapToGlobal(pos))

    def _set_grid_snap(self):
        """Set the grid snap size."""
        value, ok = QInputDialog.getDouble(
            self,
            "Grid Snap Size",
            "Snap to grid size (pixels):\n\n"
            "Hold Ctrl while dragging to snap to this grid.",
            self.grid_snap_size,
            1.0,  # min
            500.0,  # max
            0  # decimals
        )
        if ok:
            self.grid_snap_size = value
            debug_print(f"Grid snap size set to {value}")

    def _set_rotation_snap(self):
        """Set the rotation snap angle."""
        value, ok = QInputDialog.getDouble(
            self,
            "Rotation Snap Angle",
            "Snap to rotation angle (degrees):\n\n"
            "Hold Ctrl while rotating to snap to this angle.",
            self.rotation_snap_angle,
            1.0,  # min
            90.0,  # max
            0  # decimals
        )
        if ok:
            self.rotation_snap_angle = value
            debug_print(f"Rotation snap angle set to {value}")

    def _set_vertex_type(self, point_type: PointType):
        """Set the type of the selected vertex."""
        if not self.selected_vertex_id or not self.selected_primitive_id:
            return

        prim = self.primitives.get(self.selected_primitive_id)
        if not prim or prim.type != PrimitiveType.POLYGON:
            return

        # Find the control point
        cp = None
        for point in prim.points:
            if point.id == self.selected_vertex_id:
                cp = point
                break

        if not cp:
            return

        old_type = cp.point_type
        cp.point_type = point_type
        debug_print(f"Changed vertex type from {old_type.value} to {point_type.value}")

        # Handle bezier handles based on type
        if point_type == PointType.CORNER:
            # Remove bezier handles for corner points
            cp.handle_in = None
            cp.handle_out = None
        elif point_type in (PointType.SMOOTH, PointType.SYMMETRIC):
            # Create default bezier handles if they don't exist
            if not cp.handle_in and not cp.handle_out:
                # Create default handles pointing along the path
                # Find neighboring points for direction
                idx = prim.points.index(cp)
                n = len(prim.points)
                prev_pt = prim.points[(idx - 1) % n]
                next_pt = prim.points[(idx + 1) % n]

                # Direction from prev to next
                dx = next_pt.x - prev_pt.x
                dy = next_pt.y - prev_pt.y
                length = math.sqrt(dx*dx + dy*dy)
                if length > 0:
                    # Normalize and scale
                    handle_len = length * 0.25  # 25% of distance between neighbors
                    dx = dx / length * handle_len
                    dy = dy / length * handle_len
                else:
                    dx, dy = 20, 0  # Default horizontal

                cp.handle_in = (-dx, -dy)
                cp.handle_out = (dx, dy)

        # Update the vertex handle's bezier handles
        if self.selected_vertex_id in self.vertex_handles:
            handle = self.vertex_handles[self.selected_vertex_id]
            handle._hide_bezier_handles()
            if point_type != PointType.CORNER:
                handle._show_bezier_handles()

        # Update the primitive's path
        if self.selected_primitive_id in self.primitive_items:
            item = self.primitive_items[self.selected_primitive_id]
            item._create_path()
            item.update()

        self._emit_safe(self.shape_modified)

    def _clear_single_selection(self):
        """Clear single primitive selection and its handles."""
        if self.selected_primitive_id and self.selected_primitive_id in self.primitive_items:
            self.primitive_items[self.selected_primitive_id].set_selected(False)
        self.selected_primitive_id = None
        self._clear_resize_handles()
        self._clear_vertex_handles()
        self._clear_rotate_handle()

    def _clear_group_selection(self):
        """Clear group selection and hide the bounding box."""
        if self.selected_group_id and self.selected_group_id in self.group_items:
            group_item = self.group_items[self.selected_group_id]
            group_item.clear_handles(self._scene)
            group_item.set_group_selected(False)  # Hide bounding box
        self.selected_group_id = None

    def _clear_all_selection(self):
        """Clear all selections."""
        self._clear_single_selection()
        self._clear_group_selection()
        for prim_id in self.selected_primitive_ids:
            if prim_id in self.primitive_items:
                self.primitive_items[prim_id].set_selected(False)
        self.selected_primitive_ids.clear()

    def _group_selected(self):
        """Group all selected primitives."""
        if len(self.selected_primitive_ids) < 2:
            return

        debug_print(f"Grouping {len(self.selected_primitive_ids)} primitives")

        # Create group
        group_id = str(uuid.uuid4())
        group = PrimitiveGroup(
            id=group_id,
            member_ids=list(self.selected_primitive_ids)
        )
        self.groups[group_id] = group

        # Update primitives with group reference and turn off selection highlight
        for prim_id in self.selected_primitive_ids:
            self.primitives[prim_id].group_id = group_id
            if prim_id in self.primitive_items:
                self.primitive_items[prim_id].set_selected(False)

        # Create group item
        group_item = GroupItem(group, canvas=self)
        member_items = [self.primitive_items[pid] for pid in self.selected_primitive_ids]
        group_item.set_members(member_items)
        self._scene.addItem(group_item)
        group_item.create_handles(self._scene)
        self.group_items[group_id] = group_item

        # Clear individual selection, select group
        self._clear_single_selection()
        self.selected_primitive_ids.clear()
        self.selected_group_id = group_id

        self._emit_safe(self.shape_modified)

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

        # Clear group reference from primitives
        for prim_id in group.member_ids:
            if prim_id in self.primitives:
                self.primitives[prim_id].group_id = None

        # Remove group item
        if group_item:
            group_item.clear_handles(self._scene)
            if group_item.scene():
                self._scene.removeItem(group_item)
            del self.group_items[group_id]

        # Remove group
        del self.groups[group_id]

        # Clear selection
        if self.selected_group_id == group_id:
            self.selected_group_id = None

        self._emit_safe(self.shape_modified)

    # =========================================================================
    # Boolean Operations
    # =========================================================================

    def _get_primitive_path(self, prim_id: str) -> QPainterPath:
        """Get the QPainterPath for a primitive in scene coordinates."""
        if prim_id not in self.primitives or prim_id not in self.primitive_items:
            return QPainterPath()

        primitive = self.primitives[prim_id]
        item = self.primitive_items[prim_id]

        # Get the item's path and transform it to scene coordinates
        local_path = item.path()

        # Apply rotation transform around center
        transform = QTransform()
        transform.translate(item.pos().x(), item.pos().y())
        if primitive.rotation != 0:
            transform.rotate(primitive.rotation)

        return transform.map(local_path)

    def _path_to_polygon_primitive(self, path: QPainterPath, fill_color: QColor = None,
                                    stroke_color: QColor = None, stroke_width: float = 2.0) -> Optional[Primitive]:
        """Convert a QPainterPath to a polygon Primitive (uses largest subpath)."""
        primitives = self._path_to_polygon_primitives(path, fill_color, stroke_color, stroke_width)
        return primitives[0] if primitives else None

    def _path_to_polygon_primitives(self, path: QPainterPath, fill_color: QColor = None,
                                     stroke_color: QColor = None, stroke_width: float = 2.0) -> List[Primitive]:
        """Convert a QPainterPath to multiple polygon Primitives (one per subpath)."""
        # Get polygons from path
        polygons = path.toSubpathPolygons()

        if not polygons:
            return []

        primitives = []
        min_area = 100  # Minimum area to create a primitive (avoid tiny fragments)

        for poly in polygons:
            if len(poly) < 3:
                continue

            area = self._polygon_area(poly)
            if area < min_area:
                continue

            # Create control points from polygon vertices
            points = []
            for point in poly:
                cp = ControlPoint(
                    id=str(uuid.uuid4()),
                    x=point.x(),
                    y=point.y(),
                    point_type=PointType.CORNER
                )
                points.append(cp)

            # Remove last point if it's the same as first (closed path)
            if len(points) > 1:
                first = points[0]
                last = points[-1]
                if abs(first.x - last.x) < 0.1 and abs(first.y - last.y) < 0.1:
                    points.pop()

            if len(points) < 3:
                continue

            # Create primitive
            prim = Primitive(
                id=str(uuid.uuid4()),
                type=PrimitiveType.POLYGON,
                points=points,
                fill_color=fill_color or QColor(200, 200, 255),
                stroke_color=stroke_color or QColor(0, 0, 0),
                stroke_width=stroke_width,
                rotation=0.0
            )
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

    def _boolean_operation(self, operation: str):
        """Perform a boolean operation on selected primitives."""
        if len(self.selected_primitive_ids) != 2:
            debug_print(f"Boolean operation requires exactly 2 primitives")
            return

        # Use selection order: first selected = A, second selected = B
        prim1_id, prim2_id = self.selected_primitive_ids[0], self.selected_primitive_ids[1]

        debug_print(f"Boolean operation: {operation}")
        debug_print(f"  A (1st selected): {prim1_id[:8]}...")
        debug_print(f"  B (2nd selected): {prim2_id[:8]}...")

        # Get paths in scene coordinates
        path1 = self._get_primitive_path(prim1_id)
        path2 = self._get_primitive_path(prim2_id)

        if path1.isEmpty() or path2.isEmpty():
            debug_print("  One or both paths are empty")
            return

        # Get colors from first primitive
        prim1 = self.primitives[prim1_id]
        prim2 = self.primitives[prim2_id]
        fill_color = prim1.fill_color
        stroke_color = prim1.stroke_color
        stroke_width = prim1.stroke_width

        result_paths = []
        path_colors = []  # Track colors for each path (for fragment)

        if operation == 'union':
            # Union: combine both shapes
            result_path = path1.united(path2)
            result_paths = [result_path]
            path_colors = [fill_color]

        elif operation == 'combine':
            # Combine (XOR): union minus intersection
            union_path = path1.united(path2)
            intersect_path = path1.intersected(path2)
            result_path = union_path.subtracted(intersect_path)
            result_paths = [result_path]
            path_colors = [fill_color]

        elif operation == 'intersect':
            # Intersect: only the overlapping area
            result_path = path1.intersected(path2)
            result_paths = [result_path]
            path_colors = [fill_color]

        elif operation == 'subtract':
            # Subtract: first minus second
            result_path = path1.subtracted(path2)
            result_paths = [result_path]
            path_colors = [fill_color]

        elif operation == 'fragment':
            # Fragment: split into all individual regions
            # Region A only, intersection, Region B only
            intersect_path = path1.intersected(path2)
            a_only = path1.subtracted(path2)
            b_only = path2.subtracted(path1)

            # Add non-empty paths with their respective colors
            if not a_only.isEmpty():
                result_paths.append(a_only)
                path_colors.append(prim1.fill_color)
            if not intersect_path.isEmpty():
                result_paths.append(intersect_path)
                # Mix colors for intersection
                h1, s1, l1, _ = prim1.fill_color.getHsl()
                h2, s2, l2, _ = prim2.fill_color.getHsl()
                mixed_color = QColor.fromHsl((h1 + h2) // 2, (s1 + s2) // 2, (l1 + l2) // 2)
                path_colors.append(mixed_color)
            if not b_only.isEmpty():
                result_paths.append(b_only)
                path_colors.append(prim2.fill_color)

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

            # Get color for this path
            frag_color = path_colors[i] if i < len(path_colors) else fill_color

            # Get all primitives from this path (handles multiple subpaths)
            new_prims = self._path_to_polygon_primitives(
                result_path, frag_color, stroke_color, stroke_width
            )

            for new_prim in new_prims:
                self._add_primitive_from_data(new_prim)
                new_prim_ids.append(new_prim.id)
                debug_print(f"  Created new primitive: {new_prim.id[:8]}...")

        # Select the first new primitive
        if new_prim_ids:
            self.select_primitive(new_prim_ids[0])

        self._emit_safe(self.shape_modified)
        debug_print(f"  Boolean operation complete: created {len(new_prim_ids)} primitive(s)")

    def _remove_primitive(self, prim_id: str):
        """Remove a primitive from the canvas."""
        if prim_id not in self.primitives:
            return

        debug_print(f"Removing primitive: {prim_id[:8]}...")

        # Remove from any group
        prim = self.primitives[prim_id]
        if prim.group_id and prim.group_id in self.groups:
            group = self.groups[prim.group_id]
            if prim_id in group.member_ids:
                group.member_ids.remove(prim_id)

        # Remove graphics item
        if prim_id in self.primitive_items:
            item = self.primitive_items[prim_id]
            if item.scene():
                self._scene.removeItem(item)
            del self.primitive_items[prim_id]

        # Remove data
        del self.primitives[prim_id]

        # Clear selection if this was selected
        if self.selected_primitive_id == prim_id:
            self.selected_primitive_id = None
        if prim_id in self.selected_primitive_ids:
            self.selected_primitive_ids.remove(prim_id)

    def _add_primitive_from_data(self, primitive: Primitive):
        """Add a primitive to the canvas from data."""
        self.primitives[primitive.id] = primitive

        # Create graphics item
        item = SelectablePrimitiveItem(primitive, canvas=self)
        self._scene.addItem(item)
        self.primitive_items[primitive.id] = item

    # =========================================================================
    # Sparsify Operation
    # =========================================================================

    def _sparsify_polygon(self):
        """Remove extra vertices from a polygon using adjustable tolerance.

        Shows a dialog to set the tolerance, then removes vertices that
        don't contribute significantly to the shape.
        """
        if not self.selected_primitive_ids:
            return

        prim_id = self.selected_primitive_ids[0]
        prim = self.primitives.get(prim_id)

        if not prim or prim.type != PrimitiveType.POLYGON:
            debug_print("Sparsify: Not a polygon")
            return

        if len(prim.points) <= 4:
            debug_print("Sparsify: Too few vertices to sparsify")
            return

        original_count = len(prim.points)
        n = original_count

        # Calculate edge length statistics
        edge_lengths = []
        for i in range(n):
            p1 = prim.points[i]
            p2 = prim.points[(i + 1) % n]
            dist = math.sqrt((p2.x - p1.x)**2 + (p2.y - p1.y)**2)
            edge_lengths.append(dist)

        avg_edge = sum(edge_lengths) / len(edge_lengths)
        min_edge = min(edge_lengths)
        max_edge = max(edge_lengths)

        # Calculate perpendicular distances for each vertex
        perp_distances = []
        for i in range(n):
            prev_idx = (i - 1) % n
            next_idx = (i + 1) % n

            p_prev = prim.points[prev_idx]
            p_curr = prim.points[i]
            p_next = prim.points[next_idx]

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

        # Default tolerance at 75th percentile (will remove ~25% of vertices per pass)
        default_tolerance = percentile_75

        # Show dialog to get tolerance
        tolerance, ok = QInputDialog.getDouble(
            self,
            "Sparsify Polygon",
            f"Vertices: {original_count}\n\n"
            f"Edge lengths: min={min_edge:.1f}, avg={avg_edge:.1f}, max={max_edge:.1f}\n"
            f"Vertex deviations: min={min_perp:.1f}, median={median_perp:.1f}, max={max_perp:.1f}\n\n"
            f"Tolerance (vertices with deviation below this will be removed):\n"
            f"(Higher value = more vertices removed)",
            default_tolerance,
            0.1,  # min
            max_perp + 1,  # max
            1  # decimals
        )

        if not ok:
            return

        debug_print(f"Sparsify: tolerance={tolerance:.1f}, starting with {original_count} vertices")

        # Run the Douglas-Peucker-like simplification
        total_removed = self._sparsify_with_tolerance(prim, tolerance)

        final_count = len(prim.points)
        debug_print(f"Sparsify complete: {original_count} → {final_count} vertices "
                   f"(removed {total_removed})")

        if total_removed == 0:
            QMessageBox.information(
                self,
                "Sparsify",
                f"No vertices removed.\n"
                f"Try increasing the tolerance value.\n\n"
                f"Current tolerance: {tolerance:.1f}"
            )
            return

        # Update the graphics item
        if prim_id in self.primitive_items:
            item = self.primitive_items[prim_id]

            # Recalculate center from the modified points
            item._center = item._calculate_center()

            # Update position to new center
            item.setPos(item._center)
            item._last_pos = item._center

            # Recreate the path with new points
            item._create_path()

            # Force scene update
            item.prepareGeometryChange()
            item.update()
            self._scene.update()

            # Recreate vertex handles
            self._clear_vertex_handles()
            self._create_vertex_handles(prim)

        # Show result
        QMessageBox.information(
            self,
            "Sparsify Complete",
            f"Removed {total_removed} vertices.\n"
            f"Vertices: {original_count} → {final_count}"
        )

        self._emit_safe(self.shape_modified)

    def _sparsify_with_tolerance(self, prim: Primitive, tolerance: float) -> int:
        """Remove vertices that don't contribute more than tolerance to the shape.

        Uses perpendicular distance: if a vertex is within 'tolerance' distance
        of the line connecting its neighbors, it can be removed.
        """
        total_removed = 0
        max_passes = 20

        for pass_num in range(max_passes):
            if len(prim.points) <= 3:
                break

            n = len(prim.points)

            # Calculate perpendicular distance for each vertex
            perp_distances = []
            for i in range(n):
                prev_idx = (i - 1) % n
                next_idx = (i + 1) % n

                p_prev = prim.points[prev_idx]
                p_curr = prim.points[i]
                p_next = prim.points[next_idx]

                # Line from prev to next
                line_dx = p_next.x - p_prev.x
                line_dy = p_next.y - p_prev.y
                line_len = math.sqrt(line_dx**2 + line_dy**2)

                if line_len > 0.001:
                    # Perpendicular distance from p_curr to line p_prev-p_next
                    perp_dist = abs((p_curr.x - p_prev.x) * line_dy -
                                   (p_curr.y - p_prev.y) * line_dx) / line_len
                else:
                    perp_dist = 0

                perp_distances.append((i, perp_dist))

            # Find vertices that can be removed (below tolerance)
            removable = [(i, d) for i, d in perp_distances if d < tolerance]

            if not removable:
                break

            # Sort by distance (remove least significant first)
            removable.sort(key=lambda x: x[1])

            # Remove every other vertex to avoid removing adjacent ones
            to_remove = set()
            removed_indices = set()

            for idx, dist in removable:
                # Don't remove if adjacent to an already-removed vertex
                prev_idx = (idx - 1) % n
                next_idx = (idx + 1) % n

                if prev_idx in removed_indices or next_idx in removed_indices:
                    continue

                # Don't go below 3 vertices
                if n - len(to_remove) <= 3:
                    break

                to_remove.add(idx)
                removed_indices.add(idx)

            if not to_remove:
                break

            # Remove vertices
            prim.points = [p for i, p in enumerate(prim.points) if i not in to_remove]
            total_removed += len(to_remove)

            debug_print(f"  Pass {pass_num + 1}: removed {len(to_remove)} vertices")

        return total_removed

    def keyPressEvent(self, event):
        """Handle keyboard shortcuts."""
        if event.key() == Qt.Key.Key_Delete:
            if self.selected_vertex_id:
                self.delete_vertex(self.selected_vertex_id)
        elif event.key() == Qt.Key.Key_Insert or (event.key() == Qt.Key.Key_I and event.modifiers() & Qt.KeyboardModifier.ControlModifier):
            self.add_vertex_at_midpoint()

        super().keyPressEvent(event)

    def commit_all_positions(self):
        """Commit positions for all primitives (call before saving/exporting)."""
        for item in self.primitive_items.values():
            item.commit_position()

    def get_primitives_list(self) -> List[Dict]:
        """Get list of primitives for widget display."""
        result = []
        for prim_id, primitive in self.primitives.items():
            result.append({
                'id': prim_id,
                'type': primitive.type.value,
                'selected': prim_id == self.selected_primitive_id,
                'vertex_count': len(primitive.points) if primitive.type == PrimitiveType.POLYGON else 0
            })
        return result

    def update_primitive_style(self, prim_id: str, fill_color: QColor = None,
                              stroke_color: QColor = None, stroke_width: float = None):
        """Update primitive styling."""
        if prim_id not in self.primitive_items:
            return

        primitive = self.primitives[prim_id]
        item = self.primitive_items[prim_id]

        if fill_color:
            primitive.fill_color = fill_color
            item.setBrush(QBrush(fill_color))

        if stroke_color:
            primitive.stroke_color = stroke_color

        if stroke_width is not None:
            primitive.stroke_width = stroke_width

        item.setPen(QPen(primitive.stroke_color, primitive.stroke_width))
        self._emit_safe(self.primitive_modified)


# =============================================================================
# Demo Application
# =============================================================================

class ShapeEditorDemo(QMainWindow):
    """Demo of polygon editing with bezier curves."""

    def __init__(self):
        debug_print("ShapeEditorDemo.__init__()")
        super().__init__()
        title = "Shape Editor with Polygon & Bezier Editing"
        if DEBUG_ENABLED:
            title += " [DEBUG MODE]"
        self.setWindowTitle(title)

        # Main widget
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QHBoxLayout(main_widget)

        # Canvas
        debug_print("Creating canvas")
        self.canvas = EnhancedShapeEditorCanvas()
        layout.addWidget(self.canvas)

        # Controls
        debug_print("Creating controls")
        controls = self._create_controls()
        layout.addWidget(controls)

        debug_print("Connecting signals")
        self._connect_signals()
        self._update_primitives_list()

        self.resize(1100, 700)

        # Add instructions
        msg = "Right-click vertex for options | Delete key removes vertex | Ctrl+I adds vertex at midpoint"
        if DEBUG_ENABLED:
            msg = "DEBUG MODE | " + msg
        self.statusBar().showMessage(msg)

        debug_print("ShapeEditorDemo.__init__ complete")

    def _create_controls(self):
        """Create control panel."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Primitives
        prim_group = QGroupBox("Primitives")
        prim_layout = QVBoxLayout(prim_group)

        self.prim_list = QListWidget()
        prim_layout.addWidget(self.prim_list)

        btn_layout = QHBoxLayout()
        self.add_ellipse_btn = QPushButton("Ellipse")
        self.add_rect_btn = QPushButton("Rect")
        self.add_poly_btn = QPushButton("Polygon")
        self.remove_btn = QPushButton("Remove")

        btn_layout.addWidget(self.add_ellipse_btn)
        btn_layout.addWidget(self.add_rect_btn)
        btn_layout.addWidget(self.add_poly_btn)
        btn_layout.addWidget(self.remove_btn)
        prim_layout.addLayout(btn_layout)

        layout.addWidget(prim_group)

        # Style
        style_group = QGroupBox("Style")
        style_layout = QFormLayout(style_group)

        self.fill_btn = QPushButton("Choose Fill")
        self.stroke_btn = QPushButton("Choose Stroke")
        self.width_spin = QDoubleSpinBox()
        self.width_spin.setRange(0.5, 10.0)
        self.width_spin.setValue(2.0)

        style_layout.addRow("Fill:", self.fill_btn)
        style_layout.addRow("Stroke:", self.stroke_btn)
        style_layout.addRow("Width:", self.width_spin)

        layout.addWidget(style_group)

        # Debug Controls (only shown if DEBUG_ENABLED)
        if DEBUG_ENABLED:
            debug_group = QGroupBox("Debug Controls")
            debug_layout = QVBoxLayout(debug_group)

            self.toggle_debug_btn = QPushButton("Disable Debug Output")
            self.toggle_debug_btn.clicked.connect(self._toggle_debug)
            debug_layout.addWidget(self.toggle_debug_btn)

            self.reset_tracker_btn = QPushButton("Reset Recursion Tracker")
            self.reset_tracker_btn.clicked.connect(lambda: TRACKER.reset())
            debug_layout.addWidget(self.reset_tracker_btn)

            layout.addWidget(debug_group)

        # Instructions
        inst_group = QGroupBox("Instructions")
        inst_layout = QVBoxLayout(inst_group)
        inst_text = QLabel(
            "• Click polygon to show vertices\n"
            "• Click vertex to show bezier handles\n"
            "• Right-click vertex: Change type\n"
            "• Delete key: Remove vertex\n"
            "• Ctrl+I: Add vertex at midpoint\n"
            "• Drag handles to adjust curves"
        )
        inst_text.setWordWrap(True)
        inst_layout.addWidget(inst_text)
        layout.addWidget(inst_group)

        layout.addStretch()
        return widget

    def _connect_signals(self):
        """Connect signals."""
        debug_print("_connect_signals()")
        self.add_ellipse_btn.clicked.connect(lambda: self.canvas.add_primitive(PrimitiveType.ELLIPSE))
        self.add_rect_btn.clicked.connect(lambda: self.canvas.add_primitive(PrimitiveType.RECTANGLE))
        self.add_poly_btn.clicked.connect(lambda: self.canvas.add_primitive(PrimitiveType.POLYGON))
        self.remove_btn.clicked.connect(self._remove_selected)

        # Use lambdas to avoid issues with decorated methods as slots
        self.canvas.shape_modified.connect(lambda: self._update_primitives_list())
        self.canvas.primitive_selected.connect(lambda prim_id: self._update_primitives_list())

        self.fill_btn.clicked.connect(self._choose_fill)
        self.stroke_btn.clicked.connect(self._choose_stroke)
        self.width_spin.valueChanged.connect(self._update_width)

        self.prim_list.itemSelectionChanged.connect(lambda: self._on_list_selection())

    def _toggle_debug(self):
        """Toggle debug output on/off at runtime."""
        global DEBUG_ENABLED
        DEBUG_ENABLED = not DEBUG_ENABLED
        TRACKER.enabled = DEBUG_ENABLED
        if hasattr(self, 'toggle_debug_btn'):
            self.toggle_debug_btn.setText(
                "Disable Debug Output" if DEBUG_ENABLED else "Enable Debug Output"
            )
        print(f"Debug output: {'ENABLED' if DEBUG_ENABLED else 'DISABLED'}")

    def _update_primitives_list(self):
        """Update primitives list."""
        debug_print("ShapeEditorDemo._update_primitives_list()")
        # Block signals to prevent recursion from itemSelectionChanged
        self.prim_list.blockSignals(True)
        try:
            self.prim_list.clear()
            for prim in self.canvas.get_primitives_list():
                text = f"{prim['type'].title()}"
                if prim['vertex_count'] > 0:
                    text += f" ({prim['vertex_count']} vertices)"
                item = QListWidgetItem(text)
                item.setData(Qt.ItemDataRole.UserRole, prim['id'])
                self.prim_list.addItem(item)
                if prim['selected']:
                    item.setSelected(True)
        finally:
            self.prim_list.blockSignals(False)

    def _on_list_selection(self):
        """Handle list selection."""
        debug_print("ShapeEditorDemo._on_list_selection()")
        items = self.prim_list.selectedItems()
        if items:
            prim_id = items[0].data(Qt.ItemDataRole.UserRole)
            debug_print(f"  Selected from list: {prim_id[:8]}...")
            self.canvas.select_primitive(prim_id)

    def _remove_selected(self):
        """Remove selected primitive."""
        if self.canvas.selected_primitive_id:
            self.canvas.remove_primitive(self.canvas.selected_primitive_id)

    def _choose_fill(self):
        """Choose fill color."""
        if self.canvas.selected_primitive_id:
            color = QColorDialog.getColor()
            if color.isValid():
                self.canvas.update_primitive_style(self.canvas.selected_primitive_id, fill_color=color)

    def _choose_stroke(self):
        """Choose stroke color."""
        if self.canvas.selected_primitive_id:
            color = QColorDialog.getColor()
            if color.isValid():
                self.canvas.update_primitive_style(self.canvas.selected_primitive_id, stroke_color=color)

    def _update_width(self, width):
        """Update stroke width."""
        if self.canvas.selected_primitive_id:
            self.canvas.update_primitive_style(self.canvas.selected_primitive_id, stroke_width=width)


if __name__ == '__main__':
    print("="*60)
    if DEBUG_ENABLED:
        print("DEBUG MODE ENABLED")
        print("Set DEBUG_ENABLED = False at top of file to disable")
        print("Or use the 'Disable Debug Output' button in the UI")
        print("Recursion tracking will detect infinite loops")
        print("Set breakpoint on 'raise RecursionError' line to catch in debugger")
    else:
        print("Debug mode disabled")
        print("Set DEBUG_ENABLED = True at top of file to enable")
    print("="*60)

    app = QApplication([])
    demo = ShapeEditorDemo()
    demo.show()
    app.exec()
