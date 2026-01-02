"""
Shape Renderer.

Renders ShapeDefinition objects to QPainter for use in:
- Canvas node graphics items
- Palette button previews
- Shape editor preview

This provides a unified rendering pipeline that both the canvas
and palette use, ensuring consistent appearance.
"""

from typing import Optional, Tuple, List
from PyQt6.QtCore import Qt, QRectF, QPointF
from PyQt6.QtGui import (
    QPainter, QColor, QPen, QBrush, QFont, QPainterPath,
    QPixmap, QLinearGradient, QRadialGradient
)

from models.shape_definition import ShapeDefinition, ShapeStyle
from services.shape_manager import ShapeManager, get_shape_manager


class ShapeRenderer:
    """
    Static utility class for rendering ShapeDefinition objects.
    
    Provides methods to:
    - Render shapes to a QPainter
    - Create preview pixmaps for palettes
    - Handle selection and hover states
    """
    
    # Selection/hover colors
    SELECTION_COLOR = QColor("#3B82F6")  # Blue
    HOVER_COLOR = QColor("#60A5FA")       # Lighter blue
    
    @staticmethod
    def render(painter: QPainter,
               shape: ShapeDefinition,
               rect: QRectF,
               selected: bool = False,
               hover: bool = False,
               show_connectors: bool = False,
               opacity: float = 1.0):
        """
        Render a shape definition to a QPainter.
        
        Args:
            painter: QPainter to render to
            shape: ShapeDefinition to render
            rect: Bounding rectangle for the shape
            selected: Whether the shape is selected (shows selection highlight)
            hover: Whether the mouse is hovering (shows hover highlight)
            show_connectors: Whether to show connector points
            opacity: Overall opacity (0.0 to 1.0)
        """
        painter.save()
        
        # Set opacity
        if opacity < 1.0:
            painter.setOpacity(opacity)
        
        # Get shape manager for path computation
        shape_manager = get_shape_manager()
        
        # Get the unified path for this shape
        path = shape_manager.get_unified_path(shape.id, rect.width(), rect.height())
        
        # Translate path to rect position
        painter.translate(rect.topLeft())
        
        # Draw selection/hover highlight behind shape
        if selected or hover:
            highlight_path = path
            highlight_pen = QPen(
                ShapeRenderer.SELECTION_COLOR if selected else ShapeRenderer.HOVER_COLOR,
                4.0 if selected else 3.0
            )
            highlight_pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            painter.setPen(highlight_pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(highlight_path)
        
        # Draw fill
        style = shape.style
        fill_color = QColor(style.fill_color)
        fill_color.setAlphaF(style.fill_opacity)
        painter.setBrush(QBrush(fill_color))
        
        # Draw stroke
        stroke_color = QColor(style.stroke_color)
        stroke_color.setAlphaF(style.stroke_opacity)
        pen = QPen(stroke_color, style.stroke_width)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        
        # Draw the shape path
        painter.drawPath(path)
        
        # Draw icon text
        if style.icon_text:
            ShapeRenderer._draw_icon_text(painter, path, style)
        
        # Draw connectors if requested
        if show_connectors:
            ShapeRenderer._draw_connectors(painter, shape, path, rect.width(), rect.height())
        
        painter.restore()
    
    @staticmethod
    def render_by_id(painter: QPainter,
                     shape_id: str,
                     rect: QRectF,
                     selected: bool = False,
                     hover: bool = False,
                     show_connectors: bool = False,
                     opacity: float = 1.0):
        """
        Render a shape by its ID.
        
        Convenience method that looks up the shape from the ShapeManager.
        Falls back to default ellipse if shape not found.
        
        Args:
            painter: QPainter to render to
            shape_id: ID of the shape (e.g., "HOST", "RTU")
            rect: Bounding rectangle
            selected: Selection state
            hover: Hover state
            show_connectors: Show connector points
            opacity: Overall opacity
        """
        shape_manager = get_shape_manager()
        shape = shape_manager.get_shape(shape_id)
        
        if shape:
            ShapeRenderer.render(painter, shape, rect, selected, hover, show_connectors, opacity)
        else:
            # Fallback to simple ellipse
            ShapeRenderer._render_fallback(painter, rect, selected, hover)
    
    @staticmethod
    def render_preview(shape: ShapeDefinition, size: int = 32) -> QPixmap:
        """
        Create a preview pixmap for palette buttons.
        
        Args:
            shape: ShapeDefinition to render
            size: Size of the square pixmap
            
        Returns:
            QPixmap with the rendered shape
        """
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Add small padding
        padding = 2
        rect = QRectF(padding, padding, size - 2 * padding, size - 2 * padding)
        
        ShapeRenderer.render(painter, shape, rect, selected=False, hover=False)
        
        painter.end()
        return pixmap
    
    @staticmethod
    def render_preview_by_id(shape_id: str, size: int = 32) -> QPixmap:
        """
        Create a preview pixmap for a shape by ID.
        
        Args:
            shape_id: ID of the shape
            size: Size of the square pixmap
            
        Returns:
            QPixmap with the rendered shape
        """
        shape_manager = get_shape_manager()
        shape = shape_manager.get_shape(shape_id)
        
        if shape:
            return ShapeRenderer.render_preview(shape, size)
        else:
            # Fallback pixmap
            return ShapeRenderer._create_fallback_pixmap(size)
    
    @staticmethod
    def _draw_icon_text(painter: QPainter, path: QPainterPath, style: ShapeStyle):
        """Draw the icon text centered in the shape."""
        # Get center of the path
        bounds = path.boundingRect()
        center = bounds.center()
        
        # Setup font
        font = QFont(style.icon_font_family, style.icon_font_size)
        if style.icon_bold:
            font.setWeight(QFont.Weight.Bold)
        painter.setFont(font)
        
        # Setup color
        text_color = QColor(style.icon_color)
        painter.setPen(text_color)
        
        # Measure text
        fm = painter.fontMetrics()
        text_rect = fm.boundingRect(style.icon_text)
        
        # Position text at center
        x = center.x() - text_rect.width() / 2
        y = center.y() + fm.ascent() / 2 - fm.descent() / 2
        
        painter.drawText(QPointF(x, y), style.icon_text)
    
    @staticmethod
    def _draw_connectors(painter: QPainter, shape: ShapeDefinition, 
                         path: QPainterPath, width: float, height: float):
        """Draw connector points on the shape edge."""
        shape_manager = get_shape_manager()
        
        # Connector appearance
        connector_radius = 4
        connector_color = QColor("#F59E0B")  # Amber
        connector_border = QColor("#D97706")
        
        painter.setBrush(QBrush(connector_color))
        painter.setPen(QPen(connector_border, 1.5))
        
        # Get the path start offset for coordinate conversion
        offset = shape.path_start_offset
        
        for conn in shape.connectors:
            # Convert edge_position to Qt path percent using offset
            # edge_position: 0% = right (3 o'clock), increases clockwise
            qt_percent = shape_manager.edge_to_qt_percent(conn.edge_position, offset)
            pt = path.pointAtPercent(qt_percent)
            
            # Draw connector circle
            painter.drawEllipse(
                QPointF(pt.x(), pt.y()),
                connector_radius, connector_radius
            )
    
    @staticmethod
    def _render_fallback(painter: QPainter, rect: QRectF, 
                         selected: bool = False, hover: bool = False):
        """Render a fallback ellipse when shape not found."""
        painter.save()
        
        # Selection/hover highlight
        if selected or hover:
            highlight_pen = QPen(
                ShapeRenderer.SELECTION_COLOR if selected else ShapeRenderer.HOVER_COLOR,
                4.0 if selected else 3.0
            )
            painter.setPen(highlight_pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(rect)
        
        # Default gray ellipse
        painter.setBrush(QColor("#9CA3AF"))
        painter.setPen(QPen(QColor("#6B7280"), 2))
        painter.drawEllipse(rect)
        
        # Question mark
        painter.setPen(QColor("#FFFFFF"))
        font = QFont("SF Pro Display", 16)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "?")
        
        painter.restore()
    
    @staticmethod
    def _create_fallback_pixmap(size: int) -> QPixmap:
        """Create a fallback pixmap when shape not found."""
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        padding = 2
        rect = QRectF(padding, padding, size - 2 * padding, size - 2 * padding)
        
        ShapeRenderer._render_fallback(painter, rect)
        
        painter.end()
        return pixmap


class NodeShapeRenderer:
    """
    Specialized renderer for node graphics items on the canvas.
    
    Extends ShapeRenderer with node-specific features:
    - Node labels
    - Connection ports
    - State indicators (running, error, etc.)
    """
    
    @staticmethod
    def render_node(painter: QPainter,
                    shape_id: str,
                    rect: QRectF,
                    label: str = "",
                    selected: bool = False,
                    hover: bool = False,
                    show_ports: bool = True,
                    state: str = "normal"):
        """
        Render a complete node with shape, label, and ports.
        
        Args:
            painter: QPainter to render to
            shape_id: Shape ID (e.g., "HOST", "RTU")
            rect: Bounding rectangle for the node shape
            label: Node label to display below shape
            selected: Selection state
            hover: Hover state
            show_ports: Whether to show connection ports
            state: Node state ("normal", "running", "error", "disabled")
        """
        # Get opacity based on state
        opacity = 1.0
        if state == "disabled":
            opacity = 0.5
        
        # Render the shape
        ShapeRenderer.render_by_id(
            painter, shape_id, rect,
            selected=selected,
            hover=hover,
            show_connectors=show_ports,
            opacity=opacity
        )
        
        # Draw state indicator if not normal
        if state == "running":
            NodeShapeRenderer._draw_running_indicator(painter, rect)
        elif state == "error":
            NodeShapeRenderer._draw_error_indicator(painter, rect)
        
        # Draw label below shape
        if label:
            NodeShapeRenderer._draw_label(painter, rect, label)
    
    @staticmethod
    def _draw_running_indicator(painter: QPainter, rect: QRectF):
        """Draw a green pulse indicator for running state."""
        indicator_size = 8
        indicator_pos = QPointF(
            rect.right() - indicator_size / 2,
            rect.top() - indicator_size / 2
        )
        
        painter.setBrush(QColor("#22C55E"))  # Green
        painter.setPen(QPen(QColor("#16A34A"), 1))
        painter.drawEllipse(indicator_pos, indicator_size / 2, indicator_size / 2)
    
    @staticmethod
    def _draw_error_indicator(painter: QPainter, rect: QRectF):
        """Draw a red error indicator."""
        indicator_size = 8
        indicator_pos = QPointF(
            rect.right() - indicator_size / 2,
            rect.top() - indicator_size / 2
        )
        
        painter.setBrush(QColor("#EF4444"))  # Red
        painter.setPen(QPen(QColor("#DC2626"), 1))
        painter.drawEllipse(indicator_pos, indicator_size / 2, indicator_size / 2)
    
    @staticmethod
    def _draw_label(painter: QPainter, rect: QRectF, label: str):
        """Draw node label below the shape."""
        font = QFont("SF Pro Display", 10)
        painter.setFont(font)
        painter.setPen(QColor("#374151"))
        
        # Position below shape
        label_rect = QRectF(
            rect.left() - 20,
            rect.bottom() + 2,
            rect.width() + 40,
            20
        )
        
        painter.drawText(label_rect, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop, label)


class PaletteIconRenderer:
    """
    Specialized renderer for palette button icons.
    
    Creates consistent preview icons for node type buttons
    in both standard and grid palettes.
    """
    
    @staticmethod
    def create_icon(shape_id: str, size: int = 32, 
                    fallback_color: str = "#4A90D9",
                    fallback_icon: str = "?") -> QPixmap:
        """
        Create an icon pixmap for a palette button.
        
        Uses the ShapeManager if the shape exists, otherwise
        creates a simple fallback icon.
        
        Args:
            shape_id: Shape ID to render
            size: Icon size in pixels
            fallback_color: Color to use if shape not found
            fallback_icon: Text to use if shape not found
            
        Returns:
            QPixmap with the rendered icon
        """
        shape_manager = get_shape_manager()
        shape = shape_manager.get_shape(shape_id)
        
        if shape:
            return ShapeRenderer.render_preview(shape, size)
        else:
            return PaletteIconRenderer._create_fallback_icon(
                size, fallback_color, fallback_icon
            )
    
    @staticmethod
    def _create_fallback_icon(size: int, color: str, icon_text: str) -> QPixmap:
        """Create a simple fallback icon."""
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Draw circle
        padding = 2
        rect = QRectF(padding, padding, size - 2 * padding, size - 2 * padding)
        
        painter.setBrush(QColor(color))
        darker = QColor(color).darker(120)
        painter.setPen(QPen(darker, 2))
        painter.drawEllipse(rect)
        
        # Draw text
        painter.setPen(QColor("#FFFFFF"))
        font = QFont("SF Pro Display", size // 3)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, icon_text)
        
        painter.end()
        return pixmap


# Convenience functions
def render_shape(painter: QPainter, shape_id: str, rect: QRectF, **kwargs):
    """Convenience function to render a shape by ID."""
    ShapeRenderer.render_by_id(painter, shape_id, rect, **kwargs)


def create_shape_preview(shape_id: str, size: int = 32) -> QPixmap:
    """Convenience function to create a shape preview pixmap."""
    return ShapeRenderer.render_preview_by_id(shape_id, size)
