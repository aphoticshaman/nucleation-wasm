"""
Validation Module

Statistical validation of the compression dynamics framework.
"""
from .correlation import (
    validate_divergence_conflict_correlation,
    compute_lagged_correlations,
    granger_causality_test,
)

from .prediction import (
    validate_escalation_prediction,
    evaluate_prediction_performance,
    compute_roc_auc,
)

from .baselines import (
    compare_to_baselines,
    compute_gdp_baseline,
    compute_distance_baseline,
)

__all__ = [
    "validate_divergence_conflict_correlation",
    "compute_lagged_correlations",
    "granger_causality_test",
    "validate_escalation_prediction",
    "evaluate_prediction_performance",
    "compute_roc_auc",
    "compare_to_baselines",
    "compute_gdp_baseline",
    "compute_distance_baseline",
]
