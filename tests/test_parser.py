#!/usr/bin/env python3
"""
Test script for NS3 Python Parser.

This tests the parser against sample ns-3 Python code patterns.
"""

import sys
import importlib.util
from pathlib import Path

# Load the parser module directly to avoid PyQt6 dependency
def load_module(name: str, path: str):
    """Load a Python module from file path."""
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

# Get paths
script_dir = Path(__file__).parent
services_dir = script_dir.parent / "services"

# Load modules directly
parser_module = load_module("ns3_script_parser", str(services_dir / "ns3_script_parser.py"))

NS3PythonParser = parser_module.NS3PythonParser
TopologyExporter = parser_module.TopologyExporter

# Sample ns-3 Python script (similar to first.py)
SAMPLE_SCRIPT_1 = '''
"""
Simple point-to-point simulation.
Two nodes connected by a single link.
"""

from ns import ns
import sys

def main():
    # Create nodes
    nodes = ns.NodeContainer()
    nodes.Create(2)
    
    # Create point-to-point helper
    p2p = ns.PointToPointHelper()
    p2p.SetDeviceAttribute("DataRate", ns.StringValue("5Mbps"))
    p2p.SetChannelAttribute("Delay", ns.StringValue("2ms"))
    
    # Install devices
    devices = p2p.Install(nodes.Get(0), nodes.Get(1))
    
    # Install internet stack
    stack = ns.InternetStackHelper()
    stack.Install(nodes)
    
    # Assign IP addresses
    address = ns.Ipv4AddressHelper()
    address.SetBase(ns.Ipv4Address("10.1.1.0"), ns.Ipv4Mask("255.255.255.0"))
    interfaces = address.Assign(devices)
    
    # Run simulation
    ns.Simulator.Stop(ns.Seconds(10))
    ns.Simulator.Run()
    ns.Simulator.Destroy()
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
'''

# Sample matching exact first.py pattern (Install with single container)
SAMPLE_SCRIPT_FIRST_PY = '''
"""
First ns-3 tutorial script.
Two nodes with point-to-point connection.
"""

from ns import ns
import sys

def main(argv):
    # Create two nodes
    nodes = ns.NodeContainer()
    nodes.Create(2)
    
    # Create point-to-point helper and set attributes
    pointToPoint = ns.PointToPointHelper()
    pointToPoint.SetDeviceAttribute("DataRate", ns.StringValue("5Mbps"))
    pointToPoint.SetChannelAttribute("Delay", ns.StringValue("2ms"))
    
    # Install devices on ALL nodes in container
    devices = pointToPoint.Install(nodes)
    
    # Install internet stack
    stack = ns.InternetStackHelper()
    stack.Install(nodes)
    
    # Assign IP addresses  
    address = ns.Ipv4AddressHelper()
    address.SetBase(ns.Ipv4Address("10.1.1.0"), ns.Ipv4Mask("255.255.255.0"))
    interfaces = address.Assign(devices)
    
    # Run simulation
    ns.Simulator.Stop(ns.Seconds(10))
    ns.Simulator.Run()
    ns.Simulator.Destroy()
    
    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv))
'''

# Sample with multiple node containers (like third.py)
SAMPLE_SCRIPT_2 = '''
"""
Bus topology simulation with CSMA.
Multiple nodes on a shared bus.
"""

from ns import ns

def main():
    # Create node containers
    p2pNodes = ns.NodeContainer()
    p2pNodes.Create(2)
    
    csmaNodes = ns.NodeContainer()
    csmaNodes.Add(p2pNodes.Get(1))
    csmaNodes.Create(3)
    
    # Point-to-point connection
    p2p = ns.PointToPointHelper()
    p2p.SetDeviceAttribute("DataRate", ns.StringValue("5Mbps"))
    p2p.SetChannelAttribute("Delay", ns.StringValue("2ms"))
    
    p2pDevices = p2p.Install(p2pNodes)
    
    # CSMA connection
    csma = ns.CsmaHelper()
    csma.SetChannelAttribute("DataRate", ns.StringValue("100Mbps"))
    csma.SetChannelAttribute("Delay", ns.TimeValue(ns.NanoSeconds(6560)))
    
    csmaDevices = csma.Install(csmaNodes)
    
    # Internet stack
    stack = ns.InternetStackHelper()
    stack.Install(p2pNodes.Get(0))
    stack.Install(csmaNodes)
    
    # IP addresses
    address = ns.Ipv4AddressHelper()
    
    address.SetBase(ns.Ipv4Address("10.1.1.0"), ns.Ipv4Mask("255.255.255.0"))
    p2pInterfaces = address.Assign(p2pDevices)
    
    address.SetBase(ns.Ipv4Address("10.1.2.0"), ns.Ipv4Mask("255.255.255.0"))
    csmaInterfaces = address.Assign(csmaDevices)
    
    ns.Simulator.Stop(ns.Seconds(20))
    ns.Simulator.Run()
    ns.Simulator.Destroy()

if __name__ == "__main__":
    main()
'''


def test_simple_p2p():
    """Test parsing simple point-to-point topology."""
    print("=" * 60)
    print("Test 1: Simple Point-to-Point Topology")
    print("=" * 60)
    
    parser = NS3PythonParser()
    topology = parser.parse_string(SAMPLE_SCRIPT_1, "simple_p2p")
    
    print(f"\nParse success: {topology.parse_success}")
    print(f"Description: {topology.description[:100]}...")
    print(f"\nNode containers: {topology.node_containers}")
    print(f"Nodes found: {len(topology.nodes)}")
    for node in topology.nodes:
        print(f"  - {node.container_name}[{node.index}] type={node.node_type.value}")
    
    print(f"\nLinks found: {len(topology.links)}")
    for link in topology.links:
        print(f"  - {link.source_container}[{link.source_index}] <-> {link.target_container}[{link.target_index}]")
        print(f"    type={link.link_type.value}, rate={link.data_rate}, delay={link.delay}")
    
    print(f"\nHelper configs: {topology.helper_configs}")
    print(f"IP assignments: {len(topology.ip_assignments)}")
    for ip in topology.ip_assignments:
        print(f"  - {ip.device_container}: {ip.base_address}/{ip.netmask}")
    
    print(f"\nSimulation duration: {topology.duration}s")
    
    if topology.errors:
        print(f"\nErrors: {topology.errors}")
    if topology.warnings:
        print(f"\nWarnings: {topology.warnings}")
    
    # Test JSON export
    print("\n--- JSON Export ---")
    exporter = TopologyExporter()
    json_str = exporter.to_json(topology)
    print(f"JSON length: {len(json_str)} chars")
    
    return topology.parse_success


def test_csma_topology():
    """Test parsing CSMA/bus topology."""
    print("\n" + "=" * 60)
    print("Test 2: CSMA Bus Topology")
    print("=" * 60)
    
    parser = NS3PythonParser()
    topology = parser.parse_string(SAMPLE_SCRIPT_2, "csma_bus")
    
    print(f"\nParse success: {topology.parse_success}")
    print(f"Description: {topology.description[:100]}...")
    print(f"\nNode containers: {topology.node_containers}")
    print(f"Nodes found: {len(topology.nodes)}")
    
    print(f"\nLinks found: {len(topology.links)}")
    for link in topology.links:
        print(f"  - {link.source_container}[{link.source_index}] <-> {link.target_container}[{link.target_index}]")
        print(f"    type={link.link_type.value}")
    
    print(f"\nSimulation duration: {topology.duration}s")
    
    if topology.errors:
        print(f"\nErrors: {topology.errors}")
    if topology.warnings:
        print(f"\nWarnings: {topology.warnings}")
    
    return topology.parse_success


def test_first_py_pattern():
    """Test parsing the exact first.py pattern with Install(nodes)."""
    print("\n" + "=" * 60)
    print("Test 3: first.py Pattern (Install with container)")
    print("=" * 60)
    
    parser = NS3PythonParser()
    topology = parser.parse_string(SAMPLE_SCRIPT_FIRST_PY, "first")
    
    print(f"\nParse success: {topology.parse_success}")
    print(f"Description: {topology.description[:50]}...")
    print(f"\nNode containers: {topology.node_containers}")
    print(f"Nodes found: {len(topology.nodes)}")
    for node in topology.nodes:
        print(f"  - {node.container_name}[{node.index}] type={node.node_type.value}")
    
    print(f"\nLinks found: {len(topology.links)}")
    for link in topology.links:
        print(f"  - {link.source_container}[{link.source_index}] <-> {link.target_container}[{link.target_index}]")
        print(f"    type={link.link_type.value}, rate={link.data_rate}, delay={link.delay}")
    
    print(f"\nSimulation duration: {topology.duration}s")
    
    if topology.errors:
        print(f"\nErrors: {topology.errors}")
    if topology.warnings:
        print(f"\nWarnings: {topology.warnings}")
    
    # Verify expected results
    success = (
        topology.parse_success and
        len(topology.nodes) == 2 and
        len(topology.links) == 1 and
        topology.links[0].link_type.value == "point-to-point"
    )
    
    if success:
        print("\n✓ Correctly parsed first.py pattern!")
    else:
        print("\n✗ Failed to parse first.py pattern correctly")
    
    return success


def main():
    """Run all tests."""
    print("NS-3 Python Parser Test Suite")
    print("=" * 60)
    
    results = []
    
    results.append(("Simple P2P", test_simple_p2p()))
    results.append(("CSMA Bus", test_csma_topology()))
    results.append(("first.py Pattern", test_first_py_pattern()))
    
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    
    for name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"  {name}: {status}")
    
    all_passed = all(r[1] for r in results)
    print(f"\nOverall: {'All tests passed!' if all_passed else 'Some tests failed'}")
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
