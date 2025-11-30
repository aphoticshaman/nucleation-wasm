#!/usr/bin/env python3
"""
Nucleation Detection Research Pipeline
Main entry point for running all experiments and generating the paper.

Usage:
    python run_experiments.py --all           # Run everything
    python run_experiments.py --experiments   # Run experiments only
    python run_experiments.py --figures       # Generate figures only
    python run_experiments.py --manuscript    # Generate manuscript only

Author: Ryan J Cardwell (Archer Phoenix)
Version: 1.0.0
"""
import argparse
import sys
from pathlib import Path
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from simulators import TransitionType, generate_dataset
from detectors import DetectorType, create_detector
from evaluation import (
    ExperimentConfig, EvaluationHarness,
    run_ablation_study, compare_detectors, print_results_table
)
from data import DataSource, prepare_dataset, evaluate_on_real_data


def run_baseline_experiments(output_dir: Path, n_simulations: int = 200):
    """Run baseline detector comparison."""
    print("\n" + "=" * 60)
    print("PHASE 1: Baseline Detector Comparison")
    print("=" * 60)

    output_dir.mkdir(parents=True, exist_ok=True)

    result = compare_detectors(
        n_simulations=n_simulations,
        seed=42,
        output_path=output_dir / "baseline_comparison.json",
    )

    print_results_table(result)

    return result


def run_ablation_studies(output_dir: Path, n_simulations: int = 50):
    """Run ablation studies on key parameters."""
    print("\n" + "=" * 60)
    print("PHASE 2: Ablation Studies")
    print("=" * 60)

    # 1. Noise level ablation
    print("\n--- Noise Level Ablation ---")
    noise_dir = output_dir / "noise_ablation"

    base_config = ExperimentConfig(
        name="noise_ablation",
        detector_types=[
            DetectorType.VARIANCE_RATIO,
            DetectorType.VARIANCE_DERIVATIVE,
            DetectorType.CUSUM,
            DetectorType.ENSEMBLE,
        ],
        detector_params={},
        n_simulations=n_simulations,
        detection_tolerance=50,
        seed=42,
    )

    noise_values = [0.01, 0.05, 0.1, 0.15, 0.2, 0.3, 0.5]
    noise_results = run_ablation_study(
        base_config=base_config,
        ablation_variable="noise_levels",
        ablation_values=noise_values,
        output_dir=noise_dir,
    )

    print("\nNoise Ablation Summary:")
    print(f"{'Noise':>8} {'VarRatio':>10} {'VarDeriv':>10} {'CUSUM':>10} {'Ensemble':>10}")
    print("-" * 55)
    for noise, res in zip(noise_values, noise_results):
        vr = res.metrics[DetectorType.VARIANCE_RATIO].f1_score
        vd = res.metrics[DetectorType.VARIANCE_DERIVATIVE].f1_score
        cs = res.metrics[DetectorType.CUSUM].f1_score
        en = res.metrics[DetectorType.ENSEMBLE].f1_score
        print(f"{noise:>8.2f} {vr:>10.3f} {vd:>10.3f} {cs:>10.3f} {en:>10.3f}")

    # 2. Window size ablation
    print("\n--- Window Size Ablation ---")
    window_dir = output_dir / "window_ablation"

    window_values = [20, 30, 50, 75, 100, 150]
    window_results = run_ablation_study(
        base_config=ExperimentConfig(
            name="window_ablation",
            detector_types=[DetectorType.VARIANCE_RATIO, DetectorType.ENSEMBLE],
            detector_params={
                DetectorType.VARIANCE_RATIO: {"window": 50},
                DetectorType.ENSEMBLE: {"window": 50},
            },
            n_simulations=n_simulations,
            seed=42,
        ),
        ablation_variable="window",
        ablation_values=window_values,
        output_dir=window_dir,
    )

    print("\nWindow Size Ablation Summary:")
    print(f"{'Window':>8} {'VarRatio F1':>12} {'Ensemble F1':>12}")
    print("-" * 35)
    for window, res in zip(window_values, window_results):
        vr = res.metrics[DetectorType.VARIANCE_RATIO].f1_score
        en = res.metrics[DetectorType.ENSEMBLE].f1_score
        print(f"{window:>8} {vr:>12.3f} {en:>12.3f}")

    return {"noise": noise_results, "window": window_results}


def run_real_world_validation(output_dir: Path, data_dir: Path):
    """Validate on real-world data."""
    print("\n" + "=" * 60)
    print("PHASE 3: Real-World Validation")
    print("=" * 60)

    output_dir.mkdir(parents=True, exist_ok=True)
    results = {}

    # Load all available data sources
    for source in [DataSource.GDELT, DataSource.FINANCIAL, DataSource.CLIMATE]:
        print(f"\n--- {source.value.upper()} Data ---")
        datasets = prepare_dataset(source, data_dir)

        if not datasets:
            print(f"  No {source.value} data available")
            continue

        print(f"  Loaded {len(datasets)} datasets")

        # Test each detector
        source_results = {}
        for dtype in [DetectorType.VARIANCE_RATIO, DetectorType.ENSEMBLE]:
            detector = create_detector(dtype)
            eval_results = evaluate_on_real_data(datasets, detector)

            source_results[dtype.value] = eval_results
            print(f"  {dtype.value}: recall={eval_results['recall']:.2%}, "
                  f"false_alarms={eval_results['false_alarms']}")

        results[source.value] = source_results

    # Save results
    import json
    with open(output_dir / "real_world_validation.json", "w") as f:
        json.dump(results, f, indent=2, default=str)

    return results


def run_per_transition_analysis(output_dir: Path, n_simulations: int = 100):
    """Analyze performance per transition type."""
    print("\n" + "=" * 60)
    print("PHASE 4: Per-Transition-Type Analysis")
    print("=" * 60)

    output_dir.mkdir(parents=True, exist_ok=True)

    results = {}

    for ttype in TransitionType:
        print(f"\n--- {ttype.value.upper()} ---")

        config = ExperimentConfig(
            name=f"single_type_{ttype.value}",
            detector_types=list(DetectorType),
            detector_params={},
            n_simulations=n_simulations,
            transition_types=[ttype],
            detection_tolerance=50,
            seed=42,
        )

        harness = EvaluationHarness(config)
        result = harness.run_experiment()

        # Store best performer
        best_dtype = max(
            result.metrics.keys(),
            key=lambda d: result.metrics[d].f1_score
        )
        results[ttype.value] = {
            "best_detector": best_dtype.value,
            "best_f1": result.metrics[best_dtype].f1_score,
            "best_mae": result.metrics[best_dtype].mean_abs_error,
        }

        print(f"  Best: {best_dtype.value} (F1={result.metrics[best_dtype].f1_score:.3f})")

        # Save full result
        result.save(output_dir / f"analysis_{ttype.value}.json")

    # Summary
    print("\nPer-Type Summary:")
    print(f"{'Type':>15} {'Best Detector':>20} {'F1':>8} {'MAE':>8}")
    print("-" * 55)
    for ttype, data in results.items():
        print(f"{ttype:>15} {data['best_detector']:>20} {data['best_f1']:>8.3f} {data['best_mae']:>8.1f}")

    return results


def generate_figures(output_dir: Path, experiment_dir: Path):
    """Generate all publication figures."""
    print("\n" + "=" * 60)
    print("PHASE 5: Figure Generation")
    print("=" * 60)

    from visualization import create_all_figures

    figures = create_all_figures(
        output_dir=output_dir,
        experiment_dir=experiment_dir,
        seed=42,
    )

    print(f"\nGenerated {len(figures)} figures:")
    for name, path in figures.items():
        print(f"  {name}: {path}")

    return figures


def generate_manuscript(output_dir: Path, experiment_dir: Path):
    """Generate manuscript from template with results."""
    print("\n" + "=" * 60)
    print("PHASE 6: Manuscript Generation")
    print("=" * 60)

    template_path = Path(__file__).parent / "paper" / "manuscript_template.md"
    output_path = output_dir / "manuscript.md"

    if not template_path.exists():
        print(f"Template not found at {template_path}")
        return None

    # Load results
    baseline_path = experiment_dir / "baseline" / "baseline_comparison.json"
    import json

    results_data = {}
    if baseline_path.exists():
        with open(baseline_path) as f:
            results_data["baseline"] = json.load(f)

    # Read template
    with open(template_path) as f:
        template = f.read()

    # Simple template substitution
    if "baseline" in results_data:
        metrics = results_data["baseline"]["metrics"]

        # Find best performer
        best = max(metrics.items(), key=lambda x: x[1]["f1_score"])
        template = template.replace("{{best_detector}}", best[0])
        template = template.replace("{{best_f1}}", f"{best[1]['f1_score']:.3f}")
        template = template.replace("{{best_recall}}", f"{best[1]['recall']:.3f}")

        # Ensemble stats
        if "ensemble" in metrics:
            template = template.replace("{{ensemble_f1}}", f"{metrics['ensemble']['f1_score']:.3f}")
            template = template.replace("{{ensemble_mae}}", f"{metrics['ensemble']['mean_abs_error']:.1f}")

    # Add timestamp
    template = template.replace("{{generation_date}}", datetime.now().strftime("%Y-%m-%d"))

    # Write output
    output_dir.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        f.write(template)

    print(f"Manuscript written to: {output_path}")

    return output_path


def main():
    parser = argparse.ArgumentParser(
        description="Nucleation Detection Research Pipeline"
    )
    parser.add_argument("--all", action="store_true", help="Run everything")
    parser.add_argument("--experiments", action="store_true", help="Run experiments")
    parser.add_argument("--ablation", action="store_true", help="Run ablation studies")
    parser.add_argument("--real-world", action="store_true", help="Run real-world validation")
    parser.add_argument("--figures", action="store_true", help="Generate figures")
    parser.add_argument("--manuscript", action="store_true", help="Generate manuscript")
    parser.add_argument("--n-simulations", type=int, default=100,
                       help="Number of simulations per experiment")
    parser.add_argument("--output-dir", type=str, default=None,
                       help="Output directory")

    args = parser.parse_args()

    # Default to --all if no args specified
    if not any([args.all, args.experiments, args.ablation,
                args.real_world, args.figures, args.manuscript]):
        args.all = True

    # Setup paths
    base_dir = Path(__file__).parent
    if args.output_dir:
        output_base = Path(args.output_dir)
    else:
        output_base = base_dir / "experiments"

    experiment_dir = output_base
    figures_dir = base_dir / "paper" / "figures"
    manuscript_dir = base_dir / "paper"
    data_dir = base_dir / "data"

    print("=" * 60)
    print("NUCLEATION DETECTION RESEARCH PIPELINE")
    print("=" * 60)
    print(f"Output directory: {output_base}")
    print(f"Simulations per experiment: {args.n_simulations}")

    # Run selected phases
    if args.all or args.experiments:
        run_baseline_experiments(
            experiment_dir / "baseline",
            n_simulations=args.n_simulations * 2,
        )

        run_per_transition_analysis(
            experiment_dir / "per_type",
            n_simulations=args.n_simulations,
        )

    if args.all or args.ablation:
        run_ablation_studies(
            experiment_dir / "ablation",
            n_simulations=args.n_simulations // 2,
        )

    if args.all or args.real_world:
        run_real_world_validation(
            experiment_dir / "real_world",
            data_dir,
        )

    if args.all or args.figures:
        generate_figures(figures_dir, experiment_dir)

    if args.all or args.manuscript:
        generate_manuscript(manuscript_dir, experiment_dir)

    print("\n" + "=" * 60)
    print("PIPELINE COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()
