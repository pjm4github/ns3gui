"""
Shape Manager Dialog.

A dialog for browsing and managing all node shapes in the application.
Provides:
- Grid view of all shapes with previews
- Filter by category (Standard, Grid, Custom)
- Edit, reset, import, export functionality
- Create new custom shapes

Usage:
    dialog = ShapeManagerDialog(parent)
    dialog.exec()
"""

from typing import Optional, List
from PyQt6.QtCore import Qt, QSize, pyqtSignal
from PyQt6.QtGui import QPixmap, QIcon
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QWidget,
    QLabel, QPushButton, QFrame, QScrollArea,
    QGridLayout, QGroupBox, QComboBox, QLineEdit,
    QDialogButtonBox, QMessageBox, QFileDialog,
    QSizePolicy, QToolButton, QMenu
)

from models import NodeType
from models.grid_nodes import GridNodeType
from models.shape_definition import ShapeDefinition, ShapeLibrary
from services.shape_manager import get_shape_manager
from views.shape_renderer import ShapeRenderer


class ShapeCard(QFrame):
    """
    A card widget displaying a shape preview with edit/reset buttons.
    """
    
    edit_requested = pyqtSignal(str)  # shape_id
    reset_requested = pyqtSignal(str)  # shape_id
    
    def __init__(self, shape: ShapeDefinition, parent=None):
        super().__init__(parent)
        self.shape = shape
        self._setup_ui()
    
    def _setup_ui(self):
        self.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        self.setFixedSize(120, 140)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        
        # Style based on modified state
        if self.shape.modified:
            border_color = "#F59E0B"  # Amber for modified
        else:
            border_color = "#E5E7EB"  # Gray for default
        
        self.setStyleSheet(f"""
            ShapeCard {{
                background: white;
                border: 2px solid {border_color};
                border-radius: 8px;
            }}
            ShapeCard:hover {{
                border-color: #3B82F6;
                background: #F9FAFB;
            }}
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)
        
        # Shape preview
        preview_label = QLabel()
        preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        preview_label.setFixedSize(60, 60)
        
        pixmap = ShapeRenderer.render_preview(self.shape, 56)
        preview_label.setPixmap(pixmap)
        
        # Center the preview
        preview_container = QHBoxLayout()
        preview_container.addStretch()
        preview_container.addWidget(preview_label)
        preview_container.addStretch()
        layout.addLayout(preview_container)
        
        # Shape name
        name_label = QLabel(self.shape.name)
        name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name_label.setStyleSheet("""
            font-size: 11px;
            font-weight: 600;
            color: #374151;
        """)
        name_label.setWordWrap(True)
        layout.addWidget(name_label)
        
        # Modified indicator
        if self.shape.modified:
            mod_label = QLabel("(modified)")
            mod_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            mod_label.setStyleSheet("font-size: 9px; color: #F59E0B;")
            layout.addWidget(mod_label)
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(4)
        
        edit_btn = QToolButton()
        edit_btn.setText("✏")
        edit_btn.setToolTip("Edit Shape")
        edit_btn.setFixedSize(28, 24)
        edit_btn.clicked.connect(lambda: self.edit_requested.emit(self.shape.id))
        btn_layout.addWidget(edit_btn)
        
        if self.shape.modified:
            reset_btn = QToolButton()
            reset_btn.setText("↺")
            reset_btn.setToolTip("Reset to Default")
            reset_btn.setFixedSize(28, 24)
            reset_btn.clicked.connect(lambda: self.reset_requested.emit(self.shape.id))
            btn_layout.addWidget(reset_btn)
        
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
    
    def mouseDoubleClickEvent(self, event):
        """Open editor on double-click."""
        self.edit_requested.emit(self.shape.id)


class ShapeManagerDialog(QDialog):
    """
    Dialog for managing all node shapes.
    
    Layout:
    ┌────────────────────────────────────────────────────────────┐
    │ Shape Manager                                         [X]  │
    ├────────────────────────────────────────────────────────────┤
    │ Category: [All ▼]  Search: [____________]  [Import] [Export]│
    ├────────────────────────────────────────────────────────────┤
    │ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐           │
    │ │  ○ H    │ │  ○ R    │ │  ○ S    │ │  ⬡      │           │
    │ │  Host   │ │ Router  │ │ Switch  │ │Substation│           │
    │ │ [✏][↺] │ │  [✏]   │ │  [✏]   │ │ [✏][↺] │           │
    │ └─────────┘ └─────────┘ └─────────┘ └─────────┘           │
    │ ┌─────────┐ ┌─────────┐ ...                               │
    │ │  ◈      │ │  ⚡     │                                    │
    │ │CommRouter│ │CtrlCtr │                                    │
    │ │  [✏]   │ │  [✏]   │                                    │
    │ └─────────┘ └─────────┘                                    │
    ├────────────────────────────────────────────────────────────┤
    │                                              [Close]       │
    └────────────────────────────────────────────────────────────┘
    """
    
    shapes_changed = pyqtSignal()  # Emitted when any shape is modified
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.shape_manager = get_shape_manager()
        self._shape_cards: List[ShapeCard] = []
        self._setup_ui()
        self._load_shapes()
    
    def _setup_ui(self):
        self.setWindowTitle("Shape Manager")
        self.setMinimumSize(650, 500)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        
        # Top bar: filter and actions
        top_bar = QHBoxLayout()
        
        # Category filter
        top_bar.addWidget(QLabel("Category:"))
        self.category_combo = QComboBox()
        self.category_combo.addItems([
            "All Shapes",
            "Standard Nodes",
            "Grid/SCADA Nodes",
            "Modified Only",
            "Custom Only"
        ])
        self.category_combo.currentIndexChanged.connect(self._on_filter_changed)
        self.category_combo.setFixedWidth(140)
        top_bar.addWidget(self.category_combo)
        
        top_bar.addSpacing(20)
        
        # Search
        top_bar.addWidget(QLabel("Search:"))
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Filter shapes...")
        self.search_edit.textChanged.connect(self._on_filter_changed)
        self.search_edit.setFixedWidth(150)
        top_bar.addWidget(self.search_edit)
        
        top_bar.addStretch()
        
        # Import/Export buttons
        import_btn = QPushButton("Import...")
        import_btn.clicked.connect(self._import_shapes)
        top_bar.addWidget(import_btn)
        
        export_btn = QPushButton("Export...")
        export_btn.clicked.connect(self._export_shapes)
        top_bar.addWidget(export_btn)
        
        layout.addLayout(top_bar)
        
        # Scroll area for shape cards
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("""
            QScrollArea {
                border: 1px solid #E5E7EB;
                border-radius: 8px;
                background: #F9FAFB;
            }
        """)
        
        self.cards_widget = QWidget()
        self.cards_layout = QGridLayout(self.cards_widget)
        self.cards_layout.setSpacing(12)
        self.cards_layout.setContentsMargins(12, 12, 12, 12)
        
        scroll.setWidget(self.cards_widget)
        layout.addWidget(scroll)
        
        # Bottom bar
        bottom_bar = QHBoxLayout()
        
        # Stats label
        self.stats_label = QLabel()
        self.stats_label.setStyleSheet("color: #6B7280; font-size: 11px;")
        bottom_bar.addWidget(self.stats_label)
        
        bottom_bar.addStretch()
        
        # Close button
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        close_btn.setFixedWidth(80)
        bottom_bar.addWidget(close_btn)
        
        layout.addLayout(bottom_bar)
    
    def _load_shapes(self):
        """Load all shapes into the grid."""
        self._clear_cards()
        
        # Get all shapes
        all_shapes = []
        
        # Standard node shapes
        for node_type in NodeType:
            shape = self.shape_manager.get_shape(node_type.name)
            if shape:
                all_shapes.append(("standard", shape))
        
        # Grid node shapes
        for grid_type in GridNodeType:
            shape = self.shape_manager.get_shape(grid_type.name)
            if shape:
                all_shapes.append(("grid", shape))
        
        # Apply filters
        filtered = self._apply_filters(all_shapes)
        
        # Create cards
        col_count = 4
        for i, (category, shape) in enumerate(filtered):
            card = ShapeCard(shape)
            card.edit_requested.connect(self._edit_shape)
            card.reset_requested.connect(self._reset_shape)
            self._shape_cards.append(card)
            
            row = i // col_count
            col = i % col_count
            self.cards_layout.addWidget(card, row, col)
        
        # Add stretch at the bottom
        self.cards_layout.setRowStretch(len(filtered) // col_count + 1, 1)
        
        # Update stats
        modified_count = sum(1 for _, s in filtered if s.modified)
        self.stats_label.setText(
            f"{len(filtered)} shapes shown • {modified_count} modified"
        )
    
    def _clear_cards(self):
        """Remove all shape cards."""
        for card in self._shape_cards:
            self.cards_layout.removeWidget(card)
            card.deleteLater()
        self._shape_cards.clear()
    
    def _apply_filters(self, shapes: List[tuple]) -> List[tuple]:
        """Apply category and search filters."""
        category = self.category_combo.currentText()
        search = self.search_edit.text().lower().strip()
        
        filtered = []
        for cat, shape in shapes:
            # Category filter
            if category == "Standard Nodes" and cat != "standard":
                continue
            elif category == "Grid/SCADA Nodes" and cat != "grid":
                continue
            elif category == "Modified Only" and not shape.modified:
                continue
            elif category == "Custom Only" and shape.is_default:
                continue
            
            # Search filter
            if search:
                if search not in shape.name.lower() and search not in shape.id.lower():
                    continue
            
            filtered.append((cat, shape))
        
        return filtered
    
    def _on_filter_changed(self):
        """Handle filter changes."""
        self._load_shapes()
    
    def _edit_shape(self, shape_id: str):
        """Open shape editor for a shape."""
        from views.shape_editor_dialog import ShapeEditorDialog
        
        shape = self.shape_manager.get_shape(shape_id)
        if not shape:
            return
        
        dialog = ShapeEditorDialog(shape, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            # Reload to show updated state
            self._load_shapes()
            self.shapes_changed.emit()
    
    def _reset_shape(self, shape_id: str):
        """Reset a shape to default."""
        reply = QMessageBox.question(
            self, "Reset Shape",
            f"Reset '{shape_id}' to its default appearance?\n\n"
            "All customizations will be lost.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            if self.shape_manager.reset_shape_to_default(shape_id):
                self._load_shapes()
                self.shapes_changed.emit()
    
    def _import_shapes(self):
        """Import shapes from a JSON file."""
        filepath, _ = QFileDialog.getOpenFileName(
            self, "Import Shapes", "", "JSON Files (*.json)"
        )
        
        if not filepath:
            return
        
        try:
            library = ShapeLibrary.load_from_file(filepath)
            if library:
                imported = 0
                for shape in library.shapes.values():
                    self.shape_manager.update_shape(shape)
                    imported += 1
                
                QMessageBox.information(
                    self, "Import Complete",
                    f"Successfully imported {imported} shape(s)."
                )
                self._load_shapes()
                self.shapes_changed.emit()
        except Exception as e:
            QMessageBox.warning(
                self, "Import Failed",
                f"Failed to import shapes:\n{str(e)}"
            )
    
    def _export_shapes(self):
        """Export shapes to a JSON file."""
        # Ask what to export
        menu = QMenu(self)
        export_all = menu.addAction("Export All Shapes")
        export_modified = menu.addAction("Export Modified Only")
        export_selected = menu.addAction("Export Current Filter")
        
        # Position menu at cursor
        action = menu.exec(self.cursor().pos())
        
        if not action:
            return
        
        # Determine which shapes to export
        shapes_to_export = []
        
        if action == export_all:
            for node_type in NodeType:
                shape = self.shape_manager.get_shape(node_type.name)
                if shape:
                    shapes_to_export.append(shape)
            for grid_type in GridNodeType:
                shape = self.shape_manager.get_shape(grid_type.name)
                if shape:
                    shapes_to_export.append(shape)
        elif action == export_modified:
            for node_type in NodeType:
                shape = self.shape_manager.get_shape(node_type.name)
                if shape and shape.modified:
                    shapes_to_export.append(shape)
            for grid_type in GridNodeType:
                shape = self.shape_manager.get_shape(grid_type.name)
                if shape and shape.modified:
                    shapes_to_export.append(shape)
        elif action == export_selected:
            # Export what's currently shown
            for card in self._shape_cards:
                shapes_to_export.append(card.shape)
        
        if not shapes_to_export:
            QMessageBox.information(
                self, "Nothing to Export",
                "No shapes match the export criteria."
            )
            return
        
        # Get save path
        filepath, _ = QFileDialog.getSaveFileName(
            self, "Export Shapes", "shapes.json", "JSON Files (*.json)"
        )
        
        if not filepath:
            return
        
        # Create library and save
        library = ShapeLibrary()
        for shape in shapes_to_export:
            library.add_shape(shape)
        
        try:
            library.save_to_file(filepath)
            QMessageBox.information(
                self, "Export Complete",
                f"Successfully exported {len(shapes_to_export)} shape(s)."
            )
        except Exception as e:
            QMessageBox.warning(
                self, "Export Failed",
                f"Failed to export shapes:\n{str(e)}"
            )
