"""
Settings Dialog.

Provides UI for viewing and editing application settings.
"""

import os
from typing import Optional
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget,
    QWidget, QFormLayout, QLineEdit, QPushButton,
    QSpinBox, QDoubleSpinBox, QCheckBox, QComboBox,
    QGroupBox, QLabel, QFileDialog, QDialogButtonBox,
    QMessageBox, QFrame, QApplication
)

from services.settings_manager import get_settings, SettingsManager
from services.simulation_runner import NS3Detector, is_windows, is_wsl_available


class SettingsDialog(QDialog):
    """
    Settings dialog with tabbed interface.
    
    Tabs:
    - ns-3 Configuration
    - Simulation Defaults
    - User Interface
    """
    
    settingsChanged = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._settings = get_settings()
        self._setup_ui()
        self._load_current_settings()
    
    def _setup_ui(self):
        self.setWindowTitle("Settings")
        self.setMinimumWidth(550)
        self.setMinimumHeight(500)
        
        layout = QVBoxLayout(self)
        
        # Tab widget
        self._tabs = QTabWidget()
        self._tabs.addTab(self._create_ns3_tab(), "ns-3")
        self._tabs.addTab(self._create_workspace_tab(), "Workspace")
        self._tabs.addTab(self._create_simulation_tab(), "Simulation")
        self._tabs.addTab(self._create_ui_tab(), "Interface")
        layout.addWidget(self._tabs)
        
        # Settings file location info
        info_frame = QFrame()
        info_frame.setStyleSheet("""
            QFrame {
                background: #F3F4F6;
                border-radius: 4px;
                padding: 8px;
            }
            QLabel {
                color: #6B7280;
                font-size: 11px;
            }
        """)
        info_layout = QHBoxLayout(info_frame)
        info_layout.setContentsMargins(8, 4, 8, 4)
        
        path_label = QLabel(f"Settings file: {self._settings.settings_path}")
        path_label.setWordWrap(True)
        info_layout.addWidget(path_label, 1)
        
        open_btn = QPushButton("Open Folder")
        open_btn.setFixedWidth(100)
        open_btn.clicked.connect(self._open_settings_folder)
        info_layout.addWidget(open_btn)
        
        layout.addWidget(info_frame)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        reset_btn = QPushButton("Reset to Defaults")
        reset_btn.clicked.connect(self._reset_to_defaults)
        button_layout.addWidget(reset_btn)
        
        button_layout.addStretch()
        
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | 
            QDialogButtonBox.StandardButton.Cancel |
            QDialogButtonBox.StandardButton.Apply
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        buttons.button(QDialogButtonBox.StandardButton.Apply).clicked.connect(self._apply_settings)
        button_layout.addWidget(buttons)
        
        layout.addLayout(button_layout)
    
    def _create_ns3_tab(self) -> QWidget:
        """Create ns-3 configuration tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Platform info
        if is_windows():
            if is_wsl_available():
                info_text = "✓ Running on Windows with WSL available"
                info_style = "color: #059669; font-weight: bold;"
            else:
                info_text = "⚠ WSL not available - Install with: wsl --install"
                info_style = "color: #D97706; font-weight: bold;"
            
            info_label = QLabel(info_text)
            info_label.setStyleSheet(info_style)
            layout.addWidget(info_label)
        
        # ns-3 Path group
        path_group = QGroupBox("ns-3 Installation")
        path_layout = QFormLayout(path_group)
        
        # Path input
        path_input_layout = QHBoxLayout()
        self._ns3_path_edit = QLineEdit()
        self._ns3_path_edit.setPlaceholderText("/home/user/ns-allinone-3.45/ns-3.45")
        self._ns3_path_edit.textChanged.connect(self._validate_ns3_path)
        path_input_layout.addWidget(self._ns3_path_edit)
        
        browse_btn = QPushButton("Browse...")
        browse_btn.setFixedWidth(80)
        browse_btn.clicked.connect(self._browse_ns3_path)
        path_input_layout.addWidget(browse_btn)
        
        path_layout.addRow("Path:", path_input_layout)
        
        # Auto-detect button
        detect_layout = QHBoxLayout()
        detect_btn = QPushButton("Auto-detect ns-3")
        detect_btn.clicked.connect(self._auto_detect_ns3)
        detect_layout.addWidget(detect_btn)
        detect_layout.addStretch()
        path_layout.addRow("", detect_layout)
        
        # Status label
        self._ns3_status_label = QLabel()
        self._ns3_status_label.setWordWrap(True)
        path_layout.addRow("Status:", self._ns3_status_label)
        
        layout.addWidget(path_group)
        
        # WSL Settings group (Windows only)
        if is_windows():
            wsl_group = QGroupBox("WSL Settings")
            wsl_layout = QFormLayout(wsl_group)
            
            self._wsl_distro_combo = QComboBox()
            self._wsl_distro_combo.setEditable(True)
            self._populate_wsl_distributions()
            wsl_layout.addRow("Distribution:", self._wsl_distro_combo)
            
            self._use_wsl_check = QCheckBox("Use WSL for Linux-style paths")
            self._use_wsl_check.setChecked(True)
            wsl_layout.addRow("", self._use_wsl_check)
            
            layout.addWidget(wsl_group)
        
        layout.addStretch()
        return widget
    
    def _create_simulation_tab(self) -> QWidget:
        """Create simulation defaults tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Defaults group
        defaults_group = QGroupBox("Default Values")
        defaults_layout = QFormLayout(defaults_group)
        
        self._duration_spin = QDoubleSpinBox()
        self._duration_spin.setRange(0.1, 3600.0)
        self._duration_spin.setSuffix(" seconds")
        self._duration_spin.setDecimals(1)
        defaults_layout.addRow("Simulation Duration:", self._duration_spin)
        
        self._seed_spin = QSpinBox()
        self._seed_spin.setRange(1, 999999)
        defaults_layout.addRow("Random Seed:", self._seed_spin)
        
        layout.addWidget(defaults_group)
        
        # Tracing group
        tracing_group = QGroupBox("Default Tracing Options")
        tracing_layout = QVBoxLayout(tracing_group)
        
        self._flow_monitor_check = QCheckBox("Enable Flow Monitor (recommended)")
        tracing_layout.addWidget(self._flow_monitor_check)
        
        self._ascii_trace_check = QCheckBox("Enable ASCII Trace")
        tracing_layout.addWidget(self._ascii_trace_check)
        
        self._pcap_check = QCheckBox("Enable PCAP Capture")
        tracing_layout.addWidget(self._pcap_check)
        
        layout.addWidget(tracing_group)
        
        layout.addStretch()
        return widget
    
    def _create_workspace_tab(self) -> QWidget:
        """Create workspace configuration tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Workspace profile group
        profile_group = QGroupBox("Workspace Profile")
        profile_layout = QFormLayout(profile_group)
        
        self._profile_combo = QComboBox()
        self._profile_combo.addItems(["default", "test", "custom"])
        self._profile_combo.currentTextChanged.connect(self._on_profile_changed)
        profile_layout.addRow("Active Profile:", self._profile_combo)
        
        layout.addWidget(profile_group)
        
        # Workspace directory group
        dir_group = QGroupBox("Workspace Directory")
        dir_layout = QFormLayout(dir_group)
        
        # Workspace root path
        root_layout = QHBoxLayout()
        self._workspace_path_edit = QLineEdit()
        self._workspace_path_edit.setPlaceholderText("Leave empty for default location")
        root_layout.addWidget(self._workspace_path_edit)
        
        browse_btn = QPushButton("Browse...")
        browse_btn.setFixedWidth(80)
        browse_btn.clicked.connect(self._browse_workspace_path)
        root_layout.addWidget(browse_btn)
        
        dir_layout.addRow("Root Path:", root_layout)
        
        # Show current effective path
        self._effective_path_label = QLabel()
        self._effective_path_label.setStyleSheet("color: #6B7280; font-size: 11px;")
        self._effective_path_label.setWordWrap(True)
        dir_layout.addRow("", self._effective_path_label)
        
        layout.addWidget(dir_group)
        
        # Subdirectories info
        subdir_group = QGroupBox("Subdirectories")
        subdir_layout = QFormLayout(subdir_group)
        
        # Read-only display of subdirectory names
        self._topo_subdir_label = QLabel()
        subdir_layout.addRow("Topologies:", self._topo_subdir_label)
        
        self._scripts_subdir_label = QLabel()
        subdir_layout.addRow("Scripts:", self._scripts_subdir_label)
        
        self._results_subdir_label = QLabel()
        subdir_layout.addRow("Results:", self._results_subdir_label)
        
        self._templates_subdir_label = QLabel()
        subdir_layout.addRow("Templates:", self._templates_subdir_label)
        
        layout.addWidget(subdir_group)
        
        # Actions
        actions_layout = QHBoxLayout()
        
        open_workspace_btn = QPushButton("Open Workspace Folder")
        open_workspace_btn.clicked.connect(self._open_workspace_folder)
        actions_layout.addWidget(open_workspace_btn)
        
        create_dirs_btn = QPushButton("Create Directories")
        create_dirs_btn.clicked.connect(self._create_workspace_dirs)
        actions_layout.addWidget(create_dirs_btn)
        
        actions_layout.addStretch()
        layout.addLayout(actions_layout)
        
        layout.addStretch()
        return widget
    
    def _on_profile_changed(self, profile: str):
        """Handle workspace profile change."""
        # Update the workspace path edit with stored path for this profile
        workspaces = self._settings.settings.paths.workspaces
        path = workspaces.get(profile, "")
        self._workspace_path_edit.setText(path)
        self._update_effective_path()
    
    def _update_effective_path(self):
        """Update the effective path display."""
        profile = self._profile_combo.currentText()
        custom_path = self._workspace_path_edit.text().strip()
        
        # Calculate effective path
        if custom_path:
            from pathlib import Path
            effective = Path(custom_path)
        else:
            effective = self._settings.paths._get_default_workspace()
        
        self._effective_path_label.setText(f"Effective path: {effective}")
        
        # Update subdirectory labels
        paths = self._settings.paths
        self._topo_subdir_label.setText(f"{effective / paths.topologies_subdir}")
        self._scripts_subdir_label.setText(f"{effective / paths.scripts_subdir}")
        self._results_subdir_label.setText(f"{effective / paths.results_subdir}")
        self._templates_subdir_label.setText(f"{effective / paths.templates_subdir}")
    
    def _browse_workspace_path(self):
        """Browse for workspace directory."""
        current = self._workspace_path_edit.text() or str(self._settings.paths.get_workspace_root())
        path = QFileDialog.getExistingDirectory(
            self, "Select Workspace Directory", current
        )
        if path:
            self._workspace_path_edit.setText(path)
            self._update_effective_path()
    
    def _open_workspace_folder(self):
        """Open workspace folder in file explorer."""
        import subprocess
        import platform
        
        folder = str(self._settings.paths.get_workspace_root())
        
        if not os.path.exists(folder):
            QMessageBox.warning(
                self, "Folder Not Found",
                f"Workspace folder does not exist:\n{folder}\n\n"
                "Click 'Create Directories' to create it."
            )
            return
        
        if platform.system() == "Windows":
            os.startfile(folder)
        elif platform.system() == "Darwin":
            subprocess.run(["open", folder])
        else:
            subprocess.run(["xdg-open", folder])
    
    def _create_workspace_dirs(self):
        """Create workspace directories."""
        try:
            # Temporarily update settings to use current form values
            profile = self._profile_combo.currentText()
            custom_path = self._workspace_path_edit.text().strip()
            
            if custom_path:
                self._settings.paths.workspaces[profile] = custom_path
            
            old_profile = self._settings.paths.active_profile
            self._settings.paths.active_profile = profile
            
            self._settings.paths.ensure_workspace_dirs()
            
            # Restore
            self._settings.paths.active_profile = old_profile
            
            QMessageBox.information(
                self, "Success",
                "Workspace directories created successfully."
            )
            self._update_effective_path()
        except Exception as e:
            QMessageBox.critical(
                self, "Error",
                f"Failed to create directories:\n{e}"
            )
    
    def _create_ui_tab(self) -> QWidget:
        """Create UI settings tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Canvas group
        canvas_group = QGroupBox("Canvas")
        canvas_layout = QFormLayout(canvas_group)
        
        self._show_grid_check = QCheckBox("Show grid")
        canvas_layout.addRow("", self._show_grid_check)
        
        self._grid_size_spin = QSpinBox()
        self._grid_size_spin.setRange(10, 200)
        self._grid_size_spin.setSuffix(" px")
        canvas_layout.addRow("Grid Size:", self._grid_size_spin)
        
        layout.addWidget(canvas_group)
        
        # Animation group
        anim_group = QGroupBox("Packet Animation")
        anim_layout = QFormLayout(anim_group)
        
        self._show_animations_check = QCheckBox("Show packet animations")
        anim_layout.addRow("", self._show_animations_check)
        
        self._anim_speed_spin = QDoubleSpinBox()
        self._anim_speed_spin.setRange(0.1, 10.0)
        self._anim_speed_spin.setSingleStep(0.1)
        self._anim_speed_spin.setSuffix("x")
        anim_layout.addRow("Animation Speed:", self._anim_speed_spin)
        
        layout.addWidget(anim_group)
        
        # Files group
        files_group = QGroupBox("Files")
        files_layout = QFormLayout(files_group)
        
        self._recent_files_spin = QSpinBox()
        self._recent_files_spin.setRange(0, 50)
        files_layout.addRow("Recent Files (max):", self._recent_files_spin)
        
        self._auto_save_check = QCheckBox("Auto-save projects")
        files_layout.addRow("", self._auto_save_check)
        
        layout.addWidget(files_group)
        
        layout.addStretch()
        return widget
    
    def _load_current_settings(self):
        """Load current settings into form fields."""
        s = self._settings.settings
        
        # ns-3 tab
        self._ns3_path_edit.setText(s.ns3.path)
        if is_windows():
            self._use_wsl_check.setChecked(s.ns3.use_wsl)
            idx = self._wsl_distro_combo.findText(s.ns3.wsl_distribution)
            if idx >= 0:
                self._wsl_distro_combo.setCurrentIndex(idx)
            else:
                self._wsl_distro_combo.setCurrentText(s.ns3.wsl_distribution)
        
        # Workspace tab
        idx = self._profile_combo.findText(s.paths.active_profile)
        if idx >= 0:
            self._profile_combo.setCurrentIndex(idx)
        else:
            self._profile_combo.setCurrentText(s.paths.active_profile)
        
        workspace_path = s.paths.workspaces.get(s.paths.active_profile, "")
        self._workspace_path_edit.setText(workspace_path)
        self._update_effective_path()
        
        # Simulation tab
        self._duration_spin.setValue(s.simulation.duration)
        self._seed_spin.setValue(s.simulation.random_seed)
        self._flow_monitor_check.setChecked(s.simulation.enable_flow_monitor)
        self._ascii_trace_check.setChecked(s.simulation.enable_ascii_trace)
        self._pcap_check.setChecked(s.simulation.enable_pcap)
        
        # UI tab
        self._show_grid_check.setChecked(s.ui.show_grid)
        self._grid_size_spin.setValue(s.ui.grid_size)
        self._show_animations_check.setChecked(s.ui.show_packet_animations)
        self._anim_speed_spin.setValue(s.ui.animation_speed)
        self._recent_files_spin.setValue(s.ui.recent_files_max)
        self._auto_save_check.setChecked(s.ui.auto_save)
        
        # Validate ns-3 path
        self._validate_ns3_path()
    
    def _apply_settings(self):
        """Apply settings from form to settings manager."""
        s = self._settings.settings
        
        # ns-3 tab
        s.ns3.path = self._ns3_path_edit.text().strip()
        if is_windows():
            s.ns3.use_wsl = self._use_wsl_check.isChecked()
            s.ns3.wsl_distribution = self._wsl_distro_combo.currentText()
        
        # Workspace tab
        profile = self._profile_combo.currentText()
        workspace_path = self._workspace_path_edit.text().strip()
        
        s.paths.active_profile = profile
        if workspace_path:
            s.paths.workspaces[profile] = workspace_path
        elif profile in s.paths.workspaces:
            # Clear custom path if empty (use default)
            del s.paths.workspaces[profile]
        
        # Simulation tab
        s.simulation.duration = self._duration_spin.value()
        s.simulation.random_seed = self._seed_spin.value()
        s.simulation.enable_flow_monitor = self._flow_monitor_check.isChecked()
        s.simulation.enable_ascii_trace = self._ascii_trace_check.isChecked()
        s.simulation.enable_pcap = self._pcap_check.isChecked()
        
        # UI tab
        s.ui.show_grid = self._show_grid_check.isChecked()
        s.ui.grid_size = self._grid_size_spin.value()
        s.ui.show_packet_animations = self._show_animations_check.isChecked()
        s.ui.animation_speed = self._anim_speed_spin.value()
        s.ui.recent_files_max = self._recent_files_spin.value()
        s.ui.auto_save = self._auto_save_check.isChecked()
        
        # Save
        self._settings.save()
        self.settingsChanged.emit()
    
    def _on_accept(self):
        """Handle OK button."""
        self._apply_settings()
        self.accept()
    
    def _browse_ns3_path(self):
        """Browse for ns-3 directory."""
        path = QFileDialog.getExistingDirectory(
            self, "Select ns-3 Directory", 
            self._ns3_path_edit.text()
        )
        if path:
            self._ns3_path_edit.setText(path)
    
    def _auto_detect_ns3(self):
        """Auto-detect ns-3 installation."""
        self._ns3_status_label.setText("Searching...")
        self._ns3_status_label.setStyleSheet("color: #6B7280;")
        QApplication.processEvents()
        
        path = NS3Detector.find_ns3_path()
        if path:
            self._ns3_path_edit.setText(path)
            self._ns3_status_label.setText(f"✓ Found: {path}")
            self._ns3_status_label.setStyleSheet("color: #059669;")
        else:
            self._ns3_status_label.setText("✗ Could not find ns-3 installation")
            self._ns3_status_label.setStyleSheet("color: #DC2626;")
    
    def _validate_ns3_path(self):
        """Validate the current ns-3 path."""
        path = self._ns3_path_edit.text().strip()
        if not path:
            self._ns3_status_label.setText("")
            return
        
        use_wsl = is_windows() and (path.startswith('/') or path.startswith('~'))
        
        if NS3Detector.validate_ns3_path(path, use_wsl=use_wsl):
            version = NS3Detector.get_ns3_version(path, use_wsl=use_wsl) or "unknown"
            mode = "WSL" if use_wsl else "native"
            self._ns3_status_label.setText(f"✓ Valid (version: {version}, mode: {mode})")
            self._ns3_status_label.setStyleSheet("color: #059669;")
        else:
            self._ns3_status_label.setText("✗ Invalid ns-3 installation")
            self._ns3_status_label.setStyleSheet("color: #DC2626;")
    
    def _populate_wsl_distributions(self):
        """Populate WSL distribution dropdown."""
        self._wsl_distro_combo.clear()
        self._wsl_distro_combo.addItem("Ubuntu")
        
        if not is_wsl_available():
            return
        
        # Try to get list of distributions
        try:
            import subprocess
            result = subprocess.run(
                ["wsl", "--list", "--quiet"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                distros = [d.strip() for d in result.stdout.split('\n') if d.strip()]
                # Remove duplicates and docker entries
                distros = [d for d in distros if d and 'docker' not in d.lower()]
                
                self._wsl_distro_combo.clear()
                for distro in distros:
                    # Handle weird encoding from wsl --list
                    distro = distro.replace('\x00', '')
                    if distro:
                        self._wsl_distro_combo.addItem(distro)
                
                if self._wsl_distro_combo.count() == 0:
                    self._wsl_distro_combo.addItem("Ubuntu")
        except Exception:
            pass
    
    def _open_settings_folder(self):
        """Open the settings folder in file explorer."""
        import subprocess
        import platform
        
        folder = os.path.dirname(self._settings.settings_path)
        
        if platform.system() == "Windows":
            os.startfile(folder)
        elif platform.system() == "Darwin":
            subprocess.run(["open", folder])
        else:
            subprocess.run(["xdg-open", folder])
    
    def _reset_to_defaults(self):
        """Reset all settings to defaults."""
        reply = QMessageBox.question(
            self,
            "Reset Settings",
            "Are you sure you want to reset all settings to defaults?\n\n"
            "This will clear your ns-3 path and all preferences.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self._settings.reset()
            self._load_current_settings()
            self.settingsChanged.emit()
