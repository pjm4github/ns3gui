# ns-3 Network Simulator GUI

A visual interface for designing and simulating network topologies using the ns-3 discrete-event network simulator.

## Features

### Topology Editor
- **Visual node placement** - Host, Router, Switch with port-level configuration
- **Port connection points** - Visual indicators on each node showing available ports
- **Right-click and drag** between nodes/ports to create links
- **Selection** - click to select nodes, links, or individual ports
- **Zoom/Pan** - mouse wheel to zoom, middle-click to pan

### Property Panel
- View and edit node properties (name, type, description)
- Port-level configuration with L1/L2/L3 settings
- Switch subnet configuration for automatic IP assignment
- Link properties (channel type, data rate, delay)

### ns-3 Integration (Phase 2)
- **Auto-detection** of ns-3 installation
- **Script generation** - generates ns-3 Python scripts from topology
- **Traffic flows** - configure UDP Echo traffic between nodes
- **Simulation execution** - runs ns-3 as subprocess
- **Results parsing** - FlowMonitor XML results displayed in Statistics panel

### Statistics Panel
- Summary statistics (packets, throughput, latency)
- Per-flow detailed statistics table
- Console output with simulation logs

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

### ns-3 Setup (for simulation)

1. Install ns-3 following the [official guide](https://www.nsnam.org/wiki/Installation)
2. Build with Python bindings enabled:
   ```bash
   ./ns3 configure --enable-python-bindings
   ./ns3 build
   ```
3. The GUI will auto-detect ns-3 or you can configure the path manually

## Running

```bash
python main.py
```

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

### Running a Simulation

1. **Configure ns-3 Path**: The GUI auto-detects ns-3, or configure via Simulation menu
2. **Click Run**: Opens simulation configuration dialog
3. **Add Traffic Flows**: Define source/destination nodes and traffic parameters
4. **Configure Options**: Set duration, enable FlowMonitor, etc.
5. **Start Simulation**: ns-3 script is generated and executed
6. **View Results**: Statistics appear in the Stats panel after completion

## Project Structure

```
ns3_gui_mvp/
├── main.py                 # Application entry point
├── requirements.txt        # Python dependencies
├── models/
│   ├── network.py          # NetworkModel, NodeModel, LinkModel, PortConfig
│   └── simulation.py       # SimulationConfig, TrafficFlow, FlowStats
├── views/
│   ├── main_window.py      # Main window with dialogs
│   ├── topology_canvas.py  # Graphics view with port indicators
│   ├── property_panel.py   # Property editor with port editors
│   ├── node_palette.py     # Node type selection
│   └── stats_panel.py      # Statistics with tabs (Summary/Flows/Console)
└── services/
    ├── project_manager.py  # Save/load topology files
    ├── ns3_generator.py    # Generate ns-3 Python scripts
    ├── simulation_runner.py # Execute ns-3 simulation
    └── results_parser.py   # Parse FlowMonitor XML results
```

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| Delete/Backspace | Delete selected items |
| Ctrl+A | Select all |
| Ctrl+0 | Fit view to contents |
| Ctrl+R | Reset view |
| Ctrl+N | New topology |
| Ctrl+S | Save |
| Ctrl+O | Open |
| Escape | Clear selection / Cancel link drawing |

## Traffic Types

Currently supported:
- **UDP Echo** - Simple request/response packets

Coming soon (stubbed in generated code):
- **OnOff** - Constant bitrate with on/off periods  
- **BulkSend** - TCP bulk transfer
- **Ping** - ICMP ping

## File Formats

### Topology Files (.ns3topo)
JSON format containing:
- Nodes with port configurations
- Links with endpoint port bindings
- Metadata (version, creation date)

### Generated Scripts
Python scripts compatible with ns-3's Python bindings, placed in `scratch/gui_simulation.py`

### Output Files
- `flowmon-results.xml` - FlowMonitor statistics
- `trace.tr` - ASCII trace (if enabled)
- `*.pcap` - Packet captures (if enabled)

## License

BSD 2-Clause License

Copyright (c) 2025, Patrick Moran

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

1. Redistributions of source code must retain the above copyright notice, this
   list of conditions and the following disclaimer.

2. Redistributions in binary form must reproduce the above copyright notice,
   this list of conditions and the following disclaimer in the documentation
   and/or other materials provided with the distribution.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
