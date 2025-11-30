//! # Nucleation
//!
//! Entropy-based cognitive insight detection primitives.
//!
//! This crate provides the foundation for building cognitive state detection
//! and active resonance control systems. It implements:
//!
//! - **Entropy calculations**: Shannon, permutation, relative entropy
//! - **Distance metrics**: Hellinger, Jensen-Shannon, Fisher-Rao
//! - **Signal processing**: Rolling statistics, gradients, phase tracking
//! - **Nucleation detection**: Multi-signal concordance detector
//! - **ACR control**: Kuramoto-inspired phase-locking controller
//!
//! ## Quick Start
//!
//! ```rust
//! use nucleation::{NucleationDetector, DetectorConfig, DetectionPhase};
//!
//! let mut detector = NucleationDetector::with_sensitivity("balanced");
//!
//! // Process behavioral events
//! for (symbol, timestamp, weight) in events {
//!     if let Some(precursor) = detector.update(symbol, timestamp, weight) {
//!         println!("Insight precursor detected: {:?}", precursor.phase);
//!     }
//! }
//! ```
//!
//! ## ACR Controller
//!
//! ```rust
//! use nucleation::acr::{ACRController, CognitiveModality, ControlAction};
//!
//! let mut controller = ACRController::new(CognitiveModality::Integration);
//!
//! // Update with observations
//! let signal = controller.update(timestamp, event_duration, switching_freq);
//!
//! match signal.action {
//!     ControlAction::TriggerInsight => println!("Fire the hint!"),
//!     ControlAction::SlowDown => println!("Reduce pacing to {}", signal.pacing_factor),
//!     _ => {}
//! }
//! ```
//!
//! ## Architecture
//!
//! ```text
//! ┌─────────────────────────────────────────────────────────────────┐
//! │                         nucleation                              │
//! ├─────────────────────────────────────────────────────────────────┤
//! │  entropy.rs     │  distance.rs    │  signal.rs                  │
//! │  - Shannon      │  - Hellinger    │  - RollingStats             │
//! │  - Permutation  │  - JS-divergence│  - GradientTracker          │
//! │  - KL-divergence│  - Fisher-Rao   │  - PhaseTracker             │
//! │  - Entropy rate │  - Wasserstein  │  - OEPEstimator             │
//! ├─────────────────┴─────────────────┴─────────────────────────────┤
//! │  detector.rs                      │  acr.rs                     │
//! │  - NucleationDetector             │  - ACRController            │
//! │  - InsightPrecursor               │  - CognitiveModality        │
//! │  - DetectionPhase                 │  - ControlSignal            │
//! │  - Multi-signal concordance       │  - Kuramoto phase dynamics  │
//! └───────────────────────────────────┴─────────────────────────────┘
//! ```
//!
//! ## Mathematical Foundation
//!
//! Based on the Unified Entropy Theory (Theorems 1-14) and the Active
//! Cognitive Resonance (ACR) framework for phase-locked insight induction.
//!
//! Key equations:
//! - OEP: dE/dt = -E/τ + α·Σδ(t-tᵢ)·Ψ(Oᵢ) + η(t)
//! - ACR: dφ_int/dt = ω_int + K(E)·sin(φ_ext - φ_int) + β·u(t)
//! - Resonance: R(t) = |⟨exp(i·Δφ)⟩|
//!
//! ## Crate Features
//!
//! - `simd`: Enable SIMD optimizations (requires nightly)
//! - `wasm`: WASM-compatible builds for browser deployment

pub mod entropy;
pub mod distance;
pub mod signal;
pub mod detector;
pub mod acr;

// Re-exports for convenience
pub use detector::{
    NucleationDetector,
    DetectorConfig,
    DetectionPhase,
    InsightPrecursor,
};

pub use acr::{
    ACRController,
    ACRState,
    CognitiveModality,
    ControlSignal,
    ControlAction,
    LQRGains,
};

pub use entropy::{
    shannon_entropy,
    normalized_entropy,
    permutation_entropy,
    kl_divergence,
    entropy_rate,
};

pub use distance::{
    hellinger_distance,
    jensen_shannon_divergence,
    jensen_shannon_distance,
    fisher_rao_distance,
    bhattacharyya_coefficient,
    bhattacharyya_distance,
    total_variation_distance,
    wasserstein_1d,
};

pub use signal::{
    RollingStats,
    GradientTracker,
    PhaseTracker,
    OEPEstimator,
};

/// Crate version
pub const VERSION: &str = env!("CARGO_PKG_VERSION");

/// Quick detector factory
pub fn create_detector(sensitivity: &str) -> NucleationDetector {
    NucleationDetector::with_sensitivity(sensitivity)
}

/// Quick controller factory
pub fn create_controller(modality: CognitiveModality) -> ACRController {
    ACRController::new(modality)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_reexports() {
        let _ = create_detector("balanced");
        let _ = create_controller(CognitiveModality::Integration);
        let _ = shannon_entropy(&[1, 2, 3, 4]);
        let _ = hellinger_distance(&[0.5, 0.5], &[0.5, 0.5]);
    }

    #[test]
    fn test_version() {
        assert!(!VERSION.is_empty());
    }
}
