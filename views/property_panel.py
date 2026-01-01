"""
Property panel for editing selected network items.

Displays and edits properties of nodes and links with
type-specific configuration options and port-level mapping.
"""

from typing import Optional, Union
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QColor, QIcon
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox,
    QGroupBox, QScrollArea, QFrame, QPushButton, QSizePolicy,
    QCheckBox, QTextEdit, QToolButton, QStackedWidget
)

from models import (
    NodeModel, LinkModel, NodeType, MediumType, ChannelType,
    PortConfig, PortType, VlanMode, PORT_TYPE_SPECS,
    NetworkModel, RoutingMode
)


class SectionHeader(QLabel):
    """Styled section header."""
    
    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        font = QFont("SF Pro Display", 11)
        font.setWeight(QFont.Weight.DemiBold)
        self.setFont(font)
        self.setStyleSheet("""
            QLabel {
                color: #374151;
                padding: 2px 0 4px 0;
                border-bottom: 1px solid #E5E7EB;
                margin-top: 8px;
            }
        """)


class CollapsibleSection(QWidget):
    """A collapsible section with header and content."""
    
    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self._is_collapsed = False
        self._setup_ui(title)
    
    def _setup_ui(self, title: str):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Header button
        self._header = QPushButton(f"▼ {title}")
        self._header.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                border-bottom: 1px solid #E5E7EB;
                padding: 2px 0;
                text-align: left;
                font-weight: 600;
                color: #374151;
                font-size: 12px;
            }
            QPushButton:hover {
                color: #3B82F6;
            }
        """)
        self._header.clicked.connect(self._toggle)
        layout.addWidget(self._header)
        
        # Content container
        self._content = QWidget()
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(0, 8, 0, 8)
        self._content_layout.setSpacing(2)
        layout.addWidget(self._content)
        
        self._title = title
    
    def _toggle(self):
        self._is_collapsed = not self._is_collapsed
        self._content.setVisible(not self._is_collapsed)
        arrow = "▶" if self._is_collapsed else "▼"
        self._header.setText(f"{arrow} {self._title}")
    
    def add_widget(self, widget: QWidget):
        self._content_layout.addWidget(widget)
    
    def add_layout(self, layout):
        self._content_layout.addLayout(layout)
    
    def content_layout(self):
        return self._content_layout


def input_style() -> str:
    """Common input widget styling."""
    return """
        QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QTextEdit {
            border: 1px solid #D1D5DB;
            border-radius: 6px;
            padding: 2px 4px;
            background: white;
            color: #374151;
            min-height: 20px;
        }
        QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus, QTextEdit:focus {
            border-color: #3B82F6;
            outline: none;
        }
        QComboBox::drop-down {
            border: none;
            padding-right: 8px;
        }
        QCheckBox {
            color: #374151;
            spacing: 8px;
        }
        QCheckBox::indicator {
            width: 18px;
            height: 18px;
            border-radius: 4px;
            border: 1px solid #D1D5DB;
            background: white;
        }
        QCheckBox::indicator:checked {
            background: #3B82F6;
            border-color: #3B82F6;
        }
    """


class PortEditor(QFrame):
    """Comprehensive editor widget for a single port."""
    
    changed = pyqtSignal()
    
    # Status colors
    STATUS_COLORS = {
        "connected": "#10B981",  # Green
        "available": "#6B7280",  # Gray
        "disabled": "#EF4444",   # Red
    }
    
    def __init__(self, port: PortConfig, node_type: NodeType, parent=None):
        super().__init__(parent)
        self.port = port
        self.node_type = node_type
        self._is_expanded = False
        self._setup_ui()
    
    def _setup_ui(self):
        self.setStyleSheet("""
            QFrame {
                background: #F9FAFB;
                border: 1px solid #E5E7EB;
                border-radius: 6px;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(2)
        
        # Header row with expand button
        header_layout = QHBoxLayout()
        header_layout.setSpacing(2)
        
        # Status indicator
        self._status_dot = QLabel("●")
        self._update_status_indicator()
        header_layout.addWidget(self._status_dot)
        
        # Port name
        self._name_label = QLabel(self.port.display_name)
        self._name_label.setStyleSheet("font-weight: 600; color: #374151;")
        header_layout.addWidget(self._name_label)
        
        # Speed badge
        self._speed_label = QLabel(self.port.speed)
        self._speed_label.setStyleSheet("""
            background: #E5E7EB;
            color: #6B7280;
            padding: 2px 6px;
            border-radius: 4px;
            font-size: 10px;
        """)
        header_layout.addWidget(self._speed_label)
        
        header_layout.addStretch()
        
        # IP display (if assigned)
        self._ip_preview = QLabel()
        self._ip_preview.setStyleSheet("color: #6B7280; font-family: monospace; font-size: 11px;")
        self._update_ip_preview()
        header_layout.addWidget(self._ip_preview)
        
        # Expand button
        self._expand_btn = QPushButton("▶")
        self._expand_btn.setFixedSize(24, 24)
        self._expand_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                color: #6B7280;
                font-size: 10px;
            }
            QPushButton:hover {
                color: #3B82F6;
            }
        """)
        self._expand_btn.clicked.connect(self._toggle_expand)
        header_layout.addWidget(self._expand_btn)
        
        layout.addLayout(header_layout)
        
        # Expandable details section
        self._details = QWidget()
        self._details.hide()
        details_layout = QVBoxLayout(self._details)
        details_layout.setContentsMargins(0, 8, 0, 0)
        details_layout.setSpacing(2)
        
        # Layer 1 - Physical
        l1_group = self._create_layer1_section()
        details_layout.addWidget(l1_group)
        
        # Layer 2 - Data Link (mainly for switches)
        if self.node_type == NodeType.SWITCH:
            l2_group = self._create_layer2_section()
            details_layout.addWidget(l2_group)
        
        # Layer 3 - Network
        l3_group = self._create_layer3_section()
        details_layout.addWidget(l3_group)
        
        layout.addWidget(self._details)
    
    def _create_layer1_section(self) -> QWidget:
        """Create Layer 1 (Physical) settings."""
        group = QFrame()
        group.setStyleSheet("QFrame { background: white; border-radius: 4px; padding: 2px; }")
        layout = QFormLayout(group)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(2)
        
        # Section label
        l1_label = QLabel("Physical (L1)")
        l1_label.setStyleSheet("font-weight: 600; color: #6B7280; font-size: 10px;")
        layout.addRow(l1_label)
        
        # Port name
        self._port_name_edit = QLineEdit(self.port.port_name)
        self._port_name_edit.textChanged.connect(self._on_name_changed)
        self._port_name_edit.setStyleSheet(input_style())
        layout.addRow("Name:", self._port_name_edit)
        
        # Port type
        self._port_type_combo = QComboBox()
        for pt in PortType:
            spec = PORT_TYPE_SPECS[pt]
            self._port_type_combo.addItem(f"{pt.name.replace('_', ' ').title()}", pt)
        idx = self._port_type_combo.findData(self.port.port_type)
        self._port_type_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self._port_type_combo.currentIndexChanged.connect(self._on_type_changed)
        self._port_type_combo.setStyleSheet(input_style())
        layout.addRow("Type:", self._port_type_combo)
        
        # Speed
        self._speed_edit = QLineEdit(self.port.speed)
        self._speed_edit.textChanged.connect(self._on_speed_changed)
        self._speed_edit.setStyleSheet(input_style())
        layout.addRow("Speed:", self._speed_edit)
        
        # Duplex
        self._duplex_combo = QComboBox()
        self._duplex_combo.addItems(["full", "half", "auto"])
        idx = self._duplex_combo.findText(self.port.duplex)
        self._duplex_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self._duplex_combo.currentIndexChanged.connect(self._on_duplex_changed)
        self._duplex_combo.setStyleSheet(input_style())
        layout.addRow("Duplex:", self._duplex_combo)
        
        # MTU
        self._mtu_spin = QSpinBox()
        self._mtu_spin.setRange(68, 65535)
        self._mtu_spin.setValue(self.port.mtu)
        self._mtu_spin.valueChanged.connect(self._on_mtu_changed)
        self._mtu_spin.setStyleSheet(input_style())
        layout.addRow("MTU:", self._mtu_spin)
        
        # Enabled
        self._enabled_check = QCheckBox("Port enabled")
        self._enabled_check.setChecked(self.port.enabled)
        self._enabled_check.stateChanged.connect(self._on_enabled_changed)
        self._enabled_check.setStyleSheet(input_style())
        layout.addRow("", self._enabled_check)
        
        return group
    
    def _create_layer2_section(self) -> QWidget:
        """Create Layer 2 (Data Link) settings for switches."""
        group = QFrame()
        group.setStyleSheet("QFrame { background: white; border-radius: 4px; padding: 2px; }")
        layout = QFormLayout(group)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(2)
        
        # Section label
        l2_label = QLabel("Data Link (L2)")
        l2_label.setStyleSheet("font-weight: 600; color: #6B7280; font-size: 10px;")
        layout.addRow(l2_label)
        
        # MAC Address
        self._mac_edit = QLineEdit(self.port.mac_address)
        self._mac_edit.setPlaceholderText("Auto-assigned")
        self._mac_edit.textChanged.connect(self._on_mac_changed)
        self._mac_edit.setStyleSheet(input_style())
        layout.addRow("MAC:", self._mac_edit)
        
        # VLAN Mode
        self._vlan_mode_combo = QComboBox()
        self._vlan_mode_combo.addItem("Access", VlanMode.ACCESS)
        self._vlan_mode_combo.addItem("Trunk", VlanMode.TRUNK)
        idx = self._vlan_mode_combo.findData(self.port.vlan_mode)
        self._vlan_mode_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self._vlan_mode_combo.currentIndexChanged.connect(self._on_vlan_mode_changed)
        self._vlan_mode_combo.setStyleSheet(input_style())
        layout.addRow("VLAN Mode:", self._vlan_mode_combo)
        
        # VLAN ID (for access mode)
        self._vlan_id_spin = QSpinBox()
        self._vlan_id_spin.setRange(1, 4094)
        self._vlan_id_spin.setValue(self.port.vlan_id)
        self._vlan_id_spin.valueChanged.connect(self._on_vlan_id_changed)
        self._vlan_id_spin.setStyleSheet(input_style())
        layout.addRow("VLAN ID:", self._vlan_id_spin)
        
        # Trunk allowed VLANs (for trunk mode)
        self._trunk_vlans_edit = QLineEdit(self.port.trunk_allowed_vlans)
        self._trunk_vlans_edit.setPlaceholderText("e.g., 1-100,200,300-400")
        self._trunk_vlans_edit.textChanged.connect(self._on_trunk_vlans_changed)
        self._trunk_vlans_edit.setStyleSheet(input_style())
        layout.addRow("Allowed VLANs:", self._trunk_vlans_edit)
        
        return group
    
    def _create_layer3_section(self) -> QWidget:
        """Create Layer 3 (Network) settings."""
        group = QFrame()
        group.setStyleSheet("QFrame { background: white; border-radius: 4px; padding: 2px; }")
        layout = QFormLayout(group)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(2)
        
        # Section label
        l3_label = QLabel("Network (L3)")
        l3_label.setStyleSheet("font-weight: 600; color: #6B7280; font-size: 10px;")
        layout.addRow(l3_label)
        
        # IP Address (user-configured)
        self._ip_edit = QLineEdit(self.port.ip_address)
        self._ip_edit.setPlaceholderText("e.g., 10.0.1.1")
        self._ip_edit.textChanged.connect(self._on_ip_changed)
        self._ip_edit.setStyleSheet(input_style())
        layout.addRow("IP Address:", self._ip_edit)
        
        # Netmask
        self._netmask_edit = QLineEdit(self.port.netmask)
        self._netmask_edit.textChanged.connect(self._on_netmask_changed)
        self._netmask_edit.setStyleSheet(input_style())
        layout.addRow("Netmask:", self._netmask_edit)
        
        # Assigned IP (from simulation) - read-only with special styling
        assigned_ip_container = QWidget()
        assigned_ip_layout = QHBoxLayout(assigned_ip_container)
        assigned_ip_layout.setContentsMargins(0, 0, 0, 0)
        assigned_ip_layout.setSpacing(2)
        
        self._assigned_ip_label = QLabel(self.port.assigned_ip or "—")
        self._assigned_ip_label.setStyleSheet("""
            QLabel {
                font-family: 'Consolas', 'Monaco', monospace;
                color: #059669;
                font-weight: 500;
                padding: 2px 8px;
                background: #D1FAE5;
                border: 1px solid #A7F3D0;
                border-radius: 4px;
            }
        """)
        assigned_ip_layout.addWidget(self._assigned_ip_label)
        
        # Runtime badge
        runtime_badge = QLabel("runtime")
        runtime_badge.setStyleSheet("""
            QLabel {
                font-size: 9px;
                color: #6B7280;
                background: #F3F4F6;
                padding: 2px 4px;
                border-radius: 3px;
            }
        """)
        runtime_badge.setToolTip("This IP was assigned during simulation")
        assigned_ip_layout.addWidget(runtime_badge)
        assigned_ip_layout.addStretch()
        
        # Create row label with info icon
        assigned_label = QLabel("Assigned IP:")
        assigned_label.setToolTip("IP address assigned by ns-3 during simulation")
        layout.addRow(assigned_label, assigned_ip_container)
        
        # Update visibility based on whether we have an assigned IP
        self._update_assigned_ip_visibility()
        
        # MAC (for non-switches)
        if self.node_type != NodeType.SWITCH:
            self._mac_edit = QLineEdit(self.port.mac_address)
            self._mac_edit.setPlaceholderText("Auto-assigned")
            self._mac_edit.textChanged.connect(self._on_mac_changed)
            self._mac_edit.setStyleSheet(input_style())
            layout.addRow("MAC:", self._mac_edit)
        
        return group
    
    def _update_assigned_ip_visibility(self):
        """Update the assigned IP display based on current value."""
        if hasattr(self, '_assigned_ip_label'):
            if self.port.assigned_ip:
                self._assigned_ip_label.setText(self.port.assigned_ip)
                self._assigned_ip_label.setStyleSheet("""
                    QLabel {
                        font-family: 'Consolas', 'Monaco', monospace;
                        color: #059669;
                        font-weight: 500;
                        padding: 2px 8px;
                        background: #D1FAE5;
                        border: 1px solid #A7F3D0;
                        border-radius: 4px;
                    }
                """)
            else:
                self._assigned_ip_label.setText("—")
                self._assigned_ip_label.setStyleSheet("""
                    QLabel {
                        font-family: 'Consolas', 'Monaco', monospace;
                        color: #9CA3AF;
                        padding: 2px 8px;
                        background: #F9FAFB;
                        border: 1px solid #E5E7EB;
                        border-radius: 4px;
                    }
                """)
    
    def _toggle_expand(self):
        self._is_expanded = not self._is_expanded
        self._details.setVisible(self._is_expanded)
        self._expand_btn.setText("▼" if self._is_expanded else "▶")
    
    def _update_status_indicator(self):
        status = self.port.status_text
        color = self.STATUS_COLORS.get(status, "#6B7280")
        self._status_dot.setStyleSheet(f"color: {color}; font-size: 8px;")
        self._status_dot.setToolTip(status.title())
    
    def _update_ip_preview(self):
        """Update the IP preview shown in the collapsed header."""
        # Prefer assigned IP (from simulation), fall back to configured IP
        if self.port.assigned_ip:
            self._ip_preview.setText(f"⚡ {self.port.assigned_ip}")
            self._ip_preview.setStyleSheet("""
                color: #059669; 
                font-family: monospace; 
                font-size: 11px;
                font-weight: 500;
            """)
            self._ip_preview.setToolTip("Runtime-assigned IP from simulation")
        elif self.port.ip_address:
            self._ip_preview.setText(self.port.ip_address)
            self._ip_preview.setStyleSheet("color: #6B7280; font-family: monospace; font-size: 11px;")
            self._ip_preview.setToolTip("Configured IP address")
        else:
            self._ip_preview.setText("")
            self._ip_preview.setToolTip("")
    
    def refresh_from_model(self):
        """Refresh display from the port model (call after external changes)."""
        self._update_status_indicator()
        self._update_ip_preview()
        self._update_assigned_ip_visibility()
        # Update the name label
        self._name_label.setText(self.port.display_name)
    
    # Signal handlers
    def _on_name_changed(self, text):
        self.port.port_name = text
        self._name_label.setText(text or f"port{self.port.port_number}")
        self.changed.emit()
    
    def _on_type_changed(self, idx):
        self.port.port_type = self._port_type_combo.currentData()
        spec = PORT_TYPE_SPECS[self.port.port_type]
        self._speed_edit.setText(spec["speed"])
        self.changed.emit()
    
    def _on_speed_changed(self, text):
        self.port.speed = text
        self._speed_label.setText(text)
        self.changed.emit()
    
    def _on_duplex_changed(self, idx):
        self.port.duplex = self._duplex_combo.currentText()
        self.changed.emit()
    
    def _on_mtu_changed(self, value):
        self.port.mtu = value
        self.changed.emit()
    
    def _on_enabled_changed(self, state):
        self.port.enabled = bool(state)
        self._update_status_indicator()
        self.changed.emit()
    
    def _on_mac_changed(self, text):
        self.port.mac_address = text
        self.changed.emit()
    
    def _on_vlan_mode_changed(self, idx):
        self.port.vlan_mode = self._vlan_mode_combo.currentData()
        self.changed.emit()
    
    def _on_vlan_id_changed(self, value):
        self.port.vlan_id = value
        self.changed.emit()
    
    def _on_trunk_vlans_changed(self, text):
        self.port.trunk_allowed_vlans = text
        self.changed.emit()
    
    def _on_ip_changed(self, text):
        self.port.ip_address = text
        self._update_ip_preview()
        self.changed.emit()
    
    def _on_netmask_changed(self, text):
        self.port.netmask = text
        self.changed.emit()


class NodePropertiesWidget(QWidget):
    """Properties editor for a node with type-specific options and ports."""
    
    propertiesChanged = pyqtSignal()
    nodeTypeChanged = pyqtSignal(object)  # Emits new NodeType
    mediumTypeChanged = pyqtSignal(object)  # Emits new MediumType
    subnetApplied = pyqtSignal(str)  # Emits switch node ID when subnet should be applied
    editRoutingRequested = pyqtSignal(object)  # Emits node when routing edit is requested
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._node: Optional[NodeModel] = None
        self._network: Optional[NetworkModel] = None
        self._setup_ui()
    
    def set_network(self, network: 'NetworkModel'):
        """Set the network model reference for routing dialog."""
        self._network = network
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # === Basic Properties Section ===
        layout.addWidget(SectionHeader("Basic Properties"))
        
        form = QFormLayout()
        form.setContentsMargins(0, 8, 0, 12)
        form.setSpacing(2)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        
        # Name
        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText("Enter node name")
        self._name_edit.textChanged.connect(self._on_name_changed)
        self._name_edit.setStyleSheet(input_style())
        form.addRow("Name:", self._name_edit)
        
        # Type (editable)
        self._type_combo = QComboBox()
        self._type_combo.addItem("Host", NodeType.HOST)
        self._type_combo.addItem("Router", NodeType.ROUTER)
        self._type_combo.addItem("Switch", NodeType.SWITCH)
        self._type_combo.addItem("WiFi Station", NodeType.STATION)
        self._type_combo.addItem("Access Point", NodeType.ACCESS_POINT)
        self._type_combo.currentIndexChanged.connect(self._on_type_changed)
        self._type_combo.setStyleSheet(input_style())
        form.addRow("Type:", self._type_combo)
        
        # Medium type (network connection type)
        self._medium_combo = QComboBox()
        self._medium_combo.addItem("Wired (Ethernet/P2P)", MediumType.WIRED)
        self._medium_combo.addItem("WiFi Station", MediumType.WIFI_STATION)
        self._medium_combo.addItem("WiFi Access Point", MediumType.WIFI_AP)
        self._medium_combo.addItem("LTE User Equipment", MediumType.LTE_UE)
        self._medium_combo.addItem("LTE eNodeB", MediumType.LTE_ENB)
        self._medium_combo.currentIndexChanged.connect(self._on_medium_changed)
        self._medium_combo.setStyleSheet(input_style())
        form.addRow("Medium:", self._medium_combo)
        
        # Description
        self._desc_edit = QLineEdit()
        self._desc_edit.setPlaceholderText("Optional description")
        self._desc_edit.textChanged.connect(self._on_desc_changed)
        self._desc_edit.setStyleSheet(input_style())
        form.addRow("Description:", self._desc_edit)
        
        # ID (read-only)
        self._id_label = QLabel()
        self._id_label.setStyleSheet("color: #9CA3AF; font-family: monospace; font-size: 11px;")
        form.addRow("ID:", self._id_label)
        
        layout.addLayout(form)
        
        # === Type-Specific Properties Section ===
        layout.addWidget(SectionHeader("Type Settings"))
        
        self._type_settings_container = QVBoxLayout()
        self._type_settings_container.setContentsMargins(0, 8, 0, 12)
        self._type_settings_container.setSpacing(2)
        layout.addLayout(self._type_settings_container)
        
        self._create_host_settings()
        self._create_router_settings()
        self._create_switch_settings()
        
        # === Ports Section ===
        layout.addWidget(SectionHeader("Ports"))
        
        # Port summary
        self._port_summary = QLabel()
        self._port_summary.setStyleSheet("color: #6B7280; font-size: 11px; padding: 2px 0;")
        layout.addWidget(self._port_summary)
        
        # Add port button
        add_port_btn = QPushButton("+ Add Port")
        add_port_btn.setStyleSheet("""
            QPushButton {
                background: white;
                border: 1px dashed #D1D5DB;
                border-radius: 6px;
                padding: 2px;
                color: #6B7280;
            }
            QPushButton:hover {
                border-color: #3B82F6;
                color: #3B82F6;
            }
        """)
        add_port_btn.clicked.connect(self._on_add_port)
        layout.addWidget(add_port_btn)
        
        # Ports container
        self._ports_container = QVBoxLayout()
        self._ports_container.setContentsMargins(0, 8, 0, 0)
        self._ports_container.setSpacing(2)
        layout.addLayout(self._ports_container)
        
        layout.addStretch()
    
    def _create_host_settings(self):
        """Create Host-specific settings."""
        self._host_widget = QWidget()
        host_layout = QFormLayout(self._host_widget)
        host_layout.setContentsMargins(0, 0, 0, 0)
        host_layout.setSpacing(2)
        
        self._is_server_check = QCheckBox("Acts as server")
        self._is_server_check.stateChanged.connect(self._on_host_prop_changed)
        self._is_server_check.setStyleSheet(input_style())
        host_layout.addRow("Role:", self._is_server_check)
        
        # Routing button
        self._host_routing_btn = QPushButton("Edit Routing Table...")
        self._host_routing_btn.clicked.connect(self._on_edit_routing)
        self._host_routing_btn.setStyleSheet("""
            QPushButton {
                background: #3B82F6;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 2px 4px;
            }
            QPushButton:hover {
                background: #2563EB;
            }
        """)
        host_layout.addRow("Routing:", self._host_routing_btn)
        
        self._type_settings_container.addWidget(self._host_widget)
    
    def _create_router_settings(self):
        """Create Router-specific settings."""
        self._router_widget = QWidget()
        router_layout = QFormLayout(self._router_widget)
        router_layout.setContentsMargins(0, 0, 0, 0)
        router_layout.setSpacing(2)
        
        self._routing_combo = QComboBox()
        self._routing_combo.addItem("Static Routing", "static")
        self._routing_combo.addItem("OLSR", "olsr")
        self._routing_combo.addItem("AODV", "aodv")
        self._routing_combo.addItem("OSPF", "ospf")
        self._routing_combo.addItem("RIP", "rip")
        self._routing_combo.currentIndexChanged.connect(self._on_router_prop_changed)
        self._routing_combo.setStyleSheet(input_style())
        router_layout.addRow("Protocol:", self._routing_combo)
        
        self._forwarding_check = QCheckBox("Enable IP forwarding")
        self._forwarding_check.setChecked(True)
        self._forwarding_check.stateChanged.connect(self._on_router_prop_changed)
        self._forwarding_check.setStyleSheet(input_style())
        router_layout.addRow("Forwarding:", self._forwarding_check)
        
        # Routing table button
        self._router_routing_btn = QPushButton("Edit Routing Table...")
        self._router_routing_btn.clicked.connect(self._on_edit_routing)
        self._router_routing_btn.setStyleSheet("""
            QPushButton {
                background: #3B82F6;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 2px 4px;
            }
            QPushButton:hover {
                background: #2563EB;
            }
        """)
        router_layout.addRow("Routes:", self._router_routing_btn)
        
        self._type_settings_container.addWidget(self._router_widget)
    
    def _create_switch_settings(self):
        """Create Switch-specific settings."""
        self._switch_widget = QWidget()
        switch_layout = QFormLayout(self._switch_widget)
        switch_layout.setContentsMargins(0, 0, 0, 0)
        switch_layout.setSpacing(2)
        
        self._switch_mode_combo = QComboBox()
        self._switch_mode_combo.addItem("Learning Switch", "learning")
        self._switch_mode_combo.addItem("Hub Mode (Broadcast)", "hub")
        self._switch_mode_combo.currentIndexChanged.connect(self._on_switch_prop_changed)
        self._switch_mode_combo.setStyleSheet(input_style())
        switch_layout.addRow("Mode:", self._switch_mode_combo)
        
        self._stp_check = QCheckBox("Enable Spanning Tree (STP)")
        self._stp_check.stateChanged.connect(self._on_switch_prop_changed)
        self._stp_check.setStyleSheet(input_style())
        switch_layout.addRow("STP:", self._stp_check)
        
        # Subnet configuration section
        subnet_label = QLabel("Network Subnet")
        subnet_label.setStyleSheet("font-weight: 600; color: #374151; margin-top: 8px;")
        switch_layout.addRow(subnet_label)
        
        subnet_help = QLabel("Set a subnet to auto-assign IPs to connected hosts")
        subnet_help.setStyleSheet("color: #6B7280; font-size: 10px;")
        subnet_help.setWordWrap(True)
        switch_layout.addRow(subnet_help)
        
        self._subnet_base_edit = QLineEdit()
        self._subnet_base_edit.setPlaceholderText("e.g., 192.168.1.0")
        self._subnet_base_edit.textChanged.connect(self._on_subnet_changed)
        self._subnet_base_edit.setStyleSheet(input_style())
        switch_layout.addRow("Subnet:", self._subnet_base_edit)
        
        self._subnet_mask_combo = QComboBox()
        self._subnet_mask_combo.addItem("/24 (255.255.255.0)", "255.255.255.0")
        self._subnet_mask_combo.addItem("/16 (255.255.0.0)", "255.255.0.0")
        self._subnet_mask_combo.addItem("/8 (255.0.0.0)", "255.0.0.0")
        self._subnet_mask_combo.currentIndexChanged.connect(self._on_subnet_changed)
        self._subnet_mask_combo.setStyleSheet(input_style())
        switch_layout.addRow("Mask:", self._subnet_mask_combo)
        
        self._apply_subnet_btn = QPushButton("Apply to Connected Hosts")
        self._apply_subnet_btn.setStyleSheet("""
            QPushButton {
                background: #3B82F6;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 2px;
                font-weight: 500;
            }
            QPushButton:hover {
                background: #2563EB;
            }
        """)
        self._apply_subnet_btn.clicked.connect(self._on_apply_subnet)
        switch_layout.addRow("", self._apply_subnet_btn)
        
        self._type_settings_container.addWidget(self._switch_widget)
        
        # WiFi-specific settings (for STATION and ACCESS_POINT)
        self._wifi_widget = QWidget()
        wifi_layout = QFormLayout(self._wifi_widget)
        wifi_layout.setContentsMargins(0, 0, 0, 0)
        wifi_layout.setSpacing(2)
        
        wifi_header = QLabel("WiFi Settings")
        wifi_header.setStyleSheet("font-weight: bold; color: #374151; margin-top: 4px;")
        wifi_layout.addRow(wifi_header)
        
        # WiFi Standard
        self._wifi_standard_combo = QComboBox()
        self._wifi_standard_combo.addItem("802.11b (2.4GHz, 11Mbps)", "802.11b")
        self._wifi_standard_combo.addItem("802.11g (2.4GHz, 54Mbps)", "802.11g")
        self._wifi_standard_combo.addItem("802.11n (2.4/5GHz, 600Mbps)", "802.11n")
        self._wifi_standard_combo.addItem("802.11ac (5GHz, 6.9Gbps)", "802.11ac")
        self._wifi_standard_combo.addItem("802.11ax (WiFi 6)", "802.11ax")
        self._wifi_standard_combo.currentIndexChanged.connect(self._on_wifi_prop_changed)
        self._wifi_standard_combo.setStyleSheet(input_style())
        wifi_layout.addRow("Standard:", self._wifi_standard_combo)
        
        # SSID (for AP)
        self._wifi_ssid_edit = QLineEdit()
        self._wifi_ssid_edit.setPlaceholderText("ns3-wifi")
        self._wifi_ssid_edit.textChanged.connect(self._on_wifi_prop_changed)
        self._wifi_ssid_edit.setStyleSheet(input_style())
        wifi_layout.addRow("SSID:", self._wifi_ssid_edit)
        
        # Channel
        self._wifi_channel_spin = QSpinBox()
        self._wifi_channel_spin.setRange(1, 165)
        self._wifi_channel_spin.setValue(1)
        self._wifi_channel_spin.valueChanged.connect(self._on_wifi_prop_changed)
        self._wifi_channel_spin.setStyleSheet(input_style())
        wifi_layout.addRow("Channel:", self._wifi_channel_spin)
        
        # Band
        self._wifi_band_combo = QComboBox()
        self._wifi_band_combo.addItem("2.4 GHz", "2.4GHz")
        self._wifi_band_combo.addItem("5 GHz", "5GHz")
        self._wifi_band_combo.currentIndexChanged.connect(self._on_wifi_prop_changed)
        self._wifi_band_combo.setStyleSheet(input_style())
        wifi_layout.addRow("Band:", self._wifi_band_combo)
        
        # TX Power
        self._wifi_tx_power_spin = QDoubleSpinBox()
        self._wifi_tx_power_spin.setRange(0, 30)
        self._wifi_tx_power_spin.setValue(20.0)
        self._wifi_tx_power_spin.setSuffix(" dBm")
        self._wifi_tx_power_spin.valueChanged.connect(self._on_wifi_prop_changed)
        self._wifi_tx_power_spin.setStyleSheet(input_style())
        wifi_layout.addRow("TX Power:", self._wifi_tx_power_spin)
        
        self._type_settings_container.addWidget(self._wifi_widget)
        
        # Socket Application settings (for APPLICATION node type)
        self._app_widget = QWidget()
        app_layout = QFormLayout(self._app_widget)
        app_layout.setContentsMargins(0, 0, 0, 0)
        app_layout.setSpacing(2)
        
        app_header = QLabel("Socket Application Settings")
        app_header.setStyleSheet("font-weight: bold; color: #374151; margin-top: 4px;")
        app_layout.addRow(app_header)
        
        # Attached Node (which host this app runs on)
        self._app_attached_combo = QComboBox()
        self._app_attached_combo.setPlaceholderText("Select host node...")
        self._app_attached_combo.currentIndexChanged.connect(self._on_app_prop_changed)
        self._app_attached_combo.setStyleSheet(input_style())
        app_layout.addRow("Attached To:", self._app_attached_combo)
        
        # Role (sender/receiver)
        self._app_role_combo = QComboBox()
        self._app_role_combo.addItem("Sender (Client)", "sender")
        self._app_role_combo.addItem("Receiver (Server)", "receiver")
        self._app_role_combo.currentIndexChanged.connect(self._on_app_prop_changed)
        self._app_role_combo.setStyleSheet(input_style())
        app_layout.addRow("Role:", self._app_role_combo)
        
        # Protocol
        self._app_protocol_combo = QComboBox()
        self._app_protocol_combo.addItem("UDP", "UDP")
        self._app_protocol_combo.addItem("TCP", "TCP")
        self._app_protocol_combo.currentIndexChanged.connect(self._on_app_prop_changed)
        self._app_protocol_combo.setStyleSheet(input_style())
        app_layout.addRow("Protocol:", self._app_protocol_combo)
        
        # Remote Address (for sender)
        self._app_remote_addr_edit = QLineEdit()
        self._app_remote_addr_edit.setPlaceholderText("e.g., 10.1.1.2")
        self._app_remote_addr_edit.textChanged.connect(self._on_app_prop_changed)
        self._app_remote_addr_edit.setStyleSheet(input_style())
        app_layout.addRow("Remote Address:", self._app_remote_addr_edit)
        
        # Remote/Local Port
        self._app_port_spin = QSpinBox()
        self._app_port_spin.setRange(1, 65535)
        self._app_port_spin.setValue(9000)
        self._app_port_spin.valueChanged.connect(self._on_app_prop_changed)
        self._app_port_spin.setStyleSheet(input_style())
        app_layout.addRow("Port:", self._app_port_spin)
        
        # Payload settings header
        payload_header = QLabel("Payload Configuration")
        payload_header.setStyleSheet("font-weight: bold; color: #6B7280; margin-top: 8px;")
        app_layout.addRow(payload_header)
        
        # Payload Type
        self._app_payload_type_combo = QComboBox()
        self._app_payload_type_combo.addItem("Custom Pattern", "pattern")
        self._app_payload_type_combo.addItem("Random Data", "random")
        self._app_payload_type_combo.addItem("Sequence (0,1,2...)", "sequence")
        self._app_payload_type_combo.currentIndexChanged.connect(self._on_app_prop_changed)
        self._app_payload_type_combo.setStyleSheet(input_style())
        app_layout.addRow("Payload Type:", self._app_payload_type_combo)
        
        # Payload Data (for pattern)
        self._app_payload_edit = QLineEdit()
        self._app_payload_edit.setPlaceholderText("Custom payload string or hex (0x...)")
        self._app_payload_edit.textChanged.connect(self._on_app_prop_changed)
        self._app_payload_edit.setStyleSheet(input_style())
        app_layout.addRow("Payload Data:", self._app_payload_edit)
        
        # Payload Size
        self._app_payload_size_spin = QSpinBox()
        self._app_payload_size_spin.setRange(1, 65535)
        self._app_payload_size_spin.setValue(512)
        self._app_payload_size_spin.setSuffix(" bytes")
        self._app_payload_size_spin.valueChanged.connect(self._on_app_prop_changed)
        self._app_payload_size_spin.setStyleSheet(input_style())
        app_layout.addRow("Packet Size:", self._app_payload_size_spin)
        
        # Send Count
        self._app_send_count_spin = QSpinBox()
        self._app_send_count_spin.setRange(0, 1000000)
        self._app_send_count_spin.setValue(10)
        self._app_send_count_spin.setSpecialValueText("Unlimited")
        self._app_send_count_spin.valueChanged.connect(self._on_app_prop_changed)
        self._app_send_count_spin.setStyleSheet(input_style())
        app_layout.addRow("Send Count:", self._app_send_count_spin)
        
        # Send Interval
        self._app_interval_spin = QDoubleSpinBox()
        self._app_interval_spin.setRange(0.001, 60.0)
        self._app_interval_spin.setValue(1.0)
        self._app_interval_spin.setSuffix(" sec")
        self._app_interval_spin.setDecimals(3)
        self._app_interval_spin.valueChanged.connect(self._on_app_prop_changed)
        self._app_interval_spin.setStyleSheet(input_style())
        app_layout.addRow("Send Interval:", self._app_interval_spin)
        
        # Timing header
        timing_header = QLabel("Timing")
        timing_header.setStyleSheet("font-weight: bold; color: #6B7280; margin-top: 8px;")
        app_layout.addRow(timing_header)
        
        # Start Time
        self._app_start_time_spin = QDoubleSpinBox()
        self._app_start_time_spin.setRange(0.0, 1000.0)
        self._app_start_time_spin.setValue(1.0)
        self._app_start_time_spin.setSuffix(" sec")
        self._app_start_time_spin.valueChanged.connect(self._on_app_prop_changed)
        self._app_start_time_spin.setStyleSheet(input_style())
        app_layout.addRow("Start Time:", self._app_start_time_spin)
        
        # Stop Time
        self._app_stop_time_spin = QDoubleSpinBox()
        self._app_stop_time_spin.setRange(0.0, 1000.0)
        self._app_stop_time_spin.setValue(9.0)
        self._app_stop_time_spin.setSuffix(" sec")
        self._app_stop_time_spin.valueChanged.connect(self._on_app_prop_changed)
        self._app_stop_time_spin.setStyleSheet(input_style())
        app_layout.addRow("Stop Time:", self._app_stop_time_spin)
        
        self._type_settings_container.addWidget(self._app_widget)
    
    def set_node(self, node: Optional[NodeModel]):
        # Only rebuild if it's a different node
        if self._node is not None and node is not None and self._node.id == node.id:
            return  # Same node, no need to rebuild
        self._node = node
        self._update_display()
    
    def _update_display(self):
        # Clear ports
        while self._ports_container.count():
            item = self._ports_container.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # Hide all type-specific widgets
        self._host_widget.hide()
        self._router_widget.hide()
        self._switch_widget.hide()
        self._wifi_widget.hide()
        self._app_widget.hide()
        
        if not self._node:
            self._name_edit.clear()
            self._type_combo.setCurrentIndex(0)
            self._medium_combo.setCurrentIndex(0)
            self._desc_edit.clear()
            self._id_label.clear()
            self._port_summary.setText("")
            return
        
        # Block signals during update
        self._name_edit.blockSignals(True)
        self._name_edit.setText(self._node.name)
        self._name_edit.blockSignals(False)
        
        self._type_combo.blockSignals(True)
        idx = self._type_combo.findData(self._node.node_type)
        self._type_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self._type_combo.blockSignals(False)
        
        # Update medium type combo
        self._medium_combo.blockSignals(True)
        medium = getattr(self._node, 'medium_type', MediumType.WIRED)
        idx = self._medium_combo.findData(medium)
        self._medium_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self._medium_combo.blockSignals(False)
        
        self._desc_edit.blockSignals(True)
        self._desc_edit.setText(self._node.description)
        self._desc_edit.blockSignals(False)
        
        self._id_label.setText(self._node.id)
        
        # Update type-specific
        self._update_type_specific_ui()
        
        # Update port summary
        total = len(self._node.ports)
        connected = len([p for p in self._node.ports if p.is_connected])
        self._port_summary.setText(f"{connected} connected, {total - connected} available ({total} total)")
        
        # Add port editors
        for port in self._node.ports:
            editor = PortEditor(port, self._node.node_type)
            editor.changed.connect(self.propertiesChanged)
            self._ports_container.addWidget(editor)
    
    def refresh_port_displays(self):
        """Refresh all port editors to show updated assigned IPs."""
        for i in range(self._ports_container.count()):
            item = self._ports_container.itemAt(i)
            if item and item.widget():
                editor = item.widget()
                if isinstance(editor, PortEditor):
                    editor.refresh_from_model()
    
    def _update_type_specific_ui(self):
        if not self._node:
            return
        
        if self._node.node_type == NodeType.HOST:
            self._host_widget.show()
            self._is_server_check.blockSignals(True)
            self._is_server_check.setChecked(self._node.is_server)
            self._is_server_check.blockSignals(False)
            
        elif self._node.node_type == NodeType.ROUTER:
            self._router_widget.show()
            self._routing_combo.blockSignals(True)
            idx = self._routing_combo.findData(self._node.routing_protocol)
            self._routing_combo.setCurrentIndex(idx if idx >= 0 else 0)
            self._routing_combo.blockSignals(False)
            self._forwarding_check.blockSignals(True)
            self._forwarding_check.setChecked(self._node.forwarding_enabled)
            self._forwarding_check.blockSignals(False)
            
        elif self._node.node_type == NodeType.SWITCH:
            self._switch_widget.show()
            self._switch_mode_combo.blockSignals(True)
            idx = self._switch_mode_combo.findData(self._node.switching_mode)
            self._switch_mode_combo.setCurrentIndex(idx if idx >= 0 else 0)
            self._switch_mode_combo.blockSignals(False)
            self._stp_check.blockSignals(True)
            self._stp_check.setChecked(self._node.stp_enabled)
            self._stp_check.blockSignals(False)
            
            # Subnet configuration
            self._subnet_base_edit.blockSignals(True)
            self._subnet_base_edit.setText(self._node.subnet_base)
            self._subnet_base_edit.blockSignals(False)
            
            self._subnet_mask_combo.blockSignals(True)
            idx = self._subnet_mask_combo.findData(self._node.subnet_mask)
            self._subnet_mask_combo.setCurrentIndex(idx if idx >= 0 else 0)
            self._subnet_mask_combo.blockSignals(False)
        
        elif self._node.node_type in (NodeType.STATION, NodeType.ACCESS_POINT):
            self._wifi_widget.show()
            
            # WiFi Standard
            self._wifi_standard_combo.blockSignals(True)
            idx = self._wifi_standard_combo.findData(getattr(self._node, 'wifi_standard', '802.11n'))
            self._wifi_standard_combo.setCurrentIndex(idx if idx >= 0 else 2)  # Default to 802.11n
            self._wifi_standard_combo.blockSignals(False)
            
            # SSID
            self._wifi_ssid_edit.blockSignals(True)
            self._wifi_ssid_edit.setText(getattr(self._node, 'wifi_ssid', 'ns3-wifi'))
            self._wifi_ssid_edit.blockSignals(False)
            
            # Show/hide SSID based on node type (only AP really needs SSID)
            ssid_label = self._wifi_widget.layout().labelForField(self._wifi_ssid_edit)
            if ssid_label:
                ssid_label.setVisible(self._node.node_type == NodeType.ACCESS_POINT)
            self._wifi_ssid_edit.setVisible(self._node.node_type == NodeType.ACCESS_POINT)
            
            # Channel
            self._wifi_channel_spin.blockSignals(True)
            self._wifi_channel_spin.setValue(getattr(self._node, 'wifi_channel', 1))
            self._wifi_channel_spin.blockSignals(False)
            
            # Band
            self._wifi_band_combo.blockSignals(True)
            idx = self._wifi_band_combo.findData(getattr(self._node, 'wifi_band', '2.4GHz'))
            self._wifi_band_combo.setCurrentIndex(idx if idx >= 0 else 0)
            self._wifi_band_combo.blockSignals(False)
            
            # TX Power
            self._wifi_tx_power_spin.blockSignals(True)
            self._wifi_tx_power_spin.setValue(getattr(self._node, 'wifi_tx_power', 20.0))
            self._wifi_tx_power_spin.blockSignals(False)
    
    def _on_name_changed(self, text):
        if self._node:
            self._node.name = text
            self.propertiesChanged.emit()
    
    def _on_type_changed(self, index):
        if self._node:
            new_type = self._type_combo.currentData()
            if new_type != self._node.node_type:
                self._node.node_type = new_type
                self._update_type_specific_ui()
                self.nodeTypeChanged.emit(new_type)
                self.propertiesChanged.emit()
    
    def _on_medium_changed(self, index):
        if self._node:
            new_medium = self._medium_combo.currentData()
            if new_medium != getattr(self._node, 'medium_type', MediumType.WIRED):
                self._node.medium_type = new_medium
                self.mediumTypeChanged.emit(new_medium)
                self.propertiesChanged.emit()
    
    def _on_desc_changed(self, text):
        if self._node:
            self._node.description = text
            self.propertiesChanged.emit()
    
    def _on_host_prop_changed(self):
        if self._node and self._node.node_type == NodeType.HOST:
            self._node.is_server = self._is_server_check.isChecked()
            self.propertiesChanged.emit()
    
    def _on_router_prop_changed(self):
        if self._node and self._node.node_type == NodeType.ROUTER:
            self._node.routing_protocol = self._routing_combo.currentData()
            self._node.forwarding_enabled = self._forwarding_check.isChecked()
            self.propertiesChanged.emit()
    
    def _on_switch_prop_changed(self):
        if self._node and self._node.node_type == NodeType.SWITCH:
            self._node.switching_mode = self._switch_mode_combo.currentData()
            self._node.stp_enabled = self._stp_check.isChecked()
            self.propertiesChanged.emit()
    
    def _on_wifi_prop_changed(self):
        """Handle WiFi property changes."""
        if self._node and self._node.node_type in (NodeType.STATION, NodeType.ACCESS_POINT):
            self._node.wifi_standard = self._wifi_standard_combo.currentData()
            self._node.wifi_ssid = self._wifi_ssid_edit.text() or "ns3-wifi"
            self._node.wifi_channel = self._wifi_channel_spin.value()
            self._node.wifi_band = self._wifi_band_combo.currentData()
            self._node.wifi_tx_power = self._wifi_tx_power_spin.value()
            self.propertiesChanged.emit()
    
    def _update_app_attached_combo(self):
        """Update the attached node combo with available host nodes."""
        self._app_attached_combo.blockSignals(True)
        current_data = self._app_attached_combo.currentData()
        self._app_attached_combo.clear()
        self._app_attached_combo.addItem("(Not attached)", "")
        
        # Get network model to find host nodes
        # Walk up to find the main window and get the network
        parent = self.parent()
        while parent:
            if hasattr(parent, 'network'):
                network = parent.network
                for node_id, node in network.nodes.items():
                    # Only show hosts and stations as valid attachment points
                    if node.node_type in (NodeType.HOST, NodeType.STATION) and node_id != self._node.id:
                        self._app_attached_combo.addItem(f"{node.name} ({node.node_type.name})", node_id)
                break
            parent = parent.parent()
        
        # Restore selection
        if current_data:
            idx = self._app_attached_combo.findData(current_data)
            if idx >= 0:
                self._app_attached_combo.setCurrentIndex(idx)
        
        self._app_attached_combo.blockSignals(False)
    
    def _on_app_prop_changed(self):
        """Handle socket application property changes - deprecated, no longer used."""
        # APPLICATION node type has been removed - apps are now edited via double-click
        pass
    
    def _on_subnet_changed(self):
        if self._node and self._node.node_type == NodeType.SWITCH:
            self._node.subnet_base = self._subnet_base_edit.text()
            self._node.subnet_mask = self._subnet_mask_combo.currentData()
            self.propertiesChanged.emit()
    
    def _on_apply_subnet(self):
        """Apply subnet to all connected hosts."""
        if self._node and self._node.node_type == NodeType.SWITCH:
            if not self._node.subnet_base:
                return
            # Signal that we need to reassign IPs
            self.subnetApplied.emit(self._node.id)
            self._update_display()
            self.propertiesChanged.emit()
    
    def _on_edit_routing(self):
        """Open the routing table dialog for this node."""
        if not self._node:
            return
        
        if not self._network:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(
                self, 
                "Routing Editor", 
                "Network model not available. Cannot edit routing table."
            )
            return
        
        from views.routing_dialog import RoutingTableDialog
        
        dialog = RoutingTableDialog(self._node, self._network, self)
        dialog.routingChanged.connect(self.propertiesChanged.emit)
        dialog.exec()
    
    def _on_add_port(self):
        if self._node:
            self._node.add_port()
            self._update_display()
            self.propertiesChanged.emit()
    
    def highlight_port(self, port_id: str):
        """Highlight and expand a specific port editor."""
        import weakref
        from PyQt6.QtCore import QTimer
        
        # Find the port editor and expand it
        for i in range(self._ports_container.count()):
            item = self._ports_container.itemAt(i)
            if item and item.widget():
                editor = item.widget()
                if isinstance(editor, PortEditor) and editor.port.id == port_id:
                    # Expand this port
                    if not editor._is_expanded:
                        editor._toggle_expand()
                    # Highlight it
                    editor.setStyleSheet("""
                        QFrame {
                            background: #FEF3C7;
                            border: 2px solid #F59E0B;
                            border-radius: 6px;
                        }
                    """)
                    # Reset highlight after delay - use weak reference
                    weak_editor = weakref.ref(editor)
                    def reset_style():
                        try:
                            widget = weak_editor()
                            if widget is not None:
                                widget.setStyleSheet("""
                                    QFrame {
                                        background: #F9FAFB;
                                        border: 1px solid #E5E7EB;
                                        border-radius: 6px;
                                    }
                                """)
                        except (RuntimeError, ReferenceError):
                            pass  # Widget was deleted, ignore
                    QTimer.singleShot(2000, reset_style)
                    break


class LinkPropertiesWidget(QWidget):
    """Properties editor for a link with port information."""
    
    propertiesChanged = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._link: Optional[LinkModel] = None
        self._network_model = None
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        layout.addWidget(SectionHeader("Link Properties"))
        
        form = QFormLayout()
        form.setContentsMargins(0, 8, 0, 16)
        form.setSpacing(2)
        
        # Channel type
        self._type_combo = QComboBox()
        self._type_combo.addItem("Point-to-Point", ChannelType.POINT_TO_POINT)
        self._type_combo.addItem("CSMA (Ethernet)", ChannelType.CSMA)
        self._type_combo.currentIndexChanged.connect(self._on_type_changed)
        self._type_combo.setStyleSheet(input_style())
        form.addRow("Type:", self._type_combo)
        
        # Data rate
        self._rate_edit = QLineEdit()
        self._rate_edit.setPlaceholderText("e.g., 100Mbps")
        self._rate_edit.textChanged.connect(self._on_rate_changed)
        self._rate_edit.setStyleSheet(input_style())
        form.addRow("Data Rate:", self._rate_edit)
        
        # Delay
        self._delay_edit = QLineEdit()
        self._delay_edit.setPlaceholderText("e.g., 2ms")
        self._delay_edit.textChanged.connect(self._on_delay_changed)
        self._delay_edit.setStyleSheet(input_style())
        form.addRow("Delay:", self._delay_edit)
        
        # ID
        self._id_label = QLabel()
        self._id_label.setStyleSheet("color: #9CA3AF; font-family: monospace; font-size: 11px;")
        form.addRow("ID:", self._id_label)
        
        layout.addLayout(form)
        
        # Endpoints section
        layout.addWidget(SectionHeader("Port Connections"))
        
        self._endpoints_container = QVBoxLayout()
        self._endpoints_container.setContentsMargins(0, 8, 0, 0)
        self._endpoints_container.setSpacing(2)
        layout.addLayout(self._endpoints_container)
        
        layout.addStretch()
    
    def set_link(self, link: Optional[LinkModel], network_model=None):
        self._link = link
        self._network_model = network_model
        self._update_display()
    
    def _update_display(self):
        while self._endpoints_container.count():
            item = self._endpoints_container.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        if not self._link:
            self._type_combo.setCurrentIndex(0)
            self._rate_edit.clear()
            self._delay_edit.clear()
            self._id_label.clear()
            return
        
        self._type_combo.blockSignals(True)
        idx = self._type_combo.findData(self._link.channel_type)
        self._type_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self._type_combo.blockSignals(False)
        
        self._rate_edit.blockSignals(True)
        self._rate_edit.setText(self._link.data_rate)
        self._rate_edit.blockSignals(False)
        
        self._delay_edit.blockSignals(True)
        self._delay_edit.setText(self._link.delay)
        self._delay_edit.blockSignals(False)
        
        self._id_label.setText(self._link.id)
        
        # Add endpoint widgets
        if self._network_model:
            source = self._network_model.get_node(self._link.source_node_id)
            target = self._network_model.get_node(self._link.target_node_id)
            
            if source:
                source_port = source.get_port(self._link.source_port_id)
                self._add_endpoint_widget(source, source_port, "Source")
            if target:
                target_port = target.get_port(self._link.target_port_id)
                self._add_endpoint_widget(target, target_port, "Target")
    
    def _add_endpoint_widget(self, node, port, role: str):
        frame = QFrame()
        frame.setStyleSheet("""
            QFrame {
                background: #F9FAFB;
                border: 1px solid #E5E7EB;
                border-radius: 6px;
            }
        """)
        
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(2)
        
        # Header
        header = QLabel(f"{role}: {node.name}")
        header.setStyleSheet("font-weight: 600; color: #374151;")
        layout.addWidget(header)
        
        # Node type
        type_label = QLabel(f"Type: {node.node_type.name.title()}")
        type_label.setStyleSheet("color: #6B7280; font-size: 11px;")
        layout.addWidget(type_label)
        
        if port:
            # Port info
            port_label = QLabel(f"Port: {port.display_name} ({port.speed})")
            port_label.setStyleSheet("color: #374151; font-size: 11px;")
            layout.addWidget(port_label)
            
            # IP
            if port.ip_address:
                ip_label = QLabel(f"IP: {port.ip_address}/{port.netmask.split('.')[-1]}")
                ip_label.setStyleSheet("color: #374151; font-family: monospace; font-size: 11px;")
                layout.addWidget(ip_label)
        
        self._endpoints_container.addWidget(frame)
    
    def _on_type_changed(self, idx):
        if self._link:
            self._link.channel_type = self._type_combo.currentData()
            self.propertiesChanged.emit()
    
    def _on_rate_changed(self, text):
        if self._link:
            self._link.data_rate = text
            self.propertiesChanged.emit()
    
    def _on_delay_changed(self, text):
        if self._link:
            self._link.delay = text
            self.propertiesChanged.emit()


class PropertyPanel(QWidget):
    """Main property panel that switches between node and link editors."""
    
    propertiesChanged = pyqtSignal(str)  # node_id (or empty string for links)
    nodeTypeChanged = pyqtSignal(str, object)
    mediumTypeChanged = pyqtSignal(str, object)  # (node_id, new_medium_type)
    subnetApplied = pyqtSignal(str)  # switch_id when subnet should be applied
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._network_model = None
        self._current_node_id = None
        self._setup_ui()
    
    def _setup_ui(self):
        self.setMinimumWidth(300)
        self.setMaximumWidth(400)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(0)
        
        # Title
        title = QLabel("Properties")
        title_font = QFont("SF Pro Display", 14)
        title_font.setWeight(QFont.Weight.Bold)
        title.setFont(title_font)
        title.setStyleSheet("color: #111827; padding-bottom: 12px;")
        layout.addWidget(title)
        
        # Scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("""
            QScrollArea { background: transparent; }
            QScrollBar:vertical {
                background: #F3F4F6;
                width: 8px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical {
                background: #D1D5DB;
                border-radius: 4px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background: #9CA3AF;
            }
        """)
        
        self._content = QWidget()
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        
        self._node_props = NodePropertiesWidget()
        self._node_props.propertiesChanged.connect(self._on_node_properties_changed)
        self._node_props.nodeTypeChanged.connect(self._on_node_type_changed)
        self._node_props.mediumTypeChanged.connect(self._on_medium_type_changed)
        self._node_props.subnetApplied.connect(self.subnetApplied)
        self._node_props.hide()
        self._content_layout.addWidget(self._node_props)
        
        self._link_props = LinkPropertiesWidget()
        self._link_props.propertiesChanged.connect(self._on_link_properties_changed)
        self._link_props.hide()
        self._content_layout.addWidget(self._link_props)
        
        self._empty_label = QLabel("Select a node or link\nto view and edit properties")
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setStyleSheet("color: #9CA3AF; font-size: 13px; padding: 4px 2px;")
        self._content_layout.addWidget(self._empty_label)
        
        self._content_layout.addStretch()
        
        scroll.setWidget(self._content)
        layout.addWidget(scroll)
    
    def set_network_model(self, model):
        self._network_model = model
        self._node_props.set_network(model)
    
    def set_selection(self, item: Optional[Union[NodeModel, LinkModel]]):
        self._node_props.hide()
        self._link_props.hide()
        self._empty_label.hide()
        
        if item is None:
            self._empty_label.show()
            self._node_props.set_node(None)
            self._link_props.set_link(None)
            self._current_node_id = None
        elif isinstance(item, NodeModel):
            self._current_node_id = item.id
            self._node_props.set_node(item)
            self._node_props.show()
        elif isinstance(item, LinkModel):
            self._current_node_id = None
            self._link_props.set_link(item, self._network_model)
            self._link_props.show()
    
    def _on_node_type_changed(self, new_type):
        if self._current_node_id:
            self.nodeTypeChanged.emit(self._current_node_id, new_type)
    
    def _on_medium_type_changed(self, new_medium):
        if self._current_node_id:
            self.mediumTypeChanged.emit(self._current_node_id, new_medium)
    
    def _on_node_properties_changed(self):
        """Forward node properties changed with node ID."""
        node_id = self._current_node_id or ""
        self.propertiesChanged.emit(node_id)
    
    def _on_link_properties_changed(self):
        """Forward link properties changed (empty node_id)."""
        self.propertiesChanged.emit("")
    
    def scroll_to_port(self, port_id: str):
        """Scroll to and highlight a specific port in the property panel."""
        if self._node_props.isVisible():
            self._node_props.highlight_port(port_id)
    
    def refresh(self):
        if self._node_props.isVisible():
            self._node_props._update_display()
        elif self._link_props.isVisible():
            self._link_props._update_display()
    
    def refresh_port_displays(self):
        """Refresh port editors to show updated assigned IPs without full rebuild."""
        if self._node_props.isVisible():
            self._node_props.refresh_port_displays()
