"""
Topology canvas for visual network editing.

Uses Qt's Graphics View Framework for efficient rendering
and interaction handling. Includes visual port indicators
on each node that can be selected and connected.
"""

import math
import logging
from typing import Optional, List
from PyQt6.QtCore import Qt, QPointF, QRectF, pyqtSignal, QLineF, QTimer, QObject
from PyQt6.QtGui import (
    QPainter, QPen, QBrush, QColor, QFont, QPainterPath,
    QPolygonF, QTransform, QWheelEvent, QMouseEvent, QKeyEvent
)
from PyQt6.QtWidgets import (
    QGraphicsView, QGraphicsScene, QGraphicsItem,
    QGraphicsEllipseItem, QGraphicsPathItem, QGraphicsTextItem,
    QGraphicsRectItem, QApplication, QToolTip, QMenu
)

from models import NodeType, MediumType, ChannelType, PortType, Position, NetworkModel, NodeModel, LinkModel, PortConfig

# Setup logger for this module
logger = logging.getLogger(__name__)


# Color scheme
COLORS = {
    NodeType.HOST: QColor("#4A90D9"),      # Blue
    NodeType.ROUTER: QColor("#7B68EE"),    # Purple  
    NodeType.SWITCH: QColor("#50C878"),    # Green
    NodeType.STATION: QColor("#FF9500"),   # Orange for WiFi station
    NodeType.ACCESS_POINT: QColor("#FF3B30"), # Red for access point
    "link_p2p": QColor("#6B7280"),         # Gray
    "link_csma": QColor("#F59E0B"),        # Orange
    "link_wifi": QColor("#06B6D4"),        # Cyan for WiFi
    "selection": QColor("#3B82F6"),        # Bright blue
    "hover": QColor("#60A5FA"),            # Light blue
    "grid": QColor("#E5E7EB"),             # Light gray
    "background": QColor("#FAFAFA"),       # Off-white
    "port_available": QColor("#9CA3AF"),   # Gray
    "port_connected": QColor("#10B981"),   # Green
    "port_disabled": QColor("#EF4444"),    # Red
    "port_selected": QColor("#F59E0B"),    # Orange/Yellow
    "port_hover": QColor("#60A5FA"),       # Light blue
    "app_indicator": QColor("#E91E63"),    # Pink for app indicator badge
    # Route visualization colors
    "route_path": QColor("#22C55E"),       # Green for route paths
    "route_default": QColor("#3B82F6"),    # Blue for default routes
    "route_highlight": QColor("#F59E0B"),  # Orange for highlighted routes
    # Medium type colors (for wireless indicator)
    MediumType.WIRED: QColor("#4A90D9"),       # Blue (same as host)
    MediumType.WIFI_STATION: QColor("#06B6D4"), # Cyan
    MediumType.WIFI_AP: QColor("#8B5CF6"),     # Violet
    MediumType.LTE_UE: QColor("#EC4899"),      # Pink
    MediumType.LTE_ENB: QColor("#F97316"),     # Orange
}


class PortGraphicsItem(QGraphicsEllipseItem):
    """
    Visual representation of a port on a node.
    
    Shows port type abbreviation (E, FE, 1G, 10G, S, FO, W) inside the port.
    Can be clicked to select the port or dragged to create a link.
    Displays assigned IP address as a small label next to the port.
    """
    
    PORT_RADIUS = 10  # Larger to fit text
    
    # Port type to label mapping
    PORT_TYPE_LABELS = {
        PortType.ETHERNET: "E",
        PortType.FAST_ETHERNET: "FE",
        PortType.GIGABIT_ETHERNET: "1G",
        PortType.TEN_GIGABIT: "10G",
        PortType.SERIAL: "S",
        PortType.FIBER: "FO",
        PortType.WIRELESS: "W",
    }
    
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
        
        # Create label for port type
        self._label = QGraphicsTextItem(self)
        self._update_label()
        
        # Create IP address label (positioned outside port)
        self._ip_label = QGraphicsTextItem(self)
        self._ip_label.setVisible(False)
        self._update_ip_label()
        
        # Enable interactions
        self.setAcceptHoverEvents(True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, False)
        self.setZValue(10)  # Above node
        
        self._update_appearance()
    
    def _update_label(self):
        """Update the port type label text."""
        label_text = self.PORT_TYPE_LABELS.get(self.port.port_type, "?")
        self._label.setPlainText(label_text)
        
        # Style the label
        font = QFont("SF Pro Display", 6)
        font.setWeight(QFont.Weight.Bold)
        self._label.setFont(font)
        self._label.setDefaultTextColor(QColor("white"))
        
        # Center the label
        label_rect = self._label.boundingRect()
        self._label.setPos(-label_rect.width() / 2, -label_rect.height() / 2)
    
    def _update_ip_label(self):
        """Update the IP address label."""
        # Get IP to display (prefer assigned_ip from simulation, fall back to configured)
        ip = self.port.assigned_ip or self.port.ip_address
        
        if ip:
            self._ip_label.setPlainText(ip)
            self._ip_label.setVisible(True)
            
            # Style - small monospace font
            font = QFont("Consolas", 7)
            self._ip_label.setFont(font)
            self._ip_label.setDefaultTextColor(QColor("#1F2937"))  # Dark gray
            
            # Position label outside the port, away from node center
            label_rect = self._ip_label.boundingRect()
            
            # Calculate offset direction (away from node center)
            offset_distance = self.PORT_RADIUS + 3
            offset_x = math.cos(self._angle) * offset_distance
            offset_y = math.sin(self._angle) * offset_distance
            
            # Adjust position based on angle to avoid overlap
            if abs(math.cos(self._angle)) > 0.7:  # More horizontal
                if math.cos(self._angle) > 0:  # Right side
                    self._ip_label.setPos(offset_x, -label_rect.height() / 2)
                else:  # Left side
                    self._ip_label.setPos(offset_x - label_rect.width(), -label_rect.height() / 2)
            else:  # More vertical
                if math.sin(self._angle) > 0:  # Bottom
                    self._ip_label.setPos(-label_rect.width() / 2, offset_y)
                else:  # Top
                    self._ip_label.setPos(-label_rect.width() / 2, offset_y - label_rect.height())
        else:
            self._ip_label.setVisible(False)
    
    def set_assigned_ip(self, ip: str):
        """Set the assigned IP address and update display."""
        self.port.assigned_ip = ip
        self._update_ip_label()
    
    def clear_assigned_ip(self):
        """Clear the assigned IP address."""
        self.port.assigned_ip = ""
        self._update_ip_label()
    
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
        
        # Update label color for better contrast
        if self._is_selected or self._is_hovered:
            self._label.setDefaultTextColor(QColor("white"))
        elif not self.port.enabled:
            self._label.setDefaultTextColor(QColor("#FECACA"))  # Light red
        elif self.port.is_connected:
            self._label.setDefaultTextColor(QColor("white"))
        else:
            self._label.setDefaultTextColor(QColor("white"))
    
    def update_from_model(self):
        """Update appearance from the port model (call after port type changes)."""
        self._update_label()
        self._update_ip_label()
        self._update_appearance()
    
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
        port_type_name = self.port.port_type.name.replace('_', ' ').title()
        tooltip = f"{self.port.display_name} ({port_type_name})"
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
        """Handle mouse press - select port on left click, start link on right click."""
        if event.button() == Qt.MouseButton.LeftButton:
            # Notify scene of port selection
            scene = self.scene()
            if scene and isinstance(scene, TopologyScene):
                scene.on_port_clicked(self)
            event.accept()
        elif event.button() == Qt.MouseButton.RightButton:
            # Start link creation from this port
            scene = self.scene()
            if scene and isinstance(scene, TopologyScene):
                if not self.port.is_connected:
                    scene.start_link_from_port(self)
            event.accept()
        else:
            event.ignore()



class NodeGraphicsItem(QGraphicsEllipseItem):
    """
    Visual representation of a network node with port indicators.
    
    Supports selection, dragging, and shows ports around the edge.
    Shows "App" indicator when node has an application script.
    Double-click opens the Socket Application Editor.
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
        
        # Port graphics items (regular network ports)
        self._port_items: dict[str, PortGraphicsItem] = {}
        
        # App indicator (shown when node has an application script)
        self._app_indicator: Optional[QGraphicsRectItem] = None
        self._app_indicator_label: Optional[QGraphicsTextItem] = None
        
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
        self._update_app_indicator()
        
        # State
        self._is_hovered = False
    
    def _setup_appearance(self):
        """Set up colors and pen."""
        color = COLORS[self.node_model.node_type]
        self.setBrush(QBrush(color))
        self.setPen(QPen(color.darker(120), 2))
    
    def _update_app_indicator(self):
        """Show or hide the 'py' indicator based on node's app_script."""
        has_app = self.node_model.has_app_script
        
        if has_app and not self._app_indicator:
            # Create the app indicator (small badge centered below the icon, inside the node)
            badge_width = 20
            badge_height = 12
            badge_y = 10  # Below the icon (which is centered at 0)
            
            # Create the pink rectangle
            self._app_indicator = QGraphicsRectItem(
                -badge_width / 2,  # Centered horizontally
                badge_y,
                badge_width, badge_height, self
            )
            self._app_indicator.setBrush(QBrush(QColor("#E91E63")))  # Pink
            self._app_indicator.setPen(QPen(QColor("#C2185B"), 1))
            self._app_indicator.setZValue(10)  # On top
            
            # Create "py" label as child of self (not the rect) for proper positioning
            self._app_indicator_label = QGraphicsTextItem("py", self)
            font = QFont("SF Mono", 7)
            font.setWeight(QFont.Weight.Bold)
            self._app_indicator_label.setFont(font)
            self._app_indicator_label.setDefaultTextColor(QColor("white"))
            self._app_indicator_label.setZValue(11)  # Above the rectangle
            
            # Center label over the badge
            label_rect = self._app_indicator_label.boundingRect()
            self._app_indicator_label.setPos(
                -label_rect.width() / 2,
                badge_y + (badge_height - label_rect.height()) / 2
            )
        elif not has_app and self._app_indicator:
            # Remove the indicator and label
            scene = self.scene()
            if scene:
                try:
                    scene.removeItem(self._app_indicator)
                except:
                    pass
                try:
                    if self._app_indicator_label:
                        scene.removeItem(self._app_indicator_label)
                except:
                    pass
            self._app_indicator = None
            self._app_indicator_label = None
    
    def update_app_indicator(self):
        """Public method to refresh the app indicator."""
        self._update_app_indicator()
    
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
        scene = self.scene()
        for port_item in list(self._port_items.values()):
            if scene:
                try:
                    scene.removeItem(port_item)
                except (RuntimeError, AttributeError):
                    pass  # Item already removed
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
        """Get character icon for node type and medium."""
        # Base icon from node type
        base = {
            NodeType.HOST: "H",
            NodeType.ROUTER: "R",
            NodeType.SWITCH: "S",
            NodeType.STATION: "📶",     # WiFi station
            NodeType.ACCESS_POINT: "AP", # Access point
        }.get(self.node_model.node_type, "?")
        
        # Add wireless indicator for non-wired medium (legacy support)
        medium = getattr(self.node_model, 'medium_type', MediumType.WIRED)
        if medium == MediumType.WIFI_STATION:
            return "📶"  # WiFi station
        elif medium == MediumType.WIFI_AP:
            return "📡"  # Access point
        elif medium == MediumType.LTE_UE:
            return "📱"  # Mobile device
        elif medium == MediumType.LTE_ENB:
            return "🗼"  # Cell tower
        
        return base
    
    def get_port_item(self, port_id: str) -> Optional[PortGraphicsItem]:
        """Get the graphics item for a specific port."""
        return self._port_items.get(port_id)
    
    def update_label(self):
        """Update label text from model."""
        self._label.setPlainText(self.node_model.name)
        label_rect = self._label.boundingRect()
        self._label.setPos(-label_rect.width() / 2, self.NODE_RADIUS + 8)
    
    def update_appearance(self):
        """Update visual appearance when node type or medium changes."""
        # Get color based on medium type (if wireless) or node type
        medium = getattr(self.node_model, 'medium_type', MediumType.WIRED)
        if medium != MediumType.WIRED and medium in COLORS:
            color = COLORS[medium]
        else:
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
        # Check if port count changed - if so, recreate all
        if len(self._port_items) != len(self.node_model.ports):
            self._create_port_indicators()
            return
        
        # Update existing port appearances (including labels for type changes)
        for port_item in self._port_items.values():
            port_item.update_from_model()
    
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
    
    def mouseDoubleClickEvent(self, event):
        """Handle double-click - open script editor."""
        scene = self.scene()
        if scene and isinstance(scene, TopologyScene):
            scene.nodeDoubleClicked.emit(self.node_model.id)
        event.accept()
    
    def contextMenuEvent(self, event):
        """Show context menu for node - allows quick medium type selection."""
        scene = self.scene()
        if not scene or not isinstance(scene, TopologyScene):
            return
        
        # Check if we're in link creation mode (port selected) - if so, don't show menu
        if scene._link_source_port is not None:
            return
        
        menu = QMenu()
        menu.setStyleSheet("""
            QMenu {
                background: white;
                border: 1px solid #D1D5DB;
                border-radius: 8px;
                padding: 4px;
            }
            QMenu::item {
                padding: 6px 20px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background: #EBF5FF;
            }
        """)
        
        # Medium type submenu
        medium_menu = menu.addMenu("Set Medium Type")
        
        current_medium = getattr(self.node_model, 'medium_type', MediumType.WIRED)
        
        medium_options = [
            ("Wired (Ethernet/P2P)", MediumType.WIRED),
            ("WiFi Station", MediumType.WIFI_STATION),
            ("WiFi Access Point", MediumType.WIFI_AP),
            ("LTE User Equipment", MediumType.LTE_UE),
            ("LTE eNodeB", MediumType.LTE_ENB),
        ]
        
        for label, medium_type in medium_options:
            action = medium_menu.addAction(label)
            action.setCheckable(True)
            action.setChecked(medium_type == current_medium)
            action.setData(medium_type)
            action.triggered.connect(lambda checked, mt=medium_type: self._set_medium_type(mt))
        
        menu.exec(event.screenPos())
    
    def _set_medium_type(self, medium_type: MediumType):
        """Set the medium type and update appearance."""
        self.node_model.medium_type = medium_type
        self.update_appearance()
        
        # Notify scene
        scene = self.scene()
        if scene and isinstance(scene, TopologyScene):
            scene.mediumTypeChanged.emit(self.node_model.id, medium_type)
    
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
        
        # State - must be initialized before _setup_appearance
        self._is_hovered = False
        self._route_highlighted = False
        self._is_default_route = False
        
        # Visual setup
        self._setup_appearance()
        self._update_path()
    
    def _setup_appearance(self):
        """Set up colors and pen."""
        if self._route_highlighted:
            # Route highlight appearance
            color = COLORS["route_default"] if self._is_default_route else COLORS["route_path"]
            self.setPen(QPen(color, 5, Qt.PenStyle.SolidLine, 
                            Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        elif self.link_model.channel_type == ChannelType.POINT_TO_POINT:
            color = COLORS["link_p2p"]
            self.setPen(QPen(color, 3, Qt.PenStyle.SolidLine, 
                            Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        elif self.link_model.channel_type == ChannelType.WIFI:
            color = COLORS["link_wifi"]
            self.setPen(QPen(color, 3, Qt.PenStyle.DotLine, 
                            Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        else:
            color = COLORS["link_csma"]
            self.setPen(QPen(color, 3, Qt.PenStyle.SolidLine, 
                            Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    
    def set_route_highlight(self, highlighted: bool, is_default: bool = False):
        """Set route highlighting state."""
        self._route_highlighted = highlighted
        self._is_default_route = is_default
        self._setup_appearance()
        self.update()
    
    def set_activity(self, active: bool, direction: str = 'both'):
        """
        Set link activity state for visual feedback during simulation.
        
        Args:
            active: Whether the link is currently active
            direction: 'forward', 'reverse', or 'both'
        """
        if not hasattr(self, '_activity_state'):
            self._activity_state = False
            self._activity_timer = None
        
        self._activity_state = active
        
        if active:
            # Highlight link with activity color
            activity_color = QColor("#F59E0B")  # Orange for activity
            pen = QPen(activity_color, 6, Qt.PenStyle.SolidLine,
                      Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
            self.setPen(pen)
            # Keep z-order at -1 (behind nodes) - don't bring to front
        else:
            # Restore normal appearance
            self._setup_appearance()
        
        self.update()
    
    def flash_activity(self, duration_ms: int = 1500):
        """
        Flash the link to indicate activity - retriggerable one-shot.
        
        Each call resets the timer, so rapid packets keep the link highlighted.
        The link stays highlighted for duration_ms after the LAST packet.
        
        Args:
            duration_ms: Duration to stay highlighted after last trigger (default 1.5s)
        """
        from PyQt6.QtCore import QTimer
        
        # Initialize timer if needed
        if not hasattr(self, '_flash_timer'):
            self._flash_timer = None
        
        # Set active state (highlight the link)
        self.set_activity(True)
        
        # Stop existing timer if running (retriggerable behavior)
        if self._flash_timer is not None:
            self._flash_timer.stop()
            self._flash_timer.deleteLater()
        
        # Create new timer - this resets the countdown
        self._flash_timer = QTimer()
        self._flash_timer.setSingleShot(True)
        self._flash_timer.timeout.connect(self._on_flash_timeout)
        self._flash_timer.start(duration_ms)
    
    def _on_flash_timeout(self):
        """Handle flash timer expiration."""
        self.set_activity(False)
        if hasattr(self, '_flash_timer') and self._flash_timer:
            self._flash_timer.deleteLater()
            self._flash_timer = None
    
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
        if not self._route_highlighted:
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
    mediumTypeChanged = pyqtSignal(str, object)  # node_id, new_medium_type
    nodeDoubleClicked = pyqtSignal(str)  # node_id - for opening script editor
    
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
    
    def add_node(self, node_model: NodeModel):
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
        try:
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
        except Exception as e:
            print(f"Error in TopologyScene.add_link: {e}")
            import traceback
            traceback.print_exc()
            return None
    
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
    
    def flash_link_by_nodes(self, source_name: str, target_name: str, duration_ms: int = 300):
        """
        Flash link(s) between two nodes by their names.
        
        Args:
            source_name: Name of source node
            target_name: Name of target node
            duration_ms: Duration of flash in milliseconds
        """
        # Find nodes by name
        source_node_id = None
        target_node_id = None
        
        for node_id, node in self.network_model.nodes.items():
            if node.name == source_name:
                source_node_id = node_id
            elif node.name == target_name:
                target_node_id = node_id
        
        if not source_node_id or not target_node_id:
            return
        
        # Find and flash link(s) between these nodes
        for link_id, link_item in self._link_items.items():
            link = link_item.link_model
            if ((link.source_node_id == source_node_id and link.target_node_id == target_node_id) or
                (link.source_node_id == target_node_id and link.target_node_id == source_node_id)):
                link_item.flash_activity(duration_ms)
    
    def flash_links_for_node(self, node_name: str, duration_ms: int = 300):
        """
        Flash all links connected to a node by name.
        
        Args:
            node_name: Name of the node
            duration_ms: Duration of flash in milliseconds
        """
        # Find node by name
        node_id = None
        for nid, node in self.network_model.nodes.items():
            if node.name == node_name:
                node_id = nid
                break
        
        if not node_id:
            return
        
        # Flash all links connected to this node
        for link_id, link_item in self._link_items.items():
            link = link_item.link_model
            if link.source_node_id == node_id or link.target_node_id == node_id:
                link_item.flash_activity(duration_ms)
    
    def _get_links_for_path(self, path: list) -> list:
        """
        Get all link items along a path of nodes.
        
        Args:
            path: List of node IDs forming the path
            
        Returns:
            List of LinkGraphicsItem objects along the path
        """
        if len(path) < 2:
            return []
        
        links = []
        for i in range(len(path) - 1):
            node_a = path[i]
            node_b = path[i + 1]
            
            # Find link between these two nodes
            for link_id, link_item in self._link_items.items():
                link = link_item.link_model
                if ((link.source_node_id == node_a and link.target_node_id == node_b) or
                    (link.source_node_id == node_b and link.target_node_id == node_a)):
                    links.append(link_item)
                    break
        
        return links
    
    def flash_path(self, source_name: str, target_name: str, duration_ms: int = 1500):
        """
        Flash all links along the path from source to target node.
        
        This traces the full route through any intermediate nodes (switches, routers)
        and highlights all links simultaneously.
        
        Args:
            source_name: Name of source node
            target_name: Name of target node  
            duration_ms: Duration of flash in milliseconds (retriggerable)
        """
        logger.debug(f"flash_path called: source='{source_name}', target='{target_name}'")
        
        # Find node IDs by name
        source_id = None
        target_id = None
        
        for node_id, node in self.network_model.nodes.items():
            if node.name == source_name:
                source_id = node_id
                logger.debug(f"Found source node: {source_id}")
            if node.name == target_name:
                target_id = node_id
                logger.debug(f"Found target node: {target_id}")
        
        if not source_id or not target_id:
            logger.debug(f"Missing source or target, falling back to flash_links_for_node")
            self.flash_links_for_node(source_name, duration_ms)
            return
        
        # Find path between nodes using BFS
        if source_id == target_id:
            path = [source_id]
            logger.debug(f"Source equals target, path: {path}")
        else:
            # Build adjacency list from links
            adjacency = {}
            for nid in self.network_model.nodes:
                adjacency[nid] = []
            
            for link in self.network_model.links.values():
                if link.source_node_id in adjacency:
                    adjacency[link.source_node_id].append(link.target_node_id)
                if link.target_node_id in adjacency:
                    adjacency[link.target_node_id].append(link.source_node_id)
            
            logger.debug(f"Adjacency list: {adjacency}")
            
            # BFS to find shortest path
            from collections import deque
            queue = deque([(source_id, [source_id])])
            visited = {source_id}
            path = []
            
            while queue:
                current, current_path = queue.popleft()
                logger.debug(f"BFS visiting: {current}, path: {current_path}")
                
                for neighbor in adjacency.get(current, []):
                    if neighbor == target_id:
                        path = current_path + [neighbor]
                        logger.debug(f"Found path: {path}")
                        break
                    if neighbor not in visited:
                        visited.add(neighbor)
                        queue.append((neighbor, current_path + [neighbor]))
                
                if path:
                    break
        
        if not path:
            logger.debug(f"No path found, falling back to flash_links_for_node")
            self.flash_links_for_node(source_name, duration_ms)
            return
        
        # Get all links along the path and flash them
        links = self._get_links_for_path(path)
        logger.debug(f"Got {len(links)} links to flash for path {path}")
        
        if links:
            for link_item in links:
                link_item.flash_activity(duration_ms)
        else:
            logger.debug(f"No links found for path, falling back to flash_links_for_node")
            self.flash_links_for_node(source_name, duration_ms)
    
    def flash_path_by_ip(self, source_ip: str, target_ip: str, duration_ms: int = 1500):
        """
        Flash all links along the path from source IP to target IP.
        
        Looks up nodes by their assigned IP addresses.
        
        Args:
            source_ip: Source IP address (e.g., "10.1.1.1")
            target_ip: Target IP address (e.g., "10.1.1.2")
            duration_ms: Duration of flash in milliseconds
        """
        # Find nodes by assigned IP
        source_name = None
        target_name = None
        
        for node in self.network_model.nodes.values():
            for port in node.ports:
                if port.assigned_ip == source_ip:
                    source_name = node.name
                elif port.assigned_ip == target_ip:
                    target_name = node.name
        
        if source_name and target_name:
            self.flash_path(source_name, target_name, duration_ms)
    
    def clear_all_link_activity(self):
        """Reset all links to normal appearance."""
        for link_item in self._link_items.values():
            link_item.set_activity(False)
    
    def set_node_ip(self, node_name: str, ip_address: str):
        """
        Set the assigned IP address for a node's connected port.
        
        Args:
            node_name: Name of the node
            ip_address: IP address to assign (e.g., "10.1.1.1")
        """
        # Find node by name
        for node_id, node in self.network_model.nodes.items():
            if node.name == node_name:
                node_item = self._node_items.get(node_id)
                if node_item:
                    # Set IP on the first connected port
                    for port in node.ports:
                        if port.is_connected:
                            port.assigned_ip = ip_address
                            # Update the graphics
                            port_item = node_item.get_port_item(port.id)
                            if port_item:
                                port_item.set_assigned_ip(ip_address)
                            break
                return
    
    def clear_all_assigned_ips(self):
        """Clear all assigned IP addresses from all nodes."""
        for node_id, node in self.network_model.nodes.items():
            for port in node.ports:
                port.assigned_ip = ""
            node_item = self._node_items.get(node_id)
            if node_item:
                for port_item in node_item._port_items.values():
                    port_item.clear_assigned_ip()
    
    def update_links_for_node(self, node_id: str):
        """Update all links connected to a node."""
        for link_item in self._link_items.values():
            if (link_item.link_model.source_node_id == node_id or 
                link_item.link_model.target_node_id == node_id):
                link_item.update_position()
    
    def on_port_clicked(self, port_item):
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
    
    def start_link_from_port(self, port_item):
        """Start creating a link from a port."""
        # PY ports can't start new links (they're targets only)
        if hasattr(port_item, 'is_py_port') and port_item.is_py_port:
            return
        
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
        try:
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
        except Exception as e:
            print(f"Error in finish_link_at_port: {e}")
            import traceback
            traceback.print_exc()
            self.cancel_link_creation()
            return None
    
    def finish_link_at_node(self, target_node: NodeGraphicsItem) -> Optional[LinkModel]:
        """Finish creating a link at a node (auto-select port)."""
        try:
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
        except Exception as e:
            print(f"Error in finish_link_at_node: {e}")
            import traceback
            traceback.print_exc()
            self.cancel_link_creation()
            return None
    
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
    
    # Route visualization
    def show_routes_from_node(self, node_id: str):
        """Highlight all routes from a specific node."""
        self.clear_route_highlights()
        
        node = self.network_model.get_node(node_id)
        if not node:
            return
        
        # Switches don't have routing tables
        if node.node_type == NodeType.SWITCH:
            return
        
        from models import RoutingMode
        
        # Highlight outgoing routes
        for route in node.routing_table:
            if not route.enabled:
                continue
            
            # Find links that would carry traffic for this route
            path_links = self._find_path_for_route(node_id, route)
            for link_id in path_links:
                if link_id in self._link_items:
                    self._link_items[link_id].set_route_highlight(True, route.is_default_route)
    
    def show_routes_to_node(self, target_node_id: str):
        """Highlight routes from all nodes that can reach this node."""
        self.clear_route_highlights()
        
        target_node = self.network_model.get_node(target_node_id)
        if not target_node:
            return
        
        # Find all hosts that have routes to this node's networks
        for node_id, node in self.network_model.nodes.items():
            if node_id == target_node_id:
                continue
            
            # Check if this node can reach the target
            path_links = self._find_path_between_nodes(node_id, target_node_id)
            for link_id in path_links:
                if link_id in self._link_items:
                    self._link_items[link_id].set_route_highlight(True, False)
    
    def show_all_routes(self):
        """Show all configured routes in the network."""
        self.clear_route_highlights()
        
        from models import RoutingMode
        
        for node_id, node in self.network_model.nodes.items():
            # Skip switches - they don't have routing tables
            if node.node_type == NodeType.SWITCH:
                continue
            
            if node.routing_mode != RoutingMode.MANUAL:
                continue
            
            for route in node.routing_table:
                if not route.enabled:
                    continue
                
                path_links = self._find_path_for_route(node_id, route)
                for link_id in path_links:
                    if link_id in self._link_items:
                        self._link_items[link_id].set_route_highlight(True, route.is_default_route)
    
    def clear_route_highlights(self):
        """Clear all route highlighting."""
        for link_item in self._link_items.values():
            link_item.set_route_highlight(False, False)
    
    def _find_path_for_route(self, source_node_id: str, route) -> list:
        """Find link IDs that would be used for a route."""
        path_links = []
        
        # For direct routes, find the link on the specified interface
        if route.is_direct:
            # Find link connected to this interface
            interface_idx = route.interface
            current_iface = 0
            
            for link_id, link in self.network_model.links.items():
                if link.source_node_id == source_node_id:
                    if current_iface == interface_idx:
                        path_links.append(link_id)
                        break
                    current_iface += 1
                elif link.target_node_id == source_node_id:
                    if current_iface == interface_idx:
                        path_links.append(link_id)
                        break
                    current_iface += 1
        else:
            # For gateway routes, find link to gateway
            gateway = route.gateway
            
            # Find the link that connects to the gateway
            for link_id, link in self.network_model.links.items():
                # Check link endpoints to see if gateway is reachable
                link_idx = list(self.network_model.links.keys()).index(link_id)
                source_ip = f"10.1.{link_idx + 1}.1"
                target_ip = f"10.1.{link_idx + 1}.2"
                
                if link.source_node_id == source_node_id and target_ip == gateway:
                    path_links.append(link_id)
                    break
                elif link.target_node_id == source_node_id and source_ip == gateway:
                    path_links.append(link_id)
                    break
        
        return path_links
    
    def _find_path_between_nodes(self, source_id: str, target_id: str) -> list:
        """Find links on the path between two nodes (simple BFS)."""
        from collections import deque
        
        if source_id == target_id:
            return []
        
        # Build adjacency list
        adjacency = {}
        for node_id in self.network_model.nodes:
            adjacency[node_id] = []
        
        for link_id, link in self.network_model.links.items():
            adjacency[link.source_node_id].append((link.target_node_id, link_id))
            adjacency[link.target_node_id].append((link.source_node_id, link_id))
        
        # BFS to find path
        visited = {source_id}
        queue = deque([(source_id, [])])
        
        while queue:
            current, path = queue.popleft()
            
            for neighbor, link_id in adjacency.get(current, []):
                if neighbor == target_id:
                    return path + [link_id]
                
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, path + [link_id]))
        
        return []


class RouteOverlayItem(QGraphicsPathItem):
    """Overlay item for showing route paths."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._is_default = False
        self._setup_appearance()
    
    def _setup_appearance(self):
        color = COLORS["route_path"]
        pen = QPen(color, 4, Qt.PenStyle.DashLine)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        self.setPen(pen)
        self.setZValue(-0.5)  # Between links and nodes
    
    def set_is_default_route(self, is_default: bool):
        self._is_default = is_default
        color = COLORS["route_default"] if is_default else COLORS["route_path"]
        pen = self.pen()
        pen.setColor(color)
        self.setPen(pen)


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
        self._link_start_button = None  # Track which button started link creation
        
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
        elif event.button() == Qt.MouseButton.LeftButton:
            # Check if clicking on a port to start link creation
            scene_pos = self.mapToScene(event.pos())
            items = self.topology_scene.items(scene_pos)
            
            port_item = None
            for item in items:
                # Check for any port type (regular or app)
                if isinstance(item, PortGraphicsItem):
                    port_item = item
                    break
            
            if port_item:
                # Check if it's a PY port (can't start links from PY ports)
                is_py = hasattr(port_item, 'is_py_port') and port_item.is_py_port
                if not is_py and not port_item.port.is_connected:
                    self.topology_scene.start_link_from_port(port_item)
                    self._is_creating_link = True
                    self._link_start_button = Qt.MouseButton.LeftButton
                    event.accept()
                    return
            
            # Let default handling proceed (node selection, dragging, etc.)
            super().mousePressEvent(event)
        elif event.button() == Qt.MouseButton.RightButton:
            # Right-click for link creation
            scene_pos = self.mapToScene(event.pos())
            items = self.topology_scene.items(scene_pos)
            
            port_item = None
            node_item = None
            
            for item in items:
                if isinstance(item, PortGraphicsItem):
                    port_item = item
                    break
                elif isinstance(item, NodeGraphicsItem):
                    node_item = item
            
            if port_item:
                is_py = hasattr(port_item, 'is_py_port') and port_item.is_py_port
                if not is_py and not port_item.port.is_connected:
                    self.topology_scene.start_link_from_port(port_item)
                    self._is_creating_link = True
                    self._link_start_button = Qt.MouseButton.RightButton
                event.accept()
            elif node_item:
                available_ports = node_item.node_model.get_available_ports()
                if available_ports:
                    p_item = node_item.get_port_item(available_ports[0].id)
                    if p_item:
                        self.topology_scene.start_link_from_port(p_item)
                        self._is_creating_link = True
                        self._link_start_button = Qt.MouseButton.RightButton
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
             (event.button() == self._link_start_button or 
              event.button() in (Qt.MouseButton.LeftButton, Qt.MouseButton.RightButton)):
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
            self._link_start_button = None
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
                self._link_start_button = None
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
