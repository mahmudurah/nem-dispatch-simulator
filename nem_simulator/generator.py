"""
Asset Data Structures for NEM Generation, Storage & Interconnectors
===================================================================
Defines strongly-typed representations of physical power system assets
adhering to AEMO NEM MMS and PLEXOS parameter conventions.
"""

from dataclasses import dataclass
from typing import Optional

@dataclass
class Generator:
    """
    Thermal, Hydro, or Renewable Generation Asset.
    """
    generator_id: str
    name: str
    fuel_type: str                  # 'Black Coal', 'Gas CCGT', 'Gas OCGT', 'Solar', 'Wind', etc.
    region: str                     # e.g., 'NSW1', 'VIC1', 'QLD1'
    capacity_mw: float              # Nameplate capacity (MW)
    min_stable_mw: float = 0.0      # Minimum stable technical generation level (MW)
    srmc_per_mwh: float = 0.0       # Short-Run Marginal Cost ($/MWh) including fuel + variable O&M
    emission_factor: float = 0.0    # Carbon intensity factor (tCO2-e / MWh)
    ramp_rate_mw_per_min: float = 50.0 # Maximum allowable ramp rate (MW/min)
    forced_outage_rate: float = 0.0 # Expected forced outage probability (0.0 - 1.0)
    planned_outage: bool = False    # True if unit is on scheduled maintenance
    active: bool = True             # True if unit is in service

    def available_capacity(self, capacity_factor: float = 1.0) -> float:
        """Calculate effective available capacity for a specific interval."""
        if not self.active or self.planned_outage:
            return 0.0
        return self.capacity_mw * max(0.0, min(1.0, capacity_factor))


@dataclass
class StorageAsset:
    """
    Energy Storage Asset (Battery BESS or Pumped Hydro Energy Storage PHES).
    """
    storage_id: str
    name: str
    fuel_type: str                  # 'Battery BESS' or 'Pumped Hydro'
    region: str
    max_charge_mw: float            # Maximum charging power capacity (MW)
    max_discharge_mw: float         # Maximum discharging power capacity (MW)
    storage_capacity_mwh: float     # Usable energy storage capacity (MWh)
    round_trip_efficiency: float    # AC-to-AC round-trip efficiency (e.g. 0.88 for BESS, 0.76 for PHES)
    degradation_cost_per_mwh: float = 5.0 # Battery cycle degradation / water pumping variable cost ($/MWh)
    min_soc_mwh: float = 0.0        # Minimum allowable State of Charge (reserve/buffer)
    initial_soc_mwh: Optional[float] = None # Starting State of Charge at t=0
    active: bool = True

    def __post_init__(self):
        if self.initial_soc_mwh is None:
            self.initial_soc_mwh = self.storage_capacity_mwh * 0.50 # Default 50% SoC


@dataclass
class Interconnector:
    """
    High-Voltage Regional Interconnector (e.g. VNI, QNI).
    """
    interconnector_id: str
    name: str
    from_region: str
    to_region: str
    forward_limit_mw: float         # Export limit (MW)
    reverse_limit_mw: float         # Import limit (MW)
    loss_factor: float = 0.03       # Marginal loss penalty (e.g. 3%)
    marginal_cost_per_mwh: float = 5.0 # Wheeling charge / price differential floor
