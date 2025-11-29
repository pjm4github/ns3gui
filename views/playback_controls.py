"""
Playback Controls Widget.

Provides timeline slider, play/pause, speed controls for
trace-based packet animation replay.
"""

from typing import Optional
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QPushButton,
    QSlider, QLabel, QComboBox, QFrame, QStyle
)

from services.trace_player import TracePlayer, TraceStats


class PlaybackControls(QFrame):
    """
    Playback control bar with timeline and buttons.
    
    Features:
    - Play/Pause button
    - Stop button
    - Timeline slider with scrubbing
    - Speed selector
    - Time display
    """
    
    # Signals
    visibility_requested = pyqtSignal(bool)  # Show/hide packet animations
    
    def __init__(self, trace_player: TracePlayer, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._player = trace_player
        self._setup_ui()
        self._connect_signals()
    
    def _setup_ui(self):
        self.setStyleSheet("""
            PlaybackControls {
                background: #1F2937;
                border-radius: 8px;
                padding: 8px;
            }
            QLabel {
                color: #E5E7EB;
            }
            QPushButton {
                background: #374151;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 12px;
                font-size: 14px;
                min-width: 36px;
            }
            QPushButton:hover {
                background: #4B5563;
            }
            QPushButton:pressed {
                background: #1F2937;
            }
            QPushButton:disabled {
                background: #1F2937;
                color: #6B7280;
            }
            QPushButton#playBtn {
                background: #3B82F6;
                min-width: 48px;
            }
            QPushButton#playBtn:hover {
                background: #2563EB;
            }
            QSlider::groove:horizontal {
                height: 6px;
                background: #374151;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                width: 14px;
                height: 14px;
                margin: -4px 0;
                background: #3B82F6;
                border-radius: 7px;
            }
            QSlider::handle:horizontal:hover {
                background: #60A5FA;
            }
            QSlider::sub-page:horizontal {
                background: #3B82F6;
                border-radius: 3px;
            }
            QComboBox {
                background: #374151;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 24px 6px 8px;
                min-width: 70px;
            }
            QComboBox:hover {
                background: #4B5563;
            }
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 5px solid #9CA3AF;
                margin-right: 8px;
            }
            QComboBox QAbstractItemView {
                background: #374151;
                color: white;
                selection-background-color: #3B82F6;
                border: 1px solid #4B5563;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(8)
        
        # Top row: Timeline
        timeline_layout = QHBoxLayout()
        timeline_layout.setSpacing(12)
        
        # Current time
        self._current_time_label = QLabel("0:00.0")
        self._current_time_label.setFixedWidth(60)
        self._current_time_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._current_time_label.setStyleSheet("font-family: monospace; font-size: 12px;")
        timeline_layout.addWidget(self._current_time_label)
        
        # Timeline slider
        self._timeline = QSlider(Qt.Orientation.Horizontal)
        self._timeline.setRange(0, 1000)
        self._timeline.setValue(0)
        self._timeline.setEnabled(False)
        timeline_layout.addWidget(self._timeline, 1)
        
        # Total time
        self._total_time_label = QLabel("0:00.0")
        self._total_time_label.setFixedWidth(60)
        self._total_time_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self._total_time_label.setStyleSheet("font-family: monospace; font-size: 12px;")
        timeline_layout.addWidget(self._total_time_label)
        
        layout.addLayout(timeline_layout)
        
        # Bottom row: Controls
        controls_layout = QHBoxLayout()
        controls_layout.setSpacing(8)
        
        # Play/Pause button
        self._play_btn = QPushButton("▶")
        self._play_btn.setObjectName("playBtn")
        self._play_btn.setToolTip("Play/Pause (Space)")
        self._play_btn.setEnabled(False)
        controls_layout.addWidget(self._play_btn)
        
        # Stop button
        self._stop_btn = QPushButton("⏹")
        self._stop_btn.setToolTip("Stop and reset")
        self._stop_btn.setEnabled(False)
        controls_layout.addWidget(self._stop_btn)
        
        # Separator
        controls_layout.addSpacing(16)
        
        # Step backward
        self._step_back_btn = QPushButton("⏮")
        self._step_back_btn.setToolTip("Jump to start")
        self._step_back_btn.setEnabled(False)
        controls_layout.addWidget(self._step_back_btn)
        
        # Step forward
        self._step_fwd_btn = QPushButton("⏭")
        self._step_fwd_btn.setToolTip("Jump to end")
        self._step_fwd_btn.setEnabled(False)
        controls_layout.addWidget(self._step_fwd_btn)
        
        controls_layout.addStretch()
        
        # Speed selector
        speed_label = QLabel("Speed:")
        speed_label.setStyleSheet("font-size: 12px;")
        controls_layout.addWidget(speed_label)
        
        self._speed_combo = QComboBox()
        self._speed_combo.addItems(["0.25x", "0.5x", "1x", "2x", "5x", "10x", "50x", "100x"])
        self._speed_combo.setCurrentText("1x")
        self._speed_combo.setEnabled(False)
        controls_layout.addWidget(self._speed_combo)
        
        controls_layout.addSpacing(16)
        
        # Event count
        self._event_label = QLabel("No events loaded")
        self._event_label.setStyleSheet("font-size: 11px; color: #9CA3AF;")
        controls_layout.addWidget(self._event_label)
        
        controls_layout.addStretch()
        
        # Show packets toggle
        self._show_packets_btn = QPushButton("Show Packets")
        self._show_packets_btn.setCheckable(True)
        self._show_packets_btn.setChecked(True)
        self._show_packets_btn.setToolTip("Toggle packet visualization")
        controls_layout.addWidget(self._show_packets_btn)
        
        layout.addLayout(controls_layout)
    
    def _connect_signals(self):
        """Connect signals and slots."""
        # Button clicks
        self._play_btn.clicked.connect(self._on_play_clicked)
        self._stop_btn.clicked.connect(self._player.stop)
        self._step_back_btn.clicked.connect(lambda: self._player.seek(0))
        self._step_fwd_btn.clicked.connect(lambda: self._player.seek(self._player.duration))
        
        # Timeline slider
        self._timeline.sliderPressed.connect(self._on_slider_pressed)
        self._timeline.sliderReleased.connect(self._on_slider_released)
        self._timeline.valueChanged.connect(self._on_slider_changed)
        
        # Speed combo
        self._speed_combo.currentTextChanged.connect(self._on_speed_changed)
        
        # Show packets toggle
        self._show_packets_btn.toggled.connect(self.visibility_requested.emit)
        
        # Player signals
        self._player.time_changed.connect(self._on_time_changed)
        self._player.playback_finished.connect(self._on_playback_finished)
        self._player.stats_updated.connect(self._on_stats_updated)
    
    def _on_play_clicked(self):
        """Handle play/pause button click."""
        if self._player.is_playing:
            self._player.pause()
            self._play_btn.setText("▶")
        else:
            self._player.play()
            self._play_btn.setText("⏸")
    
    def _on_slider_pressed(self):
        """Handle slider press - pause during drag."""
        self._was_playing = self._player.is_playing
        self._player.pause()
    
    def _on_slider_released(self):
        """Handle slider release - seek and optionally resume."""
        progress = self._timeline.value() / 1000.0
        self._player.seek_progress(progress)
        if self._was_playing:
            self._player.play()
            self._play_btn.setText("⏸")
    
    def _on_slider_changed(self, value: int):
        """Handle slider value change during drag."""
        if self._timeline.isSliderDown():
            # Preview time during drag
            progress = value / 1000.0
            time_secs = progress * self._player.duration
            self._current_time_label.setText(self._format_time(time_secs))
    
    def _on_speed_changed(self, text: str):
        """Handle speed change."""
        speed = float(text.rstrip('x'))
        self._player.speed = speed
    
    def _on_time_changed(self, time_seconds: float):
        """Handle time update from player."""
        self._current_time_label.setText(self._format_time(time_seconds))
        
        # Update slider (without triggering valueChanged feedback)
        if not self._timeline.isSliderDown():
            progress = int(self._player.progress * 1000)
            self._timeline.blockSignals(True)
            self._timeline.setValue(progress)
            self._timeline.blockSignals(False)
    
    def _on_playback_finished(self):
        """Handle playback finished."""
        self._play_btn.setText("▶")
    
    def _on_stats_updated(self, stats: TraceStats):
        """Handle trace stats update."""
        self._event_label.setText(
            f"{stats.total_events} events | "
            f"TX: {stats.total_packets_tx} | "
            f"RX: {stats.total_packets_rx} | "
            f"Drop: {stats.total_packets_dropped}"
        )
        self._total_time_label.setText(self._format_time(stats.duration_seconds))
    
    def _format_time(self, seconds: float) -> str:
        """Format time as M:SS.d"""
        if seconds < 0:
            seconds = 0
        mins = int(seconds // 60)
        secs = seconds % 60
        return f"{mins}:{secs:04.1f}"
    
    def set_enabled(self, enabled: bool):
        """Enable/disable all controls."""
        self._play_btn.setEnabled(enabled)
        self._stop_btn.setEnabled(enabled)
        self._step_back_btn.setEnabled(enabled)
        self._step_fwd_btn.setEnabled(enabled)
        self._timeline.setEnabled(enabled)
        self._speed_combo.setEnabled(enabled)
    
    def on_trace_loaded(self):
        """Called when a trace is loaded."""
        self.set_enabled(True)
        self._play_btn.setText("▶")
    
    def on_trace_cleared(self):
        """Called when trace is cleared."""
        self.set_enabled(False)
        self._play_btn.setText("▶")
        self._current_time_label.setText("0:00.0")
        self._total_time_label.setText("0:00.0")
        self._event_label.setText("No events loaded")
        self._timeline.setValue(0)
    
    def reset(self):
        """Reset to initial state."""
        self.on_trace_cleared()
