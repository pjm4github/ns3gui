"""
Project manager for saving and loading network topologies.

Uses a JSON format inspired by common network topology standards
like GNS3, Mininet, and YANG models.
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Optional
from dataclasses import asdict

from models import (
    NetworkModel, NodeModel, LinkModel, NodeType, ChannelType,
    Position, PortConfig, PortType, VlanMode
)


# Schema version for future compatibility
SCHEMA_VERSION = "1.0"


class ProjectManager:
    """
    Handles saving and loading network topology projects.
    
    File format follows a structure inspired by:
    - GNS3 project format
    - Mininet topology format
    - IETF network topology YANG model (simplified)
    """
    
    def __init__(self):
        self._current_file: Optional[Path] = None
    
    @property
    def current_file(self) -> Optional[Path]:
        """Get the current project file path."""
        return self._current_file
    
    @property
    def has_file(self) -> bool:
        """Check if a file is currently open."""
        return self._current_file is not None
    
    def save(self, network: NetworkModel, filepath: Path) -> bool:
        """
        Save network topology to a JSON file.
        
        Args:
            network: The NetworkModel to save
            filepath: Path to save the file
            
        Returns:
            True if successful, False otherwise
        """
        try:
            data = self._serialize_network(network)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            self._current_file = filepath
            return True
            
        except Exception as e:
            print(f"Error saving project: {e}")
            return False
    
    def load(self, filepath: Path) -> Optional[NetworkModel]:
        """
        Load network topology from a JSON file.
        
        Args:
            filepath: Path to the file to load
            
        Returns:
            NetworkModel if successful, None otherwise
        """
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            network = self._deserialize_network(data)
            self._current_file = filepath
            return network
            
        except Exception as e:
            print(f"Error loading project: {e}")
            return None
    
    def _serialize_network(self, network: NetworkModel) -> dict:
        """Convert NetworkModel to JSON-serializable dictionary."""
        return {
            "schema": {
                "version": SCHEMA_VERSION,
                "format": "ns3-gui-topology"
            },
            "metadata": {
                "created": datetime.now().isoformat(),
                "generator": "ns3-gui-mvp",
                "description": ""
            },
            "simulation": {
                "duration": network.simulation_duration,
                "units": "seconds"
            },
            "topology": {
                "nodes": [
                    self._serialize_node(node) 
                    for node in network.nodes.values()
                ],
                "links": [
                    self._serialize_link(link, network)
                    for link in network.links.values()
                ]
            }
        }
    
    def _serialize_node(self, node: NodeModel) -> dict:
        """Convert NodeModel to dictionary."""
        # Base node properties
        node_data = {
            "id": node.id,
            "name": node.name,
            "type": node.node_type.name.lower(),
            "description": node.description,
            "position": {
                "x": node.position.x,
                "y": node.position.y
            },
            "ports": [
                self._serialize_port(port)
                for port in node.ports
            ]
        }
        
        # Type-specific properties
        if node.node_type == NodeType.HOST:
            node_data["host_config"] = {
                "is_server": node.is_server
            }
        elif node.node_type == NodeType.ROUTER:
            node_data["router_config"] = {
                "routing_protocol": node.routing_protocol,
                "ip_forwarding": node.forwarding_enabled
            }
        elif node.node_type == NodeType.SWITCH:
            node_data["switch_config"] = {
                "switching_mode": node.switching_mode,
                "stp_enabled": node.stp_enabled,
                "subnet_base": node.subnet_base,
                "subnet_mask": node.subnet_mask
            }
        
        return node_data
    
    def _serialize_port(self, port: PortConfig) -> dict:
        """Convert PortConfig to dictionary."""
        return {
            "id": port.id,
            "port_number": port.port_number,
            "port_name": port.port_name,
            "port_type": port.port_type.name.lower(),
            "speed": port.speed,
            "duplex": port.duplex,
            "enabled": port.enabled,
            "mtu": port.mtu,
            "mac_address": port.mac_address,
            "vlan_id": port.vlan_id,
            "vlan_mode": port.vlan_mode.name.lower(),
            "trunk_allowed_vlans": port.trunk_allowed_vlans,
            "ip_address": port.ip_address,
            "netmask": port.netmask,
            "connected_link_id": port.connected_link_id
        }
    
    def _serialize_link(self, link: LinkModel, network: NetworkModel) -> dict:
        """Convert LinkModel to dictionary."""
        # Get endpoint node and port info
        source_node = network.get_node(link.source_node_id)
        target_node = network.get_node(link.target_node_id)
        
        source_port = source_node.get_port(link.source_port_id) if source_node else None
        target_port = target_node.get_port(link.target_port_id) if target_node else None
        
        return {
            "id": link.id,
            "type": link.channel_type.name.lower(),
            "endpoints": {
                "source": {
                    "node_id": link.source_node_id,
                    "node_name": source_node.name if source_node else "",
                    "port_id": link.source_port_id,
                    "port_name": source_port.display_name if source_port else ""
                },
                "target": {
                    "node_id": link.target_node_id,
                    "node_name": target_node.name if target_node else "",
                    "port_id": link.target_port_id,
                    "port_name": target_port.display_name if target_port else ""
                }
            },
            "properties": {
                "data_rate": link.data_rate,
                "delay": link.delay
            }
        }
    
    def _deserialize_network(self, data: dict) -> NetworkModel:
        """Convert dictionary to NetworkModel."""
        network = NetworkModel()
        
        # Load simulation settings
        if "simulation" in data:
            network.simulation_duration = data["simulation"].get("duration", 10.0)
        
        # Load topology
        topology = data.get("topology", {})
        
        # First pass: create all nodes
        for node_data in topology.get("nodes", []):
            node = self._deserialize_node(node_data)
            network.nodes[node.id] = node
        
        # Second pass: create all links
        for link_data in topology.get("links", []):
            link = self._deserialize_link(link_data)
            network.links[link.id] = link
        
        # Update subnet counter based on loaded links
        network._next_subnet = len(network.links) + 1
        
        return network
    
    def _deserialize_node(self, data: dict) -> NodeModel:
        """Convert dictionary to NodeModel."""
        # Parse node type
        type_str = data.get("type", "host").upper()
        try:
            node_type = NodeType[type_str]
        except KeyError:
            node_type = NodeType.HOST
        
        # Create node with basic properties
        # Note: __post_init__ will create default ports, we'll replace them if data has ports
        node = NodeModel(
            id=data.get("id", ""),
            node_type=node_type,
            name=data.get("name", ""),
            description=data.get("description", ""),
            position=Position(
                x=data.get("position", {}).get("x", 0),
                y=data.get("position", {}).get("y", 0)
            ),
        )
        
        # Load ports from data (replace auto-generated defaults)
        saved_ports = data.get("ports", [])
        if saved_ports:
            # Clear auto-generated ports and load saved ones
            node.ports.clear()
            for port_data in saved_ports:
                port = self._deserialize_port(port_data)
                node.ports.append(port)
        
        # Load type-specific config
        if node_type == NodeType.HOST:
            host_config = data.get("host_config", {})
            node.is_server = host_config.get("is_server", False)
            
        elif node_type == NodeType.ROUTER:
            router_config = data.get("router_config", {})
            node.routing_protocol = router_config.get("routing_protocol", "static")
            node.forwarding_enabled = router_config.get("ip_forwarding", True)
            
        elif node_type == NodeType.SWITCH:
            switch_config = data.get("switch_config", {})
            node.switching_mode = switch_config.get("switching_mode", "learning")
            node.stp_enabled = switch_config.get("stp_enabled", False)
            node.subnet_base = switch_config.get("subnet_base", "")
            node.subnet_mask = switch_config.get("subnet_mask", "255.255.255.0")
        
        return node
    
    def _deserialize_port(self, data: dict) -> PortConfig:
        """Convert dictionary to PortConfig."""
        # Parse port type
        type_str = data.get("port_type", "gigabit_ethernet").upper()
        try:
            port_type = PortType[type_str]
        except KeyError:
            port_type = PortType.GIGABIT_ETHERNET
        
        # Parse VLAN mode
        vlan_mode_str = data.get("vlan_mode", "access").upper()
        try:
            vlan_mode = VlanMode[vlan_mode_str]
        except KeyError:
            vlan_mode = VlanMode.ACCESS
        
        return PortConfig(
            id=data.get("id", ""),
            port_number=data.get("port_number", 0),
            port_name=data.get("port_name", ""),
            port_type=port_type,
            speed=data.get("speed", "1Gbps"),
            duplex=data.get("duplex", "full"),
            enabled=data.get("enabled", True),
            mtu=data.get("mtu", 1500),
            mac_address=data.get("mac_address", ""),
            vlan_id=data.get("vlan_id", 1),
            vlan_mode=vlan_mode,
            trunk_allowed_vlans=data.get("trunk_allowed_vlans", "1-4094"),
            ip_address=data.get("ip_address", ""),
            netmask=data.get("netmask", "255.255.255.0"),
            connected_link_id=data.get("connected_link_id")
        )
    
    def _deserialize_link(self, data: dict) -> LinkModel:
        """Convert dictionary to LinkModel."""
        # Parse channel type
        type_str = data.get("type", "point_to_point").upper()
        try:
            channel_type = ChannelType[type_str]
        except KeyError:
            channel_type = ChannelType.POINT_TO_POINT
        
        endpoints = data.get("endpoints", {})
        properties = data.get("properties", {})
        
        return LinkModel(
            id=data.get("id", ""),
            channel_type=channel_type,
            source_node_id=endpoints.get("source", {}).get("node_id", ""),
            target_node_id=endpoints.get("target", {}).get("node_id", ""),
            source_port_id=endpoints.get("source", {}).get("port_id", ""),
            target_port_id=endpoints.get("target", {}).get("port_id", ""),
            data_rate=properties.get("data_rate", "100Mbps"),
            delay=properties.get("delay", "2ms")
        )


def export_to_mininet(network: NetworkModel) -> str:
    """
    Export topology to Mininet Python script format.
    
    This generates a standalone Mininet script that can recreate
    the topology outside of ns-3.
    """
    lines = [
        '#!/usr/bin/env python3',
        '"""',
        'Mininet topology generated by ns3-gui',
        f'Generated: {datetime.now().isoformat()}',
        '"""',
        '',
        'from mininet.net import Mininet',
        'from mininet.node import Controller, OVSSwitch',
        'from mininet.cli import CLI',
        'from mininet.log import setLogLevel',
        '',
        'def create_topology():',
        '    net = Mininet(controller=Controller, switch=OVSSwitch)',
        '    ',
        '    # Add controller',
        '    net.addController("c0")',
        '    ',
        '    # Add nodes',
    ]
    
    # Add nodes
    for node in network.nodes.values():
        if node.node_type == NodeType.HOST:
            lines.append(f'    {node.name} = net.addHost("{node.name}")')
        elif node.node_type == NodeType.SWITCH:
            lines.append(f'    {node.name} = net.addSwitch("{node.name}")')
        elif node.node_type == NodeType.ROUTER:
            # Mininet uses hosts with IP forwarding for routers
            lines.append(f'    {node.name} = net.addHost("{node.name}")')
    
    lines.append('    ')
    lines.append('    # Add links')
    
    # Add links
    for link in network.links.values():
        source = network.get_node(link.source_node_id)
        target = network.get_node(link.target_node_id)
        if source and target:
            lines.append(f'    net.addLink({source.name}, {target.name})')
    
    lines.extend([
        '    ',
        '    return net',
        '',
        'if __name__ == "__main__":',
        '    setLogLevel("info")',
        '    net = create_topology()',
        '    net.start()',
        '    CLI(net)',
        '    net.stop()',
    ])
    
    return '\n'.join(lines)
