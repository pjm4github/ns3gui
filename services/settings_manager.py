"""
Settings Manager.

Handles application settings with JSON file storage.
"""

import json
import os
from dataclasses import dataclass, field, asdict
from typing import Optional
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
class AppSettings:
    """Complete application settings."""
    ns3: NS3Settings = field(default_factory=NS3Settings)
    simulation: SimulationDefaults = field(default_factory=SimulationDefaults)
    ui: UISettings = field(default_factory=UISettings)
    recent_files: list = field(default_factory=list)
    window_geometry: dict = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "ns3": asdict(self.ns3),
            "simulation": asdict(self.simulation),
            "ui": asdict(self.ui),
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
    
    def __init__(self):
        self._settings = AppSettings()
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
    
    def _get_settings_path(self) -> Path:
        """Get platform-specific settings directory."""
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


def get_settings() -> SettingsManager:
    """Get the global settings manager instance."""
    global _settings_manager
    if _settings_manager is None:
        _settings_manager = SettingsManager()
    return _settings_manager
