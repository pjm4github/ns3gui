# ns-3 PyQt GUI Framework Architecture

## Overview

This document describes the architecture for a PyQt6-based graphical interface for the ns-3 network simulator. The design follows a **Model-View-Controller (MVC)** pattern with a dedicated **Service Layer** to handle ns-3 integration and I/O operations.

---

## Layer Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    PRESENTATION LAYER                           │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌───────────┐  │
│  │ MainWindow  │ │  Topology   │ │   Panels    │ │  Dialogs  │  │
│  │             │ │   Canvas    │ │  & Docks    │ │           │  │
│  └─────────────┘ └─────────────┘ └─────────────┘ └───────────┘  │
├─────────────────────────────────────────────────────────────────┤
│                    CONTROLLER LAYER                             │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌───────────┐  │
│  │  Topology   │ │ Simulation  │ │Visualization│ │  Config   │  │
│  │ Controller  │ │ Controller  │ │ Controller  │ │Controller │  │
│  └─────────────┘ └─────────────┘ └─────────────┘ └───────────┘  │
├─────────────────────────────────────────────────────────────────┤
│                      MODEL LAYER                                │
│  ┌─────────────────────────────┐ ┌─────────────────────────────┐│
│  │       Domain Models         │ │       State Models          ││
│  │  Network, Node, Channel,    │ │  SimState, Selection,       ││
│  │  Application, Protocol      │ │  UndoStack, Clipboard       ││
│  └─────────────────────────────┘ └─────────────────────────────┘│
├─────────────────────────────────────────────────────────────────┤
│                     SERVICE LAYER                               │
│  ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌─────────────────┐  │
│  │ NS3Bridge │ │  Script   │ │  Trace    │ │    Project      │  │
│  │           │ │ Generator │ │  Parser   │ │    Manager      │  │
│  └───────────┘ └───────────┘ └───────────┘ └─────────────────┘  │
├─────────────────────────────────────────────────────────────────┤
│                   ns-3 CORE (C++/Python)                        │
│  ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌─────────────────┐  │
│  │ Simulator │ │   Nodes   │ │ NetDevices│ │   FlowMonitor   │  │
│  └───────────┘ └───────────┘ └───────────┘ └─────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 1. Presentation Layer

### 1.1 MainWindow
The central application window managing layout and coordination.

```python
class MainWindow(QMainWindow):
    """
    Primary application window.
    
    Responsibilities:
    - Menu bar and toolbar management
    - Dock widget arrangement
    - Global keyboard shortcuts
    - Status bar updates
    - Window state persistence
    """
    
    # Key components
    topology_canvas: TopologyCanvas
    property_panel: PropertyPanel
    simulation_toolbar: SimulationToolbar
    console_dock: ConsoleDock
    stats_dock: StatsDock
```

### 1.2 TopologyCanvas
The visual network editor using Qt's Graphics View Framework.

```python
class TopologyCanvas(QGraphicsView):
    """
    Interactive network topology editor.
    
    Features:
    - Drag-and-drop node placement
    - Bezier curve link drawing
    - Rubber-band selection
    - Zoom and pan navigation
    - Grid snapping
    - Mini-map overlay
    
    Signals:
        nodeAdded(NodeGraphicsItem)
        nodeRemoved(str)  # node_id
        linkCreated(str, str)  # source_id, target_id
        selectionChanged(list[str])
    """
    
class NodeGraphicsItem(QGraphicsItem):
    """Visual representation of a network node."""
    
class LinkGraphicsItem(QGraphicsPathItem):
    """Visual representation of a network link/channel."""
```

### 1.3 Panel Widgets

```python
class PropertyPanel(QWidget):
    """
    Context-sensitive property editor.
    Displays editable attributes for selected node/link.
    Uses QDataWidgetMapper for model binding.
    """

class NodePalette(QListWidget):
    """
    Draggable node type palette.
    Categories: Hosts, Routers, Switches, Wireless, LTE
    """

class SimulationToolbar(QToolBar):
    """
    Simulation control buttons:
    - Run/Pause/Stop
    - Speed slider
    - Time display
    - Progress indicator
    """

class ConsoleOutput(QPlainTextEdit):
    """
    Logging console with severity filtering.
    Captures ns-3 log output and script errors.
    """
```

### 1.4 Visualization Widgets

```python
class StatsPanel(QWidget):
    """
    Real-time statistics dashboard.
    
    Contains:
    - ThroughputChart (PyQtGraph PlotWidget)
    - LatencyChart
    - PacketLossIndicator
    - FlowTable (QTableView)
    """

class PacketAnimator:
    """
    Animates packet flow on TopologyCanvas.
    Uses QPropertyAnimation for smooth transitions.
    Color-codes by protocol/application.
    """

class TimelineWidget(QWidget):
    """
    Simulation event timeline.
    Shows discrete events on a scrollable track.
    Allows jumping to specific simulation times.
    """
```

---

## 2. Controller Layer

### 2.1 TopologyController

```python
class TopologyController(QObject):
    """
    Manages topology editing operations.
    
    Responsibilities:
    - Translates UI actions to model changes
    - Manages undo/redo stack
    - Validates topology constraints
    - Coordinates with SelectionModel
    
    Key Methods:
        add_node(node_type: str, position: QPointF) -> NodeModel
        remove_node(node_id: str)
        create_link(source_id: str, target_id: str, channel_type: str)
        remove_link(link_id: str)
        duplicate_selection()
        align_nodes(alignment: Alignment)
    """
    
    # Signals
    topologyChanged = Signal()
    validationError = Signal(str)
```

### 2.2 SimulationController

```python
class SimulationController(QObject):
    """
    Controls simulation lifecycle.
    
    Responsibilities:
    - Builds ns-3 simulation from model
    - Manages simulation thread
    - Dispatches trace events to UI
    - Collects and aggregates results
    
    Key Methods:
        start_simulation()
        pause_simulation()
        stop_simulation()
        set_speed(multiplier: float)
        seek_to_time(sim_time: float)
    
    Signals:
        simulationStarted()
        simulationPaused()
        simulationStopped()
        simulationProgress(current_time: float, end_time: float)
        packetEvent(PacketEventData)
        statsUpdated(StatsSnapshot)
    """
```

### 2.3 VisualizationController

```python
class VisualizationController(QObject):
    """
    Coordinates real-time visualization updates.
    
    Responsibilities:
    - Throttles UI updates for performance
    - Manages animation queue
    - Updates chart data series
    - Handles visualization settings
    """
```

### 2.4 ConfigurationController

```python
class ConfigurationController(QObject):
    """
    Manages node/link/application configuration.
    
    Responsibilities:
    - Populates property panels
    - Validates configuration changes
    - Applies defaults from templates
    - Manages protocol stack configuration
    """
```

---

## 3. Model Layer

### 3.1 Domain Models

```python
@dataclass
class NetworkModel:
    """
    Root model for entire network topology.
    
    Attributes:
        nodes: dict[str, NodeModel]
        channels: dict[str, ChannelModel]
        applications: dict[str, ApplicationModel]
        global_config: GlobalConfig
    
    Methods:
        to_dict() -> dict  # Serialization
        from_dict(data: dict) -> NetworkModel
        validate() -> list[ValidationError]
    """

@dataclass
class NodeModel:
    """
    Represents a network node.
    
    Attributes:
        id: str
        node_type: NodeType  # HOST, ROUTER, SWITCH, AP, UE, ENB
        name: str
        position: tuple[float, float]
        
        # Network configuration
        interfaces: list[InterfaceConfig]
        ip_addresses: list[str]
        
        # Mobility
        mobility_model: MobilityConfig | None
        
        # Protocol stack
        internet_stack: InternetStackConfig
        
        # Visual
        icon: str
        color: str
    """

@dataclass  
class ChannelModel:
    """
    Represents a network channel/link.
    
    Attributes:
        id: str
        channel_type: ChannelType  # P2P, CSMA, WIFI, LTE
        endpoints: tuple[str, str]  # node IDs
        
        # Physical parameters
        data_rate: str  # e.g., "100Mbps"
        delay: str  # e.g., "2ms"
        error_model: ErrorModelConfig | None
        
        # Wireless specific
        wifi_standard: str | None
        propagation_model: str | None
    """

@dataclass
class ApplicationModel:
    """
    Represents an ns-3 application.
    
    Attributes:
        id: str
        app_type: AppType  # UDP_ECHO, BULK_SEND, ON_OFF, PACKET_SINK
        node_id: str
        
        # Timing
        start_time: str
        stop_time: str
        
        # App-specific config
        parameters: dict[str, Any]
    """
```

### 3.2 State Models

```python
class SimulationState(QObject):
    """
    Observable simulation state.
    
    Properties (with change signals):
        status: SimStatus  # IDLE, RUNNING, PAUSED, COMPLETED, ERROR
        current_time: float
        end_time: float
        speed_multiplier: float
        
    Computed:
        progress: float  # 0.0 - 1.0
        is_running: bool
    """

class SelectionModel(QObject):
    """
    Tracks selected items in topology.
    
    Signals:
        selectionChanged(selected_ids: list[str])
    
    Methods:
        select(item_id: str, extend: bool = False)
        deselect(item_id: str)
        clear()
        select_all()
    """
```

---

## 4. Service Layer

### 4.1 NS3Bridge

The critical integration layer between PyQt and ns-3.

```python
class NS3Bridge(QObject):
    """
    Bridge between GUI models and ns-3 simulation core.
    
    Responsibilities:
    - Translates NetworkModel to ns-3 objects
    - Runs simulation in separate thread/process
    - Captures trace callbacks
    - Marshals data between ns-3 and Qt
    
    Threading Strategy:
    - ns-3 runs in QThread or subprocess
    - Uses signals/slots for thread-safe communication
    - Queue-based event dispatch
    
    Key Methods:
        build_simulation(network: NetworkModel)
        run(duration: float)
        pause()
        resume()
        stop()
        get_flow_stats() -> FlowStatsData
    
    Signals:
        packetTransmitted(PacketEvent)
        packetReceived(PacketEvent)
        packetDropped(PacketEvent)
        flowStatsUpdated(FlowStats)
        simulationFinished(ResultsSummary)
    """
    
    def build_simulation(self, network: NetworkModel):
        """
        Constructs ns-3 simulation from model.
        
        Steps:
        1. Create NodeContainer for each node
        2. Install appropriate NetDevices
        3. Configure channels with parameters
        4. Install InternetStack
        5. Assign IP addresses
        6. Install applications
        7. Configure FlowMonitor
        8. Connect trace sources
        """
        pass
```

### 4.2 ScriptGenerator

```python
class ScriptGenerator:
    """
    Generates ns-3 Python scripts from GUI models.
    
    Allows users to:
    - Export simulation as standalone script
    - Learn ns-3 scripting from GUI actions
    - Customize generated code
    
    Methods:
        generate(network: NetworkModel) -> str
        generate_with_comments(network: NetworkModel) -> str
    """
```

### 4.3 TraceParser

```python
class TraceParser:
    """
    Parses ns-3 trace files for visualization.
    
    Supported formats:
    - ASCII trace (.tr)
    - PCAP files (.pcap)
    - FlowMonitor XML
    
    Methods:
        parse_ascii_trace(path: Path) -> list[TraceEvent]
        parse_pcap(path: Path) -> list[PacketData]
        parse_flow_monitor(path: Path) -> FlowMonitorResults
    """
```

### 4.4 ProjectManager

```python
class ProjectManager:
    """
    Handles project persistence.
    
    Project structure:
        my_simulation.ns3gui/
        ├── project.json          # Metadata
        ├── topology.json         # NetworkModel
        ├── settings.json         # Simulation settings
        ├── results/              # Simulation outputs
        │   ├── run_001/
        │   │   ├── flow_stats.xml
        │   │   └── traces/
        │   └── run_002/
        └── scripts/              # Generated/custom scripts
    
    Methods:
        new_project(path: Path)
        open_project(path: Path) -> NetworkModel
        save_project()
        export_scenario(format: str)  # JSON, XML
    """
```

---

## 5. Data Flow Examples

### 5.1 Adding a Node

```
User drags "Router" from palette to canvas
    │
    ▼
TopologyCanvas.dropEvent()
    │
    ├─► TopologyController.add_node("router", position)
    │       │
    │       ├─► UndoStack.push(AddNodeCommand)
    │       │
    │       ├─► NetworkModel.add_node(NodeModel)
    │       │
    │       └─► emit topologyChanged
    │
    └─► TopologyCanvas creates NodeGraphicsItem
```

### 5.2 Running Simulation

```
User clicks "Run" button
    │
    ▼
SimulationController.start_simulation()
    │
    ├─► Validate NetworkModel
    │
    ├─► NS3Bridge.build_simulation(network_model)
    │       │
    │       └─► Creates ns-3 objects in worker thread
    │
    ├─► NS3Bridge.run(duration)
    │       │
    │       └─► Simulator::Run() in worker thread
    │               │
    │               └─► Trace callbacks emit signals
    │
    └─► VisualizationController receives signals
            │
            ├─► Updates StatsCharts
            │
            └─► Triggers PacketAnimator
```

---

## 6. Threading Model

```
┌─────────────────────────────────────────────────────────┐
│                     MAIN THREAD                         │
│                                                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐  │
│  │     GUI     │  │ Controllers │  │     Models      │  │
│  │   Widgets   │◄─┤             ├─►│   (thread-safe  │  │
│  │             │  │             │  │    read-only)   │  │
│  └─────────────┘  └─────────────┘  └─────────────────┘  │
│         ▲                                    ▲          │
│         │         Qt Signals/Slots           │          │
│         │         (queued connection)        │          │
│         ▼                                    ▼          │
├─────────────────────────────────────────────────────────┤
│                   SIMULATION THREAD                     │
│                                                         │
│  ┌─────────────────────────────────────────────────┐    │
│  │                  NS3Bridge                      │    │
│  │  ┌───────────┐  ┌───────────┐  ┌─────────────┐  │    │
│  │  │ Simulator │  │   Trace   │  │    Flow     │  │    │
│  │  │    Run    │  │ Callbacks │  │   Monitor   │  │    │
│  │  └───────────┘  └───────────┘  └─────────────┘  │    │
│  └─────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────┘
```

**Key Threading Principles:**
1. All GUI updates happen on main thread
2. ns-3 simulation runs in dedicated QThread
3. Communication via Qt queued signals
4. Models are immutable during simulation
5. Results copied to main thread atomically

---

## 7. Directory Structure

```
ns3_gui/
├── __init__.py
├── main.py                     # Application entry point
├── app.py                      # QApplication setup
│
├── presentation/
│   ├── __init__.py
│   ├── main_window.py
│   ├── canvas/
│   │   ├── topology_canvas.py
│   │   ├── graphics_items.py
│   │   └── tools.py            # Selection, pan, link tools
│   ├── panels/
│   │   ├── property_panel.py
│   │   ├── node_palette.py
│   │   ├── console.py
│   │   └── stats_panel.py
│   ├── dialogs/
│   │   ├── node_config.py
│   │   ├── app_wizard.py
│   │   └── simulation_settings.py
│   └── visualization/
│       ├── charts.py
│       ├── packet_animator.py
│       └── timeline.py
│
├── controllers/
│   ├── __init__.py
│   ├── topology_controller.py
│   ├── simulation_controller.py
│   ├── visualization_controller.py
│   └── config_controller.py
│
├── models/
│   ├── __init__.py
│   ├── network.py
│   ├── node.py
│   ├── channel.py
│   ├── application.py
│   ├── state.py
│   └── commands.py             # Undo/redo commands
│
├── services/
│   ├── __init__.py
│   ├── ns3_bridge.py
│   ├── script_generator.py
│   ├── trace_parser.py
│   ├── project_manager.py
│   └── results_exporter.py
│
├── resources/
│   ├── icons/
│   ├── styles/
│   └── templates/
│
└── tests/
    ├── test_models.py
    ├── test_controllers.py
    └── test_ns3_bridge.py
```

---

## 8. Technology Stack

| Component | Technology |
|-----------|------------|
| GUI Framework | PyQt6 |
| Charting | PyQtGraph |
| ns-3 Bindings | ns3-python (cppyy-based) |
| Serialization | JSON (orjson for performance) |
| Database | SQLite (results caching) |
| Testing | pytest + pytest-qt |
| Packaging | PyInstaller |

---

## 9. Extension Points

### 9.1 Plugin System

```python
class NodeTypePlugin(Protocol):
    """Interface for custom node types."""
    
    @property
    def node_type_id(self) -> str: ...
    
    @property
    def display_name(self) -> str: ...
    
    @property
    def icon(self) -> QIcon: ...
    
    def create_ns3_node(self, config: dict) -> ns.Node: ...
    
    def get_config_widget(self) -> QWidget: ...
```

### 9.2 Custom Visualizations

```python
class VisualizationPlugin(Protocol):
    """Interface for custom visualization panels."""
    
    def create_widget(self) -> QWidget: ...
    
    def on_packet_event(self, event: PacketEvent): ...
    
    def on_stats_update(self, stats: StatsSnapshot): ...
```

---

## 10. Future Considerations

1. **Distributed Simulation**: Support for MPI-based distributed ns-3
2. **3D Visualization**: OpenGL-based 3D topology view for mobile scenarios
3. **Machine Learning Integration**: Interface with ns3-gym for RL experiments
4. **Cloud Execution**: Run simulations on remote servers
5. **Collaboration**: Multi-user editing with operational transforms
