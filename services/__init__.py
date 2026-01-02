"""Services package."""

from .project_manager import ProjectManager, export_to_mininet
from .ns3_generator import NS3ScriptGenerator, generate_ns3_script
from .grid_ns3_generator import GridNS3Generator
from .simulation_runner import (
    NS3Detector,
    SimulationRunner,
    NS3SimulationManager,
    is_windows,
    is_wsl_available,
    windows_to_wsl_path,
    wsl_to_windows_path,
    wsl_unc_path_to_linux,
)
from .results_parser import ResultsParser, AsciiTraceParser, TraceEvent
from .trace_player import (
    TraceParser,
    TracePlayer,
    PacketEvent,
    PacketEventType,
    TraceStats,
)
from .settings_manager import (
    SettingsManager,
    AppSettings,
    NS3Settings,
    SimulationDefaults,
    UISettings,
    PathSettings,
    get_settings,
    reset_settings_manager,
)
from .ns3_script_parser import (
    NS3PythonParser,
    ExtractedTopology,
    ExtractedNode,
    ExtractedLink,
    TopologyExporter,
)
from .topology_converter import (
    TopologyConverter,
    WorkspaceManager,
    NS3ExampleProcessor,
)
from .shape_manager import (
    ShapeManager,
    get_shape_manager,
)

__all__ = [
    "ProjectManager",
    "export_to_mininet",
    # NS-3 Script Generation
    "NS3ScriptGenerator",
    "generate_ns3_script",
    "GridNS3Generator",  # Grid-specific generator
    "NS3Detector",
    "SimulationRunner",
    "NS3SimulationManager",
    "is_windows",
    "is_wsl_available",
    "windows_to_wsl_path",
    "wsl_to_windows_path",
    "wsl_unc_path_to_linux",
    "ResultsParser",
    "AsciiTraceParser",
    "TraceEvent",
    "TraceParser",
    "TracePlayer",
    "PacketEvent",
    "PacketEventType",
    "TraceStats",
    "SettingsManager",
    "AppSettings",
    "NS3Settings",
    "SimulationDefaults",
    "UISettings",
    "PathSettings",
    "get_settings",
    "reset_settings_manager",
    # NS-3 script parsing
    "NS3PythonParser",
    "ExtractedTopology",
    "ExtractedNode",
    "ExtractedLink",
    "TopologyExporter",
    # Topology conversion
    "TopologyConverter",
    "WorkspaceManager",
    "NS3ExampleProcessor",
    # Shape management
    "ShapeManager",
    "get_shape_manager",
]
