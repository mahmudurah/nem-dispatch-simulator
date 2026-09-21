"""
NEM Dispatch Simulator
======================
An open-source National Electricity Market (NEM) Economic Dispatch & Unit Commitment
simulation engine in Python. Formulates linear programming (LP/MILP) dispatch,
battery energy storage (BESS) state-of-charge cycling, transmission interconnector limits,
and NSW Electricity Infrastructure Roadmap policy scenarios.

Author: Dr. Md Mahmudur Rahman (PhD)
Repository: https://github.com/mahmudurah/nem-dispatch-simulator
"""

__version__ = "1.0.0"
__author__ = "Dr. Md Mahmudur Rahman"

from .generator import Generator, StorageAsset, Interconnector
from .model import NEMDispatchEngine, DispatchResult
from .scenarios import load_nsw_scenario, run_scenario_comparison
