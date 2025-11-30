"""
NS-3 Python script generator.

Generates ns-3 Python scripts from NetworkModel and SimulationConfig.
"""

from datetime import datetime
from typing import Optional, Dict, Set, Tuple, List
from models import (
    NetworkModel, NodeModel, LinkModel, NodeType, ChannelType,
    SimulationConfig, TrafficFlow, TrafficApplication, TrafficProtocol
)


class NS3ScriptGenerator:
    """
    Generates ns-3 Python scripts from network topology and simulation config.
    
    The generated scripts use ns-3's Python bindings and can be run with:
        ./ns3 run scratch/generated_script.py
    """
    
    def __init__(self):
        self._node_index_map: dict[str, int] = {}
        self._link_index_map: dict[str, int] = {}
    
    def _get_port_ip(self, node: NodeModel, port_id: str) -> Tuple[Optional[str], Optional[str]]:
        """Get IP address and netmask for a port, if configured.
        
        Returns:
            Tuple of (ip_address, netmask) or (None, None) if not configured
        """
        for port in node.ports:
            if port.id == port_id:
                ip = port.ip_address if port.ip_address else None
                mask = port.netmask if port.netmask else "255.255.255.0"
                return (ip, mask)
        return (None, None)
    
    def _get_link_endpoint_port(self, network: NetworkModel, link: LinkModel, is_source: bool) -> Optional[str]:
        """Get the port ID for a link endpoint."""
        if is_source:
            return link.source_port_id
        else:
            return link.target_port_id
    
    def _analyze_switch_segments(self, network: NetworkModel) -> Dict[str, List[Tuple[str, str, str]]]:
        """Analyze which nodes/ports are connected to each switch.
        
        Returns:
            Dict mapping switch_id to list of (node_id, port_id, link_id) tuples
        """
        switch_segments = {}
        
        for node in network.nodes.values():
            if node.node_type == NodeType.SWITCH:
                switch_segments[node.id] = []
        
        for link_id, link in network.links.items():
            source_node = network.nodes.get(link.source_node_id)
            target_node = network.nodes.get(link.target_node_id)
            
            if source_node and source_node.node_type == NodeType.SWITCH:
                # Target connects to this switch
                switch_segments[source_node.id].append(
                    (link.target_node_id, link.target_port_id, link_id)
                )
            
            if target_node and target_node.node_type == NodeType.SWITCH:
                # Source connects to this switch
                switch_segments[target_node.id].append(
                    (link.source_node_id, link.source_port_id, link_id)
                )
        
        return switch_segments
    
    def _determine_switch_subnet(self, network: NetworkModel, connected_nodes: List[Tuple[str, str, str]]) -> Tuple[str, str]:
        """Determine what subnet to use for a switch segment based on connected nodes.
        
        Looks for any configured IPs on connected ports and uses that subnet,
        or generates a new one if none found.
        
        Returns:
            Tuple of (subnet_base, netmask) e.g. ("10.1.5.0", "255.255.255.0")
        """
        # Look for any configured IPs on connected ports
        for node_id, port_id, link_id in connected_nodes:
            node = network.nodes.get(node_id)
            if node:
                ip, mask = self._get_port_ip(node, port_id)
                if ip:
                    # Extract subnet from this IP
                    parts = ip.split('.')
                    if len(parts) == 4:
                        subnet = f"{parts[0]}.{parts[1]}.{parts[2]}.0"
                        return (subnet, mask or "255.255.255.0")
        
        # No configured IPs found, will use auto-assignment
        return (None, "255.255.255.0")
    
    def generate(
        self, 
        network: NetworkModel, 
        sim_config: SimulationConfig,
        output_dir: str = "."
    ) -> str:
        """
        Generate complete ns-3 Python script.
        
        Args:
            network: The network topology model
            sim_config: Simulation configuration with flows
            output_dir: Directory for output files (traces, pcap)
            
        Returns:
            Complete Python script as string
        """
        # Build node index mapping (node_id -> integer index)
        self._node_index_map = {
            node_id: idx 
            for idx, node_id in enumerate(network.nodes.keys())
        }
        
        sections = [
            self._generate_header(network, sim_config),
            self._generate_imports(),
            self._generate_main_function_start(),
            self._generate_nodes(network),
            self._generate_channels(network),
            self._generate_internet_stack(network),
            self._generate_ip_addresses(network),
            self._generate_routing(network),
            self._generate_applications(network, sim_config),
            self._generate_tracing(sim_config, output_dir),
            self._generate_simulation_run(sim_config, output_dir),
            self._generate_main_function_end(),
            self._generate_main_call(),
        ]
        
        return "\n".join(sections)
    
    def _generate_header(self, network: NetworkModel, sim_config: SimulationConfig) -> str:
        """Generate script header with metadata."""
        return f'''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NS-3 Simulation Script
Generated by ns3-gui on {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

Topology:
  - Nodes: {len(network.nodes)}
  - Links: {len(network.links)}
  - Traffic Flows: {len(sim_config.flows)}
  
Simulation Duration: {sim_config.duration} seconds
"""
'''
    
    def _generate_imports(self) -> str:
        """Generate ns-3 import statements."""
        return '''
# NS-3 imports (ns-3.45+ with cppyy bindings)
from ns import ns

import sys
'''
    
    def _generate_main_function_start(self) -> str:
        """Generate main function start."""
        return '''
def main():
    """Run the simulation."""
    
    # Enable logging for debugging (optional)
    # ns.LogComponentEnable("UdpEchoClientApplication", ns.LOG_LEVEL_INFO)
    # ns.LogComponentEnable("UdpEchoServerApplication", ns.LOG_LEVEL_INFO)
'''
    
    def _generate_nodes(self, network: NetworkModel) -> str:
        """Generate node creation code."""
        lines = [
            "    # ============================================",
            "    # Create Nodes",
            "    # ============================================",
            f"    nodes = ns.NodeContainer()",
            f"    nodes.Create({len(network.nodes)})",
            "",
            "    # Node mapping:",
        ]
        
        for node_id, idx in self._node_index_map.items():
            node = network.nodes[node_id]
            lines.append(f"    # Node {idx}: {node.name} ({node.node_type.name})")
        
        lines.append("")
        return "\n".join(lines)
    
    def _generate_channels(self, network: NetworkModel) -> str:
        """Generate channel/link configuration."""
        lines = [
            "    # ============================================",
            "    # Create Links/Channels",
            "    # ============================================",
            "    ",
            "    # Point-to-point helper for direct links",
            "    p2p = ns.PointToPointHelper()",
            "",
            "    # CSMA helper for shared medium (switch connections)",
            "    csma = ns.CsmaHelper()",
            "",
            "    # Store all NetDeviceContainers",
            "    all_devices = []",
            "",
        ]
        
        for idx, (link_id, link) in enumerate(network.links.items()):
            source_idx = self._node_index_map.get(link.source_node_id, 0)
            target_idx = self._node_index_map.get(link.target_node_id, 0)
            
            source_node = network.nodes.get(link.source_node_id)
            target_node = network.nodes.get(link.target_node_id)
            
            source_name = source_node.name if source_node else "unknown"
            target_name = target_node.name if target_node else "unknown"
            
            # Check if either end is a switch - must use CSMA for bridging
            source_is_switch = source_node and source_node.node_type == NodeType.SWITCH
            target_is_switch = target_node and target_node.node_type == NodeType.SWITCH
            use_csma = source_is_switch or target_is_switch or link.channel_type == ChannelType.CSMA
            
            lines.append(f"    # Link {idx}: {source_name} <-> {target_name}")
            
            if use_csma:
                # CSMA required for switch bridging (P2P doesn't support SendFrom)
                lines.extend([
                    f"    csma.SetChannelAttribute('DataRate', ns.StringValue('{link.data_rate}'))",
                    f"    csma.SetChannelAttribute('Delay', ns.StringValue('{link.delay}'))",
                    f"    link{idx}_nodes = ns.NodeContainer()",
                    f"    link{idx}_nodes.Add(nodes.Get({source_idx}))",
                    f"    link{idx}_nodes.Add(nodes.Get({target_idx}))",
                    f"    devices{idx} = csma.Install(link{idx}_nodes)",
                    f"    all_devices.append(devices{idx})",
                    "",
                ])
            else:
                # Point-to-point for direct host-to-host links
                lines.extend([
                    f"    p2p.SetDeviceAttribute('DataRate', ns.StringValue('{link.data_rate}'))",
                    f"    p2p.SetChannelAttribute('Delay', ns.StringValue('{link.delay}'))",
                    f"    link{idx}_nodes = ns.NodeContainer()",
                    f"    link{idx}_nodes.Add(nodes.Get({source_idx}))",
                    f"    link{idx}_nodes.Add(nodes.Get({target_idx}))",
                    f"    devices{idx} = p2p.Install(link{idx}_nodes)",
                    f"    all_devices.append(devices{idx})",
                    "",
                ])
        
        return "\n".join(lines)
    
    def _generate_internet_stack(self, network: NetworkModel) -> str:
        """Generate IP stack installation."""
        # Find switch/router nodes that should act as bridges
        switch_indices = []
        host_indices = []
        
        for node_id, node in network.nodes.items():
            idx = self._node_index_map.get(node_id, 0)
            if node.node_type in (NodeType.SWITCH,):
                switch_indices.append(idx)
            else:
                host_indices.append(idx)
        
        lines = [
            "    # ============================================",
            "    # Install Internet Stack",
            "    # ============================================",
            "    internet_stack = ns.InternetStackHelper()",
            "",
        ]
        
        if switch_indices:
            # Only install IP stack on non-switch nodes
            lines.extend([
                "    # Install Internet stack only on hosts/routers (not switches)",
                "    host_nodes = ns.NodeContainer()",
            ])
            for idx in host_indices:
                lines.append(f"    host_nodes.Add(nodes.Get({idx}))")
            lines.extend([
                "    internet_stack.Install(host_nodes)",
                "",
                "    # Set up bridge on switch nodes",
                "    bridge_helper = ns.BridgeHelper()",
                "",
            ])
            
            # For each switch, bridge all its connected devices
            for switch_id, switch_node in network.nodes.items():
                if switch_node.node_type not in (NodeType.SWITCH,):
                    continue
                
                switch_idx = self._node_index_map.get(switch_id, 0)
                
                # Find all links connected to this switch
                connected_link_indices = []
                for link_idx, (link_id, link) in enumerate(network.links.items()):
                    if link.source_node_id == switch_id or link.target_node_id == switch_id:
                        connected_link_indices.append((link_idx, link.source_node_id == switch_id))
                
                if connected_link_indices:
                    lines.append(f"    # Bridge devices on switch node {switch_idx} ({switch_node.name})")
                    lines.append(f"    switch{switch_idx}_devices = ns.NetDeviceContainer()")
                    
                    for link_idx, is_source in connected_link_indices:
                        # Device index: 0 if switch is source, 1 if switch is target
                        dev_idx = 0 if is_source else 1
                        lines.append(f"    switch{switch_idx}_devices.Add(devices{link_idx}.Get({dev_idx}))")
                    
                    lines.append(f"    bridge_helper.Install(nodes.Get({switch_idx}), switch{switch_idx}_devices)")
                    lines.append("")
        else:
            lines.extend([
                "    internet_stack.Install(nodes)",
                "",
            ])
        
        return "\n".join(lines)
    
    def _generate_ip_addresses(self, network: NetworkModel) -> str:
        """Generate IP address assignment.
        
        This method handles complex topologies with switches by:
        1. Respecting user-defined IP addresses when present
        2. Grouping switch-connected devices into segments
        3. Using consistent subnets within each segment
        4. Falling back to auto-assignment for unconfigured interfaces
        """
        # Check if we have switches (bridged network)
        has_switches = any(
            node.node_type in (NodeType.SWITCH,) 
            for node in network.nodes.values()
        )
        
        lines = [
            "    # ============================================",
            "    # Assign IP Addresses",
            "    # ============================================",
            "    ipv4 = ns.Ipv4AddressHelper()",
            "",
            "    # Store interfaces for later use",
            "    all_interfaces = []",
            "",
        ]
        
        # Track which links are connected to switches
        switch_connected_links = set()
        if has_switches:
            switch_segments = self._analyze_switch_segments(network)
            for switch_id, connected in switch_segments.items():
                for node_id, port_id, link_id in connected:
                    switch_connected_links.add(link_id)
        
        # Use a subnet counter for auto-assignment
        auto_subnet_counter = 1
        
        # For each switch segment, determine its subnet and assign IPs
        if has_switches:
            switch_segments = self._analyze_switch_segments(network)
            
            # Process each switch's segment
            for switch_id, connected_nodes in switch_segments.items():
                switch_node = network.nodes.get(switch_id)
                switch_name = switch_node.name if switch_node else "switch"
                
                if not connected_nodes:
                    continue
                
                # Determine subnet for this switch segment
                segment_subnet, segment_mask = self._determine_switch_subnet(network, connected_nodes)
                
                if segment_subnet:
                    lines.extend([
                        f"    # Switch segment: {switch_name}",
                        f"    # Using subnet {segment_subnet}/24 based on configured IPs",
                        f"    switch_subnet = '{segment_subnet}'",
                        "",
                    ])
                else:
                    # Auto-assign subnet for this switch segment
                    segment_subnet = f"10.1.{auto_subnet_counter}.0"
                    auto_subnet_counter += 1
                    lines.extend([
                        f"    # Switch segment: {switch_name}",
                        f"    # Auto-assigned subnet {segment_subnet}/24",
                        f"    switch_subnet = '{segment_subnet}'",
                        "",
                    ])
                
                lines.append(f"    ipv4.SetBase(ns.Ipv4Address(switch_subnet), ns.Ipv4Mask('255.255.255.0'))")
                lines.append("")
        
        # Now assign IPs per link
        for idx, (link_id, link) in enumerate(network.links.items()):
            source_node = network.nodes.get(link.source_node_id)
            target_node = network.nodes.get(link.target_node_id)
            
            source_is_switch = source_node and source_node.node_type in (NodeType.SWITCH,)
            target_is_switch = target_node and target_node.node_type in (NodeType.SWITCH,)
            
            # Create interface container for this link
            lines.append(f"    interfaces{idx} = ns.Ipv4InterfaceContainer()")
            
            if source_is_switch and target_is_switch:
                # Switch-to-switch link, no IP assignment
                lines.append(f"    # Switch-to-switch link, no IP assignment")
                
            elif source_is_switch or target_is_switch:
                # One end is switch - only assign IP to non-switch end
                if source_is_switch:
                    host_node = target_node
                    host_port = link.target_port_id
                    dev_idx = 1  # Target is device index 1
                else:
                    host_node = source_node
                    host_port = link.source_port_id
                    dev_idx = 0  # Source is device index 0
                
                # Check if this port has a user-defined IP
                user_ip, user_mask = self._get_port_ip(host_node, host_port) if host_node else (None, None)
                
                if user_ip:
                    # Use user-defined IP - extract subnet and set base
                    parts = user_ip.split('.')
                    subnet = f"{parts[0]}.{parts[1]}.{parts[2]}.0"
                    host_octet = parts[3]
                    lines.extend([
                        f"    # Using user-configured IP: {user_ip}",
                        f"    ipv4.SetBase(ns.Ipv4Address('{subnet}'), ns.Ipv4Mask('{user_mask}'), ns.Ipv4Address('0.0.0.{host_octet}'))",
                        f"    host_dev{idx} = ns.NetDeviceContainer()",
                        f"    host_dev{idx}.Add(devices{idx}.Get({dev_idx}))",
                        f"    interfaces{idx} = ipv4.Assign(host_dev{idx})",
                    ])
                else:
                    # Use auto-assigned IP from switch segment subnet
                    lines.extend([
                        f"    # Auto-assign IP on switch segment",
                        f"    host_dev{idx} = ns.NetDeviceContainer()",
                        f"    host_dev{idx}.Add(devices{idx}.Get({dev_idx}))",
                        f"    interfaces{idx} = ipv4.Assign(host_dev{idx})",
                    ])
            else:
                # Direct point-to-point link (no switch)
                # Check for user-defined IPs on both ends
                source_ip, source_mask = self._get_port_ip(source_node, link.source_port_id) if source_node else (None, None)
                target_ip, target_mask = self._get_port_ip(target_node, link.target_port_id) if target_node else (None, None)
                
                if source_ip and target_ip:
                    # Both have user-defined IPs - use source's subnet
                    parts = source_ip.split('.')
                    subnet = f"{parts[0]}.{parts[1]}.{parts[2]}.0"
                    lines.extend([
                        f"    # Using user-configured IPs: {source_ip} <-> {target_ip}",
                        f"    ipv4.SetBase(ns.Ipv4Address('{subnet}'), ns.Ipv4Mask('{source_mask}'))",
                        f"    interfaces{idx} = ipv4.Assign(devices{idx})",
                    ])
                elif source_ip:
                    # Only source has IP
                    parts = source_ip.split('.')
                    subnet = f"{parts[0]}.{parts[1]}.{parts[2]}.0"
                    lines.extend([
                        f"    # Source has configured IP: {source_ip}",
                        f"    ipv4.SetBase(ns.Ipv4Address('{subnet}'), ns.Ipv4Mask('{source_mask}'))",
                        f"    interfaces{idx} = ipv4.Assign(devices{idx})",
                    ])
                elif target_ip:
                    # Only target has IP
                    parts = target_ip.split('.')
                    subnet = f"{parts[0]}.{parts[1]}.{parts[2]}.0"
                    lines.extend([
                        f"    # Target has configured IP: {target_ip}",
                        f"    ipv4.SetBase(ns.Ipv4Address('{subnet}'), ns.Ipv4Mask('{target_mask}'))",
                        f"    interfaces{idx} = ipv4.Assign(devices{idx})",
                    ])
                else:
                    # No user-defined IPs, auto-assign
                    subnet = f"10.1.{auto_subnet_counter}.0"
                    auto_subnet_counter += 1
                    lines.extend([
                        f"    # Auto-assign subnet {subnet}/24",
                        f"    ipv4.SetBase(ns.Ipv4Address('{subnet}'), ns.Ipv4Mask('255.255.255.0'))",
                        f"    interfaces{idx} = ipv4.Assign(devices{idx})",
                    ])
            
            lines.extend([
                f"    all_interfaces.append(interfaces{idx})",
                "",
            ])
        
        # Print IP addresses for reference
        lines.extend([
            "    # Print assigned IP addresses",
            "    print('\\nIP Address Assignment:')",
        ])
        
        for idx, (link_id, link) in enumerate(network.links.items()):
            source_node = network.nodes.get(link.source_node_id)
            target_node = network.nodes.get(link.target_node_id)
            source_name = source_node.name if source_node else "unknown"
            target_name = target_node.name if target_node else "unknown"
            
            source_is_switch = source_node and source_node.node_type in (NodeType.SWITCH,)
            target_is_switch = target_node and target_node.node_type in (NodeType.SWITCH,)
            
            if source_is_switch and target_is_switch:
                lines.append(f"    print(f'  Link {idx}: {source_name} <-> {target_name} (no IP - switch link)')")
            elif source_is_switch:
                lines.append(f"    print(f'  Link {idx}: {source_name} (switch) <-> {{interfaces{idx}.GetAddress(0)}} ({target_name})')")
            elif target_is_switch:
                lines.append(f"    print(f'  Link {idx}: {{interfaces{idx}.GetAddress(0)}} ({source_name}) <-> {target_name} (switch)')")
            else:
                lines.append(f"    print(f'  Link {idx}: {{interfaces{idx}.GetAddress(0)}} ({source_name}) <-> {{interfaces{idx}.GetAddress(1)}} ({target_name})')")
        
        lines.append("    print()")
        lines.append("")
        return "\n".join(lines)
    
    def _generate_routing(self, network: NetworkModel) -> str:
        """Generate routing configuration."""
        from models import RoutingMode, RouteType
        
        # Check if we have routers that need routing
        has_routers = any(
            node.node_type == NodeType.ROUTER 
            for node in network.nodes.values()
        )
        
        # Check if any node has manual routing configured
        has_manual_routing = any(
            node.routing_mode == RoutingMode.MANUAL and len(node.routing_table) > 0
            for node in network.nodes.values()
        )
        
        # Check if we have switches (which can confuse GlobalRoutingHelper)
        has_switches = any(
            node.node_type == NodeType.SWITCH
            for node in network.nodes.values()
        )
        
        # Count how many routers are connected to switches
        # This is problematic for GlobalRoutingHelper
        routers_on_switches = 0
        if has_switches:
            switch_segments = self._analyze_switch_segments(network)
            for switch_id, connected in switch_segments.items():
                for node_id, port_id, link_id in connected:
                    node = network.nodes.get(node_id)
                    if node and node.node_type == NodeType.ROUTER:
                        routers_on_switches += 1
        
        # If multiple routers on same switch, GlobalRoutingHelper may fail
        use_global_routing = has_routers and not has_switches
        if has_switches and routers_on_switches <= 1:
            # Single router on switch is usually OK
            use_global_routing = True
        
        lines = [
            "    # ============================================",
            "    # Configure Routing",
            "    # ============================================",
        ]
        
        if has_manual_routing:
            # Generate static routes for nodes with manual routing
            lines.extend([
                "    # Manual static routing configuration",
                "",
            ])
            
            for node_id, node in network.nodes.items():
                if node.routing_mode != RoutingMode.MANUAL or not node.routing_table:
                    continue
                
                node_idx = self._node_index_map.get(node_id, 0)
                
                lines.extend([
                    f"    # Static routes for {node.name}",
                    f"    ipv4_{node_idx} = nodes.Get({node_idx}).GetObject[ns.Ipv4]()",
                    f"    # Get the static routing protocol from the node's routing list",
                    f"    static_routing_{node_idx} = ipv4_{node_idx}.GetRoutingProtocol().GetObject[ns.Ipv4StaticRouting]()",
                    "",
                ])
                
                for route in node.routing_table:
                    if not route.enabled:
                        continue
                    
                    # Parse destination network
                    dest_parts = route.destination.split('.')
                    dest_network = route.destination
                    
                    # Calculate netmask from prefix length
                    prefix = route.prefix_length
                    mask_int = (0xFFFFFFFF << (32 - prefix)) & 0xFFFFFFFF
                    mask = f"{(mask_int >> 24) & 0xFF}.{(mask_int >> 16) & 0xFF}.{(mask_int >> 8) & 0xFF}.{mask_int & 0xFF}"
                    
                    # For connected/direct routes, ns-3 auto-adds them when IPs are assigned
                    # So we only need to add routes that go through a gateway
                    if route.is_direct:
                        # Skip - connected routes are added automatically by ns-3
                        lines.extend([
                            f"    # Route: {route.cidr} via interface {route.interface} (connected - auto-added by ns-3)",
                        ])
                    elif route.destination == "0.0.0.0" and route.prefix_length == 0:
                        # Default route - need to add explicitly
                        lines.extend([
                            f"    # Default route via {route.gateway}",
                            f"    static_routing_{node_idx}.SetDefaultRoute(",
                            f"        ns.Ipv4Address('{route.gateway}'),",
                            f"        {route.interface + 1}  # interface index",
                            f"    )",
                        ])
                    else:
                        # Route via gateway - need to add explicitly
                        lines.extend([
                            f"    # Route: {route.cidr} via {route.gateway}",
                            f"    static_routing_{node_idx}.AddNetworkRouteTo(",
                            f"        ns.Ipv4Address('{dest_network}'),",
                            f"        ns.Ipv4Mask('{mask}'),",
                            f"        ns.Ipv4Address('{route.gateway}'),",
                            f"        {route.interface + 1},  # interface index",
                            f"        0  # metric",
                            f"    )",
                        ])
                
                lines.append("")
            
            # Only use global routing if it's safe to do so
            if use_global_routing:
                lines.extend([
                    "    # Use global routing for nodes without manual routes",
                    "    ns.Ipv4GlobalRoutingHelper.PopulateRoutingTables()",
                    "",
                ])
            else:
                lines.extend([
                    "    # NOTE: Skipping GlobalRoutingHelper due to complex switch topology",
                    "    # Multiple routers on same switch segment can cause routing issues",
                    "    # Consider configuring manual routes for proper connectivity",
                    "    print('WARNING: GlobalRoutingHelper skipped - complex switch topology')",
                    "    print('         Configure manual routes for full connectivity')",
                    "",
                ])
                
                # Add default routes for hosts that don't have manual routing
                lines.extend([
                    "    # Set up default routes for hosts without manual routing",
                ])
                for node_id, node in network.nodes.items():
                    if node.node_type != NodeType.HOST:
                        continue
                    if node.routing_mode == RoutingMode.MANUAL and node.routing_table:
                        continue  # Already has manual routes
                    
                    node_idx = self._node_index_map.get(node_id, 0)
                    
                    # Find the router this host is connected to
                    for link_idx, (link_id, link) in enumerate(network.links.items()):
                        connected_node_id = None
                        host_port_id = None
                        router_port_id = None
                        
                        if link.source_node_id == node_id:
                            connected_node_id = link.target_node_id
                            host_port_id = link.source_port_id
                            router_port_id = link.target_port_id
                        elif link.target_node_id == node_id:
                            connected_node_id = link.source_node_id
                            host_port_id = link.target_port_id
                            router_port_id = link.source_port_id
                        else:
                            continue
                        
                        connected_node = network.nodes.get(connected_node_id)
                        if not connected_node:
                            continue
                        
                        # If connected to a router, set that as default gateway
                        if connected_node.node_type == NodeType.ROUTER:
                            gateway_ip, _ = self._get_port_ip(connected_node, router_port_id)
                            if gateway_ip:
                                lines.extend([
                                    f"    # Default gateway for {node.name} -> {connected_node.name}",
                                    f"    ipv4_{node_idx} = nodes.Get({node_idx}).GetObject[ns.Ipv4]()",
                                    f"    static_routing_{node_idx} = ipv4_{node_idx}.GetRoutingProtocol().GetObject[ns.Ipv4StaticRouting]()",
                                    f"    static_routing_{node_idx}.SetDefaultRoute(ns.Ipv4Address('{gateway_ip}'), 1)",
                                ])
                            break
                
                lines.append("")
        
        elif use_global_routing:
            # Use global routing - automatically computes shortest paths
            lines.extend([
                "    # Enable global routing (automatically computes routes)",
                "    ns.Ipv4GlobalRoutingHelper.PopulateRoutingTables()",
                "    print('Routing tables populated via global routing')",
                "",
            ])
        elif has_switches and routers_on_switches > 1:
            # Complex topology - warn about routing
            lines.extend([
                "    # WARNING: Complex switch topology with multiple routers",
                "    # GlobalRoutingHelper cannot handle this configuration",
                "    # Please configure manual routes on routers for connectivity",
                "    print('WARNING: Multiple routers connected to switch')",
                "    print('         GlobalRoutingHelper cannot compute routes')",
                "    print('         Configure manual static routes for connectivity')",
                "",
            ])
        else:
            lines.extend([
                "    # No routers - no explicit routing needed",
                "    # (direct links or bridged network)",
                "",
            ])
        
        # Print routing tables
        if has_routers or has_manual_routing:
            lines.extend([
                "    # Print routing tables",
                "    print('\\n' + '=' * 60)",
                "    print('ROUTING TABLES')",
                "    print('=' * 60)",
                "",
            ])
            
            # Print routing info for each node
            for node_id, node in network.nodes.items():
                node_idx = self._node_index_map.get(node_id, 0)
                
                lines.append(f"    print(f'\\nNode {node_idx} ({node.name}):')")
                lines.append(f"    print('-' * 40)")
                
                if node.routing_mode == RoutingMode.MANUAL and node.routing_table:
                    # Print manually configured routes
                    lines.append(f"    print('  [Manual Routing Mode]')")
                    for route in node.routing_table:
                        if route.enabled:
                            gw_str = "direct" if route.is_direct else route.gateway
                            lines.append(f"    print('  {route.cidr} via {gw_str} (if{route.interface})')")
                else:
                    # Print auto-computed routes
                    lines.append(f"    print('  [Auto Routing Mode]')")
                    
                    # Find all links connected to this node and get their subnets
                    for link_idx, (link_id, link) in enumerate(network.links.items()):
                        is_source = link.source_node_id == node_id
                        is_target = link.target_node_id == node_id
                        
                        if not (is_source or is_target):
                            continue
                        
                        # Skip links to switches - they don't have IP subnets directly
                        other_node_id = link.target_node_id if is_source else link.source_node_id
                        other_node = network.nodes.get(other_node_id)
                        if other_node and other_node.node_type == NodeType.SWITCH:
                            # For switch connections, get subnet from the switch segment
                            lines.append(f"    print('  (switch segment) via interface {link_idx}')")
                            continue
                        
                        # Get the port for this node on this link
                        port_id = link.source_port_id if is_source else link.target_port_id
                        ip, mask = self._get_port_ip(node, port_id)
                        
                        if ip:
                            # Use the actual IP subnet
                            parts = ip.split('.')
                            subnet = f"{parts[0]}.{parts[1]}.{parts[2]}.0"
                            lines.append(f"    print('  {subnet}/24 via direct (interface {link_idx})')")
                        else:
                            # Use auto-assigned subnet
                            lines.append(f"    print(f'  10.1.{link_idx + 1}.0/24 via direct (interface {link_idx})')")
                
                lines.append("")
            
            lines.append("    print()")
        
        lines.append("")
        return "\n".join(lines)
    
    def _generate_applications(self, network: NetworkModel, sim_config: SimulationConfig) -> str:
        """Generate traffic applications."""
        lines = [
            "    # ============================================",
            "    # Create Applications (Traffic Generators)",
            "    # ============================================",
            "",
        ]
        
        if not sim_config.flows:
            lines.extend([
                "    # No traffic flows configured",
                "    # Add flows in the GUI to generate traffic",
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
            
            lines.append(f"    # Flow {flow_idx}: {flow.name} ({source_name} -> {target_name})")
            
            if flow.application == TrafficApplication.ECHO:
                lines.extend(self._generate_echo_application(
                    flow_idx, flow, source_idx, target_idx, network
                ))
            else:
                # Stub for other application types
                lines.extend([
                    f"    # TODO: {flow.application.value} application not yet implemented",
                    f"    # Supported types: echo",
                    f"    # Future: onoff, bulk, ping",
                    "",
                ])
        
        return "\n".join(lines)
    
    def _generate_echo_application(
        self, 
        flow_idx: int, 
        flow: TrafficFlow, 
        source_idx: int, 
        target_idx: int,
        network: NetworkModel
    ) -> list[str]:
        """Generate UDP Echo client/server application."""
        # Find the interface address for the target node
        # We need to find which link connects to the target (directly or through switch)
        target_link_idx = None
        interface_idx = 0  # Default to first interface
        
        target_node = network.nodes.get(flow.target_node_id)
        
        for idx, (link_id, link) in enumerate(network.links.items()):
            link_source = network.nodes.get(link.source_node_id)
            link_target = network.nodes.get(link.target_node_id)
            
            # Check if target node is directly connected to this link
            if link.target_node_id == flow.target_node_id:
                # Target is the "target" side of the link
                target_is_switch = link_target and link_target.node_type in (NodeType.SWITCH,)
                source_is_switch = link_source and link_source.node_type in (NodeType.SWITCH,)
                
                if source_is_switch:
                    # Link is: switch -> target_host
                    # IP is assigned to host only (index 0 in the single-device container)
                    target_link_idx = idx
                    interface_idx = 0
                else:
                    # Link is: host -> target_host (direct)
                    target_link_idx = idx
                    interface_idx = 1
                break
            elif link.source_node_id == flow.target_node_id:
                # Target is the "source" side of the link
                target_is_switch = link_source and link_source.node_type in (NodeType.SWITCH,)
                source_is_switch = link_target and link_target.node_type in (NodeType.SWITCH,)
                
                if source_is_switch:
                    # Link is: target_host -> switch
                    # IP is assigned to host only (index 0 in the single-device container)
                    target_link_idx = idx
                    interface_idx = 0
                else:
                    # Link is: target_host -> host (direct)
                    target_link_idx = idx
                    interface_idx = 0
                break
        
        if target_link_idx is None:
            return [f"    # Flow {flow_idx}: Cannot find interface for target node", ""]
        
        port = 9000 + flow_idx
        
        lines = [
            f"    # UDP Echo Server on node {target_idx}",
            f"    echo_server{flow_idx} = ns.UdpEchoServerHelper({port})",
            f"    server_apps{flow_idx} = echo_server{flow_idx}.Install(nodes.Get({target_idx}))",
            f"    server_apps{flow_idx}.Start(ns.Seconds({flow.start_time - 0.5}))",
            f"    server_apps{flow_idx}.Stop(ns.Seconds({flow.stop_time + 0.5}))",
            "",
            f"    # UDP Echo Client on node {source_idx}",
            f"    target_addr{flow_idx} = interfaces{target_link_idx}.GetAddress({interface_idx})",
            f"    print(f'Flow {flow_idx}: Sending to {{target_addr{flow_idx}}}:{port}')",
            f"    remote_addr{flow_idx} = ns.InetSocketAddress(target_addr{flow_idx}, {port})",
            f"    echo_client{flow_idx} = ns.UdpEchoClientHelper(remote_addr{flow_idx}.ConvertTo())",
            f"    echo_client{flow_idx}.SetAttribute('MaxPackets', ns.UintegerValue({flow.echo_packets}))",
            f"    echo_client{flow_idx}.SetAttribute('Interval', ns.TimeValue(ns.Seconds({flow.echo_interval})))",
            f"    echo_client{flow_idx}.SetAttribute('PacketSize', ns.UintegerValue({flow.packet_size}))",
            f"    client_apps{flow_idx} = echo_client{flow_idx}.Install(nodes.Get({source_idx}))",
            f"    client_apps{flow_idx}.Start(ns.Seconds({flow.start_time}))",
            f"    client_apps{flow_idx}.Stop(ns.Seconds({flow.stop_time}))",
            "",
            "    # ----------------------------------------",
            "    # Alternative traffic generators (commented out):",
            "    # ----------------------------------------",
            "    # OnOff Application (constant bitrate with on/off periods):",
            "    # onoff = ns.OnOffHelper('ns3::UdpSocketFactory',",
            "    #     ns.InetSocketAddress(target_addr, port))",
            "    # onoff.SetAttribute('DataRate', ns.StringValue('1Mbps'))",
            "    # onoff.SetAttribute('PacketSize', ns.UintegerValue(1024))",
            "    #",
            "    # Bulk Send Application (TCP bulk transfer):",
            "    # bulk = ns.BulkSendHelper('ns3::TcpSocketFactory',",
            "    #     ns.InetSocketAddress(target_addr, port))",
            "    # bulk.SetAttribute('MaxBytes', ns.UintegerValue(0))  # unlimited",
            "    #",
            "    # Packet Sink (receiver for OnOff/BulkSend):",
            "    # sink = ns.PacketSinkHelper('ns3::UdpSocketFactory',",
            "    #     ns.InetSocketAddress(ns.Ipv4Address.GetAny(), port))",
            "    # ----------------------------------------",
            "",
        ]
        return lines
    
    def _generate_tracing(self, sim_config: SimulationConfig, output_dir: str) -> str:
        """Generate tracing/logging code."""
        lines = [
            "    # ============================================",
            "    # Setup Tracing and Monitoring",
            "    # ============================================",
            "",
            "    # Packet trace callback for GUI visualization",
            "    packet_uid_counter = [0]  # Use list for mutable closure",
            "    ",
            "    def trace_tx(context, packet):",
            "        # Parse context to get node and device",
            "        # Context format: /NodeList/n/DeviceList/d/...",
            "        try:",
            "            parts = context.split('/')",
            "            node_idx = int(parts[2]) if len(parts) > 2 else 0",
            "            dev_idx = int(parts[4]) if len(parts) > 4 else 0",
            "            time_ns = ns.Simulator.Now().GetNanoSeconds()",
            "            size = packet.GetSize()",
            "            uid = packet_uid_counter[0]",
            "            packet_uid_counter[0] += 1",
            "            # Format: PKT|time_ns|event|node|device|size|src_node|dst_node|link_id|protocol",
            "            print(f'PKT|{time_ns}|TX|{node_idx}|{dev_idx}|{size}|-1|-1||UDP')",
            "        except:",
            "            pass",
            "    ",
            "    def trace_rx(context, packet):",
            "        try:",
            "            parts = context.split('/')",
            "            node_idx = int(parts[2]) if len(parts) > 2 else 0",
            "            dev_idx = int(parts[4]) if len(parts) > 4 else 0",
            "            time_ns = ns.Simulator.Now().GetNanoSeconds()",
            "            size = packet.GetSize()",
            "            print(f'PKT|{time_ns}|RX|{node_idx}|{dev_idx}|{size}|-1|-1||UDP')",
            "        except:",
            "            pass",
            "    ",
            "    def trace_drop(context, packet):",
            "        try:",
            "            parts = context.split('/')",
            "            node_idx = int(parts[2]) if len(parts) > 2 else 0",
            "            dev_idx = int(parts[4]) if len(parts) > 4 else 0",
            "            time_ns = ns.Simulator.Now().GetNanoSeconds()",
            "            size = packet.GetSize()",
            "            print(f'PKT|{time_ns}|DROP|{node_idx}|{dev_idx}|{size}|-1|-1||')",
            "        except:",
            "            pass",
            "    ",
            "    # Connect trace callbacks",
            "    # Note: In ns-3 Python bindings, we use Config.Connect or device-specific callbacks",
            "    # For now, we'll use the MacTx and MacRx callbacks if available",
            "    try:",
            "        ns.Config.ConnectWithoutContext(",
            "            '/NodeList/*/DeviceList/*/$ns3::PointToPointNetDevice/MacTx',",
            "            ns.MakeCallback(trace_tx))",
            "        ns.Config.ConnectWithoutContext(",
            "            '/NodeList/*/DeviceList/*/$ns3::PointToPointNetDevice/MacRx',",
            "            ns.MakeCallback(trace_rx))",
            "    except Exception as e:",
            "        print(f'Note: Could not connect packet trace callbacks: {e}')",
            "",
        ]
        
        if sim_config.enable_ascii_trace:
            lines.extend([
                "    # ASCII Trace",
                f"    ascii_trace = ns.AsciiTraceHelper()",
                f"    p2p.EnableAsciiAll(ascii_trace.CreateFileStream('{output_dir}/trace.tr'))",
                "",
            ])
        
        if sim_config.enable_pcap:
            lines.extend([
                "    # PCAP Trace (packet capture)",
                f"    p2p.EnablePcapAll('{output_dir}/capture')",
                "",
            ])
        
        if sim_config.enable_flow_monitor:
            lines.extend([
                "    # Flow Monitor for statistics",
                "    flow_helper = ns.FlowMonitorHelper()",
                "    flow_monitor = flow_helper.InstallAll()",
                "",
            ])
        
        return "\n".join(lines)
    
    def _generate_simulation_run(self, sim_config: SimulationConfig, output_dir: str) -> str:
        """Generate simulation run code."""
        lines = [
            "    # ============================================",
            "    # Run Simulation",
            "    # ============================================",
            f"    ns.Simulator.Stop(ns.Seconds({sim_config.duration}))",
            "",
            f"    print('Starting simulation for {sim_config.duration} seconds...')",
            "    print()",
            "",
            "    ns.Simulator.Run()",
            "",
        ]
        
        if sim_config.enable_flow_monitor:
            lines.extend([
                "    # ============================================",
                "    # Collect and Print Statistics",
                "    # ============================================",
                "    print('\\n' + '='*60)",
                "    print('SIMULATION RESULTS')",
                "    print('='*60)",
                "",
                "    flow_monitor.CheckForLostPackets()",
                "    classifier = flow_helper.GetClassifier()",
                "    stats = flow_monitor.GetFlowStats()",
                "",
                "    print(f'\\nFlow Statistics:')",
                "    print('-'*60)",
                "",
                "    for flow_id, flow_stats in stats:",
                "        # Get flow classifier info",
                "        t = classifier.FindFlow(flow_id)",
                "        ",
                "        proto = 'UDP' if t.protocol == 17 else 'TCP' if t.protocol == 6 else f'Proto-{t.protocol}'",
                "        ",
                "        print(f'Flow {flow_id} ({proto})')",
                "        print(f'  {t.sourceAddress}:{t.sourcePort} -> {t.destinationAddress}:{t.destinationPort}')",
                "        print(f'  Tx Packets: {flow_stats.txPackets}')",
                "        print(f'  Rx Packets: {flow_stats.rxPackets}')",
                "        print(f'  Tx Bytes:   {flow_stats.txBytes}')",
                "        print(f'  Rx Bytes:   {flow_stats.rxBytes}')",
                "        ",
                "        if flow_stats.rxPackets > 0:",
                "            # Calculate throughput",
                "            duration = (flow_stats.timeLastRxPacket.GetSeconds() - ",
                "                       flow_stats.timeFirstTxPacket.GetSeconds())",
                "            if duration > 0:",
                "                throughput = (flow_stats.rxBytes * 8) / duration / 1e6",
                "                print(f'  Throughput: {throughput:.2f} Mbps')",
                "            ",
                "            # Calculate delay",
                "            delay = flow_stats.delaySum.GetSeconds() / flow_stats.rxPackets * 1000",
                "            print(f'  Mean Delay: {delay:.2f} ms')",
                "            ",
                "            # Calculate jitter",
                "            if flow_stats.rxPackets > 1:",
                "                jitter = flow_stats.jitterSum.GetSeconds() / (flow_stats.rxPackets - 1) * 1000",
                "                print(f'  Mean Jitter: {jitter:.2f} ms')",
                "        ",
                "        lost = flow_stats.txPackets - flow_stats.rxPackets",
                "        if flow_stats.txPackets > 0:",
                "            loss_pct = (lost / flow_stats.txPackets) * 100",
                "            print(f'  Lost Packets: {lost} ({loss_pct:.1f}%)')",
                "        print()",
                "",
                "    # Save flow monitor results to XML",
                f"    flow_monitor.SerializeToXmlFile('{output_dir}/flowmon-results.xml', True, True)",
                f"    print('Flow monitor results saved to: {output_dir}/flowmon-results.xml')",
                "",
            ])
        
        lines.extend([
            "    ns.Simulator.Destroy()",
            "    print('\\nSimulation completed successfully.')",
            "",
        ])
        
        return "\n".join(lines)
    
    def _generate_main_function_end(self) -> str:
        """Generate main function end."""
        return '''
    return 0
'''
    
    def _generate_main_call(self) -> str:
        """Generate main function call."""
        return '''
if __name__ == '__main__':
    sys.exit(main())
'''


def generate_ns3_script(
    network: NetworkModel, 
    sim_config: SimulationConfig,
    output_dir: str = "."
) -> str:
    """
    Convenience function to generate an ns-3 script.
    
    Args:
        network: Network topology model
        sim_config: Simulation configuration
        output_dir: Output directory for trace files
        
    Returns:
        Generated Python script as string
    """
    generator = NS3ScriptGenerator()
    return generator.generate(network, sim_config, output_dir)
