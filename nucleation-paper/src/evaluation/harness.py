"""
Evaluation Harness for Nucleation Detection
Runs systematic experiments and computes performance metrics.

Author: Ryan J Cardwell (Archer Phoenix)
Version: 1.0.0
"""
import numpy as np
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from pathlib import Path
import json
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from simulators.phase_transitions import (
    simulate, SimulationConfig, SimulationResult, TransitionType, generate_dataset
)
from detectors.nucleation_detectors import (
    create_detector, DetectorType, DetectionResult, BaseDetector
)


@dataclass
class EvaluationMetrics:
    """Metrics for a single detector on a dataset."""
    detector_type: DetectorType
    true_positives: int = 0
    false_positives: int = 0
    false_negatives: int = 0
    true_negatives: int = 0

    # Detection timing
    mean_detection_error: float = 0.0  # Mean signed error (early = negative)
    std_detection_error: float = 0.0
    mean_abs_error: float = 0.0  # Mean absolute error
    median_abs_error: float = 0.0

    # Confidence calibration
    mean_confidence: float = 0.0
    confidence_correlation: float = 0.0  # Correlation between confidence and accuracy

    # Per-transition-type breakdown
    per_type_metrics: Dict[str, Dict[str, float]] = field(default_factory=dict)

    # Timing
    mean_runtime_ms: float = 0.0

    @property
    def precision(self) -> float:
        denom = self.true_positives + self.false_positives
        return self.true_positives / denom if denom > 0 else 0.0

    @property
    def recall(self) -> float:
        denom = self.true_positives + self.false_negatives
        return self.true_positives / denom if denom > 0 else 0.0

    @property
    def f1_score(self) -> float:
        p, r = self.precision, self.recall
        return 2 * p * r / (p + r) if (p + r) > 0 else 0.0

    @property
    def accuracy(self) -> float:
        total = self.true_positives + self.false_positives + self.true_negatives + self.false_negatives
        return (self.true_positives + self.true_negatives) / total if total > 0 else 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "detector_type": self.detector_type.value,
            "true_positives": self.true_positives,
            "false_positives": self.false_positives,
            "false_negatives": self.false_negatives,
            "true_negatives": self.true_negatives,
            "precision": self.precision,
            "recall": self.recall,
            "f1_score": self.f1_score,
            "accuracy": self.accuracy,
            "mean_detection_error": self.mean_detection_error,
            "std_detection_error": self.std_detection_error,
            "mean_abs_error": self.mean_abs_error,
            "median_abs_error": self.median_abs_error,
            "mean_confidence": self.mean_confidence,
            "confidence_correlation": self.confidence_correlation,
            "mean_runtime_ms": self.mean_runtime_ms,
            "per_type_metrics": self.per_type_metrics,
        }


@dataclass
class ExperimentConfig:
    """Configuration for an evaluation experiment."""
    name: str
    detector_types: List[DetectorType]
    detector_params: Dict[DetectorType, Dict[str, Any]]
    n_simulations: int = 100
    transition_types: Optional[List[TransitionType]] = None
    noise_levels: List[float] = field(default_factory=lambda: [0.05, 0.1, 0.15, 0.2, 0.3])
    durations: Tuple[int, int] = (500, 2000)
    detection_tolerance: int = 50  # Frames within which detection is "correct"
    seed: int = 42
    n_workers: int = 4


@dataclass
class ExperimentResult:
    """Results from an evaluation experiment."""
    config: ExperimentConfig
    metrics: Dict[DetectorType, EvaluationMetrics]
    detailed_results: List[Dict[str, Any]]
    timestamp: str
    total_runtime_s: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "config": {
                "name": self.config.name,
                "n_simulations": self.config.n_simulations,
                "noise_levels": self.config.noise_levels,
                "durations": self.config.durations,
                "detection_tolerance": self.config.detection_tolerance,
                "seed": self.config.seed,
            },
            "metrics": {k.value: v.to_dict() for k, v in self.metrics.items()},
            "timestamp": self.timestamp,
            "total_runtime_s": self.total_runtime_s,
        }

    def save(self, path: Path) -> None:
        """Save results to JSON file."""
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)


class EvaluationHarness:
    """Main harness for running nucleation detection experiments."""

    def __init__(self, config: ExperimentConfig):
        self.config = config
        self.detectors: Dict[DetectorType, BaseDetector] = {}

        # Create detectors
        for dtype in config.detector_types:
            params = config.detector_params.get(dtype, {})
            self.detectors[dtype] = create_detector(dtype, **params)

    def evaluate_single(
        self,
        simulation: SimulationResult,
        detector: BaseDetector,
    ) -> Tuple[DetectionResult, float]:
        """
        Evaluate a single detector on a single simulation.

        Returns:
            (detection_result, runtime_ms)
        """
        start = time.perf_counter()
        result = detector.detect(simulation.state)
        runtime = (time.perf_counter() - start) * 1000

        return result, runtime

    def run_experiment(self) -> ExperimentResult:
        """Run the full experiment."""
        start_time = time.time()

        # Generate dataset
        print(f"Generating {self.config.n_simulations} simulations...")
        dataset = generate_dataset(
            n_simulations=self.config.n_simulations,
            transition_types=self.config.transition_types,
            noise_levels=self.config.noise_levels,
            durations=self.config.durations,
            seed=self.config.seed,
        )

        # Initialize metrics
        metrics = {dtype: EvaluationMetrics(detector_type=dtype)
                  for dtype in self.config.detector_types}

        detailed_results = []

        # Track per-type and detection errors
        detection_errors: Dict[DetectorType, List[int]] = {
            dtype: [] for dtype in self.config.detector_types
        }
        confidences: Dict[DetectorType, List[Tuple[float, bool]]] = {
            dtype: [] for dtype in self.config.detector_types
        }
        runtimes: Dict[DetectorType, List[float]] = {
            dtype: [] for dtype in self.config.detector_types
        }
        per_type_errors: Dict[DetectorType, Dict[TransitionType, List[int]]] = {
            dtype: {ttype: [] for ttype in TransitionType}
            for dtype in self.config.detector_types
        }

        # Run evaluations
        print(f"Evaluating {len(self.config.detector_types)} detectors...")

        for i, sim in enumerate(dataset):
            if (i + 1) % 20 == 0:
                print(f"  Progress: {i+1}/{len(dataset)}")

            sim_result = {
                "simulation_id": i,
                "transition_type": sim.transition_type.value,
                "true_transition_index": sim.transition_index,
                "duration": sim.config.duration,
                "noise_level": sim.config.noise_level,
                "detections": {},
            }

            for dtype, detector in self.detectors.items():
                detection, runtime = self.evaluate_single(sim, detector)
                runtimes[dtype].append(runtime)

                # Determine if detection is correct
                if detection.detected and detection.detection_index is not None:
                    error = detection.detection_index - sim.transition_index
                    within_tolerance = abs(error) <= self.config.detection_tolerance

                    if within_tolerance:
                        metrics[dtype].true_positives += 1
                        detection_errors[dtype].append(error)
                        per_type_errors[dtype][sim.transition_type].append(error)
                        confidences[dtype].append((detection.confidence, True))
                    else:
                        # Detected but too far from true transition
                        metrics[dtype].false_positives += 1
                        confidences[dtype].append((detection.confidence, False))
                else:
                    # Not detected - this is a miss
                    metrics[dtype].false_negatives += 1
                    confidences[dtype].append((0.0, False))

                sim_result["detections"][dtype.value] = {
                    "detected": detection.detected,
                    "index": detection.detection_index,
                    "confidence": detection.confidence,
                    "error": detection.detection_index - sim.transition_index
                            if detection.detection_index else None,
                }

            detailed_results.append(sim_result)

        # Compute aggregate metrics
        for dtype in self.config.detector_types:
            errors = detection_errors[dtype]
            if len(errors) > 0:
                metrics[dtype].mean_detection_error = float(np.mean(errors))
                metrics[dtype].std_detection_error = float(np.std(errors))
                metrics[dtype].mean_abs_error = float(np.mean(np.abs(errors)))
                metrics[dtype].median_abs_error = float(np.median(np.abs(errors)))

            # Confidence stats
            confs = confidences[dtype]
            if len(confs) > 0:
                metrics[dtype].mean_confidence = float(np.mean([c for c, _ in confs]))

                # Confidence-accuracy correlation
                conf_vals = np.array([c for c, _ in confs])
                correct_vals = np.array([1 if correct else 0 for _, correct in confs])
                if np.std(conf_vals) > 0 and np.std(correct_vals) > 0:
                    metrics[dtype].confidence_correlation = float(
                        np.corrcoef(conf_vals, correct_vals)[0, 1]
                    )

            # Runtime
            metrics[dtype].mean_runtime_ms = float(np.mean(runtimes[dtype]))

            # Per-type breakdown
            for ttype in TransitionType:
                type_errors = per_type_errors[dtype][ttype]
                if len(type_errors) > 0:
                    metrics[dtype].per_type_metrics[ttype.value] = {
                        "n_correct": len(type_errors),
                        "mean_error": float(np.mean(type_errors)),
                        "std_error": float(np.std(type_errors)),
                        "mean_abs_error": float(np.mean(np.abs(type_errors))),
                    }

        total_runtime = time.time() - start_time
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")

        return ExperimentResult(
            config=self.config,
            metrics=metrics,
            detailed_results=detailed_results,
            timestamp=timestamp,
            total_runtime_s=total_runtime,
        )


def run_ablation_study(
    base_config: ExperimentConfig,
    ablation_variable: str,
    ablation_values: List[Any],
    output_dir: Path,
) -> List[ExperimentResult]:
    """
    Run ablation study varying one parameter.

    Args:
        base_config: Base experiment configuration
        ablation_variable: Parameter to vary (e.g., "noise_levels", "n_simulations")
        ablation_values: Values to test
        output_dir: Directory to save results

    Returns:
        List of experiment results
    """
    results = []
    output_dir.mkdir(parents=True, exist_ok=True)

    for i, value in enumerate(ablation_values):
        print(f"\nAblation {i+1}/{len(ablation_values)}: {ablation_variable}={value}")

        # Create modified config
        config_dict = {
            "name": f"{base_config.name}_{ablation_variable}_{i}",
            "detector_types": base_config.detector_types,
            "detector_params": base_config.detector_params,
            "n_simulations": base_config.n_simulations,
            "transition_types": base_config.transition_types,
            "noise_levels": base_config.noise_levels,
            "durations": base_config.durations,
            "detection_tolerance": base_config.detection_tolerance,
            "seed": base_config.seed + i,  # Different seed for each
        }

        # Apply ablation
        if ablation_variable == "noise_levels":
            config_dict["noise_levels"] = [value]
        elif ablation_variable == "window":
            config_dict["detector_params"] = {
                dtype: {**params, "window": value}
                for dtype, params in base_config.detector_params.items()
            }
        elif ablation_variable == "duration":
            config_dict["durations"] = (value, value + 1)
        else:
            raise ValueError(f"Unknown ablation variable: {ablation_variable}")

        config = ExperimentConfig(**config_dict)

        # Run experiment
        harness = EvaluationHarness(config)
        result = harness.run_experiment()
        results.append(result)

        # Save individual result
        result.save(output_dir / f"ablation_{ablation_variable}_{i}.json")

    # Save summary
    summary = {
        "ablation_variable": ablation_variable,
        "ablation_values": ablation_values,
        "results": [
            {
                "value": v,
                "metrics": {
                    dtype.value: {
                        "precision": r.metrics[dtype].precision,
                        "recall": r.metrics[dtype].recall,
                        "f1": r.metrics[dtype].f1_score,
                        "mean_abs_error": r.metrics[dtype].mean_abs_error,
                    }
                    for dtype in base_config.detector_types
                },
            }
            for v, r in zip(ablation_values, results)
        ],
    }

    with open(output_dir / f"ablation_{ablation_variable}_summary.json", "w") as f:
        json.dump(summary, f, indent=2)

    return results


def compare_detectors(
    n_simulations: int = 200,
    seed: int = 42,
    output_path: Optional[Path] = None,
) -> ExperimentResult:
    """
    Run comprehensive detector comparison.
    """
    config = ExperimentConfig(
        name="detector_comparison",
        detector_types=list(DetectorType),
        detector_params={},  # Use defaults
        n_simulations=n_simulations,
        noise_levels=[0.05, 0.1, 0.15, 0.2, 0.3],
        durations=(500, 2000),
        detection_tolerance=50,
        seed=seed,
    )

    harness = EvaluationHarness(config)
    result = harness.run_experiment()

    if output_path:
        result.save(output_path)

    return result


def print_results_table(result: ExperimentResult) -> None:
    """Print formatted results table."""
    print("\n" + "=" * 90)
    print(f"EXPERIMENT: {result.config.name}")
    print(f"Timestamp: {result.timestamp}")
    print(f"Runtime: {result.total_runtime_s:.1f}s")
    print("=" * 90)

    print(f"\n{'Detector':<25} {'Prec':>7} {'Recall':>7} {'F1':>7} "
          f"{'MAE':>7} {'Conf':>7} {'Runtime':>10}")
    print("-" * 90)

    for dtype in result.config.detector_types:
        m = result.metrics[dtype]
        print(f"{dtype.value:<25} {m.precision:>7.3f} {m.recall:>7.3f} {m.f1_score:>7.3f} "
              f"{m.mean_abs_error:>7.1f} {m.mean_confidence:>7.3f} {m.mean_runtime_ms:>8.2f}ms")

    print("-" * 90)

    # Per-type breakdown
    print("\nPer-Transition-Type Breakdown (Mean Absolute Error):")
    print(f"\n{'Detector':<25}", end="")
    for ttype in TransitionType:
        print(f" {ttype.value[:10]:>10}", end="")
    print()
    print("-" * 90)

    for dtype in result.config.detector_types:
        m = result.metrics[dtype]
        print(f"{dtype.value:<25}", end="")
        for ttype in TransitionType:
            if ttype.value in m.per_type_metrics:
                mae = m.per_type_metrics[ttype.value]["mean_abs_error"]
                print(f" {mae:>10.1f}", end="")
            else:
                print(f" {'N/A':>10}", end="")
        print()


if __name__ == "__main__":
    # Run detector comparison
    print("Running nucleation detector evaluation...")

    output_dir = Path(__file__).parent.parent.parent / "experiments" / "baseline"
    output_dir.mkdir(parents=True, exist_ok=True)

    result = compare_detectors(
        n_simulations=100,
        seed=42,
        output_path=output_dir / "baseline_comparison.json",
    )

    print_results_table(result)

    # Run noise ablation
    print("\n\nRunning noise level ablation study...")

    base_config = ExperimentConfig(
        name="noise_ablation",
        detector_types=[DetectorType.VARIANCE_RATIO, DetectorType.ENSEMBLE],
        detector_params={},
        n_simulations=50,
        detection_tolerance=50,
        seed=42,
    )

    ablation_results = run_ablation_study(
        base_config=base_config,
        ablation_variable="noise_levels",
        ablation_values=[0.01, 0.05, 0.1, 0.2, 0.3, 0.5],
        output_dir=output_dir / "noise_ablation",
    )

    print("\nNoise Ablation Summary:")
    print(f"{'Noise':>8} {'VarRatio F1':>12} {'Ensemble F1':>12}")
    print("-" * 35)
    for noise, res in zip([0.01, 0.05, 0.1, 0.2, 0.3, 0.5], ablation_results):
        vr_f1 = res.metrics[DetectorType.VARIANCE_RATIO].f1_score
        ens_f1 = res.metrics[DetectorType.ENSEMBLE].f1_score
        print(f"{noise:>8.2f} {vr_f1:>12.3f} {ens_f1:>12.3f}")
