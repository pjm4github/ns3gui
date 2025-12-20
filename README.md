# ns-3 Network Simulator GUI

A PyQt6-based visual interface for designing and simulating network topologies using the ns-3 discrete-event network simulator.

**Version:** 1.0

## Documentation

| Document | Description |
|----------|-------------|
| [NS3_GUI_V1_SUMMARY.md](docs/NS3_GUI_V1_SUMMARY.md) | Comprehensive architecture and feature documentation |
| [NS3_GUI_QUICK_REF.md](docs/NS3_GUI_QUICK_REF.md) | Quick reference card for developers |

---

## Features

### Topology Editor
- **Visual node placement** - Host, Router, Switch, Access Point, Station
- **Port connection points** - Visual indicators on each node showing available ports
- **B-spline curved links** - Smooth link curves with adjustable control points
- **Right-click and drag** between nodes/ports to create links
- **Selection** - Click to select nodes, links, or individual ports
- **Zoom/Pan** - Mouse wheel to zoom, middle-click to pan
- **Route visualization** - Highlight routing paths on canvas

### Node Types
| Type | Description |
|------|-------------|
| Host | End host/workstation |
| Router | Layer 3 router with routing table |
| Switch | Layer 2 bridge |
| Access Point | WiFi access point |
| Station | WiFi client |

### Property Panel
- View and edit node properties (name, type, description)
- Port-level configuration with L1/L2/L3 settings
- Switch subnet configuration for automatic IP assignment
- Link properties (channel type, data rate, delay)
- **Routing table configuration** - Manual static routes for hosts and routers

### ns-3 Integration
- **Auto-detection** of ns-3 installation in WSL
- **Script generation** - Generates ns-3 Python scripts from topology
- **Traffic flows** - Configure UDP Echo, OnOff, BulkSend traffic
- **Custom socket applications** - Write Python code for custom traffic
- **Simulation execution** - Runs ns-3 as WSL subprocess
- **Results parsing** - FlowMonitor XML results displayed in Statistics panel
- **Packet animation** - Replay packet flow after simulation

### Statistics Panel
- Summary statistics (packets, throughput, latency)
- Per-flow detailed statistics table
- Console output with real-time simulation logs
- Packet animation replay with timeline controls

### Project System
- Project-based workflow with structured directories
- Save/load topologies with routing tables and traffic flows
- Simulation results archival with timestamps
- Application script persistence per node

---

## Installation

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt
```

### ns-3 Setup (WSL - Required for Simulation)

1. Install WSL2 with Ubuntu:
   ```bash
   wsl --install
   ```

2. Inside WSL, install ns-3:
   ```bash
   sudo apt update
   sudo apt install g++ python3 python3-dev cmake ninja-build git
   sudo apt install libboost-all-dev libgsl-dev libsqlite3-dev
   pip install cppyy --break-system-packages
   
   git clone https://gitlab.com/nsnam/ns-3-dev.git ~/ns-3-dev
   cd ~/ns-3-dev
   ./ns3 configure --enable-python-bindings
   ./ns3 build
   ```

3. The GUI will auto-detect ns-3, or configure the path manually via Settings

---

## Running

```bash
python main.py
```

---

## Usage

### Creating a Topology

1. **Add Nodes**: Click a node type in the left palette to add it
2. **Position Nodes**: Drag nodes to arrange your topology
3. **Create Links**: Right-click on a node/port and drag to another to connect

### Port Selection

- Nodes display small circles representing ports
- **Left-click** a port to select it (highlighted in Property Panel)
- **Right-click** a port to start link creation from that specific port
- Port colors: Gray=available, Green=connected, Red=disabled, Orange=selected

### Custom Socket Applications

Double-click any node to open the Socket Application Editor:
- Write custom Python code extending `ApplicationBase`
- Define `setup()`, `create_payload()`, `handle_receive()` methods
- Applications are saved with the project

### Configuring Routing Tables

1. **Select a node** (host or router)
2. **Click "Edit Routing Table..."** in the Property Panel
3. **Choose routing mode**:
   - **Auto**: ns-3's GlobalRoutingHelper computes routes automatically
   - **Manual**: Configure static routes yourself
4. **For Manual mode**:
   - Click **"Auto-Fill Routes"** to generate suggested routes
   - **Add Route**: Manually add destination, gateway, interface
   - For hosts, use the **Default Gateway** shortcut field

### Visualizing Routes

- **View → Routes → Show All Routes** (Ctrl+Shift+R): Highlights all manual routes
- **View → Routes → Show Routes From Selected Node**: Shows outgoing routes
- **View → Routes → Show Routes To Selected Node**: Shows incoming paths
- **Escape**: Clear route highlights

### Running a Simulation

1. **Configure ns-3 Path**: Auto-detected or set via Simulation menu
2. **Click Run** (F5): Opens simulation configuration dialog
3. **Add Traffic Flows**: Define source/destination and traffic parameters
4. **Configure Options**: Set duration, enable FlowMonitor, etc.
5. **Start Simulation**: ns-3 script is generated and executed
6. **View Results**: Statistics appear in the Stats panel after completion
7. **Replay Animation**: Use playback controls to visualize packet flow

---

## Project Structure

```
ns3_gui_mvp/
├── main.py                     # Application entry point
├── requirements.txt            # Python dependencies
├── pytest.ini                  # Test configuration
├── run_tests.py               # Test runner
│
├── docs/
│   ├── NS3_GUI_V1_SUMMARY.md  # Full architecture documentation
│   └── NS3_GUI_QUICK_REF.md   # Quick reference for developers
│
├── models/
│   ├── network.py              # NetworkModel, NodeModel, LinkModel, PortConfig, RouteEntry
│   └── simulation.py           # SimulationConfig, TrafficFlow, FlowStats
│
├── views/
│   ├── main_window.py          # Main window, menus, toolbars, dialogs
│   ├── topology_canvas.py      # QGraphicsView canvas with nodes, links, ports
│   ├── property_panel.py       # Property editors
│   ├── node_palette.py         # Node type palette
│   ├── stats_panel.py          # Statistics display
│   ├── playback_controls.py    # Packet animation timeline
│   ├── socket_app_editor.py    # Custom application code editor
│   ├── help_dialog.py          # ns-3 API reference
│   ├── settings_dialog.py      # Application settings
│   └── project_dialog.py       # Project management dialogs
│
├── services/
│   ├── project_manager.py      # Save/load projects
│   ├── ns3_generator.py        # Generate ns-3 Python scripts
│   ├── simulation_runner.py    # WSL subprocess execution
│   ├── ns3_detector.py         # Auto-detect ns-3 installation
│   ├── results_parser.py       # Parse FlowMonitor XML
│   ├── trace_player.py         # Packet trace replay
│   ├── script_parser.py        # Import existing ns-3 scripts
│   └── topology_converter.py   # Convert parsed scripts to model
│
├── resources/
│   └── icons/                  # Node type icons
│
└── tests/
    ├── unit/                   # Unit tests
    ├── integration/            # Integration tests
    └── e2e/                    # End-to-end tests
```

---

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| Delete/Backspace | Delete selected items |
| Ctrl+A | Select all |
| Ctrl+0 | Fit view to contents |
| Ctrl+R | Reset view |
| Ctrl+Shift+R | Toggle route visualization |
| Ctrl+N | New project |
| Ctrl+S | Save |
| Ctrl+O | Open |
| F1 | ns-3 Help dialog |
| F5 | Run simulation |
| Escape | Clear selection / Cancel link / Clear highlights |

---

## Traffic Types

| Type | Protocol | Description |
|------|----------|-------------|
| UDP Echo | UDP | Request/response echo packets |
| OnOff | UDP/TCP | Constant bitrate with on/off periods |
| BulkSend | TCP | Maximum throughput bulk transfer |
| Custom Socket | UDP/TCP | User-defined Python application |

---

## File Formats

### Project Files (.ns3proj directory)

```
my_project.ns3proj/
├── project.json          # Metadata and run history
├── topology.json         # Network topology
├── scripts/
│   ├── gui_simulation.py # Generated ns-3 script
│   ├── app_base.py       # Custom app base class
│   └── apps/             # Node application scripts
└── results/
    └── run_YYYYMMDD_HHMMSS/
        ├── console.log
        ├── stats.json
        ├── flowmon-results.xml
        └── pcap/
```

### Generated Scripts

Python scripts compatible with ns-3's Python bindings (cppyy-based, ns-3.45+)

### Output Files

- `flowmon-results.xml` - FlowMonitor statistics
- `trace.tr` - ASCII trace (if enabled)
- `*.pcap` - Packet captures (if enabled)

---

## Testing

```bash
python run_tests.py           # All tests except slow
python run_tests.py --all     # All tests including e2e
python run_tests.py --unit    # Unit tests only
python run_tests.py --cov     # With coverage report
```

---

## Requirements

- Python 3.11+
- PyQt6 6.4+
- Windows 10/11 with WSL2
- ns-3.45+ with Python bindings (in WSL)

---

## License

MIT
---

## V2 Grid Extensions

### Grid Infrastructure Support

V2 adds comprehensive support for modeling electric grid SCADA/EMS communication networks.

#### Grid Node Types
| Type | Description | Base ns-3 Type |
|------|-------------|----------------|
| Control Center | SCADA/EMS master station | HOST |
| RTU | Remote Terminal Unit | HOST |
| IED | Intelligent Electronic Device | HOST |
| Relay | Protective Relay | HOST |
| Meter | Smart Meter | HOST |
| Data Concentrator | Data aggregation point | HOST |
| Gateway | Protocol converter/firewall | ROUTER |
| Cellular Gateway | Cellular modem gateway | ROUTER |

#### Grid Link Types
| Type | Data Rate | Latency | ns-3 Helper |
|------|-----------|---------|-------------|
| Fiber | 1 Gbps | ~0.1ms | PointToPointHelper |
| Microwave | 100 Mbps | ~1ms | PointToPointHelper |
| Licensed Radio | 9.6 kbps | ~50ms | PointToPointHelper |
| Cellular LTE | 50 Mbps | ~30ms | PointToPointHelper* |
| Satellite GEO | 5 Mbps | ~540ms RTT | PointToPointHelper |
| Satellite LEO | 50 Mbps | ~40ms RTT | PointToPointHelper |
| Ethernet LAN | 1 Gbps | ~0.1ms | CsmaHelper |

*Full LTE requires LteHelper with EPC; simplified P2P model used by default.

#### SCADA Traffic Classes
- **SCADA Integrity Poll** - Full data scan (60s interval)
- **SCADA Exception Poll** - Change-based polling (4s interval)
- **GOOSE** - IEC 61850 protection messages (<4ms)
- **Control Select/Operate** - SBO command sequence
- **Sampled Values** - Continuous waveform data
- **Telemetry** - Analog/status updates
- **Heartbeat** - Supervision messages (30s)
- **Time Sync** - PTP/NTP synchronization

#### Failure Injection Types
- **Link Down/Up** - Complete link failure/recovery
- **Link Degraded** - Increased BER/packet loss
- **Link Flapping** - Intermittent connectivity
- **Node Power Loss** - All interfaces disabled
- **Node Reboot** - Temporary outage with recovery
- **Network Partition** - Segment isolation
- **DoS Attack** - Traffic flooding
- **Cascading Failure** - Sequential failures with delays

### Quick Start (V2 Grid Features)

```python
from models import (
    NetworkModel, SimulationConfig,
    GridNodeModel, GridNodeType,
    GridLinkModel, GridLinkType,
    GridTrafficFlow, GridTrafficClass,
    create_single_link_failure,
    PollingSchedule,
)
from services.grid_ns3_generator import GridNS3Generator

# Create network
network = NetworkModel()

# Create control center and RTUs (direct instantiation - no factories)
cc = GridNodeModel(grid_type=GridNodeType.CONTROL_CENTER, name="EMS")
rtu1 = GridNodeModel(grid_type=GridNodeType.RTU, name="RTU_Sub1", substation_id="sub1")
rtu2 = GridNodeModel(grid_type=GridNodeType.RTU, name="RTU_Sub2", substation_id="sub2")

network.nodes[cc.id] = cc
network.nodes[rtu1.id] = rtu1
network.nodes[rtu2.id] = rtu2

# Create links - fiber primary, satellite backup
fiber = GridLinkModel(
    grid_link_type=GridLinkType.FIBER,
    source_node_id=cc.id,
    target_node_id=rtu1.id,
    distance_km=50.0,
)
satellite = GridLinkModel(
    grid_link_type=GridLinkType.SATELLITE_GEO,
    source_node_id=cc.id,
    target_node_id=rtu2.id,
)

network.links[fiber.id] = fiber
network.links[satellite.id] = satellite

# Create SCADA polling traffic
poll1 = GridTrafficFlow(
    traffic_class=GridTrafficClass.SCADA_EXCEPTION_POLL,
    source_node_id=cc.id,
    target_node_id=rtu1.id,
)
poll2 = GridTrafficFlow(
    traffic_class=GridTrafficClass.SCADA_EXCEPTION_POLL,
    source_node_id=cc.id,
    target_node_id=rtu2.id,
)

sim_config = SimulationConfig(duration=120.0, flows=[poll1, poll2])

# Create failure scenario - fiber fails at t=30s for 15s
failure = create_single_link_failure(
    link_id=fiber.id,
    trigger_time_s=30.0,
    duration_s=15.0,
)

# Generate ns-3 script
generator = GridNS3Generator()
script = generator.generate(network, sim_config, failure_scenario=failure)

# Save to file
with open("grid_simulation.py", "w") as f:
    f.write(script)
```

### Generated Script Features

The `GridNS3Generator` produces ns-3 Python scripts with:

1. **Mixed Channel Types**
   - Fiber/copper → PointToPointHelper with appropriate rates
   - LAN → CsmaHelper for shared medium
   - Satellite → PointToPointHelper with high delay (540ms RTT for GEO)
   - Cellular → Simplified P2P model (full LTE available via LteHelper)

2. **Error Models**
   - Automatic BER configuration based on link type
   - RateErrorModel for bit errors
   - BurstErrorModel for bursty errors

3. **SCADA Applications**
   - Polling traffic using UdpEchoClient/Server
   - GOOSE approximated with OnOff application
   - Control commands with SBO timing

4. **Failure Injection**
   - `Simulator.Schedule()` for timed events
   - Link disable/enable via ReceiveEnable attribute
   - Node failure by disabling all interfaces
   - Error rate modification for degradation

5. **Routing**
   - Global routing (default)
   - Static routes for manual configuration
   - OLSR/AODV/RIP protocol setup (when specified)

### Architecture

```
GridNS3Generator (extends NS3ScriptGenerator)
├── _generate_grid_channels()     # Mixed link types
├── _generate_grid_link()         # Per-link type handling
├── _generate_error_model()       # BER configuration
├── _generate_grid_routing()      # Multi-protocol routing
├── _generate_grid_applications() # SCADA traffic
│   ├── _generate_polling_application()
│   ├── _generate_goose_application()
│   └── _generate_control_application()
└── _generate_failure_injection() # Scheduled failures
    └── _generate_failure_event_callbacks()
```

### Model Inheritance

V2 models properly extend V1 base classes:

```
NodeModel (V1)
    └── GridNodeModel (V2)
        - grid_type → auto-sets node_type
        - grid_role, scan_class, protocols
        - DNP3/IEC61850 configuration

LinkModel (V1)
    └── GridLinkModel (V2)
        - grid_link_type → auto-sets channel_type
        - BER, reliability, MTBF/MTTR
        - Wireless/cellular/satellite params

TrafficFlow (V1)
    └── GridTrafficFlow (V2)
        - traffic_class → auto-sets application
        - Priority (DSCP), timeout, retry
        - DNP3/GOOSE message config
```

This inheritance means grid models work seamlessly with existing V1 infrastructure:
- `NetworkModel.nodes` accepts `GridNodeModel`
- Base `NS3ScriptGenerator` can process grid models
- Serialization works automatically


