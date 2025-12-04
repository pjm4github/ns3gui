"""
Help dialog with comprehensive ns-3 API reference.

Provides 8 tabs covering each step of ns-3 simulation:
1. Create Nodes
2. Create Channels/Links
3. Install Internet Stack
4. Assign IP Addresses
5. Setup Routing
6. Create Applications
7. Enable Tracing
8. Run Simulation
"""

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QColor
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget,
    QLabel, QScrollArea, QFrame, QPushButton, QTextBrowser,
    QSplitter, QTreeWidget, QTreeWidgetItem, QSizePolicy
)


class HelpDialog(QDialog):
    """Main help dialog with tabbed API reference."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("ns-3 Simulation Help")
        self.setMinimumSize(900, 700)
        self.resize(1000, 750)
        self._setup_ui()
    
    def _setup_ui(self):
        """Setup the dialog UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Header
        header = QFrame()
        header.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #1e40af, stop:1 #3b82f6);
                padding: 20px;
            }
        """)
        header_layout = QVBoxLayout(header)
        
        title = QLabel("ns-3 Simulation Guide")
        title.setStyleSheet("color: white; font-size: 24px; font-weight: bold;")
        header_layout.addWidget(title)
        
        subtitle = QLabel("Complete API reference for building network simulations")
        subtitle.setStyleSheet("color: rgba(255,255,255,0.8); font-size: 14px;")
        header_layout.addWidget(subtitle)
        
        layout.addWidget(header)
        
        # Tab widget
        self._tabs = QTabWidget()
        self._tabs.setStyleSheet("""
            QTabWidget::pane {
                border: none;
                background: white;
            }
            QTabBar::tab {
                padding: 10px 16px;
                margin-right: 2px;
                background: #f3f4f6;
                border: none;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
            }
            QTabBar::tab:selected {
                background: white;
                color: #1e40af;
                font-weight: bold;
            }
            QTabBar::tab:hover:!selected {
                background: #e5e7eb;
            }
        """)
        
        # Add all 8 tabs
        self._tabs.addTab(self._create_nodes_tab(), "1. Nodes")
        self._tabs.addTab(self._create_channels_tab(), "2. Channels")
        self._tabs.addTab(self._create_stack_tab(), "3. Internet Stack")
        self._tabs.addTab(self._create_addressing_tab(), "4. IP Addresses")
        self._tabs.addTab(self._create_routing_tab(), "5. Routing")
        self._tabs.addTab(self._create_applications_tab(), "6. Applications")
        self._tabs.addTab(self._create_tracing_tab(), "7. Tracing")
        self._tabs.addTab(self._create_simulation_tab(), "8. Simulation")
        
        layout.addWidget(self._tabs)
        
        # Footer with close button
        footer = QFrame()
        footer.setStyleSheet("background: #f9fafb; border-top: 1px solid #e5e7eb;")
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(16, 12, 16, 12)
        
        footer_layout.addStretch()
        
        close_btn = QPushButton("Close")
        close_btn.setStyleSheet("""
            QPushButton {
                background: #3b82f6;
                color: white;
                border: none;
                padding: 8px 24px;
                border-radius: 6px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #2563eb;
            }
        """)
        close_btn.clicked.connect(self.accept)
        footer_layout.addWidget(close_btn)
        
        layout.addWidget(footer)
    
    def _create_scroll_content(self, html_content: str) -> QWidget:
        """Create a scrollable content widget with HTML."""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                background: white;
            }
        """)
        
        content = QTextBrowser()
        content.setOpenExternalLinks(True)
        content.setStyleSheet("""
            QTextBrowser {
                border: none;
                padding: 20px;
                background: white;
                font-size: 13px;
                line-height: 1.6;
            }
        """)
        content.setHtml(self._wrap_html(html_content))
        
        scroll.setWidget(content)
        return scroll
    
    def _wrap_html(self, content: str) -> str:
        """Wrap content in styled HTML."""
        return f"""
        <html>
        <head>
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                font-size: 13px;
                line-height: 1.6;
                color: #1f2937;
            }}
            h1 {{
                color: #1e40af;
                font-size: 22px;
                border-bottom: 2px solid #3b82f6;
                padding-bottom: 8px;
                margin-top: 0;
            }}
            h2 {{
                color: #1e40af;
                font-size: 18px;
                margin-top: 24px;
                margin-bottom: 12px;
            }}
            h3 {{
                color: #374151;
                font-size: 15px;
                margin-top: 20px;
                margin-bottom: 8px;
            }}
            table {{
                border-collapse: collapse;
                width: 100%;
                margin: 12px 0;
            }}
            th {{
                background: #1e40af;
                color: white;
                padding: 10px 12px;
                text-align: left;
                font-weight: 600;
            }}
            td {{
                border: 1px solid #e5e7eb;
                padding: 8px 12px;
                vertical-align: top;
            }}
            tr:nth-child(even) {{
                background: #f9fafb;
            }}
            code {{
                background: #f3f4f6;
                padding: 2px 6px;
                border-radius: 4px;
                font-family: 'SF Mono', Consolas, monospace;
                font-size: 12px;
                color: #dc2626;
            }}
            pre {{
                background: #1f2937;
                color: #f9fafb;
                padding: 16px;
                border-radius: 8px;
                overflow-x: auto;
                font-family: 'SF Mono', Consolas, monospace;
                font-size: 12px;
                line-height: 1.5;
            }}
            .tip {{
                background: #ecfdf5;
                border-left: 4px solid #10b981;
                padding: 12px 16px;
                margin: 16px 0;
                border-radius: 0 8px 8px 0;
            }}
            .warning {{
                background: #fef3c7;
                border-left: 4px solid #f59e0b;
                padding: 12px 16px;
                margin: 16px 0;
                border-radius: 0 8px 8px 0;
            }}
            .note {{
                background: #eff6ff;
                border-left: 4px solid #3b82f6;
                padding: 12px 16px;
                margin: 16px 0;
                border-radius: 0 8px 8px 0;
            }}
        </style>
        </head>
        <body>
        {content}
        </body>
        </html>
        """
    
    def _create_nodes_tab(self) -> QWidget:
        """Create the Nodes tab content."""
        content = """
        <h1>Step 1: Create Nodes</h1>
        
        <p>In ns-3, nodes are generic containers that become hosts, routers, switches, or 
        wireless devices based on what you install on them. The first step in any simulation 
        is creating the nodes.</p>
        
        <div class="tip">
            <strong>GUI Tip:</strong> Use the Node Palette on the left to drag and drop 
            nodes onto the canvas. Choose from Host, Router, Switch, WiFi Station, or Access Point.
        </div>
        
        <h2>NodeContainer</h2>
        <p>The primary container for managing multiple nodes.</p>
        
        <table>
            <tr><th>Method</th><th>Description</th><th>Example</th></tr>
            <tr>
                <td><code>NodeContainer()</code></td>
                <td>Constructor - creates empty container</td>
                <td><code>nodes = ns.NodeContainer()</code></td>
            </tr>
            <tr>
                <td><code>.Create(n)</code></td>
                <td>Create n blank nodes</td>
                <td><code>nodes.Create(4)</code></td>
            </tr>
            <tr>
                <td><code>.Add(node)</code></td>
                <td>Add existing node to container</td>
                <td><code>nodes.Add(otherNode)</code></td>
            </tr>
            <tr>
                <td><code>.Add(container)</code></td>
                <td>Add nodes from another container</td>
                <td><code>nodes.Add(otherContainer)</code></td>
            </tr>
            <tr>
                <td><code>.Get(i)</code></td>
                <td>Get node at index i</td>
                <td><code>node = nodes.Get(0)</code></td>
            </tr>
            <tr>
                <td><code>.GetN()</code></td>
                <td>Get number of nodes</td>
                <td><code>count = nodes.GetN()</code></td>
            </tr>
        </table>
        
        <h2>Node</h2>
        <p>Individual node object representing a network device.</p>
        
        <table>
            <tr><th>Method</th><th>Description</th><th>Example</th></tr>
            <tr>
                <td><code>Node()</code></td>
                <td>Create single node</td>
                <td><code>node = ns.Node()</code></td>
            </tr>
            <tr>
                <td><code>.GetId()</code></td>
                <td>Get unique node ID</td>
                <td><code>id = node.GetId()</code></td>
            </tr>
            <tr>
                <td><code>.GetNDevices()</code></td>
                <td>Count of network devices/interfaces</td>
                <td><code>n = node.GetNDevices()</code></td>
            </tr>
            <tr>
                <td><code>.GetDevice(i)</code></td>
                <td>Get network device at index</td>
                <td><code>dev = node.GetDevice(0)</code></td>
            </tr>
            <tr>
                <td><code>.GetNApplications()</code></td>
                <td>Count of installed applications</td>
                <td><code>n = node.GetNApplications()</code></td>
            </tr>
            <tr>
                <td><code>.GetApplication(i)</code></td>
                <td>Get application at index</td>
                <td><code>app = node.GetApplication(0)</code></td>
            </tr>
        </table>
        
        <h2>Naming Nodes</h2>
        <p>You can assign human-readable names to nodes for easier reference.</p>
        
        <table>
            <tr><th>Method</th><th>Description</th><th>Example</th></tr>
            <tr>
                <td><code>Names.Add(name, node)</code></td>
                <td>Assign name to node</td>
                <td><code>ns.Names.Add("server", nodes.Get(0))</code></td>
            </tr>
            <tr>
                <td><code>Names.Find(name)</code></td>
                <td>Find object by name</td>
                <td><code>node = ns.Names.Find("server")</code></td>
            </tr>
        </table>
        
        <h2>Node Types in GUI</h2>
        <table>
            <tr><th>Type</th><th>Icon</th><th>Description</th></tr>
            <tr><td>Host</td><td>H</td><td>End device (PC, server, workstation)</td></tr>
            <tr><td>Router</td><td>R</td><td>Forwards packets between networks</td></tr>
            <tr><td>Switch</td><td>S</td><td>Layer 2 device (Ethernet bridge)</td></tr>
            <tr><td>Station</td><td>📶</td><td>WiFi client device</td></tr>
            <tr><td>Access Point</td><td>AP</td><td>WiFi access point</td></tr>
        </table>
        
        <h2>Example Code</h2>
        <pre>
# Create a container with 4 nodes
nodes = ns.NodeContainer()
nodes.Create(4)

# Access individual nodes
server = nodes.Get(0)
client = nodes.Get(1)
router = nodes.Get(2)
switch = nodes.Get(3)

# Name nodes for easier reference
ns.Names.Add("server", server)
ns.Names.Add("client", client)

# Check node count
print(f"Created {nodes.GetN()} nodes")
        </pre>
        """
        return self._create_scroll_content(content)
    
    def _create_channels_tab(self) -> QWidget:
        """Create the Channels/Links tab content."""
        content = """
        <h1>Step 2: Create Channels/Links</h1>
        
        <p>Channels connect nodes together. ns-3 provides different channel types for 
        wired and wireless connections.</p>
        
        <div class="tip">
            <strong>GUI Tip:</strong> Right-click and drag between nodes to create links. 
            The link type is determined by the connected node types.
        </div>
        
        <h2>Point-to-Point (Dedicated Link)</h2>
        <p>Creates a dedicated connection between exactly 2 nodes, like a direct cable.</p>
        
        <table>
            <tr><th>Method</th><th>Description</th><th>Example</th></tr>
            <tr>
                <td><code>PointToPointHelper()</code></td>
                <td>Constructor</td>
                <td><code>p2p = ns.PointToPointHelper()</code></td>
            </tr>
            <tr>
                <td><code>.SetDeviceAttribute(name, value)</code></td>
                <td>Set device attribute</td>
                <td><code>p2p.SetDeviceAttribute('DataRate', ns.StringValue('100Mbps'))</code></td>
            </tr>
            <tr>
                <td><code>.SetChannelAttribute(name, value)</code></td>
                <td>Set channel attribute</td>
                <td><code>p2p.SetChannelAttribute('Delay', ns.StringValue('2ms'))</code></td>
            </tr>
            <tr>
                <td><code>.Install(nodes)</code></td>
                <td>Install on NodeContainer (2 nodes)</td>
                <td><code>devices = p2p.Install(nodes)</code></td>
            </tr>
            <tr>
                <td><code>.Install(nodeA, nodeB)</code></td>
                <td>Install on two specific nodes</td>
                <td><code>devices = p2p.Install(n1, n2)</code></td>
            </tr>
        </table>
        
        <h3>Common P2P Attributes</h3>
        <table>
            <tr><th>Attribute</th><th>Values</th><th>Description</th></tr>
            <tr><td>DataRate</td><td>"10Mbps", "100Mbps", "1Gbps", "10Gbps"</td><td>Link bandwidth</td></tr>
            <tr><td>Delay</td><td>"1ms", "2ms", "10us", "1ns"</td><td>Propagation delay</td></tr>
            <tr><td>Mtu</td><td>1500 (default)</td><td>Maximum transmission unit</td></tr>
        </table>
        
        <h2>CSMA (Ethernet/Shared Medium)</h2>
        <p>Shared medium where multiple nodes share bandwidth (like Ethernet hub).</p>
        
        <table>
            <tr><th>Method</th><th>Description</th><th>Example</th></tr>
            <tr>
                <td><code>CsmaHelper()</code></td>
                <td>Constructor</td>
                <td><code>csma = ns.CsmaHelper()</code></td>
            </tr>
            <tr>
                <td><code>.SetChannelAttribute(name, value)</code></td>
                <td>Set channel attribute</td>
                <td><code>csma.SetChannelAttribute('DataRate', ns.StringValue('100Mbps'))</code></td>
            </tr>
            <tr>
                <td><code>.Install(nodes)</code></td>
                <td>Install on all nodes in container</td>
                <td><code>devices = csma.Install(nodes)</code></td>
            </tr>
        </table>
        
        <h2>WiFi</h2>
        <p>802.11 wireless network setup requires multiple helpers.</p>
        
        <h3>WiFi Standards</h3>
        <table>
            <tr><th>Standard</th><th>Constant</th><th>Band</th><th>Max Speed</th></tr>
            <tr><td>802.11a</td><td><code>ns.WIFI_STANDARD_80211a</code></td><td>5 GHz</td><td>54 Mbps</td></tr>
            <tr><td>802.11b</td><td><code>ns.WIFI_STANDARD_80211b</code></td><td>2.4 GHz</td><td>11 Mbps</td></tr>
            <tr><td>802.11g</td><td><code>ns.WIFI_STANDARD_80211g</code></td><td>2.4 GHz</td><td>54 Mbps</td></tr>
            <tr><td>802.11n</td><td><code>ns.WIFI_STANDARD_80211n</code></td><td>2.4/5 GHz</td><td>600 Mbps</td></tr>
            <tr><td>802.11ac</td><td><code>ns.WIFI_STANDARD_80211ac</code></td><td>5 GHz</td><td>6.9 Gbps</td></tr>
            <tr><td>802.11ax</td><td><code>ns.WIFI_STANDARD_80211ax</code></td><td>2.4/5/6 GHz</td><td>9.6 Gbps</td></tr>
        </table>
        
        <h3>WiFi Helper APIs</h3>
        <table>
            <tr><th>Helper</th><th>Purpose</th></tr>
            <tr><td><code>WifiHelper</code></td><td>Main WiFi configuration (standard, rate manager)</td></tr>
            <tr><td><code>YansWifiChannelHelper</code></td><td>Propagation and loss models</td></tr>
            <tr><td><code>YansWifiPhyHelper</code></td><td>Physical layer configuration</td></tr>
            <tr><td><code>WifiMacHelper</code></td><td>MAC layer (Station, AP, Ad-hoc)</td></tr>
        </table>
        
        <h3>MAC Types</h3>
        <pre>
# Station (client)
mac.SetType('ns3::StaWifiMac',
    'Ssid', ns.SsidValue(ssid),
    'ActiveProbing', ns.BooleanValue(False))

# Access Point
mac.SetType('ns3::ApWifiMac',
    'Ssid', ns.SsidValue(ssid))

# Ad-hoc (peer-to-peer)
mac.SetType('ns3::AdhocWifiMac')
        </pre>
        
        <h3>Rate Managers</h3>
        <table>
            <tr><th>Manager</th><th>Description</th></tr>
            <tr><td><code>'ns3::AarfWifiManager'</code></td><td>Adaptive ARF (good default)</td></tr>
            <tr><td><code>'ns3::ConstantRateWifiManager'</code></td><td>Fixed rate</td></tr>
            <tr><td><code>'ns3::MinstrelWifiManager'</code></td><td>Minstrel algorithm</td></tr>
            <tr><td><code>'ns3::IdealWifiManager'</code></td><td>Ideal (uses SNR)</td></tr>
        </table>
        
        <h2>Bridge (L2 Switch)</h2>
        <table>
            <tr><th>Method</th><th>Description</th><th>Example</th></tr>
            <tr>
                <td><code>BridgeHelper()</code></td>
                <td>Constructor</td>
                <td><code>bridge = ns.BridgeHelper()</code></td>
            </tr>
            <tr>
                <td><code>.Install(node, devices)</code></td>
                <td>Install bridge on switch node</td>
                <td><code>bridge.Install(switchNode, connectedDevices)</code></td>
            </tr>
        </table>
        
        <h2>NetDeviceContainer</h2>
        <p>Returned by Install() methods, holds network interfaces.</p>
        
        <table>
            <tr><th>Method</th><th>Description</th><th>Example</th></tr>
            <tr><td><code>.Get(i)</code></td><td>Get device at index</td><td><code>dev = devices.Get(0)</code></td>
            <tr><td><code>.GetN()</code></td><td>Get device count</td><td><code>n = devices.GetN()</code></td>
            <tr><td><code>.Add(device)</code></td><td>Add device</td><td><code>devices.Add(dev)</code></td>
            <tr><td><code>.Add(container)</code></td><td>Merge containers</td><td><code>devices.Add(other)</code></td>
        </table>
        
        <h2>Complete WiFi Example</h2>
        <pre>
# Create SSID
ssid = ns.Ssid('my-network')

# Setup channel and PHY
channel = ns.YansWifiChannelHelper.Default()
phy = ns.YansWifiPhyHelper()
phy.SetChannel(channel.Create())

# Setup WiFi helper
wifi = ns.WifiHelper()
wifi.SetStandard(ns.WIFI_STANDARD_80211n)
wifi.SetRemoteStationManager('ns3::AarfWifiManager')

# Setup MAC for stations
mac = ns.WifiMacHelper()
mac.SetType('ns3::StaWifiMac',
    'Ssid', ns.SsidValue(ssid))
staDevices = wifi.Install(phy, mac, staNodes)

# Setup MAC for AP
mac.SetType('ns3::ApWifiMac',
    'Ssid', ns.SsidValue(ssid))
apDevices = wifi.Install(phy, mac, apNodes)

# Mobility is REQUIRED for WiFi
mobility = ns.MobilityHelper()
mobility.SetMobilityModel('ns3::ConstantPositionMobilityModel')
mobility.Install(staNodes)
mobility.Install(apNodes)
        </pre>
        """
        return self._create_scroll_content(content)
    
    def _create_stack_tab(self) -> QWidget:
        """Create the Internet Stack tab content."""
        content = """
        <h1>Step 3: Install Internet Stack</h1>
        
        <p>The Internet Stack installs the TCP/IP protocol suite on nodes, including 
        IPv4, TCP, UDP, ICMP, and ARP. Without this, nodes cannot communicate using IP.</p>
        
        <div class="note">
            <strong>Note:</strong> L2 switches (bridges) should NOT have the internet stack 
            installed - they forward at Layer 2 only.
        </div>
        
        <h2>InternetStackHelper</h2>
        
        <table>
            <tr><th>Method</th><th>Description</th><th>Example</th></tr>
            <tr>
                <td><code>InternetStackHelper()</code></td>
                <td>Constructor</td>
                <td><code>stack = ns.InternetStackHelper()</code></td>
            </tr>
            <tr>
                <td><code>.Install(nodes)</code></td>
                <td>Install on NodeContainer</td>
                <td><code>stack.Install(nodes)</code></td>
            </tr>
            <tr>
                <td><code>.Install(node)</code></td>
                <td>Install on single node</td>
                <td><code>stack.Install(node)</code></td>
            </tr>
            <tr>
                <td><code>.InstallAll()</code></td>
                <td>Install on all nodes in simulation</td>
                <td><code>stack.InstallAll()</code></td>
            </tr>
            <tr>
                <td><code>.SetRoutingHelper(helper)</code></td>
                <td>Set routing protocol</td>
                <td><code>stack.SetRoutingHelper(olsr)</code></td>
            </tr>
            <tr>
                <td><code>.SetIpv4StackInstall(bool)</code></td>
                <td>Enable/disable IPv4</td>
                <td><code>stack.SetIpv4StackInstall(True)</code></td>
            </tr>
            <tr>
                <td><code>.SetIpv6StackInstall(bool)</code></td>
                <td>Enable/disable IPv6</td>
                <td><code>stack.SetIpv6StackInstall(False)</code></td>
            </tr>
            <tr>
                <td><code>.SetTcp(type)</code></td>
                <td>Set TCP congestion control variant</td>
                <td><code>stack.SetTcp('ns3::TcpCubic')</code></td>
            </tr>
        </table>
        
        <h2>TCP Variants</h2>
        <p>ns-3 supports multiple TCP congestion control algorithms.</p>
        
        <table>
            <tr><th>Variant</th><th>String</th><th>Description</th></tr>
            <tr>
                <td>NewReno</td>
                <td><code>'ns3::TcpNewReno'</code></td>
                <td>Default, classic TCP</td>
            </tr>
            <tr>
                <td>CUBIC</td>
                <td><code>'ns3::TcpCubic'</code></td>
                <td>Linux default, good for high BDP</td>
            </tr>
            <tr>
                <td>BBR</td>
                <td><code>'ns3::TcpBbr'</code></td>
                <td>Google's bottleneck bandwidth algorithm</td>
            </tr>
            <tr>
                <td>Vegas</td>
                <td><code>'ns3::TcpVegas'</code></td>
                <td>Delay-based congestion control</td>
            </tr>
            <tr>
                <td>Westwood+</td>
                <td><code>'ns3::TcpWestwoodPlus'</code></td>
                <td>Good for wireless networks</td>
            </tr>
        </table>
        
        <h2>What Gets Installed</h2>
        <p>The InternetStackHelper installs:</p>
        <ul>
            <li><strong>IPv4/IPv6</strong> - Network layer addressing and routing</li>
            <li><strong>TCP</strong> - Reliable, ordered byte stream</li>
            <li><strong>UDP</strong> - Unreliable datagram service</li>
            <li><strong>ICMP</strong> - Control messages (ping, errors)</li>
            <li><strong>ARP</strong> - Address resolution (IP to MAC)</li>
            <li><strong>Routing tables</strong> - Empty initially</li>
        </ul>
        
        <h2>Example: Basic Installation</h2>
        <pre>
# Create nodes
nodes = ns.NodeContainer()
nodes.Create(4)

# Install internet stack on all nodes
stack = ns.InternetStackHelper()
stack.Install(nodes)
        </pre>
        
        <h2>Example: Exclude Switch Nodes</h2>
        <pre>
# Create node containers
hosts = ns.NodeContainer()
hosts.Create(3)

switches = ns.NodeContainer()
switches.Create(1)

# Only install stack on hosts (not switches)
stack = ns.InternetStackHelper()
stack.Install(hosts)

# Switches use BridgeHelper instead
bridge = ns.BridgeHelper()
        </pre>
        
        <h2>Example: Custom TCP</h2>
        <pre>
# Use CUBIC TCP with custom settings
stack = ns.InternetStackHelper()
stack.SetTcp('ns3::TcpCubic')
stack.Install(nodes)

# Or set via Config
ns.Config.SetDefault('ns3::TcpL4Protocol::SocketType',
    ns.StringValue('ns3::TcpCubic'))
        </pre>
        
        <h2>Example: With Routing Protocol</h2>
        <pre>
# Use OLSR for ad-hoc network
olsr = ns.OlsrHelper()
stack = ns.InternetStackHelper()
stack.SetRoutingHelper(olsr)
stack.Install(nodes)
        </pre>
        """
        return self._create_scroll_content(content)
    
    def _create_addressing_tab(self) -> QWidget:
        """Create the IP Addresses tab content."""
        content = """
        <h1>Step 4: Assign IP Addresses</h1>
        
        <p>After installing the internet stack, you need to assign IP addresses to 
        network interfaces. Each link typically gets its own subnet.</p>
        
        <div class="tip">
            <strong>GUI Tip:</strong> Select a port in the Property Panel to configure 
            its IP address and netmask. Leave blank for auto-assignment.
        </div>
        
        <h2>Ipv4AddressHelper</h2>
        
        <table>
            <tr><th>Method</th><th>Description</th><th>Example</th></tr>
            <tr>
                <td><code>Ipv4AddressHelper()</code></td>
                <td>Constructor</td>
                <td><code>ipv4 = ns.Ipv4AddressHelper()</code></td>
            </tr>
            <tr>
                <td><code>.SetBase(network, mask)</code></td>
                <td>Set network and mask</td>
                <td><code>ipv4.SetBase(ns.Ipv4Address('10.1.1.0'), ns.Ipv4Mask('255.255.255.0'))</code></td>
            </tr>
            <tr>
                <td><code>.SetBase(network, mask, base)</code></td>
                <td>Set with starting address</td>
                <td><code>ipv4.SetBase(addr, mask, ns.Ipv4Address('0.0.0.10'))</code></td>
            </tr>
            <tr>
                <td><code>.Assign(devices)</code></td>
                <td>Assign IPs to devices</td>
                <td><code>interfaces = ipv4.Assign(devices)</code></td>
            </tr>
            <tr>
                <td><code>.NewNetwork()</code></td>
                <td>Increment to next network</td>
                <td><code>ipv4.NewNetwork()</code></td>
            </tr>
        </table>
        
        <h2>Ipv4InterfaceContainer</h2>
        <p>Returned by Assign(), holds interface information.</p>
        
        <table>
            <tr><th>Method</th><th>Description</th><th>Example</th></tr>
            <tr>
                <td><code>.GetN()</code></td>
                <td>Get interface count</td>
                <td><code>n = interfaces.GetN()</code></td>
            </tr>
            <tr>
                <td><code>.GetAddress(i)</code></td>
                <td>Get IP address at index</td>
                <td><code>addr = interfaces.GetAddress(0)</code></td>
            </tr>
            <tr>
                <td><code>.GetAddress(i, j)</code></td>
                <td>Get jth address on ith interface</td>
                <td><code>addr = interfaces.GetAddress(0, 0)</code></td>
            </tr>
            <tr>
                <td><code>.Add(container)</code></td>
                <td>Merge containers</td>
                <td><code>interfaces.Add(other)</code></td>
            </tr>
        </table>
        
        <h2>Ipv4Address</h2>
        
        <table>
            <tr><th>Method</th><th>Description</th><th>Example</th></tr>
            <tr>
                <td><code>Ipv4Address(string)</code></td>
                <td>Create from string</td>
                <td><code>addr = ns.Ipv4Address('10.1.1.1')</code></td>
            </tr>
            <tr>
                <td><code>Ipv4Address.GetAny()</code></td>
                <td>Get 0.0.0.0 (any address)</td>
                <td><code>any = ns.Ipv4Address.GetAny()</code></td>
            </tr>
            <tr>
                <td><code>Ipv4Address.GetBroadcast()</code></td>
                <td>Get 255.255.255.255</td>
                <td><code>bcast = ns.Ipv4Address.GetBroadcast()</code></td>
            </tr>
            <tr>
                <td><code>Ipv4Address.GetLoopback()</code></td>
                <td>Get 127.0.0.1</td>
                <td><code>lo = ns.Ipv4Address.GetLoopback()</code></td>
            </tr>
        </table>
        
        <h2>Ipv4Mask</h2>
        
        <table>
            <tr><th>Method</th><th>Description</th><th>Example</th></tr>
            <tr>
                <td><code>Ipv4Mask(string)</code></td>
                <td>Create from dotted notation</td>
                <td><code>mask = ns.Ipv4Mask('255.255.255.0')</code></td>
            </tr>
            <tr>
                <td><code>Ipv4Mask(prefix)</code></td>
                <td>Create from prefix length</td>
                <td><code>mask = ns.Ipv4Mask('/24')</code></td>
            </tr>
        </table>
        
        <h2>Common Subnet Masks</h2>
        <table>
            <tr><th>CIDR</th><th>Mask</th><th>Hosts</th></tr>
            <tr><td>/8</td><td>255.0.0.0</td><td>16,777,214</td></tr>
            <tr><td>/16</td><td>255.255.0.0</td><td>65,534</td></tr>
            <tr><td>/24</td><td>255.255.255.0</td><td>254</td></tr>
            <tr><td>/30</td><td>255.255.255.252</td><td>2 (point-to-point)</td></tr>
        </table>
        
        <h2>Example: Multiple Subnets</h2>
        <pre>
ipv4 = ns.Ipv4AddressHelper()

# Link 1: 10.1.1.0/24
ipv4.SetBase(ns.Ipv4Address('10.1.1.0'), 
             ns.Ipv4Mask('255.255.255.0'))
interfaces1 = ipv4.Assign(devices1)

# Link 2: 10.1.2.0/24
ipv4.SetBase(ns.Ipv4Address('10.1.2.0'), 
             ns.Ipv4Mask('255.255.255.0'))
interfaces2 = ipv4.Assign(devices2)

# Print addresses
print(f"Node 0: {interfaces1.GetAddress(0)}")
print(f"Node 1: {interfaces1.GetAddress(1)}")
        </pre>
        
        <h2>Example: Custom Starting Address</h2>
        <pre>
# Start from .10 instead of .1
ipv4.SetBase(
    ns.Ipv4Address('10.1.1.0'),
    ns.Ipv4Mask('255.255.255.0'),
    ns.Ipv4Address('0.0.0.10')  # Start at .10
)
interfaces = ipv4.Assign(devices)
# First device gets 10.1.1.10, second gets 10.1.1.11, etc.
        </pre>
        
        <h2>IPv6 Support</h2>
        <pre>
ipv6 = ns.Ipv6AddressHelper()
ipv6.SetBase(ns.Ipv6Address('2001:db8::'), 
             ns.Ipv6Prefix(64))
interfaces = ipv6.Assign(devices)
        </pre>
        """
        return self._create_scroll_content(content)
    
    def _create_routing_tab(self) -> QWidget:
        """Create the Routing tab content."""
        content = """
        <h1>Step 5: Setup Routing</h1>
        
        <p>Routing determines how packets find their way through the network. ns-3 
        provides automatic global routing as well as various routing protocols.</p>
        
        <div class="tip">
            <strong>GUI Tip:</strong> By default, the GUI uses Global Routing which 
            automatically computes shortest paths. For manual routes, edit the routing 
            table in the Property Panel.
        </div>
        
        <h2>Global Routing (Most Common)</h2>
        <p>Computes shortest paths across the entire topology using Dijkstra's algorithm. 
        Best for static topologies where you just want things to work.</p>
        
        <table>
            <tr><th>Method</th><th>Description</th><th>Example</th></tr>
            <tr>
                <td><code>.PopulateRoutingTables()</code></td>
                <td>Compute all routes (call once at start)</td>
                <td><code>ns.Ipv4GlobalRoutingHelper.PopulateRoutingTables()</code></td>
            </tr>
            <tr>
                <td><code>.RecomputeRoutingTables()</code></td>
                <td>Recompute routes (after topology change)</td>
                <td><code>ns.Ipv4GlobalRoutingHelper.RecomputeRoutingTables()</code></td>
            </tr>
        </table>
        
        <div class="warning">
            <strong>Important:</strong> Call PopulateRoutingTables() AFTER assigning 
            all IP addresses, otherwise routes won't be complete.
        </div>
        
        <h2>Static Routing</h2>
        <p>Manually configure routes for specific paths.</p>
        
        <table>
            <tr><th>Method</th><th>Description</th></tr>
            <tr>
                <td><code>Ipv4StaticRoutingHelper()</code></td>
                <td>Constructor</td>
            </tr>
            <tr>
                <td><code>.GetStaticRouting(ipv4)</code></td>
                <td>Get routing table for node</td>
            </tr>
        </table>
        
        <h3>Ipv4StaticRouting Methods</h3>
        <table>
            <tr><th>Method</th><th>Description</th></tr>
            <tr>
                <td><code>.AddNetworkRouteTo(dest, mask, nextHop, interface)</code></td>
                <td>Add route via next hop</td>
            </tr>
            <tr>
                <td><code>.AddNetworkRouteTo(dest, mask, interface)</code></td>
                <td>Add direct route</td>
            </tr>
            <tr>
                <td><code>.AddHostRouteTo(dest, nextHop, interface)</code></td>
                <td>Add host-specific route</td>
            </tr>
            <tr>
                <td><code>.SetDefaultRoute(nextHop, interface)</code></td>
                <td>Set default gateway</td>
            </tr>
            <tr>
                <td><code>.GetNRoutes()</code></td>
                <td>Get route count</td>
            </tr>
            <tr>
                <td><code>.GetRoute(i)</code></td>
                <td>Get route at index</td>
            </tr>
            <tr>
                <td><code>.RemoveRoute(i)</code></td>
                <td>Remove route at index</td>
            </tr>
        </table>
        
        <h2>Dynamic Routing Protocols</h2>
        <p>For mobile/ad-hoc networks or when you want realistic protocol behavior.</p>
        
        <table>
            <tr><th>Protocol</th><th>Helper</th><th>Type</th><th>Use Case</th></tr>
            <tr>
                <td>OLSR</td>
                <td><code>OlsrHelper()</code></td>
                <td>Proactive</td>
                <td>Ad-hoc networks, maintains routes continuously</td>
            </tr>
            <tr>
                <td>AODV</td>
                <td><code>AodvHelper()</code></td>
                <td>Reactive</td>
                <td>Ad-hoc, discovers routes on-demand</td>
            </tr>
            <tr>
                <td>DSDV</td>
                <td><code>DsdvHelper()</code></td>
                <td>Proactive</td>
                <td>Ad-hoc, distance-vector based</td>
            </tr>
            <tr>
                <td>RIP</td>
                <td><code>RipHelper()</code></td>
                <td>Distance Vector</td>
                <td>Traditional networks</td>
            </tr>
        </table>
        
        <h2>Combining Routing Protocols</h2>
        <pre>
# Use multiple routing protocols with priorities
list = ns.Ipv4ListRoutingHelper()
list.Add(staticRouting, 0)   # Highest priority
list.Add(olsr, 10)           # Lower priority

stack = ns.InternetStackHelper()
stack.SetRoutingHelper(list)
stack.Install(nodes)
        </pre>
        
        <h2>Example: Global Routing</h2>
        <pre>
# After setting up topology and addresses...
ns.Ipv4GlobalRoutingHelper.PopulateRoutingTables()
print('Routing tables computed')
        </pre>
        
        <h2>Example: Static Routes</h2>
        <pre>
staticRouting = ns.Ipv4StaticRoutingHelper()

# Get node's IPv4 object
ipv4 = nodes.Get(0).GetObject(ns.Ipv4.GetTypeId())
routing = staticRouting.GetStaticRouting(ipv4)

# Add route to 10.2.0.0/24 via gateway 10.1.1.2
routing.AddNetworkRouteTo(
    ns.Ipv4Address('10.2.0.0'),
    ns.Ipv4Mask('255.255.255.0'),
    ns.Ipv4Address('10.1.1.2'),
    1  # interface index
)

# Set default gateway
routing.SetDefaultRoute(
    ns.Ipv4Address('10.1.1.1'),
    1  # interface index
)
        </pre>
        
        <h2>Example: OLSR for Ad-hoc</h2>
        <pre>
# Setup OLSR routing
olsr = ns.OlsrHelper()

stack = ns.InternetStackHelper()
stack.SetRoutingHelper(olsr)
stack.Install(nodes)

# OLSR will automatically exchange routes
# No need to call PopulateRoutingTables()
        </pre>
        """
        return self._create_scroll_content(content)
    
    def _create_applications_tab(self) -> QWidget:
        """Create the Applications tab content."""
        content = """
        <h1>Step 6: Create Applications</h1>
        
        <p>Applications generate and consume network traffic. ns-3 provides several 
        built-in traffic generators for different use cases.</p>
        
        <div class="tip">
            <strong>GUI Tip:</strong> Configure traffic flows in the Simulation Config 
            dialog. Choose from Echo, OnOff, or BulkSend application types.
        </div>
        
        <h2>ApplicationContainer</h2>
        <p>Returned by Install() methods, used to control application timing.</p>
        
        <table>
            <tr><th>Method</th><th>Description</th><th>Example</th></tr>
            <tr>
                <td><code>.Start(time)</code></td>
                <td>Set application start time</td>
                <td><code>apps.Start(ns.Seconds(1.0))</code></td>
            </tr>
            <tr>
                <td><code>.Stop(time)</code></td>
                <td>Set application stop time</td>
                <td><code>apps.Stop(ns.Seconds(9.0))</code></td>
            </tr>
            <tr>
                <td><code>.Get(i)</code></td>
                <td>Get application at index</td>
                <td><code>app = apps.Get(0)</code></td>
            </tr>
            <tr>
                <td><code>.GetN()</code></td>
                <td>Get application count</td>
                <td><code>n = apps.GetN()</code></td>
            </tr>
        </table>
        
        <h2>UDP Echo (Request/Response)</h2>
        <p>Client sends packets, server echoes them back. Good for latency testing.</p>
        
        <h3>UdpEchoServerHelper</h3>
        <table>
            <tr><th>Method</th><th>Description</th></tr>
            <tr><td><code>UdpEchoServerHelper(port)</code></td><td>Constructor with port</td></tr>
            <tr><td><code>.Install(node)</code></td><td>Install on node</td></tr>
            <tr><td><code>.SetAttribute(name, value)</code></td><td>Set attribute</td></tr>
        </table>
        
        <h3>UdpEchoClientHelper</h3>
        <table>
            <tr><th>Method</th><th>Description</th></tr>
            <tr><td><code>UdpEchoClientHelper(address, port)</code></td><td>Constructor</td></tr>
            <tr><td><code>.Install(node)</code></td><td>Install on node</td></tr>
            <tr><td><code>.SetAttribute(name, value)</code></td><td>Set attribute</td></tr>
        </table>
        
        <h3>Echo Client Attributes</h3>
        <table>
            <tr><th>Attribute</th><th>Type</th><th>Description</th></tr>
            <tr><td>MaxPackets</td><td>UintegerValue</td><td>Number of packets to send (0 = unlimited)</td></tr>
            <tr><td>Interval</td><td>TimeValue</td><td>Time between packets</td></tr>
            <tr><td>PacketSize</td><td>UintegerValue</td><td>Size in bytes</td></tr>
        </table>
        
        <pre>
# UDP Echo Example
server = ns.UdpEchoServerHelper(9000)
serverApps = server.Install(nodes.Get(1))
serverApps.Start(ns.Seconds(1.0))
serverApps.Stop(ns.Seconds(10.0))

client = ns.UdpEchoClientHelper(interfaces.GetAddress(1), 9000)
client.SetAttribute('MaxPackets', ns.UintegerValue(10))
client.SetAttribute('Interval', ns.TimeValue(ns.Seconds(1.0)))
client.SetAttribute('PacketSize', ns.UintegerValue(1024))
clientApps = client.Install(nodes.Get(0))
clientApps.Start(ns.Seconds(2.0))
clientApps.Stop(ns.Seconds(10.0))
        </pre>
        
        <h2>OnOff (Constant Bitrate)</h2>
        <p>Generates traffic at a constant rate with configurable on/off periods. 
        Use with PacketSink receiver.</p>
        
        <h3>OnOffHelper</h3>
        <table>
            <tr><th>Method</th><th>Description</th></tr>
            <tr><td><code>OnOffHelper(protocol, address)</code></td><td>Constructor</td></tr>
            <tr><td><code>.Install(node)</code></td><td>Install on node</td></tr>
            <tr><td><code>.SetAttribute(name, value)</code></td><td>Set attribute</td></tr>
            <tr><td><code>.SetConstantRate(rate)</code></td><td>Helper for constant rate</td></tr>
        </table>
        
        <h3>OnOff Attributes</h3>
        <table>
            <tr><th>Attribute</th><th>Type</th><th>Description</th></tr>
            <tr><td>DataRate</td><td>DataRateValue/StringValue</td><td>Send rate ("1Mbps")</td></tr>
            <tr><td>PacketSize</td><td>UintegerValue</td><td>Packet size in bytes</td></tr>
            <tr><td>OnTime</td><td>StringValue</td><td>ON period distribution</td></tr>
            <tr><td>OffTime</td><td>StringValue</td><td>OFF period distribution</td></tr>
            <tr><td>MaxBytes</td><td>UintegerValue</td><td>Maximum bytes (0 = unlimited)</td></tr>
        </table>
        
        <pre>
# OnOff Example - Constant 1 Mbps stream
remoteAddr = ns.InetSocketAddress(destIP, 9000)

# Receiver (PacketSink)
sinkAddr = ns.InetSocketAddress(ns.Ipv4Address.GetAny(), 9000)
sink = ns.PacketSinkHelper('ns3::UdpSocketFactory', sinkAddr.ConvertTo())
sinkApps = sink.Install(nodes.Get(1))
sinkApps.Start(ns.Seconds(0.5))

# Sender (OnOff)
onoff = ns.OnOffHelper('ns3::UdpSocketFactory', remoteAddr.ConvertTo())
onoff.SetAttribute('DataRate', ns.StringValue('1Mbps'))
onoff.SetAttribute('PacketSize', ns.UintegerValue(1024))
# Always on (no off periods)
onoff.SetAttribute('OnTime', ns.StringValue('ns3::ConstantRandomVariable[Constant=1]'))
onoff.SetAttribute('OffTime', ns.StringValue('ns3::ConstantRandomVariable[Constant=0]'))
onoffApps = onoff.Install(nodes.Get(0))
onoffApps.Start(ns.Seconds(1.0))
onoffApps.Stop(ns.Seconds(9.0))
        </pre>
        
        <h2>Bulk Send (TCP Max Throughput)</h2>
        <p>Sends as fast as TCP allows. Good for measuring maximum throughput.</p>
        
        <h3>BulkSendHelper</h3>
        <table>
            <tr><th>Attribute</th><th>Type</th><th>Description</th></tr>
            <tr><td>MaxBytes</td><td>UintegerValue</td><td>Bytes to send (0 = unlimited)</td></tr>
            <tr><td>SendSize</td><td>UintegerValue</td><td>Size per send call (default 512)</td></tr>
        </table>
        
        <pre>
# Bulk Send Example - TCP throughput test
remoteAddr = ns.InetSocketAddress(destIP, 9000)

# Receiver
sinkAddr = ns.InetSocketAddress(ns.Ipv4Address.GetAny(), 9000)
sink = ns.PacketSinkHelper('ns3::TcpSocketFactory', sinkAddr.ConvertTo())
sinkApps = sink.Install(nodes.Get(1))
sinkApps.Start(ns.Seconds(0.0))

# Sender
bulk = ns.BulkSendHelper('ns3::TcpSocketFactory', remoteAddr.ConvertTo())
bulk.SetAttribute('MaxBytes', ns.UintegerValue(0))  # Unlimited
bulkApps = bulk.Install(nodes.Get(0))
bulkApps.Start(ns.Seconds(1.0))
bulkApps.Stop(ns.Seconds(9.0))
        </pre>
        
        <h2>PacketSink (Receiver)</h2>
        <p>Receives and consumes traffic. Pair with OnOff or BulkSend.</p>
        
        <pre>
# Listen on any address, specific port
localAddr = ns.InetSocketAddress(ns.Ipv4Address.GetAny(), 9000)
sink = ns.PacketSinkHelper('ns3::UdpSocketFactory', localAddr.ConvertTo())
sinkApps = sink.Install(node)
        </pre>
        
        <h2>Socket Factories</h2>
        <table>
            <tr><th>Protocol String</th><th>Description</th></tr>
            <tr><td><code>'ns3::UdpSocketFactory'</code></td><td>UDP socket</td></tr>
            <tr><td><code>'ns3::TcpSocketFactory'</code></td><td>TCP socket</td></tr>
        </table>
        
        <h2>InetSocketAddress</h2>
        <table>
            <tr><th>Method</th><th>Description</th></tr>
            <tr><td><code>InetSocketAddress(address, port)</code></td><td>Create with IP and port</td></tr>
            <tr><td><code>InetSocketAddress(port)</code></td><td>Any address + port</td></tr>
            <tr><td><code>.ConvertTo()</code></td><td>Convert to Address type</td></tr>
        </table>
        """
        return self._create_scroll_content(content)
    
    def _create_tracing_tab(self) -> QWidget:
        """Create the Tracing tab content."""
        content = """
        <h1>Step 7: Enable Tracing</h1>
        
        <p>Tracing captures simulation data for analysis. ns-3 provides multiple 
        tracing options from packet-level details to aggregate statistics.</p>
        
        <div class="note">
            <strong>GUI Note:</strong> Enable tracing options in the Simulation Config 
            dialog. Results are displayed in the Stats Panel after simulation.
        </div>
        
        <h2>Flow Monitor (Recommended)</h2>
        <p>Collects per-flow statistics including throughput, delay, jitter, and loss.</p>
        
        <h3>FlowMonitorHelper</h3>
        <table>
            <tr><th>Method</th><th>Description</th><th>Example</th></tr>
            <tr>
                <td><code>FlowMonitorHelper()</code></td>
                <td>Constructor</td>
                <td><code>flowHelper = ns.FlowMonitorHelper()</code></td>
            </tr>
            <tr>
                <td><code>.InstallAll()</code></td>
                <td>Install on all nodes</td>
                <td><code>monitor = flowHelper.InstallAll()</code></td>
            </tr>
            <tr>
                <td><code>.Install(nodes)</code></td>
                <td>Install on specific nodes</td>
                <td><code>monitor = flowHelper.Install(nodes)</code></td>
            </tr>
            <tr>
                <td><code>.GetMonitor()</code></td>
                <td>Get FlowMonitor object</td>
                <td><code>monitor = flowHelper.GetMonitor()</code></td>
            </tr>
            <tr>
                <td><code>.GetClassifier()</code></td>
                <td>Get flow classifier</td>
                <td><code>classifier = flowHelper.GetClassifier()</code></td>
            </tr>
        </table>
        
        <h3>FlowMonitor</h3>
        <table>
            <tr><th>Method</th><th>Description</th></tr>
            <tr><td><code>.CheckForLostPackets()</code></td><td>Finalize lost packet detection</td></tr>
            <tr><td><code>.GetFlowStats()</code></td><td>Get all flow statistics</td></tr>
            <tr><td><code>.SerializeToXmlFile(filename, hist, probes)</code></td><td>Save to XML</td></tr>
        </table>
        
        <h3>FlowStats Fields</h3>
        <table>
            <tr><th>Field</th><th>Description</th></tr>
            <tr><td><code>txPackets</code></td><td>Transmitted packets</td></tr>
            <tr><td><code>txBytes</code></td><td>Transmitted bytes</td></tr>
            <tr><td><code>rxPackets</code></td><td>Received packets</td></tr>
            <tr><td><code>rxBytes</code></td><td>Received bytes</td></tr>
            <tr><td><code>delaySum</code></td><td>Total delay (Time object)</td></tr>
            <tr><td><code>jitterSum</code></td><td>Total jitter (Time object)</td></tr>
            <tr><td><code>lostPackets</code></td><td>Lost packet count</td></tr>
            <tr><td><code>timeFirstTxPacket</code></td><td>First TX timestamp</td></tr>
            <tr><td><code>timeLastRxPacket</code></td><td>Last RX timestamp</td></tr>
        </table>
        
        <h3>Flow Classifier (5-Tuple)</h3>
        <table>
            <tr><th>Field</th><th>Description</th></tr>
            <tr><td><code>sourceAddress</code></td><td>Source IP</td></tr>
            <tr><td><code>destinationAddress</code></td><td>Destination IP</td></tr>
            <tr><td><code>sourcePort</code></td><td>Source port</td></tr>
            <tr><td><code>destinationPort</code></td><td>Destination port</td></tr>
            <tr><td><code>protocol</code></td><td>Protocol (6=TCP, 17=UDP)</td></tr>
        </table>
        
        <pre>
# Flow Monitor Example
flowHelper = ns.FlowMonitorHelper()
flowMonitor = flowHelper.InstallAll()

# After simulation...
ns.Simulator.Run()

flowMonitor.CheckForLostPackets()
classifier = flowHelper.GetClassifier()
stats = flowMonitor.GetFlowStats()

for flowId, flowStats in stats:
    t = classifier.FindFlow(flowId)
    proto = 'UDP' if t.protocol == 17 else 'TCP'
    
    print(f'Flow {flowId} ({proto})')
    print(f'  {t.sourceAddress}:{t.sourcePort} -> {t.destinationAddress}:{t.destinationPort}')
    print(f'  TX: {flowStats.txPackets} packets, {flowStats.txBytes} bytes')
    print(f'  RX: {flowStats.rxPackets} packets, {flowStats.rxBytes} bytes')
    
    if flowStats.rxPackets > 0:
        duration = flowStats.timeLastRxPacket.GetSeconds() - flowStats.timeFirstTxPacket.GetSeconds()
        throughput = (flowStats.rxBytes * 8) / duration / 1e6
        delay = flowStats.delaySum.GetSeconds() / flowStats.rxPackets * 1000
        print(f'  Throughput: {throughput:.2f} Mbps')
        print(f'  Mean Delay: {delay:.2f} ms')

# Save to XML
flowMonitor.SerializeToXmlFile('flowmon.xml', True, True)
        </pre>
        
        <h2>ASCII Tracing</h2>
        <p>Human-readable text log of all packet events.</p>
        
        <pre>
ascii = ns.AsciiTraceHelper()

# Enable on P2P links
p2p.EnableAsciiAll(ascii.CreateFileStream('p2p-trace.tr'))

# Enable on CSMA links
csma.EnableAsciiAll(ascii.CreateFileStream('csma-trace.tr'))

# Enable on WiFi
phy.EnableAsciiAll(ascii.CreateFileStream('wifi-trace.tr'))
        </pre>
        
        <h2>PCAP Tracing</h2>
        <p>Packet capture files viewable in Wireshark.</p>
        
        <pre>
# Enable PCAP on all P2P devices
p2p.EnablePcapAll('p2p')
# Creates: p2p-0-0.pcap, p2p-0-1.pcap, etc.

# Enable PCAP on specific device
p2p.EnablePcap('trace', devices.Get(0), True)  # promiscuous

# Enable on WiFi
phy.EnablePcapAll('wifi')
        </pre>
        
        <h2>Animation (NetAnim)</h2>
        <p>Generate XML for NetAnim visualization tool.</p>
        
        <pre>
anim = ns.AnimationInterface('animation.xml')

# Set node positions
anim.SetConstantPosition(nodes.Get(0), 10.0, 20.0)
anim.SetConstantPosition(nodes.Get(1), 50.0, 20.0)

# Include packet metadata
anim.EnablePacketMetadata(True)

# Track routing changes
anim.EnableIpv4RouteTracking('routes.xml', 
    ns.Seconds(0), ns.Seconds(10), ns.Seconds(1))
        </pre>
        """
        return self._create_scroll_content(content)
    
    def _create_simulation_tab(self) -> QWidget:
        """Create the Simulation tab content."""
        content = """
        <h1>Step 8: Run Simulation</h1>
        
        <p>The final step is running the simulation and collecting results. ns-3 uses 
        a discrete-event simulator that processes events in time order.</p>
        
        <h2>Simulator Control</h2>
        
        <table>
            <tr><th>Method</th><th>Description</th><th>Example</th></tr>
            <tr>
                <td><code>.Run()</code></td>
                <td>Run until no events or Stop time</td>
                <td><code>ns.Simulator.Run()</code></td>
            </tr>
            <tr>
                <td><code>.Stop(time)</code></td>
                <td>Set simulation end time</td>
                <td><code>ns.Simulator.Stop(ns.Seconds(10.0))</code></td>
            </tr>
            <tr>
                <td><code>.Destroy()</code></td>
                <td>Clean up simulator (call at end)</td>
                <td><code>ns.Simulator.Destroy()</code></td>
            </tr>
            <tr>
                <td><code>.Now()</code></td>
                <td>Get current simulation time</td>
                <td><code>now = ns.Simulator.Now()</code></td>
            </tr>
            <tr>
                <td><code>.Schedule(time, callback)</code></td>
                <td>Schedule event at future time</td>
                <td><code>ns.Simulator.Schedule(ns.Seconds(5), myFunc)</code></td>
            </tr>
            <tr>
                <td><code>.ScheduleNow(callback)</code></td>
                <td>Schedule event immediately</td>
                <td><code>ns.Simulator.ScheduleNow(myFunc)</code></td>
            </tr>
            <tr>
                <td><code>.IsFinished()</code></td>
                <td>Check if simulation complete</td>
                <td><code>done = ns.Simulator.IsFinished()</code></td>
            </tr>
        </table>
        
        <h2>Time Values</h2>
        
        <h3>Creating Time</h3>
        <table>
            <tr><th>Function</th><th>Description</th><th>Example</th></tr>
            <tr><td><code>Seconds(val)</code></td><td>Create from seconds</td><td><code>t = ns.Seconds(1.5)</code></td></tr>
            <tr><td><code>MilliSeconds(val)</code></td><td>Create from milliseconds</td><td><code>t = ns.MilliSeconds(100)</code></td></tr>
            <tr><td><code>MicroSeconds(val)</code></td><td>Create from microseconds</td><td><code>t = ns.MicroSeconds(500)</code></td></tr>
            <tr><td><code>NanoSeconds(val)</code></td><td>Create from nanoseconds</td><td><code>t = ns.NanoSeconds(1000)</code></td></tr>
            <tr><td><code>Time(string)</code></td><td>Create from string</td><td><code>t = ns.Time('1.5s')</code></td></tr>
        </table>
        
        <h3>Reading Time</h3>
        <table>
            <tr><th>Method</th><th>Description</th><th>Example</th></tr>
            <tr><td><code>.GetSeconds()</code></td><td>Get as seconds (float)</td><td><code>secs = t.GetSeconds()</code></td></tr>
            <tr><td><code>.GetMilliSeconds()</code></td><td>Get as milliseconds</td><td><code>ms = t.GetMilliSeconds()</code></td></tr>
            <tr><td><code>.GetMicroSeconds()</code></td><td>Get as microseconds</td><td><code>us = t.GetMicroSeconds()</code></td></tr>
            <tr><td><code>.GetNanoSeconds()</code></td><td>Get as nanoseconds</td><td><code>ns_val = t.GetNanoSeconds()</code></td></tr>
        </table>
        
        <h2>Attribute Values</h2>
        <p>Used with SetAttribute() and Config::SetDefault().</p>
        
        <table>
            <tr><th>Type</th><th>Constructor</th><th>Example</th></tr>
            <tr><td>StringValue</td><td><code>StringValue(string)</code></td><td><code>ns.StringValue('100Mbps')</code></td></tr>
            <tr><td>UintegerValue</td><td><code>UintegerValue(uint)</code></td><td><code>ns.UintegerValue(1024)</code></td></tr>
            <tr><td>IntegerValue</td><td><code>IntegerValue(int)</code></td><td><code>ns.IntegerValue(-1)</code></td></tr>
            <tr><td>DoubleValue</td><td><code>DoubleValue(double)</code></td><td><code>ns.DoubleValue(3.14)</code></td></tr>
            <tr><td>BooleanValue</td><td><code>BooleanValue(bool)</code></td><td><code>ns.BooleanValue(True)</code></td></tr>
            <tr><td>TimeValue</td><td><code>TimeValue(time)</code></td><td><code>ns.TimeValue(ns.Seconds(1.0))</code></td></tr>
            <tr><td>DataRateValue</td><td><code>DataRateValue(rate)</code></td><td><code>ns.DataRateValue(ns.DataRate('1Mbps'))</code></td></tr>
        </table>
        
        <h2>Random Number Generation</h2>
        <p>Control simulation randomness for reproducibility.</p>
        
        <table>
            <tr><th>Method</th><th>Description</th><th>Example</th></tr>
            <tr>
                <td><code>RngSeedManager.SetSeed(seed)</code></td>
                <td>Set global seed</td>
                <td><code>ns.RngSeedManager.SetSeed(12345)</code></td>
            </tr>
            <tr>
                <td><code>RngSeedManager.SetRun(run)</code></td>
                <td>Set run number</td>
                <td><code>ns.RngSeedManager.SetRun(1)</code></td>
            </tr>
        </table>
        
        <h2>Logging</h2>
        <p>Enable component logging for debugging.</p>
        
        <pre>
# Enable logging for specific component
ns.LogComponentEnable('UdpEchoClientApplication', ns.LOG_LEVEL_INFO)
ns.LogComponentEnable('UdpEchoServerApplication', ns.LOG_LEVEL_INFO)

# Log levels (from least to most verbose):
# LOG_LEVEL_ERROR  - Errors only
# LOG_LEVEL_WARN   - Warnings + errors
# LOG_LEVEL_INFO   - Info + above
# LOG_LEVEL_DEBUG  - Debug + above
# LOG_LEVEL_ALL    - Everything
        </pre>
        
        <h2>Complete Simulation Pattern</h2>
        <pre>
# Set random seed for reproducibility
ns.RngSeedManager.SetSeed(12345)

# ... (setup nodes, links, stack, IPs, routing, apps) ...

# Enable tracing
flowHelper = ns.FlowMonitorHelper()
flowMonitor = flowHelper.InstallAll()

# Set simulation duration
ns.Simulator.Stop(ns.Seconds(10.0))

# Run simulation
print('Starting simulation...')
ns.Simulator.Run()
print('Simulation complete.')

# Collect statistics
flowMonitor.CheckForLostPackets()
stats = flowMonitor.GetFlowStats()
# ... process stats ...

# Save results
flowMonitor.SerializeToXmlFile('results.xml', True, True)

# Clean up
ns.Simulator.Destroy()
        </pre>
        
        <h2>Calculating Metrics</h2>
        <pre>
for flowId, flowStats in stats:
    # Throughput (Mbps)
    duration = (flowStats.timeLastRxPacket.GetSeconds() - 
                flowStats.timeFirstTxPacket.GetSeconds())
    if duration > 0:
        throughput = (flowStats.rxBytes * 8) / duration / 1e6
    
    # Mean Delay (ms)
    if flowStats.rxPackets > 0:
        delay = flowStats.delaySum.GetSeconds() / flowStats.rxPackets * 1000
    
    # Mean Jitter (ms)
    if flowStats.rxPackets > 1:
        jitter = flowStats.jitterSum.GetSeconds() / (flowStats.rxPackets - 1) * 1000
    
    # Packet Loss (%)
    lost = flowStats.txPackets - flowStats.rxPackets
    if flowStats.txPackets > 0:
        loss_pct = (lost / flowStats.txPackets) * 100
        </pre>
        """
        return self._create_scroll_content(content)


def show_help_dialog(parent=None):
    """Show the help dialog."""
    dialog = HelpDialog(parent)
    dialog.exec()
