"""
Integration tests for project workflow.

Tests:
- Create new project
- Open existing project
- Save project with all components
- Load topology, flows, and app scripts
- Run history management
"""

import pytest
import json
from pathlib import Path
from datetime import datetime

from models.network import NetworkModel, NodeModel, LinkModel, NodeType, Position
from models.simulation import SimulationConfig, TrafficFlow, TrafficProtocol, TrafficApplication
from models.project import Project, ProjectManager, ProjectMetadata, SimulationRun


class TestProjectCreation:
    """Tests for project creation."""
    
    def test_create_project(self, project_manager):
        """Test creating a new project."""
        project = project_manager.create_project("test_project", "Test description")
        
        assert project is not None
        assert project.name == "test_project"
        assert project.metadata.description == "Test description"
        assert project.path is not None
        assert project.path.exists()
    
    def test_create_project_directory_structure(self, project_manager):
        """Test that project creates correct directory structure."""
        project = project_manager.create_project("dir_test")
        
        # Check directories exist
        assert (project.path / "scripts").exists()
        assert (project.path / "results").exists()
        
        # Check project.json exists
        assert (project.path / "project.json").exists()
    
    def test_create_project_sanitizes_name(self, project_manager):
        """Test that project names are sanitized."""
        project = project_manager.create_project("Test@Project#Invalid$Chars")
        
        # Name should be sanitized (no special chars except ._- and space in path)
        assert "@" not in project.path.name
        assert "#" not in project.path.name
        assert "$" not in project.path.name
    
    def test_create_duplicate_project_name(self, project_manager):
        """Test creating project with duplicate name."""
        project_manager.create_project("duplicate")
        project2 = project_manager.create_project("duplicate")
        
        # Should create with modified name
        assert project2.path.name != "duplicate" or project2.path != project_manager.projects_dir / "duplicate"


class TestProjectSaving:
    """Tests for saving project components."""
    
    def test_save_topology(self, project_manager, simple_network):
        """Test saving topology to project."""
        project = project_manager.create_project("topo_test")
        
        project_manager.save_project(project, network_model=simple_network)
        
        assert project.topology_path.exists()
        
        with open(project.topology_path) as f:
            data = json.load(f)
        
        assert len(data["topology"]["nodes"]) == 2
    
    def test_save_flows(self, project_manager, simple_network):
        """Test saving flows to project."""
        project = project_manager.create_project("flow_test")
        
        config = SimulationConfig()
        config.flows.append(TrafficFlow(
            id="f1",
            name="Test Flow",
            source_node_id="host1",
            target_node_id="host2",
            protocol=TrafficProtocol.UDP,
            application=TrafficApplication.ECHO
        ))
        
        project_manager.save_project(
            project, 
            network_model=simple_network,
            sim_config=config
        )
        
        assert project.flows_path.exists()
        
        with open(project.flows_path) as f:
            data = json.load(f)
        
        assert len(data["flows"]) == 1
    
    def test_save_app_scripts(self, project_manager, simple_network, temp_dir):
        """Test saving application scripts."""
        project = project_manager.create_project("script_test")
        
        # Create a temp output dir with a script
        output_dir = temp_dir / "output"
        output_dir.mkdir()
        (output_dir / "test_app.py").write_text("print('test')")
        
        project_manager.save_project(
            project,
            network_model=simple_network,
            output_dir=str(output_dir)
        )
        
        # Check script was copied
        assert (project.scripts_dir / "test_app.py").exists()


class TestProjectLoading:
    """Tests for loading project components."""
    
    def test_open_project(self, project_manager, simple_network):
        """Test opening an existing project."""
        # Create and save
        original = project_manager.create_project("open_test")
        project_manager.save_project(original, network_model=simple_network)
        
        # Close and reopen
        project_manager._current_project = None
        loaded = project_manager.open_project("open_test")
        
        assert loaded is not None
        assert loaded.name == "open_test"
    
    def test_load_topology(self, project_manager, simple_network):
        """Test loading topology from project."""
        project = project_manager.create_project("load_topo")
        project_manager.save_project(project, network_model=simple_network)
        
        loaded_network = project_manager.load_topology(project)
        
        assert loaded_network is not None
        assert len(loaded_network.nodes) == 2
    
    def test_load_flows(self, project_manager, simple_network):
        """Test loading flows from project."""
        project = project_manager.create_project("load_flows")
        
        config = SimulationConfig()
        config.flows.append(TrafficFlow(
            id="f1",
            name="Test Flow",
            source_node_id="host1",
            target_node_id="host2"
        ))
        
        project_manager.save_project(project, network_model=simple_network, sim_config=config)
        
        flows = project_manager.load_flows(project)
        
        assert len(flows) == 1
        assert flows[0]["name"] == "Test Flow"


class TestRunHistory:
    """Tests for simulation run history."""
    
    def test_create_run_directory(self, project_manager):
        """Test creating a run directory."""
        project = project_manager.create_project("run_test")
        
        run_dir = project.create_run_dir()
        
        assert run_dir.exists()
        assert run_dir.parent == project.results_dir
        assert run_dir.name.startswith("run_")
    
    def test_add_simulation_run(self, project_manager):
        """Test adding a simulation run record."""
        project = project_manager.create_project("run_record")
        
        run = SimulationRun(
            id="run_20250101_120000",
            timestamp=datetime.now().isoformat(),
            duration=10.0,
            status="success"
        )
        
        project_manager.add_simulation_run(project, run)
        
        # Reload and verify
        loaded = project_manager.open_project("run_record")
        assert len(loaded.runs) == 1
        assert loaded.runs[0].status == "success"
    
    def test_multiple_runs(self, project_manager):
        """Test multiple simulation runs."""
        project = project_manager.create_project("multi_run")
        
        for i in range(3):
            run = SimulationRun(
                id=f"run_{i}",
                timestamp=datetime.now().isoformat(),
                duration=10.0,
                status="success"
            )
            project_manager.add_simulation_run(project, run)
        
        loaded = project_manager.open_project("multi_run")
        assert len(loaded.runs) == 3


class TestProjectWorkflow:
    """End-to-end workflow tests."""
    
    def test_full_workflow(self, project_manager, simple_network):
        """Test complete project workflow."""
        # 1. Create project
        project = project_manager.create_project("workflow_test", "Full workflow test")
        
        # 2. Create simulation config with flow
        config = SimulationConfig()
        config.duration = 15.0
        config.flows.append(TrafficFlow(
            id="f1",
            name="Main Flow",
            source_node_id="host1",
            target_node_id="host2",
            protocol=TrafficProtocol.UDP,
            application=TrafficApplication.ECHO,
            start_time=1.0,
            stop_time=14.0
        ))
        
        # 3. Save everything
        project_manager.save_project(
            project,
            network_model=simple_network,
            sim_config=config
        )
        
        # 4. Add a run record
        run_dir = project.create_run_dir()
        run = SimulationRun(
            id=run_dir.name,
            timestamp=datetime.now().isoformat(),
            duration=15.0,
            status="success",
            console_log_path=f"results/{run_dir.name}/console.log"
        )
        project_manager.add_simulation_run(project, run)
        
        # 5. Close and reopen
        project_manager._current_project = None
        
        # 6. Verify everything loads correctly
        loaded = project_manager.open_project("workflow_test")
        assert loaded.name == "workflow_test"
        assert loaded.metadata.description == "Full workflow test"
        
        loaded_network = project_manager.load_topology(loaded)
        assert len(loaded_network.nodes) == 2
        
        loaded_flows = project_manager.load_flows(loaded)
        assert len(loaded_flows) == 1
        assert loaded_flows[0]["name"] == "Main Flow"
        
        assert len(loaded.runs) == 1
        assert loaded.runs[0].status == "success"
    
    def test_project_with_app_scripts(self, project_manager):
        """Test project with custom application scripts."""
        project = project_manager.create_project("app_test")
        
        # Create network with app script
        network = NetworkModel()
        host = NodeModel(id="h1", node_type=NodeType.HOST, name="Host 1", position=Position(0, 0))
        host.app_script = """
from app_base import ApplicationBase

class TestApp(ApplicationBase):
    def create_payload(self):
        return b"test data"
"""
        network.nodes[host.id] = host
        
        # Save project
        project_manager.save_project(project, network_model=network)
        
        # Verify app_script_file is in topology
        with open(project.topology_path) as f:
            data = json.load(f)
        
        node_data = data["topology"]["nodes"][0]
        assert "app_script_file" in node_data


class TestListProjects:
    """Tests for listing projects."""
    
    def test_list_projects(self, project_manager):
        """Test listing all projects."""
        # Create some projects
        project_manager.create_project("proj1")
        project_manager.create_project("proj2")
        project_manager.create_project("proj3")
        
        projects = project_manager.list_projects()
        
        assert len(projects) >= 3
        names = [p["name"] for p in projects]
        assert "proj1" in names
        assert "proj2" in names
        assert "proj3" in names
