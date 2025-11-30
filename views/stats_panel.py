"""
Statistics panel for displaying simulation metrics.

Shows packet counts, throughput, and other statistics.
Includes tabs for summary, per-flow details, and console output.
"""

from typing import Optional, List
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QColor
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QFrame, QGridLayout, QProgressBar, QSizePolicy,
    QTabWidget, QTableWidget, QTableWidgetItem, QHeaderView,
    QTextEdit, QScrollArea, QPushButton, QTreeWidget, QTreeWidgetItem
)

from models import (
    SimulationStats, SimulationState, SimulationStatus, 
    SimulationResults, FlowStats
)


class StatCard(QFrame):
    """A card displaying a single statistic."""
    
    def __init__(self, title: str, value: str = "0", unit: str = "", parent=None):
        super().__init__(parent)
        self._title = title
        self._value = value
        self._unit = unit
        self._setup_ui()
    
    def _setup_ui(self):
        self.setStyleSheet("""
            QFrame {
                background: white;
                border: 1px solid #E5E7EB;
                border-radius: 8px;
                padding: 12px;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(4)
        
        # Title
        title_label = QLabel(self._title)
        title_label.setStyleSheet("color: #6B7280; font-size: 11px;")
        layout.addWidget(title_label)
        
        # Value row
        value_layout = QHBoxLayout()
        value_layout.setSpacing(4)
        
        self._value_label = QLabel(self._value)
        self._value_label.setStyleSheet("""
            color: #111827;
            font-size: 24px;
            font-weight: 600;
        """)
        value_layout.addWidget(self._value_label)
        
        if self._unit:
            self._unit_label = QLabel(self._unit)
            self._unit_label.setStyleSheet("color: #9CA3AF; font-size: 12px;")
            self._unit_label.setAlignment(Qt.AlignmentFlag.AlignBottom)
            value_layout.addWidget(self._unit_label)
        
        value_layout.addStretch()
        layout.addLayout(value_layout)
    
    def set_value(self, value: str):
        """Update the displayed value."""
        self._value_label.setText(value)


class SummaryTab(QWidget):
    """Summary statistics tab."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 12, 0, 0)
        layout.setSpacing(12)
        
        # Stats grid
        grid = QGridLayout()
        grid.setSpacing(10)
        
        self._sent_card = StatCard("Packets Sent", "0")
        grid.addWidget(self._sent_card, 0, 0)
        
        self._received_card = StatCard("Packets Received", "0")
        grid.addWidget(self._received_card, 0, 1)
        
        self._dropped_card = StatCard("Packets Dropped", "0")
        grid.addWidget(self._dropped_card, 1, 0)
        
        self._loss_card = StatCard("Packet Loss", "0", "%")
        grid.addWidget(self._loss_card, 1, 1)
        
        self._throughput_card = StatCard("Avg Throughput", "0", "Mbps")
        grid.addWidget(self._throughput_card, 2, 0)
        
        self._latency_card = StatCard("Avg Latency", "0", "ms")
        grid.addWidget(self._latency_card, 2, 1)
        
        layout.addLayout(grid)
        layout.addStretch()
    
    def update_stats(self, stats: SimulationStats):
        """Update all statistics displays."""
        self._sent_card.set_value(str(stats.packets_sent))
        self._received_card.set_value(str(stats.packets_received))
        self._dropped_card.set_value(str(stats.packets_dropped))
        self._loss_card.set_value(f"{stats.packet_loss_rate * 100:.1f}")
        self._throughput_card.set_value(f"{stats.throughput_bps / 1e6:.2f}")
        self._latency_card.set_value(f"{stats.avg_latency_ms:.2f}")
    
    def reset(self):
        """Reset to initial state."""
        self.update_stats(SimulationStats())


class FlowsTab(QWidget):
    """Per-flow statistics tab."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 12, 0, 0)
        layout.setSpacing(8)
        
        # Table for flow statistics
        self._table = QTableWidget()
        self._table.setColumnCount(9)
        self._table.setHorizontalHeaderLabels([
            "Flow", "Source", "Destination", "Protocol",
            "Tx Pkts", "Rx Pkts", "Lost", "Throughput", "Delay"
        ])
        
        # Style table
        self._table.setStyleSheet("""
            QTableWidget {
                background: white;
                border: 1px solid #E5E7EB;
                border-radius: 6px;
                gridline-color: #F3F4F6;
            }
            QTableWidget::item {
                padding: 8px;
            }
            QHeaderView::section {
                background: #F9FAFB;
                border: none;
                border-bottom: 1px solid #E5E7EB;
                padding: 8px;
                font-weight: 600;
                color: #374151;
            }
        """)
        
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        
        self._table.verticalHeader().setVisible(False)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setAlternatingRowColors(True)
        
        layout.addWidget(self._table)
        
        # Empty state label
        self._empty_label = QLabel("No flow statistics available.\nRun a simulation to see results.")
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setStyleSheet("color: #9CA3AF; font-size: 12px; padding: 40px;")
        layout.addWidget(self._empty_label)
        
        self._table.hide()
    
    def update_flows(self, flow_stats: List[FlowStats]):
        """Update table with flow statistics."""
        if not flow_stats:
            self._table.hide()
            self._empty_label.show()
            return
        
        self._empty_label.hide()
        self._table.show()
        
        self._table.setRowCount(len(flow_stats))
        
        for row, flow in enumerate(flow_stats):
            # Flow ID
            self._table.setItem(row, 0, QTableWidgetItem(str(flow.flow_id)))
            
            # Source
            src = f"{flow.source_address}:{flow.source_port}" if flow.source_port else flow.source_address
            self._table.setItem(row, 1, QTableWidgetItem(src))
            
            # Destination
            dst = f"{flow.destination_address}:{flow.destination_port}" if flow.destination_port else flow.destination_address
            self._table.setItem(row, 2, QTableWidgetItem(dst))
            
            # Protocol
            self._table.setItem(row, 3, QTableWidgetItem(flow.protocol_name))
            
            # Tx Packets
            self._table.setItem(row, 4, QTableWidgetItem(str(flow.tx_packets)))
            
            # Rx Packets
            self._table.setItem(row, 5, QTableWidgetItem(str(flow.rx_packets)))
            
            # Lost
            lost_item = QTableWidgetItem(f"{flow.lost_packets} ({flow.packet_loss_percent:.1f}%)")
            if flow.packet_loss_percent > 5:
                lost_item.setForeground(QColor("#EF4444"))
            self._table.setItem(row, 6, lost_item)
            
            # Throughput
            self._table.setItem(row, 7, QTableWidgetItem(f"{flow.throughput_mbps:.2f} Mbps"))
            
            # Delay
            self._table.setItem(row, 8, QTableWidgetItem(f"{flow.mean_delay_ms:.2f} ms"))
    
    def reset(self):
        """Reset to initial state."""
        self._table.setRowCount(0)
        self._table.hide()
        self._empty_label.show()


class ConsoleTab(QWidget):
    """Console output tab with timestamps and log levels."""
    
    # Log level colors
    LOG_COLORS = {
        'ERROR': '#EF4444',    # Red
        'WARN': '#F59E0B',     # Orange
        'WARNING': '#F59E0B',  # Orange
        'INFO': '#3B82F6',     # Blue
        'DEBUG': '#6B7280',    # Gray
        'SUCCESS': '#10B981',  # Green
        'SIM': '#8B5CF6',      # Purple - simulation output
    }
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        self._start_time = None
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 12, 0, 0)
        layout.setSpacing(8)
        
        # Toolbar
        toolbar_layout = QHBoxLayout()
        toolbar_layout.setSpacing(8)
        
        # Filter buttons
        self._show_errors = QPushButton("Errors")
        self._show_errors.setCheckable(True)
        self._show_errors.setChecked(True)
        self._show_errors.setStyleSheet(self._get_filter_btn_style('#EF4444'))
        toolbar_layout.addWidget(self._show_errors)
        
        self._show_warnings = QPushButton("Warnings")
        self._show_warnings.setCheckable(True)
        self._show_warnings.setChecked(True)
        self._show_warnings.setStyleSheet(self._get_filter_btn_style('#F59E0B'))
        toolbar_layout.addWidget(self._show_warnings)
        
        self._show_info = QPushButton("Info")
        self._show_info.setCheckable(True)
        self._show_info.setChecked(True)
        self._show_info.setStyleSheet(self._get_filter_btn_style('#3B82F6'))
        toolbar_layout.addWidget(self._show_info)
        
        toolbar_layout.addStretch()
        
        # Auto-scroll checkbox
        from PyQt6.QtWidgets import QCheckBox
        self._auto_scroll = QCheckBox("Auto-scroll")
        self._auto_scroll.setChecked(True)
        self._auto_scroll.setStyleSheet("color: #6B7280;")
        toolbar_layout.addWidget(self._auto_scroll)
        
        layout.addLayout(toolbar_layout)
        
        # Console output
        self._console = QTextEdit()
        self._console.setReadOnly(True)
        self._console.setStyleSheet("""
            QTextEdit {
                background: #1F2937;
                color: #F3F4F6;
                font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
                font-size: 12px;
                border: 1px solid #374151;
                border-radius: 6px;
                padding: 8px;
            }
        """)
        layout.addWidget(self._console)
        
        # Button row
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)
        
        btn_layout.addStretch()
        
        copy_btn = QPushButton("Copy All")
        copy_btn.setStyleSheet("""
            QPushButton {
                background: #374151;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
            }
            QPushButton:hover {
                background: #4B5563;
            }
        """)
        copy_btn.clicked.connect(self._copy_all)
        btn_layout.addWidget(copy_btn)
        
        clear_btn = QPushButton("Clear")
        clear_btn.setStyleSheet("""
            QPushButton {
                background: #374151;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
            }
            QPushButton:hover {
                background: #4B5563;
            }
        """)
        clear_btn.clicked.connect(self.reset)
        btn_layout.addWidget(clear_btn)
        
        layout.addLayout(btn_layout)
    
    def _get_filter_btn_style(self, color: str) -> str:
        return f"""
            QPushButton {{
                background: transparent;
                color: {color};
                border: 1px solid {color};
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 11px;
            }}
            QPushButton:checked {{
                background: {color};
                color: white;
            }}
            QPushButton:hover {{
                background: {color}20;
            }}
        """
    
    def _copy_all(self):
        """Copy all console text to clipboard."""
        from PyQt6.QtWidgets import QApplication
        QApplication.clipboard().setText(self._console.toPlainText())
    
    def start_session(self):
        """Start a new logging session."""
        from datetime import datetime
        self._start_time = datetime.now()
        self._console.clear()
        self.log("INFO", f"Session started at {self._start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        self.log("INFO", "-" * 50)
    
    def log(self, level: str, message: str):
        """Add a log message with level and timestamp."""
        from datetime import datetime
        
        level = level.upper()
        color = self.LOG_COLORS.get(level, '#F3F4F6')
        
        # Calculate elapsed time
        if self._start_time:
            elapsed = (datetime.now() - self._start_time).total_seconds()
            timestamp = f"[{elapsed:7.2f}s]"
        else:
            timestamp = f"[{datetime.now().strftime('%H:%M:%S')}]"
        
        # Format the log line with HTML
        level_tag = f'<span style="color: {color}; font-weight: bold;">[{level:5}]</span>'
        time_tag = f'<span style="color: #9CA3AF;">{timestamp}</span>'
        msg_color = color if level in ('ERROR', 'WARN', 'WARNING') else '#F3F4F6'
        msg_tag = f'<span style="color: {msg_color};">{self._escape_html(message)}</span>'
        
        html = f'{time_tag} {level_tag} {msg_tag}'
        self._console.append(html)
        
        # Auto-scroll if enabled
        if self._auto_scroll.isChecked():
            scrollbar = self._console.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())
    
    def _escape_html(self, text: str) -> str:
        """Escape HTML special characters."""
        return (text
            .replace('&', '&amp;')
            .replace('<', '&lt;')
            .replace('>', '&gt;')
            .replace('"', '&quot;')
        )
    
    def append_line(self, text: str):
        """Append a line to the console (auto-detect level)."""
        text = text.strip()
        if not text:
            return
        
        # Auto-detect log level from content
        text_lower = text.lower()
        if 'error' in text_lower or 'failed' in text_lower or 'exception' in text_lower:
            level = 'ERROR'
        elif 'warn' in text_lower:
            level = 'WARN'
        elif 'success' in text_lower or 'completed' in text_lower:
            level = 'SUCCESS'
        elif text.startswith('Simulator') or text.startswith('Node') or 'routing' in text_lower:
            level = 'SIM'
        else:
            level = 'INFO'
        
        self.log(level, text)
    
    def set_text(self, text: str):
        """Set the entire console text."""
        self.reset()
        for line in text.split('\n'):
            self.append_line(line)
    
    def reset(self):
        """Clear console and reset session."""
        self._console.clear()
        self._start_time = None


class RoutingTab(QWidget):
    """Routing tables tab."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 12, 0, 0)
        layout.setSpacing(8)
        
        # Tree widget for routing tables
        self._tree = QTreeWidget()
        self._tree.setHeaderLabels(["Destination", "Gateway", "Interface"])
        self._tree.setStyleSheet("""
            QTreeWidget {
                background: white;
                border: 1px solid #E5E7EB;
                border-radius: 6px;
            }
            QTreeWidget::item {
                padding: 4px;
            }
            QTreeWidget::item:selected {
                background: #EFF6FF;
                color: #1E40AF;
            }
            QHeaderView::section {
                background: #F9FAFB;
                border: none;
                border-bottom: 1px solid #E5E7EB;
                padding: 8px;
                font-weight: 600;
                color: #374151;
            }
        """)
        self._tree.setAlternatingRowColors(True)
        
        header = self._tree.header()
        header.setStretchLastSection(True)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        
        layout.addWidget(self._tree)
        
        # Empty state label
        self._empty_label = QLabel("No routing information available.\nRun a simulation with routers to see routing tables.")
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setStyleSheet("color: #9CA3AF; font-size: 12px; padding: 40px;")
        layout.addWidget(self._empty_label)
        
        self._tree.hide()
    
    def parse_and_display(self, console_output: str):
        """Parse routing tables from console output and display them."""
        self._tree.clear()
        
        # Parse routing table section from output
        import re
        
        # Find the ROUTING TABLES section
        in_routing = False
        past_header = False  # Track if we're past the header separator
        current_node = None
        routes_found = False
        
        lines = console_output.split('\n')
        
        for line in lines:
            # Detect start of routing tables section
            if "ROUTING TABLES" in line:
                in_routing = True
                past_header = False
                continue
            
            # Skip the separator line right after "ROUTING TABLES"
            if in_routing and not past_header:
                if line.strip().startswith('='):
                    past_header = True
                    continue
            
            # Detect end of routing section (next major section like "Flow 0:" or "SIMULATION RESULTS")
            if in_routing and past_header:
                if line.startswith("Flow ") or "SIMULATION RESULTS" in line:
                    in_routing = False
                    continue
                # Another === line after we've seen nodes means end of section
                if line.strip().startswith('=') and current_node is not None:
                    in_routing = False
                    continue
            
            if not in_routing:
                continue
            
            # Skip separator lines (dashes)
            if line.strip().startswith('-'):
                continue
            
            # Parse node header: "Node 0 (host_01d2):"
            node_match = re.match(r"Node (\d+) \(([^)]+)\):", line)
            if node_match:
                node_idx = node_match.group(1)
                node_name = node_match.group(2)
                
                # Create tree item for this node
                node_item = QTreeWidgetItem([f"Node {node_idx}: {node_name}", "", ""])
                node_item.setExpanded(True)
                font = node_item.font(0)
                font.setBold(True)
                node_item.setFont(0, font)
                self._tree.addTopLevelItem(node_item)
                current_node = node_item
                continue
            
            # Parse route entries in various formats:
            # Format 1: "10.1.2.0/24 via direct (local)"
            # Format 2: "0.0.0.0/0 via 10.1.2.2 (default)"
            # Format 3: "10.1.1.0/24 via direct (interface 1)"
            route_match = re.match(r"\s*(\d+\.\d+\.\d+\.\d+)/(\d+)\s+via\s+(\S+)\s*\(([^)]+)\)", line)
            if route_match and current_node:
                dest = route_match.group(1)
                cidr = route_match.group(2)
                gateway = route_match.group(3)
                route_type = route_match.group(4)
                
                dest_display = f"{dest}/{cidr}"
                
                # Gateway display
                if gateway == "direct":
                    gateway_display = "direct"
                else:
                    gateway_display = gateway
                
                route_item = QTreeWidgetItem([dest_display, gateway_display, route_type])
                current_node.addChild(route_item)
                routes_found = True
                continue
            
            # Also try simpler format without parentheses
            # Format: "  10.1.1.0/24 via 10.1.1.2 dev if1"
            route_match2 = re.match(r"\s*(\d+\.\d+\.\d+\.\d+)/(\S+)\s+via\s+(\S+)\s+dev\s+(\S+)", line)
            if route_match2 and current_node:
                dest = route_match2.group(1)
                mask = route_match2.group(2)
                gateway = route_match2.group(3)
                interface = route_match2.group(4)
                
                # Convert mask to CIDR if needed
                if '.' in mask:
                    cidr = self._mask_to_cidr(mask)
                else:
                    cidr = mask
                
                dest_display = f"{dest}/{cidr}"
                gateway_display = "direct" if gateway == "0.0.0.0" else gateway
                
                route_item = QTreeWidgetItem([dest_display, gateway_display, interface])
                current_node.addChild(route_item)
                routes_found = True
        
        if routes_found:
            self._empty_label.hide()
            self._tree.show()
            self._tree.expandAll()
        else:
            self._tree.hide()
            self._empty_label.show()
    
    def _mask_to_cidr(self, mask: str) -> str:
        """Convert subnet mask to CIDR notation."""
        try:
            parts = mask.split('.')
            binary = ''.join(format(int(p), '08b') for p in parts)
            return str(binary.count('1'))
        except:
            return mask
    
    def reset(self):
        """Reset to initial state."""
        self._tree.clear()
        self._tree.hide()
        self._empty_label.show()


class StatsPanel(QWidget):
    """
    Panel displaying simulation statistics.
    
    Shows:
    - Summary statistics
    - Per-flow details
    - Console output
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        
        # Title
        title = QLabel("Statistics")
        title_font = QFont("SF Pro Display", 14)
        title_font.setWeight(QFont.Weight.Bold)
        title.setFont(title_font)
        title.setStyleSheet("color: #111827;")
        layout.addWidget(title)
        
        # Status indicator
        self._status_frame = QFrame()
        self._status_frame.setStyleSheet("""
            QFrame {
                background: #F3F4F6;
                border-radius: 6px;
                padding: 8px;
            }
        """)
        status_layout = QHBoxLayout(self._status_frame)
        status_layout.setContentsMargins(10, 6, 10, 6)
        
        self._status_dot = QLabel("●")
        self._status_dot.setStyleSheet("color: #9CA3AF; font-size: 10px;")
        status_layout.addWidget(self._status_dot)
        
        self._status_label = QLabel("Idle")
        self._status_label.setStyleSheet("color: #6B7280; font-size: 12px;")
        status_layout.addWidget(self._status_label)
        status_layout.addStretch()
        
        layout.addWidget(self._status_frame)
        
        # Progress bar (for simulation time)
        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        self._progress.setTextVisible(False)
        self._progress.setFixedHeight(6)
        self._progress.setStyleSheet("""
            QProgressBar {
                background: #E5E7EB;
                border: none;
                border-radius: 3px;
            }
            QProgressBar::chunk {
                background: #3B82F6;
                border-radius: 3px;
            }
        """)
        layout.addWidget(self._progress)
        
        # Time display
        self._time_label = QLabel("0.00s / 10.00s")
        self._time_label.setStyleSheet("color: #6B7280; font-size: 11px;")
        self._time_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        layout.addWidget(self._time_label)
        
        # Tabs
        self._tabs = QTabWidget()
        self._tabs.setStyleSheet("""
            QTabWidget::pane {
                border: none;
            }
            QTabBar::tab {
                background: #F3F4F6;
                border: none;
                padding: 8px 16px;
                margin-right: 2px;
                border-radius: 4px 4px 0 0;
                color: #6B7280;
            }
            QTabBar::tab:selected {
                background: white;
                color: #111827;
            }
            QTabBar::tab:hover:!selected {
                background: #E5E7EB;
            }
        """)
        
        self._summary_tab = SummaryTab()
        self._tabs.addTab(self._summary_tab, "Summary")
        
        self._flows_tab = FlowsTab()
        self._tabs.addTab(self._flows_tab, "Flows")
        
        self._routing_tab = RoutingTab()
        self._tabs.addTab(self._routing_tab, "Routing")
        
        self._console_tab = ConsoleTab()
        self._tabs.addTab(self._console_tab, "Console")
        
        layout.addWidget(self._tabs)
    
    def set_status(self, status: SimulationStatus):
        """Update the status display."""
        status_config = {
            SimulationStatus.IDLE: ("●", "#9CA3AF", "Idle"),
            SimulationStatus.BUILDING: ("●", "#F59E0B", "Building..."),
            SimulationStatus.RUNNING: ("●", "#10B981", "Running"),
            SimulationStatus.PAUSED: ("●", "#F59E0B", "Paused"),
            SimulationStatus.COMPLETED: ("✓", "#10B981", "Completed"),
            SimulationStatus.ERROR: ("✕", "#EF4444", "Error"),
        }
        
        dot, color, text = status_config.get(status, ("●", "#9CA3AF", "Unknown"))
        self._status_dot.setText(dot)
        self._status_dot.setStyleSheet(f"color: {color}; font-size: 10px;")
        self._status_label.setText(text)
    
    def set_progress(self, current_time: float, end_time: float):
        """Update progress bar and time display."""
        if end_time > 0:
            progress = int((current_time / end_time) * 100)
            self._progress.setValue(min(100, progress))
        
        self._time_label.setText(f"{current_time:.2f}s / {end_time:.2f}s")
    
    def update_stats(self, stats: SimulationStats):
        """Update summary statistics displays."""
        self._summary_tab.update_stats(stats)
    
    def display_results(self, results: SimulationResults):
        """Display complete simulation results."""
        # Update summary
        stats = SimulationStats.from_results(results)
        self._summary_tab.update_stats(stats)
        
        # Update flows table
        self._flows_tab.update_flows(results.flow_stats)
        
        # Update routing tables
        self._routing_tab.parse_and_display(results.console_output)
        
        # Update console
        self._console_tab.set_text(results.console_output)
        
        # Switch to summary tab if we have results
        if results.flow_stats:
            self._tabs.setCurrentIndex(0)
    
    def append_console_line(self, line: str):
        """Append a line to the console output."""
        self._console_tab.append_line(line)
    
    def log_console(self, level: str, message: str):
        """Log a message with specified level to the console."""
        self._console_tab.log(level, message)
    
    def start_console_session(self):
        """Start a new console logging session."""
        self._console_tab.start_session()
    
    def reset(self):
        """Reset all displays to initial state."""
        self.set_status(SimulationStatus.IDLE)
        self.set_progress(0, 10)
        self._summary_tab.reset()
        self._flows_tab.reset()
        self._routing_tab.reset()
        self._console_tab.reset()
    
    def connect_state(self, state: SimulationState):
        """Connect to a simulation state for automatic updates."""
        state.statusChanged.connect(self.set_status)
        state.progressChanged.connect(self.set_progress)
        state.statsUpdated.connect(self.update_stats)
        state.resultsReady.connect(self.display_results)
