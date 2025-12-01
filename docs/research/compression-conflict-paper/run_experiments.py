#!/usr/bin/env python3
"""
Compression Dynamics of Conflict - Main Experiment Runner

Validates the hypothesis that conflict intensity is proportional to
KL divergence of actor compression schemes.

Usage:
    python run_experiments.py                  # Full analysis
    python run_experiments.py --quick          # Quick test
    python run_experiments.py --case-study UKR # Specific case study
    python run_experiments.py --fetch-data     # Download data only

Author: Ryan J Cardwell (Archer Phoenix)
"""
import argparse
import sys
from pathlib import Path
from datetime import datetime, timedelta
import json
import warnings
warnings.filterwarnings('ignore')

import numpy as np
import pandas as pd

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from compression_dynamics import (
    CompressionDynamicsModel,
    CompressionScheme,
    EventCompressionExtractor,
    GoldsteinCompressionExtractor,
)
from conflict import GDELTClient, aggregate_dyad_intensity
from validation.correlation import (
    validate_divergence_conflict_correlation,
    compute_lagged_correlations,
    granger_causality_test,
)
from validation.prediction import (
    validate_escalation_prediction,
    define_escalation_events,
)
from validation.baselines import compare_to_baselines


def fetch_conflict_data(
    start_date: str,
    end_date: str,
    cache_dir: str = ".gdelt_cache",
) -> pd.DataFrame:
    """Fetch GDELT conflict data."""
    client = GDELTClient(Path(cache_dir))
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")
    return client.fetch_range(start, end)


def extract_compression_schemes(
    events: pd.DataFrame,
    actors: list,
    window_days: int = 14,
) -> dict:
    """Extract compression schemes for actors from GDELT events."""
    extractor = GoldsteinCompressionExtractor(n_bins=10)

    schemes_by_actor = {}

    for actor in actors:
        print(f"  Extracting scheme for {actor}...")

        # Filter to actor's events
        actor_events = events[
            (events['Actor1CountryCode'] == actor) |
            (events['Actor2CountryCode'] == actor)
        ]

        if len(actor_events) < 50:
            print(f"    Skipping {actor} (only {len(actor_events)} events)")
            continue

        # Extract temporal schemes
        scheme = extractor.extract_scheme(
            actor_events,
            actor,
            actor_column='Actor1CountryCode',
        )

        schemes_by_actor[actor] = scheme
        print(f"    {actor}: {scheme.metadata.get('n_events', 0)} events, entropy={scheme.entropy:.3f}")

    return schemes_by_actor


def compute_dyad_divergences(
    schemes: dict,
    dyads: list,
) -> pd.DataFrame:
    """Compute divergences for all dyads."""
    results = []

    for actor_a, actor_b in dyads:
        if actor_a not in schemes or actor_b not in schemes:
            continue

        scheme_a = schemes[actor_a]
        scheme_b = schemes[actor_b]

        phi = scheme_a.symmetric_divergence(scheme_b)
        js = scheme_a.jensen_shannon(scheme_b)

        results.append({
            'actor_a': actor_a,
            'actor_b': actor_b,
            'phi': phi,
            'js': js,
            'kl_a_b': scheme_a.kl_divergence(scheme_b),
            'kl_b_a': scheme_b.kl_divergence(scheme_a),
        })

    return pd.DataFrame(results)


def run_correlation_analysis(
    divergence_df: pd.DataFrame,
    intensity_df: pd.DataFrame,
) -> dict:
    """Run correlation analysis (H1)."""
    print("\n" + "=" * 70)
    print("HYPOTHESIS 1: Divergence-Conflict Correlation")
    print("=" * 70)

    # Merge data
    merged = pd.merge(
        divergence_df,
        intensity_df,
        on=['actor_a', 'actor_b'],
        how='inner',
    )

    if len(merged) < 10:
        print("  Insufficient data for correlation analysis")
        return {'r': np.nan, 'p': 1.0, 'n': len(merged)}

    # Main correlation
    result = validate_divergence_conflict_correlation(
        divergence_df,
        intensity_df,
        divergence_col='phi',
        intensity_col='intensity',
        merge_on=['actor_a', 'actor_b'],
    )

    print(f"\n  Correlation (Φ vs intensity):")
    print(f"    r = {result.r:.3f} [{result.ci_lower:.3f}, {result.ci_upper:.3f}]")
    print(f"    p = {result.p_value:.4f}")
    print(f"    n = {result.n}")

    significance = "SIGNIFICANT" if result.p_value < 0.05 else "NOT SIGNIFICANT"
    print(f"\n  Result: {significance}")

    return {
        'r': result.r,
        'ci_lower': result.ci_lower,
        'ci_upper': result.ci_upper,
        'p': result.p_value,
        'n': result.n,
        'significant': result.p_value < 0.05,
    }


def run_temporal_analysis(
    divergence_series: pd.DataFrame,
    conflict_series: pd.DataFrame,
) -> dict:
    """Run temporal precedence analysis (H2)."""
    print("\n" + "=" * 70)
    print("HYPOTHESIS 2: Temporal Precedence")
    print("=" * 70)

    # Lagged correlations
    lagged = compute_lagged_correlations(
        divergence_series,
        conflict_series,
        max_lag=60,
        lag_step=7,
    )

    if lagged.empty:
        print("  Insufficient data for temporal analysis")
        return {'best_lag': 0, 'best_r': np.nan, 'granger_p': 1.0}

    # Find best lag
    best_idx = lagged['correlation'].abs().idxmax()
    best_lag = lagged.loc[best_idx, 'lag_days']
    best_r = lagged.loc[best_idx, 'correlation']

    print(f"\n  Lagged correlations:")
    print(f"    Best lag: {best_lag} days (r = {best_r:.3f})")

    if best_lag > 0:
        print(f"    Interpretation: Divergence LEADS conflict")
    elif best_lag < 0:
        print(f"    Interpretation: Conflict LEADS divergence")
    else:
        print(f"    Interpretation: Contemporaneous relationship")

    # Granger causality (if we have time series)
    granger_result = {'div_causes_conf': 1.0, 'conf_causes_div': 1.0}

    if 'phi' in divergence_series.columns and 'intensity' in conflict_series.columns:
        try:
            div_vals = divergence_series['phi'].values
            conf_vals = conflict_series['intensity'].values

            if len(div_vals) == len(conf_vals) and len(div_vals) > 50:
                gc = granger_causality_test(div_vals, conf_vals, max_lag=8)

                print(f"\n  Granger Causality:")
                print(f"    Divergence → Conflict: F={gc['divergence_causes_conflict'].f_statistic:.2f}, p={gc['divergence_causes_conflict'].p_value:.4f}")
                print(f"    Conflict → Divergence: F={gc['conflict_causes_divergence'].f_statistic:.2f}, p={gc['conflict_causes_divergence'].p_value:.4f}")

                granger_result = {
                    'div_causes_conf': gc['divergence_causes_conflict'].p_value,
                    'conf_causes_div': gc['conflict_causes_divergence'].p_value,
                }
        except Exception as e:
            print(f"  Granger test failed: {e}")

    return {
        'best_lag': int(best_lag),
        'best_r': float(best_r),
        'lagged_correlations': lagged.to_dict('records'),
        'granger_p_div_to_conf': granger_result['div_causes_conf'],
        'granger_p_conf_to_div': granger_result['conf_causes_div'],
    }


def run_prediction_analysis(
    model: CompressionDynamicsModel,
    test_data: pd.DataFrame,
) -> dict:
    """Run escalation prediction analysis (H3)."""
    print("\n" + "=" * 70)
    print("HYPOTHESIS 3: Escalation Prediction")
    print("=" * 70)

    # Define escalation events
    test_with_escalation = define_escalation_events(test_data)

    predictions = []
    actuals = []

    # Generate predictions for each observation
    dyads = test_with_escalation.groupby(['actor_a', 'actor_b']).size().index.tolist()

    for actor_a, actor_b in dyads:
        try:
            pred = model.predict_escalation(actor_a, actor_b)
            dyad_mask = (
                (test_with_escalation['actor_a'] == actor_a) &
                (test_with_escalation['actor_b'] == actor_b)
            )
            dyad_escalations = test_with_escalation[dyad_mask]['escalation'].values

            for esc in dyad_escalations:
                predictions.append(pred['probability'])
                actuals.append(esc)

        except (KeyError, ValueError):
            continue

    if len(predictions) < 10:
        print("  Insufficient predictions generated")
        return {'auc': 0.5, 'n_predictions': len(predictions)}

    predictions = np.array(predictions)
    actuals = np.array(actuals)

    # Evaluate
    result = validate_escalation_prediction(predictions, actuals)

    print(f"\n  Prediction Performance:")
    print(f"    AUC: {result.auc:.3f} [{result.auc_ci_lower:.3f}, {result.auc_ci_upper:.3f}]")
    print(f"    Average Precision: {result.avg_precision:.3f}")
    print(f"    Best F1: {result.best_f1:.3f}")
    print(f"    N predictions: {len(predictions)}")
    print(f"    N escalations: {result.n_positive}")
    print(f"    Base rate: {result.n_positive / (result.n_positive + result.n_negative):.3f}")

    # Compare to baseline
    baseline_auc = 0.5
    improvement = result.auc - baseline_auc

    print(f"\n  vs Random Baseline:")
    print(f"    Improvement: +{improvement:.3f}")

    return {
        'auc': result.auc,
        'auc_ci_lower': result.auc_ci_lower,
        'auc_ci_upper': result.auc_ci_upper,
        'avg_precision': result.avg_precision,
        'best_f1': result.best_f1,
        'n_predictions': len(predictions),
        'n_escalations': result.n_positive,
        'base_rate': result.n_positive / (result.n_positive + result.n_negative),
        'improvement_over_random': improvement,
    }


def run_case_study(
    events: pd.DataFrame,
    actor_a: str,
    actor_b: str,
) -> dict:
    """Run case study for specific dyad."""
    print("\n" + "=" * 70)
    print(f"CASE STUDY: {actor_a} - {actor_b}")
    print("=" * 70)

    # Filter to dyad
    dyad_events = events[
        ((events['Actor1CountryCode'] == actor_a) & (events['Actor2CountryCode'] == actor_b)) |
        ((events['Actor1CountryCode'] == actor_b) & (events['Actor2CountryCode'] == actor_a))
    ]

    print(f"\n  Events in dyad: {len(dyad_events)}")

    if len(dyad_events) < 30:
        print("  Insufficient events for case study")
        return {}

    # Extract schemes over time
    extractor = GoldsteinCompressionExtractor(n_bins=10)

    # Parse dates
    dyad_events = dyad_events.copy()
    dyad_events['date'] = pd.to_datetime(
        dyad_events['SQLDATE'].astype(str),
        format='%Y%m%d',
        errors='coerce',
    )
    dyad_events = dyad_events.dropna(subset=['date'])
    dyad_events.set_index('date', inplace=True)

    # Weekly aggregation
    weekly_stats = []
    for week_end, week_df in dyad_events.groupby(pd.Grouper(freq='W')):
        if len(week_df) < 5:
            continue

        week_df = week_df.reset_index()

        # Extract schemes for both actors
        scheme_a = extractor.extract_scheme(week_df, actor_a, 'Actor1CountryCode')
        scheme_b = extractor.extract_scheme(week_df, actor_b, 'Actor1CountryCode')

        phi = scheme_a.symmetric_divergence(scheme_b)

        # Mean Goldstein
        mean_goldstein = week_df['GoldsteinScale'].mean()

        weekly_stats.append({
            'week': week_end,
            'phi': phi,
            'mean_goldstein': mean_goldstein,
            'n_events': len(week_df),
        })

    if not weekly_stats:
        return {}

    weekly_df = pd.DataFrame(weekly_stats)

    print(f"\n  Weekly statistics:")
    print(f"    Time range: {weekly_df['week'].min()} to {weekly_df['week'].max()}")
    print(f"    Mean Φ: {weekly_df['phi'].mean():.3f}")
    print(f"    Mean Goldstein: {weekly_df['mean_goldstein'].mean():.2f}")

    # Correlation within dyad
    if len(weekly_df) >= 10:
        from scipy.stats import pearsonr
        r, p = pearsonr(weekly_df['phi'], -weekly_df['mean_goldstein'])
        print(f"\n  Within-dyad correlation:")
        print(f"    r(Φ, conflict) = {r:.3f}, p = {p:.4f}")

    return {
        'actor_a': actor_a,
        'actor_b': actor_b,
        'n_weeks': len(weekly_df),
        'mean_phi': float(weekly_df['phi'].mean()),
        'mean_goldstein': float(weekly_df['mean_goldstein'].mean()),
        'weekly_data': weekly_df.to_dict('records'),
    }


def main():
    parser = argparse.ArgumentParser(description="Compression Dynamics Experiments")
    parser.add_argument("--quick", action="store_true", help="Quick test (7 days)")
    parser.add_argument("--days", type=int, default=60, help="Days of data to analyze")
    parser.add_argument("--fetch-data", action="store_true", help="Only fetch data")
    parser.add_argument("--case-study", type=str, help="Run case study for country code")
    parser.add_argument("--output", type=str, default="results", help="Output directory")

    args = parser.parse_args()

    output_dir = Path(args.output)
    output_dir.mkdir(exist_ok=True)

    # Determine date range
    if args.quick:
        days = 7
    else:
        days = args.days

    end_date = datetime.now() - timedelta(days=2)
    start_date = end_date - timedelta(days=days)

    print("=" * 70)
    print("COMPRESSION DYNAMICS OF CONFLICT")
    print("KL-Divergence Framework Validation")
    print("=" * 70)
    print(f"\nDate range: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")

    # Fetch data
    print("\n" + "-" * 70)
    print("PHASE 1: Data Acquisition")
    print("-" * 70)

    events = fetch_conflict_data(
        start_date.strftime("%Y-%m-%d"),
        end_date.strftime("%Y-%m-%d"),
    )

    if events.empty:
        print("ERROR: No events fetched. Check internet connection.")
        return

    print(f"\nTotal events: {len(events):,}")

    if args.fetch_data:
        print("\nData fetched. Exiting (--fetch-data mode)")
        return

    # Key actors to analyze
    actors = ['USA', 'RUS', 'CHN', 'UKR', 'ISR', 'IRN', 'GBR', 'FRA', 'DEU', 'TUR']

    # Generate dyads
    dyads = []
    for i, a in enumerate(actors):
        for b in actors[i+1:]:
            dyads.append((a, b))

    print(f"Analyzing {len(actors)} actors, {len(dyads)} dyads")

    # Case study mode
    if args.case_study:
        # Find dyads involving the specified country
        case_actor = args.case_study.upper()
        case_dyads = [d for d in dyads if case_actor in d]

        if not case_dyads:
            print(f"No dyads found for {case_actor}")
            return

        for dyad in case_dyads[:3]:  # Top 3
            result = run_case_study(events, dyad[0], dyad[1])

        return

    # Phase 2: Extract compression schemes
    print("\n" + "-" * 70)
    print("PHASE 2: Compression Scheme Extraction")
    print("-" * 70)

    schemes = extract_compression_schemes(events, actors)

    if len(schemes) < 2:
        print("ERROR: Insufficient schemes extracted")
        return

    # Compute divergences
    print("\n" + "-" * 70)
    print("PHASE 3: Computing Divergences")
    print("-" * 70)

    divergence_df = compute_dyad_divergences(schemes, dyads)
    print(f"\nComputed divergences for {len(divergence_df)} dyads")

    # Compute conflict intensity
    print("\n" + "-" * 70)
    print("PHASE 4: Computing Conflict Intensity")
    print("-" * 70)

    intensity_df = aggregate_dyad_intensity(events, window_days=days)
    print(f"Computed intensity for {len(intensity_df)} dyad-periods")

    # Initialize model
    model = CompressionDynamicsModel(n_categories=10)
    for actor, scheme in schemes.items():
        model.register_actor(actor, scheme.distribution)

    # Run analyses
    results = {
        'metadata': {
            'start_date': start_date.strftime('%Y-%m-%d'),
            'end_date': end_date.strftime('%Y-%m-%d'),
            'n_events': len(events),
            'n_actors': len(schemes),
            'n_dyads': len(divergence_df),
        },
    }

    # H1: Correlation
    results['h1_correlation'] = run_correlation_analysis(divergence_df, intensity_df)

    # H2: Temporal
    if len(intensity_df) > 20:
        results['h2_temporal'] = run_temporal_analysis(divergence_df, intensity_df)
    else:
        results['h2_temporal'] = {'note': 'Insufficient time series data'}

    # H3: Prediction
    if len(intensity_df) > 20:
        results['h3_prediction'] = run_prediction_analysis(model, intensity_df)
    else:
        results['h3_prediction'] = {'note': 'Insufficient data for prediction'}

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    h1 = results['h1_correlation']
    h2 = results.get('h2_temporal', {})
    h3 = results.get('h3_prediction', {})

    print(f"\nH1 (Correlation): r = {h1.get('r', np.nan):.3f}, p = {h1.get('p', 1.0):.4f}")
    print(f"H2 (Temporal): Best lag = {h2.get('best_lag', 'N/A')}, r = {h2.get('best_r', np.nan):.3f}")
    print(f"H3 (Prediction): AUC = {h3.get('auc', 0.5):.3f}")

    # Overall assessment
    print("\n" + "-" * 70)
    h1_pass = h1.get('significant', False) and h1.get('r', 0) > 0.2
    h2_pass = h2.get('best_lag', 0) > 0 and abs(h2.get('best_r', 0)) > 0.2
    h3_pass = h3.get('auc', 0.5) > 0.6

    print(f"H1 (Divergence correlates with conflict): {'✓ PASS' if h1_pass else '✗ FAIL'}")
    print(f"H2 (Divergence leads conflict):           {'✓ PASS' if h2_pass else '✗ FAIL'}")
    print(f"H3 (Model predicts escalation):           {'✓ PASS' if h3_pass else '✗ FAIL'}")

    # Save results
    results_file = output_dir / "experiment_results.json"
    with open(results_file, 'w') as f:
        # Convert numpy types for JSON
        def convert(obj):
            if isinstance(obj, np.floating):
                return float(obj)
            if isinstance(obj, np.integer):
                return int(obj)
            if isinstance(obj, np.ndarray):
                return obj.tolist()
            if isinstance(obj, pd.Timestamp):
                return obj.isoformat()
            return obj

        json.dump(results, f, indent=2, default=convert)

    print(f"\nResults saved to: {results_file}")
    print("=" * 70)


if __name__ == "__main__":
    main()
