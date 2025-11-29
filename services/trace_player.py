"""
Trace Player Service.

Parses ns-3 trace output and provides playback functionality
for animating packets in the GUI.
"""

import re
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import List, Optional, Dict, Callable
from PyQt6.QtCore import QObject, QTimer, pyqtSignal


class PacketEventType(Enum):
    """Type of packet event."""
    TX = auto()      # Packet transmitted
    RX = auto()      # Packet received
    ENQUEUE = auto() # Packet enqueued
    DEQUEUE = auto() # Packet dequeued
    DROP = auto()    # Packet dropped


@dataclass
class PacketEvent:
    """A single packet event from the trace."""
    time_ns: int                    # Simulation time in nanoseconds
    event_type: PacketEventType     # Type of event
    node_id: int                    # Node where event occurred
    device_id: int = 0              # Device/interface index
    packet_id: int = 0              # Unique packet identifier
    packet_size: int = 0            # Packet size in bytes
    source_node: int = -1           # Source node (for animation)
    target_node: int = -1           # Target node (for animation)
    link_id: str = ""               # Link ID for animation
    protocol: str = ""              # Protocol (UDP, TCP, etc.)
    extra: Dict = field(default_factory=dict)
    
    @property
    def time_seconds(self) -> float:
        """Get time in seconds."""
        return self.time_ns / 1e9
    
    @property
    def time_ms(self) -> float:
        """Get time in milliseconds."""
        return self.time_ns / 1e6


@dataclass
class TraceStats:
    """Statistics from a trace."""
    total_events: int = 0
    total_packets_tx: int = 0
    total_packets_rx: int = 0
    total_packets_dropped: int = 0
    total_bytes_tx: int = 0
    total_bytes_rx: int = 0
    duration_ns: int = 0
    
    @property
    def duration_seconds(self) -> float:
        return self.duration_ns / 1e9


class TraceParser:
    """
    Parse ns-3 trace output.
    
    Supports multiple trace formats:
    - Custom PKT| format from generated scripts
    - ASCII trace format
    """
    
    # Pattern for our custom PKT format:
    # PKT|time_ns|event|node|device|size|src_node|dst_node|link_id|protocol
    PKT_PATTERN = re.compile(
        r"PKT\|(\d+)\|(\w+)\|(\d+)\|(\d+)\|(\d+)\|(-?\d+)\|(-?\d+)\|([^|]*)\|?(\w*)"
    )
    
    # Pattern for standard ASCII trace:
    # +/- time /NodeList/n/DeviceList/d/... size ...
    ASCII_PATTERN = re.compile(
        r"([+\-rd])\s+(\d+\.?\d*(?:e[+\-]?\d+)?(?:ns|us|ms|s)?)\s+"
        r"/NodeList/(\d+)/DeviceList/(\d+)/[^\s]+\s+"
        r"(?:ns3::)?(\w+)\s*"
    )
    
    def parse_file(self, file_path: str) -> List[PacketEvent]:
        """Parse a trace file."""
        events = []
        try:
            with open(file_path, 'r') as f:
                for line in f:
                    event = self.parse_line(line.strip())
                    if event:
                        events.append(event)
        except Exception as e:
            print(f"Error parsing trace file: {e}")
        
        # Sort by time
        events.sort(key=lambda e: e.time_ns)
        return events
    
    def parse_output(self, output: str) -> List[PacketEvent]:
        """Parse trace output string."""
        events = []
        for line in output.split('\n'):
            event = self.parse_line(line.strip())
            if event:
                events.append(event)
        events.sort(key=lambda e: e.time_ns)
        return events
    
    def parse_line(self, line: str) -> Optional[PacketEvent]:
        """Parse a single trace line."""
        if not line:
            return None
        
        # Try custom PKT format first
        match = self.PKT_PATTERN.match(line)
        if match:
            return self._parse_pkt_format(match)
        
        # Try ASCII trace format
        match = self.ASCII_PATTERN.match(line)
        if match:
            return self._parse_ascii_format(match)
        
        return None
    
    def _parse_pkt_format(self, match: re.Match) -> PacketEvent:
        """Parse our custom PKT format."""
        event_map = {
            'TX': PacketEventType.TX,
            'RX': PacketEventType.RX,
            'ENQ': PacketEventType.ENQUEUE,
            'DEQ': PacketEventType.DEQUEUE,
            'DROP': PacketEventType.DROP,
        }
        
        return PacketEvent(
            time_ns=int(match.group(1)),
            event_type=event_map.get(match.group(2), PacketEventType.TX),
            node_id=int(match.group(3)),
            device_id=int(match.group(4)),
            packet_size=int(match.group(5)),
            source_node=int(match.group(6)),
            target_node=int(match.group(7)),
            link_id=match.group(8),
            protocol=match.group(9) if match.group(9) else "",
        )
    
    def _parse_ascii_format(self, match: re.Match) -> PacketEvent:
        """Parse standard ASCII trace format."""
        event_map = {
            '+': PacketEventType.ENQUEUE,
            '-': PacketEventType.DEQUEUE,
            'r': PacketEventType.RX,
            'd': PacketEventType.DROP,
        }
        
        # Parse time (could be in different units)
        time_str = match.group(2)
        time_ns = self._parse_time_to_ns(time_str)
        
        return PacketEvent(
            time_ns=time_ns,
            event_type=event_map.get(match.group(1), PacketEventType.TX),
            node_id=int(match.group(3)),
            device_id=int(match.group(4)),
            protocol=match.group(5),
        )
    
    def _parse_time_to_ns(self, time_str: str) -> int:
        """Parse time string to nanoseconds."""
        time_str = time_str.lower()
        
        if time_str.endswith('ns'):
            return int(float(time_str[:-2]))
        elif time_str.endswith('us'):
            return int(float(time_str[:-2]) * 1e3)
        elif time_str.endswith('ms'):
            return int(float(time_str[:-2]) * 1e6)
        elif time_str.endswith('s'):
            return int(float(time_str[:-1]) * 1e9)
        else:
            # Assume seconds
            return int(float(time_str) * 1e9)
    
    def compute_stats(self, events: List[PacketEvent]) -> TraceStats:
        """Compute statistics from events."""
        stats = TraceStats()
        stats.total_events = len(events)
        
        for event in events:
            if event.event_type == PacketEventType.TX:
                stats.total_packets_tx += 1
                stats.total_bytes_tx += event.packet_size
            elif event.event_type == PacketEventType.RX:
                stats.total_packets_rx += 1
                stats.total_bytes_rx += event.packet_size
            elif event.event_type == PacketEventType.DROP:
                stats.total_packets_dropped += 1
        
        if events:
            stats.duration_ns = events[-1].time_ns - events[0].time_ns
        
        return stats


class TracePlayer(QObject):
    """
    Plays back trace events with timing control.
    
    Emits signals for packet events that the GUI can use
    to animate packets on the canvas.
    """
    
    # Signals
    packet_event = pyqtSignal(object)  # PacketEvent
    time_changed = pyqtSignal(float)   # Current time in seconds
    playback_finished = pyqtSignal()
    stats_updated = pyqtSignal(object) # TraceStats
    
    # Playback speed options
    SPEEDS = [0.25, 0.5, 1.0, 2.0, 5.0, 10.0, 50.0, 100.0]
    
    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        
        self._events: List[PacketEvent] = []
        self._current_index: int = 0
        self._current_time_ns: int = 0
        self._start_time_ns: int = 0
        self._end_time_ns: int = 0
        
        self._speed: float = 1.0
        self._is_playing: bool = False
        self._is_loaded: bool = False
        
        # Timer for playback
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._advance)
        self._tick_interval_ms = 16  # ~60fps
        
        self._parser = TraceParser()
        self._stats = TraceStats()
    
    @property
    def is_loaded(self) -> bool:
        return self._is_loaded
    
    @property
    def is_playing(self) -> bool:
        return self._is_playing
    
    @property
    def current_time(self) -> float:
        """Current playback time in seconds."""
        return self._current_time_ns / 1e9
    
    @property
    def duration(self) -> float:
        """Total duration in seconds."""
        if not self._events:
            return 0.0
        return (self._end_time_ns - self._start_time_ns) / 1e9
    
    @property
    def progress(self) -> float:
        """Playback progress 0.0 to 1.0."""
        if self.duration <= 0:
            return 0.0
        elapsed = self._current_time_ns - self._start_time_ns
        return min(1.0, max(0.0, elapsed / (self._end_time_ns - self._start_time_ns)))
    
    @property
    def speed(self) -> float:
        return self._speed
    
    @speed.setter
    def speed(self, value: float):
        self._speed = max(0.1, min(100.0, value))
    
    @property
    def stats(self) -> TraceStats:
        return self._stats
    
    @property
    def event_count(self) -> int:
        return len(self._events)
    
    def load_file(self, file_path: str) -> bool:
        """Load events from a trace file."""
        self.stop()
        self._events = self._parser.parse_file(file_path)
        return self._finalize_load()
    
    def load_output(self, output: str) -> bool:
        """Load events from simulation output string."""
        self.stop()
        self._events = self._parser.parse_output(output)
        return self._finalize_load()
    
    def load_events(self, events: List[PacketEvent]) -> bool:
        """Load events directly."""
        self.stop()
        self._events = sorted(events, key=lambda e: e.time_ns)
        return self._finalize_load()
    
    def _finalize_load(self) -> bool:
        """Finalize loading of events."""
        if not self._events:
            self._is_loaded = False
            return False
        
        self._start_time_ns = self._events[0].time_ns
        self._end_time_ns = self._events[-1].time_ns
        self._current_time_ns = self._start_time_ns
        self._current_index = 0
        self._is_loaded = True
        
        # Compute stats
        self._stats = self._parser.compute_stats(self._events)
        self.stats_updated.emit(self._stats)
        
        self.time_changed.emit(self.current_time)
        return True
    
    def play(self):
        """Start or resume playback."""
        if not self._is_loaded:
            return
        
        self._is_playing = True
        self._timer.start(self._tick_interval_ms)
    
    def pause(self):
        """Pause playback."""
        self._is_playing = False
        self._timer.stop()
    
    def stop(self):
        """Stop playback and reset to beginning."""
        self._is_playing = False
        self._timer.stop()
        self._current_index = 0
        if self._events:
            self._current_time_ns = self._start_time_ns
        else:
            self._current_time_ns = 0
        self.time_changed.emit(self.current_time)
    
    def seek(self, time_seconds: float):
        """Seek to a specific time."""
        was_playing = self._is_playing
        self.pause()
        
        target_ns = int(time_seconds * 1e9)
        target_ns = max(self._start_time_ns, min(self._end_time_ns, target_ns))
        self._current_time_ns = target_ns
        
        # Find the event index for this time
        self._current_index = self._find_event_index(target_ns)
        
        self.time_changed.emit(self.current_time)
        
        if was_playing:
            self.play()
    
    def seek_progress(self, progress: float):
        """Seek to a progress point (0.0 to 1.0)."""
        if self.duration <= 0:
            return
        time_seconds = progress * self.duration
        self.seek(time_seconds)
    
    def _find_event_index(self, time_ns: int) -> int:
        """Binary search for event index at or after time."""
        left, right = 0, len(self._events)
        while left < right:
            mid = (left + right) // 2
            if self._events[mid].time_ns < time_ns:
                left = mid + 1
            else:
                right = mid
        return left
    
    def _advance(self):
        """Advance playback by one tick."""
        if not self._is_playing or not self._is_loaded:
            return
        
        # Calculate time advancement
        real_dt_ns = self._tick_interval_ms * 1e6  # Convert ms to ns
        sim_dt_ns = int(real_dt_ns * self._speed)
        
        new_time_ns = self._current_time_ns + sim_dt_ns
        
        # Emit all events between current time and new time
        while (self._current_index < len(self._events) and 
               self._events[self._current_index].time_ns <= new_time_ns):
            event = self._events[self._current_index]
            self.packet_event.emit(event)
            self._current_index += 1
        
        self._current_time_ns = new_time_ns
        self.time_changed.emit(self.current_time)
        
        # Check if finished
        if self._current_time_ns >= self._end_time_ns:
            self.pause()
            self.playback_finished.emit()
    
    def get_events_in_range(self, start_ns: int, end_ns: int) -> List[PacketEvent]:
        """Get all events in a time range."""
        start_idx = self._find_event_index(start_ns)
        end_idx = self._find_event_index(end_ns)
        return self._events[start_idx:end_idx]
