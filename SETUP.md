# NS-3 GUI Setup Guide

This guide covers setting up the NS-3 GUI with ns-3 running on WSL2 (Windows Subsystem for Linux).

## Prerequisites

- Windows 10/11 with WSL2 enabled
- Ubuntu installed in WSL2
- Python 3.10+ on Windows
- PyQt6

## Windows Setup

### 1. Install Python Dependencies

```powershell
# Create virtual environment (optional but recommended)
python -m venv venv
.\venv\Scripts\activate

# Install requirements
pip install -r requirements.txt
```

### 2. Verify WSL2 is Working

```powershell
# Check WSL status (note: two dashes)
wsl --status

# List installed distributions
wsl --list --verbose
```

### 3. Set Ubuntu as Default WSL Distribution

If you have multiple WSL distributions (e.g., Docker), set Ubuntu as default:

```powershell
wsl --set-default Ubuntu

# Verify - Ubuntu should have an asterisk (*)
wsl --list --verbose
```

Expected output:
```
  NAME                   STATE           VERSION
* Ubuntu                 Running         2
  docker-desktop         Stopped         2
```

## WSL/Ubuntu Setup

### 1. Install Basic Dependencies

```bash
# Open Ubuntu terminal
wsl

# Update package list
sudo apt update

# Install Python and pip
sudo apt install -y python3 python3-pip python3-dev

# Make 'python' command point to python3
sudo apt install -y python-is-python3

# Verify
python --version
pip --version
```

### 2. Install ns-3 Build Dependencies

```bash
sudo apt install -y \
    g++ \
    cmake \
    ninja-build \
    git \
    libboost-all-dev \
    libgsl-dev
```

### 3. Download and Extract ns-3

```bash
cd ~

# Download ns-3.45 (or your preferred version)
wget https://www.nsnam.org/releases/ns-allinone-3.45.tar.bz2

# Extract
tar xjf ns-allinone-3.45.tar.bz2

cd ns-allinone-3.45/ns-3.45
```

### 4. Install Python Bindings Dependency (cppyy)

**This is critical for Python bindings to work!**

```bash
pip install cppyy --break-system-packages
```

### 5. Set Environment Variable for Bindings

Add to your `~/.bashrc`:

```bash
echo 'export NS3_BINDINGS_INSTALL_DIR="$HOME/.local/lib/python3.12/site-packages"' >> ~/.bashrc
source ~/.bashrc
```

### 6. Remove Incompatible Contrib Modules (Optional but Recommended)

Some contrib modules may cause issues with Python bindings:

```bash
cd ~/ns-allinone-3.45/ns-3.45/contrib

# Remove problematic modules
rm -rf netsimulyzer

cd ..
```

### 7. Configure ns-3 with Python Bindings

```bash
cd ~/ns-allinone-3.45/ns-3.45

./ns3 configure --enable-python-bindings --enable-examples
```

**Verify the output shows:**
```
Python Bindings               : ON
PyViz visualizer              : ON
```

If Python Bindings shows OFF, check that cppyy is installed correctly.

### 8. Build ns-3

```bash
./ns3 build
```

**Note:** This takes 15-30+ minutes as it compiles ns-3 and generates Python bindings.

### 9. Verify Python Bindings Work

```bash
# Test a Python example
./ns3 run src/core/examples/sample-simulator.py
```

Expected output (ignore the warnings):
```
[runStaticInitializersOnce]: Failed to materialize symbols...  # These warnings are OK
ExampleFunction received event at 10s
RandomFunction received event at 18.165320442 s
Member method received event at 20s started at 10s
```

If you see the "received event" messages, Python bindings are working!

## Running the GUI

### 1. Start the Application

```powershell
cd ns3_gui_mvp
python main.py
```

### 2. Configure ns-3 Path (First Time Only)

1. Go to **Edit → Settings** (or press Ctrl+,)
2. In the **ns-3** tab, enter your ns-3 path: `/home/YOUR_USERNAME/ns-allinone-3.45/ns-3.45`
3. You should see: `✓ Valid (version: 3.45, mode: WSL)`
4. Click **OK** - the path is saved for future sessions

Or when you click **Run**:
1. The "Configure ns-3 Path" dialog appears
2. Enter: `/home/YOUR_USERNAME/ns-allinone-3.45/ns-3.45`
3. Click **OK**

### 3. Create a Simulation

1. Add nodes from the left palette (drag Host nodes onto canvas)
2. Connect nodes by clicking a port on one node and dragging to a port on another
3. Click **Run** (or press F5) to configure simulation parameters
4. Add traffic flows (e.g., UDP Echo between two hosts)
5. Click **OK** to start the simulation

### 4. View Results

After simulation completes:
- **Summary tab**: Packet counts, throughput, latency
- **Flows tab**: Per-flow statistics  
- **Console tab**: Raw ns-3 output

## Troubleshooting

### "wsl: Unknown key 'automount.crossDistro'" Warning

This is a harmless warning. To fix:

```powershell
wsl -e nano /etc/wsl.conf
```

Delete or comment out the line with `crossDistro`, save (Ctrl+O, Enter, Ctrl+X), then:

```powershell
wsl --shutdown
```

### "No such file or directory" with ~ Path

The `~` shortcut doesn't expand properly when called from PowerShell. Use the full path:

```powershell
# Instead of: wsl -e ls ~/ns-allinone-3.45/ns-3.45/ns3
# Use:        wsl -e ls /home/YOUR_USERNAME/ns-allinone-3.45/ns-3.45/ns3
```

### "ModuleNotFoundError: No module named 'ns'"

Python bindings aren't installed. Check:

1. Is cppyy installed?
   ```bash
   pip show cppyy
   ```

2. Did configure show `Python Bindings: ON`?
   ```bash
   ./ns3 configure --enable-python-bindings --enable-examples
   ```

3. Did you rebuild after configuring?
   ```bash
   ./ns3 build
   ```

### "Command 'pip' not found"

Install pip:
```bash
sudo apt install python3-pip
```

### "Command 'python' not found"

Create symlink:
```bash
sudo apt install python-is-python3
```

### "Bindings: python bindings disabled due to missing dependencies: cppyy"

Install cppyy:
```bash
pip install cppyy --break-system-packages
```

Then reconfigure and rebuild:
```bash
./ns3 configure --enable-python-bindings --enable-examples
./ns3 build
```

### "Failed to load header file ns3/netsimulyzer-module.h"

Remove the incompatible contrib module:
```bash
rm -rf ~/ns-allinone-3.45/ns-3.45/contrib/netsimulyzer
./ns3 clean
./ns3 configure --enable-python-bindings --enable-examples
./ns3 build
```

### ns-3 Not Found in GUI

1. Verify Ubuntu is your default WSL distribution:
   ```powershell
   wsl --set-default Ubuntu
   ```

2. Use the full Linux path (not Windows path):
   - ✅ `/home/pmoran/ns-allinone-3.45/ns-3.45`
   - ❌ `C:\Users\...`
   - ❌ `\\wsl$\Ubuntu\home\...`

### Simulation Fails to Start

Test that ns-3 can run from PowerShell:

```powershell
wsl -e bash -c "cd /home/YOUR_USERNAME/ns-allinone-3.45/ns-3.45 && ./ns3 run first"
```

If this fails, there's an issue with your ns-3 installation inside WSL.

### "runStaticInitializersOnce: Failed to materialize symbols" Warnings

These warnings are **normal** with cppyy bindings and can be ignored. The simulation still runs correctly.

### "Could not connect packet trace callbacks" Warning

This is a limitation of the cppyy bindings - they don't support template callbacks. The simulation runs fine, but packet animations won't work.

## Settings File Location

The GUI saves settings (including ns-3 path) to a JSON file:

| Platform | Path |
|----------|------|
| **Windows** | `%APPDATA%\NS3GUI\settings.json` |
| **Linux** | `~/.config/NS3GUI/settings.json` |
| **macOS** | `~/Library/Application Support/NS3GUI/settings.json` |

To reset settings, delete this file.

## Workspace Configuration

The GUI uses a workspace directory structure to organize topology files, generated scripts, and simulation results.

### Default Workspace Location

| Platform | Default Path |
|----------|-------------|
| **Windows** | `Documents\NS3GUI\` |
| **Linux** | `~/ns3gui/` |
| **macOS** | `~/Documents/NS3GUI/` |

### Workspace Structure

```
NS3GUI/                     # Workspace root
├── topologies/             # Saved topology files (.json)
├── scripts/                # Generated ns-3 Python scripts
├── results/                # Simulation output files
└── templates/              # Topology templates
```

### Configuring the Workspace

1. Go to **Edit → Settings** (or press Ctrl+,)
2. Select the **Workspace** tab
3. Choose a workspace profile:
   - **default**: Normal user workspace
   - **test**: For automated testing
   - **custom**: User-defined workspace
4. Optionally set a custom root path
5. Click **Create Directories** to ensure folders exist
6. Click **OK** to save

### Workspace Profiles

Workspace profiles allow different configurations for different use cases:

| Profile | Use Case |
|---------|----------|
| **default** | Normal day-to-day usage |
| **test** | Automated testing with isolated test data |
| **custom** | User-defined workspace for specific projects |

Each profile can have its own root directory. If no custom path is set, the default platform-specific location is used.

### Test Configuration

For automated testing, configure the test workspace:

1. Set active profile to "test"
2. Set a path like `C:\NS3GUI_Tests` or `/tmp/ns3gui_tests`
3. Tests will read/write files from this isolated location

### Programmatic Access

For scripts and automation:

```python
from services.settings_manager import get_settings

# Get settings manager
settings = get_settings()

# Get workspace directories
topo_dir = settings.get_topologies_dir()
scripts_dir = settings.get_scripts_dir()
results_dir = settings.get_results_dir()

# Switch profiles
settings.set_workspace_profile("test")

# Set custom workspace path
settings.set_workspace_path("test", "/tmp/ns3gui_tests")
```

## File Locations

| Item | Location |
|------|----------|
| GUI Application | Windows: `C:\...\ns3_gui_mvp\` |
| ns-3 Installation | WSL: `/home/USER/ns-allinone-3.45/ns-3.45/` |
| Simulation Scripts | WSL: `~/ns-allinone-3.45/ns-3.45/scratch/` |
| Simulation Output | Windows: `%TEMP%\ns3_gui_*\` |
| Settings File | Windows: `%APPDATA%\NS3GUI\settings.json` |

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                      Windows                                │
│  ┌───────────────────────────────────────────────────────┐  │
│  │                  PyQt6 GUI                            │  │
│  │  • Topology editor                                    │  │
│  │  • Generate ns-3 Python script                        │  │
│  │  • Display results                                    │  │
│  └───────────────────────────────────────────────────────┘  │
│                            │                                │
│                    wsl -e bash -c "..."                     │
│                            ▼                                │
│  ┌───────────────────────────────────────────────────────┐  │
│  │                  WSL2 (Ubuntu)                        │  │
│  │  • ns-3 simulator with Python bindings (cppyy)        │  │
│  │  • Execute: ./ns3 run scratch/gui_simulation.py       │  │
│  │  • Output via stdout back to GUI                      │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

## Quick Reference Commands

### PowerShell (Windows)

```powershell
# Check WSL status
wsl --status

# Set Ubuntu as default
wsl --set-default Ubuntu

# Test ns-3
wsl -e bash -c "cd ~/ns-allinone-3.45/ns-3.45 && ./ns3 run first"

# Open Ubuntu terminal
wsl
```

### Bash (WSL/Ubuntu)

```bash
# Find ns-3 path
find ~ -name "ns3" -type f 2>/dev/null

# Configure ns-3
./ns3 configure --enable-python-bindings --enable-examples

# Build ns-3
./ns3 build

# Test Python bindings
./ns3 run src/core/examples/sample-simulator.py

# Clean and rebuild
./ns3 clean
./ns3 configure --enable-python-bindings --enable-examples
./ns3 build
```
