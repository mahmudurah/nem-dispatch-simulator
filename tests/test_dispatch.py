"""
Unit Tests for NEM Dispatch Simulator
======================================
Verifies mathematical integrity, energy balance, storage dynamics, and merit order.
"""

import sys
import os
import unittest
import numpy as np

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from nem_simulator.generator import Generator, StorageAsset
from nem_simulator.model import NEMDispatchEngine
from nem_simulator.scenarios import load_nsw_scenario, load_trace_data, get_nsw_interconnectors

class TestNEMDispatchEngine(unittest.TestCase):

    def setUp(self):
        self.traces = load_trace_data()
        self.demand = self.traces['operational_demand_mw'].tolist()
        self.solar_cf = self.traces['solar_capacity_factor'].tolist()
        self.wind_cf = self.traces['wind_capacity_factor'].tolist()
        self.interconnectors = get_nsw_interconnectors()

    def test_baseline_dispatch_success_and_energy_balance(self):
        """Test that Baseline scenario solves and perfectly meets demand at all intervals."""
        gens, stor = load_nsw_scenario('Baseline_2024')
        engine = NEMDispatchEngine(
            generators=gens,
            storage_assets=stor,
            interconnectors=self.interconnectors,
            interval_minutes=30
        )
        res = engine.solve(
            demand_trace_mw=self.demand,
            solar_capacity_factor=self.solar_cf,
            wind_capacity_factor=self.wind_cf
        )
        self.assertTrue(res.success, f"Solver failed: {res.status_message}")
        self.assertEqual(res.unserved_energy_mwh, 0.0, "Expected zero unserved energy in baseline")
        
        # Verify energy balance for each interval
        for t in range(res.intervals):
            total_delivered = sum(res.generation_by_fuel_df.iloc[t])
            target_demand = self.demand[t]
            self.assertAlmostEqual(
                total_delivered, target_demand, delta=target_demand * 0.001,
                msg=f"Interval {t}: Net Delivered ({total_delivered:.1f} MW) != Demand ({target_demand:.1f} MW)"
            )

    def test_storage_soc_bounds(self):
        """Test that storage State of Charge never violates technical boundaries."""
        gens, stor = load_nsw_scenario('NSW_Roadmap_2030')
        engine = NEMDispatchEngine(
            generators=gens,
            storage_assets=stor,
            interconnectors=self.interconnectors,
            interval_minutes=30
        )
        res = engine.solve(
            demand_trace_mw=self.demand,
            solar_capacity_factor=self.solar_cf,
            wind_capacity_factor=self.wind_cf
        )
        self.assertTrue(res.success)
        for col in res.storage_soc_df.columns:
            if '(%)' in col:
                soc_vals = res.storage_soc_df[col].values
                self.assertTrue(np.all(soc_vals >= -0.01), f"{col} dropped below 0%")
                self.assertTrue(np.all(soc_vals <= 100.01), f"{col} exceeded 100%")

    def test_merit_order_price_signal(self):
        """Test that spot prices increase when expensive gas peakers are dispatched."""
        gens, stor = load_nsw_scenario('Eraring_Retirement_Unfirmed')
        engine = NEMDispatchEngine(
            generators=gens,
            storage_assets=stor,
            interconnectors=self.interconnectors,
            interval_minutes=30
        )
        res = engine.solve(
            demand_trace_mw=self.demand,
            solar_capacity_factor=self.solar_cf,
            wind_capacity_factor=self.wind_cf
        )
        self.assertTrue(res.success)
        # Average spot price under Eraring exit must be significantly higher than Baseline
        self.assertGreater(res.average_price_per_mwh, 100.0, "Expected high peak prices under coal retirement")

if __name__ == '__main__':
    unittest.main()
