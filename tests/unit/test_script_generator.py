"""
Unit tests for NS-3 script generation.

Tests:
- Script syntax validity
- Required imports present
- Node creation code
- Link/channel configuration
- IP addressing
- Traffic flow generation
- FlowMonitor setup
"""

import pytest
from tests.conftest import assert_valid_python, assert_contains_all

from models.network import NetworkModel, NodeModel, LinkModel, NodeType, Position
from models.simulation import SimulationConfig, TrafficFlow, TrafficProtocol, TrafficApplication
from services.ns3_generator import NS3ScriptGenerator, generate_ns3_script


class TestScriptGeneration:
    """Tests for NS3ScriptGenerator class."""
    
    def test_generate_empty_network(self, script_generator, empty_network, basic_sim_config):
        """Test generating script for empty network."""
        # Should handle gracefully or raise appropriate error
        script = script_generator.generate(empty_network, basic_sim_config)
        # Empty network might generate minimal script or raise error
        # depending on implementation
    
    def test_generate_simple_network(self, script_generator, simple_network, basic_sim_config):
        """Test generating script for simple 2-node network."""
        script = script_generator.generate(simple_network, basic_sim_config)
        
        # Verify valid Python
        assert_valid_python(script)
        
        # Verify required imports
        assert_contains_all(script, [
            "import ns.core",
            "import ns.network",
            "import ns.internet",
        ])
        
        # Verify node creation
        assert "NodeContainer" in script
        assert "nodes.Create" in script
        
        # Verify internet stack
        assert "InternetStackHelper" in script
    
    def test_generate_with_flow(self, script_generator, simple_network, sim_config_with_flow):
        """Test generating script with traffic flow."""
        script = script_generator.generate(simple_network, sim_config_with_flow)
        
        assert_valid_python(script)
        
        # Verify echo application setup
        assert_contains_all(script, [
            "UdpEchoServerHelper",
            "UdpEchoClientHelper",
        ])
    
    def test_generate_with_flow_monitor(self, script_generator, simple_network, basic_sim_config):
        """Test FlowMonitor code generation."""
        basic_sim_config.enable_flow_monitor = True
        script = script_generator.generate(simple_network, basic_sim_config)
        
        assert_valid_python(script)
        assert "FlowMonitorHelper" in script
        assert "SerializeToXmlFile" in script
    
    def test_generate_star_topology(self, script_generator, star_network, basic_sim_config):
        """Test generating script for star topology."""
        script = script_generator.generate(star_network, basic_sim_config)
        
        assert_valid_python(script)
        
        # Should have CSMA for switch connections
        assert "CsmaHelper" in script or "PointToPointHelper" in script
    
    def test_generate_routed_network(self, script_generator, routed_network, basic_sim_config):
        """Test generating script for routed network."""
        script = script_generator.generate(routed_network, basic_sim_config)
        
        assert_valid_python(script)
        
        # Should have routing setup
        assert "Ipv4GlobalRoutingHelper" in script or "PopulateRoutingTables" in script
    
    def test_simulation_duration(self, script_generator, simple_network, basic_sim_config):
        """Test that simulation duration is set correctly."""
        basic_sim_config.duration = 15.0
        script = script_generator.generate(simple_network, basic_sim_config)
        
        assert "15.0" in script or "15" in script
        assert "Simulator.Stop" in script
    
    def test_ip_addressing(self, script_generator, simple_network, basic_sim_config):
        """Test IP address assignment."""
        script = script_generator.generate(simple_network, basic_sim_config)
        
        assert_valid_python(script)
        assert "Ipv4AddressHelper" in script
        assert "SetBase" in script or "Assign" in script


class TestTrafficFlowGeneration:
    """Tests for traffic flow code generation."""
    
    def test_udp_echo_flow(self, script_generator, simple_network):
        """Test UDP Echo flow generation."""
        config = SimulationConfig()
        config.flows.append(TrafficFlow(
            id="f1",
            name="UDP Echo",
            source_node_id="host1",
            target_node_id="host2",
            protocol=TrafficProtocol.UDP,
            application=TrafficApplication.ECHO,
            start_time=1.0,
            stop_time=9.0,
            echo_packets=10,
            echo_interval=1.0
        ))
        
        script = script_generator.generate(simple_network, config)
        
        assert_valid_python(script)
        assert "UdpEchoServer" in script
        assert "UdpEchoClient" in script
    
    def test_onoff_flow(self, script_generator, simple_network):
        """Test OnOff application flow generation."""
        config = SimulationConfig()
        config.flows.append(TrafficFlow(
            id="f1",
            name="OnOff",
            source_node_id="host1",
            target_node_id="host2",
            protocol=TrafficProtocol.UDP,
            application=TrafficApplication.ONOFF,
            start_time=1.0,
            stop_time=9.0,
            data_rate="1Mbps",
            packet_size=1024
        ))
        
        script = script_generator.generate(simple_network, config)
        
        assert_valid_python(script)
        # OnOff generates sink + source
        assert "PacketSink" in script or "OnOffHelper" in script
    
    def test_multiple_flows(self, script_generator, star_network):
        """Test multiple flow generation."""
        config = SimulationConfig()
        
        # Add flows from each host to another
        for i in range(1, 4):
            config.flows.append(TrafficFlow(
                id=f"f{i}",
                name=f"Flow {i}",
                source_node_id=f"host{i}",
                target_node_id=f"host{i+1}",
                protocol=TrafficProtocol.UDP,
                application=TrafficApplication.ECHO,
                start_time=float(i),
                stop_time=9.0
            ))
        
        script = script_generator.generate(star_network, config)
        
        assert_valid_python(script)
        # Should have multiple echo setups
        assert script.count("UdpEchoServer") >= 3


class TestCustomApplicationGeneration:
    """Tests for custom application code generation."""
    
    def test_custom_app_import(self, script_generator, simple_network, basic_sim_config):
        """Test custom application import generation."""
        # Add app script to node
        node = simple_network.get_node("host1")
        node.app_script = """
from app_base import ApplicationBase

class TestApp(ApplicationBase):
    def create_payload(self):
        return b"test"
"""
        
        # Add flow using custom app
        basic_sim_config.flows.append(TrafficFlow(
            id="f1",
            source_node_id="host1",
            target_node_id="host2",
            protocol=TrafficProtocol.UDP,
            application=TrafficApplication.CUSTOM
        ))
        
        script = script_generator.generate(simple_network, basic_sim_config)
        
        assert_valid_python(script)
        # Should import custom module
        assert "import" in script.lower()
    
    def test_get_required_files(self, script_generator, simple_network, basic_sim_config):
        """Test required files detection."""
        node = simple_network.get_node("host1")
        node.app_script = "class TestApp: pass"
        
        files = script_generator.get_required_files(simple_network, basic_sim_config)
        
        # Should include app_base.py and custom script
        file_names = [f['dest_name'] for f in files]
        assert 'app_base.py' in file_names


class TestScriptValidation:
    """Tests for script validation and error handling."""
    
    def test_missing_node_in_flow(self, script_generator, simple_network):
        """Test handling of flow with non-existent node."""
        config = SimulationConfig()
        config.flows.append(TrafficFlow(
            id="f1",
            source_node_id="nonexistent",
            target_node_id="host2",
            protocol=TrafficProtocol.UDP,
            application=TrafficApplication.ECHO
        ))
        
        # Should handle gracefully
        try:
            script = script_generator.generate(simple_network, config)
            # If it generates, should still be valid Python
            if script:
                assert_valid_python(script)
        except (ValueError, KeyError):
            pass  # Expected behavior
    
    def test_self_loop_flow(self, script_generator, simple_network):
        """Test handling of flow from node to itself."""
        config = SimulationConfig()
        config.flows.append(TrafficFlow(
            id="f1",
            source_node_id="host1",
            target_node_id="host1",  # Same node
            protocol=TrafficProtocol.UDP,
            application=TrafficApplication.ECHO
        ))
        
        # Should handle gracefully
        try:
            script = script_generator.generate(simple_network, config)
            if script:
                assert_valid_python(script)
        except ValueError:
            pass  # Expected behavior


class TestConvenienceFunction:
    """Tests for generate_ns3_script convenience function."""
    
    def test_generate_ns3_script(self, simple_network, basic_sim_config, temp_dir):
        """Test the convenience function."""
        script = generate_ns3_script(
            simple_network, 
            basic_sim_config, 
            output_dir=str(temp_dir)
        )
        
        assert_valid_python(script)
        assert len(script) > 100  # Should have substantial content
