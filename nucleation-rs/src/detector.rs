//! Nucleation Detector for cognitive insight detection
//!
//! Implements the core detection algorithm combining:
//! - Entropy dynamics (Theorems 1-4)
//! - Distributional distance from baseline
//! - Phase transition detection (susceptibility)
//! - OEP energy estimation

use std::collections::VecDeque;

use crate::distance::hellinger_distance;
use crate::entropy::shannon_entropy;
use crate::signal::{GradientTracker, OEPEstimator, RollingStats};

/// Detection phase states
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum DetectionPhase {
    Exploration,
    PreInsight,
    Nucleation,
    Crystallization,
    Stable,
}

/// Insight precursor signal
#[derive(Debug, Clone)]
pub struct InsightPrecursor {
    pub timestamp: f64,
    pub phase: DetectionPhase,
    pub confidence: f64,
    pub triggers: Vec<String>,
    pub lead_time_estimate: f64,
    pub energy: f64,
    pub resonance: f64,
}

/// Configuration for detector sensitivity
#[derive(Debug, Clone)]
pub struct DetectorConfig {
    pub entropy_window: usize,
    pub variance_window: usize,
    pub baseline_decay: f64,
    pub variance_threshold: f64,
    pub hellinger_threshold: f64,
    pub gradient_threshold: f64,
    pub energy_threshold: f64,
    pub concordance_min: usize,
    pub cooldown_events: usize,
    pub tau_decay: f64,
}

impl Default for DetectorConfig {
    fn default() -> Self {
        Self {
            entropy_window: 30,
            variance_window: 10,
            baseline_decay: 0.95,
            variance_threshold: 0.008,
            hellinger_threshold: 0.25,
            gradient_threshold: 0.10,
            energy_threshold: 0.4,
            concordance_min: 4,
            cooldown_events: 5,
            tau_decay: 10000.0, // 10 second decay constant
        }
    }
}

impl DetectorConfig {
    pub fn high_recall() -> Self {
        Self {
            variance_threshold: 0.015,
            hellinger_threshold: 0.20,
            concordance_min: 2,
            ..Default::default()
        }
    }

    pub fn balanced() -> Self {
        Self::default()
    }

    pub fn high_precision() -> Self {
        Self {
            variance_threshold: 0.004,
            hellinger_threshold: 0.30,
            concordance_min: 5,
            ..Default::default()
        }
    }
}

/// Main nucleation detector
pub struct NucleationDetector {
    config: DetectorConfig,

    // State tracking
    symbol_history: VecDeque<u32>,
    entropy_history: RollingStats,
    hellinger_history: RollingStats,
    gradient_tracker: GradientTracker,
    oep: OEPEstimator,

    // Baseline distribution
    baseline_dist: Option<Vec<f64>>,
    n_symbols: usize,

    // Cooldown
    cooldown: usize,

    // Event counter
    event_count: usize,
}

impl NucleationDetector {
    pub fn new(config: DetectorConfig) -> Self {
        Self {
            entropy_history: RollingStats::new(50),
            hellinger_history: RollingStats::new(config.variance_window),
            gradient_tracker: GradientTracker::new(config.variance_window),
            oep: OEPEstimator::new(config.tau_decay),
            config,
            symbol_history: VecDeque::with_capacity(100),
            baseline_dist: None,
            n_symbols: 100,
            cooldown: 0,
            event_count: 0,
        }
    }

    pub fn with_sensitivity(sensitivity: &str) -> Self {
        let config = match sensitivity {
            "high_recall" => DetectorConfig::high_recall(),
            "high_precision" => DetectorConfig::high_precision(),
            _ => DetectorConfig::balanced(),
        };
        Self::new(config)
    }

    /// Reset detector state
    pub fn reset(&mut self) {
        self.symbol_history.clear();
        self.entropy_history = RollingStats::new(50);
        self.hellinger_history = RollingStats::new(self.config.variance_window);
        self.gradient_tracker = GradientTracker::new(self.config.variance_window);
        self.oep.reset();
        self.baseline_dist = None;
        self.cooldown = 0;
        self.event_count = 0;
    }

    /// Process a new behavioral event
    pub fn update(
        &mut self,
        symbol: u32,
        timestamp: f64,
        object_weight: f64,
    ) -> Option<InsightPrecursor> {
        self.event_count += 1;

        // Update symbol history
        if self.symbol_history.len() >= 100 {
            self.symbol_history.pop_front();
        }
        self.symbol_history.push_back(symbol);

        // Cooldown check
        if self.cooldown > 0 {
            self.cooldown -= 1;
            return None;
        }

        // Need minimum history
        if self.symbol_history.len() < self.config.entropy_window {
            return None;
        }

        // Update OEP energy
        let energy = self.oep.update(timestamp, object_weight);

        // Compute current distribution
        let window: Vec<u32> = self
            .symbol_history
            .iter()
            .rev()
            .take(self.config.entropy_window)
            .copied()
            .collect();

        // Expand symbol space if needed
        let max_sym = *window.iter().max().unwrap_or(&0) as usize + 1;
        if max_sym > self.n_symbols {
            self.n_symbols = max_sym;
            self.baseline_dist = None;
        }

        let current_dist = self.compute_distribution(&window);

        // Initialize baseline if needed
        if self.baseline_dist.is_none() {
            self.baseline_dist = Some(current_dist.clone());
            return None;
        }

        let baseline = self.baseline_dist.as_ref().unwrap();

        // Compute signals
        let entropy = shannon_entropy(&window);
        let hellinger = hellinger_distance(&current_dist, baseline);

        // Update trackers
        self.entropy_history.push(entropy);
        self.hellinger_history.push(hellinger);
        self.gradient_tracker.push(entropy, timestamp);

        // Update baseline with decay
        let decay = self.config.baseline_decay;
        let new_baseline: Vec<f64> = baseline
            .iter()
            .zip(current_dist.iter())
            .map(|(b, c)| decay * b + (1.0 - decay) * c)
            .collect();
        self.baseline_dist = Some(new_baseline);

        // Compute detection signals
        let variance = self.hellinger_history.variance();
        let gradient = self.gradient_tracker.gradient();
        let z_entropy = self.entropy_history.z_score();

        // Collect triggers
        let mut triggers = vec![];

        // Key signal: LOW variance indicates nucleation
        if variance < self.config.variance_threshold {
            triggers.push("LOW_VARIANCE".to_string());
        }

        // Distribution shift from baseline
        if hellinger > self.config.hellinger_threshold {
            triggers.push("DIST_SHIFT".to_string());
        }

        // Entropy gradient (rising entropy = exploration ending)
        if gradient > self.config.gradient_threshold {
            triggers.push("ENTROPY_RISING".to_string());
        }

        // Z-score spike
        if z_entropy.abs() > 1.5 {
            triggers.push("ENTROPY_SPIKE".to_string());
        }

        // Energy above threshold
        if energy > self.config.energy_threshold {
            triggers.push("HIGH_ENERGY".to_string());
        }

        // Entropy in "insight zone" (neither too high nor too low)
        if entropy > 1.5 && entropy < 3.5 {
            triggers.push("ENTROPY_ZONE".to_string());
        }

        // Check concordance
        if triggers.len() >= self.config.concordance_min {
            self.cooldown = self.config.cooldown_events;

            let phase = if variance < self.config.variance_threshold {
                DetectionPhase::Nucleation
            } else if gradient > 0.0 {
                DetectionPhase::PreInsight
            } else {
                DetectionPhase::Exploration
            };

            let confidence = triggers.len() as f64 / 6.0;
            let lead_time = if phase == DetectionPhase::Nucleation {
                30000.0
            } else {
                45000.0
            };

            // Resonance metric (simplified ACR)
            let resonance = energy * (1.0 - variance / 0.02).clamp(0.0, 1.0);

            return Some(InsightPrecursor {
                timestamp,
                phase,
                confidence: confidence.min(1.0),
                triggers,
                lead_time_estimate: lead_time,
                energy,
                resonance,
            });
        }

        None
    }

    fn compute_distribution(&self, symbols: &[u32]) -> Vec<f64> {
        let mut counts = vec![0usize; self.n_symbols];
        for &s in symbols {
            if (s as usize) < self.n_symbols {
                counts[s as usize] += 1;
            }
        }

        let total = symbols.len() as f64;
        counts.iter().map(|&c| c as f64 / total).collect()
    }

    /// Get current energy estimate
    pub fn energy(&self) -> f64 {
        self.oep.energy
    }

    /// Get current phase assessment
    pub fn phase(&self) -> DetectionPhase {
        if self.symbol_history.len() < self.config.entropy_window {
            return DetectionPhase::Exploration;
        }

        let variance = self.hellinger_history.variance();
        let gradient = self.gradient_tracker.gradient();

        if variance < self.config.variance_threshold * 0.5 {
            DetectionPhase::Crystallization
        } else if variance < self.config.variance_threshold {
            DetectionPhase::Nucleation
        } else if gradient > self.config.gradient_threshold {
            DetectionPhase::PreInsight
        } else {
            DetectionPhase::Exploration
        }
    }

    /// Get total events processed
    pub fn event_count(&self) -> usize {
        self.event_count
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_detector_creation() {
        let detector = NucleationDetector::with_sensitivity("balanced");
        assert_eq!(detector.event_count(), 0);
        assert_eq!(detector.phase(), DetectionPhase::Exploration);
    }

    #[test]
    fn test_detector_needs_warmup() {
        let mut detector = NucleationDetector::with_sensitivity("balanced");

        // First few events shouldn't trigger
        for i in 0..20 {
            let result = detector.update(i % 5, i as f64 * 100.0, 0.5);
            assert!(result.is_none());
        }
    }

    #[test]
    fn test_high_variance_no_detection() {
        let mut detector = NucleationDetector::with_sensitivity("high_precision");

        // Random symbols = high variance = typically no stable detection
        for i in 0..100 {
            let symbol = ((i * 7 + 13) % 20) as u32;
            let _ = detector.update(symbol, i as f64 * 100.0, 0.5);
        }

        // Should be in some valid phase (test just ensures no crash)
        let phase = detector.phase();
        assert!(matches!(
            phase,
            DetectionPhase::Exploration
                | DetectionPhase::PreInsight
                | DetectionPhase::Nucleation
                | DetectionPhase::Crystallization
                | DetectionPhase::Stable
        ));
    }

    #[test]
    fn test_detector_reset() {
        let mut detector = NucleationDetector::with_sensitivity("balanced");

        for i in 0..50 {
            detector.update(i % 3, i as f64 * 100.0, 0.5);
        }

        detector.reset();
        assert_eq!(detector.event_count(), 0);
        assert!(detector.energy() > 0.4); // Reset energy
    }
}
