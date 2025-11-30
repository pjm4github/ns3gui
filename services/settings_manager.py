"""
Settings Manager.

Handles application settings with JSON file storage.
"""

import json
import os
from dataclasses import dataclass, field, asdict
from typing import Optional, Dict, List
from pathlib import Path


@dataclass
class NS3Settings:
    """ns-3 related settings."""
    path: str = ""
    use_wsl: bool = True
    wsl_distribution: str = "Ubuntu"
    auto_detect: bool = True


@dataclass 
class SimulationDefaults:
    """Default simulation parameters."""
    duration: float = 10.0
    random_seed: int = 1
    enable_flow_monitor: bool = True
    enable_ascii_trace: bool = False
    enable_pcap: bool = False


@dataclass
class UISettings:
    """User interface settings."""
    theme: str = "light"
    show_grid: bool = True
    grid_size: int = 50
    auto_save: bool = True
    auto_save_interval: int = 300  # seconds
    recent_files_max: int = 10
    animation_speed: float = 1.0
    show_packet_animations: bool = True


@dataclass
class PathSettings:
    """
    Workspace and file path settings.
    
    Supports multiple workspace configurations for different use cases:
    - default: Normal user workspace
    - test: Automated testing workspace
    - custom: User-defined workspace
    """
    # Active workspace profile
    active_profile: str = "default"
    
    # Workspace profiles - maps profile name to base directory
    # If empty, uses platform-specific default
    workspaces: Dict[str, str] = field(default_factory=dict)
    
    # Subdirectory names within workspace
    topologies_subdir: str = "topologies"
    scripts_subdir: str = "scripts"
    results_subdir: str = "results"
    templates_subdir: str = "templates"
    
    # Last used directories (for file dialogs)
    last_open_dir: str = ""
    last_save_dir: str = ""
    last_export_dir: str = ""
    
    def get_workspace_root(self, profile: Optional[str] = None) -> Path:
        """
        Get the root directory for a workspace profile.
        
        Args:
            profile: Profile name, or None to use active profile
            
        Returns:
            Path to workspace root directory
        """
        profile = profile or self.active_profile
        
        # Check if profile has explicit path
        if profile in self.workspaces and self.workspaces[profile]:
            return Path(self.workspaces[profile])
        
        # Use platform-specific default
        return self._get_default_workspace()
    
    def _get_default_workspace(self) -> Path:
        """Get platform-specific default workspace directory."""
        import platform
        system = platform.system()
        
        if system == "Windows":
            # Use Documents folder on Windows
            docs = Path(os.environ.get("USERPROFILE", "~")) / "Documents"
            return docs.expanduser() / "NS3GUI"
        elif system == "Darwin":  # macOS
            return Path.home() / "Documents" / "NS3GUI"
        else:  # Linux and others
            return Path.home() / "ns3gui"
    
    def get_topologies_dir(self, profile: Optional[str] = None) -> Path:
        """Get the topologies directory for a profile."""
        return self.get_workspace_root(profile) / self.topologies_subdir
    
    def get_scripts_dir(self, profile: Optional[str] = None) -> Path:
        """Get the generated scripts directory for a profile."""
        return self.get_workspace_root(profile) / self.scripts_subdir
    
    def get_results_dir(self, profile: Optional[str] = None) -> Path:
        """Get the simulation results directory for a profile."""
        return self.get_workspace_root(profile) / self.results_subdir
    
    def get_templates_dir(self, profile: Optional[str] = None) -> Path:
        """Get the topology templates directory for a profile."""
        return self.get_workspace_root(profile) / self.templates_subdir
    
    def ensure_workspace_dirs(self, profile: Optional[str] = None):
        """Create workspace directories if they don't exist."""
        dirs = [
            self.get_topologies_dir(profile),
            self.get_scripts_dir(profile),
            self.get_results_dir(profile),
            self.get_templates_dir(profile),
        ]
        for d in dirs:
            d.mkdir(parents=True, exist_ok=True)


@dataclass
class AppSettings:
    """Complete application settings."""
    ns3: NS3Settings = field(default_factory=NS3Settings)
    simulation: SimulationDefaults = field(default_factory=SimulationDefaults)
    ui: UISettings = field(default_factory=UISettings)
    paths: PathSettings = field(default_factory=PathSettings)
    recent_files: list = field(default_factory=list)
    window_geometry: dict = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "ns3": asdict(self.ns3),
            "simulation": asdict(self.simulation),
            "ui": asdict(self.ui),
            "paths": asdict(self.paths),
            "recent_files": self.recent_files,
            "window_geometry": self.window_geometry,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "AppSettings":
        """Create from dictionary."""
        settings = cls()
        
        if "ns3" in data:
            settings.ns3 = NS3Settings(**data["ns3"])
        if "simulation" in data:
            settings.simulation = SimulationDefaults(**data["simulation"])
        if "ui" in data:
            settings.ui = UISettings(**data["ui"])
        if "paths" in data:
            # Handle paths specially to deal with nested dict
            paths_data = data["paths"]
            settings.paths = PathSettings(
                active_profile=paths_data.get("active_profile", "default"),
                workspaces=paths_data.get("workspaces", {}),
                topologies_subdir=paths_data.get("topologies_subdir", "topologies"),
                scripts_subdir=paths_data.get("scripts_subdir", "scripts"),
                results_subdir=paths_data.get("results_subdir", "results"),
                templates_subdir=paths_data.get("templates_subdir", "templates"),
                last_open_dir=paths_data.get("last_open_dir", ""),
                last_save_dir=paths_data.get("last_save_dir", ""),
                last_export_dir=paths_data.get("last_export_dir", ""),
            )
        if "recent_files" in data:
            settings.recent_files = data["recent_files"]
        if "window_geometry" in data:
            settings.window_geometry = data["window_geometry"]
        
        return settings


class SettingsManager:
    """
    Manages application settings with JSON file storage.
    
    Settings file location:
    - Windows: %APPDATA%/NS3GUI/settings.json
    - Linux: ~/.config/NS3GUI/settings.json
    - macOS: ~/Library/Application Support/NS3GUI/settings.json
    """
    
    APP_NAME = "NS3GUI"
    SETTINGS_FILE = "settings.json"
    
    def __init__(self, config_override: Optional[str] = None):
        """
        Initialize settings manager.
        
        Args:
            config_override: Optional path to override config file location.
                            Useful for testing.
        """
        self._settings = AppSettings()
        self._config_override = config_override
        self._settings_path = self._get_settings_path()
        self._ensure_settings_dir()
        self.load()
    
    @property
    def settings(self) -> AppSettings:
        """Get current settings."""
        return self._settings
    
    @property
    def settings_path(self) -> str:
        """Get the settings file path."""
        return str(self._settings_path)
    
    @property
    def paths(self) -> PathSettings:
        """Get path settings."""
        return self._settings.paths
    
    # Convenience properties for common settings
    @property
    def ns3_path(self) -> str:
        return self._settings.ns3.path
    
    @ns3_path.setter
    def ns3_path(self, value: str):
        self._settings.ns3.path = value
        self.save()
    
    @property
    def ns3_use_wsl(self) -> bool:
        return self._settings.ns3.use_wsl
    
    @ns3_use_wsl.setter
    def ns3_use_wsl(self, value: bool):
        self._settings.ns3.use_wsl = value
        self.save()
    
    @property
    def wsl_distribution(self) -> str:
        return self._settings.ns3.wsl_distribution
    
    @wsl_distribution.setter
    def wsl_distribution(self, value: str):
        self._settings.ns3.wsl_distribution = value
        self.save()
    
    # Path convenience methods
    def get_topologies_dir(self) -> Path:
        """Get the active topologies directory."""
        return self._settings.paths.get_topologies_dir()
    
    def get_scripts_dir(self) -> Path:
        """Get the active scripts directory."""
        return self._settings.paths.get_scripts_dir()
    
    def get_results_dir(self) -> Path:
        """Get the active results directory."""
        return self._settings.paths.get_results_dir()
    
    def get_open_directory(self) -> str:
        """Get the directory to use for Open dialogs."""
        # Priority: last used > topologies dir > current dir
        if self._settings.paths.last_open_dir and os.path.isdir(self._settings.paths.last_open_dir):
            return self._settings.paths.last_open_dir
        
        topo_dir = self.get_topologies_dir()
        if topo_dir.exists():
            return str(topo_dir)
        
        return ""
    
    def set_open_directory(self, path: str):
        """Set the last used Open directory."""
        if os.path.isfile(path):
            path = os.path.dirname(path)
        self._settings.paths.last_open_dir = path
        self.save()
    
    def get_save_directory(self) -> str:
        """Get the directory to use for Save dialogs."""
        # Priority: last used > topologies dir > current dir
        if self._settings.paths.last_save_dir and os.path.isdir(self._settings.paths.last_save_dir):
            return self._settings.paths.last_save_dir
        
        topo_dir = self.get_topologies_dir()
        if topo_dir.exists():
            return str(topo_dir)
        
        return ""
    
    def set_save_directory(self, path: str):
        """Set the last used Save directory."""
        if os.path.isfile(path):
            path = os.path.dirname(path)
        self._settings.paths.last_save_dir = path
        self.save()
    
    def set_workspace_profile(self, profile: str):
        """Set the active workspace profile."""
        self._settings.paths.active_profile = profile
        self.save()
    
    def set_workspace_path(self, profile: str, path: str):
        """Set the path for a workspace profile."""
        self._settings.paths.workspaces[profile] = path
        self.save()
    
    def ensure_workspace(self):
        """Ensure workspace directories exist for active profile."""
        self._settings.paths.ensure_workspace_dirs()
    
    def _get_settings_path(self) -> Path:
        """Get platform-specific settings directory."""
        if self._config_override:
            return Path(self._config_override)
        
        import platform
        system = platform.system()
        
        if system == "Windows":
            base = os.environ.get("APPDATA", os.path.expanduser("~"))
            config_dir = Path(base) / self.APP_NAME
        elif system == "Darwin":  # macOS
            config_dir = Path.home() / "Library" / "Application Support" / self.APP_NAME
        else:  # Linux and others
            xdg_config = os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config"))
            config_dir = Path(xdg_config) / self.APP_NAME
        
        return config_dir / self.SETTINGS_FILE
    
    def _ensure_settings_dir(self):
        """Create settings directory if it doesn't exist."""
        self._settings_path.parent.mkdir(parents=True, exist_ok=True)
    
    def load(self) -> bool:
        """Load settings from file."""
        if not self._settings_path.exists():
            return False
        
        try:
            with open(self._settings_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._settings = AppSettings.from_dict(data)
            return True
        except Exception as e:
            print(f"Error loading settings: {e}")
            return False
    
    def save(self) -> bool:
        """Save settings to file."""
        try:
            self._ensure_settings_dir()
            with open(self._settings_path, "w", encoding="utf-8") as f:
                json.dump(self._settings.to_dict(), f, indent=2)
            return True
        except Exception as e:
            print(f"Error saving settings: {e}")
            return False
    
    def reset(self):
        """Reset settings to defaults."""
        self._settings = AppSettings()
        self.save()
    
    def add_recent_file(self, file_path: str):
        """Add a file to recent files list."""
        # Remove if already exists
        if file_path in self._settings.recent_files:
            self._settings.recent_files.remove(file_path)
        
        # Add to front
        self._settings.recent_files.insert(0, file_path)
        
        # Trim to max
        max_files = self._settings.ui.recent_files_max
        self._settings.recent_files = self._settings.recent_files[:max_files]
        
        self.save()
    
    def get_recent_files(self) -> list:
        """Get recent files list, filtered to existing files."""
        existing = [f for f in self._settings.recent_files if os.path.exists(f)]
        if len(existing) != len(self._settings.recent_files):
            self._settings.recent_files = existing
            self.save()
        return existing
    
    def save_window_geometry(self, geometry: bytes, state: bytes):
        """Save window geometry and state."""
        import base64
        self._settings.window_geometry = {
            "geometry": base64.b64encode(geometry).decode("ascii"),
            "state": base64.b64encode(state).decode("ascii"),
        }
        self.save()
    
    def get_window_geometry(self) -> tuple:
        """Get saved window geometry and state."""
        import base64
        geo = self._settings.window_geometry
        if not geo:
            return None, None
        
        try:
            geometry = base64.b64decode(geo.get("geometry", ""))
            state = base64.b64decode(geo.get("state", ""))
            return geometry, state
        except Exception:
            return None, None


# Global settings instance
_settings_manager: Optional[SettingsManager] = None


def get_settings(config_override: Optional[str] = None) -> SettingsManager:
    """
    Get the global settings manager instance.
    
    Args:
        config_override: Optional path to override config location.
                        Only used on first call to initialize.
    """
    global _settings_manager
    if _settings_manager is None:
        _settings_manager = SettingsManager(config_override)
    return _settings_manager


def reset_settings_manager():
    """Reset the global settings manager (useful for testing)."""
    global _settings_manager
    _settings_manager = None
