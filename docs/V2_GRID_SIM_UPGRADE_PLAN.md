# Electric Grid Communication Network Simulator - V2 Implementation Plan

## Executive Summary

V2 extends the ns-3 PyQt GUI Framework to model cyber-physical simulations of electric grid communication networks. This includes control centers, substations, RTUs/IEDs, diverse communication links, SCADA traffic patterns, failure injection, and comprehensive metrics collection.

---

## Phase 1: Domain Model Extensions

### 1.1 New Node Types for Grid Infrastructure

**File: `models/grid_nodes.py`**

```python
class GridNodeType(Enum):
    """Electric grid-specific node types."""
    CONTROL_CENTER = auto()      # Primary or backup control center (SCADA master)
    SUBSTATION = auto()          # Electrical substation with comm equipment
    RTU = auto()                 # Remote Terminal Unit (legacy SCADA)
    IED = auto()                 # Intelligent Electronic Device (modern)
    DATA_CONCENTRATOR = auto()   # Aggregates data from multiple RTUs/IEDs
    GATEWAY = auto()             # Protocol converter / firewall
    COMM_TOWER = auto()          # Microwave/radio tower
    SATELLITE_TERMINAL = auto()  # VSAT terminal for backup

class GridNodeRole(Enum):
    """Functional role in the grid hierarchy."""
    MASTER = auto()              # Control center (issues commands)
    SLAVE = auto()               # RTU/IED (responds to polls)
    INTERMEDIATE = auto()        # Data concentrator / gateway

@dataclass
class GridNodeModel(NodeModel):
    """Extended node model for grid infrastructure."""
    grid_type: GridNodeType = GridNodeType.RTU
    grid_role: GridNodeRole = GridNodeRole.SLAVE
    
    # Substation properties
    substation_id: str = ""      # Parent substation identifier
    voltage_level: str = ""      # e.g., "138kV", "69kV", "13.8kV"
    
    # RTU/IED properties
    dnp3_address: int = 0        # DNP3 slave address
    polling_group: int = 1       # Which polling group (for staggered polls)
    scan_class: int = 1          # 1=fast scan, 2=normal, 3=slow
    
    # Redundancy
    is_backup: bool = False      # Backup control center / comm path
    failover_priority: int = 0   # Lower = higher priority
```

### 1.2 Extended Link Types

**File: `models/grid_links.py`**

```python
class GridLinkType(Enum):
    """Communication link types in grid networks."""
    FIBER = auto()               # Primary backbone (PointToPoint)
    MICROWAVE = auto()           # Line-of-sight radio (PointToPoint with loss)
    SERIAL_RADIO = auto()        # Legacy serial radio (low bandwidth)
    CELLULAR_LTE = auto()        # LTE/5G backup (LteHelper)
    SATELLITE = auto()           # VSAT backup (high latency)
    ETHERNET_LAN = auto()        # Substation LAN (CSMA)
    WIFI_MESH = auto()           # Wireless mesh backup (WifiHelper)

@dataclass
class GridLinkModel(LinkModel):
    """Extended link model for grid communications."""
    grid_link_type: GridLinkType = GridLinkType.FIBER
    
    # Physical properties
    distance_km: float = 0.0     # For propagation delay calculation
    
    # Link characteristics by type
    # Fiber: 1-10 Gbps, ~5μs/km delay
    # Microwave: 10-100 Mbps, atmospheric loss
    # LTE: 10-100 Mbps, variable latency
    # Satellite: 1-10 Mbps, ~600ms RTT
    # Serial radio: 9.6-56 kbps, reliable
    
    # Redundancy
    is_backup_path: bool = False
    backup_for_link_id: str = ""  # Primary link this backs up
    
    # Default parameters per type
    def get_default_params(self) -> dict:
        defaults = {
            GridLinkType.FIBER: {"data_rate": "1Gbps", "delay": "1ms"},
            GridLinkType.MICROWAVE: {"data_rate": "100Mbps", "delay": "5ms"},
            GridLinkType.SERIAL_RADIO: {"data_rate": "19200bps", "delay": "50ms"},
            GridLinkType.CELLULAR_LTE: {"data_rate": "50Mbps", "delay": "30ms"},
            GridLinkType.SATELLITE: {"data_rate": "5Mbps", "delay": "600ms"},
            GridLinkType.ETHERNET_LAN: {"data_rate": "1Gbps", "delay": "0.1ms"},
            GridLinkType.WIFI_MESH: {"data_rate": "54Mbps", "delay": "5ms"},
        }
        return defaults.get(self.grid_link_type, {})
```

### 1.3 Traffic Classes for SCADA

**File: `models/grid_traffic.py`**

```python
class GridTrafficClass(Enum):
    """Traffic types in grid SCADA systems."""
    SCADA_POLL = auto()          # Periodic polling (integrity scan)
    SCADA_RESPONSE = auto()      # RTU/IED response to poll
    PROTECTION_MSG = auto()      # GOOSE/MMS protection messages (critical)
    TELEMETRY = auto()           # Continuous analog measurements
    HEARTBEAT = auto()           # Keep-alive / supervision
    EVENT_REPORT = auto()        # Unsolicited event notification (DNP3 Class 1)
    CONTROL_CMD = auto()         # Operate/Select-Before-Operate commands
    FILE_TRANSFER = auto()       # Firmware updates, config files
    TIME_SYNC = auto()           # NTP/PTP time synchronization

class GridTrafficPriority(Enum):
    """QoS priority levels (maps to DSCP)."""
    CRITICAL = 0                 # EF (46) - Protection messages
    HIGH = 1                     # AF41 (34) - Control commands
    MEDIUM = 2                   # AF21 (18) - SCADA polling
    LOW = 3                      # BE (0) - File transfers

@dataclass
class GridTrafficFlow(TrafficFlow):
    """Extended traffic flow for grid communications."""
    traffic_class: GridTrafficClass = GridTrafficClass.SCADA_POLL
    priority: GridTrafficPriority = GridTrafficPriority.MEDIUM
    
    # SCADA polling parameters
    poll_interval_ms: int = 1000     # Integrity poll interval
    response_timeout_ms: int = 5000  # Timeout for response
    retry_count: int = 3
    
    # DNP3 specific
    dnp3_function_code: int = 1      # 1=Read, 2=Write, 3=Select, 4=Operate
    data_points: int = 100           # Number of points in message
    
    # Telemetry specific
    sample_rate_hz: float = 1.0      # For continuous telemetry
    
    # Protection message specific
    is_multicast: bool = False       # GOOSE multicast
    max_latency_ms: int = 4          # IEC 61850 requirement
```

---

## Phase 2: Failure Injection System

### 2.1 Event Model

**File: `models/failure_events.py`**

```python
class FailureEventType(Enum):
    """Types of failure events that can be injected."""
    # Link failures
    LINK_DOWN = auto()           # Complete link failure
    LINK_DEGRADED = auto()       # Reduced bandwidth/increased latency
    LINK_FLAPPING = auto()       # Intermittent up/down
    LINK_CONGESTION = auto()     # Queue buildup, drops
    
    # Node failures
    NODE_POWER_LOSS = auto()     # Complete node failure
    NODE_REBOOT = auto()         # Temporary unavailability
    NODE_CPU_OVERLOAD = auto()   # Delayed processing
    NODE_MEMORY_FULL = auto()    # Packet drops
    
    # Network-wide
    PARTITION = auto()           # Network split
    BROADCAST_STORM = auto()     # L2 storm
    ROUTING_FAILURE = auto()     # Routing protocol issue
    
    # Cyber attacks (for security analysis)
    DOS_ATTACK = auto()          # Denial of service
    MITM_DELAY = auto()          # Man-in-the-middle adding delay
    PACKET_INJECTION = auto()    # Spurious packets

class FailureEventState(Enum):
    """State of a failure event."""
    SCHEDULED = auto()
    ACTIVE = auto()
    RECOVERED = auto()
    CANCELLED = auto()

@dataclass
class FailureEvent:
    """A scheduled failure event."""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = ""
    event_type: FailureEventType = FailureEventType.LINK_DOWN
    
    # Timing
    trigger_time: float = 0.0    # When to trigger (sim seconds)
    duration: float = -1.0       # Duration (-1 = permanent until recovery)
    recovery_time: float = -1.0  # Explicit recovery time (optional)
    
    # Target specification
    target_type: str = "link"    # "link", "node", "network"
    target_id: str = ""          # Link or node ID
    target_ids: list[str] = field(default_factory=list)  # For partitions
    
    # Event parameters
    parameters: dict = field(default_factory=dict)
    # Examples:
    # LINK_DOWN: {} (no params needed)
    # LINK_DEGRADED: {"new_data_rate": "1Mbps", "new_delay": "100ms"}
    # LINK_FLAPPING: {"up_duration": 5.0, "down_duration": 2.0, "cycles": 3}
    # NODE_REBOOT: {"reboot_duration": 30.0}
    # PARTITION: {"group_a": ["node1", "node2"], "group_b": ["node3", "node4"]}
    
    # State tracking
    state: FailureEventState = FailureEventState.SCHEDULED
    actual_trigger_time: float = 0.0
    actual_recovery_time: float = 0.0
    
    # Cascading effects
    causes_events: list[str] = field(default_factory=list)  # IDs of triggered events
    caused_by_event: str = ""    # ID of parent event

@dataclass
class FailureScenario:
    """A collection of failure events forming a scenario."""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = "Unnamed Scenario"
    description: str = ""
    events: list[FailureEvent] = field(default_factory=list)
    
    # Scenario metadata
    category: str = ""           # e.g., "Equipment Failure", "Cyber Attack", "Natural Disaster"
    severity: int = 1            # 1-5 scale
    probability: str = ""        # e.g., "Rare", "Unlikely", "Possible"
    
    def add_event(self, event: FailureEvent):
        self.events.append(event)
        self.events.sort(key=lambda e: e.trigger_time)
    
    def get_events_at_time(self, time: float) -> list[FailureEvent]:
        return [e for e in self.events if e.trigger_time == time]
    
    def get_active_events_at_time(self, time: float) -> list[FailureEvent]:
        active = []
        for e in self.events:
            if e.trigger_time <= time:
                if e.duration < 0 or (e.trigger_time + e.duration) > time:
                    active.append(e)
        return active
```

### 2.2 Failure Injection Engine

**File: `services/failure_injector.py`**

```python
class FailureInjector:
    """
    Generates ns-3 code for failure injection using Simulator::Schedule.
    """
    
    def generate_failure_code(self, scenario: FailureScenario) -> str:
        """Generate complete failure injection code section."""
        lines = []
        lines.append("# ========== Failure Injection ==========")
        lines.append("")
        
        # Generate helper functions
        lines.extend(self._generate_helper_functions())
        
        # Schedule each event
        for event in scenario.events:
            lines.extend(self._generate_event_schedule(event))
        
        return "\n".join(lines)
    
    def _generate_helper_functions(self) -> list[str]:
        """Generate reusable failure injection functions."""
        return [
            "def disable_link(device):",
            "    \"\"\"Disable a network device (simulates link failure).\"\"\"",
            "    device.SetAttribute('Mtu', ns.core.UintegerValue(0))",
            "",
            "def enable_link(device, mtu=1500):",
            "    \"\"\"Re-enable a network device.\"\"\"",
            "    device.SetAttribute('Mtu', ns.core.UintegerValue(mtu))",
            "",
            "def set_link_data_rate(channel, rate_str):",
            "    \"\"\"Change link data rate (for degradation).\"\"\"",
            "    channel.SetAttribute('DataRate', ns.network.DataRateValue(ns.network.DataRate(rate_str)))",
            "",
            "def set_link_delay(channel, delay_str):",
            "    \"\"\"Change link delay.\"\"\"",
            "    channel.SetAttribute('Delay', ns.core.TimeValue(ns.core.Time(delay_str)))",
            "",
            "def disable_node_interfaces(node):",
            "    \"\"\"Disable all interfaces on a node (simulates power loss).\"\"\"",
            "    ipv4 = node.GetObject(ns.internet.Ipv4.GetTypeId())",
            "    if ipv4:",
            "        for i in range(ipv4.GetNInterfaces()):",
            "            ipv4.SetDown(i)",
            "",
            "def enable_node_interfaces(node):",
            "    \"\"\"Re-enable all interfaces on a node.\"\"\"",
            "    ipv4 = node.GetObject(ns.internet.Ipv4.GetTypeId())",
            "    if ipv4:",
            "        for i in range(ipv4.GetNInterfaces()):",
            "            ipv4.SetUp(i)",
            "",
        ]
    
    def _generate_event_schedule(self, event: FailureEvent) -> list[str]:
        """Generate Simulator::Schedule calls for an event."""
        lines = [f"# Event: {event.name} ({event.event_type.name})"]
        
        trigger_ns = f"ns.core.Seconds({event.trigger_time})"
        
        if event.event_type == FailureEventType.LINK_DOWN:
            lines.append(f"ns.core.Simulator.Schedule({trigger_ns}, disable_link, {event.target_id}_device)")
            if event.duration > 0:
                recovery_ns = f"ns.core.Seconds({event.trigger_time + event.duration})"
                lines.append(f"ns.core.Simulator.Schedule({recovery_ns}, enable_link, {event.target_id}_device)")
        
        elif event.event_type == FailureEventType.LINK_DEGRADED:
            new_rate = event.parameters.get("new_data_rate", "1Mbps")
            new_delay = event.parameters.get("new_delay", "100ms")
            lines.append(f"ns.core.Simulator.Schedule({trigger_ns}, set_link_data_rate, {event.target_id}_channel, '{new_rate}')")
            lines.append(f"ns.core.Simulator.Schedule({trigger_ns}, set_link_delay, {event.target_id}_channel, '{new_delay}')")
        
        elif event.event_type == FailureEventType.NODE_POWER_LOSS:
            lines.append(f"ns.core.Simulator.Schedule({trigger_ns}, disable_node_interfaces, nodes.Get({event.target_id}))")
            if event.duration > 0:
                recovery_ns = f"ns.core.Seconds({event.trigger_time + event.duration})"
                lines.append(f"ns.core.Simulator.Schedule({recovery_ns}, enable_node_interfaces, nodes.Get({event.target_id}))")
        
        # ... additional event types
        
        lines.append("")
        return lines
```

---

## Phase 3: GUI Components

### 3.1 Grid Topology Editor Extensions

**File: `views/grid_editor.py`**

```
Components to add:
├── GridNodePalette          # Palette with grid-specific node types
│   ├── Control Center icon
│   ├── Substation icon
│   ├── RTU icon
│   ├── IED icon
│   └── Gateway icon
├── GridLinkTypeSelector     # Link type dropdown in properties
├── SubstationGroupBox       # Visual grouping of substation components
└── TopologyValidator        # Validates grid topology rules
```

### 3.2 Failure Scenario Panel

**File: `views/failure_panel.py`**

```python
class FailureScenarioPanel(QWidget):
    """
    Panel for creating and managing failure scenarios.
    
    Layout:
    ┌─────────────────────────────────────────────────────────┐
    │ Scenario: [Dropdown ▼] [New] [Clone] [Delete]           │
    ├─────────────────────────────────────────────────────────┤
    │ Events Timeline                                         │
    │ ┌─────────────────────────────────────────────────────┐ │
    │ │ 0s    5s    10s   15s   20s   25s   30s             │ │
    │ │ ├─────┼─────┼─────┼─────┼─────┼─────┤               │ │
    │ │ █ Link1 Down                                        │ │
    │ │       █████ Node2 Degraded                          │ │
    │ │             █ Link3 Flapping                        │ │
    │ └─────────────────────────────────────────────────────┘ │
    ├─────────────────────────────────────────────────────────┤
    │ [+ Add Event]                                           │
    ├─────────────────────────────────────────────────────────┤
    │ Event Details                                           │
    │ ┌─────────────────────────────────────────────────────┐ │
    │ │ Name: [_______________]                             │ │
    │ │ Type: [Link Down ▼]                                 │ │
    │ │ Target: [Link: fiber_cc_sub1 ▼]                     │ │
    │ │ Time: [10.0] s  Duration: [5.0] s                   │ │
    │ │ Parameters: [Edit...]                               │ │
    │ └─────────────────────────────────────────────────────┘ │
    └─────────────────────────────────────────────────────────┘
    """
```

### 3.3 Event Timeline Widget

**File: `views/widgets/event_timeline.py`**

```python
class EventTimelineWidget(QWidget):
    """
    Visual timeline showing failure events.
    
    Features:
    - Drag events to reschedule
    - Drag edges to change duration
    - Color coding by event type
    - Zoom in/out on timeline
    - Current simulation time indicator
    """
    
    eventSelected = pyqtSignal(str)  # Event ID
    eventMoved = pyqtSignal(str, float)  # Event ID, new time
    eventResized = pyqtSignal(str, float)  # Event ID, new duration
```

### 3.4 Traffic Pattern Editor

**File: `views/traffic_pattern_editor.py`**

```python
class SCADATrafficPatternEditor(QWidget):
    """
    Editor for configuring SCADA traffic patterns.
    
    Layout:
    ┌─────────────────────────────────────────────────────────┐
    │ Traffic Patterns                                        │
    ├─────────────────────────────────────────────────────────┤
    │ ┌─ Polling Configuration ──────────────────────────────┐│
    │ │ Control Center: [CC1 ▼]                              ││
    │ │                                                      ││
    │ │ Poll Group 1 (Fast - 1s)                             ││
    │ │   ☑ Sub1-RTU1  ☑ Sub1-RTU2  ☑ Sub2-RTU1             ││
    │ │                                                      ││
    │ │ Poll Group 2 (Normal - 4s)                           ││
    │ │   ☑ Sub3-RTU1  ☑ Sub3-RTU2  ☑ Sub4-RTU1             ││
    │ │                                                      ││
    │ │ Poll Group 3 (Slow - 30s)                            ││
    │ │   ☑ Sub5-RTU1  ☐ Sub5-RTU2                          ││
    │ └──────────────────────────────────────────────────────┘│
    │                                                         │
    │ ┌─ Traffic Summary ────────────────────────────────────┐│
    │ │ Total Polls/sec: 12.5                                ││
    │ │ Bandwidth estimate: 156 kbps                         ││
    │ │ Expected latency: 45ms avg                           ││
    │ └──────────────────────────────────────────────────────┘│
    └─────────────────────────────────────────────────────────┘
    """
```

### 3.5 Metrics Dashboard

**File: `views/metrics_dashboard.py`**

```python
class GridMetricsDashboard(QWidget):
    """
    Real-time and post-simulation metrics display.
    
    Layout:
    ┌────────────────────────────────────────────────────────────────┐
    │ ┌─ System Health ──────────┐ ┌─ Message Delivery ───────────┐  │
    │ │ Links Up: 45/48          │ │ Polls Sent: 1,234            │  │
    │ │ Nodes Up: 52/52          │ │ Responses: 1,230 (99.7%)     │  │
    │ │ Routing Converged: Yes   │ │ Timeouts: 4                  │  │
    │ └──────────────────────────┘ │ Avg Latency: 23ms            │  │
    │                              └──────────────────────────────┘  │
    ├────────────────────────────────────────────────────────────────┤
    │ Latency Over Time                                              │
    │ ┌────────────────────────────────────────────────────────────┐ │
    │ │     ╭───╮                    ╭────╮                        │ │
    │ │ 50ms│   │      Link Failure  │    │  Recovery              │ │
    │ │     │   ╰────╮    ↓         ╭╯    ╰────────                │ │
    │ │ 25ms│        ╰────╯────────╯                               │ │
    │ │     ├────┬────┬────┬────┬────┬────┬────┬────┬────┬────     │ │
    │ │     0s   5s   10s  15s  20s  25s  30s  35s  40s  45s       │ │
    │ └────────────────────────────────────────────────────────────┘ │
    ├────────────────────────────────────────────────────────────────┤
    │ Flow Statistics                                                │
    │ ┌──────────────────────────────────────────────────────────┐   │
    │ │ Flow          │ Packets │ Loss  │ Delay  │ Throughput    │   │
    │ ├───────────────┼─────────┼───────┼────────┼───────────────┤   │
    │ │ CC→Sub1 Poll  │ 450     │ 0.2%  │ 12ms   │ 45 kbps       │   │
    │ │ CC→Sub2 Poll  │ 450     │ 0.0%  │ 8ms    │ 45 kbps       │   │
    │ │ Sub1→CC Resp  │ 448     │ 0.4%  │ 14ms   │ 89 kbps       │   │
    │ └──────────────────────────────────────────────────────────┘   │
    └────────────────────────────────────────────────────────────────┘
    """
```

---

## Phase 4: Code Generation Extensions

### 4.1 Extended NS3ScriptGenerator

**File: `services/grid_script_generator.py`**

```python
class GridNS3ScriptGenerator(NS3ScriptGenerator):
    """
    Extended generator for grid-specific simulations.
    
    Adds:
    - Grid node type handling
    - Mixed link types (fiber, microwave, LTE, satellite)
    - SCADA traffic patterns
    - Failure injection scheduling
    - FlowMonitor with grid-specific metrics
    - Custom tracing callbacks
    """
    
    def generate(self, network: NetworkModel, sim_config: SimulationConfig,
                 failure_scenario: Optional[FailureScenario] = None) -> str:
        """Generate complete grid simulation script."""
        
        sections = [
            self._generate_header(network, sim_config),
            self._generate_imports(),
            self._generate_custom_tracers(),
            self._generate_nodes(network),
            self._generate_mixed_channels(network),  # New: handles all link types
            self._generate_internet_stack(network),
            self._generate_ip_assignment(network),
            self._generate_routing(network, sim_config),
            self._generate_scada_applications(network, sim_config),  # New
            self._generate_flow_monitor(sim_config),
            self._generate_custom_metrics(sim_config),  # New
        ]
        
        if failure_scenario:
            sections.append(self._generate_failure_injection(failure_scenario))
        
        sections.extend([
            self._generate_simulation_control(sim_config),
            self._generate_results_collection(),
        ])
        
        return "\n\n".join(sections)
    
    def _generate_scada_applications(self, network: NetworkModel, 
                                      sim_config: SimulationConfig) -> str:
        """Generate SCADA polling applications."""
        lines = ["# ========== SCADA Applications =========="]
        
        for flow in sim_config.flows:
            if isinstance(flow, GridTrafficFlow):
                if flow.traffic_class == GridTrafficClass.SCADA_POLL:
                    lines.extend(self._generate_polling_app(flow))
                elif flow.traffic_class == GridTrafficClass.TELEMETRY:
                    lines.extend(self._generate_telemetry_app(flow))
                # ... etc
        
        return "\n".join(lines)
```

### 4.2 Routing Configuration Generator

**File: `services/routing_generator.py`**

```python
class GridRoutingGenerator:
    """
    Generates routing configuration for grid networks.
    
    Supports:
    - Static routing (deterministic paths for critical traffic)
    - OLSR (dynamic routing with failure recovery)
    - RIP (for simpler dynamic scenarios)
    - Hybrid (static primary + dynamic backup)
    """
    
    def generate_static_routing(self, network: NetworkModel) -> str:
        """Generate Ipv4StaticRoutingHelper configuration."""
        
    def generate_olsr_routing(self, network: NetworkModel) -> str:
        """Generate OlsrHelper configuration for dynamic routing."""
        
    def generate_hybrid_routing(self, network: NetworkModel) -> str:
        """
        Generate hybrid routing:
        - Primary paths: Static routes
        - Backup paths: OLSR with higher metrics
        """
```

---

## Phase 5: Pre-built Templates

### 5.1 Template Library

**File: `templates/grid_templates.py`**

```python
GRID_TEMPLATES = {
    "small_regional": {
        "name": "Small Regional Grid",
        "description": "1 control center, 10 substations, fiber backbone",
        "nodes": {
            "control_centers": 1,
            "substations": 10,
            "rtus_per_substation": 2,
        },
        "links": {
            "backbone": "FIBER",
            "substation_lan": "CSMA",
        }
    },
    "medium_utility": {
        "name": "Medium Utility Grid",
        "description": "Primary + backup CC, 30 substations, mixed media",
        "nodes": {
            "control_centers": 2,
            "substations": 30,
            "rtus_per_substation": 3,
        },
        "links": {
            "backbone": "FIBER",
            "backup_backbone": "MICROWAVE",
            "substation_lan": "CSMA",
            "remote_substations": "CELLULAR_LTE",
        }
    },
    "resilient_grid": {
        "name": "Resilient Grid with Satellite Backup",
        "description": "Full redundancy with satellite last-resort",
        # ...
    }
}
```

### 5.2 Failure Scenario Templates

**File: `templates/failure_scenarios.py`**

```python
FAILURE_SCENARIOS = {
    "single_link_failure": {
        "name": "Single Link Failure",
        "description": "Primary backbone link fails, tests failover",
        "events": [
            {"type": "LINK_DOWN", "target": "backbone_1", "time": 10.0, "duration": 30.0}
        ]
    },
    "control_center_failover": {
        "name": "Control Center Failover",
        "description": "Primary CC loses power, backup takes over",
        "events": [
            {"type": "NODE_POWER_LOSS", "target": "cc_primary", "time": 15.0, "duration": 120.0}
        ]
    },
    "cascading_failure": {
        "name": "Cascading Failure",
        "description": "Storm damages multiple links progressively",
        "events": [
            {"type": "LINK_DOWN", "target": "link_1", "time": 5.0},
            {"type": "LINK_DOWN", "target": "link_2", "time": 8.0},
            {"type": "LINK_DEGRADED", "target": "link_3", "time": 10.0, 
             "params": {"new_data_rate": "10Mbps"}},
            {"type": "NODE_POWER_LOSS", "target": "substation_5", "time": 15.0},
        ]
    },
    "cyber_attack_dos": {
        "name": "DoS Attack on Control Center",
        "description": "Simulates bandwidth exhaustion attack",
        "events": [
            {"type": "LINK_CONGESTION", "target": "cc_uplink", "time": 20.0,
             "params": {"queue_fill_percent": 95}}
        ]
    },
    "network_partition": {
        "name": "Network Partition",
        "description": "Network splits into two isolated segments",
        "events": [
            {"type": "PARTITION", "time": 10.0,
             "params": {
                 "group_a": ["cc_primary", "sub_1", "sub_2", "sub_3"],
                 "group_b": ["cc_backup", "sub_4", "sub_5"]
             }}
        ]
    }
}
```

---

## Phase 6: Implementation Schedule

### Sprint 1 (Week 1-2): Foundation
| Task | Priority | Effort |
|------|----------|--------|
| GridNodeType, GridLinkType enums | High | 2h |
| GridNodeModel, GridLinkModel dataclasses | High | 4h |
| GridTrafficClass, GridTrafficFlow models | High | 4h |
| FailureEvent, FailureScenario models | High | 4h |
| Unit tests for all models | High | 4h |

### Sprint 2 (Week 3-4): Code Generation
| Task | Priority | Effort |
|------|----------|--------|
| Extend NS3ScriptGenerator for grid types | High | 8h |
| PointToPointHelper for fiber/microwave | High | 4h |
| CsmaHelper for substation LANs | High | 4h |
| LteHelper for cellular backup | Medium | 6h |
| WifiHelper for mesh backup | Medium | 4h |
| FailureInjector code generation | High | 8h |
| Static/OLSR/RIP routing generation | High | 6h |
| Integration tests | High | 4h |

### Sprint 3 (Week 5-6): GUI - Part 1
| Task | Priority | Effort |
|------|----------|--------|
| Grid node palette icons | High | 4h |
| Node properties panel extensions | High | 4h |
| Link type selector | High | 2h |
| Traffic pattern editor (basic) | High | 8h |
| Substation grouping visualization | Medium | 6h |

### Sprint 4 (Week 7-8): GUI - Part 2
| Task | Priority | Effort |
|------|----------|--------|
| FailureScenarioPanel | High | 8h |
| EventTimelineWidget | High | 12h |
| Event properties dialog | High | 4h |
| Drag-and-drop event scheduling | Medium | 6h |

### Sprint 5 (Week 9-10): Metrics & Templates
| Task | Priority | Effort |
|------|----------|--------|
| GridMetricsDashboard | High | 10h |
| FlowMonitor integration | High | 4h |
| Custom tracing for SCADA metrics | High | 6h |
| Grid template library | Medium | 4h |
| Failure scenario templates | Medium | 4h |
| Export/import scenarios | Medium | 4h |

### Sprint 6 (Week 11-12): Polish & Testing
| Task | Priority | Effort |
|------|----------|--------|
| End-to-end testing | High | 12h |
| Documentation | High | 8h |
| Example scenarios | High | 6h |
| Performance optimization | Medium | 4h |
| Bug fixes & polish | High | 10h |

---

## File Structure Summary

```
ns3gui_v2/
├── models/
│   ├── __init__.py
│   ├── network.py              # V1 (extended)
│   ├── simulation.py           # V1 (extended)
│   ├── project.py              # V1
│   ├── grid_nodes.py           # NEW: Grid node types
│   ├── grid_links.py           # NEW: Grid link types
│   ├── grid_traffic.py         # NEW: SCADA traffic classes
│   └── failure_events.py       # NEW: Failure injection models
├── services/
│   ├── __init__.py
│   ├── ns3_generator.py        # V1 (base class)
│   ├── grid_script_generator.py # NEW: Extended generator
│   ├── failure_injector.py     # NEW: Failure code generation
│   ├── routing_generator.py    # NEW: Routing configuration
│   └── metrics_collector.py    # NEW: Results parsing
├── views/
│   ├── __init__.py
│   ├── main_window.py          # V1 (extended)
│   ├── canvas.py               # V1 (extended for grid icons)
│   ├── grid_editor.py          # NEW: Grid-specific editor
│   ├── failure_panel.py        # NEW: Failure scenario panel
│   ├── traffic_pattern_editor.py # NEW: SCADA patterns
│   ├── metrics_dashboard.py    # NEW: Metrics display
│   └── widgets/
│       ├── event_timeline.py   # NEW: Timeline widget
│       ├── node_palette.py     # Extended for grid types
│       └── property_panels.py  # Extended for grid properties
├── templates/
│   ├── grid_templates.py       # NEW: Network templates
│   └── failure_scenarios.py    # NEW: Scenario templates
├── tests/
│   ├── test_grid_models.py
│   ├── test_failure_injection.py
│   ├── test_code_generation.py
│   └── test_integration.py
└── resources/
    └── icons/
        ├── control_center.svg
        ├── substation.svg
        ├── rtu.svg
        ├── ied.svg
        └── ...
```

---

## Success Criteria

1. **Model Completeness**: All grid node types, link types, and traffic classes defined
2. **Code Generation**: Generated ns-3 scripts run without errors
3. **Failure Injection**: Events trigger at correct times with expected effects
4. **Routing Failover**: Dynamic routing converges after failures (OLSR < 10s)
5. **Metrics Accuracy**: FlowMonitor data matches expected SCADA patterns
6. **GUI Usability**: Can build a 20-substation scenario in < 10 minutes
7. **Scenario Playback**: Timeline clearly shows event sequence

---

## Next Steps

1. **Confirm priorities** - Which phase to start with?
2. **Review V1 code** - Identify exact extension points
3. **Begin Sprint 1** - Implement foundation models
4. **Create test fixtures** - Sample grid topology for testing

Ready to begin implementation when you are.