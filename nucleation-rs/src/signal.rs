//! Signal processing primitives for behavioral time series
//!
//! Variance tracking, gradient computation, and phase analysis
//! for cognitive state estimation.

use std::collections::VecDeque;

/// Rolling statistics tracker with exponential weighting
pub struct RollingStats {
    window_size: usize,
    values: VecDeque<f64>,
    sum: f64,
    sum_sq: f64,
}

impl RollingStats {
    pub fn new(window_size: usize) -> Self {
        Self {
            window_size,
            values: VecDeque::with_capacity(window_size),
            sum: 0.0,
            sum_sq: 0.0,
        }
    }

    pub fn push(&mut self, value: f64) {
        if self.values.len() >= self.window_size {
            if let Some(old) = self.values.pop_front() {
                self.sum -= old;
                self.sum_sq -= old * old;
            }
        }

        self.values.push_back(value);
        self.sum += value;
        self.sum_sq += value * value;
    }

    pub fn mean(&self) -> f64 {
        if self.values.is_empty() {
            0.0
        } else {
            self.sum / self.values.len() as f64
        }
    }

    pub fn variance(&self) -> f64 {
        let n = self.values.len() as f64;
        if n < 2.0 {
            return 0.0;
        }

        let mean = self.mean();
        self.sum_sq / n - mean * mean
    }

    pub fn std_dev(&self) -> f64 {
        self.variance().sqrt()
    }

    pub fn len(&self) -> usize {
        self.values.len()
    }

    pub fn is_empty(&self) -> bool {
        self.values.is_empty()
    }

    /// Z-score of most recent value
    pub fn z_score(&self) -> f64 {
        if self.values.is_empty() {
            return 0.0;
        }

        let std = self.std_dev();
        if std < 1e-10 {
            return 0.0;
        }

        let last = *self.values.back().unwrap();
        (last - self.mean()) / std
    }
}

/// Gradient estimator using finite differences
pub struct GradientTracker {
    window_size: usize,
    values: VecDeque<f64>,
    timestamps: VecDeque<f64>,
}

impl GradientTracker {
    pub fn new(window_size: usize) -> Self {
        Self {
            window_size,
            values: VecDeque::with_capacity(window_size),
            timestamps: VecDeque::with_capacity(window_size),
        }
    }

    pub fn push(&mut self, value: f64, timestamp: f64) {
        if self.values.len() >= self.window_size {
            self.values.pop_front();
            self.timestamps.pop_front();
        }

        self.values.push_back(value);
        self.timestamps.push_back(timestamp);
    }

    /// Linear regression slope
    pub fn gradient(&self) -> f64 {
        let n = self.values.len();
        if n < 2 {
            return 0.0;
        }

        let n_f = n as f64;

        // Compute means
        let mean_t: f64 = self.timestamps.iter().sum::<f64>() / n_f;
        let mean_v: f64 = self.values.iter().sum::<f64>() / n_f;

        // Compute covariance and variance
        let mut cov = 0.0;
        let mut var_t = 0.0;

        for (t, v) in self.timestamps.iter().zip(self.values.iter()) {
            let dt = t - mean_t;
            let dv = v - mean_v;
            cov += dt * dv;
            var_t += dt * dt;
        }

        if var_t < 1e-10 {
            return 0.0;
        }

        cov / var_t
    }

    /// Second derivative estimate
    pub fn acceleration(&self) -> f64 {
        let n = self.values.len();
        if n < 3 {
            return 0.0;
        }

        // Use 3-point central difference on gradients
        let v: Vec<f64> = self.values.iter().copied().collect();
        let t: Vec<f64> = self.timestamps.iter().copied().collect();

        let dt1 = t[n - 1] - t[n - 2];
        let dt2 = t[n - 2] - t[n - 3];

        if dt1 < 1e-10 || dt2 < 1e-10 {
            return 0.0;
        }

        let g1 = (v[n - 1] - v[n - 2]) / dt1;
        let g2 = (v[n - 2] - v[n - 3]) / dt2;

        (g1 - g2) / ((dt1 + dt2) / 2.0)
    }
}

/// Phase estimator using Hilbert-like analysis
pub struct PhaseTracker {
    history: VecDeque<f64>,
    window_size: usize,
}

impl PhaseTracker {
    pub fn new(window_size: usize) -> Self {
        Self {
            history: VecDeque::with_capacity(window_size),
            window_size,
        }
    }

    pub fn push(&mut self, value: f64) {
        if self.history.len() >= self.window_size {
            self.history.pop_front();
        }
        self.history.push_back(value);
    }

    /// Estimate instantaneous phase using zero-crossings
    pub fn phase(&self) -> f64 {
        if self.history.len() < 4 {
            return 0.0;
        }

        let values: Vec<f64> = self.history.iter().copied().collect();
        let mean: f64 = values.iter().sum::<f64>() / values.len() as f64;

        // Find zero crossings (relative to mean)
        let centered: Vec<f64> = values.iter().map(|v| v - mean).collect();

        let mut last_crossing = 0;
        let mut crossings = vec![];

        for i in 1..centered.len() {
            if centered[i - 1] * centered[i] < 0.0 {
                crossings.push(i);
                last_crossing = i;
            }
        }

        if crossings.len() < 2 {
            return 0.0;
        }

        // Estimate period from crossings
        let period = 2.0 * (crossings.last().unwrap() - crossings.first().unwrap()) as f64
            / (crossings.len() - 1) as f64;

        if period < 1.0 {
            return 0.0;
        }

        // Phase = position within current period
        let pos_in_period = (values.len() - last_crossing) as f64;
        2.0 * std::f64::consts::PI * (pos_in_period / period)
    }

    /// Estimate dominant frequency
    pub fn frequency(&self) -> f64 {
        let phase = self.phase();
        if phase.abs() < 1e-10 {
            return 0.0;
        }

        // Rough frequency from phase change rate
        let values: Vec<f64> = self.history.iter().copied().collect();
        let n = values.len();
        if n < 4 {
            return 0.0;
        }

        // Count sign changes in derivative
        let mut sign_changes = 0;
        for i in 2..n {
            let d1 = values[i - 1] - values[i - 2];
            let d2 = values[i] - values[i - 1];
            if d1 * d2 < 0.0 {
                sign_changes += 1;
            }
        }

        // Frequency ~ sign_changes / (2 * window)
        sign_changes as f64 / (2.0 * n as f64)
    }
}

/// Oscillatory Entrainment Potential (OEP) estimator
/// From ACR framework: dE/dt = -E/tau + alpha*sum(delta(t-ti)*Psi(Oi)) + noise
pub struct OEPEstimator {
    pub energy: f64,
    pub tau: f64,
    last_timestamp: f64,
}

impl OEPEstimator {
    pub fn new(tau: f64) -> Self {
        Self {
            energy: 0.5,
            tau,
            last_timestamp: 0.0,
        }
    }

    /// Update energy based on new event
    pub fn update(&mut self, timestamp: f64, object_weight: f64) -> f64 {
        let dt = timestamp - self.last_timestamp;

        // Exponential decay
        let decay = (-dt / self.tau).exp();
        self.energy = self.energy * decay + object_weight;

        // Clamp to [0, 1]
        self.energy = self.energy.clamp(0.0, 1.0);

        self.last_timestamp = timestamp;
        self.energy
    }

    /// Reset to initial state
    pub fn reset(&mut self) {
        self.energy = 0.5;
        self.last_timestamp = 0.0;
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_rolling_stats_mean() {
        let mut stats = RollingStats::new(5);
        for i in 1..=5 {
            stats.push(i as f64);
        }
        assert!((stats.mean() - 3.0).abs() < 1e-10);
    }

    #[test]
    fn test_rolling_stats_variance() {
        let mut stats = RollingStats::new(5);
        for i in 1..=5 {
            stats.push(i as f64);
        }
        // Var([1,2,3,4,5]) = 2
        assert!((stats.variance() - 2.0).abs() < 0.01);
    }

    #[test]
    fn test_gradient_tracker() {
        let mut tracker = GradientTracker::new(10);
        // Linear: y = 2x
        for i in 0..10 {
            tracker.push(2.0 * i as f64, i as f64);
        }
        assert!((tracker.gradient() - 2.0).abs() < 0.01);
    }

    #[test]
    fn test_oep_decay() {
        let mut oep = OEPEstimator::new(1000.0);
        oep.update(0.0, 1.0);
        assert!(oep.energy > 0.9);

        // After tau, energy should decay to ~37%
        oep.update(1000.0, 0.0);
        assert!((oep.energy - 0.368).abs() < 0.05);
    }
}
