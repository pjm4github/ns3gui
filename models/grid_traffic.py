"""
Electric Grid SCADA Traffic Models.

Extends the base TrafficFlow to support grid-specific traffic patterns
including SCADA polling, protection messages, telemetry, and control commands.
"""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional, List, Dict, Any
import uuid

# Import V1 base classes
from .simulation import TrafficFlow, TrafficProtocol, TrafficApplication


class GridTrafficClass(Enum):
    """
    Traffic types in electric grid SCADA/EMS systems.
    
    Each class has different priority, latency requirements, and
    generation patterns.
    """
    # SCADA Polling
    SCADA_INTEGRITY_POLL = auto()
    SCADA_EXCEPTION_POLL = auto()
    SCADA_RESPONSE = auto()
    
    # Control Operations
    SCADA_CONTROL_SELECT = auto()
    SCADA_CONTROL_OPERATE = auto()
    CONTROL_SELECT = auto()
    CONTROL_OPERATE = auto()
    CONTROL_DIRECT = auto()
    CONTROL_RESPONSE = auto()
    
    # Protection (IEC 61850)
    GOOSE = auto()
    IEC61850_GOOSE = auto()
    IEC61850_MMS = auto()
    SAMPLED_VALUES = auto()
    MMS_REPORT = auto()
    
    # Telemetry
    TELEMETRY_ANALOG = auto()
    TELEMETRY_STATUS = auto()
    TELEMETRY_SOE = auto()
    
    # Supervision
    HEARTBEAT = auto()
    TIME_SYNC = auto()
    
    # Bulk Data
    FILE_TRANSFER = auto()
    HISTORICAL_DATA = auto()
    
    # Events
    EVENT_ALARM = auto()
    EVENT_LOG = auto()
    
    # Inter-Control Center
    ICCP_DATA = auto()
    ICCP_CONTROL = auto()
    ICCP_BILATERAL = auto()
    
    def to_base_application(self) -> TrafficApplication:
        """Map to V1 TrafficApplication for code generation."""
        mapping = {
            GridTrafficClass.SCADA_INTEGRITY_POLL: TrafficApplication.ECHO,
            GridTrafficClass.SCADA_EXCEPTION_POLL: TrafficApplication.ECHO,
            GridTrafficClass.HEARTBEAT: TrafficApplication.ECHO,
            GridTrafficClass.GOOSE: TrafficApplication.ONOFF,
            GridTrafficClass.IEC61850_GOOSE: TrafficApplication.ONOFF,
            GridTrafficClass.TELEMETRY_ANALOG: TrafficApplication.ONOFF,
            GridTrafficClass.FILE_TRANSFER: TrafficApplication.BULK_SEND,
        }
        return mapping.get(self, TrafficApplication.ECHO)


class GridTrafficPriority(Enum):
    """
    QoS priority levels mapping to DSCP values.
    
    Based on IEC 62351-6 recommendations for power system communications.
    """
    PROTECTION = (46, "EF")
    CONTROL = (34, "AF41")
    SCADA_HIGH = (26, "AF31")
    SCADA_NORMAL = (18, "AF21")
    MONITORING = (10, "AF11")
    BEST_EFFORT = (0, "BE")
    
    def __init__(self, dscp: int, name: str):
        self._dscp = dscp
        self._dscp_name = name
    
    @property
    def dscp(self) -> int:
        return self._dscp
    
    @property
    def dscp_name(self) -> str:
        return self._dscp_name


class DNP3FunctionCode(Enum):
    """DNP3 application layer function codes."""
    READ = 0x01
    WRITE = 0x02
    SELECT = 0x03
    OPERATE = 0x04
    DIRECT_OPERATE = 0x05
    DIRECT_OPERATE_NR = 0x06
    COLD_RESTART = 0x0D
    WARM_RESTART = 0x0E
    ENABLE_UNSOLICITED = 0x14
    DISABLE_UNSOLICITED = 0x15
    DELAY_MEASURE = 0x17
    RESPONSE = 0x81
    UNSOLICITED_RESPONSE = 0x82


class DNP3ObjectGroup(Enum):
    """Common DNP3 data object groups."""
    BINARY_INPUT = 1
    BINARY_INPUT_EVENT = 2
    DOUBLE_BIT_INPUT = 3
    BINARY_OUTPUT = 10
    BINARY_OUTPUT_EVENT = 11
    COUNTER = 20
    COUNTER_EVENT = 22
    ANALOG_INPUT = 30
    ANALOG_INPUT_EVENT = 32
    ANALOG_OUTPUT = 40
    ANALOG_OUTPUT_EVENT = 42
    TIME_DATE = 50
    CLASS_DATA = 60


@dataclass
class DNP3MessageConfig:
    """Configuration for DNP3 message generation."""
    function_code: DNP3FunctionCode = DNP3FunctionCode.READ
    objects: List[Dict[str, int]] = field(default_factory=list)
    class_1: bool = False
    class_2: bool = False
    class_3: bool = False
    integrity_scan: bool = False
    confirm_required: bool = False
    unsolicited: bool = False
    
    def __post_init__(self):
        if not self.objects and self.integrity_scan:
            self.objects = [
                {"group": 1, "variation": 2, "count": 32},
                {"group": 30, "variation": 1, "count": 32},
                {"group": 20, "variation": 1, "count": 8},
            ]
            self.class_1 = True
            self.class_2 = True
            self.class_3 = True
    
    @property
    def estimated_request_bytes(self) -> int:
        size = 10  # Headers
        size += len(self.objects) * 2
        return size
    
    @property
    def estimated_response_bytes(self) -> int:
        size = 10
        for obj in self.objects:
            group = obj.get("group", 0)
            count = obj.get("count", 0)
            bytes_per_point = {1: 1, 2: 8, 10: 1, 20: 4, 30: 4, 32: 8}.get(group, 2)
            size += count * bytes_per_point + 3
        return size


@dataclass
class GOOSEMessageConfig:
    """Configuration for IEC 61850 GOOSE message generation."""
    gocb_ref: str = ""
    go_id: str = ""
    data_set: str = ""
    min_time_ms: int = 2
    max_time_ms: int = 1000
    num_entries: int = 10
    vlan_id: int = 0
    vlan_priority: int = 4
    trigger_on_change: bool = True
    change_probability: float = 0.01
    
    @property
    def estimated_bytes(self) -> int:
        return 14 + 8 + 4 + self.num_entries * 4


# Default configurations for each traffic class
GRID_TRAFFIC_DEFAULTS: Dict[GridTrafficClass, Dict[str, Any]] = {
    GridTrafficClass.SCADA_INTEGRITY_POLL: {
        "interval_ms": 60000,
        "priority": GridTrafficPriority.SCADA_NORMAL,
        "timeout_ms": 10000,
        "bidirectional": True,
    },
    GridTrafficClass.SCADA_EXCEPTION_POLL: {
        "interval_ms": 4000,
        "priority": GridTrafficPriority.SCADA_NORMAL,
        "timeout_ms": 5000,
        "bidirectional": True,
    },
    GridTrafficClass.CONTROL_SELECT: {
        "interval_ms": 0,
        "priority": GridTrafficPriority.CONTROL,
        "timeout_ms": 2000,
        "bidirectional": True,
    },
    GridTrafficClass.CONTROL_OPERATE: {
        "interval_ms": 0,
        "priority": GridTrafficPriority.CONTROL,
        "timeout_ms": 2000,
        "bidirectional": True,
    },
    GridTrafficClass.GOOSE: {
        "interval_ms": 1000,
        "priority": GridTrafficPriority.PROTECTION,
        "timeout_ms": 4,
        "bidirectional": False,
    },
    GridTrafficClass.SAMPLED_VALUES: {
        "interval_ms": 0,
        "priority": GridTrafficPriority.PROTECTION,
        "bidirectional": False,
    },
    GridTrafficClass.TELEMETRY_ANALOG: {
        "interval_ms": 1000,
        "priority": GridTrafficPriority.MONITORING,
        "bidirectional": False,
    },
    GridTrafficClass.HEARTBEAT: {
        "interval_ms": 30000,
        "priority": GridTrafficPriority.BEST_EFFORT,
        "timeout_ms": 10000,
        "packet_size": 20,
        "bidirectional": True,
    },
    GridTrafficClass.TIME_SYNC: {
        "interval_ms": 1000,
        "priority": GridTrafficPriority.SCADA_HIGH,
        "packet_size": 48,
        "bidirectional": True,
    },
    GridTrafficClass.FILE_TRANSFER: {
        "interval_ms": 0,
        "priority": GridTrafficPriority.BEST_EFFORT,
        "timeout_ms": 30000,
        "bidirectional": True,
    },
}


@dataclass
class GridTrafficFlow(TrafficFlow):
    """
    Extended traffic flow for electric grid SCADA traffic.
    
    Inherits from TrafficFlow and adds grid-specific properties.
    Can be used anywhere a TrafficFlow is expected.
    
    Inherited from TrafficFlow:
        id, name, source_node_id, target_node_id, protocol, application,
        port, data_rate, packet_size, start_time, stop_time, enabled,
        echo_interval, echo_packet_size, onoff_data_rate, onoff_packet_size,
        onoff_on_time, onoff_off_time, bulk_max_bytes, etc.
        
    Grid-specific attributes:
        traffic_class: Grid traffic classification
        priority: QoS priority level
        interval_ms: Polling/transmission interval
        dnp3_config: DNP3 message configuration
        goose_config: GOOSE message configuration
    """
    # Grid-specific classification
    traffic_class: GridTrafficClass = GridTrafficClass.SCADA_EXCEPTION_POLL
    priority: GridTrafficPriority = GridTrafficPriority.SCADA_NORMAL
    
    # Additional targets for multicast
    target_node_ids: List[str] = field(default_factory=list)
    multicast_group: str = ""
    
    # Interval (ms) - maps to echo_interval in base class
    interval_ms: int = 0  # 0 = use default for traffic class
    poll_interval_s: float = 0.0  # Alias for interval in seconds (for editor)
    initial_delay_ms: int = 0
    jitter_ms: int = 0
    
    # Packet sizes (for editor)
    request_size_bytes: int = 64
    response_size_bytes: int = 128
    
    # Protocol configuration
    grid_protocol: str = "DNP3"
    dnp3_config: DNP3MessageConfig = field(default_factory=DNP3MessageConfig)
    goose_config: Optional[GOOSEMessageConfig] = None
    
    # Reliability
    timeout_ms: int = 5000
    retry_count: int = 3
    required_success_rate: float = 0.99
    
    # Traffic characteristics
    bidirectional: bool = True
    burst_count: int = 1
    
    # State tracking
    messages_sent: int = 0
    messages_received: int = 0
    timeouts: int = 0
    
    def __post_init__(self):
        """
        Initialize grid traffic flow with proper defaults based on traffic_class.
        
        This method:
        1. Sets base application type from traffic_class
        2. Applies traffic-class-specific defaults for priority, interval, etc.
        3. Sets appropriate default port for SCADA traffic
        4. Syncs interval_ms to parent's echo_interval
        5. Generates appropriate name if not specified
        """
        # 1. Set base application type from traffic class
        self.application = self.traffic_class.to_base_application()
        
        # 2. Apply traffic class defaults
        defaults = GRID_TRAFFIC_DEFAULTS.get(self.traffic_class, {})
        
        if self.interval_ms == 0 and "interval_ms" in defaults:
            self.interval_ms = defaults["interval_ms"]
        if "priority" in defaults and self.priority == GridTrafficPriority.SCADA_NORMAL:
            self.priority = defaults["priority"]
        if "timeout_ms" in defaults and self.timeout_ms == 5000:
            self.timeout_ms = defaults["timeout_ms"]
        if "bidirectional" in defaults:
            self.bidirectional = defaults["bidirectional"]
        
        # 3. Set SCADA-appropriate default port (DNP3 uses 20000)
        if self.port == 9:  # Parent's default
            self.port = 20000
        
        # 4. Sync interval_ms / poll_interval_s to base class echo_interval (seconds)
        if self.poll_interval_s > 0 and self.interval_ms == 0:
            self.interval_ms = int(self.poll_interval_s * 1000)
        elif self.interval_ms > 0:
            self.poll_interval_s = self.interval_ms / 1000.0
        
        if self.interval_ms > 0:
            self.echo_interval = self.interval_ms / 1000.0
        
        # 5. Sync packet sizes
        if self.request_size_bytes > 0:
            self.packet_size = self.request_size_bytes
        if self.response_size_bytes > 0:
            self.echo_packet_size = self.response_size_bytes
        
        # 6. Generate name if not set
        if not self.name:
            self.name = f"{self.traffic_class.name.lower()}_{self.id[:4]}"
    
    @property
    def is_periodic(self) -> bool:
        return self.interval_ms > 0
    
    @property
    def is_protection_class(self) -> bool:
        return self.traffic_class in (
            GridTrafficClass.GOOSE,
            GridTrafficClass.SAMPLED_VALUES,
        )
    
    @property
    def dscp_value(self) -> int:
        return self.priority.dscp
    
    @property
    def effective_interval_ms(self) -> int:
        if self.interval_ms > 0:
            return self.interval_ms
        defaults = GRID_TRAFFIC_DEFAULTS.get(self.traffic_class, {})
        return defaults.get("interval_ms", 4000)
    
    @property
    def success_rate(self) -> float:
        if self.messages_sent == 0:
            return 1.0
        return self.messages_received / self.messages_sent


@dataclass
class PollingSchedule:
    """
    Defines a complete SCADA polling schedule for a control center.
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = "Default Schedule"
    control_center_id: str = ""
    
    # Polling groups
    groups: List[Dict[str, Any]] = field(default_factory=list)
    
    # Global settings
    integrity_interval_ms: int = 60000
    exception_interval_ms: int = 4000
    
    def __post_init__(self):
        if not self.groups:
            self.groups = [
                {"name": "Class 1 (Fast)", "interval_ms": 1000, "device_ids": [], "stagger_ms": 50},
                {"name": "Class 2 (Normal)", "interval_ms": 4000, "device_ids": [], "stagger_ms": 100},
                {"name": "Class 3 (Slow)", "interval_ms": 30000, "device_ids": [], "stagger_ms": 500},
            ]
    
    def add_device_to_group(self, device_id: str, group_index: int = 1):
        if 0 <= group_index < len(self.groups):
            if device_id not in self.groups[group_index]["device_ids"]:
                self.groups[group_index]["device_ids"].append(device_id)
    
    def remove_device(self, device_id: str):
        for group in self.groups:
            if device_id in group["device_ids"]:
                group["device_ids"].remove(device_id)
    
    def get_device_group(self, device_id: str) -> Optional[Dict[str, Any]]:
        for group in self.groups:
            if device_id in group["device_ids"]:
                return group
        return None
    
    def generate_traffic_flows(self) -> List[GridTrafficFlow]:
        """
        Generate traffic flows for this polling schedule.
        
        Returns:
            List of GridTrafficFlow instances
        """
        flows = []
        
        for group in self.groups:
            interval_ms = group["interval_ms"]
            stagger_ms = group.get("stagger_ms", 100)
            
            for i, device_id in enumerate(group["device_ids"]):
                initial_delay = i * stagger_ms
                
                flow = GridTrafficFlow(
                    traffic_class=GridTrafficClass.SCADA_EXCEPTION_POLL,
                    source_node_id=self.control_center_id,
                    target_node_id=device_id,
                    interval_ms=interval_ms,
                    initial_delay_ms=initial_delay,
                )
                flow.dnp3_config.class_1 = True
                flow.dnp3_config.class_2 = True
                flow.dnp3_config.class_3 = True
                
                flows.append(flow)
        
        return flows
    
    @property
    def total_polls_per_minute(self) -> float:
        total = 0.0
        for group in self.groups:
            interval_ms = group["interval_ms"]
            if interval_ms > 0:
                device_count = len(group["device_ids"])
                polls_per_minute = (60000.0 / interval_ms) * device_count
                total += polls_per_minute
        return total
    
    @property
    def estimated_bandwidth_kbps(self) -> float:
        bytes_per_poll = 700
        polls_per_second = self.total_polls_per_minute / 60.0
        return (bytes_per_poll * polls_per_second * 8) / 1000.0


# Predefined traffic patterns
TRAFFIC_PATTERNS = {
    "standard_scada": {
        "name": "Standard SCADA Polling",
        "description": "Typical SCADA polling pattern with 4-second exception scans",
        "flows": [
            {"class": GridTrafficClass.SCADA_EXCEPTION_POLL, "interval_ms": 4000},
            {"class": GridTrafficClass.SCADA_INTEGRITY_POLL, "interval_ms": 60000},
            {"class": GridTrafficClass.HEARTBEAT, "interval_ms": 30000},
        ]
    },
    "fast_scan": {
        "name": "Fast Scan Pattern",
        "description": "High-speed scanning for critical substations",
        "flows": [
            {"class": GridTrafficClass.SCADA_EXCEPTION_POLL, "interval_ms": 1000},
            {"class": GridTrafficClass.SCADA_INTEGRITY_POLL, "interval_ms": 30000},
        ]
    },
    "iec61850_protection": {
        "name": "IEC 61850 Protection",
        "description": "Protection messaging with GOOSE",
        "flows": [
            {"class": GridTrafficClass.GOOSE, "interval_ms": 1000},
            {"class": GridTrafficClass.MMS_REPORT, "interval_ms": 1000},
        ]
    },
}


# Traffic class defaults for the editor
TRAFFIC_CLASS_DEFAULTS: Dict[GridTrafficClass, Dict[str, Any]] = {
    GridTrafficClass.SCADA_INTEGRITY_POLL: {
        "poll_interval_s": 60.0,
        "request_size_bytes": 64,
        "response_size_bytes": 512,
        "timeout_ms": 10000,
    },
    GridTrafficClass.SCADA_EXCEPTION_POLL: {
        "poll_interval_s": 4.0,
        "request_size_bytes": 32,
        "response_size_bytes": 128,
        "timeout_ms": 5000,
    },
    GridTrafficClass.SCADA_CONTROL_SELECT: {
        "poll_interval_s": 0,
        "request_size_bytes": 32,
        "response_size_bytes": 32,
        "timeout_ms": 2000,
    },
    GridTrafficClass.SCADA_CONTROL_OPERATE: {
        "poll_interval_s": 0,
        "request_size_bytes": 32,
        "response_size_bytes": 32,
        "timeout_ms": 2000,
    },
    GridTrafficClass.IEC61850_GOOSE: {
        "poll_interval_s": 1.0,
        "request_size_bytes": 128,
        "response_size_bytes": 0,
        "timeout_ms": 4,
    },
    GridTrafficClass.IEC61850_MMS: {
        "poll_interval_s": 10.0,
        "request_size_bytes": 64,
        "response_size_bytes": 256,
        "timeout_ms": 5000,
    },
    GridTrafficClass.ICCP_BILATERAL: {
        "poll_interval_s": 30.0,
        "request_size_bytes": 256,
        "response_size_bytes": 256,
        "timeout_ms": 10000,
    },
    GridTrafficClass.HEARTBEAT: {
        "poll_interval_s": 30.0,
        "request_size_bytes": 20,
        "response_size_bytes": 20,
        "timeout_ms": 10000,
    },
}


@dataclass
class PollingGroup:
    """
    A group of devices polled together with the same timing parameters.
    
    Used by the Traffic Pattern Editor to organize polling configuration.
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = "Polling Group"
    
    # Timing
    poll_interval_s: float = 60.0
    response_timeout_s: float = 5.0
    stagger_offset_ms: int = 100
    
    # Traffic type
    traffic_class: GridTrafficClass = GridTrafficClass.SCADA_EXCEPTION_POLL
    priority: GridTrafficPriority = GridTrafficPriority.SCADA_NORMAL
    
    # Member devices
    member_node_ids: List[str] = field(default_factory=list)
    
    # Protocol settings
    protocol: str = "DNP3"
    
    # State
    enabled: bool = True
    
    def __post_init__(self):
        if not self.name:
            self.name = f"Group_{self.id[:4]}"
    
    @property
    def member_count(self) -> int:
        return len(self.member_node_ids)
    
    @property
    def polls_per_minute(self) -> float:
        if self.poll_interval_s > 0:
            return 60.0 / self.poll_interval_s * self.member_count
        return 0
    
    def add_member(self, node_id: str):
        if node_id not in self.member_node_ids:
            self.member_node_ids.append(node_id)
    
    def remove_member(self, node_id: str):
        if node_id in self.member_node_ids:
            self.member_node_ids.remove(node_id)
    
    def generate_flows(self, source_id: str, start_time: float = 1.0, 
                       stop_time: float = 60.0) -> List['GridTrafficFlow']:
        """Generate traffic flows for all members in this group."""
        flows = []
        
        for i, member_id in enumerate(self.member_node_ids):
            initial_delay = i * self.stagger_offset_ms / 1000.0
            
            flow = GridTrafficFlow(
                traffic_class=self.traffic_class,
                priority=self.priority,
                source_node_id=source_id,
                target_node_id=member_id,
                interval_ms=int(self.poll_interval_s * 1000),
                initial_delay_ms=int(initial_delay * 1000),
                start_time=start_time + initial_delay,
                stop_time=stop_time,
                timeout_ms=int(self.response_timeout_s * 1000),
            )
            flows.append(flow)
        
        return flows


@dataclass 
class TrafficProfile:
    """
    A complete traffic profile combining multiple polling groups.
    
    Used to define standard traffic patterns that can be applied
    to a network topology.
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = "Traffic Profile"
    description: str = ""
    
    # Polling groups
    polling_groups: List[PollingGroup] = field(default_factory=list)
    
    # Additional flows (not part of polling groups)
    additional_flows: List['GridTrafficFlow'] = field(default_factory=list)
    
    # Timing
    simulation_duration_s: float = 120.0
    warmup_time_s: float = 1.0
    
    # Tags
    tags: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        if not self.name:
            self.name = f"Profile_{self.id[:4]}"
    
    def add_polling_group(self, group: PollingGroup):
        self.polling_groups.append(group)
    
    def remove_polling_group(self, group_id: str):
        self.polling_groups = [g for g in self.polling_groups if g.id != group_id]
    
    def generate_all_flows(self, control_center_id: str) -> List['GridTrafficFlow']:
        """Generate all traffic flows for this profile."""
        flows = []
        
        for group in self.polling_groups:
            if group.enabled:
                group_flows = group.generate_flows(
                    source_id=control_center_id,
                    start_time=self.warmup_time_s,
                    stop_time=self.simulation_duration_s,
                )
                flows.extend(group_flows)
        
        flows.extend(self.additional_flows)
        return flows
    
    @property
    def total_polls_per_minute(self) -> float:
        return sum(g.polls_per_minute for g in self.polling_groups if g.enabled)
    
    @property
    def total_devices(self) -> int:
        return sum(g.member_count for g in self.polling_groups)


@dataclass
class QoSConfig:
    """
    Quality of Service configuration for grid traffic.
    
    Maps to ns-3 traffic control and QoS settings.
    """
    # DSCP marking
    enable_dscp: bool = True
    default_dscp: int = 0
    
    # Traffic class to DSCP mapping
    dscp_mapping: Dict[GridTrafficClass, int] = field(default_factory=lambda: {
        GridTrafficClass.GOOSE: 46,
        GridTrafficClass.IEC61850_GOOSE: 46,
        GridTrafficClass.SCADA_CONTROL_SELECT: 34,
        GridTrafficClass.SCADA_CONTROL_OPERATE: 34,
        GridTrafficClass.SCADA_EXCEPTION_POLL: 26,
        GridTrafficClass.SCADA_INTEGRITY_POLL: 18,
        GridTrafficClass.HEARTBEAT: 0,
    })
    
    # Queue configuration
    enable_queuing: bool = True
    queue_discipline: str = "pfifo_fast"  # or "htb", "cbq"
    
    # Rate limiting
    enable_rate_limit: bool = False
    max_rate_kbps: int = 10000
    burst_bytes: int = 15000
    
    def get_dscp_for_class(self, traffic_class: GridTrafficClass) -> int:
        return self.dscp_mapping.get(traffic_class, self.default_dscp)
