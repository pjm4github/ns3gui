"""
Metrics Dashboard for Grid Simulation Monitoring.

Provides real-time visualization of:
- Latency metrics (end-to-end, per-hop)
- Packet loss statistics
- Failover timing measurements
- Throughput and bandwidth utilization
- Protocol-specific metrics (DNP3, IEC 61850)
"""

from typing import Optional, List, Dict, Tuple
from dataclasses import dataclass, field
from collections import deque
import time
import random

from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QRectF, QPointF
from PyQt6.QtGui import (
    QFont, QColor, QPainter, QPen, QBrush, QPainterPath,
    QLinearGradient, QRadialGradient
)
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QScrollArea, QSplitter, QGridLayout, QGroupBox,
    QProgressBar, QSizePolicy, QToolButton
)


@dataclass
class MetricSample:
    """A single metric sample."""
    timestamp: float
    value: float
    label: str = ""


@dataclass
class MetricSeries:
    """A time series of metric samples."""
    name: str
    unit: str
    color: str
    samples: deque = field(default_factory=lambda: deque(maxlen=100))
    min_value: float = 0.0
    max_value: float = 100.0
    warning_threshold: float = -1.0
    critical_threshold: float = -1.0
    
    @property
    def current_value(self) -> float:
        if self.samples:
            return self.samples[-1].value
        return 0.0
    
    @property
    def average(self) -> float:
        if self.samples:
            return sum(s.value for s in self.samples) / len(self.samples)
        return 0.0
    
    @property
    def min(self) -> float:
        if self.samples:
            return min(s.value for s in self.samples)
        return 0.0
    
    @property
    def max(self) -> float:
        if self.samples:
            return max(s.value for s in self.samples)
        return 0.0
    
    def add_sample(self, value: float, timestamp: float = None, label: str = ""):
        if timestamp is None:
            timestamp = time.time()
        self.samples.append(MetricSample(timestamp, value, label))


class SparklineWidget(QWidget):
    """
    Compact sparkline chart for displaying metric trends.
    """
    
    def __init__(self, series: MetricSeries = None, parent=None):
        super().__init__(parent)
        self.series = series
        self.setMinimumHeight(40)
        self.setMinimumWidth(100)
    
    def set_series(self, series: MetricSeries):
        self.series = series
        self.update()
    
    def paintEvent(self, event):
        if not self.series or not self.series.samples:
            return
        
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        width = self.width()
        height = self.height()
        margin = 4
        
        samples = list(self.series.samples)
        if len(samples) < 2:
            return
        
        # Calculate value range
        values = [s.value for s in samples]
        min_val = min(values)
        max_val = max(values)
        val_range = max_val - min_val if max_val != min_val else 1
        
        # Draw background
        painter.fillRect(0, 0, width, height, QColor("#F9FAFB"))
        
        # Draw warning/critical zones
        if self.series.warning_threshold > 0:
            y = height - margin - (self.series.warning_threshold - min_val) / val_range * (height - 2 * margin)
            painter.fillRect(0, int(margin), width, int(y - margin), QColor("#FEF3C7"))
        
        # Build path
        path = QPainterPath()
        for i, sample in enumerate(samples):
            x = margin + (i / (len(samples) - 1)) * (width - 2 * margin)
            y = height - margin - (sample.value - min_val) / val_range * (height - 2 * margin)
            
            if i == 0:
                path.moveTo(x, y)
            else:
                path.lineTo(x, y)
        
        # Draw line
        color = QColor(self.series.color)
        painter.setPen(QPen(color, 2))
        painter.drawPath(path)
        
        # Draw current value dot
        if samples:
            last = samples[-1]
            x = width - margin
            y = height - margin - (last.value - min_val) / val_range * (height - 2 * margin)
            painter.setBrush(color)
            painter.drawEllipse(QPointF(x, y), 4, 4)


class MetricCard(QFrame):
    """
    Card displaying a single metric with current value, trend, and sparkline.
    """
    
    def __init__(self, series: MetricSeries, parent=None):
        super().__init__(parent)
        self.series = series
        self._setup_ui()
    
    def _setup_ui(self):
        self.setFrameStyle(QFrame.Shape.StyledPanel)
        self.setStyleSheet("""
            MetricCard {
                background: white;
                border: 1px solid #E5E7EB;
                border-radius: 12px;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(2)
        
        # Header
        header = QHBoxLayout()
        
        self.title_label = QLabel(self.series.name)
        self.title_label.setStyleSheet("color: #6B7280; font-size: 12px;")
        header.addWidget(self.title_label)
        
        header.addStretch()
        
        # Status indicator
        self.status_dot = QLabel("●")
        self.status_dot.setStyleSheet("color: #10B981; font-size: 10px;")
        header.addWidget(self.status_dot)
        
        layout.addLayout(header)
        
        # Current value
        value_layout = QHBoxLayout()
        
        self.value_label = QLabel("--")
        self.value_label.setStyleSheet(f"""
            color: {self.series.color};
            font-size: 28px;
            font-weight: bold;
        """)
        value_layout.addWidget(self.value_label)
        
        self.unit_label = QLabel(self.series.unit)
        self.unit_label.setStyleSheet("color: #9CA3AF; font-size: 14px;")
        value_layout.addWidget(self.unit_label)
        
        value_layout.addStretch()
        
        # Trend arrow
        self.trend_label = QLabel("")
        self.trend_label.setStyleSheet("font-size: 16px;")
        value_layout.addWidget(self.trend_label)
        
        layout.addLayout(value_layout)
        
        # Sparkline
        self.sparkline = SparklineWidget(self.series)
        layout.addWidget(self.sparkline)
        
        # Stats row
        stats = QHBoxLayout()
        
        self.min_label = QLabel("Min: --")
        self.min_label.setStyleSheet("color: #9CA3AF; font-size: 10px;")
        stats.addWidget(self.min_label)
        
        self.avg_label = QLabel("Avg: --")
        self.avg_label.setStyleSheet("color: #9CA3AF; font-size: 10px;")
        stats.addWidget(self.avg_label)
        
        self.max_label = QLabel("Max: --")
        self.max_label.setStyleSheet("color: #9CA3AF; font-size: 10px;")
        stats.addWidget(self.max_label)
        
        stats.addStretch()
        layout.addLayout(stats)
    
    def update_display(self):
        """Update the display from series data."""
        if not self.series.samples:
            return
        
        current = self.series.current_value
        self.value_label.setText(f"{current:.1f}")
        
        # Update stats
        self.min_label.setText(f"Min: {self.series.min:.1f}")
        self.avg_label.setText(f"Avg: {self.series.average:.1f}")
        self.max_label.setText(f"Max: {self.series.max:.1f}")
        
        # Update trend
        samples = list(self.series.samples)
        if len(samples) >= 2:
            prev = samples[-2].value
            if current > prev * 1.05:
                self.trend_label.setText("↑")
                self.trend_label.setStyleSheet("color: #EF4444; font-size: 16px;")
            elif current < prev * 0.95:
                self.trend_label.setText("↓")
                self.trend_label.setStyleSheet("color: #10B981; font-size: 16px;")
            else:
                self.trend_label.setText("→")
                self.trend_label.setStyleSheet("color: #6B7280; font-size: 16px;")
        
        # Update status
        if self.series.critical_threshold > 0 and current >= self.series.critical_threshold:
            self.status_dot.setStyleSheet("color: #EF4444; font-size: 10px;")
        elif self.series.warning_threshold > 0 and current >= self.series.warning_threshold:
            self.status_dot.setStyleSheet("color: #F59E0B; font-size: 10px;")
        else:
            self.status_dot.setStyleSheet("color: #10B981; font-size: 10px;")
        
        # Update sparkline
        self.sparkline.update()


class GaugeWidget(QWidget):
    """
    Circular gauge for displaying percentage values.
    """
    
    def __init__(self, label: str = "", color: str = "#3B82F6", parent=None):
        super().__init__(parent)
        self.label = label
        self.color = color
        self.value = 0.0
        self.max_value = 100.0
        
        self.setMinimumSize(120, 120)
    
    def set_value(self, value: float, max_value: float = 100.0):
        self.value = value
        self.max_value = max_value
        self.update()
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        size = min(self.width(), self.height())
        center = QPointF(self.width() / 2, self.height() / 2)
        radius = size / 2 - 10
        
        # Background arc
        painter.setPen(QPen(QColor("#E5E7EB"), 8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawArc(
            QRectF(center.x() - radius, center.y() - radius, radius * 2, radius * 2),
            225 * 16,  # Start angle (in 1/16th degrees)
            -270 * 16  # Span angle
        )
        
        # Value arc
        if self.max_value > 0:
            angle = int(270 * (self.value / self.max_value))
            painter.setPen(QPen(QColor(self.color), 8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            painter.drawArc(
                QRectF(center.x() - radius, center.y() - radius, radius * 2, radius * 2),
                225 * 16,
                -angle * 16
            )
        
        # Value text
        painter.setPen(QColor("#1F2937"))
        font = QFont("SF Pro Display", 20)
        font.setWeight(QFont.Weight.Bold)
        painter.setFont(font)
        
        value_text = f"{self.value:.0f}" if self.value == int(self.value) else f"{self.value:.1f}"
        painter.drawText(
            QRectF(0, center.y() - 20, self.width(), 40),
            Qt.AlignmentFlag.AlignCenter,
            value_text
        )
        
        # Label
        painter.setPen(QColor("#6B7280"))
        font.setPointSize(10)
        font.setWeight(QFont.Weight.Normal)
        painter.setFont(font)
        painter.drawText(
            QRectF(0, center.y() + 15, self.width(), 20),
            Qt.AlignmentFlag.AlignCenter,
            self.label
        )


class FlowStatusWidget(QFrame):
    """
    Widget showing status of individual traffic flows.
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.flows: List[Dict] = []
        self._setup_ui()
    
    def _setup_ui(self):
        self.setStyleSheet("""
            FlowStatusWidget {
                background: white;
                border: 1px solid #E5E7EB;
                border-radius: 8px;
            }
        """)
        
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(2, 2, 2, 2)
        self.layout.setSpacing(2)
        
        # Header
        header = QLabel("Flow Status")
        header.setStyleSheet("font-weight: bold; color: #374151;")
        self.layout.addWidget(header)
        
        self.flow_container = QVBoxLayout()
        self.layout.addLayout(self.flow_container)
        self.layout.addStretch()
    
    def set_flows(self, flows: List[Dict]):
        """
        Set flow status data.
        
        Each flow dict should have:
        - name: str
        - status: str ("active", "warning", "error", "inactive")
        - latency_ms: float
        - packets_sent: int
        - packets_lost: int
        """
        self.flows = flows
        self._refresh()
    
    def _refresh(self):
        # Clear existing
        while self.flow_container.count():
            item = self.flow_container.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        for flow in self.flows:
            row = self._create_flow_row(flow)
            self.flow_container.addWidget(row)
    
    def _create_flow_row(self, flow: Dict) -> QFrame:
        row = QFrame()
        row.setStyleSheet("""
            QFrame {
                background: #F9FAFB;
                border-radius: 4px;
                padding: 2px;
            }
        """)
        
        layout = QHBoxLayout(row)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(2)
        
        # Status indicator
        status = flow.get("status", "inactive")
        status_colors = {
            "active": "#10B981",
            "warning": "#F59E0B",
            "error": "#EF4444",
            "inactive": "#9CA3AF",
        }
        
        status_dot = QLabel("●")
        status_dot.setStyleSheet(f"color: {status_colors.get(status, '#9CA3AF')}; font-size: 10px;")
        layout.addWidget(status_dot)
        
        # Name
        name_label = QLabel(flow.get("name", "Unknown"))
        name_label.setStyleSheet("color: #374151; font-size: 12px;")
        layout.addWidget(name_label, 1)
        
        # Latency
        latency = flow.get("latency_ms", 0)
        latency_label = QLabel(f"{latency:.1f}ms")
        latency_label.setStyleSheet("color: #6B7280; font-size: 11px;")
        layout.addWidget(latency_label)
        
        # Loss
        sent = flow.get("packets_sent", 0)
        lost = flow.get("packets_lost", 0)
        loss_pct = (lost / sent * 100) if sent > 0 else 0
        
        loss_label = QLabel(f"{loss_pct:.1f}%")
        loss_color = "#10B981" if loss_pct < 1 else ("#F59E0B" if loss_pct < 5 else "#EF4444")
        loss_label.setStyleSheet(f"color: {loss_color}; font-size: 11px;")
        layout.addWidget(loss_label)
        
        return row


class FailoverTimeline(QWidget):
    """
    Widget showing failover event timeline.
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.events: List[Dict] = []
        self.setMinimumHeight(80)
    
    def set_events(self, events: List[Dict]):
        """
        Set failover events.
        
        Each event dict should have:
        - time_s: float
        - type: str ("failure", "detection", "switchover", "recovery")
        - description: str
        """
        self.events = sorted(events, key=lambda e: e.get("time_s", 0))
        self.update()
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        width = self.width()
        height = self.height()
        margin = 40
        line_y = height // 2
        
        # Draw timeline line
        painter.setPen(QPen(QColor("#D1D5DB"), 2))
        painter.drawLine(margin, line_y, width - margin, line_y)
        
        if not self.events:
            painter.setPen(QColor("#9CA3AF"))
            painter.drawText(QRectF(0, 0, width, height),
                Qt.AlignmentFlag.AlignCenter, "No failover events")
            return
        
        # Calculate time range
        min_time = min(e.get("time_s", 0) for e in self.events)
        max_time = max(e.get("time_s", 0) for e in self.events)
        time_range = max_time - min_time if max_time != min_time else 1
        
        # Event colors
        colors = {
            "failure": "#EF4444",
            "detection": "#F59E0B",
            "switchover": "#3B82F6",
            "recovery": "#10B981",
        }
        
        # Draw events
        for i, evt in enumerate(self.events):
            t = evt.get("time_s", 0)
            x = margin + (t - min_time) / time_range * (width - 2 * margin)
            
            event_type = evt.get("type", "failure")
            color = QColor(colors.get(event_type, "#6B7280"))
            
            # Draw marker
            painter.setBrush(color)
            painter.setPen(QPen(color.darker(120), 2))
            painter.drawEllipse(QPointF(x, line_y), 8, 8)
            
            # Draw time label
            painter.setPen(QColor("#374151"))
            font = QFont("SF Pro Display", 9)
            painter.setFont(font)
            
            y_offset = -25 if i % 2 == 0 else 25
            painter.drawText(
                QRectF(x - 30, line_y + y_offset, 60, 20),
                Qt.AlignmentFlag.AlignCenter,
                f"{t:.1f}s"
            )


class MetricsDashboard(QWidget):
    """
    Complete metrics dashboard for grid simulation monitoring.
    
    Displays:
    - Key performance indicators (latency, loss, throughput)
    - Per-flow status
    - Failover timing
    - Protocol metrics
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Metric series
        self.latency_series = MetricSeries(
            name="End-to-End Latency",
            unit="ms",
            color="#3B82F6",
            warning_threshold=50,
            critical_threshold=100,
        )
        
        self.loss_series = MetricSeries(
            name="Packet Loss",
            unit="%",
            color="#EF4444",
            warning_threshold=1,
            critical_threshold=5,
        )
        
        self.throughput_series = MetricSeries(
            name="Throughput",
            unit="kbps",
            color="#10B981",
        )
        
        self.response_time_series = MetricSeries(
            name="Response Time",
            unit="ms",
            color="#8B5CF6",
            warning_threshold=100,
            critical_threshold=500,
        )
        
        self._setup_ui()
        
        # Demo data timer (for testing)
        self.demo_timer = QTimer()
        self.demo_timer.timeout.connect(self._add_demo_data)
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Header
        header = self._create_header()
        layout.addWidget(header)
        
        # Scrollable content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: #F3F4F6; }")
        
        content = QWidget()
        content.setStyleSheet("background: #F3F4F6;")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(2, 2, 2, 2)
        content_layout.setSpacing(2)
        
        # KPI Cards row
        kpi_row = QHBoxLayout()
        kpi_row.setSpacing(2)
        
        self.latency_card = MetricCard(self.latency_series)
        kpi_row.addWidget(self.latency_card)
        
        self.loss_card = MetricCard(self.loss_series)
        kpi_row.addWidget(self.loss_card)
        
        self.throughput_card = MetricCard(self.throughput_series)
        kpi_row.addWidget(self.throughput_card)
        
        self.response_card = MetricCard(self.response_time_series)
        kpi_row.addWidget(self.response_card)
        
        content_layout.addLayout(kpi_row)
        
        # Second row: gauges and flow status
        second_row = QHBoxLayout()
        second_row.setSpacing(2)
        
        # Gauges group
        gauges_group = QFrame()
        gauges_group.setStyleSheet("""
            QFrame {
                background: white;
                border: 1px solid #E5E7EB;
                border-radius: 12px;
            }
        """)
        gauges_layout = QVBoxLayout(gauges_group)
        gauges_layout.setContentsMargins(2, 2, 2, 2)
        
        gauges_title = QLabel("System Health")
        gauges_title.setStyleSheet("font-weight: bold; color: #374151;")
        gauges_layout.addWidget(gauges_title)
        
        gauges_row = QHBoxLayout()
        
        self.availability_gauge = GaugeWidget("Availability", "#10B981")
        self.availability_gauge.set_value(99.9)
        gauges_row.addWidget(self.availability_gauge)
        
        self.success_gauge = GaugeWidget("Success Rate", "#3B82F6")
        self.success_gauge.set_value(98.5)
        gauges_row.addWidget(self.success_gauge)
        
        self.health_gauge = GaugeWidget("Health", "#8B5CF6")
        self.health_gauge.set_value(95.0)
        gauges_row.addWidget(self.health_gauge)
        
        gauges_layout.addLayout(gauges_row)
        second_row.addWidget(gauges_group)
        
        # Flow status
        self.flow_status = FlowStatusWidget()
        second_row.addWidget(self.flow_status)
        
        content_layout.addLayout(second_row)
        
        # Failover timeline
        timeline_group = QFrame()
        timeline_group.setStyleSheet("""
            QFrame {
                background: white;
                border: 1px solid #E5E7EB;
                border-radius: 12px;
            }
        """)
        timeline_layout = QVBoxLayout(timeline_group)
        timeline_layout.setContentsMargins(2, 2, 2, 2)
        
        timeline_title = QLabel("Failover Timeline")
        timeline_title.setStyleSheet("font-weight: bold; color: #374151;")
        timeline_layout.addWidget(timeline_title)
        
        self.failover_timeline = FailoverTimeline()
        timeline_layout.addWidget(self.failover_timeline)
        
        content_layout.addWidget(timeline_group)
        
        content_layout.addStretch()
        
        scroll.setWidget(content)
        layout.addWidget(scroll)
    
    def _create_header(self) -> QFrame:
        header = QFrame()
        header.setStyleSheet("""
            QFrame {
                background: white;
                border-bottom: 1px solid #E5E7EB;
            }
        """)
        
        layout = QHBoxLayout(header)
        layout.setContentsMargins(2, 2, 2, 2)
        
        title = QLabel("Metrics Dashboard")
        title_font = QFont("SF Pro Display", 16)
        title_font.setWeight(QFont.Weight.Bold)
        title.setFont(title_font)
        layout.addWidget(title)
        
        layout.addStretch()
        
        # Status
        self.status_label = QLabel("● Monitoring")
        self.status_label.setStyleSheet("color: #10B981; font-weight: 500;")
        layout.addWidget(self.status_label)
        
        # Demo button
        demo_btn = QPushButton("Demo Data")
        demo_btn.setCheckable(True)
        demo_btn.setStyleSheet("""
            QPushButton {
                background: #F3F4F6;
                border: 1px solid #D1D5DB;
                border-radius: 6px;
                padding: 2px 4px;
            }
            QPushButton:checked {
                background: #3B82F6;
                color: white;
                border-color: #3B82F6;
            }
        """)
        demo_btn.toggled.connect(self._toggle_demo)
        layout.addWidget(demo_btn)
        
        # Reset button
        reset_btn = QPushButton("Reset")
        reset_btn.setStyleSheet("""
            QPushButton {
                background: #F3F4F6;
                border: 1px solid #D1D5DB;
                border-radius: 6px;
                padding: 2px 4px;
            }
            QPushButton:hover { background: #E5E7EB; }
        """)
        reset_btn.clicked.connect(self.reset_metrics)
        layout.addWidget(reset_btn)
        
        return header
    
    def add_latency_sample(self, value: float, timestamp: float = None):
        """Add a latency sample."""
        self.latency_series.add_sample(value, timestamp)
        self.latency_card.update_display()
    
    def add_loss_sample(self, value: float, timestamp: float = None):
        """Add a packet loss sample."""
        self.loss_series.add_sample(value, timestamp)
        self.loss_card.update_display()
    
    def add_throughput_sample(self, value: float, timestamp: float = None):
        """Add a throughput sample."""
        self.throughput_series.add_sample(value, timestamp)
        self.throughput_card.update_display()
    
    def add_response_time_sample(self, value: float, timestamp: float = None):
        """Add a response time sample."""
        self.response_time_series.add_sample(value, timestamp)
        self.response_card.update_display()
    
    def update_flow_status(self, flows: List[Dict]):
        """Update flow status display."""
        self.flow_status.set_flows(flows)
    
    def update_failover_events(self, events: List[Dict]):
        """Update failover timeline."""
        self.failover_timeline.set_events(events)
    
    def update_gauges(self, availability: float, success_rate: float, health: float):
        """Update gauge values."""
        self.availability_gauge.set_value(availability)
        self.success_gauge.set_value(success_rate)
        self.health_gauge.set_value(health)
    
    def reset_metrics(self):
        """Reset all metrics."""
        self.latency_series.samples.clear()
        self.loss_series.samples.clear()
        self.throughput_series.samples.clear()
        self.response_time_series.samples.clear()
        
        self.latency_card.update_display()
        self.loss_card.update_display()
        self.throughput_card.update_display()
        self.response_card.update_display()
        
        self.flow_status.set_flows([])
        self.failover_timeline.set_events([])
    
    def _toggle_demo(self, enabled: bool):
        """Toggle demo data generation."""
        if enabled:
            self.demo_timer.start(500)  # Update every 500ms
            self.status_label.setText("● Demo Mode")
            self.status_label.setStyleSheet("color: #F59E0B; font-weight: 500;")
        else:
            self.demo_timer.stop()
            self.status_label.setText("● Monitoring")
            self.status_label.setStyleSheet("color: #10B981; font-weight: 500;")
    
    def _add_demo_data(self):
        """Add demo data for testing."""
        # Add random samples
        self.add_latency_sample(20 + random.gauss(0, 5))
        self.add_loss_sample(max(0, random.gauss(0.5, 0.3)))
        self.add_throughput_sample(100 + random.gauss(0, 10))
        self.add_response_time_sample(50 + random.gauss(0, 15))
        
        # Update flow status
        flows = [
            {"name": "EMS → RTU_1", "status": "active", "latency_ms": 15.2, "packets_sent": 1000, "packets_lost": 2},
            {"name": "EMS → RTU_2", "status": "active", "latency_ms": 18.5, "packets_sent": 1000, "packets_lost": 5},
            {"name": "EMS → RTU_3", "status": "warning", "latency_ms": 45.0, "packets_sent": 1000, "packets_lost": 15},
        ]
        self.update_flow_status(flows)
        
        # Update gauges
        self.update_gauges(
            99.9 - random.uniform(0, 0.5),
            98.5 + random.gauss(0, 0.5),
            95.0 + random.gauss(0, 2),
        )
