"""
NS-3 Script Parser.

Parses ns-3 Python example scripts to extract network topology information.
Converts extracted topology to NetworkModel format for use in the GUI.

This module handles Phase 1 of ns-3 test integration:
- Parse Python scripts using AST
- Extract node containers, links, IP assignments
- Convert to topology.json format
- Mirror ns-3 directory structure in workspace
"""

import ast
import re
import json
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Set, Any
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class ChannelMedium(Enum):
    """
    Types of network channel/medium in ns-3.
    
    This represents the physical layer connection type, NOT a node type.
    - POINT_TO_POINT: Direct dedicated link between exactly 2 nodes
    - CSMA: Shared medium (like Ethernet hub/bus) where multiple nodes share bandwidth
    - WIFI: Wireless shared medium with 802.11 protocol
    - LTE: Cellular network connection
    """
    POINT_TO_POINT = "point-to-point"
    CSMA = "csma"  # Carrier Sense Multiple Access - shared Ethernet-like medium
    WIFI = "wifi"
    LTE = "lte"
    UNKNOWN = "unknown"


# Alias for backward compatibility
LinkType = ChannelMedium


class NodeRole(Enum):
    """
    Inferred role of a node in the network.
    
    Note: In ns-3, all nodes are generic - their "type" is inferred from:
    - Number of connections (many connections -> likely a router)
    - Applications installed (server apps vs client apps)
    - Position in topology (edge vs center)
    """
    HOST = "host"          # End device (client or server)
    ROUTER = "router"      # Forwards packets between networks
    SWITCH = "switch"      # Layer 2 device (GUI representation of CSMA segment)
    ACCESS_POINT = "access_point"  # Wireless access point
    UNKNOWN = "unknown"


# Alias for backward compatibility
NodeType = NodeRole


class MediumHint(Enum):
    """
    Hint about what network medium a node uses.
    
    This is inferred from the helper types used to install devices on nodes.
    """
    WIRED = "wired"              # Default - P2P or CSMA
    WIFI_STATION = "wifi_sta"   # WiFi station (client)
    WIFI_AP = "wifi_ap"         # WiFi access point
    LTE_UE = "lte_ue"           # LTE user equipment
    LTE_ENB = "lte_enb"         # LTE eNodeB


@dataclass
class ExtractedNode:
    """
    A node extracted from ns-3 script.
    
    In ns-3, all nodes are generic NodeContainer entries. The "type" here
    is inferred based on connectivity and installed applications, not 
    explicitly defined in the script.
    
    Attributes:
        container_name: Name of the NodeContainer (e.g., "nodes", "servers")
        index: Index within the container
        node_type: Inferred role (HOST, ROUTER, etc.)
        medium_hint: Network medium type (WIRED, WIFI_STATION, etc.)
        inferred_role: More specific role description (e.g., "server", "client")
    """
    container_name: str
    index: int
    node_type: NodeRole = NodeRole.HOST
    medium_hint: MediumHint = MediumHint.WIRED
    inferred_role: str = ""  # e.g., "server", "client", "gateway"
    
    @property
    def key(self) -> Tuple[str, int]:
        """Unique key for this node."""
        return (self.container_name, self.index)


@dataclass
class ExtractedLink:
    """
    A network connection extracted from ns-3 script.
    
    Represents the channel/medium connecting nodes. The channel_medium
    determines how nodes communicate:
    - POINT_TO_POINT: Dedicated link between exactly 2 nodes
    - CSMA: Shared medium (multiple nodes, like Ethernet bus/hub)
    - WIFI: Wireless shared medium
    
    Attributes:
        source_container: NodeContainer name for source node
        source_index: Index of source node in its container
        target_container: NodeContainer name for target node  
        target_index: Index of target node in its container
        link_type: Channel medium type (POINT_TO_POINT, CSMA, etc.)
        data_rate: Configured data rate (e.g., "5Mbps", "1Gbps")
        delay: Configured delay (e.g., "2ms", "10us")
        device_container: Name of the NetDeviceContainer variable
    """
    source_container: str
    source_index: int
    target_container: str
    target_index: int
    link_type: ChannelMedium = ChannelMedium.POINT_TO_POINT
    data_rate: str = ""
    delay: str = ""
    device_container: str = ""  # Name of NetDeviceContainer
    helper_name: str = ""  # Name of helper variable used
    
    @property
    def source_key(self) -> Tuple[str, int]:
        return (self.source_container, self.source_index)
    
    @property
    def target_key(self) -> Tuple[str, int]:
        return (self.target_container, self.target_index)


@dataclass
class ExtractedIPAssignment:
    """IP address assignment extracted from script."""
    device_container: str
    base_address: str
    netmask: str


@dataclass
class ExtractedApplication:
    """Application/traffic configuration extracted from script."""
    app_type: str  # "UdpEcho", "OnOff", "PacketSink", "BulkSend", etc.
    node_container: str
    node_index: int
    port: int = 9
    is_server: bool = False
    remote_address: str = ""     # Destination IP address
    protocol: str = "UDP"        # UDP or TCP
    data_rate: str = ""          # e.g., "500kb/s"
    packet_size: int = 0         # bytes
    start_time: float = 0.0
    stop_time: float = 0.0
    helper_var: str = ""         # Variable name of helper (for tracking)


@dataclass
class ExtractedTopology:
    """Complete topology extracted from an ns-3 script."""
    source_file: str
    script_name: str = ""
    module_name: str = ""  # e.g., "point-to-point", "csma"
    description: str = ""
    
    # Extracted elements
    nodes: List[ExtractedNode] = field(default_factory=list)
    links: List[ExtractedLink] = field(default_factory=list)
    ip_assignments: List[ExtractedIPAssignment] = field(default_factory=list)
    applications: List[ExtractedApplication] = field(default_factory=list)
    
    # Metadata
    node_containers: Dict[str, int] = field(default_factory=dict)  # name -> count
    device_containers: Dict[str, str] = field(default_factory=dict)  # name -> link_type
    helper_configs: Dict[str, Dict[str, str]] = field(default_factory=dict)  # helper -> {attr: value}
    
    # Parsing status
    parse_success: bool = False
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    
    # Simulation parameters
    duration: float = 10.0
    
    def add_error(self, msg: str):
        self.errors.append(msg)
        
    def add_warning(self, msg: str):
        self.warnings.append(msg)
    
    def get_node(self, container: str, index: int) -> Optional[ExtractedNode]:
        """Find a node by container name and index."""
        for node in self.nodes:
            if node.container_name == container and node.index == index:
                return node
        return None


class NS3PythonVisitor(ast.NodeVisitor):
    """
    AST visitor that extracts ns-3 topology information from Python scripts.
    
    Recognizes patterns like:
    - nodes = ns.NodeContainer()
    - nodes.Create(4)
    - p2p.Install(nodes.Get(0), nodes.Get(1))
    - address.SetBase("10.1.1.0", "255.255.255.0")
    """
    
    def __init__(self, topology: ExtractedTopology):
        self.topology = topology
        self.variables: Dict[str, Any] = {}  # Track variable assignments
        self.current_helper: Optional[str] = None  # Track current helper being configured
        self.helper_types: Dict[str, str] = {}  # variable name -> helper type
        self.app_helpers: Dict[str, Dict[str, Any]] = {}  # app helper var -> {config}
        
    def visit_Assign(self, node: ast.Assign):
        """Track variable assignments to understand context."""
        if len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            var_name = node.targets[0].id
            
            # Track simple numeric assignments
            if isinstance(node.value, ast.Constant) and isinstance(node.value.value, (int, float)):
                self.variables[var_name] = node.value.value
            
            # Track NodeContainer creation
            if self._is_ns3_call(node.value, "NodeContainer"):
                self.helper_types[var_name] = "NodeContainer"
                
            # Track helper creation
            elif self._is_ns3_call(node.value, "PointToPointHelper"):
                self.helper_types[var_name] = "PointToPointHelper"
                self.topology.helper_configs[var_name] = {}
                
            elif self._is_ns3_call(node.value, "CsmaHelper"):
                self.helper_types[var_name] = "CsmaHelper"
                self.topology.helper_configs[var_name] = {}
                
            elif self._is_ns3_call(node.value, "Ipv4AddressHelper"):
                self.helper_types[var_name] = "Ipv4AddressHelper"
                
            elif self._is_ns3_call(node.value, "InternetStackHelper"):
                self.helper_types[var_name] = "InternetStackHelper"
            
            # Track application helpers
            elif self._is_ns3_call(node.value, "OnOffHelper"):
                self.helper_types[var_name] = "OnOffHelper"
                self._parse_onoff_helper(var_name, node.value)
                
            elif self._is_ns3_call(node.value, "PacketSinkHelper"):
                self.helper_types[var_name] = "PacketSinkHelper"
                self._parse_packet_sink_helper(var_name, node.value)
                
            elif self._is_ns3_call(node.value, "UdpEchoServerHelper"):
                self.helper_types[var_name] = "UdpEchoServerHelper"
                self._parse_udp_echo_server_helper(var_name, node.value)
                
            elif self._is_ns3_call(node.value, "UdpEchoClientHelper"):
                self.helper_types[var_name] = "UdpEchoClientHelper"
                self._parse_udp_echo_client_helper(var_name, node.value)
                
            elif self._is_ns3_call(node.value, "BulkSendHelper"):
                self.helper_types[var_name] = "BulkSendHelper"
                self._parse_bulk_send_helper(var_name, node.value)
                
            # Track Install() results (NetDeviceContainer)
            elif isinstance(node.value, ast.Call):
                call_name = self._get_method_name(node.value)
                if call_name == "Install":
                    obj_name = self._get_object_name(node.value)
                    # Check if this is an application install
                    if obj_name and obj_name in self.app_helpers:
                        self._handle_app_install(obj_name, var_name, node.value)
                    else:
                        self.helper_types[var_name] = "NetDeviceContainer"
                    
        self.generic_visit(node)
    
    def visit_Expr(self, node: ast.Expr):
        """Visit expression statements (method calls without assignment)."""
        if isinstance(node.value, ast.Call):
            self._process_call(node.value)
        self.generic_visit(node)
    
    def visit_For(self, node: ast.For):
        """
        Visit for loops to extract topology from loop bodies.
        
        Handles patterns like:
            for i in range(4):
                container = ns.NodeContainer()
                container.Add(terminals.Get(i))
                container.Add(csmaSwitch)
                link = csma.Install(container)
        """
        # Try to determine loop range
        loop_count = self._get_loop_range(node)
        loop_var = node.target.id if isinstance(node.target, ast.Name) else None
        
        if loop_count is not None and loop_var:
            # Process the loop body for each iteration conceptually
            # We'll analyze the body to understand the pattern
            self._process_loop_body(node.body, loop_var, loop_count)
        
        # Still do generic visit to catch other patterns
        self.generic_visit(node)
    
    def _get_loop_range(self, node: ast.For) -> Optional[int]:
        """Extract the range count from a for loop."""
        # for i in range(n):
        if isinstance(node.iter, ast.Call):
            if isinstance(node.iter.func, ast.Name) and node.iter.func.id == "range":
                if node.iter.args:
                    return self._get_int_value(node.iter.args[0])
        return None
    
    def _process_loop_body(self, body: list, loop_var: str, loop_count: int):
        """
        Process a for loop body to extract topology patterns.
        
        Recognizes patterns like building temporary containers and installing links.
        """
        # Track what's happening in the loop
        temp_container_var = None
        source_container = None
        target_container = None
        helper_var = None
        
        for stmt in body:
            # Look for: container = ns.NodeContainer()
            if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1:
                if isinstance(stmt.targets[0], ast.Name):
                    var_name = stmt.targets[0].id
                    if self._is_ns3_call(stmt.value, "NodeContainer"):
                        temp_container_var = var_name
                    
                    # Look for: link = helper.Install(container)
                    elif isinstance(stmt.value, ast.Call):
                        method_name = self._get_method_name(stmt.value)
                        if method_name == "Install":
                            helper_var = self._get_object_name(stmt.value)
            
            # Look for: container.Add(source.Get(i)) or container.Add(target)
            elif isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
                method_name = self._get_method_name(stmt.value)
                obj_name = self._get_object_name(stmt.value)
                
                if method_name == "Add" and obj_name == temp_container_var:
                    # Analyze what's being added
                    if stmt.value.args:
                        arg = stmt.value.args[0]
                        added_container = self._extract_container_from_get(arg)
                        if added_container:
                            if source_container is None:
                                source_container = added_container
                            else:
                                target_container = added_container
        
        # If we found a valid pattern, create the links
        if source_container and target_container and helper_var:
            self._create_loop_links(
                source_container, target_container, 
                helper_var, loop_var, loop_count
            )
    
    def _extract_container_from_get(self, node: ast.AST) -> Optional[str]:
        """Extract container name from expressions like 'terminals.Get(i)' or 'csmaSwitch'."""
        # Handle: container.Get(i)
        if isinstance(node, ast.Call):
            method_name = self._get_method_name(node)
            if method_name == "Get":
                return self._get_object_name(node)
        # Handle: just a variable name (container itself)
        elif isinstance(node, ast.Name):
            return node.id
        # Handle: ns.NodeContainer reference
        elif isinstance(node, ast.Attribute):
            return node.attr
        return None
    
    def _create_loop_links(self, source_container: str, target_container: str,
                           helper_var: str, loop_var: str, loop_count: int):
        """Create links based on loop analysis."""
        # Determine link type from helper
        helper_type = self.helper_types.get(helper_var, "")
        if "Csma" in helper_type:
            link_type = ChannelMedium.CSMA
        elif "PointToPoint" in helper_type:
            link_type = ChannelMedium.POINT_TO_POINT
        else:
            link_type = ChannelMedium.UNKNOWN
        
        # Get node counts
        source_count = self.topology.node_containers.get(source_container, 0)
        target_count = self.topology.node_containers.get(target_container, 0)
        
        # Track existing links to avoid duplicates
        existing_links = set()
        for link in self.topology.links:
            existing_links.add((link.source_container, link.source_index, 
                               link.target_container, link.target_index))
        
        # Create links from each source node to the target
        # Pattern: for i in range(n): connect source[i] to target
        for i in range(min(loop_count, source_count)):
            # Target is usually a single node (like a switch)
            target_idx = 0 if target_count == 1 else (i % target_count)
            
            # Check for duplicate
            link_key = (source_container, i, target_container, target_idx)
            if link_key in existing_links:
                continue
            
            link = ExtractedLink(
                source_container=source_container,
                source_index=i,
                target_container=target_container,
                target_index=target_idx,
                link_type=link_type,
                helper_name=helper_var,
            )
            
            self.topology.links.append(link)
    
    def visit_Call(self, node: ast.Call):
        """Visit all function/method calls."""
        self._process_call(node)
        self.generic_visit(node)
    
    def _process_call(self, node: ast.Call):
        """Process a function/method call to extract topology info."""
        method_name = self._get_method_name(node)
        obj_name = self._get_object_name(node)
        
        if not method_name:
            return
            
        # NodeContainer.Create(n)
        if method_name == "Create" and obj_name:
            self._handle_create(obj_name, node)
            
        # Helper.Install(...)
        elif method_name == "Install" and obj_name:
            self._handle_install(obj_name, node)
            
        # Helper.SetDeviceAttribute(...) / SetChannelAttribute(...)
        elif method_name in ("SetDeviceAttribute", "SetChannelAttribute") and obj_name:
            self._handle_set_attribute(obj_name, method_name, node)
            
        # Ipv4AddressHelper.SetBase(...)
        elif method_name == "SetBase" and obj_name:
            self._handle_set_base(obj_name, node)
            
        # Ipv4AddressHelper.Assign(...)
        elif method_name == "Assign" and obj_name:
            self._handle_assign(obj_name, node)
            
        # Simulator.Stop(...)
        elif method_name == "Stop":
            # Check if this is Simulator.Stop or app.Stop
            if obj_name and obj_name in ["Simulator", "ns"]:
                self._handle_simulator_stop(node)
            elif obj_name:
                self._handle_app_stop(obj_name, node)
                
        # app.Start(...)
        elif method_name == "Start" and obj_name:
            self._handle_app_start(obj_name, node)
            
        # Application helpers - SetAttribute, SetConstantRate
        elif method_name in ("SetAttribute", "SetConstantRate") and obj_name:
            self._handle_app_attribute(obj_name, node)
    
    def _handle_create(self, container_name: str, node: ast.Call):
        """Handle NodeContainer.Create(n) call."""
        if not node.args:
            return
        
        # Try to get the count
        count = self._get_int_value(node.args[0])
        
        # Infer medium type from container name
        medium_hint = self._infer_medium_from_name(container_name)
        
        # Infer node type from container name
        node_type = self._infer_node_type_from_name(container_name)
        
        if count is None:
            # Use default count and record as TODO
            default_count = 3
            self.topology.add_warning(
                f"Could not determine node count for {container_name}.Create(), using default={default_count}"
            )
            count = default_count
            
        self.topology.node_containers[container_name] = count
        
        # Create individual node entries
        for i in range(count):
            ext_node = ExtractedNode(
                container_name=container_name,
                index=i,
                node_type=node_type,
                medium_hint=medium_hint,
            )
            self.topology.nodes.append(ext_node)
    
    def _infer_node_type_from_name(self, container_name: str) -> NodeRole:
        """Infer node type/role from container variable name."""
        name_lower = container_name.lower()
        
        # Switch patterns
        if "switch" in name_lower:
            return NodeRole.SWITCH
        if "bridge" in name_lower:
            return NodeRole.SWITCH
        if "hub" in name_lower:
            return NodeRole.SWITCH
            
        # Router patterns
        if "router" in name_lower:
            return NodeRole.ROUTER
        if "gateway" in name_lower:
            return NodeRole.ROUTER
            
        # Access point patterns
        if "ap" in name_lower and ("wifi" in name_lower or "wlan" in name_lower):
            return NodeRole.ACCESS_POINT
        if "accesspoint" in name_lower:
            return NodeRole.ACCESS_POINT
            
        # Default to HOST
        return NodeRole.HOST
    
    def _infer_medium_from_name(self, container_name: str) -> MediumHint:
        """Infer network medium type from container variable name."""
        name_lower = container_name.lower()
        
        # WiFi patterns
        if "wifista" in name_lower or "wifi_sta" in name_lower or "stanode" in name_lower:
            return MediumHint.WIFI_STATION
        if "wifiap" in name_lower or "wifi_ap" in name_lower or "apnode" in name_lower:
            return MediumHint.WIFI_AP
        if "wifi" in name_lower:
            # Generic wifi - assume station
            return MediumHint.WIFI_STATION
            
        # LTE patterns
        if "ue" in name_lower and "lte" in name_lower:
            return MediumHint.LTE_UE
        if "enb" in name_lower or "enodeb" in name_lower:
            return MediumHint.LTE_ENB
        if "lte" in name_lower:
            return MediumHint.LTE_UE  # Default to UE
            
        # Default to wired
        return MediumHint.WIRED
    
    def _handle_install(self, helper_name: str, node: ast.Call):
        """Handle Helper.Install(...) call to extract links."""
        helper_type = self.helper_types.get(helper_name, "")
        
        if helper_type == "PointToPointHelper":
            self._handle_p2p_install(helper_name, node)
        elif helper_type == "CsmaHelper":
            self._handle_csma_install(helper_name, node)
        elif helper_type == "WifiHelper":
            self._handle_wifi_install(helper_name, node)
        elif helper_type == "InternetStackHelper":
            # Internet stack install - just note it
            pass
        else:
            # Try to infer from helper name patterns
            helper_lower = helper_name.lower()
            if "p2p" in helper_lower or "pointtopoint" in helper_lower:
                self._handle_p2p_install(helper_name, node)
            elif "csma" in helper_lower:
                self._handle_csma_install(helper_name, node)
            elif "wifi" in helper_lower:
                self._handle_wifi_install(helper_name, node)
            elif len(node.args) == 2:
                # Two args usually means P2P between two nodes
                self._handle_p2p_install(helper_name, node)
            elif len(node.args) == 1:
                # One arg could be either - check if container has 2 nodes
                container_ref = self._parse_node_container_reference(node.args[0])
                if container_ref:
                    container_name = container_ref[0]
                    count = self.topology.node_containers.get(container_name, 0)
                    if count == 2:
                        # 2 nodes with P2P helper pattern
                        self._handle_p2p_install(helper_name, node)
                    else:
                        # Multiple nodes -> CSMA/shared medium
                        self._handle_csma_install(helper_name, node)
    
    def _handle_p2p_install(self, helper_name: str, node: ast.Call):
        """
        Handle PointToPointHelper.Install(...).
        
        Supports two patterns:
        1. Install(node1, node2) - connects two specific nodes
        2. Install(nodeContainer) - connects nodes 0 and 1 in the container
        """
        if len(node.args) == 2:
            # Pattern 1: Install(node1, node2)
            source = self._parse_node_reference(node.args[0])
            target = self._parse_node_reference(node.args[1])
            
            if source and target:
                config = self.topology.helper_configs.get(helper_name, {})
                
                link = ExtractedLink(
                    source_container=source[0],
                    source_index=source[1],
                    target_container=target[0],
                    target_index=target[1],
                    link_type=LinkType.POINT_TO_POINT,
                    data_rate=config.get("DataRate", ""),
                    delay=config.get("Delay", ""),
                )
                self.topology.links.append(link)
                
        elif len(node.args) == 1:
            # Pattern 2: Install(nodeContainer) - connects node 0 to node 1
            container_ref = self._parse_node_container_reference(node.args[0])
            
            if container_ref:
                container_name, start_idx, end_idx = container_ref
                count = self.topology.node_containers.get(container_name, 0)
                
                # Default: connect first two nodes
                if start_idx is None:
                    start_idx = 0
                if end_idx is None:
                    end_idx = min(1, count - 1)
                
                # For P2P with container, connect consecutive pairs
                # Most common case: 2 nodes -> 1 link between them
                config = self.topology.helper_configs.get(helper_name, {})
                
                if count == 2 or (end_idx - start_idx) == 1:
                    # Simple case: connect node 0 to node 1
                    link = ExtractedLink(
                        source_container=container_name,
                        source_index=start_idx,
                        target_container=container_name,
                        target_index=start_idx + 1 if start_idx + 1 <= end_idx else end_idx,
                        link_type=LinkType.POINT_TO_POINT,
                        data_rate=config.get("DataRate", ""),
                        delay=config.get("Delay", ""),
                    )
                    self.topology.links.append(link)
                else:
                    # Multiple nodes: create chain of P2P links
                    for i in range(start_idx, end_idx):
                        link = ExtractedLink(
                            source_container=container_name,
                            source_index=i,
                            target_container=container_name,
                            target_index=i + 1,
                            link_type=LinkType.POINT_TO_POINT,
                            data_rate=config.get("DataRate", ""),
                            delay=config.get("Delay", ""),
                        )
                        self.topology.links.append(link)
    
    def _handle_csma_install(self, helper_name: str, node: ast.Call):
        """Handle CsmaHelper.Install(nodeContainer) - creates shared medium."""
        if len(node.args) < 1:
            return
            
        # CSMA connects all nodes in a container to a shared medium
        container_ref = self._parse_node_container_reference(node.args[0])
        
        if container_ref:
            container_name, start_idx, end_idx = container_ref
            count = self.topology.node_containers.get(container_name, 0)
            
            if end_idx is None:
                end_idx = count - 1
                
            # For CSMA, we create a "virtual switch" connecting all nodes
            # This is a simplification - in GUI we'll represent as a switch
            config = self.topology.helper_configs.get(helper_name, {})
            
            # Create links between consecutive nodes (chain topology)
            # or mark as CSMA segment for later switch creation
            for i in range(start_idx, end_idx):
                link = ExtractedLink(
                    source_container=container_name,
                    source_index=i,
                    target_container=container_name,
                    target_index=i + 1,
                    link_type=LinkType.CSMA,
                    data_rate=config.get("DataRate", ""),
                    delay=config.get("Delay", ""),
                )
                self.topology.links.append(link)
    
    def _handle_wifi_install(self, helper_name: str, node: ast.Call):
        """
        Handle WifiHelper.Install(phy, mac, nodes).
        
        WiFi install typically has 3 args: (phy, mac, nodes)
        This updates nodes' medium_hint to WIFI_STATION or WIFI_AP
        and creates WiFi links.
        """
        # WiFi install typically: wifi.Install(phy, mac, nodes)
        # Get the last argument which should be the node container
        if not node.args:
            return
            
        # Last argument is usually the node container
        nodes_arg = node.args[-1]
        container_ref = self._parse_node_container_reference(nodes_arg)
        
        if not container_ref:
            return
            
        container_name, start_idx, end_idx = container_ref
        count = self.topology.node_containers.get(container_name, 0)
        
        if start_idx is None:
            start_idx = 0
        if end_idx is None:
            end_idx = count - 1
            
        # Determine if these are stations or APs based on name hints
        medium_hint = self._infer_medium_from_name(container_name)
        if medium_hint == MediumHint.WIRED:
            # Default to station if no hint from name
            medium_hint = MediumHint.WIFI_STATION
            
        # Update medium_hint for all nodes in this container
        for ext_node in self.topology.nodes:
            if ext_node.container_name == container_name:
                if start_idx <= ext_node.index <= end_idx:
                    ext_node.medium_hint = medium_hint
        
        # Create WiFi links between nodes (simplified - all connect to each other)
        # In reality, WiFi stations connect to AP, but we represent as WIFI medium
        if count >= 2:
            for i in range(start_idx, end_idx):
                link = ExtractedLink(
                    source_container=container_name,
                    source_index=i,
                    target_container=container_name,
                    target_index=i + 1,
                    link_type=LinkType.WIFI,
                )
                self.topology.links.append(link)
    
    def _handle_set_attribute(self, helper_name: str, method: str, node: ast.Call):
        """Handle SetDeviceAttribute/SetChannelAttribute."""
        if len(node.args) < 2:
            return
            
        attr_name = self._get_string_value(node.args[0])
        attr_value = self._get_string_from_value_wrapper(node.args[1])
        
        if attr_name and attr_value:
            if helper_name not in self.topology.helper_configs:
                self.topology.helper_configs[helper_name] = {}
            self.topology.helper_configs[helper_name][attr_name] = attr_value
    
    def _handle_set_base(self, helper_name: str, node: ast.Call):
        """Handle Ipv4AddressHelper.SetBase(base, mask)."""
        if len(node.args) < 2:
            return
            
        base = self._get_string_value(node.args[0])
        mask = self._get_string_value(node.args[1])
        
        if base and mask:
            # Store for later association with device containers
            self.variables[f"{helper_name}_base"] = base
            self.variables[f"{helper_name}_mask"] = mask
    
    def _handle_assign(self, helper_name: str, node: ast.Call):
        """Handle Ipv4AddressHelper.Assign(devices)."""
        if len(node.args) < 1:
            return
            
        device_container = self._get_name(node.args[0])
        base = self.variables.get(f"{helper_name}_base", "")
        mask = self.variables.get(f"{helper_name}_mask", "")
        
        if device_container and base:
            assignment = ExtractedIPAssignment(
                device_container=device_container,
                base_address=base,
                netmask=mask,
            )
            self.topology.ip_assignments.append(assignment)
    
    def _handle_simulator_stop(self, node: ast.Call):
        """Handle Simulator.Stop(Seconds(n))."""
        if node.args:
            # Try to extract duration from Seconds(n) or Time(...)
            duration = self._extract_time_value(node.args[0])
            if duration:
                self.topology.duration = duration
    
    def _handle_app_start(self, var_name: str, node: ast.Call):
        """
        Handle app.Start(ns.Seconds(n)) calls.
        
        Updates the most recently created application's start time.
        """
        if not node.args:
            return
            
        start_time = self._extract_time_value(node.args[0])
        if start_time is None:
            return
        
        # Update the most recent application if it matches
        if self.topology.applications:
            # Find the app that was most recently installed
            # Usually the variable 'app' is reused
            self.topology.applications[-1].start_time = start_time
    
    def _handle_app_stop(self, var_name: str, node: ast.Call):
        """
        Handle app.Stop(ns.Seconds(n)) calls.
        
        Updates the most recently created application's stop time.
        """
        if not node.args:
            return
            
        stop_time = self._extract_time_value(node.args[0])
        if stop_time is None:
            return
        
        # Update the most recent application
        if self.topology.applications:
            self.topology.applications[-1].stop_time = stop_time
    
    def _handle_app_attribute(self, helper_name: str, node: ast.Call):
        """Handle application helper SetAttribute/SetConstantRate calls."""
        if helper_name not in self.app_helpers:
            return
            
        method_name = self._get_method_name(node)
        
        if method_name == "SetConstantRate" and node.args:
            # onoff.SetConstantRate(ns.DataRate("500kb/s"))
            rate = self._extract_data_rate(node.args[0])
            if rate:
                self.app_helpers[helper_name]["data_rate"] = rate
                
        elif method_name == "SetAttribute" and len(node.args) >= 2:
            # helper.SetAttribute("Remote", ns.AddressValue(...))
            attr_name = self._get_string_value(node.args[0])
            if attr_name == "Remote":
                addr = self._extract_address_from_arg(node.args[1])
                if addr:
                    self.app_helpers[helper_name]["remote_address"] = addr
            elif attr_name == "DataRate":
                rate = self._extract_data_rate(node.args[1])
                if rate:
                    self.app_helpers[helper_name]["data_rate"] = rate
            elif attr_name == "PacketSize":
                size = self._get_int_value(node.args[1])
                if size:
                    self.app_helpers[helper_name]["packet_size"] = size
    
    def _parse_onoff_helper(self, var_name: str, node: ast.Call):
        """
        Parse OnOffHelper constructor.
        
        Pattern: ns.OnOffHelper("ns3::UdpSocketFactory", ns.InetSocketAddress(...).ConvertTo())
        """
        config = {
            "type": "OnOff",
            "protocol": "UDP",
            "remote_address": "",
            "port": 9,
            "data_rate": "500kb/s",
        }
        
        if len(node.args) >= 1:
            # First arg is socket factory
            factory = self._get_string_value(node.args[0])
            if factory and "Tcp" in factory:
                config["protocol"] = "TCP"
        
        if len(node.args) >= 2:
            # Second arg is address
            addr_info = self._extract_inet_socket_address(node.args[1])
            if addr_info:
                config["remote_address"] = addr_info.get("address", "")
                config["port"] = addr_info.get("port", 9)
        
        self.app_helpers[var_name] = config
    
    def _parse_packet_sink_helper(self, var_name: str, node: ast.Call):
        """
        Parse PacketSinkHelper constructor.
        
        Pattern: ns.PacketSinkHelper("ns3::UdpSocketFactory", ns.InetSocketAddress(...).ConvertTo())
        """
        config = {
            "type": "PacketSink",
            "protocol": "UDP",
            "port": 9,
        }
        
        if len(node.args) >= 1:
            factory = self._get_string_value(node.args[0])
            if factory and "Tcp" in factory:
                config["protocol"] = "TCP"
        
        if len(node.args) >= 2:
            addr_info = self._extract_inet_socket_address(node.args[1])
            if addr_info:
                config["port"] = addr_info.get("port", 9)
        
        self.app_helpers[var_name] = config
    
    def _parse_udp_echo_server_helper(self, var_name: str, node: ast.Call):
        """Parse UdpEchoServerHelper constructor."""
        config = {
            "type": "UdpEchoServer",
            "protocol": "UDP",
            "port": 9,
        }
        
        if node.args:
            port = self._get_int_value(node.args[0])
            if port:
                config["port"] = port
        
        self.app_helpers[var_name] = config
    
    def _parse_udp_echo_client_helper(self, var_name: str, node: ast.Call):
        """Parse UdpEchoClientHelper constructor."""
        config = {
            "type": "UdpEchoClient",
            "protocol": "UDP",
            "remote_address": "",
            "port": 9,
        }
        
        if len(node.args) >= 1:
            # First arg is address
            addr = self._extract_address_from_arg(node.args[0])
            if addr:
                config["remote_address"] = addr
        
        if len(node.args) >= 2:
            port = self._get_int_value(node.args[1])
            if port:
                config["port"] = port
        
        self.app_helpers[var_name] = config
    
    def _parse_bulk_send_helper(self, var_name: str, node: ast.Call):
        """Parse BulkSendHelper constructor."""
        config = {
            "type": "BulkSend",
            "protocol": "TCP",
            "remote_address": "",
            "port": 9,
        }
        
        if len(node.args) >= 2:
            addr_info = self._extract_inet_socket_address(node.args[1])
            if addr_info:
                config["remote_address"] = addr_info.get("address", "")
                config["port"] = addr_info.get("port", 9)
        
        self.app_helpers[var_name] = config
    
    def _handle_app_install(self, helper_name: str, result_var: str, node: ast.Call):
        """
        Handle application Install call.
        
        Pattern: app = helper.Install(nodes.Get(0)) or helper.Install(nodes)
        """
        if helper_name not in self.app_helpers:
            return
            
        config = self.app_helpers[helper_name]
        
        # Get the node(s) being installed on
        if node.args:
            node_info = self._extract_node_reference(node.args[0])
            if node_info:
                container, index = node_info
                
                app = ExtractedApplication(
                    app_type=config.get("type", "Unknown"),
                    node_container=container,
                    node_index=index,
                    port=config.get("port", 9),
                    is_server=config.get("type") in ("PacketSink", "UdpEchoServer"),
                    remote_address=config.get("remote_address", ""),
                    protocol=config.get("protocol", "UDP"),
                    data_rate=config.get("data_rate", ""),
                    packet_size=config.get("packet_size", 0),
                    helper_var=helper_name,
                )
                
                self.topology.applications.append(app)
                
                # Track the result variable for Start/Stop calls
                self._pending_app_container = result_var
                self._pending_app_index = len(self.topology.applications) - 1
    
    def _extract_inet_socket_address(self, node: ast.AST) -> Optional[Dict[str, Any]]:
        """
        Extract address and port from InetSocketAddress call.
        
        Patterns:
        - ns.InetSocketAddress(ns.Ipv4Address("10.1.1.2"), port).ConvertTo()
        - ns.InetSocketAddress(ns.Ipv4Address.GetAny(), port).ConvertTo()
        """
        # Handle .ConvertTo() wrapper
        if isinstance(node, ast.Call):
            method = self._get_method_name(node)
            if method == "ConvertTo":
                # Get the inner call
                if isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Call):
                    node = node.func.value
        
        if not isinstance(node, ast.Call):
            return None
            
        # Check if it's InetSocketAddress
        if not self._is_ns3_call(node, "InetSocketAddress"):
            return None
        
        result = {"address": "", "port": 9}
        
        if len(node.args) >= 1:
            # First arg is address
            result["address"] = self._extract_address_from_arg(node.args[0])
        
        if len(node.args) >= 2:
            # Second arg is port
            port = self._get_int_value(node.args[1])
            if port:
                result["port"] = port
        
        return result
    
    def _extract_address_from_arg(self, node: ast.AST) -> str:
        """Extract IP address from various patterns."""
        if isinstance(node, ast.Call):
            method = self._get_method_name(node)
            
            # ns.Ipv4Address("10.1.1.2")
            if self._is_ns3_call(node, "Ipv4Address"):
                if node.args:
                    return self._get_string_value(node.args[0]) or ""
            
            # ns.Ipv4Address.GetAny()
            if method == "GetAny":
                return "0.0.0.0"
            
            # ns.AddressValue(...)
            if self._is_ns3_call(node, "AddressValue"):
                if node.args:
                    return self._extract_address_from_arg(node.args[0])
            
            # InetSocketAddress - extract just the address part
            addr_info = self._extract_inet_socket_address(node)
            if addr_info:
                return addr_info.get("address", "")
        
        return ""
    
    def _extract_data_rate(self, node: ast.AST) -> str:
        """Extract data rate from DataRate call or DataRateValue."""
        if isinstance(node, ast.Call):
            # ns.DataRate("500kb/s") or ns.DataRateValue(...)
            if node.args:
                arg = node.args[0]
                if isinstance(arg, ast.Constant):
                    return str(arg.value)
                elif isinstance(arg, ast.Call):
                    return self._extract_data_rate(arg)
        return ""
    
    def _extract_node_reference(self, node: ast.AST) -> Optional[Tuple[str, int]]:
        """
        Extract node container and index from node reference.
        
        Patterns:
        - nodes.Get(0)
        - nodes (whole container, assume index 0)
        """
        if isinstance(node, ast.Call):
            method = self._get_method_name(node)
            if method == "Get":
                obj = self._get_object_name(node)
                if obj and node.args:
                    idx = self._get_int_value(node.args[0])
                    if idx is not None:
                        return (obj, idx)
        elif isinstance(node, ast.Name):
            # Whole container reference
            return (node.id, 0)
        
        return None
    
    # =========================================================================
    # Helper methods for parsing AST nodes
    # =========================================================================
    
    def _is_ns3_call(self, node: ast.expr, class_name: str) -> bool:
        """Check if node is a call to ns.ClassName() or ns.core.ClassName()."""
        if not isinstance(node, ast.Call):
            return False
            
        func = node.func
        
        # ns.NodeContainer()
        if isinstance(func, ast.Attribute):
            if func.attr == class_name:
                return True
                
        # Direct call: NodeContainer()
        if isinstance(func, ast.Name) and func.id == class_name:
            return True
            
        return False
    
    def _get_method_name(self, node: ast.Call) -> Optional[str]:
        """Get the method name from a call node."""
        if isinstance(node.func, ast.Attribute):
            return node.func.attr
        elif isinstance(node.func, ast.Name):
            return node.func.id
        return None
    
    def _get_object_name(self, node: ast.Call) -> Optional[str]:
        """Get the object name from a method call (obj.method())."""
        if isinstance(node.func, ast.Attribute):
            if isinstance(node.func.value, ast.Name):
                return node.func.value.id
            elif isinstance(node.func.value, ast.Attribute):
                # Handle chained attributes like ns.Simulator
                return node.func.value.attr
        return None
    
    def _get_name(self, node: ast.expr) -> Optional[str]:
        """Get a simple name from a node."""
        if isinstance(node, ast.Name):
            return node.id
        return None
    
    def _get_int_value(self, node: ast.expr) -> Optional[int]:
        """Extract integer value from AST node."""
        if isinstance(node, ast.Constant) and isinstance(node.value, int):
            return node.value
        elif isinstance(node, ast.Name):
            # Look up variable
            val = self.variables.get(node.id)
            if isinstance(val, int):
                return val
        elif isinstance(node, ast.Num):  # Python 3.7 compatibility
            return node.n
        return None
    
    def _get_string_value(self, node: ast.expr) -> Optional[str]:
        """Extract string value from AST node."""
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return node.value
        elif isinstance(node, ast.Str):  # Python 3.7 compatibility
            return node.s
        return None
    
    def _get_string_from_value_wrapper(self, node: ast.expr) -> Optional[str]:
        """Extract string from StringValue("...") or similar wrapper."""
        if isinstance(node, ast.Call):
            # StringValue("5Mbps") or similar
            if node.args:
                return self._get_string_value(node.args[0])
        return self._get_string_value(node)
    
    def _parse_node_reference(self, node: ast.expr) -> Optional[Tuple[str, int]]:
        """
        Parse a node reference like:
        - nodes.Get(0)
        - nodes
        - nodes[0]
        
        Returns (container_name, index) or None.
        """
        # nodes.Get(0)
        if isinstance(node, ast.Call):
            method = self._get_method_name(node)
            obj = self._get_object_name(node)
            
            if method == "Get" and obj and node.args:
                index = self._get_int_value(node.args[0])
                if index is not None:
                    return (obj, index)
                    
        # Simple name - assume index 0
        elif isinstance(node, ast.Name):
            return (node.id, 0)
            
        # nodes[0] subscript
        elif isinstance(node, ast.Subscript):
            if isinstance(node.value, ast.Name):
                container = node.value.id
                if isinstance(node.slice, ast.Constant):
                    return (container, node.slice.value)
                elif isinstance(node.slice, ast.Index):  # Python 3.7
                    if isinstance(node.slice.value, ast.Constant):
                        return (container, node.slice.value.value)
                        
        return None
    
    def _parse_node_container_reference(self, node: ast.expr) -> Optional[Tuple[str, int, Optional[int]]]:
        """
        Parse a node container reference that might be a slice:
        - nodes (all nodes)
        - nodes[1:3] (slice)
        
        Returns (container_name, start_index, end_index) or None.
        """
        if isinstance(node, ast.Name):
            return (node.id, 0, None)
            
        elif isinstance(node, ast.Subscript):
            if isinstance(node.value, ast.Name):
                container = node.value.id
                
                if isinstance(node.slice, ast.Slice):
                    lower = self._get_int_value(node.slice.lower) if node.slice.lower else 0
                    upper = self._get_int_value(node.slice.upper) if node.slice.upper else None
                    return (container, lower or 0, upper)
                    
        return None
    
    def _extract_time_value(self, node: ast.expr) -> Optional[float]:
        """Extract time value from Seconds(n), MilliSeconds(n), etc."""
        if isinstance(node, ast.Call):
            func_name = self._get_method_name(node)
            if func_name in ("Seconds", "Second") and node.args:
                val = self._get_int_value(node.args[0])
                if val is None:
                    # Try float
                    if isinstance(node.args[0], ast.Constant):
                        val = node.args[0].value
                return float(val) if val else None
            elif func_name == "MilliSeconds" and node.args:
                val = self._get_int_value(node.args[0])
                return val / 1000.0 if val else None
        return None


class NS3PythonParser:
    """
    Main parser class for ns-3 Python scripts.
    
    Usage:
        parser = NS3PythonParser()
        topology = parser.parse_file(Path("first.py"))
        if topology.parse_success:
            # Use topology data
    """
    
    def __init__(self):
        self.last_error: Optional[str] = None
    
    def parse_file(self, filepath: Path) -> ExtractedTopology:
        """
        Parse a Python file and extract topology.
        
        Args:
            filepath: Path to the Python script
            
        Returns:
            ExtractedTopology with extracted data and status
        """
        topology = ExtractedTopology(source_file=str(filepath))
        topology.script_name = filepath.stem
        
        # Try to infer module from path
        # e.g., src/point-to-point/examples/first.py -> "point-to-point"
        parts = filepath.parts
        if "src" in parts:
            src_idx = parts.index("src")
            if src_idx + 1 < len(parts):
                topology.module_name = parts[src_idx + 1]
        elif "examples" in parts:
            examples_idx = parts.index("examples")
            if examples_idx > 0:
                topology.module_name = parts[examples_idx - 1]
        
        try:
            with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
                source = f.read()
        except Exception as e:
            topology.add_error(f"Could not read file: {e}")
            return topology
        
        # Extract description from docstring or comments
        topology.description = self._extract_description(source)
        
        # Parse AST
        try:
            tree = ast.parse(source)
        except SyntaxError as e:
            topology.add_error(f"Syntax error at line {e.lineno}: {e.msg}")
            return topology
        except Exception as e:
            topology.add_error(f"Parse error: {e}")
            return topology
        
        # Visit AST to extract topology
        visitor = NS3PythonVisitor(topology)
        visitor.visit(tree)
        
        # Post-process and validate
        self._post_process(topology)
        
        # Mark success if we found something
        if topology.nodes or topology.links:
            topology.parse_success = True
        else:
            topology.add_warning("No topology elements found")
            
        return topology
    
    def parse_string(self, source: str, name: str = "script") -> ExtractedTopology:
        """Parse Python source code from a string."""
        topology = ExtractedTopology(source_file=name)
        topology.script_name = name
        
        try:
            tree = ast.parse(source)
        except SyntaxError as e:
            topology.add_error(f"Syntax error at line {e.lineno}: {e.msg}")
            return topology
        
        visitor = NS3PythonVisitor(topology)
        visitor.visit(tree)
        
        self._post_process(topology)
        
        if topology.nodes or topology.links:
            topology.parse_success = True
            
        return topology
    
    def _extract_description(self, source: str) -> str:
        """Extract description from module docstring or initial comments."""
        lines = source.split('\n')
        description_lines = []
        in_docstring = False
        docstring_char = None
        
        for line in lines[:30]:  # Only check first 30 lines
            stripped = line.strip()
            
            # Check for docstring start
            if not in_docstring:
                if stripped.startswith('"""') or stripped.startswith("'''"):
                    docstring_char = stripped[:3]
                    if stripped.count(docstring_char) >= 2:
                        # Single line docstring
                        description_lines.append(stripped[3:-3])
                        break
                    else:
                        in_docstring = True
                        remainder = stripped[3:]
                        if remainder:
                            description_lines.append(remainder)
                elif stripped.startswith('#'):
                    # Comment line
                    comment = stripped[1:].strip()
                    if comment and not comment.startswith('!'):  # Skip shebang
                        description_lines.append(comment)
                elif stripped and not stripped.startswith('import') and not stripped.startswith('from'):
                    # Non-comment, non-import line - stop looking
                    break
            else:
                # In docstring
                if docstring_char in stripped:
                    # End of docstring
                    end_idx = stripped.index(docstring_char)
                    if end_idx > 0:
                        description_lines.append(stripped[:end_idx])
                    break
                else:
                    description_lines.append(stripped)
        
        return ' '.join(description_lines).strip()[:500]  # Limit length
    
    def _post_process(self, topology: ExtractedTopology):
        """Post-process extracted topology for consistency."""
        # Remove duplicate nodes
        seen_nodes: Set[Tuple[str, int]] = set()
        unique_nodes = []
        for node in topology.nodes:
            if node.key not in seen_nodes:
                seen_nodes.add(node.key)
                unique_nodes.append(node)
        topology.nodes = unique_nodes
        
        # Validate links reference existing nodes
        valid_links = []
        for link in topology.links:
            source_exists = link.source_key in seen_nodes
            target_exists = link.target_key in seen_nodes
            
            if source_exists and target_exists:
                valid_links.append(link)
            else:
                if not source_exists:
                    topology.add_warning(
                        f"Link references unknown node: {link.source_container}[{link.source_index}]"
                    )
                if not target_exists:
                    topology.add_warning(
                        f"Link references unknown node: {link.target_container}[{link.target_index}]"
                    )
        topology.links = valid_links
        
        # Infer node types based on connectivity
        self._infer_node_types(topology)
    
    def _infer_node_types(self, topology: ExtractedTopology):
        """Infer node types based on connectivity patterns."""
        # Count connections per node
        connection_count: Dict[Tuple[str, int], int] = {}
        
        for link in topology.links:
            connection_count[link.source_key] = connection_count.get(link.source_key, 0) + 1
            connection_count[link.target_key] = connection_count.get(link.target_key, 0) + 1
        
        # Nodes with many connections might be routers (unless already explicitly typed)
        for node in topology.nodes:
            count = connection_count.get(node.key, 0)
            
            # Don't override explicit switch type (from name inference)
            if node.node_type == NodeType.SWITCH:
                continue
                
            if count > 2 and node.node_type == NodeType.HOST:
                # Only upgrade HOST to ROUTER, don't change SWITCH
                node.node_type = NodeType.ROUTER
            elif count == 0:
                node.node_type = NodeType.HOST
                node.inferred_role = "isolated"


class TopologyExporter:
    """
    Export extracted topology to various formats.
    """
    
    def to_dict(self, topology: ExtractedTopology) -> dict:
        """Convert extracted topology to dictionary (for JSON export)."""
        return {
            "extraction_info": {
                "source_file": topology.source_file,
                "script_name": topology.script_name,
                "module_name": topology.module_name,
                "description": topology.description,
                "parse_success": topology.parse_success,
                "errors": topology.errors,
                "warnings": topology.warnings,
                "extracted_at": datetime.now().isoformat(),
            },
            "topology_summary": {
                "node_count": len(topology.nodes),
                "link_count": len(topology.links),
                "node_containers": topology.node_containers,
                "duration": topology.duration,
            },
            "nodes": [
                {
                    "container": n.container_name,
                    "index": n.index,
                    "type": n.node_type.value,
                    "role": n.inferred_role,
                }
                for n in topology.nodes
            ],
            "links": [
                {
                    "source": {"container": l.source_container, "index": l.source_index},
                    "target": {"container": l.target_container, "index": l.target_index},
                    "type": l.link_type.value,
                    "data_rate": l.data_rate,
                    "delay": l.delay,
                }
                for l in topology.links
            ],
            "ip_assignments": [
                {
                    "device_container": ip.device_container,
                    "base": ip.base_address,
                    "mask": ip.netmask,
                }
                for ip in topology.ip_assignments
            ],
            "helper_configs": topology.helper_configs,
        }
    
    def to_json(self, topology: ExtractedTopology, indent: int = 2) -> str:
        """Convert extracted topology to JSON string."""
        return json.dumps(self.to_dict(topology), indent=indent)
    
    def save_json(self, topology: ExtractedTopology, filepath: Path):
        """Save extracted topology to JSON file."""
        filepath.parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(self.to_json(topology))
