"""
Network topology data models.

These models represent the network configuration that will be
translated to ns-3 simulation objects.
"""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional
import uuid


class NodeType(Enum):
    """
    Types of network nodes supported in the GUI.
    
    Note: In ns-3, all nodes are generic. This type is for GUI visualization
    and determines the icon/behavior in the editor.
    """
    HOST = auto()         # End device (client, server, workstation) - wired
    ROUTER = auto()       # Forwards packets between networks
    SWITCH = auto()       # Layer 2 device (also used to visualize CSMA segments)
    STATION = auto()      # WiFi station (wireless client)
    ACCESS_POINT = auto() # WiFi access point
    APPLICATION = auto()  # Socket application feed point (attaches to host)


class MediumType(Enum):
    """
    Type of network medium/connection for a node.
    
    This affects the visual representation in the GUI:
    - WIRED: Standard wired connection (default)
    - WIFI_STATION: WiFi client/station node (wireless icon)
    - WIFI_AP: WiFi access point (AP icon)
    - LTE_UE: LTE user equipment (mobile icon)
    - LTE_ENB: LTE eNodeB base station
    
    This is a property of the node, not the link, because in ns-3
    a node's network device determines what medium it uses.
    """
    WIRED = auto()        # Default wired (Ethernet/P2P)
    WIFI_STATION = auto() # WiFi station (client)
    WIFI_AP = auto()      # WiFi access point
    LTE_UE = auto()       # LTE user equipment
    LTE_ENB = auto()      # LTE base station


class ChannelType(Enum):
    """
    Types of network channel/medium for links.
    
    This represents the physical layer connection type:
    - POINT_TO_POINT: Dedicated link between exactly 2 nodes (like a cable)
    - CSMA: Shared medium where multiple nodes share bandwidth (like Ethernet hub)
    - WIFI: 802.11 wireless channel
    
    In ns-3, CSMA uses Carrier Sense Multiple Access protocol where nodes
    listen before transmitting to avoid collisions.
    """
    POINT_TO_POINT = auto()  # Dedicated point-to-point link
    CSMA = auto()            # Carrier Sense Multiple Access (shared medium)
    WIFI = auto()            # 802.11 WiFi wireless


class RoutingMode(Enum):
    """How routing is configured for a node."""
    AUTO = auto()       # Use GlobalRoutingHelper (automatic shortest path)
    MANUAL = auto()     # User-defined static routes only


class RouteType(Enum):
    """Type of routing table entry."""
    CONNECTED = auto()  # Directly connected network (auto-detected)
    STATIC = auto()     # Manually configured static route
    DEFAULT = auto()    # Default gateway route


@dataclass
class RouteEntry:
    """A single routing table entry."""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    destination: str = "0.0.0.0"      # Network address (e.g., "10.1.1.0")
    prefix_length: int = 24            # CIDR prefix (e.g., 24 for /24)
    gateway: str = "0.0.0.0"          # Next hop IP (0.0.0.0 = directly connected)
    interface: int = 0                 # Output interface index
    metric: int = 1                    # Route priority/cost
    route_type: RouteType = RouteType.STATIC
    enabled: bool = True
    
    @property
    def netmask(self) -> str:
        """Convert prefix length to dotted decimal netmask."""
        if self.prefix_length == 0:
            return "0.0.0.0"
        bits = (0xFFFFFFFF << (32 - self.prefix_length)) & 0xFFFFFFFF
        return f"{(bits >> 24) & 0xFF}.{(bits >> 16) & 0xFF}.{(bits >> 8) & 0xFF}.{bits & 0xFF}"
    
    @property
    def cidr(self) -> str:
        """Return destination in CIDR notation."""
        return f"{self.destination}/{self.prefix_length}"
    
    @property
    def is_default_route(self) -> bool:
        """Check if this is a default route."""
        return self.destination == "0.0.0.0" and self.prefix_length == 0
    
    @property
    def is_direct(self) -> bool:
        """Check if this is a directly connected route."""
        return self.gateway == "0.0.0.0" or self.route_type == RouteType.CONNECTED
    
    def matches_network(self, ip: str) -> bool:
        """Check if an IP address matches this route's network."""
        try:
            # Convert IPs to integers for comparison
            def ip_to_int(ip_str):
                parts = ip_str.split('.')
                return (int(parts[0]) << 24) + (int(parts[1]) << 16) + (int(parts[2]) << 8) + int(parts[3])
            
            ip_int = ip_to_int(ip)
            dest_int = ip_to_int(self.destination)
            mask_int = (0xFFFFFFFF << (32 - self.prefix_length)) & 0xFFFFFFFF
            
            return (ip_int & mask_int) == (dest_int & mask_int)
        except:
            return False


class PortType(Enum):
    """Types of physical ports."""
    ETHERNET = auto()
    FAST_ETHERNET = auto()
    GIGABIT_ETHERNET = auto()
    TEN_GIGABIT = auto()
    SERIAL = auto()
    FIBER = auto()
    WIRELESS = auto()


class VlanMode(Enum):
    """VLAN port modes for switches."""
    ACCESS = auto()
    TRUNK = auto()


@dataclass
class Position:
    """2D position on the canvas."""
    x: float = 0.0
    y: float = 0.0
    
    def to_tuple(self) -> tuple[float, float]:
        return (self.x, self.y)


# Port type specifications with default speeds
PORT_TYPE_SPECS = {
    PortType.ETHERNET: {"speed": "10Mbps", "name_prefix": "eth"},
    PortType.FAST_ETHERNET: {"speed": "100Mbps", "name_prefix": "fa"},
    PortType.GIGABIT_ETHERNET: {"speed": "1Gbps", "name_prefix": "gi"},
    PortType.TEN_GIGABIT: {"speed": "10Gbps", "name_prefix": "te"},
    PortType.SERIAL: {"speed": "1.544Mbps", "name_prefix": "se"},
    PortType.FIBER: {"speed": "10Gbps", "name_prefix": "fi"},
    PortType.WIRELESS: {"speed": "54Mbps", "name_prefix": "wlan"},
}

# Default port configurations per node type
DEFAULT_PORT_CONFIGS = {
    NodeType.HOST: {
        "num_ports": 1,
        "port_type": PortType.GIGABIT_ETHERNET,
    },
    NodeType.ROUTER: {
        "num_ports": 4,
        "port_type": PortType.GIGABIT_ETHERNET,
    },
    NodeType.SWITCH: {
        "num_ports": 8,
        "port_type": PortType.GIGABIT_ETHERNET,
    },
    NodeType.STATION: {
        "num_ports": 1,
        "port_type": PortType.WIRELESS,
    },
    NodeType.ACCESS_POINT: {
        "num_ports": 2,  # 1 wireless + 1 wired uplink
        "port_type": PortType.WIRELESS,
    },
    NodeType.APPLICATION: {
        "num_ports": 1,  # Virtual port to attach to host
        "port_type": PortType.GIGABIT_ETHERNET,
    },
}


@dataclass
class PortConfig:
    """
    Represents a physical/logical port on a network device.
    
    Includes Layer 1 (physical), Layer 2 (data link), and 
    Layer 3 (network) configurations.
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    
    # Physical layer (L1)
    port_number: int = 0
    port_name: str = ""
    port_type: PortType = PortType.GIGABIT_ETHERNET
    speed: str = "1Gbps"
    duplex: str = "full"  # full, half, auto
    enabled: bool = True
    mtu: int = 1500
    
    # Data link layer (L2)
    mac_address: str = ""
    vlan_id: int = 1
    vlan_mode: VlanMode = VlanMode.ACCESS
    trunk_allowed_vlans: str = "1-4094"
    
    # Network layer (L3)
    ip_address: str = ""
    netmask: str = "255.255.255.0"
    
    # Link binding
    connected_link_id: Optional[str] = None
    
    @property
    def is_connected(self) -> bool:
        """Check if port is connected to a link."""
        return self.connected_link_id is not None
    
    @property 
    def display_name(self) -> str:
        """Get display name for the port."""
        return self.port_name or f"port{self.port_number}"
    
    @property
    def status_text(self) -> str:
        """Get status text for display."""
        if not self.enabled:
            return "disabled"
        if self.is_connected:
            return "connected"
        return "available"


@dataclass
class NodeModel:
    """
    Represents a network node (host, router, switch).
    
    Attributes:
        id: Unique identifier
        node_type: Type of node (HOST, ROUTER, SWITCH)
        medium_type: Network medium (WIRED, WIFI_STATION, WIFI_AP, etc.)
        name: Display name
        position: Canvas position
        ports: Physical/logical ports on this node
        
    Type-specific attributes:
        Host: is_server
        Router: routing_protocol, forwarding_enabled
        Switch: stp_enabled, switching_mode, subnet_base, subnet_mask
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    node_type: NodeType = NodeType.HOST
    medium_type: MediumType = MediumType.WIRED  # Network medium type
    name: str = ""
    position: Position = field(default_factory=Position)
    
    # Ports
    ports: list[PortConfig] = field(default_factory=list)
    
    # Host-specific properties
    is_server: bool = False
    
    # Router-specific properties
    routing_protocol: str = "static"  # static, olsr, aodv, ospf
    forwarding_enabled: bool = True
    
    # Switch-specific properties  
    stp_enabled: bool = False
    switching_mode: str = "learning"  # learning, hub
    subnet_base: str = ""  # e.g., "192.168.1.0" - if set, all connected hosts use this subnet
    subnet_mask: str = "255.255.255.0"
    _next_host_ip: int = field(default=1, repr=False)  # Next host IP in subnet
    
    # WiFi-specific properties (for STATION and ACCESS_POINT)
    wifi_standard: str = "802.11n"  # 802.11a, 802.11b, 802.11g, 802.11n, 802.11ac, 802.11ax
    wifi_ssid: str = "ns3-wifi"     # Network SSID (used by AP)
    wifi_channel: int = 1           # WiFi channel number (1-11 for 2.4GHz, 36-165 for 5GHz)
    wifi_band: str = "2.4GHz"       # 2.4GHz or 5GHz
    wifi_tx_power: float = 20.0     # Transmit power in dBm
    
    # Socket Application properties (for APPLICATION node type)
    # These define a custom socket-based packet sender/receiver
    app_attached_node_id: str = ""       # ID of host node this app attaches to
    app_role: str = "sender"             # "sender" or "receiver"
    app_protocol: str = "UDP"            # "UDP" or "TCP"
    app_remote_address: str = ""         # Destination IP (for sender)
    app_remote_port: int = 9000          # Destination port
    app_local_port: int = 9000           # Local port (for receiver)
    app_payload_type: str = "pattern"    # "pattern", "file", "callback"
    app_payload_data: str = ""           # Payload pattern or file path
    app_payload_size: int = 512          # Packet payload size in bytes
    app_send_count: int = 10             # Number of packets to send (0 = unlimited)
    app_send_interval: float = 1.0       # Interval between sends (seconds)
    app_start_time: float = 1.0          # Application start time
    app_stop_time: float = 9.0           # Application stop time
    
    # Routing table (for hosts and routers)
    routing_mode: RoutingMode = RoutingMode.AUTO
    routing_table: list[RouteEntry] = field(default_factory=list)
    default_gateway: str = ""  # Shortcut for hosts
    
    # Common optional properties
    description: str = ""
    
    def __post_init__(self):
        if not self.name:
            self.name = f"{self.node_type.name.lower()}_{self.id[:4]}"
        
        # Initialize default ports if none exist
        if not self.ports:
            self._initialize_default_ports()
    
    def _initialize_default_ports(self):
        """Create default ports based on node type."""
        config = DEFAULT_PORT_CONFIGS.get(self.node_type, DEFAULT_PORT_CONFIGS[NodeType.HOST])
        num_ports = config["num_ports"]
        port_type = config["port_type"]
        spec = PORT_TYPE_SPECS[port_type]
        
        for i in range(num_ports):
            port = PortConfig(
                port_number=i,
                port_name=f"{spec['name_prefix']}{i}",
                port_type=port_type,
                speed=spec["speed"],
            )
            self.ports.append(port)
    
    def add_port(self, port_type: PortType = PortType.GIGABIT_ETHERNET) -> PortConfig:
        """Add a new port to this node."""
        spec = PORT_TYPE_SPECS[port_type]
        port_num = len(self.ports)
        port = PortConfig(
            port_number=port_num,
            port_name=f"{spec['name_prefix']}{port_num}",
            port_type=port_type,
            speed=spec["speed"],
        )
        self.ports.append(port)
        return port
    
    def remove_port(self, port_id: str) -> Optional[PortConfig]:
        """Remove a port by ID (only if not connected)."""
        for i, port in enumerate(self.ports):
            if port.id == port_id:
                if port.is_connected:
                    return None  # Can't remove connected port
                return self.ports.pop(i)
        return None
    
    def get_port(self, port_id: str) -> Optional[PortConfig]:
        """Get a port by ID."""
        for port in self.ports:
            if port.id == port_id:
                return port
        return None
    
    def get_port_by_number(self, port_number: int) -> Optional[PortConfig]:
        """Get a port by its number."""
        for port in self.ports:
            if port.port_number == port_number:
                return port
        return None
    
    def get_available_ports(self) -> list[PortConfig]:
        """Get all ports that are not connected."""
        return [p for p in self.ports if not p.is_connected and p.enabled]
    
    def get_port_for_link(self, link_id: str) -> Optional[PortConfig]:
        """Get the port connected to a specific link."""
        for port in self.ports:
            if port.connected_link_id == link_id:
                return port
        return None
    
    # Routing table management methods
    def add_route(self, route: RouteEntry) -> None:
        """Add a route to the routing table."""
        self.routing_table.append(route)
    
    def remove_route(self, route_id: str) -> bool:
        """Remove a route by ID."""
        for i, route in enumerate(self.routing_table):
            if route.id == route_id:
                self.routing_table.pop(i)
                return True
        return False
    
    def get_route(self, route_id: str) -> Optional[RouteEntry]:
        """Get a route by ID."""
        for route in self.routing_table:
            if route.id == route_id:
                return route
        return None
    
    def clear_routes(self, route_type: Optional[RouteType] = None) -> None:
        """Clear routes, optionally filtered by type."""
        if route_type is None:
            self.routing_table.clear()
        else:
            self.routing_table = [r for r in self.routing_table if r.route_type != route_type]
    
    def get_routes_by_type(self, route_type: RouteType) -> list[RouteEntry]:
        """Get all routes of a specific type."""
        return [r for r in self.routing_table if r.route_type == route_type]
    
    def has_default_route(self) -> bool:
        """Check if there's a default route configured."""
        return any(r.is_default_route for r in self.routing_table)
    
    def set_default_gateway_route(self, gateway: str, interface: int = 0) -> None:
        """Set or update the default gateway route."""
        # Remove existing default route
        self.routing_table = [r for r in self.routing_table if not r.is_default_route]
        
        # Add new default route
        if gateway:
            self.default_gateway = gateway
            self.routing_table.append(RouteEntry(
                destination="0.0.0.0",
                prefix_length=0,
                gateway=gateway,
                interface=interface,
                route_type=RouteType.DEFAULT
            ))
    
    # Legacy compatibility - interfaces property maps to ports
    @property
    def interfaces(self) -> list[PortConfig]:
        """Legacy property for backward compatibility."""
        return self.ports
    
    def get_interface_for_link(self, link_id: str) -> Optional[PortConfig]:
        """Legacy method for backward compatibility."""
        return self.get_port_for_link(link_id)


@dataclass
class LinkModel:
    """
    Represents a network link/channel between two ports on two nodes.
    
    Attributes:
        id: Unique identifier
        channel_type: Type of channel (P2P, CSMA)
        source_node_id: ID of source node
        target_node_id: ID of target node
        source_port_id: ID of port on source node
        target_port_id: ID of port on target node
        data_rate: Link speed (e.g., "100Mbps")
        delay: Propagation delay (e.g., "2ms")
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    channel_type: ChannelType = ChannelType.POINT_TO_POINT
    source_node_id: str = ""
    target_node_id: str = ""
    source_port_id: str = ""
    target_port_id: str = ""
    data_rate: str = "100Mbps"
    delay: str = "2ms"
    
    @property
    def name(self) -> str:
        return f"link_{self.id[:4]}"


@dataclass 
class ApplicationConfig:
    """Configuration for a network application (UDP echo for MVP)."""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    app_type: str = "udp_echo"  # Only UDP echo for MVP
    server_node_id: str = ""
    client_node_id: str = ""
    port: int = 9
    start_time: float = 1.0  # seconds
    stop_time: float = 10.0  # seconds
    packet_size: int = 1024  # bytes
    num_packets: int = 100


@dataclass
class NetworkModel:
    """
    Root model containing the entire network topology.
    
    This is the main data structure that gets translated to ns-3.
    """
    nodes: dict[str, NodeModel] = field(default_factory=dict)
    links: dict[str, LinkModel] = field(default_factory=dict)
    applications: list[ApplicationConfig] = field(default_factory=list)
    
    # Global simulation settings
    simulation_duration: float = 10.0  # seconds
    
    # Saved traffic flows (persisted with the topology file)
    saved_flows: list = field(default_factory=list)  # List of TrafficFlow objects
    
    # Import metadata and tracking
    import_metadata: dict = field(default_factory=dict)  # Source file info, etc.
    todos: list = field(default_factory=list)  # Unhandled patterns from import
    warnings: list = field(default_factory=list)  # Non-critical issues
    
    # Auto IP assignment tracking
    _next_subnet: int = field(default=1, repr=False)
    
    def add_node(self, node_type: NodeType, position: Position) -> NodeModel:
        """Create and add a new node to the network."""
        node = NodeModel(node_type=node_type, position=position)
        self.nodes[node.id] = node
        return node
    
    def remove_node(self, node_id: str) -> Optional[NodeModel]:
        """Remove a node and all its connected links."""
        if node_id not in self.nodes:
            return None
        
        # Remove connected links
        links_to_remove = [
            link_id for link_id, link in self.links.items()
            if link.source_node_id == node_id or link.target_node_id == node_id
        ]
        for link_id in links_to_remove:
            self.remove_link(link_id)
        
        return self.nodes.pop(node_id)
    
    def add_link(
        self, 
        source_id: str, 
        target_id: str, 
        channel_type: ChannelType = ChannelType.POINT_TO_POINT,
        source_port_id: str = "",
        target_port_id: str = ""
    ) -> Optional[LinkModel]:
        """
        Create and add a link between two nodes.
        
        If port IDs are not specified, automatically selects available ports.
        """
        if source_id not in self.nodes or target_id not in self.nodes:
            return None
        
        source_node = self.nodes[source_id]
        target_node = self.nodes[target_id]
        
        # Find or validate ports
        if source_port_id:
            source_port = source_node.get_port(source_port_id)
            if not source_port or source_port.is_connected:
                return None
        else:
            available = source_node.get_available_ports()
            if not available:
                return None
            source_port = available[0]
        
        if target_port_id:
            target_port = target_node.get_port(target_port_id)
            if not target_port or target_port.is_connected:
                return None
        else:
            available = target_node.get_available_ports()
            if not available:
                return None
            target_port = available[0]
        
        # Check if link already exists between these ports
        for link in self.links.values():
            if (link.source_port_id == source_port.id and link.target_port_id == target_port.id) or \
               (link.source_port_id == target_port.id and link.target_port_id == source_port.id):
                return None
        
        link = LinkModel(
            channel_type=channel_type,
            source_node_id=source_id,
            target_node_id=target_id,
            source_port_id=source_port.id,
            target_port_id=target_port.id
        )
        self.links[link.id] = link
        
        # Bind ports to link
        source_port.connected_link_id = link.id
        target_port.connected_link_id = link.id
        
        # Auto-assign IP addresses based on topology
        self._assign_ip_addresses(source_node, source_port, target_node, target_port)
        
        return link
    
    def _assign_ip_addresses(
        self, 
        node1: NodeModel, 
        port1: PortConfig, 
        node2: NodeModel, 
        port2: PortConfig
    ):
        """
        Assign IP addresses based on network topology.
        
        Rules:
        1. If connecting to a switch with subnet_base configured, 
           use that subnet for the non-switch node
        2. Switch ports don't get IPs (Layer 2 device)
        3. Otherwise, create a new point-to-point subnet
        """
        # Check if either node is a switch with subnet configured
        switch_node = None
        other_node = None
        other_port = None
        switch_port = None
        
        if node1.node_type == NodeType.SWITCH:
            switch_node = node1
            switch_port = port1
            other_node = node2
            other_port = port2
        elif node2.node_type == NodeType.SWITCH:
            switch_node = node2
            switch_port = port2
            other_node = node1
            other_port = port1
        
        if switch_node and switch_node.subnet_base:
            # Use switch's subnet for the connected device
            # Switch ports typically don't have IPs (Layer 2)
            switch_port.ip_address = ""
            
            # Assign next available IP in switch's subnet to the other device
            base_parts = switch_node.subnet_base.split('.')
            if len(base_parts) == 4:
                host_ip = switch_node._next_host_ip
                switch_node._next_host_ip += 1
                # Skip .0 (network) and .255 (broadcast)
                if host_ip == 0:
                    host_ip = 1
                    switch_node._next_host_ip = 2
                other_port.ip_address = f"{base_parts[0]}.{base_parts[1]}.{base_parts[2]}.{host_ip}"
                other_port.netmask = switch_node.subnet_mask
        
        elif switch_node:
            # Switch without subnet config - no IPs assigned
            switch_port.ip_address = ""
            other_port.ip_address = ""
        
        else:
            # Point-to-point link between non-switch devices
            subnet = self._next_subnet
            self._next_subnet += 1
            port1.ip_address = f"10.0.{subnet}.1"
            port2.ip_address = f"10.0.{subnet}.2"
    
    def reassign_switch_ips(self, switch_id: str):
        """
        Reassign IPs to all hosts connected to a switch based on its subnet config.
        Call this after changing a switch's subnet_base.
        """
        switch = self.nodes.get(switch_id)
        if not switch or switch.node_type != NodeType.SWITCH:
            return
        
        if not switch.subnet_base:
            return
        
        # Reset host IP counter
        switch._next_host_ip = 1
        
        # Find all links connected to this switch
        for link in self.links.values():
            other_node = None
            other_port = None
            
            if link.source_node_id == switch_id:
                other_node = self.nodes.get(link.target_node_id)
                if other_node:
                    other_port = other_node.get_port(link.target_port_id)
            elif link.target_node_id == switch_id:
                other_node = self.nodes.get(link.source_node_id)
                if other_node:
                    other_port = other_node.get_port(link.source_port_id)
            
            if other_node and other_port and other_node.node_type != NodeType.SWITCH:
                base_parts = switch.subnet_base.split('.')
                if len(base_parts) == 4:
                    host_ip = switch._next_host_ip
                    switch._next_host_ip += 1
                    other_port.ip_address = f"{base_parts[0]}.{base_parts[1]}.{base_parts[2]}.{host_ip}"
                    other_port.netmask = switch.subnet_mask
    
    def remove_link(self, link_id: str) -> Optional[LinkModel]:
        """Remove a link and clean up port bindings."""
        if link_id not in self.links:
            return None
        
        link = self.links[link_id]
        
        # Unbind ports
        source_node = self.nodes.get(link.source_node_id)
        target_node = self.nodes.get(link.target_node_id)
        
        if source_node:
            port = source_node.get_port(link.source_port_id)
            if port:
                port.connected_link_id = None
                port.ip_address = ""
        
        if target_node:
            port = target_node.get_port(link.target_port_id)
            if port:
                port.connected_link_id = None
                port.ip_address = ""
        
        return self.links.pop(link_id)
    
    def get_node(self, node_id: str) -> Optional[NodeModel]:
        """Get a node by ID."""
        return self.nodes.get(node_id)
    
    def get_link(self, link_id: str) -> Optional[LinkModel]:
        """Get a link by ID."""
        return self.links.get(link_id)
    
    def clear(self):
        """Clear all nodes, links, and applications."""
        self.nodes.clear()
        self.links.clear()
        self.applications.clear()
        self._next_subnet = 1
    
    def to_dict(self) -> dict:
        """Serialize to dictionary for saving."""
        return {
            "nodes": {
                nid: {
                    "id": n.id,
                    "node_type": n.node_type.name,
                    "name": n.name,
                    "position": {"x": n.position.x, "y": n.position.y},
                    "ports": [
                        {
                            "id": p.id,
                            "port_number": p.port_number,
                            "port_name": p.port_name,
                            "port_type": p.port_type.name,
                            "speed": p.speed,
                            "duplex": p.duplex,
                            "enabled": p.enabled,
                            "mtu": p.mtu,
                            "mac_address": p.mac_address,
                            "vlan_id": p.vlan_id,
                            "vlan_mode": p.vlan_mode.name,
                            "ip_address": p.ip_address,
                            "netmask": p.netmask,
                            "connected_link_id": p.connected_link_id
                        }
                        for p in n.ports
                    ]
                }
                for nid, n in self.nodes.items()
            },
            "links": {
                lid: {
                    "id": l.id,
                    "channel_type": l.channel_type.name,
                    "source_node_id": l.source_node_id,
                    "target_node_id": l.target_node_id,
                    "source_port_id": l.source_port_id,
                    "target_port_id": l.target_port_id,
                    "data_rate": l.data_rate,
                    "delay": l.delay
                }
                for lid, l in self.links.items()
            },
            "simulation_duration": self.simulation_duration
        }
