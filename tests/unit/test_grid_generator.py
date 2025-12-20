"""
Unit tests for GridNS3Generator.

Tests the grid-specific ns-3 script generation including:
- Mixed channel type generation
- Failure injection code
- SCADA application generation
- Routing configuration
"""

import pytest

from models import (
    NetworkModel, SimulationConfig, NodeType, ChannelType,
    TrafficFlow, TrafficProtocol, TrafficApplication,
    GridNodeModel, GridNodeType, GridLinkModel, GridLinkType,
    GridTrafficFlow, GridTrafficClass, GridTrafficPriority,
    FailureScenario, FailureEvent, FailureEventType,
    create_single_link_failure, create_cascading_failure,
)

from services import GridNS3Generator


class TestGridNS3GeneratorBasic:
    """Test basic GridNS3Generator functionality."""
    
    def test_instantiation(self):
        """Test generator can be instantiated."""
        gen = GridNS3Generator()
        assert gen is not None
    
    def test_empty_network(self):
        """Test generation with empty network."""
        gen = GridNS3Generator()
        network = NetworkModel()
        sim_config = SimulationConfig(duration=10.0)
        
        script = gen.generate(network, sim_config)
        
        assert "NS-3 Grid SCADA Network Simulation Script" in script
        assert "def main():" in script
        assert "ns.Simulator.Run()" in script
    
    def test_header_includes_grid_info(self):
        """Test header includes grid-specific metadata."""
        gen = GridNS3Generator()
        network = NetworkModel()
        
        # Add grid nodes
        cc = GridNodeModel(grid_type=GridNodeType.CONTROL_CENTER, name="CC1")
        rtu = GridNodeModel(grid_type=GridNodeType.RTU, name="RTU1")
        network.nodes[cc.id] = cc
        network.nodes[rtu.id] = rtu
        
        sim_config = SimulationConfig(duration=10.0)
        script = gen.generate(network, sim_config)
        
        assert "Grid Extension" in script
        assert "2 grid nodes" in script


class TestGridLinkGeneration:
    """Test grid-specific link type code generation."""
    
    def test_fiber_link(self):
        """Test fiber link generates P2P code."""
        gen = GridNS3Generator()
        network = NetworkModel()
        
        cc = GridNodeModel(grid_type=GridNodeType.CONTROL_CENTER, name="CC")
        rtu = GridNodeModel(grid_type=GridNodeType.RTU, name="RTU")
        network.nodes[cc.id] = cc
        network.nodes[rtu.id] = rtu
        
        link = GridLinkModel(
            grid_link_type=GridLinkType.FIBER,
            source_node_id=cc.id,
            target_node_id=rtu.id,
        )
        network.links[link.id] = link
        
        script = gen.generate(network, SimulationConfig())
        
        assert "FIBER" in script
        assert "p2p.SetDeviceAttribute" in script
        assert "1Gbps" in script
    
    def test_satellite_link_high_delay(self):
        """Test satellite link includes high delay."""
        gen = GridNS3Generator()
        network = NetworkModel()
        
        cc = GridNodeModel(grid_type=GridNodeType.CONTROL_CENTER, name="CC")
        remote = GridNodeModel(grid_type=GridNodeType.RTU, name="Remote")
        network.nodes[cc.id] = cc
        network.nodes[remote.id] = remote
        
        link = GridLinkModel(
            grid_link_type=GridLinkType.SATELLITE_GEO,
            source_node_id=cc.id,
            target_node_id=remote.id,
        )
        network.links[link.id] = link
        
        script = gen.generate(network, SimulationConfig())
        
        assert "SATELLITE_GEO" in script
        assert "540ms" in script or "270" in script  # Round-trip or one-way
    
    def test_cellular_link(self):
        """Test cellular link generation."""
        gen = GridNS3Generator()
        network = NetworkModel()
        
        gw = GridNodeModel(grid_type=GridNodeType.CELLULAR_GATEWAY, name="GW")
        meter = GridNodeModel(grid_type=GridNodeType.METER, name="Meter")
        network.nodes[gw.id] = gw
        network.nodes[meter.id] = meter
        
        link = GridLinkModel(
            grid_link_type=GridLinkType.CELLULAR_LTE,
            source_node_id=gw.id,
            target_node_id=meter.id,
        )
        network.links[link.id] = link
        
        script = gen.generate(network, SimulationConfig())
        
        assert "CELLULAR_LTE" in script
    
    def test_error_model_generation(self):
        """Test error model generated for links with BER."""
        gen = GridNS3Generator()
        network = NetworkModel()
        
        cc = GridNodeModel(grid_type=GridNodeType.CONTROL_CENTER, name="CC")
        rtu = GridNodeModel(grid_type=GridNodeType.RTU, name="RTU")
        network.nodes[cc.id] = cc
        network.nodes[rtu.id] = rtu
        
        # Link with high BER
        link = GridLinkModel(
            grid_link_type=GridLinkType.LICENSED_RADIO,
            source_node_id=cc.id,
            target_node_id=rtu.id,
            bit_error_rate=1e-5,
        )
        network.links[link.id] = link
        
        script = gen.generate(network, SimulationConfig())
        
        assert "Error Model" in script or "RateErrorModel" in script


class TestSCADAApplicationGeneration:
    """Test SCADA traffic application code generation."""
    
    def test_polling_application(self):
        """Test SCADA polling traffic generation."""
        gen = GridNS3Generator()
        network = NetworkModel()
        
        cc = GridNodeModel(grid_type=GridNodeType.CONTROL_CENTER, name="CC")
        rtu = GridNodeModel(grid_type=GridNodeType.RTU, name="RTU")
        network.nodes[cc.id] = cc
        network.nodes[rtu.id] = rtu
        
        link = GridLinkModel(
            grid_link_type=GridLinkType.FIBER,
            source_node_id=cc.id,
            target_node_id=rtu.id,
        )
        network.links[link.id] = link
        
        # SCADA polling flow
        flow = GridTrafficFlow(
            traffic_class=GridTrafficClass.SCADA_EXCEPTION_POLL,
            source_node_id=cc.id,
            target_node_id=rtu.id,
        )
        
        sim_config = SimulationConfig(duration=60.0, flows=[flow])
        script = gen.generate(network, sim_config)
        
        assert "SCADA" in script
        assert "SCADA_EXCEPTION_POLL" in script
        assert "UdpEchoServer" in script or "echo_server" in script
    
    def test_goose_application(self):
        """Test GOOSE multicast traffic generation."""
        gen = GridNS3Generator()
        network = NetworkModel()
        
        ied1 = GridNodeModel(grid_type=GridNodeType.IED, name="IED1")
        ied2 = GridNodeModel(grid_type=GridNodeType.IED, name="IED2")
        network.nodes[ied1.id] = ied1
        network.nodes[ied2.id] = ied2
        
        link = GridLinkModel(
            grid_link_type=GridLinkType.ETHERNET_LAN,
            source_node_id=ied1.id,
            target_node_id=ied2.id,
        )
        network.links[link.id] = link
        
        # GOOSE flow
        flow = GridTrafficFlow(
            traffic_class=GridTrafficClass.GOOSE,
            source_node_id=ied1.id,
            target_node_id=ied2.id,
        )
        
        sim_config = SimulationConfig(duration=10.0, flows=[flow])
        script = gen.generate(network, sim_config)
        
        assert "GOOSE" in script
        assert "multicast" in script.lower() or "OnOff" in script
    
    def test_control_application(self):
        """Test control command traffic generation."""
        gen = GridNS3Generator()
        network = NetworkModel()
        
        cc = GridNodeModel(grid_type=GridNodeType.CONTROL_CENTER, name="CC")
        rtu = GridNodeModel(grid_type=GridNodeType.RTU, name="RTU")
        network.nodes[cc.id] = cc
        network.nodes[rtu.id] = rtu
        
        link = GridLinkModel(
            grid_link_type=GridLinkType.FIBER,
            source_node_id=cc.id,
            target_node_id=rtu.id,
        )
        network.links[link.id] = link
        
        # Control flow
        flow = GridTrafficFlow(
            traffic_class=GridTrafficClass.CONTROL_OPERATE,
            source_node_id=cc.id,
            target_node_id=rtu.id,
        )
        
        sim_config = SimulationConfig(duration=10.0, flows=[flow])
        script = gen.generate(network, sim_config)
        
        assert "CONTROL" in script or "Control" in script


class TestFailureInjection:
    """Test failure injection code generation."""
    
    def test_link_failure_injection(self):
        """Test link failure scheduled events."""
        gen = GridNS3Generator()
        network = NetworkModel()
        
        cc = GridNodeModel(grid_type=GridNodeType.CONTROL_CENTER, name="CC")
        rtu = GridNodeModel(grid_type=GridNodeType.RTU, name="RTU")
        network.nodes[cc.id] = cc
        network.nodes[rtu.id] = rtu
        
        link = GridLinkModel(
            grid_link_type=GridLinkType.FIBER,
            source_node_id=cc.id,
            target_node_id=rtu.id,
        )
        network.links[link.id] = link
        
        # Create failure scenario
        scenario = create_single_link_failure(
            link_id=link.id,
            trigger_time_s=5.0,
            duration_s=10.0,
        )
        
        sim_config = SimulationConfig(duration=30.0)
        script = gen.generate(network, sim_config, failure_scenario=scenario)
        
        assert "Failure Injection" in script
        assert "LINK_DOWN" in script or "failure_event" in script
        assert "Simulator.Schedule" in script
        assert "5.0" in script or "5" in script  # Trigger time
    
    def test_cascading_failure(self):
        """Test cascading failure scenario."""
        gen = GridNS3Generator()
        network = NetworkModel()
        
        cc = GridNodeModel(grid_type=GridNodeType.CONTROL_CENTER, name="CC")
        rtu1 = GridNodeModel(grid_type=GridNodeType.RTU, name="RTU1")
        rtu2 = GridNodeModel(grid_type=GridNodeType.RTU, name="RTU2")
        network.nodes[cc.id] = cc
        network.nodes[rtu1.id] = rtu1
        network.nodes[rtu2.id] = rtu2
        
        link1 = GridLinkModel(
            grid_link_type=GridLinkType.FIBER,
            source_node_id=cc.id,
            target_node_id=rtu1.id,
        )
        link2 = GridLinkModel(
            grid_link_type=GridLinkType.FIBER,
            source_node_id=cc.id,
            target_node_id=rtu2.id,
        )
        network.links[link1.id] = link1
        network.links[link2.id] = link2
        
        # Cascading failure
        scenario = create_cascading_failure(
            initial_link_id=link1.id,
            affected_node_ids=[rtu1.id, rtu2.id],
            trigger_time_s=10.0,
            cascade_delay_s=2.0,
        )
        
        sim_config = SimulationConfig(duration=60.0)
        script = gen.generate(network, sim_config, failure_scenario=scenario)
        
        assert "Failure Injection" in script
        assert scenario.event_count == 3
    
    def test_no_failure_scenario(self):
        """Test generation without failure scenario."""
        gen = GridNS3Generator()
        network = NetworkModel()
        
        cc = GridNodeModel(grid_type=GridNodeType.CONTROL_CENTER, name="CC")
        network.nodes[cc.id] = cc
        
        sim_config = SimulationConfig(duration=10.0)
        script = gen.generate(network, sim_config, failure_scenario=None)
        
        # Should not have failure injection section
        assert "Failure Injection Scenario" not in script or "Events: 0" in script


class TestRoutingGeneration:
    """Test routing configuration code generation."""
    
    def test_global_routing_default(self):
        """Test global routing is used by default."""
        gen = GridNS3Generator()
        network = NetworkModel()
        
        cc = GridNodeModel(grid_type=GridNodeType.CONTROL_CENTER, name="CC")
        rtu = GridNodeModel(grid_type=GridNodeType.RTU, name="RTU")
        network.nodes[cc.id] = cc
        network.nodes[rtu.id] = rtu
        
        link = GridLinkModel(
            grid_link_type=GridLinkType.FIBER,
            source_node_id=cc.id,
            target_node_id=rtu.id,
        )
        network.links[link.id] = link
        
        script = gen.generate(network, SimulationConfig())
        
        assert "PopulateRoutingTables" in script or "global routing" in script.lower()


class TestMixedTopology:
    """Test generation with mixed grid and standard components."""
    
    def test_mixed_node_types(self):
        """Test network with both GridNodeModel and NodeModel."""
        from models import NodeModel
        
        gen = GridNS3Generator()
        network = NetworkModel()
        
        # Grid node
        cc = GridNodeModel(grid_type=GridNodeType.CONTROL_CENTER, name="CC")
        network.nodes[cc.id] = cc
        
        # Standard node
        host = NodeModel(node_type=NodeType.HOST, name="Host")
        network.nodes[host.id] = host
        
        # Standard link between them
        from models import LinkModel
        link = LinkModel(
            source_node_id=cc.id,
            target_node_id=host.id,
        )
        network.links[link.id] = link
        
        script = gen.generate(network, SimulationConfig())
        
        assert "CC" in script
        assert "Host" in script
        assert "nodes.Create(2)" in script
    
    def test_mixed_traffic_flows(self):
        """Test with both GridTrafficFlow and standard TrafficFlow."""
        gen = GridNS3Generator()
        network = NetworkModel()
        
        cc = GridNodeModel(grid_type=GridNodeType.CONTROL_CENTER, name="CC")
        rtu = GridNodeModel(grid_type=GridNodeType.RTU, name="RTU")
        network.nodes[cc.id] = cc
        network.nodes[rtu.id] = rtu
        
        link = GridLinkModel(
            grid_link_type=GridLinkType.FIBER,
            source_node_id=cc.id,
            target_node_id=rtu.id,
        )
        network.links[link.id] = link
        
        # Grid traffic
        grid_flow = GridTrafficFlow(
            traffic_class=GridTrafficClass.SCADA_EXCEPTION_POLL,
            source_node_id=cc.id,
            target_node_id=rtu.id,
        )
        
        # Standard traffic
        std_flow = TrafficFlow(
            source_node_id=rtu.id,
            target_node_id=cc.id,
            application=TrafficApplication.ECHO,
        )
        
        sim_config = SimulationConfig(duration=30.0, flows=[grid_flow, std_flow])
        script = gen.generate(network, sim_config)
        
        assert "SCADA" in script
        assert "echo" in script.lower() or "Echo" in script


class TestCompleteGridSimulation:
    """Integration tests for complete grid simulation scripts."""
    
    def test_complete_scada_network(self):
        """Test complete SCADA network simulation generation."""
        gen = GridNS3Generator()
        network = NetworkModel()
        
        # Control center
        cc = GridNodeModel(grid_type=GridNodeType.CONTROL_CENTER, name="EMS")
        network.nodes[cc.id] = cc
        
        # Multiple RTUs
        rtus = []
        for i in range(3):
            rtu = GridNodeModel(
                grid_type=GridNodeType.RTU,
                name=f"RTU_{i+1}",
                substation_id=f"sub_{i+1}",
            )
            network.nodes[rtu.id] = rtu
            rtus.append(rtu)
            
            # Link to CC
            link = GridLinkModel(
                grid_link_type=GridLinkType.FIBER,
                source_node_id=cc.id,
                target_node_id=rtu.id,
            )
            network.links[link.id] = link
        
        # Polling flows to each RTU
        flows = []
        for rtu in rtus:
            flow = GridTrafficFlow(
                traffic_class=GridTrafficClass.SCADA_EXCEPTION_POLL,
                source_node_id=cc.id,
                target_node_id=rtu.id,
            )
            flows.append(flow)
        
        sim_config = SimulationConfig(duration=60.0, flows=flows)
        script = gen.generate(network, sim_config)
        
        # Verify complete script
        assert "#!/usr/bin/env python3" in script
        assert "from ns import ns" in script
        assert "def main():" in script
        assert "nodes.Create(4)" in script
        assert "EMS" in script
        assert "RTU_1" in script
        assert "ns.Simulator.Run()" in script
        assert "ns.Simulator.Destroy()" in script
    
    def test_script_has_valid_python_structure(self):
        """Test generated script has valid Python structure."""
        gen = GridNS3Generator()
        network = NetworkModel()
        
        cc = GridNodeModel(grid_type=GridNodeType.CONTROL_CENTER, name="CC")
        rtu = GridNodeModel(grid_type=GridNodeType.RTU, name="RTU")
        network.nodes[cc.id] = cc
        network.nodes[rtu.id] = rtu
        
        link = GridLinkModel(
            grid_link_type=GridLinkType.FIBER,
            source_node_id=cc.id,
            target_node_id=rtu.id,
        )
        network.links[link.id] = link
        
        script = gen.generate(network, SimulationConfig())
        
        # Basic structure checks
        assert script.count("def main():") == 1
        assert "if __name__" in script
        
        # Verify script is syntactically valid Python
        import ast
        try:
            ast.parse(script)
        except SyntaxError as e:
            pytest.fail(f"Generated script has syntax error: {e}")
