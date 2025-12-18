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