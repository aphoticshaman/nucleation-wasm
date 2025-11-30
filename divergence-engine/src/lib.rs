//! # Divergence Engine
//!
//! High-performance compression dynamics engine for conflict prediction.
//!
//! ## Theory
//!
//! Conflict potential between actors A and B equals the symmetric
//! KL divergence of their "compression schemes" - their internal predictive
//! models mapping observations to categories.
//!
//! ```text
//! Φ(A,B) = D_KL(C_A || C_B) + D_KL(C_B || C_A)
//! ```
//!
//! ## Features
//!
//! - `std` (default): Standard library support
//! - `wasm`: WebAssembly bindings via wasm-bindgen
//! - `streaming`: Async streaming interface for real-time data
//!
//! ## Example
//!
//! ```rust
//! use divergence_engine::{CompressionScheme, CompressionDynamicsModel};
//!
//! let mut model = CompressionDynamicsModel::new(10);
//!
//! // Register actors with different worldviews
//! let dist_a = vec![0.4, 0.3, 0.15, 0.1, 0.03, 0.01, 0.005, 0.003, 0.001, 0.001];
//! let dist_b = vec![0.15, 0.12, 0.11, 0.10, 0.10, 0.10, 0.10, 0.08, 0.07, 0.07];
//!
//! model.register_actor("USA", Some(dist_a), None);
//! model.register_actor("RUS", Some(dist_b), None);
//!
//! // Compute conflict potential
//! let potential = model.compute_conflict_potential("USA", "RUS").unwrap();
//! println!("Φ(USA, RUS) = {:.4}", potential.phi);
//! ```
//!
//! Author: Ryan J Cardwell (Archer Phoenix)

pub mod divergence;
pub mod error;
pub mod model;
pub mod scheme;

#[cfg(feature = "streaming")]
pub mod streaming;

#[cfg(feature = "wasm")]
pub mod wasm;

// Re-exports
pub use divergence::*;
pub use error::*;
pub use model::*;
pub use scheme::*;

#[cfg(feature = "streaming")]
pub use streaming::*;

/// Crate version
pub const VERSION: &str = env!("CARGO_PKG_VERSION");

/// Initialize the engine (call once, especially important for WASM)
#[cfg(feature = "wasm")]
pub fn init() {
    console_error_panic_hook::set_once();
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_basic_workflow() {
        let mut model = CompressionDynamicsModel::new(10);

        let dist_a = vec![0.4, 0.3, 0.15, 0.1, 0.03, 0.01, 0.005, 0.003, 0.001, 0.001];
        let dist_b = vec![0.15, 0.12, 0.11, 0.10, 0.10, 0.10, 0.10, 0.08, 0.07, 0.07];

        model.register_actor("USA", Some(dist_a), None);
        model.register_actor("RUS", Some(dist_b), None);

        let potential = model.compute_conflict_potential("USA", "RUS").unwrap();

        assert!(potential.phi > 0.0);
        assert!(potential.js >= 0.0 && potential.js <= 1.0);
        assert!(potential.hellinger >= 0.0 && potential.hellinger <= 1.0);
    }
}
