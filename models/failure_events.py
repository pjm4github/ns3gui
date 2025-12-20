"""
Failure Event and Scenario Models.

Defines failure events for grid resilience testing including link failures,
node outages, degradation, and network partitions.
"""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional, List, Dict, Any
import uuid
from datetime import datetime


class FailureEventType(Enum):
    """Types of failure events that can be injected into the simulation."""
    # Link Failures
    LINK_DOWN = auto()
    LINK_UP = auto()
    LINK_DEGRADED = auto()
    LINK_RESTORED = auto()
    LINK_FLAPPING = auto()
    LINK_CONGESTION = auto()
    LINK_ERROR_RATE = auto()
    
    # Node Failures
    NODE_POWER_LOSS = auto()
    NODE_POWER_RESTORE = auto()
    NODE_REBOOT = auto()
    NODE_CPU_OVERLOAD = auto()
    NODE_MEMORY_EXHAUSTION = auto()
    NODE_INTERFACE_DOWN = auto()
    NODE_INTERFACE_UP = auto()
    
    # Network-wide
    PARTITION = auto()
    PARTITION_HEAL = auto()
    BROADCAST_STORM = auto()
    ROUTING_FAILURE = auto()
    ROUTING_CONVERGENCE = auto()
    
    # Cyber Events
    DOS_FLOOD = auto()
    DOS_SLOWLORIS = auto()
    MITM_DELAY = auto()
    MITM_DROP = auto()
    PACKET_REPLAY = auto()
    PACKET_INJECTION = auto()
    
    # Environmental
    WEATHER_INTERFERENCE = auto()
    SOLAR_FLARE = auto()
    PHYSICAL_DAMAGE = auto()
    
    # Scheduled Maintenance
    PLANNED_OUTAGE = auto()
    FAILOVER_TEST = auto()


class FailureEventState(Enum):
    """Lifecycle state of a failure event."""
    SCHEDULED = auto()
    PENDING = auto()
    ACTIVE = auto()
    RECOVERING = auto()
    RECOVERED = auto()
    CANCELLED = auto()
    FAILED = auto()


class FailureSeverity(Enum):
    """Severity classification for failure events."""
    CRITICAL = 1
    MAJOR = 2
    MINOR = 3
    WARNING = 4
    INFO = 5


class FailureCategory(Enum):
    """Category for organizing failure scenarios."""
    EQUIPMENT = auto()
    NATURAL = auto()
    CYBER = auto()
    HUMAN = auto()
    MAINTENANCE = auto()
    CASCADING = auto()
    UNKNOWN = auto()


@dataclass
class FailureEventParameters:
    """Parameters that modify how a failure event behaves."""
    # Link Degradation
    new_data_rate: str = ""
    new_delay: str = ""
    new_jitter: str = ""
    error_rate: float = 0.0
    
    # Flapping
    up_duration_s: float = 5.0
    down_duration_s: float = 2.0
    flap_cycles: int = 3
    
    # Congestion
    queue_fill_percent: int = 95
    drop_probability: float = 0.1
    
    # Node Reboot
    reboot_duration_s: float = 30.0
    boot_sequence_delay_s: float = 5.0
    
    # Partition
    group_a_node_ids: List[str] = field(default_factory=list)
    group_b_node_ids: List[str] = field(default_factory=list)
    partition_links: List[str] = field(default_factory=list)
    
    # DoS
    flood_rate_pps: int = 10000
    flood_packet_size: int = 64
    target_port: int = 0
    
    # MITM
    added_delay_ms: float = 50.0
    drop_probability_mitm: float = 0.1
    affected_traffic_class: str = ""
    
    # Weather/Environmental
    interference_db: float = 10.0
    affected_link_types: List[str] = field(default_factory=list)
    
    # Generic
    custom_attributes: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        result = {}
        for key, value in self.__dict__.items():
            if value and value != [] and value != {}:
                result[key] = value
        return result


@dataclass
class FailureEvent:
    """A single failure event to be injected into the simulation."""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = ""
    description: str = ""
    event_type: FailureEventType = FailureEventType.LINK_DOWN
    severity: FailureSeverity = FailureSeverity.MAJOR
    
    # Timing
    trigger_time_s: float = 0.0
    duration_s: float = -1.0
    recovery_time_s: float = -1.0
    
    # Target specification
    target_type: str = "link"
    target_id: str = ""
    target_ids: List[str] = field(default_factory=list)
    target_interface: int = -1
    
    # Parameters
    parameters: FailureEventParameters = field(default_factory=FailureEventParameters)
    
    # State tracking
    state: FailureEventState = FailureEventState.SCHEDULED
    actual_trigger_time: float = 0.0
    actual_recovery_time: float = 0.0
    error_message: str = ""
    
    # Cascading relationships
    causes_events: List[str] = field(default_factory=list)
    caused_by_event: str = ""
    depends_on_events: List[str] = field(default_factory=list)
    
    # Probability
    probability: float = 1.0
    
    # Tags
    tags: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        if not self.name:
            self.name = f"{self.event_type.name.lower()}_{self.id[:4]}"
        
        if not self.target_type:
            if self.event_type.name.startswith("LINK_"):
                self.target_type = "link"
            elif self.event_type.name.startswith("NODE_"):
                self.target_type = "node"
            else:
                self.target_type = "network"
    
    @property
    def is_active(self) -> bool:
        return self.state == FailureEventState.ACTIVE
    
    @property
    def is_scheduled(self) -> bool:
        return self.state == FailureEventState.SCHEDULED
    
    @property
    def is_completed(self) -> bool:
        return self.state in (FailureEventState.RECOVERED, FailureEventState.CANCELLED)
    
    @property
    def has_duration(self) -> bool:
        return self.duration_s > 0 or self.recovery_time_s > 0
    
    @property
    def effective_recovery_time(self) -> float:
        if self.recovery_time_s > 0:
            return self.recovery_time_s
        elif self.duration_s > 0:
            return self.trigger_time_s + self.duration_s
        else:
            return -1.0
    
    @property
    def is_cascading_root(self) -> bool:
        return len(self.causes_events) > 0 and not self.caused_by_event
    
    @property
    def is_cascading_effect(self) -> bool:
        return bool(self.caused_by_event)
    
    def get_all_targets(self) -> List[str]:
        targets = []
        if self.target_id:
            targets.append(self.target_id)
        targets.extend(self.target_ids)
        return list(set(targets))
    
    def can_trigger_at(self, sim_time: float) -> bool:
        if self.state != FailureEventState.SCHEDULED:
            return False
        return self.trigger_time_s <= sim_time
    
    def should_recover_at(self, sim_time: float) -> bool:
        if self.state != FailureEventState.ACTIVE:
            return False
        recovery = self.effective_recovery_time
        return recovery > 0 and recovery <= sim_time


@dataclass
class CascadingFailureRule:
    """Rule for automatically generating cascading failures."""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = ""
    
    trigger_event_types: List[FailureEventType] = field(default_factory=list)
    trigger_target_patterns: List[str] = field(default_factory=list)
    
    generated_event_type: FailureEventType = FailureEventType.LINK_DOWN
    delay_s: float = 0.0
    delay_random_s: float = 0.0
    probability: float = 1.0
    
    target_selection: str = "adjacent"
    target_count: int = 1
    
    generated_parameters: FailureEventParameters = field(default_factory=FailureEventParameters)
    generated_duration_s: float = -1.0
    
    enabled: bool = True


@dataclass
class FailureScenario:
    """A collection of failure events forming a complete test scenario."""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = "Unnamed Scenario"
    description: str = ""
    
    events: List[FailureEvent] = field(default_factory=list)
    cascading_rules: List[CascadingFailureRule] = field(default_factory=list)
    
    category: FailureCategory = FailureCategory.EQUIPMENT
    severity: FailureSeverity = FailureSeverity.MAJOR
    probability: str = ""
    nerc_category: str = ""
    
    tags: List[str] = field(default_factory=list)
    
    enabled: bool = True
    repeat_count: int = 1
    random_seed: int = 0
    
    time_offset_s: float = 0.0
    time_scale: float = 1.0
    
    version: int = 1
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    modified_at: str = field(default_factory=lambda: datetime.now().isoformat())
    author: str = ""
    
    def add_event(self, event: FailureEvent) -> None:
        self.events.append(event)
        self.events.sort(key=lambda e: e.trigger_time_s)
        self.modified_at = datetime.now().isoformat()
    
    def remove_event(self, event_id: str) -> Optional[FailureEvent]:
        for i, event in enumerate(self.events):
            if event.id == event_id:
                self.modified_at = datetime.now().isoformat()
                return self.events.pop(i)
        return None
    
    def get_event(self, event_id: str) -> Optional[FailureEvent]:
        for event in self.events:
            if event.id == event_id:
                return event
        return None
    
    def get_events_at_time(self, time_s: float, tolerance: float = 0.001) -> List[FailureEvent]:
        return [e for e in self.events if abs(e.trigger_time_s - time_s) < tolerance]
    
    def get_events_in_range(self, start_s: float, end_s: float) -> List[FailureEvent]:
        return [e for e in self.events if start_s <= e.trigger_time_s <= end_s]
    
    def get_active_events_at_time(self, time_s: float) -> List[FailureEvent]:
        active = []
        for e in self.events:
            if e.trigger_time_s <= time_s:
                recovery = e.effective_recovery_time
                if recovery < 0 or recovery > time_s:
                    active.append(e)
        return active
    
    def get_events_by_type(self, event_type: FailureEventType) -> List[FailureEvent]:
        return [e for e in self.events if e.event_type == event_type]
    
    def get_events_by_target(self, target_id: str) -> List[FailureEvent]:
        return [e for e in self.events if target_id in e.get_all_targets()]
    
    @property
    def duration_s(self) -> float:
        if not self.events:
            return 0.0
        max_time = 0.0
        for e in self.events:
            end_time = e.effective_recovery_time
            if end_time < 0:
                end_time = e.trigger_time_s
            max_time = max(max_time, end_time)
        return max_time
    
    @property
    def event_count(self) -> int:
        return len(self.events)
    
    @property
    def unique_targets(self) -> List[str]:
        targets = set()
        for e in self.events:
            targets.update(e.get_all_targets())
        return list(targets)
    
    @property
    def has_cascading(self) -> bool:
        return any(e.is_cascading_root or e.is_cascading_effect for e in self.events)
    
    def reset_event_states(self) -> None:
        for event in self.events:
            event.state = FailureEventState.SCHEDULED
            event.actual_trigger_time = 0.0
            event.actual_recovery_time = 0.0
            event.error_message = ""
    
    def clone(self) -> 'FailureScenario':
        import copy
        new_scenario = copy.deepcopy(self)
        new_scenario.id = str(uuid.uuid4())[:8]
        new_scenario.name = f"{self.name} (copy)"
        new_scenario.created_at = datetime.now().isoformat()
        new_scenario.modified_at = datetime.now().isoformat()
        return new_scenario


# ===== Factory Functions =====

def create_single_link_failure(
    link_id: str,
    trigger_time_s: float = 10.0,
    duration_s: float = 30.0,
    name: str = ""
) -> FailureScenario:
    scenario = FailureScenario(
        name=name or f"Single Link Failure - {link_id}",
        description="Tests system response to a single link failure",
        category=FailureCategory.EQUIPMENT,
        severity=FailureSeverity.MINOR,
    )
    scenario.add_event(FailureEvent(
        name=f"link_down_{link_id}",
        event_type=FailureEventType.LINK_DOWN,
        target_type="link",
        target_id=link_id,
        trigger_time_s=trigger_time_s,
        duration_s=duration_s,
    ))
    return scenario


def create_node_power_loss(
    node_id: str,
    trigger_time_s: float = 10.0,
    duration_s: float = 60.0,
    name: str = ""
) -> FailureScenario:
    scenario = FailureScenario(
        name=name or f"Node Power Loss - {node_id}",
        description="Tests system response to complete node failure",
        category=FailureCategory.EQUIPMENT,
        severity=FailureSeverity.MAJOR,
    )
    scenario.add_event(FailureEvent(
        name=f"power_loss_{node_id}",
        event_type=FailureEventType.NODE_POWER_LOSS,
        target_type="node",
        target_id=node_id,
        trigger_time_s=trigger_time_s,
        duration_s=duration_s,
    ))
    return scenario


def create_cascading_failure(
    initial_link_id: str,
    affected_node_ids: List[str],
    trigger_time_s: float = 10.0,
    cascade_delay_s: float = 5.0,
    name: str = ""
) -> FailureScenario:
    scenario = FailureScenario(
        name=name or "Cascading Failure",
        description="Initial failure cascades to affect multiple components",
        category=FailureCategory.CASCADING,
        severity=FailureSeverity.CRITICAL,
    )
    
    initial_event = FailureEvent(
        name=f"initial_failure_{initial_link_id}",
        event_type=FailureEventType.LINK_DOWN,
        target_type="link",
        target_id=initial_link_id,
        trigger_time_s=trigger_time_s,
        duration_s=-1,
    )
    scenario.add_event(initial_event)
    
    for i, node_id in enumerate(affected_node_ids):
        cascade_event = FailureEvent(
            name=f"cascade_{node_id}",
            event_type=FailureEventType.NODE_POWER_LOSS,
            target_type="node",
            target_id=node_id,
            trigger_time_s=trigger_time_s + cascade_delay_s * (i + 1),
            duration_s=-1,
            caused_by_event=initial_event.id,
        )
        initial_event.causes_events.append(cascade_event.id)
        scenario.add_event(cascade_event)
    
    return scenario


def create_network_partition(
    group_a_ids: List[str],
    group_b_ids: List[str],
    partition_link_ids: List[str],
    trigger_time_s: float = 10.0,
    duration_s: float = 60.0,
    name: str = ""
) -> FailureScenario:
    scenario = FailureScenario(
        name=name or "Network Partition",
        description="Network splits into isolated segments",
        category=FailureCategory.EQUIPMENT,
        severity=FailureSeverity.CRITICAL,
    )
    
    params = FailureEventParameters(
        group_a_node_ids=group_a_ids,
        group_b_node_ids=group_b_ids,
        partition_links=partition_link_ids,
    )
    
    scenario.add_event(FailureEvent(
        name="partition",
        event_type=FailureEventType.PARTITION,
        target_type="network",
        target_ids=partition_link_ids,
        trigger_time_s=trigger_time_s,
        duration_s=duration_s,
        parameters=params,
    ))
    
    return scenario


def create_control_center_failover(
    primary_cc_id: str,
    backup_cc_id: str,
    trigger_time_s: float = 10.0,
    outage_duration_s: float = 120.0,
    name: str = ""
) -> FailureScenario:
    scenario = FailureScenario(
        name=name or "Control Center Failover",
        description="Primary control center fails, testing backup takeover",
        category=FailureCategory.EQUIPMENT,
        severity=FailureSeverity.CRITICAL,
        tags=["failover", "redundancy", "control_center"],
    )
    
    scenario.add_event(FailureEvent(
        name=f"cc_failure_{primary_cc_id}",
        event_type=FailureEventType.NODE_POWER_LOSS,
        target_type="node",
        target_id=primary_cc_id,
        trigger_time_s=trigger_time_s,
        duration_s=outage_duration_s,
        severity=FailureSeverity.CRITICAL,
    ))
    
    return scenario


def create_dos_attack(
    target_id: str,
    trigger_time_s: float = 10.0,
    duration_s: float = 30.0,
    flood_rate_pps: int = 10000,
    name: str = ""
) -> FailureScenario:
    scenario = FailureScenario(
        name=name or f"DoS Attack on {target_id}",
        description="Denial of service attack via packet flooding",
        category=FailureCategory.CYBER,
        severity=FailureSeverity.CRITICAL,
        tags=["cyber", "dos", "security"],
    )
    
    params = FailureEventParameters(
        flood_rate_pps=flood_rate_pps,
        flood_packet_size=64,
    )
    
    scenario.add_event(FailureEvent(
        name=f"dos_{target_id}",
        event_type=FailureEventType.DOS_FLOOD,
        target_type="node",
        target_id=target_id,
        trigger_time_s=trigger_time_s,
        duration_s=duration_s,
        parameters=params,
        severity=FailureSeverity.CRITICAL,
    ))
    
    return scenario


# Predefined scenario templates
SCENARIO_TEMPLATES = {
    "single_link_failure": {
        "name": "Single Link Failure",
        "factory": create_single_link_failure,
        "category": FailureCategory.EQUIPMENT,
    },
    "node_power_loss": {
        "name": "Node Power Loss",
        "factory": create_node_power_loss,
        "category": FailureCategory.EQUIPMENT,
    },
    "cascading_failure": {
        "name": "Cascading Failure",
        "factory": create_cascading_failure,
        "category": FailureCategory.CASCADING,
    },
    "network_partition": {
        "name": "Network Partition",
        "factory": create_network_partition,
        "category": FailureCategory.EQUIPMENT,
    },
    "cc_failover": {
        "name": "Control Center Failover",
        "factory": create_control_center_failover,
        "category": FailureCategory.EQUIPMENT,
    },
    "dos_attack": {
        "name": "DoS Attack",
        "factory": create_dos_attack,
        "category": FailureCategory.CYBER,
    },
}
