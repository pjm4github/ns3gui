"""
Topology Converter.

Converts ExtractedTopology from ns-3 script parsing to NetworkModel
for use in the GUI editor.

Key concepts:
- ns-3 nodes are generic; their "type" (host/router) is inferred from connectivity
- CSMA (shared medium) segments are represented visually with a switch node
- Point-to-point links are direct connections between exactly 2 nodes

Also handles saving to workspace with mirrored directory structure.
"""

import math
import uuid
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from models.network import (
    NetworkModel, NodeModel, LinkModel, PortConfig, Position,
    NodeType, MediumType, PortType, ChannelType, RouteEntry, RoutingMode
)
from models.simulation import (
    SimulationConfig, TrafficFlow, TrafficApplication, TrafficProtocol
)
from services.ns3_script_parser import (
    ExtractedTopology, ExtractedNode, ExtractedLink, ExtractedApplication,
    ChannelMedium as ExtractedChannelMedium, 
    NodeRole as ExtractedNodeRole,
    MediumHint,
    # Aliases for backward compatibility
    LinkType as ExtractedLinkType, 
    NodeType as ExtractedNodeType
)


def generate_id() -> str:
    """Generate a short unique ID."""
    return uuid.uuid4().hex[:8]


class TopologyConverter:
    """
    Convert ExtractedTopology to NetworkModel.
    
    Handles:
    - Creating nodes with inferred roles (host, router, switch)
    - Creating links between nodes based on channel medium
    - Auto-layout of nodes for visual display
    - IP address assignment based on extracted data
    - Creating virtual switch nodes to represent CSMA shared medium segments
    
    CSMA Representation:
        In ns-3, CSMA is a shared medium where all nodes can hear each other
        (like an Ethernet hub or bus). In the GUI, we represent this with a
        central switch node connected to all nodes on the segment. This is a
        visual simplification - the actual ns-3 simulation uses true CSMA.
    """
    
    def __init__(self):
        self.node_spacing = 150  # Pixels between nodes
        self.csma_switch_nodes: Dict[str, str] = {}  # CSMA segment -> virtual switch node ID
    
    def convert(self, extracted: ExtractedTopology) -> NetworkModel:
        """
        Convert extracted topology to NetworkModel.
        
        Args:
            extracted: Topology data extracted from ns-3 script
            
        Returns:
            NetworkModel ready for use in GUI
        """
        network = NetworkModel()
        
        # Store import metadata
        network.import_metadata = {
            "source_file": extracted.source_file,
            "script_name": extracted.script_name,
            "module_name": extracted.module_name,
            "description": extracted.description,
            "original_duration": extracted.duration,
        }
        
        # Copy parser warnings as network warnings
        for warning in extracted.warnings:
            network.warnings.append({
                "source": "parser",
                "message": warning
            })
        
        # Copy parser errors as todos (things that need attention)
        for error in extracted.errors:
            network.todos.append({
                "type": "parse_error",
                "source": "parser", 
                "message": error
            })
        
        # Store extraction info
        if extracted.duration > 0:
            network.simulation_duration = extracted.duration
        
        # Map from (container, index) to node ID
        node_map: Dict[Tuple[str, int], str] = {}
        
        # First pass: identify CSMA segments and any existing switches that act as hubs
        csma_segments = self._identify_csma_segments(extracted)
        
        # Create regular nodes first (so we can reference switch nodes)
        for ext_node in extracted.nodes:
            node = self._create_node(ext_node, len(network.nodes))
            network.nodes[node.id] = node
            node_map[ext_node.key] = node.id
        
        # Now register existing switches as CSMA hubs, or create virtual ones
        for segment_key, node_keys in csma_segments.items():
            # Check if this segment has an existing switch as hub
            if hasattr(self, '_csma_hub_switches') and segment_key in self._csma_hub_switches:
                switch_key = self._csma_hub_switches[segment_key]
                if switch_key in node_map:
                    self.csma_switch_nodes[segment_key] = node_map[switch_key]
                    continue
            
            # No existing switch - create a virtual one if needed
            if len(node_keys) > 2:  # Only create switch for 3+ nodes
                switch = self._create_csma_switch_node(segment_key, len(network.nodes))
                network.nodes[switch.id] = switch
                self.csma_switch_nodes[segment_key] = switch.id
        
        # Apply layout
        self._apply_layout(network, extracted)
        
        # Create links
        for ext_link in extracted.links:
            if ext_link.link_type == ExtractedLinkType.CSMA:
                # CSMA links go through switch if one was created
                self._create_csma_links(network, ext_link, node_map)
            else:
                # Point-to-point link
                link = self._create_link(ext_link, node_map, network)
                if link:
                    network.links[link.id] = link
        
        # Apply IP addresses
        self._apply_ip_addresses(network, extracted, node_map)
        
        # Convert applications to traffic flows
        traffic_flows = self._convert_applications_to_flows(extracted, node_map)
        
        return network, traffic_flows
    
    def _identify_csma_segments(self, extracted: ExtractedTopology) -> Dict[str, List[Tuple[str, int]]]:
        """
        Identify CSMA segments (groups of nodes on shared medium).
        
        If links connect to an existing SWITCH node, that switch becomes the hub.
        Otherwise, we'll create a virtual hub later.
        
        Returns dict mapping segment identifier to list of node keys.
        """
        segments: Dict[str, List[Tuple[str, int]]] = {}
        
        # Track which switch nodes are used as CSMA hubs
        self._csma_hub_switches: Dict[str, Tuple[str, int]] = {}  # segment_key -> switch node key
        
        for link in extracted.links:
            if link.link_type == ExtractedLinkType.CSMA:
                # Check if either endpoint is a switch
                source_node = extracted.get_node(link.source_container, link.source_index)
                target_node = extracted.get_node(link.target_container, link.target_index)
                
                source_is_switch = source_node and source_node.node_type == ExtractedNodeRole.SWITCH
                target_is_switch = target_node and target_node.node_type == ExtractedNodeRole.SWITCH
                
                # Determine segment key - use the switch's container if one exists
                if target_is_switch:
                    segment_key = f"csma_{link.target_container}"
                    self._csma_hub_switches[segment_key] = link.target_key
                elif source_is_switch:
                    segment_key = f"csma_{link.source_container}"
                    self._csma_hub_switches[segment_key] = link.source_key
                else:
                    # No switch involved, use source container
                    segment_key = f"csma_{link.source_container}"
                
                if segment_key not in segments:
                    segments[segment_key] = []
                
                # Add non-switch nodes to the segment
                if not source_is_switch and link.source_key not in segments[segment_key]:
                    segments[segment_key].append(link.source_key)
                if not target_is_switch and link.target_key not in segments[segment_key]:
                    segments[segment_key].append(link.target_key)
        
        return segments
    
    def _create_csma_switch_node(self, segment_key: str, index: int) -> NodeModel:
        """
        Create a virtual switch node to represent a CSMA shared medium segment.
        
        This is a GUI representation only - in the actual ns-3 simulation,
        CSMA nodes communicate via a shared channel (like an Ethernet hub/bus),
        not through a switch. The switch visualization helps users understand
        which nodes share bandwidth on the same collision domain.
        """
        # NodeModel.__post_init__ will create default 8 ports for SWITCH type
        node = NodeModel(
            id=generate_id(),
            name=f"csma_hub_{segment_key}",
            node_type=NodeType.SWITCH,
            description=f"Virtual hub representing CSMA shared medium '{segment_key}' (not a real ns-3 node)",
        )
        
        return node
    
    def _create_node(self, ext_node: ExtractedNode, index: int) -> NodeModel:
        """Create a NodeModel from ExtractedNode."""
        # Map extracted node type to GUI node type
        node_type = self._map_node_type(ext_node.node_type)
        
        # Map medium hint to medium type
        medium_type = self._map_medium_type(ext_node.medium_hint)
        
        # Generate name
        name = f"{ext_node.container_name}_{ext_node.index}"
        
        # Create node - NodeModel.__post_init__ will create default ports
        node = NodeModel(
            id=generate_id(),
            name=name,
            node_type=node_type,
            medium_type=medium_type,
            description=f"From container '{ext_node.container_name}' index {ext_node.index}",
        )
        
        return node
    
    def _map_node_type(self, ext_type: ExtractedNodeType) -> NodeType:
        """Map extracted node type to GUI node type."""
        mapping = {
            ExtractedNodeType.HOST: NodeType.HOST,
            ExtractedNodeType.ROUTER: NodeType.ROUTER,
            ExtractedNodeType.SWITCH: NodeType.SWITCH,
            ExtractedNodeType.ACCESS_POINT: NodeType.ROUTER,  # Treat AP as router for now
            ExtractedNodeType.UNKNOWN: NodeType.HOST,
        }
        return mapping.get(ext_type, NodeType.HOST)
    
    def _map_medium_type(self, hint: MediumHint) -> MediumType:
        """Map parser's MediumHint to model's MediumType."""
        mapping = {
            MediumHint.WIRED: MediumType.WIRED,
            MediumHint.WIFI_STATION: MediumType.WIFI_STATION,
            MediumHint.WIFI_AP: MediumType.WIFI_AP,
            MediumHint.LTE_UE: MediumType.LTE_UE,
            MediumHint.LTE_ENB: MediumType.LTE_ENB,
        }
        return mapping.get(hint, MediumType.WIRED)
    
    def _create_link(
        self, 
        ext_link: ExtractedLink, 
        node_map: Dict[Tuple[str, int], str],
        network: NetworkModel
    ) -> Optional[LinkModel]:
        """Create a LinkModel from ExtractedLink."""
        source_id = node_map.get(ext_link.source_key)
        target_id = node_map.get(ext_link.target_key)
        
        if not source_id or not target_id:
            return None
        
        source_node = network.nodes.get(source_id)
        target_node = network.nodes.get(target_id)
        
        if not source_node or not target_node:
            return None
        
        # Find available ports
        source_port = self._find_available_port(source_node, network)
        target_port = self._find_available_port(target_node, network)
        
        if not source_port or not target_port:
            # Add new ports if needed
            source_port = self._add_port(source_node)
            target_port = self._add_port(target_node)
        
        # Parse data rate and delay
        data_rate = ext_link.data_rate or "1Gbps"
        delay = ext_link.delay or "1ms"
        
        link = LinkModel(
            id=generate_id(),
            source_node_id=source_id,
            target_node_id=target_id,
            source_port_id=source_port.id,
            target_port_id=target_port.id,
            channel_type=self._map_channel_type(ext_link.link_type, network),
            data_rate=data_rate,
            delay=delay,
        )
        
        # Mark ports as connected
        source_port.connected_link_id = link.id
        target_port.connected_link_id = link.id
        
        return link
    
    def _create_csma_links(
        self,
        network: NetworkModel,
        ext_link: ExtractedLink,
        node_map: Dict[Tuple[str, int], str]
    ):
        """
        Create links for CSMA shared medium segment.
        
        If an existing switch node is the hub, connects hosts to it.
        If 3+ nodes are on the segment without a switch, connects them through a virtual switch.
        Otherwise creates direct CSMA links between nodes.
        """
        # Determine the segment key - check both source and target
        # If one is a switch, use its container name
        source_id = node_map.get(ext_link.source_key)
        target_id = node_map.get(ext_link.target_key)
        
        source_node = network.nodes.get(source_id) if source_id else None
        target_node = network.nodes.get(target_id) if target_id else None
        
        source_is_switch = source_node and source_node.node_type == NodeType.SWITCH
        target_is_switch = target_node and target_node.node_type == NodeType.SWITCH
        
        # Determine the segment key based on which end is the switch
        if target_is_switch:
            segment_key = f"csma_{ext_link.target_container}"
        elif source_is_switch:
            segment_key = f"csma_{ext_link.source_container}"
        else:
            segment_key = f"csma_{ext_link.source_container}"
        
        switch_id = self.csma_switch_nodes.get(segment_key)
        
        if switch_id:
            # Connect non-switch nodes to the switch
            switch_node = network.nodes.get(switch_id)
            if not switch_node:
                return
            
            # If one end is already the switch, just connect the other end
            if source_is_switch or target_is_switch:
                # Figure out which is the host
                if source_is_switch:
                    host_id = target_id
                    host_node = target_node
                else:
                    host_id = source_id
                    host_node = source_node
                
                if not host_id or not host_node:
                    return
                
                # Skip if it's the switch itself
                if host_node.node_type == NodeType.SWITCH:
                    return
                
                # Check if already connected
                already_connected = any(
                    (l.source_node_id == host_id and l.target_node_id == switch_id) or
                    (l.target_node_id == host_id and l.source_node_id == switch_id)
                    for l in network.links.values()
                )
                
                if not already_connected:
                    host_port = self._find_available_port(host_node, network) or self._add_port(host_node)
                    switch_port = self._find_available_port(switch_node, network) or self._add_port(switch_node)
                    
                    link = LinkModel(
                        id=generate_id(),
                        source_node_id=host_id,
                        target_node_id=switch_id,
                        source_port_id=host_port.id,
                        target_port_id=switch_port.id,
                        channel_type=ChannelType.CSMA,
                        data_rate=ext_link.data_rate or "100Mbps",
                        delay=ext_link.delay or "1ms",
                    )
                    
                    host_port.connected_link_id = link.id
                    switch_port.connected_link_id = link.id
                    network.links[link.id] = link
            else:
                # Neither end is a switch - connect both to the virtual switch
                for node_key in [ext_link.source_key, ext_link.target_key]:
                    node_id = node_map.get(node_key)
                    if not node_id:
                        continue
                    
                    node = network.nodes.get(node_id)
                    if not node or node.node_type == NodeType.SWITCH:
                        continue
                    
                    # Check if already connected to this switch
                    already_connected = any(
                        (l.source_node_id == node_id and l.target_node_id == switch_id) or
                        (l.target_node_id == node_id and l.source_node_id == switch_id)
                        for l in network.links.values()
                    )
                    
                    if already_connected:
                        continue
                    
                    # Create link to switch
                    node_port = self._find_available_port(node, network) or self._add_port(node)
                    switch_port = self._find_available_port(switch_node, network) or self._add_port(switch_node)
                    
                    link = LinkModel(
                        id=generate_id(),
                        source_node_id=node_id,
                        target_node_id=switch_id,
                        source_port_id=node_port.id,
                        target_port_id=switch_port.id,
                        channel_type=ChannelType.CSMA,
                        data_rate=ext_link.data_rate or "100Mbps",
                        delay=ext_link.delay or "1ms",
                    )
                    
                    node_port.connected_link_id = link.id
                    switch_port.connected_link_id = link.id
                    network.links[link.id] = link
        else:
            # Direct link (small CSMA segment)
            link = self._create_link(ext_link, node_map, network)
            if link:
                link.channel_type = ChannelType.CSMA
                network.links[link.id] = link
    
    def _map_channel_type(self, link_type: ExtractedLinkType, network: NetworkModel) -> ChannelType:
        """
        Map extracted link type to channel type.
        
        Unsupported types are recorded in network.todos and default to POINT_TO_POINT.
        """
        mapping = {
            ExtractedLinkType.POINT_TO_POINT: ChannelType.POINT_TO_POINT,
            ExtractedLinkType.CSMA: ChannelType.CSMA,
        }
        
        if link_type in mapping:
            return mapping[link_type]
        
        # Unsupported link type - record as TODO
        todo_entry = {
            "type": "unsupported_link_type",
            "link_type": link_type.value if hasattr(link_type, 'value') else str(link_type),
            "message": f"Link type '{link_type.value}' is not yet supported, using POINT_TO_POINT as fallback",
            "suggestion": "Future implementation needed for this link type"
        }
        
        # Only add if not already recorded
        if todo_entry not in network.todos:
            network.todos.append(todo_entry)
        
        return ChannelType.POINT_TO_POINT
    
    def _find_available_port(self, node: NodeModel, network: NetworkModel) -> Optional[PortConfig]:
        """Find an unconnected port on a node."""
        for port in node.ports:
            if not port.connected_link_id:
                return port
        return None
    
    def _add_port(self, node: NodeModel) -> PortConfig:
        """Add a new port to a node."""
        port_num = len(node.ports)
        port = PortConfig(
            id=generate_id(),
            port_number=port_num,
            port_name=f"gi{port_num}",
            port_type=PortType.GIGABIT_ETHERNET,
        )
        node.ports.append(port)
        return port
    
    def _apply_layout(self, network: NetworkModel, extracted: ExtractedTopology):
        """
        Apply automatic layout to nodes.
        
        Uses a simple grid/circular layout based on topology structure.
        """
        nodes = list(network.nodes.values())
        n = len(nodes)
        
        if n == 0:
            return
        
        # Separate switches from other nodes
        switches = [n for n in nodes if n.node_type == NodeType.SWITCH]
        others = [n for n in nodes if n.node_type != NodeType.SWITCH]
        
        if len(others) <= 4:
            # Small topology: arrange in a line or simple grid
            self._layout_line(others)
        else:
            # Larger topology: arrange in a circle
            self._layout_circle(others)
        
        # Place switches in the center
        if switches:
            self._layout_center(switches, others)
    
    def _layout_line(self, nodes: List[NodeModel]):
        """Arrange nodes in a horizontal line."""
        n = len(nodes)
        total_width = (n - 1) * self.node_spacing
        start_x = -total_width / 2
        
        for i, node in enumerate(nodes):
            node.position = Position(x=start_x + i * self.node_spacing, y=0)
    
    def _layout_circle(self, nodes: List[NodeModel]):
        """Arrange nodes in a circle."""
        n = len(nodes)
        radius = max(100, n * self.node_spacing / (2 * math.pi))
        
        for i, node in enumerate(nodes):
            angle = 2 * math.pi * i / n - math.pi / 2  # Start from top
            x = radius * math.cos(angle)
            y = radius * math.sin(angle)
            node.position = Position(x=x, y=y)
    
    def _layout_center(self, center_nodes: List[NodeModel], other_nodes: List[NodeModel]):
        """Place center nodes (switches) in the center of other nodes."""
        if not other_nodes:
            self._layout_line(center_nodes)
            return
        
        # Calculate centroid of other nodes
        cx = sum(n.position.x for n in other_nodes) / len(other_nodes)
        cy = sum(n.position.y for n in other_nodes) / len(other_nodes)
        
        # Place center nodes around the centroid
        n = len(center_nodes)
        for i, node in enumerate(center_nodes):
            offset_x = (i - (n - 1) / 2) * 80
            node.position = Position(x=cx + offset_x, y=cy)
    
    def _apply_ip_addresses(
        self,
        network: NetworkModel,
        extracted: ExtractedTopology,
        node_map: Dict[Tuple[str, int], str]
    ):
        """Apply IP addresses based on extracted data."""
        # This is a simplified implementation
        # In practice, we'd need to track which devices correspond to which links
        
        subnet_counter = 1
        
        for link in network.links.values():
            source_node = network.nodes.get(link.source_node_id)
            target_node = network.nodes.get(link.target_node_id)
            
            if not source_node or not target_node:
                continue
            
            # Find the ports
            source_port = None
            target_port = None
            
            for port in source_node.ports:
                if port.id == link.source_port_id:
                    source_port = port
                    break
            
            for port in target_node.ports:
                if port.id == link.target_port_id:
                    target_port = port
                    break
            
            if source_port and target_port:
                # Assign IPs if not already set
                if not source_port.ip_address:
                    source_port.ip_address = f"10.1.{subnet_counter}.1"
                    source_port.netmask = "255.255.255.0"
                
                if not target_port.ip_address:
                    target_port.ip_address = f"10.1.{subnet_counter}.2"
                    target_port.netmask = "255.255.255.0"
                
                subnet_counter += 1
    
    def _convert_applications_to_flows(
        self,
        extracted: ExtractedTopology,
        node_map: Dict[Tuple[str, int], str]
    ) -> List[TrafficFlow]:
        """
        Convert extracted applications to TrafficFlow objects.
        
        Matches OnOff/BulkSend sources with PacketSink destinations
        to create complete flow definitions.
        """
        flows: List[TrafficFlow] = []
        
        # Separate sources (generators) and sinks
        sources: List[ExtractedApplication] = []
        sinks: Dict[Tuple[str, int], ExtractedApplication] = {}  # keyed by (container, index)
        
        for app in extracted.applications:
            if app.app_type in ("OnOff", "BulkSend", "UdpEchoClient"):
                sources.append(app)
            elif app.app_type in ("PacketSink", "UdpEchoServer"):
                key = (app.node_container, app.node_index)
                sinks[key] = app
        
        # Create flows from sources
        for source_app in sources:
            source_key = (source_app.node_container, source_app.node_index)
            source_node_id = node_map.get(source_key, "")
            
            # Determine target node from remote_address
            target_node_id = ""
            if source_app.remote_address:
                target_node_id = self._find_node_by_ip(
                    extracted, node_map, source_app.remote_address
                )
            
            # Map app type to TrafficApplication enum
            app_type = TrafficApplication.ONOFF
            if source_app.app_type == "BulkSend":
                app_type = TrafficApplication.BULK_SEND
            elif source_app.app_type == "UdpEchoClient":
                app_type = TrafficApplication.ECHO
            
            # Map protocol
            protocol = TrafficProtocol.UDP
            if source_app.protocol == "TCP":
                protocol = TrafficProtocol.TCP
            
            flow = TrafficFlow(
                name=f"{source_app.app_type}_{source_app.node_container}_{source_app.node_index}",
                source_node_id=source_node_id,
                target_node_id=target_node_id,
                dest_address=source_app.remote_address,
                port=source_app.port,
                protocol=protocol,
                application=app_type,
                start_time=source_app.start_time,
                stop_time=source_app.stop_time if source_app.stop_time > 0 else 10.0,
                data_rate=source_app.data_rate or "500kb/s",
                packet_size=source_app.packet_size if source_app.packet_size > 0 else 1024,
            )
            
            flows.append(flow)
        
        return flows
    
    def _find_node_by_ip(
        self,
        extracted: ExtractedTopology,
        node_map: Dict[Tuple[str, int], str],
        ip_address: str
    ) -> str:
        """
        Find the node ID that has the given IP address.
        
        This is a heuristic - we look at IP assignments and try to match.
        """
        # Look through IP assignments
        for assignment in extracted.ip_assignments:
            # Parse the base address to see if ip_address falls in this range
            base = assignment.base_address
            
            # Simple matching: check if the IP's first 3 octets match the base
            if ip_address and base:
                ip_parts = ip_address.split('.')
                base_parts = base.split('.')
                
                if len(ip_parts) >= 3 and len(base_parts) >= 3:
                    if ip_parts[:3] == base_parts[:3]:
                        # This IP is in this subnet
                        # Try to find the node index from last octet
                        try:
                            host_num = int(ip_parts[3])
                            # In most ns-3 examples, host addresses start at .1
                            # and correspond to node indices
                            for key, node_id in node_map.items():
                                container, idx = key
                                # Check if this container is in the assignment
                                if assignment.device_container in ["terminalDevices", "devices", container]:
                                    # Simple heuristic: host_num - 1 = node_index
                                    if idx == host_num - 1:
                                        return node_id
                        except ValueError:
                            pass
        
        # Fallback: try direct matching in IP assignments
        # This won't work for most cases but is a safety net
        return ""


class WorkspaceManager:
    """
    Manage workspace directory structure mirroring ns-3 layout.
    
    Directory structure:
    workspace/
    ├── extracted/              # Raw extraction results
    │   └── src/
    │       ├── point-to-point/
    │       │   └── examples/
    │       │       ├── first.extracted.json
    │       │       └── first.topology.json
    │       └── csma/
    │           └── examples/
    │               └── ...
    ├── topologies/             # Converted topology files (ready for GUI)
    │   └── ns3-examples/
    │       ├── point-to-point/
    │       │   └── first.json
    │       └── csma/
    │           └── ...
    └── scripts/                # Generated simulation scripts
    """
    
    def __init__(self, workspace_root: Path):
        self.workspace_root = Path(workspace_root)
        self.extracted_dir = self.workspace_root / "extracted"
        self.topologies_dir = self.workspace_root / "topologies" / "ns3-examples"
        self.scripts_dir = self.workspace_root / "scripts"
    
    def ensure_directories(self):
        """Create workspace directory structure."""
        self.extracted_dir.mkdir(parents=True, exist_ok=True)
        self.topologies_dir.mkdir(parents=True, exist_ok=True)
        self.scripts_dir.mkdir(parents=True, exist_ok=True)
    
    def get_extracted_path(self, ns3_relative_path: Path, suffix: str = ".extracted.json") -> Path:
        """
        Get path for extracted data file, mirroring ns-3 structure.
        
        Args:
            ns3_relative_path: Path relative to ns-3 root (e.g., "src/point-to-point/examples/first.py")
            suffix: File suffix to use
            
        Returns:
            Path in workspace extracted directory
        """
        # Remove .py extension and add suffix
        stem = ns3_relative_path.stem
        parent = ns3_relative_path.parent
        
        output_path = self.extracted_dir / parent / f"{stem}{suffix}"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        return output_path
    
    def get_topology_path(self, ns3_relative_path: Path) -> Path:
        """
        Get path for converted topology file.
        
        Args:
            ns3_relative_path: Path relative to ns-3 root
            
        Returns:
            Path in workspace topologies directory
        """
        # Extract module name and script name
        parts = ns3_relative_path.parts
        
        # Try to find module name
        module_name = "misc"
        if "src" in parts:
            src_idx = parts.index("src")
            if src_idx + 1 < len(parts):
                module_name = parts[src_idx + 1]
        elif "examples" in parts:
            examples_idx = parts.index("examples")
            if examples_idx > 0:
                module_name = parts[examples_idx - 1]
        
        stem = ns3_relative_path.stem
        output_path = self.topologies_dir / module_name / f"{stem}.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        return output_path
    
    def save_extracted(self, topology: ExtractedTopology, ns3_relative_path: Path):
        """Save extracted topology data."""
        from services.ns3_script_parser import TopologyExporter
        
        exporter = TopologyExporter()
        output_path = self.get_extracted_path(ns3_relative_path)
        exporter.save_json(topology, output_path)
        
        return output_path
    
    def save_topology(self, network: NetworkModel, ns3_relative_path: Path) -> Path:
        """Save converted NetworkModel topology."""
        from services.project_manager import ProjectManager
        
        output_path = self.get_topology_path(ns3_relative_path)
        
        manager = ProjectManager()
        manager.save(network, output_path)
        
        return output_path


class NS3ExampleProcessor:
    """
    Process ns-3 example scripts to extract and convert topologies.
    
    Usage:
        processor = NS3ExampleProcessor(
            ns3_path="/home/user/ns-allinone-3.45/ns-3.45",
            workspace_path="/home/user/Documents/NS3GUI"
        )
        
        # Process a single file
        result = processor.process_file("src/point-to-point/examples/first.py")
        
        # Process all Python examples
        results = processor.process_all_python_examples()
    """
    
    def __init__(self, ns3_path: str, workspace_path: str):
        self.ns3_path = Path(ns3_path)
        self.workspace = WorkspaceManager(Path(workspace_path))
        self.parser = NS3PythonParser()
        self.converter = TopologyConverter()
        
        # Ensure workspace exists
        self.workspace.ensure_directories()
    
    def process_file(self, relative_path: str) -> Dict:
        """
        Process a single ns-3 Python example file.
        
        Args:
            relative_path: Path relative to ns-3 root (e.g., "src/point-to-point/examples/first.py")
            
        Returns:
            Dict with processing results
        """
        rel_path = Path(relative_path)
        full_path = self.ns3_path / rel_path
        
        result = {
            "source_file": str(full_path),
            "relative_path": str(rel_path),
            "success": False,
            "extracted_path": None,
            "topology_path": None,
            "errors": [],
            "warnings": [],
            "node_count": 0,
            "link_count": 0,
        }
        
        if not full_path.exists():
            result["errors"].append(f"File not found: {full_path}")
            return result
        
        if full_path.suffix != ".py":
            result["errors"].append(f"Not a Python file: {full_path}")
            return result
        
        # Parse the script
        extracted = self.parser.parse_file(full_path)
        result["errors"].extend(extracted.errors)
        result["warnings"].extend(extracted.warnings)
        
        # Save extracted data
        try:
            extracted_path = self.workspace.save_extracted(extracted, rel_path)
            result["extracted_path"] = str(extracted_path)
        except Exception as e:
            result["errors"].append(f"Failed to save extracted data: {e}")
        
        if not extracted.parse_success:
            return result
        
        # Convert to NetworkModel
        try:
            network, traffic_flows = self.converter.convert(extracted)
            result["node_count"] = len(network.nodes)
            result["link_count"] = len(network.links)
            result["traffic_flows"] = traffic_flows
            
            # Save topology
            topology_path = self.workspace.save_topology(network, rel_path)
            result["topology_path"] = str(topology_path)
            result["success"] = True
            
        except Exception as e:
            result["errors"].append(f"Failed to convert topology: {e}")
        
        return result
    
    def discover_python_examples(self) -> List[Path]:
        """
        Discover all Python example files in ns-3.
        
        Returns:
            List of paths relative to ns-3 root
        """
        examples = []
        
        # Search in src/*/examples/
        for py_file in self.ns3_path.glob("src/*/examples/*.py"):
            examples.append(py_file.relative_to(self.ns3_path))
        
        # Search in examples/
        for py_file in self.ns3_path.glob("examples/**/*.py"):
            examples.append(py_file.relative_to(self.ns3_path))
        
        # Filter out test files and __init__.py
        examples = [
            p for p in examples 
            if not p.name.startswith("test_") 
            and p.name != "__init__.py"
            and "test" not in p.parts
        ]
        
        return sorted(examples)
    
    def process_all_python_examples(self, progress_callback=None) -> List[Dict]:
        """
        Process all Python examples in ns-3.
        
        Args:
            progress_callback: Optional callback(current, total, path) for progress updates
            
        Returns:
            List of processing results
        """
        examples = self.discover_python_examples()
        results = []
        
        for i, rel_path in enumerate(examples):
            if progress_callback:
                progress_callback(i, len(examples), str(rel_path))
            
            result = self.process_file(str(rel_path))
            results.append(result)
        
        if progress_callback:
            progress_callback(len(examples), len(examples), "Done")
        
        return results
    
    def get_processing_summary(self, results: List[Dict]) -> Dict:
        """Generate summary of processing results."""
        successful = [r for r in results if r["success"]]
        failed = [r for r in results if not r["success"]]
        
        total_nodes = sum(r["node_count"] for r in successful)
        total_links = sum(r["link_count"] for r in successful)
        
        all_errors = []
        for r in results:
            for err in r["errors"]:
                all_errors.append(f"{r['relative_path']}: {err}")
        
        return {
            "total_files": len(results),
            "successful": len(successful),
            "failed": len(failed),
            "total_nodes_extracted": total_nodes,
            "total_links_extracted": total_links,
            "success_rate": len(successful) / len(results) * 100 if results else 0,
            "errors": all_errors[:20],  # Limit to first 20 errors
            "successful_files": [r["relative_path"] for r in successful],
            "failed_files": [r["relative_path"] for r in failed],
        }
