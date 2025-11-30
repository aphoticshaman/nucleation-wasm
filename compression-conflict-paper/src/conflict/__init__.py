"""
Conflict Data Module

Integration with GDELT, ACLED, and UCDP conflict datasets.
"""
from .gdelt_client import GDELTClient, fetch_gdelt_events, aggregate_dyad_intensity
from .ucdp_loader import UCDPLoader, load_ucdp_conflicts

__all__ = [
    "GDELTClient",
    "fetch_gdelt_events",
    "aggregate_dyad_intensity",
    "UCDPLoader",
    "load_ucdp_conflicts",
]
