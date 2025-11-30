"""
Nucleation Detector Candidates v2.0
Improved detection algorithms based on diagnostic analysis.

Key improvements from v1:
- Sustained detection (not first crossing)
- Peak/inflection detection
- Adaptive thresholds
- Dual-direction variance change detection
- Better baseline estimation

Author: Ryan J Cardwell (Archer Phoenix)
Version: 2.0.0
"""
import numpy as np
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from abc import ABC, abstractmethod
from enum import Enum


class DetectorType(Enum):
    VARIANCE_RATIO = "variance_ratio"
    VARIANCE_DERIVATIVE = "variance_derivative"
    VARIANCE_INFLECTION = "variance_inflection"
    ENSEMBLE = "ensemble"
    ROLLING_ZSCORE = "rolling_zscore"
    CUSUM = "cusum"
    CHANGE_POINT = "change_point"


@dataclass
class DetectionResult:
    """Result from a nucleation detector."""
    detected: bool
    detection_index: Optional[int]
    confidence: float
    detector_type: DetectorType
    signal: np.ndarray
    threshold: float
    metadata: Dict[str, Any]


class BaseDetector(ABC):
    """Abstract base class for nucleation detectors."""

    def __init__(self, window: int = 50, threshold: float = 0.5):
        self.window = window
        self.threshold = threshold

    @abstractmethod
    def detect(self, signal: np.ndarray) -> DetectionResult:
        """Detect nucleation point in time series."""
        pass

    def compute_rolling_variance(self, signal: np.ndarray, window: Optional[int] = None) -> np.ndarray:
        """Compute rolling variance with given window."""
        w = window or self.window
        n = len(signal)
        variance = np.full(n, np.nan)
        for i in range(w, n):
            variance[i] = np.var(signal[i-w:i])
        return variance

    def compute_rolling_mean(self, signal: np.ndarray, window: Optional[int] = None) -> np.ndarray:
        """Compute rolling mean with given window."""
        w = window or self.window
        n = len(signal)
        mean = np.full(n, np.nan)
        for i in range(w, n):
            mean[i] = np.mean(signal[i-w:i])
        return mean

    def find_sustained_crossing(
        self,
        signal: np.ndarray,
        threshold: float,
        direction: str = "below",
        sustain_count: int = 10,
        start_idx: int = 0,
    ) -> Optional[int]:
        """
        Find first index where signal crosses threshold AND stays there.

        Args:
            signal: The signal to analyze
            threshold: Threshold value
            direction: "below" or "above"
            sustain_count: How many consecutive points must satisfy condition
            start_idx: Index to start searching from
        """
        n = len(signal)
        valid = ~np.isnan(signal)

        for i in range(max(start_idx, sustain_count), n - sustain_count):
            if not valid[i]:
                continue

            if direction == "below":
                check = signal[i:i+sustain_count] < threshold
            else:
                check = signal[i:i+sustain_count] > threshold

            # Check we have enough valid points
            if np.sum(~np.isnan(signal[i:i+sustain_count])) < sustain_count // 2:
                continue

            if np.nanmean(check) > 0.7:  # 70% must satisfy
                return i

        return None

    def find_peak(
        self,
        signal: np.ndarray,
        mode: str = "max",
        start_frac: float = 0.15,
        end_frac: float = 0.85,
    ) -> Optional[int]:
        """Find peak (max or min) in signal, excluding edges."""
        n = len(signal)
        start = int(n * start_frac)
        end = int(n * end_frac)

        valid = ~np.isnan(signal[start:end])
        if not np.any(valid):
            return None

        subsignal = signal[start:end].copy()
        subsignal[~valid] = np.nanmean(subsignal) if mode == "max" else np.nanmean(subsignal)

        if mode == "max":
            idx = np.argmax(subsignal)
        else:
            idx = np.argmin(subsignal)

        return start + idx


class VarianceRatioDetector(BaseDetector):
    """
    Detects transitions by comparing variance to adaptive baseline.

    Improved: Uses rolling baseline, sustained detection, bidirectional.
    """

    def __init__(
        self,
        window: int = 40,
        baseline_window: int = 80,
        threshold: float = 0.4,
        sustain: int = 15,
    ):
        super().__init__(window, threshold)
        self.baseline_window = baseline_window
        self.sustain = sustain

    def detect(self, signal: np.ndarray) -> DetectionResult:
        n = len(signal)
        variance = self.compute_rolling_variance(signal)

        # Compute rolling baseline (trailing window)
        baseline = np.full(n, np.nan)
        for i in range(self.baseline_window + self.window, n):
            baseline[i] = np.nanmean(variance[i-self.baseline_window:i-self.window//2])

        # Handle edge case
        baseline[np.isnan(baseline)] = np.nanmedian(variance[~np.isnan(variance)])

        # Avoid division by zero
        baseline = np.maximum(baseline, 1e-10)

        # Compute ratio
        ratio = variance / baseline

        # Find sustained deviation (either direction)
        detection_idx = None
        confidence = 0.0

        # Check for reduction
        idx_low = self.find_sustained_crossing(
            ratio, self.threshold, direction="below",
            sustain_count=self.sustain, start_idx=self.baseline_window
        )

        # Check for increase (CSD signature)
        idx_high = self.find_sustained_crossing(
            ratio, 1.0 / self.threshold, direction="above",
            sustain_count=self.sustain, start_idx=self.baseline_window
        )

        # Take earliest valid detection
        candidates = [i for i in [idx_low, idx_high] if i is not None]
        if candidates:
            detection_idx = min(candidates)
            r = ratio[detection_idx] if not np.isnan(ratio[detection_idx]) else 1.0
            confidence = abs(1.0 - r)
            detected = True
        else:
            detected = False

        return DetectionResult(
            detected=detected,
            detection_index=detection_idx,
            confidence=float(min(1.0, confidence)),
            detector_type=DetectorType.VARIANCE_RATIO,
            signal=ratio,
            threshold=self.threshold,
            metadata={
                "window": self.window,
                "baseline_window": self.baseline_window,
                "sustain": self.sustain,
            },
        )


class VarianceDerivativeDetector(BaseDetector):
    """
    Detects transitions via rate of change in variance.

    Improved: Finds peak in derivative magnitude, not first crossing.
    """

    def __init__(
        self,
        window: int = 40,
        derivative_window: int = 25,
        threshold: float = 0.3,
    ):
        super().__init__(window, threshold)
        self.derivative_window = derivative_window

    def detect(self, signal: np.ndarray) -> DetectionResult:
        variance = self.compute_rolling_variance(signal)
        n = len(variance)

        # Compute normalized derivative
        derivative = np.full(n, np.nan)
        for i in range(self.derivative_window + self.window, n):
            if np.isnan(variance[i]) or np.isnan(variance[i - self.derivative_window]):
                continue
            mean_var = np.nanmean(variance[i-self.derivative_window:i+1])
            if mean_var > 1e-10:
                derivative[i] = (variance[i] - variance[i - self.derivative_window]) / mean_var

        # Find peak in absolute derivative (fastest change)
        abs_deriv = np.abs(derivative)
        peak_idx = self.find_peak(abs_deriv, mode="max")

        if peak_idx is not None and not np.isnan(abs_deriv[peak_idx]):
            if abs_deriv[peak_idx] > self.threshold:
                detection_idx = peak_idx
                confidence = min(1.0, abs_deriv[peak_idx] / self.threshold)
                detected = True
            else:
                detection_idx = None
                confidence = 0.0
                detected = False
        else:
            detection_idx = None
            confidence = 0.0
            detected = False

        return DetectionResult(
            detected=detected,
            detection_index=detection_idx,
            confidence=float(confidence),
            detector_type=DetectorType.VARIANCE_DERIVATIVE,
            signal=derivative,
            threshold=self.threshold,
            metadata={
                "window": self.window,
                "derivative_window": self.derivative_window,
            },
        )


class VarianceInflectionDetector(BaseDetector):
    """
    Detects inflection points in variance trajectory.

    Finds where variance changes from increasing to decreasing (or vice versa).
    This captures both CSD (increase) and commitment (decrease) patterns.
    """

    def __init__(
        self,
        window: int = 40,
        smooth_window: int = 20,
        threshold: float = 0.2,
    ):
        super().__init__(window, threshold)
        self.smooth_window = smooth_window

    def detect(self, signal: np.ndarray) -> DetectionResult:
        variance = self.compute_rolling_variance(signal)
        n = len(variance)

        # Smooth the variance
        kernel = np.ones(self.smooth_window) / self.smooth_window
        valid_var = variance.copy()
        valid_var[np.isnan(valid_var)] = np.nanmedian(variance)
        smoothed = np.convolve(valid_var, kernel, mode='same')

        # First derivative (slope)
        d1 = np.gradient(smoothed)

        # Second derivative (curvature)
        d2 = np.gradient(d1)

        # Find zero crossings of first derivative (peaks/troughs in variance)
        # or peaks in second derivative magnitude (inflection points)
        inflection_signal = np.abs(d2)

        # Find the most prominent inflection
        peak_idx = self.find_peak(inflection_signal, mode="max")

        if peak_idx is not None:
            score = inflection_signal[peak_idx]
            # Normalize by typical variation
            typical = np.nanstd(inflection_signal)
            if typical > 1e-10:
                normalized_score = score / typical
            else:
                normalized_score = 0

            if normalized_score > self.threshold:
                detection_idx = peak_idx
                confidence = min(1.0, normalized_score / (self.threshold * 3))
                detected = True
            else:
                detection_idx = None
                confidence = 0.0
                detected = False
        else:
            detection_idx = None
            confidence = 0.0
            detected = False

        return DetectionResult(
            detected=detected,
            detection_index=detection_idx,
            confidence=float(confidence),
            detector_type=DetectorType.VARIANCE_INFLECTION,
            signal=inflection_signal,
            threshold=self.threshold,
            metadata={
                "window": self.window,
                "smooth_window": self.smooth_window,
            },
        )


class RollingZScoreDetector(BaseDetector):
    """
    Detects anomalous variance using adaptive z-score.

    Improved: Sustained anomaly detection, not first spike.
    """

    def __init__(
        self,
        window: int = 40,
        zscore_window: int = 80,
        threshold: float = 2.0,
        sustain: int = 10,
    ):
        super().__init__(window, threshold)
        self.zscore_window = zscore_window
        self.sustain = sustain

    def detect(self, signal: np.ndarray) -> DetectionResult:
        variance = self.compute_rolling_variance(signal)
        n = len(variance)
        zscore = np.full(n, np.nan)

        for i in range(self.zscore_window + self.window, n):
            window_data = variance[i-self.zscore_window:i-self.window//2]
            valid_data = window_data[~np.isnan(window_data)]

            if len(valid_data) > 10:
                mean = np.mean(valid_data)
                std = np.std(valid_data)

                if std > 1e-10 and not np.isnan(variance[i]):
                    zscore[i] = (variance[i] - mean) / std

        # Find sustained extreme z-score (either direction)
        abs_zscore = np.abs(zscore)

        detection_idx = self.find_sustained_crossing(
            abs_zscore, self.threshold, direction="above",
            sustain_count=self.sustain, start_idx=self.zscore_window
        )

        if detection_idx is not None:
            confidence = min(1.0, np.nanmean(abs_zscore[detection_idx:detection_idx+self.sustain]) / self.threshold)
            detected = True
        else:
            confidence = 0.0
            detected = False

        return DetectionResult(
            detected=detected,
            detection_index=detection_idx,
            confidence=float(confidence),
            detector_type=DetectorType.ROLLING_ZSCORE,
            signal=zscore,
            threshold=self.threshold,
            metadata={
                "window": self.window,
                "zscore_window": self.zscore_window,
                "sustain": self.sustain,
            },
        )


class CUSUMDetector(BaseDetector):
    """
    Cumulative Sum (CUSUM) detector for variance changes.

    Improved: Bidirectional detection, adaptive parameters.
    """

    def __init__(
        self,
        window: int = 40,
        drift: float = 0.3,
        threshold: float = 4.0,
    ):
        super().__init__(window, threshold)
        self.drift = drift

    def detect(self, signal: np.ndarray) -> DetectionResult:
        variance = self.compute_rolling_variance(signal)
        n = len(variance)

        valid_mask = ~np.isnan(variance)
        if np.sum(valid_mask) < 20:
            return DetectionResult(
                detected=False, detection_index=None, confidence=0.0,
                detector_type=DetectorType.CUSUM,
                signal=np.full(n, np.nan), threshold=self.threshold,
                metadata={"error": "insufficient_data"},
            )

        valid_variance = variance[valid_mask]

        # Adaptive baseline from first third
        baseline_n = max(10, len(valid_variance) // 3)
        mean = np.mean(valid_variance[:baseline_n])
        std = np.std(valid_variance[:baseline_n])
        if std < 1e-10:
            std = np.std(valid_variance)
        if std < 1e-10:
            std = 1.0

        standardized = (valid_variance - mean) / std

        # CUSUM for both directions
        cusum_pos = np.zeros(len(standardized))
        cusum_neg = np.zeros(len(standardized))

        for i in range(1, len(standardized)):
            cusum_pos[i] = max(0, cusum_pos[i-1] + standardized[i] - self.drift)
            cusum_neg[i] = min(0, cusum_neg[i-1] + standardized[i] + self.drift)

        # Map back to original indices
        cusum_combined = np.full(n, np.nan)
        # Use max of absolute values
        cusum_abs = np.maximum(cusum_pos, np.abs(cusum_neg))
        cusum_combined[valid_mask] = cusum_abs

        # Find first threshold crossing
        valid_indices = np.where(valid_mask)[0]
        for i, idx in enumerate(valid_indices):
            if cusum_abs[i] > self.threshold:
                detection_idx = idx
                confidence = min(1.0, cusum_abs[i] / self.threshold)
                return DetectionResult(
                    detected=True, detection_index=detection_idx,
                    confidence=float(confidence),
                    detector_type=DetectorType.CUSUM,
                    signal=cusum_combined, threshold=self.threshold,
                    metadata={"drift": self.drift, "baseline_mean": float(mean), "baseline_std": float(std)},
                )

        return DetectionResult(
            detected=False, detection_index=None, confidence=0.0,
            detector_type=DetectorType.CUSUM,
            signal=cusum_combined, threshold=self.threshold,
            metadata={"drift": self.drift},
        )


class ChangePointDetector(BaseDetector):
    """
    Detects change points using likelihood ratio approach.

    Tests whether splitting signal at each point improves fit.
    """

    def __init__(
        self,
        window: int = 40,
        min_segment: int = 50,
        threshold: float = 0.3,
    ):
        super().__init__(window, threshold)
        self.min_segment = min_segment

    def detect(self, signal: np.ndarray) -> DetectionResult:
        variance = self.compute_rolling_variance(signal)
        n = len(variance)

        valid = ~np.isnan(variance)
        if np.sum(valid) < 2 * self.min_segment:
            return DetectionResult(
                detected=False, detection_index=None, confidence=0.0,
                detector_type=DetectorType.CHANGE_POINT,
                signal=np.zeros(n), threshold=self.threshold,
                metadata={"error": "insufficient_data"},
            )

        # Compute log-likelihood ratio for each potential change point
        llr = np.zeros(n)

        for i in range(self.min_segment + self.window, n - self.min_segment):
            left = variance[self.window:i]
            right = variance[i:n]

            left_valid = left[~np.isnan(left)]
            right_valid = right[~np.isnan(right)]

            if len(left_valid) < 10 or len(right_valid) < 10:
                continue

            # Variance of variances (meta-variance)
            var_left = np.var(left_valid)
            var_right = np.var(right_valid)
            var_all = np.var(variance[self.window:n][~np.isnan(variance[self.window:n])])

            if var_all > 1e-10:
                # Ratio of within-segment variance to total variance
                # Lower ratio = better split
                weighted_within = (len(left_valid) * var_left + len(right_valid) * var_right) / (len(left_valid) + len(right_valid))
                llr[i] = 1.0 - weighted_within / var_all

        # Find best change point
        peak_idx = self.find_peak(llr, mode="max")

        if peak_idx is not None and llr[peak_idx] > self.threshold:
            detection_idx = peak_idx
            confidence = min(1.0, llr[peak_idx])
            detected = True
        else:
            detection_idx = None
            confidence = 0.0
            detected = False

        return DetectionResult(
            detected=detected,
            detection_index=detection_idx,
            confidence=float(confidence),
            detector_type=DetectorType.CHANGE_POINT,
            signal=llr,
            threshold=self.threshold,
            metadata={"min_segment": self.min_segment},
        )


class EnsembleDetector(BaseDetector):
    """
    Combines multiple detectors with weighted voting.

    Improved: Uses median of detections, requires agreement.
    """

    def __init__(
        self,
        window: int = 40,
        threshold: float = 0.4,
        weights: Optional[Dict[DetectorType, float]] = None,
    ):
        super().__init__(window, threshold)

        self.detectors = [
            VarianceRatioDetector(window=window),
            VarianceDerivativeDetector(window=window),
            VarianceInflectionDetector(window=window),
            RollingZScoreDetector(window=window),
            CUSUMDetector(window=window),
            ChangePointDetector(window=window),
        ]

        if weights is None:
            self.weights = {
                DetectorType.VARIANCE_RATIO: 1.5,
                DetectorType.VARIANCE_DERIVATIVE: 1.2,
                DetectorType.VARIANCE_INFLECTION: 1.0,
                DetectorType.ROLLING_ZSCORE: 0.8,
                DetectorType.CUSUM: 1.0,
                DetectorType.CHANGE_POINT: 1.3,
            }
        else:
            self.weights = weights

    def detect(self, signal: np.ndarray) -> DetectionResult:
        results = [d.detect(signal) for d in self.detectors]

        detections = []
        for result in results:
            if result.detected and result.detection_index is not None:
                weight = self.weights.get(result.detector_type, 1.0)
                detections.append({
                    "type": result.detector_type,
                    "index": result.detection_index,
                    "confidence": result.confidence,
                    "weight": weight,
                })

        if not detections:
            return DetectionResult(
                detected=False, detection_index=None, confidence=0.0,
                detector_type=DetectorType.ENSEMBLE,
                signal=np.zeros(len(signal)), threshold=self.threshold,
                metadata={"votes": 0, "detectors": len(self.detectors)},
            )

        # Voting with agreement threshold
        vote_fraction = len(detections) / len(self.detectors)
        detected = vote_fraction >= self.threshold

        if not detected:
            return DetectionResult(
                detected=False, detection_index=None, confidence=0.0,
                detector_type=DetectorType.ENSEMBLE,
                signal=np.zeros(len(signal)), threshold=self.threshold,
                metadata={"votes": len(detections), "detectors": len(self.detectors), "vote_fraction": vote_fraction},
            )

        # Weighted median of detection indices
        indices = np.array([d["index"] for d in detections])
        weights_arr = np.array([d["weight"] for d in detections])

        # Sort by index
        sorted_order = np.argsort(indices)
        sorted_indices = indices[sorted_order]
        sorted_weights = weights_arr[sorted_order]

        # Weighted median
        cumsum = np.cumsum(sorted_weights)
        half = cumsum[-1] / 2
        median_pos = np.searchsorted(cumsum, half)
        detection_idx = int(sorted_indices[min(median_pos, len(sorted_indices)-1)])

        # Combined confidence
        total_weight = sum(d["weight"] for d in detections)
        weighted_conf = sum(d["confidence"] * d["weight"] for d in detections) / total_weight

        # Create combined signal
        combined = np.zeros(len(signal))
        for result in results:
            if np.any(~np.isnan(result.signal)):
                s = result.signal.copy()
                s[np.isnan(s)] = 0
                # Normalize
                smax = np.max(np.abs(s))
                if smax > 0:
                    s = s / smax
                combined += s * self.weights.get(result.detector_type, 1.0)
        combined /= sum(self.weights.values())

        return DetectionResult(
            detected=True,
            detection_index=detection_idx,
            confidence=float(weighted_conf),
            detector_type=DetectorType.ENSEMBLE,
            signal=combined,
            threshold=self.threshold,
            metadata={
                "votes": len(detections),
                "detectors": len(self.detectors),
                "vote_fraction": vote_fraction,
                "individual_results": [
                    {"type": r.detector_type.value, "detected": r.detected,
                     "index": r.detection_index, "confidence": r.confidence}
                    for r in results
                ],
            },
        )


def create_detector(detector_type: DetectorType, **kwargs) -> BaseDetector:
    """Factory function to create detectors."""
    detector_classes = {
        DetectorType.VARIANCE_RATIO: VarianceRatioDetector,
        DetectorType.VARIANCE_DERIVATIVE: VarianceDerivativeDetector,
        DetectorType.VARIANCE_INFLECTION: VarianceInflectionDetector,
        DetectorType.ROLLING_ZSCORE: RollingZScoreDetector,
        DetectorType.CUSUM: CUSUMDetector,
        DetectorType.CHANGE_POINT: ChangePointDetector,
        DetectorType.ENSEMBLE: EnsembleDetector,
    }
    return detector_classes[detector_type](**kwargs)


if __name__ == "__main__":
    from pathlib import Path
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from simulators.phase_transitions import simulate, SimulationConfig, TransitionType

    print("Testing nucleation detectors v2.0...")
    print("=" * 70)

    for ttype in TransitionType:
        print(f"\n{ttype.value.upper()}:")
        print("-" * 50)

        config = SimulationConfig(
            transition_type=ttype,
            duration=1000,
            noise_level=0.1,
            seed=42,
        )
        result = simulate(config)

        for dtype in DetectorType:
            detector = create_detector(dtype)
            detection = detector.detect(result.state)

            if detection.detected and detection.detection_index is not None:
                error = detection.detection_index - result.transition_index
                timing = "EARLY" if error < -30 else "LATE" if error > 30 else "OK"
                print(f"  {dtype.value:22s}: idx={detection.detection_index:4d} "
                      f"(true={result.transition_index:4d}, err={error:+4d}) "
                      f"[{timing:5s}] conf={detection.confidence:.2f}")
            else:
                print(f"  {dtype.value:22s}: NOT DETECTED (true={result.transition_index})")

    print("\n" + "=" * 70)
    print("Detector testing complete.")
