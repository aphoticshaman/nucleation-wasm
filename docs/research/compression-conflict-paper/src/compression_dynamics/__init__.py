"""
Compression Dynamics Module

Core implementation of compression schemes and conflict potential calculations.
"""
from .schemes import (
    CompressionScheme,
    ConflictPotential,
    Grievance,
    CompressionDynamicsModel,
    SchemeSource,
    compute_dyad_divergence_timeseries,
)

from .text_extractor import (
    TextCompressionExtractor,
    LDACompressionExtractor,
    create_text_extractor,
)

from .event_extractor import (
    EventCompressionExtractor,
    GoldsteinCompressionExtractor,
    HybridCompressionExtractor,
)

__all__ = [
    # Core schemes
    "CompressionScheme",
    "ConflictPotential",
    "Grievance",
    "CompressionDynamicsModel",
    "SchemeSource",
    "compute_dyad_divergence_timeseries",
    # Text extractors
    "TextCompressionExtractor",
    "LDACompressionExtractor",
    "create_text_extractor",
    # Event extractors
    "EventCompressionExtractor",
    "GoldsteinCompressionExtractor",
    "HybridCompressionExtractor",
]
