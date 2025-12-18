"""
Unit tests for network model classes.

Tests:
- NodeModel creation and properties
- LinkModel creation and validation
- NetworkModel operations (add/remove nodes/links)
- Port configuration
- Routing table management
"""

import pytest
from models.network import (
    NetworkModel, NodeModel, LinkModel, NodeType, Position, 
    PortConfig, PortType, MediumType, RouteEntry, RoutingMode
)


class TestNodeModel:
    """Tests for NodeModel class."""
    
    def test_create_host(self):
        """Test creating a host node."""
        node = NodeModel(
            id="test1",
            node_type=NodeType.HOST,
            name="Test Host"
        )
        assert node.id == "test1"
        assert node.node_type == NodeType.HOST
        assert node.name == "Test Host"
        assert len(node.ports) > 0  # Should have default ports
    
    def test_create_router(self):
        """Test creating a router node."""
        node = NodeModel(
            id="router1",
            node_type=NodeType.ROUTER,
            name="Test Router"
        )
        assert node.node_type == NodeType.ROUTER
        assert node.forwarding_enabled == True  # Default for routers
    
    def test_create_switch(self):
        """Test creating a switch node."""
        node = NodeModel(
            id="switch1",
            node_type=NodeType.SWITCH,
            name="Test Switch"
        )
        assert node.node_type == NodeType.SWITCH
        assert len(node.ports) >= 4  # Switches should have multiple ports
    
    def test_node_position(self):
        """Test node positioning."""
        node = NodeModel(
            id="test1",
            node_type=NodeType.HOST,
            position=Position(100, 200)
        )
        assert node.position.x == 100
        assert node.position.y == 200
    
    def test_node_medium_type(self):
        """Test node medium type."""
        wired = NodeModel(id="w1", node_type=NodeType.HOST, medium_type=MediumType.WIRED, position=Position(0, 0))
        wifi = NodeModel(id="w2", node_type=NodeType.HOST, medium_type=MediumType.WIFI_STATION, position=Position(100, 0))
        
        assert wired.medium_type == MediumType.WIRED
        assert wifi.medium_type == MediumType.WIFI_STATION
    
    def test_app_script(self):
        """Test application script storage."""
        node = NodeModel(id="test1", node_type=NodeType.HOST)
        assert not node.has_app_script
        
        node.app_script = "print('hello')"
        assert node.has_app_script
        assert node.app_script == "print('hello')"
    
    def test_routing_table(self):
        """Test routing table operations."""
        node = NodeModel(id="test1", node_type=NodeType.HOST)
        
        route = RouteEntry(
            id="route1",
            destination="10.1.2.0",
            prefix_length=24,
            gateway="10.1.1.1",
            interface=0
        )
        node.routing_table.append(route)
        
        assert len(node.routing_table) == 1
        assert node.routing_table[0].destination == "10.1.2.0"


class TestLinkModel:
    """Tests for LinkModel class."""
    
    def test_create_link(self):
        """Test creating a link."""
        link = LinkModel(
            id="link1",
            source_node_id="node1",
            target_node_id="node2"
        )
        assert link.id == "link1"
        assert link.source_node_id == "node1"
        assert link.target_node_id == "node2"
    
    def test_link_properties(self):
        """Test link properties."""
        link = LinkModel(
            id="link1",
            source_node_id="node1",
            target_node_id="node2",
            data_rate="100Mbps",
            delay="2ms"
        )
        assert link.data_rate == "100Mbps"
        assert link.delay == "2ms"
    
    def test_link_with_ports(self):
        """Test link with specific port IDs."""
        link = LinkModel(
            id="link1",
            source_node_id="node1",
            target_node_id="node2",
            source_port_id="port1",
            target_port_id="port2"
        )
        assert link.source_port_id == "port1"
        assert link.target_port_id == "port2"


class TestNetworkModel:
    """Tests for NetworkModel class."""
    
    def test_empty_network(self, empty_network):
        """Test empty network creation."""
        assert len(empty_network.nodes) == 0
        assert len(empty_network.links) == 0
    
    def test_add_node(self, empty_network):
        """Test adding a node using the API."""
        node = empty_network.add_node(NodeType.HOST, Position(100, 100))
        
        assert len(empty_network.nodes) == 1
        assert empty_network.get_node(node.id) == node
    
    def test_add_duplicate_node(self, empty_network):
        """Test that duplicate node IDs are handled."""
        node1 = NodeModel(id="test1", node_type=NodeType.HOST, position=Position(0, 0))
        node2 = NodeModel(id="test1", node_type=NodeType.HOST, position=Position(100, 100))
        
        empty_network.nodes[node1.id] = node1
        empty_network.nodes[node2.id] = node2  # Should overwrite
        
        assert len(empty_network.nodes) == 1
    
    def test_remove_node(self, simple_network):
        """Test removing a node."""
        initial_count = len(simple_network.nodes)
        simple_network.remove_node("host1")
        
        assert len(simple_network.nodes) == initial_count - 1
        assert simple_network.get_node("host1") is None
    
    def test_add_link(self, empty_network):
        """Test adding a link using the API."""
        # First add nodes using the API
        node1 = empty_network.add_node(NodeType.HOST, Position(0, 0))
        node2 = empty_network.add_node(NodeType.HOST, Position(100, 0))
        
        # Add link using API
        link = empty_network.add_link(node1.id, node2.id)
        
        assert len(empty_network.links) == 1
        assert link is not None
    
    def test_remove_link(self, simple_network):
        """Test removing a link."""
        initial_count = len(simple_network.links)
        simple_network.remove_link("link1")
        
        assert len(simple_network.links) == initial_count - 1
    
    def test_get_node(self, simple_network):
        """Test getting a node by ID."""
        node = simple_network.get_node("host1")
        assert node is not None
        assert node.name == "Host 1"
        
        # Non-existent node
        assert simple_network.get_node("nonexistent") is None
    
    def test_get_link(self, simple_network):
        """Test getting a link by ID."""
        link = simple_network.get_link("link1")
        assert link is not None
        assert link.source_node_id == "host1"
        
        # Non-existent link
        assert simple_network.get_link("nonexistent") is None


class TestPortConfig:
    """Tests for PortConfig class."""
    
    def test_create_port(self):
        """Test creating a port."""
        port = PortConfig(
            id="port1",
            port_number=0,
            port_name="eth0"
        )
        assert port.id == "port1"
        assert port.port_number == 0
        assert port.port_name == "eth0"
    
    def test_port_ip_config(self):
        """Test port IP configuration."""
        port = PortConfig(
            id="port1",
            ip_address="10.1.1.1",
            netmask="255.255.255.0"
        )
        assert port.ip_address == "10.1.1.1"
        assert port.netmask == "255.255.255.0"
    
    def test_port_types(self):
        """Test different port types."""
        ethernet = PortConfig(id="p1", port_type=PortType.ETHERNET)
        wireless = PortConfig(id="p2", port_type=PortType.WIRELESS)
        
        assert ethernet.port_type == PortType.ETHERNET
        assert wireless.port_type == PortType.WIRELESS


class TestRouteEntry:
    """Tests for RouteEntry class."""
    
    def test_create_route(self):
        """Test creating a route entry."""
        route = RouteEntry(
            id="route1",
            destination="10.1.2.0",
            prefix_length=24,
            gateway="10.1.1.1",
            interface=0
        )
        assert route.destination == "10.1.2.0"
        assert route.prefix_length == 24
        assert route.gateway == "10.1.1.1"
    
    def test_default_route(self):
        """Test creating a default route."""
        route = RouteEntry(
            id="default",
            destination="0.0.0.0",
            prefix_length=0,
            gateway="10.1.1.1",
            interface=0
        )
        assert route.destination == "0.0.0.0"
        assert route.prefix_length == 0
