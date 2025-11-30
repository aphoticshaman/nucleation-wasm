"""
Correlation Analysis for Compression Dynamics

Tests H1: KL divergence correlates with conflict intensity.
Tests H2: Divergence changes PRECEDE conflict changes.

Author: Ryan J Cardwell (Archer Phoenix)
"""
import numpy as np
import pandas as pd
from scipy import stats
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass


@dataclass
class CorrelationResult:
    """Result from correlation analysis."""
    metric: str
    r: float
    p_value: float
    ci_lower: float
    ci_upper: float
    n: int
    method: str


@dataclass
class GrangerResult:
    """Result from Granger causality test."""
    direction: str  # 'divergence_causes_conflict' or 'conflict_causes_divergence'
    f_statistic: float
    p_value: float
    max_lag: int
    best_lag: int


def validate_divergence_conflict_correlation(
    divergence_data: pd.DataFrame,
    conflict_data: pd.DataFrame,
    divergence_col: str = 'phi',
    intensity_col: str = 'intensity',
    merge_on: List[str] = ['actor_a', 'actor_b', 'date'],
    method: str = 'pearson',
    n_bootstrap: int = 1000,
) -> CorrelationResult:
    """
    Test H1: KL divergence correlates with conflict intensity.

    Args:
        divergence_data: DataFrame with divergence values
        conflict_data: DataFrame with conflict intensity
        divergence_col: Column name for divergence
        intensity_col: Column name for intensity
        merge_on: Columns to merge on
        method: 'pearson' or 'spearman'
        n_bootstrap: Number of bootstrap samples for CI

    Returns:
        CorrelationResult with r, p-value, and confidence interval
    """
    # Merge datasets
    merged = pd.merge(
        conflict_data,
        divergence_data,
        on=merge_on,
        how='inner',
    )

    if len(merged) < 10:
        return CorrelationResult(
            metric=f'{divergence_col}_vs_{intensity_col}',
            r=np.nan,
            p_value=1.0,
            ci_lower=np.nan,
            ci_upper=np.nan,
            n=len(merged),
            method=method,
        )

    x = merged[divergence_col].values
    y = merged[intensity_col].values

    # Remove NaN
    mask = ~(np.isnan(x) | np.isnan(y))
    x = x[mask]
    y = y[mask]

    if len(x) < 10:
        return CorrelationResult(
            metric=f'{divergence_col}_vs_{intensity_col}',
            r=np.nan,
            p_value=1.0,
            ci_lower=np.nan,
            ci_upper=np.nan,
            n=len(x),
            method=method,
        )

    # Compute correlation
    if method == 'pearson':
        r, p = stats.pearsonr(x, y)
    else:
        r, p = stats.spearmanr(x, y)

    # Bootstrap confidence interval
    bootstrap_r = []
    for _ in range(n_bootstrap):
        indices = np.random.choice(len(x), size=len(x), replace=True)
        if method == 'pearson':
            boot_r, _ = stats.pearsonr(x[indices], y[indices])
        else:
            boot_r, _ = stats.spearmanr(x[indices], y[indices])
        bootstrap_r.append(boot_r)

    ci_lower = np.percentile(bootstrap_r, 2.5)
    ci_upper = np.percentile(bootstrap_r, 97.5)

    return CorrelationResult(
        metric=f'{divergence_col}_vs_{intensity_col}',
        r=r,
        p_value=p,
        ci_lower=ci_lower,
        ci_upper=ci_upper,
        n=len(x),
        method=method,
    )


def compute_lagged_correlations(
    divergence_series: pd.DataFrame,
    conflict_series: pd.DataFrame,
    divergence_col: str = 'phi',
    intensity_col: str = 'intensity',
    max_lag: int = 90,
    lag_step: int = 7,
) -> pd.DataFrame:
    """
    Compute cross-correlations at various lags.

    Tests H2: Does divergence LEAD conflict?

    Positive lag = divergence leads conflict (causal direction)
    Negative lag = conflict leads divergence (reverse causality)

    Args:
        divergence_series: Time series of divergence
        conflict_series: Time series of conflict intensity
        divergence_col: Column for divergence values
        intensity_col: Column for intensity values
        max_lag: Maximum lag in days
        lag_step: Step size for lags

    Returns:
        DataFrame with lag, correlation, p-value columns
    """
    # Align series by date
    if 'date' in divergence_series.columns:
        div_ts = divergence_series.set_index('date')[divergence_col].sort_index()
    else:
        div_ts = divergence_series[divergence_col]

    if 'date' in conflict_series.columns:
        conf_ts = conflict_series.set_index('date')[intensity_col].sort_index()
    else:
        conf_ts = conflict_series[intensity_col]

    # Align
    common_idx = div_ts.index.intersection(conf_ts.index)
    if len(common_idx) < 20:
        return pd.DataFrame()

    div_ts = div_ts.loc[common_idx]
    conf_ts = conf_ts.loc[common_idx]

    results = []
    lags = range(-max_lag, max_lag + 1, lag_step)

    for lag in lags:
        if lag > 0:
            # Positive lag: divergence leads conflict
            div_shifted = div_ts.shift(lag)
        elif lag < 0:
            # Negative lag: conflict leads divergence
            div_shifted = div_ts.shift(lag)
        else:
            div_shifted = div_ts

        # Remove NaN from shift
        mask = ~(div_shifted.isna() | conf_ts.isna())
        if mask.sum() < 10:
            continue

        r, p = stats.pearsonr(
            div_shifted[mask].values,
            conf_ts[mask].values,
        )

        results.append({
            'lag_days': lag,
            'correlation': r,
            'p_value': p,
            'n': mask.sum(),
            'interpretation': (
                'divergence_leads' if lag > 0 else
                'conflict_leads' if lag < 0 else
                'contemporaneous'
            ),
        })

    return pd.DataFrame(results)


def granger_causality_test(
    divergence_series: np.ndarray,
    conflict_series: np.ndarray,
    max_lag: int = 12,
) -> Dict[str, GrangerResult]:
    """
    Granger causality test for temporal precedence.

    Tests whether past values of divergence help predict conflict
    (and vice versa).

    Args:
        divergence_series: Time series of divergence values
        conflict_series: Time series of conflict intensity
        max_lag: Maximum lag to test

    Returns:
        Dict with results for both directions
    """
    try:
        from statsmodels.tsa.stattools import grangercausalitytests
    except ImportError:
        # Return placeholder if statsmodels not available
        return {
            'divergence_causes_conflict': GrangerResult(
                direction='divergence_causes_conflict',
                f_statistic=np.nan,
                p_value=1.0,
                max_lag=max_lag,
                best_lag=1,
            ),
            'conflict_causes_divergence': GrangerResult(
                direction='conflict_causes_divergence',
                f_statistic=np.nan,
                p_value=1.0,
                max_lag=max_lag,
                best_lag=1,
            ),
        }

    # Remove NaN
    mask = ~(np.isnan(divergence_series) | np.isnan(conflict_series))
    div = divergence_series[mask]
    conf = conflict_series[mask]

    if len(div) < max_lag * 3:
        return {
            'divergence_causes_conflict': GrangerResult(
                direction='divergence_causes_conflict',
                f_statistic=np.nan,
                p_value=1.0,
                max_lag=max_lag,
                best_lag=1,
            ),
            'conflict_causes_divergence': GrangerResult(
                direction='conflict_causes_divergence',
                f_statistic=np.nan,
                p_value=1.0,
                max_lag=max_lag,
                best_lag=1,
            ),
        }

    results = {}

    # Test: does divergence Granger-cause conflict?
    try:
        data = np.column_stack([conf, div])
        gc_results = grangercausalitytests(data, maxlag=max_lag, verbose=False)

        # Find best lag (lowest p-value)
        best_lag = 1
        best_p = 1.0
        best_f = 0.0
        for lag in range(1, max_lag + 1):
            f_stat = gc_results[lag][0]['ssr_ftest'][0]
            p_val = gc_results[lag][0]['ssr_ftest'][1]
            if p_val < best_p:
                best_p = p_val
                best_f = f_stat
                best_lag = lag

        results['divergence_causes_conflict'] = GrangerResult(
            direction='divergence_causes_conflict',
            f_statistic=best_f,
            p_value=best_p,
            max_lag=max_lag,
            best_lag=best_lag,
        )
    except Exception:
        results['divergence_causes_conflict'] = GrangerResult(
            direction='divergence_causes_conflict',
            f_statistic=np.nan,
            p_value=1.0,
            max_lag=max_lag,
            best_lag=1,
        )

    # Test: does conflict Granger-cause divergence?
    try:
        data = np.column_stack([div, conf])
        gc_results = grangercausalitytests(data, maxlag=max_lag, verbose=False)

        best_lag = 1
        best_p = 1.0
        best_f = 0.0
        for lag in range(1, max_lag + 1):
            f_stat = gc_results[lag][0]['ssr_ftest'][0]
            p_val = gc_results[lag][0]['ssr_ftest'][1]
            if p_val < best_p:
                best_p = p_val
                best_f = f_stat
                best_lag = lag

        results['conflict_causes_divergence'] = GrangerResult(
            direction='conflict_causes_divergence',
            f_statistic=best_f,
            p_value=best_p,
            max_lag=max_lag,
            best_lag=best_lag,
        )
    except Exception:
        results['conflict_causes_divergence'] = GrangerResult(
            direction='conflict_causes_divergence',
            f_statistic=np.nan,
            p_value=1.0,
            max_lag=max_lag,
            best_lag=1,
        )

    return results


def compute_partial_correlations(
    data: pd.DataFrame,
    x_col: str,
    y_col: str,
    control_cols: List[str],
) -> Tuple[float, float]:
    """
    Compute partial correlation controlling for confounders.

    Args:
        data: DataFrame with all variables
        x_col: First variable
        y_col: Second variable
        control_cols: Variables to control for

    Returns:
        Tuple of (partial_r, p_value)
    """
    from scipy.stats import pearsonr

    # Simple implementation: residualize both variables
    if not control_cols:
        return pearsonr(data[x_col], data[y_col])

    # Residualize x
    X_control = data[control_cols].values
    X_control = np.column_stack([np.ones(len(X_control)), X_control])
    x_vals = data[x_col].values

    try:
        beta_x = np.linalg.lstsq(X_control, x_vals, rcond=None)[0]
        x_residuals = x_vals - X_control @ beta_x
    except:
        x_residuals = x_vals

    # Residualize y
    y_vals = data[y_col].values
    try:
        beta_y = np.linalg.lstsq(X_control, y_vals, rcond=None)[0]
        y_residuals = y_vals - X_control @ beta_y
    except:
        y_residuals = y_vals

    return pearsonr(x_residuals, y_residuals)


if __name__ == "__main__":
    print("Testing Correlation Analysis...")
    print("=" * 70)

    # Create synthetic data
    np.random.seed(42)
    n = 200

    # Divergence (cause)
    divergence = np.random.randn(n).cumsum() * 0.1
    divergence = (divergence - divergence.min()) / (divergence.max() - divergence.min())

    # Conflict (effect) - divergence leads by ~10 steps
    noise = np.random.randn(n) * 0.2
    conflict = np.zeros(n)
    for i in range(10, n):
        conflict[i] = 0.3 * divergence[i-10] + 0.5 * conflict[i-1] + noise[i]
    conflict = (conflict - conflict.min()) / (conflict.max() - conflict.min() + 1e-10)

    dates = pd.date_range('2020-01-01', periods=n, freq='D')

    div_df = pd.DataFrame({
        'date': dates,
        'actor_a': 'USA',
        'actor_b': 'RUS',
        'phi': divergence,
    })

    conf_df = pd.DataFrame({
        'date': dates,
        'actor_a': 'USA',
        'actor_b': 'RUS',
        'intensity': conflict,
    })

    # Test correlation
    result = validate_divergence_conflict_correlation(div_df, conf_df)
    print(f"\nCorrelation (contemporaneous):")
    print(f"  r = {result.r:.3f} [{result.ci_lower:.3f}, {result.ci_upper:.3f}]")
    print(f"  p = {result.p_value:.4f}")
    print(f"  n = {result.n}")

    # Test lagged correlations
    lagged = compute_lagged_correlations(div_df, conf_df, max_lag=30, lag_step=5)
    print(f"\nLagged correlations:")
    if not lagged.empty:
        best_lag = lagged.loc[lagged['correlation'].abs().idxmax()]
        print(f"  Best lag: {best_lag['lag_days']} days (r = {best_lag['correlation']:.3f})")
        print(f"  Interpretation: {best_lag['interpretation']}")

    # Test Granger causality
    granger = granger_causality_test(divergence, conflict, max_lag=15)
    print(f"\nGranger causality:")
    for direction, result in granger.items():
        print(f"  {direction}:")
        print(f"    F = {result.f_statistic:.2f}, p = {result.p_value:.4f}")
        print(f"    Best lag = {result.best_lag}")

    print("\n" + "=" * 70)
