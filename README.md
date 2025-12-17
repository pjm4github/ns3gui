# ns-3 Network Simulator GUI

A visual interface for designing and simulating network topologies using the ns-3 discrete-event network simulator.

## Features

### Project-Based Workflow
- **Project management** - Organize simulations into self-contained projects
- **Automatic saving** - Topology, flows, scripts, and results saved to project directory
- **Run history** - Each simulation run is timestamped and preserved with its configuration
- **Workspace configuration** - Customizable workspace location for all projects

### Topology Editor
- **Visual node placement** - Host, Router, Switch with port-level configuration
- **Port connection points** - Visual indicators on each node showing available ports
- **Right-click and drag** between nodes/ports to create links
- **Radial Bezier curves** - Elegant curved connections between nodes
- **Selection** - Click to select nodes, links, or individual ports
- **Zoom/Pan** - Mouse wheel to zoom, middle-click to pan
- **Double-click nodes** - Open the Socket Application Editor

### Property Panel
- View and edit node properties (name, type, description)
- Port-level configuration with L1/L2/L3 settings
- Switch subnet configuration for automatic IP assignment
- Link properties (channel type, data rate, delay)
- **Routing table configuration** - Manual static routes for hosts and routers

### Custom Socket Applications
- **Visual code editor** - Double-click any node to open the application editor
- **Python-based** - Extend `ApplicationBase` class for custom traffic patterns
- **Syntax highlighting** - Full Python editor with error checking
- **"Py" indicator** - Nodes with custom applications show a visual badge
- **Project persistence** - Application scripts saved to project's scripts directory

### ns-3 Integration
- **Auto-detection** of ns-3 installation (Linux native or WSL on Windows)
- **Script generation** - Generates ns-3 Python scripts from topology
- **Traffic flows** - Configure UDP/TCP traffic between nodes
- **Simulation execution** - Runs ns-3 as subprocess with real-time output
- **Results parsing** - FlowMonitor XML results displayed in Statistics panel
- **Packet animation** - Visual playback of packet flow through the network

### Statistics Panel
- Summary statistics (packets, throughput, latency)
- Per-flow detailed statistics table
- Routing table display
- Console output with simulation logs

## Project Directory Structure

When you create a project, it organizes all simulation artifacts in a structured directory:

```
workspace/
└── projects/
    └── my_network/                    # Project folder (project name)
        ├── project.json               # Project metadata and settings
        ├── topology.json              # Network topology definition
        ├── flows.json                 # Current traffic flow definitions
        ├── scripts/                   # Generated simulation files
        │   ├── gui_simulation.py      # Main simulation script
        │   ├── app_base.py            # Application base class
        │   └── *.py                   # Host application scripts (e.g., host_1.py)
        └── results/                   # Simulation results
            └── run_YYYYMMDD_HHMMSS/   # Timestamped run folder
                ├── run_info.json      # Run metadata
                ├── flows.json         # Flows used for this specific run
                ├── console.log        # WSL/ns-3 console output
                ├── trace.xml          # ns-3 trace file
                ├── stats.json         # Parsed statistics
                └── pcap/              # PCAP files (if enabled)
```

### File Descriptions

| File | Description |
|------|-------------|
| `project.json` | Project metadata: name, description, creation date, run history |
| `topology.json` | Network topology with nodes, links, ports, routing, and app script references |
| `flows.json` | Traffic flow definitions (source, target, protocol, timing, etc.) |
| `scripts/*.py` | Generated and custom Python scripts for ns-3 simulation |
| `results/run_*/` | Timestamped folders containing each simulation run's outputs |

## Installation & Setup

For detailed installation instructions, including ns-3 setup and platform-specific guidance, see **[SETUP.md](SETUP.md)**.

### Quick Start

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt

# Run the application
python main.py
```

## Usage

### Creating a Project

1. **File → Project → New Project...** (Ctrl+Shift+N)
2. Enter project name and optional description
3. Project directory is created in the workspace

### Opening a Project

1. **File → Project → Open Project...** (Ctrl+Shift+O)
2. Select from the list of existing projects
3. Topology, flows, and application scripts are automatically loaded

### Creating a Topology

1. **Add Nodes**: Click a node type in the left palette to add it
2. **Position Nodes**: Drag nodes to arrange your topology
3. **Create Links**: Right-click on a node/port and drag to another to connect
4. **Save**: Press Ctrl+S to save to the current project

### Port Selection

- Nodes display small circles representing ports
- **Left-click** a port to select it (highlighted in Property Panel)
- **Right-click** a port to start link creation from that specific port
- Port colors: Gray=available, Green=connected, Red=disabled, Orange=selected

### Creating Custom Applications

1. **Double-click** any node to open the Socket Application Editor
2. Write your Python code extending `ApplicationBase`
3. Click **Save** or **Save & Close** to save
4. The node will show a "Py" badge indicating it has a custom application
5. Application is automatically saved to the project's `scripts/` directory

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

1. **Configure ns-3 Path**: Edit → Settings → ns-3 tab (auto-detected if available)
2. **Click Run** (F5): Opens simulation configuration dialog
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

### Configuring Settings

Access all application settings via **Edit → Settings...** (Ctrl+,):

| Tab | Settings |
|-----|----------|
| **General** | Theme, auto-save, default values |
| **ns-3** | ns-3 installation path, WSL distribution |
| **Workspace** | Workspace root directory for all projects |

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| Ctrl+Shift+N | New project |
| Ctrl+Shift+O | Open project |
| Ctrl+N | New topology |
| Ctrl+S | Save |
| Ctrl+O | Open file |
| Ctrl+, | Settings |
| F5 | Run simulation |
| Delete/Backspace | Delete selected items |
| Ctrl+A | Select all |
| Ctrl+0 | Fit view to contents |
| Ctrl+R | Reset view |
| Ctrl+Shift+R | Toggle route visualization |
| Escape | Clear selection / Cancel link drawing / Clear route highlights |

## Source Code Structure

```
ns3_gui_mvp/
├── main.py                 # Application entry point
├── requirements.txt        # Python dependencies
├── SETUP.md                # Detailed setup instructions
├── LICENSE                 # License file
├── templates/
│   └── app_base.py         # ApplicationBase class template
├── models/
│   ├── network.py          # NetworkModel, NodeModel, LinkModel, PortConfig, RouteEntry
│   ├── simulation.py       # SimulationConfig, TrafficFlow, FlowStats
│   └── project.py          # Project, ProjectManager, ProjectMetadata
├── views/
│   ├── main_window.py      # Main window with menus and dialogs
│   ├── topology_canvas.py  # Graphics view with port indicators and route visualization
│   ├── property_panel.py   # Property editor with port editors
│   ├── routing_dialog.py   # Routing table configuration dialog
│   ├── project_dialog.py   # Project management dialogs
│   ├── settings_dialog.py  # Application settings dialog
│   ├── socket_app_editor.py # Custom application code editor
│   ├── node_palette.py     # Node type selection
│   └── stats_panel.py      # Statistics with tabs (Summary/Flows/Routing/Console)
└── services/
    ├── project_manager.py  # Save/load topology files
    ├── settings_manager.py # Application settings persistence
    ├── ns3_generator.py    # Generate ns-3 Python scripts
    ├── simulation_runner.py # Execute ns-3 simulation
    ├── trace_player.py     # Packet animation playback
    └── results_parser.py   # Parse FlowMonitor XML results
```

## Traffic Types

Currently supported:
- **UDP Echo** - Simple request/response packets
- **Custom Socket Application** - User-defined Python applications using ApplicationBase

Coming soon (stubbed in generated code):
- **OnOff** - Constant bitrate with on/off periods  
- **BulkSend** - TCP bulk transfer
- **Ping** - ICMP ping

## Custom Socket Applications (ApplicationBase)

The GUI supports custom Python-based traffic generators through the `ApplicationBase` class architecture. This allows you to create sophisticated traffic patterns, custom protocols, and data-driven simulations.

### Quick Example

```python
from app_base import ApplicationBase

class MyCustomApp(ApplicationBase):
    """Custom traffic generator."""
    
    def on_setup(self):
        """Called once during setup."""
        self.message_id = 0
    
    def create_payload(self) -> bytes:
        """Generate each packet's content."""
        self.message_id += 1
        msg = f"Message {self.message_id} at {self.get_current_time():.3f}s"
        return msg.encode('utf-8')
    
    def on_packet_sent(self, seq: int, payload: bytes):
        """Called after sending."""
        self.log(f"Sent #{seq}: {payload.decode()}")
    
    def on_start(self):
        """Called when application starts."""
        self.log("Application started!")
    
    def on_stop(self):
        """Called when application stops."""
        stats = self.get_stats()
        self.log(f"Finished: {stats['packets_sent']} packets sent")
```

### Using Custom Applications in Simulation

1. **Double-click** a node to open the Socket Application Editor
2. Write your custom class extending `ApplicationBase`
3. **Save** the application
4. In **Simulation → Run Simulation**, add a Traffic Flow
5. Select source and target nodes
6. Check **"Use Socket Application Node"**
7. Select your APPLICATION node from the dropdown
8. Run the simulation

## File Formats

### Topology Files (topology.json)

JSON format containing nodes, links, routing configuration, app script references, and saved traffic flows.

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
    "nodes": [
      {
        "id": "abc123",
        "name": "Host 1",
        "type": "host",
        "app_script_file": "scripts/host_1.py",
        "routing": {
          "mode": "manual",
          "default_gateway": "10.1.1.2",
          "routes": [...]
        },
        ...
      }
    ],
    "links": [...]
  }
}
```

### Output Files
- `flowmon-results.xml` - FlowMonitor statistics
- `trace.xml` - XML trace file
- `*.pcap` - Packet captures (if enabled)

## License

This project is licensed under the terms specified in the [LICENSE](LICENSE) file.
