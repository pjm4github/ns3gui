# ns-3 GUI v1.0 - Quick Reference

## What It Is
PyQt6 GUI for ns-3 network simulator. Runs on Windows, executes ns-3 in WSL.

## Core Files to Know

| Purpose | Files |
|---------|-------|
| **Models** | `models/network.py` (NetworkModel, NodeModel, LinkModel, PortConfig, RouteEntry) |
| | `models/simulation.py` (TrafficFlow, FlowStats, SimulationConfig) |
| **Main UI** | `views/main_window.py` (menus, toolbars, dialogs) |
| **Canvas** | `views/topology_canvas.py` (NodeGraphicsItem, LinkGraphicsItem, ports) |
| **Properties** | `views/property_panel.py` (node/link/port editors) |
| **Script Gen** | `services/ns3_generator.py` (topology → ns-3 Python script) |
| **Simulation** | `services/simulation_runner.py` (WSL subprocess execution) |
| **Project** | `services/project_manager.py` (save/load .ns3proj) |
| **Custom Apps** | `views/socket_app_editor.py` + generated `app_base.py` |

## Node Types
`HOST`, `ROUTER`, `SWITCH`, `ACCESS_POINT`, `STATION`

## Channel Types  
`POINT_TO_POINT`, `CSMA`, `WIFI`

## Traffic Types
`UDP_ECHO`, `ON_OFF`, `BULK_SEND`, `CUSTOM_SOCKET`

## Key Patterns

**Adding features typically involves:**
1. Model class in `models/`
2. UI widget in `views/`
3. Generator code in `services/ns3_generator.py`

**WSL path conversion:**
- `C:\foo` ↔ `/mnt/c/foo`
- Uses `wsl.exe` subprocess for execution

**Custom apps:** User writes Python class extending `ApplicationBase`, saved in project's `scripts/apps/`

## NOT Implemented Yet
- Undo/redo (partial)
- LTE/5G
- Mobility models (only static)
- Error models
- IPv6
- OSPF/RIP/AODV
- Plugin system
- 3D visualization
- Mini-map

## Starting a New Feature

1. Upload current `ns3_gui_mvp.zip`
2. Upload `NS3_GUI_V1_SUMMARY.md` (this doc's parent)
3. Describe the feature you want
4. Reference specific files if you know which need changes
