"""
NS-3 Import Dialog.

Dialog for importing ns-3 Python example scripts into the GUI.
Parses the script, extracts topology, and saves to workspace.
"""

import os
from pathlib import Path
from typing import Optional, Dict, List

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QPushButton, QFileDialog,
    QGroupBox, QTextEdit, QProgressBar, QDialogButtonBox,
    QMessageBox, QListWidget, QListWidgetItem, QSplitter,
    QWidget, QCheckBox, QApplication
)

from services.settings_manager import SettingsManager
from services.ns3_script_parser import NS3PythonParser, TopologyExporter
from services.topology_converter import TopologyConverter, WorkspaceManager
from services.simulation_runner import (
    is_windows, wsl_to_windows_path, wsl_unc_path_to_linux
)


class NS3ImportDialog(QDialog):
    """
    Dialog for importing a single ns-3 Python example.
    
    Allows user to:
    1. Select an ns-3 Python script file
    2. Preview the parsing results
    3. Import the topology to workspace
    """
    
    def __init__(self, settings_manager: SettingsManager, parent=None):
        super().__init__(parent)
        self.settings_manager = settings_manager
        self._result: Optional[Dict] = None
        self._extracted_topology = None
        self._windows_filepath: str = ""  # Windows-accessible path
        self._linux_filepath: str = ""    # Linux path for ns-3 relative calculation
        
        self._setup_ui()
        self._update_ns3_path()
    
    def _setup_ui(self):
        """Set up the dialog UI."""
        self.setWindowTitle("Import ns-3 Example")
        self.setMinimumSize(800, 700)
        
        layout = QVBoxLayout(self)
        
        # ns-3 path info
        ns3_group = QGroupBox("ns-3 Installation")
        ns3_layout = QHBoxLayout(ns3_group)
        
        self._ns3_path_label = QLabel()
        self._ns3_path_label.setWordWrap(True)
        ns3_layout.addWidget(QLabel("Path:"))
        ns3_layout.addWidget(self._ns3_path_label, 1)
        
        # Scan button
        self._scan_btn = QPushButton("Scan for Python Files")
        self._scan_btn.clicked.connect(self._on_scan)
        ns3_layout.addWidget(self._scan_btn)
        
        layout.addWidget(ns3_group)
        
        # Scanned files table
        scan_group = QGroupBox("Discovered Python Files (double-click to select)")
        scan_layout = QVBoxLayout(scan_group)
        
        self._scan_table = QListWidget()
        self._scan_table.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self._scan_table.itemDoubleClicked.connect(self._on_scan_item_double_clicked)
        self._scan_table.setMinimumHeight(150)
        scan_layout.addWidget(self._scan_table)
        
        self._scan_status_label = QLabel("Click 'Scan for Python Files' to search ns-3 directory")
        self._scan_status_label.setStyleSheet("color: #6B7280;")
        scan_layout.addWidget(self._scan_status_label)
        
        layout.addWidget(scan_group)
        
        # File selection (manual)
        file_group = QGroupBox("Selected Python Script")
        file_layout = QHBoxLayout(file_group)
        
        self._file_edit = QLineEdit()
        self._file_edit.setPlaceholderText("Select an ns-3 Python example file...")
        self._file_edit.textChanged.connect(self._on_file_changed)
        file_layout.addWidget(self._file_edit)
        
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._on_browse)
        file_layout.addWidget(browse_btn)
        
        layout.addWidget(file_group)
        
        # Preview area
        preview_group = QGroupBox("Preview")
        preview_layout = QVBoxLayout(preview_group)
        
        self._preview_text = QTextEdit()
        self._preview_text.setReadOnly(True)
        self._preview_text.setMaximumHeight(150)
        preview_layout.addWidget(self._preview_text)
        
        # Parse button
        parse_layout = QHBoxLayout()
        self._parse_btn = QPushButton("Parse Script")
        self._parse_btn.clicked.connect(self._on_parse)
        self._parse_btn.setEnabled(False)
        parse_layout.addWidget(self._parse_btn)
        parse_layout.addStretch()
        preview_layout.addLayout(parse_layout)
        
        layout.addWidget(preview_group)
        
        # Results area
        results_group = QGroupBox("Extraction Results")
        results_layout = QFormLayout(results_group)
        
        self._nodes_label = QLabel("-")
        results_layout.addRow("Nodes:", self._nodes_label)
        
        self._links_label = QLabel("-")
        results_layout.addRow("Links:", self._links_label)
        
        self._description_label = QLabel("-")
        self._description_label.setWordWrap(True)
        results_layout.addRow("Description:", self._description_label)
        
        self._status_label = QLabel("")
        self._status_label.setWordWrap(True)
        results_layout.addRow("Status:", self._status_label)
        
        layout.addWidget(results_group)
        
        # Output path
        output_group = QGroupBox("Output")
        output_layout = QFormLayout(output_group)
        
        self._output_path_label = QLabel("-")
        self._output_path_label.setWordWrap(True)
        output_layout.addRow("Will save to:", self._output_path_label)
        
        layout.addWidget(output_group)
        
        # Buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self._on_accept)
        button_box.rejected.connect(self.reject)
        self._ok_btn = button_box.button(QDialogButtonBox.StandardButton.Ok)
        self._ok_btn.setText("Import")
        self._ok_btn.setEnabled(False)
        layout.addWidget(button_box)
    
    def _update_ns3_path(self):
        """Update ns-3 path display."""
        ns3_path = self.settings_manager.ns3_path
        if ns3_path:
            # Show Windows-accessible path if on Windows
            if is_windows() and ns3_path.startswith('/'):
                distro = self.settings_manager.wsl_distribution or "Ubuntu"
                display_path = wsl_to_windows_path(ns3_path, distro)
            else:
                display_path = ns3_path
            
            self._ns3_path_label.setText(display_path)
            self._ns3_path_label.setStyleSheet("color: #059669;")
        else:
            self._ns3_path_label.setText("Not configured - set in Settings")
            self._ns3_path_label.setStyleSheet("color: #DC2626;")
    
    def _on_scan(self):
        """Scan ns-3 directory for Python files using find command."""
        import subprocess
        
        ns3_path = self.settings_manager.ns3_path
        if not ns3_path:
            QMessageBox.warning(
                self,
                "ns-3 Not Found",
                "Please configure the ns-3 path in Settings first."
            )
            return
        
        self._scan_table.clear()
        self._scan_status_label.setText("Scanning...")
        self._scan_status_label.setStyleSheet("color: #6B7280;")
        QApplication.processEvents()
        
        try:
            # Run find command via WSL on Windows
            if is_windows():
                distro = self.settings_manager.wsl_distribution or "Ubuntu"
                # Use bash -c to properly handle the find command with quoted pattern
                find_cmd = f'find "{ns3_path}" -name "*.py" -type f'
                cmd = ["wsl", "-d", distro, "bash", "-c", find_cmd]
            else:
                # Native Linux/Mac
                cmd = ["find", ns3_path, "-name", "*.py", "-type", "f"]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60  # 60 second timeout
            )
            
            if result.returncode != 0:
                self._scan_status_label.setText(f"Scan failed: {result.stderr[:100]}")
                self._scan_status_label.setStyleSheet("color: #DC2626;")
                return
            
            # Parse results - these are Linux paths from WSL
            files = [f.strip() for f in result.stdout.strip().split('\n') if f.strip()]
            
            # Filter out __pycache__, test files, etc.
            filtered_files = []
            for f in files:
                if '__pycache__' in f:
                    continue
                if '/.git/' in f or '\\.git\\' in f:
                    continue
                # Keep the file
                filtered_files.append(f)
            
            # Sort by path
            filtered_files.sort()
            
            # Get distro for path conversion
            distro = self.settings_manager.wsl_distribution or "Ubuntu"
            
            # Populate table with Windows-accessible paths
            for linux_path in filtered_files:
                # Convert to Windows path for display and use
                if is_windows():
                    win_path = wsl_to_windows_path(linux_path, distro)
                    display_path = win_path
                else:
                    display_path = linux_path
                
                item = QListWidgetItem(display_path)
                # Store the Windows-accessible path as data
                item.setData(Qt.ItemDataRole.UserRole, display_path)
                self._scan_table.addItem(item)
            
            self._scan_status_label.setText(f"Found {len(filtered_files)} Python files. Double-click to select.")
            self._scan_status_label.setStyleSheet("color: #059669;")
            
        except subprocess.TimeoutExpired:
            self._scan_status_label.setText("Scan timed out. Try a more specific path.")
            self._scan_status_label.setStyleSheet("color: #DC2626;")
        except Exception as e:
            self._scan_status_label.setText(f"Scan error: {str(e)[:100]}")
            self._scan_status_label.setStyleSheet("color: #DC2626;")
    
    def _on_scan_item_double_clicked(self, item: QListWidgetItem):
        """Handle double-click on scanned file - populate file edit."""
        filepath = item.data(Qt.ItemDataRole.UserRole)
        if filepath:
            # Path is already in the correct format (Windows or Linux)
            self._file_edit.setText(filepath)

    def _on_browse(self):
        """Browse for ns-3 Python script."""
        # Start in ns-3 examples directory if available
        start_dir = ""
        ns3_path = self.settings_manager.ns3_path
        
        if ns3_path:
            # Convert WSL path to Windows-accessible path if on Windows
            if is_windows() and ns3_path.startswith('/'):
                # Get WSL distro from settings
                distro = self.settings_manager.wsl_distribution or "Ubuntu"
                win_ns3_path = wsl_to_windows_path(ns3_path, distro)
                examples_dir = Path(win_ns3_path) / "src"
                
                if examples_dir.exists():
                    start_dir = str(examples_dir)
                elif Path(win_ns3_path).exists():
                    start_dir = win_ns3_path
            else:
                # Native path
                examples_dir = Path(ns3_path) / "src"
                if examples_dir.exists():
                    start_dir = str(examples_dir)
                else:
                    start_dir = ns3_path
        
        filepath, _ = QFileDialog.getOpenFileName(
            self,
            "Select ns-3 Python Example",
            start_dir,
            "Python Scripts (*.py);;All Files (*)"
        )
        
        if filepath:
            # QFileDialog returns forward slashes even on Windows for UNC paths
            # Just set the text - _on_file_changed will handle normalization
            self._file_edit.setText(filepath)
    
    def _on_file_changed(self, text: str):
        """Handle file path change."""
        if not text:
            self._parse_btn.setEnabled(False)
            self._output_path_label.setText("-")
            return
        
        # Normalize the path - QFileDialog may return forward slashes
        normalized_path = text.replace('/', '\\') if is_windows() else text
        
        # Determine actual file path for validation
        actual_path = self._get_actual_filepath(normalized_path)
        
        # Try to check if file exists
        try:
            path = Path(actual_path) if actual_path else None
            exists = path.exists() if path else False
            is_py = path.suffix == ".py" if path else False
        except Exception as e:
            exists = False
            is_py = False
            print(f"DEBUG: Exception checking path: {e}")
        
        # Debug output - show in status label for visibility
        debug_info = (
            f"Input: {text[:50]}...\n"
            f"Normalized: {normalized_path[:50]}...\n"
            f"Actual: {actual_path[:50] if actual_path else 'None'}...\n"
            f"Exists: {exists}, Is .py: {is_py}"
        )
        print(f"DEBUG _on_file_changed:\n{debug_info}")
        
        valid = exists and is_py
        self._parse_btn.setEnabled(valid)
        
        if valid:
            # Update output path preview (use the Linux-style path for ns-3 structure)
            linux_path = wsl_unc_path_to_linux(text)
            self._update_output_path(Path(linux_path))
            # Store paths for later
            self._windows_filepath = actual_path
            self._linux_filepath = linux_path
            self._status_label.setText(f"✓ File found")
            self._status_label.setStyleSheet("color: #059669;")
        else:
            self._output_path_label.setText("-")
            self._status_label.setText(f"File not found or invalid:\n{actual_path}")
            self._status_label.setStyleSheet("color: #DC2626;")
    
    def _get_actual_filepath(self, display_path: str) -> str:
        """
        Get the actual filesystem path for a displayed path.
        
        Handles:
        - Windows UNC paths: \\\\wsl$\\Ubuntu\\... or //wsl$/Ubuntu/...
        - Linux paths: /home/user/...
        - Windows paths: C:\\...
        """
        if not display_path:
            return display_path
        
        # Normalize slashes for Windows
        if is_windows():
            normalized = display_path.replace('/', '\\')
        else:
            normalized = display_path
        
        # If it's already a UNC path (\\wsl$\... or \\wsl.localhost\...)
        if normalized.startswith('\\\\wsl'):
            return normalized
        
        # If it's a Linux path and we're on Windows, convert to UNC
        if is_windows() and normalized.startswith('\\') and not normalized.startswith('\\\\'):
            # Single backslash start - might be a weird path, treat as Linux
            distro = self.settings_manager.wsl_distribution or "Ubuntu"
            linux_path = normalized.replace('\\', '/')
            return wsl_to_windows_path(linux_path, distro)
        
        if is_windows() and display_path.startswith('/'):
            # Linux-style path on Windows
            distro = self.settings_manager.wsl_distribution or "Ubuntu"
            return wsl_to_windows_path(display_path, distro)
        
        return normalized
    
    def _update_output_path(self, script_path: Path):
        """Update the output path preview."""
        workspace_root = self.settings_manager.paths.get_workspace_root()
        
        # Try to determine relative path from ns-3
        ns3_path = self.settings_manager.ns3_path
        if ns3_path:
            try:
                rel_path = script_path.relative_to(ns3_path)
            except ValueError:
                rel_path = Path(script_path.name)
        else:
            rel_path = Path(script_path.name)
        
        # Calculate output path
        workspace = WorkspaceManager(workspace_root)
        output_path = workspace.get_topology_path(rel_path)
        
        self._output_path_label.setText(str(output_path))
    
    def _on_parse(self):
        """Parse the selected script."""
        display_path = self._file_edit.text()
        actual_path = self._get_actual_filepath(display_path)
        filepath = Path(actual_path)
        
        if not filepath.exists():
            self._status_label.setText(f"✗ File not found: {filepath}")
            self._status_label.setStyleSheet("color: #DC2626;")
            return
        
        self._preview_text.clear()
        self._status_label.setText("Parsing...")
        self._status_label.setStyleSheet("color: #6B7280;")
        QApplication.processEvents()
        
        # Parse the script
        parser = NS3PythonParser()
        self._extracted_topology = parser.parse_file(filepath)
        
        # Store the Linux path for relative path calculation
        if display_path.startswith('/'):
            self._linux_filepath = display_path
        else:
            self._linux_filepath = wsl_unc_path_to_linux(display_path)
        
        # Update preview with script content
        try:
            with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()[:2000]  # First 2000 chars
                if len(content) == 2000:
                    content += "\n... (truncated)"
                self._preview_text.setPlainText(content)
        except Exception as e:
            self._preview_text.setPlainText(f"Error reading file: {e}")
        
        # Update results
        topo = self._extracted_topology
        self._nodes_label.setText(str(len(topo.nodes)))
        self._links_label.setText(str(len(topo.links)))
        self._description_label.setText(topo.description[:200] if topo.description else "-")
        
        if topo.parse_success:
            self._status_label.setText("✓ Parsing successful")
            self._status_label.setStyleSheet("color: #059669;")
            self._ok_btn.setEnabled(True)
        else:
            errors = "\n".join(topo.errors[:3])
            self._status_label.setText(f"✗ Parsing failed:\n{errors}")
            self._status_label.setStyleSheet("color: #DC2626;")
            self._ok_btn.setEnabled(False)
        
        if topo.warnings:
            current = self._status_label.text()
            warnings = "\n".join(topo.warnings[:3])
            self._status_label.setText(f"{current}\n\nWarnings:\n{warnings}")
    
    def _on_accept(self):
        """Accept and import the topology."""
        if not self._extracted_topology or not self._extracted_topology.parse_success:
            return
        
        # Use the Linux path for relative path calculation
        linux_path = getattr(self, '_linux_filepath', self._file_edit.text())
        filepath = Path(linux_path)
        workspace_root = self.settings_manager.paths.get_workspace_root()
        
        # Calculate relative path from ns-3 root
        ns3_path = self.settings_manager.ns3_path
        if ns3_path:
            try:
                rel_path = filepath.relative_to(ns3_path)
            except ValueError:
                rel_path = Path(filepath.name)
        else:
            rel_path = Path(filepath.name)
        
        try:
            # Convert to NetworkModel and TrafficFlows
            converter = TopologyConverter()
            network, traffic_flows = converter.convert(self._extracted_topology)
            
            # Save to workspace
            workspace = WorkspaceManager(workspace_root)
            workspace.ensure_directories()
            
            # Save extracted data
            workspace.save_extracted(self._extracted_topology, rel_path)
            
            # Save topology
            topology_path = workspace.save_topology(network, rel_path)
            
            # Store result
            self._result = {
                "success": True,
                "topology_path": str(topology_path),
                "node_count": len(network.nodes),
                "link_count": len(network.links),
                "source_file": linux_path,
                "traffic_flows": traffic_flows,
            }
            
            self.accept()
            
        except Exception as e:
            QMessageBox.critical(
                self,
                "Import Error",
                f"Failed to import topology:\n{e}"
            )
    
    def get_result(self) -> Optional[Dict]:
        """Get the import result."""
        return self._result


class BatchImportWorker(QThread):
    """Worker thread for batch importing ns-3 examples."""
    
    progress = pyqtSignal(int, int, str)  # current, total, path
    file_completed = pyqtSignal(dict)  # result dict
    finished_all = pyqtSignal(list)  # all results
    
    def __init__(self, ns3_path: str, workspace_path: str, files: List[Path]):
        super().__init__()
        self.ns3_path = ns3_path
        self.workspace_path = workspace_path
        self.files = files
        self._cancelled = False
    
    def cancel(self):
        """Cancel the import."""
        self._cancelled = True
    
    def run(self):
        """Run the batch import."""
        from services.topology_converter import NS3ExampleProcessor
        
        processor = NS3ExampleProcessor(self.ns3_path, self.workspace_path)
        results = []
        
        for i, rel_path in enumerate(self.files):
            if self._cancelled:
                break
            
            self.progress.emit(i, len(self.files), str(rel_path))
            
            result = processor.process_file(str(rel_path))
            results.append(result)
            self.file_completed.emit(result)
        
        self.progress.emit(len(self.files), len(self.files), "Done")
        self.finished_all.emit(results)


class NS3BatchImportDialog(QDialog):
    """
    Dialog for batch importing ns-3 Python examples.
    
    Discovers all Python examples in ns-3 and allows batch import.
    """
    
    def __init__(self, settings_manager: SettingsManager, parent=None):
        super().__init__(parent)
        self.settings_manager = settings_manager
        self._worker: Optional[BatchImportWorker] = None
        self._discovered_files: List[Path] = []
        
        self._setup_ui()
        self._check_ns3_path()
    
    def _setup_ui(self):
        """Set up the dialog UI."""
        self.setWindowTitle("Batch Import ns-3 Examples")
        self.setMinimumSize(700, 600)
        
        layout = QVBoxLayout(self)
        
        # ns-3 path info
        ns3_group = QGroupBox("ns-3 Installation")
        ns3_layout = QHBoxLayout(ns3_group)
        
        self._ns3_path_label = QLabel()
        self._ns3_path_label.setWordWrap(True)
        ns3_layout.addWidget(self._ns3_path_label, 1)
        
        discover_btn = QPushButton("Discover Examples")
        discover_btn.clicked.connect(self._on_discover)
        ns3_layout.addWidget(discover_btn)
        
        layout.addWidget(ns3_group)
        
        # Splitter for file list and results
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # File list
        file_widget = QWidget()
        file_layout = QVBoxLayout(file_widget)
        file_layout.setContentsMargins(0, 0, 0, 0)
        
        file_layout.addWidget(QLabel("Discovered Python Examples:"))
        
        self._file_list = QListWidget()
        self._file_list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        file_layout.addWidget(self._file_list)
        
        select_layout = QHBoxLayout()
        select_all_btn = QPushButton("Select All")
        select_all_btn.clicked.connect(self._on_select_all)
        select_layout.addWidget(select_all_btn)
        
        select_none_btn = QPushButton("Select None")
        select_none_btn.clicked.connect(self._on_select_none)
        select_layout.addWidget(select_none_btn)
        
        select_layout.addStretch()
        file_layout.addLayout(select_layout)
        
        splitter.addWidget(file_widget)
        
        # Results area
        results_widget = QWidget()
        results_layout = QVBoxLayout(results_widget)
        results_layout.setContentsMargins(0, 0, 0, 0)
        
        results_layout.addWidget(QLabel("Import Results:"))
        
        self._results_text = QTextEdit()
        self._results_text.setReadOnly(True)
        results_layout.addWidget(self._results_text)
        
        splitter.addWidget(results_widget)
        splitter.setSizes([350, 350])
        
        layout.addWidget(splitter)
        
        # Progress
        progress_layout = QHBoxLayout()
        
        self._progress_bar = QProgressBar()
        self._progress_bar.setVisible(False)
        progress_layout.addWidget(self._progress_bar)
        
        self._progress_label = QLabel("")
        progress_layout.addWidget(self._progress_label)
        
        layout.addLayout(progress_layout)
        
        # Summary
        self._summary_label = QLabel("")
        self._summary_label.setWordWrap(True)
        layout.addWidget(self._summary_label)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        self._import_btn = QPushButton("Import Selected")
        self._import_btn.clicked.connect(self._on_import)
        self._import_btn.setEnabled(False)
        button_layout.addWidget(self._import_btn)
        
        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.clicked.connect(self._on_cancel)
        self._cancel_btn.setVisible(False)
        button_layout.addWidget(self._cancel_btn)
        
        button_layout.addStretch()
        
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        button_layout.addWidget(close_btn)
        
        layout.addLayout(button_layout)
    
    def _check_ns3_path(self):
        """Check if ns-3 path is configured."""
        ns3_path = self.settings_manager.ns3_path
        
        # Convert to Windows path if needed for validation
        if ns3_path:
            actual_path = ns3_path
            if is_windows() and ns3_path.startswith('/'):
                distro = self.settings_manager.wsl_distribution or "Ubuntu"
                actual_path = wsl_to_windows_path(ns3_path, distro)
            
            if os.path.isdir(actual_path):
                self._ns3_path_label.setText(f"✓ {ns3_path}")
                self._ns3_path_label.setStyleSheet("color: #059669;")
                return
        
        self._ns3_path_label.setText("✗ ns-3 path not configured. Set in Edit → Settings.")
        self._ns3_path_label.setStyleSheet("color: #DC2626;")
    
    def _get_ns3_windows_path(self) -> Optional[str]:
        """Get the Windows-accessible ns-3 path."""
        ns3_path = self.settings_manager.ns3_path
        if not ns3_path:
            return None
        
        if is_windows() and ns3_path.startswith('/'):
            distro = self.settings_manager.wsl_distribution or "Ubuntu"
            return wsl_to_windows_path(ns3_path, distro)
        
        return ns3_path
    
    def _on_discover(self):
        """Discover Python examples in ns-3."""
        ns3_path = self.settings_manager.ns3_path
        actual_path = self._get_ns3_windows_path()
        
        if not actual_path or not os.path.isdir(actual_path):
            QMessageBox.warning(
                self,
                "ns-3 Not Found",
                "Please configure the ns-3 path in Settings first.\n\n"
                f"Configured path: {ns3_path}\n"
                f"Actual path: {actual_path}"
            )
            return
        
        self._file_list.clear()
        self._discovered_files = []
        
        self._progress_label.setText("Discovering files...")
        QApplication.processEvents()
        
        ns3_root = Path(actual_path)
        
        # Find Python examples
        patterns = [
            "src/*/examples/*.py",
            "examples/**/*.py",
        ]
        
        for pattern in patterns:
            for py_file in ns3_root.glob(pattern):
                # Filter out test files and __init__.py
                if (py_file.name.startswith("test_") or 
                    py_file.name == "__init__.py" or
                    "test" in py_file.parts):
                    continue
                
                try:
                    rel_path = py_file.relative_to(ns3_root)
                    self._discovered_files.append(rel_path)
                except ValueError:
                    pass
        
        # Sort and deduplicate
        self._discovered_files = sorted(set(self._discovered_files))
        
        # Populate list
        for rel_path in self._discovered_files:
            item = QListWidgetItem(str(rel_path))
            item.setData(Qt.ItemDataRole.UserRole, rel_path)
            self._file_list.addItem(item)
        
        self._progress_label.setText(f"Found {len(self._discovered_files)} Python examples")
        self._import_btn.setEnabled(len(self._discovered_files) > 0)
    
    def _on_select_all(self):
        """Select all files."""
        self._file_list.selectAll()
    
    def _on_select_none(self):
        """Deselect all files."""
        self._file_list.clearSelection()
    
    def _on_import(self):
        """Start batch import."""
        selected_items = self._file_list.selectedItems()
        if not selected_items:
            QMessageBox.information(
                self,
                "No Selection",
                "Please select files to import."
            )
            return
        
        selected_files = [item.data(Qt.ItemDataRole.UserRole) for item in selected_items]
        
        # Use Windows-accessible path for file operations
        ns3_path = self._get_ns3_windows_path()
        workspace_path = str(self.settings_manager.paths.get_workspace_root())
        
        # Clear results
        self._results_text.clear()
        
        # Set up progress
        self._progress_bar.setVisible(True)
        self._progress_bar.setMaximum(len(selected_files))
        self._progress_bar.setValue(0)
        
        self._import_btn.setEnabled(False)
        self._cancel_btn.setVisible(True)
        
        # Start worker
        self._worker = BatchImportWorker(ns3_path, workspace_path, selected_files)
        self._worker.progress.connect(self._on_progress)
        self._worker.file_completed.connect(self._on_file_completed)
        self._worker.finished_all.connect(self._on_finished)
        self._worker.start()
    
    def _on_cancel(self):
        """Cancel the import."""
        if self._worker:
            self._worker.cancel()
            self._progress_label.setText("Cancelling...")
    
    def _on_progress(self, current: int, total: int, path: str):
        """Handle progress update."""
        self._progress_bar.setValue(current)
        self._progress_label.setText(f"Processing {current}/{total}: {path}")
    
    def _on_file_completed(self, result: dict):
        """Handle single file completion."""
        path = result.get("relative_path", "unknown")
        if result.get("success"):
            self._results_text.append(
                f"✓ {path} - {result.get('node_count', 0)} nodes, "
                f"{result.get('link_count', 0)} links"
            )
        else:
            errors = ", ".join(result.get("errors", ["unknown error"])[:2])
            self._results_text.append(f"✗ {path} - {errors}")
    
    def _on_finished(self, results: list):
        """Handle batch completion."""
        self._progress_bar.setVisible(False)
        self._cancel_btn.setVisible(False)
        self._import_btn.setEnabled(True)
        
        # Calculate summary
        successful = [r for r in results if r.get("success")]
        failed = [r for r in results if not r.get("success")]
        total_nodes = sum(r.get("node_count", 0) for r in successful)
        total_links = sum(r.get("link_count", 0) for r in successful)
        
        self._summary_label.setText(
            f"Completed: {len(successful)}/{len(results)} successful, "
            f"{total_nodes} total nodes, {total_links} total links"
        )
        
        if successful:
            self._summary_label.setStyleSheet("color: #059669; font-weight: bold;")
        else:
            self._summary_label.setStyleSheet("color: #DC2626; font-weight: bold;")
        
        self._worker = None
    
    def closeEvent(self, event):
        """Handle close event."""
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
            self._worker.wait(2000)
        super().closeEvent(event)
