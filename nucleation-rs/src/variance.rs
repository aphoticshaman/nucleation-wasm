//! Variance Inflection Detector
//!
//! Detects phase transitions by finding peaks in the second derivative
//! of rolling variance. This captures both:
//! - Critical Slowing Down (CSD): variance INCREASES before bifurcation
//! - Commitment transitions: variance DECREASES before crystallization
//!
//! The key insight: transitions produce inflection points in variance,
//! regardless of direction. We detect peaks in |d²V/dt²|.
//!
//! Algorithm:
//! 1. Maintain rolling window of observations
//! 2. Compute rolling variance V(t)
//! 3. Smooth V(t) with convolution kernel
//! 4. Compute second derivative d²V/dt²
//! 5. Detect peaks in |d²V/dt²| above threshold

use std::collections::VecDeque;

#[cfg(feature = "serde")]
use serde::{Deserialize, Serialize};

/// Phase classification for the detector state.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
#[cfg_attr(feature = "serde", derive(Serialize, Deserialize))]
pub enum Phase {
    /// Normal operation, no transition detected
    Stable,
    /// Variance dynamics changing, possible transition approaching
    Approaching,
    /// Strong inflection signal, transition likely imminent
    Critical,
    /// Active transition detected
    Transitioning,
}

impl Default for Phase {
    fn default() -> Self {
        Self::Stable
    }
}

/// Smoothing kernel type for variance trajectory.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
#[cfg_attr(feature = "serde", derive(Serialize, Deserialize))]
pub enum SmoothingKernel {
    /// Uniform weights (box filter)
    Uniform,
    /// Gaussian-like weights (approximated triangular)
    Gaussian,
}

impl Default for SmoothingKernel {
    fn default() -> Self {
        Self::Uniform
    }
}

/// Configuration for the variance inflection detector.
#[derive(Debug, Clone)]
#[cfg_attr(feature = "serde", derive(Serialize, Deserialize))]
pub struct VarianceConfig {
    /// Window size for rolling variance calculation
    pub window_size: usize,
    /// Window size for smoothing the variance trajectory
    pub smoothing_window: usize,
    /// Threshold for inflection magnitude (z-score)
    pub threshold: f64,
    /// Minimum observations between detected transitions
    pub min_peak_distance: usize,
    /// Smoothing kernel type
    pub kernel: SmoothingKernel,
}

impl Default for VarianceConfig {
    fn default() -> Self {
        Self {
            window_size: 40,
            smoothing_window: 15,
            threshold: 1.5,
            min_peak_distance: 20,
            kernel: SmoothingKernel::Uniform,
        }
    }
}

impl VarianceConfig {
    pub fn sensitive() -> Self {
        Self {
            threshold: 1.0,
            min_peak_distance: 10,
            ..Default::default()
        }
    }

    pub fn conservative() -> Self {
        Self {
            threshold: 2.5,
            min_peak_distance: 30,
            ..Default::default()
        }
    }
}

/// Detection result from the variance inflection detector.
#[derive(Debug, Clone)]
#[cfg_attr(feature = "serde", derive(Serialize, Deserialize))]
pub struct InflectionResult {
    pub phase: Phase,
    pub confidence: f64,
    pub inflection_magnitude: f64,
    pub current_variance: f64,
    pub variance_trend: f64,
    pub d2_variance: f64,
}

/// Variance Inflection Detector
///
/// Streaming detector that identifies phase transitions by monitoring
/// the second derivative of rolling variance.
#[derive(Debug)]
#[cfg_attr(feature = "serde", derive(Serialize, Deserialize))]
pub struct VarianceInflectionDetector {
    config: VarianceConfig,

    // Raw observation buffer
    observations: VecDeque<f64>,

    // Variance trajectory
    variance_history: VecDeque<f64>,

    // Smoothed variance
    smoothed_variance: VecDeque<f64>,

    // First derivative of variance
    d1_variance: VecDeque<f64>,

    // Second derivative of variance (inflection)
    d2_variance: VecDeque<f64>,

    // Baseline statistics for threshold adaptation
    baseline_d2_mean: f64,
    baseline_d2_std: f64,
    baseline_samples: usize,

    // Cooldown counter for peak detection
    cooldown: usize,

    // Total observations processed
    count: usize,
}

impl VarianceInflectionDetector {
    pub fn new(config: VarianceConfig) -> Self {
        let cap = config.window_size * 3;
        Self {
            config,
            observations: VecDeque::with_capacity(cap),
            variance_history: VecDeque::with_capacity(cap),
            smoothed_variance: VecDeque::with_capacity(cap),
            d1_variance: VecDeque::with_capacity(cap),
            d2_variance: VecDeque::with_capacity(cap),
            baseline_d2_mean: 0.0,
            baseline_d2_std: 1.0,
            baseline_samples: 0,
            cooldown: 0,
            count: 0,
        }
    }

    pub fn with_default_config() -> Self {
        Self::new(VarianceConfig::default())
    }

    /// Process a single observation and return detection result.
    pub fn update(&mut self, value: f64) -> InflectionResult {
        self.count += 1;

        // Add to observation buffer
        if self.observations.len() >= self.config.window_size * 3 {
            self.observations.pop_front();
        }
        self.observations.push_back(value);

        // Compute rolling variance if we have enough data
        if self.observations.len() >= self.config.window_size {
            let variance = self.compute_rolling_variance();
            self.update_variance_trajectory(variance);
        }

        // Update cooldown
        if self.cooldown > 0 {
            self.cooldown -= 1;
        }

        self.compute_result()
    }

    /// Process multiple observations.
    pub fn update_batch(&mut self, values: &[f64]) -> InflectionResult {
        for &v in values.iter().take(values.len().saturating_sub(1)) {
            self.update(v);
        }
        if let Some(&last) = values.last() {
            self.update(last)
        } else {
            self.compute_result()
        }
    }

    /// Get current phase classification.
    pub fn current_phase(&self) -> Phase {
        self.compute_result().phase
    }

    /// Get confidence in current phase assessment.
    pub fn confidence(&self) -> f64 {
        self.compute_result().confidence
    }

    /// Get current rolling variance.
    pub fn current_variance(&self) -> f64 {
        self.variance_history.back().copied().unwrap_or(0.0)
    }

    /// Get current inflection magnitude (|d²V/dt²| z-score).
    pub fn inflection_magnitude(&self) -> f64 {
        if let Some(&d2) = self.d2_variance.back() {
            if self.baseline_d2_std > 1e-10 {
                (d2.abs() - self.baseline_d2_mean) / self.baseline_d2_std
            } else {
                0.0
            }
        } else {
            0.0
        }
    }

    /// Reset detector state.
    pub fn reset(&mut self) {
        self.observations.clear();
        self.variance_history.clear();
        self.smoothed_variance.clear();
        self.d1_variance.clear();
        self.d2_variance.clear();
        self.baseline_d2_mean = 0.0;
        self.baseline_d2_std = 1.0;
        self.baseline_samples = 0;
        self.cooldown = 0;
        self.count = 0;
    }

    /// Get total observations processed.
    pub fn count(&self) -> usize {
        self.count
    }

    /// Get the configuration.
    pub fn config(&self) -> &VarianceConfig {
        &self.config
    }

    // Internal: compute rolling variance of recent observations
    fn compute_rolling_variance(&self) -> f64 {
        let n = self.config.window_size;
        if self.observations.len() < n {
            return 0.0;
        }

        let window: Vec<f64> = self.observations.iter()
            .rev()
            .take(n)
            .copied()
            .collect();

        let mean: f64 = window.iter().sum::<f64>() / n as f64;
        let variance: f64 = window.iter()
            .map(|x| (x - mean).powi(2))
            .sum::<f64>() / n as f64;

        variance
    }

    // Internal: update variance trajectory and derivatives
    fn update_variance_trajectory(&mut self, variance: f64) {
        // Store raw variance
        if self.variance_history.len() >= self.config.window_size * 2 {
            self.variance_history.pop_front();
        }
        self.variance_history.push_back(variance);

        // Smooth variance
        let smoothed = self.smooth_variance();
        if self.smoothed_variance.len() >= self.config.window_size * 2 {
            self.smoothed_variance.pop_front();
        }
        self.smoothed_variance.push_back(smoothed);

        // Compute first derivative (gradient)
        if self.smoothed_variance.len() >= 2 {
            let d1 = self.smoothed_variance.back().unwrap()
                - self.smoothed_variance.iter().rev().nth(1).unwrap();

            if self.d1_variance.len() >= self.config.window_size * 2 {
                self.d1_variance.pop_front();
            }
            self.d1_variance.push_back(d1);
        }

        // Compute second derivative (inflection)
        if self.d1_variance.len() >= 2 {
            let d2 = self.d1_variance.back().unwrap()
                - self.d1_variance.iter().rev().nth(1).unwrap();

            if self.d2_variance.len() >= self.config.window_size * 2 {
                self.d2_variance.pop_front();
            }
            self.d2_variance.push_back(d2);

            // Update baseline statistics (exponential moving average)
            self.update_baseline(d2.abs());
        }
    }

    // Internal: smooth variance using configured kernel
    fn smooth_variance(&self) -> f64 {
        let n = self.config.smoothing_window.min(self.variance_history.len());
        if n == 0 {
            return self.variance_history.back().copied().unwrap_or(0.0);
        }

        let window: Vec<f64> = self.variance_history.iter()
            .rev()
            .take(n)
            .copied()
            .collect();

        match self.config.kernel {
            SmoothingKernel::Uniform => {
                window.iter().sum::<f64>() / n as f64
            }
            SmoothingKernel::Gaussian => {
                // Triangular approximation of Gaussian
                let weights: Vec<f64> = (0..n)
                    .map(|i| {
                        let x = i as f64 / n as f64;
                        1.0 - x // Linear decay
                    })
                    .collect();
                let weight_sum: f64 = weights.iter().sum();

                window.iter()
                    .zip(weights.iter())
                    .map(|(v, w)| v * w)
                    .sum::<f64>() / weight_sum
            }
        }
    }

    // Internal: update baseline statistics for adaptive thresholding
    fn update_baseline(&mut self, abs_d2: f64) {
        self.baseline_samples += 1;

        // Exponential moving average for mean
        let alpha = 0.02;
        self.baseline_d2_mean = (1.0 - alpha) * self.baseline_d2_mean + alpha * abs_d2;

        // Running estimate of std dev
        let deviation = (abs_d2 - self.baseline_d2_mean).powi(2);
        let variance_estimate = (1.0 - alpha) * self.baseline_d2_std.powi(2) + alpha * deviation;
        self.baseline_d2_std = variance_estimate.sqrt().max(1e-10);
    }

    // Internal: compute detection result
    fn compute_result(&self) -> InflectionResult {
        let current_variance = self.current_variance();
        let d2 = self.d2_variance.back().copied().unwrap_or(0.0);

        // Compute z-score of inflection magnitude
        let z_score = if self.baseline_d2_std > 1e-10 {
            (d2.abs() - self.baseline_d2_mean) / self.baseline_d2_std
        } else {
            0.0
        };

        // Variance trend (first derivative)
        let variance_trend = self.d1_variance.back().copied().unwrap_or(0.0);

        // Determine phase
        let phase = if self.count < self.config.window_size * 2 {
            Phase::Stable // Warmup period
        } else if self.cooldown > 0 {
            Phase::Transitioning
        } else if z_score > self.config.threshold * 1.5 {
            Phase::Critical
        } else if z_score > self.config.threshold {
            Phase::Approaching
        } else {
            Phase::Stable
        };

        // Set cooldown on critical detection
        // (Note: can't mutate self here, caller should handle)

        // Confidence based on z-score relative to threshold
        let confidence = if self.count < self.config.window_size {
            0.0
        } else {
            (z_score / (self.config.threshold * 2.0)).clamp(0.0, 1.0)
        };

        InflectionResult {
            phase,
            confidence,
            inflection_magnitude: z_score,
            current_variance,
            variance_trend,
            d2_variance: d2,
        }
    }

    /// Check if a transition was just detected (and set cooldown).
    pub fn check_transition(&mut self) -> Option<InflectionResult> {
        let result = self.compute_result();

        if result.phase == Phase::Critical && self.cooldown == 0 {
            self.cooldown = self.config.min_peak_distance;
            Some(result)
        } else {
            None
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_detector_creation() {
        let detector = VarianceInflectionDetector::with_default_config();
        assert_eq!(detector.count(), 0);
        assert_eq!(detector.current_phase(), Phase::Stable);
    }

    #[test]
    fn test_warmup_period() {
        let mut detector = VarianceInflectionDetector::with_default_config();

        // During warmup, should stay stable
        for i in 0..30 {
            let result = detector.update(i as f64);
            assert_eq!(result.phase, Phase::Stable);
        }
    }

    #[test]
    fn test_constant_input_stable() {
        let mut detector = VarianceInflectionDetector::with_default_config();

        // Constant input should produce stable phase
        for _ in 0..200 {
            detector.update(5.0);
        }

        assert_eq!(detector.current_phase(), Phase::Stable);
        assert!(detector.current_variance() < 0.01);
    }

    #[test]
    fn test_variance_change_detection() {
        let mut detector = VarianceInflectionDetector::new(VarianceConfig {
            threshold: 1.0,
            ..Default::default()
        });

        // Stable period with low variance
        for i in 0..100 {
            detector.update(50.0 + (i as f64 * 0.01).sin() * 0.1);
        }

        // Sudden high variance period (should trigger detection)
        for i in 0..50 {
            detector.update(50.0 + (i as f64).sin() * 10.0);
        }

        // Should have detected something
        let result = detector.compute_result();
        assert!(result.inflection_magnitude > 0.0);
    }

    #[test]
    fn test_reset() {
        let mut detector = VarianceInflectionDetector::with_default_config();

        for i in 0..100 {
            detector.update(i as f64);
        }
        assert!(detector.count() > 0);

        detector.reset();
        assert_eq!(detector.count(), 0);
        assert_eq!(detector.current_variance(), 0.0);
    }

    #[test]
    fn test_batch_update() {
        let mut detector = VarianceInflectionDetector::with_default_config();
        let values: Vec<f64> = (0..100).map(|i| i as f64).collect();

        detector.update_batch(&values);
        assert_eq!(detector.count(), 100);
    }
}
