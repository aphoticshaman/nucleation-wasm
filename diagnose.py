#!/usr/bin/env python3
"""
Diagnostic analysis of nucleation detection failure modes.
Identifies why F1 is low and what needs fixing.
"""
import numpy as np
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from simulators.phase_transitions import (
    simulate, SimulationConfig, TransitionType, compute_variance_trajectory
)
from detectors.nucleation_detectors import create_detector, DetectorType


def analyze_variance_dynamics():
    """Check if variance actually reduces before transitions."""
    print("=" * 70)
    print("DIAGNOSTIC 1: Does variance actually REDUCE before transitions?")
    print("=" * 70)

    results = {ttype: {"reduces": 0, "increases": 0, "flat": 0} for ttype in TransitionType}

    for ttype in TransitionType:
        print(f"\n{ttype.value.upper()}:")

        for seed in range(20):
            config = SimulationConfig(
                transition_type=ttype,
                duration=1000,
                noise_level=0.1,
                seed=seed,
            )
            sim = simulate(config)
            var_traj = compute_variance_trajectory(sim.state, window=30)

            trans_idx = sim.transition_index

            # Compare variance windows before transition
            if trans_idx > 100:
                far_before = var_traj[trans_idx - 80:trans_idx - 50]
                just_before = var_traj[trans_idx - 30:trans_idx]

                far_var = np.nanmean(far_before)
                just_var = np.nanmean(just_before)

                if far_var > 0 and just_var > 0:
                    change = (just_var - far_var) / far_var
                    if change < -0.1:
                        results[ttype]["reduces"] += 1
                    elif change > 0.1:
                        results[ttype]["increases"] += 1
                    else:
                        results[ttype]["flat"] += 1

        r = results[ttype]
        total = r["reduces"] + r["increases"] + r["flat"]
        if total > 0:
            print(f"  Reduces: {r['reduces']:3d} ({100*r['reduces']/total:.0f}%)")
            print(f"  Increases: {r['increases']:3d} ({100*r['increases']/total:.0f}%)")
            print(f"  Flat: {r['flat']:3d} ({100*r['flat']/total:.0f}%)")


def analyze_transition_detection_accuracy():
    """Check where true transitions actually occur vs where simulators say."""
    print("\n" + "=" * 70)
    print("DIAGNOSTIC 2: Transition detection accuracy in simulators")
    print("=" * 70)

    for ttype in TransitionType:
        print(f"\n{ttype.value.upper()}:")

        for seed in range(5):
            config = SimulationConfig(
                transition_type=ttype,
                duration=1000,
                noise_level=0.1,
                seed=seed,
            )
            sim = simulate(config)

            # Find actual state change
            state = sim.state
            abs_state = np.abs(state)

            # Rolling mean of absolute state
            window = 30
            rolling_abs = np.array([np.mean(abs_state[max(0,i-window):i+1])
                                   for i in range(len(state))])

            # Find where state first consistently exceeds early baseline
            baseline = np.mean(rolling_abs[:100])
            threshold = baseline * 3
            actual_crossings = np.where(rolling_abs > threshold)[0]
            actual_trans = actual_crossings[0] if len(actual_crossings) > 0 else -1

            reported = sim.transition_index
            error = actual_trans - reported if actual_trans > 0 else "N/A"

            print(f"  Seed {seed}: reported={reported:4d}, state-based={actual_trans}, error={error}")


def analyze_detector_triggering():
    """Understand when and why detectors trigger."""
    print("\n" + "=" * 70)
    print("DIAGNOSTIC 3: Detector triggering patterns")
    print("=" * 70)

    for ttype in TransitionType:
        print(f"\n{ttype.value.upper()}:")

        config = SimulationConfig(
            transition_type=ttype,
            duration=1000,
            noise_level=0.1,
            seed=42,
        )
        sim = simulate(config)
        true_trans = sim.transition_index

        for dtype in [DetectorType.VARIANCE_RATIO, DetectorType.CUSUM, DetectorType.ENSEMBLE]:
            detector = create_detector(dtype)
            result = detector.detect(sim.state)

            if result.detected:
                det_idx = result.detection_index
                error = det_idx - true_trans
                timing = "EARLY" if error < -30 else "LATE" if error > 30 else "OK"
                print(f"  {dtype.value:20s}: idx={det_idx:4d}, true={true_trans:4d}, "
                      f"error={error:+4d} [{timing}] conf={result.confidence:.2f}")
            else:
                print(f"  {dtype.value:20s}: NOT DETECTED (true={true_trans})")


def analyze_false_positives():
    """Check what causes false positives - early detections due to noise."""
    print("\n" + "=" * 70)
    print("DIAGNOSTIC 4: False positive analysis (early triggers)")
    print("=" * 70)

    early_triggers = {dtype: 0 for dtype in DetectorType}
    late_triggers = {dtype: 0 for dtype in DetectorType}
    correct_triggers = {dtype: 0 for dtype in DetectorType}
    no_detect = {dtype: 0 for dtype in DetectorType}
    total = 0

    for ttype in TransitionType:
        for seed in range(25):
            config = SimulationConfig(
                transition_type=ttype,
                duration=1000,
                noise_level=0.15,
                seed=seed,
            )
            sim = simulate(config)
            true_trans = sim.transition_index
            total += 1

            for dtype in DetectorType:
                detector = create_detector(dtype)
                result = detector.detect(sim.state)

                if result.detected and result.detection_index is not None:
                    error = result.detection_index - true_trans
                    if error < -50:
                        early_triggers[dtype] += 1
                    elif error > 50:
                        late_triggers[dtype] += 1
                    else:
                        correct_triggers[dtype] += 1
                else:
                    no_detect[dtype] += 1

    print(f"\nResults across {total} simulations:")
    print(f"{'Detector':<25} {'Early':>8} {'Correct':>8} {'Late':>8} {'Missed':>8}")
    print("-" * 60)

    for dtype in DetectorType:
        print(f"{dtype.value:<25} {early_triggers[dtype]:>8} {correct_triggers[dtype]:>8} "
              f"{late_triggers[dtype]:>8} {no_detect[dtype]:>8}")

    # Calculate what's hurting F1 most
    print("\n--- Root Cause Analysis ---")
    for dtype in DetectorType:
        e = early_triggers[dtype]
        c = correct_triggers[dtype]
        l = late_triggers[dtype]
        m = no_detect[dtype]

        precision = c / (e + c + l) if (e + c + l) > 0 else 0
        recall = c / (c + l + m) if (c + l + m) > 0 else 0  # late = wrong, missed = missed

        main_issue = "EARLY TRIGGERS" if e > max(l, m) else "MISSES" if m > l else "LATE"
        print(f"{dtype.value:<25}: P={precision:.2f}, R={recall:.2f} -> Main issue: {main_issue}")


def check_threshold_sensitivity():
    """Check if thresholds are too aggressive."""
    print("\n" + "=" * 70)
    print("DIAGNOSTIC 5: Threshold sensitivity analysis")
    print("=" * 70)

    # Test variance ratio detector with different thresholds
    thresholds = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8]

    for thresh in thresholds:
        correct = 0
        early = 0
        late = 0
        missed = 0

        for ttype in TransitionType:
            for seed in range(10):
                config = SimulationConfig(
                    transition_type=ttype,
                    duration=1000,
                    noise_level=0.1,
                    seed=seed,
                )
                sim = simulate(config)

                from detectors.nucleation_detectors import VarianceRatioDetector
                detector = VarianceRatioDetector(threshold=thresh)
                result = detector.detect(sim.state)

                if result.detected and result.detection_index is not None:
                    error = result.detection_index - sim.transition_index
                    if error < -50:
                        early += 1
                    elif error > 50:
                        late += 1
                    else:
                        correct += 1
                else:
                    missed += 1

        total = correct + early + late + missed
        print(f"Threshold {thresh:.1f}: correct={correct:3d} ({100*correct/total:.0f}%), "
              f"early={early:3d}, late={late:3d}, missed={missed:3d}")


if __name__ == "__main__":
    analyze_variance_dynamics()
    analyze_transition_detection_accuracy()
    analyze_detector_triggering()
    analyze_false_positives()
    check_threshold_sensitivity()

    print("\n" + "=" * 70)
    print("DIAGNOSTIC COMPLETE - Review output to identify refactoring priorities")
    print("=" * 70)
