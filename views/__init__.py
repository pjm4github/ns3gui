"""Views package."""

from .topology_canvas import (
    TopologyCanvas,
    TopologyScene,
    NodeGraphicsItem,
    LinkGraphicsItem,
    PacketAnimationItem,
    PacketAnimationManager,
)
from .property_panel import PropertyPanel
from .node_palette import NodePalette
from .stats_panel import StatsPanel
from .playback_controls import PlaybackControls
from .settings_dialog import SettingsDialog
from .ns3_import_dialog import NS3ImportDialog, NS3BatchImportDialog
from .code_preview_dialog import CodePreviewDialog
from .help_dialog import HelpDialog
from .socket_app_editor import SocketAppEditorDialog
from .project_dialog import (
    NewProjectDialog,
    OpenProjectDialog,
    WorkspaceSettingsDialog,
    ProjectInfoDialog,
)
from .main_window import MainWindow

# V2 Grid GUI Components
from .grid_node_palette import (
    GridNodeTypeButton,
    GridNodePalette,
    CombinedNodePalette,
)
from .failure_scenario_panel import (
    EventTimelineWidget,
    EventEditorDialog,
    FailureScenarioPanel,
)
from .traffic_pattern_editor import (
    PollingGroupWidget,
    FlowEditorDialog,
    TrafficFlowTable,
    TrafficPatternEditor,
)
from .metrics_dashboard import (
    MetricSeries,
    SparklineWidget,
    MetricCard,
    GaugeWidget,
    FlowStatusWidget,
    FailoverTimeline,
    MetricsDashboard,
)

__all__ = [
    # Base components
    "TopologyCanvas",
    "TopologyScene", 
    "NodeGraphicsItem",
    "LinkGraphicsItem",
    "PacketAnimationItem",
    "PacketAnimationManager",
    "PropertyPanel",
    "NodePalette",
    "StatsPanel",
    "PlaybackControls",
    "SettingsDialog",
    "NS3ImportDialog",
    "NS3BatchImportDialog",
    "CodePreviewDialog",
    "HelpDialog",
    "SocketAppEditorDialog",
    "NewProjectDialog",
    "OpenProjectDialog",
    "WorkspaceSettingsDialog",
    "ProjectInfoDialog",
    "MainWindow",
    # V2 Grid GUI Components
    "GridNodeTypeButton",
    "GridNodePalette",
    "CombinedNodePalette",
    "EventTimelineWidget",
    "EventEditorDialog",
    "FailureScenarioPanel",
    "PollingGroupWidget",
    "FlowEditorDialog",
    "TrafficFlowTable",
    "TrafficPatternEditor",
    "MetricSeries",
    "SparklineWidget",
    "MetricCard",
    "GaugeWidget",
    "FlowStatusWidget",
    "FailoverTimeline",
    "MetricsDashboard",
]
