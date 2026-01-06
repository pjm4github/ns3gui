"""
Models package.

This package contains all data models for the ns-3 GUI application.

V1 Base Models:
- Network topology (NodeModel, LinkModel, NetworkModel)
- Simulation configuration (TrafficFlow, SimulationConfig)
- Project management (Project, ProjectManager)

V2 Grid Extensions:
- Grid node types (GridNodeType, GridNodeConfig, SubstationModel)
- Grid link types (GridLinkType, GridLinkConfig)
- Grid traffic patterns (GridTrafficClass, GridTrafficConfig, PollingSchedule)
- Failure injection (FailureEvent, FailureScenario)
"""

# ============================================================================
# V1 Base Models
# ============================================================================

from .network import (
    NodeType,
    MediumType,
    ChannelType,
    PortType,
    VlanMode,
    RoutingMode,
    ProtocolStack,
    NodeBehavior,
    RouteType,
    RouteEntry,
    Position,
    PortConfig,
    NodeModel,
    LinkModel,
    ApplicationConfig,
    NetworkModel,
    PORT_TYPE_SPECS,
    DEFAULT_PORT_CONFIGS,
)
from .simulation import (
    SimulationStatus,
    SimulationStats,
    SimulationState,
    TrafficProtocol,
    TrafficApplication,
    TrafficFlow,
    SimulationConfig,
    FlowStats,
    SimulationResults,
)
from .project import (
    ProjectState,
    SimulationRun,
    ProjectMetadata,
    Project,
    ProjectManager,
)

# ============================================================================
# V2 Grid Extensions
# ============================================================================

# Grid Nodes (extends NodeModel)
from .grid_nodes import (
    GridNodeType,
    GridNodeRole,
    GridProtocol,
    ScanClass,
    VoltageLevel,
    DNP3Config,
    IEC61850Config,
    GridNodeModel,      # Subclass of NodeModel - use directly
    SubstationModel,
    GRID_NODE_DEFAULTS,
)

# Grid Links (extends LinkModel)
from .grid_links import (
    GridLinkType,
    LinkReliabilityClass,
    LinkOwnership,
    WirelessParams,
    CellularParams,
    SatelliteParams,
    GridLinkModel,      # Subclass of LinkModel - use directly
    GRID_LINK_DEFAULTS,
)

# Grid Traffic (extends TrafficFlow)
from .grid_traffic import (
    GridTrafficClass,
    GridTrafficPriority,
    DNP3FunctionCode,
    DNP3ObjectGroup,
    DNP3MessageConfig,
    GOOSEMessageConfig,
    GridTrafficFlow,    # Subclass of TrafficFlow - use directly
    PollingSchedule,
    PollingGroup,
    TrafficProfile,
    QoSConfig,
    GRID_TRAFFIC_DEFAULTS,
    TRAFFIC_CLASS_DEFAULTS,
    TRAFFIC_PATTERNS,
)

# Failure Events
from .failure_events import (
    FailureEventType,
    FailureEventState,
    FailureSeverity,
    FailureCategory,
    FailureEventParameters,
    FailureEvent,
    CascadingFailureRule,
    FailureScenario,
    SCENARIO_TEMPLATES,
    create_single_link_failure,
    create_node_power_loss,
    create_cascading_failure,
    create_network_partition,
    create_control_center_failover,
    create_dos_attack,
)

# Shape Definitions (Custom Node Shapes)
from .shape_definition import (
    PrimitiveType,
    PointType,
    EdgeType,
    ControlPoint,
    Edge,
    ShapePrimitive,
    ShapeConnector,
    ShapeStyle,
    ShapeDefinition,
    ShapeLibrary,
)


__all__ = [
    # ===== V1 Base Models =====
    # Network
    "NodeType",
    "MediumType",
    "ChannelType",
    "PortType",
    "VlanMode",
    "RoutingMode",
    "ProtocolStack",
    "NodeBehavior",
    "RouteType",
    "RouteEntry",
    "Position",
    "PortConfig",
    "NodeModel",
    "LinkModel",
    "ApplicationConfig",
    "NetworkModel",
    "PORT_TYPE_SPECS",
    "DEFAULT_PORT_CONFIGS",
    # Simulation
    "SimulationStatus",
    "SimulationStats",
    "SimulationState",
    "TrafficProtocol",
    "TrafficApplication",
    "TrafficFlow",
    "SimulationConfig",
    "FlowStats",
    "SimulationResults",
    # Project
    "ProjectState",
    "SimulationRun",
    "ProjectMetadata",
    "Project",
    "ProjectManager",
    
    # ===== V2 Grid Extensions =====
    # Grid Nodes (extends NodeModel)
    "GridNodeType",
    "GridNodeRole",
    "GridProtocol",
    "ScanClass",
    "VoltageLevel",
    "DNP3Config",
    "IEC61850Config",
    "GridNodeModel",
    "SubstationModel",
    "GRID_NODE_DEFAULTS",
    # Grid Links (extends LinkModel)
    "GridLinkType",
    "LinkReliabilityClass",
    "LinkOwnership",
    "WirelessParams",
    "CellularParams",
    "SatelliteParams",
    "GridLinkModel",
    "GRID_LINK_DEFAULTS",
    # Grid Traffic (extends TrafficFlow)
    "GridTrafficClass",
    "GridTrafficPriority",
    "DNP3FunctionCode",
    "DNP3ObjectGroup",
    "DNP3MessageConfig",
    "GOOSEMessageConfig",
    "GridTrafficFlow",
    "PollingSchedule",
    "PollingGroup",
    "TrafficProfile",
    "QoSConfig",
    "GRID_TRAFFIC_DEFAULTS",
    "TRAFFIC_CLASS_DEFAULTS",
    "TRAFFIC_PATTERNS",
    # Failure Events
    "FailureEventType",
    "FailureEventState",
    "FailureSeverity",
    "FailureCategory",
    "FailureEventParameters",
    "FailureEvent",
    "CascadingFailureRule",
    "FailureScenario",
    "SCENARIO_TEMPLATES",
    "create_single_link_failure",
    "create_node_power_loss",
    "create_cascading_failure",
    "create_network_partition",
    "create_control_center_failover",
    "create_dos_attack",
    # Shape Definitions (Custom Node Shapes)
    "PrimitiveType",
    "PointType",
    "EdgeType",
    "ControlPoint",
    "Edge",
    "ShapePrimitive",
    "ShapeConnector",
    "ShapeStyle",
    "ShapeDefinition",
    "ShapeLibrary",
]
