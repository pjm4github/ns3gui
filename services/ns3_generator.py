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
        # Normalize output_dir to use forward slashes (for Linux compatibility)
        # Windows paths with backslashes would be interpreted as escape sequences
        output_dir = output_dir.replace('\\', '/')
        
        # Build node index mapping (node_id -> integer index)
        real_nodes = [
            (node_id, node) for node_id, node in network.nodes.items()
        ]
        self._node_index_map = {
            node_id: idx 
            for idx, (node_id, node) in enumerate(real_nodes)
        }
        
        # Initialize link tracking (will be populated in _generate_channels)
        self._link_device_map = {}    # link_id -> device_idx
        self._wifi_link_ids = set()   # Track WiFi links that are skipped
        self._wired_device_count = 0  # Count of wired devices created
        
        # Initialize WiFi tracking (will be populated in _generate_wifi_setup)
        self._wifi_sta_devices_var = None
        self._wifi_sta_count = 0
        self._wifi_ap_devices_var = None
        self._wifi_ap_count = 0
        
        # Check if any flows use APPLICATION nodes
        has_app_flows = any(
            flow.app_enabled and flow.app_node_id
            for flow in sim_config.flows
        )
        
        sections = [
            self._generate_header(network, sim_config),
            self._generate_imports(has_app_flows),
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
    
    def _generate_imports(self, has_app_flows: bool = False) -> str:
        """Generate ns-3 import statements."""
        lines = [
            '',
            '# NS-3 imports (ns-3.45+ with cppyy bindings)',
            'from ns import ns',
            '',
            'import sys',
        ]
        
        if has_app_flows:
            lines.extend([
                '',
                '# Import ApplicationBase for custom socket applications',
                'from app_base import ApplicationBase',
            ])
        
        return '\n'.join(lines) + '\n'
    
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
        # Count only real network nodes (not APPLICATION nodes)
        real_node_count = len(self._node_index_map)
        
        lines = [
            "    # ============================================",
            "    # Create Nodes",
            "    # ============================================",
            f"    nodes = ns.NodeContainer()",
            f"    nodes.Create({real_node_count})",
            "",
            "    # Node mapping:",
        ]
        
        for node_id, idx in self._node_index_map.items():
            node = network.nodes[node_id]
            lines.append(f"    # Node {idx}: {node.name} ({node.node_type.name})")
        
        # Note nodes with application scripts
        app_script_nodes = [n for n in network.nodes.values() if n.has_app_script]
        if app_script_nodes:
            lines.append("")
            lines.append("    # Nodes with custom application scripts:")
            for node in app_script_nodes:
                if node.id in self._node_index_map:
                    lines.append(f"    # Node {self._node_index_map[node.id]}: {node.name} has custom app script")
        
        lines.append("")
        return "\n".join(lines)
    
    def _generate_channels(self, network: NetworkModel) -> str:
        """Generate channel/link configuration."""
        # Check if we have WiFi nodes
        has_wifi = any(
            node.node_type in (NodeType.STATION, NodeType.ACCESS_POINT)
            for node in network.nodes.values()
        )
        
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
        
        # Generate WiFi setup if we have WiFi nodes
        if has_wifi:
            lines.extend(self._generate_wifi_setup(network))
        
        # Track which links are actually created (non-WiFi) and their mapping
        # This maps original link_id to the device index used in generated code
        self._link_device_map = {}  # link_id -> device_idx
        self._wifi_link_ids = set()  # Track WiFi links that are skipped
        
        device_idx = 0  # Counter for created devices
        
        for link_id, link in network.links.items():
            source_idx = self._node_index_map.get(link.source_node_id, 0)
            target_idx = self._node_index_map.get(link.target_node_id, 0)
            
            source_node = network.nodes.get(link.source_node_id)
            target_node = network.nodes.get(link.target_node_id)
            
            source_name = source_node.name if source_node else "unknown"
            target_name = target_node.name if target_node else "unknown"
            
            # Check if this is a WiFi link
            # A link is WiFi ONLY if:
            # 1. Explicitly marked as WiFi channel type, OR
            # 2. It connects a STATION to another WiFi node (STATION or ACCESS_POINT)
            # 
            # An AP-to-Router/Switch/Host link is a WIRED uplink, not WiFi
            source_is_station = source_node and source_node.node_type == NodeType.STATION
            target_is_station = target_node and target_node.node_type == NodeType.STATION
            source_is_ap = source_node and source_node.node_type == NodeType.ACCESS_POINT
            target_is_ap = target_node and target_node.node_type == NodeType.ACCESS_POINT
            
            is_wifi_link = (
                link.channel_type == ChannelType.WIFI or
                (source_is_station and (target_is_station or target_is_ap)) or
                (target_is_station and (source_is_station or source_is_ap))
            )
            
            # Skip WiFi links here - they're handled in _generate_wifi_setup
            if is_wifi_link:
                self._wifi_link_ids.add(link_id)
                continue
            
            # Store the mapping from link_id to device index
            self._link_device_map[link_id] = device_idx
            
            # Check if either end is a switch - must use CSMA for bridging
            source_is_switch = source_node and source_node.node_type == NodeType.SWITCH
            target_is_switch = target_node and target_node.node_type == NodeType.SWITCH
            use_csma = source_is_switch or target_is_switch or link.channel_type == ChannelType.CSMA
            
            lines.append(f"    # Link {device_idx}: {source_name} <-> {target_name}")
            
            if use_csma:
                # CSMA required for switch bridging (P2P doesn't support SendFrom)
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
                # Point-to-point for direct host-to-host links
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
            
            device_idx += 1  # Increment for next device
        
        # Store the count for use in IP assignment
        self._wired_device_count = device_idx
        
        return "\n".join(lines)
    
    def _generate_wifi_setup(self, network: NetworkModel) -> list[str]:
        """Generate WiFi network setup code."""
        lines = [
            "    # ----------------------------------------",
            "    # WiFi Network Setup",
            "    # ----------------------------------------",
            "",
        ]
        
        # Find all APs and stations
        ap_nodes = []
        sta_nodes = []
        
        for node_id, node in network.nodes.items():
            idx = self._node_index_map.get(node_id, 0)
            if node.node_type == NodeType.ACCESS_POINT:
                ap_nodes.append((idx, node))
            elif node.node_type == NodeType.STATION:
                sta_nodes.append((idx, node))
        
        if not ap_nodes and not sta_nodes:
            return []
        
        # Get WiFi settings from the first AP (or use defaults)
        wifi_standard = "802.11n"
        wifi_ssid = "ns3-wifi"
        wifi_channel = 1
        wifi_band = "2.4GHz"
        
        if ap_nodes:
            ap_node = ap_nodes[0][1]
            wifi_standard = getattr(ap_node, 'wifi_standard', '802.11n')
            wifi_ssid = getattr(ap_node, 'wifi_ssid', 'ns3-wifi')
            wifi_channel = getattr(ap_node, 'wifi_channel', 1)
            wifi_band = getattr(ap_node, 'wifi_band', '2.4GHz')
        
        # Map wifi standard to ns-3 enum
        wifi_standard_map = {
            "802.11a": "WIFI_STANDARD_80211a",
            "802.11b": "WIFI_STANDARD_80211b",
            "802.11g": "WIFI_STANDARD_80211g",
            "802.11n": "WIFI_STANDARD_80211n",
            "802.11ac": "WIFI_STANDARD_80211ac",
            "802.11ax": "WIFI_STANDARD_80211ax",
        }
        ns3_standard = wifi_standard_map.get(wifi_standard, "WIFI_STANDARD_80211n")
        
        lines.extend([
            f"    # WiFi Configuration: {wifi_standard}, SSID: {wifi_ssid}",
            f"    wifi_ssid = ns.Ssid('{wifi_ssid}')",
            "",
            "    # Create WiFi channel and PHY",
            "    wifi_channel = ns.YansWifiChannelHelper.Default()",
            "    wifi_phy = ns.YansWifiPhyHelper()",
            "    wifi_phy.SetChannel(wifi_channel.Create())",
            "",
            "    # WiFi helper",
            "    wifi = ns.WifiHelper()",
            f"    wifi.SetStandard(ns.{ns3_standard})",
            "    wifi.SetRemoteStationManager('ns3::AarfWifiManager')",
            "",
            "    # MAC configuration",
            "    wifi_mac = ns.WifiMacHelper()",
            "",
        ])
        
        # Setup station nodes
        if sta_nodes:
            sta_indices = [idx for idx, _ in sta_nodes]
            lines.extend([
                "    # WiFi Stations",
                "    sta_nodes = ns.NodeContainer()",
            ])
            for idx in sta_indices:
                lines.append(f"    sta_nodes.Add(nodes.Get({idx}))")
            
            lines.extend([
                "",
                "    wifi_mac.SetType('ns3::StaWifiMac',",
                "        'Ssid', ns.SsidValue(wifi_ssid),",
                "        'ActiveProbing', ns.BooleanValue(False))",
                "    sta_devices = wifi.Install(wifi_phy, wifi_mac, sta_nodes)",
                "    all_devices.append(sta_devices)",
                "",
            ])
            
            # Store WiFi device info for IP assignment
            self._wifi_sta_devices_var = "sta_devices"
            self._wifi_sta_count = len(sta_nodes)
        
        # Setup AP nodes
        if ap_nodes:
            ap_indices = [idx for idx, _ in ap_nodes]
            lines.extend([
                "    # WiFi Access Points",
                "    ap_nodes = ns.NodeContainer()",
            ])
            for idx in ap_indices:
                lines.append(f"    ap_nodes.Add(nodes.Get({idx}))")
            
            lines.extend([
                "",
                "    wifi_mac.SetType('ns3::ApWifiMac',",
                "        'Ssid', ns.SsidValue(wifi_ssid))",
                "    ap_devices = wifi.Install(wifi_phy, wifi_mac, ap_nodes)",
                "    all_devices.append(ap_devices)",
                "",
            ])
            
            self._wifi_ap_devices_var = "ap_devices"
            self._wifi_ap_count = len(ap_nodes)
        
        # Setup mobility (required for WiFi)
        lines.extend([
            "    # Mobility (required for WiFi)",
            "    mobility = ns.MobilityHelper()",
            "    mobility.SetMobilityModel('ns3::ConstantPositionMobilityModel')",
            "",
        ])
        
        if sta_nodes:
            lines.append("    mobility.Install(sta_nodes)")
        if ap_nodes:
            lines.append("    mobility.Install(ap_nodes)")
        
        lines.append("")
        
        return lines
    
    def _generate_internet_stack(self, network: NetworkModel) -> str:
        """Generate IP stack installation."""
        # Find switch nodes that should act as bridges
        # STATION and ACCESS_POINT get IP stack (they're like hosts/routers for L3)
        switch_indices = []
        host_indices = []
        
        for node_id, node in network.nodes.items():
            idx = self._node_index_map.get(node_id, 0)
            if node.node_type == NodeType.SWITCH:
                switch_indices.append(idx)
            else:
                # HOST, ROUTER, STATION, ACCESS_POINT all get IP stack
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
                "    # Install Internet stack only on hosts/routers/WiFi nodes (not L2 switches)",
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
                if switch_node.node_type != NodeType.SWITCH:
                    continue
                
                switch_idx = self._node_index_map.get(switch_id, 0)
                
                # Find all links connected to this switch
                connected_link_info = []
                for link_id, link in network.links.items():
                    # Skip WiFi links (they don't go through switches)
                    if link_id in self._wifi_link_ids:
                        continue
                    
                    # Get the device index from our mapping
                    device_idx = self._link_device_map.get(link_id)
                    if device_idx is None:
                        continue
                    
                    if link.source_node_id == switch_id or link.target_node_id == switch_id:
                        connected_link_info.append((device_idx, link.source_node_id == switch_id))
                
                if connected_link_info:
                    lines.append(f"    # Bridge devices on switch node {switch_idx} ({switch_node.name})")
                    lines.append(f"    switch{switch_idx}_devices = ns.NetDeviceContainer()")
                    
                    for device_idx, is_source in connected_link_info:
                        # Device index: 0 if switch is source, 1 if switch is target
                        dev_idx = 0 if is_source else 1
                        lines.append(f"    switch{switch_idx}_devices.Add(devices{device_idx}.Get({dev_idx}))")
                    
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
        1. Putting all hosts on the same switch segment on the same subnet
        2. Respecting user-defined IP addresses when present
        3. Using auto-assignment for unconfigured interfaces
        4. Handling P2P links separately from switch segments
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
        
        # Track which links have been processed (for switch segments)
        processed_links = set()
        
        # Use a subnet counter for auto-assignment
        auto_subnet_counter = 1
        
        # First, handle switch segments - all hosts on same switch should be on same subnet
        if has_switches:
            switch_segments = self._analyze_switch_segments(network)
            
            for switch_id, connected_nodes in switch_segments.items():
                switch_node = network.nodes.get(switch_id)
                switch_name = switch_node.name if switch_node else "switch"
                
                if not connected_nodes:
                    continue
                
                # Determine subnet for this switch segment
                segment_subnet, segment_mask = self._determine_switch_subnet(network, connected_nodes)
                
                if not segment_subnet:
                    # Auto-assign subnet for this switch segment
                    segment_subnet = f"10.1.{auto_subnet_counter}.0"
                    auto_subnet_counter += 1
                
                lines.extend([
                    f"    # ----------------------------------------",
                    f"    # Switch segment: {switch_name}",
                    f"    # All hosts on this switch share subnet {segment_subnet}/24",
                    f"    # ----------------------------------------",
                    f"    ipv4.SetBase(ns.Ipv4Address('{segment_subnet}'), ns.Ipv4Mask('255.255.255.0'))",
                    "",
                ])
                
                # Assign IPs to all HOST nodes connected to this switch (skip other switches)
                host_counter = 1
                for node_id, port_id, link_id in connected_nodes:
                    # Mark this link as processed
                    processed_links.add(link_id)
                    
                    # Skip WiFi links
                    if link_id in self._wifi_link_ids:
                        continue
                    
                    host_node = network.nodes.get(node_id)
                    if not host_node:
                        continue
                    
                    # Skip if this "connected node" is also a switch (switch-to-switch link)
                    if host_node.node_type == NodeType.SWITCH:
                        continue
                    
                    # Get the device index from our mapping
                    device_idx = self._link_device_map.get(link_id)
                    if device_idx is None:
                        continue
                    
                    link = network.links[link_id]
                    
                    # Determine which device index is the host (not the switch)
                    if link.source_node_id == switch_id:
                        dev_idx = 1  # Target is host
                    else:
                        dev_idx = 0  # Source is host
                    
                    # Check for user-configured IP on the SAME subnet as segment
                    user_ip, _ = self._get_port_ip(host_node, port_id)
                    use_user_ip = False
                    
                    if user_ip:
                        # Check if user IP is on the same subnet as segment
                        parts = user_ip.split('.')
                        user_subnet = f"{parts[0]}.{parts[1]}.{parts[2]}.0"
                        if user_subnet == segment_subnet:
                            use_user_ip = True
                            host_octet = parts[3]
                    
                    if use_user_ip:
                        # Use user IP (already on correct subnet)
                        lines.extend([
                            f"    # {host_node.name}: using configured IP {user_ip}",
                            f"    host_dev{device_idx} = ns.NetDeviceContainer()",
                            f"    host_dev{device_idx}.Add(devices{device_idx}.Get({dev_idx}))",
                            f"    ipv4.SetBase(ns.Ipv4Address('{segment_subnet}'), ns.Ipv4Mask('255.255.255.0'), ns.Ipv4Address('0.0.0.{host_octet}'))",
                            f"    interfaces{device_idx} = ipv4.Assign(host_dev{device_idx})",
                            f"    all_interfaces.append(interfaces{device_idx})",
                        ])
                    else:
                        # Auto-assign IP on switch segment (incrementing)
                        lines.extend([
                            f"    # {host_node.name}: auto-assigned IP {segment_subnet.rsplit('.', 1)[0]}.{host_counter}",
                            f"    host_dev{device_idx} = ns.NetDeviceContainer()",
                            f"    host_dev{device_idx}.Add(devices{device_idx}.Get({dev_idx}))",
                            f"    interfaces{device_idx} = ipv4.Assign(host_dev{device_idx})",
                            f"    all_interfaces.append(interfaces{device_idx})",
                        ])
                        host_counter += 1
                    
                    lines.append("")
        
        # Now handle remaining links (P2P links not connected to switches)
        for link_id, link in network.links.items():
            if link_id in processed_links:
                continue  # Already handled as part of switch segment
            
            # Skip WiFi links - they're handled separately
            if link_id in self._wifi_link_ids:
                continue
            
            # Get the device index from our mapping
            idx = self._link_device_map.get(link_id)
            if idx is None:
                continue  # Link wasn't created (shouldn't happen)
            
            source_node = network.nodes.get(link.source_node_id)
            target_node = network.nodes.get(link.target_node_id)
            
            source_is_switch = source_node and source_node.node_type == NodeType.SWITCH
            target_is_switch = target_node and target_node.node_type == NodeType.SWITCH
            
            if source_is_switch and target_is_switch:
                # Switch-to-switch link, no IP assignment
                lines.append(f"    # Link {idx}: Switch-to-switch, no IP assignment")
                continue
            
            # Direct point-to-point link (no switch involved)
            source_ip, source_mask = self._get_port_ip(source_node, link.source_port_id) if source_node else (None, None)
            target_ip, target_mask = self._get_port_ip(target_node, link.target_port_id) if target_node else (None, None)
            
            if source_ip and target_ip:
                # Both have user-defined IPs - use source's subnet
                parts = source_ip.split('.')
                subnet = f"{parts[0]}.{parts[1]}.{parts[2]}.0"
                lines.extend([
                    f"    # Link {idx}: Using user-configured IPs: {source_ip} <-> {target_ip}",
                    f"    ipv4.SetBase(ns.Ipv4Address('{subnet}'), ns.Ipv4Mask('{source_mask}'))",
                    f"    interfaces{idx} = ipv4.Assign(devices{idx})",
                    f"    all_interfaces.append(interfaces{idx})",
                ])
            elif source_ip:
                parts = source_ip.split('.')
                subnet = f"{parts[0]}.{parts[1]}.{parts[2]}.0"
                lines.extend([
                    f"    # Link {idx}: Source has configured IP: {source_ip}",
                    f"    ipv4.SetBase(ns.Ipv4Address('{subnet}'), ns.Ipv4Mask('{source_mask}'))",
                    f"    interfaces{idx} = ipv4.Assign(devices{idx})",
                    f"    all_interfaces.append(interfaces{idx})",
                ])
            elif target_ip:
                parts = target_ip.split('.')
                subnet = f"{parts[0]}.{parts[1]}.{parts[2]}.0"
                lines.extend([
                    f"    # Link {idx}: Target has configured IP: {target_ip}",
                    f"    ipv4.SetBase(ns.Ipv4Address('{subnet}'), ns.Ipv4Mask('{target_mask}'))",
                    f"    interfaces{idx} = ipv4.Assign(devices{idx})",
                    f"    all_interfaces.append(interfaces{idx})",
                ])
            else:
                # No user-defined IPs, auto-assign
                subnet = f"10.1.{auto_subnet_counter}.0"
                auto_subnet_counter += 1
                lines.extend([
                    f"    # Link {idx}: Auto-assign subnet {subnet}/24",
                    f"    ipv4.SetBase(ns.Ipv4Address('{subnet}'), ns.Ipv4Mask('255.255.255.0'))",
                    f"    interfaces{idx} = ipv4.Assign(devices{idx})",
                    f"    all_interfaces.append(interfaces{idx})",
                ])
            
            lines.append("")
        
        # Handle WiFi IP assignment if we have WiFi devices
        has_wifi = any(
            node.node_type in (NodeType.STATION, NodeType.ACCESS_POINT)
            for node in network.nodes.values()
        )
        
        if has_wifi:
            wifi_subnet = f"10.1.{auto_subnet_counter}.0"
            auto_subnet_counter += 1
            
            lines.extend([
                "    # ----------------------------------------",
                "    # WiFi Network IP Assignment",
                f"    # All WiFi devices share subnet {wifi_subnet}/24",
                "    # ----------------------------------------",
                f"    ipv4.SetBase(ns.Ipv4Address('{wifi_subnet}'), ns.Ipv4Mask('255.255.255.0'))",
                "",
            ])
            
            # Check if we have sta_devices and ap_devices variables
            if hasattr(self, '_wifi_sta_devices_var') and self._wifi_sta_count > 0:
                lines.extend([
                    "    # Assign IPs to WiFi stations",
                    "    wifi_sta_interfaces = ipv4.Assign(sta_devices)",
                    "    all_interfaces.append(wifi_sta_interfaces)",
                    f"    for i in range({self._wifi_sta_count}):",
                    "        print(f'  WiFi Station {{i}}: {{wifi_sta_interfaces.GetAddress(i)}}')",
                    "",
                ])
            
            if hasattr(self, '_wifi_ap_devices_var') and self._wifi_ap_count > 0:
                lines.extend([
                    "    # Assign IPs to WiFi access points",
                    "    wifi_ap_interfaces = ipv4.Assign(ap_devices)",
                    "    all_interfaces.append(wifi_ap_interfaces)",
                    f"    for i in range({self._wifi_ap_count}):",
                    "        print(f'  WiFi AP {{i}}: {{wifi_ap_interfaces.GetAddress(i)}}')",
                    "",
                ])
        
        # Print IP addresses for reference
        lines.extend([
            "    # Print assigned IP addresses",
            "    print('\\nIP Address Assignment:')",
        ])
        
        for link_id, link in network.links.items():
            # Skip WiFi links
            if link_id in self._wifi_link_ids:
                continue
            
            # Get the device index from our mapping
            idx = self._link_device_map.get(link_id)
            if idx is None:
                continue
            
            source_node = network.nodes.get(link.source_node_id)
            target_node = network.nodes.get(link.target_node_id)
            source_name = source_node.name if source_node else "unknown"
            target_name = target_node.name if target_node else "unknown"
            
            source_is_switch = source_node and source_node.node_type == NodeType.SWITCH
            target_is_switch = target_node and target_node.node_type == NodeType.SWITCH
            
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
            
            # Check if this flow uses a node with a custom app script
            # First check explicit app_enabled flag
            app_enabled = getattr(flow, 'app_enabled', False)
            app_node_id = getattr(flow, 'app_node_id', '')
            
            # If not explicitly set, check if source node has an app script
            if not app_enabled and source_node and source_node.has_app_script:
                app_enabled = True
                app_node_id = source_node.id
                lines.append(f"    # Auto-detected app script on source node")
            
            if app_enabled and app_node_id:
                # Use the node's custom script
                app_node = network.nodes.get(app_node_id)
                if app_node and app_node.has_app_script:
                    lines.append(f"    # Using custom app script from: {app_node.name}")
                    lines.extend(self._generate_app_node_flow(
                        flow_idx, flow, source_idx, target_idx, app_node, network
                    ))
                else:
                    lines.append(f"    # WARNING: Node {app_node_id} has no app script, using default")
                    lines.extend(self._generate_echo_application(
                        flow_idx, flow, source_idx, target_idx, network
                    ))
            elif flow.application == TrafficApplication.ECHO:
                lines.extend(self._generate_echo_application(
                    flow_idx, flow, source_idx, target_idx, network
                ))
            elif flow.application == TrafficApplication.ONOFF:
                lines.extend(self._generate_onoff_application(
                    flow_idx, flow, source_idx, target_idx, network
                ))
            elif flow.application == TrafficApplication.BULK_SEND:
                lines.extend(self._generate_bulk_send_application(
                    flow_idx, flow, source_idx, target_idx, network
                ))
            elif flow.application == TrafficApplication.CUSTOM_SOCKET:
                lines.extend(self._generate_custom_socket_application(
                    flow_idx, flow, source_idx, target_idx, network
                ))
            else:
                # Stub for other application types (ping, etc.)
                lines.extend([
                    f"    # TODO: {flow.application.value} application not yet implemented",
                    f"    # Supported types: echo, onoff, bulk_send, socket",
                    "",
                ])
        
        # Generate socket applications from APPLICATION nodes
        app_lines = self._generate_application_node_sockets(network)
        if app_lines:
            lines.append("")
            lines.extend(app_lines)
        
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
    
    def _generate_onoff_application(
        self, 
        flow_idx: int, 
        flow: TrafficFlow, 
        source_idx: int, 
        target_idx: int,
        network: NetworkModel
    ) -> list[str]:
        """Generate OnOff (constant bitrate) application with PacketSink receiver."""
        # Find the interface address for the target node
        target_link_idx, interface_idx = self._find_target_interface(flow, network)
        
        if target_link_idx is None:
            return [f"    # Flow {flow_idx}: Cannot find interface for target node", ""]
        
        # Use port from flow or default
        port = flow.port if flow.port else 9000 + flow_idx
        
        # Determine socket factory based on protocol
        if flow.protocol == TrafficProtocol.TCP:
            socket_factory = "ns3::TcpSocketFactory"
        else:
            socket_factory = "ns3::UdpSocketFactory"
        
        # Parse data rate - ensure it has units
        data_rate = flow.data_rate or "500kb/s"
        if not any(unit in data_rate.lower() for unit in ['bps', 'b/s', 'kbps', 'kb/s', 'mbps', 'mb/s', 'gbps', 'gb/s']):
            data_rate = f"{data_rate}bps"
        
        packet_size = flow.packet_size or 512
        
        lines = [
            f"    # OnOff Traffic: {flow.name}",
            f"    # Protocol: {flow.protocol.value.upper()}, Rate: {data_rate}, Packet Size: {packet_size}",
            "",
            f"    # PacketSink (receiver) on node {target_idx}",
            f"    sink_addr{flow_idx} = ns.InetSocketAddress(ns.Ipv4Address.GetAny(), {port})",
            f"    sink{flow_idx} = ns.PacketSinkHelper('{socket_factory}', sink_addr{flow_idx}.ConvertTo())",
            f"    sink_apps{flow_idx} = sink{flow_idx}.Install(nodes.Get({target_idx}))",
            f"    sink_apps{flow_idx}.Start(ns.Seconds({max(0, flow.start_time - 0.5)}))",
            f"    sink_apps{flow_idx}.Stop(ns.Seconds({flow.stop_time + 1.0}))",
            "",
            f"    # OnOff (sender) on node {source_idx}",
            f"    target_addr{flow_idx} = interfaces{target_link_idx}.GetAddress({interface_idx})",
            f"    print(f'Flow {flow_idx} ({flow.name}): {{nodes.Get({source_idx})}} -> {{target_addr{flow_idx}}}:{port} @ {data_rate}')",
            f"    remote{flow_idx} = ns.InetSocketAddress(target_addr{flow_idx}, {port})",
            f"    onoff{flow_idx} = ns.OnOffHelper('{socket_factory}', remote{flow_idx}.ConvertTo())",
            f"    onoff{flow_idx}.SetAttribute('DataRate', ns.DataRateValue(ns.DataRate('{data_rate}')))",
            f"    onoff{flow_idx}.SetAttribute('PacketSize', ns.UintegerValue({packet_size}))",
            "    # Constant traffic (always on)",
            f"    onoff{flow_idx}.SetAttribute('OnTime', ns.StringValue('ns3::ConstantRandomVariable[Constant=1]'))",
            f"    onoff{flow_idx}.SetAttribute('OffTime', ns.StringValue('ns3::ConstantRandomVariable[Constant=0]'))",
            f"    onoff_apps{flow_idx} = onoff{flow_idx}.Install(nodes.Get({source_idx}))",
            f"    onoff_apps{flow_idx}.Start(ns.Seconds({flow.start_time}))",
            f"    onoff_apps{flow_idx}.Stop(ns.Seconds({flow.stop_time}))",
            "",
        ]
        return lines
    
    def _generate_bulk_send_application(
        self, 
        flow_idx: int, 
        flow: TrafficFlow, 
        source_idx: int, 
        target_idx: int,
        network: NetworkModel
    ) -> list[str]:
        """Generate BulkSend (TCP max throughput) application with PacketSink receiver."""
        target_link_idx, interface_idx = self._find_target_interface(flow, network)
        
        if target_link_idx is None:
            return [f"    # Flow {flow_idx}: Cannot find interface for target node", ""]
        
        port = flow.port if flow.port else 9000 + flow_idx
        packet_size = flow.packet_size or 512
        
        lines = [
            f"    # BulkSend Traffic: {flow.name}",
            f"    # TCP bulk transfer (maximum throughput)",
            "",
            f"    # PacketSink (receiver) on node {target_idx}",
            f"    sink_addr{flow_idx} = ns.InetSocketAddress(ns.Ipv4Address.GetAny(), {port})",
            f"    sink{flow_idx} = ns.PacketSinkHelper('ns3::TcpSocketFactory', sink_addr{flow_idx}.ConvertTo())",
            f"    sink_apps{flow_idx} = sink{flow_idx}.Install(nodes.Get({target_idx}))",
            f"    sink_apps{flow_idx}.Start(ns.Seconds({max(0, flow.start_time - 0.5)}))",
            f"    sink_apps{flow_idx}.Stop(ns.Seconds({flow.stop_time + 1.0}))",
            "",
            f"    # BulkSend (sender) on node {source_idx}",
            f"    target_addr{flow_idx} = interfaces{target_link_idx}.GetAddress({interface_idx})",
            f"    print(f'Flow {flow_idx} ({flow.name}): BulkSend to {{target_addr{flow_idx}}}:{port}')",
            f"    remote{flow_idx} = ns.InetSocketAddress(target_addr{flow_idx}, {port})",
            f"    bulk{flow_idx} = ns.BulkSendHelper('ns3::TcpSocketFactory', remote{flow_idx}.ConvertTo())",
            f"    bulk{flow_idx}.SetAttribute('SendSize', ns.UintegerValue({packet_size}))",
            f"    bulk{flow_idx}.SetAttribute('MaxBytes', ns.UintegerValue(0))",  # 0 = unlimited
            f"    bulk_apps{flow_idx} = bulk{flow_idx}.Install(nodes.Get({source_idx}))",
            f"    bulk_apps{flow_idx}.Start(ns.Seconds({flow.start_time}))",
            f"    bulk_apps{flow_idx}.Stop(ns.Seconds({flow.stop_time}))",
            "",
        ]
        return lines
    
    def _find_target_interface(self, flow: TrafficFlow, network: NetworkModel) -> tuple:
        """Find the link index and interface index for a flow's target node."""
        target_link_idx = None
        interface_idx = 0
        
        for idx, (link_id, link) in enumerate(network.links.items()):
            link_source = network.nodes.get(link.source_node_id)
            link_target = network.nodes.get(link.target_node_id)
            
            if link.target_node_id == flow.target_node_id:
                source_is_switch = link_source and link_source.node_type in (NodeType.SWITCH,)
                if source_is_switch:
                    target_link_idx = idx
                    interface_idx = 0
                else:
                    target_link_idx = idx
                    interface_idx = 1
                break
            elif link.source_node_id == flow.target_node_id:
                target_is_switch = link_target and link_target.node_type in (NodeType.SWITCH,)
                if target_is_switch:
                    target_link_idx = idx
                    interface_idx = 0
                else:
                    target_link_idx = idx
                    interface_idx = 0
                break
        
        return target_link_idx, interface_idx
    
    def _generate_app_node_flow(
        self,
        flow_idx: int,
        flow: TrafficFlow,
        source_idx: int,
        target_idx: int,
        app_node: NodeModel,
        network: NetworkModel
    ) -> list[str]:
        """Generate a flow using a node's custom app script with ApplicationBase."""
        target_link_idx, interface_idx = self._find_target_interface(flow, network)
        
        if target_link_idx is None:
            return [f"    # Flow {flow_idx}: Cannot find interface for target node", ""]
        
        port = flow.port if flow.port else 9000 + flow_idx
        protocol = "UDP" if flow.protocol == TrafficProtocol.UDP else "TCP"
        
        # Get source and target node names
        source_node = network.nodes.get(flow.source_node_id)
        target_node = network.nodes.get(flow.target_node_id)
        source_name = source_node.name if source_node else f"Node{source_idx}"
        target_name = target_node.name if target_node else f"Node{target_idx}"
        
        # Sanitize app name for class name
        app_class_name = self._sanitize_class_name(app_node.name) + "App"
        module_name = self._sanitize_module_name(app_node.name)
        
        lines = [
            f"    # =========================================================",
            f"    # Flow {flow_idx}: Custom Application from '{app_node.name}'",
            f"    # Source: {source_name} -> Target: {target_name}",
            f"    # =========================================================",
            "",
        ]
        
        # Check if node has a custom script
        if app_node.has_app_script:
            lines.extend(self._generate_custom_app_flow(
                flow_idx, flow, source_idx, target_idx, app_node,
                app_class_name, module_name, protocol, port, 
                target_link_idx, interface_idx, network
            ))
        else:
            # Generate default ApplicationBase usage
            lines.append(f"    # No custom script found, using default ApplicationBase")
            lines.extend(self._generate_default_application_flow(
                flow_idx, flow, source_idx, target_idx, app_node,
                protocol, port, target_link_idx, interface_idx, network
            ))
        
        return lines
    
    def _sanitize_module_name(self, name: str) -> str:
        """Convert a name to a valid Python module name."""
        import re
        # Replace non-alphanumeric with underscore, lowercase
        clean = re.sub(r'[^a-zA-Z0-9]', '_', name).lower()
        # Ensure it doesn't start with a number
        if clean and clean[0].isdigit():
            clean = 'app_' + clean
        return clean or 'custom_app'
    
    def _sanitize_class_name(self, name: str) -> str:
        """Convert a name to a valid Python class name."""
        # Remove invalid characters and convert to CamelCase
        import re
        # Replace non-alphanumeric with underscore
        clean = re.sub(r'[^a-zA-Z0-9]', '_', name)
        # Split and capitalize each part
        parts = clean.split('_')
        return ''.join(part.capitalize() for part in parts if part)
    
    def _generate_custom_app_flow(
        self,
        flow_idx: int,
        flow: TrafficFlow,
        source_idx: int,
        target_idx: int,
        app_node: NodeModel,
        app_class_name: str,
        module_name: str,
        protocol: str,
        port: int,
        target_link_idx: int,
        interface_idx: int,
        network: NetworkModel
    ) -> list[str]:
        """Generate flow code using custom ApplicationBase subclass."""
        # Get node names for config
        source_node = network.nodes.get(flow.source_node_id)
        target_node = network.nodes.get(flow.target_node_id)
        source_name = source_node.name if source_node else f"Node{source_idx}"
        target_name = target_node.name if target_node else f"Node{target_idx}"
        
        # Generate unique app variable name
        app_var = f"custom_app_{flow_idx}"
        
        # Calculate send interval from flow config
        send_interval = getattr(flow, 'socket_send_interval', 1.0)
        if hasattr(flow, 'echo_interval'):
            send_interval = flow.echo_interval
        
        # Calculate number of packets
        num_packets = int((flow.stop_time - flow.start_time) / send_interval)
        if num_packets < 1:
            num_packets = 1
        
        lines = [
            f"    # Custom application from {app_node.name}",
            f"    # Module: {module_name}, Class: {app_class_name}",
            "",
            f"    # Get target IP address",
            f"    target_ip_{flow_idx} = str(interfaces{target_link_idx}.GetAddress({interface_idx}))",
            "",
            f"    # Configuration for the application",
            f"    {app_var}_config = {{",
            f"        'node': nodes.Get({source_idx}),",
            f"        'target_address': target_ip_{flow_idx},",
            f"        'target_port': {port},",
            f"        'protocol': '{protocol}',",
            f"        'start_time': {flow.start_time},",
            f"        'stop_time': {flow.stop_time},",
            f"        'send_interval': {send_interval},",
            f"        'packet_size': {flow.packet_size or 512},",
            f"        'app_name': '{app_node.name}',",
            f"        'source_node_name': '{source_name}',",
            f"        'target_node_name': '{target_name}',",
            f"    }}",
            "",
            f"    # Create and setup the custom application",
            f"    {app_var} = None",
            f"    try:",
            f"        from {module_name} import {app_class_name}",
            f"        {app_var} = {app_class_name}({app_var}_config)",
            f"        {app_var}.setup()",
            f"        print(f'[Setup] Custom app {app_node.name} ready on {source_name}')",
            f"    except ImportError as e:",
            f"        print(f'[Warning] Could not import {app_class_name}: {{e}}')",
            f"        print(f'[Warning] Using default ApplicationBase')",
            f"        from app_base import ApplicationBase",
            f"        {app_var} = ApplicationBase({app_var}_config)",
            f"        {app_var}.setup()",
            f"    except Exception as e:",
            f"        print(f'[Error] Failed to setup application: {{e}}')",
            f"        import traceback",
            f"        traceback.print_exc()",
            "",
            f"    # Setup receiver (PacketSink) on target node",
            f"    sink_addr_{flow_idx} = ns.InetSocketAddress(ns.Ipv4Address.GetAny(), {port})",
            f"    sink_{flow_idx} = ns.PacketSinkHelper(",
            f"        'ns3::{protocol.capitalize()}SocketFactory',",
            f"        sink_addr_{flow_idx}.ConvertTo()",
            f"    )",
            f"    sink_apps_{flow_idx} = sink_{flow_idx}.Install(nodes.Get({target_idx}))",
            f"    sink_apps_{flow_idx}.Start(ns.Seconds({max(0, flow.start_time - 0.5)}))",
            f"    sink_apps_{flow_idx}.Stop(ns.Seconds({flow.stop_time + 1.0}))",
            "",
            f"    # Define send function for this app",
            f"    def send_packet_{flow_idx}():",
            f"        if {app_var}:",
            f"            {app_var}.send_packet()",
            "",
            f"    # Define start function",
            f"    def start_app_{flow_idx}():",
            f"        if {app_var}:",
            f"            {app_var}.start()",
            f"            print(f'[{{ns.Simulator.Now().GetSeconds():.3f}}s] Starting {app_node.name}')",
            "",
            f"    # Define stop function", 
            f"    def stop_app_{flow_idx}():",
            f"        if {app_var}:",
            f"            {app_var}.stop()",
            "",
        ]
        
        return lines
    
    def _generate_custom_app_scheduling(self, network: NetworkModel, sim_config: SimulationConfig) -> str:
        """Generate scheduling code for custom applications."""
        lines = []
        
        # Check if we have any custom app flows
        has_custom_apps = False
        for flow_idx, flow in enumerate(sim_config.flows):
            source_node = network.nodes.get(flow.source_node_id)
            app_enabled = getattr(flow, 'app_enabled', False)
            app_node_id = getattr(flow, 'app_node_id', '')
            
            if not app_enabled and source_node and source_node.has_app_script:
                has_custom_apps = True
                break
            if app_enabled and app_node_id:
                app_node = network.nodes.get(app_node_id)
                if app_node and app_node.has_app_script:
                    has_custom_apps = True
                    break
        
        if not has_custom_apps:
            return ""
        
        lines = [
            "",
            "    # ============================================",
            "    # Schedule Custom Application Events",
            "    # ============================================",
            "    # Note: Using a workaround for ns-3 Python binding limitations",
            "    # We manually call send functions after simulation runs in steps",
            "",
        ]
        
        # Generate scheduling for each custom app flow
        for flow_idx, flow in enumerate(sim_config.flows):
            source_node = network.nodes.get(flow.source_node_id)
            app_enabled = getattr(flow, 'app_enabled', False)
            app_node_id = getattr(flow, 'app_node_id', '')
            
            # Check if this flow uses a custom app
            use_custom = False
            if not app_enabled and source_node and source_node.has_app_script:
                use_custom = True
            elif app_enabled and app_node_id:
                app_node = network.nodes.get(app_node_id)
                if app_node and app_node.has_app_script:
                    use_custom = True
            
            if not use_custom:
                continue
            
            send_interval = getattr(flow, 'socket_send_interval', 1.0)
            if hasattr(flow, 'echo_interval'):
                send_interval = flow.echo_interval
            
            lines.extend([
                f"    # Schedule events for flow {flow_idx}",
                f"    # Start app at {flow.start_time}s, stop at {flow.stop_time}s",
                f"    # Send packets every {send_interval}s",
                "",
            ])
        
        return "\n".join(lines)
    
    def _generate_default_application_flow(
        self,
        flow_idx: int,
        flow: TrafficFlow,
        source_idx: int,
        target_idx: int,
        app_node: NodeModel,
        protocol: str,
        port: int,
        target_link_idx: int,
        interface_idx: int,
        network: NetworkModel
    ) -> list[str]:
        """Generate flow using default ApplicationBase (no custom script)."""
        # Get node names for config
        source_node = network.nodes.get(flow.source_node_id)
        target_node = network.nodes.get(flow.target_node_id)
        source_name = source_node.name if source_node else f"Node{source_idx}"
        target_name = target_node.name if target_node else f"Node{target_idx}"
        
        app_var = f"app_{flow_idx}"
        
        # Calculate send interval
        send_interval = getattr(flow, 'socket_send_interval', 1.0)
        if hasattr(flow, 'echo_interval'):
            send_interval = flow.echo_interval
        
        lines = [
            f"    # Using default ApplicationBase (no custom script)",
            "",
            f"    # Get target IP address",
            f"    target_ip_{flow_idx} = str(interfaces{target_link_idx}.GetAddress({interface_idx}))",
            "",
            f"    # Configuration for the application",
            f"    {app_var}_config = {{",
            f"        'node': nodes.Get({source_idx}),",
            f"        'target_address': target_ip_{flow_idx},",
            f"        'target_port': {port},",
            f"        'protocol': '{protocol}',",
            f"        'start_time': {flow.start_time},",
            f"        'stop_time': {flow.stop_time},",
            f"        'send_interval': {send_interval},",
            f"        'packet_size': {flow.packet_size or 512},",
            f"        'app_name': '{app_node.name}',",
            f"        'source_node_name': '{source_name}',",
            f"        'target_node_name': '{target_name}',",
            f"        'flow_idx': {flow_idx},",
            f"    }}",
            "",
            f"    # Create and setup the default application",
            f"    {app_var} = ApplicationBase({app_var}_config)",
            f"    {app_var}.setup()",
            f"    print(f'[Setup] Default application configured on {source_name}')",
            "",
            f"    # Setup receiver (PacketSink) on target",
            f"    sink_addr_{flow_idx} = ns.InetSocketAddress(ns.Ipv4Address.GetAny(), {port})",
            f"    sink_{flow_idx} = ns.PacketSinkHelper(",
            f"        'ns3::{protocol.capitalize()}SocketFactory',",
            f"        sink_addr_{flow_idx}.ConvertTo()",
            f"    )",
            f"    sink_apps_{flow_idx} = sink_{flow_idx}.Install(nodes.Get({target_idx}))",
            f"    sink_apps_{flow_idx}.Start(ns.Seconds({max(0, flow.start_time - 0.5)}))",
            f"    sink_apps_{flow_idx}.Stop(ns.Seconds({flow.stop_time + 1.0}))",
            "",
        ]
        
        return lines
    
    def _generate_custom_socket_application(
        self, 
        flow_idx: int, 
        flow: TrafficFlow, 
        source_idx: int, 
        target_idx: int,
        network: NetworkModel
    ) -> list[str]:
        """Generate custom socket-based application with custom payload."""
        target_link_idx, interface_idx = self._find_target_interface(flow, network)
        
        if target_link_idx is None:
            return [f"    # Flow {flow_idx}: Cannot find interface for target node", ""]
        
        port = flow.port if flow.port else 9000 + flow_idx
        packet_size = flow.packet_size or 512
        send_count = getattr(flow, 'socket_send_count', 10)
        send_interval = getattr(flow, 'socket_send_interval', 1.0)
        payload_type = getattr(flow, 'socket_payload_type', 'pattern')
        payload_pattern = getattr(flow, 'socket_payload_pattern', '')
        
        protocol = "UDP" if flow.protocol == TrafficProtocol.UDP else "TCP"
        socket_factory = f"ns3::{protocol.lower().capitalize()}SocketFactory"
        
        lines = [
            f"    # Custom Socket Application: {flow.name}",
            f"    # Protocol: {protocol}, Payload: {payload_type}",
            "",
            "    # ----------------------------------------",
            f"    # Socket Application {flow_idx}",
            "    # ----------------------------------------",
            "",
        ]
        
        # Generate payload data based on type
        if payload_type == "pattern" and payload_pattern:
            # Check if hex format
            if payload_pattern.startswith("0x"):
                lines.append(f"    payload_data{flow_idx} = bytes.fromhex('{payload_pattern[2:]}')")
            else:
                lines.append(f"    payload_data{flow_idx} = b'{payload_pattern}'")
        elif payload_type == "sequence":
            lines.append(f"    payload_data{flow_idx} = bytes(range(256)) * ({packet_size} // 256 + 1)")
            lines.append(f"    payload_data{flow_idx} = payload_data{flow_idx}[:{packet_size}]")
        else:  # random
            lines.append(f"    import random")
            lines.append(f"    payload_data{flow_idx} = bytes([random.randint(0, 255) for _ in range({packet_size})])")
        
        lines.append("")
        
        # Receiver socket setup
        lines.extend([
            f"    # Receiver socket on node {target_idx}",
            f"    def setup_receiver{flow_idx}():",
            f"        recv_socket = ns.Socket.CreateSocket(",
            f"            nodes.Get({target_idx}),",
            f"            ns.{protocol.lower().capitalize()}SocketFactory.GetTypeId()",
            f"        )",
            f"        local_addr = ns.InetSocketAddress(ns.Ipv4Address.GetAny(), {port})",
            f"        recv_socket.Bind(local_addr.ConvertTo())",
            f"        print(f'Receiver {flow_idx}: Listening on port {port}')",
            f"        return recv_socket",
            "",
        ])
        
        # Sender socket setup and send function
        lines.extend([
            f"    # Sender socket on node {source_idx}",
            f"    target_addr{flow_idx} = interfaces{target_link_idx}.GetAddress({interface_idx})",
            f"    print(f'Flow {flow_idx} ({flow.name}): Socket sender to {{target_addr{flow_idx}}}:{port}')",
            "",
            f"    send_socket{flow_idx} = None",
            f"    packets_sent{flow_idx} = [0]  # Use list for closure",
            "",
            f"    def setup_sender{flow_idx}():",
            f"        global send_socket{flow_idx}",
            f"        send_socket{flow_idx} = ns.Socket.CreateSocket(",
            f"            nodes.Get({source_idx}),",
            f"            ns.{protocol.lower().capitalize()}SocketFactory.GetTypeId()",
            f"        )",
            f"        remote_addr = ns.InetSocketAddress(target_addr{flow_idx}, {port})",
            f"        send_socket{flow_idx}.Connect(remote_addr.ConvertTo())",
            f"        print(f'Sender {flow_idx}: Connected to {{target_addr{flow_idx}}}:{port}')",
            "",
        ])
        
        # Send packet function
        lines.extend([
            f"    def send_packet{flow_idx}():",
            f"        if send_socket{flow_idx} is None:",
            f"            return",
        ])
        
        if send_count > 0:
            lines.extend([
                f"        if packets_sent{flow_idx}[0] >= {send_count}:",
                f"            return",
            ])
        
        lines.extend([
            f"        packet = ns.Packet(payload_data{flow_idx}, len(payload_data{flow_idx}))",
            f"        send_socket{flow_idx}.Send(packet)",
            f"        packets_sent{flow_idx}[0] += 1",
            f"        print(f'Flow {flow_idx}: Sent packet {{packets_sent{flow_idx}[0]}} ({{len(payload_data{flow_idx})}} bytes)')",
        ])
        
        if send_count > 0:
            lines.append(f"        if packets_sent{flow_idx}[0] < {send_count}:")
            lines.append(f"            ns.Simulator.Schedule(ns.Seconds({send_interval}), send_packet{flow_idx})")
        else:
            lines.append(f"        ns.Simulator.Schedule(ns.Seconds({send_interval}), send_packet{flow_idx})")
        
        lines.append("")
        
        # Schedule setup and first packet
        lines.extend([
            f"    # Schedule socket setup and transmission",
            f"    ns.Simulator.Schedule(ns.Seconds({max(0, flow.start_time - 0.5)}), setup_receiver{flow_idx})",
            f"    ns.Simulator.Schedule(ns.Seconds({flow.start_time - 0.1}), setup_sender{flow_idx})",
            f"    ns.Simulator.Schedule(ns.Seconds({flow.start_time}), send_packet{flow_idx})",
            "",
        ])
        
        return lines
    
    def _generate_application_node_sockets(self, network: NetworkModel) -> list[str]:
        """Generate socket applications from nodes with custom app scripts."""
        lines = []
        
        # Find all nodes with application scripts
        app_script_nodes = [
            (node_id, node) for node_id, node in network.nodes.items()
            if node.has_app_script
        ]
        
        if not app_script_nodes:
            return lines
        
        lines.extend([
            "    # ----------------------------------------",
            "    # Custom Socket Applications from Nodes",
            "    # ----------------------------------------",
            "",
        ])
        
        for app_idx, (node_id, app_node) in enumerate(app_script_nodes):
            node_idx = self._node_index_map.get(node_id)
            if node_idx is None:
                lines.append(f"    # {app_node.name}: SKIPPED - not in node map")
                continue
            
            lines.append(f"    # Custom app from {app_node.name} (Node {node_idx})")
            lines.append(f"    # App script stored in node.app_script - will be written at runtime")
        
        return lines
    
    def _script_exists(self, script_path: str) -> bool:
        """Check if a custom script file exists."""
        import os
        return script_path and os.path.isfile(script_path)
    
    def _generate_custom_script_integration(
        self, app_idx: int, app_node: NodeModel, host_idx: int, script_path: str,
        role: str, protocol: str, remote_addr: str, port: int, payload_size: int,
        send_count: int, send_interval: float, start_time: float
    ) -> list[str]:
        """Generate code that integrates with a custom Python script."""
        import os
        
        # Read the custom script
        script_content = ""
        try:
            with open(script_path, 'r') as f:
                script_content = f.read()
        except Exception as e:
            return [f"    # ERROR: Could not read script {script_path}: {e}", ""]
        
        lines = [
            f"    # Custom script: {os.path.basename(script_path)}",
            "",
            "    # --- Begin custom script integration ---",
            "",
        ]
        
        # Add the custom script as embedded code with namespace isolation
        safe_name = f"_app_script_{app_idx}"
        
        lines.extend([
            f"    # Load custom script module for {app_node.name}",
            f"    import types",
            f"    {safe_name}_module = types.ModuleType('{safe_name}')",
            f"    {safe_name}_module.CONFIG = {{",
            f"        'node_index': {host_idx},",
            f"        'remote_address': '{remote_addr}',",
            f"        'remote_port': {port},",
            f"        'protocol': '{protocol}',",
            f"        'packet_size': {payload_size},",
            f"        'send_count': {send_count},",
            f"        'send_interval': {send_interval},",
            f"    }}",
            "",
        ])
        
        # Embed the script code (indented and escaped)
        lines.append(f"    {safe_name}_code = '''")
        for line in script_content.split('\n'):
            # Escape triple quotes in the script
            escaped_line = line.replace("'''", "' ' '")
            lines.append(escaped_line)
        lines.append("'''")
        lines.append("")
        
        lines.extend([
            f"    exec({safe_name}_code, {safe_name}_module.__dict__)",
            "",
        ])
        
        # Call on_simulation_start if it exists
        lines.extend([
            f"    # Initialize custom script",
            f"    if hasattr({safe_name}_module, 'on_simulation_start'):",
            f"        try:",
            f"            {safe_name}_module.on_simulation_start()",
            f"        except Exception as e:",
            f"            print(f'{app_node.name}: on_simulation_start error: {{e}}')",
            "",
        ])
        
        if role == "sender":
            lines.extend(self._generate_custom_script_sender(
                app_idx, app_node.name, host_idx, safe_name, protocol, remote_addr,
                port, send_count, send_interval, start_time
            ))
        else:
            lines.extend(self._generate_custom_script_receiver(
                app_idx, app_node.name, host_idx, safe_name, protocol, port, start_time
            ))
        
        lines.extend([
            "    # --- End custom script integration ---",
            "",
        ])
        
        return lines
    
    def _generate_custom_script_sender(
        self, app_idx: int, app_name: str, host_idx: int, safe_name: str,
        protocol: str, remote_addr: str, port: int, send_count: int, 
        send_interval: float, start_time: float
    ) -> list[str]:
        """Generate sender code that uses custom script's create_payload."""
        lines = [
            f"    # Sender using custom create_payload()",
            f"    app_socket_{app_idx} = None",
            f"    app_sent_{app_idx} = [0]",
            "",
            f"    def setup_app_sender_{app_idx}():",
            f"        global app_socket_{app_idx}",
            f"        app_socket_{app_idx} = ns.Socket.CreateSocket(",
            f"            nodes.Get({host_idx}),",
            f"            ns.{protocol.capitalize()}SocketFactory.GetTypeId()",
            f"        )",
        ]
        
        if remote_addr:
            lines.extend([
                f"        remote = ns.InetSocketAddress(ns.Ipv4Address('{remote_addr}'), {port})",
                f"        app_socket_{app_idx}.Connect(remote.ConvertTo())",
                f"        print(f'{app_name}: Connected to {remote_addr}:{port}')",
            ])
        
        lines.extend([
            "",
            f"    def app_send_{app_idx}():",
            f"        if app_socket_{app_idx} is None:",
            f"            return",
        ])
        
        if send_count > 0:
            lines.extend([
                f"        if app_sent_{app_idx}[0] >= {send_count}:",
                f"            # Call on_simulation_end if defined",
                f"            if hasattr({safe_name}_module, 'on_simulation_end'):",
                f"                try:",
                f"                    {safe_name}_module.on_simulation_end()",
                f"                except Exception as e:",
                f"                    print(f'{app_name}: on_simulation_end error: {{e}}')",
                f"            return",
            ])
        
        lines.extend([
            f"        # Get payload from custom create_payload()",
            f"        try:",
            f"            payload = {safe_name}_module.create_payload()",
            f"            if not isinstance(payload, bytes):",
            f"                payload = str(payload).encode('utf-8')",
            f"        except Exception as e:",
            f"            print(f'{app_name}: create_payload error: {{e}}')",
            f"            payload = b'ERROR'",
            "",
            f"        pkt = ns.Packet(payload, len(payload))",
            f"        app_socket_{app_idx}.Send(pkt)",
            f"        app_sent_{app_idx}[0] += 1",
            "",
            f"        # Call on_packet_sent callback",
            f"        if hasattr({safe_name}_module, 'on_packet_sent'):",
            f"            try:",
            f"                {safe_name}_module.on_packet_sent(app_sent_{app_idx}[0] - 1, payload)",
            f"            except Exception as e:",
            f"                print(f'{app_name}: on_packet_sent error: {{e}}')",
        ])
        
        if send_count > 0:
            lines.extend([
                f"        if app_sent_{app_idx}[0] < {send_count}:",
                f"            ns.Simulator.Schedule(ns.Seconds({send_interval}), app_send_{app_idx})",
            ])
        else:
            lines.append(f"        ns.Simulator.Schedule(ns.Seconds({send_interval}), app_send_{app_idx})")
        
        lines.extend([
            "",
            f"    ns.Simulator.Schedule(ns.Seconds({start_time - 0.1}), setup_app_sender_{app_idx})",
            f"    ns.Simulator.Schedule(ns.Seconds({start_time}), app_send_{app_idx})",
            "",
        ])
        
        return lines
    
    def _generate_custom_script_receiver(
        self, app_idx: int, app_name: str, host_idx: int, safe_name: str,
        protocol: str, port: int, start_time: float
    ) -> list[str]:
        """Generate receiver code that uses custom script's on_packet_received."""
        lines = [
            f"    # Receiver using custom on_packet_received()",
            f"    recv_socket_{app_idx} = None",
            "",
            f"    def setup_app_receiver_{app_idx}():",
            f"        global recv_socket_{app_idx}",
            f"        recv_socket_{app_idx} = ns.Socket.CreateSocket(",
            f"            nodes.Get({host_idx}),",
            f"            ns.{protocol.capitalize()}SocketFactory.GetTypeId()",
            f"        )",
            f"        local = ns.InetSocketAddress(ns.Ipv4Address.GetAny(), {port})",
            f"        recv_socket_{app_idx}.Bind(local.ConvertTo())",
            f"        print(f'{app_name}: Receiver listening on port {port}')",
            "",
            f"        # Note: In ns-3 Python bindings, setting up recv callbacks is complex",
            f"        # The on_packet_received callback would need C++ callback registration",
            f"        # For now, the receiver just binds to accept incoming packets",
            "",
            f"    ns.Simulator.Schedule(ns.Seconds({max(0, start_time - 0.5)}), setup_app_receiver_{app_idx})",
            "",
        ]
        
        return lines
    
    def _generate_default_receiver(
        self, app_idx: int, app_name: str, host_idx: int, protocol: str, port: int,
        start_time: float
    ) -> list[str]:
        """Generate default receiver code (no custom script)."""
        return [
            f"    def setup_app_receiver_{app_idx}():",
            f"        recv_sock = ns.Socket.CreateSocket(",
            f"            nodes.Get({host_idx}),",
            f"            ns.{protocol.capitalize()}SocketFactory.GetTypeId()",
            f"        )",
            f"        local = ns.InetSocketAddress(ns.Ipv4Address.GetAny(), {port})",
            f"        recv_sock.Bind(local.ConvertTo())",
            f"        print(f'{app_name}: Receiver listening on port {port}')",
            "",
            f"    ns.Simulator.Schedule(ns.Seconds({max(0, start_time - 0.5)}), setup_app_receiver_{app_idx})",
            "",
        ]
    
    def _generate_default_sender(
        self, app_idx: int, app_name: str, host_idx: int, protocol: str, 
        remote_addr: str, port: int, payload_type: str, payload_data: str,
        payload_size: int, send_count: int, send_interval: float, start_time: float
    ) -> list[str]:
        """Generate default sender code (no custom script)."""
        lines = []
        
        # Payload generation
        if payload_type == "pattern" and payload_data:
            if payload_data.startswith("0x"):
                lines.append(f"    app_payload_{app_idx} = bytes.fromhex('{payload_data[2:]}')")
            else:
                escaped = payload_data.replace("\\", "\\\\").replace("'", "\\'")
                lines.append(f"    app_payload_{app_idx} = b'{escaped}'")
            lines.append(f"    # Pad or truncate to {payload_size} bytes")
            lines.append(f"    app_payload_{app_idx} = (app_payload_{app_idx} * ({payload_size} // len(app_payload_{app_idx}) + 1))[:{payload_size}]")
        elif payload_type == "sequence":
            lines.append(f"    app_payload_{app_idx} = bytes(range(256)) * ({payload_size} // 256 + 1)")
            lines.append(f"    app_payload_{app_idx} = app_payload_{app_idx}[:{payload_size}]")
        else:
            lines.append(f"    app_payload_{app_idx} = bytes([i % 256 for i in range({payload_size})])")
        
        lines.append("")
        
        lines.extend([
            f"    app_socket_{app_idx} = None",
            f"    app_sent_{app_idx} = [0]",
            "",
            f"    def setup_app_sender_{app_idx}():",
            f"        global app_socket_{app_idx}",
            f"        app_socket_{app_idx} = ns.Socket.CreateSocket(",
            f"            nodes.Get({host_idx}),",
            f"            ns.{protocol.capitalize()}SocketFactory.GetTypeId()",
            f"        )",
        ])
        
        if remote_addr:
            lines.extend([
                f"        remote = ns.InetSocketAddress(ns.Ipv4Address('{remote_addr}'), {port})",
                f"        app_socket_{app_idx}.Connect(remote.ConvertTo())",
                f"        print(f'{app_name}: Sender connected to {remote_addr}:{port}')",
            ])
        else:
            lines.append(f"        print(f'{app_name}: WARNING - No remote address configured')")
        
        lines.extend([
            "",
            f"    def app_send_{app_idx}():",
            f"        if app_socket_{app_idx} is None:",
            f"            return",
        ])
        
        if send_count > 0:
            lines.extend([
                f"        if app_sent_{app_idx}[0] >= {send_count}:",
                f"            return",
            ])
        
        lines.extend([
            f"        pkt = ns.Packet(app_payload_{app_idx}, len(app_payload_{app_idx}))",
            f"        app_socket_{app_idx}.Send(pkt)",
            f"        app_sent_{app_idx}[0] += 1",
            f"        print(f'{app_name}: Sent packet {{app_sent_{app_idx}[0]}}')",
        ])
        
        if send_count > 0:
            lines.append(f"        if app_sent_{app_idx}[0] < {send_count}:")
            lines.append(f"            ns.Simulator.Schedule(ns.Seconds({send_interval}), app_send_{app_idx})")
        else:
            lines.append(f"        ns.Simulator.Schedule(ns.Seconds({send_interval}), app_send_{app_idx})")
        
        lines.extend([
            "",
            f"    ns.Simulator.Schedule(ns.Seconds({start_time - 0.1}), setup_app_sender_{app_idx})",
            f"    ns.Simulator.Schedule(ns.Seconds({start_time}), app_send_{app_idx})",
            "",
        ])
        
        return lines

    def _generate_tracing(self, sim_config: SimulationConfig, output_dir: str) -> str:
        """Generate tracing/logging code."""
        lines = [
            "    # ============================================",
            "    # Setup Tracing and Monitoring",
            "    # ============================================",
            "",
        ]
        
        if sim_config.enable_ascii_trace:
            lines.extend([
                "    # ASCII Trace for packet-level details",
                "    ascii_trace = ns.AsciiTraceHelper()",
                f"    p2p.EnableAsciiAll(ascii_trace.CreateFileStream('{output_dir}/trace.tr'))",
                f"    csma.EnableAsciiAll(ascii_trace.CreateFileStream('{output_dir}/csma-trace.tr'))",
                "",
            ])
        
        if sim_config.enable_pcap:
            lines.extend([
                "    # PCAP Trace (packet capture)",
                f"    p2p.EnablePcapAll('{output_dir}/p2p-capture')",
                f"    csma.EnablePcapAll('{output_dir}/csma-capture')",
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
            "    # Collect custom apps (filter out None and config dicts)",
            "    custom_apps = []",
            "    for name, val in list(locals().items()):",
            "        if name.startswith('custom_app_') and not name.endswith('_config'):",
            "            if val is not None and hasattr(val, 'start_time'):",
            "                custom_apps.append(val)",
            "",
            "    if custom_apps:",
            "        print(f'Running with {len(custom_apps)} custom application(s)')",
            "        # Run simulation in steps to allow Python app sends",
            "        step_size = 0.1  # 100ms steps",
            "        current_time = 0.0",
            f"        end_time = {sim_config.duration}",
            "",
            "        # Track send times for each app",
            "        app_next_send = {}",
            "        for i, app in enumerate(custom_apps):",
            "            app_next_send[i] = app.start_time",
            "",
            "        while current_time < end_time:",
            "            # Advance simulation by step",
            "            next_time = min(current_time + step_size, end_time)",
            "            ns.Simulator.Stop(ns.Seconds(next_time))",
            "            ns.Simulator.Run()",
            "            current_time = ns.Simulator.Now().GetSeconds()",
            "",
            "            # Check each custom app for sends",
            "            for i, app in enumerate(custom_apps):",
            "                # Start app if it's time",
            "                if not app.is_running and current_time >= app.start_time:",
            "                    app.start()",
            "",
            "                # Stop app if it's time",
            "                if app.is_running and current_time >= app.stop_time:",
            "                    app.stop()",
            "                    continue",
            "",
            "                # Send packets if it's time",
            "                while app.is_running and app_next_send[i] <= current_time:",
            "                    app.send_packet()",
            "                    app_next_send[i] += app.send_interval",
            "",
            "        # Final cleanup",
            "        for app in custom_apps:",
            "            if app.is_running:",
            "                app.stop()",
            "    else:",
            "        # No custom apps, run normally",
            "        ns.Simulator.Run()",
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
    
    def get_required_files(
        self, 
        network: NetworkModel, 
        sim_config: SimulationConfig
    ) -> list[dict]:
        """
        Get list of files required for simulation with custom applications.
        
        Returns a list of dicts with:
            - 'type': 'base' | 'custom'
            - 'source_path': Path to source file (or None for embedded)
            - 'dest_name': Destination filename in scratch directory
            - 'content': File content (if embedded, otherwise None)
        
        Args:
            network: Network topology model
            sim_config: Simulation configuration
            
        Returns:
            List of file descriptors needed for simulation
        """
        files = []
        added_nodes = set()
        
        # Check flows for nodes with app scripts
        for flow in sim_config.flows:
            # Check explicit app_node_id
            app_node_id = getattr(flow, 'app_node_id', '')
            if flow.app_enabled and app_node_id:
                app_node = network.nodes.get(app_node_id)
                if app_node and app_node.has_app_script and app_node.id not in added_nodes:
                    module_name = self._sanitize_module_name(app_node.name)
                    files.append({
                        'type': 'custom',
                        'source_path': None,
                        'dest_name': f'{module_name}.py',
                        'content': app_node.app_script,
                    })
                    added_nodes.add(app_node.id)
            
            # Also check if source node has app script (auto-detect)
            source_node = network.nodes.get(flow.source_node_id)
            if source_node and source_node.has_app_script and source_node.id not in added_nodes:
                module_name = self._sanitize_module_name(source_node.name)
                files.append({
                    'type': 'custom',
                    'source_path': None,
                    'dest_name': f'{module_name}.py',
                    'content': source_node.app_script,
                })
                added_nodes.add(source_node.id)
        
        # If we have any custom scripts, we need app_base.py
        if files:
            import os
            base_path = os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                'templates',
                'app_base.py'
            )
            
            # Insert app_base.py at the beginning
            files.insert(0, {
                'type': 'base',
                'source_path': base_path,
                'dest_name': 'app_base.py',
                'content': None,
            })
        
        return files


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
