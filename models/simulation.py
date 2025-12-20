"""
Simulation state and configuration models.

Tracks simulation execution state, traffic flows, and results.
"""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional
import uuid

# Try to import PyQt6, but make it optional for testing
try:
    from PyQt6.QtCore import QObject, pyqtSignal
    _PYQT_AVAILABLE = True
except ImportError:
    _PYQT_AVAILABLE = False
    QObject = object  # Fallback for inheritance
    pyqtSignal = lambda *args: None  # Dummy signal


class SimulationStatus(Enum):
    """Current state of the simulation."""
    IDLE = auto()
    BUILDING = auto()
    RUNNING = auto()
    PAUSED = auto()
    COMPLETED = auto()
    ERROR = auto()


class TrafficProtocol(Enum):
    """Network protocol for traffic generation."""
    UDP = "udp"
    TCP = "tcp"


class TrafficApplication(Enum):
    """Type of traffic application."""
    ECHO = "echo"           # Simple request-response
    ONOFF = "onoff"         # Constant bitrate with on/off periods
    BULK_SEND = "bulk"      # TCP bulk transfer
    PING = "ping"           # ICMP ping
    CUSTOM_SOCKET = "socket"  # Custom socket-based application with payload


@dataclass
class TrafficFlow:
    """
    Defines a traffic flow between two nodes.
    
    Represents an ns-3 application configuration for traffic generation.
    Can model OnOff, UdpEcho, BulkSend, and other application types.
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = ""
    
    # Endpoints
    source_node_id: str = ""      # Node generating traffic
    target_node_id: str = ""      # Node receiving traffic  
    dest_address: str = ""        # Explicit destination IP (optional, can be inferred)
    port: int = 9                 # Destination port
    
    # Application type and protocol
    protocol: TrafficProtocol = TrafficProtocol.UDP
    application: TrafficApplication = TrafficApplication.ECHO
    
    # Timing
    start_time: float = 1.0       # seconds
    stop_time: float = 9.0        # seconds
    
    # Traffic parameters
    data_rate: str = "500kb/s"    # Data rate for OnOff
    packet_size: int = 1024       # bytes
    
    # Echo-specific
    echo_packets: int = 10        # Number of packets to send
    echo_interval: float = 1.0    # Interval between packets
    
    # Custom Socket-specific
    socket_payload_type: str = "pattern"  # "pattern", "random", "sequence"
    socket_payload_pattern: str = ""       # Custom payload data (hex or string)
    socket_payload_format: str = "string"  # "string", "hex", "json"
    socket_send_count: int = 10            # Number of packets to send (0 = continuous)
    socket_send_interval: float = 1.0      # Interval between sends
    
    # Application Node integration
    app_enabled: bool = False              # Use attached APPLICATION node for this flow
    app_node_id: str = ""                  # ID of the APPLICATION node to use
    
    def __post_init__(self):
        if not self.name:
            self.name = f"flow_{self.id[:4]}"


@dataclass
class SimulationConfig:
    """Complete simulation configuration."""
    duration: float = 10.0  # seconds
    flows: list[TrafficFlow] = field(default_factory=list)
    enable_pcap: bool = False
    enable_ascii_trace: bool = True
    enable_flow_monitor: bool = True
    random_seed: int = 1
    
    def add_flow(self, flow: TrafficFlow):
        """Add a traffic flow."""
        self.flows.append(flow)
    
    def remove_flow(self, flow_id: str):
        """Remove a traffic flow by ID."""
        self.flows = [f for f in self.flows if f.id != flow_id]
    
    def get_flow(self, flow_id: str) -> Optional[TrafficFlow]:
        """Get a flow by ID."""
        for f in self.flows:
            if f.id == flow_id:
                return f
        return None


@dataclass
class FlowStats:
    """Statistics for a single flow from FlowMonitor."""
    flow_id: int = 0
    source_address: str = ""
    destination_address: str = ""
    source_port: int = 0
    destination_port: int = 0
    protocol: int = 0  # 6=TCP, 17=UDP
    tx_packets: int = 0
    rx_packets: int = 0
    tx_bytes: int = 0
    rx_bytes: int = 0
    delay_sum_ns: int = 0
    jitter_sum_ns: int = 0
    lost_packets: int = 0
    times_forwarded: int = 0
    first_tx_time_ns: int = 0
    last_rx_time_ns: int = 0
    
    @property
    def throughput_mbps(self) -> float:
        """Calculate throughput in Mbps."""
        if self.last_rx_time_ns <= self.first_tx_time_ns:
            return 0.0
        duration_s = (self.last_rx_time_ns - self.first_tx_time_ns) / 1e9
        if duration_s <= 0:
            return 0.0
        return (self.rx_bytes * 8) / duration_s / 1e6
    
    @property
    def packet_loss_percent(self) -> float:
        """Calculate packet loss percentage."""
        if self.tx_packets == 0:
            return 0.0
        return (self.lost_packets / self.tx_packets) * 100
    
    @property
    def mean_delay_ms(self) -> float:
        """Calculate mean delay in milliseconds."""
        if self.rx_packets == 0:
            return 0.0
        return (self.delay_sum_ns / self.rx_packets) / 1e6
    
    @property
    def mean_jitter_ms(self) -> float:
        """Calculate mean jitter in milliseconds."""
        if self.rx_packets <= 1:
            return 0.0
        return (self.jitter_sum_ns / (self.rx_packets - 1)) / 1e6
    
    @property
    def protocol_name(self) -> str:
        """Get protocol name."""
        return {6: "TCP", 17: "UDP"}.get(self.protocol, f"Proto-{self.protocol}")


@dataclass
class SimulationResults:
    """Complete simulation results."""
    success: bool = False
    error_message: str = ""
    duration_actual: float = 0.0
    flow_stats: list[FlowStats] = field(default_factory=list)
    console_output: str = ""
    trace_file_path: str = ""
    pcap_files: list[str] = field(default_factory=list)
    
    @property
    def total_tx_packets(self) -> int:
        return sum(f.tx_packets for f in self.flow_stats)
    
    @property
    def total_rx_packets(self) -> int:
        return sum(f.rx_packets for f in self.flow_stats)
    
    @property
    def total_lost_packets(self) -> int:
        return sum(f.lost_packets for f in self.flow_stats)
    
    @property
    def average_throughput_mbps(self) -> float:
        if not self.flow_stats:
            return 0.0
        return sum(f.throughput_mbps for f in self.flow_stats) / len(self.flow_stats)
    
    @property
    def average_delay_ms(self) -> float:
        delays = [f.mean_delay_ms for f in self.flow_stats if f.rx_packets > 0]
        if not delays:
            return 0.0
        return sum(delays) / len(delays)


@dataclass
class SimulationStats:
    """Statistics collected during simulation."""
    packets_sent: int = 0
    packets_received: int = 0
    packets_dropped: int = 0
    total_bytes: int = 0
    throughput_bps: float = 0.0
    avg_latency_ms: float = 0.0
    
    @property
    def packet_loss_rate(self) -> float:
        if self.packets_sent == 0:
            return 0.0
        return (self.packets_sent - self.packets_received) / self.packets_sent
    
    @classmethod
    def from_results(cls, results: SimulationResults) -> 'SimulationStats':
        """Create stats summary from full results."""
        return cls(
            packets_sent=results.total_tx_packets,
            packets_received=results.total_rx_packets,
            packets_dropped=results.total_lost_packets,
            total_bytes=sum(f.rx_bytes for f in results.flow_stats),
            throughput_bps=results.average_throughput_mbps * 1e6,
            avg_latency_ms=results.average_delay_ms
        )


class SimulationState(QObject):
    """
    Observable simulation state.
    
    Emits signals when state changes to update UI.
    """
    
    # Signals
    statusChanged = pyqtSignal(SimulationStatus)
    progressChanged = pyqtSignal(float, float)  # current_time, total_time
    statsUpdated = pyqtSignal(SimulationStats)
    resultsReady = pyqtSignal(SimulationResults)
    logMessage = pyqtSignal(str, str)  # level, message
    errorOccurred = pyqtSignal(str)
    
    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._status = SimulationStatus.IDLE
        self._current_time = 0.0
        self._end_time = 10.0
        self._stats = SimulationStats()
        self._results: Optional[SimulationResults] = None
        self._error_message = ""
    
    @property
    def status(self) -> SimulationStatus:
        return self._status
    
    @status.setter
    def status(self, value: SimulationStatus):
        if self._status != value:
            self._status = value
            self.statusChanged.emit(value)
    
    @property
    def current_time(self) -> float:
        return self._current_time
    
    @current_time.setter
    def current_time(self, value: float):
        self._current_time = value
        self.progressChanged.emit(value, self._end_time)
    
    @property
    def end_time(self) -> float:
        return self._end_time
    
    @end_time.setter
    def end_time(self, value: float):
        self._end_time = value
    
    @property
    def progress(self) -> float:
        """Progress as 0.0 to 1.0."""
        if self._end_time <= 0:
            return 0.0
        return min(1.0, self._current_time / self._end_time)
    
    @property
    def stats(self) -> SimulationStats:
        return self._stats
    
    @property
    def results(self) -> Optional[SimulationResults]:
        return self._results
    
    def update_stats(self, stats: SimulationStats):
        """Update statistics and emit signal."""
        self._stats = stats
        self.statsUpdated.emit(stats)
    
    def set_results(self, results: SimulationResults):
        """Set final results and emit signal."""
        self._results = results
        self._stats = SimulationStats.from_results(results)
        self.statsUpdated.emit(self._stats)
        self.resultsReady.emit(results)
    
    @property
    def is_running(self) -> bool:
        return self._status == SimulationStatus.RUNNING
    
    @property
    def is_idle(self) -> bool:
        return self._status == SimulationStatus.IDLE
    
    @property
    def can_start(self) -> bool:
        return self._status in (SimulationStatus.IDLE, SimulationStatus.COMPLETED, SimulationStatus.ERROR)
    
    @property
    def can_stop(self) -> bool:
        return self._status in (SimulationStatus.RUNNING, SimulationStatus.PAUSED, SimulationStatus.BUILDING)
    
    def reset(self):
        """Reset to initial state."""
        self._status = SimulationStatus.IDLE
        self._current_time = 0.0
        self._stats = SimulationStats()
        self._results = None
        self._error_message = ""
        self.statusChanged.emit(self._status)
        self.progressChanged.emit(0.0, self._end_time)
        self.statsUpdated.emit(self._stats)
    
    def log(self, level: str, message: str):
        """Emit a log message."""
        self.logMessage.emit(level, message)
    
    def set_error(self, message: str):
        """Set error state with message."""
        self._error_message = message
        self.status = SimulationStatus.ERROR
        self.errorOccurred.emit(message)
