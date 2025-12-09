"""
Base Application Class for NS3 GUI Socket Applications.

This class provides the foundation for custom socket-based applications
in ns-3 simulations. Users extend this class to create custom traffic 
generators with full control over packet content.

Compatible with ns-3.45+ Python bindings (cppyy-based).

IMPORTANT: Due to limitations in ns-3 Python bindings, this class does NOT
use ns.Simulator.Schedule() for Python callbacks. Instead, it integrates
with ns-3's built-in application scheduling via helper functions defined
in the simulation script.

Usage:
    class MyApp(ApplicationBase):
        def create_payload(self) -> bytes:
            return b"Hello from my app!"
"""

# NS-3 imports (ns-3.45+ with cppyy bindings)
from ns import ns


class ApplicationBase:
    """
    Base class for custom ns-3 socket applications.
    
    This class manages socket creation and packet transmission.
    The actual scheduling is handled by the simulation script using
    ns-3's native scheduling mechanisms.
    """
    
    def __init__(self, config: dict):
        """
        Initialize the application with configuration.
        
        Args:
            config: Dictionary containing:
                - node: ns.Node object to install app on
                - target_address: Destination IP address (str)
                - target_port: Destination port number (int)
                - protocol: "UDP" or "TCP"
                - start_time: Simulation start time in seconds (float)
                - stop_time: Simulation stop time in seconds (float)
                - send_interval: Time between packets in seconds (float)
                - packet_size: Default packet size in bytes (int)
                - app_name: Name identifier for this application (str)
                - source_node_name: Name of source node (str)
                - target_node_name: Name of target node (str)
        """
        self.config = config
        self.node = config.get('node')
        self.target_address = config.get('target_address', '10.1.1.2')
        self.target_port = config.get('target_port', 9000)
        self.protocol = config.get('protocol', 'UDP').upper()
        self.start_time = config.get('start_time', 1.0)
        self.stop_time = config.get('stop_time', 10.0)
        self.send_interval = config.get('send_interval', 1.0)
        self.packet_size = config.get('packet_size', 512)
        self.app_name = config.get('app_name', 'CustomApp')
        self.source_node_name = config.get('source_node_name', 'Source')
        self.target_node_name = config.get('target_node_name', 'Target')
        
        # Runtime state
        self.socket = None
        self.is_running = False
        self.packets_sent = 0
        self.bytes_sent = 0
        
        # Calculate max packets
        self._max_packets = int((self.stop_time - self.start_time) / self.send_interval) + 1
    
    def setup(self):
        """
        Set up the application socket.
        
        This creates the socket and connects to the target.
        Call this during simulation setup.
        """
        # Create the socket
        self._create_socket()
        
        # Call user initialization hook
        self.on_setup()
        
        self.log(f"Setup complete - ready to send to {self.target_address}:{self.target_port}")
    
    def _create_socket(self):
        """Create the appropriate socket type."""
        if self.protocol == 'TCP':
            tid = ns.TcpSocketFactory.GetTypeId()
        else:
            tid = ns.UdpSocketFactory.GetTypeId()
        
        self.socket = ns.Socket.CreateSocket(self.node, tid)
        
        # Connect to remote (for UDP this just sets the default destination)
        remote = ns.InetSocketAddress(
            ns.Ipv4Address(self.target_address),
            self.target_port
        )
        result = self.socket.Connect(remote.ConvertTo())
        if result == 0:
            self.log(f"Socket connected to {self.target_address}:{self.target_port}")
        else:
            self.log(f"Socket connect returned: {result}")
    
    def start(self):
        """
        Start the application.
        Called by the simulation script at start_time.
        """
        self.is_running = True
        self.on_start()
    
    def stop(self):
        """
        Stop the application.
        Called by the simulation script at stop_time.
        """
        self.is_running = False
        self.on_stop()
        
        # Close socket
        if self.socket:
            try:
                self.socket.Close()
            except:
                pass
    
    def send_packet(self):
        """
        Send one packet.
        Called by the simulation script at each send time.
        
        Returns:
            int: Number of bytes sent, or -1 on error
        """
        if not self.socket:
            return -1
        
        # Get payload from user method
        try:
            payload = self.create_payload()
        except Exception as e:
            self.log(f"Error in create_payload: {e}")
            payload = b"error"
        
        if payload is None:
            payload = b'\x00' * self.packet_size
        
        # Create ns-3 packet with the payload size
        packet = ns.Packet(len(payload))
        
        # Send the packet
        bytes_sent = self.socket.Send(packet)
        
        if bytes_sent > 0:
            self.packets_sent += 1
            self.bytes_sent += bytes_sent
            
            # Call user callback
            try:
                self.on_packet_sent(self.packets_sent, payload)
            except Exception as e:
                self.log(f"Error in on_packet_sent: {e}")
        
        return bytes_sent
    
    # =========================================================================
    # USER-OVERRIDABLE METHODS
    # =========================================================================
    
    def on_setup(self):
        """
        Called during application setup, before simulation starts.
        Override this to initialize custom state variables.
        """
        pass
    
    def on_start(self):
        """Called when the application starts."""
        self.log(f"Starting - target: {self.target_address}:{self.target_port}")
    
    def on_stop(self):
        """Called when the application stops."""
        self.log(f"Stopped - sent {self.packets_sent} packets, {self.bytes_sent} bytes")
    
    def create_payload(self) -> bytes:
        """
        Generate the payload for each packet.
        Override this to customize packet content.
        
        Returns:
            bytes: The payload data to send
        """
        msg = f"Packet {self.packets_sent + 1} from {self.app_name}"
        return msg.encode('utf-8')
    
    def on_packet_sent(self, sequence: int, payload: bytes):
        """
        Called after each packet is sent.
        Override for custom logging or actions.
        
        Args:
            sequence: Packet sequence number (1-indexed)
            payload: The payload that was sent
        """
        self.log(f"Sent packet #{sequence}: {len(payload)} bytes")
    
    # =========================================================================
    # UTILITY METHODS
    # =========================================================================
    
    def log(self, message: str):
        """Log a message with timestamp and app name."""
        try:
            time = ns.Simulator.Now().GetSeconds()
        except:
            time = 0.0
        print(f"[{time:.3f}s] [{self.app_name}] {message}")
    
    def get_current_time(self) -> float:
        """Get the current simulation time in seconds."""
        return ns.Simulator.Now().GetSeconds()
    
    def get_stats(self) -> dict:
        """Get current statistics."""
        return {
            'packets_sent': self.packets_sent,
            'bytes_sent': self.bytes_sent,
        }
