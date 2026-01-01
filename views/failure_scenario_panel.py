"""
Failure Scenario Panel with Visual Timeline.

Provides a visual interface for creating and managing failure scenarios:
- Event timeline with drag-to-reschedule, resize-for-duration
- Template-based scenario creation
- Event property editor
- Visual representation of event sequences and cascades
"""

from typing import Optional, List, Dict, Callable
from dataclasses import dataclass
from PyQt6.QtCore import (
    Qt, pyqtSignal, QRectF, QPointF, QTimer, QMimeData,
    QPropertyAnimation, QEasingCurve
)
from PyQt6.QtGui import (
    QFont, QColor, QPainter, QPen, QBrush, QPainterPath,
    QLinearGradient, QMouseEvent, QWheelEvent, QKeyEvent,
    QCursor, QDrag
)
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QScrollArea, QSplitter, QComboBox, QSpinBox,
    QDoubleSpinBox, QLineEdit, QTextEdit, QListWidget,
    QListWidgetItem, QDialog, QDialogButtonBox, QFormLayout,
    QGroupBox, QCheckBox, QToolButton, QMenu, QMessageBox,
    QSizePolicy, QGraphicsDropShadowEffect
)

from models.failure_events import (
    FailureEvent, FailureScenario, FailureEventType, FailureEventState,
    FailureSeverity, FailureCategory, FailureEventParameters,
    SCENARIO_TEMPLATES, create_single_link_failure, create_node_power_loss,
)


@dataclass
class TimelineEventRect:
    """Visual representation of an event on the timeline."""
    event: FailureEvent
    x: float  # Start position (pixels)
    width: float  # Duration width (pixels)
    y: float  # Row position
    height: float = 30
    selected: bool = False
    hovered: bool = False


class EventTimelineWidget(QWidget):
    """
    Visual timeline widget for scheduling failure events.
    
    Features:
    - Drag events horizontally to change trigger time
    - Resize events to change duration
    - Zoom in/out on timeline
    - Visual indicators for event types and severity
    """
    
    eventSelected = pyqtSignal(FailureEvent)
    eventModified = pyqtSignal(FailureEvent)
    eventDoubleClicked = pyqtSignal(FailureEvent)
    timelineClicked = pyqtSignal(float)  # Time in seconds
    
    # Event type colors
    EVENT_COLORS = {
        FailureEventType.LINK_DOWN: "#EF4444",      # Red
        FailureEventType.LINK_UP: "#10B981",        # Green
        FailureEventType.LINK_DEGRADED: "#F59E0B",  # Amber
        FailureEventType.NODE_POWER_LOSS: "#DC2626",# Dark red
        FailureEventType.NODE_REBOOT: "#8B5CF6",    # Purple
        FailureEventType.PARTITION: "#7C3AED",      # Violet
        FailureEventType.DOS_FLOOD: "#1F2937",      # Dark
        FailureEventType.PLANNED_OUTAGE: "#6B7280", # Gray
    }
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.scenario: Optional[FailureScenario] = None
        self.event_rects: List[TimelineEventRect] = []
        
        # Timeline settings
        self.timeline_start = 0.0  # seconds
        self.timeline_end = 60.0   # seconds
        self.pixels_per_second = 10.0
        self.row_height = 40
        self.header_height = 30
        self.margin_left = 60
        self.margin_right = 20
        
        # Interaction state
        self.selected_event: Optional[FailureEvent] = None
        self.hovered_event: Optional[FailureEvent] = None
        self.dragging = False
        self.resizing = False
        self.resize_edge: str = ""  # "left" or "right"
        self.drag_start_pos: Optional[QPointF] = None
        self.drag_start_time: float = 0.0
        self.drag_start_duration: float = 0.0
        
        # Setup
        self.setMinimumHeight(150)
        self.setMinimumWidth(400)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        
        self.setStyleSheet("background: white; border: 1px solid #E5E7EB; border-radius: 8px;")
    
    def set_scenario(self, scenario: Optional[FailureScenario]):
        """Set the failure scenario to display."""
        self.scenario = scenario
        self._rebuild_event_rects()
        
        # Auto-adjust timeline to fit scenario
        if scenario and scenario.events:
            max_time = scenario.duration_s
            self.timeline_end = max(60.0, max_time * 1.2)
        
        self.update()
    
    def set_timeline_range(self, start: float, end: float):
        """Set the visible time range."""
        self.timeline_start = start
        self.timeline_end = end
        self._rebuild_event_rects()
        self.update()
    
    def set_zoom(self, pixels_per_second: float):
        """Set the zoom level (pixels per second)."""
        self.pixels_per_second = max(1.0, min(100.0, pixels_per_second))
        self._rebuild_event_rects()
        self.update()
    
    def _rebuild_event_rects(self):
        """Rebuild visual rectangles from scenario events."""
        self.event_rects.clear()
        
        if not self.scenario:
            return
        
        # Assign rows to events (simple: one row per event for now)
        # Could be optimized to pack non-overlapping events
        for i, event in enumerate(self.scenario.events):
            x = self._time_to_x(event.trigger_time_s)
            
            # Width based on duration
            if event.has_duration:
                end_time = event.effective_recovery_time
                width = max(10, self._time_to_x(end_time) - x)
            else:
                width = 20  # Minimum width for instant events
            
            y = self.header_height + i * self.row_height + 5
            
            rect = TimelineEventRect(
                event=event,
                x=x,
                width=width,
                y=y,
                selected=(event == self.selected_event),
                hovered=(event == self.hovered_event),
            )
            self.event_rects.append(rect)
    
    def _time_to_x(self, time_s: float) -> float:
        """Convert time in seconds to x pixel position."""
        return self.margin_left + (time_s - self.timeline_start) * self.pixels_per_second
    
    def _x_to_time(self, x: float) -> float:
        """Convert x pixel position to time in seconds."""
        return self.timeline_start + (x - self.margin_left) / self.pixels_per_second
    
    def _get_event_at(self, pos: QPointF) -> Optional[TimelineEventRect]:
        """Get the event rect at the given position."""
        for rect in reversed(self.event_rects):  # Check front-to-back
            if (rect.x <= pos.x() <= rect.x + rect.width and
                rect.y <= pos.y() <= rect.y + rect.height):
                return rect
        return None
    
    def _get_resize_edge(self, rect: TimelineEventRect, pos: QPointF) -> str:
        """Determine if position is on a resize edge."""
        edge_width = 8
        if abs(pos.x() - rect.x) < edge_width:
            return "left"
        elif abs(pos.x() - (rect.x + rect.width)) < edge_width:
            return "right"
        return ""
    
    def paintEvent(self, event):
        """Paint the timeline."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        width = self.width()
        height = self.height()
        
        # Background
        painter.fillRect(0, 0, width, height, QColor("#FFFFFF"))
        
        # Header background
        painter.fillRect(0, 0, width, self.header_height, QColor("#F9FAFB"))
        painter.setPen(QPen(QColor("#E5E7EB"), 1))
        painter.drawLine(0, self.header_height, width, self.header_height)
        
        # Time markers
        self._draw_time_markers(painter, width)
        
        # Grid lines
        self._draw_grid_lines(painter, width, height)
        
        # Current time indicator
        self._draw_current_time(painter, height)
        
        # Events
        for rect in self.event_rects:
            self._draw_event_rect(painter, rect)
        
        # "Now" label on left
        painter.setPen(QColor("#6B7280"))
        painter.setFont(QFont("SF Pro Display", 9))
        painter.drawText(5, self.header_height - 8, "Time (s)")
    
    def _draw_time_markers(self, painter: QPainter, width: int):
        """Draw time markers on the header."""
        painter.setPen(QColor("#374151"))
        painter.setFont(QFont("SF Pro Display", 9))
        
        # Determine marker interval based on zoom
        if self.pixels_per_second >= 20:
            interval = 5
        elif self.pixels_per_second >= 5:
            interval = 10
        else:
            interval = 30
        
        t = self.timeline_start
        while t <= self.timeline_end:
            x = self._time_to_x(t)
            if self.margin_left <= x <= width - self.margin_right:
                # Major tick
                painter.setPen(QColor("#374151"))
                painter.drawLine(int(x), self.header_height - 10, int(x), self.header_height)
                
                # Label
                label = f"{int(t)}" if t == int(t) else f"{t:.1f}"
                painter.drawText(int(x) - 15, self.header_height - 12, label)
            
            t += interval
    
    def _draw_grid_lines(self, painter: QPainter, width: int, height: int):
        """Draw vertical grid lines."""
        painter.setPen(QPen(QColor("#F3F4F6"), 1, Qt.PenStyle.DotLine))
        
        interval = 10 if self.pixels_per_second >= 5 else 30
        
        t = self.timeline_start
        while t <= self.timeline_end:
            x = self._time_to_x(t)
            if self.margin_left <= x <= width - self.margin_right:
                painter.drawLine(int(x), self.header_height, int(x), height)
            t += interval
    
    def _draw_current_time(self, painter: QPainter, height: int):
        """Draw current simulation time indicator."""
        # For now, just draw at t=0
        x = self._time_to_x(0)
        if x >= self.margin_left:
            painter.setPen(QPen(QColor("#3B82F6"), 2))
            painter.drawLine(int(x), self.header_height, int(x), height)
    
    def _draw_event_rect(self, painter: QPainter, rect: TimelineEventRect):
        """Draw a single event rectangle."""
        event = rect.event
        
        # Get color
        base_color = QColor(self.EVENT_COLORS.get(event.event_type, "#6B7280"))
        
        # Adjust for selection/hover
        if rect.selected:
            border_color = QColor("#1F2937")
            border_width = 3
        elif rect.hovered:
            border_color = base_color.darker(120)
            border_width = 2
        else:
            border_color = base_color.darker(110)
            border_width = 1
        
        # Draw shadow for selected
        if rect.selected:
            shadow_rect = QRectF(rect.x + 2, rect.y + 2, rect.width, rect.height)
            painter.fillRect(shadow_rect, QColor(0, 0, 0, 30))
        
        # Main rectangle
        event_rect = QRectF(rect.x, rect.y, rect.width, rect.height)
        
        # Gradient fill
        gradient = QLinearGradient(rect.x, rect.y, rect.x, rect.y + rect.height)
        gradient.setColorAt(0, base_color.lighter(110))
        gradient.setColorAt(1, base_color)
        
        painter.setBrush(QBrush(gradient))
        painter.setPen(QPen(border_color, border_width))
        painter.drawRoundedRect(event_rect, 4, 4)
        
        # Event label
        painter.setPen(QColor("white"))
        font = QFont("SF Pro Display", 9)
        font.setWeight(QFont.Weight.Bold)
        painter.setFont(font)
        
        label = event.event_type.name.replace("_", " ")[:15]
        text_rect = event_rect.adjusted(4, 0, -4, 0)
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, label)
        
        # Resize handles when selected
        if rect.selected:
            handle_color = QColor("#1F2937")
            painter.setBrush(handle_color)
            painter.setPen(Qt.PenStyle.NoPen)
            
            # Left handle
            painter.drawRect(int(rect.x - 2), int(rect.y + rect.height/2 - 6), 4, 12)
            # Right handle
            painter.drawRect(int(rect.x + rect.width - 2), int(rect.y + rect.height/2 - 6), 4, 12)
    
    def mousePressEvent(self, event: QMouseEvent):
        """Handle mouse press for selection and drag start."""
        pos = event.position()
        
        event_rect = self._get_event_at(pos)
        
        if event.button() == Qt.MouseButton.LeftButton:
            if event_rect:
                # Select event
                self.selected_event = event_rect.event
                self.eventSelected.emit(event_rect.event)
                
                # Check for resize
                edge = self._get_resize_edge(event_rect, pos)
                if edge and event_rect.event.has_duration:
                    self.resizing = True
                    self.resize_edge = edge
                else:
                    self.dragging = True
                
                self.drag_start_pos = pos
                self.drag_start_time = event_rect.event.trigger_time_s
                self.drag_start_duration = event_rect.event.duration_s
                
                self._rebuild_event_rects()
                self.update()
            else:
                # Click on empty timeline
                self.selected_event = None
                time = self._x_to_time(pos.x())
                self.timelineClicked.emit(max(0, time))
                self._rebuild_event_rects()
                self.update()
        
        elif event.button() == Qt.MouseButton.RightButton:
            if event_rect:
                self._show_event_context_menu(event_rect.event, event.globalPosition().toPoint())
    
    def mouseMoveEvent(self, event: QMouseEvent):
        """Handle mouse move for dragging and hover."""
        pos = event.position()
        
        if self.dragging and self.selected_event and self.drag_start_pos:
            # Move event
            delta_x = pos.x() - self.drag_start_pos.x()
            delta_time = delta_x / self.pixels_per_second
            new_time = max(0, self.drag_start_time + delta_time)
            
            self.selected_event.trigger_time_s = new_time
            if self.selected_event.recovery_time_s > 0:
                # Adjust recovery time to maintain duration
                self.selected_event.recovery_time_s = new_time + self.drag_start_duration
            
            self._rebuild_event_rects()
            self.update()
        
        elif self.resizing and self.selected_event and self.drag_start_pos:
            # Resize event
            delta_x = pos.x() - self.drag_start_pos.x()
            delta_time = delta_x / self.pixels_per_second
            
            if self.resize_edge == "right":
                new_duration = max(1, self.drag_start_duration + delta_time)
                self.selected_event.duration_s = new_duration
            elif self.resize_edge == "left":
                new_time = max(0, self.drag_start_time + delta_time)
                time_diff = new_time - self.drag_start_time
                new_duration = max(1, self.drag_start_duration - time_diff)
                self.selected_event.trigger_time_s = new_time
                self.selected_event.duration_s = new_duration
            
            self._rebuild_event_rects()
            self.update()
        
        else:
            # Hover detection
            event_rect = self._get_event_at(pos)
            old_hovered = self.hovered_event
            self.hovered_event = event_rect.event if event_rect else None
            
            # Update cursor
            if event_rect:
                edge = self._get_resize_edge(event_rect, pos)
                if edge:
                    self.setCursor(Qt.CursorShape.SizeHorCursor)
                else:
                    self.setCursor(Qt.CursorShape.PointingHandCursor)
            else:
                self.setCursor(Qt.CursorShape.ArrowCursor)
            
            if old_hovered != self.hovered_event:
                self._rebuild_event_rects()
                self.update()
    
    def mouseReleaseEvent(self, event: QMouseEvent):
        """Handle mouse release to end drag."""
        if self.dragging or self.resizing:
            if self.selected_event:
                self.eventModified.emit(self.selected_event)
        
        self.dragging = False
        self.resizing = False
        self.drag_start_pos = None
    
    def mouseDoubleClickEvent(self, event: QMouseEvent):
        """Handle double-click to edit event."""
        pos = event.position()
        event_rect = self._get_event_at(pos)
        
        if event_rect:
            self.eventDoubleClicked.emit(event_rect.event)
        else:
            # Double-click on empty space to create new event
            time = self._x_to_time(pos.x())
            self.timelineClicked.emit(max(0, time))
    
    def wheelEvent(self, event: QWheelEvent):
        """Handle wheel for zoom."""
        delta = event.angleDelta().y()
        
        if delta > 0:
            self.set_zoom(self.pixels_per_second * 1.2)
        else:
            self.set_zoom(self.pixels_per_second / 1.2)
    
    def keyPressEvent(self, event: QKeyEvent):
        """Handle keyboard shortcuts."""
        if event.key() == Qt.Key.Key_Delete and self.selected_event:
            # Delete selected event
            if self.scenario:
                self.scenario.events.remove(self.selected_event)
                self.selected_event = None
                self._rebuild_event_rects()
                self.update()
    
    def _show_event_context_menu(self, event: FailureEvent, pos):
        """Show context menu for an event."""
        menu = QMenu(self)
        
        edit_action = menu.addAction("Edit Event...")
        edit_action.triggered.connect(lambda: self.eventDoubleClicked.emit(event))
        
        menu.addSeparator()
        
        delete_action = menu.addAction("Delete Event")
        delete_action.triggered.connect(lambda: self._delete_event(event))
        
        menu.addSeparator()
        
        duplicate_action = menu.addAction("Duplicate")
        duplicate_action.triggered.connect(lambda: self._duplicate_event(event))
        
        menu.exec(pos)
    
    def _delete_event(self, event: FailureEvent):
        """Delete an event from the scenario."""
        if self.scenario and event in self.scenario.events:
            self.scenario.events.remove(event)
            if self.selected_event == event:
                self.selected_event = None
            self._rebuild_event_rects()
            self.update()
    
    def _duplicate_event(self, event: FailureEvent):
        """Duplicate an event."""
        if self.scenario:
            import copy
            new_event = copy.deepcopy(event)
            new_event.id = str(__import__('uuid').uuid4())[:8]
            new_event.trigger_time_s += 5  # Offset by 5 seconds
            new_event.name = f"{event.name} (copy)"
            self.scenario.add_event(new_event)
            self._rebuild_event_rects()
            self.update()


class EventEditorDialog(QDialog):
    """Dialog for editing failure event properties."""
    
    def __init__(self, event: Optional[FailureEvent] = None, 
                 available_targets: List[str] = None,
                 parent=None):
        super().__init__(parent)
        self.event = event or FailureEvent()
        self.available_targets = available_targets or []
        self._setup_ui()
        self._populate_from_event()
    
    def _setup_ui(self):
        self.setWindowTitle("Edit Failure Event" if self.event.id else "New Failure Event")
        self.setMinimumWidth(450)
        
        layout = QVBoxLayout(self)
        
        # Form
        form = QFormLayout()
        form.setSpacing(2)
        
        # Name
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Event name...")
        form.addRow("Name:", self.name_edit)
        
        # Event type
        self.type_combo = QComboBox()
        for event_type in FailureEventType:
            self.type_combo.addItem(
                event_type.name.replace("_", " ").title(),
                event_type
            )
        form.addRow("Type:", self.type_combo)
        
        # Target
        self.target_combo = QComboBox()
        self.target_combo.setEditable(True)
        self.target_combo.addItems(self.available_targets)
        form.addRow("Target:", self.target_combo)
        
        # Severity
        self.severity_combo = QComboBox()
        for severity in FailureSeverity:
            self.severity_combo.addItem(severity.name.title(), severity)
        form.addRow("Severity:", self.severity_combo)
        
        layout.addLayout(form)
        
        # Timing group
        timing_group = QGroupBox("Timing")
        timing_layout = QFormLayout(timing_group)
        
        self.trigger_spin = QDoubleSpinBox()
        self.trigger_spin.setRange(0, 10000)
        self.trigger_spin.setDecimals(1)
        self.trigger_spin.setSuffix(" s")
        timing_layout.addRow("Trigger Time:", self.trigger_spin)
        
        self.duration_spin = QDoubleSpinBox()
        self.duration_spin.setRange(-1, 10000)
        self.duration_spin.setDecimals(1)
        self.duration_spin.setSuffix(" s")
        self.duration_spin.setSpecialValueText("Permanent")
        timing_layout.addRow("Duration:", self.duration_spin)
        
        layout.addWidget(timing_group)
        
        # Description
        desc_group = QGroupBox("Description")
        desc_layout = QVBoxLayout(desc_group)
        self.desc_edit = QTextEdit()
        self.desc_edit.setMaximumHeight(80)
        self.desc_edit.setPlaceholderText("Optional description...")
        desc_layout.addWidget(self.desc_edit)
        layout.addWidget(desc_group)
        
        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | 
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
    
    def _populate_from_event(self):
        """Populate form from event."""
        self.name_edit.setText(self.event.name)
        
        idx = self.type_combo.findData(self.event.event_type)
        if idx >= 0:
            self.type_combo.setCurrentIndex(idx)
        
        self.target_combo.setCurrentText(self.event.target_id)
        
        idx = self.severity_combo.findData(self.event.severity)
        if idx >= 0:
            self.severity_combo.setCurrentIndex(idx)
        
        self.trigger_spin.setValue(self.event.trigger_time_s)
        self.duration_spin.setValue(self.event.duration_s)
        self.desc_edit.setPlainText(self.event.description)
    
    def _on_accept(self):
        """Apply changes and accept."""
        self.event.name = self.name_edit.text() or f"event_{self.event.id[:4]}"
        self.event.event_type = self.type_combo.currentData()
        self.event.target_id = self.target_combo.currentText()
        self.event.severity = self.severity_combo.currentData()
        self.event.trigger_time_s = self.trigger_spin.value()
        self.event.duration_s = self.duration_spin.value()
        self.event.description = self.desc_edit.toPlainText()
        
        self.accept()
    
    def get_event(self) -> FailureEvent:
        return self.event


class FailureScenarioPanel(QWidget):
    """
    Complete panel for managing failure scenarios.
    
    Includes:
    - Scenario selector/creator
    - Event timeline
    - Event list
    - Property editor
    """
    
    scenarioChanged = pyqtSignal(FailureScenario)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.current_scenario: Optional[FailureScenario] = None
        self.available_targets: List[str] = []  # Node/link IDs
        
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Header
        header = self._create_header()
        layout.addWidget(header)
        
        # Main content with splitter
        splitter = QSplitter(Qt.Orientation.Vertical)
        
        # Timeline
        timeline_frame = QFrame()
        timeline_frame.setStyleSheet("background: white;")
        timeline_layout = QVBoxLayout(timeline_frame)
        timeline_layout.setContentsMargins(2, 2, 2, 2)
        
        timeline_label = QLabel("Event Timeline")
        timeline_label.setStyleSheet("font-weight: bold; color: #374151;")
        timeline_layout.addWidget(timeline_label)
        
        self.timeline = EventTimelineWidget()
        self.timeline.eventSelected.connect(self._on_event_selected)
        self.timeline.eventModified.connect(self._on_event_modified)
        self.timeline.eventDoubleClicked.connect(self._on_event_double_clicked)
        self.timeline.timelineClicked.connect(self._on_timeline_clicked)
        timeline_layout.addWidget(self.timeline)
        
        splitter.addWidget(timeline_frame)
        
        # Event list and properties
        bottom_frame = QFrame()
        bottom_layout = QHBoxLayout(bottom_frame)
        bottom_layout.setContentsMargins(2, 2, 2, 2)
        
        # Event list
        list_frame = QFrame()
        list_layout = QVBoxLayout(list_frame)
        list_layout.setContentsMargins(0, 0, 0, 0)
        
        list_header = QHBoxLayout()
        list_label = QLabel("Events")
        list_label.setStyleSheet("font-weight: bold; color: #374151;")
        list_header.addWidget(list_label)
        
        add_btn = QToolButton()
        add_btn.setText("+")
        add_btn.setStyleSheet("""
            QToolButton {
                background: #3B82F6;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 2px 8px;
                font-weight: bold;
            }
            QToolButton:hover { background: #2563EB; }
        """)
        add_btn.clicked.connect(self._add_event)
        list_header.addWidget(add_btn)
        list_layout.addLayout(list_header)
        
        self.event_list = QListWidget()
        self.event_list.setStyleSheet("""
            QListWidget {
                border: 1px solid #E5E7EB;
                border-radius: 6px;
            }
            QListWidget::item {
                padding: 2px;
                border-bottom: 1px solid #F3F4F6;
            }
            QListWidget::item:selected {
                background: #EFF6FF;
                color: #1F2937;
            }
        """)
        self.event_list.currentItemChanged.connect(self._on_list_selection_changed)
        list_layout.addWidget(self.event_list)
        
        bottom_layout.addWidget(list_frame, 1)
        
        # Properties panel
        props_frame = QFrame()
        props_frame.setStyleSheet("""
            QFrame {
                background: #F9FAFB;
                border: 1px solid #E5E7EB;
                border-radius: 8px;
            }
        """)
        props_layout = QVBoxLayout(props_frame)
        
        props_label = QLabel("Event Properties")
        props_label.setStyleSheet("font-weight: bold; color: #374151;")
        props_layout.addWidget(props_label)
        
        self.props_content = QLabel("Select an event to view properties")
        self.props_content.setStyleSheet("color: #9CA3AF;")
        self.props_content.setAlignment(Qt.AlignmentFlag.AlignCenter)
        props_layout.addWidget(self.props_content)
        props_layout.addStretch()
        
        bottom_layout.addWidget(props_frame, 1)
        
        splitter.addWidget(bottom_frame)
        
        splitter.setSizes([200, 150])
        layout.addWidget(splitter)
    
    def _create_header(self) -> QFrame:
        """Create the header with scenario controls."""
        header = QFrame()
        header.setStyleSheet("""
            QFrame {
                background: #F9FAFB;
                border-bottom: 1px solid #E5E7EB;
            }
        """)
        
        layout = QHBoxLayout(header)
        layout.setContentsMargins(2, 2, 2, 2)
        
        # Title
        title = QLabel("Failure Scenarios")
        title_font = QFont("SF Pro Display", 14)
        title_font.setWeight(QFont.Weight.Bold)
        title.setFont(title_font)
        layout.addWidget(title)
        
        layout.addStretch()
        
        # Scenario selector
        self.scenario_combo = QComboBox()
        self.scenario_combo.setMinimumWidth(200)
        self.scenario_combo.addItem("(No Scenario)")
        self.scenario_combo.currentIndexChanged.connect(self._on_scenario_selected)
        layout.addWidget(self.scenario_combo)
        
        # New from template
        template_btn = QPushButton("New from Template")
        template_btn.setStyleSheet("""
            QPushButton {
                background: #3B82F6;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 2px 4px;
                font-weight: 500;
            }
            QPushButton:hover { background: #2563EB; }
        """)
        template_btn.clicked.connect(self._show_template_menu)
        layout.addWidget(template_btn)
        
        return header
    
    def set_available_targets(self, node_ids: List[str], link_ids: List[str]):
        """Set available targets for event creation."""
        self.available_targets = node_ids + link_ids
    
    def set_scenario(self, scenario: Optional[FailureScenario]):
        """Set the current failure scenario."""
        self.current_scenario = scenario
        self.timeline.set_scenario(scenario)
        self._update_event_list()
        self.scenarioChanged.emit(scenario)
    
    def get_scenario(self) -> Optional[FailureScenario]:
        """Get the current scenario."""
        return self.current_scenario
    
    def _update_event_list(self):
        """Update the event list widget."""
        self.event_list.clear()
        
        if not self.current_scenario:
            return
        
        for event in self.current_scenario.events:
            item = QListWidgetItem()
            
            type_name = event.event_type.name.replace("_", " ").title()
            time_str = f"t={event.trigger_time_s:.1f}s"
            if event.has_duration:
                time_str += f", dur={event.duration_s:.1f}s"
            
            item.setText(f"{type_name}\n{time_str}")
            item.setData(Qt.ItemDataRole.UserRole, event)
            
            # Color indicator
            color = EventTimelineWidget.EVENT_COLORS.get(event.event_type, "#6B7280")
            item.setBackground(QColor(color).lighter(180))
            
            self.event_list.addItem(item)
    
    def _on_event_selected(self, event: FailureEvent):
        """Handle event selection from timeline."""
        # Find and select in list
        for i in range(self.event_list.count()):
            item = self.event_list.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == event:
                self.event_list.setCurrentItem(item)
                break
        
        self._show_event_properties(event)
    
    def _on_event_modified(self, event: FailureEvent):
        """Handle event modification from timeline."""
        self._update_event_list()
        if self.current_scenario:
            self.scenarioChanged.emit(self.current_scenario)
    
    def _on_event_double_clicked(self, event: FailureEvent):
        """Handle event double-click to edit."""
        dialog = EventEditorDialog(event, self.available_targets, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.timeline.set_scenario(self.current_scenario)
            self._update_event_list()
            if self.current_scenario:
                self.scenarioChanged.emit(self.current_scenario)
    
    def _on_timeline_clicked(self, time: float):
        """Handle click on empty timeline to create event."""
        result = QMessageBox.question(
            self,
            "Create Event",
            f"Create new event at t={time:.1f}s?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if result == QMessageBox.StandardButton.Yes:
            self._add_event(trigger_time=time)
    
    def _on_list_selection_changed(self, current, previous):
        """Handle event list selection change."""
        if current:
            event = current.data(Qt.ItemDataRole.UserRole)
            self.timeline.selected_event = event
            self.timeline._rebuild_event_rects()
            self.timeline.update()
            self._show_event_properties(event)
    
    def _on_scenario_selected(self, index: int):
        """Handle scenario selection from combo."""
        if index == 0:
            self.set_scenario(None)
    
    def _show_event_properties(self, event: FailureEvent):
        """Show event properties in the properties panel."""
        props_text = f"""
<b>{event.name}</b><br>
<br>
<b>Type:</b> {event.event_type.name.replace('_', ' ').title()}<br>
<b>Target:</b> {event.target_id or 'None'}<br>
<b>Severity:</b> {event.severity.name.title()}<br>
<br>
<b>Trigger:</b> {event.trigger_time_s:.1f}s<br>
<b>Duration:</b> {'Permanent' if event.duration_s < 0 else f'{event.duration_s:.1f}s'}<br>
"""
        if event.has_duration:
            props_text += f"<b>Recovery:</b> {event.effective_recovery_time:.1f}s<br>"
        
        if event.description:
            props_text += f"<br><b>Description:</b><br>{event.description}"
        
        self.props_content.setText(props_text)
    
    def _add_event(self, trigger_time: float = None):
        """Add a new event."""
        if not self.current_scenario:
            # Create new scenario
            self.current_scenario = FailureScenario(name="New Scenario")
        
        event = FailureEvent(
            trigger_time_s=trigger_time if trigger_time is not None else 10.0,
            duration_s=30.0,
        )
        
        dialog = EventEditorDialog(event, self.available_targets, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.current_scenario.add_event(dialog.get_event())
            self.timeline.set_scenario(self.current_scenario)
            self._update_event_list()
            self.scenarioChanged.emit(self.current_scenario)
    
    def _show_template_menu(self):
        """Show menu for creating scenario from template."""
        menu = QMenu(self)
        
        for template_id, template_info in SCENARIO_TEMPLATES.items():
            action = menu.addAction(template_info["name"])
            action.setData(template_id)
            action.triggered.connect(lambda checked, tid=template_id: self._create_from_template(tid))
        
        # Show menu below button
        btn = self.sender()
        if btn:
            menu.exec(btn.mapToGlobal(btn.rect().bottomLeft()))
    
    def _create_from_template(self, template_id: str):
        """Create a new scenario from a template."""
        template = SCENARIO_TEMPLATES.get(template_id)
        if not template:
            return
        
        # Show dialog to get parameters
        if template_id == "single_link_failure":
            if not self.available_targets:
                QMessageBox.warning(self, "No Targets", 
                    "Add nodes and links to the network first.")
                return
            
            target, ok = self._select_target("Select Link", 
                [t for t in self.available_targets if t.startswith("link")] or self.available_targets)
            if ok and target:
                scenario = create_single_link_failure(target)
                self.set_scenario(scenario)
        
        elif template_id == "node_power_loss":
            if not self.available_targets:
                QMessageBox.warning(self, "No Targets",
                    "Add nodes to the network first.")
                return
            
            target, ok = self._select_target("Select Node",
                [t for t in self.available_targets if not t.startswith("link")] or self.available_targets)
            if ok and target:
                scenario = create_node_power_loss(target)
                self.set_scenario(scenario)
        
        else:
            # Generic template - just create with defaults
            factory = template.get("factory")
            if factory:
                try:
                    scenario = factory("target_placeholder")
                    self.set_scenario(scenario)
                except Exception as e:
                    QMessageBox.warning(self, "Error", f"Could not create scenario: {e}")
    
    def _select_target(self, title: str, options: List[str]) -> tuple:
        """Show dialog to select a target."""
        from PyQt6.QtWidgets import QInputDialog
        
        target, ok = QInputDialog.getItem(
            self, title, "Select target:", options, 0, False
        )
        return target, ok
