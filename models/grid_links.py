"""
Electric Grid Communication Link Models.

Extends the base LinkModel to support grid-specific link types including
fiber, microwave, serial radio, cellular, and satellite communications.
"""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional, Dict, Any, List

# Import V1 base classes
from .network import LinkModel, ChannelType


class GridLinkType(Enum):
    """
    Communication link types commonly used in electric grid networks.
    
    Each type maps to specific ns-3 helpers and has characteristic
    data rates, latencies, and reliability profiles.
    """
    # Wired - Primary backbone
    FIBER = auto()
    COPPER_SERIAL = auto()
    ETHERNET_LAN = auto()
    
    # Wireless - Line of sight
    MICROWAVE = auto()
    LICENSED_RADIO = auto()
    SPREAD_SPECTRUM = auto()
    
    # Wireless - Cellular
    CELLULAR_LTE = auto()
    CELLULAR_5G = auto()
    PRIVATE_LTE = auto()
    
    # Wireless - Satellite
    SATELLITE_GEO = auto()
    SATELLITE_LEO = auto()
    
    # Wireless - Mesh/Local
    WIFI_MESH = auto()
    WIMAX = auto()
    ZIGBEE = auto()
    
    # Special
    EMULATED = auto()
    
    def to_base_channel_type(self) -> ChannelType:
        """Map grid link type to V1 ChannelType for ns-3 code generation."""
        mapping = {
            GridLinkType.FIBER: ChannelType.POINT_TO_POINT,
            GridLinkType.COPPER_SERIAL: ChannelType.POINT_TO_POINT,
            GridLinkType.ETHERNET_LAN: ChannelType.CSMA,
            GridLinkType.MICROWAVE: ChannelType.POINT_TO_POINT,
            GridLinkType.LICENSED_RADIO: ChannelType.POINT_TO_POINT,
            GridLinkType.SPREAD_SPECTRUM: ChannelType.POINT_TO_POINT,
            GridLinkType.CELLULAR_LTE: ChannelType.POINT_TO_POINT,
            GridLinkType.CELLULAR_5G: ChannelType.POINT_TO_POINT,
            GridLinkType.PRIVATE_LTE: ChannelType.POINT_TO_POINT,
            GridLinkType.SATELLITE_GEO: ChannelType.POINT_TO_POINT,
            GridLinkType.SATELLITE_LEO: ChannelType.POINT_TO_POINT,
            GridLinkType.WIFI_MESH: ChannelType.WIFI,
            GridLinkType.WIMAX: ChannelType.POINT_TO_POINT,
            GridLinkType.ZIGBEE: ChannelType.POINT_TO_POINT,
            GridLinkType.EMULATED: ChannelType.POINT_TO_POINT,
        }
        return mapping.get(self, ChannelType.POINT_TO_POINT)
    
    def get_ns3_helper(self) -> str:
        """Get the ns-3 helper class name for this link type."""
        helpers = {
            GridLinkType.FIBER: "PointToPointHelper",
            GridLinkType.COPPER_SERIAL: "PointToPointHelper",
            GridLinkType.ETHERNET_LAN: "CsmaHelper",
            GridLinkType.MICROWAVE: "PointToPointHelper",
            GridLinkType.LICENSED_RADIO: "PointToPointHelper",
            GridLinkType.SPREAD_SPECTRUM: "PointToPointHelper",
            GridLinkType.CELLULAR_LTE: "LteHelper",
            GridLinkType.CELLULAR_5G: "LteHelper",
            GridLinkType.PRIVATE_LTE: "LteHelper",
            GridLinkType.SATELLITE_GEO: "PointToPointHelper",
            GridLinkType.SATELLITE_LEO: "PointToPointHelper",
            GridLinkType.WIFI_MESH: "WifiHelper",
            GridLinkType.WIMAX: "WimaxHelper",
            GridLinkType.ZIGBEE: "LrWpanHelper",
            GridLinkType.EMULATED: "EmuFdNetDeviceHelper",
        }
        return helpers.get(self, "PointToPointHelper")


class LinkReliabilityClass(Enum):
    """Reliability classification for grid communication links."""
    CRITICAL = auto()      # 99.999% - protection circuits
    HIGH = auto()          # 99.99% - SCADA backbone
    STANDARD = auto()      # 99.9% - normal operations
    BACKUP = auto()        # 99% - backup/emergency only
    BEST_EFFORT = auto()   # No guarantee


class LinkOwnership(Enum):
    """Ownership model for communication infrastructure."""
    UTILITY_OWNED = auto()
    LEASED = auto()
    SHARED = auto()
    PUBLIC = auto()


# Default parameters for each link type
GRID_LINK_DEFAULTS: Dict[GridLinkType, Dict[str, Any]] = {
    GridLinkType.FIBER: {
        "data_rate": "1Gbps",
        "delay": "0.1ms",
        "bit_error_rate": 1e-12,
        "reliability_class": LinkReliabilityClass.HIGH,
    },
    GridLinkType.COPPER_SERIAL: {
        "data_rate": "19200bps",
        "delay": "10ms",
        "bit_error_rate": 1e-6,
        "reliability_class": LinkReliabilityClass.STANDARD,
    },
    GridLinkType.ETHERNET_LAN: {
        "data_rate": "1Gbps",
        "delay": "0.01ms",
        "bit_error_rate": 1e-10,
        "reliability_class": LinkReliabilityClass.HIGH,
    },
    GridLinkType.MICROWAVE: {
        "data_rate": "100Mbps",
        "delay": "1ms",
        "bit_error_rate": 1e-8,
        "reliability_class": LinkReliabilityClass.HIGH,
    },
    GridLinkType.LICENSED_RADIO: {
        "data_rate": "9600bps",
        "delay": "50ms",
        "bit_error_rate": 1e-5,
        "reliability_class": LinkReliabilityClass.STANDARD,
    },
    GridLinkType.SPREAD_SPECTRUM: {
        "data_rate": "115200bps",
        "delay": "20ms",
        "bit_error_rate": 1e-6,
        "reliability_class": LinkReliabilityClass.STANDARD,
    },
    GridLinkType.CELLULAR_LTE: {
        "data_rate": "50Mbps",
        "delay": "30ms",
        "bit_error_rate": 1e-6,
        "reliability_class": LinkReliabilityClass.STANDARD,
    },
    GridLinkType.CELLULAR_5G: {
        "data_rate": "100Mbps",
        "delay": "10ms",
        "bit_error_rate": 1e-7,
        "reliability_class": LinkReliabilityClass.STANDARD,
    },
    GridLinkType.PRIVATE_LTE: {
        "data_rate": "50Mbps",
        "delay": "20ms",
        "bit_error_rate": 1e-7,
        "reliability_class": LinkReliabilityClass.HIGH,
    },
    GridLinkType.SATELLITE_GEO: {
        "data_rate": "5Mbps",
        "delay": "270ms",
        "bit_error_rate": 1e-7,
        "reliability_class": LinkReliabilityClass.BACKUP,
    },
    GridLinkType.SATELLITE_LEO: {
        "data_rate": "50Mbps",
        "delay": "20ms",
        "bit_error_rate": 1e-7,
        "reliability_class": LinkReliabilityClass.STANDARD,
    },
    GridLinkType.WIFI_MESH: {
        "data_rate": "54Mbps",
        "delay": "5ms",
        "bit_error_rate": 1e-5,
        "reliability_class": LinkReliabilityClass.BACKUP,
    },
    GridLinkType.WIMAX: {
        "data_rate": "10Mbps",
        "delay": "30ms",
        "bit_error_rate": 1e-6,
        "reliability_class": LinkReliabilityClass.STANDARD,
    },
    GridLinkType.ZIGBEE: {
        "data_rate": "250kbps",
        "delay": "10ms",
        "bit_error_rate": 1e-5,
        "reliability_class": LinkReliabilityClass.BEST_EFFORT,
    },
}


@dataclass
class WirelessParams:
    """Additional parameters for wireless links."""
    frequency_mhz: float = 900.0
    bandwidth_mhz: float = 20.0
    tx_power_dbm: float = 20.0
    rx_sensitivity_dbm: float = -90.0
    antenna_gain_dbi: float = 0.0
    propagation_model: str = "FriisPropagationLossModel"
    path_loss_exponent: float = 2.0
    fading_enabled: bool = False
    fading_model: str = "NakagamiFading"


@dataclass
class CellularParams:
    """Parameters specific to cellular (LTE/5G) links."""
    technology: str = "LTE"
    band: int = 7
    enb_tx_power_dbm: float = 43.0
    ue_tx_power_dbm: float = 23.0
    qci: int = 9
    gbr_kbps: int = 0
    mbr_kbps: int = 0
    handover_enabled: bool = False


@dataclass
class SatelliteParams:
    """Parameters specific to satellite links."""
    orbit_type: str = "GEO"
    altitude_km: float = 35786.0
    eirp_dbw: float = 50.0
    g_t_db_k: float = 25.0
    one_way_delay_ms: float = 270.0
    rain_attenuation_margin_db: float = 3.0
    availability_percent: float = 99.5


@dataclass
class GridLinkModel(LinkModel):
    """
    Extended link model for electric grid communications.
    
    Inherits from LinkModel and adds grid-specific properties.
    Can be used anywhere a LinkModel is expected.
    
    Inherited from LinkModel:
        id, channel_type, source_node_id, target_node_id,
        source_port_id, target_port_id, data_rate, delay
        
    Grid-specific attributes:
        grid_link_type: Specific type of grid communication link
        distance_km: Physical distance
        reliability_class: SLA classification
        bit_error_rate: Link BER for error modeling
        And more...
    """
    # Grid-specific type (more specific than base channel_type)
    grid_link_type: GridLinkType = GridLinkType.FIBER
    
    # Physical properties
    distance_km: float = 0.0
    
    # Type-specific parameters
    wireless_params: Optional[WirelessParams] = None
    cellular_params: Optional[CellularParams] = None
    satellite_params: Optional[SatelliteParams] = None
    
    # Error model
    bit_error_rate: float = 0.0
    packet_error_rate: float = 0.0
    burst_error_enabled: bool = False
    burst_error_rate: float = 0.0
    
    # Reliability
    reliability_class: LinkReliabilityClass = LinkReliabilityClass.STANDARD
    mtbf_hours: float = 8760.0   # Mean time between failures (1 year)
    mttr_hours: float = 4.0      # Mean time to repair
    
    # Ownership
    ownership: LinkOwnership = LinkOwnership.UTILITY_OWNED
    carrier_name: str = ""
    circuit_id: str = ""
    
    # Redundancy
    is_backup_path: bool = False
    backup_for_link_id: str = ""
    primary_link_id: str = ""
    failover_time_ms: int = 5000
    auto_failover: bool = True
    
    # Traffic engineering
    traffic_priority: int = 0
    reserved_bandwidth_bps: int = 0
    
    # Operational state
    is_up: bool = True
    
    def __post_init__(self):
        # Set base channel_type from grid_link_type
        self.channel_type = self.grid_link_type.to_base_channel_type()
        
        # Apply type-specific defaults if not already set
        defaults = GRID_LINK_DEFAULTS.get(self.grid_link_type, {})
        
        if self.data_rate == "100Mbps":  # Default from parent
            self.data_rate = defaults.get("data_rate", "100Mbps")
        if self.delay == "2ms":  # Default from parent
            self.delay = defaults.get("delay", "2ms")
        if self.bit_error_rate == 0.0:
            self.bit_error_rate = defaults.get("bit_error_rate", 0.0)
        if self.reliability_class == LinkReliabilityClass.STANDARD:
            self.reliability_class = defaults.get("reliability_class", LinkReliabilityClass.STANDARD)
        
        # Create type-specific parameter objects if needed
        if self.grid_link_type in (GridLinkType.MICROWAVE, GridLinkType.LICENSED_RADIO,
                                    GridLinkType.SPREAD_SPECTRUM, GridLinkType.WIFI_MESH):
            if self.wireless_params is None:
                self.wireless_params = WirelessParams()
        
        if self.grid_link_type in (GridLinkType.CELLULAR_LTE, GridLinkType.CELLULAR_5G,
                                    GridLinkType.PRIVATE_LTE):
            if self.cellular_params is None:
                self.cellular_params = CellularParams()
        
        if self.grid_link_type in (GridLinkType.SATELLITE_GEO, GridLinkType.SATELLITE_LEO):
            if self.satellite_params is None:
                self.satellite_params = SatelliteParams()
                if self.grid_link_type == GridLinkType.SATELLITE_LEO:
                    self.satellite_params.orbit_type = "LEO"
                    self.satellite_params.altitude_km = 550.0
                    self.satellite_params.one_way_delay_ms = 20.0
    
    @property
    def ns3_helper(self) -> str:
        return self.grid_link_type.get_ns3_helper()
    
    @property
    def is_wireless(self) -> bool:
        return self.grid_link_type in (
            GridLinkType.MICROWAVE, GridLinkType.LICENSED_RADIO,
            GridLinkType.SPREAD_SPECTRUM, GridLinkType.CELLULAR_LTE,
            GridLinkType.CELLULAR_5G, GridLinkType.PRIVATE_LTE,
            GridLinkType.SATELLITE_GEO, GridLinkType.SATELLITE_LEO,
            GridLinkType.WIFI_MESH, GridLinkType.WIMAX, GridLinkType.ZIGBEE,
        )
    
    @property
    def is_high_latency(self) -> bool:
        """Check if this is a high-latency link (>100ms one-way)."""
        return self.grid_link_type == GridLinkType.SATELLITE_GEO
    
    @property
    def availability_percent(self) -> float:
        """Calculate expected availability based on MTBF/MTTR."""
        if self.mtbf_hours <= 0:
            return 0.0
        return (self.mtbf_hours / (self.mtbf_hours + self.mttr_hours)) * 100.0
    
    def get_error_model_config(self) -> Optional[Dict[str, Any]]:
        """Get ns-3 error model configuration if BER is set."""
        if self.bit_error_rate <= 0:
            return None
        
        if self.burst_error_enabled:
            return {
                "model_type": "BurstErrorModel",
                "parameters": {
                    "ErrorRate": self.burst_error_rate,
                }
            }
        else:
            return {
                "model_type": "RateErrorModel",
                "parameters": {
                    "ErrorRate": self.bit_error_rate,
                    "ErrorUnit": "ERROR_UNIT_BIT",
                }
            }
    
    @classmethod
    def create_backup_for(
        cls,
        primary_link: 'GridLinkModel',
        backup_type: GridLinkType,
        **kwargs
    ) -> 'GridLinkModel':
        """
        Create a backup link for an existing primary link.
        
        Usage:
            primary = GridLinkModel(grid_link_type=GridLinkType.FIBER, ...)
            backup = GridLinkModel.create_backup_for(primary, GridLinkType.SATELLITE_GEO)
        
        Args:
            primary_link: The primary link to back up
            backup_type: Type for the backup link
            **kwargs: Additional attributes
            
        Returns:
            New GridLinkModel configured as backup for the primary
        """
        return cls(
            grid_link_type=backup_type,
            source_node_id=primary_link.source_node_id,
            target_node_id=primary_link.target_node_id,
            source_port_id="",  # Will need new ports
            target_port_id="",
            distance_km=primary_link.distance_km,
            is_backup_path=True,
            backup_for_link_id=primary_link.id,
            primary_link_id=primary_link.id,
            **kwargs
        )
