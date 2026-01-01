"""
Project Dialog - UI for managing projects and workspace.

Provides dialogs for:
- Creating new projects
- Opening existing projects  
- Managing workspace location
- Viewing project details
"""

import os
from pathlib import Path
from datetime import datetime
from typing import Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QPushButton, QFileDialog,
    QGroupBox, QTextEdit, QListWidget, QListWidgetItem,
    QDialogButtonBox, QMessageBox, QTabWidget, QWidget,
    QSplitter, QTreeWidget, QTreeWidgetItem, QHeaderView,
    QApplication
)
from PyQt6.QtGui import QFont

from models.project import Project, ProjectManager, ProjectMetadata
from services.settings_manager import SettingsManager


class NewProjectDialog(QDialog):
    """Dialog for creating a new project."""
    
    def __init__(self, project_manager: ProjectManager, parent=None):
        super().__init__(parent)
        self.project_manager = project_manager
        self._created_project: Optional[Project] = None
        
        self._setup_ui()
    
    def _setup_ui(self):
        self.setWindowTitle("New Project")
        self.setMinimumWidth(450)
        
        layout = QVBoxLayout(self)
        
        # Project info
        form = QFormLayout()
        
        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText("Enter project name...")
        self._name_edit.textChanged.connect(self._validate)
        form.addRow("Project Name:", self._name_edit)
        
        self._desc_edit = QTextEdit()
        self._desc_edit.setPlaceholderText("Optional description...")
        self._desc_edit.setMaximumHeight(80)
        form.addRow("Description:", self._desc_edit)
        
        layout.addLayout(form)
        
        # Location info
        location_group = QGroupBox("Project Location")
        loc_layout = QVBoxLayout(location_group)
        
        self._location_label = QLabel()
        self._location_label.setWordWrap(True)
        self._location_label.setStyleSheet("color: #6B7280;")
        loc_layout.addWidget(self._location_label)
        
        layout.addWidget(location_group)
        
        # Buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self._on_create)
        button_box.rejected.connect(self.reject)
        self._ok_btn = button_box.button(QDialogButtonBox.StandardButton.Ok)
        self._ok_btn.setText("Create Project")
        self._ok_btn.setEnabled(False)
        layout.addWidget(button_box)
        
        self._update_location()
    
    def _validate(self):
        """Validate input and update UI."""
        name = self._name_edit.text().strip()
        valid = len(name) > 0
        self._ok_btn.setEnabled(valid)
        self._update_location()
    
    def _update_location(self):
        """Update location preview."""
        name = self._name_edit.text().strip()
        if name:
            # Sanitize name
            safe_name = "".join(c for c in name if c.isalnum() or c in "._- ").strip()
            if not safe_name:
                safe_name = "untitled"
            path = self.project_manager.projects_dir / safe_name
            self._location_label.setText(f"Will be created at:\n{path}")
        else:
            self._location_label.setText(f"Projects folder:\n{self.project_manager.projects_dir}")
    
    def _on_create(self):
        """Create the project."""
        name = self._name_edit.text().strip()
        description = self._desc_edit.toPlainText().strip()
        
        try:
            self._created_project = self.project_manager.create_project(name, description)
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to create project:\n{e}")
    
    def get_project(self) -> Optional[Project]:
        """Get the created project."""
        return self._created_project


class OpenProjectDialog(QDialog):
    """Dialog for opening an existing project."""
    
    def __init__(self, project_manager: ProjectManager, parent=None):
        super().__init__(parent)
        self.project_manager = project_manager
        self._selected_project: Optional[Project] = None
        
        self._setup_ui()
        self._load_projects()
    
    def _setup_ui(self):
        self.setWindowTitle("Open Project")
        self.setMinimumSize(600, 450)
        
        layout = QVBoxLayout(self)
        
        # Workspace info
        workspace_layout = QHBoxLayout()
        workspace_layout.addWidget(QLabel("Workspace:"))
        self._workspace_label = QLabel(str(self.project_manager.projects_dir))
        self._workspace_label.setStyleSheet("color: #059669; font-weight: bold;")
        workspace_layout.addWidget(self._workspace_label, 1)
        
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self._load_projects)
        workspace_layout.addWidget(refresh_btn)
        
        layout.addLayout(workspace_layout)
        
        # Project list
        self._project_tree = QTreeWidget()
        self._project_tree.setHeaderLabels(["Name", "Description", "Modified", "Runs"])
        self._project_tree.setRootIsDecorated(False)
        self._project_tree.setAlternatingRowColors(True)
        self._project_tree.itemDoubleClicked.connect(self._on_double_click)
        self._project_tree.itemSelectionChanged.connect(self._on_selection_changed)
        
        header = self._project_tree.header()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        
        layout.addWidget(self._project_tree)
        
        # Project details
        details_group = QGroupBox("Project Details")
        details_layout = QFormLayout(details_group)
        
        self._path_label = QLabel("-")
        self._path_label.setWordWrap(True)
        details_layout.addRow("Path:", self._path_label)
        
        self._has_topology_label = QLabel("-")
        details_layout.addRow("Has Topology:", self._has_topology_label)
        
        layout.addWidget(details_group)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        delete_btn = QPushButton("Delete Project")
        delete_btn.clicked.connect(self._on_delete)
        btn_layout.addWidget(delete_btn)
        
        btn_layout.addStretch()
        
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Open |
            QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self._on_open)
        button_box.rejected.connect(self.reject)
        self._open_btn = button_box.button(QDialogButtonBox.StandardButton.Open)
        self._open_btn.setEnabled(False)
        btn_layout.addWidget(button_box)
        
        layout.addLayout(btn_layout)
    
    def _load_projects(self):
        """Load and display projects."""
        self._project_tree.clear()
        
        try:
            projects = self.project_manager.list_projects()
            
            for proj in projects:
                item = QTreeWidgetItem([
                    proj["name"],
                    proj.get("description", "")[:50],
                    self._format_date(proj.get("modified", "")),
                    str(proj.get("run_count", 0))
                ])
                item.setData(0, Qt.ItemDataRole.UserRole, proj)
                self._project_tree.addTopLevelItem(item)
            
            if not projects:
                item = QTreeWidgetItem(["(No projects found)", "", "", ""])
                item.setFlags(Qt.ItemFlag.NoItemFlags)
                self._project_tree.addTopLevelItem(item)
                
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to load projects:\n{e}")
    
    def _format_date(self, iso_date: str) -> str:
        """Format ISO date for display."""
        if not iso_date:
            return "-"
        try:
            dt = datetime.fromisoformat(iso_date)
            return dt.strftime("%Y-%m-%d %H:%M")
        except:
            return iso_date[:16] if len(iso_date) > 16 else iso_date
    
    def _on_selection_changed(self):
        """Handle selection change."""
        items = self._project_tree.selectedItems()
        if items:
            proj = items[0].data(0, Qt.ItemDataRole.UserRole)
            if proj:
                self._path_label.setText(proj.get("path", "-"))
                self._has_topology_label.setText("Yes" if proj.get("has_topology") else "No")
                self._open_btn.setEnabled(True)
            else:
                self._clear_details()
        else:
            self._clear_details()
    
    def _clear_details(self):
        """Clear details panel."""
        self._path_label.setText("-")
        self._has_topology_label.setText("-")
        self._open_btn.setEnabled(False)
    
    def _on_double_click(self, item: QTreeWidgetItem, column: int):
        """Handle double-click to open."""
        proj = item.data(0, Qt.ItemDataRole.UserRole)
        if proj:
            self._on_open()
    
    def _on_open(self):
        """Open selected project."""
        items = self._project_tree.selectedItems()
        if not items:
            return
        
        proj = items[0].data(0, Qt.ItemDataRole.UserRole)
        if not proj:
            return
        
        try:
            self._selected_project = self.project_manager.open_project(proj["path"])
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to open project:\n{e}")
    
    def _on_delete(self):
        """Delete selected project."""
        items = self._project_tree.selectedItems()
        if not items:
            return
        
        proj = items[0].data(0, Qt.ItemDataRole.UserRole)
        if not proj:
            return
        
        reply = QMessageBox.question(
            self,
            "Delete Project",
            f"Are you sure you want to delete '{proj['name']}'?\n\n"
            "This will permanently delete all project files including:\n"
            "- Topology\n"
            "- Generated scripts\n"
            "- Simulation results\n\n"
            "This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                self.project_manager.delete_project(proj["path"])
                self._load_projects()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to delete project:\n{e}")
    
    def get_project(self) -> Optional[Project]:
        """Get the opened project."""
        return self._selected_project


class WorkspaceSettingsDialog(QDialog):
    """Dialog for configuring workspace location."""
    
    workspaceChanged = pyqtSignal(str)
    
    def __init__(self, settings_manager: SettingsManager, parent=None):
        super().__init__(parent)
        self.settings_manager = settings_manager
        
        self._setup_ui()
        self._load_settings()
    
    def _setup_ui(self):
        self.setWindowTitle("Workspace Settings")
        self.setMinimumWidth(500)
        
        layout = QVBoxLayout(self)
        
        # Info
        info_label = QLabel(
            "The workspace is where all your projects are stored.\n"
            "Each project contains its topology, scripts, and simulation results."
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: #6B7280; margin-bottom: 2px;")
        layout.addWidget(info_label)
        
        # Current workspace
        current_group = QGroupBox("Current Workspace")
        current_layout = QVBoxLayout(current_group)
        
        self._current_path_label = QLabel()
        self._current_path_label.setWordWrap(True)
        self._current_path_label.setStyleSheet("font-weight: bold;")
        current_layout.addWidget(self._current_path_label)
        
        layout.addWidget(current_group)
        
        # Change workspace
        change_group = QGroupBox("Change Workspace")
        change_layout = QVBoxLayout(change_group)
        
        path_layout = QHBoxLayout()
        self._path_edit = QLineEdit()
        self._path_edit.setPlaceholderText("Select workspace folder...")
        path_layout.addWidget(self._path_edit)
        
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._on_browse)
        path_layout.addWidget(browse_btn)
        
        change_layout.addLayout(path_layout)
        
        # Default button
        default_btn = QPushButton("Reset to Default Location")
        default_btn.clicked.connect(self._on_reset_default)
        change_layout.addWidget(default_btn)
        
        layout.addWidget(change_group)
        
        # Structure preview
        structure_group = QGroupBox("Workspace Structure")
        structure_layout = QVBoxLayout(structure_group)
        
        structure_text = QLabel(
            "workspace/\n"
            "└── projects/\n"
            "    └── my_project/\n"
            "        ├── project.json\n"
            "        ├── topology.json\n"
            "        ├── flows.json\n"
            "        ├── scripts/\n"
            "        ├── results/\n"
            "        └── imports/"
        )
        structure_text.setFont(QFont("Consolas", 9))
        structure_text.setStyleSheet("color: #6B7280; background: #F3F4F6; padding: 2px;")
        structure_layout.addWidget(structure_text)
        
        layout.addWidget(structure_group)
        
        # Buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save |
            QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self._on_save)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
    
    def _load_settings(self):
        """Load current settings."""
        current_path = self.settings_manager.paths.get_workspace_root()
        self._current_path_label.setText(str(current_path))
        self._path_edit.setText(str(current_path))
    
    def _on_browse(self):
        """Browse for workspace folder."""
        current = self._path_edit.text() or str(Path.home())
        
        folder = QFileDialog.getExistingDirectory(
            self,
            "Select Workspace Folder",
            current,
            QFileDialog.Option.ShowDirsOnly
        )
        
        if folder:
            self._path_edit.setText(folder)
    
    def _on_reset_default(self):
        """Reset to default workspace location."""
        default_path = self.settings_manager.paths._get_default_workspace()
        self._path_edit.setText(str(default_path))
    
    def _on_save(self):
        """Save workspace settings."""
        new_path = self._path_edit.text().strip()
        
        if not new_path:
            QMessageBox.warning(self, "Error", "Please specify a workspace path.")
            return
        
        # Update settings
        self.settings_manager.paths.workspaces["default"] = new_path
        self.settings_manager.save()
        
        # Create directory if needed
        try:
            Path(new_path).mkdir(parents=True, exist_ok=True)
            (Path(new_path) / "projects").mkdir(exist_ok=True)
        except Exception as e:
            QMessageBox.warning(self, "Warning", f"Could not create workspace folder:\n{e}")
        
        self.workspaceChanged.emit(new_path)
        self.accept()


class ProjectInfoDialog(QDialog):
    """Dialog showing detailed project information."""
    
    def __init__(self, project: Project, parent=None):
        super().__init__(parent)
        self.project = project
        
        self._setup_ui()
    
    def _setup_ui(self):
        self.setWindowTitle(f"Project: {self.project.name}")
        self.setMinimumSize(500, 400)
        
        layout = QVBoxLayout(self)
        
        # Tabs
        tabs = QTabWidget()
        
        # General tab
        general_widget = QWidget()
        general_layout = QFormLayout(general_widget)
        
        general_layout.addRow("Name:", QLabel(self.project.metadata.name))
        general_layout.addRow("Description:", QLabel(self.project.metadata.description or "-"))
        general_layout.addRow("Created:", QLabel(self._format_date(self.project.metadata.created)))
        general_layout.addRow("Modified:", QLabel(self._format_date(self.project.metadata.modified)))
        general_layout.addRow("Path:", QLabel(str(self.project.path) if self.project.path else "-"))
        
        tabs.addTab(general_widget, "General")
        
        # Files tab
        files_widget = QWidget()
        files_layout = QVBoxLayout(files_widget)
        
        self._files_tree = QTreeWidget()
        self._files_tree.setHeaderLabels(["File", "Size", "Status"])
        self._files_tree.setRootIsDecorated(True)
        self._populate_files_tree()
        files_layout.addWidget(self._files_tree)
        
        tabs.addTab(files_widget, "Files")
        
        # Runs tab
        runs_widget = QWidget()
        runs_layout = QVBoxLayout(runs_widget)
        
        self._runs_list = QListWidget()
        for run in self.project.runs:
            status_icon = "✓" if run.status == "success" else "✗"
            self._runs_list.addItem(f"{status_icon} {run.id} - {run.status}")
        
        if not self.project.runs:
            self._runs_list.addItem("(No simulation runs)")
        
        runs_layout.addWidget(self._runs_list)
        
        tabs.addTab(runs_widget, f"Runs ({len(self.project.runs)})")
        
        layout.addWidget(tabs)
        
        # Close button
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
    
    def _format_date(self, iso_date: str) -> str:
        """Format ISO date for display."""
        if not iso_date:
            return "-"
        try:
            dt = datetime.fromisoformat(iso_date)
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except:
            return iso_date
    
    def _populate_files_tree(self):
        """Populate files tree with project structure."""
        if not self.project.path:
            return
        
        root = self.project.path
        
        def add_path(parent_item, path: Path, name: str = None):
            name = name or path.name
            
            if path.is_file():
                size = path.stat().st_size
                size_str = self._format_size(size)
                item = QTreeWidgetItem([name, size_str, "✓"])
            else:
                item = QTreeWidgetItem([name, "", ""])
                if path.exists():
                    for child in sorted(path.iterdir()):
                        if not child.name.startswith('.'):
                            add_path(item, child)
            
            if parent_item is None:
                self._files_tree.addTopLevelItem(item)
            else:
                parent_item.addChild(item)
            
            return item
        
        # Add main project files
        for file_name in ["project.json", "topology.json", "flows.json"]:
            file_path = root / file_name
            if file_path.exists():
                add_path(None, file_path)
            else:
                item = QTreeWidgetItem([file_name, "-", "(not created)"])
                item.setForeground(2, Qt.GlobalColor.gray)
                self._files_tree.addTopLevelItem(item)
        
        # Add directories
        for dir_name in ["scripts", "results", "imports"]:
            dir_path = root / dir_name
            add_path(None, dir_path)
        
        self._files_tree.expandAll()
    
    def _format_size(self, size: int) -> str:
        """Format file size for display."""
        if size < 1024:
            return f"{size} B"
        elif size < 1024 * 1024:
            return f"{size / 1024:.1f} KB"
        else:
            return f"{size / (1024 * 1024):.1f} MB"
