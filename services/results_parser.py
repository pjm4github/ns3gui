"""
NS-3 Results Parser.

Parses simulation output files (FlowMonitor XML, ASCII traces, etc.)
"""

import xml.etree.ElementTree as ET
from typing import List, Optional
from dataclasses import dataclass
from models import FlowStats


class ResultsParser:
    """
    Parse ns-3 simulation output files.
    
    Supports:
    - FlowMonitor XML output
    - ASCII trace files (basic parsing)
    - Console output parsing
    """
    
    def parse_flow_monitor_xml(self, file_path: str) -> List[FlowStats]:
        """
        Parse FlowMonitor XML output file.
        
        Args:
            file_path: Path to flowmon-results.xml
            
        Returns:
            List of FlowStats for each flow
        """
        flows = []
        
        try:
            tree = ET.parse(file_path)
            root = tree.getroot()
            
            # Parse flow stats
            flow_stats_elem = root.find("FlowStats")
            if flow_stats_elem is None:
                return flows
            
            # Parse IPv4 flow classifier for address info
            classifier_info = {}
            classifier = root.find("Ipv4FlowClassifier")
            if classifier is not None:
                for flow_elem in classifier.findall("Flow"):
                    flow_id = int(flow_elem.get("flowId", 0))
                    classifier_info[flow_id] = {
                        "source_address": flow_elem.get("sourceAddress", ""),
                        "destination_address": flow_elem.get("destinationAddress", ""),
                        "source_port": int(flow_elem.get("sourcePort", 0)),
                        "destination_port": int(flow_elem.get("destinationPort", 0)),
                        "protocol": int(flow_elem.get("protocol", 0)),
                    }
            
            # Parse each flow's statistics
            for flow_elem in flow_stats_elem.findall("Flow"):
                flow_id = int(flow_elem.get("flowId", 0))
                
                # Get classifier info
                clf = classifier_info.get(flow_id, {})
                
                # Parse time values (in nanoseconds)
                def parse_time_ns(attr: str) -> int:
                    val = flow_elem.get(attr, "+0.0ns")
                    # Format: +1.234567890e+09ns or similar
                    val = val.rstrip("ns").lstrip("+")
                    try:
                        return int(float(val))
                    except ValueError:
                        return 0
                
                stats = FlowStats(
                    flow_id=flow_id,
                    source_address=clf.get("source_address", ""),
                    destination_address=clf.get("destination_address", ""),
                    source_port=clf.get("source_port", 0),
                    destination_port=clf.get("destination_port", 0),
                    protocol=clf.get("protocol", 0),
                    tx_packets=int(flow_elem.get("txPackets", 0)),
                    rx_packets=int(flow_elem.get("rxPackets", 0)),
                    tx_bytes=int(flow_elem.get("txBytes", 0)),
                    rx_bytes=int(flow_elem.get("rxBytes", 0)),
                    delay_sum_ns=parse_time_ns("delaySum"),
                    jitter_sum_ns=parse_time_ns("jitterSum"),
                    lost_packets=int(flow_elem.get("lostPackets", 0)),
                    times_forwarded=int(flow_elem.get("timesForwarded", 0)),
                    first_tx_time_ns=parse_time_ns("timeFirstTxPacket"),
                    last_rx_time_ns=parse_time_ns("timeLastRxPacket"),
                )
                
                flows.append(stats)
                
        except ET.ParseError as e:
            print(f"XML parse error: {e}")
        except Exception as e:
            print(f"Error parsing FlowMonitor results: {e}")
        
        return flows
    
    def parse_console_output(self, output: str) -> List[FlowStats]:
        """
        Parse flow statistics from console output.
        
        This is a fallback when XML is not available.
        Parses output like:
            Flow 1 (UDP)
              10.1.1.1:49153 -> 10.1.1.2:9000
              Tx Packets: 10
              Rx Packets: 10
              ...
        
        Args:
            output: Console output string
            
        Returns:
            List of FlowStats parsed from output
        """
        import re
        flows = []
        
        # Split into flow blocks
        flow_blocks = re.split(r"Flow (\d+)", output)
        
        i = 1
        while i < len(flow_blocks) - 1:
            flow_id = int(flow_blocks[i])
            block = flow_blocks[i + 1]
            
            stats = FlowStats(flow_id=flow_id)
            
            # Parse protocol
            proto_match = re.search(r"\((UDP|TCP)\)", block)
            if proto_match:
                stats.protocol = 17 if proto_match.group(1) == "UDP" else 6
            
            # Parse addresses
            addr_match = re.search(r"(\d+\.\d+\.\d+\.\d+):(\d+)\s*->\s*(\d+\.\d+\.\d+\.\d+):(\d+)", block)
            if addr_match:
                stats.source_address = addr_match.group(1)
                stats.source_port = int(addr_match.group(2))
                stats.destination_address = addr_match.group(3)
                stats.destination_port = int(addr_match.group(4))
            
            # Parse packet counts
            tx_match = re.search(r"Tx Packets:\s*(\d+)", block)
            if tx_match:
                stats.tx_packets = int(tx_match.group(1))
            
            rx_match = re.search(r"Rx Packets:\s*(\d+)", block)
            if rx_match:
                stats.rx_packets = int(rx_match.group(1))
            
            # Parse bytes
            tx_bytes_match = re.search(r"Tx Bytes:\s*(\d+)", block)
            if tx_bytes_match:
                stats.tx_bytes = int(tx_bytes_match.group(1))
            
            rx_bytes_match = re.search(r"Rx Bytes:\s*(\d+)", block)
            if rx_bytes_match:
                stats.rx_bytes = int(rx_bytes_match.group(1))
            
            # Parse lost packets
            lost_match = re.search(r"Lost Packets:\s*(\d+)", block)
            if lost_match:
                stats.lost_packets = int(lost_match.group(1))
            
            flows.append(stats)
            i += 2
        
        return flows


@dataclass
class TraceEvent:
    """A single event from an ASCII trace file."""
    time: float
    event_type: str  # '+' (enqueue), '-' (dequeue), 'r' (receive), 'd' (drop)
    node_id: int
    device: str
    packet_type: str
    size: int
    details: str = ""


class AsciiTraceParser:
    """
    Parse ns-3 ASCII trace files.
    
    Format varies by module but typically:
    + time /NodeList/x/DeviceList/y ... packet_info
    """
    
    def parse(self, file_path: str) -> List[TraceEvent]:
        """
        Parse ASCII trace file.
        
        Args:
            file_path: Path to trace file
            
        Returns:
            List of TraceEvent objects
        """
        events = []
        
        try:
            with open(file_path, "r") as f:
                for line in f:
                    event = self._parse_line(line.strip())
                    if event:
                        events.append(event)
        except Exception as e:
            print(f"Error parsing trace file: {e}")
        
        return events
    
    def _parse_line(self, line: str) -> Optional[TraceEvent]:
        """Parse a single trace line."""
        if not line or line.startswith("#"):
            return None
        
        import re
        
        # Common trace format: +/- time /NodeList/n/... size details
        match = re.match(
            r"([+\-rd])\s+(\d+\.?\d*)\s+/NodeList/(\d+)/\S+\s+(\S+)\s+(\d+)\s*(.*)",
            line
        )
        
        if match:
            return TraceEvent(
                event_type=match.group(1),
                time=float(match.group(2)),
                node_id=int(match.group(3)),
                device="",
                packet_type=match.group(4),
                size=int(match.group(5)),
                details=match.group(6),
            )
        
        return None
    
    def get_packet_counts(self, events: List[TraceEvent]) -> dict:
        """
        Calculate packet counts from trace events.
        
        Returns:
            Dict with 'sent', 'received', 'dropped' counts
        """
        counts = {
            "sent": 0,
            "received": 0,
            "dropped": 0,
        }
        
        for event in events:
            if event.event_type == "+":
                counts["sent"] += 1
            elif event.event_type == "r":
                counts["received"] += 1
            elif event.event_type == "d":
                counts["dropped"] += 1
        
        return counts
