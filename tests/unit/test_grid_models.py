"""
Unit tests for Grid-specific models (V2 extensions).

These tests extend the V1 test suite with grid-specific functionality.
The grid models use inheritance:
- GridNodeModel extends NodeModel
- GridLinkModel extends LinkModel
- GridTrafficFlow extends TrafficFlow

No factory functions needed - use constructors directly with __post_init__ 
handling all defaults based on type.
"""

import pytest

# Import V1 base models
from models import (
    NodeType, NodeModel, LinkModel, ChannelType, Position,
    TrafficFlow, TrafficProtocol, TrafficApplication,
    NetworkModel,
)

# Import V2 grid models (no factory functions - use classes directly)
from models import (
    # Grid Nodes (extends NodeModel)
    GridNodeType, GridNodeRole, GridProtocol, ScanClass, VoltageLevel,
    DNP3Config, IEC61850Config, GridNodeModel, SubstationModel,
    GRID_NODE_DEFAULTS,
    # Grid Links (extends LinkModel)
    GridLinkType, LinkReliabilityClass, LinkOwnership,
    WirelessParams, CellularParams, SatelliteParams, GridLinkModel,
    GRID_LINK_DEFAULTS,
    # Grid Traffic (extends TrafficFlow)
    GridTrafficClass, GridTrafficPriority, DNP3FunctionCode, DNP3ObjectGroup,
    DNP3MessageConfig, GOOSEMessageConfig, GridTrafficFlow, PollingSchedule,
    GRID_TRAFFIC_DEFAULTS, TRAFFIC_PATTERNS,
    # Failure Events
    FailureEventType, FailureEventState, FailureSeverity, FailureCategory,
    FailureEventParameters, FailureEvent, CascadingFailureRule, FailureScenario,
    SCENARIO_TEMPLATES, create_single_link_failure, create_node_power_loss,
    create_cascading_failure, create_network_partition,
    create_control_center_failover, create_dos_attack,
)


# ============================================================================
# Grid Node Tests
# ============================================================================

class TestGridNodeEnums:
    """Test grid node enumeration types."""
    
    def test_grid_node_type_values(self):
        assert GridNodeType.CONTROL_CENTER is not None
        assert GridNodeType.RTU is not None
        assert GridNodeType.IED is not None
    
    def test_grid_node_type_to_base(self):
        assert GridNodeType.CONTROL_CENTER.to_base_node_type() == NodeType.HOST
        assert GridNodeType.GATEWAY.to_base_node_type() == NodeType.ROUTER
        assert GridNodeType.COMM_SWITCH.to_base_node_type() == NodeType.SWITCH
    
    def test_scan_class_values(self):
        assert ScanClass.CLASS_1.value == 1
        assert ScanClass.CLASS_2.value == 2


class TestDNP3Config:
    """Test DNP3 configuration model."""
    
    def test_default_config(self):
        config = DNP3Config()
        assert config.enabled is True
        assert config.master_address == 1
    
    def test_custom_config(self):
        config = DNP3Config(slave_address=100)
        assert config.slave_address == 100


class TestGridNodeModel:
    """Test GridNodeModel which extends NodeModel."""
    
    def test_inheritance(self):
        """GridNodeModel should be subclass of NodeModel."""
        assert issubclass(GridNodeModel, NodeModel)
    
    def test_instance_check(self):
        """GridNodeModel instance should also be NodeModel."""
        node = GridNodeModel(grid_type=GridNodeType.RTU)
        assert isinstance(node, NodeModel)
        assert isinstance(node, GridNodeModel)
    
    def test_base_node_type_auto_set(self):
        """Base node_type should auto-set from grid_type."""
        node = GridNodeModel(grid_type=GridNodeType.CONTROL_CENTER)
        assert node.node_type == NodeType.HOST
        
        node = GridNodeModel(grid_type=GridNodeType.GATEWAY)
        assert node.node_type == NodeType.ROUTER
    
    def test_poll_interval_from_scan_class(self):
        node = GridNodeModel(grid_type=GridNodeType.RTU, scan_class=ScanClass.CLASS_1)
        assert node.poll_interval_effective_ms == 1000
    
    def test_auto_role_assignment(self):
        """Roles should auto-set based on grid_type."""
        cc = GridNodeModel(grid_type=GridNodeType.CONTROL_CENTER)
        assert cc.grid_role == GridNodeRole.MASTER
        
        rtu = GridNodeModel(grid_type=GridNodeType.RTU)
        assert rtu.grid_role == GridNodeRole.SLAVE
    
    def test_auto_scan_class_assignment(self):
        """Scan class should auto-set based on grid_type."""
        cc = GridNodeModel(grid_type=GridNodeType.CONTROL_CENTER)
        assert cc.scan_class == ScanClass.INTEGRITY
        
        ied = GridNodeModel(grid_type=GridNodeType.IED)
        assert ied.scan_class == ScanClass.CLASS_1
    
    def test_direct_instantiation(self):
        """Test creating nodes directly without factory."""
        # Control center - should get MASTER role, INTEGRITY scan
        cc = GridNodeModel(grid_type=GridNodeType.CONTROL_CENTER, name="EMS")
        assert cc.grid_type == GridNodeType.CONTROL_CENTER
        assert cc.node_type == NodeType.HOST
        assert cc.name == "EMS"
        assert cc.grid_role == GridNodeRole.MASTER
        assert cc.scan_class == ScanClass.INTEGRITY
        
        # RTU - should get SLAVE role, CLASS_2 scan
        rtu = GridNodeModel(grid_type=GridNodeType.RTU, substation_id="sub1")
        assert rtu.grid_type == GridNodeType.RTU
        assert rtu.substation_id == "sub1"
        assert rtu.grid_role == GridNodeRole.SLAVE
    
    def test_can_add_to_network_model(self):
        """GridNodeModel should work with NetworkModel."""
        network = NetworkModel()
        node = GridNodeModel(grid_type=GridNodeType.CONTROL_CENTER, name="CC1")
        network.nodes[node.id] = node
        assert node.id in network.nodes


class TestSubstationModel:
    """Test substation model."""
    
    def test_default_substation(self):
        sub = SubstationModel()
        assert sub.device_count == 0
    
    def test_add_device(self):
        sub = SubstationModel(name="Test Sub")
        rtu = GridNodeModel(grid_type=GridNodeType.RTU, name="RTU1")
        sub.add_device(rtu)
        assert rtu.id in sub.rtu_ids


# ============================================================================
# Grid Link Tests
# ============================================================================

class TestGridLinkEnums:
    """Test grid link enumeration types."""
    
    def test_grid_link_type_to_base(self):
        assert GridLinkType.FIBER.to_base_channel_type() == ChannelType.POINT_TO_POINT
        assert GridLinkType.ETHERNET_LAN.to_base_channel_type() == ChannelType.CSMA
    
    def test_ns3_helper(self):
        assert GridLinkType.FIBER.get_ns3_helper() == "PointToPointHelper"
        assert GridLinkType.CELLULAR_LTE.get_ns3_helper() == "LteHelper"


class TestGridLinkModel:
    """Test GridLinkModel which extends LinkModel."""
    
    def test_inheritance(self):
        """GridLinkModel should be subclass of LinkModel."""
        assert issubclass(GridLinkModel, LinkModel)
    
    def test_instance_check(self):
        """GridLinkModel instance should also be LinkModel."""
        link = GridLinkModel(
            grid_link_type=GridLinkType.FIBER,
            source_node_id="n1",
            target_node_id="n2",
        )
        assert isinstance(link, LinkModel)
        assert isinstance(link, GridLinkModel)
    
    def test_base_channel_type_auto_set(self):
        link = GridLinkModel(
            grid_link_type=GridLinkType.FIBER,
            source_node_id="n1",
            target_node_id="n2",
        )
        assert link.channel_type == ChannelType.POINT_TO_POINT
    
    def test_fiber_defaults(self):
        """Fiber should get appropriate defaults."""
        link = GridLinkModel(
            grid_link_type=GridLinkType.FIBER,
            source_node_id="n1",
            target_node_id="n2",
        )
        assert link.data_rate == "1Gbps"
    
    def test_satellite_params(self):
        """Satellite links should auto-create params."""
        link = GridLinkModel(
            grid_link_type=GridLinkType.SATELLITE_GEO,
            source_node_id="n1",
            target_node_id="n2",
        )
        assert link.satellite_params is not None
        assert link.is_high_latency is True
    
    def test_direct_instantiation(self):
        """Test creating links directly without factory."""
        link = GridLinkModel(
            grid_link_type=GridLinkType.FIBER,
            source_node_id="cc1",
            target_node_id="sub1",
            distance_km=50.0,
        )
        assert link.channel_type == ChannelType.POINT_TO_POINT
        assert link.distance_km == 50.0
        assert link.data_rate == "1Gbps"
    
    def test_create_backup_classmethod(self):
        """Test creating backup link via classmethod."""
        primary = GridLinkModel(
            grid_link_type=GridLinkType.FIBER,
            source_node_id="cc1",
            target_node_id="sub1",
        )
        backup = GridLinkModel.create_backup_for(primary, GridLinkType.SATELLITE_GEO)
        
        assert backup.is_backup_path is True
        assert backup.backup_for_link_id == primary.id
        assert backup.grid_link_type == GridLinkType.SATELLITE_GEO


# ============================================================================
# Grid Traffic Tests
# ============================================================================

class TestGridTrafficEnums:
    """Test grid traffic enumeration types."""
    
    def test_traffic_class_to_base(self):
        assert GridTrafficClass.SCADA_INTEGRITY_POLL.to_base_application() == TrafficApplication.ECHO
        assert GridTrafficClass.GOOSE.to_base_application() == TrafficApplication.ONOFF
    
    def test_priority_dscp(self):
        assert GridTrafficPriority.PROTECTION.dscp == 46
        assert GridTrafficPriority.BEST_EFFORT.dscp == 0


class TestGridTrafficFlow:
    """Test GridTrafficFlow which extends TrafficFlow."""
    
    def test_inheritance(self):
        """GridTrafficFlow should be subclass of TrafficFlow."""
        assert issubclass(GridTrafficFlow, TrafficFlow)
    
    def test_instance_check(self):
        """GridTrafficFlow instance should also be TrafficFlow."""
        flow = GridTrafficFlow(
            traffic_class=GridTrafficClass.SCADA_EXCEPTION_POLL,
            source_node_id="cc1",
            target_node_id="rtu1",
        )
        assert isinstance(flow, TrafficFlow)
        assert isinstance(flow, GridTrafficFlow)
    
    def test_base_application_auto_set(self):
        flow = GridTrafficFlow(
            traffic_class=GridTrafficClass.SCADA_EXCEPTION_POLL,
            source_node_id="cc1",
            target_node_id="rtu1",
        )
        assert flow.application == TrafficApplication.ECHO
    
    def test_goose_priority(self):
        """GOOSE traffic should get protection priority."""
        flow = GridTrafficFlow(
            traffic_class=GridTrafficClass.GOOSE,
            source_node_id="ied1",
            target_node_id="ied2",
        )
        assert flow.priority == GridTrafficPriority.PROTECTION
    
    def test_direct_instantiation(self):
        """Test creating traffic flows directly without factory."""
        flow = GridTrafficFlow(
            traffic_class=GridTrafficClass.SCADA_EXCEPTION_POLL,
            source_node_id="cc1",
            target_node_id="rtu1",
        )
        assert flow.source_node_id == "cc1"
        assert flow.target_node_id == "rtu1"
        assert flow.interval_ms == 4000  # Default for exception poll
        assert flow.port == 20000  # SCADA default port
    
    def test_auto_interval_from_class(self):
        """Interval should auto-set from traffic class."""
        # Exception poll: 4000ms
        flow = GridTrafficFlow(
            traffic_class=GridTrafficClass.SCADA_EXCEPTION_POLL,
            source_node_id="cc1",
            target_node_id="rtu1",
        )
        assert flow.interval_ms == 4000
        
        # Integrity poll: 60000ms
        flow = GridTrafficFlow(
            traffic_class=GridTrafficClass.SCADA_INTEGRITY_POLL,
            source_node_id="cc1",
            target_node_id="rtu1",
        )
        assert flow.interval_ms == 60000


class TestPollingSchedule:
    """Test polling schedule model."""
    
    def test_default_schedule(self):
        schedule = PollingSchedule(control_center_id="cc1")
        assert len(schedule.groups) == 3
    
    def test_generate_traffic_flows(self):
        schedule = PollingSchedule(control_center_id="cc1")
        schedule.add_device_to_group("rtu1", 0)
        flows = schedule.generate_traffic_flows()
        assert len(flows) == 1
        assert all(isinstance(f, GridTrafficFlow) for f in flows)


# ============================================================================
# Failure Event Tests
# ============================================================================

class TestFailureEvent:
    """Test failure event model."""
    
    def test_default_event(self):
        event = FailureEvent()
        assert event.event_type == FailureEventType.LINK_DOWN
    
    def test_event_with_duration(self):
        event = FailureEvent(trigger_time_s=10.0, duration_s=30.0)
        assert event.effective_recovery_time == 40.0


class TestFailureScenario:
    """Test failure scenario model."""
    
    def test_add_events_sorted(self):
        scenario = FailureScenario()
        scenario.add_event(FailureEvent(trigger_time_s=30.0))
        scenario.add_event(FailureEvent(trigger_time_s=10.0))
        times = [e.trigger_time_s for e in scenario.events]
        assert times == [10.0, 30.0]


class TestScenarioFactories:
    """Test scenario factory functions."""
    
    def test_create_single_link_failure(self):
        scenario = create_single_link_failure("link1", 15.0, 45.0)
        assert scenario.event_count == 1
    
    def test_create_cascading_failure(self):
        scenario = create_cascading_failure("link1", ["n1", "n2"], 10.0, 5.0)
        assert scenario.event_count == 3


# ============================================================================
# Integration Tests
# ============================================================================

class TestV1V2Integration:
    """Test that V2 models work correctly with V1 base classes."""
    
    def test_network_model_accepts_grid_nodes(self):
        """NetworkModel should accept GridNodeModel instances."""
        network = NetworkModel()
        cc = GridNodeModel(grid_type=GridNodeType.CONTROL_CENTER, name="CC1")
        rtu = GridNodeModel(grid_type=GridNodeType.RTU, name="RTU1")
        
        network.nodes[cc.id] = cc
        network.nodes[rtu.id] = rtu
        
        assert len(network.nodes) == 2
        # Grid-specific properties still accessible
        assert network.nodes[cc.id].grid_type == GridNodeType.CONTROL_CENTER
    
    def test_complete_grid_topology(self):
        """Test building complete topology with all V2 components."""
        # Create nodes directly
        cc = GridNodeModel(grid_type=GridNodeType.CONTROL_CENTER, name="CC1")
        rtu = GridNodeModel(grid_type=GridNodeType.RTU, name="RTU1")
        
        # Create link directly
        link = GridLinkModel(
            grid_link_type=GridLinkType.FIBER,
            source_node_id=cc.id,
            target_node_id=rtu.id,
        )
        
        # Create traffic directly
        flow = GridTrafficFlow(
            traffic_class=GridTrafficClass.SCADA_EXCEPTION_POLL,
            source_node_id=cc.id,
            target_node_id=rtu.id,
        )
        
        # Create failure (still uses factory - it's a different pattern)
        scenario = create_single_link_failure(link.id, 10.0)
        
        # Build network
        network = NetworkModel()
        network.nodes[cc.id] = cc
        network.nodes[rtu.id] = rtu
        network.links[link.id] = link
        
        # Verify
        assert scenario.events[0].target_id == link.id
        assert flow.source_node_id == cc.id
        assert link.source_node_id in network.nodes
