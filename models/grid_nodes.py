"""
Electric Grid Infrastructure Node Models.

Extends the base NodeModel to support grid-specific node types including
control centers, substations, RTUs, IEDs, and communication infrastructure.
"""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional, List
import uuid

# Import V1 base classes
from .network import NodeModel, NodeType, MediumType, Position, PortConfig, PortType


class GridNodeType(Enum):
    """
    Electric grid-specific node types.
    
    These represent the functional roles of nodes in a grid SCADA/EMS system.
    """
    # Control hierarchy
    CONTROL_CENTER = auto()
    BACKUP_CONTROL_CENTER = auto()
    
    # Substation equipment
    SUBSTATION = auto()
    RTU = auto()
    IED = auto()
    DATA_CONCENTRATOR = auto()
    RELAY = auto()
    METER = auto()
    
    # Communication infrastructure
    GATEWAY = auto()
    COMM_ROUTER = auto()
    COMM_SWITCH = auto()
    COMM_TOWER = auto()
    SATELLITE_TERMINAL = auto()
    CELLULAR_GATEWAY = auto()
    
    # Special nodes
    HISTORIAN = auto()
    HMI = auto()
    
    def to_base_node_type(self) -> NodeType:
        """Map grid type to V1 NodeType for ns-3 code generation."""
        mapping = {
            GridNodeType.CONTROL_CENTER: NodeType.HOST,
            GridNodeType.BACKUP_CONTROL_CENTER: NodeType.HOST,
            GridNodeType.SUBSTATION: NodeType.SWITCH,
            GridNodeType.RTU: NodeType.HOST,
            GridNodeType.IED: NodeType.HOST,
            GridNodeType.DATA_CONCENTRATOR: NodeType.HOST,
            GridNodeType.RELAY: NodeType.HOST,
            GridNodeType.METER: NodeType.HOST,
            GridNodeType.GATEWAY: NodeType.ROUTER,
            GridNodeType.COMM_ROUTER: NodeType.ROUTER,
            GridNodeType.COMM_SWITCH: NodeType.SWITCH,
            GridNodeType.COMM_TOWER: NodeType.HOST,
            GridNodeType.SATELLITE_TERMINAL: NodeType.HOST,
            GridNodeType.CELLULAR_GATEWAY: NodeType.HOST,
            GridNodeType.HISTORIAN: NodeType.HOST,
            GridNodeType.HMI: NodeType.HOST,
        }
        return mapping.get(self, NodeType.HOST)


class GridNodeRole(Enum):
    """Functional role in the SCADA master-slave hierarchy."""
    MASTER = auto()
    SLAVE = auto()
    INTERMEDIATE = auto()
    PEER = auto()


class GridProtocol(Enum):
    """Communication protocols used in grid SCADA systems."""
    DNP3 = auto()
    IEC_61850 = auto()
    IEC_60870_5_104 = auto()
    MODBUS_TCP = auto()
    ICCP = auto()
    GOOSE = auto()
    MMS = auto()
    OPC_UA = auto()


class ScanClass(Enum):
    """SCADA scan/poll classes determining polling frequency."""
    EXCEPTION = 0
    CLASS_1 = 1
    CLASS_2 = 2
    CLASS_3 = 3
    INTEGRITY = 4


class VoltageLevel(Enum):
    """Transmission/distribution voltage levels."""
    TRANSMISSION_500KV = "500kV"
    TRANSMISSION_345KV = "345kV"
    TRANSMISSION_230KV = "230kV"
    TRANSMISSION_138KV = "138kV"
    SUBTRANSMISSION_69KV = "69kV"
    DISTRIBUTION_34KV = "34.5kV"
    DISTRIBUTION_13KV = "13.8kV"
    DISTRIBUTION_4KV = "4.16kV"
    SECONDARY_480V = "480V"
    SECONDARY_240V = "240V"


@dataclass
class DNP3Config:
    """DNP3 protocol configuration for a grid node."""
    enabled: bool = True
    master_address: int = 1
    slave_address: int = 10
    confirm_timeout_ms: int = 1000
    max_retries: int = 3
    response_timeout_ms: int = 5000
    unsolicited_enabled: bool = True
    class1_events: bool = True
    class2_events: bool = True
    class3_events: bool = True
    num_binary_inputs: int = 32
    num_binary_outputs: int = 16
    num_analog_inputs: int = 32
    num_analog_outputs: int = 8
    num_counters: int = 8


@dataclass
class IEC61850Config:
    """IEC 61850 protocol configuration for a grid node."""
    enabled: bool = False
    ied_name: str = ""
    ap_name: str = "S1"
    goose_enabled: bool = False
    goose_app_id: int = 0
    goose_multicast_mac: str = "01:0C:CD:01:00:00"
    goose_vlan_id: int = 0
    goose_vlan_priority: int = 4
    mms_enabled: bool = True
    mms_port: int = 102
    logical_devices: List[str] = field(default_factory=lambda: ["LD0"])


@dataclass
class GridNodeModel(NodeModel):
    """
    Extended node model for electric grid infrastructure.
    
    Inherits from NodeModel and adds grid-specific properties.
    Can be used anywhere a NodeModel is expected.
    
    Usage:
        # Create directly - no factory needed
        cc = GridNodeModel(grid_type=GridNodeType.CONTROL_CENTER, name="EMS")
        rtu = GridNodeModel(grid_type=GridNodeType.RTU, substation_id="sub1")
        
        # Works with NetworkModel because it IS-A NodeModel
        network.nodes[cc.id] = cc
    
    Inherited from NodeModel:
        id, node_type, medium_type, name, position, ports
        is_server, routing_protocol, forwarding_enabled
        stp_enabled, switching_mode, subnet_base, subnet_mask
        wifi_standard, wifi_ssid, wifi_channel, etc.
        routing_mode, routing_table, default_gateway, description
        
    Grid-specific attributes:
        grid_type: Type of grid equipment (auto-sets node_type)
        grid_role: Functional role (auto-set from grid_type if not specified)
        substation_id: Parent substation identifier
        voltage_level: Associated voltage level
        dnp3_config: DNP3 protocol settings
        iec61850_config: IEC 61850 settings
        scan_class: Polling frequency class (auto-set from grid_type)
        polling_group: Group number for staggered polls
    """
    # Grid-specific type (more specific than base node_type)
    grid_type: GridNodeType = GridNodeType.RTU
    
    # Use None as sentinel to detect "not explicitly set" 
    grid_role: Optional[GridNodeRole] = None
    scan_class: Optional[ScanClass] = None
    primary_protocol: Optional[GridProtocol] = None
    
    # Hierarchy
    substation_id: str = ""
    parent_node_id: str = ""
    
    # Electrical properties
    voltage_level: Optional[VoltageLevel] = None
    
    # Communication protocols
    dnp3_config: DNP3Config = field(default_factory=DNP3Config)
    iec61850_config: IEC61850Config = field(default_factory=IEC61850Config)
    
    # IP addressing (supplements base port IPs)
    primary_ip: str = ""
    backup_ip: str = ""
    
    # Polling configuration
    polling_group: int = 1
    poll_interval_ms: int = 0  # 0 = use scan class default
    response_timeout_ms: int = 5000
    retry_count: int = 3
    
    # Redundancy
    is_backup: bool = False
    redundancy_group: str = ""
    failover_priority: int = 0
    failover_trigger_ms: int = 10000
    
    # Operational state (for simulation tracking)
    is_online: bool = True
    last_poll_time: float = 0.0
    last_response_time: float = 0.0
    consecutive_failures: int = 0
    
    # Visual grouping
    group_id: str = ""
    group_color: str = ""
    
    def __post_init__(self):
        """
        Initialize grid node with proper defaults based on grid_type.
        
        This method:
        1. Sets base node_type from grid_type (before parent init)
        2. Calls parent __post_init__ for ports and name
        3. Applies grid-type-specific defaults for role, scan_class, protocol
        4. Generates grid-appropriate name if not specified
        """
        # 1. Set the base node_type based on grid_type BEFORE calling parent
        self.node_type = self.grid_type.to_base_node_type()
        
        # 2. Call parent __post_init__ for name and port initialization
        super().__post_init__()
        
        # 3. Apply grid-type-specific defaults from GRID_NODE_DEFAULTS
        defaults = GRID_NODE_DEFAULTS.get(self.grid_type, {})
        
        # Set grid_role if not explicitly provided
        if self.grid_role is None:
            if self.grid_type in (GridNodeType.CONTROL_CENTER, GridNodeType.BACKUP_CONTROL_CENTER):
                self.grid_role = GridNodeRole.MASTER
            elif self.grid_type in (GridNodeType.GATEWAY, GridNodeType.DATA_CONCENTRATOR):
                self.grid_role = GridNodeRole.INTERMEDIATE
            else:
                self.grid_role = defaults.get("grid_role", GridNodeRole.SLAVE)
        
        # Set scan_class if not explicitly provided
        if self.scan_class is None:
            self.scan_class = defaults.get("scan_class", ScanClass.CLASS_2)
        
        # Set primary_protocol if not explicitly provided
        if self.primary_protocol is None:
            self.primary_protocol = defaults.get("primary_protocol", GridProtocol.DNP3)
        
        # 4. Override default name if it was auto-generated by parent
        # Parent generates names like "host_xxxx", we want "control_center_xxxx"
        if self.name.startswith(f"{self.node_type.name.lower()}_"):
            self.name = f"{self.grid_type.name.lower()}_{self.id[:4]}"
    
    @property
    def is_master(self) -> bool:
        return self.grid_role == GridNodeRole.MASTER
    
    @property
    def is_slave(self) -> bool:
        return self.grid_role == GridNodeRole.SLAVE
    
    @property
    def is_field_device(self) -> bool:
        return self.grid_type in (
            GridNodeType.RTU, GridNodeType.IED,
            GridNodeType.RELAY, GridNodeType.METER,
        )
    
    @property
    def supports_goose(self) -> bool:
        return (
            self.grid_type in (GridNodeType.IED, GridNodeType.RELAY) and
            self.iec61850_config.enabled and
            self.iec61850_config.goose_enabled
        )
    
    @property
    def poll_interval_effective_ms(self) -> int:
        if self.poll_interval_ms > 0:
            return self.poll_interval_ms
        
        defaults = {
            ScanClass.EXCEPTION: 0,
            ScanClass.CLASS_1: 1000,
            ScanClass.CLASS_2: 4000,
            ScanClass.CLASS_3: 30000,
            ScanClass.INTEGRITY: 60000,
        }
        return defaults.get(self.scan_class, 4000)


@dataclass
class SubstationModel:
    """
    Represents an electrical substation containing multiple RTUs/IEDs.
    
    This is a logical grouping that helps organize the grid topology.
    Note: This is NOT a node itself, but a container for organizing nodes.
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = ""
    description: str = ""
    
    # Location
    region: str = ""
    latitude: float = 0.0
    longitude: float = 0.0
    
    # Electrical
    voltage_levels: List[VoltageLevel] = field(default_factory=list)
    is_transmission: bool = True
    
    # Communication
    primary_comm_path: str = ""
    backup_comm_path: str = ""
    
    # Contained equipment (node IDs)
    rtu_ids: List[str] = field(default_factory=list)
    ied_ids: List[str] = field(default_factory=list)
    gateway_ids: List[str] = field(default_factory=list)
    
    # Visual
    position_x: float = 0.0
    position_y: float = 0.0
    width: float = 200.0
    height: float = 150.0
    color: str = "#E8E8E8"
    
    def __post_init__(self):
        if not self.name:
            self.name = f"Substation_{self.id[:4]}"
    
    @property
    def all_device_ids(self) -> List[str]:
        return self.rtu_ids + self.ied_ids + self.gateway_ids
    
    @property
    def device_count(self) -> int:
        return len(self.all_device_ids)
    
    def add_device(self, node: GridNodeModel) -> None:
        """Add a grid node to this substation."""
        node.substation_id = self.id
        if node.grid_type == GridNodeType.RTU:
            if node.id not in self.rtu_ids:
                self.rtu_ids.append(node.id)
        elif node.grid_type == GridNodeType.IED:
            if node.id not in self.ied_ids:
                self.ied_ids.append(node.id)
        elif node.grid_type == GridNodeType.GATEWAY:
            if node.id not in self.gateway_ids:
                self.gateway_ids.append(node.id)


# Default configurations for common grid node types
GRID_NODE_DEFAULTS = {
    GridNodeType.CONTROL_CENTER: {
        "grid_role": GridNodeRole.MASTER,
        "scan_class": ScanClass.INTEGRITY,
    },
    GridNodeType.RTU: {
        "grid_role": GridNodeRole.SLAVE,
        "scan_class": ScanClass.CLASS_2,
    },
    GridNodeType.IED: {
        "grid_role": GridNodeRole.SLAVE,
        "scan_class": ScanClass.CLASS_1,
        "primary_protocol": GridProtocol.IEC_61850,
    },
    GridNodeType.DATA_CONCENTRATOR: {
        "grid_role": GridNodeRole.INTERMEDIATE,
        "scan_class": ScanClass.CLASS_2,
    },
    GridNodeType.GATEWAY: {
        "grid_role": GridNodeRole.INTERMEDIATE,
    },
    GridNodeType.RELAY: {
        "grid_role": GridNodeRole.SLAVE,
        "scan_class": ScanClass.CLASS_1,
        "primary_protocol": GridProtocol.IEC_61850,
    },
}
