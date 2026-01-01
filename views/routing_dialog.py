"""
Routing Table Dialog.

Dialog for viewing and editing routing tables on nodes.
"""

from typing import Optional, List, Tuple
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QColor, QIntValidator
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QComboBox,
    QLineEdit, QSpinBox, QGroupBox, QRadioButton, QButtonGroup,
    QMessageBox, QFrame, QWidget, QCheckBox, QSplitter
)

from models import (
    NodeModel, NetworkModel, NodeType, LinkModel,
    RoutingMode, RouteType, RouteEntry
)


class RoutingTableDialog(QDialog):
    """Dialog for editing a node's routing table."""
    
    routingChanged = pyqtSignal()  # Emitted when routing is modified
    
    def __init__(self, node: NodeModel, network: NetworkModel, parent=None):
        super().__init__(parent)
        self._node = node
        self._network = network
        self._connected_networks: List[Tuple[str, int, int, str]] = []  # (network, prefix, interface, link_id)
        
        self.setWindowTitle(f"Routing Table - {node.name}")
        self.setMinimumSize(700, 500)
        self._setup_ui()
        self._load_data()
    
    def _setup_ui(self):
        """Set up the dialog UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        
        # Header
        header = QLabel(f"Configure routing for {self._node.name}")
        header.setFont(QFont("SF Pro Display", 14, QFont.Weight.Bold))
        layout.addWidget(header)
        
        # Routing Mode Selection
        mode_group = QGroupBox("Routing Mode")
        mode_layout = QHBoxLayout(mode_group)
        
        self._mode_button_group = QButtonGroup(self)
        
        self._auto_radio = QRadioButton("Automatic (Global Routing)")
        self._auto_radio.setToolTip("ns-3 automatically computes shortest path routes")
        self._mode_button_group.addButton(self._auto_radio, 0)
        mode_layout.addWidget(self._auto_radio)
        
        self._manual_radio = QRadioButton("Manual (Static Routes)")
        self._manual_radio.setToolTip("Configure routes manually")
        self._mode_button_group.addButton(self._manual_radio, 1)
        mode_layout.addWidget(self._manual_radio)
        
        mode_layout.addStretch()
        layout.addWidget(mode_group)
        
        # Connect mode change
        self._mode_button_group.buttonClicked.connect(self._on_mode_changed)
        
        # Splitter for connected networks and routing table
        splitter = QSplitter(Qt.Orientation.Vertical)
        
        # Connected Networks (read-only, auto-detected)
        connected_group = QGroupBox("Connected Networks (Auto-detected)")
        connected_layout = QVBoxLayout(connected_group)
        
        self._connected_table = QTableWidget()
        self._connected_table.setColumnCount(4)
        self._connected_table.setHorizontalHeaderLabels(["Network", "Interface", "IP Address", "Link To"])
        self._connected_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._connected_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._connected_table.setAlternatingRowColors(True)
        self._connected_table.setMaximumHeight(120)
        
        header = self._connected_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        
        connected_layout.addWidget(self._connected_table)
        splitter.addWidget(connected_group)
        
        # Routing Table (editable)
        routes_group = QGroupBox("Routing Table")
        routes_layout = QVBoxLayout(routes_group)
        
        # Routing table
        self._routes_table = QTableWidget()
        self._routes_table.setColumnCount(7)
        self._routes_table.setHorizontalHeaderLabels([
            "Enabled", "Destination", "Prefix", "Gateway", "Interface", "Metric", "Type"
        ])
        self._routes_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._routes_table.setAlternatingRowColors(True)
        
        header = self._routes_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)
        
        routes_layout.addWidget(self._routes_table)
        
        # Route buttons
        route_btn_layout = QHBoxLayout()
        
        self._add_route_btn = QPushButton("Add Route")
        self._add_route_btn.clicked.connect(self._add_route)
        route_btn_layout.addWidget(self._add_route_btn)
        
        self._edit_route_btn = QPushButton("Edit Route")
        self._edit_route_btn.clicked.connect(self._edit_route)
        route_btn_layout.addWidget(self._edit_route_btn)
        
        self._delete_route_btn = QPushButton("Delete Route")
        self._delete_route_btn.clicked.connect(self._delete_route)
        route_btn_layout.addWidget(self._delete_route_btn)
        
        route_btn_layout.addStretch()
        
        self._auto_fill_btn = QPushButton("Auto-Fill Routes")
        self._auto_fill_btn.setToolTip("Generate routes based on network topology")
        self._auto_fill_btn.clicked.connect(self._auto_fill_routes)
        route_btn_layout.addWidget(self._auto_fill_btn)
        
        self._clear_routes_btn = QPushButton("Clear All")
        self._clear_routes_btn.clicked.connect(self._clear_routes)
        route_btn_layout.addWidget(self._clear_routes_btn)
        
        routes_layout.addLayout(route_btn_layout)
        splitter.addWidget(routes_group)
        
        layout.addWidget(splitter)
        
        # Default Gateway shortcut for hosts
        if self._node.node_type == NodeType.HOST:
            gw_group = QGroupBox("Default Gateway (Shortcut)")
            gw_layout = QHBoxLayout(gw_group)
            
            gw_layout.addWidget(QLabel("Gateway IP:"))
            self._default_gw_edit = QLineEdit()
            self._default_gw_edit.setPlaceholderText("e.g., 10.1.1.2")
            self._default_gw_edit.textChanged.connect(self._on_default_gw_changed)
            gw_layout.addWidget(self._default_gw_edit)
            
            gw_layout.addStretch()
            layout.addWidget(gw_group)
        
        # Dialog buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        
        ok_btn = QPushButton("OK")
        ok_btn.setDefault(True)
        ok_btn.clicked.connect(self._save_and_close)
        btn_layout.addWidget(ok_btn)
        
        layout.addLayout(btn_layout)
        
        # Apply styles
        self._apply_styles()
    
    def _apply_styles(self):
        """Apply consistent styling."""
        self.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 1px solid #E5E7EB;
                border-radius: 6px;
                margin-top: 2px;
                padding-top: 8px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
            QTableWidget {
                border: 1px solid #E5E7EB;
                border-radius: 4px;
                gridline-color: #F3F4F6;
            }
            QTableWidget::item {
                padding: 4px;
            }
            QHeaderView::section {
                background: #F9FAFB;
                border: none;
                border-bottom: 1px solid #E5E7EB;
                padding: 6px;
                font-weight: 600;
            }
            QPushButton {
                background: #3B82F6;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 2px 4px;
                font-weight: 500;
            }
            QPushButton:hover {
                background: #2563EB;
            }
            QPushButton:disabled {
                background: #9CA3AF;
            }
            QLineEdit, QSpinBox, QComboBox {
                border: 1px solid #D1D5DB;
                border-radius: 4px;
                padding: 4px 8px;
            }
        """)
    
    def _load_data(self):
        """Load current routing data into the UI."""
        # Set routing mode
        if self._node.routing_mode == RoutingMode.AUTO:
            self._auto_radio.setChecked(True)
        else:
            self._manual_radio.setChecked(True)
        
        # Detect connected networks
        self._detect_connected_networks()
        self._populate_connected_table()
        
        # Load routing table
        self._populate_routes_table()
        
        # Load default gateway for hosts
        if self._node.node_type == NodeType.HOST:
            self._default_gw_edit.setText(self._node.default_gateway)
        
        # Update UI state
        self._update_ui_state()
    
    def _detect_connected_networks(self):
        """Detect directly connected networks from topology."""
        self._connected_networks.clear()
        
        interface_idx = 0
        for link_id, link in self._network.links.items():
            if link.source_node_id == self._node.id:
                # This node is the source
                other_node = self._network.nodes.get(link.target_node_id)
                other_name = other_node.name if other_node else "unknown"
                
                # Determine network based on link index
                link_idx = list(self._network.links.keys()).index(link_id)
                network = f"10.1.{link_idx + 1}.0"
                my_ip = f"10.1.{link_idx + 1}.1"
                
                self._connected_networks.append((network, 24, interface_idx, other_name, my_ip, link_id))
                interface_idx += 1
                
            elif link.target_node_id == self._node.id:
                # This node is the target
                other_node = self._network.nodes.get(link.source_node_id)
                other_name = other_node.name if other_node else "unknown"
                
                link_idx = list(self._network.links.keys()).index(link_id)
                network = f"10.1.{link_idx + 1}.0"
                my_ip = f"10.1.{link_idx + 1}.2"
                
                self._connected_networks.append((network, 24, interface_idx, other_name, my_ip, link_id))
                interface_idx += 1
    
    def _populate_connected_table(self):
        """Populate the connected networks table."""
        self._connected_table.setRowCount(len(self._connected_networks))
        
        for row, (network, prefix, iface, other_name, my_ip, _) in enumerate(self._connected_networks):
            self._connected_table.setItem(row, 0, QTableWidgetItem(f"{network}/{prefix}"))
            self._connected_table.setItem(row, 1, QTableWidgetItem(f"if{iface}"))
            self._connected_table.setItem(row, 2, QTableWidgetItem(my_ip))
            self._connected_table.setItem(row, 3, QTableWidgetItem(other_name))
    
    def _populate_routes_table(self):
        """Populate the routing table."""
        self._routes_table.setRowCount(len(self._node.routing_table))
        
        for row, route in enumerate(self._node.routing_table):
            # Store route ID in the row
            self._routes_table.setVerticalHeaderItem(row, QTableWidgetItem(route.id))
            
            # Enabled checkbox
            enabled_check = QCheckBox()
            enabled_check.setChecked(route.enabled)
            enabled_widget = QWidget()
            enabled_layout = QHBoxLayout(enabled_widget)
            enabled_layout.addWidget(enabled_check)
            enabled_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            enabled_layout.setContentsMargins(0, 0, 0, 0)
            self._routes_table.setCellWidget(row, 0, enabled_widget)
            
            # Destination
            self._routes_table.setItem(row, 1, QTableWidgetItem(route.destination))
            
            # Prefix
            self._routes_table.setItem(row, 2, QTableWidgetItem(f"/{route.prefix_length}"))
            
            # Gateway
            gw_display = "direct" if route.is_direct else route.gateway
            self._routes_table.setItem(row, 3, QTableWidgetItem(gw_display))
            
            # Interface
            self._routes_table.setItem(row, 4, QTableWidgetItem(f"if{route.interface}"))
            
            # Metric
            self._routes_table.setItem(row, 5, QTableWidgetItem(str(route.metric)))
            
            # Type
            type_item = QTableWidgetItem(route.route_type.name.lower())
            if route.route_type == RouteType.CONNECTED:
                type_item.setForeground(QColor("#059669"))  # Green
            elif route.route_type == RouteType.DEFAULT:
                type_item.setForeground(QColor("#2563EB"))  # Blue
            self._routes_table.setItem(row, 6, type_item)
    
    def _on_mode_changed(self):
        """Handle routing mode change."""
        self._update_ui_state()
    
    def _update_ui_state(self):
        """Update UI elements based on current state."""
        is_manual = self._manual_radio.isChecked()
        
        self._routes_table.setEnabled(is_manual)
        self._add_route_btn.setEnabled(is_manual)
        self._edit_route_btn.setEnabled(is_manual)
        self._delete_route_btn.setEnabled(is_manual)
        self._auto_fill_btn.setEnabled(is_manual)
        self._clear_routes_btn.setEnabled(is_manual)
        
        if hasattr(self, '_default_gw_edit'):
            self._default_gw_edit.setEnabled(is_manual)
    
    def _add_route(self):
        """Add a new route."""
        dialog = RouteEditDialog(
            route=None,
            connected_networks=self._connected_networks,
            parent=self
        )
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            route = dialog.get_route()
            self._node.routing_table.append(route)
            self._populate_routes_table()
    
    def _edit_route(self):
        """Edit the selected route."""
        row = self._routes_table.currentRow()
        if row < 0:
            QMessageBox.information(self, "Edit Route", "Please select a route to edit.")
            return
        
        if row >= len(self._node.routing_table):
            return
        
        route = self._node.routing_table[row]
        
        dialog = RouteEditDialog(
            route=route,
            connected_networks=self._connected_networks,
            parent=self
        )
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            updated_route = dialog.get_route()
            self._node.routing_table[row] = updated_route
            self._populate_routes_table()
    
    def _delete_route(self):
        """Delete the selected route."""
        row = self._routes_table.currentRow()
        if row < 0:
            QMessageBox.information(self, "Delete Route", "Please select a route to delete.")
            return
        
        if row >= len(self._node.routing_table):
            return
        
        route = self._node.routing_table[row]
        
        reply = QMessageBox.question(
            self,
            "Delete Route",
            f"Delete route to {route.cidr}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self._node.routing_table.pop(row)
            self._populate_routes_table()
    
    def _auto_fill_routes(self):
        """Automatically generate routes based on topology."""
        reply = QMessageBox.question(
            self,
            "Auto-Fill Routes",
            "This will add routes for all reachable networks.\n"
            "Existing routes will be preserved.\n\nContinue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply != QMessageBox.StandardButton.Yes:
            return
        
        # Add connected network routes
        existing_dests = {r.destination for r in self._node.routing_table}
        
        for network, prefix, iface, other_name, my_ip, link_id in self._connected_networks:
            if network not in existing_dests:
                self._node.routing_table.append(RouteEntry(
                    destination=network,
                    prefix_length=prefix,
                    gateway="0.0.0.0",
                    interface=iface,
                    route_type=RouteType.CONNECTED
                ))
        
        # For hosts, add default route through first router found
        if self._node.node_type == NodeType.HOST:
            if not self._node.has_default_route():
                # Find a connected router
                for network, prefix, iface, other_name, my_ip, link_id in self._connected_networks:
                    link = self._network.links.get(link_id)
                    if link:
                        # Find the other node
                        other_id = link.target_node_id if link.source_node_id == self._node.id else link.source_node_id
                        other_node = self._network.nodes.get(other_id)
                        
                        if other_node and other_node.node_type == NodeType.ROUTER:
                            # Determine router's IP on this link
                            link_idx = list(self._network.links.keys()).index(link_id)
                            if link.source_node_id == self._node.id:
                                router_ip = f"10.1.{link_idx + 1}.2"
                            else:
                                router_ip = f"10.1.{link_idx + 1}.1"
                            
                            self._node.routing_table.append(RouteEntry(
                                destination="0.0.0.0",
                                prefix_length=0,
                                gateway=router_ip,
                                interface=iface,
                                route_type=RouteType.DEFAULT
                            ))
                            self._node.default_gateway = router_ip
                            if hasattr(self, '_default_gw_edit'):
                                self._default_gw_edit.setText(router_ip)
                            break
        
        # For routers, add routes to all other networks through connected routers
        elif self._node.node_type == NodeType.ROUTER:
            # Find all networks in topology
            all_networks = set()
            for link_idx, (link_id, link) in enumerate(self._network.links.items()):
                network = f"10.1.{link_idx + 1}.0"
                all_networks.add((network, 24, link_idx))
            
            # Add routes to networks we're not directly connected to
            connected_network_addrs = {n[0] for n in self._connected_networks}
            
            for network, prefix, link_idx in all_networks:
                if network not in connected_network_addrs and network not in existing_dests:
                    # Find path through another router (simplified - just add route through first hop)
                    # In a real implementation, you'd compute actual paths
                    # For now, we'll just note these need manual configuration
                    pass
        
        self._populate_routes_table()
        QMessageBox.information(
            self,
            "Auto-Fill Complete",
            f"Added {len(self._node.routing_table)} routes.\n"
            "Review and edit as needed."
        )
    
    def _clear_routes(self):
        """Clear all routes."""
        reply = QMessageBox.question(
            self,
            "Clear Routes",
            "Clear all routes from the routing table?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self._node.routing_table.clear()
            self._populate_routes_table()
    
    def _on_default_gw_changed(self, text: str):
        """Handle default gateway text change."""
        # Will be saved when OK is clicked
        pass
    
    def _save_and_close(self):
        """Save changes and close dialog."""
        # Save routing mode
        self._node.routing_mode = RoutingMode.AUTO if self._auto_radio.isChecked() else RoutingMode.MANUAL
        
        # Save default gateway for hosts
        if self._node.node_type == NodeType.HOST and hasattr(self, '_default_gw_edit'):
            gw = self._default_gw_edit.text().strip()
            if gw and gw != self._node.default_gateway:
                self._node.set_default_gateway_route(gw, 0)
        
        # Update enabled state from checkboxes
        for row in range(self._routes_table.rowCount()):
            if row < len(self._node.routing_table):
                widget = self._routes_table.cellWidget(row, 0)
                if widget:
                    checkbox = widget.findChild(QCheckBox)
                    if checkbox:
                        self._node.routing_table[row].enabled = checkbox.isChecked()
        
        self.routingChanged.emit()
        self.accept()


class RouteEditDialog(QDialog):
    """Dialog for adding/editing a single route."""
    
    def __init__(self, route: Optional[RouteEntry], connected_networks: list, parent=None):
        super().__init__(parent)
        self._route = route
        self._connected_networks = connected_networks
        self._is_edit = route is not None
        
        self.setWindowTitle("Edit Route" if self._is_edit else "Add Route")
        self.setMinimumWidth(400)
        self._setup_ui()
        self._load_data()
    
    def _setup_ui(self):
        """Set up the dialog UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        
        # Destination
        dest_layout = QHBoxLayout()
        dest_layout.addWidget(QLabel("Destination:"))
        self._dest_edit = QLineEdit()
        self._dest_edit.setPlaceholderText("e.g., 10.1.2.0 or 0.0.0.0")
        dest_layout.addWidget(self._dest_edit)
        dest_layout.addWidget(QLabel("/"))
        self._prefix_spin = QSpinBox()
        self._prefix_spin.setRange(0, 32)
        self._prefix_spin.setValue(24)
        dest_layout.addWidget(self._prefix_spin)
        layout.addLayout(dest_layout)
        
        # Gateway
        gw_layout = QHBoxLayout()
        gw_layout.addWidget(QLabel("Gateway:"))
        self._gw_edit = QLineEdit()
        self._gw_edit.setPlaceholderText("e.g., 10.1.1.2 or 0.0.0.0 for direct")
        gw_layout.addWidget(self._gw_edit)
        
        self._direct_check = QCheckBox("Direct (no gateway)")
        self._direct_check.toggled.connect(self._on_direct_toggled)
        gw_layout.addWidget(self._direct_check)
        layout.addLayout(gw_layout)
        
        # Interface
        iface_layout = QHBoxLayout()
        iface_layout.addWidget(QLabel("Interface:"))
        self._iface_combo = QComboBox()
        for network, prefix, iface, other_name, my_ip, _ in self._connected_networks:
            self._iface_combo.addItem(f"if{iface} ({my_ip} -> {other_name})", iface)
        if self._iface_combo.count() == 0:
            self._iface_combo.addItem("if0", 0)
        iface_layout.addWidget(self._iface_combo)
        iface_layout.addStretch()
        layout.addLayout(iface_layout)
        
        # Metric
        metric_layout = QHBoxLayout()
        metric_layout.addWidget(QLabel("Metric:"))
        self._metric_spin = QSpinBox()
        self._metric_spin.setRange(1, 9999)
        self._metric_spin.setValue(1)
        metric_layout.addWidget(self._metric_spin)
        metric_layout.addStretch()
        layout.addLayout(metric_layout)
        
        # Route type
        type_layout = QHBoxLayout()
        type_layout.addWidget(QLabel("Type:"))
        self._type_combo = QComboBox()
        self._type_combo.addItem("Static", RouteType.STATIC)
        self._type_combo.addItem("Default", RouteType.DEFAULT)
        self._type_combo.addItem("Connected", RouteType.CONNECTED)
        type_layout.addWidget(self._type_combo)
        type_layout.addStretch()
        layout.addLayout(type_layout)
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        
        ok_btn = QPushButton("OK")
        ok_btn.setDefault(True)
        ok_btn.clicked.connect(self._validate_and_accept)
        btn_layout.addWidget(ok_btn)
        
        layout.addLayout(btn_layout)
    
    def _load_data(self):
        """Load route data if editing."""
        if self._route:
            self._dest_edit.setText(self._route.destination)
            self._prefix_spin.setValue(self._route.prefix_length)
            self._gw_edit.setText(self._route.gateway)
            self._direct_check.setChecked(self._route.is_direct)
            self._metric_spin.setValue(self._route.metric)
            
            # Set interface
            for i in range(self._iface_combo.count()):
                if self._iface_combo.itemData(i) == self._route.interface:
                    self._iface_combo.setCurrentIndex(i)
                    break
            
            # Set type
            for i in range(self._type_combo.count()):
                if self._type_combo.itemData(i) == self._route.route_type:
                    self._type_combo.setCurrentIndex(i)
                    break
    
    def _on_direct_toggled(self, checked: bool):
        """Handle direct checkbox toggle."""
        self._gw_edit.setEnabled(not checked)
        if checked:
            self._gw_edit.setText("0.0.0.0")
    
    def _validate_and_accept(self):
        """Validate input and accept dialog."""
        dest = self._dest_edit.text().strip()
        
        # Validate destination IP format
        if not self._is_valid_ip(dest):
            QMessageBox.warning(self, "Invalid Input", "Please enter a valid destination IP address.")
            return
        
        # Validate gateway if not direct
        if not self._direct_check.isChecked():
            gw = self._gw_edit.text().strip()
            if not self._is_valid_ip(gw):
                QMessageBox.warning(self, "Invalid Input", "Please enter a valid gateway IP address.")
                return
        
        self.accept()
    
    def _is_valid_ip(self, ip: str) -> bool:
        """Check if string is a valid IP address."""
        try:
            parts = ip.split('.')
            if len(parts) != 4:
                return False
            for part in parts:
                num = int(part)
                if num < 0 or num > 255:
                    return False
            return True
        except:
            return False
    
    def get_route(self) -> RouteEntry:
        """Get the configured route."""
        route_id = self._route.id if self._route else None
        
        return RouteEntry(
            id=route_id or str(__import__('uuid').uuid4())[:8],
            destination=self._dest_edit.text().strip(),
            prefix_length=self._prefix_spin.value(),
            gateway="0.0.0.0" if self._direct_check.isChecked() else self._gw_edit.text().strip(),
            interface=self._iface_combo.currentData() or 0,
            metric=self._metric_spin.value(),
            route_type=self._type_combo.currentData() or RouteType.STATIC,
            enabled=True
        )
