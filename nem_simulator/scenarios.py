"""
NSW Policy Scenario Definitions
================================
Defines three state-level policy scenarios modeling the NSW Electricity
Infrastructure Roadmap and coal retirements.
"""

import os
import pandas as pd
from typing import Dict, List, Tuple

from .generator import Generator, StorageAsset, Interconnector
from .model import NEMDispatchEngine, DispatchResult

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')

def load_generator_catalog(csv_path: str = None) -> List[Generator]:
    """Load generator specifications from CSV catalog."""
    if csv_path is None:
        csv_path = os.path.join(DATA_DIR, 'generators_nsw.csv')
    
    df = pd.read_csv(csv_path)
    generators = []
    
    for _, row in df.iterrows():
        # Exclude storage assets here (handled separately)
        if not bool(row.get('is_storage', False)):
            generators.append(Generator(
                generator_id=str(row['generator_id']),
                name=str(row['name']),
                fuel_type=str(row['fuel_type']),
                region=str(row['region']),
                capacity_mw=float(row['capacity_mw']),
                min_stable_mw=float(row.get('min_stable_mw', 0.0)),
                srmc_per_mwh=float(row['srmc_per_mwh']),
                emission_factor=float(row.get('emission_factor_t_per_mwh', 0.0)),
                ramp_rate_mw_per_min=float(row.get('ramp_rate_mw_per_min', 50.0)),
                active=True
            ))
    return generators

def load_storage_catalog(csv_path: str = None) -> List[StorageAsset]:
    """Load storage assets (BESS, PHES) from CSV catalog."""
    if csv_path is None:
        csv_path = os.path.join(DATA_DIR, 'generators_nsw.csv')
        
    df = pd.read_csv(csv_path)
    storage_assets = []
    
    for _, row in df.iterrows():
        if bool(row.get('is_storage', False)):
            cap_mw = float(row['capacity_mw'])
            cap_mwh = float(row.get('storage_capacity_mwh', cap_mw * 4.0))
            storage_assets.append(StorageAsset(
                storage_id=str(row['generator_id']),
                name=str(row['name']),
                fuel_type=str(row['fuel_type']),
                region=str(row['region']),
                max_charge_mw=cap_mw,
                max_discharge_mw=cap_mw,
                storage_capacity_mwh=cap_mwh,
                round_trip_efficiency=float(row.get('round_trip_efficiency', 0.85)),
                degradation_cost_per_mwh=float(row['srmc_per_mwh']),
                active=True
            ))
    return storage_assets

def load_trace_data(csv_path: str = None) -> pd.DataFrame:
    """Load 48 half-hour demand and renewable availability traces."""
    if csv_path is None:
        csv_path = os.path.join(DATA_DIR, 'demand_and_renewables_48hh.csv')
    return pd.read_csv(csv_path)

def load_nsw_scenario(scenario_name: str) -> Tuple[List[Generator], List[StorageAsset]]:
    """
    Configure generation and storage fleet for a target NSW policy scenario.
    
    Scenarios:
    1. 'Baseline_2024': Current operating fleet (Eraring active, existing renewables, Waratah BESS).
    2. 'Eraring_Retirement_Unfirmed': Eraring fully retired without replacement firming.
    3. 'NSW_Roadmap_2030': Eraring retired, 3 GW CWO REZ online, 8h Long-Duration Storage online.
    """
    all_gens = load_generator_catalog()
    all_storage = load_storage_catalog()
    
    scenario_name_lower = scenario_name.lower()

    if scenario_name_lower in ['baseline', 'baseline_2024']:
        # Filter out future REZ projects
        active_gens = [g for g in all_gens if not g.generator_id.startswith('CWO_REZ')]
        # Only existing storage
        active_storage = [s for s in all_storage if s.storage_id in ['SHOALHAVEN_PH', 'WARATAH_SUPER_BESS']]
        return active_gens, active_storage

    elif scenario_name_lower in ['eraring_exit', 'eraring_retirement_unfirmed']:
        # Eraring retired, NO new REZ or LDS added
        active_gens = [g for g in all_gens if g.generator_id != 'ERARING_1_4' and not g.generator_id.startswith('CWO_REZ')]
        active_storage = [s for s in all_storage if s.storage_id in ['SHOALHAVEN_PH', 'WARATAH_SUPER_BESS']]
        return active_gens, active_storage

    elif scenario_name_lower in ['nsw_roadmap', 'nsw_roadmap_2030']:
        # Eraring retired, CWO REZ Solar & Wind active, Long Duration Storage active
        active_gens = [g for g in all_gens if g.generator_id != 'ERARING_1_4']
        active_storage = all_storage # Includes Waratah, Shoalhaven, and 8h LDS Pumped Hydro
        return active_gens, active_storage

    else:
        raise ValueError(f"Unknown scenario: {scenario_name}. Choose from: 'Baseline_2024', 'Eraring_Retirement_Unfirmed', 'NSW_Roadmap_2030'.")

def get_nsw_interconnectors() -> List[Interconnector]:
    """Return standard NEM interconnectors feeding NSW."""
    return [
        Interconnector(
            interconnector_id='VNI',
            name='Victoria-NSW Interconnector (VNI)',
            from_region='VIC1',
            to_region='NSW1',
            forward_limit_mw=600.0,
            reverse_limit_mw=600.0,
            marginal_cost_per_mwh=68.00
        ),
        Interconnector(
            interconnector_id='QNI',
            name='Queensland-NSW Interconnector (QNI)',
            from_region='QLD1',
            to_region='NSW1',
            forward_limit_mw=400.0,
            reverse_limit_mw=400.0,
            marginal_cost_per_mwh=72.00
        )
    ]

def run_scenario_comparison() -> Dict[str, DispatchResult]:
    """Execute all three policy scenarios and return results dictionary."""
    traces = load_trace_data()
    demand = traces['operational_demand_mw'].tolist()
    solar_cf = traces['solar_capacity_factor'].tolist()
    wind_cf = traces['wind_capacity_factor'].tolist()

    scenario_names = [
        'Baseline_2024',
        'Eraring_Retirement_Unfirmed',
        'NSW_Roadmap_2030'
    ]

    interconnectors = get_nsw_interconnectors()

    results = {}
    for sc_name in scenario_names:
        gens, stor = load_nsw_scenario(sc_name)
        engine = NEMDispatchEngine(
            generators=gens,
            storage_assets=stor,
            interconnectors=interconnectors,
            interval_minutes=30
        )
        res = engine.solve(
            demand_trace_mw=demand,
            solar_capacity_factor=solar_cf,
            wind_capacity_factor=wind_cf,
            enforce_ramp_rates=True
        )
        results[sc_name] = res
        
    return results
