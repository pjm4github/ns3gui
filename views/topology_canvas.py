"""
Topology canvas for visual network editing.

Uses Qt's Graphics View Framework for efficient rendering
and interaction handling. Includes visual port indicators
on each node that can be selected and connected.
"""

import math
from typing import Optional, List
from PyQt6.QtCore import Qt, QPointF, QRectF, pyqtSignal, QLineF, QTimer, QObject
from PyQt6.QtGui import (
    QPainter, QPen, QBrush, QColor, QFont, QPainterPath,
    QPolygonF, QTransform, QWheelEvent, QMouseEvent, QKeyEvent
)
from PyQt6.QtWidgets import (
    QGraphicsView, QGraphicsScene, QGraphicsItem,
    QGraphicsEllipseItem, QGraphicsPathItem, QGraphicsTextItem,
    QGraphicsRectItem, QApplication, QToolTip
)

from models import NodeType, ChannelType, Position, NetworkModel, NodeModel, LinkModel, PortConfig


# Color scheme
COLORS = {
    NodeType.HOST: QColor("#4A90D9"),      # Blue
    NodeType.ROUTER: QColor("#7B68EE"),    # Purple  
    NodeType.SWITCH: QColor("#50C878"),    # Green
    "link_p2p": QColor("#6B7280"),         # Gray
    "link_csma": QColor("#F59E0B"),        # Orange
    "selection": QColor("#3B82F6"),        # Bright blue
    "hover": QColor("#60A5FA"),            # Light blue
    "grid": QColor("#E5E7EB"),             # Light gray
    "background": QColor("#FAFAFA"),       # Off-white
    "port_available": QColor("#9CA3AF"),   # Gray
    "port_connected": QColor("#10B981"),   # Green
    "port_disabled": QColor("#EF4444"),    # Red
    "port_selected": QColor("#F59E0B"),    # Orange/Yellow
    "port_hover": QColor("#60A5FA"),       # Light blue
}


class PortGraphicsItem(QGraphicsEllipseItem):
    """
    Visual representation of a port on a node.
    
    Small circle that can be clicked to select the port
    or dragged to create a link.
    """
    
    PORT_RADIUS = 6
    
    def __init__(self, port: PortConfig, angle: float, node_radius: float, 
                 parent: 'NodeGraphicsItem'):
        # Position port on the edge of the node
        self._angle = angle
        self._node_radius = node_radius
        x = math.cos(angle) * node_radius
        y = math.sin(angle) * node_radius
        
        super().__init__(
            -self.PORT_RADIUS, -self.PORT_RADIUS,
            self.PORT_RADIUS * 2, self.PORT_RADIUS * 2,
            parent
        )
        self.setPos(x, y)
        
        self.port = port
        self.parent_node = parent
        self._is_hovered = False
        self._is_selected = False
        
        # Enable interactions
        self.setAcceptHoverEvents(True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, False)
        self.setZValue(10)  # Above node
        
        self._update_appearance()
    
    def _update_appearance(self):
        """Update color based on port state."""
        if self._is_selected:
            color = COLORS["port_selected"]
        elif self._is_hovered:
            color = COLORS["port_hover"]
        elif not self.port.enabled:
            color = COLORS["port_disabled"]
        elif self.port.is_connected:
            color = COLORS["port_connected"]
        else:
            color = COLORS["port_available"]
        
        self.setBrush(QBrush(color))
        self.setPen(QPen(color.darker(120), 1))
    
    def set_selected(self, selected: bool):
        """Set selection state."""
        self._is_selected = selected
        self._update_appearance()
    
    def get_scene_center(self) -> QPointF:
        """Get the center point in scene coordinates."""
        return self.scenePos()
    
    def hoverEnterEvent(self, event):
        """Handle hover enter."""
        self._is_hovered = True
        self._update_appearance()
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        
        # Show tooltip with port info
        tooltip = f"{self.port.display_name}"
        if self.port.ip_address:
            tooltip += f"\n{self.port.ip_address}"
        if self.port.is_connected:
            tooltip += "\n(connected)"
        QToolTip.showText(event.screenPos(), tooltip)
        
        super().hoverEnterEvent(event)
    
    def hoverLeaveEvent(self, event):
        """Handle hover leave."""
        self._is_hovered = False
        self._update_appearance()
        self.unsetCursor()
        QToolTip.hideText()
        super().hoverLeaveEvent(event)
    
    def mousePressEvent(self, event):
        """Handle mouse press - select port on left click."""
        if event.button() == Qt.MouseButton.LeftButton:
            # Notify scene of port selection
            scene = self.scene()
            if scene and isinstance(scene, TopologyScene):
                scene.on_port_clicked(self)
            event.accept()
        else:
            # Let other buttons (including right-click) propagate to parent/canvas
            event.ignore()


class NodeGraphicsItem(QGraphicsEllipseItem):
    """
    Visual representation of a network node with port indicators.
    
    Supports selection, dragging, and shows ports around the edge.
    """
    
    NODE_RADIUS = 35
    
    def __init__(self, node_model: NodeModel, parent: Optional[QGraphicsItem] = None):
        super().__init__(
            -self.NODE_RADIUS, -self.NODE_RADIUS,
            self.NODE_RADIUS * 2, self.NODE_RADIUS * 2,
            parent
        )
        self.node_model = node_model
        self.setPos(node_model.position.x, node_model.position.y)
        
        # Port graphics items
        self._port_items: dict[str, PortGraphicsItem] = {}
        
        # Enable interactions
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setAcceptHoverEvents(True)
        
        # Visual setup
        self._setup_appearance()
        self._create_label()
        self._create_icon()
        self._create_port_indicators()
        
        # State
        self._is_hovered = False
    
    def _setup_appearance(self):
        """Set up colors and pen."""
        color = COLORS[self.node_model.node_type]
        self.setBrush(QBrush(color))
        self.setPen(QPen(color.darker(120), 2))
    
    def _create_label(self):
        """Create the node name label."""
        self._label = QGraphicsTextItem(self.node_model.name, self)
        font = QFont("SF Pro Display", 9)
        font.setWeight(QFont.Weight.Medium)
        self._label.setFont(font)
        self._label.setDefaultTextColor(QColor("#374151"))
        
        # Center label below node
        label_rect = self._label.boundingRect()
        self._label.setPos(-label_rect.width() / 2, self.NODE_RADIUS + 8)
    
    def _create_icon(self):
        """Create icon indicating node type."""
        self._icon = QGraphicsTextItem(self._get_icon_char(), self)
        font = QFont("SF Pro Display", 14)
        font.setWeight(QFont.Weight.Bold)
        self._icon.setFont(font)
        self._icon.setDefaultTextColor(QColor("white"))
        
        # Center icon in node
        icon_rect = self._icon.boundingRect()
        self._icon.setPos(-icon_rect.width() / 2, -icon_rect.height() / 2)
    
    def _create_port_indicators(self):
        """Create visual indicators for each port."""
        # Clear existing port items
        for port_item in self._port_items.values():
            self.scene().removeItem(port_item) if self.scene() else None
        self._port_items.clear()
        
        num_ports = len(self.node_model.ports)
        if num_ports == 0:
            return
        
        # Distribute ports evenly around the node
        # Start from right side (-π/2) and go clockwise
        start_angle = -math.pi / 2
        
        for i, port in enumerate(self.node_model.ports):
            if num_ports == 1:
                angle = 0  # Single port on right
            else:
                # Distribute evenly
                angle = start_angle + (2 * math.pi * i / num_ports)
            
            port_item = PortGraphicsItem(port, angle, self.NODE_RADIUS, self)
            self._port_items[port.id] = port_item
    
    def _get_icon_char(self) -> str:
        """Get character icon for node type."""
        return {
            NodeType.HOST: "H",
            NodeType.ROUTER: "R",
            NodeType.SWITCH: "S",
        }.get(self.node_model.node_type, "?")
    
    def get_port_item(self, port_id: str) -> Optional[PortGraphicsItem]:
        """Get the graphics item for a specific port."""
        return self._port_items.get(port_id)
    
    def update_label(self):
        """Update label text from model."""
        self._label.setPlainText(self.node_model.name)
        label_rect = self._label.boundingRect()
        self._label.setPos(-label_rect.width() / 2, self.NODE_RADIUS + 8)
    
    def update_appearance(self):
        """Update visual appearance when node type changes."""
        # Update colors
        color = COLORS[self.node_model.node_type]
        self.setBrush(QBrush(color))
        self.setPen(QPen(color.darker(120), 2))
        
        # Update icon
        self._icon.setPlainText(self._get_icon_char())
        icon_rect = self._icon.boundingRect()
        self._icon.setPos(-icon_rect.width() / 2, -icon_rect.height() / 2)
        
        self.update()
    
    def update_ports(self):
        """Refresh port indicators to match model."""
        self._create_port_indicators()
        # Update existing port appearances
        for port_item in self._port_items.values():
            port_item._update_appearance()
    
    def itemChange(self, change: QGraphicsItem.GraphicsItemChange, value):
        """Handle item changes like position updates."""
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            # Update model position
            pos = self.pos()
            self.node_model.position.x = pos.x()
            self.node_model.position.y = pos.y()
            
            # Notify scene to update connected links
            scene = self.scene()
            if scene and isinstance(scene, TopologyScene):
                scene.update_links_for_node(self.node_model.id)
        
        return super().itemChange(change, value)
    
    def hoverEnterEvent(self, event):
        """Handle hover enter."""
        self._is_hovered = True
        self.setPen(QPen(COLORS["hover"], 3))
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        super().hoverEnterEvent(event)
    
    def hoverLeaveEvent(self, event):
        """Handle hover leave."""
        self._is_hovered = False
        color = COLORS[self.node_model.node_type]
        self.setPen(QPen(color.darker(120), 2))
        self.unsetCursor()
        super().hoverLeaveEvent(event)
    
    def paint(self, painter: QPainter, option, widget):
        """Custom paint with selection highlight."""
        # Draw selection ring
        if self.isSelected():
            painter.setPen(QPen(COLORS["selection"], 3, Qt.PenStyle.DashLine))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(self.rect().adjusted(-5, -5, 5, 5))
        
        # Draw node
        super().paint(painter, option, widget)


class LinkGraphicsItem(QGraphicsPathItem):
    """
    Visual representation of a network link between two ports.
    
    Draws a line from source port to target port.
    """
    
    def __init__(
        self, 
        link_model: LinkModel,
        source_item: NodeGraphicsItem,
        target_item: NodeGraphicsItem,
        parent: Optional[QGraphicsItem] = None
    ):
        super().__init__(parent)
        self.link_model = link_model
        self.source_item = source_item
        self.target_item = target_item
        
        # Enable selection
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setAcceptHoverEvents(True)
        
        # Visual setup
        self._setup_appearance()
        self._update_path()
        
        # State
        self._is_hovered = False
    
    def _setup_appearance(self):
        """Set up colors and pen."""
        if self.link_model.channel_type == ChannelType.POINT_TO_POINT:
            color = COLORS["link_p2p"]
        else:
            color = COLORS["link_csma"]
        
        self.setPen(QPen(color, 3, Qt.PenStyle.SolidLine, 
                        Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    
    def _update_path(self):
        """Update the path between source and target ports."""
        # Get port positions if available
        source_port_item = self.source_item.get_port_item(self.link_model.source_port_id)
        target_port_item = self.target_item.get_port_item(self.link_model.target_port_id)
        
        if source_port_item and target_port_item:
            start = source_port_item.get_scene_center()
            end = target_port_item.get_scene_center()
        else:
            # Fallback to node centers
            start = self.source_item.scenePos()
            end = self.target_item.scenePos()
        
        # Create curved path
        path = QPainterPath()
        path.moveTo(start)
        
        # Calculate control point for a subtle curve
        mid = (start + end) / 2
        dx = end.x() - start.x()
        dy = end.y() - start.y()
        
        # Perpendicular offset for curve
        length = math.sqrt(dx*dx + dy*dy)
        if length > 0:
            offset = min(length * 0.1, 30)
            # Perpendicular direction
            px = -dy / length * offset
            py = dx / length * offset
            control = QPointF(mid.x() + px, mid.y() + py)
            path.quadTo(control, end)
        else:
            path.lineTo(end)
        
        self.setPath(path)
    
    def update_position(self):
        """Update path when nodes move."""
        self._update_path()
    
    def hoverEnterEvent(self, event):
        """Handle hover enter."""
        self._is_hovered = True
        pen = self.pen()
        pen.setWidth(5)
        pen.setColor(COLORS["hover"])
        self.setPen(pen)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        super().hoverEnterEvent(event)
    
    def hoverLeaveEvent(self, event):
        """Handle hover leave."""
        self._is_hovered = False
        self._setup_appearance()
        self.unsetCursor()
        super().hoverLeaveEvent(event)
    
    def paint(self, painter: QPainter, option, widget):
        """Custom paint with selection highlight."""
        if self.isSelected():
            # Draw selection glow
            glow_pen = QPen(COLORS["selection"], 8)
            glow_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(glow_pen)
            painter.drawPath(self.path())
        
        super().paint(painter, option, widget)


class TempLinkItem(QGraphicsPathItem):
    """Temporary link shown while creating a new connection."""
    
    def __init__(self):
        super().__init__()
        self.setPen(QPen(COLORS["selection"], 2, Qt.PenStyle.DashLine))
        self.setZValue(100)  # Above everything
        self._start_pos = QPointF()
    
    def set_start(self, pos: QPointF):
        """Set the starting position."""
        self._start_pos = pos
    
    def update_end(self, end_pos: QPointF):
        """Update the end position."""
        path = QPainterPath()
        path.moveTo(self._start_pos)
        path.lineTo(end_pos)
        self.setPath(path)


class PacketAnimationItem(QGraphicsEllipseItem):
    """
    Animated packet moving along a link.
    
    Shows packet transmission/reception with smooth animation.
    """
    
    PACKET_RADIUS = 6
    
    # Colors for different packet types
    COLORS = {
        'tx': QColor("#3B82F6"),    # Blue - transmit
        'rx': QColor("#10B981"),    # Green - receive
        'drop': QColor("#EF4444"),  # Red - drop
        'default': QColor("#F59E0B"),  # Orange - default
    }
    
    def __init__(
        self, 
        source_pos: QPointF,
        target_pos: QPointF,
        packet_type: str = 'tx',
        parent: Optional[QGraphicsItem] = None
    ):
        r = self.PACKET_RADIUS
        super().__init__(-r, -r, r * 2, r * 2, parent)
        
        self._source_pos = source_pos
        self._target_pos = target_pos
        self._progress = 0.0
        
        # Visual setup
        color = self.COLORS.get(packet_type, self.COLORS['default'])
        self.setBrush(QBrush(color))
        self.setPen(QPen(color.darker(120), 1))
        self.setZValue(50)  # Above links, below UI elements
        
        # Start at source
        self.setPos(source_pos)
        
        # Animation
        self._animation_timer: Optional[QTimer] = None
        self._animation_duration_ms = 300
        self._animation_start_time = 0
    
    @property
    def progress(self) -> float:
        return self._progress
    
    @progress.setter
    def progress(self, value: float):
        """Set position along path (0.0 = source, 1.0 = target)."""
        self._progress = max(0.0, min(1.0, value))
        
        # Interpolate position
        x = self._source_pos.x() + (self._target_pos.x() - self._source_pos.x()) * self._progress
        y = self._source_pos.y() + (self._target_pos.y() - self._source_pos.y()) * self._progress
        self.setPos(x, y)
    
    def animate(self, duration_ms: int = 300, on_complete: Optional[callable] = None):
        """Animate packet from source to target."""
        self._animation_duration_ms = duration_ms
        self._on_complete = on_complete
        self._animation_elapsed = 0
        
        self._animation_timer = QTimer()
        self._animation_timer.timeout.connect(self._animate_step)
        self._animation_timer.start(16)  # ~60fps
    
    def _animate_step(self):
        """Advance animation one step."""
        self._animation_elapsed += 16
        t = self._animation_elapsed / self._animation_duration_ms
        
        if t >= 1.0:
            self.progress = 1.0
            self._animation_timer.stop()
            self._animation_timer = None
            if self._on_complete:
                self._on_complete(self)
        else:
            # Ease in-out
            t = t * t * (3 - 2 * t)
            self.progress = t
    
    def stop_animation(self):
        """Stop ongoing animation."""
        if self._animation_timer:
            self._animation_timer.stop()
            self._animation_timer = None


class PacketAnimationManager(QObject):
    """
    Manages multiple packet animations on the canvas.
    
    Coordinates packet creation, animation, and cleanup.
    """
    
    def __init__(self, scene: 'TopologyScene', parent: Optional[QObject] = None):
        super().__init__(parent)
        self._scene = scene
        self._active_packets: List[PacketAnimationItem] = []
        self._max_packets = 50  # Limit for performance
        self._enabled = True
        self._animation_speed = 1.0
    
    @property
    def enabled(self) -> bool:
        return self._enabled
    
    @enabled.setter
    def enabled(self, value: bool):
        self._enabled = value
        if not value:
            self.clear_all()
    
    @property
    def animation_speed(self) -> float:
        return self._animation_speed
    
    @animation_speed.setter
    def animation_speed(self, value: float):
        self._animation_speed = max(0.1, min(10.0, value))
    
    def animate_packet(
        self,
        source_node_id: str,
        target_node_id: str,
        packet_type: str = 'tx',
        duration_ms: int = 300
    ):
        """
        Create and animate a packet between two nodes.
        
        Args:
            source_node_id: Source node ID
            target_node_id: Target node ID
            packet_type: Type of packet (tx, rx, drop)
            duration_ms: Animation duration
        """
        if not self._enabled:
            return
        
        # Get node positions
        source_item = self._scene._node_items.get(source_node_id)
        target_item = self._scene._node_items.get(target_node_id)
        
        if not source_item or not target_item:
            return
        
        source_pos = source_item.scenePos()
        target_pos = target_item.scenePos()
        
        # Limit active packets
        if len(self._active_packets) >= self._max_packets:
            self._remove_oldest()
        
        # Create packet
        packet = PacketAnimationItem(source_pos, target_pos, packet_type)
        self._scene.addItem(packet)
        self._active_packets.append(packet)
        
        # Adjust duration for speed
        adjusted_duration = int(duration_ms / self._animation_speed)
        
        # Animate
        packet.animate(adjusted_duration, self._on_packet_complete)
    
    def animate_packet_on_link(
        self,
        link_id: str,
        direction: str = 'forward',  # 'forward' or 'backward'
        packet_type: str = 'tx',
        duration_ms: int = 300
    ):
        """
        Animate a packet along a specific link.
        
        Args:
            link_id: Link ID
            direction: Animation direction
            packet_type: Type of packet
            duration_ms: Animation duration
        """
        if not self._enabled:
            return
        
        link_item = self._scene._link_items.get(link_id)
        if not link_item:
            return
        
        if direction == 'forward':
            source_pos = link_item.source_item.scenePos()
            target_pos = link_item.target_item.scenePos()
        else:
            source_pos = link_item.target_item.scenePos()
            target_pos = link_item.source_item.scenePos()
        
        # Limit active packets
        if len(self._active_packets) >= self._max_packets:
            self._remove_oldest()
        
        # Create and animate packet
        packet = PacketAnimationItem(source_pos, target_pos, packet_type)
        self._scene.addItem(packet)
        self._active_packets.append(packet)
        
        adjusted_duration = int(duration_ms / self._animation_speed)
        packet.animate(adjusted_duration, self._on_packet_complete)
    
    def _on_packet_complete(self, packet: PacketAnimationItem):
        """Handle packet animation completion."""
        if packet in self._active_packets:
            self._active_packets.remove(packet)
        self._scene.removeItem(packet)
    
    def _remove_oldest(self):
        """Remove oldest packet to make room."""
        if self._active_packets:
            packet = self._active_packets.pop(0)
            packet.stop_animation()
            self._scene.removeItem(packet)
    
    def clear_all(self):
        """Remove all active packets."""
        for packet in self._active_packets[:]:
            packet.stop_animation()
            self._scene.removeItem(packet)
        self._active_packets.clear()


class TopologyScene(QGraphicsScene):
    """
    Scene managing all network topology items.
    
    Handles node/link creation, deletion, and selection.
    """
    
    # Signals
    nodeAdded = pyqtSignal(object)       # NodeModel
    nodeRemoved = pyqtSignal(str)        # node_id
    linkAdded = pyqtSignal(object)       # LinkModel
    linkRemoved = pyqtSignal(str)        # link_id
    portSelected = pyqtSignal(object, object)  # NodeModel, PortConfig
    
    def __init__(self, network_model: NetworkModel, parent=None):
        super().__init__(parent)
        self.network_model = network_model
        
        # Graphics items tracking
        self._node_items: dict[str, NodeGraphicsItem] = {}
        self._link_items: dict[str, LinkGraphicsItem] = {}
        
        # Link creation state
        self._temp_link: Optional[TempLinkItem] = None
        self._link_source_port: Optional[PortGraphicsItem] = None
        self._selected_port: Optional[PortGraphicsItem] = None
        
        # Packet animation manager
        self._animation_manager = PacketAnimationManager(self)
        
        # Setup
        self.setBackgroundBrush(COLORS["background"])
        self._draw_grid()
    
    @property
    def animation_manager(self) -> PacketAnimationManager:
        """Get the packet animation manager."""
        return self._animation_manager
    
    def _draw_grid(self):
        """Draw background grid."""
        grid_size = 50
        scene_rect = QRectF(-2000, -2000, 4000, 4000)
        self.setSceneRect(scene_rect)
        
        # Grid is drawn in canvas paintEvent
    
    def add_node(self, node_model: NodeModel) -> NodeGraphicsItem:
        """Add a node to the scene."""
        item = NodeGraphicsItem(node_model)
        self.addItem(item)
        self._node_items[node_model.id] = item
        self.nodeAdded.emit(node_model)
        return item
    
    def remove_node(self, node_id: str):
        """Remove a node from the scene."""
        if node_id in self._node_items:
            item = self._node_items.pop(node_id)
            
            # Clear any port references that point to this node's ports
            if self._selected_port and self._selected_port.parent_node == item:
                self._selected_port = None
            if self._link_source_port and self._link_source_port.parent_node == item:
                self.cancel_link_creation()
            
            self.removeItem(item)
            self.nodeRemoved.emit(node_id)
    
    def add_link(self, link_model: LinkModel) -> Optional[LinkGraphicsItem]:
        """Add a link to the scene."""
        source_item = self._node_items.get(link_model.source_node_id)
        target_item = self._node_items.get(link_model.target_node_id)
        
        if not source_item or not target_item:
            return None
        
        item = LinkGraphicsItem(link_model, source_item, target_item)
        self.addItem(item)
        item.setZValue(-1)  # Behind nodes
        self._link_items[link_model.id] = item
        
        # Update port appearances
        source_item.update_ports()
        target_item.update_ports()
        
        self.linkAdded.emit(link_model)
        return item
    
    def remove_link(self, link_id: str):
        """Remove a link from the scene."""
        if link_id in self._link_items:
            link_item = self._link_items.pop(link_id)
            
            # Update port appearances - safely check if nodes still exist
            try:
                if link_item.source_item and link_item.source_item.node_model.id in self._node_items:
                    link_item.source_item.update_ports()
                if link_item.target_item and link_item.target_item.node_model.id in self._node_items:
                    link_item.target_item.update_ports()
            except (RuntimeError, AttributeError):
                pass  # Items were deleted
            
            self.removeItem(link_item)
            self.linkRemoved.emit(link_id)
    
    def get_node_item(self, node_id: str) -> Optional[NodeGraphicsItem]:
        """Get node graphics item by ID."""
        return self._node_items.get(node_id)
    
    def get_link_item(self, link_id: str) -> Optional[LinkGraphicsItem]:
        """Get link graphics item by ID."""
        return self._link_items.get(link_id)
    
    def update_links_for_node(self, node_id: str):
        """Update all links connected to a node."""
        for link_item in self._link_items.values():
            if (link_item.link_model.source_node_id == node_id or 
                link_item.link_model.target_node_id == node_id):
                link_item.update_position()
    
    def on_port_clicked(self, port_item: PortGraphicsItem):
        """Handle port selection."""
        # Deselect previous port
        if self._selected_port and self._selected_port != port_item:
            try:
                self._selected_port.set_selected(False)
            except (RuntimeError, AttributeError):
                pass  # Previous port was deleted
        
        # Select new port
        self._selected_port = port_item
        port_item.set_selected(True)
        
        # Emit signal with node and port
        node_model = port_item.parent_node.node_model
        self.portSelected.emit(node_model, port_item.port)
    
    def start_link_from_port(self, port_item: PortGraphicsItem):
        """Start creating a link from a port."""
        if port_item.port.is_connected:
            return  # Can't start from connected port
        
        self._link_source_port = port_item
        
        # Create temporary link visual
        self._temp_link = TempLinkItem()
        self._temp_link.set_start(port_item.get_scene_center())
        self.addItem(self._temp_link)
    
    def update_temp_link(self, scene_pos: QPointF):
        """Update temporary link end position."""
        if self._temp_link:
            self._temp_link.update_end(scene_pos)
    
    def finish_link_at_port(self, target_port: PortGraphicsItem) -> Optional[LinkModel]:
        """Finish creating a link at a target port."""
        if not self._link_source_port or not self._temp_link:
            return None
        
        source_port = self._link_source_port
        
        # Validate
        if source_port == target_port:
            self.cancel_link_creation()
            return None
        
        if source_port.parent_node == target_port.parent_node:
            self.cancel_link_creation()
            return None
        
        if target_port.port.is_connected:
            self.cancel_link_creation()
            return None
        
        # Create link in model
        source_node = source_port.parent_node.node_model
        target_node = target_port.parent_node.node_model
        
        link = self.network_model.add_link(
            source_node.id, 
            target_node.id,
            source_port_id=source_port.port.id,
            target_port_id=target_port.port.id
        )
        
        if link:
            self.add_link(link)
        
        self.cancel_link_creation()
        return link
    
    def finish_link_at_node(self, target_node: NodeGraphicsItem) -> Optional[LinkModel]:
        """Finish creating a link at a node (auto-select port)."""
        if not self._link_source_port or not self._temp_link:
            return None
        
        source_port = self._link_source_port
        source_node = source_port.parent_node.node_model
        target_node_model = target_node.node_model
        
        if source_node.id == target_node_model.id:
            self.cancel_link_creation()
            return None
        
        # Create link in model (will auto-select available port)
        link = self.network_model.add_link(
            source_node.id,
            target_node_model.id,
            source_port_id=source_port.port.id
        )
        
        if link:
            self.add_link(link)
        
        self.cancel_link_creation()
        return link
    
    def cancel_link_creation(self):
        """Cancel the current link creation."""
        if self._temp_link:
            self.removeItem(self._temp_link)
            self._temp_link = None
        self._link_source_port = None
    
    def clear_port_selection(self):
        """Clear the selected port."""
        if self._selected_port:
            try:
                self._selected_port.set_selected(False)
            except (RuntimeError, AttributeError):
                pass  # Port was deleted
            self._selected_port = None
    
    def delete_selected(self):
        """Delete all selected items."""
        for item in self.selectedItems():
            if isinstance(item, NodeGraphicsItem):
                # Remove from model first (handles link cleanup)
                self.network_model.remove_node(item.node_model.id)
                # Remove links from scene
                links_to_remove = [
                    lid for lid, litem in self._link_items.items()
                    if litem.source_item == item or litem.target_item == item
                ]
                for lid in links_to_remove:
                    self.remove_link(lid)
                # Remove node
                self.remove_node(item.node_model.id)
            elif isinstance(item, LinkGraphicsItem):
                self.network_model.remove_link(item.link_model.id)
                self.remove_link(item.link_model.id)
    
    def clear_topology(self):
        """Clear all nodes and links."""
        for link_id in list(self._link_items.keys()):
            self.remove_link(link_id)
        for node_id in list(self._node_items.keys()):
            self.remove_node(node_id)
        self.network_model.clear()


class TopologyCanvas(QGraphicsView):
    """
    Main canvas widget for viewing and editing the network topology.
    
    Provides zooming, panning, and interaction handling.
    """
    
    # Signals
    itemSelected = pyqtSignal(object)  # NodeModel, LinkModel, or None
    portSelected = pyqtSignal(object, object)  # NodeModel, PortConfig
    
    def __init__(self, network_model: NetworkModel, parent=None):
        super().__init__(parent)
        
        # Create scene
        self.topology_scene = TopologyScene(network_model)
        self.setScene(self.topology_scene)
        
        # Connect scene signals
        self.topology_scene.portSelected.connect(self.portSelected)
        
        # View settings
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        
        # State
        self._zoom_factor = 1.0
        self._is_panning = False
        self._last_pan_pos = QPointF()
        self._is_creating_link = False
        
        # Connect selection changes
        self.topology_scene.selectionChanged.connect(self._on_selection_changed)
    
    def drawBackground(self, painter: QPainter, rect: QRectF):
        """Draw grid background."""
        super().drawBackground(painter, rect)
        
        # Draw grid
        grid_size = 50
        
        left = int(rect.left()) - (int(rect.left()) % grid_size)
        top = int(rect.top()) - (int(rect.top()) % grid_size)
        
        painter.setPen(QPen(COLORS["grid"], 1))
        
        # Vertical lines
        x = left
        while x < rect.right():
            painter.drawLine(int(x), int(rect.top()), int(x), int(rect.bottom()))
            x += grid_size
        
        # Horizontal lines
        y = top
        while y < rect.bottom():
            painter.drawLine(int(rect.left()), int(y), int(rect.right()), int(y))
            y += grid_size
    
    def add_node_at_center(self, node_type: NodeType) -> NodeGraphicsItem:
        """Add a new node at the center of the visible area."""
        center = self.mapToScene(self.viewport().rect().center())
        node = self.topology_scene.network_model.add_node(
            node_type, 
            Position(center.x(), center.y())
        )
        return self.topology_scene.add_node(node)
    
    def add_node_at_position(self, node_type: NodeType, pos: QPointF) -> NodeGraphicsItem:
        """Add a new node at a specific scene position."""
        node = self.topology_scene.network_model.add_node(
            node_type,
            Position(pos.x(), pos.y())
        )
        return self.topology_scene.add_node(node)
    
    def _on_selection_changed(self):
        """Handle selection changes."""
        selected = self.topology_scene.selectedItems()
        
        # Clear port selection when selecting other items
        self.topology_scene.clear_port_selection()
        
        if len(selected) == 1:
            item = selected[0]
            if isinstance(item, NodeGraphicsItem):
                self.itemSelected.emit(item.node_model)
            elif isinstance(item, LinkGraphicsItem):
                self.itemSelected.emit(item.link_model)
            else:
                self.itemSelected.emit(None)
        else:
            self.itemSelected.emit(None)
    
    def wheelEvent(self, event: QWheelEvent):
        """Handle zoom with mouse wheel."""
        factor = 1.15
        
        if event.angleDelta().y() > 0:
            self._zoom_factor *= factor
            self.scale(factor, factor)
        else:
            self._zoom_factor /= factor
            self.scale(1 / factor, 1 / factor)
        
        # Clamp zoom
        if self._zoom_factor < 0.1:
            self._zoom_factor = 0.1
        elif self._zoom_factor > 5:
            self._zoom_factor = 5
    
    def mousePressEvent(self, event: QMouseEvent):
        """Handle mouse press."""
        if event.button() == Qt.MouseButton.MiddleButton:
            # Pan with middle mouse
            self._is_panning = True
            self._last_pan_pos = event.position()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
        elif event.button() == Qt.MouseButton.RightButton:
            # Check if we're starting link creation
            scene_pos = self.mapToScene(event.pos())
            
            # Get all items at this position, sorted by Z-order (topmost first)
            items = self.topology_scene.items(scene_pos)
            
            # Find the first port or node
            port_item = None
            node_item = None
            
            for item in items:
                if isinstance(item, PortGraphicsItem):
                    port_item = item
                    break  # Port is topmost, use it
                elif isinstance(item, NodeGraphicsItem):
                    node_item = item
                    # Don't break - keep looking for a port
            
            if port_item:
                # Start link from specific port
                if not port_item.port.is_connected:
                    self.topology_scene.start_link_from_port(port_item)
                    self._is_creating_link = True
                event.accept()
            elif node_item:
                # Start link from node (auto-select first available port)
                available_ports = node_item.node_model.get_available_ports()
                if available_ports:
                    p_item = node_item.get_port_item(available_ports[0].id)
                    if p_item:
                        self.topology_scene.start_link_from_port(p_item)
                        self._is_creating_link = True
                event.accept()
            else:
                super().mousePressEvent(event)
        else:
            super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event: QMouseEvent):
        """Handle mouse move."""
        if self._is_panning:
            delta = event.position() - self._last_pan_pos
            self._last_pan_pos = event.position()
            
            self.horizontalScrollBar().setValue(
                self.horizontalScrollBar().value() - int(delta.x())
            )
            self.verticalScrollBar().setValue(
                self.verticalScrollBar().value() - int(delta.y())
            )
            event.accept()
        elif self._is_creating_link or self.topology_scene._temp_link:
            # Update temp link
            scene_pos = self.mapToScene(event.pos())
            self.topology_scene.update_temp_link(scene_pos)
            event.accept()
        else:
            super().mouseMoveEvent(event)
    
    def mouseReleaseEvent(self, event: QMouseEvent):
        """Handle mouse release."""
        if self._is_panning and event.button() == Qt.MouseButton.MiddleButton:
            self._is_panning = False
            self.unsetCursor()
            event.accept()
        elif (self._is_creating_link or self.topology_scene._temp_link) and \
             event.button() == Qt.MouseButton.RightButton:
            # Finish link creation
            scene_pos = self.mapToScene(event.pos())
            
            # Get all items at this position
            items = self.topology_scene.items(scene_pos)
            
            # Find the first port or node
            port_item = None
            node_item = None
            
            for item in items:
                if isinstance(item, PortGraphicsItem):
                    port_item = item
                    break  # Port is topmost, use it
                elif isinstance(item, NodeGraphicsItem):
                    node_item = item
                    # Don't break - keep looking for a port
            
            if port_item:
                self.topology_scene.finish_link_at_port(port_item)
            elif node_item:
                self.topology_scene.finish_link_at_node(node_item)
            else:
                self.topology_scene.cancel_link_creation()
            
            self._is_creating_link = False
            event.accept()
        else:
            super().mouseReleaseEvent(event)
    
    def keyPressEvent(self, event: QKeyEvent):
        """Handle keyboard shortcuts."""
        if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            self.topology_scene.delete_selected()
            event.accept()
        elif event.key() == Qt.Key.Key_Escape:
            # Cancel link creation or clear selection
            if self.topology_scene._temp_link:
                self.topology_scene.cancel_link_creation()
                self._is_creating_link = False
            else:
                self.topology_scene.clearSelection()
                self.topology_scene.clear_port_selection()
            event.accept()
        elif event.key() == Qt.Key.Key_A and event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            # Select all
            for item in self.topology_scene.items():
                if isinstance(item, (NodeGraphicsItem, LinkGraphicsItem)):
                    item.setSelected(True)
            event.accept()
        else:
            super().keyPressEvent(event)
    
    def fit_contents(self):
        """Fit view to show all items."""
        self.fitInView(self.topology_scene.itemsBoundingRect().adjusted(-50, -50, 50, 50),
                       Qt.AspectRatioMode.KeepAspectRatio)
    
    def reset_view(self):
        """Reset to default zoom and position."""
        self.resetTransform()
        self._zoom_factor = 1.0
        self.centerOn(0, 0)
