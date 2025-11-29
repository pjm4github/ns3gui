"""
Main application window.

Assembles all UI components and manages the application layout.
"""

import os
import sys
import tempfile
from pathlib import Path
from typing import Optional
from PyQt6.QtCore import Qt, QSettings
from PyQt6.QtGui import QFont, QAction, QKeySequence, QIcon
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QToolBar, QPushButton, QLabel, QSplitter,
    QStatusBar, QMessageBox, QFrame, QApplication,
    QDockWidget, QMenuBar, QMenu, QFileDialog,
    QDialog, QFormLayout, QLineEdit, QSpinBox,
    QDoubleSpinBox, QComboBox, QDialogButtonBox,
    QGroupBox, QListWidget, QListWidgetItem
)

from models import (
    NetworkModel, NodeModel, NodeType, PortConfig, 
    SimulationState, SimulationStatus, SimulationConfig,
    TrafficFlow, TrafficApplication, TrafficProtocol,
    SimulationResults
)
from views import TopologyCanvas, PropertyPanel, NodePalette, StatsPanel
from services import (
    ProjectManager, export_to_mininet,
    NS3ScriptGenerator, NS3SimulationManager, NS3Detector
)


class SimulationToolbar(QToolBar):
    """Toolbar with simulation controls."""
    
    def __init__(self, parent=None):
        super().__init__("Simulation", parent)
        self.setMovable(False)
        self._setup_ui()
    
    def _setup_ui(self):
        self.setStyleSheet("""
            QToolBar {
                background: #F9FAFB;
                border-bottom: 1px solid #E5E7EB;
                padding: 8px 16px;
                spacing: 8px;
            }
            QPushButton {
                padding: 8px 16px;
                border-radius: 6px;
                font-weight: 500;
                font-size: 13px;
            }
        """)
        
        # Run button
        self.run_btn = QPushButton("▶ Run")
        self.run_btn.setStyleSheet("""
            QPushButton {
                background: #10B981;
                color: white;
                border: none;
            }
            QPushButton:hover {
                background: #059669;
            }
            QPushButton:disabled {
                background: #9CA3AF;
            }
        """)
        self.addWidget(self.run_btn)
        
        # Stop button
        self.stop_btn = QPushButton("◼ Stop")
        self.stop_btn.setEnabled(False)
        self.stop_btn.setStyleSheet("""
            QPushButton {
                background: #EF4444;
                color: white;
                border: none;
            }
            QPushButton:hover {
                background: #DC2626;
            }
            QPushButton:disabled {
                background: #9CA3AF;
            }
        """)
        self.addWidget(self.stop_btn)
        
        self.addSeparator()
        
        # Clear button
        self.clear_btn = QPushButton("Clear Topology")
        self.clear_btn.setStyleSheet("""
            QPushButton {
                background: white;
                color: #374151;
                border: 1px solid #D1D5DB;
            }
            QPushButton:hover {
                background: #F3F4F6;
            }
        """)
        self.addWidget(self.clear_btn)
        
        # Spacer
        spacer = QWidget()
        spacer.setSizePolicy(
            spacer.sizePolicy().horizontalPolicy(),
            spacer.sizePolicy().verticalPolicy()
        )
        spacer.setMinimumWidth(0)
        from PyQt6.QtWidgets import QSizePolicy
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.addWidget(spacer)
        
        # Status label
        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("color: #6B7280; font-size: 12px;")
        self.addWidget(self.status_label)
    
    def set_running(self, running: bool):
        """Update button states for running/stopped."""
        self.run_btn.setEnabled(not running)
        self.stop_btn.setEnabled(running)
        self.clear_btn.setEnabled(not running)


class MainWindow(QMainWindow):
    """
    Main application window for ns-3 GUI.
    
    Layout:
    ┌─────────────────────────────────────────────────────┐
    │  Toolbar: [Run] [Stop] [Clear]           Status     │
    ├─────────────┬───────────────────────┬───────────────┤
    │             │                       │               │
    │   Node      │                       │   Property    │
    │   Palette   │   Topology Canvas     │   Panel       │
    │             │                       │               │
    │             │                       ├───────────────┤
    │             │                       │               │
    │             │                       │   Stats       │
    │             │                       │   Panel       │
    │             │                       │               │
    ├─────────────┴───────────────────────┴───────────────┤
    │  Status Bar                                         │
    └─────────────────────────────────────────────────────┘
    """
    
    def __init__(self):
        super().__init__()
        
        # Models
        self.network_model = NetworkModel()
        self.simulation_state = SimulationState()
        self.project_manager = ProjectManager()
        self.sim_config = SimulationConfig()
        
        # Simulation manager
        self.sim_manager = NS3SimulationManager()
        self._sim_output_dir = ""
        
        # Setup
        self._setup_window()
        self._setup_menu()
        self._setup_toolbar()
        self._setup_central_widget()
        self._setup_status_bar()
        self._connect_signals()
        self._connect_simulation_signals()
    
    def _setup_window(self):
        """Configure window properties."""
        self._update_window_title()
        self.setMinimumSize(1200, 800)
        self.resize(1400, 900)
        
        # Style
        self.setStyleSheet("""
            QMainWindow {
                background: #F3F4F6;
            }
            QSplitter::handle {
                background: #E5E7EB;
            }
            QSplitter::handle:horizontal {
                width: 1px;
            }
        """)
    
    def _update_window_title(self):
        """Update window title with current file name."""
        base_title = "ns-3 Network Simulator"
        if self.project_manager.has_file:
            filename = self.project_manager.current_file.name
            self.setWindowTitle(f"{filename} - {base_title}")
        else:
            self.setWindowTitle(f"Untitled - {base_title}")
    
    def _setup_menu(self):
        """Create menu bar."""
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu("&File")
        
        new_action = QAction("&New Topology", self)
        new_action.setShortcut(QKeySequence.StandardKey.New)
        new_action.triggered.connect(self._on_new_topology)
        file_menu.addAction(new_action)
        
        file_menu.addSeparator()
        
        open_action = QAction("&Open...", self)
        open_action.setShortcut(QKeySequence.StandardKey.Open)
        open_action.triggered.connect(self._on_open_file)
        file_menu.addAction(open_action)
        
        save_action = QAction("&Save", self)
        save_action.setShortcut(QKeySequence.StandardKey.Save)
        save_action.triggered.connect(self._on_save_file)
        file_menu.addAction(save_action)
        
        save_as_action = QAction("Save &As...", self)
        save_as_action.setShortcut(QKeySequence.StandardKey.SaveAs)
        save_as_action.triggered.connect(self._on_save_file_as)
        file_menu.addAction(save_as_action)
        
        file_menu.addSeparator()
        
        # Export submenu
        export_menu = file_menu.addMenu("&Export")
        
        export_mininet_action = QAction("Mininet Script (.py)", self)
        export_mininet_action.triggered.connect(self._on_export_mininet)
        export_menu.addAction(export_mininet_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction("E&xit", self)
        exit_action.setShortcut(QKeySequence.StandardKey.Quit)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # Edit menu
        edit_menu = menubar.addMenu("&Edit")
        
        delete_action = QAction("&Delete Selected", self)
        delete_action.setShortcut(QKeySequence.StandardKey.Delete)
        delete_action.triggered.connect(self._on_delete_selected)
        edit_menu.addAction(delete_action)
        
        select_all_action = QAction("Select &All", self)
        select_all_action.setShortcut(QKeySequence.StandardKey.SelectAll)
        select_all_action.triggered.connect(self._on_select_all)
        edit_menu.addAction(select_all_action)
        
        # View menu
        view_menu = menubar.addMenu("&View")
        
        fit_action = QAction("&Fit to Contents", self)
        fit_action.setShortcut("Ctrl+0")
        fit_action.triggered.connect(self._on_fit_contents)
        view_menu.addAction(fit_action)
        
        reset_view_action = QAction("&Reset View", self)
        reset_view_action.setShortcut("Ctrl+R")
        reset_view_action.triggered.connect(self._on_reset_view)
        view_menu.addAction(reset_view_action)
        
        # Help menu
        help_menu = menubar.addMenu("&Help")
        
        about_action = QAction("&About", self)
        about_action.triggered.connect(self._on_about)
        help_menu.addAction(about_action)
    
    def _setup_toolbar(self):
        """Create and add toolbar."""
        self.toolbar = SimulationToolbar()
        self.addToolBar(self.toolbar)
        
        # Connect toolbar buttons
        self.toolbar.run_btn.clicked.connect(self._on_run_simulation)
        self.toolbar.stop_btn.clicked.connect(self._on_stop_simulation)
        self.toolbar.clear_btn.clicked.connect(self._on_clear_topology)
    
    def _setup_central_widget(self):
        """Create the main layout with all panels."""
        central = QWidget()
        self.setCentralWidget(central)
        
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Main splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Left panel - Node palette
        self.node_palette = NodePalette()
        self.node_palette.setStyleSheet("""
            QWidget {
                background: white;
                border-right: 1px solid #E5E7EB;
            }
        """)
        splitter.addWidget(self.node_palette)
        
        # Center - Topology canvas
        self.canvas = TopologyCanvas(self.network_model)
        self.canvas.setStyleSheet("""
            QGraphicsView {
                border: none;
            }
        """)
        splitter.addWidget(self.canvas)
        
        # Right panel - Properties and Stats in vertical splitter
        right_splitter = QSplitter(Qt.Orientation.Vertical)
        right_splitter.setStyleSheet("""
            QSplitter {
                background: white;
                border-left: 1px solid #E5E7EB;
            }
            QSplitter::handle {
                background: #E5E7EB;
                height: 3px;
            }
            QSplitter::handle:hover {
                background: #D1D5DB;
            }
        """)
        
        # Property panel
        self.property_panel = PropertyPanel()
        self.property_panel.set_network_model(self.network_model)
        right_splitter.addWidget(self.property_panel)
        
        # Stats panel
        self.stats_panel = StatsPanel()
        self.stats_panel.connect_state(self.simulation_state)
        right_splitter.addWidget(self.stats_panel)
        
        # Set initial sizes for right splitter (property: 60%, stats: 40%)
        right_splitter.setSizes([350, 250])
        right_splitter.setStretchFactor(0, 1)
        right_splitter.setStretchFactor(1, 1)
        
        splitter.addWidget(right_splitter)
        
        # Set splitter sizes (left: 250, center: stretch, right: 300)
        splitter.setSizes([250, 800, 300])
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 0)
        
        layout.addWidget(splitter)
    
    def _setup_status_bar(self):
        """Create status bar."""
        status = QStatusBar()
        status.setStyleSheet("""
            QStatusBar {
                background: #F9FAFB;
                border-top: 1px solid #E5E7EB;
                padding: 4px 8px;
                color: #6B7280;
                font-size: 12px;
            }
        """)
        self.setStatusBar(status)
        
        # Node/link count
        self._count_label = QLabel("Nodes: 0  Links: 0")
        status.addWidget(self._count_label)
        
        # Spacer
        status.addWidget(QWidget(), 1)
        
        # Instructions
        self._instruction_label = QLabel("Click nodes to add • Right-drag to link • Scroll to zoom")
        status.addWidget(self._instruction_label)
    
    def _connect_signals(self):
        """Connect all signals."""
        # Node palette -> Canvas
        self.node_palette.nodeTypeSelected.connect(self._on_node_type_selected)
        
        # Canvas -> Property panel
        self.canvas.itemSelected.connect(self.property_panel.set_selection)
        self.canvas.portSelected.connect(self._on_port_selected)
        
        # Scene changes -> Status bar update
        self.canvas.topology_scene.nodeAdded.connect(self._update_counts)
        self.canvas.topology_scene.nodeRemoved.connect(self._update_counts)
        self.canvas.topology_scene.linkAdded.connect(self._update_counts)
        self.canvas.topology_scene.linkRemoved.connect(self._update_counts)
        
        # Property changes -> Canvas update
        self.property_panel.propertiesChanged.connect(self._on_properties_changed)
        
        # Node type change -> Canvas update
        self.property_panel.nodeTypeChanged.connect(self._on_node_type_changed)
        
        # Subnet applied -> Reassign IPs
        self.property_panel.subnetApplied.connect(self._on_subnet_applied)
        
        # Simulation state
        self.simulation_state.statusChanged.connect(self._on_simulation_status_changed)
    
    def _connect_simulation_signals(self):
        """Connect simulation manager signals."""
        self.sim_manager.simulationStarted.connect(self._on_simulation_started)
        self.sim_manager.simulationFinished.connect(self._on_simulation_finished)
        self.sim_manager.simulationError.connect(self._on_simulation_error)
        self.sim_manager.outputReceived.connect(self._on_simulation_output)
        self.sim_manager.progressUpdated.connect(self._on_simulation_progress)
    
    def _on_node_type_selected(self, node_type: NodeType):
        """Handle node type selection from palette."""
        item = self.canvas.add_node_at_center(node_type)
        self.statusBar().showMessage(f"Added {node_type.name.lower()}", 2000)
    
    def _on_port_selected(self, node_model: NodeModel, port: PortConfig):
        """Handle port selection from canvas."""
        # Set node selection in property panel
        self.property_panel.set_selection(node_model)
        # Scroll to and highlight the specific port
        self.property_panel.scroll_to_port(port.id)
        self.statusBar().showMessage(f"Selected port {port.display_name} on {node_model.name}", 2000)
    
    def _on_properties_changed(self):
        """Handle property changes."""
        # Update node labels if name changed
        selected = self.canvas.topology_scene.selectedItems()
        for item in selected:
            from views.topology_canvas import NodeGraphicsItem
            if isinstance(item, NodeGraphicsItem):
                item.update_label()
    
    def _on_node_type_changed(self, node_id: str, new_type: NodeType):
        """Handle node type change from property panel."""
        # Update the visual representation
        node_item = self.canvas.topology_scene.get_node_item(node_id)
        if node_item:
            node_item.update_appearance()
            node_item.update_label()
        self.statusBar().showMessage(f"Changed node type to {new_type.name.lower()}", 2000)
    
    def _on_subnet_applied(self, switch_id: str):
        """Handle subnet application to connected hosts."""
        self.network_model.reassign_switch_ips(switch_id)
        switch = self.network_model.get_node(switch_id)
        if switch:
            self.statusBar().showMessage(
                f"Applied subnet {switch.subnet_base} to connected hosts", 
                3000
            )
        # Refresh property panel to show updated IPs
        self.property_panel.refresh()
    
    def _update_counts(self):
        """Update node/link count in status bar."""
        num_nodes = len(self.network_model.nodes)
        num_links = len(self.network_model.links)
        self._count_label.setText(f"Nodes: {num_nodes}  Links: {num_links}")
    
    def _on_run_simulation(self):
        """Start simulation."""
        # Validate topology
        if len(self.network_model.nodes) < 2:
            QMessageBox.warning(
                self,
                "Cannot Run",
                "Please create at least 2 nodes and connect them with a link."
            )
            return
        
        if len(self.network_model.links) < 1:
            QMessageBox.warning(
                self,
                "Cannot Run", 
                "Please connect nodes with at least one link."
            )
            return
        
        # Check if ns-3 is available
        if not self.sim_manager.ns3_available:
            # Show configuration dialog
            self._show_ns3_config_dialog()
            return
        
        # Show simulation configuration dialog
        dialog = SimulationConfigDialog(self.network_model, self.sim_config, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        
        # Update config from dialog
        self.sim_config = dialog.get_config()
        
        # Generate ns-3 script
        self.simulation_state.status = SimulationStatus.BUILDING
        self.toolbar.set_running(True)
        self.statusBar().showMessage("Generating ns-3 script...")
        
        generator = NS3ScriptGenerator()
        
        # Create output directory
        self._sim_output_dir = tempfile.mkdtemp(prefix="ns3_gui_")
        
        try:
            script = generator.generate(
                self.network_model, 
                self.sim_config,
                self._sim_output_dir
            )
        except Exception as e:
            self.simulation_state.set_error(f"Script generation failed: {e}")
            self.toolbar.set_running(False)
            QMessageBox.critical(self, "Error", f"Failed to generate script:\n{e}")
            return
        
        # Start simulation
        self.simulation_state.status = SimulationStatus.RUNNING
        self.simulation_state.end_time = self.sim_config.duration
        self.stats_panel.reset()
        self.statusBar().showMessage("Running ns-3 simulation...")
        
        # Run simulation
        success = self.sim_manager.run_simulation(script, self._sim_output_dir)
        if not success:
            self.simulation_state.set_error("Failed to start simulation")
            self.toolbar.set_running(False)
    
    def _on_stop_simulation(self):
        """Stop simulation."""
        if self.sim_manager.is_running:
            self.sim_manager.stop_simulation()
        self.simulation_state.status = SimulationStatus.IDLE
        self.toolbar.set_running(False)
        self.statusBar().showMessage("Simulation stopped", 2000)
    
    def _on_simulation_started(self):
        """Handle simulation start."""
        self.statusBar().showMessage("Simulation running...")
    
    def _on_simulation_finished(self, results: SimulationResults):
        """Handle simulation completion."""
        self.toolbar.set_running(False)
        
        if results.success:
            self.simulation_state.status = SimulationStatus.COMPLETED
            self.simulation_state.set_results(results)
            self.statusBar().showMessage("Simulation completed successfully", 5000)
        else:
            self.simulation_state.set_error(results.error_message)
            self.statusBar().showMessage(f"Simulation failed: {results.error_message}", 5000)
    
    def _on_simulation_error(self, error_msg: str):
        """Handle simulation error."""
        self.toolbar.set_running(False)
        self.simulation_state.set_error(error_msg)
        QMessageBox.warning(self, "Simulation Error", error_msg)
    
    def _on_simulation_output(self, line: str):
        """Handle simulation output line."""
        self.stats_panel.append_console_line(line)
    
    def _on_simulation_progress(self, progress: int):
        """Handle simulation progress update."""
        # Estimate current time from progress
        current_time = (progress / 100.0) * self.sim_config.duration
        self.simulation_state.current_time = current_time
    
    def _show_ns3_config_dialog(self):
        """Show dialog to configure ns-3 path."""
        dialog = NS3PathDialog(self.sim_manager.ns3_path, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            path = dialog.get_path()
            if NS3Detector.validate_ns3_path(path):
                self.sim_manager.ns3_path = path
                QMessageBox.information(
                    self, 
                    "ns-3 Configured",
                    f"ns-3 found at: {path}\nVersion: {NS3Detector.get_ns3_version(path) or 'unknown'}"
                )
            else:
                QMessageBox.warning(self, "Invalid Path", "The specified path is not a valid ns-3 installation.")
    
    def _on_clear_topology(self):
        """Clear the topology after confirmation."""
        if len(self.network_model.nodes) == 0:
            return
        
        reply = QMessageBox.question(
            self,
            "Clear Topology",
            "Are you sure you want to clear the entire topology?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.canvas.topology_scene.clear_topology()
            self.property_panel.set_selection(None)
            self.stats_panel.reset()
            self._update_counts()
            self.statusBar().showMessage("Topology cleared", 2000)
    
    def _on_simulation_status_changed(self, status: SimulationStatus):
        """Handle simulation status changes."""
        status_text = {
            SimulationStatus.IDLE: "Ready",
            SimulationStatus.BUILDING: "Building simulation...",
            SimulationStatus.RUNNING: "Simulation running...",
            SimulationStatus.PAUSED: "Simulation paused",
            SimulationStatus.COMPLETED: "Simulation completed",
            SimulationStatus.ERROR: "Simulation error",
        }
        self.toolbar.status_label.setText(status_text.get(status, "Unknown"))
    
    def _on_new_topology(self):
        """Create new topology."""
        if len(self.network_model.nodes) > 0:
            reply = QMessageBox.question(
                self,
                "New Topology",
                "Discard current topology and create a new one?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
        
        self.canvas.topology_scene.clear_topology()
        self.property_panel.set_selection(None)
        self.stats_panel.reset()
        self._update_counts()
        self.project_manager._current_file = None
        self._update_window_title()
        self.statusBar().showMessage("New topology created", 2000)
    
    def _on_open_file(self):
        """Open a topology file."""
        filepath, _ = QFileDialog.getOpenFileName(
            self,
            "Open Topology",
            "",
            "NS-3 GUI Topology (*.json);;All Files (*)"
        )
        
        if not filepath:
            return
        
        # Clear current topology
        self.canvas.topology_scene.clear_topology()
        
        # Load the file
        loaded_network = self.project_manager.load(Path(filepath))
        
        if loaded_network is None:
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to load topology from:\n{filepath}"
            )
            return
        
        # Replace network model and rebuild canvas
        self.network_model = loaded_network
        self.property_panel.set_network_model(self.network_model)
        
        # Recreate visual items from loaded model
        self._rebuild_canvas_from_model()
        
        self._update_window_title()
        self._update_counts()
        self.statusBar().showMessage(f"Opened {Path(filepath).name}", 2000)
    
    def _rebuild_canvas_from_model(self):
        """Rebuild canvas graphics items from the network model."""
        scene = self.canvas.topology_scene
        scene.network_model = self.network_model
        
        # Create node graphics items
        from PyQt6.QtCore import QPointF
        from views.topology_canvas import NodeGraphicsItem, LinkGraphicsItem
        
        for node in self.network_model.nodes.values():
            item = NodeGraphicsItem(node)
            scene.addItem(item)
            scene._node_items[node.id] = item
        
        # Create link graphics items
        for link in self.network_model.links.values():
            source_item = scene._node_items.get(link.source_node_id)
            target_item = scene._node_items.get(link.target_node_id)
            
            if source_item and target_item:
                link_item = LinkGraphicsItem(link, source_item, target_item)
                scene.addItem(link_item)
                link_item.setZValue(-1)
                scene._link_items[link.id] = link_item
    
    def _on_save_file(self):
        """Save to current file or prompt for new file."""
        if self.project_manager.has_file:
            self._save_to_file(self.project_manager.current_file)
        else:
            self._on_save_file_as()
    
    def _on_save_file_as(self):
        """Save topology to a new file."""
        filepath, _ = QFileDialog.getSaveFileName(
            self,
            "Save Topology",
            "topology.json",
            "NS-3 GUI Topology (*.json);;All Files (*)"
        )
        
        if filepath:
            # Ensure .json extension
            if not filepath.endswith('.json'):
                filepath += '.json'
            self._save_to_file(Path(filepath))
    
    def _save_to_file(self, filepath: Path):
        """Save network model to the specified file."""
        if self.project_manager.save(self.network_model, filepath):
            self._update_window_title()
            self.statusBar().showMessage(f"Saved to {filepath.name}", 2000)
        else:
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to save topology to:\n{filepath}"
            )
    
    def _on_export_mininet(self):
        """Export topology as Mininet Python script."""
        if len(self.network_model.nodes) == 0:
            QMessageBox.warning(
                self,
                "Cannot Export",
                "Please create a topology before exporting."
            )
            return
        
        filepath, _ = QFileDialog.getSaveFileName(
            self,
            "Export Mininet Script",
            "topology_mininet.py",
            "Python Script (*.py);;All Files (*)"
        )
        
        if not filepath:
            return
        
        try:
            script = export_to_mininet(self.network_model)
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(script)
            self.statusBar().showMessage(f"Exported to {Path(filepath).name}", 2000)
        except Exception as e:
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to export Mininet script:\n{e}"
            )
    
    def _on_delete_selected(self):
        """Delete selected items."""
        self.canvas.topology_scene.delete_selected()
    
    def _on_select_all(self):
        """Select all items."""
        for item in self.canvas.topology_scene.items():
            from views.topology_canvas import NodeGraphicsItem, LinkGraphicsItem
            if isinstance(item, (NodeGraphicsItem, LinkGraphicsItem)):
                item.setSelected(True)
    
    def _on_fit_contents(self):
        """Fit view to contents."""
        self.canvas.fit_contents()
    
    def _on_reset_view(self):
        """Reset view to default."""
        self.canvas.reset_view()
    
    def _on_about(self):
        """Show about dialog."""
        ns3_status = "Not configured"
        if self.sim_manager.ns3_available:
            version = self.sim_manager.ns3_version or "unknown"
            ns3_status = f"Found (v{version})"
        
        QMessageBox.about(
            self,
            "About ns-3 GUI",
            "<h3>ns-3 Network Simulator GUI</h3>"
            "<p>A visual interface for the ns-3 discrete-event network simulator.</p>"
            "<p><b>Features:</b></p>"
            "<ul>"
            "<li>Visual topology editor</li>"
            "<li>Port-level network configuration</li>"
            "<li>ns-3 script generation</li>"
            "<li>Simulation execution and results</li>"
            "</ul>"
            f"<p><b>ns-3 Status:</b> {ns3_status}</p>"
        )


class NS3PathDialog(QDialog):
    """Dialog for configuring ns-3 installation path."""
    
    def __init__(self, current_path: str = "", parent=None):
        super().__init__(parent)
        self._path = current_path
        self._setup_ui()
    
    def _setup_ui(self):
        self.setWindowTitle("Configure ns-3 Path")
        self.setMinimumWidth(500)
        
        layout = QVBoxLayout(self)
        
        # Instructions
        info = QLabel(
            "Specify the path to your ns-3 installation.\n"
            "This should be the directory containing the 'ns3' or 'waf' script."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: #6B7280; margin-bottom: 12px;")
        layout.addWidget(info)
        
        # Path input
        path_layout = QHBoxLayout()
        
        self._path_edit = QLineEdit(self._path)
        self._path_edit.setPlaceholderText("/path/to/ns-3")
        path_layout.addWidget(self._path_edit)
        
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse)
        path_layout.addWidget(browse_btn)
        
        layout.addLayout(path_layout)
        
        # Auto-detect button
        detect_btn = QPushButton("Auto-detect ns-3")
        detect_btn.clicked.connect(self._auto_detect)
        layout.addWidget(detect_btn)
        
        # Status
        self._status_label = QLabel()
        self._status_label.setStyleSheet("color: #6B7280; font-size: 11px;")
        layout.addWidget(self._status_label)
        
        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        
        # Validate current path
        self._validate_path()
        self._path_edit.textChanged.connect(self._validate_path)
    
    def _browse(self):
        """Browse for ns-3 directory."""
        path = QFileDialog.getExistingDirectory(
            self, "Select ns-3 Directory", self._path_edit.text()
        )
        if path:
            self._path_edit.setText(path)
    
    def _auto_detect(self):
        """Try to auto-detect ns-3."""
        path = NS3Detector.find_ns3_path()
        if path:
            self._path_edit.setText(path)
            self._status_label.setText(f"✓ Found ns-3 at: {path}")
            self._status_label.setStyleSheet("color: #10B981; font-size: 11px;")
        else:
            self._status_label.setText("✗ Could not auto-detect ns-3 installation")
            self._status_label.setStyleSheet("color: #EF4444; font-size: 11px;")
    
    def _validate_path(self):
        """Validate the current path."""
        path = self._path_edit.text()
        if not path:
            self._status_label.setText("")
            return
        
        if NS3Detector.validate_ns3_path(path):
            version = NS3Detector.get_ns3_version(path) or "unknown"
            self._status_label.setText(f"✓ Valid ns-3 installation (version: {version})")
            self._status_label.setStyleSheet("color: #10B981; font-size: 11px;")
        else:
            self._status_label.setText("✗ Not a valid ns-3 installation")
            self._status_label.setStyleSheet("color: #EF4444; font-size: 11px;")
    
    def get_path(self) -> str:
        """Get the configured path."""
        return self._path_edit.text()


class SimulationConfigDialog(QDialog):
    """Dialog for configuring simulation parameters."""
    
    def __init__(self, network: NetworkModel, config: SimulationConfig, parent=None):
        super().__init__(parent)
        self._network = network
        self._config = config
        self._setup_ui()
    
    def _setup_ui(self):
        self.setWindowTitle("Simulation Configuration")
        self.setMinimumWidth(600)
        self.setMinimumHeight(500)
        
        layout = QVBoxLayout(self)
        
        # General settings
        general_group = QGroupBox("General Settings")
        general_layout = QFormLayout(general_group)
        
        self._duration_spin = QDoubleSpinBox()
        self._duration_spin.setRange(1.0, 3600.0)
        self._duration_spin.setValue(self._config.duration)
        self._duration_spin.setSuffix(" seconds")
        general_layout.addRow("Duration:", self._duration_spin)
        
        self._seed_spin = QSpinBox()
        self._seed_spin.setRange(1, 999999)
        self._seed_spin.setValue(self._config.random_seed)
        general_layout.addRow("Random Seed:", self._seed_spin)
        
        layout.addWidget(general_group)
        
        # Traffic flows
        flows_group = QGroupBox("Traffic Flows")
        flows_layout = QVBoxLayout(flows_group)
        
        # Flow list
        self._flow_list = QListWidget()
        self._flow_list.setMinimumHeight(150)
        self._update_flow_list()
        flows_layout.addWidget(self._flow_list)
        
        # Flow buttons
        flow_btn_layout = QHBoxLayout()
        
        add_flow_btn = QPushButton("Add Flow")
        add_flow_btn.clicked.connect(self._add_flow)
        flow_btn_layout.addWidget(add_flow_btn)
        
        edit_flow_btn = QPushButton("Edit Flow")
        edit_flow_btn.clicked.connect(self._edit_flow)
        flow_btn_layout.addWidget(edit_flow_btn)
        
        remove_flow_btn = QPushButton("Remove Flow")
        remove_flow_btn.clicked.connect(self._remove_flow)
        flow_btn_layout.addWidget(remove_flow_btn)
        
        flow_btn_layout.addStretch()
        flows_layout.addLayout(flow_btn_layout)
        
        layout.addWidget(flows_group)
        
        # Output options
        output_group = QGroupBox("Output Options")
        output_layout = QVBoxLayout(output_group)
        
        from PyQt6.QtWidgets import QCheckBox
        
        self._flowmon_check = QCheckBox("Enable Flow Monitor (recommended)")
        self._flowmon_check.setChecked(self._config.enable_flow_monitor)
        output_layout.addWidget(self._flowmon_check)
        
        self._ascii_check = QCheckBox("Enable ASCII Trace")
        self._ascii_check.setChecked(self._config.enable_ascii_trace)
        output_layout.addWidget(self._ascii_check)
        
        self._pcap_check = QCheckBox("Enable PCAP Capture")
        self._pcap_check.setChecked(self._config.enable_pcap)
        output_layout.addWidget(self._pcap_check)
        
        layout.addWidget(output_group)
        
        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
    
    def _update_flow_list(self):
        """Update the flow list display."""
        self._flow_list.clear()
        for flow in self._config.flows:
            source = self._network.get_node(flow.source_node_id)
            target = self._network.get_node(flow.target_node_id)
            source_name = source.name if source else "?"
            target_name = target.name if target else "?"
            
            item = QListWidgetItem(
                f"{flow.name}: {source_name} → {target_name} "
                f"({flow.application.value}, {flow.protocol.value})"
            )
            item.setData(Qt.ItemDataRole.UserRole, flow.id)
            self._flow_list.addItem(item)
    
    def _add_flow(self):
        """Add a new traffic flow."""
        dialog = FlowEditorDialog(self._network, None, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            flow = dialog.get_flow()
            self._config.add_flow(flow)
            self._update_flow_list()
    
    def _edit_flow(self):
        """Edit selected flow."""
        item = self._flow_list.currentItem()
        if not item:
            return
        
        flow_id = item.data(Qt.ItemDataRole.UserRole)
        flow = self._config.get_flow(flow_id)
        if not flow:
            return
        
        dialog = FlowEditorDialog(self._network, flow, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            updated = dialog.get_flow()
            # Update flow in place
            idx = next(i for i, f in enumerate(self._config.flows) if f.id == flow_id)
            self._config.flows[idx] = updated
            self._update_flow_list()
    
    def _remove_flow(self):
        """Remove selected flow."""
        item = self._flow_list.currentItem()
        if not item:
            return
        
        flow_id = item.data(Qt.ItemDataRole.UserRole)
        self._config.remove_flow(flow_id)
        self._update_flow_list()
    
    def get_config(self) -> SimulationConfig:
        """Get the updated configuration."""
        self._config.duration = self._duration_spin.value()
        self._config.random_seed = self._seed_spin.value()
        self._config.enable_flow_monitor = self._flowmon_check.isChecked()
        self._config.enable_ascii_trace = self._ascii_check.isChecked()
        self._config.enable_pcap = self._pcap_check.isChecked()
        return self._config


class FlowEditorDialog(QDialog):
    """Dialog for editing a traffic flow."""
    
    def __init__(self, network: NetworkModel, flow: Optional[TrafficFlow], parent=None):
        super().__init__(parent)
        self._network = network
        self._flow = flow or TrafficFlow()
        self._setup_ui()
    
    def _setup_ui(self):
        self.setWindowTitle("Edit Traffic Flow" if self._flow.source_node_id else "Add Traffic Flow")
        self.setMinimumWidth(400)
        
        layout = QFormLayout(self)
        
        # Name
        self._name_edit = QLineEdit(self._flow.name)
        layout.addRow("Name:", self._name_edit)
        
        # Source node
        self._source_combo = QComboBox()
        for node_id, node in self._network.nodes.items():
            self._source_combo.addItem(f"{node.name} ({node.node_type.name})", node_id)
        
        if self._flow.source_node_id:
            idx = self._source_combo.findData(self._flow.source_node_id)
            if idx >= 0:
                self._source_combo.setCurrentIndex(idx)
        layout.addRow("Source Node:", self._source_combo)
        
        # Target node
        self._target_combo = QComboBox()
        for node_id, node in self._network.nodes.items():
            self._target_combo.addItem(f"{node.name} ({node.node_type.name})", node_id)
        
        if self._flow.target_node_id:
            idx = self._target_combo.findData(self._flow.target_node_id)
            if idx >= 0:
                self._target_combo.setCurrentIndex(idx)
        layout.addRow("Target Node:", self._target_combo)
        
        # Application type
        self._app_combo = QComboBox()
        self._app_combo.addItem("UDP Echo", TrafficApplication.ECHO)
        self._app_combo.addItem("On/Off (CBR)", TrafficApplication.ONOFF)
        self._app_combo.addItem("Bulk Send (TCP)", TrafficApplication.BULK_SEND)
        
        idx = self._app_combo.findData(self._flow.application)
        if idx >= 0:
            self._app_combo.setCurrentIndex(idx)
        layout.addRow("Application:", self._app_combo)
        
        # Protocol
        self._proto_combo = QComboBox()
        self._proto_combo.addItem("UDP", TrafficProtocol.UDP)
        self._proto_combo.addItem("TCP", TrafficProtocol.TCP)
        
        idx = self._proto_combo.findData(self._flow.protocol)
        if idx >= 0:
            self._proto_combo.setCurrentIndex(idx)
        layout.addRow("Protocol:", self._proto_combo)
        
        # Timing
        self._start_spin = QDoubleSpinBox()
        self._start_spin.setRange(0.0, 3600.0)
        self._start_spin.setValue(self._flow.start_time)
        self._start_spin.setSuffix(" s")
        layout.addRow("Start Time:", self._start_spin)
        
        self._stop_spin = QDoubleSpinBox()
        self._stop_spin.setRange(0.1, 3600.0)
        self._stop_spin.setValue(self._flow.stop_time)
        self._stop_spin.setSuffix(" s")
        layout.addRow("Stop Time:", self._stop_spin)
        
        # Echo-specific settings
        self._packets_spin = QSpinBox()
        self._packets_spin.setRange(1, 100000)
        self._packets_spin.setValue(self._flow.echo_packets)
        layout.addRow("Packets:", self._packets_spin)
        
        self._interval_spin = QDoubleSpinBox()
        self._interval_spin.setRange(0.001, 60.0)
        self._interval_spin.setValue(self._flow.echo_interval)
        self._interval_spin.setSuffix(" s")
        layout.addRow("Interval:", self._interval_spin)
        
        self._size_spin = QSpinBox()
        self._size_spin.setRange(1, 65535)
        self._size_spin.setValue(self._flow.packet_size)
        self._size_spin.setSuffix(" bytes")
        layout.addRow("Packet Size:", self._size_spin)
        
        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)
    
    def get_flow(self) -> TrafficFlow:
        """Get the configured flow."""
        self._flow.name = self._name_edit.text() or f"flow_{self._flow.id[:4]}"
        self._flow.source_node_id = self._source_combo.currentData()
        self._flow.target_node_id = self._target_combo.currentData()
        self._flow.application = self._app_combo.currentData()
        self._flow.protocol = self._proto_combo.currentData()
        self._flow.start_time = self._start_spin.value()
        self._flow.stop_time = self._stop_spin.value()
        self._flow.echo_packets = self._packets_spin.value()
        self._flow.echo_interval = self._interval_spin.value()
        self._flow.packet_size = self._size_spin.value()
        return self._flow
