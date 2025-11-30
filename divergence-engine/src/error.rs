//! Error types for the divergence engine.

use thiserror::Error;

/// Main error type for divergence engine operations.
#[derive(Error, Debug, Clone)]
pub enum DivergenceError {
    /// Distribution dimensions don't match
    #[error("Dimension mismatch: expected {expected}, got {got}")]
    DimensionMismatch { expected: usize, got: usize },

    /// Actor not found in model
    #[error("Unknown actor: {0}")]
    UnknownActor(String),

    /// Invalid probability distribution
    #[error("Invalid distribution: {0}")]
    InvalidDistribution(String),

    /// Numerical error (overflow, underflow, NaN)
    #[error("Numerical error: {0}")]
    NumericalError(String),

    /// Configuration error
    #[error("Configuration error: {0}")]
    ConfigError(String),

    /// Serialization error
    #[error("Serialization error: {0}")]
    SerializationError(String),
}

/// Result type alias for divergence operations.
pub type Result<T> = std::result::Result<T, DivergenceError>;

impl DivergenceError {
    /// Check if this is a recoverable error
    pub fn is_recoverable(&self) -> bool {
        matches!(
            self,
            DivergenceError::NumericalError(_) | DivergenceError::InvalidDistribution(_)
        )
    }
}

#[cfg(feature = "wasm")]
impl From<DivergenceError> for wasm_bindgen::JsValue {
    fn from(err: DivergenceError) -> Self {
        wasm_bindgen::JsValue::from_str(&err.to_string())
    }
}
