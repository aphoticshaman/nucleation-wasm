"""
Prediction Validation for Compression Dynamics

Tests H3: Model can predict escalation events.

Author: Ryan J Cardwell (Archer Phoenix)
"""
import numpy as np
import pandas as pd
from scipy import stats
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from sklearn.metrics import (
    roc_auc_score,
    precision_recall_curve,
    average_precision_score,
    f1_score,
    confusion_matrix,
)


@dataclass
class PredictionResult:
    """Result from prediction evaluation."""
    auc: float
    auc_ci_lower: float
    auc_ci_upper: float
    avg_precision: float
    best_f1: float
    best_threshold: float
    n_positive: int
    n_negative: int


@dataclass
class EscalationEvent:
    """An escalation event for prediction."""
    actor_a: str
    actor_b: str
    date: pd.Timestamp
    intensity_before: float
    intensity_after: float
    escalation_magnitude: float


def define_escalation_events(
    intensity_series: pd.DataFrame,
    threshold_method: str = 'std',
    threshold_value: float = 1.5,
    min_intensity_change: float = 0.1,
) -> pd.DataFrame:
    """
    Define escalation events from intensity time series.

    Escalation = significant increase in conflict intensity.

    Args:
        intensity_series: DataFrame with date and intensity columns
        threshold_method: 'std' (standard deviations), 'quantile', or 'absolute'
        threshold_value: Threshold value (interpretation depends on method)
        min_intensity_change: Minimum absolute change to count

    Returns:
        DataFrame with escalation events marked
    """
    df = intensity_series.copy()

    if 'intensity' not in df.columns:
        raise ValueError("intensity_series must have 'intensity' column")

    # Compute intensity change
    df['intensity_change'] = df['intensity'].diff()

    # Define threshold
    if threshold_method == 'std':
        std = df['intensity_change'].std()
        threshold = threshold_value * std
    elif threshold_method == 'quantile':
        threshold = df['intensity_change'].quantile(threshold_value)
    else:
        threshold = threshold_value

    # Mark escalations
    df['escalation'] = (
        (df['intensity_change'] > threshold) &
        (df['intensity_change'].abs() > min_intensity_change)
    ).astype(int)

    df['escalation_magnitude'] = df['intensity_change'].clip(lower=0)

    return df


def validate_escalation_prediction(
    predictions: np.ndarray,
    actuals: np.ndarray,
    n_bootstrap: int = 1000,
) -> PredictionResult:
    """
    Evaluate escalation prediction performance.

    Args:
        predictions: Predicted probabilities of escalation
        actuals: Binary escalation labels (0/1)
        n_bootstrap: Number of bootstrap samples for CI

    Returns:
        PredictionResult with AUC, precision, F1
    """
    # Remove NaN
    mask = ~(np.isnan(predictions) | np.isnan(actuals))
    predictions = predictions[mask]
    actuals = actuals[mask]

    if len(predictions) < 10 or actuals.sum() < 2:
        return PredictionResult(
            auc=0.5,
            auc_ci_lower=0.0,
            auc_ci_upper=1.0,
            avg_precision=actuals.mean() if len(actuals) > 0 else 0.0,
            best_f1=0.0,
            best_threshold=0.5,
            n_positive=int(actuals.sum()),
            n_negative=int((1 - actuals).sum()),
        )

    # ROC AUC
    try:
        auc = roc_auc_score(actuals, predictions)
    except ValueError:
        auc = 0.5

    # Bootstrap CI for AUC
    bootstrap_aucs = []
    for _ in range(n_bootstrap):
        indices = np.random.choice(len(predictions), size=len(predictions), replace=True)
        boot_preds = predictions[indices]
        boot_actuals = actuals[indices]

        if boot_actuals.sum() > 0 and boot_actuals.sum() < len(boot_actuals):
            try:
                boot_auc = roc_auc_score(boot_actuals, boot_preds)
                bootstrap_aucs.append(boot_auc)
            except ValueError:
                continue

    if bootstrap_aucs:
        auc_ci_lower = np.percentile(bootstrap_aucs, 2.5)
        auc_ci_upper = np.percentile(bootstrap_aucs, 97.5)
    else:
        auc_ci_lower = auc - 0.1
        auc_ci_upper = auc + 0.1

    # Average precision
    try:
        avg_precision = average_precision_score(actuals, predictions)
    except ValueError:
        avg_precision = actuals.mean()

    # Best F1 score
    precision, recall, thresholds = precision_recall_curve(actuals, predictions)
    f1_scores = 2 * (precision * recall) / (precision + recall + 1e-10)
    best_f1_idx = np.argmax(f1_scores)
    best_f1 = f1_scores[best_f1_idx]
    best_threshold = thresholds[best_f1_idx] if best_f1_idx < len(thresholds) else 0.5

    return PredictionResult(
        auc=auc,
        auc_ci_lower=auc_ci_lower,
        auc_ci_upper=auc_ci_upper,
        avg_precision=avg_precision,
        best_f1=best_f1,
        best_threshold=best_threshold,
        n_positive=int(actuals.sum()),
        n_negative=int((1 - actuals).sum()),
    )


def evaluate_prediction_performance(
    model,
    test_data: pd.DataFrame,
    horizon_days: int = 30,
    intensity_col: str = 'intensity',
) -> Dict:
    """
    Evaluate model's prediction performance on test set.

    Args:
        model: CompressionDynamicsModel instance
        test_data: Test data with actor pairs and intensity
        horizon_days: Prediction horizon
        intensity_col: Column name for intensity

    Returns:
        Dict with performance metrics
    """
    predictions = []
    actuals = []

    # Get unique dyads
    dyads = test_data.groupby(['actor_a', 'actor_b']).size().index.tolist()

    for actor_a, actor_b in dyads:
        dyad_data = test_data[
            (test_data['actor_a'] == actor_a) &
            (test_data['actor_b'] == actor_b)
        ].sort_values('date')

        if len(dyad_data) < 3:
            continue

        # For each time point, predict next period
        for i in range(len(dyad_data) - 1):
            try:
                pred = model.predict_escalation(actor_a, actor_b, horizon_days)
                predictions.append(pred['probability'])

                # Actual: did escalation occur?
                current_intensity = dyad_data.iloc[i][intensity_col]
                next_intensity = dyad_data.iloc[i + 1][intensity_col]
                escalated = int(next_intensity > current_intensity * 1.2)  # 20% increase
                actuals.append(escalated)

            except (KeyError, ValueError):
                continue

    if not predictions:
        return {
            'auc': 0.5,
            'n_predictions': 0,
            'error': 'No valid predictions generated',
        }

    predictions = np.array(predictions)
    actuals = np.array(actuals)

    result = validate_escalation_prediction(predictions, actuals)

    return {
        'auc': result.auc,
        'auc_ci': (result.auc_ci_lower, result.auc_ci_upper),
        'avg_precision': result.avg_precision,
        'best_f1': result.best_f1,
        'best_threshold': result.best_threshold,
        'n_predictions': len(predictions),
        'n_escalations': result.n_positive,
        'base_rate': result.n_positive / (result.n_positive + result.n_negative),
    }


def compute_roc_auc(
    predictions: np.ndarray,
    actuals: np.ndarray,
) -> float:
    """
    Compute ROC AUC score.

    Args:
        predictions: Predicted probabilities
        actuals: Binary labels

    Returns:
        AUC score
    """
    try:
        return roc_auc_score(actuals, predictions)
    except ValueError:
        return 0.5


def compute_precision_recall_curve(
    predictions: np.ndarray,
    actuals: np.ndarray,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Compute precision-recall curve.

    Args:
        predictions: Predicted probabilities
        actuals: Binary labels

    Returns:
        Tuple of (precision, recall, thresholds)
    """
    return precision_recall_curve(actuals, predictions)


def stratified_evaluation(
    predictions: np.ndarray,
    actuals: np.ndarray,
    strata: np.ndarray,
) -> pd.DataFrame:
    """
    Evaluate performance stratified by a grouping variable.

    Args:
        predictions: Predicted probabilities
        actuals: Binary labels
        strata: Grouping variable (e.g., region, year)

    Returns:
        DataFrame with performance by stratum
    """
    results = []

    for stratum in np.unique(strata):
        mask = strata == stratum

        if mask.sum() < 10:
            continue

        stratum_preds = predictions[mask]
        stratum_actuals = actuals[mask]

        if stratum_actuals.sum() == 0 or stratum_actuals.sum() == len(stratum_actuals):
            auc = 0.5
        else:
            try:
                auc = roc_auc_score(stratum_actuals, stratum_preds)
            except ValueError:
                auc = 0.5

        results.append({
            'stratum': stratum,
            'auc': auc,
            'n': mask.sum(),
            'n_positive': stratum_actuals.sum(),
            'base_rate': stratum_actuals.mean(),
        })

    return pd.DataFrame(results)


def calibration_analysis(
    predictions: np.ndarray,
    actuals: np.ndarray,
    n_bins: int = 10,
) -> pd.DataFrame:
    """
    Analyze prediction calibration.

    Well-calibrated: predicted probability ≈ actual frequency.

    Args:
        predictions: Predicted probabilities
        actuals: Binary labels
        n_bins: Number of bins for calibration

    Returns:
        DataFrame with calibration statistics
    """
    # Bin predictions
    bin_edges = np.linspace(0, 1, n_bins + 1)
    bin_indices = np.digitize(predictions, bin_edges[:-1]) - 1
    bin_indices = np.clip(bin_indices, 0, n_bins - 1)

    results = []
    for bin_idx in range(n_bins):
        mask = bin_indices == bin_idx

        if mask.sum() == 0:
            continue

        mean_predicted = predictions[mask].mean()
        mean_actual = actuals[mask].mean()
        n = mask.sum()

        results.append({
            'bin': bin_idx,
            'bin_range': f"{bin_edges[bin_idx]:.2f}-{bin_edges[bin_idx+1]:.2f}",
            'mean_predicted': mean_predicted,
            'mean_actual': mean_actual,
            'calibration_error': abs(mean_predicted - mean_actual),
            'n': n,
        })

    return pd.DataFrame(results)


if __name__ == "__main__":
    print("Testing Prediction Validation...")
    print("=" * 70)

    # Create synthetic data
    np.random.seed(42)
    n = 500

    # True escalation probability depends on some latent factor
    latent = np.random.randn(n)
    true_prob = 1 / (1 + np.exp(-latent))

    # Actual escalations
    actuals = (np.random.random(n) < true_prob).astype(int)

    # Model predictions (with some noise)
    predictions = true_prob + np.random.randn(n) * 0.1
    predictions = np.clip(predictions, 0, 1)

    # Evaluate
    result = validate_escalation_prediction(predictions, actuals)

    print(f"\nPrediction Performance:")
    print(f"  AUC: {result.auc:.3f} [{result.auc_ci_lower:.3f}, {result.auc_ci_upper:.3f}]")
    print(f"  Average Precision: {result.avg_precision:.3f}")
    print(f"  Best F1: {result.best_f1:.3f} (threshold={result.best_threshold:.3f})")
    print(f"  N positive: {result.n_positive}")
    print(f"  N negative: {result.n_negative}")
    print(f"  Base rate: {result.n_positive / (result.n_positive + result.n_negative):.3f}")

    # Calibration
    print(f"\nCalibration Analysis:")
    cal_df = calibration_analysis(predictions, actuals, n_bins=5)
    for _, row in cal_df.iterrows():
        print(f"  {row['bin_range']}: predicted={row['mean_predicted']:.3f}, actual={row['mean_actual']:.3f}")

    # Test with random baseline
    random_preds = np.random.random(n)
    baseline_result = validate_escalation_prediction(random_preds, actuals)
    print(f"\nRandom Baseline AUC: {baseline_result.auc:.3f}")
    print(f"Improvement over baseline: {result.auc - baseline_result.auc:.3f}")

    print("\n" + "=" * 70)
