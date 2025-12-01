"""
Baseline Models for Comparison

Compares compression divergence to traditional conflict predictors.

Author: Ryan J Cardwell (Archer Phoenix)
"""
import numpy as np
import pandas as pd
from typing import Dict, List, Optional
from dataclasses import dataclass
from sklearn.metrics import roc_auc_score


@dataclass
class BaselineResult:
    """Result from baseline model."""
    name: str
    auc: float
    feature_importance: Optional[float] = None
    description: str = ""


def compute_gdp_baseline(
    dyad_data: pd.DataFrame,
    gdp_data: pd.DataFrame,
    actor_col_a: str = 'actor_a',
    actor_col_b: str = 'actor_b',
    gdp_col: str = 'gdp_per_capita',
    outcome_col: str = 'escalation',
) -> BaselineResult:
    """
    GDP difference as conflict predictor.

    Economic disparity is a traditional predictor of conflict.

    Args:
        dyad_data: Dyad-level data with escalation outcomes
        gdp_data: GDP data by actor
        actor_col_a: Column for first actor
        actor_col_b: Column for second actor
        gdp_col: Column for GDP values
        outcome_col: Column for escalation outcome

    Returns:
        BaselineResult with AUC
    """
    # Merge GDP data for both actors
    merged = dyad_data.copy()

    # GDP for actor A
    gdp_a = gdp_data.rename(columns={
        'actor': actor_col_a,
        gdp_col: 'gdp_a',
    })
    merged = merged.merge(gdp_a[[actor_col_a, 'gdp_a']], on=actor_col_a, how='left')

    # GDP for actor B
    gdp_b = gdp_data.rename(columns={
        'actor': actor_col_b,
        gdp_col: 'gdp_b',
    })
    merged = merged.merge(gdp_b[[actor_col_b, 'gdp_b']], on=actor_col_b, how='left')

    # GDP difference (log ratio)
    merged['gdp_diff'] = np.abs(np.log(merged['gdp_a'] / merged['gdp_b'] + 1e-10))

    # Remove missing
    valid = merged.dropna(subset=['gdp_diff', outcome_col])

    if len(valid) < 10 or valid[outcome_col].nunique() < 2:
        return BaselineResult(
            name='gdp_difference',
            auc=0.5,
            description='GDP per capita difference (log ratio)',
        )

    try:
        auc = roc_auc_score(valid[outcome_col], valid['gdp_diff'])
    except ValueError:
        auc = 0.5

    return BaselineResult(
        name='gdp_difference',
        auc=auc,
        description='GDP per capita difference (log ratio)',
    )


def compute_distance_baseline(
    dyad_data: pd.DataFrame,
    distance_data: pd.DataFrame,
    outcome_col: str = 'escalation',
) -> BaselineResult:
    """
    Geographic distance as conflict predictor.

    Contiguity is a strong predictor of interstate conflict.

    Args:
        dyad_data: Dyad-level data
        distance_data: Distance between actors
        outcome_col: Escalation outcome column

    Returns:
        BaselineResult with AUC
    """
    merged = dyad_data.merge(
        distance_data,
        on=['actor_a', 'actor_b'],
        how='left',
    )

    valid = merged.dropna(subset=['distance', outcome_col])

    if len(valid) < 10 or valid[outcome_col].nunique() < 2:
        return BaselineResult(
            name='geographic_distance',
            auc=0.5,
            description='Geographic distance (inverse relationship)',
        )

    # Inverse distance (closer = more conflict)
    distance_predictor = -np.log(valid['distance'] + 1)

    try:
        auc = roc_auc_score(valid[outcome_col], distance_predictor)
    except ValueError:
        auc = 0.5

    return BaselineResult(
        name='geographic_distance',
        auc=auc,
        description='Geographic distance (inverse relationship)',
    )


def compute_historical_conflict_baseline(
    dyad_data: pd.DataFrame,
    outcome_col: str = 'escalation',
    history_col: str = 'historical_conflict_count',
) -> BaselineResult:
    """
    Historical conflict count as predictor.

    Past conflict predicts future conflict.

    Args:
        dyad_data: Dyad-level data with historical counts
        outcome_col: Escalation outcome column
        history_col: Historical conflict count column

    Returns:
        BaselineResult with AUC
    """
    valid = dyad_data.dropna(subset=[history_col, outcome_col])

    if len(valid) < 10 or valid[outcome_col].nunique() < 2:
        return BaselineResult(
            name='historical_conflict',
            auc=0.5,
            description='Count of past conflicts between actors',
        )

    try:
        auc = roc_auc_score(valid[outcome_col], valid[history_col])
    except ValueError:
        auc = 0.5

    return BaselineResult(
        name='historical_conflict',
        auc=auc,
        description='Count of past conflicts between actors',
    )


def compute_ethnic_fractionalization_baseline(
    dyad_data: pd.DataFrame,
    elf_data: pd.DataFrame,
    outcome_col: str = 'escalation',
) -> BaselineResult:
    """
    Ethnic fractionalization as conflict predictor.

    ELF index (Alesina et al.) as predictor.

    Args:
        dyad_data: Dyad-level data
        elf_data: ELF data by actor
        outcome_col: Escalation outcome column

    Returns:
        BaselineResult with AUC
    """
    merged = dyad_data.copy()

    # ELF for both actors
    elf_a = elf_data.rename(columns={'actor': 'actor_a', 'elf': 'elf_a'})
    elf_b = elf_data.rename(columns={'actor': 'actor_b', 'elf': 'elf_b'})

    merged = merged.merge(elf_a[['actor_a', 'elf_a']], on='actor_a', how='left')
    merged = merged.merge(elf_b[['actor_b', 'elf_b']], on='actor_b', how='left')

    # Average ELF (or max)
    merged['elf_avg'] = (merged['elf_a'] + merged['elf_b']) / 2

    valid = merged.dropna(subset=['elf_avg', outcome_col])

    if len(valid) < 10 or valid[outcome_col].nunique() < 2:
        return BaselineResult(
            name='ethnic_fractionalization',
            auc=0.5,
            description='Ethnic Linguistic Fractionalization index',
        )

    try:
        auc = roc_auc_score(valid[outcome_col], valid['elf_avg'])
    except ValueError:
        auc = 0.5

    return BaselineResult(
        name='ethnic_fractionalization',
        auc=auc,
        description='Ethnic Linguistic Fractionalization index',
    )


def compute_intensity_lag_baseline(
    dyad_data: pd.DataFrame,
    outcome_col: str = 'escalation',
    intensity_col: str = 'intensity',
    lag: int = 1,
) -> BaselineResult:
    """
    Lagged intensity as predictor.

    Simple autoregressive baseline.

    Args:
        dyad_data: Dyad-level time series data
        outcome_col: Escalation outcome column
        intensity_col: Intensity column
        lag: Number of periods to lag

    Returns:
        BaselineResult with AUC
    """
    df = dyad_data.copy()
    df['intensity_lag'] = df.groupby(['actor_a', 'actor_b'])[intensity_col].shift(lag)

    valid = df.dropna(subset=['intensity_lag', outcome_col])

    if len(valid) < 10 or valid[outcome_col].nunique() < 2:
        return BaselineResult(
            name=f'intensity_lag_{lag}',
            auc=0.5,
            description=f'Intensity lagged by {lag} periods',
        )

    try:
        auc = roc_auc_score(valid[outcome_col], valid['intensity_lag'])
    except ValueError:
        auc = 0.5

    return BaselineResult(
        name=f'intensity_lag_{lag}',
        auc=auc,
        description=f'Intensity lagged by {lag} periods',
    )


def compare_to_baselines(
    compression_predictions: np.ndarray,
    actuals: np.ndarray,
    dyad_data: pd.DataFrame,
    additional_data: Optional[Dict[str, pd.DataFrame]] = None,
) -> pd.DataFrame:
    """
    Compare compression divergence model to all baselines.

    Args:
        compression_predictions: Our model's predictions
        actuals: Actual escalation outcomes
        dyad_data: Dyad-level data
        additional_data: Dict with 'gdp', 'distance', 'elf' DataFrames

    Returns:
        DataFrame comparing AUC across models
    """
    results = []

    # Our model
    try:
        our_auc = roc_auc_score(actuals, compression_predictions)
    except ValueError:
        our_auc = 0.5

    results.append({
        'model': 'compression_divergence',
        'auc': our_auc,
        'description': 'KL divergence of compression schemes',
        'is_baseline': False,
    })

    # Random baseline
    random_preds = np.random.random(len(actuals))
    results.append({
        'model': 'random',
        'auc': 0.5,
        'description': 'Random predictions',
        'is_baseline': True,
    })

    # Intensity lag baseline
    if 'intensity' in dyad_data.columns and 'escalation' in dyad_data.columns:
        lag_result = compute_intensity_lag_baseline(dyad_data)
        results.append({
            'model': lag_result.name,
            'auc': lag_result.auc,
            'description': lag_result.description,
            'is_baseline': True,
        })

    # GDP baseline
    if additional_data and 'gdp' in additional_data:
        gdp_result = compute_gdp_baseline(
            dyad_data,
            additional_data['gdp'],
        )
        results.append({
            'model': gdp_result.name,
            'auc': gdp_result.auc,
            'description': gdp_result.description,
            'is_baseline': True,
        })

    # Historical conflict baseline
    if 'historical_conflict_count' in dyad_data.columns:
        hist_result = compute_historical_conflict_baseline(dyad_data)
        results.append({
            'model': hist_result.name,
            'auc': hist_result.auc,
            'description': hist_result.description,
            'is_baseline': True,
        })

    df = pd.DataFrame(results)
    df = df.sort_values('auc', ascending=False)

    # Add improvement over random
    df['improvement_over_random'] = df['auc'] - 0.5

    return df


def ensemble_with_baselines(
    compression_predictions: np.ndarray,
    baseline_predictions: Dict[str, np.ndarray],
    actuals: np.ndarray,
    weights: Optional[Dict[str, float]] = None,
) -> Dict:
    """
    Create ensemble combining compression divergence with baselines.

    Args:
        compression_predictions: Our model's predictions
        baseline_predictions: Dict of baseline predictions
        actuals: Actual outcomes
        weights: Optional weights for ensemble

    Returns:
        Dict with ensemble AUC and individual AUCs
    """
    if weights is None:
        # Equal weights
        n_models = 1 + len(baseline_predictions)
        weights = {'compression': 1 / n_models}
        for name in baseline_predictions:
            weights[name] = 1 / n_models

    # Weighted ensemble
    ensemble_pred = weights.get('compression', 0.5) * compression_predictions
    for name, preds in baseline_predictions.items():
        ensemble_pred += weights.get(name, 0) * preds

    ensemble_pred /= sum(weights.values())

    # Compute AUCs
    results = {
        'ensemble_auc': roc_auc_score(actuals, ensemble_pred),
        'compression_auc': roc_auc_score(actuals, compression_predictions),
    }

    for name, preds in baseline_predictions.items():
        try:
            results[f'{name}_auc'] = roc_auc_score(actuals, preds)
        except ValueError:
            results[f'{name}_auc'] = 0.5

    return results


if __name__ == "__main__":
    print("Testing Baseline Comparisons...")
    print("=" * 70)

    # Create synthetic data
    np.random.seed(42)
    n = 300

    # True relationship: escalation depends on divergence + some baseline effects
    divergence = np.random.randn(n)
    gdp_diff = np.abs(np.random.randn(n))
    historical = np.random.poisson(2, n)

    # True probability
    logit = 0.5 * divergence + 0.2 * gdp_diff + 0.1 * historical
    true_prob = 1 / (1 + np.exp(-logit))
    actuals = (np.random.random(n) < true_prob).astype(int)

    # Our predictions (good model)
    our_preds = true_prob + np.random.randn(n) * 0.1
    our_preds = np.clip(our_preds, 0, 1)

    # Baseline predictions (worse)
    gdp_preds = (gdp_diff - gdp_diff.min()) / (gdp_diff.max() - gdp_diff.min())
    hist_preds = (historical - historical.min()) / (historical.max() - historical.min() + 1e-10)

    # Create dyad data
    dyad_data = pd.DataFrame({
        'actor_a': ['USA'] * n,
        'actor_b': ['RUS'] * n,
        'escalation': actuals,
        'intensity': np.random.randn(n).cumsum(),
        'historical_conflict_count': historical,
    })

    # Compare
    comparison = compare_to_baselines(our_preds, actuals, dyad_data)

    print("\nModel Comparison:")
    print("-" * 70)
    for _, row in comparison.iterrows():
        status = "✓" if not row['is_baseline'] else " "
        print(f"  {status} {row['model']:30s} AUC={row['auc']:.3f} (+{row['improvement_over_random']:.3f})")

    # Ensemble
    baseline_preds = {
        'gdp_diff': gdp_preds,
        'historical': hist_preds,
    }
    ensemble_results = ensemble_with_baselines(our_preds, baseline_preds, actuals)

    print(f"\nEnsemble Results:")
    print(f"  Compression only: {ensemble_results['compression_auc']:.3f}")
    print(f"  Ensemble:         {ensemble_results['ensemble_auc']:.3f}")
    print(f"  Improvement:      {ensemble_results['ensemble_auc'] - ensemble_results['compression_auc']:.3f}")

    print("\n" + "=" * 70)
