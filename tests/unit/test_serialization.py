"""
Unit tests for topology serialization (save/load).

Tests:
- Save topology to JSON
- Load topology from JSON
- Round-trip preservation
- Schema validation
- Flow serialization
- Routing table serialization
"""

import pytest
import json
from pathlib import Path

from models.network import (
    NetworkModel, NodeModel, LinkModel, NodeType, Position,
    PortConfig, RouteEntry, RoutingMode, MediumType
)
from models.simulation import TrafficFlow, TrafficProtocol, TrafficApplication
from services.project_manager import ProjectManager


class TestTopologySerialization:
    """Tests for topology save/load operations."""
    
    def test_save_empty_network(self, empty_network, temp_dir):
        """Test saving an empty network."""
        pm = ProjectManager()
        filepath = temp_dir / "empty.json"
        
        result = pm.save(empty_network, filepath)
        
        assert result == True
        assert filepath.exists()
        
        # Verify JSON structure
        with open(filepath) as f:
            data = json.load(f)
        
        assert "topology" in data
        assert "nodes" in data["topology"]
        assert "links" in data["topology"]
    
    def test_save_simple_network(self, simple_network, temp_dir):
        """Test saving a simple network."""
        pm = ProjectManager()
        filepath = temp_dir / "simple.json"
        
        pm.save(simple_network, filepath)
        
        with open(filepath) as f:
            data = json.load(f)
        
        assert len(data["topology"]["nodes"]) == 2
        assert len(data["topology"]["links"]) == 1
    
    def test_load_topology(self, simple_network, temp_dir):
        """Test loading a topology."""
        pm = ProjectManager()
        filepath = temp_dir / "test.json"
        
        # Save first
        pm.save(simple_network, filepath)
        
        # Load
        loaded = pm.load(filepath)
        
        assert loaded is not None
        assert len(loaded.nodes) == 2
        assert len(loaded.links) == 1
    
    def test_roundtrip_preservation(self, simple_network, temp_dir):
        """Test that save/load preserves data."""
        pm = ProjectManager()
        filepath = temp_dir / "roundtrip.json"
        
        # Get original data
        original_node_names = {n.name for n in simple_network.nodes.values()}
        
        # Save and load
        pm.save(simple_network, filepath)
        loaded = pm.load(filepath)
        
        # Verify preservation
        loaded_node_names = {n.name for n in loaded.nodes.values()}
        assert original_node_names == loaded_node_names
    
    def test_node_properties_preserved(self, temp_dir):
        """Test that node properties are preserved."""
        network = NetworkModel()
        node = NodeModel(
            id="test1",
            node_type=NodeType.HOST,
            name="Test Node",
            description="A test node",
            position=Position(150, 250),
            medium_type=MediumType.WIRED
        )
        network.add_node(node)
        
        pm = ProjectManager()
        filepath = temp_dir / "props.json"
        pm.save(network, filepath)
        loaded = pm.load(filepath)
        
        loaded_node = loaded.get_node("test1")
        assert loaded_node.name == "Test Node"
        assert loaded_node.description == "A test node"
        assert loaded_node.position.x == 150
        assert loaded_node.position.y == 250
        assert loaded_node.medium_type == MediumType.WIRED
    
    def test_port_config_preserved(self, temp_dir):
        """Test that port configuration is preserved."""
        network = NetworkModel()
        node = NodeModel(id="test1", node_type=NodeType.HOST)
        
        # Configure a port
        if node.ports:
            node.ports[0].ip_address = "10.1.1.1"
            node.ports[0].netmask = "255.255.255.0"
        
        network.add_node(node)
        
        pm = ProjectManager()
        filepath = temp_dir / "ports.json"
        pm.save(network, filepath)
        loaded = pm.load(filepath)
        
        loaded_node = loaded.get_node("test1")
        if loaded_node.ports:
            assert loaded_node.ports[0].ip_address == "10.1.1.1"
            assert loaded_node.ports[0].netmask == "255.255.255.0"
    
    def test_routing_table_preserved(self, temp_dir):
        """Test that routing tables are preserved."""
        network = NetworkModel()
        node = NodeModel(id="test1", node_type=NodeType.HOST)
        node.routing_mode = RoutingMode.MANUAL
        node.routing_table.append(RouteEntry(
            id="r1",
            destination="10.1.2.0",
            prefix_length=24,
            gateway="10.1.1.254",
            interface=0
        ))
        network.add_node(node)
        
        pm = ProjectManager()
        filepath = temp_dir / "routes.json"
        pm.save(network, filepath)
        loaded = pm.load(filepath)
        
        loaded_node = loaded.get_node("test1")
        assert loaded_node.routing_mode == RoutingMode.MANUAL
        assert len(loaded_node.routing_table) == 1
        assert loaded_node.routing_table[0].destination == "10.1.2.0"
    
    def test_link_properties_preserved(self, temp_dir):
        """Test that link properties are preserved."""
        network = NetworkModel()
        
        node1 = NodeModel(id="n1", node_type=NodeType.HOST)
        node2 = NodeModel(id="n2", node_type=NodeType.HOST)
        network.add_node(node1)
        network.add_node(node2)
        
        link = LinkModel(
            id="link1",
            source_node_id="n1",
            target_node_id="n2",
            data_rate="100Mbps",
            delay="5ms"
        )
        network.add_link(link)
        
        pm = ProjectManager()
        filepath = temp_dir / "links.json"
        pm.save(network, filepath)
        loaded = pm.load(filepath)
        
        loaded_link = loaded.get_link("link1")
        assert loaded_link.data_rate == "100Mbps"
        assert loaded_link.delay == "5ms"
    
    def test_app_script_file_preserved(self, temp_dir):
        """Test that app_script_file reference is preserved."""
        network = NetworkModel()
        node = NodeModel(id="test1", node_type=NodeType.HOST, name="Host 1")
        node.app_script = "print('test')"  # Has script
        network.add_node(node)
        
        pm = ProjectManager()
        filepath = temp_dir / "app.json"
        pm.save(network, filepath)
        
        # Check the JSON directly
        with open(filepath) as f:
            data = json.load(f)
        
        node_data = data["topology"]["nodes"][0]
        assert "app_script_file" in node_data
        assert node_data["app_script_file"] == "scripts/host_1.py"


class TestFlowSerialization:
    """Tests for traffic flow serialization."""
    
    def test_save_flows(self, simple_network, temp_dir):
        """Test saving flows with topology."""
        flow = TrafficFlow(
            id="f1",
            name="Test Flow",
            source_node_id="host1",
            target_node_id="host2",
            protocol=TrafficProtocol.UDP,
            application=TrafficApplication.ECHO,
            start_time=1.0,
            stop_time=9.0
        )
        simple_network.saved_flows.append(flow)
        
        pm = ProjectManager()
        filepath = temp_dir / "flows.json"
        pm.save(simple_network, filepath)
        
        with open(filepath) as f:
            data = json.load(f)
        
        assert "simulation" in data
        assert "flows" in data["simulation"]
        assert len(data["simulation"]["flows"]) == 1
    
    def test_load_flows(self, simple_network, temp_dir):
        """Test loading flows with topology."""
        flow = TrafficFlow(
            id="f1",
            name="Test Flow",
            source_node_id="host1",
            target_node_id="host2",
            protocol=TrafficProtocol.UDP,
            application=TrafficApplication.ECHO
        )
        simple_network.saved_flows.append(flow)
        
        pm = ProjectManager()
        filepath = temp_dir / "flows.json"
        pm.save(simple_network, filepath)
        loaded = pm.load(filepath)
        
        assert len(loaded.saved_flows) == 1
        assert loaded.saved_flows[0].name == "Test Flow"


class TestSchemaValidation:
    """Tests for JSON schema validation."""
    
    def test_invalid_json(self, temp_dir):
        """Test loading invalid JSON."""
        filepath = temp_dir / "invalid.json"
        filepath.write_text("not valid json {")
        
        pm = ProjectManager()
        
        with pytest.raises(ValueError):
            pm.load(filepath)
    
    def test_missing_topology(self, temp_dir):
        """Test loading JSON without topology section."""
        filepath = temp_dir / "missing.json"
        filepath.write_text('{"schema": {"version": "1.0"}}')
        
        pm = ProjectManager()
        
        with pytest.raises(ValueError):
            pm.load(filepath)
    
    def test_nonexistent_file(self, temp_dir):
        """Test loading non-existent file."""
        pm = ProjectManager()
        
        with pytest.raises(FileNotFoundError):
            pm.load(temp_dir / "nonexistent.json")


class TestComplexTopologies:
    """Tests for complex topology serialization."""
    
    def test_star_topology_roundtrip(self, star_network, temp_dir):
        """Test star topology save/load."""
        pm = ProjectManager()
        filepath = temp_dir / "star.json"
        
        pm.save(star_network, filepath)
        loaded = pm.load(filepath)
        
        assert len(loaded.nodes) == 5  # 1 switch + 4 hosts
        assert len(loaded.links) == 4
    
    def test_routed_topology_roundtrip(self, routed_network, temp_dir):
        """Test routed topology save/load."""
        pm = ProjectManager()
        filepath = temp_dir / "routed.json"
        
        pm.save(routed_network, filepath)
        loaded = pm.load(filepath)
        
        assert len(loaded.nodes) == 3  # 1 router + 2 hosts
        
        # Verify router is correct type
        router = None
        for node in loaded.nodes.values():
            if node.node_type == NodeType.ROUTER:
                router = node
                break
        
        assert router is not None
