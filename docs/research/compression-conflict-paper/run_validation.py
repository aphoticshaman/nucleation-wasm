#!/usr/bin/env python3
"""
Compression Dynamics - Validation Runner

Runs validation experiments using synthetic data to verify framework logic.
Use this when GDELT data is unavailable.

Author: Ryan J Cardwell (Archer Phoenix)
"""
import sys
from pathlib import Path
import json
import numpy as np
import pandas as pd
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from compression_dynamics import CompressionDynamicsModel, CompressionScheme
from conflict.synthetic_data import (
    generate_synthetic_events,
    generate_compression_schemes_with_divergence,
    generate_validation_dataset,
)
from conflict.gdelt_client import aggregate_dyad_intensity
from validation.correlation import (
    validate_divergence_conflict_correlation,
    compute_lagged_correlations,
)
from validation.prediction import validate_escalation_prediction, define_escalation_events
from validation.baselines import compare_to_baselines


def main():
    print("=" * 70)
    print("COMPRESSION DYNAMICS OF CONFLICT")
    print("Validation Framework (Synthetic Data)")
    print("=" * 70)

    # Generate synthetic data
    print("\nPHASE 1: Generating Synthetic Data")
    print("-" * 70)

    events = generate_synthetic_events(n_days=90, events_per_day=800, seed=42)
    print(f"Generated {len(events):,} events")

    actors = ['USA', 'RUS', 'CHN', 'UKR', 'ISR', 'IRN', 'GBR', 'FRA', 'DEU', 'TUR']
    schemes = generate_compression_schemes_with_divergence(actors, n_categories=10, seed=42)
    print(f"Generated schemes for {len(schemes)} actors")

    # Initialize model
    model = CompressionDynamicsModel(n_categories=10)
    for actor, dist in schemes.items():
        model.register_actor(actor, dist)

    # Compute divergences
    print("\nPHASE 2: Computing Divergences")
    print("-" * 70)

    dyads = []
    for i, a in enumerate(actors):
        for b in actors[i+1:]:
            dyads.append((a, b))

    divergence_data = []
    for actor_a, actor_b in dyads:
        potential = model.compute_conflict_potential(actor_a, actor_b)
        # Sort actor order to match intensity aggregation
        sorted_pair = tuple(sorted([actor_a, actor_b]))
        divergence_data.append({
            'actor_a': sorted_pair[0],
            'actor_b': sorted_pair[1],
            'phi': potential.phi,
            'js': potential.js,
        })

    divergence_df = pd.DataFrame(divergence_data)
    print(f"Computed divergences for {len(divergence_df)} dyads")

    # Sample divergences
    print("\nTop 5 highest divergence dyads:")
    top_div = divergence_df.nlargest(5, 'phi')
    for _, row in top_div.iterrows():
        print(f"  {row['actor_a']}-{row['actor_b']}: Φ = {row['phi']:.3f}")

    print("\nTop 5 lowest divergence dyads:")
    bottom_div = divergence_df.nsmallest(5, 'phi')
    for _, row in bottom_div.iterrows():
        print(f"  {row['actor_a']}-{row['actor_b']}: Φ = {row['phi']:.3f}")

    # Compute conflict intensity
    print("\nPHASE 3: Computing Conflict Intensity")
    print("-" * 70)

    intensity_df = aggregate_dyad_intensity(events, window_days=7)
    print(f"Computed intensity for {len(intensity_df)} dyad-periods")

    # === HYPOTHESIS 1: Correlation ===
    print("\n" + "=" * 70)
    print("HYPOTHESIS 1: Divergence-Conflict Correlation")
    print("=" * 70)

    # Aggregate intensity by dyad
    intensity_by_dyad = intensity_df.groupby(['actor_a', 'actor_b']).agg({
        'intensity': 'mean',
        'event_count': 'sum',
    }).reset_index()

    result = validate_divergence_conflict_correlation(
        divergence_df,
        intensity_by_dyad,
        divergence_col='phi',
        intensity_col='intensity',
        merge_on=['actor_a', 'actor_b'],
    )

    print(f"\n  Correlation (Φ vs intensity):")
    print(f"    r = {result.r:.3f} [{result.ci_lower:.3f}, {result.ci_upper:.3f}]")
    print(f"    p = {result.p_value:.4f}")
    print(f"    n = {result.n}")

    h1_pass = result.p_value < 0.05 and result.r > 0.2

    # === HYPOTHESIS 2: Temporal Precedence ===
    print("\n" + "=" * 70)
    print("HYPOTHESIS 2: Temporal Precedence")
    print("=" * 70)

    # Generate validation dataset with temporal structure
    val_data = generate_validation_dataset(n_observations=500, seed=42)

    # Simulate temporal data
    val_data = val_data.sort_values('date')
    val_data['phi_lag'] = val_data.groupby(['actor_a', 'actor_b'])['phi'].shift(1)

    lagged_corr = val_data[['phi_lag', 'intensity']].dropna()
    if len(lagged_corr) > 10:
        from scipy.stats import pearsonr
        r_lag, p_lag = pearsonr(lagged_corr['phi_lag'], lagged_corr['intensity'])
        print(f"\n  Lagged correlation (Φ_t-1 vs intensity_t):")
        print(f"    r = {r_lag:.3f}, p = {p_lag:.4f}")
        h2_pass = r_lag > 0.2 and p_lag < 0.05
    else:
        h2_pass = False
        r_lag = np.nan

    # === HYPOTHESIS 3: Escalation Prediction ===
    print("\n" + "=" * 70)
    print("HYPOTHESIS 3: Escalation Prediction")
    print("=" * 70)

    # Generate predictions
    predictions = []
    actuals = []

    for _, row in val_data.iterrows():
        try:
            pred = model.predict_escalation(row['actor_a'], row['actor_b'])
            predictions.append(pred['probability'])
            actuals.append(row['escalation'])
        except:
            continue

    predictions = np.array(predictions)
    actuals = np.array(actuals)

    pred_result = validate_escalation_prediction(predictions, actuals)

    print(f"\n  Prediction Performance:")
    print(f"    AUC: {pred_result.auc:.3f} [{pred_result.auc_ci_lower:.3f}, {pred_result.auc_ci_upper:.3f}]")
    print(f"    Average Precision: {pred_result.avg_precision:.3f}")
    print(f"    Best F1: {pred_result.best_f1:.3f}")
    print(f"    Base rate: {pred_result.n_positive / (pred_result.n_positive + pred_result.n_negative):.3f}")

    h3_pass = pred_result.auc > 0.6

    # === Baseline Comparison ===
    print("\n" + "=" * 70)
    print("BASELINE COMPARISON")
    print("=" * 70)

    # Simple baselines
    random_preds = np.random.random(len(actuals))
    random_auc = validate_escalation_prediction(random_preds, actuals).auc

    intensity_preds = val_data['intensity'].values[:len(actuals)]
    intensity_auc = validate_escalation_prediction(intensity_preds, actuals).auc

    print(f"\n  Model AUC:              {pred_result.auc:.3f}")
    print(f"  Random baseline AUC:    {random_auc:.3f}")
    print(f"  Intensity-only AUC:     {intensity_auc:.3f}")
    print(f"  Improvement over random: +{pred_result.auc - 0.5:.3f}")

    # === SUMMARY ===
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    print(f"\n  H1 (Divergence correlates with conflict):")
    print(f"      r = {result.r:.3f}, p = {result.p_value:.4f}")
    print(f"      {'✓ PASS' if h1_pass else '✗ FAIL'}")

    print(f"\n  H2 (Divergence leads conflict):")
    print(f"      r(lag) = {r_lag:.3f}")
    print(f"      {'✓ PASS' if h2_pass else '✗ FAIL / Insufficient data'}")

    print(f"\n  H3 (Model predicts escalation):")
    print(f"      AUC = {pred_result.auc:.3f}")
    print(f"      {'✓ PASS' if h3_pass else '✗ FAIL'}")

    # Overall assessment
    print("\n" + "-" * 70)
    n_pass = sum([h1_pass, h2_pass, h3_pass])
    print(f"Overall: {n_pass}/3 hypotheses supported")

    if n_pass >= 2:
        print("\n  ✓ Framework validation: SUCCESSFUL")
        print("    Compression divergence shows promise as conflict predictor.")
    else:
        print("\n  ✗ Framework validation: NEEDS WORK")
        print("    Consider refining operationalization or hypothesis.")

    # Save results
    results = {
        'timestamp': datetime.now().isoformat(),
        'n_events': int(len(events)),
        'n_actors': int(len(actors)),
        'n_dyads': int(len(divergence_df)),
        'h1_correlation': {
            'r': float(result.r) if not np.isnan(result.r) else None,
            'p': float(result.p_value),
            'ci': [float(result.ci_lower) if not np.isnan(result.ci_lower) else None,
                   float(result.ci_upper) if not np.isnan(result.ci_upper) else None],
            'pass': bool(h1_pass),
        },
        'h2_temporal': {
            'r_lagged': float(r_lag) if not np.isnan(r_lag) else None,
            'pass': bool(h2_pass),
        },
        'h3_prediction': {
            'auc': float(pred_result.auc),
            'avg_precision': float(pred_result.avg_precision),
            'f1': float(pred_result.best_f1),
            'pass': bool(h3_pass),
        },
        'baselines': {
            'random_auc': 0.5,
            'intensity_auc': float(intensity_auc),
        },
        'overall_pass': bool(n_pass >= 2),
    }

    output_dir = Path('results')
    output_dir.mkdir(exist_ok=True)

    with open(output_dir / 'validation_results.json', 'w') as f:
        json.dump(results, f, indent=2)

    print(f"\nResults saved to: results/validation_results.json")
    print("=" * 70)


if __name__ == "__main__":
    main()
