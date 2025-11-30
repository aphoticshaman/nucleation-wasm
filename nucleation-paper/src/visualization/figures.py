"""
Figure Generation for Nucleation Detection Paper
Creates publication-ready figures for demonstrating variance reduction hypothesis.

Author: Ryan J Cardwell (Archer Phoenix)
Version: 1.0.0
"""
import numpy as np
from pathlib import Path
from typing import List, Dict, Optional, Any
import json

# Check for matplotlib availability
try:
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    from matplotlib.gridspec import GridSpec
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False
    print("Warning: matplotlib not available. Figure generation disabled.")

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from simulators.phase_transitions import (
    simulate, SimulationConfig, SimulationResult, TransitionType,
    compute_variance_trajectory
)
from detectors.nucleation_detectors import (
    create_detector, DetectorType, DetectionResult
)


# Publication-quality style settings
STYLE = {
    "figure.figsize": (10, 6),
    "font.size": 11,
    "font.family": "serif",
    "axes.labelsize": 12,
    "axes.titlesize": 13,
    "legend.fontsize": 10,
    "xtick.labelsize": 10,
    "ytick.labelsize": 10,
    "lines.linewidth": 1.5,
    "axes.linewidth": 1.0,
    "axes.grid": True,
    "grid.alpha": 0.3,
    "figure.dpi": 150,
}

# Color palette
COLORS = {
    "state": "#1f77b4",
    "variance": "#ff7f0e",
    "control": "#2ca02c",
    "detection": "#d62728",
    "true_transition": "#9467bd",
    "pitchfork": "#1f77b4",
    "saddle_node": "#ff7f0e",
    "hopf": "#2ca02c",
    "transcritical": "#d62728",
}


def apply_style():
    """Apply publication style to matplotlib."""
    if HAS_MATPLOTLIB:
        plt.rcParams.update(STYLE)


def plot_simulation(
    result: SimulationResult,
    output_path: Optional[Path] = None,
    show_variance: bool = True,
    show_control: bool = True,
    figsize: tuple = (12, 8),
) -> Optional[Any]:
    """
    Plot a single simulation with state, variance, and control parameter.
    """
    if not HAS_MATPLOTLIB:
        print("matplotlib not available")
        return None

    apply_style()

    n_plots = 1 + int(show_variance) + int(show_control)
    fig, axes = plt.subplots(n_plots, 1, figsize=figsize, sharex=True)
    if n_plots == 1:
        axes = [axes]

    time = result.time
    ax_idx = 0

    # State plot
    ax = axes[ax_idx]
    ax.plot(time, result.state, color=COLORS["state"], label="State x(t)")
    ax.axvline(time[result.transition_index], color=COLORS["true_transition"],
               linestyle="--", linewidth=2, label="True transition")
    ax.set_ylabel("State")
    ax.legend(loc="upper left")
    ax.set_title(f"{result.transition_type.value.replace('_', ' ').title()} Bifurcation")
    ax_idx += 1

    # Variance plot
    if show_variance:
        ax = axes[ax_idx]
        variance = compute_variance_trajectory(result.state, window=50)
        ax.plot(time, variance, color=COLORS["variance"], label="Rolling Variance")
        ax.axvline(time[result.transition_index], color=COLORS["true_transition"],
                   linestyle="--", linewidth=2)

        # Highlight variance reduction zone
        trans_idx = result.transition_index
        pre_start = max(0, trans_idx - 100)
        ax.axvspan(time[pre_start], time[trans_idx], alpha=0.2, color=COLORS["variance"],
                   label="Pre-transition zone")

        ax.set_ylabel("Variance")
        ax.legend(loc="upper left")
        ax_idx += 1

    # Control parameter
    if show_control:
        ax = axes[ax_idx]
        ax.plot(time, result.control_param, color=COLORS["control"],
                label="Control parameter r(t)")
        ax.axvline(time[result.transition_index], color=COLORS["true_transition"],
                   linestyle="--", linewidth=2)
        ax.set_ylabel("Control")
        ax.legend(loc="upper left")

    axes[-1].set_xlabel("Time")

    plt.tight_layout()

    if output_path:
        plt.savefig(output_path, dpi=300, bbox_inches="tight")
        print(f"Saved: {output_path}")

    return fig


def plot_variance_reduction_phenomenon(
    output_path: Optional[Path] = None,
    seed: int = 42,
) -> Optional[Any]:
    """
    Create the key figure demonstrating variance REDUCTION before transitions.
    Shows all four bifurcation types side by side.
    """
    if not HAS_MATPLOTLIB:
        print("matplotlib not available")
        return None

    apply_style()

    fig = plt.figure(figsize=(14, 15))
    gs = GridSpec(6, 2, figure=fig, hspace=0.3, wspace=0.25)

    transition_types = list(TransitionType)

    for i, ttype in enumerate(transition_types):
        config = SimulationConfig(
            transition_type=ttype,
            duration=1000,
            noise_level=0.1,
            seed=seed + i,
        )
        result = simulate(config)
        variance = compute_variance_trajectory(result.state, window=50)

        # State subplot
        ax_state = fig.add_subplot(gs[i, 0])
        ax_state.plot(result.time, result.state, color=COLORS.get(ttype.value, COLORS["state"]))
        ax_state.axvline(result.time[result.transition_index],
                         color=COLORS["true_transition"], linestyle="--", linewidth=2)
        ax_state.set_ylabel("State")
        ax_state.set_title(f"{ttype.value.replace('_', ' ').title()}")
        if i == len(transition_types) - 1:
            ax_state.set_xlabel("Time")

        # Variance subplot
        ax_var = fig.add_subplot(gs[i, 1])
        ax_var.plot(result.time, variance, color=COLORS["variance"])
        ax_var.axvline(result.time[result.transition_index],
                       color=COLORS["true_transition"], linestyle="--", linewidth=2)

        # Mark variance reduction
        trans_idx = result.transition_index
        pre_start = max(50, trans_idx - 80)
        if trans_idx > pre_start:
            pre_var = np.nanmean(variance[pre_start:trans_idx-20])
            at_var = np.nanmean(variance[trans_idx-20:trans_idx])
            if pre_var > 0:
                reduction = (pre_var - at_var) / pre_var * 100
                ax_var.annotate(f"↓{reduction:.0f}%",
                               xy=(result.time[trans_idx-10], at_var),
                               fontsize=10, color=COLORS["detection"])

        ax_var.set_ylabel("Variance")
        if i == len(transition_types) - 1:
            ax_var.set_xlabel("Time")

    fig.suptitle("Variance Reduction Before Phase Transitions", fontsize=14, y=1.02)

    if output_path:
        plt.savefig(output_path, dpi=300, bbox_inches="tight")
        print(f"Saved: {output_path}")

    return fig


def plot_detection_comparison(
    n_examples: int = 4,
    output_path: Optional[Path] = None,
    seed: int = 42,
) -> Optional[Any]:
    """
    Compare different detectors on same simulations.
    """
    if not HAS_MATPLOTLIB:
        print("matplotlib not available")
        return None

    apply_style()

    fig = plt.figure(figsize=(14, 12))

    detectors = [
        ("Variance Ratio", DetectorType.VARIANCE_RATIO),
        ("CUSUM", DetectorType.CUSUM),
        ("Ensemble", DetectorType.ENSEMBLE),
    ]

    for i, ttype in enumerate(list(TransitionType)[:n_examples]):
        config = SimulationConfig(
            transition_type=ttype,
            duration=1000,
            noise_level=0.15,
            seed=seed + i,
        )
        result = simulate(config)

        ax = fig.add_subplot(n_examples, 1, i + 1)

        # Plot state
        ax.plot(result.time, result.state, color=COLORS["state"], alpha=0.7, label="State")

        # True transition
        ax.axvline(result.time[result.transition_index], color=COLORS["true_transition"],
                   linestyle="-", linewidth=2, label="True transition")

        # Detector predictions
        line_styles = ["--", "-.", ":"]
        for (name, dtype), ls in zip(detectors, line_styles):
            detector = create_detector(dtype)
            detection = detector.detect(result.state)
            if detection.detected and detection.detection_index is not None:
                ax.axvline(result.time[detection.detection_index],
                          linestyle=ls, linewidth=1.5,
                          label=f"{name} ({detection.detection_index - result.transition_index:+d})")

        ax.set_ylabel("State")
        ax.set_title(f"{ttype.value.replace('_', ' ').title()} Bifurcation")
        ax.legend(loc="upper right", fontsize=8)

    plt.xlabel("Time")
    plt.tight_layout()

    if output_path:
        plt.savefig(output_path, dpi=300, bbox_inches="tight")
        print(f"Saved: {output_path}")

    return fig


def plot_ablation_results(
    results_path: Path,
    output_path: Optional[Path] = None,
) -> Optional[Any]:
    """
    Plot results from ablation study.
    """
    if not HAS_MATPLOTLIB:
        print("matplotlib not available")
        return None

    apply_style()

    with open(results_path) as f:
        data = json.load(f)

    variable = data["ablation_variable"]
    values = data["ablation_values"]
    results = data["results"]

    fig, axes = plt.subplots(1, 2, figsize=(12, 5))

    # F1 Score plot
    ax = axes[0]
    for dtype_str in results[0]["metrics"].keys():
        f1_scores = [r["metrics"][dtype_str]["f1"] for r in results]
        ax.plot(values, f1_scores, marker="o", label=dtype_str)
    ax.set_xlabel(variable.replace("_", " ").title())
    ax.set_ylabel("F1 Score")
    ax.set_title("Detection Performance vs " + variable.replace("_", " ").title())
    ax.legend()
    ax.grid(True, alpha=0.3)

    # Mean Absolute Error plot
    ax = axes[1]
    for dtype_str in results[0]["metrics"].keys():
        mae = [r["metrics"][dtype_str]["mean_abs_error"] for r in results]
        ax.plot(values, mae, marker="s", label=dtype_str)
    ax.set_xlabel(variable.replace("_", " ").title())
    ax.set_ylabel("Mean Absolute Error (frames)")
    ax.set_title("Timing Accuracy vs " + variable.replace("_", " ").title())
    ax.legend()
    ax.grid(True, alpha=0.3)

    plt.tight_layout()

    if output_path:
        plt.savefig(output_path, dpi=300, bbox_inches="tight")
        print(f"Saved: {output_path}")

    return fig


def plot_metrics_summary(
    experiment_path: Path,
    output_path: Optional[Path] = None,
) -> Optional[Any]:
    """
    Create summary bar chart of detector performance metrics.
    """
    if not HAS_MATPLOTLIB:
        print("matplotlib not available")
        return None

    apply_style()

    with open(experiment_path) as f:
        data = json.load(f)

    metrics = data["metrics"]
    detector_names = list(metrics.keys())

    fig, axes = plt.subplots(1, 3, figsize=(14, 5))

    # Precision, Recall, F1
    x = np.arange(len(detector_names))
    width = 0.25

    prec = [metrics[d]["precision"] for d in detector_names]
    recall = [metrics[d]["recall"] for d in detector_names]
    f1 = [metrics[d]["f1_score"] for d in detector_names]

    ax = axes[0]
    bars1 = ax.bar(x - width, prec, width, label="Precision", color=COLORS["state"])
    bars2 = ax.bar(x, recall, width, label="Recall", color=COLORS["variance"])
    bars3 = ax.bar(x + width, f1, width, label="F1", color=COLORS["control"])
    ax.set_ylabel("Score")
    ax.set_title("Detection Metrics")
    ax.set_xticks(x)
    ax.set_xticklabels([d.replace("_", "\n") for d in detector_names], fontsize=8)
    ax.legend()
    ax.set_ylim(0, 1)

    # Mean Absolute Error
    ax = axes[1]
    mae = [metrics[d]["mean_abs_error"] for d in detector_names]
    ax.bar(x, mae, color=COLORS["detection"])
    ax.set_ylabel("Frames")
    ax.set_title("Mean Absolute Error")
    ax.set_xticks(x)
    ax.set_xticklabels([d.replace("_", "\n") for d in detector_names], fontsize=8)

    # Runtime
    ax = axes[2]
    runtime = [metrics[d]["mean_runtime_ms"] for d in detector_names]
    ax.bar(x, runtime, color=COLORS["true_transition"])
    ax.set_ylabel("ms")
    ax.set_title("Mean Runtime")
    ax.set_xticks(x)
    ax.set_xticklabels([d.replace("_", "\n") for d in detector_names], fontsize=8)

    plt.tight_layout()

    if output_path:
        plt.savefig(output_path, dpi=300, bbox_inches="tight")
        print(f"Saved: {output_path}")

    return fig


def create_all_figures(
    output_dir: Path,
    experiment_dir: Optional[Path] = None,
    seed: int = 42,
) -> Dict[str, Path]:
    """
    Generate all figures for the paper.

    Returns:
        Dictionary mapping figure name to output path
    """
    if not HAS_MATPLOTLIB:
        print("matplotlib not available - cannot generate figures")
        return {}

    output_dir.mkdir(parents=True, exist_ok=True)
    figures = {}

    # Figure 1: Variance reduction phenomenon
    path = output_dir / "fig1_variance_reduction.png"
    plot_variance_reduction_phenomenon(output_path=path, seed=seed)
    figures["variance_reduction"] = path

    # Figure 2: Example simulations for each type
    for ttype in TransitionType:
        config = SimulationConfig(
            transition_type=ttype,
            duration=1000,
            noise_level=0.1,
            seed=seed,
        )
        result = simulate(config)
        path = output_dir / f"fig2_{ttype.value}_example.png"
        plot_simulation(result, output_path=path)
        figures[f"{ttype.value}_example"] = path

    # Figure 3: Detector comparison
    path = output_dir / "fig3_detector_comparison.png"
    plot_detection_comparison(output_path=path, seed=seed)
    figures["detector_comparison"] = path

    # Figure 4: Metrics summary (if experiment results exist)
    if experiment_dir:
        baseline_path = experiment_dir / "baseline" / "baseline_comparison.json"
        if baseline_path.exists():
            path = output_dir / "fig4_metrics_summary.png"
            plot_metrics_summary(baseline_path, output_path=path)
            figures["metrics_summary"] = path

        # Figure 5: Ablation results
        ablation_path = experiment_dir / "baseline" / "noise_ablation" / "ablation_noise_levels_summary.json"
        if ablation_path.exists():
            path = output_dir / "fig5_noise_ablation.png"
            plot_ablation_results(ablation_path, output_path=path)
            figures["noise_ablation"] = path

    return figures


if __name__ == "__main__":
    # Generate all figures
    paper_dir = Path(__file__).parent.parent.parent
    figures_dir = paper_dir / "paper" / "figures"
    experiments_dir = paper_dir / "experiments"

    print("Generating figures for nucleation detection paper...")

    figures = create_all_figures(
        output_dir=figures_dir,
        experiment_dir=experiments_dir if experiments_dir.exists() else None,
        seed=42,
    )

    print(f"\nGenerated {len(figures)} figures:")
    for name, path in figures.items():
        print(f"  {name}: {path}")
