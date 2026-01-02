"""
Main application window.

Assembles all UI components and manages the application layout.
"""

import os
import sys
import tempfile
from pathlib import Path
from typing import Optional, List
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QAction, QKeySequence, QIcon
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QToolBar, QPushButton, QLabel, QSplitter,
    QStatusBar, QMessageBox, QFrame, QApplication,
    QDockWidget, QMenuBar, QMenu, QFileDialog,
    QDialog, QFormLayout, QLineEdit, QSpinBox,
    QDoubleSpinBox, QComboBox, QDialogButtonBox,
    QGroupBox, QListWidget, QListWidgetItem, QCheckBox,
    QTabWidget
)

from models import (
    NetworkModel, NodeModel, NodeType, PortConfig, 
    SimulationState, SimulationStatus, SimulationConfig,
    TrafficFlow, TrafficApplication, TrafficProtocol,
    SimulationResults, Project, ProjectManager as ProjectMgr,
    # Grid models
    GridNodeModel, GridNodeType, GridTrafficFlow, FailureScenario,
)
from views import TopologyCanvas, PropertyPanel, NodePalette, StatsPanel, PlaybackControls
from views.settings_dialog import SettingsDialog
from views.project_dialog import (
    NewProjectDialog, OpenProjectDialog, ProjectInfoDialog
)
# Grid GUI components
from views.grid_node_palette import CombinedNodePalette
from views.failure_scenario_panel import FailureScenarioPanel
from views.traffic_pattern_editor import TrafficPatternEditor
from views.metrics_dashboard import MetricsDashboard
from views.layout_debugger import LayoutDebugger, enable_layout_debugging

from services import (
    ProjectManager, export_to_mininet,
    NS3ScriptGenerator, NS3SimulationManager, NS3Detector,
    TracePlayer, PacketEvent, PacketEventType,
    get_settings, ShapeManager, get_shape_manager
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
                padding: 2px 4px;
                spacing: 2px;
            }
            QPushButton {
                padding: 2px 8px;
                border-radius: 4px;
                font-weight: 500;
                font-size: 12px;
            }
            QCheckBox {
                color: #374151;
                font-size: 12px;
                spacing: 2px;
            }
            QCheckBox::indicator {
                width: 14px;
                height: 14px;
                border-radius: 3px;
                border: 1px solid #D1D5DB;
                background: white;
            }
            QCheckBox::indicator:checked {
                background: #3B82F6;
                border-color: #3B82F6;
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
        
        # Preview checkbox
        from PyQt6.QtWidgets import QCheckBox
        self.preview_check = QCheckBox("Preview Code")
        self.preview_check.setToolTip("Preview and edit generated ns-3 script before running")
        self.addWidget(self.preview_check)
        
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
        
        self.addSeparator()
        
        # Simulation time display - always visible
        self._total_time = 10.0  # Default
        self._current_time = 0.0
        self._is_running = False
        self._is_completed = False
        
        self.time_label = QLabel("0.000 sec")
        self.time_label.setStyleSheet("""
            QLabel {
                color: #374151;
                font-size: 14px;
                font-weight: bold;
                font-family: 'Consolas', 'Monaco', monospace;
                padding: 2px 4px;
                background: #F3F4F6;
                border: 1px solid #D1D5DB;
                border-radius: 4px;
                min-width: 100px;
            }
        """)
        self.addWidget(self.time_label)
    
    def set_running(self, running: bool):
        """Update button states for running/stopped."""
        self.run_btn.setEnabled(not running)
        self.stop_btn.setEnabled(running)
        self.clear_btn.setEnabled(not running)
        self._is_running = running
        
        if running:
            self._is_completed = False
            self._current_time = 0.0
            self._update_time_display()
    
    def set_total_time(self, total_time: float):
        """Set the total simulation duration."""
        self._total_time = total_time
        self._update_time_display()
    
    def reset_time(self):
        """Reset time display for a new simulation."""
        self._current_time = 0.0
        self._is_completed = False
        self._update_time_display()
    
    def update_simulation_time(self, current_time: float, total_time: float = None):
        """Update the simulation time display."""
        self._current_time = current_time
        if total_time is not None:
            self._total_time = total_time
        
        # Check if simulation completed
        if current_time >= self._total_time - 0.001:
            self._is_completed = True
        
        self._update_time_display()
    
    def _update_time_display(self):
        """Update the time label appearance based on state."""
        if self._is_completed:
            # Completed state - show end time with indicator
            text = f"{self._current_time:.3f} sec (end)"
            bg_color = "#DCFCE7"  # Light green
            text_color = "#166534"  # Dark green
            border_color = "#86EFAC"
        elif self._is_running:
            # Running state - show current time with progress color
            text = f"{self._current_time:.3f} sec"
            progress = self._current_time / self._total_time if self._total_time > 0 else 0
            if progress < 0.5:
                bg_color = "#DBEAFE"  # Light blue
                text_color = "#1E40AF"  # Dark blue
                border_color = "#93C5FD"
            else:
                bg_color = "#FEF3C7"  # Light amber
                text_color = "#92400E"  # Dark amber
                border_color = "#FCD34D"
        else:
            # Idle state
            text = f"{self._current_time:.3f} sec"
            bg_color = "#F3F4F6"  # Light gray
            text_color = "#374151"  # Dark gray
            border_color = "#D1D5DB"
        
        self.time_label.setText(text)
        self.time_label.setStyleSheet(f"""
            QLabel {{
                color: {text_color};
                font-size: 14px;
                font-weight: bold;
                font-family: 'Consolas', 'Monaco', monospace;
                padding: 2px 4px;
                background: {bg_color};
                border: 1px solid {border_color};
                border-radius: 4px;
                min-width: 100px;
            }}
        """)


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
        
        # Settings manager (JSON file based)
        self.settings_manager = get_settings()
        
        # Ensure workspace directories exist
        try:
            self.settings_manager.ensure_workspace()
        except Exception as e:
            print(f"Warning: Could not create workspace directories: {e}")
        
        # Models
        self.network_model = NetworkModel()
        self.simulation_state = SimulationState()
        self.project_manager = ProjectManager()  # Legacy file-based manager
        self.sim_config = SimulationConfig()
        
        # Project manager (new project-based workflow)
        workspace_root = self.settings_manager.paths.get_workspace_root()
        self.project_mgr = ProjectMgr(workspace_root)
        self.project_mgr.ensure_workspace()
        self._current_project: Optional[Project] = None
        
        # Simulation manager
        self.sim_manager = NS3SimulationManager()
        self._sim_output_dir = ""
        self._current_project_path = ""  # Path to current project file
        
        # Grid-specific models
        self.failure_scenario: Optional[FailureScenario] = None
        
        # Load saved ns-3 path from settings
        self._load_ns3_settings()
        
        # Initialize shape manager (loads default + user shapes)
        self.shape_manager = get_shape_manager()
        self.shape_manager.initialize()
        
        # Trace player for packet animation
        self.trace_player = TracePlayer()
        
        # Setup
        self._setup_window()
        self._setup_menu()
        self._setup_toolbar()
        self._setup_central_widget()
        self._setup_playback_controls()
        self._setup_status_bar()
        self._connect_signals()
        self._connect_simulation_signals()
        self._connect_trace_player_signals()
        
        # Restore window geometry
        self._load_window_settings()
        
        # Enable layout debugging (Ctrl+hover to identify widgets)
        self._setup_layout_debugger()
    
    def _load_ns3_settings(self):
        """Load saved ns-3 configuration from settings file."""
        s = self.settings_manager.settings.ns3
        if s.path:
            self.sim_manager.ns3_path = s.path
            self.sim_manager.use_wsl = s.use_wsl
            if self.sim_manager.ns3_available:
                print(f"Loaded ns-3 path: {s.path}")
            else:
                print(f"Saved ns-3 path invalid: {s.path}")
    
    def _save_ns3_settings(self):
        """Save ns-3 configuration to settings file."""
        s = self.settings_manager.settings.ns3
        s.path = self.sim_manager.ns3_path
        s.use_wsl = self.sim_manager.use_wsl
        self.settings_manager.save()
    
    def _load_window_settings(self):
        """Restore window geometry and state."""
        geometry, state = self.settings_manager.get_window_geometry()
        if geometry:
            self.restoreGeometry(geometry)
        if state:
            self.restoreState(state)
    
    def _save_window_settings(self):
        """Save window geometry and state."""
        self.settings_manager.save_window_geometry(
            self.saveGeometry(),
            self.saveState()
        )
    
    def closeEvent(self, event):
        """Handle window close - save settings."""
        self._save_window_settings()
        super().closeEvent(event)
    
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
        """Update window title with current project/file name."""
        base_title = "ns-3 Network Simulator"
        
        # Check if we have a project open
        if self._current_project:
            project_name = self._current_project.name
            self.setWindowTitle(f"{project_name} - {base_title}")
        elif self.project_manager.has_file:
            filename = self.project_manager.current_file.name
            self.setWindowTitle(f"{filename} - {base_title}")
        else:
            self.setWindowTitle(f"Untitled - {base_title}")
    
    def _setup_menu(self):
        """Create menu bar."""
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu("&File")
        
        # Project submenu
        project_menu = file_menu.addMenu("&Project")
        
        new_project_action = QAction("&New Project...", self)
        new_project_action.setShortcut("Ctrl+Shift+N")
        new_project_action.setStatusTip("Create a new project")
        new_project_action.triggered.connect(self._on_new_project)
        project_menu.addAction(new_project_action)
        
        open_project_action = QAction("&Open Project...", self)
        open_project_action.setShortcut("Ctrl+Shift+O")
        open_project_action.setStatusTip("Open an existing project")
        open_project_action.triggered.connect(self._on_open_project)
        project_menu.addAction(open_project_action)
        
        project_menu.addSeparator()
        
        project_info_action = QAction("Project &Info...", self)
        project_info_action.setStatusTip("View current project details")
        project_info_action.triggered.connect(self._on_project_info)
        project_menu.addAction(project_info_action)
        
        file_menu.addSeparator()
        
        new_action = QAction("&New Topology", self)
        new_action.setShortcut(QKeySequence.StandardKey.New)
        new_action.triggered.connect(self._on_new_topology)
        file_menu.addAction(new_action)
        
        file_menu.addSeparator()
        
        open_action = QAction("&Open...", self)
        open_action.setShortcut(QKeySequence.StandardKey.Open)
        open_action.triggered.connect(self._on_open_file)
        file_menu.addAction(open_action)
        
        # Import submenu
        import_menu = file_menu.addMenu("&Import")
        
        import_ns3_action = QAction("ns-3 Python Example...", self)
        import_ns3_action.setStatusTip("Import topology from an ns-3 Python example script")
        import_ns3_action.triggered.connect(self._on_import_ns3_example)
        import_menu.addAction(import_ns3_action)
        
        import_ns3_batch_action = QAction("Batch Import ns-3 Examples...", self)
        import_ns3_batch_action.setStatusTip("Import all Python examples from ns-3")
        import_ns3_batch_action.triggered.connect(self._on_import_ns3_batch)
        import_menu.addAction(import_ns3_batch_action)
        
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
        
        edit_menu.addSeparator()
        
        settings_action = QAction("&Settings...", self)
        settings_action.setShortcut("Ctrl+,")
        settings_action.triggered.connect(self._on_show_settings)
        edit_menu.addAction(settings_action)
        
        edit_menu.addSeparator()
        
        shape_manager_action = QAction("Shape &Manager...", self)
        shape_manager_action.triggered.connect(self._on_show_shape_manager)
        edit_menu.addAction(shape_manager_action)
        
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
        
        view_menu.addSeparator()
        
        # Route visualization submenu
        route_menu = view_menu.addMenu("&Routes")
        
        self._show_routes_action = QAction("Show &All Routes", self)
        self._show_routes_action.setCheckable(True)
        self._show_routes_action.setShortcut("Ctrl+Shift+R")
        self._show_routes_action.triggered.connect(self._on_toggle_show_routes)
        route_menu.addAction(self._show_routes_action)
        
        show_routes_from_action = QAction("Show Routes &From Selected Node", self)
        show_routes_from_action.triggered.connect(self._on_show_routes_from_selected)
        route_menu.addAction(show_routes_from_action)
        
        show_routes_to_action = QAction("Show Routes &To Selected Node", self)
        show_routes_to_action.triggered.connect(self._on_show_routes_to_selected)
        route_menu.addAction(show_routes_to_action)
        
        clear_routes_action = QAction("&Clear Route Highlights", self)
        clear_routes_action.setShortcut("Escape")
        clear_routes_action.triggered.connect(self._on_clear_route_highlights)
        route_menu.addAction(clear_routes_action)
        
        # Simulation menu
        sim_menu = menubar.addMenu("&Simulation")
        
        run_action = QAction("&Run Simulation", self)
        run_action.setShortcut("F5")
        run_action.triggered.connect(self._on_run_simulation)
        sim_menu.addAction(run_action)
        
        stop_action = QAction("&Stop Simulation", self)
        stop_action.setShortcut("Shift+F5")
        stop_action.triggered.connect(self._on_stop_simulation)
        sim_menu.addAction(stop_action)
        
        sim_menu.addSeparator()
        
        ns3_config_action = QAction("Configure &ns-3 Path...", self)
        ns3_config_action.triggered.connect(self._show_ns3_config_dialog)
        sim_menu.addAction(ns3_config_action)
        
        # Help menu
        help_menu = menubar.addMenu("&Help")
        
        # ns-3 API Help
        ns3_help_action = QAction("ns-3 &Simulation Guide", self)
        ns3_help_action.setShortcut("F1")
        ns3_help_action.triggered.connect(self._on_show_help)
        help_menu.addAction(ns3_help_action)
        
        help_menu.addSeparator()
        
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
        """Create the main layout with all panels including Grid components."""
        central = QWidget()
        self.setCentralWidget(central)
        
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Main splitter (horizontal: left palette | center | right properties)
        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Left panel - Combined Node palette (standard + grid nodes)
        self.node_palette = CombinedNodePalette()
        self.node_palette.setStyleSheet("""
            QWidget {
                background: white;
                border-right: 1px solid #E5E7EB;
            }
        """)
        main_splitter.addWidget(self.node_palette)
        
        # Center - Canvas and bottom tabs in vertical splitter
        center_splitter = QSplitter(Qt.Orientation.Vertical)
        
        # Topology canvas
        self.canvas = TopologyCanvas(self.network_model)
        self.canvas.setStyleSheet("""
            QGraphicsView {
                border: none;
            }
        """)
        center_splitter.addWidget(self.canvas)
        
        # Bottom tabs: Traffic, Failures, Metrics
        self.bottom_tabs = QTabWidget()
        self.bottom_tabs.setStyleSheet("""
            QTabWidget::pane {
                border: none;
                border-top: 1px solid #E5E7EB;
                background: white;
            }
            QTabBar::tab {
                padding: 2px 4px;
                border: none;
                background: #F3F4F6;
                margin-right: 1px;
            }
            QTabBar::tab:selected {
                background: white;
                border-top: 2px solid #3B82F6;
            }
            QTabBar::tab:hover:!selected {
                background: #E5E7EB;
            }
        """)
        
        # Traffic Pattern Editor tab
        self.traffic_editor = TrafficPatternEditor()
        self.bottom_tabs.addTab(self.traffic_editor, "Traffic Patterns")
        
        # Failure Scenario Panel tab
        self.failure_panel = FailureScenarioPanel()
        self.bottom_tabs.addTab(self.failure_panel, "Failure Scenarios")
        
        # Metrics Dashboard tab
        self.metrics_dashboard = MetricsDashboard()
        self.bottom_tabs.addTab(self.metrics_dashboard, "Metrics")
        
        center_splitter.addWidget(self.bottom_tabs)
        
        # Set initial sizes for center splitter (canvas: 70%, tabs: 30%)
        center_splitter.setSizes([500, 200])
        center_splitter.setStretchFactor(0, 1)
        center_splitter.setStretchFactor(1, 0)
        
        main_splitter.addWidget(center_splitter)
        
        # Right panel - Properties and Stats in vertical splitter
        right_splitter = QSplitter(Qt.Orientation.Vertical)
        right_splitter.setStyleSheet("""
            QSplitter {
                background: white;
                border-left: 1px solid #E5E7EB;
            }
            QSplitter::handle {
                background: #E5E7EB;
                height: 2px;
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
        
        main_splitter.addWidget(right_splitter)
        
        # Set splitter sizes (left: 280, center: stretch, right: 300)
        main_splitter.setSizes([280, 800, 300])
        main_splitter.setStretchFactor(0, 0)
        main_splitter.setStretchFactor(1, 1)
        main_splitter.setStretchFactor(2, 0)
        
        layout.addWidget(main_splitter)
    
    def _setup_playback_controls(self):
        """Create playback controls bar at bottom of canvas."""
        # Create playback controls
        self.playback_controls = PlaybackControls(self.trace_player)
        self.playback_controls.setVisible(False)  # Hidden until trace loaded
        
        # Add to main layout (below the splitter)
        central = self.centralWidget()
        if central and central.layout():
            central.layout().addWidget(self.playback_controls)
    
    def _setup_status_bar(self):
        """Create status bar."""
        status = QStatusBar()
        status.setObjectName("MainWindow_StatusBar")
        status.setStyleSheet("""
            QStatusBar {
                background: #F9FAFB;
                border-top: 1px solid #E5E7EB;
                padding: 2px 8px;
                color: #6B7280;
                font-size: 12px;
            }
        """)
        self.setStatusBar(status)
        
        # Node/link count
        self._count_label = QLabel("Nodes: 0  Links: 0")
        self._count_label.setObjectName("MainWindow_CountLabel")
        status.addWidget(self._count_label)
        
        # Spacer
        status.addWidget(QWidget(), 1)
        
        # Instructions
        self._instruction_label = QLabel("Click nodes to add • Right-drag to link • Scroll to zoom • Ctrl+hover for widget info")
        self._instruction_label.setObjectName("MainWindow_InstructionLabel")
        status.addWidget(self._instruction_label)
    
    def _setup_layout_debugger(self):
        """Setup layout debugger for Ctrl+hover widget identification."""
        debugger = LayoutDebugger.instance()
        
        # Register main components with meaningful identifiers
        debugger.register_widget(self, "MainWindow")
        debugger.register_widget(self.node_palette, "CombinedNodePalette")
        debugger.register_widget(self.canvas, "TopologyCanvas")
        debugger.register_widget(self.property_panel, "PropertyPanel")
        debugger.register_widget(self.stats_panel, "StatsPanel")
        debugger.register_widget(self.bottom_tabs, "BottomTabs")
        debugger.register_widget(self.traffic_editor, "TrafficPatternEditor")
        debugger.register_widget(self.failure_panel, "FailureScenarioPanel")
        debugger.register_widget(self.metrics_dashboard, "MetricsDashboard")
        
        # Auto-register children of key components
        debugger.auto_register(self.node_palette, "NodePalette", max_depth=5)
        debugger.auto_register(self.traffic_editor, "TrafficEditor", max_depth=4)
        debugger.auto_register(self.failure_panel, "FailurePanel", max_depth=4)
        debugger.auto_register(self.metrics_dashboard, "MetricsDash", max_depth=4)

    def _connect_signals(self):
        """Connect all signals."""
        # Node palette -> Canvas (standard nodes via nodeTypeSelected string)
        self.node_palette.nodeTypeSelected.connect(self._on_node_type_selected_by_name)
        
        # Grid node palette -> Canvas (grid nodes)
        self.node_palette.gridNodeTypeSelected.connect(self._on_grid_node_type_selected)
        
        # Canvas -> Property panel
        self.canvas.itemSelected.connect(self.property_panel.set_selection)
        self.canvas.portSelected.connect(self._on_port_selected)
        
        # Scene changes -> Status bar update
        self.canvas.topology_scene.nodeAdded.connect(self._update_counts)
        self.canvas.topology_scene.nodeRemoved.connect(self._update_counts)
        self.canvas.topology_scene.linkAdded.connect(self._update_counts)
        self.canvas.topology_scene.linkRemoved.connect(self._update_counts)
        
        # Scene changes -> Update grid editors
        self.canvas.topology_scene.nodeAdded.connect(self._update_grid_editors)
        self.canvas.topology_scene.nodeRemoved.connect(self._update_grid_editors)
        self.canvas.topology_scene.linkAdded.connect(self._update_grid_editors)
        self.canvas.topology_scene.linkRemoved.connect(self._update_grid_editors)
        
        # Scene medium type change -> property panel update
        self.canvas.topology_scene.mediumTypeChanged.connect(self._on_scene_medium_type_changed)
        
        # Application node double-click -> open script editor
        self.canvas.topology_scene.nodeDoubleClicked.connect(self._on_node_double_clicked)
        
        # Shape edited -> refresh palette icons
        self.canvas.topology_scene.shapeEdited.connect(self._on_shape_edited)
        
        # Property changes -> Canvas update
        self.property_panel.propertiesChanged.connect(self._on_properties_changed)
        
        # Node type change -> Canvas update
        self.property_panel.nodeTypeChanged.connect(self._on_node_type_changed)
        
        # Medium type change -> Canvas update
        self.property_panel.mediumTypeChanged.connect(self._on_medium_type_changed)
        
        # Subnet applied -> Reassign IPs
        self.property_panel.subnetApplied.connect(self._on_subnet_applied)
        
        # Simulation state
        self.simulation_state.statusChanged.connect(self._on_simulation_status_changed)
        
        # Traffic editor -> sim_config
        self.traffic_editor.flowsChanged.connect(self._on_traffic_flows_changed)
        
        # Failure panel -> failure_scenario
        self.failure_panel.scenarioChanged.connect(self._on_failure_scenario_changed)
    
    def _connect_simulation_signals(self):
        """Connect simulation manager signals."""
        self.sim_manager.simulationStarted.connect(self._on_simulation_started)
        self.sim_manager.simulationFinished.connect(self._on_simulation_finished)
        self.sim_manager.simulationError.connect(self._on_simulation_error)
        self.sim_manager.outputReceived.connect(self._on_simulation_output)
        self.sim_manager.progressUpdated.connect(self._on_simulation_progress)
    
    def _connect_trace_player_signals(self):
        """Connect trace player signals for packet animation."""
        self.trace_player.packet_event.connect(self._on_packet_event)
        self.trace_player.playback_finished.connect(self._on_playback_finished)
        
        # Playback controls visibility toggle
        self.playback_controls.visibility_requested.connect(
            lambda visible: setattr(
                self.canvas.topology_scene.animation_manager, 
                'enabled', 
                visible
            )
        )
    
    def _on_packet_event(self, event: PacketEvent):
        """Handle packet event from trace player - animate packet."""
        # Map node indices to node IDs
        node_ids = list(self.network_model.nodes.keys())
        
        if event.event_type == PacketEventType.TX:
            # Find the link for this transmission
            node_idx = event.node_id
            if node_idx < len(node_ids):
                source_id = node_ids[node_idx]
                # Find a link from this node
                for link_id, link in self.network_model.links.items():
                    if link.source_node_id == source_id:
                        self.canvas.topology_scene.animation_manager.animate_packet_on_link(
                            link_id, 'forward', 'tx', 
                            int(200 / self.trace_player.speed)
                        )
                        break
                    elif link.target_node_id == source_id:
                        self.canvas.topology_scene.animation_manager.animate_packet_on_link(
                            link_id, 'backward', 'tx',
                            int(200 / self.trace_player.speed)
                        )
                        break
        
        elif event.event_type == PacketEventType.RX:
            # Could show a receive animation if desired
            pass
        
        elif event.event_type == PacketEventType.DROP:
            # Show drop animation
            node_idx = event.node_id
            if node_idx < len(node_ids):
                source_id = node_ids[node_idx]
                for link_id, link in self.network_model.links.items():
                    if link.source_node_id == source_id or link.target_node_id == source_id:
                        # Just show a brief flash for dropped packet
                        self.canvas.topology_scene.animation_manager.animate_packet_on_link(
                            link_id, 'forward', 'drop', 100
                        )
                        break
    
    def _on_playback_finished(self):
        """Handle trace playback finished."""
        self.statusBar().showMessage("Playback finished", 3000)
    
    def _on_node_type_selected(self, node_type: NodeType):
        """Handle node type selection from palette."""
        item = self.canvas.add_node_at_center(node_type)
        self.statusBar().showMessage(f"Added {node_type.name.lower()}", 2000)
    
    def _on_node_type_selected_by_name(self, type_name: str):
        """Handle node type selection by name string from CombinedNodePalette."""
        # Check if it's a grid node type (prefixed with GRID_)
        if type_name.startswith("GRID_"):
            # This will be handled by _on_grid_node_type_selected
            return
        
        # Standard node type
        try:
            node_type = NodeType[type_name]
            self._on_node_type_selected(node_type)
        except KeyError:
            self.statusBar().showMessage(f"Unknown node type: {type_name}", 2000)
    
    def _on_grid_node_type_selected(self, grid_type: GridNodeType):
        """Handle grid node type selection from palette."""
        # Create a GridNodeModel
        node = GridNodeModel(grid_type=grid_type)
        
        # Position at center of visible area
        center = self.canvas.mapToScene(self.canvas.viewport().rect().center())
        node.position.x = center.x()
        node.position.y = center.y()
        
        # Add to network model
        self.network_model.nodes[node.id] = node
        
        # Add to canvas
        self.canvas.topology_scene.add_node(node)
        
        # Update status
        type_name = grid_type.name.replace("_", " ").title()
        self.statusBar().showMessage(f"Added {type_name}", 2000)
        self._update_counts()
        self._update_grid_editors()
    
    def _on_traffic_flows_changed(self, flows: List[GridTrafficFlow]):
        """Handle traffic flows changed from editor."""
        # Update sim_config with the new flows
        self.sim_config.flows = flows
        self.statusBar().showMessage(f"Traffic: {len(flows)} flows configured", 2000)
    
    def _on_failure_scenario_changed(self, scenario: FailureScenario):
        """Handle failure scenario changed from editor."""
        self.failure_scenario = scenario
        if scenario:
            self.statusBar().showMessage(
                f"Failure scenario: {scenario.name} ({len(scenario.events)} events)", 
                2000
            )
    
    def _update_grid_editors(self):
        """Update grid editors with current network state."""
        # Build node info dict for traffic editor
        nodes = {}
        for node_id, node in self.network_model.nodes.items():
            if isinstance(node, GridNodeModel):
                nodes[node_id] = (node.name, node.grid_type)
            else:
                nodes[node_id] = (node.name, node.node_type)
        
        self.traffic_editor.set_network_nodes(nodes)
        
        # Update failure panel targets
        node_ids = list(self.network_model.nodes.keys())
        link_ids = list(self.network_model.links.keys())
        self.failure_panel.set_available_targets(node_ids, link_ids)
    
    def _on_port_selected(self, node_model: NodeModel, port: PortConfig):
        """Handle port selection from canvas."""
        # Set node selection in property panel
        self.property_panel.set_selection(node_model)
        # Scroll to and highlight the specific port
        self.property_panel.scroll_to_port(port.id)
        self.statusBar().showMessage(f"Selected port {port.display_name} on {node_model.name}", 2000)
    
    def _on_properties_changed(self, node_id: str):
        """Handle property changes."""
        if not node_id:
            # Link properties changed, nothing to update visually
            return
        
        # Update node graphics (labels and ports)
        from views.topology_canvas import NodeGraphicsItem
        node_item = self.canvas.topology_scene.get_node_item(node_id)
        if node_item:
            node_item.update_label()
            node_item.update_ports()  # Update port graphics (type labels, etc.)
    
    def _on_node_type_changed(self, node_id: str, new_type: NodeType):
        """Handle node type change from property panel."""
        # Update the visual representation
        node_item = self.canvas.topology_scene.get_node_item(node_id)
        if node_item:
            node_item.update_appearance()
            node_item.update_label()
        self.statusBar().showMessage(f"Changed node type to {new_type.name.lower()}", 2000)
    
    def _on_medium_type_changed(self, node_id: str, new_medium):
        """Handle medium type change from property panel."""
        from models import MediumType
        # Update the visual representation
        node_item = self.canvas.topology_scene.get_node_item(node_id)
        if node_item:
            node_item.update_appearance()
            node_item.update_label()
        medium_name = new_medium.name.replace('_', ' ').title() if hasattr(new_medium, 'name') else str(new_medium)
        self.statusBar().showMessage(f"Changed medium type to {medium_name}", 2000)
    
    def _on_scene_medium_type_changed(self, node_id: str, new_medium):
        """Handle medium type change from canvas context menu."""
        from models import MediumType
        # Refresh property panel to show updated medium
        self.property_panel.refresh()
        medium_name = new_medium.name.replace('_', ' ').title() if hasattr(new_medium, 'name') else str(new_medium)
        self.statusBar().showMessage(f"Changed medium type to {medium_name}", 2000)
    
    def _on_node_double_clicked(self, node_id: str):
        """Handle double-click on any node - open script editor."""
        from views.socket_app_editor import SocketAppEditorDialog
        
        node = self.network_model.get_node(node_id)
        if not node:
            return
        
        # Open the editor dialog
        dialog = SocketAppEditorDialog(node, self)
        dialog.scriptSaved.connect(self._on_app_script_saved)
        result = dialog.exec()
        
        # Update the node's visual indicator after dialog closes
        if result:
            self._update_node_app_indicator(node_id)
    
    def _update_node_app_indicator(self, node_id: str):
        """Update the App indicator on a node after script changes."""
        node_item = self.canvas.topology_scene._node_items.get(node_id)
        if node_item:
            node_item.update_app_indicator()
    
    def _on_app_script_saved(self, node_id: str, script_content: str):
        """Handle script saved for a node."""
        node = self.network_model.get_node(node_id)
        if node:
            # Store script content in node model
            node.app_script = script_content
            self._update_node_app_indicator(node_id)
            
            # Also save to project scripts directory if project is open
            if self._current_project and self._current_project.scripts_dir:
                try:
                    scripts_dir = self._current_project.scripts_dir
                    scripts_dir.mkdir(parents=True, exist_ok=True)
                    
                    # Generate filename from node name (same format used in topology.json)
                    safe_name = "".join(c if c.isalnum() or c == '_' else '_' for c in node.name.lower())
                    script_filename = f"{safe_name}.py"
                    script_path = scripts_dir / script_filename
                    
                    with open(script_path, 'w') as f:
                        f.write(script_content)
                    
                    self.statusBar().showMessage(
                        f"Saved {node.name} script to project: {script_filename}", 
                        3000
                    )
                except Exception as e:
                    print(f"Warning: Could not save script to project: {e}")
                    self.statusBar().showMessage(f"Saved script for {node.name}", 3000)
            else:
                self.statusBar().showMessage(f"Saved application script for {node.name}", 3000)
    
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
        
        # Auto-generate flows for nodes with app scripts that aren't in a flow
        self._auto_generate_app_flows()
        
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
        
        # Check if preview is enabled
        if hasattr(self.toolbar, 'preview_check') and self.toolbar.preview_check.isChecked():
            try:
                from views.code_preview_dialog import CodePreviewDialog
                
                # Show preview dialog
                self.toolbar.set_running(False)
                self.simulation_state.status = SimulationStatus.IDLE
                
                edited_script = CodePreviewDialog.preview_code(
                    script, 
                    "simulation.py",
                    self
                )
                
                if edited_script is None:
                    # User cancelled
                    self.statusBar().showMessage("Simulation cancelled", 2000)
                    return
                
                # Use the edited script
                script = edited_script
                self.toolbar.set_running(True)
                self.simulation_state.status = SimulationStatus.BUILDING
                
            except Exception as e:
                import traceback
                traceback.print_exc()
                self.toolbar.set_running(False)
                self.simulation_state.status = SimulationStatus.IDLE
                QMessageBox.critical(
                    self, 
                    "Preview Error",
                    f"Failed to show code preview:\n{e}\n\nRunning without preview."
                )
                # Continue without preview
                self.toolbar.set_running(True)
                self.simulation_state.status = SimulationStatus.BUILDING
        
        # Save script to workspace (local copy)
        self._save_script_to_workspace(script)
        
        # Get required files (app_base.py, custom scripts)
        required_files = generator.get_required_files(self.network_model, self.sim_config)
        
        # Start simulation
        self.simulation_state.status = SimulationStatus.RUNNING
        self.simulation_state.end_time = self.sim_config.duration
        self.stats_panel.reset()
        self.statusBar().showMessage("Running ns-3 simulation...")
        
        # Run simulation
        success = self.sim_manager.run_simulation(script, self._sim_output_dir, required_files)
        if not success:
            self.simulation_state.set_error("Failed to start simulation")
            self.toolbar.set_running(False)
    
    def _auto_generate_app_flows(self):
        """
        Auto-generate flows for nodes with app scripts that aren't already in a flow.
        
        This allows users to just attach an app script to a node and run without
        manually creating a traffic flow.
        """
        from models.simulation import TrafficFlow, TrafficApplication, TrafficProtocol
        
        # Find nodes with app scripts
        nodes_with_scripts = [
            node for node in self.network_model.nodes.values()
            if node.has_app_script
        ]
        
        if not nodes_with_scripts:
            return
        
        # Find which nodes are already sources in existing flows
        existing_sources = {flow.source_node_id for flow in self.sim_config.flows}
        
        for source_node in nodes_with_scripts:
            if source_node.id in existing_sources:
                continue  # Already has a flow
            
            # Find a suitable target node (any other node that's connected)
            target_node = self._find_connected_target(source_node)
            if not target_node:
                continue
            
            # Create a new flow
            flow = TrafficFlow(
                name=f"{source_node.name}_app_flow",
                source_node_id=source_node.id,
                target_node_id=target_node.id,
                application=TrafficApplication.CUSTOM_SOCKET,
                protocol=TrafficProtocol.UDP,
                start_time=1.0,
                stop_time=9.0,
                app_enabled=True,
                app_node_id=source_node.id,
            )
            self.sim_config.flows.append(flow)
            self.statusBar().showMessage(
                f"Auto-created flow: {source_node.name} → {target_node.name}", 3000
            )
    
    def _find_connected_target(self, source_node):
        """Find a suitable target node connected to the source."""
        from models.network import NodeType
        
        # Get all nodes connected to source via links
        connected_ids = set()
        for link in self.network_model.links.values():
            if link.source_node_id == source_node.id:
                connected_ids.add(link.target_node_id)
            elif link.target_node_id == source_node.id:
                connected_ids.add(link.source_node_id)
        
        # If directly connected, prefer hosts over routers/switches
        for node_id in connected_ids:
            node = self.network_model.nodes.get(node_id)
            if node and node.node_type == NodeType.HOST and node.id != source_node.id:
                return node
        
        # Otherwise, find any host in the network (for multi-hop paths)
        for node in self.network_model.nodes.values():
            if node.node_type == NodeType.HOST and node.id != source_node.id:
                return node
        
        # Fallback: any other node
        for node in self.network_model.nodes.values():
            if node.id != source_node.id:
                return node
        
        return None
    
    def _save_script_to_workspace(self, script: str):
        """
        Save generated script to project or workspace directory.
        
        If a project is open, saves to the project's scripts directory.
        Otherwise creates a 'generated_scripts' folder in the workspace.
        
        Note: Support files (app_base.py, app scripts) are copied after
        simulation completes in _save_simulation_results().
        """
        import os
        from datetime import datetime
        
        # If we have a project, save to project scripts directory
        if self._current_project and self._current_project.scripts_dir:
            scripts_dir = self._current_project.scripts_dir
            scripts_dir.mkdir(parents=True, exist_ok=True)
            
            # Save main simulation script
            script_path = scripts_dir / "gui_simulation.py"
            try:
                with open(script_path, 'w') as f:
                    f.write(script)
                self.stats_panel.log_console("INFO", f"Script saved to: {script_path}")
            except Exception as e:
                self.stats_panel.log_console("WARN", f"Could not save script: {e}")
            return
        
        # Fallback: save to workspace generated_scripts directory
        if self._current_project_path:
            workspace_dir = os.path.dirname(self._current_project_path)
        else:
            # Use home directory if no project is open
            workspace_dir = os.path.expanduser("~")
        
        # Create generated_scripts directory
        scripts_dir = os.path.join(workspace_dir, "generated_scripts")
        os.makedirs(scripts_dir, exist_ok=True)
        
        # Generate filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        script_filename = f"simulation_{timestamp}.py"
        script_path = os.path.join(scripts_dir, script_filename)
        
        # Save the script
        try:
            with open(script_path, 'w') as f:
                f.write(script)
            self.statusBar().showMessage(f"Script saved to {script_path}", 3000)
        except Exception as e:
            # Non-fatal error, just log it
            print(f"Warning: Could not save script to workspace: {e}")
    
    def _on_stop_simulation(self):
        """Stop simulation."""
        if self.sim_manager.is_running:
            self.sim_manager.stop_simulation()
        self.simulation_state.status = SimulationStatus.IDLE
        self.toolbar.set_running(False)
        
        # Clear any link activity highlighting
        self.canvas.topology_scene.clear_all_link_activity()
        
        self.statusBar().showMessage("Simulation stopped", 2000)
    
    def _on_simulation_started(self):
        """Handle simulation start."""
        self.statusBar().showMessage("Simulation running...")
        
        # Reset and configure toolbar time display
        self.toolbar.reset_time()
        self.toolbar.set_total_time(self.sim_config.duration)
        
        # Clear sender-to-target mapping from previous run
        self._sender_targets = {}
        
        # Pre-populate sender-to-target mapping from flow configuration
        # This maps source node NAME to target node NAME for path animation
        self._sender_to_target_node = {}
        for flow in self.sim_config.flows:
            source_node = self.network_model.nodes.get(flow.source_node_id)
            target_node = self.network_model.nodes.get(flow.target_node_id)
            if source_node and target_node:
                self._sender_to_target_node[source_node.name] = target_node.name
        
        # Start console logging session
        self.stats_panel.start_console_session()
        self.stats_panel.log_console("INFO", "Simulation started")
        self.stats_panel.log_console("INFO", f"Duration: {self.sim_config.duration}s")
        self.stats_panel.log_console("INFO", f"Flows: {len(self.sim_config.flows)}")
        
        # Reset stats and set running status
        self.stats_panel.set_status(SimulationStatus.RUNNING)
        self.stats_panel.set_progress(0, self.sim_config.duration)
        
        # Clear any previous trace
        self.trace_player.stop()
        self.playback_controls.setVisible(False)
    
    def _on_simulation_finished(self, results: SimulationResults):
        """Handle simulation completion."""
        self.toolbar.set_running(False)
        
        # Update time display to show final time (stays visible)
        self.toolbar.update_simulation_time(self.sim_config.duration, self.sim_config.duration)
        
        # Don't clear link activity immediately - let the retriggerable timers
        # run their course so the last packet flash completes naturally
        
        if results.success:
            self.simulation_state.status = SimulationStatus.COMPLETED
            self.simulation_state.set_results(results)
            self.stats_panel.set_status(SimulationStatus.COMPLETED)
            self.stats_panel.set_progress(self.sim_config.duration, self.sim_config.duration)
            
            # Log success
            self.stats_panel.log_console("SUCCESS", "Simulation completed successfully")
            if results.flow_stats:
                self.stats_panel.log_console("INFO", f"Collected stats for {len(results.flow_stats)} flow(s)")
            
            self.statusBar().showMessage("Simulation completed successfully", 5000)
            
            # Load trace for playback if we have packet events
            if results.console_output:
                loaded = self.trace_player.load_output(results.console_output)
                if loaded and self.trace_player.event_count > 0:
                    self.playback_controls.setVisible(True)
                    self.playback_controls.on_trace_loaded()
                    self.stats_panel.log_console("INFO", f"Loaded {self.trace_player.event_count} packet events for replay")
                    self.statusBar().showMessage(
                        f"Loaded {self.trace_player.event_count} packet events for replay", 
                        5000
                    )
            
            # Save results to project if we have one
            self._save_simulation_results(results, success=True)
        else:
            self.simulation_state.set_error(results.error_message)
            self.stats_panel.set_status(SimulationStatus.ERROR)
            self.stats_panel.log_console("ERROR", f"Simulation failed: {results.error_message}")
            self.statusBar().showMessage(f"Simulation failed: {results.error_message}", 5000)
            
            # Save failed results to project too
            self._save_simulation_results(results, success=False)
    
    def _save_simulation_results(self, results: SimulationResults, success: bool):
        """Save simulation results to the current project."""
        if not self._current_project:
            return
        
        import json
        import shutil
        from datetime import datetime
        from models.project import SimulationRun
        
        try:
            # Create timestamped run directory
            run_dir = self._current_project.create_run_dir()
            run_id = run_dir.name
            
            # Save console output
            console_log_path = ""
            if results.console_output:
                console_file = run_dir / "console.log"
                with open(console_file, 'w', encoding='utf-8') as f:
                    f.write(results.console_output)
                console_log_path = f"results/{run_id}/console.log"
                self.stats_panel.log_console("INFO", f"Console log saved to: {console_file}")
            
            # Copy flows.json to run directory (snapshot of flows used for this run)
            flows_file = self._current_project.flows_path
            if flows_file and flows_file.exists():
                shutil.copy2(flows_file, run_dir / "flows.json")
                self.stats_panel.log_console("INFO", f"Flows saved to: {run_dir / 'flows.json'}")
            elif self.sim_config.flows:
                # Save current flows if flows.json doesn't exist yet
                flows_data = {
                    "flows": [
                        {
                            "id": f.id,
                            "name": f.name,
                            "source_node_id": f.source_node_id,
                            "target_node_id": f.target_node_id,
                            "protocol": f.protocol.value if hasattr(f.protocol, 'value') else str(f.protocol),
                            "application": f.application.value if hasattr(f.application, 'value') else str(f.application),
                            "start_time": f.start_time,
                            "stop_time": f.stop_time,
                            "data_rate": f.data_rate,
                            "packet_size": f.packet_size,
                        }
                        for f in self.sim_config.flows
                    ]
                }
                with open(run_dir / "flows.json", 'w') as f:
                    json.dump(flows_data, f, indent=2)
                self.stats_panel.log_console("INFO", f"Flows saved to: {run_dir / 'flows.json'}")
            
            # Copy trace file if exists
            trace_file_path = ""
            if results.trace_file_path and Path(results.trace_file_path).exists():
                trace_dest = run_dir / "trace.xml"
                shutil.copy2(results.trace_file_path, trace_dest)
                trace_file_path = f"results/{run_id}/trace.xml"
                self.stats_panel.log_console("INFO", f"Trace file saved to: {trace_dest}")
            
            # Copy PCAP files if any
            if results.pcap_files:
                pcap_dir = run_dir / "pcap"
                pcap_dir.mkdir(exist_ok=True)
                for pcap_path in results.pcap_files:
                    if Path(pcap_path).exists():
                        shutil.copy2(pcap_path, pcap_dir / Path(pcap_path).name)
                self.stats_panel.log_console("INFO", f"PCAP files saved to: {pcap_dir}")
            
            # Save statistics as JSON
            stats_file_path = ""
            stats_data = {
                "success": success,
                "duration_configured": self.sim_config.duration,
                "duration_actual": results.duration_actual,
                "total_tx_packets": results.total_tx_packets,
                "total_rx_packets": results.total_rx_packets,
                "total_lost_packets": results.total_lost_packets,
                "average_throughput_mbps": results.average_throughput_mbps,
                "average_delay_ms": results.average_delay_ms,
                "flow_stats": [
                    {
                        "flow_id": f.flow_id,
                        "source_address": f.source_address,
                        "destination_address": f.destination_address,
                        "source_port": f.source_port,
                        "destination_port": f.destination_port,
                        "protocol": f.protocol,
                        "protocol_name": f.protocol_name,
                        "tx_packets": f.tx_packets,
                        "rx_packets": f.rx_packets,
                        "tx_bytes": f.tx_bytes,
                        "rx_bytes": f.rx_bytes,
                        "lost_packets": f.lost_packets,
                        "packet_loss_percent": f.packet_loss_percent,
                        "throughput_mbps": f.throughput_mbps,
                        "mean_delay_ms": f.mean_delay_ms,
                        "mean_jitter_ms": f.mean_jitter_ms
                    }
                    for f in results.flow_stats
                ]
            }
            stats_file = run_dir / "stats.json"
            with open(stats_file, 'w') as f:
                json.dump(stats_data, f, indent=2)
            stats_file_path = f"results/{run_id}/stats.json"
            
            # Save run info
            run_info = {
                "id": run_id,
                "timestamp": datetime.now().isoformat(),
                "status": "success" if success else "failed",
                "error_message": results.error_message if not success else "",
                "node_count": len(self.network_model.nodes),
                "link_count": len(self.network_model.links),
                "duration": self.sim_config.duration,
                "ns3_path": self.sim_manager.ns3_path
            }
            run_info_file = run_dir / "run_info.json"
            with open(run_info_file, 'w') as f:
                json.dump(run_info, f, indent=2)
            
            # Copy generated scripts to project scripts directory using project manager
            self.project_mgr._save_scripts(
                self._current_project, 
                output_dir=self._sim_output_dir
            )
            self.stats_panel.log_console("INFO", f"Scripts saved to: {self._current_project.scripts_dir}")
            
            # Add run record to project
            run_record = SimulationRun(
                id=run_id,
                timestamp=datetime.now().isoformat(),
                duration=self.sim_config.duration,
                status="success" if success else "failed",
                console_log_path=console_log_path,
                trace_file_path=trace_file_path,
                stats_file_path=stats_file_path,
                error_message=results.error_message if not success else "",
                node_count=len(self.network_model.nodes),
                link_count=len(self.network_model.links),
                flow_count=len(results.flow_stats),
                packets_sent=results.total_tx_packets,
                packets_received=results.total_rx_packets,
                packets_dropped=results.total_lost_packets,
                throughput_mbps=results.average_throughput_mbps
            )
            self.project_mgr.add_simulation_run(self._current_project, run_record)
            
            # Save the complete project (topology, flows, scripts)
            self._sync_flows_to_network_model()
            self.project_mgr.save_project(
                self._current_project, 
                network_model=self.network_model,
                sim_config=self.sim_config,
                output_dir=self._sim_output_dir
            )
            
            self.stats_panel.log_console("SUCCESS", f"Results saved to project: {run_dir}")
            
        except Exception as e:
            self.stats_panel.log_console("ERROR", f"Failed to save results: {e}")
            import traceback
            traceback.print_exc()
    
    def _on_simulation_error(self, error_msg: str):
        """Handle simulation error."""
        self.toolbar.set_running(False)
        self.simulation_state.set_error(error_msg)
        self.stats_panel.set_status(SimulationStatus.ERROR)
        self.stats_panel.log_console("ERROR", error_msg)
        
        # Save error to project
        if self._current_project:
            from models.project import SimulationRun
            from datetime import datetime
            import json
            
            try:
                run_dir = self._current_project.create_run_dir()
                run_id = run_dir.name
                
                # Save error info
                error_info = {
                    "status": "error",
                    "error_message": error_msg,
                    "timestamp": datetime.now().isoformat(),
                    "node_count": len(self.network_model.nodes),
                    "link_count": len(self.network_model.links)
                }
                with open(run_dir / "error_info.json", 'w') as f:
                    json.dump(error_info, f, indent=2)
                
                # Save console output if available
                console_text = self.stats_panel.get_console_text()
                if console_text:
                    with open(run_dir / "console.log", 'w') as f:
                        f.write(console_text)
                
                # Add run record
                run_record = SimulationRun(
                    id=run_id,
                    timestamp=datetime.now().isoformat(),
                    duration=self.sim_config.duration,
                    status="error",
                    error_message=error_msg,
                    console_log_path=f"results/{run_id}/console.log",
                    node_count=len(self.network_model.nodes),
                    link_count=len(self.network_model.links)
                )
                self.project_mgr.add_simulation_run(self._current_project, run_record)
                
            except Exception as e:
                print(f"Failed to save error to project: {e}")
        
        # Show detailed error dialog
        error_dialog = QMessageBox(self)
        error_dialog.setIcon(QMessageBox.Icon.Warning)
        error_dialog.setWindowTitle("Simulation Error")
        error_dialog.setText("The simulation encountered an error.")
        error_dialog.setInformativeText(error_msg)
        error_dialog.setDetailedText(
            "Possible causes:\n"
            "- Invalid topology configuration\n"
            "- ns-3 script generation error\n"
            "- ns-3 runtime error\n"
            "- Missing ns-3 modules\n\n"
            "Check the Console tab for more details."
        )
        error_dialog.setStandardButtons(QMessageBox.StandardButton.Ok)
        error_dialog.exec()
    
    def _on_simulation_output(self, line: str):
        """Handle simulation output line."""
        self.stats_panel.append_console_line(line)
        
        import re
        
        # Parse simulation time from output like "[1.500s]" or "Time: 5.0s"
        time_match = re.search(r'\[(\d+\.?\d*)s\]', line)
        if time_match:
            try:
                current_time = float(time_match.group(1))
                self.toolbar.update_simulation_time(current_time, self.sim_config.duration)
                self.simulation_state.current_time = current_time
            except ValueError:
                pass
        else:
            # Alternative format: "Time: 5.0s" or "time=5.0"
            time_match2 = re.search(r'[Tt]ime[=:]\s*(\d+\.?\d*)', line)
            if time_match2:
                try:
                    current_time = float(time_match2.group(1))
                    self.toolbar.update_simulation_time(current_time, self.sim_config.duration)
                    self.simulation_state.current_time = current_time
                except ValueError:
                    pass
        
        # Parse IP address assignments from output
        # Format: "Link 0: 10.1.1.1 (host_9eae) <-> switch_9833 (switch)"
        # or: "10.1.1.1:49153 -> 10.1.1.2:9"
        ip_assign_match = re.search(r'Link \d+:\s+([\d.]+)\s+\(([^)]+)\)\s+<->\s+([^\s]+)', line)
        if ip_assign_match:
            ip = ip_assign_match.group(1)
            node_name = ip_assign_match.group(2)
            self.canvas.topology_scene.set_node_ip(node_name, ip)
            # Refresh property panel to show new IP
            self.property_panel.refresh_port_displays()
        
        # Also parse from flow statistics output
        # Format: "10.1.1.1:49153 -> 10.1.1.2:9"
        flow_match = re.search(r'([\d.]+):(\d+)\s+->\s+([\d.]+):(\d+)', line)
        if flow_match:
            # This gives us the IPs used in flows, but we've already captured them above
            pass
        
        # Parse "Starting" events for app startup indication and capture target
        # Format: "[1.500s] [host_9eae] Starting - target: 10.1.1.2:9"
        start_match = re.search(r'\[[\d.]+s\]\s+\[([^\]]+)\]\s+Starting\s*-\s*target:\s*([\d.]+)', line)
        if start_match:
            node_name = start_match.group(1)
            target_ip = start_match.group(2)
            # Store the target IP for this sender to use in path animation
            if not hasattr(self, '_sender_targets'):
                self._sender_targets = {}
            self._sender_targets[node_name] = target_ip
        
        # Parse packet send events from app output
        # Format: "[1.500s] [host_9eae] Sent packet #1: 29 bytes"
        send_match = re.search(r'\[[\d.]+s\]\s+\[([^\]]+)\]\s+Sent packet', line)
        if send_match:
            sender_name = send_match.group(1)
            # Use pre-populated flow mapping (set at simulation start)
            target_name = getattr(self, '_sender_to_target_node', {}).get(sender_name)
            if target_name:
                # Flash entire path from sender to target using node names
                self.canvas.topology_scene.flash_path(sender_name, target_name, duration_ms=1500)
            else:
                # Fallback: flash all links connected to sender
                self.canvas.topology_scene.flash_links_for_node(sender_name, duration_ms=1500)
    
    def _get_node_name_by_ip(self, ip: str) -> str:
        """Get node name by assigned IP address."""
        for node in self.canvas.topology_scene.network_model.nodes.values():
            for port in node.ports:
                if port.assigned_ip == ip:
                    return node.name
        return ""
    
    def _get_sender_ip(self, sender_name: str) -> str:
        """Get the assigned IP for a sender node by name."""
        for node in self.canvas.topology_scene.network_model.nodes.values():
            if node.name == sender_name:
                for port in node.ports:
                    if port.assigned_ip:
                        return port.assigned_ip
        return ""
    
    def _on_simulation_progress(self, progress: int):
        """Handle simulation progress update."""
        # Estimate current time from progress
        current_time = (progress / 100.0) * self.sim_config.duration
        self.simulation_state.current_time = current_time
        self.stats_panel.set_progress(current_time, self.sim_config.duration)
        self.toolbar.update_simulation_time(current_time, self.sim_config.duration)
    
    def _show_ns3_config_dialog(self):
        """Show dialog to configure ns-3 path."""
        dialog = NS3PathDialog(self.sim_manager.ns3_path, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            path = dialog.get_path()
            use_wsl = NS3Detector.is_wsl_path(path)
            if NS3Detector.validate_ns3_path(path, use_wsl=use_wsl):
                self.sim_manager.ns3_path = path
                # Save settings for next time
                self._save_ns3_settings()
                QMessageBox.information(
                    self, 
                    "ns-3 Configured",
                    f"ns-3 found at: {path}\n"
                    f"Version: {NS3Detector.get_ns3_version(path, use_wsl=use_wsl) or 'unknown'}\n"
                    f"Mode: {'WSL' if use_wsl else 'Native'}\n\n"
                    f"This path has been saved for future sessions."
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
    
    def _on_show_settings(self):
        """Show the settings dialog."""
        dialog = SettingsDialog(self)
        dialog.settingsChanged.connect(self._on_settings_changed)
        dialog.workspaceChanged.connect(self._on_workspace_changed)
        dialog.exec()
    
    def _on_show_shape_manager(self):
        """Show the shape manager dialog."""
        from views.shape_manager_dialog import ShapeManagerDialog
        
        dialog = ShapeManagerDialog(self)
        dialog.shapes_changed.connect(self._on_shapes_changed)
        dialog.exec()
    
    def _on_shapes_changed(self):
        """Handle shape changes from shape manager."""
        # Refresh canvas to show updated shapes
        if hasattr(self, 'canvas') and self.canvas:
            # Clear shape cache
            shape_manager = get_shape_manager()
            shape_manager._path_cache.clear()
            
            # Update all nodes on canvas
            self.canvas.topology_scene.update()
            
            # Also refresh palette icons by recreating them
            # (This is a bit heavy-handed but ensures consistency)
            self._refresh_palette_icons()
        
        self.statusBar().showMessage("Shapes updated", 2000)
    
    def _refresh_palette_icons(self):
        """Refresh palette icons after shape changes."""
        # Call refresh_icons on the palette to re-render all icons
        if hasattr(self, 'node_palette') and self.node_palette:
            self.node_palette.refresh_icons()
    
    def _on_shape_edited(self, shape_id: str):
        """Handle shape edited from canvas (via Ctrl+double-click or context menu)."""
        # Refresh palette icons to show the updated shape
        self._refresh_palette_icons()
        self.statusBar().showMessage(f"Shape '{shape_id}' updated", 2000)
    
    def _on_settings_changed(self):
        """Handle settings changes from dialog."""
        # Reload ns-3 settings
        self._load_ns3_settings()
        
        # Apply UI settings
        s = self.settings_manager.settings.ui
        self.trace_player.speed = s.animation_speed
        self.canvas.topology_scene.animation_manager.enabled = s.show_packet_animations
        
        self.statusBar().showMessage("Settings updated", 2000)
    
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
    
    # ==================== Project Management ====================
    
    def _on_new_project(self):
        """Create a new project."""
        dialog = NewProjectDialog(self.project_mgr, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            project = dialog.get_project()
            if project:
                self._current_project = project
                # Clear current topology for new project
                self.canvas.topology_scene.clear_topology()
                self.property_panel.set_selection(None)
                self.stats_panel.reset()
                self._update_counts()
                self._update_window_title()
                self.statusBar().showMessage(f"Created project: {project.name}", 3000)
    
    def _on_open_project(self):
        """Open an existing project."""
        try:
            dialog = OpenProjectDialog(self.project_mgr, self)
        except Exception as e:
            print(f"Error creating dialog: {e}")
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "Error", f"Failed to open project dialog:\n{e}")
            return
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            project = dialog.get_project()
            if project:
                self._current_project = project
                
                # Load topology if present
                try:
                    # Clear current topology first
                    self.canvas.topology_scene.clear_topology()
                    
                    network = self.project_mgr.load_topology(project)
                    if network:
                        # Replace network model and rebuild canvas
                        self.network_model = network
                        self.property_panel.set_network_model(self.network_model)
                        
                        # Recreate visual items from loaded model
                        self._rebuild_canvas_from_model()
                        
                        self.property_panel.set_selection(None)
                        self.stats_panel.reset()
                        self._update_counts()
                        
                        # Load flows from project and sync to sim_config
                        self._load_project_flows(project)
                        
                        # Load app scripts from project scripts directory
                        self._load_project_app_scripts(project)
                        
                        flow_count = len(self.sim_config.flows)
                        msg = f"Opened project: {project.name} ({len(network.nodes)} nodes"
                        if flow_count > 0:
                            msg += f", {flow_count} flows"
                        msg += ")"
                        self.statusBar().showMessage(msg, 3000)
                    else:
                        self.statusBar().showMessage(
                            f"Opened project: {project.name} (no topology)", 
                            3000
                        )
                except Exception as e:
                    QMessageBox.warning(
                        self, "Warning", 
                        f"Could not load topology:\n{e}"
                    )
                    import traceback
                    traceback.print_exc()
                
                self._update_window_title()
    
    def _load_project_app_scripts(self, project):
        """Load app scripts from project directory into nodes.
        
        Uses the app_script_file field from topology.json to locate script files.
        Falls back to generating filename from node name if app_script_file not set.
        """
        if not project.path:
            return
        
        project_dir = project.path
        loaded_count = 0
        
        # Iterate through all nodes in the network model
        for node in self.network_model.nodes.values():
            try:
                script_path = None
                
                # First try using app_script_file from topology
                if node.app_script_file:
                    script_path = project_dir / node.app_script_file
                    if not script_path.exists():
                        script_path = None
                
                # Fall back to generating filename from node name
                if not script_path and project.scripts_dir and project.scripts_dir.exists():
                    safe_name = "".join(
                        c if c.isalnum() or c == '_' else '_' 
                        for c in node.name.lower()
                    )
                    script_filename = f"{safe_name}.py"
                    fallback_path = project.scripts_dir / script_filename
                    if fallback_path.exists():
                        script_path = fallback_path
                
                # Load script if found
                if script_path and script_path.exists():
                    with open(script_path, 'r') as f:
                        script_content = f.read()
                    
                    # Load script into node
                    node.app_script = script_content
                    loaded_count += 1
                    
                    # Update visual indicator
                    self._update_node_app_indicator(node.id)
                    
            except Exception as e:
                print(f"Warning: Could not load script for {node.name}: {e}")
        
        if loaded_count > 0:
            self.stats_panel.log_console("INFO", f"Loaded {loaded_count} app script(s) from project")
    
    def _load_project_flows(self, project):
        """Load flows from project into sim_config."""
        from models import TrafficFlow, TrafficProtocol, TrafficApplication
        
        flows_data = self.project_mgr.load_flows(project)
        if not flows_data:
            return
        
        self.sim_config.flows.clear()
        for flow_dict in flows_data:
            try:
                # Convert string protocol/application to enums
                protocol = flow_dict.get('protocol', 'UDP')
                if isinstance(protocol, str):
                    protocol = TrafficProtocol(protocol) if protocol in [p.value for p in TrafficProtocol] else TrafficProtocol.UDP
                
                application = flow_dict.get('application', 'ONOFF')
                if isinstance(application, str):
                    application = TrafficApplication(application) if application in [a.value for a in TrafficApplication] else TrafficApplication.ONOFF
                
                flow = TrafficFlow(
                    id=flow_dict.get('id', ''),
                    name=flow_dict.get('name', ''),
                    source_node_id=flow_dict.get('source_node_id', ''),
                    target_node_id=flow_dict.get('target_node_id', ''),
                    protocol=protocol,
                    application=application,
                    start_time=flow_dict.get('start_time', 1.0),
                    stop_time=flow_dict.get('stop_time', 9.0),
                    data_rate=flow_dict.get('data_rate', '500kb/s'),
                    packet_size=flow_dict.get('packet_size', 1024),
                    port=flow_dict.get('port', 9),
                    echo_packets=flow_dict.get('echo_packets', 10),
                    echo_interval=flow_dict.get('echo_interval', 1.0),
                )
                self.sim_config.flows.append(flow)
                
                # Also add to network model saved_flows
                self.network_model.saved_flows.append(flow)
            except Exception as e:
                print(f"Error loading flow: {e}")
    
    def _on_project_info(self):
        """Show current project information."""
        if not self._current_project:
            QMessageBox.information(
                self, "No Project",
                "No project is currently open.\n\n"
                "Use File → Project → New Project to create one,\n"
                "or File → Project → Open Project to open an existing one."
            )
            return
        
        dialog = ProjectInfoDialog(self._current_project, self)
        dialog.exec()
    
    def _on_workspace_changed(self, new_path: str):
        """Handle workspace location change."""
        # Reinitialize project manager with new workspace
        self.project_mgr = ProjectMgr(Path(new_path))
        self.project_mgr.ensure_workspace()
        self.statusBar().showMessage(f"Workspace changed to: {new_path}", 3000)
    
    def _save_current_project(self):
        """Save the current project including topology, flows, and scripts."""
        if not self._current_project:
            return False
        
        try:
            # Save flows to network model before saving project
            self._sync_flows_to_network_model()
            
            # Save project with all components
            self.project_mgr.save_project(
                self._current_project, 
                network_model=self.network_model,
                sim_config=self.sim_config,
                output_dir=self._sim_output_dir if self._sim_output_dir else None
            )
            
            # Build status message
            node_count = len(self.network_model.nodes)
            link_count = len(self.network_model.links)
            flow_count = len(self.sim_config.flows) if self.sim_config.flows else len(self.network_model.saved_flows)
            
            msg = f"Project saved: {self._current_project.name} ({node_count} nodes, {link_count} links"
            if flow_count > 0:
                msg += f", {flow_count} flows"
            msg += ")"
            
            self.statusBar().showMessage(msg, 3000)
            return True
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save project:\n{e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _sync_flows_to_network_model(self):
        """Sync current simulation config flows to network model for saving."""
        if not self.sim_config.flows:
            return
        
        # Save flows to network model
        self.network_model.saved_flows.clear()
        for flow in self.sim_config.flows:
            # Store a copy
            saved_flow = TrafficFlow(
                id=flow.id,
                name=flow.name,
                source_node_id=flow.source_node_id,
                target_node_id=flow.target_node_id,
                protocol=flow.protocol,
                application=flow.application,
                start_time=flow.start_time,
                stop_time=flow.stop_time,
                data_rate=flow.data_rate,
                packet_size=flow.packet_size,
                echo_packets=flow.echo_packets,
                echo_interval=flow.echo_interval
            )
            self.network_model.saved_flows.append(saved_flow)
    
    # ==================== File Operations ====================

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
        # Get default directory from settings
        default_dir = self.settings_manager.get_open_directory()
        
        filepath, _ = QFileDialog.getOpenFileName(
            self,
            "Open Topology",
            default_dir,
            "NS-3 GUI Topology (*.json);;All Files (*)"
        )
        
        if not filepath:
            return
        
        # Remember the directory for next time
        self.settings_manager.set_open_directory(filepath)
        
        try:
            # Clear current topology
            self.canvas.topology_scene.clear_topology()
            
            # Load the file
            loaded_network = self.project_manager.load(Path(filepath))
            
            if loaded_network is None:
                raise ValueError("Failed to parse topology file")
            
            # Replace network model and rebuild canvas
            self.network_model = loaded_network
            self.property_panel.set_network_model(self.network_model)
            
            # Recreate visual items from loaded model
            self._rebuild_canvas_from_model()
            
            self._update_window_title()
            self._update_counts()
            
            # Track current project path
            self._current_project_path = filepath
            
            # Log success info
            node_count = len(self.network_model.nodes)
            link_count = len(self.network_model.links)
            flow_count = len(self.network_model.saved_flows)
            
            msg = f"Opened {Path(filepath).name}: {node_count} nodes, {link_count} links"
            if flow_count > 0:
                msg += f", {flow_count} saved flows"
            
            self.statusBar().showMessage(msg, 3000)
            
        except Exception as e:
            error_msg = str(e)
            QMessageBox.critical(
                self,
                "Error Opening File",
                f"Failed to load topology from:\n{filepath}\n\nError: {error_msg}"
            )
            # Reset to empty state
            self.network_model = NetworkModel()
            self.property_panel.set_network_model(self.network_model)
            self.canvas.topology_scene.network_model = self.network_model
            self._update_counts()
            self._update_window_title()
    
    def _rebuild_canvas_from_model(self):
        """Rebuild canvas graphics items from the network model."""
        try:
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
            
            # Update port appearances after all links are created
            for node_item in scene._node_items.values():
                node_item.update_ports()
                
        except Exception as e:
            print(f"Error in _rebuild_canvas_from_model: {e}")
            import traceback
            traceback.print_exc()
            QMessageBox.warning(
                self,
                "Warning",
                f"Error rebuilding canvas: {str(e)}"
            )
    
    def _on_save_file(self):
        """Save to current file or project."""
        # If we have a project open, save to project
        if self._current_project:
            self._save_current_project()
        elif self.project_manager.has_file:
            self._save_to_file(self.project_manager.current_file)
        else:
            self._on_save_file_as()
    
    def _on_save_file_as(self):
        """Save topology to a new file."""
        # If we have a project, offer to save to project or new file
        if self._current_project:
            reply = QMessageBox.question(
                self,
                "Save As",
                f"You have project '{self._current_project.name}' open.\n\n"
                "Do you want to save to the project?\n\n"
                "Click 'Yes' to save to project, 'No' to save to a different file.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel
            )
            if reply == QMessageBox.StandardButton.Yes:
                self._save_current_project()
                return
            elif reply == QMessageBox.StandardButton.Cancel:
                return
        
        # Get default directory from settings
        default_dir = self.settings_manager.get_save_directory()
        default_path = os.path.join(default_dir, "topology.json") if default_dir else "topology.json"
        
        filepath, _ = QFileDialog.getSaveFileName(
            self,
            "Save Topology",
            default_path,
            "NS-3 GUI Topology (*.json);;All Files (*)"
        )
        
        if filepath:
            # Remember the directory for next time
            self.settings_manager.set_save_directory(filepath)
            
            # Ensure .json extension
            if not filepath.endswith('.json'):
                filepath += '.json'
            self._save_to_file(Path(filepath))
    
    def _save_to_file(self, filepath: Path):
        """Save network model to the specified file."""
        try:
            # Sync flows to network model before saving
            self._sync_flows_to_network_model()
            
            if self.project_manager.save(self.network_model, filepath):
                self._update_window_title()
                
                # Track current project path
                self._current_project_path = str(filepath)
                
                # Build detailed status message
                node_count = len(self.network_model.nodes)
                link_count = len(self.network_model.links)
                flow_count = len(self.network_model.saved_flows)
                
                msg = f"Saved to {filepath.name}: {node_count} nodes, {link_count} links"
                if flow_count > 0:
                    msg += f", {flow_count} flows"
                
                self.statusBar().showMessage(msg, 3000)
            else:
                raise IOError("Save operation returned failure")
        except Exception as e:
            error_msg = str(e)
            QMessageBox.critical(
                self,
                "Error Saving File",
                f"Failed to save topology to:\n{filepath}\n\nError: {error_msg}"
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
    
    def _on_import_ns3_example(self):
        """Import topology from an ns-3 Python example script."""
        from views.ns3_import_dialog import NS3ImportDialog
        
        dialog = NS3ImportDialog(self.settings_manager, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            result = dialog.get_result()
            if result and result.get("success"):
                # Load the converted topology
                topology_path = result.get("topology_path")
                if topology_path and os.path.exists(topology_path):
                    self._load_topology_file(Path(topology_path))
                    
                    # Import traffic flows if present
                    traffic_flows = result.get("traffic_flows", [])
                    if traffic_flows:
                        self.sim_config.flows = traffic_flows
                        flow_msg = f", {len(traffic_flows)} traffic flows"
                    else:
                        flow_msg = ""
                    
                    self.statusBar().showMessage(
                        f"Imported {result.get('node_count', 0)} nodes, "
                        f"{result.get('link_count', 0)} links{flow_msg} from ns-3 example",
                        5000
                    )
    
    def _on_import_ns3_batch(self):
        """Batch import all ns-3 Python examples."""
        from views.ns3_import_dialog import NS3BatchImportDialog
        
        dialog = NS3BatchImportDialog(self.settings_manager, self)
        dialog.exec()
    
    def _load_topology_file(self, filepath: Path):
        """Load a topology file into the canvas."""
        try:
            # Clear current topology
            self.canvas.topology_scene.clear_topology()
            
            # Load the file
            loaded_network = self.project_manager.load(filepath)
            
            if loaded_network is None:
                raise ValueError("Failed to parse topology file")
            
            # Replace network model and rebuild canvas
            self.network_model = loaded_network
            self.property_panel.set_network_model(self.network_model)
            
            # Rebuild canvas with loaded nodes and links
            self._rebuild_canvas_from_model()
            
            # Update recent files
            self.settings_manager.add_recent_file(str(filepath))
            
            # Update state
            self.project_manager._current_file = filepath
            self._update_counts()
            self._update_window_title()
            
        except Exception as e:
            QMessageBox.critical(
                self,
                "Error Loading Topology",
                f"Failed to load topology:\n{e}"
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
    
    def _on_toggle_show_routes(self, checked: bool):
        """Toggle showing all routes."""
        if checked:
            self.canvas.topology_scene.show_all_routes()
            self.statusBar().showMessage("Showing all configured routes", 3000)
        else:
            self.canvas.topology_scene.clear_route_highlights()
            self.statusBar().showMessage("Route highlights cleared", 2000)
    
    def _on_show_routes_from_selected(self):
        """Show routes originating from the selected node."""
        selected = self.canvas.topology_scene.selectedItems()
        
        node_item = None
        for item in selected:
            if hasattr(item, 'node_model'):
                node_item = item
                break
        
        if not node_item:
            QMessageBox.information(
                self, 
                "Show Routes", 
                "Please select a node first."
            )
            return
        
        self.canvas.topology_scene.show_routes_from_node(node_item.node_model.id)
        self._show_routes_action.setChecked(False)
        self.statusBar().showMessage(
            f"Showing routes from {node_item.node_model.name}", 3000
        )
    
    def _on_show_routes_to_selected(self):
        """Show routes to the selected node."""
        selected = self.canvas.topology_scene.selectedItems()
        
        node_item = None
        for item in selected:
            if hasattr(item, 'node_model'):
                node_item = item
                break
        
        if not node_item:
            QMessageBox.information(
                self, 
                "Show Routes", 
                "Please select a node first."
            )
            return
        
        self.canvas.topology_scene.show_routes_to_node(node_item.node_model.id)
        self._show_routes_action.setChecked(False)
        self.statusBar().showMessage(
            f"Showing routes to {node_item.node_model.name}", 3000
        )
    
    def _on_clear_route_highlights(self):
        """Clear all route highlighting."""
        self.canvas.topology_scene.clear_route_highlights()
        self._show_routes_action.setChecked(False)
        self.statusBar().showMessage("Route highlights cleared", 2000)
    
    def _on_show_help(self):
        """Show the ns-3 simulation help dialog."""
        from views.help_dialog import HelpDialog
        dialog = HelpDialog(self)
        dialog.exec()
    
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
            f"<p><b>Execution Mode:</b> {self.sim_manager.execution_mode}</p>"
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
        
        # Platform info
        from services.simulation_runner import is_windows, is_wsl_available
        
        if is_windows():
            if is_wsl_available():
                platform_info = QLabel(
                    "✓ Running on Windows with WSL available.\n"
                    "You can use a Linux path (e.g., ~/ns-3-dev) to run ns-3 inside WSL."
                )
                platform_info.setStyleSheet("color: #10B981; margin-bottom: 2px;")
            else:
                platform_info = QLabel(
                    "⚠ Running on Windows without WSL.\n"
                    "Install WSL to run ns-3: Open PowerShell as Admin and run 'wsl --install'"
                )
                platform_info.setStyleSheet("color: #F59E0B; margin-bottom: 2px;")
            platform_info.setWordWrap(True)
            layout.addWidget(platform_info)
        
        # Instructions
        info = QLabel(
            "Specify the path to your ns-3 installation.\n"
            "This should be the directory containing the 'ns3' or 'waf' script."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: #6B7280; margin-bottom: 2px;")
        layout.addWidget(info)
        
        # Path input
        path_layout = QHBoxLayout()
        
        self._path_edit = QLineEdit(self._path)
        if is_windows():
            self._path_edit.setPlaceholderText("~/ns-3-dev (WSL) or C:\\ns3\\ns-3-dev (native)")
        else:
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
        
        # WSL path examples (on Windows)
        if is_windows():
            examples = QLabel(
                "Examples:\n"
                "  WSL: ~/ns-3-dev, /home/username/ns-allinone-3.40/ns-3.40\n"
                "  Windows: C:\\ns3\\ns-3-dev (if installed natively)"
            )
            examples.setStyleSheet("color: #9CA3AF; font-size: 10px; margin-top: 8px;")
            layout.addWidget(examples)
        
        # Status
        self._status_label = QLabel()
        self._status_label.setStyleSheet("color: #6B7280; font-size: 11px;")
        self._status_label.setWordWrap(True)
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
        self._status_label.setText("Searching for ns-3...")
        self._status_label.setStyleSheet("color: #6B7280; font-size: 11px;")
        QApplication.processEvents()  # Update UI
        
        path = NS3Detector.find_ns3_path()
        if path:
            self._path_edit.setText(path)
            mode = "WSL" if NS3Detector.is_wsl_path(path) else "native"
            self._status_label.setText(f"✓ Found ns-3 at: {path} ({mode})")
            self._status_label.setStyleSheet("color: #10B981; font-size: 11px;")
        else:
            msg = "✗ Could not auto-detect ns-3 installation"
            from services.simulation_runner import is_windows, is_wsl_available
            if is_windows() and not is_wsl_available():
                msg += "\n\nWSL not available. Install with: wsl --install"
            self._status_label.setText(msg)
            self._status_label.setStyleSheet("color: #EF4444; font-size: 11px;")
    
    def _validate_path(self):
        """Validate the current path."""
        path = self._path_edit.text()
        if not path:
            self._status_label.setText("")
            return
        
        # Determine if this is a WSL path
        use_wsl = NS3Detector.is_wsl_path(path)
        
        if NS3Detector.validate_ns3_path(path, use_wsl=use_wsl):
            version = NS3Detector.get_ns3_version(path, use_wsl=use_wsl) or "unknown"
            mode = "WSL" if use_wsl else "native"
            self._status_label.setText(f"✓ Valid ns-3 installation (version: {version}, mode: {mode})")
            self._status_label.setStyleSheet("color: #10B981; font-size: 11px;")
        else:
            msg = "✗ Not a valid ns-3 installation"
            if use_wsl:
                from services.simulation_runner import is_wsl_available
                if not is_wsl_available():
                    msg += " (WSL not available)"
            self._status_label.setText(msg)
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
        
        # Auto-load saved flows if config is empty and there are saved flows
        self._auto_load_saved_flows()
    
    def _auto_load_saved_flows(self):
        """Automatically load saved flows if the config is empty."""
        if not self._config.flows and self._network.saved_flows:
            # Silently load saved flows
            from models import TrafficFlow
            for saved_flow in self._network.saved_flows:
                # Validate that source and target nodes still exist
                if (saved_flow.source_node_id in self._network.nodes and 
                    saved_flow.target_node_id in self._network.nodes):
                    # Create a copy with a new ID
                    new_flow = TrafficFlow(
                        name=saved_flow.name,
                        source_node_id=saved_flow.source_node_id,
                        target_node_id=saved_flow.target_node_id,
                        protocol=saved_flow.protocol,
                        application=saved_flow.application,
                        start_time=saved_flow.start_time,
                        stop_time=saved_flow.stop_time,
                        data_rate=saved_flow.data_rate,
                        packet_size=saved_flow.packet_size,
                        echo_packets=saved_flow.echo_packets,
                        echo_interval=saved_flow.echo_interval
                    )
                    self._config.flows.append(new_flow)
            
            # Update the flow list display
            self._update_flow_list()
    
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
        
        # Load/Save buttons
        load_flows_btn = QPushButton("Load Saved")
        load_flows_btn.setToolTip("Load flows saved with the topology")
        load_flows_btn.clicked.connect(self._load_saved_flows)
        flow_btn_layout.addWidget(load_flows_btn)
        
        save_flows_btn = QPushButton("Save Flows")
        save_flows_btn.setToolTip("Save current flows with the topology")
        save_flows_btn.clicked.connect(self._save_flows)
        flow_btn_layout.addWidget(save_flows_btn)
        
        flows_layout.addLayout(flow_btn_layout)
        
        # Show saved flows count
        saved_count = len(self._network.saved_flows)
        if saved_count > 0:
            saved_label = QLabel(f"({saved_count} flow(s) saved with topology)")
            saved_label.setStyleSheet("color: #6B7280; font-size: 11px; font-style: italic;")
            flows_layout.addWidget(saved_label)
        
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
            
            # Use target node name, or dest_address if no node, or "?" as fallback
            if target:
                target_name = target.name
            elif flow.dest_address:
                target_name = flow.dest_address
            else:
                target_name = "?"
            
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
    
    def _load_saved_flows(self):
        """Load flows that were saved with the topology."""
        if not self._network.saved_flows:
            QMessageBox.information(
                self,
                "No Saved Flows",
                "No flows have been saved with this topology.\n\n"
                "Use 'Save Flows' to save the current flows."
            )
            return
        
        # Ask user how to handle existing flows
        if self._config.flows:
            reply = QMessageBox.question(
                self,
                "Load Saved Flows",
                f"Found {len(self._network.saved_flows)} saved flow(s).\n\n"
                "Do you want to replace the current flows or add to them?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Yes
            )
            
            if reply == QMessageBox.StandardButton.Cancel:
                return
            elif reply == QMessageBox.StandardButton.Yes:
                # Replace
                self._config.flows.clear()
        
        # Load saved flows
        loaded_count = 0
        for saved_flow in self._network.saved_flows:
            # Validate that source and target nodes still exist
            if (saved_flow.source_node_id in self._network.nodes and 
                saved_flow.target_node_id in self._network.nodes):
                # Create a copy with a new ID to avoid conflicts
                from models import TrafficFlow
                new_flow = TrafficFlow(
                    name=saved_flow.name,
                    source_node_id=saved_flow.source_node_id,
                    target_node_id=saved_flow.target_node_id,
                    protocol=saved_flow.protocol,
                    application=saved_flow.application,
                    start_time=saved_flow.start_time,
                    stop_time=saved_flow.stop_time,
                    data_rate=saved_flow.data_rate,
                    packet_size=saved_flow.packet_size,
                    echo_packets=saved_flow.echo_packets,
                    echo_interval=saved_flow.echo_interval
                )
                self._config.flows.append(new_flow)
                loaded_count += 1
        
        self._update_flow_list()
        
        if loaded_count > 0:
            QMessageBox.information(
                self,
                "Flows Loaded",
                f"Loaded {loaded_count} flow(s) from saved topology."
            )
        else:
            QMessageBox.warning(
                self,
                "No Valid Flows",
                "No valid flows could be loaded.\n"
                "The referenced nodes may have been deleted."
            )
    
    def _save_flows(self):
        """Save current flows with the topology."""
        if not self._config.flows:
            QMessageBox.information(
                self,
                "No Flows",
                "No flows to save. Add some flows first."
            )
            return
        
        # Confirm if there are already saved flows
        if self._network.saved_flows:
            reply = QMessageBox.question(
                self,
                "Save Flows",
                f"This will replace {len(self._network.saved_flows)} previously saved flow(s) "
                f"with {len(self._config.flows)} current flow(s).\n\nContinue?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
        
        # Save flows to network model
        self._network.saved_flows.clear()
        for flow in self._config.flows:
            # Store a copy
            from models import TrafficFlow
            saved_flow = TrafficFlow(
                id=flow.id,
                name=flow.name,
                source_node_id=flow.source_node_id,
                target_node_id=flow.target_node_id,
                protocol=flow.protocol,
                application=flow.application,
                start_time=flow.start_time,
                stop_time=flow.stop_time,
                data_rate=flow.data_rate,
                packet_size=flow.packet_size,
                echo_packets=flow.echo_packets,
                echo_interval=flow.echo_interval
            )
            self._network.saved_flows.append(saved_flow)
        
        QMessageBox.information(
            self,
            "Flows Saved",
            f"Saved {len(self._config.flows)} flow(s) with the topology.\n\n"
            "Remember to save the project file (Ctrl+S) to persist."
        )
    
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
        self.setMinimumWidth(450)
        
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
        self._source_combo.currentIndexChanged.connect(self._update_app_node_combo)
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
        
        # Separator
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setStyleSheet("background: #E5E7EB; margin: 8px 0;")
        layout.addRow(separator)
        
        # Application Node toggle
        self._app_enabled_check = QCheckBox("Use Socket Application Node")
        self._app_enabled_check.setChecked(self._flow.app_enabled)
        self._app_enabled_check.setToolTip(
            "Enable to use a custom Socket Application node for this flow.\n"
            "The application's create_payload() function will generate the traffic."
        )
        self._app_enabled_check.stateChanged.connect(self._on_app_enabled_changed)
        layout.addRow(self._app_enabled_check)
        
        # Application node selector
        self._app_node_combo = QComboBox()
        self._app_node_combo.addItem("(Select Application Node)", "")
        self._update_app_node_combo()
        
        if self._flow.app_node_id:
            idx = self._app_node_combo.findData(self._flow.app_node_id)
            if idx >= 0:
                self._app_node_combo.setCurrentIndex(idx)
        self._app_node_combo.setEnabled(self._flow.app_enabled)
        layout.addRow("Application Node:", self._app_node_combo)
        
        # Separator
        separator2 = QFrame()
        separator2.setFrameShape(QFrame.Shape.HLine)
        separator2.setStyleSheet("background: #E5E7EB; margin: 8px 0;")
        layout.addRow(separator2)
        
        # Application type
        self._app_combo = QComboBox()
        self._app_combo.addItem("UDP Echo", TrafficApplication.ECHO)
        self._app_combo.addItem("On/Off (CBR)", TrafficApplication.ONOFF)
        self._app_combo.addItem("Bulk Send (TCP)", TrafficApplication.BULK_SEND)
        self._app_combo.addItem("Custom Socket", TrafficApplication.CUSTOM_SOCKET)
        
        idx = self._app_combo.findData(self._flow.application)
        if idx >= 0:
            self._app_combo.setCurrentIndex(idx)
        layout.addRow("Application Type:", self._app_combo)
        
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
        
        # Update UI state
        self._on_app_enabled_changed()
    
    def _on_app_enabled_changed(self):
        """Handle app_enabled checkbox change."""
        enabled = self._app_enabled_check.isChecked()
        self._app_node_combo.setEnabled(enabled)
        
        # If enabled, auto-select CUSTOM_SOCKET application type
        if enabled:
            idx = self._app_combo.findData(TrafficApplication.CUSTOM_SOCKET)
            if idx >= 0:
                self._app_combo.setCurrentIndex(idx)
    
    def _update_app_node_combo(self):
        """Update the application node combo based on source node."""
        current_selection = self._app_node_combo.currentData()
        self._app_node_combo.clear()
        self._app_node_combo.addItem("(Select Node with App Script)", "")
        
        source_node_id = self._source_combo.currentData()
        
        # Find nodes with application scripts
        for node_id, node in self._network.nodes.items():
            if node.has_app_script:
                # Show nodes with app scripts
                if node_id == source_node_id:
                    self._app_node_combo.addItem(f"⚡ {node.name} (source)", node_id)
                else:
                    self._app_node_combo.addItem(f"⚡ {node.name}", node_id)
        
        # Restore selection if possible
        if current_selection:
            idx = self._app_node_combo.findData(current_selection)
            if idx >= 0:
                self._app_node_combo.setCurrentIndex(idx)
    
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
        self._flow.app_enabled = self._app_enabled_check.isChecked()
        self._flow.app_node_id = self._app_node_combo.currentData() or ""
        return self._flow
