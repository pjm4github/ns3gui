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


class LinkType(Enum):
    """Types of network links in ns-3."""
    POINT_TO_POINT = "point-to-point"
    CSMA = "csma"
    WIFI = "wifi"
    LTE = "lte"
    UNKNOWN = "unknown"


class NodeType(Enum):
    """Inferred node types."""
    HOST = "host"
    ROUTER = "router"
    SWITCH = "switch"
    ACCESS_POINT = "access_point"
    UNKNOWN = "unknown"


@dataclass
class ExtractedNode:
    """A node extracted from ns-3 script."""
    container_name: str
    index: int
    node_type: NodeType = NodeType.HOST
    inferred_role: str = ""  # e.g., "server", "client", "gateway"
    
    @property
    def key(self) -> Tuple[str, int]:
        """Unique key for this node."""
        return (self.container_name, self.index)


@dataclass
class ExtractedLink:
    """A link extracted from ns-3 script."""
    source_container: str
    source_index: int
    target_container: str
    target_index: int
    link_type: LinkType = LinkType.POINT_TO_POINT
    data_rate: str = ""
    delay: str = ""
    device_container: str = ""  # Name of NetDeviceContainer
    
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
    app_type: str  # "UdpEcho", "OnOff", "PacketSink", etc.
    node_container: str
    node_index: int
    port: int = 0
    is_server: bool = False
    remote_address: str = ""
    start_time: float = 0.0
    stop_time: float = 0.0


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
                
            # Track Install() results (NetDeviceContainer)
            elif isinstance(node.value, ast.Call):
                call_name = self._get_method_name(node.value)
                if call_name == "Install":
                    self.helper_types[var_name] = "NetDeviceContainer"
                    
        self.generic_visit(node)
    
    def visit_Expr(self, node: ast.Expr):
        """Visit expression statements (method calls without assignment)."""
        if isinstance(node.value, ast.Call):
            self._process_call(node.value)
        self.generic_visit(node)
    
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
            self._handle_simulator_stop(node)
            
        # Application helpers
        elif method_name in ("SetAttribute",) and obj_name:
            self._handle_app_attribute(obj_name, node)
    
    def _handle_create(self, container_name: str, node: ast.Call):
        """Handle NodeContainer.Create(n) call."""
        if not node.args:
            return
            
        count = self._get_int_value(node.args[0])
        if count is None:
            self.topology.add_warning(f"Could not determine node count for {container_name}.Create()")
            return
            
        self.topology.node_containers[container_name] = count
        
        # Create individual node entries
        for i in range(count):
            ext_node = ExtractedNode(
                container_name=container_name,
                index=i,
                node_type=NodeType.HOST,
            )
            self.topology.nodes.append(ext_node)
    
    def _handle_install(self, helper_name: str, node: ast.Call):
        """Handle Helper.Install(...) call to extract links."""
        helper_type = self.helper_types.get(helper_name, "")
        
        if helper_type == "PointToPointHelper":
            self._handle_p2p_install(helper_name, node)
        elif helper_type == "CsmaHelper":
            self._handle_csma_install(helper_name, node)
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
    
    def _handle_app_attribute(self, helper_name: str, node: ast.Call):
        """Handle application helper attributes."""
        # TODO: Extract application configurations
        pass
    
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
        
        # Nodes with many connections might be routers
        for node in topology.nodes:
            count = connection_count.get(node.key, 0)
            if count > 2:
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
