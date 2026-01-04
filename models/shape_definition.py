"""
Shape Definition Models for Custom Node Shapes.

This module defines the data structures for customizable node shapes
that can be edited visually and stored in JSON configuration files.

Key concepts:
- ShapeDefinition: Complete definition of a node shape
- ShapePrimitive: Basic geometric elements (ellipse, rectangle, polygon, path)
- ControlPoint: Editable vertices with optional bezier handles
- Edge: Connections between points (line, quadratic, cubic bezier)
- ShapeConnector: Port attachment points constrained to shape edges
- ShapeStyle: Visual appearance (colors, stroke, icon)

Multiple primitives can be combined via union to create complex shapes.
"""

from dataclasses import dataclass, field, asdict
from typing import List, Optional, Tuple, Dict, Any, Union
from enum import Enum
import uuid
import json
from pathlib import Path


# =============================================================================
# Enumerations
# =============================================================================

class PrimitiveType(Enum):
    """Types of shape primitives that can be combined."""
    ELLIPSE = "ellipse"
    RECTANGLE = "rectangle"
    POLYGON = "polygon"
    PATH = "path"  # Bezier path with curves


class PointType(Enum):
    """Types of control points."""
    CORNER = "corner"           # Sharp corner (polygon vertex)
    SMOOTH = "smooth"           # Smooth curve point (bezier, handles can differ)
    SYMMETRIC = "symmetric"     # Symmetric bezier handles (equal length/angle)
    EDGE_MIDPOINT = "edge"      # Point on edge (for subdividing)


class EdgeType(Enum):
    """Types of edges between points."""
    LINE = "line"               # Straight line segment
    QUADRATIC = "quadratic"     # Quadratic bezier (1 control point)
    CUBIC = "cubic"             # Cubic bezier (2 control points)
    ARC = "arc"                 # Circular/elliptical arc


# =============================================================================
# Helper Functions
# =============================================================================

def _generate_id() -> str:
    """Generate a short unique ID."""
    return str(uuid.uuid4())[:8]


def _clamp(value: float, min_val: float = 0.0, max_val: float = 1.0) -> float:
    """Clamp a value to a range."""
    return max(min_val, min(max_val, value))


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class ControlPoint:
    """
    A control point in a shape primitive.
    
    Coordinates are normalized (0.0 to 1.0) relative to the shape's bounding box.
    For bezier curves, handle_in/handle_out define the control handles as
    offsets relative to the point position.
    
    Attributes:
        id: Unique identifier for this point
        x: Normalized X coordinate (0.0 = left, 1.0 = right)
        y: Normalized Y coordinate (0.0 = top, 1.0 = bottom)
        point_type: Type of point (corner, smooth, symmetric)
        handle_in: Incoming bezier handle offset (dx, dy) - for curves entering this point
        handle_out: Outgoing bezier handle offset (dx, dy) - for curves leaving this point
    """
    id: str = field(default_factory=_generate_id)
    x: float = 0.5
    y: float = 0.5
    point_type: PointType = PointType.CORNER
    handle_in: Optional[Tuple[float, float]] = None
    handle_out: Optional[Tuple[float, float]] = None
    
    def __post_init__(self):
        """Validate and clamp coordinates."""
        self.x = _clamp(self.x)
        self.y = _clamp(self.y)
        if isinstance(self.point_type, str):
            self.point_type = PointType(self.point_type)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        d = {
            "id": self.id,
            "x": self.x,
            "y": self.y,
            "point_type": self.point_type.value,
        }
        if self.handle_in is not None:
            d["handle_in"] = list(self.handle_in)
        if self.handle_out is not None:
            d["handle_out"] = list(self.handle_out)
        return d
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ControlPoint':
        """Create from dictionary."""
        return cls(
            id=data.get("id", _generate_id()),
            x=data.get("x", 0.5),
            y=data.get("y", 0.5),
            point_type=PointType(data.get("point_type", "corner")),
            handle_in=tuple(data["handle_in"]) if data.get("handle_in") else None,
            handle_out=tuple(data["handle_out"]) if data.get("handle_out") else None,
        )
    
    def copy(self) -> 'ControlPoint':
        """Create a deep copy."""
        return ControlPoint(
            id=_generate_id(),  # New ID for the copy
            x=self.x,
            y=self.y,
            point_type=self.point_type,
            handle_in=self.handle_in,
            handle_out=self.handle_out,
        )


@dataclass
class Edge:
    """
    An edge connecting two control points.
    
    For bezier curves, control1 and control2 define the curve's control points
    as normalized coordinates (not offsets).
    
    Attributes:
        start_point_id: ID of the starting ControlPoint
        end_point_id: ID of the ending ControlPoint
        edge_type: Type of edge (line, quadratic, cubic, arc)
        control1: First control point for curves (x, y) normalized
        control2: Second control point for cubic bezier (x, y) normalized
    """
    start_point_id: str = ""
    end_point_id: str = ""
    edge_type: EdgeType = EdgeType.LINE
    control1: Optional[Tuple[float, float]] = None
    control2: Optional[Tuple[float, float]] = None
    
    def __post_init__(self):
        """Convert string edge_type to enum if needed."""
        if isinstance(self.edge_type, str):
            self.edge_type = EdgeType(self.edge_type)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        d = {
            "start_point_id": self.start_point_id,
            "end_point_id": self.end_point_id,
            "edge_type": self.edge_type.value,
        }
        if self.control1 is not None:
            d["control1"] = list(self.control1)
        if self.control2 is not None:
            d["control2"] = list(self.control2)
        return d
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Edge':
        """Create from dictionary."""
        return cls(
            start_point_id=data.get("start_point_id", ""),
            end_point_id=data.get("end_point_id", ""),
            edge_type=EdgeType(data.get("edge_type", "line")),
            control1=tuple(data["control1"]) if data.get("control1") else None,
            control2=tuple(data["control2"]) if data.get("control2") else None,
        )


@dataclass
class ShapePrimitive:
    """
    A single geometric primitive (ellipse, rectangle, polygon, or path).
    
    Multiple primitives can be combined via union to form complex shapes.
    Coordinates are normalized (0.0 to 1.0) relative to the shape's bounding box.
    
    Attributes:
        id: Unique identifier for this primitive
        primitive_type: Type of primitive (ellipse, rectangle, polygon, path)
        bounds: Bounding box for ellipse/rectangle (x, y, width, height) normalized
        rotation: Rotation angle in degrees (for ellipse/rectangle)
        corner_radius: Corner radius for rectangle (0 = sharp corners) normalized
        points: List of control points (for polygon/path)
        edges: Edge definitions (for path with curves; if empty, auto-connect points)
        closed: Whether the shape is closed (polygon) or open (path)
    """
    id: str = field(default_factory=_generate_id)
    primitive_type: PrimitiveType = PrimitiveType.ELLIPSE
    
    # For ELLIPSE/RECTANGLE: bounding box in normalized coords
    bounds: Tuple[float, float, float, float] = (0.0, 0.0, 1.0, 1.0)  # x, y, w, h
    
    # For ELLIPSE/RECTANGLE: optional rotation in degrees
    rotation: float = 0.0
    
    # For RECTANGLE: corner radius (0 = sharp corners), normalized to min dimension
    corner_radius: float = 0.0
    
    # For POLYGON/PATH: list of control points
    points: List[ControlPoint] = field(default_factory=list)
    
    # For PATH: edges with curve definitions (if empty, auto-connect in order as lines)
    edges: List[Edge] = field(default_factory=list)
    
    # Whether this primitive is closed (polygon) or open (path segment)
    closed: bool = True
    
    def __post_init__(self):
        """Convert string primitive_type to enum if needed."""
        if isinstance(self.primitive_type, str):
            self.primitive_type = PrimitiveType(self.primitive_type)
        if isinstance(self.bounds, list):
            self.bounds = tuple(self.bounds)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        d = {
            "id": self.id,
            "primitive_type": self.primitive_type.value,
            "bounds": list(self.bounds),
            "rotation": self.rotation,
            "corner_radius": self.corner_radius,
            "closed": self.closed,
        }
        if self.points:
            d["points"] = [p.to_dict() for p in self.points]
        if self.edges:
            d["edges"] = [e.to_dict() for e in self.edges]
        return d
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ShapePrimitive':
        """Create from dictionary."""
        return cls(
            id=data.get("id", _generate_id()),
            primitive_type=PrimitiveType(data.get("primitive_type", "ellipse")),
            bounds=tuple(data.get("bounds", [0.0, 0.0, 1.0, 1.0])),
            rotation=data.get("rotation", 0.0),
            corner_radius=data.get("corner_radius", 0.0),
            points=[ControlPoint.from_dict(p) for p in data.get("points", [])],
            edges=[Edge.from_dict(e) for e in data.get("edges", [])],
            closed=data.get("closed", True),
        )
    
    def copy(self) -> 'ShapePrimitive':
        """Create a deep copy with new IDs."""
        return ShapePrimitive(
            id=_generate_id(),
            primitive_type=self.primitive_type,
            bounds=self.bounds,
            rotation=self.rotation,
            corner_radius=self.corner_radius,
            points=[p.copy() for p in self.points],
            edges=[Edge(e.start_point_id, e.end_point_id, e.edge_type, e.control1, e.control2) 
                   for e in self.edges],
            closed=self.closed,
        )
    
    @classmethod
    def create_ellipse(cls, x: float = 0.0, y: float = 0.0, 
                       w: float = 1.0, h: float = 1.0) -> 'ShapePrimitive':
        """Factory method to create an ellipse primitive."""
        return cls(
            primitive_type=PrimitiveType.ELLIPSE,
            bounds=(x, y, w, h),
        )
    
    @classmethod
    def create_rectangle(cls, x: float = 0.0, y: float = 0.0,
                         w: float = 1.0, h: float = 1.0,
                         corner_radius: float = 0.0) -> 'ShapePrimitive':
        """Factory method to create a rectangle primitive."""
        return cls(
            primitive_type=PrimitiveType.RECTANGLE,
            bounds=(x, y, w, h),
            corner_radius=corner_radius,
        )
    
    @classmethod
    def create_polygon(cls, points: List[Tuple[float, float]]) -> 'ShapePrimitive':
        """Factory method to create a polygon primitive from (x, y) tuples."""
        control_points = [
            ControlPoint(x=x, y=y, point_type=PointType.CORNER)
            for x, y in points
        ]
        return cls(
            primitive_type=PrimitiveType.POLYGON,
            points=control_points,
            closed=True,
        )
    
    @classmethod
    def create_hexagon(cls) -> 'ShapePrimitive':
        """Factory method to create a regular hexagon starting at top vertex."""
        import math
        points = []
        for i in range(6):
            # Start at top (90°) and go clockwise
            angle = math.pi / 2 - i * math.pi / 3
            x = 0.5 + 0.5 * math.cos(angle)
            y = 0.5 - 0.5 * math.sin(angle)  # Y inverted for screen coords
            points.append((x, y))
        return cls.create_polygon(points)


@dataclass
class ShapeConnector:
    """
    A port/connector attachment point on the shape edge.
    
    Position is parameterized along the unified shape edge (0.0 to 1.0 around 
    the perimeter). The actual (x, y) position and outward angle are computed
    at render time based on the shape's QPainterPath.
    
    Attributes:
        id: Unique identifier for this connector
        edge_position: Position along the edge (0.0 to 1.0, wraps around)
        label: Display label for the connector (e.g., "eth0", "N", "Primary")
        direction: Direction of the connector ("outward", "inward", or angle in degrees)
    """
    id: str = field(default_factory=_generate_id)
    edge_position: float = 0.0  # 0.0-1.0 position along unified edge
    label: str = ""
    direction: str = "outward"  # "outward", "inward", or angle like "45"
    
    def __post_init__(self):
        """Validate edge_position."""
        self.edge_position = _clamp(self.edge_position)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "edge_position": self.edge_position,
            "label": self.label,
            "direction": self.direction,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ShapeConnector':
        """Create from dictionary."""
        return cls(
            id=data.get("id", _generate_id()),
            edge_position=data.get("edge_position", 0.0),
            label=data.get("label", ""),
            direction=data.get("direction", "outward"),
        )
    
    def copy(self) -> 'ShapeConnector':
        """Create a copy with new ID."""
        return ShapeConnector(
            id=_generate_id(),
            edge_position=self.edge_position,
            label=self.label,
            direction=self.direction,
        )


@dataclass
class ShapeStyle:
    """
    Visual styling for a shape.
    
    Attributes:
        fill_color: Fill color as hex string (e.g., "#4A90D9")
        fill_opacity: Fill opacity (0.0 to 1.0)
        stroke_color: Stroke/outline color as hex string
        stroke_width: Stroke width in pixels
        stroke_opacity: Stroke opacity (0.0 to 1.0)
        icon_text: Text or emoji displayed in the center of the shape
        icon_font_family: Font family for icon text
        icon_font_size: Font size in points for icon text
        icon_color: Color for icon text as hex string
        icon_bold: Whether icon text should be bold
    """
    fill_color: str = "#4A90D9"
    fill_opacity: float = 1.0
    stroke_color: str = "#2563EB"
    stroke_width: float = 2.0
    stroke_opacity: float = 1.0
    icon_text: str = ""
    icon_font_family: str = "SF Pro Display"
    icon_font_size: int = 16
    icon_color: str = "#FFFFFF"
    icon_bold: bool = True
    
    def __post_init__(self):
        """Validate opacity values."""
        self.fill_opacity = _clamp(self.fill_opacity)
        self.stroke_opacity = _clamp(self.stroke_opacity)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "fill_color": self.fill_color,
            "fill_opacity": self.fill_opacity,
            "stroke_color": self.stroke_color,
            "stroke_width": self.stroke_width,
            "stroke_opacity": self.stroke_opacity,
            "icon_text": self.icon_text,
            "icon_font_family": self.icon_font_family,
            "icon_font_size": self.icon_font_size,
            "icon_color": self.icon_color,
            "icon_bold": self.icon_bold,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ShapeStyle':
        """Create from dictionary."""
        return cls(
            fill_color=data.get("fill_color", "#4A90D9"),
            fill_opacity=data.get("fill_opacity", 1.0),
            stroke_color=data.get("stroke_color", "#2563EB"),
            stroke_width=data.get("stroke_width", 2.0),
            stroke_opacity=data.get("stroke_opacity", 1.0),
            icon_text=data.get("icon_text", ""),
            icon_font_family=data.get("icon_font_family", "SF Pro Display"),
            icon_font_size=data.get("icon_font_size", 16),
            icon_color=data.get("icon_color", "#FFFFFF"),
            icon_bold=data.get("icon_bold", True),
        )
    
    def copy(self) -> 'ShapeStyle':
        """Create a copy."""
        return ShapeStyle.from_dict(self.to_dict())


# =============================================================================
# Simulator Node Defaults
# =============================================================================

@dataclass
class SimulatorNodeDefaults:
    """
    Default node properties for a specific simulator.
    
    This class provides an extensible way to define simulator-specific
    properties that are applied when a shape is instantiated on the canvas.
    
    The design supports multiple simulators by storing defaults in a dict
    keyed by simulator name (e.g., "ns3", "omnet", "custom").
    
    Attributes:
        simulator: Identifier for the target simulator (e.g., "ns3", "omnet")
        base_type: The fundamental node type in the simulator
            For ns-3: "host", "router", "switch", "station", "access_point"
        protocol_stack: Network stack configuration
            For ns-3: "internet" (L3 routing), "bridge" (L2 switching), "none"
        num_ports: Default number of network ports/interfaces
        port_types: Default port/interface types
            For ns-3: "ethernet", "wifi", "lte", "p2p"
        medium_type: Physical medium type
            For ns-3: "wired", "wifi_station", "wifi_ap", "lte_ue", "lte_enb"
        routing_mode: How routing is configured
            For ns-3: "auto" (GlobalRoutingHelper), "manual" (static routes)
        applications: Default applications to install
            For ns-3: list of app configs like {"type": "udp_echo_server", "port": 9}
        custom_properties: Additional simulator-specific properties
            Extensible dict for future needs
    
    Example for ns-3 host:
        SimulatorNodeDefaults(
            simulator="ns3",
            base_type="host",
            protocol_stack="internet",
            num_ports=4,
            port_types=["ethernet"],
            medium_type="wired",
            routing_mode="auto",
        )
    
    Example for ns-3 switch:
        SimulatorNodeDefaults(
            simulator="ns3",
            base_type="switch",
            protocol_stack="bridge",
            num_ports=8,
            port_types=["ethernet"],
            medium_type="wired",
            routing_mode="none",
        )
    """
    simulator: str = "ns3"
    base_type: str = "host"
    protocol_stack: str = "internet"
    num_ports: int = 4
    port_types: List[str] = field(default_factory=lambda: ["ethernet"])
    medium_type: str = "wired"
    routing_mode: str = "auto"
    applications: List[Dict[str, Any]] = field(default_factory=list)
    custom_properties: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "simulator": self.simulator,
            "base_type": self.base_type,
            "protocol_stack": self.protocol_stack,
            "num_ports": self.num_ports,
            "port_types": self.port_types,
            "medium_type": self.medium_type,
            "routing_mode": self.routing_mode,
            "applications": self.applications,
            "custom_properties": self.custom_properties,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SimulatorNodeDefaults':
        """Create from dictionary."""
        return cls(
            simulator=data.get("simulator", "ns3"),
            base_type=data.get("base_type", "host"),
            protocol_stack=data.get("protocol_stack", "internet"),
            num_ports=data.get("num_ports", 4),
            port_types=data.get("port_types", ["ethernet"]),
            medium_type=data.get("medium_type", "wired"),
            routing_mode=data.get("routing_mode", "auto"),
            applications=data.get("applications", []),
            custom_properties=data.get("custom_properties", {}),
        )
    
    def copy(self) -> 'SimulatorNodeDefaults':
        """Create a deep copy."""
        import copy as copy_module
        return SimulatorNodeDefaults(
            simulator=self.simulator,
            base_type=self.base_type,
            protocol_stack=self.protocol_stack,
            num_ports=self.num_ports,
            port_types=list(self.port_types),
            medium_type=self.medium_type,
            routing_mode=self.routing_mode,
            applications=copy_module.deepcopy(self.applications),
            custom_properties=copy_module.deepcopy(self.custom_properties),
        )
    
    @classmethod
    def for_ns3_host(cls) -> 'SimulatorNodeDefaults':
        """Create defaults for an ns-3 host node."""
        return cls(
            simulator="ns3",
            base_type="host",
            protocol_stack="internet",
            num_ports=4,
            port_types=["ethernet"],
            medium_type="wired",
            routing_mode="auto",
        )
    
    @classmethod
    def for_ns3_router(cls) -> 'SimulatorNodeDefaults':
        """Create defaults for an ns-3 router node."""
        return cls(
            simulator="ns3",
            base_type="router",
            protocol_stack="internet",
            num_ports=4,
            port_types=["ethernet"],
            medium_type="wired",
            routing_mode="auto",
        )
    
    @classmethod
    def for_ns3_switch(cls) -> 'SimulatorNodeDefaults':
        """Create defaults for an ns-3 switch node."""
        return cls(
            simulator="ns3",
            base_type="switch",
            protocol_stack="bridge",
            num_ports=8,
            port_types=["ethernet"],
            medium_type="wired",
            routing_mode="none",
        )
    
    @classmethod
    def for_ns3_wifi_station(cls) -> 'SimulatorNodeDefaults':
        """Create defaults for an ns-3 WiFi station node."""
        return cls(
            simulator="ns3",
            base_type="station",
            protocol_stack="internet",
            num_ports=1,
            port_types=["wifi"],
            medium_type="wifi_station",
            routing_mode="auto",
        )
    
    @classmethod
    def for_ns3_access_point(cls) -> 'SimulatorNodeDefaults':
        """Create defaults for an ns-3 WiFi access point node."""
        return cls(
            simulator="ns3",
            base_type="access_point",
            protocol_stack="internet",
            num_ports=2,
            port_types=["wifi", "ethernet"],
            medium_type="wifi_ap",
            routing_mode="auto",
        )


@dataclass
class ShapeDefinition:
    """
    Complete definition of a node shape.
    
    Consists of one or more primitives that are unioned together to form the
    final shape. Connectors are positioned along the unified edge.
    
    Attributes:
        id: Unique shape ID (e.g., "HOST", "RTU", "CONTROL_CENTER")
        name: Human-readable display name
        version: Version number for migration tracking
        primitives: List of primitives that make up this shape (unioned together)
        connectors: List of connector attachment points
        style: Visual styling (colors, stroke, icon)
        base_width: Default width in pixels when rendered
        base_height: Default height in pixels when rendered
        path_start_offset: Offset to align 0% with 3 o'clock position (0-1).
            This is calculated when the shape is created/modified and maps
            between the Qt path percent and our angular coordinate system.
        palette: Name of the palette group this shape belongs to (e.g., "Standard", "Grid")
        simulator_defaults: Dict mapping simulator name to SimulatorNodeDefaults.
            When a shape is dropped on the canvas, the defaults for the current
            simulator are used to initialize the node properties.
            Example: {"ns3": SimulatorNodeDefaults(base_type="switch", ...)}
        is_default: True if this is a built-in shape (not user-modified)
        modified: True if user has edited this shape from its default
    """
    id: str
    name: str
    version: int = 1
    primitives: List[ShapePrimitive] = field(default_factory=list)
    connectors: List[ShapeConnector] = field(default_factory=list)
    style: ShapeStyle = field(default_factory=ShapeStyle)
    base_width: float = 50.0
    base_height: float = 50.0
    path_start_offset: float = 0.0  # Offset to align 0% with 3 o'clock
    palette: str = "Standard"  # Palette group name
    simulator_defaults: Dict[str, SimulatorNodeDefaults] = field(default_factory=dict)
    is_default: bool = True
    modified: bool = False
    
    def get_simulator_defaults(self, simulator: str = "ns3") -> SimulatorNodeDefaults:
        """
        Get defaults for a specific simulator.
        
        Args:
            simulator: Simulator identifier (default: "ns3")
            
        Returns:
            SimulatorNodeDefaults for the simulator, or default host if not found
        """
        if simulator in self.simulator_defaults:
            return self.simulator_defaults[simulator]
        # Return default host properties if not specified
        return SimulatorNodeDefaults.for_ns3_host()
    
    def set_simulator_defaults(self, defaults: SimulatorNodeDefaults):
        """
        Set defaults for a simulator.
        
        Args:
            defaults: SimulatorNodeDefaults to store (uses defaults.simulator as key)
        """
        self.simulator_defaults[defaults.simulator] = defaults
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "name": self.name,
            "version": self.version,
            "primitives": [p.to_dict() for p in self.primitives],
            "connectors": [c.to_dict() for c in self.connectors],
            "style": self.style.to_dict(),
            "base_width": self.base_width,
            "base_height": self.base_height,
            "path_start_offset": self.path_start_offset,
            "palette": self.palette,
            "simulator_defaults": {
                sim: defaults.to_dict() 
                for sim, defaults in self.simulator_defaults.items()
            },
            "is_default": self.is_default,
            "modified": self.modified,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ShapeDefinition':
        """Create from dictionary."""
        # Parse simulator_defaults
        sim_defaults = {}
        for sim, defaults_data in data.get("simulator_defaults", {}).items():
            sim_defaults[sim] = SimulatorNodeDefaults.from_dict(defaults_data)
        
        return cls(
            id=data.get("id", ""),
            name=data.get("name", ""),
            version=data.get("version", 1),
            primitives=[ShapePrimitive.from_dict(p) for p in data.get("primitives", [])],
            connectors=[ShapeConnector.from_dict(c) for c in data.get("connectors", [])],
            style=ShapeStyle.from_dict(data.get("style", {})),
            base_width=data.get("base_width", 50.0),
            base_height=data.get("base_height", 50.0),
            path_start_offset=data.get("path_start_offset", 0.0),
            palette=data.get("palette", "Standard"),
            simulator_defaults=sim_defaults,
            is_default=data.get("is_default", True),
            modified=data.get("modified", False),
        )
    
    def copy(self) -> 'ShapeDefinition':
        """Create a deep copy."""
        return ShapeDefinition(
            id=self.id,
            name=self.name,
            version=self.version,
            primitives=[p.copy() for p in self.primitives],
            connectors=[c.copy() for c in self.connectors],
            style=self.style.copy(),
            base_width=self.base_width,
            base_height=self.base_height,
            path_start_offset=self.path_start_offset,
            palette=self.palette,
            simulator_defaults={
                sim: defaults.copy() 
                for sim, defaults in self.simulator_defaults.items()
            },
            is_default=False,  # Copy is not default
            modified=True,     # Copy is considered modified
        )
    
    def to_json(self, indent: int = 2) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)
    
    @classmethod
    def from_json(cls, json_str: str) -> 'ShapeDefinition':
        """Deserialize from JSON string."""
        return cls.from_dict(json.loads(json_str))
    
    def save_to_file(self, filepath: Union[str, Path]) -> bool:
        """Save shape definition to a JSON file."""
        try:
            path = Path(filepath)
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, 'w', encoding='utf-8') as f:
                f.write(self.to_json())
            return True
        except Exception as e:
            print(f"Error saving shape to {filepath}: {e}")
            return False
    
    @classmethod
    def load_from_file(cls, filepath: Union[str, Path]) -> Optional['ShapeDefinition']:
        """Load shape definition from a JSON file."""
        try:
            path = Path(filepath)
            with open(path, 'r', encoding='utf-8') as f:
                return cls.from_json(f.read())
        except Exception as e:
            print(f"Error loading shape from {filepath}: {e}")
            return None
    
    def get_point_by_id(self, point_id: str) -> Optional[ControlPoint]:
        """Find a control point by ID across all primitives."""
        for prim in self.primitives:
            for pt in prim.points:
                if pt.id == point_id:
                    return pt
        return None
    
    def get_connector_by_id(self, connector_id: str) -> Optional[ShapeConnector]:
        """Find a connector by ID."""
        for conn in self.connectors:
            if conn.id == connector_id:
                return conn
        return None
    
    def add_primitive(self, primitive: ShapePrimitive):
        """Add a primitive to the shape."""
        self.primitives.append(primitive)
        self.modified = True
    
    def remove_primitive(self, primitive_id: str) -> bool:
        """Remove a primitive by ID."""
        for i, prim in enumerate(self.primitives):
            if prim.id == primitive_id:
                self.primitives.pop(i)
                self.modified = True
                return True
        return False
    
    def add_connector(self, connector: ShapeConnector):
        """Add a connector to the shape."""
        self.connectors.append(connector)
        self.modified = True
    
    def remove_connector(self, connector_id: str) -> bool:
        """Remove a connector by ID."""
        for i, conn in enumerate(self.connectors):
            if conn.id == connector_id:
                self.connectors.pop(i)
                self.modified = True
                return True
        return False


# =============================================================================
# Shape Library (Collection of Shapes organized by Palette)
# =============================================================================

@dataclass
class PaletteGroup:
    """
    A group of shapes belonging to a single palette tab.
    
    Attributes:
        palette: Name of the palette (e.g., "Standard", "Grid", "Custom")
        shapes: Dictionary mapping shape ID to ShapeDefinition
    """
    palette: str
    shapes: Dict[str, ShapeDefinition] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "palette": self.palette,
            "shapes": {sid: shape.to_dict() for sid, shape in self.shapes.items()},
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PaletteGroup':
        """Create from dictionary."""
        shapes = {}
        for sid, sdata in data.get("shapes", {}).items():
            shape = ShapeDefinition.from_dict(sdata)
            shape.palette = data.get("palette", "Standard")  # Ensure palette is set
            shapes[sid] = shape
        return cls(
            palette=data.get("palette", "Standard"),
            shapes=shapes,
        )


@dataclass
class ShapeLibrary:
    """
    A collection of shape definitions organized by palette groups.
    
    Used to store and manage multiple shapes in a single JSON file,
    with shapes grouped by their palette tab.
    
    File format (version 2.0):
    {
        "version": "2.0",
        "palettes": [
            {
                "palette": "Standard",
                "shapes": {
                    "HOST": {...},
                    "ROUTER": {...}
                }
            },
            {
                "palette": "Grid",
                "shapes": {
                    "CONTROL_CENTER": {...},
                    "SUBSTATION": {...}
                }
            }
        ]
    }
    
    Attributes:
        version: File format version
        palettes: List of PaletteGroup objects
    """
    version: str = "2.0"
    palettes: List[PaletteGroup] = field(default_factory=list)
    
    @property
    def shapes(self) -> Dict[str, ShapeDefinition]:
        """Get all shapes as a flat dictionary (for backward compatibility)."""
        result = {}
        for group in self.palettes:
            result.update(group.shapes)
        return result
    
    def get_palette_names(self) -> List[str]:
        """Get list of all palette names."""
        return [group.palette for group in self.palettes]
    
    def get_palette_group(self, palette_name: str) -> Optional[PaletteGroup]:
        """Get a palette group by name."""
        for group in self.palettes:
            if group.palette == palette_name:
                return group
        return None
    
    def get_or_create_palette(self, palette_name: str) -> PaletteGroup:
        """Get or create a palette group by name."""
        group = self.get_palette_group(palette_name)
        if group is None:
            group = PaletteGroup(palette=palette_name)
            self.palettes.append(group)
        return group
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "version": self.version,
            "palettes": [group.to_dict() for group in self.palettes],
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ShapeLibrary':
        """Create from dictionary, supporting both old and new formats."""
        version = data.get("version", "1.0")
        
        # Check for new format (version 2.0 with palettes)
        if "palettes" in data:
            palettes = [PaletteGroup.from_dict(p) for p in data.get("palettes", [])]
            return cls(version="2.0", palettes=palettes)
        
        # Legacy format (version 1.0 with flat shapes dict)
        # Convert to new format by inferring palette from shape IDs
        from models.network import NodeType
        from models.grid_nodes import GridNodeType
        
        standard_ids = {nt.name for nt in NodeType}
        grid_ids = {gt.name for gt in GridNodeType}
        
        standard_group = PaletteGroup(palette="Standard")
        grid_group = PaletteGroup(palette="Grid")
        custom_group = PaletteGroup(palette="Custom")
        
        for sid, sdata in data.get("shapes", {}).items():
            shape = ShapeDefinition.from_dict(sdata)
            
            # Determine palette from shape ID or existing palette field
            if shape.palette and shape.palette != "Standard":
                palette_name = shape.palette
            elif sid in standard_ids:
                palette_name = "Standard"
            elif sid in grid_ids:
                palette_name = "Grid"
            else:
                palette_name = "Custom"
            
            shape.palette = palette_name
            
            if palette_name == "Standard":
                standard_group.shapes[sid] = shape
            elif palette_name == "Grid":
                grid_group.shapes[sid] = shape
            else:
                custom_group.shapes[sid] = shape
        
        palettes = []
        if standard_group.shapes:
            palettes.append(standard_group)
        if grid_group.shapes:
            palettes.append(grid_group)
        if custom_group.shapes:
            palettes.append(custom_group)
        
        return cls(version="2.0", palettes=palettes)
    
    def to_json(self, indent: int = 2) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)
    
    @classmethod
    def from_json(cls, json_str: str) -> 'ShapeLibrary':
        """Deserialize from JSON string."""
        return cls.from_dict(json.loads(json_str))
    
    def save_to_file(self, filepath: Union[str, Path]) -> bool:
        """Save shape library to a JSON file."""
        try:
            path = Path(filepath)
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, 'w', encoding='utf-8') as f:
                f.write(self.to_json())
            return True
        except Exception as e:
            print(f"Error saving shape library to {filepath}: {e}")
            return False
    
    @classmethod
    def load_from_file(cls, filepath: Union[str, Path]) -> Optional['ShapeLibrary']:
        """Load shape library from a JSON file."""
        try:
            path = Path(filepath)
            if not path.exists():
                return None
            with open(path, 'r', encoding='utf-8') as f:
                return cls.from_json(f.read())
        except Exception as e:
            print(f"Error loading shape library from {filepath}: {e}")
            return None
    
    def get_shape(self, shape_id: str) -> Optional[ShapeDefinition]:
        """Get a shape by ID (searches all palettes)."""
        for group in self.palettes:
            if shape_id in group.shapes:
                return group.shapes[shape_id]
        return None
    
    def add_shape(self, shape: ShapeDefinition):
        """Add or update a shape in the library, placing it in the correct palette."""
        palette_name = shape.palette or "Standard"
        group = self.get_or_create_palette(palette_name)
        group.shapes[shape.id] = shape
    
    def remove_shape(self, shape_id: str) -> bool:
        """Remove a shape by ID."""
        for group in self.palettes:
            if shape_id in group.shapes:
                del group.shapes[shape_id]
                return True
        return False
    
    def merge(self, other: 'ShapeLibrary', overwrite: bool = True):
        """
        Merge another library into this one.
        
        Args:
            other: Library to merge from
            overwrite: If True, replace existing shapes; if False, skip duplicates
        """
        for other_group in other.palettes:
            group = self.get_or_create_palette(other_group.palette)
            for sid, shape in other_group.shapes.items():
                if overwrite or sid not in group.shapes:
                    group.shapes[sid] = shape


# =============================================================================
# Export all public symbols
# =============================================================================

__all__ = [
    # Enums
    "PrimitiveType",
    "PointType",
    "EdgeType",
    # Data classes
    "ControlPoint",
    "Edge",
    "ShapePrimitive",
    "ShapeConnector",
    "ShapeStyle",
    "SimulatorNodeDefaults",
    "ShapeDefinition",
    "PaletteGroup",
    "ShapeLibrary",
]
