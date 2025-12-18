# ns-3 Network Simulator GUI - Version 1.0 Summary

## Overview

A PyQt6-based graphical interface for designing, simulating, and analyzing network topologies using the ns-3 discrete-event network simulator. The application runs on Windows with ns-3 executing in WSL (Windows Subsystem for Linux).

---

## Architecture

### Layer Structure

```
┌─────────────────────────────────────────────────────────────────┐
│                    PRESENTATION LAYER                           │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌───────────┐  │
│  │ MainWindow  │ │  Topology   │ │   Panels    │ │  Dialogs  │  │
│  │             │ │   Canvas    │ │  & Docks    │ │           │  │
│  └─────────────┘ └─────────────┘ └─────────────┘ └───────────┘  │
├─────────────────────────────────────────────────────────────────┤
│                      MODEL LAYER                                │
│  ┌─────────────────────────────┐ ┌─────────────────────────────┐│
│  │       Domain Models         │ │       State Models          ││
│  │  NetworkModel, NodeModel,   │ │  SimulationState,           ││
│  │  LinkModel, PortConfig      │ │  TrafficFlow, FlowStats     ││
│  └─────────────────────────────┘ └─────────────────────────────┘│
├─────────────────────────────────────────────────────────────────┤
│                     SERVICE LAYER                               │
│  ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌─────────────────┐  │
│  │ NS3Bridge │ │  Script   │ │  Results  │ │    Project      │  │
│  │ Generator │ │ Generator │ │  Parser   │ │    Manager      │  │
│  └───────────┘ └───────────┘ └───────────┘ └─────────────────┘  │
├─────────────────────────────────────────────────────────────────┤
│                   ns-3 CORE (WSL/Linux)                         │
│  ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌─────────────────┐  │
│  │ Simulator │ │   Nodes   │ │ NetDevices│ │   FlowMonitor   │  │
│  └───────────┘ └───────────┘ └───────────┘ └─────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### Directory Structure

```
ns3_gui_mvp/
├── main.py                     # Application entry point
├── requirements.txt            # Python dependencies
├── pytest.ini                  # Test configuration
├── run_tests.py               # Test runner script
├── README.md                   # User documentation
│
├── models/
│   ├── __init__.py
│   ├── network.py              # NetworkModel, NodeModel, LinkModel, PortConfig, RouteEntry
│   └── simulation.py           # SimulationConfig, TrafficFlow, FlowStats, SimulationResults
│
├── views/
│   ├── __init__.py
│   ├── main_window.py          # Main window, menus, toolbars, dialogs
│   ├── topology_canvas.py      # QGraphicsView canvas, NodeGraphicsItem, LinkGraphicsItem, ports
│   ├── property_panel.py       # Property editors for nodes, links, ports
│   ├── node_palette.py         # Draggable node type palette
│   ├── stats_panel.py          # Statistics display (Summary/Flows/Console tabs)
│   ├── playback_controls.py    # Packet animation timeline controls
│   ├── socket_app_editor.py    # Custom socket application code editor
│   ├── help_dialog.py          # ns-3 API reference dialog (8 tabs)
│   ├── settings_dialog.py      # Application settings
│   └── project_dialog.py       # New/Open project dialogs
│
├── services/
│   ├── __init__.py
│   ├── project_manager.py      # Save/load projects and topologies
│   ├── ns3_generator.py        # Generate ns-3 Python scripts from topology
│   ├── simulation_runner.py    # Execute ns-3 via WSL subprocess
│   ├── ns3_detector.py         # Auto-detect ns-3 installation in WSL
│   ├── results_parser.py       # Parse FlowMonitor XML results
│   ├── trace_player.py         # Parse and replay packet trace events
│   ├── script_parser.py        # Parse existing ns-3 scripts for import
│   ├── topology_converter.py   # Convert parsed scripts to NetworkModel
│   ├── mininet_export.py       # Export topology to Mininet format
│   └── settings.py             # Application settings management
│
├── resources/
│   └── icons/                  # Node type icons
│
└── tests/
    ├── conftest.py             # Pytest fixtures
    ├── unit/                   # Unit tests for models, services
    ├── integration/            # Integration tests
    └── e2e/                    # End-to-end tests (requires ns-3)
```

---

## Implemented Features

### Node Types

| Type | Icon | Description | ns-3 Mapping |
|------|------|-------------|--------------|
| HOST | 🖥️ | End host/workstation | NodeContainer |
| ROUTER | 📡 | Layer 3 router | Node with multiple interfaces |
| SWITCH | 🔀 | Layer 2 bridge | BridgeHelper |
| ACCESS_POINT | 📶 | WiFi access point | ApWifiMac |
| STATION | 📱 | WiFi client | StaWifiMac |

### Channel/Link Types

| Type | Description | Key Attributes |
|------|-------------|----------------|
| POINT_TO_POINT | Dedicated link between 2 nodes | DataRate, Delay |
| CSMA | Shared Ethernet segment | DataRate, Delay |
| WIFI | 802.11 wireless | Standard (a/b/g/n/ac/ax), SSID |

### Traffic Application Types

| Type | Protocol | Description |
|------|----------|-------------|
| UDP_ECHO | UDP | Request/response echo |
| ON_OFF | UDP/TCP | Constant bitrate with on/off periods |
| BULK_SEND | TCP | Maximum throughput bulk transfer |
| CUSTOM_SOCKET | UDP/TCP | User-defined Python socket application |

### Canvas Features

- Drag-and-drop node placement from palette
- Right-click drag to create links between nodes/ports
- Visual port indicators on nodes (colored circles)
- B-spline curved links with control point editing
- Rubber-band selection
- Zoom (mouse wheel) and pan (middle-click drag)
- Grid snapping
- Route visualization (highlight paths)
- Link activity animation during simulation
- Node "App" badge indicator for custom applications

### Property Panel

- Node properties: name, type, description
- Port-level configuration (L1/L2/L3 settings)
- IP address assignment (manual or auto via switch subnet)
- Link properties: channel type, data rate, delay
- Routing table editor for routers (manual/auto modes)

### Simulation Features

- Auto-detection of ns-3 installation in WSL
- Script generation from visual topology
- Traffic flow configuration dialog
- Real-time console output during simulation
- Progress tracking with simulation time display
- FlowMonitor statistics collection
- Packet animation replay after simulation
- Custom socket application support (Python code editor)

### Project System

- Project-based workflow with structured directories:
  ```
  my_project.ns3proj/
  ├── project.json          # Metadata and run history
  ├── topology.json         # Network topology
  ├── scripts/
  │   ├── gui_simulation.py # Generated ns-3 script
  │   ├── app_base.py       # Base class for custom apps
  │   └── apps/             # Custom node application scripts
  └── results/
      └── run_YYYYMMDD_HHMMSS/
          ├── console.log
          ├── stats.json
          ├── flowmon-results.xml
          └── pcap/
  ```
- Save/load topologies with routing tables and traffic flows
- Simulation results archival with timestamps
- Application script persistence per node

### Import/Export

- Import existing ns-3 Python scripts (parser extracts topology)
- Batch import from ns-3 examples directory
- Export to Mininet Python scripts
- Export generated ns-3 script for manual editing

### Statistics & Analysis

- Summary statistics: packets sent/received/lost, throughput, latency
- Per-flow detailed statistics table
- Console output with real-time simulation logs
- Post-simulation packet animation replay with timeline controls

---

## Key Technical Details

### WSL Integration

The application runs on Windows but executes ns-3 simulations in WSL:

```
Windows (PyQt6 GUI)  ←→  WSL (ns-3 Python bindings)
                          │
                          ├── Script copied to WSL scratch/
                          ├── ns-3 runs via subprocess
                          └── Results parsed from XML/stdout
```

Path conversion handled automatically:
- `C:\path` ↔ `/mnt/c/path`
- `\\wsl$\Ubuntu\home\...` ↔ `/home/...`

### Custom Socket Applications

Users can write custom Python applications that run inside ns-3:

```python
class Host_xxxx(ApplicationBase):
    def setup(self):
        # Called once at start
        pass
    
    def create_payload(self):
        # Return bytes to send
        return b"Hello"
    
    def handle_receive(self, data, from_addr):
        # Process received data
        pass
```

The `ApplicationBase` class provides:
- Socket management (UDP/TCP)
- Timing control (start_time, stop_time, interval)
- ns-3 Simulator integration
- Logging utilities

### B-Spline Link Curves

Links use cubic B-splines for smooth curves:
- Short links (<50px): straight line
- Medium links (50-150px): 1 control point
- Long links (>150px): 2 control points
- Control points can be adjusted interactively

### Routing

Two modes supported:
1. **AUTO**: Uses `Ipv4GlobalRoutingHelper.PopulateRoutingTables()` (Dijkstra)
2. **MANUAL**: User-configured static routes via routing table dialog

Route visualization shows paths on canvas with highlighted links.

---

## Dependencies

```
PyQt6>=6.4.0
pyqtgraph>=0.13.0
sip>=6.7.0
pytest>=7.0.0
pytest-qt>=4.2.0
pytest-cov>=4.0.0
```

### ns-3 Requirements (WSL)

- ns-3.45+ with Python bindings enabled
- Built with: `./ns3 configure --enable-python-bindings && ./ns3 build`
- cppyy-based bindings (not pybindgen)

---

## Known Limitations / Not Yet Implemented

### From Original Architecture (Deferred)

1. **Distributed Simulation** - MPI-based distributed ns-3
2. **3D Visualization** - OpenGL-based 3D topology view
3. **Machine Learning Integration** - ns3-gym interface
4. **Cloud Execution** - Remote server simulation
5. **Collaboration** - Multi-user editing

### Partially Implemented

1. **Undo/Redo** - Model exists but not fully wired to UI
2. **PCAP Viewer** - Files generated but no built-in viewer
3. **Timeline Widget** - Playback controls exist, full timeline planned
4. **Mini-map** - Not implemented
5. **Plugin System** - Architecture defined, not exposed

### Network Features Not Yet Supported

1. **LTE/5G** - LteHelper, NrHelper
2. **Error Models** - RateErrorModel, BurstErrorModel
3. **QoS/Traffic Control** - Queue disciplines (RED, CoDel)
4. **Mobility Models** - Random walk, waypoints (only static positions)
5. **IPv6** - Ipv6AddressHelper
6. **Dynamic Routing Protocols** - OSPF, RIP, OLSR, AODV
7. **V4PingHelper** - ICMP ping application
8. **Energy Models** - Battery/power consumption

---

## Usage Tips for Future Development

### Adding a New Node Type

1. Add enum value to `NodeType` in `models/network.py`
2. Add icon to `resources/icons/`
3. Update `NodePalette` in `views/node_palette.py`
4. Update `NodeGraphicsItem` icon mapping in `views/topology_canvas.py`
5. Add property widget if needed in `views/property_panel.py`
6. Update `NS3ScriptGenerator` to handle new type

### Adding a New Application Type

1. Add enum value to `AppType` in `models/simulation.py`
2. Update flow editor dialog in `views/main_window.py`
3. Add generation code in `services/ns3_generator.py` `_generate_applications()`

### Adding a New Channel Type

1. Add enum value to `ChannelType` in `models/network.py`
2. Update link type combo in `views/property_panel.py`
3. Add helper setup in `services/ns3_generator.py` `_generate_channels()`

---

## Testing

Run tests with:
```bash
python run_tests.py           # All tests except slow
python run_tests.py --all     # All tests including e2e
python run_tests.py --unit    # Unit tests only
python run_tests.py --cov     # With coverage report
```

Test categories:
- `unit/` - Model and service logic (no Qt)
- `integration/` - Component interactions
- `e2e/` - Full simulation execution (requires ns-3)

---

## File Formats

### topology.json

```json
{
  "version": "1.0",
  "nodes": {
    "host_xxxx": {
      "id": "host_xxxx",
      "node_type": "HOST",
      "name": "Host 1",
      "position": [100, 200],
      "ports": [...],
      "routing_table": [...],
      "has_app_script": true,
      "app_script_path": "scripts/apps/host_xxxx.py"
    }
  },
  "links": {...},
  "simulation": {
    "flows": [...]
  }
}
```

### project.json

```json
{
  "name": "My Simulation",
  "created": "2025-12-18T...",
  "modified": "2025-12-18T...",
  "ns3_path": "/home/user/ns-allinone-3.45/ns-3.45",
  "runs": [
    {
      "timestamp": "...",
      "success": true,
      "result_dir": "results/run_..."
    }
  ]
}
```

---

## Contact / Development Notes

- Primary development platform: Windows 11 + WSL2 (Ubuntu)
- Python version: 3.11+
- PyQt version: 6.4+
- ns-3 version: 3.45+

This document should be included when starting new development conversations to provide full context of the v1.0 implementation.
