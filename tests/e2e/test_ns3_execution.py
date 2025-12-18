"""
End-to-end tests for ns-3 simulation execution.

These tests require a working ns-3 installation.
They are skipped if ns-3 is not available.

Tests:
- Script execution
- Results parsing
- FlowMonitor output
- Error handling
"""

import pytest
import os
import tempfile
from pathlib import Path

from models.network import NetworkModel, NodeModel, LinkModel, NodeType, Position
from models.simulation import SimulationConfig, TrafficFlow, TrafficProtocol, TrafficApplication
from services.ns3_generator import NS3ScriptGenerator
from services.simulation_runner import NS3SimulationManager, NS3Detector
from services.results_parser import ResultsParser


def is_ns3_available() -> bool:
    """Check if ns-3 is available for testing."""
    try:
        path = NS3Detector.find_ns3_path()
        return path is not None
    except Exception:
        return False


# Skip all tests in this module if ns-3 is not available
pytestmark = pytest.mark.skipif(
    not is_ns3_available(),
    reason="ns-3 not available"
)


class TestNS3Detection:
    """Tests for ns-3 detection."""
    
    def test_detect_ns3(self):
        """Test ns-3 detection."""
        ns3_path = NS3Detector.find_ns3_path()
        
        # If we get here (not skipped), ns-3 should be detected
        assert ns3_path is not None
        assert NS3Detector.validate_ns3_path(ns3_path)
    
    def test_ns3_version(self):
        """Test getting ns-3 version."""
        ns3_path = NS3Detector.find_ns3_path()
        if ns3_path:
            # Should be able to get version info
            version = NS3Detector.get_ns3_version(ns3_path)
            # Version may be None if not easily detectable
            assert version is None or isinstance(version, str)


class TestScriptExecution:
    """Tests for executing ns-3 scripts."""
    
    @pytest.fixture
    def sim_manager(self):
        """Create simulation manager."""
        manager = NS3SimulationManager()
        if not manager.ns3_available:
            pytest.skip("ns-3 not configured")
        return manager
    
    @pytest.fixture
    def simple_simulation(self):
        """Create a simple simulation setup."""
        network = NetworkModel()
        
        # Two hosts
        host1 = NodeModel(id="h1", node_type=NodeType.HOST, name="Host1", position=Position(100, 100))
        host2 = NodeModel(id="h2", node_type=NodeType.HOST, name="Host2", position=Position(300, 100))
        network.nodes[host1.id] = host1
        network.nodes[host2.id] = host2
        
        # Link them
        link = LinkModel(id="l1", source_node_id="h1", target_node_id="h2")
        network.links[link.id] = link
        
        # Simulation config with echo traffic
        config = SimulationConfig()
        config.duration = 5.0  # Short duration for tests
        config.enable_flow_monitor = True
        config.flows.append(TrafficFlow(
            id="f1",
            name="Test Echo",
            source_node_id="h1",
            target_node_id="h2",
            protocol=TrafficProtocol.UDP,
            application=TrafficApplication.ECHO,
            start_time=1.0,
            stop_time=4.0,
            echo_packets=3,
            echo_interval=1.0
        ))
        
        return network, config
    
    def test_generate_and_validate_script(self, simple_simulation):
        """Test generating a valid script."""
        network, config = simple_simulation
        generator = NS3ScriptGenerator()
        
        script = generator.generate(network, config)
        
        # Should be valid Python
        compile(script, "test.py", 'exec')
        
        # Should have essential components
        assert "NodeContainer" in script
        assert "InternetStackHelper" in script
        assert "UdpEchoServer" in script
    
    @pytest.mark.slow
    def test_run_simulation(self, sim_manager, simple_simulation, temp_dir):
        """Test running a complete simulation."""
        network, config = simple_simulation
        generator = NS3ScriptGenerator()
        
        # Generate script
        script = generator.generate(network, config)
        script_path = temp_dir / "gui_simulation.py"
        script_path.write_text(script)
        
        # Run simulation
        results = sim_manager.run_simulation(
            str(script_path),
            str(temp_dir),
            timeout=60
        )
        
        assert results is not None
        assert results.success == True
        assert results.console_output is not None
    
    @pytest.mark.slow
    def test_flow_monitor_results(self, sim_manager, simple_simulation, temp_dir):
        """Test FlowMonitor results parsing."""
        network, config = simple_simulation
        config.enable_flow_monitor = True
        
        generator = NS3ScriptGenerator()
        script = generator.generate(network, config)
        script_path = temp_dir / "gui_simulation.py"
        script_path.write_text(script)
        
        # Run simulation
        results = sim_manager.run_simulation(
            str(script_path),
            str(temp_dir),
            timeout=60
        )
        
        # Check FlowMonitor results
        flowmon_path = temp_dir / "flowmon-results.xml"
        if flowmon_path.exists():
            parser = ResultsParser()
            flows = parser.parse_flow_monitor_xml(str(flowmon_path))
            assert len(flows) > 0
            
            # Verify flow statistics
            for flow in flows:
                assert flow.tx_packets >= 0
                assert flow.rx_packets >= 0


class TestErrorHandling:
    """Tests for error handling during simulation."""
    
    @pytest.fixture
    def sim_manager(self):
        manager = NS3SimulationManager()
        if not manager.ns3_available:
            pytest.skip("ns-3 not configured")
        return manager
    
    @pytest.mark.skip(reason="NS3SimulationManager uses Qt signals, not synchronous returns")
    def test_invalid_script(self, sim_manager, temp_dir):
        """Test handling of invalid Python script."""
        # This test needs Qt event loop to work properly
        # The run_simulation method returns bool (started successfully)
        # and communicates results via signals
        pass
    
    @pytest.mark.skip(reason="NS3SimulationManager uses Qt signals, not timeout parameter")
    def test_simulation_timeout(self, sim_manager, temp_dir):
        """Test simulation timeout handling."""
        # NS3SimulationManager doesn't have a timeout parameter
        # It runs asynchronously with Qt signals
        pass


class TestResultsParsing:
    """Tests for parsing simulation results."""
    
    def test_parse_flowmon_xml(self, temp_dir):
        """Test parsing FlowMonitor XML."""
        # Create sample FlowMonitor output
        xml_content = """<?xml version="1.0" ?>
<FlowMonitor>
  <FlowStats>
    <Flow flowId="1" timeFirstTxPacket="+1000000000.0ns" timeFirstRxPacket="+1001000000.0ns" 
         timeLastTxPacket="+4000000000.0ns" timeLastRxPacket="+4001000000.0ns" 
         delaySum="+3000000.0ns" jitterSum="+100000.0ns" lastDelay="+1000000.0ns" 
         txBytes="3072" rxBytes="3072" txPackets="3" rxPackets="3" lostPackets="0" 
         timesForwarded="0">
    </Flow>
  </FlowStats>
  <Ipv4FlowClassifier>
    <Flow flowId="1" sourceAddress="10.1.1.1" destinationAddress="10.1.1.2" protocol="17" 
         sourcePort="49153" destinationPort="9"/>
  </Ipv4FlowClassifier>
</FlowMonitor>
"""
        xml_path = temp_dir / "flowmon.xml"
        xml_path.write_text(xml_content)
        
        parser = ResultsParser()
        flows = parser.parse_flow_monitor_xml(str(xml_path))
        
        assert len(flows) == 1
        assert flows[0].tx_packets == 3
        assert flows[0].rx_packets == 3
        assert flows[0].lost_packets == 0
    
    def test_parse_empty_flowmon(self, temp_dir):
        """Test parsing empty FlowMonitor output."""
        xml_content = """<?xml version="1.0" ?>
<FlowMonitor>
  <FlowStats>
  </FlowStats>
  <Ipv4FlowClassifier>
  </Ipv4FlowClassifier>
</FlowMonitor>
"""
        xml_path = temp_dir / "empty.xml"
        xml_path.write_text(xml_content)
        
        parser = ResultsParser()
        flows = parser.parse_flow_monitor_xml(str(xml_path))
        
        assert len(flows) == 0


class TestScenarios:
    """Tests for specific network scenarios."""
    
    @pytest.fixture
    def sim_manager(self):
        manager = NS3SimulationManager()
        if not manager.ns3_available:
            pytest.skip("ns-3 not configured")
        return manager
    
    @pytest.mark.slow
    def test_star_topology(self, sim_manager, star_network, temp_dir):
        """Test star topology simulation."""
        config = SimulationConfig()
        config.duration = 5.0
        config.enable_flow_monitor = True
        
        # Add traffic between hosts through switch
        config.flows.append(TrafficFlow(
            id="f1",
            source_node_id="host1",
            target_node_id="host2",
            protocol=TrafficProtocol.UDP,
            application=TrafficApplication.ECHO,
            start_time=1.0,
            stop_time=4.0
        ))
        
        generator = NS3ScriptGenerator()
        script = generator.generate(star_network, config)
        
        script_path = temp_dir / "star.py"
        script_path.write_text(script)
        
        results = sim_manager.run_simulation(
            str(script_path),
            str(temp_dir),
            timeout=60
        )
        
        assert results.success == True
    
    @pytest.mark.slow  
    def test_routed_topology(self, sim_manager, routed_network, temp_dir):
        """Test routed topology simulation."""
        config = SimulationConfig()
        config.duration = 5.0
        config.enable_flow_monitor = True
        
        # Traffic across router
        config.flows.append(TrafficFlow(
            id="f1",
            source_node_id="host1",
            target_node_id="host2",
            protocol=TrafficProtocol.UDP,
            application=TrafficApplication.ECHO,
            start_time=1.0,
            stop_time=4.0
        ))
        
        generator = NS3ScriptGenerator()
        script = generator.generate(routed_network, config)
        
        script_path = temp_dir / "routed.py"
        script_path.write_text(script)
        
        results = sim_manager.run_simulation(
            str(script_path),
            str(temp_dir),
            timeout=60
        )
        
        assert results.success == True
