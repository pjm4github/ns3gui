"""
Pytest configuration and shared fixtures for ns-3 GUI tests.
"""

import pytest
import tempfile
import shutil
from pathlib import Path
from typing import Generator

# Add parent directory to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from models.network import NetworkModel, NodeModel, LinkModel, NodeType, Position, PortConfig
from models.simulation import SimulationConfig, TrafficFlow, TrafficProtocol, TrafficApplication
from models.project import Project, ProjectManager, ProjectMetadata
from services.project_manager import ProjectManager as LegacyProjectManager
from services.ns3_generator import NS3ScriptGenerator


# ============== Temporary Directory Fixtures ==============

@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for test files."""
    tmp = tempfile.mkdtemp(prefix="ns3_gui_test_")
    yield Path(tmp)
    shutil.rmtree(tmp, ignore_errors=True)


@pytest.fixture
def temp_workspace(temp_dir: Path) -> Path:
    """Create a temporary workspace directory structure."""
    workspace = temp_dir / "workspace"
    workspace.mkdir()
    (workspace / "projects").mkdir()
    return workspace


# ============== Model Fixtures ==============

@pytest.fixture
def empty_network() -> NetworkModel:
    """Create an empty network model."""
    return NetworkModel()


@pytest.fixture
def simple_network() -> NetworkModel:
    """Create a simple 2-node network with one link."""
    network = NetworkModel()
    
    # Create two hosts
    host1 = NodeModel(
        id="host1",
        node_type=NodeType.HOST,
        name="Host 1",
        position=Position(100, 100)
    )
    host2 = NodeModel(
        id="host2", 
        node_type=NodeType.HOST,
        name="Host 2",
        position=Position(300, 100)
    )
    
    network.add_node(host1)
    network.add_node(host2)
    
    # Create link between them
    link = LinkModel(
        id="link1",
        source_node_id="host1",
        target_node_id="host2",
        source_port_id=host1.ports[0].id if host1.ports else "",
        target_port_id=host2.ports[0].id if host2.ports else "",
    )
    network.add_link(link)
    
    return network


@pytest.fixture
def star_network() -> NetworkModel:
    """Create a star topology with a switch and 4 hosts."""
    network = NetworkModel()
    
    # Create central switch
    switch = NodeModel(
        id="switch1",
        node_type=NodeType.SWITCH,
        name="Switch 1",
        position=Position(200, 200)
    )
    network.add_node(switch)
    
    # Create 4 hosts around the switch
    positions = [(100, 100), (300, 100), (100, 300), (300, 300)]
    for i, (x, y) in enumerate(positions, 1):
        host = NodeModel(
            id=f"host{i}",
            node_type=NodeType.HOST,
            name=f"Host {i}",
            position=Position(x, y)
        )
        network.add_node(host)
        
        # Link to switch
        link = LinkModel(
            id=f"link{i}",
            source_node_id=f"host{i}",
            target_node_id="switch1",
            source_port_id=host.ports[0].id if host.ports else "",
            target_port_id=switch.ports[i-1].id if len(switch.ports) >= i else "",
        )
        network.add_link(link)
    
    return network


@pytest.fixture
def routed_network() -> NetworkModel:
    """Create a network with router connecting two subnets."""
    network = NetworkModel()
    
    # Create router
    router = NodeModel(
        id="router1",
        node_type=NodeType.ROUTER,
        name="Router 1",
        position=Position(200, 200)
    )
    network.add_node(router)
    
    # Create hosts on each side
    host1 = NodeModel(
        id="host1",
        node_type=NodeType.HOST,
        name="Host 1",
        position=Position(50, 200)
    )
    host2 = NodeModel(
        id="host2",
        node_type=NodeType.HOST,
        name="Host 2", 
        position=Position(350, 200)
    )
    network.add_node(host1)
    network.add_node(host2)
    
    # Create links
    link1 = LinkModel(
        id="link1",
        source_node_id="host1",
        target_node_id="router1",
    )
    link2 = LinkModel(
        id="link2",
        source_node_id="router1",
        target_node_id="host2",
    )
    network.add_link(link1)
    network.add_link(link2)
    
    return network


# ============== Simulation Config Fixtures ==============

@pytest.fixture
def basic_sim_config() -> SimulationConfig:
    """Create a basic simulation configuration."""
    config = SimulationConfig()
    config.duration = 10.0
    config.enable_flow_monitor = True
    return config


@pytest.fixture
def sim_config_with_flow(simple_network: NetworkModel) -> SimulationConfig:
    """Create simulation config with a traffic flow."""
    config = SimulationConfig()
    config.duration = 10.0
    config.enable_flow_monitor = True
    
    flow = TrafficFlow(
        id="flow1",
        name="Test Flow",
        source_node_id="host1",
        target_node_id="host2",
        protocol=TrafficProtocol.UDP,
        application=TrafficApplication.ECHO,
        start_time=1.0,
        stop_time=9.0,
        packet_size=1024,
        echo_packets=10,
        echo_interval=1.0
    )
    config.flows.append(flow)
    
    return config


# ============== Project Fixtures ==============

@pytest.fixture
def project_manager(temp_workspace: Path) -> ProjectManager:
    """Create a project manager with temporary workspace."""
    return ProjectManager(temp_workspace)


@pytest.fixture
def test_project(project_manager: ProjectManager) -> Project:
    """Create a test project."""
    return project_manager.create_project("test_project", "Test project for unit tests")


# ============== Generator Fixtures ==============

@pytest.fixture
def script_generator() -> NS3ScriptGenerator:
    """Create an NS3 script generator."""
    return NS3ScriptGenerator()


# ============== Helper Functions ==============

def assert_valid_python(code: str, filename: str = "test.py"):
    """Assert that code is valid Python syntax."""
    try:
        compile(code, filename, 'exec')
    except SyntaxError as e:
        pytest.fail(f"Invalid Python syntax at line {e.lineno}: {e.msg}\n{code}")


def assert_contains_all(text: str, substrings: list[str]):
    """Assert that text contains all substrings."""
    for s in substrings:
        assert s in text, f"Expected '{s}' in text"


def count_occurrences(text: str, substring: str) -> int:
    """Count occurrences of substring in text."""
    return text.count(substring)
