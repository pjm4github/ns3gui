"""
Grid-specific NS-3 Python script generator.

Extends NS3ScriptGenerator to support:
- Mixed channel type generation (Fiber→P2P, LAN→CSMA, Cellular→LTE, etc.)
- Failure injection code using Simulator::Schedule
- SCADA application generation (DNP3-like polling traffic)
- Advanced routing configuration (Static/OLSR/RIP/AODV)
"""

from datetime import datetime
from typing import Optional, Dict, Set, Tuple, List, Any, Union

from models import (
    NetworkModel, NodeModel, LinkModel, NodeType, ChannelType,
    SimulationConfig, TrafficFlow, TrafficApplication, TrafficProtocol,
    RoutingMode,
)

# Import V2 grid models
from models import (
    GridNodeModel, GridNodeType, GridNodeRole, GridProtocol, ScanClass,
    GridLinkModel, GridLinkType, LinkReliabilityClass,
    GridTrafficFlow, GridTrafficClass, GridTrafficPriority,
    DNP3MessageConfig, GOOSEMessageConfig,
    FailureScenario, FailureEvent, FailureEventType, FailureEventState,
)

# Handle both package and standalone import
try:
    from .ns3_generator import NS3ScriptGenerator
except ImportError:
    # Direct file import for standalone use
    import importlib.util
    import os
    _dir = os.path.dirname(os.path.abspath(__file__))
    _spec = importlib.util.spec_from_file_location("ns3_generator", os.path.join(_dir, "ns3_generator.py"))
    _ns3_gen = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_ns3_gen)
    NS3ScriptGenerator = _ns3_gen.NS3ScriptGenerator


class GridNS3Generator(NS3ScriptGenerator):
    """
    Generates ns-3 Python scripts for grid SCADA network simulations.
    
    Extends the base NS3ScriptGenerator with:
    - Grid-specific link types (fiber, microwave, cellular, satellite)
    - SCADA traffic generation (polling, control, GOOSE)
    - Failure injection scenarios
    - Advanced routing protocols
    
    Usage:
        generator = GridNS3Generator()
        script = generator.generate(network, sim_config, failure_scenario)
    """
    
    def __init__(self):
        super().__init__()
        self._failure_scenario: Optional[FailureScenario] = None
        self._grid_link_map: Dict[str, GridLinkModel] = {}
        self._grid_node_map: Dict[str, GridNodeModel] = {}
        self._grid_traffic_map: Dict[str, GridTrafficFlow] = {}
    
    def generate(
        self,
        network: NetworkModel,
        sim_config: SimulationConfig,
        output_dir: str = ".",
        failure_scenario: Optional[FailureScenario] = None,
    ) -> str:
        """
        Generate complete ns-3 Python script with grid extensions.
        
        Args:
            network: The network topology model (may contain GridNodeModel/GridLinkModel)
            sim_config: Simulation configuration with flows (may contain GridTrafficFlow)
            output_dir: Directory for output files
            failure_scenario: Optional failure injection scenario
            
        Returns:
            Complete Python script as string
        """
        self._failure_scenario = failure_scenario
        
        # Build maps of grid-specific models for easy lookup
        self._grid_node_map = {
            node_id: node for node_id, node in network.nodes.items()
            if isinstance(node, GridNodeModel)
        }
        self._grid_link_map = {
            link_id: link for link_id, link in network.links.items()
            if isinstance(link, GridLinkModel)
        }
        self._grid_traffic_map = {
            flow.id: flow for flow in sim_config.flows
            if isinstance(flow, GridTrafficFlow)
        }
        
        # Call parent generate with extended sections
        output_dir = output_dir.replace('\\', '/')
        
        # Build node index mapping
        real_nodes = list(network.nodes.items())
        self._node_index_map = {
            node_id: idx for idx, (node_id, node) in enumerate(real_nodes)
        }
        
        # Initialize tracking
        self._link_device_map = {}
        self._wifi_link_ids = set()
        self._wired_device_count = 0
        self._wifi_sta_devices_var = None
        self._wifi_sta_count = 0
        self._wifi_ap_devices_var = None
        self._wifi_ap_count = 0
        
        sections = [
            self._generate_header(network, sim_config),
            self._generate_imports(has_app_flows=False),
            self._generate_main_function_start(),
            self._generate_nodes(network),
            self._generate_grid_channels(network),  # Extended version
            self._generate_internet_stack(network),
            self._generate_ip_addresses(network),
            self._generate_grid_routing(network),  # Extended version
            self._generate_grid_applications(network, sim_config),  # Extended version
            self._generate_failure_injection(),  # NEW: failure scenarios
            self._generate_tracing(sim_config, output_dir),
            self._generate_simulation_run(sim_config, output_dir),
            self._generate_main_function_end(),
            self._generate_main_call(),
        ]
        
        return "\n".join(sections)
    
    def _generate_header(self, network: NetworkModel, sim_config: SimulationConfig) -> str:
        """Generate script header with grid-specific metadata."""
        # Count grid-specific components
        grid_nodes = len(self._grid_node_map)
        grid_links = len(self._grid_link_map)
        grid_flows = len(self._grid_traffic_map)
        
        failure_info = ""
        if self._failure_scenario:
            failure_info = f"""
Failure Scenario: {self._failure_scenario.name}
  - Events: {self._failure_scenario.event_count}
  - Duration: {self._failure_scenario.duration_s:.1f}s"""
        
        return f'''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NS-3 Grid SCADA Network Simulation Script
Generated by ns3-gui (Grid Extension) on {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

Topology:
  - Total Nodes: {len(network.nodes)} ({grid_nodes} grid nodes)
  - Total Links: {len(network.links)} ({grid_links} grid links)
  - Traffic Flows: {len(sim_config.flows)} ({grid_flows} SCADA flows)
{failure_info}
Simulation Duration: {sim_config.duration} seconds
"""
'''
    
    def _generate_grid_channels(self, network: NetworkModel) -> str:
        """
        Generate channel configuration with grid-specific link types.
        
        Handles:
        - GridLinkType.FIBER → PointToPointHelper (1Gbps, low delay)
        - GridLinkType.MICROWAVE → PointToPointHelper (with wireless params)
        - GridLinkType.CELLULAR_LTE → LTE helpers
        - GridLinkType.SATELLITE_GEO → PointToPointHelper (high delay)
        - Standard LinkModel → parent behavior
        """
        lines = [
            "    # ============================================",
            "    # Create Links/Channels (Grid Network)",
            "    # ============================================",
            "",
            "    # Helpers for different link types",
            "    p2p = ns.PointToPointHelper()",
            "    csma = ns.CsmaHelper()",
            "",
            "    # Store all NetDeviceContainers",
            "    all_devices = []",
            "",
        ]
        
        # Track error models to configure
        error_model_links: List[Tuple[int, GridLinkModel]] = []
        
        device_idx = 0
        
        for link_id, link in network.links.items():
            source_idx = self._node_index_map.get(link.source_node_id, 0)
            target_idx = self._node_index_map.get(link.target_node_id, 0)
            
            source_node = network.nodes.get(link.source_node_id)
            target_node = network.nodes.get(link.target_node_id)
            source_name = source_node.name if source_node else "unknown"
            target_name = target_node.name if target_node else "unknown"
            
            # Store mapping
            self._link_device_map[link_id] = device_idx
            
            # Check if this is a GridLinkModel
            if isinstance(link, GridLinkModel):
                lines.extend(self._generate_grid_link(
                    device_idx, link, source_idx, target_idx, source_name, target_name
                ))
                
                # Track if we need error model
                if link.bit_error_rate > 0:
                    error_model_links.append((device_idx, link))
            else:
                # Standard link - use parent logic
                lines.extend(self._generate_standard_link(
                    device_idx, link, source_idx, target_idx, source_name, target_name, network
                ))
            
            device_idx += 1
        
        self._wired_device_count = device_idx
        
        # Generate error models if needed
        if error_model_links:
            lines.append("")
            lines.append("    # ----------------------------------------")
            lines.append("    # Configure Error Models")
            lines.append("    # ----------------------------------------")
            for dev_idx, grid_link in error_model_links:
                lines.extend(self._generate_error_model(dev_idx, grid_link))
        
        lines.append("")
        return "\n".join(lines)
    
    def _generate_grid_link(
        self,
        device_idx: int,
        link: GridLinkModel,
        source_idx: int,
        target_idx: int,
        source_name: str,
        target_name: str,
    ) -> List[str]:
        """Generate ns-3 code for a grid-specific link type."""
        lines = []
        link_type = link.grid_link_type
        
        # Add comment with grid link info
        lines.append(f"    # Link {device_idx}: {source_name} <-> {target_name}")
        lines.append(f"    # Type: {link_type.name}, Data Rate: {link.data_rate}, Delay: {link.delay}")
        
        if link_type in (GridLinkType.FIBER, GridLinkType.COPPER_SERIAL,
                         GridLinkType.MICROWAVE, GridLinkType.LICENSED_RADIO,
                         GridLinkType.SPREAD_SPECTRUM):
            # Point-to-point links
            lines.extend([
                f"    p2p.SetDeviceAttribute('DataRate', ns.StringValue('{link.data_rate}'))",
                f"    p2p.SetChannelAttribute('Delay', ns.StringValue('{link.delay}'))",
                f"    link{device_idx}_nodes = ns.NodeContainer()",
                f"    link{device_idx}_nodes.Add(nodes.Get({source_idx}))",
                f"    link{device_idx}_nodes.Add(nodes.Get({target_idx}))",
                f"    devices{device_idx} = p2p.Install(link{device_idx}_nodes)",
                f"    all_devices.append(devices{device_idx})",
                "",
            ])
        
        elif link_type == GridLinkType.ETHERNET_LAN:
            # CSMA for LAN segments
            lines.extend([
                f"    csma.SetChannelAttribute('DataRate', ns.StringValue('{link.data_rate}'))",
                f"    csma.SetChannelAttribute('Delay', ns.StringValue('{link.delay}'))",
                f"    link{device_idx}_nodes = ns.NodeContainer()",
                f"    link{device_idx}_nodes.Add(nodes.Get({source_idx}))",
                f"    link{device_idx}_nodes.Add(nodes.Get({target_idx}))",
                f"    devices{device_idx} = csma.Install(link{device_idx}_nodes)",
                f"    all_devices.append(devices{device_idx})",
                "",
            ])
        
        elif link_type in (GridLinkType.SATELLITE_GEO, GridLinkType.SATELLITE_LEO):
            # Satellite links - P2P with high delay
            delay = link.delay
            if link.satellite_params:
                delay = f"{link.satellite_params.one_way_delay_ms * 2}ms"
            
            lines.extend([
                f"    # Satellite link ({link_type.name})",
                f"    p2p.SetDeviceAttribute('DataRate', ns.StringValue('{link.data_rate}'))",
                f"    p2p.SetChannelAttribute('Delay', ns.StringValue('{delay}'))",
                f"    link{device_idx}_nodes = ns.NodeContainer()",
                f"    link{device_idx}_nodes.Add(nodes.Get({source_idx}))",
                f"    link{device_idx}_nodes.Add(nodes.Get({target_idx}))",
                f"    devices{device_idx} = p2p.Install(link{device_idx}_nodes)",
                f"    all_devices.append(devices{device_idx})",
                "",
            ])
        
        elif link_type in (GridLinkType.CELLULAR_LTE, GridLinkType.CELLULAR_5G,
                           GridLinkType.PRIVATE_LTE):
            # LTE/Cellular links
            # Note: Full LTE requires complex setup; this is a simplified P2P approximation
            lines.extend([
                f"    # Cellular link ({link_type.name}) - simplified P2P model",
                f"    # For full LTE simulation, use LteHelper with EPC",
                f"    p2p.SetDeviceAttribute('DataRate', ns.StringValue('{link.data_rate}'))",
                f"    p2p.SetChannelAttribute('Delay', ns.StringValue('{link.delay}'))",
                f"    link{device_idx}_nodes = ns.NodeContainer()",
                f"    link{device_idx}_nodes.Add(nodes.Get({source_idx}))",
                f"    link{device_idx}_nodes.Add(nodes.Get({target_idx}))",
                f"    devices{device_idx} = p2p.Install(link{device_idx}_nodes)",
                f"    all_devices.append(devices{device_idx})",
                "",
            ])
        
        else:
            # Default to P2P for unknown types
            lines.extend([
                f"    # {link_type.name} link (using P2P model)",
                f"    p2p.SetDeviceAttribute('DataRate', ns.StringValue('{link.data_rate}'))",
                f"    p2p.SetChannelAttribute('Delay', ns.StringValue('{link.delay}'))",
                f"    link{device_idx}_nodes = ns.NodeContainer()",
                f"    link{device_idx}_nodes.Add(nodes.Get({source_idx}))",
                f"    link{device_idx}_nodes.Add(nodes.Get({target_idx}))",
                f"    devices{device_idx} = p2p.Install(link{device_idx}_nodes)",
                f"    all_devices.append(devices{device_idx})",
                "",
            ])
        
        return lines
    
    def _generate_standard_link(
        self,
        device_idx: int,
        link: LinkModel,
        source_idx: int,
        target_idx: int,
        source_name: str,
        target_name: str,
        network: NetworkModel,
    ) -> List[str]:
        """Generate ns-3 code for a standard (non-grid) link."""
        lines = []
        
        source_node = network.nodes.get(link.source_node_id)
        target_node = network.nodes.get(link.target_node_id)
        
        source_is_switch = source_node and source_node.node_type == NodeType.SWITCH
        target_is_switch = target_node and target_node.node_type == NodeType.SWITCH
        use_csma = source_is_switch or target_is_switch or link.channel_type == ChannelType.CSMA
        
        lines.append(f"    # Link {device_idx}: {source_name} <-> {target_name}")
        
        if use_csma:
            lines.extend([
                f"    csma.SetChannelAttribute('DataRate', ns.StringValue('{link.data_rate}'))",
                f"    csma.SetChannelAttribute('Delay', ns.StringValue('{link.delay}'))",
                f"    link{device_idx}_nodes = ns.NodeContainer()",
                f"    link{device_idx}_nodes.Add(nodes.Get({source_idx}))",
                f"    link{device_idx}_nodes.Add(nodes.Get({target_idx}))",
                f"    devices{device_idx} = csma.Install(link{device_idx}_nodes)",
                f"    all_devices.append(devices{device_idx})",
                "",
            ])
        else:
            lines.extend([
                f"    p2p.SetDeviceAttribute('DataRate', ns.StringValue('{link.data_rate}'))",
                f"    p2p.SetChannelAttribute('Delay', ns.StringValue('{link.delay}'))",
                f"    link{device_idx}_nodes = ns.NodeContainer()",
                f"    link{device_idx}_nodes.Add(nodes.Get({source_idx}))",
                f"    link{device_idx}_nodes.Add(nodes.Get({target_idx}))",
                f"    devices{device_idx} = p2p.Install(link{device_idx}_nodes)",
                f"    all_devices.append(devices{device_idx})",
                "",
            ])
        
        return lines
    
    def _generate_error_model(self, device_idx: int, link: GridLinkModel) -> List[str]:
        """Generate error model configuration for a link."""
        lines = []
        
        config = link.get_error_model_config()
        if not config:
            return lines
        
        model_type = config["model_type"]
        params = config["parameters"]
        
        lines.append(f"    # Error model for link {device_idx} (BER: {link.bit_error_rate})")
        
        if model_type == "RateErrorModel":
            lines.extend([
                f"    error_model_{device_idx} = ns.CreateObject[ns.RateErrorModel]()",
                f"    error_model_{device_idx}.SetAttribute('ErrorRate', ns.DoubleValue({params['ErrorRate']}))",
                f"    # Note: ErrorUnit defaults to ERROR_UNIT_BIT",
                f"    devices{device_idx}.Get(0).SetAttribute('ReceiveErrorModel', ns.PointerValue(error_model_{device_idx}))",
                f"    devices{device_idx}.Get(1).SetAttribute('ReceiveErrorModel', ns.PointerValue(error_model_{device_idx}))",
                "",
            ])
        elif model_type == "BurstErrorModel":
            lines.extend([
                f"    error_model_{device_idx} = ns.CreateObject[ns.BurstErrorModel]()",
                f"    error_model_{device_idx}.SetAttribute('ErrorRate', ns.DoubleValue({params['ErrorRate']}))",
                f"    devices{device_idx}.Get(0).SetAttribute('ReceiveErrorModel', ns.PointerValue(error_model_{device_idx}))",
                f"    devices{device_idx}.Get(1).SetAttribute('ReceiveErrorModel', ns.PointerValue(error_model_{device_idx}))",
                "",
            ])
        
        return lines
    
    def _generate_grid_routing(self, network: NetworkModel) -> str:
        """
        Generate routing configuration with support for multiple protocols.
        
        Supports:
        - Static routing (manual routes)
        - Global routing (shortest path)
        - OLSR (Optimized Link State Routing)
        - AODV (Ad-hoc On-Demand Distance Vector)
        - RIP (Routing Information Protocol)
        """
        lines = [
            "    # ============================================",
            "    # Configure Routing (Grid Network)",
            "    # ============================================",
            "",
        ]
        
        # Analyze routing requirements
        routing_protocols_needed: Set[str] = set()
        nodes_with_manual = []
        
        for node_id, node in network.nodes.items():
            if isinstance(node, GridNodeModel):
                # Grid nodes might specify routing via their grid_type
                pass
            
            if hasattr(node, 'routing_mode') and node.routing_mode == RoutingMode.MANUAL:
                if node.routing_table:
                    nodes_with_manual.append((node_id, node))
            
            if hasattr(node, 'routing_protocol'):
                routing_protocols_needed.add(node.routing_protocol.lower())
        
        # Generate OLSR setup if needed
        if 'olsr' in routing_protocols_needed:
            lines.extend(self._generate_olsr_routing(network))
        
        # Generate AODV setup if needed
        if 'aodv' in routing_protocols_needed:
            lines.extend(self._generate_aodv_routing(network))
        
        # Generate RIP setup if needed
        if 'rip' in routing_protocols_needed:
            lines.extend(self._generate_rip_routing(network))
        
        # Generate manual static routes
        if nodes_with_manual:
            lines.extend(self._generate_static_routes(nodes_with_manual))
        
        # Default: use global routing if no specific protocol
        if not routing_protocols_needed or 'static' in routing_protocols_needed:
            lines.extend([
                "    # Enable global routing (automatic shortest path computation)",
                "    ns.Ipv4GlobalRoutingHelper.PopulateRoutingTables()",
                "    print('Routing tables populated via global routing')",
                "",
            ])
        
        return "\n".join(lines)
    
    def _generate_olsr_routing(self, network: NetworkModel) -> List[str]:
        """Generate OLSR routing configuration."""
        lines = [
            "    # ----------------------------------------",
            "    # OLSR Routing Protocol Setup",
            "    # ----------------------------------------",
            "    olsr = ns.OlsrHelper()",
            "",
            "    # Find nodes that use OLSR",
            "    olsr_nodes = ns.NodeContainer()",
        ]
        
        for node_id, node in network.nodes.items():
            if hasattr(node, 'routing_protocol') and node.routing_protocol.lower() == 'olsr':
                node_idx = self._node_index_map.get(node_id, 0)
                lines.append(f"    olsr_nodes.Add(nodes.Get({node_idx}))  # {node.name}")
        
        lines.extend([
            "",
            "    # Install OLSR on selected nodes",
            "    olsr_list = olsr.Install(olsr_nodes)",
            "",
            "    # For nodes not using OLSR, use static routing",
            "    static_routing = ns.Ipv4StaticRoutingHelper()",
            "    list_routing = ns.Ipv4ListRoutingHelper()",
            "    list_routing.Add(static_routing, 0)",
            "    list_routing.Add(olsr, 10)",
            "",
        ])
        
        return lines
    
    def _generate_aodv_routing(self, network: NetworkModel) -> List[str]:
        """Generate AODV routing configuration."""
        lines = [
            "    # ----------------------------------------",
            "    # AODV Routing Protocol Setup",
            "    # ----------------------------------------",
            "    aodv = ns.AodvHelper()",
            "",
            "    # Find nodes that use AODV",
            "    aodv_nodes = ns.NodeContainer()",
        ]
        
        for node_id, node in network.nodes.items():
            if hasattr(node, 'routing_protocol') and node.routing_protocol.lower() == 'aodv':
                node_idx = self._node_index_map.get(node_id, 0)
                lines.append(f"    aodv_nodes.Add(nodes.Get({node_idx}))  # {node.name}")
        
        lines.extend([
            "",
            "    # Install AODV on selected nodes",
            "    # Note: AODV is typically used with InternetStackHelper",
            "    # stack.SetRoutingHelper(aodv)",
            "",
        ])
        
        return lines
    
    def _generate_rip_routing(self, network: NetworkModel) -> List[str]:
        """Generate RIP routing configuration."""
        lines = [
            "    # ----------------------------------------",
            "    # RIP Routing Protocol Setup",
            "    # ----------------------------------------",
            "    rip = ns.RipHelper()",
            "    # Note: SplitHorizon enabled by default",
            "",
        ]
        
        return lines
    
    def _generate_static_routes(self, nodes_with_manual: List[Tuple[str, NodeModel]]) -> List[str]:
        """Generate static route configuration for nodes with manual routing."""
        lines = [
            "    # ----------------------------------------",
            "    # Static Route Configuration",
            "    # ----------------------------------------",
            "",
        ]
        
        for node_id, node in nodes_with_manual:
            node_idx = self._node_index_map.get(node_id, 0)
            
            lines.extend([
                f"    # Static routes for {node.name}",
                f"    ipv4_{node_idx} = nodes.Get({node_idx}).GetObject[ns.Ipv4]()",
                f"    static_{node_idx} = ns.Ipv4StaticRouting.GetRouting(ipv4_{node_idx})",
                "",
            ])
            
            for route in node.routing_table:
                if not route.enabled:
                    continue
                
                if route.is_default_route:
                    lines.append(
                        f"    static_{node_idx}.SetDefaultRoute("
                        f"ns.Ipv4Address('{route.gateway}'), {route.interface})"
                    )
                else:
                    if route.is_direct:
                        lines.append(
                            f"    static_{node_idx}.AddNetworkRouteTo("
                            f"ns.Ipv4Address('{route.destination}'), "
                            f"ns.Ipv4Mask('{route.netmask}'), {route.interface})"
                        )
                    else:
                        lines.append(
                            f"    static_{node_idx}.AddNetworkRouteTo("
                            f"ns.Ipv4Address('{route.destination}'), "
                            f"ns.Ipv4Mask('{route.netmask}'), "
                            f"ns.Ipv4Address('{route.gateway}'), {route.interface})"
                        )
            
            lines.append("")
        
        return lines
    
    def _generate_grid_applications(
        self,
        network: NetworkModel,
        sim_config: SimulationConfig,
    ) -> str:
        """
        Generate traffic applications with grid-specific SCADA traffic.
        
        Handles:
        - GridTrafficFlow → SCADA polling applications
        - GOOSE multicast traffic
        - Standard TrafficFlow → parent behavior
        """
        lines = [
            "    # ============================================",
            "    # Create Applications (SCADA Traffic)",
            "    # ============================================",
            "",
            "    # List for receiver poll functions (not used with standard ns-3 apps)",
            "    _receiver_poll_functions = []",
            "",
        ]
        
        if not sim_config.flows:
            lines.extend([
                "    # No traffic flows configured",
                "",
            ])
            return "\n".join(lines)
        
        for flow_idx, flow in enumerate(sim_config.flows):
            source_idx = self._node_index_map.get(flow.source_node_id)
            target_idx = self._node_index_map.get(flow.target_node_id)
            
            if source_idx is None or target_idx is None:
                lines.append(f"    # Flow {flow_idx}: SKIPPED - invalid node reference")
                continue
            
            source_node = network.nodes.get(flow.source_node_id)
            target_node = network.nodes.get(flow.target_node_id)
            source_name = source_node.name if source_node else "unknown"
            target_name = target_node.name if target_node else "unknown"
            
            if isinstance(flow, GridTrafficFlow):
                # Grid-specific SCADA traffic
                lines.extend(self._generate_scada_application(
                    flow_idx, flow, source_idx, target_idx, source_name, target_name, network
                ))
            else:
                # Standard traffic - delegate to parent
                lines.append(f"    # Flow {flow_idx}: {flow.name} ({source_name} -> {target_name})")
                if flow.application == TrafficApplication.ECHO:
                    lines.extend(self._generate_echo_app_simple(
                        flow_idx, flow, source_idx, target_idx, network
                    ))
                elif flow.application == TrafficApplication.ONOFF:
                    lines.extend(self._generate_onoff_app_simple(
                        flow_idx, flow, source_idx, target_idx, network
                    ))
                else:
                    lines.append(f"    # TODO: {flow.application.value} not implemented")
                lines.append("")
        
        return "\n".join(lines)
    
    def _generate_scada_application(
        self,
        flow_idx: int,
        flow: GridTrafficFlow,
        source_idx: int,
        target_idx: int,
        source_name: str,
        target_name: str,
        network: NetworkModel,
    ) -> List[str]:
        """Generate SCADA polling/traffic application."""
        lines = []
        
        traffic_class = flow.traffic_class
        priority = flow.priority
        
        lines.append(f"    # Flow {flow_idx}: SCADA {traffic_class.name}")
        lines.append(f"    # {source_name} -> {target_name}, Priority: {priority.name}")
        
        if traffic_class == GridTrafficClass.GOOSE:
            # GOOSE is multicast, low-latency
            lines.extend(self._generate_goose_application(
                flow_idx, flow, source_idx, target_idx, network
            ))
        elif traffic_class in (GridTrafficClass.SCADA_INTEGRITY_POLL,
                                GridTrafficClass.SCADA_EXCEPTION_POLL):
            # Polling traffic - request/response
            lines.extend(self._generate_polling_application(
                flow_idx, flow, source_idx, target_idx, network
            ))
        elif traffic_class in (GridTrafficClass.CONTROL_SELECT,
                                GridTrafficClass.CONTROL_OPERATE):
            # Control commands - low latency, high priority
            lines.extend(self._generate_control_application(
                flow_idx, flow, source_idx, target_idx, network
            ))
        else:
            # Default: use echo-style application
            lines.extend(self._generate_echo_app_simple(
                flow_idx, flow, source_idx, target_idx, network
            ))
        
        lines.append("")
        return lines
    
    def _find_target_interface(
        self,
        flow: Union[GridTrafficFlow, TrafficFlow],
        network: NetworkModel,
    ) -> Tuple[Optional[int], int]:
        """
        Find the correct interface container and index for a flow's target node.
        
        Returns:
            Tuple of (link_index, interface_index) or (None, 0) if not found.
            link_index: Which interfaces{N} container to use
            interface_index: Which address in that container (0 or 1)
        """
        from models.network import NodeType
        
        target_link_idx = None
        interface_idx = 0
        
        for idx, (link_id, link) in enumerate(network.links.items()):
            link_source = network.nodes.get(link.source_node_id)
            link_target = network.nodes.get(link.target_node_id)
            
            # Check if target node is the "target" side of this link
            if link.target_node_id == flow.target_node_id:
                source_is_switch = link_source and link_source.node_type in (NodeType.SWITCH,)
                if source_is_switch:
                    # switch -> target: IP at index 0
                    target_link_idx = idx
                    interface_idx = 0
                else:
                    # host -> target: IP at index 1
                    target_link_idx = idx
                    interface_idx = 1
                break
            # Check if target node is the "source" side of this link
            elif link.source_node_id == flow.target_node_id:
                target_is_switch = link_source and link_source.node_type in (NodeType.SWITCH,)
                if target_is_switch:
                    target_link_idx = idx
                    interface_idx = 0
                else:
                    # target -> host: IP at index 0
                    target_link_idx = idx
                    interface_idx = 0
                break
        
        return target_link_idx, interface_idx

    def _generate_polling_application(
        self,
        flow_idx: int,
        flow: GridTrafficFlow,
        source_idx: int,
        target_idx: int,
        network: NetworkModel,
    ) -> List[str]:
        """Generate SCADA polling (request/response) application."""
        lines = []
        
        interval_s = flow.interval_ms / 1000.0 if flow.interval_ms > 0 else 4.0
        
        # Estimate packet sizes from DNP3 config
        request_size = 64  # Default
        response_size = 256  # Default
        if flow.dnp3_config:
            request_size = flow.dnp3_config.estimated_request_bytes
            response_size = flow.dnp3_config.estimated_response_bytes
        
        # Find the correct interface for the target
        target_link_idx, interface_idx = self._find_target_interface(flow, network)
        
        if target_link_idx is None:
            lines.append(f"    # Flow {flow_idx}: ERROR - Cannot find interface for target node")
            return lines
        
        lines.extend([
            f"    # SCADA Polling: interval={interval_s}s, request={request_size}B, response={response_size}B",
            "",
            f"    # Server (RTU/IED) on target node",
            f"    echo_server_{flow_idx} = ns.UdpEchoServerHelper({flow.port})",
            f"    server_apps_{flow_idx} = echo_server_{flow_idx}.Install(nodes.Get({target_idx}))",
            f"    server_apps_{flow_idx}.Start(ns.Seconds(0.0))",
            f"    server_apps_{flow_idx}.Stop(ns.Seconds({flow.stop_time}))",
            "",
            f"    # Client (Master/CC) on source node",
            f"    target_addr_{flow_idx} = interfaces{target_link_idx}.GetAddress({interface_idx})",
            f"    remote_addr_{flow_idx} = ns.InetSocketAddress(target_addr_{flow_idx}, {flow.port})",
            f"    echo_client_{flow_idx} = ns.UdpEchoClientHelper(remote_addr_{flow_idx}.ConvertTo())",
            f"    echo_client_{flow_idx}.SetAttribute('MaxPackets', ns.UintegerValue({int((flow.stop_time - flow.start_time) / interval_s)}))",
            f"    echo_client_{flow_idx}.SetAttribute('Interval', ns.TimeValue(ns.Seconds({interval_s})))",
            f"    echo_client_{flow_idx}.SetAttribute('PacketSize', ns.UintegerValue({request_size}))",
            f"    client_apps_{flow_idx} = echo_client_{flow_idx}.Install(nodes.Get({source_idx}))",
            f"    client_apps_{flow_idx}.Start(ns.Seconds({flow.start_time}))",
            f"    client_apps_{flow_idx}.Stop(ns.Seconds({flow.stop_time}))",
        ])
        
        return lines
    
    def _generate_goose_application(
        self,
        flow_idx: int,
        flow: GridTrafficFlow,
        source_idx: int,
        target_idx: int,
        network: NetworkModel,
    ) -> List[str]:
        """Generate GOOSE (IEC 61850) multicast application."""
        lines = []
        
        # GOOSE uses multicast and has very tight timing requirements
        # In ns-3, we approximate with OnOff UDP
        
        interval_ms = 1000  # Default retransmit interval
        if flow.goose_config:
            interval_ms = flow.goose_config.max_time_ms
        
        packet_size = 100  # Typical GOOSE message
        if flow.goose_config:
            packet_size = flow.goose_config.estimated_bytes
        
        lines.extend([
            f"    # GOOSE multicast traffic (IEC 61850)",
            f"    # Note: Using unicast UDP as approximation for multicast",
            f"    # Real GOOSE uses Layer 2 multicast with strict timing",
            "",
            f"    # OnOff application for GOOSE-like traffic",
            f"    goose_helper_{flow_idx} = ns.OnOffHelper(",
            f"        'ns3::UdpSocketFactory',",
            f"        ns.InetSocketAddress(interfaces0.GetAddress({target_idx}), {flow.port})",
            f"    )",
            f"    goose_helper_{flow_idx}.SetAttribute('DataRate', ns.StringValue('1Mbps'))",
            f"    goose_helper_{flow_idx}.SetAttribute('PacketSize', ns.UintegerValue({packet_size}))",
            f"    goose_helper_{flow_idx}.SetAttribute('OnTime', ns.StringValue('ns3::ConstantRandomVariable[Constant=0.001]'))",
            f"    goose_helper_{flow_idx}.SetAttribute('OffTime', ns.StringValue('ns3::ConstantRandomVariable[Constant={interval_ms / 1000.0}]'))",
            f"    goose_apps_{flow_idx} = goose_helper_{flow_idx}.Install(nodes.Get({source_idx}))",
            f"    goose_apps_{flow_idx}.Start(ns.Seconds({flow.start_time}))",
            f"    goose_apps_{flow_idx}.Stop(ns.Seconds({flow.stop_time}))",
        ])
        
        return lines
    
    def _generate_control_application(
        self,
        flow_idx: int,
        flow: GridTrafficFlow,
        source_idx: int,
        target_idx: int,
        network: NetworkModel,
    ) -> List[str]:
        """Generate control command (Select-Before-Operate) application."""
        lines = []
        
        # Control commands are sporadic, not periodic
        # Model as a single echo exchange
        packet_size = 64  # Control message size
        
        # Find the correct interface for the target
        target_link_idx, interface_idx = self._find_target_interface(flow, network)
        
        if target_link_idx is None:
            lines.append(f"    # Flow {flow_idx}: ERROR - Cannot find interface for target node")
            return lines
        
        lines.extend([
            f"    # Control command traffic (Select-Before-Operate)",
            f"    # Note: Real control is event-driven, not periodic",
            "",
            f"    ctrl_server_{flow_idx} = ns.UdpEchoServerHelper({flow.port})",
            f"    ctrl_srv_apps_{flow_idx} = ctrl_server_{flow_idx}.Install(nodes.Get({target_idx}))",
            f"    ctrl_srv_apps_{flow_idx}.Start(ns.Seconds(0.0))",
            f"    ctrl_srv_apps_{flow_idx}.Stop(ns.Seconds({flow.stop_time}))",
            "",
            f"    ctrl_target_{flow_idx} = interfaces{target_link_idx}.GetAddress({interface_idx})",
            f"    ctrl_addr_{flow_idx} = ns.InetSocketAddress(ctrl_target_{flow_idx}, {flow.port})",
            f"    ctrl_client_{flow_idx} = ns.UdpEchoClientHelper(ctrl_addr_{flow_idx}.ConvertTo())",
            f"    ctrl_client_{flow_idx}.SetAttribute('MaxPackets', ns.UintegerValue(2))  # SELECT + OPERATE",
            f"    ctrl_client_{flow_idx}.SetAttribute('Interval', ns.TimeValue(ns.Seconds(0.5)))",
            f"    ctrl_client_{flow_idx}.SetAttribute('PacketSize', ns.UintegerValue({packet_size}))",
            f"    ctrl_cli_apps_{flow_idx} = ctrl_client_{flow_idx}.Install(nodes.Get({source_idx}))",
            f"    ctrl_cli_apps_{flow_idx}.Start(ns.Seconds({flow.start_time}))",
            f"    ctrl_cli_apps_{flow_idx}.Stop(ns.Seconds({flow.stop_time}))",
        ])
        
        return lines
    
    def _generate_echo_app_simple(
        self,
        flow_idx: int,
        flow: TrafficFlow,
        source_idx: int,
        target_idx: int,
        network: NetworkModel,
    ) -> List[str]:
        """Generate simple UDP echo application."""
        # Find the correct interface for the target
        target_link_idx, interface_idx = self._find_target_interface(flow, network)
        
        if target_link_idx is None:
            return [f"    # Flow {flow_idx}: ERROR - Cannot find interface for target node"]
        
        lines = [
            f"    # UDP Echo application",
            f"    echo_server_{flow_idx} = ns.UdpEchoServerHelper({flow.port})",
            f"    srv_apps_{flow_idx} = echo_server_{flow_idx}.Install(nodes.Get({target_idx}))",
            f"    srv_apps_{flow_idx}.Start(ns.Seconds(0.0))",
            f"    srv_apps_{flow_idx}.Stop(ns.Seconds({flow.stop_time}))",
            "",
            f"    target_addr_{flow_idx} = interfaces{target_link_idx}.GetAddress({interface_idx})",
            f"    echo_addr_{flow_idx} = ns.InetSocketAddress(target_addr_{flow_idx}, {flow.port})",
            f"    echo_client_{flow_idx} = ns.UdpEchoClientHelper(echo_addr_{flow_idx}.ConvertTo())",
            f"    echo_client_{flow_idx}.SetAttribute('MaxPackets', ns.UintegerValue({flow.echo_packets}))",
            f"    echo_client_{flow_idx}.SetAttribute('Interval', ns.TimeValue(ns.Seconds({flow.echo_interval})))",
            f"    echo_client_{flow_idx}.SetAttribute('PacketSize', ns.UintegerValue({flow.packet_size}))",
            f"    cli_apps_{flow_idx} = echo_client_{flow_idx}.Install(nodes.Get({source_idx}))",
            f"    cli_apps_{flow_idx}.Start(ns.Seconds({flow.start_time}))",
            f"    cli_apps_{flow_idx}.Stop(ns.Seconds({flow.stop_time}))",
        ]
        return lines
    
    def _generate_onoff_app_simple(
        self,
        flow_idx: int,
        flow: TrafficFlow,
        source_idx: int,
        target_idx: int,
        network: NetworkModel,
    ) -> List[str]:
        """Generate simple OnOff application."""
        # Find the correct interface for the target
        target_link_idx, interface_idx = self._find_target_interface(flow, network)
        
        if target_link_idx is None:
            return [f"    # Flow {flow_idx}: ERROR - Cannot find interface for target node"]
        
        lines = [
            f"    # OnOff application",
            f"    sink_{flow_idx} = ns.PacketSinkHelper(",
            f"        'ns3::UdpSocketFactory',",
            f"        ns.InetSocketAddress(ns.Ipv4Address.GetAny(), {flow.port})",
            f"    )",
            f"    sink_apps_{flow_idx} = sink_{flow_idx}.Install(nodes.Get({target_idx}))",
            f"    sink_apps_{flow_idx}.Start(ns.Seconds(0.0))",
            f"    sink_apps_{flow_idx}.Stop(ns.Seconds({flow.stop_time}))",
            "",
            f"    target_addr_{flow_idx} = interfaces{target_link_idx}.GetAddress({interface_idx})",
            f"    onoff_{flow_idx} = ns.OnOffHelper(",
            f"        'ns3::UdpSocketFactory',",
            f"        ns.InetSocketAddress(target_addr_{flow_idx}, {flow.port})",
            f"    )",
            f"    onoff_{flow_idx}.SetAttribute('DataRate', ns.StringValue('{flow.data_rate}'))",
            f"    onoff_{flow_idx}.SetAttribute('PacketSize', ns.UintegerValue({flow.packet_size}))",
            f"    onoff_apps_{flow_idx} = onoff_{flow_idx}.Install(nodes.Get({source_idx}))",
            f"    onoff_apps_{flow_idx}.Start(ns.Seconds({flow.start_time}))",
            f"    onoff_apps_{flow_idx}.Stop(ns.Seconds({flow.stop_time}))",
        ]
        return lines
    
    def _generate_failure_injection(self) -> str:
        """
        Generate failure injection code.
        
        NOTE: ns-3's Python bindings (cppyy) do not support scheduling Python
        callbacks via Simulator::Schedule. Failure injection using callbacks
        is therefore not available in Python-based ns-3 scripts.
        
        For failure scenarios, consider:
        1. Using C++ ns-3 scripts with proper callback support
        2. Running multiple simulations with different static configurations
        3. Using ns-3's built-in error models with time-based parameters
        """
        if not self._failure_scenario or not self._failure_scenario.events:
            return ""
        
        # Generate informational comment about the failure scenario
        # but don't generate the actual callback code since it won't work
        lines = [
            "    # ============================================",
            "    # Failure Injection Scenario (INFORMATIONAL)",
            "    # ============================================",
            f"    # Scenario: {self._failure_scenario.name}",
            f"    # Events: {self._failure_scenario.event_count}",
            "    #",
            "    # NOTE: Dynamic failure injection via Simulator.Schedule() is not",
            "    # supported in ns-3 Python bindings (cppyy cannot pass Python callbacks).",
            "    #",
            "    # Planned events:",
        ]
        
        for event_idx, event in enumerate(self._failure_scenario.events):
            event_type = event.event_type.name
            trigger_time = event.trigger_time_s
            target_id = event.target_id
            
            lines.append(f"    #   - Event {event_idx}: {event_type} on {target_id} at t={trigger_time}s")
            
            if event.has_duration:
                recovery_time = event.effective_recovery_time
                lines.append(f"    #     Recovery at t={recovery_time}s")
        
        lines.extend([
            "    #",
            "    # To implement failure injection, use one of these approaches:",
            "    #   1. Write a C++ ns-3 script with MakeCallback",
            "    #   2. Run separate simulations for pre/during/post failure",
            "    #   3. Use static error rate configuration",
            "",
            f"    print('Failure scenario: {self._failure_scenario.name} ({self._failure_scenario.event_count} events)')",
            "    print('Note: Dynamic failure injection not supported in Python bindings')",
            "",
        ])
        
        return "\n".join(lines)
