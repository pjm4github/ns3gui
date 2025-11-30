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
- **Routing table configuration** - manual static routes for hosts and routers

### ns-3 Integration
- **Auto-detection** of ns-3 installation
- **Script generation** - generates ns-3 Python scripts from topology
- **Traffic flows** - configure UDP Echo traffic between nodes
- **Simulation execution** - runs ns-3 as subprocess
- **Results parsing** - FlowMonitor XML results displayed in Statistics panel

### Statistics Panel
- Summary statistics (packets, throughput, latency)
- Per-flow detailed statistics table
- Routing table display
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

### Configuring Routing Tables

Hosts and routers can have manually configured routing tables:

1. **Select a node** (host or router)
2. **Click "Edit Routing Table..."** in the Property Panel
3. **Choose routing mode**:
   - **Auto**: ns-3's GlobalRoutingHelper computes routes automatically
   - **Manual**: Configure static routes yourself
4. **For Manual mode**:
   - Click **"Auto-Fill Routes"** to generate suggested routes from topology
   - **Add Route**: Manually add a route with destination, gateway, interface
   - **Edit/Delete**: Modify existing routes
   - For hosts, use the **Default Gateway** shortcut field

### Visualizing Routes

The GUI can highlight routing paths on the canvas:

1. **View Menu → Routes → Show All Routes** (Ctrl+Shift+R): Highlights all manually configured routes
2. **View Menu → Routes → Show Routes From Selected Node**: Shows routes originating from selected node
3. **View Menu → Routes → Show Routes To Selected Node**: Shows paths that can reach the selected node
4. **View Menu → Routes → Clear Route Highlights** (Escape): Clears highlighting

Route visualization colors:
- **Green**: Regular route paths
- **Blue**: Default routes (0.0.0.0/0)

### Running a Simulation

1. **Configure ns-3 Path**: The GUI auto-detects ns-3, or configure via Simulation menu
2. **Click Run**: Opens simulation configuration dialog
3. **Add Traffic Flows**: Define source/destination nodes and traffic parameters
4. **Configure Options**: Set duration, enable FlowMonitor, etc.
5. **Start Simulation**: ns-3 script is generated and executed
6. **View Results**: Statistics appear in the Stats panel after completion

### Managing Traffic Flows

Traffic flows define the network traffic to simulate between nodes.

#### Creating Flows
1. Open **Simulation → Run Simulation** (F5)
2. Click **"Add Flow"** in the Traffic Flows section
3. Configure:
   - **Source/Target**: Select endpoints from dropdown
   - **Protocol**: UDP or TCP
   - **Application**: Echo, OnOff, BulkSend, or Ping
   - **Timing**: Start time, stop time
   - **Traffic parameters**: Packet size, data rate, echo interval

#### Saving Flows with Topology
Flows can be saved with the topology file so they persist across sessions:

1. Configure your traffic flows in the Simulation dialog
2. Click **"Save Flows"** to store them with the topology
3. **Save the project** (Ctrl+S) to persist to disk

#### Loading Saved Flows
- **Automatic**: When opening the Simulation dialog, saved flows are automatically loaded if no flows are currently configured
- **Manual**: Click **"Load Saved"** to restore flows from the topology file
  - Choose to **replace** current flows or **add** to them

## Project Structure

```
ns3_gui_mvp/
├── main.py                 # Application entry point
├── requirements.txt        # Python dependencies
├── models/
│   ├── network.py          # NetworkModel, NodeModel, LinkModel, PortConfig, RouteEntry
│   └── simulation.py       # SimulationConfig, TrafficFlow, FlowStats
├── views/
│   ├── main_window.py      # Main window with dialogs
│   ├── topology_canvas.py  # Graphics view with port indicators and route visualization
│   ├── property_panel.py   # Property editor with port editors
│   ├── routing_dialog.py   # Routing table configuration dialog
│   ├── node_palette.py     # Node type selection
│   └── stats_panel.py      # Statistics with tabs (Summary/Flows/Routing/Console)
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
| Ctrl+Shift+R | Toggle route visualization |
| Ctrl+N | New topology |
| Ctrl+S | Save |
| Ctrl+O | Open |
| F5 | Run simulation |
| Escape | Clear selection / Cancel link drawing / Clear route highlights |

## Traffic Types

Currently supported:
- **UDP Echo** - Simple request/response packets

Coming soon (stubbed in generated code):
- **OnOff** - Constant bitrate with on/off periods  
- **BulkSend** - TCP bulk transfer
- **Ping** - ICMP ping

## File Formats

### Topology Files (.json)

JSON format containing nodes, links, routing configuration, and saved traffic flows.

#### Structure Overview
```json
{
  "schema": {
    "version": "1.0",
    "format": "ns3-gui-topology"
  },
  "metadata": {
    "created": "2025-01-15T10:30:00",
    "generator": "ns3-gui-mvp"
  },
  "simulation": {
    "duration": 10.0,
    "units": "seconds",
    "flows": [...]
  },
  "topology": {
    "nodes": [...],
    "links": [...]
  }
}
```

#### Traffic Flow Structure
Flows are stored in `simulation.flows`:
```json
{
  "flows": [
    {
      "id": "abc12345",
      "name": "flow_abc1",
      "source_node_id": "host1_id",
      "target_node_id": "host2_id",
      "protocol": "udp",
      "application": "echo",
      "start_time": 1.0,
      "stop_time": 9.0,
      "data_rate": "1Mbps",
      "packet_size": 1024,
      "echo_packets": 10,
      "echo_interval": 1.0
    }
  ]
}
```

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Unique flow identifier |
| `name` | string | Display name for the flow |
| `source_node_id` | string | ID of the source node |
| `target_node_id` | string | ID of the target node |
| `protocol` | string | `"udp"` or `"tcp"` |
| `application` | string | `"echo"`, `"onoff"`, `"bulk"`, or `"ping"` |
| `start_time` | float | Simulation time to start (seconds) |
| `stop_time` | float | Simulation time to stop (seconds) |
| `data_rate` | string | Data rate (e.g., `"1Mbps"`, `"500Kbps"`) |
| `packet_size` | int | Packet size in bytes |
| `echo_packets` | int | Number of echo packets to send |
| `echo_interval` | float | Interval between echo packets (seconds) |

#### Routing Configuration Structure
Per-node routing is stored in each node's `routing` field:
```json
{
  "nodes": [
    {
      "id": "host1_id",
      "type": "host",
      "name": "host_1",
      "routing": {
        "mode": "manual",
        "default_gateway": "10.1.1.2",
        "routes": [
          {
            "id": "route123",
            "destination": "10.1.2.0",
            "prefix_length": 24,
            "gateway": "10.1.1.2",
            "interface": 0,
            "metric": 1,
            "route_type": "static",
            "enabled": true
          }
        ]
      }
    }
  ]
}
```

| Field | Type | Description |
|-------|------|-------------|
| `mode` | string | `"auto"` (GlobalRoutingHelper) or `"manual"` (static routes) |
| `default_gateway` | string | Default gateway IP (shortcut for hosts) |
| `routes[].destination` | string | Network address (e.g., `"10.1.2.0"`) |
| `routes[].prefix_length` | int | CIDR prefix (e.g., `24` for /24) |
| `routes[].gateway` | string | Next hop IP (`"0.0.0.0"` for direct/connected) |
| `routes[].interface` | int | Interface index (0-based) |
| `routes[].metric` | int | Route metric/priority |
| `routes[].route_type` | string | `"static"`, `"connected"`, or `"default"` |
| `routes[].enabled` | bool | Whether route is active |

### Generated Scripts
Python scripts compatible with ns-3's Python bindings, placed in `scratch/gui_simulation.py`

### Output Files
- `flowmon-results.xml` - FlowMonitor statistics
- `trace.tr` - ASCII trace (if enabled)
- `*.pcap` - Packet captures (if enabled)

## License

MIT
