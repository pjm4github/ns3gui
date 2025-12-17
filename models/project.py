"""
Project Model - Organizes all simulation artifacts.

A project is a self-contained unit containing:
- Topology definition (nodes, links, ports)
- Traffic flows configuration
- Generated simulation scripts
- Simulation run results
- Console output logs

Directory Structure:
    projects/
    └── my_network/                    # Project folder (project name)
        ├── project.json               # Project metadata and settings
        ├── topology.json              # Network topology definition
        ├── flows.json                 # Current traffic flow definitions
        ├── scripts/                   # Generated simulation files
        │   ├── gui_simulation.py      # Main simulation script
        │   ├── app_base.py            # Application base class
        │   └── *.py                   # Host application scripts
        └── results/                   # Simulation results
            └── run_YYYYMMDD_HHMMSS/   # Timestamped run folder
                ├── run_info.json      # Run metadata
                ├── flows.json         # Flows used for this run
                ├── console.log        # WSL console output
                ├── trace.xml          # ns-3 trace file
                └── stats.json         # Parsed statistics
"""

import json
import shutil
import os
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field, asdict
from typing import Optional, Dict, List, Any, TYPE_CHECKING
from enum import Enum

if TYPE_CHECKING:
    from models.network import NetworkModel
    from models.simulation import SimulationConfig


class ProjectState(Enum):
    """Project lifecycle states."""
    NEW = "new"                    # Just created, not saved
    SAVED = "saved"               # Saved to disk
    MODIFIED = "modified"         # Has unsaved changes
    SIMULATION_READY = "ready"    # Ready to run simulation
    RUNNING = "running"           # Simulation in progress
    COMPLETED = "completed"       # Simulation finished


@dataclass
class SimulationRun:
    """Record of a simulation run."""
    id: str
    timestamp: str                # ISO format
    duration: float               # Configured duration
    status: str                   # success, failed, cancelled
    console_log_path: str = ""    # Relative path to console.log
    trace_file_path: str = ""     # Relative path to trace file
    stats_file_path: str = ""     # Relative path to stats.json
    error_message: str = ""
    node_count: int = 0
    link_count: int = 0
    flow_count: int = 0
    
    # Performance metrics (if available)
    packets_sent: int = 0
    packets_received: int = 0
    packets_dropped: int = 0
    throughput_mbps: float = 0.0


@dataclass 
class ProjectMetadata:
    """Project configuration and metadata."""
    name: str
    description: str = ""
    author: str = ""
    created: str = ""             # ISO format
    modified: str = ""            # ISO format
    version: str = "1.0"
    schema_version: str = "1.0"
    
    # Simulation settings
    simulation_duration: float = 10.0
    random_seed: int = 1
    
    # ns-3 settings
    ns3_path: str = ""            # Path used for this project
    
    # Import info (if imported from ns-3 example)
    imported_from: str = ""       # Original script path
    import_date: str = ""


@dataclass
class Project:
    """
    Complete project containing all simulation artifacts.
    
    This is the main container that ties together:
    - Network topology (stored in topology.json)
    - Traffic flows (stored in flows.json, managed via NetworkModel.saved_flows)
    - Simulation scripts (stored in scripts/)
    - Run results (stored in results/)
    
    Note: Flows are not stored in Project directly - they are saved/loaded
    via the NetworkModel.saved_flows or SimulationConfig.flows.
    """
    metadata: ProjectMetadata
    runs: List[SimulationRun] = field(default_factory=list)
    
    # Runtime state (not persisted)
    _path: Optional[Path] = field(default=None, repr=False)
    _state: ProjectState = field(default=ProjectState.NEW, repr=False)
    
    @property
    def path(self) -> Optional[Path]:
        """Get the project directory path."""
        return self._path
    
    @property
    def name(self) -> str:
        """Get project name."""
        return self.metadata.name
    
    @property
    def state(self) -> ProjectState:
        """Get project state."""
        return self._state
    
    @property
    def topology_path(self) -> Optional[Path]:
        """Get path to topology.json."""
        if self._path:
            return self._path / "topology.json"
        return None
    
    @property
    def flows_path(self) -> Optional[Path]:
        """Get path to flows.json."""
        if self._path:
            return self._path / "flows.json"
        return None
    
    @property
    def scripts_dir(self) -> Optional[Path]:
        """Get path to scripts directory."""
        if self._path:
            return self._path / "scripts"
        return None
    
    @property
    def results_dir(self) -> Optional[Path]:
        """Get path to results directory."""
        if self._path:
            return self._path / "results"
        return None
    
    def get_run_dir(self, run_id: str) -> Optional[Path]:
        """Get path to a specific run's directory."""
        if self._path:
            return self._path / "results" / run_id
        return None
    
    def create_run_dir(self) -> Path:
        """Create a new timestamped run directory."""
        if not self._path:
            raise ValueError("Project has no path set")
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        run_dir = self._path / "results" / f"run_{timestamp}"
        run_dir.mkdir(parents=True, exist_ok=True)
        return run_dir


class ProjectManager:
    """
    Manages project lifecycle: create, open, save, close.
    
    Usage:
        pm = ProjectManager(workspace_root)
        
        # Create new project
        project = pm.create_project("my_network")
        
        # Open existing project
        project = pm.open_project("my_network")
        
        # Save project
        pm.save_project(project, network_model)
        
        # List projects
        projects = pm.list_projects()
    """
    
    def __init__(self, workspace_root: Path):
        """
        Initialize project manager.
        
        Args:
            workspace_root: Root directory for all projects
        """
        self.workspace_root = Path(workspace_root)
        self.projects_dir = self.workspace_root / "projects"
        self._current_project: Optional[Project] = None
    
    @property
    def current_project(self) -> Optional[Project]:
        """Get the currently open project."""
        return self._current_project
    
    def ensure_workspace(self):
        """Create workspace directories if needed."""
        self.projects_dir.mkdir(parents=True, exist_ok=True)
    
    def list_projects(self) -> List[Dict[str, Any]]:
        """
        List all projects in the workspace.
        
        Returns:
            List of project info dictionaries with name, path, modified date
        """
        self.ensure_workspace()
        projects = []
        
        for item in self.projects_dir.iterdir():
            if item.is_dir():
                project_file = item / "project.json"
                if project_file.exists():
                    try:
                        with open(project_file, 'r') as f:
                            data = json.load(f)
                        projects.append({
                            "name": data.get("metadata", {}).get("name", item.name),
                            "path": str(item),
                            "description": data.get("metadata", {}).get("description", ""),
                            "modified": data.get("metadata", {}).get("modified", ""),
                            "has_topology": (item / "topology.json").exists(),
                            "run_count": len(list((item / "results").glob("run_*"))) if (item / "results").exists() else 0
                        })
                    except Exception as e:
                        # Include project even if metadata is corrupt
                        projects.append({
                            "name": item.name,
                            "path": str(item),
                            "description": f"(error reading metadata: {e})",
                            "modified": "",
                            "has_topology": (item / "topology.json").exists(),
                            "run_count": 0
                        })
        
        # Sort by modified date (newest first)
        projects.sort(key=lambda p: p.get("modified", ""), reverse=True)
        return projects
    
    def create_project(self, name: str, description: str = "") -> Project:
        """
        Create a new project.
        
        Args:
            name: Project name (used as directory name)
            description: Optional description
            
        Returns:
            New Project instance
        """
        self.ensure_workspace()
        
        # Sanitize name for filesystem
        safe_name = "".join(c for c in name if c.isalnum() or c in "._- ").strip()
        if not safe_name:
            safe_name = "untitled"
        
        project_path = self.projects_dir / safe_name
        
        # Handle name conflicts
        if project_path.exists():
            counter = 1
            while (self.projects_dir / f"{safe_name}_{counter}").exists():
                counter += 1
            safe_name = f"{safe_name}_{counter}"
            project_path = self.projects_dir / safe_name
        
        # Create directory structure
        project_path.mkdir(parents=True)
        (project_path / "scripts").mkdir()
        (project_path / "results").mkdir()
        
        # Create metadata
        now = datetime.now().isoformat()
        metadata = ProjectMetadata(
            name=safe_name,
            description=description,
            created=now,
            modified=now
        )
        
        project = Project(metadata=metadata)
        project._path = project_path
        project._state = ProjectState.NEW
        
        # Save initial project file
        self._save_project_metadata(project)
        
        self._current_project = project
        return project
    
    def open_project(self, name_or_path: str) -> Project:
        """
        Open an existing project.
        
        Args:
            name_or_path: Project name or full path
            
        Returns:
            Loaded Project instance
        """
        # Determine path
        path = Path(name_or_path)
        if not path.is_absolute():
            path = self.projects_dir / name_or_path
        
        if not path.exists():
            raise FileNotFoundError(f"Project not found: {path}")
        
        project_file = path / "project.json"
        if not project_file.exists():
            raise ValueError(f"Invalid project: missing project.json")
        
        # Load project metadata
        with open(project_file, 'r') as f:
            data = json.load(f)
        
        metadata = ProjectMetadata(**data.get("metadata", {}))
        
        # Load run history
        runs = []
        for run_data in data.get("runs", []):
            runs.append(SimulationRun(**run_data))
        
        project = Project(metadata=metadata, runs=runs)
        project._path = path
        project._state = ProjectState.SAVED
        
        self._current_project = project
        return project
    
    def load_flows(self, project: Project):
        """
        Load flows from project's flows.json.
        
        Args:
            project: Project to load flows from
            
        Returns:
            List of flow dictionaries (to be converted to TrafficFlow objects by caller)
        """
        if not project._path:
            return []
        
        flows_file = project._path / "flows.json"
        if not flows_file.exists():
            return []
        
        try:
            with open(flows_file, 'r') as f:
                data = json.load(f)
            return data.get("flows", [])
        except Exception as e:
            print(f"Error loading flows: {e}")
            return []
    
    def save_project(
        self, 
        project: Project, 
        network_model=None,
        sim_config=None,
        script_content: str = None,
        output_dir: str = None
    ):
        """
        Save all project components to disk.
        
        Args:
            project: Project to save
            network_model: Optional NetworkModel to save as topology
            sim_config: Optional SimulationConfig with flows to save
            script_content: Optional generated script content to save
            output_dir: Optional temp directory with generated files to copy
        """
        if not project._path:
            raise ValueError("Project has no path")
        
        # Update modified timestamp
        project.metadata.modified = datetime.now().isoformat()
        
        # Save project metadata
        self._save_project_metadata(project)
        
        # Save topology if provided
        if network_model:
            self._save_topology(project, network_model)
            
            # Save flows from network_model.saved_flows
            if hasattr(network_model, 'saved_flows') and network_model.saved_flows:
                self._save_flows_from_network(project, network_model)
        
        # Save flows from sim_config if provided
        if sim_config and hasattr(sim_config, 'flows') and sim_config.flows:
            self._save_flows_from_config(project, sim_config)
        
        # Save scripts
        if script_content or output_dir:
            self._save_scripts(project, script_content, output_dir)
        
        project._state = ProjectState.SAVED
    
    def _save_project_metadata(self, project: Project):
        """Save project.json file."""
        project_file = project._path / "project.json"
        
        data = {
            "metadata": asdict(project.metadata),
            "runs": [asdict(r) for r in project.runs]
        }
        
        with open(project_file, 'w') as f:
            json.dump(data, f, indent=2)
    
    def _save_flows_from_network(self, project: Project, network_model):
        """Save flows from network_model.saved_flows to flows.json."""
        flows_file = project._path / "flows.json"
        
        flows_data = []
        for flow in network_model.saved_flows:
            # Convert TrafficFlow from simulation.py to dict
            flow_dict = {
                "id": flow.id,
                "name": flow.name,
                "source_node_id": flow.source_node_id,
                "target_node_id": flow.target_node_id,
                "protocol": flow.protocol.value if hasattr(flow.protocol, 'value') else str(flow.protocol),
                "application": flow.application.value if hasattr(flow.application, 'value') else str(flow.application),
                "start_time": flow.start_time,
                "stop_time": flow.stop_time,
                "data_rate": flow.data_rate,
                "packet_size": flow.packet_size,
                "port": getattr(flow, 'port', 9),
                "echo_packets": getattr(flow, 'echo_packets', 10),
                "echo_interval": getattr(flow, 'echo_interval', 1.0),
            }
            flows_data.append(flow_dict)
        
        data = {"flows": flows_data}
        
        with open(flows_file, 'w') as f:
            json.dump(data, f, indent=2)
    
    def _save_flows_from_config(self, project: Project, sim_config):
        """Save flows from SimulationConfig to flows.json."""
        flows_file = project._path / "flows.json"
        
        flows_data = []
        for flow in sim_config.flows:
            flow_dict = {
                "id": flow.id,
                "name": flow.name,
                "source_node_id": flow.source_node_id,
                "target_node_id": flow.target_node_id,
                "protocol": flow.protocol.value if hasattr(flow.protocol, 'value') else str(flow.protocol),
                "application": flow.application.value if hasattr(flow.application, 'value') else str(flow.application),
                "start_time": flow.start_time,
                "stop_time": flow.stop_time,
                "data_rate": flow.data_rate,
                "packet_size": flow.packet_size,
                "port": getattr(flow, 'port', 9),
                "echo_packets": getattr(flow, 'echo_packets', 10),
                "echo_interval": getattr(flow, 'echo_interval', 1.0),
            }
            flows_data.append(flow_dict)
        
        data = {"flows": flows_data}
        
        with open(flows_file, 'w') as f:
            json.dump(data, f, indent=2)
    
    def _save_scripts(self, project: Project, script_content: str = None, output_dir: str = None):
        """Save generated scripts to project scripts directory."""
        scripts_dir = project.scripts_dir
        if not scripts_dir:
            return
        
        scripts_dir.mkdir(parents=True, exist_ok=True)
        
        # Save main script content if provided
        if script_content:
            script_path = scripts_dir / "gui_simulation.py"
            with open(script_path, 'w') as f:
                f.write(script_content)
        
        # Copy files from output directory if provided
        if output_dir and Path(output_dir).exists():
            output_path = Path(output_dir)
            
            # Copy all .py files from output dir (includes app scripts)
            for py_file in output_path.glob("*.py"):
                shutil.copy2(py_file, scripts_dir / py_file.name)
            
            # Also copy any .py files from apps subdirectory to scripts dir
            apps_src = output_path / "apps"
            if apps_src.exists():
                for app_file in apps_src.glob("*.py"):
                    shutil.copy2(app_file, scripts_dir / app_file.name)
            
            # Copy app_base.py from templates if not already present
            app_base_dest = scripts_dir / "app_base.py"
            if not app_base_dest.exists():
                # Try to find app_base.py in templates
                templates_dir = Path(__file__).parent.parent / "templates"
                app_base_src = templates_dir / "app_base.py"
                if app_base_src.exists():
                    shutil.copy2(app_base_src, app_base_dest)
    
    def _save_topology(self, project: Project, network_model):
        """Save topology.json file."""
        from services.project_manager import ProjectManager as LegacyPM
        
        legacy_pm = LegacyPM()
        legacy_pm.save(network_model, project.topology_path)
    
    def load_topology(self, project: Project):
        """
        Load topology from project.
        
        Args:
            project: Project to load topology from
            
        Returns:
            NetworkModel instance or None
        """
        if not project.topology_path or not project.topology_path.exists():
            return None
        
        from services.project_manager import ProjectManager as LegacyPM
        legacy_pm = LegacyPM()
        return legacy_pm.load(project.topology_path)
    
    def delete_project(self, name_or_path: str):
        """
        Delete a project and all its contents.
        
        Args:
            name_or_path: Project name or full path
        """
        path = Path(name_or_path)
        if not path.is_absolute():
            path = self.projects_dir / name_or_path
        
        if path.exists():
            shutil.rmtree(path)
        
        if self._current_project and self._current_project._path == path:
            self._current_project = None
    
    def duplicate_project(self, source_name: str, new_name: str) -> Project:
        """
        Create a copy of an existing project.
        
        Args:
            source_name: Name of project to copy
            new_name: Name for the new copy
            
        Returns:
            New Project instance
        """
        source_path = self.projects_dir / source_name
        if not source_path.exists():
            raise FileNotFoundError(f"Source project not found: {source_name}")
        
        # Create new project
        new_project = self.create_project(new_name)
        
        # Copy contents (except results)
        for item in source_path.iterdir():
            if item.name == "results":
                continue  # Don't copy run results
            if item.is_file():
                shutil.copy2(item, new_project._path / item.name)
            elif item.is_dir() and item.name != "results":
                shutil.copytree(item, new_project._path / item.name, dirs_exist_ok=True)
        
        # Update metadata
        new_project.metadata.name = new_project._path.name
        new_project.metadata.created = datetime.now().isoformat()
        new_project.metadata.modified = datetime.now().isoformat()
        self._save_project_metadata(new_project)
        
        return new_project
    
    def add_simulation_run(self, project: Project, run: SimulationRun):
        """Add a simulation run record to the project."""
        project.runs.append(run)
        self._save_project_metadata(project)
    
    def import_ns3_script(self, project: Project, script_path: Path) -> Path:
        """
        Import an ns-3 script into the project's scripts directory.
        
        Args:
            project: Target project
            script_path: Path to ns-3 script
            
        Returns:
            Path to imported copy
        """
        if not project.scripts_dir:
            raise ValueError("Project has no path")
        
        project.scripts_dir.mkdir(exist_ok=True)
        dest_path = project.scripts_dir / script_path.name
        
        shutil.copy2(script_path, dest_path)
        
        # Update metadata
        project.metadata.imported_from = str(script_path)
        project.metadata.import_date = datetime.now().isoformat()
        self._save_project_metadata(project)
        
        return dest_path
