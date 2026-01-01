"""
Traffic Pattern Editor for SCADA Communication Configuration.

Provides a visual interface for configuring:
- SCADA polling groups (integrity polls, exception polls, control commands)
- Traffic flows between control centers and field devices
- Protocol settings (DNP3, IEC 61850, Modbus)
- Quality of Service parameters
"""

from typing import Optional, List, Dict, Callable
from dataclasses import dataclass
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QColor, QPainter, QIcon
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QScrollArea, QSplitter, QComboBox, QSpinBox,
    QDoubleSpinBox, QLineEdit, QTableWidget, QTableWidgetItem,
    QHeaderView, QDialog, QDialogButtonBox, QFormLayout,
    QGroupBox, QCheckBox, QToolButton, QMenu, QMessageBox,
    QTreeWidget, QTreeWidgetItem, QTabWidget, QListWidget,
    QListWidgetItem, QAbstractItemView, QSizePolicy
)

from models.grid_traffic import (
    GridTrafficFlow, GridTrafficClass, GridTrafficPriority,
    PollingGroup, TrafficProfile, QoSConfig,
    TRAFFIC_CLASS_DEFAULTS,
)
from models.grid_nodes import GridNodeType, GridProtocol, ScanClass


class PollingGroupWidget(QFrame):
    """
    Widget for editing a single polling group.
    
    A polling group represents a set of RTUs/IEDs that are polled
    together with the same timing parameters.
    """
    
    modified = pyqtSignal()
    deleteRequested = pyqtSignal(object)  # Emits self
    
    def __init__(self, group: PollingGroup, parent=None):
        super().__init__(parent)
        self.group = group
        self._setup_ui()
        self._populate()
    
    def _setup_ui(self):
        self.setFrameStyle(QFrame.Shape.StyledPanel)
        self.setStyleSheet("""
            PollingGroupWidget {
                background: white;
                border: 1px solid #E5E7EB;
                border-radius: 8px;
            }
            PollingGroupWidget:hover {
                border-color: #3B82F6;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(2)
        
        # Header
        header = QHBoxLayout()
        
        self.name_edit = QLineEdit()
        self.name_edit.setStyleSheet("""
            QLineEdit {
                font-weight: bold;
                font-size: 13px;
                border: none;
                background: transparent;
            }
            QLineEdit:focus {
                background: #F3F4F6;
                border-radius: 4px;
            }
        """)
        self.name_edit.textChanged.connect(self._on_name_changed)
        header.addWidget(self.name_edit)
        
        header.addStretch()
        
        # Delete button
        delete_btn = QToolButton()
        delete_btn.setText("×")
        delete_btn.setStyleSheet("""
            QToolButton {
                color: #9CA3AF;
                border: none;
                font-size: 18px;
            }
            QToolButton:hover {
                color: #EF4444;
            }
        """)
        delete_btn.clicked.connect(lambda: self.deleteRequested.emit(self))
        header.addWidget(delete_btn)
        
        layout.addLayout(header)
        
        # Timing row
        timing_layout = QHBoxLayout()
        
        timing_layout.addWidget(QLabel("Interval:"))
        self.interval_spin = QDoubleSpinBox()
        self.interval_spin.setRange(0.1, 3600)
        self.interval_spin.setDecimals(1)
        self.interval_spin.setSuffix(" s")
        self.interval_spin.valueChanged.connect(self._on_interval_changed)
        timing_layout.addWidget(self.interval_spin)
        
        timing_layout.addWidget(QLabel("Timeout:"))
        self.timeout_spin = QDoubleSpinBox()
        self.timeout_spin.setRange(0.1, 60)
        self.timeout_spin.setDecimals(1)
        self.timeout_spin.setSuffix(" s")
        self.timeout_spin.valueChanged.connect(self._on_timeout_changed)
        timing_layout.addWidget(self.timeout_spin)
        
        timing_layout.addStretch()
        layout.addLayout(timing_layout)
        
        # Traffic class
        class_layout = QHBoxLayout()
        class_layout.addWidget(QLabel("Class:"))
        
        self.class_combo = QComboBox()
        for tc in GridTrafficClass:
            self.class_combo.addItem(tc.name.replace("_", " ").title(), tc)
        self.class_combo.currentIndexChanged.connect(self._on_class_changed)
        class_layout.addWidget(self.class_combo)
        
        class_layout.addWidget(QLabel("Priority:"))
        self.priority_combo = QComboBox()
        for p in GridTrafficPriority:
            self.priority_combo.addItem(p.name.replace("_", " ").title(), p)
        self.priority_combo.currentIndexChanged.connect(self._on_priority_changed)
        class_layout.addWidget(self.priority_combo)
        
        class_layout.addStretch()
        layout.addLayout(class_layout)
        
        # Member count
        self.member_label = QLabel()
        self.member_label.setStyleSheet("color: #6B7280; font-size: 11px;")
        layout.addWidget(self.member_label)
    
    def _populate(self):
        """Populate from group data."""
        self.name_edit.setText(self.group.name)
        self.interval_spin.setValue(self.group.poll_interval_s)
        self.timeout_spin.setValue(self.group.response_timeout_s)
        
        idx = self.class_combo.findData(self.group.traffic_class)
        if idx >= 0:
            self.class_combo.setCurrentIndex(idx)
        
        idx = self.priority_combo.findData(self.group.priority)
        if idx >= 0:
            self.priority_combo.setCurrentIndex(idx)
        
        self._update_member_label()
    
    def _update_member_label(self):
        count = len(self.group.member_node_ids)
        self.member_label.setText(f"{count} device{'s' if count != 1 else ''} in group")
    
    def _on_name_changed(self, text):
        self.group.name = text
        self.modified.emit()
    
    def _on_interval_changed(self, value):
        self.group.poll_interval_s = value
        self.modified.emit()
    
    def _on_timeout_changed(self, value):
        self.group.response_timeout_s = value
        self.modified.emit()
    
    def _on_class_changed(self, index):
        self.group.traffic_class = self.class_combo.currentData()
        self.modified.emit()
    
    def _on_priority_changed(self, index):
        self.group.priority = self.priority_combo.currentData()
        self.modified.emit()


class FlowEditorDialog(QDialog):
    """Dialog for editing a traffic flow."""
    
    def __init__(self, flow: Optional[GridTrafficFlow] = None,
                 available_sources: List[tuple] = None,  # [(id, name), ...]
                 available_targets: List[tuple] = None,
                 parent=None):
        super().__init__(parent)
        self.flow = flow or GridTrafficFlow()
        self.available_sources = available_sources or []
        self.available_targets = available_targets or []
        self._setup_ui()
        self._populate()
    
    def _setup_ui(self):
        self.setWindowTitle("Edit Traffic Flow")
        self.setMinimumWidth(500)
        
        layout = QVBoxLayout(self)
        
        # Endpoints
        endpoint_group = QGroupBox("Endpoints")
        endpoint_layout = QFormLayout(endpoint_group)
        
        self.source_combo = QComboBox()
        for node_id, name in self.available_sources:
            self.source_combo.addItem(f"{name} ({node_id[:8]})", node_id)
        endpoint_layout.addRow("Source:", self.source_combo)
        
        self.target_combo = QComboBox()
        for node_id, name in self.available_targets:
            self.target_combo.addItem(f"{name} ({node_id[:8]})", node_id)
        endpoint_layout.addRow("Target:", self.target_combo)
        
        layout.addWidget(endpoint_group)
        
        # Traffic type
        type_group = QGroupBox("Traffic Type")
        type_layout = QFormLayout(type_group)
        
        self.class_combo = QComboBox()
        for tc in GridTrafficClass:
            self.class_combo.addItem(tc.name.replace("_", " ").title(), tc)
        self.class_combo.currentIndexChanged.connect(self._on_class_changed)
        type_layout.addRow("Class:", self.class_combo)
        
        self.priority_combo = QComboBox()
        for p in GridTrafficPriority:
            self.priority_combo.addItem(p.name.replace("_", " ").title(), p)
        type_layout.addRow("Priority:", self.priority_combo)
        
        layout.addWidget(type_group)
        
        # Timing
        timing_group = QGroupBox("Timing")
        timing_layout = QFormLayout(timing_group)
        
        self.start_spin = QDoubleSpinBox()
        self.start_spin.setRange(0, 10000)
        self.start_spin.setDecimals(1)
        self.start_spin.setSuffix(" s")
        timing_layout.addRow("Start Time:", self.start_spin)
        
        self.stop_spin = QDoubleSpinBox()
        self.stop_spin.setRange(0, 10000)
        self.stop_spin.setDecimals(1)
        self.stop_spin.setSuffix(" s")
        timing_layout.addRow("Stop Time:", self.stop_spin)
        
        self.interval_spin = QDoubleSpinBox()
        self.interval_spin.setRange(0.1, 3600)
        self.interval_spin.setDecimals(1)
        self.interval_spin.setSuffix(" s")
        timing_layout.addRow("Interval:", self.interval_spin)
        
        layout.addWidget(timing_group)
        
        # Packet sizes
        packet_group = QGroupBox("Packet Sizes")
        packet_layout = QFormLayout(packet_group)
        
        self.request_size_spin = QSpinBox()
        self.request_size_spin.setRange(1, 65535)
        self.request_size_spin.setSuffix(" bytes")
        packet_layout.addRow("Request:", self.request_size_spin)
        
        self.response_size_spin = QSpinBox()
        self.response_size_spin.setRange(1, 65535)
        self.response_size_spin.setSuffix(" bytes")
        packet_layout.addRow("Response:", self.response_size_spin)
        
        layout.addWidget(packet_group)
        
        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
    
    def _populate(self):
        """Populate from flow data."""
        # Find source in combo
        for i in range(self.source_combo.count()):
            if self.source_combo.itemData(i) == self.flow.source_node_id:
                self.source_combo.setCurrentIndex(i)
                break
        
        for i in range(self.target_combo.count()):
            if self.target_combo.itemData(i) == self.flow.target_node_id:
                self.target_combo.setCurrentIndex(i)
                break
        
        idx = self.class_combo.findData(self.flow.traffic_class)
        if idx >= 0:
            self.class_combo.setCurrentIndex(idx)
        
        idx = self.priority_combo.findData(self.flow.priority)
        if idx >= 0:
            self.priority_combo.setCurrentIndex(idx)
        
        self.start_spin.setValue(self.flow.start_time)
        self.stop_spin.setValue(self.flow.stop_time)
        self.interval_spin.setValue(self.flow.poll_interval_s)
        self.request_size_spin.setValue(self.flow.request_size_bytes)
        self.response_size_spin.setValue(self.flow.response_size_bytes)
    
    def _on_class_changed(self, index):
        """Apply defaults when traffic class changes."""
        tc = self.class_combo.currentData()
        if tc in TRAFFIC_CLASS_DEFAULTS:
            defaults = TRAFFIC_CLASS_DEFAULTS[tc]
            self.interval_spin.setValue(defaults.get("poll_interval_s", 60))
            self.request_size_spin.setValue(defaults.get("request_size_bytes", 64))
            self.response_size_spin.setValue(defaults.get("response_size_bytes", 64))
    
    def _on_accept(self):
        """Apply changes and accept."""
        self.flow.source_node_id = self.source_combo.currentData()
        self.flow.target_node_id = self.target_combo.currentData()
        self.flow.traffic_class = self.class_combo.currentData()
        self.flow.priority = self.priority_combo.currentData()
        self.flow.start_time = self.start_spin.value()
        self.flow.stop_time = self.stop_spin.value()
        self.flow.poll_interval_s = self.interval_spin.value()
        self.flow.request_size_bytes = self.request_size_spin.value()
        self.flow.response_size_bytes = self.response_size_spin.value()
        
        self.accept()
    
    def get_flow(self) -> GridTrafficFlow:
        return self.flow


class TrafficFlowTable(QTableWidget):
    """Table widget for displaying and editing traffic flows."""
    
    flowSelected = pyqtSignal(GridTrafficFlow)
    flowModified = pyqtSignal()
    
    COLUMNS = [
        ("Source", 120),
        ("Target", 120),
        ("Class", 150),
        ("Priority", 80),
        ("Interval", 70),
        ("Start", 60),
        ("Stop", 60),
    ]
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.flows: List[GridTrafficFlow] = []
        self._setup_ui()
    
    def _setup_ui(self):
        self.setColumnCount(len(self.COLUMNS))
        self.setHorizontalHeaderLabels([c[0] for c in self.COLUMNS])
        
        header = self.horizontalHeader()
        for i, (_, width) in enumerate(self.COLUMNS):
            header.resizeSection(i, width)
        header.setStretchLastSection(True)
        
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setAlternatingRowColors(True)
        
        self.setStyleSheet("""
            QTableWidget {
                border: 1px solid #E5E7EB;
                border-radius: 6px;
                gridline-color: #F3F4F6;
            }
            QHeaderView::section {
                background: #F9FAFB;
                border: none;
                border-bottom: 1px solid #E5E7EB;
                padding: 2px;
                font-weight: 600;
            }
            QTableWidget::item {
                padding: 2px;
            }
            QTableWidget::item:selected {
                background: #EFF6FF;
                color: #1F2937;
            }
        """)
        
        self.itemSelectionChanged.connect(self._on_selection_changed)
        self.cellDoubleClicked.connect(self._on_double_click)
    
    def set_flows(self, flows: List[GridTrafficFlow], node_names: Dict[str, str] = None):
        """Set the list of flows to display."""
        self.flows = flows
        self.node_names = node_names or {}
        self._refresh()
    
    def _refresh(self):
        """Refresh table from flows."""
        self.setRowCount(len(self.flows))
        
        for row, flow in enumerate(self.flows):
            self._set_row(row, flow)
    
    def _set_row(self, row: int, flow: GridTrafficFlow):
        """Set a single row from a flow."""
        source_name = self.node_names.get(flow.source_node_id, flow.source_node_id[:8])
        target_name = self.node_names.get(flow.target_node_id, flow.target_node_id[:8])
        
        items = [
            source_name,
            target_name,
            flow.traffic_class.name.replace("_", " ").title(),
            flow.priority.name.replace("_", " "),
            f"{flow.poll_interval_s:.1f}s",
            f"{flow.start_time:.1f}s",
            f"{flow.stop_time:.1f}s",
        ]
        
        for col, text in enumerate(items):
            item = QTableWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, flow)
            
            # Color based on traffic class
            if col == 2:  # Class column
                color = self._get_class_color(flow.traffic_class)
                item.setBackground(QColor(color).lighter(170))
            
            self.setItem(row, col, item)
    
    def _get_class_color(self, tc: GridTrafficClass) -> str:
        """Get color for traffic class."""
        colors = {
            GridTrafficClass.SCADA_INTEGRITY_POLL: "#3B82F6",
            GridTrafficClass.SCADA_EXCEPTION_POLL: "#10B981",
            GridTrafficClass.SCADA_CONTROL_SELECT: "#F59E0B",
            GridTrafficClass.SCADA_CONTROL_OPERATE: "#EF4444",
            GridTrafficClass.IEC61850_GOOSE: "#8B5CF6",
            GridTrafficClass.IEC61850_MMS: "#6366F1",
            GridTrafficClass.ICCP_BILATERAL: "#EC4899",
        }
        return colors.get(tc, "#6B7280")
    
    def _on_selection_changed(self):
        """Handle selection change."""
        items = self.selectedItems()
        if items:
            flow = items[0].data(Qt.ItemDataRole.UserRole)
            if flow:
                self.flowSelected.emit(flow)
    
    def _on_double_click(self, row: int, col: int):
        """Handle double-click to edit."""
        if row < len(self.flows):
            flow = self.flows[row]
            self.flowSelected.emit(flow)
    
    def get_selected_flow(self) -> Optional[GridTrafficFlow]:
        """Get the currently selected flow."""
        items = self.selectedItems()
        if items:
            return items[0].data(Qt.ItemDataRole.UserRole)
        return None


class TrafficPatternEditor(QWidget):
    """
    Complete editor for SCADA traffic patterns.
    
    Features:
    - Polling group management
    - Individual flow configuration
    - Auto-generate flows from polling groups
    - Traffic templates (DNP3, IEC 61850, etc.)
    """
    
    flowsChanged = pyqtSignal(list)  # Emits list of GridTrafficFlow
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.flows: List[GridTrafficFlow] = []
        self.polling_groups: List[PollingGroup] = []
        self.nodes: Dict[str, tuple] = {}  # id -> (name, type)
        
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Header
        header = self._create_header()
        layout.addWidget(header)
        
        # Tab widget for groups vs flows
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane {
                border: none;
                background: white;
            }
            QTabBar::tab {
                padding: 2px 4px;
                border: none;
                background: #F3F4F6;
            }
            QTabBar::tab:selected {
                background: white;
                border-bottom: 2px solid #3B82F6;
            }
        """)
        
        # Polling Groups tab
        groups_widget = self._create_groups_tab()
        self.tabs.addTab(groups_widget, "Polling Groups")
        
        # Traffic Flows tab
        flows_widget = self._create_flows_tab()
        self.tabs.addTab(flows_widget, "Traffic Flows")
        
        # Templates tab
        templates_widget = self._create_templates_tab()
        self.tabs.addTab(templates_widget, "Templates")
        
        layout.addWidget(self.tabs)
    
    def _create_header(self) -> QFrame:
        """Create header with title and actions."""
        header = QFrame()
        header.setStyleSheet("""
            QFrame {
                background: #F9FAFB;
                border-bottom: 1px solid #E5E7EB;
            }
        """)
        
        layout = QHBoxLayout(header)
        layout.setContentsMargins(2, 2, 2, 2)
        
        title = QLabel("Traffic Patterns")
        title_font = QFont("SF Pro Display", 14)
        title_font.setWeight(QFont.Weight.Bold)
        title.setFont(title_font)
        layout.addWidget(title)
        
        layout.addStretch()
        
        # Generate button
        generate_btn = QPushButton("Generate from Groups")
        generate_btn.setStyleSheet("""
            QPushButton {
                background: #10B981;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 2px 4px;
                font-weight: 500;
            }
            QPushButton:hover { background: #059669; }
        """)
        generate_btn.clicked.connect(self._generate_flows_from_groups)
        layout.addWidget(generate_btn)
        
        return header
    
    def _create_groups_tab(self) -> QWidget:
        """Create the polling groups tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(2, 2, 2, 2)
        
        # Toolbar
        toolbar = QHBoxLayout()
        
        add_btn = QPushButton("+ Add Group")
        add_btn.setStyleSheet("""
            QPushButton {
                background: #3B82F6;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 2px 4px;
            }
            QPushButton:hover { background: #2563EB; }
        """)
        add_btn.clicked.connect(self._add_polling_group)
        toolbar.addWidget(add_btn)
        
        toolbar.addStretch()
        
        layout.addLayout(toolbar)
        
        # Scroll area for groups
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        
        self.groups_container = QWidget()
        self.groups_layout = QVBoxLayout(self.groups_container)
        self.groups_layout.setContentsMargins(0, 0, 0, 0)
        self.groups_layout.setSpacing(2)
        self.groups_layout.addStretch()
        
        scroll.setWidget(self.groups_container)
        layout.addWidget(scroll)
        
        return widget
    
    def _create_flows_tab(self) -> QWidget:
        """Create the traffic flows tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(2, 2, 2, 2)
        
        # Toolbar
        toolbar = QHBoxLayout()
        
        add_btn = QPushButton("+ Add Flow")
        add_btn.setStyleSheet("""
            QPushButton {
                background: #3B82F6;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 2px 4px;
            }
            QPushButton:hover { background: #2563EB; }
        """)
        add_btn.clicked.connect(self._add_flow)
        toolbar.addWidget(add_btn)
        
        edit_btn = QPushButton("Edit")
        edit_btn.clicked.connect(self._edit_flow)
        toolbar.addWidget(edit_btn)
        
        delete_btn = QPushButton("Delete")
        delete_btn.setStyleSheet("""
            QPushButton {
                background: #EF4444;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 2px 4px;
            }
            QPushButton:hover { background: #DC2626; }
        """)
        delete_btn.clicked.connect(self._delete_flow)
        toolbar.addWidget(delete_btn)
        
        toolbar.addStretch()
        
        layout.addLayout(toolbar)
        
        # Flow table
        self.flow_table = TrafficFlowTable()
        self.flow_table.flowModified.connect(self._on_flows_modified)
        layout.addWidget(self.flow_table)
        
        return widget
    
    def _create_templates_tab(self) -> QWidget:
        """Create the templates tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(2, 2, 2, 2)
        
        info = QLabel("Apply standard traffic patterns based on protocol profiles:")
        info.setStyleSheet("color: #6B7280;")
        layout.addWidget(info)
        
        # Template buttons
        templates = [
            ("DNP3 Standard Polling", "Standard DNP3 polling with integrity, exception, and time sync"),
            ("IEC 61850 GOOSE + MMS", "GOOSE for protection, MMS for SCADA"),
            ("Modbus TCP Polling", "Simple Modbus polling pattern"),
            ("ICCP Bilateral Exchange", "Inter-control center communication"),
        ]
        
        for name, desc in templates:
            btn_frame = QFrame()
            btn_frame.setStyleSheet("""
                QFrame {
                    background: white;
                    border: 1px solid #E5E7EB;
                    border-radius: 8px;
                    padding: 2px;
                }
                QFrame:hover {
                    border-color: #3B82F6;
                }
            """)
            
            btn_layout = QVBoxLayout(btn_frame)
            
            name_label = QLabel(name)
            name_label.setStyleSheet("font-weight: bold; color: #1F2937;")
            btn_layout.addWidget(name_label)
            
            desc_label = QLabel(desc)
            desc_label.setStyleSheet("color: #6B7280; font-size: 11px;")
            btn_layout.addWidget(desc_label)
            
            apply_btn = QPushButton("Apply Template")
            apply_btn.setStyleSheet("""
                QPushButton {
                    background: #F3F4F6;
                    border: 1px solid #D1D5DB;
                    border-radius: 4px;
                    padding: 2px 4px;
                }
                QPushButton:hover { background: #E5E7EB; }
            """)
            apply_btn.clicked.connect(lambda checked, n=name: self._apply_template(n))
            btn_layout.addWidget(apply_btn)
            
            layout.addWidget(btn_frame)
        
        layout.addStretch()
        
        return widget
    
    def set_network_nodes(self, nodes: Dict[str, tuple]):
        """
        Set available network nodes for flow endpoints.
        
        Args:
            nodes: Dict mapping node_id to (name, grid_type) tuple
        """
        self.nodes = nodes
    
    def set_flows(self, flows: List[GridTrafficFlow]):
        """Set the list of traffic flows."""
        self.flows = flows
        node_names = {nid: info[0] for nid, info in self.nodes.items()}
        self.flow_table.set_flows(flows, node_names)
    
    def get_flows(self) -> List[GridTrafficFlow]:
        """Get the current list of flows."""
        return self.flows
    
    def set_polling_groups(self, groups: List[PollingGroup]):
        """Set the list of polling groups."""
        self.polling_groups = groups
        self._refresh_groups_ui()
    
    def _refresh_groups_ui(self):
        """Refresh the polling groups UI."""
        # Remove existing group widgets
        while self.groups_layout.count() > 1:  # Keep the stretch
            item = self.groups_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # Add group widgets
        for group in self.polling_groups:
            widget = PollingGroupWidget(group)
            widget.modified.connect(self._on_groups_modified)
            widget.deleteRequested.connect(self._on_group_delete_requested)
            self.groups_layout.insertWidget(self.groups_layout.count() - 1, widget)
    
    def _add_polling_group(self):
        """Add a new polling group."""
        group = PollingGroup(
            name=f"Group {len(self.polling_groups) + 1}",
            poll_interval_s=60.0,
        )
        self.polling_groups.append(group)
        self._refresh_groups_ui()
    
    def _on_groups_modified(self):
        """Handle group modification."""
        pass  # Could emit a signal
    
    def _on_group_delete_requested(self, widget: PollingGroupWidget):
        """Handle group deletion request."""
        if widget.group in self.polling_groups:
            self.polling_groups.remove(widget.group)
            self._refresh_groups_ui()
    
    def _add_flow(self):
        """Add a new traffic flow."""
        sources = [(nid, info[0]) for nid, info in self.nodes.items() 
                   if info[1] in (GridNodeType.CONTROL_CENTER, GridNodeType.BACKUP_CONTROL_CENTER)]
        targets = [(nid, info[0]) for nid, info in self.nodes.items()
                   if info[1] not in (GridNodeType.CONTROL_CENTER, GridNodeType.BACKUP_CONTROL_CENTER)]
        
        if not sources or not targets:
            QMessageBox.warning(self, "No Nodes",
                "Add control centers and field devices to the network first.")
            return
        
        dialog = FlowEditorDialog(None, sources, targets, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.flows.append(dialog.get_flow())
            self._on_flows_modified()
    
    def _edit_flow(self):
        """Edit the selected flow."""
        flow = self.flow_table.get_selected_flow()
        if not flow:
            return
        
        sources = [(nid, info[0]) for nid, info in self.nodes.items()]
        targets = sources
        
        dialog = FlowEditorDialog(flow, sources, targets, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._on_flows_modified()
    
    def _delete_flow(self):
        """Delete the selected flow."""
        flow = self.flow_table.get_selected_flow()
        if flow and flow in self.flows:
            self.flows.remove(flow)
            self._on_flows_modified()
    
    def _on_flows_modified(self):
        """Handle flow list modification."""
        node_names = {nid: info[0] for nid, info in self.nodes.items()}
        self.flow_table.set_flows(self.flows, node_names)
        self.flowsChanged.emit(self.flows)
    
    def _generate_flows_from_groups(self):
        """Generate flows from polling groups."""
        if not self.polling_groups:
            QMessageBox.information(self, "No Groups",
                "Create polling groups first, then generate flows.")
            return
        
        # Find control center
        cc_id = None
        for nid, (name, ntype) in self.nodes.items():
            if ntype == GridNodeType.CONTROL_CENTER:
                cc_id = nid
                break
        
        if not cc_id:
            QMessageBox.warning(self, "No Control Center",
                "Add a control center to the network first.")
            return
        
        # Generate flows for each group member
        new_flows = []
        for group in self.polling_groups:
            for member_id in group.member_node_ids:
                flow = GridTrafficFlow(
                    traffic_class=group.traffic_class,
                    priority=group.priority,
                    source_node_id=cc_id,
                    target_node_id=member_id,
                    poll_interval_s=group.poll_interval_s,
                    start_time=1.0,
                    stop_time=group.poll_interval_s * 10,  # Run for 10 polls
                )
                new_flows.append(flow)
        
        if new_flows:
            self.flows.extend(new_flows)
            self._on_flows_modified()
            QMessageBox.information(self, "Flows Generated",
                f"Generated {len(new_flows)} traffic flows from polling groups.")
    
    def _apply_template(self, template_name: str):
        """Apply a traffic template."""
        # Find control center and field devices
        cc_id = None
        field_devices = []
        
        for nid, (name, ntype) in self.nodes.items():
            if ntype == GridNodeType.CONTROL_CENTER:
                cc_id = nid
            elif ntype in (GridNodeType.RTU, GridNodeType.IED, GridNodeType.DATA_CONCENTRATOR):
                field_devices.append(nid)
        
        if not cc_id or not field_devices:
            QMessageBox.warning(self, "Insufficient Nodes",
                "Add a control center and field devices first.")
            return
        
        new_flows = []
        
        if template_name == "DNP3 Standard Polling":
            # Integrity poll to all devices
            for dev_id in field_devices:
                new_flows.append(GridTrafficFlow(
                    traffic_class=GridTrafficClass.SCADA_INTEGRITY_POLL,
                    source_node_id=cc_id,
                    target_node_id=dev_id,
                    poll_interval_s=60.0,
                    start_time=1.0,
                    stop_time=120.0,
                ))
                # Exception poll
                new_flows.append(GridTrafficFlow(
                    traffic_class=GridTrafficClass.SCADA_EXCEPTION_POLL,
                    source_node_id=cc_id,
                    target_node_id=dev_id,
                    poll_interval_s=4.0,
                    start_time=1.0,
                    stop_time=120.0,
                ))
        
        elif template_name == "IEC 61850 GOOSE + MMS":
            for dev_id in field_devices:
                # MMS polling
                new_flows.append(GridTrafficFlow(
                    traffic_class=GridTrafficClass.IEC61850_MMS,
                    source_node_id=cc_id,
                    target_node_id=dev_id,
                    poll_interval_s=10.0,
                    start_time=1.0,
                    stop_time=120.0,
                ))
        
        if new_flows:
            self.flows.extend(new_flows)
            self._on_flows_modified()
            QMessageBox.information(self, "Template Applied",
                f"Added {len(new_flows)} flows from '{template_name}' template.")
