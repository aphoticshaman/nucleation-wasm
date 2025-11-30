//! # Nucleation
//!
//! Phase transition detection and compression dynamics for early warning systems.
//!
//! This crate provides tools for detecting phase transitions in complex systems
//! and monitoring conflict potential between actors. It implements:
//!
//! ## Core Modules
//!
//! - **Variance Inflection Detection**: Identify phase transitions via d²V/dt²
//! - **Compression Dynamics**: KL-divergence framework for conflict modeling
//! - **Shepherd Dynamics**: Unified early warning combining both approaches
//!
//! ## Supporting Modules
//!
//! - **Entropy calculations**: Shannon, permutation, relative entropy
//! - **Distance metrics**: Hellinger, Jensen-Shannon, Fisher-Rao, Wasserstein
//! - **Signal processing**: Rolling statistics, gradients, phase tracking
//! - **Cognitive detection**: Entropy-based insight detection (ACR framework)
//!
//! ## Quick Start: Variance Inflection
//!
//! ```rust,ignore
//! use nucleation::{VarianceInflectionDetector, VarianceConfig, Phase};
//!
//! let mut detector = VarianceInflectionDetector::with_default_config();
//!
//! // Stream observations
//! for value in time_series {
//!     let result = detector.update(value);
//!     match result.phase {
//!         Phase::Critical => println!("Transition imminent!"),
//!         Phase::Approaching => println!("Watch closely..."),
//!         _ => {}
//!     }
//! }
//! ```
//!
//! ## Quick Start: Compression Dynamics
//!
//! ```rust,ignore
//! use nucleation::{CompressionDynamicsModel, CompressionScheme};
//!
//! let mut model = CompressionDynamicsModel::new(50);
//!
//! model.register_actor("USA", Some(vec![/* distribution */]));
//! model.register_actor("RUS", Some(vec![/* distribution */]));
//!
//! let potential = model.conflict_potential("USA", "RUS").unwrap();
//! println!("Conflict potential Φ = {:.3}", potential.phi);
//! ```
//!
//! ## Quick Start: Shepherd Dynamics (Unified)
//!
//! ```rust,ignore
//! use nucleation::{ShepherdDynamics, AlertLevel};
//!
//! let mut shepherd = ShepherdDynamics::new(50);
//!
//! shepherd.register_actor("USA", None);
//! shepherd.register_actor("RUS", None);
//!
//! // Update with observations over time
//! let alerts = shepherd.update_actor("USA", &observation, timestamp);
//!
//! for alert in alerts {
//!     if alert.alert_level >= AlertLevel::Orange {
//!         println!("WARNING: {}", alert.message);
//!     }
//! }
//! ```
//!
//! ## Architecture
//!
//! ```text
//! ┌─────────────────────────────────────────────────────────────────────────┐
//! │                            nucleation                                    │
//! ├─────────────────────────────────────────────────────────────────────────┤
//! │  CORE DETECTION                                                          │
//! │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────────┐  │
//! │  │  variance.rs    │  │  compression.rs │  │  shepherd.rs            │  │
//! │  │  - Inflection   │  │  - Schemes      │  │  - Unified EWS         │  │
//! │  │  - Phase detect │→ │  - Φ(A,B)       │→ │  - Nucleation alerts   │  │
//! │  │  - d²V/dt²      │  │  - Grievance    │  │  - Multi-dyad monitor  │  │
//! │  └─────────────────┘  └─────────────────┘  └─────────────────────────┘  │
//! ├─────────────────────────────────────────────────────────────────────────┤
//! │  PRIMITIVES                                                              │
//! │  entropy.rs       │  distance.rs      │  signal.rs                      │
//! │  - Shannon        │  - Hellinger      │  - RollingStats                 │
//! │  - Permutation    │  - JS-divergence  │  - GradientTracker              │
//! │  - KL-divergence  │  - Fisher-Rao     │  - PhaseTracker                 │
//! ├─────────────────────────────────────────────────────────────────────────┤
//! │  COGNITIVE (LEGACY)                                                      │
//! │  detector.rs      │  acr.rs                                              │
//! │  - CognitiveDetector │  - ACRController                                  │
//! │  - InsightPrecursor  │  - Kuramoto dynamics                              │
//! └─────────────────────────────────────────────────────────────────────────┘
//! ```
//!
//! ## Key Equations
//!
//! **Conflict Potential** (Compression Dynamics):
//! ```text
//! Φ(A,B) = D_KL(C_A || C_B) + D_KL(C_B || C_A)
//! ```
//!
//! **Variance Inflection** (Phase Detection):
//! ```text
//! Signal = |d²V/dt²| where V = rolling variance
//! Transition when z-score(Signal) > threshold
//! ```
//!
//! **Shepherd Dynamics** (Unified):
//! ```text
//! Monitor Φ(t) trajectory with variance inflection detector
//! Alert when nucleation signature detected in divergence dynamics
//! ```
//!
//! ## Crate Features
//!
//! - `std`: Standard library support (default)
//! - `wasm`: WASM-compatible builds with JS bindings
//! - `serialize`: Serde serialization support
//! - `simd`: SIMD optimizations (requires nightly)

// Core modules
pub mod variance;
pub mod compression;
pub mod shepherd;

// Primitive modules
pub mod entropy;
pub mod distance;
pub mod signal;

// Cognitive/Legacy modules
pub mod detector;
pub mod acr;

// ============================================================================
// Core exports (Phase transition & Conflict)
// ============================================================================

pub use variance::{
    VarianceInflectionDetector,
    VarianceConfig,
    SmoothingKernel,
    Phase,
    InflectionResult,
};

pub use compression::{
    CompressionScheme,
    CompressionDynamicsModel,
    ConflictPotential,
    Grievance,
    SchemeSource,
};

pub use shepherd::{
    ShepherdDynamics,
    NucleationAlert,
    AlertLevel,
};

// ============================================================================
// Primitive exports
// ============================================================================

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

// ============================================================================
// Cognitive/Legacy exports (renamed for clarity)
// ============================================================================

pub use detector::{
    NucleationDetector as CognitiveDetector,
    DetectorConfig as CognitiveConfig,
    DetectionPhase as CognitivePhase,
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

// ============================================================================
// Convenience re-exports (backwards compatibility)
// ============================================================================

// Keep old names for backwards compatibility
pub use detector::NucleationDetector;
pub use detector::DetectorConfig;
pub use detector::DetectionPhase;

// ============================================================================
// Version and factories
// ============================================================================

/// Crate version
pub const VERSION: &str = env!("CARGO_PKG_VERSION");

/// Create a variance inflection detector with default config.
pub fn create_variance_detector() -> VarianceInflectionDetector {
    VarianceInflectionDetector::with_default_config()
}

/// Create a compression dynamics model.
pub fn create_compression_model(n_categories: usize) -> CompressionDynamicsModel {
    CompressionDynamicsModel::new(n_categories)
}

/// Create a Shepherd Dynamics system.
pub fn create_shepherd(n_categories: usize) -> ShepherdDynamics {
    ShepherdDynamics::new(n_categories)
}

/// Create a cognitive detector (legacy).
pub fn create_detector(sensitivity: &str) -> NucleationDetector {
    NucleationDetector::with_sensitivity(sensitivity)
}

/// Create an ACR controller (legacy).
pub fn create_controller(modality: CognitiveModality) -> ACRController {
    ACRController::new(modality)
}

// ============================================================================
// WASM bindings (when feature enabled)
// ============================================================================

#[cfg(feature = "wasm")]
pub mod wasm;

// ============================================================================
// Tests
// ============================================================================

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_variance_detector_creation() {
        let detector = create_variance_detector();
        assert_eq!(detector.count(), 0);
    }

    #[test]
    fn test_compression_model_creation() {
        let model = create_compression_model(10);
        assert!(model.actors().is_empty());
    }

    #[test]
    fn test_shepherd_creation() {
        let shepherd = create_shepherd(10);
        assert!(shepherd.actors().is_empty());
    }

    #[test]
    fn test_legacy_exports() {
        let _ = create_detector("balanced");
        let _ = create_controller(CognitiveModality::Integration);
        let _ = shannon_entropy(&[1, 2, 3, 4]);
        let _ = hellinger_distance(&[0.5, 0.5], &[0.5, 0.5]);
    }

    #[test]
    fn test_version() {
        assert!(!VERSION.is_empty());
        assert!(VERSION.starts_with("0.2"));
    }
}
