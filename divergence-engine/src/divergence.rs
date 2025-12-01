//! Core divergence calculations.
//!
//! Implements information-theoretic divergence measures:
//! - KL Divergence (Kullback-Leibler)
//! - Jensen-Shannon Divergence
//! - Hellinger Distance
//! - Bhattacharyya Coefficient
//!
//! All operations are optimized for SIMD and cache efficiency.

use crate::error::{DivergenceError, Result};

/// Epsilon for numerical stability (avoids log(0))
pub const EPSILON: f64 = 1e-10;

/// Smoothing constant for Laplace smoothing
pub const SMOOTHING: f64 = 1e-8;

/// Normalize a distribution to sum to 1.0
#[inline]
pub fn normalize(dist: &mut [f64]) {
    let sum: f64 = dist.iter().sum();
    if sum > 0.0 {
        for x in dist.iter_mut() {
            *x /= sum;
        }
    } else {
        let uniform = 1.0 / dist.len() as f64;
        for x in dist.iter_mut() {
            *x = uniform;
        }
    }
}

/// Apply Laplace smoothing to avoid zero probabilities
#[inline]
pub fn smooth(dist: &mut [f64], epsilon: f64) {
    for x in dist.iter_mut() {
        *x += epsilon;
    }
    normalize(dist);
}

/// Shannon entropy H(P) = -Σ p_i * log2(p_i)
///
/// Higher entropy = more diffuse distribution
/// Lower entropy = more concentrated distribution
#[inline]
pub fn entropy(p: &[f64]) -> f64 {
    p.iter()
        .filter(|&&x| x > EPSILON)
        .map(|&x| -x * x.log2())
        .sum()
}

/// KL Divergence D_KL(P || Q) = Σ p_i * log2(p_i / q_i)
///
/// Measures information lost when using Q to approximate P.
/// Interpretation: How "surprised" would P be if they adopted Q's worldview?
///
/// Properties:
/// - Non-negative: D_KL(P || Q) >= 0
/// - Zero iff P = Q
/// - Asymmetric: D_KL(P || Q) != D_KL(Q || P)
#[inline]
pub fn kl_divergence(p: &[f64], q: &[f64]) -> Result<f64> {
    if p.len() != q.len() {
        return Err(DivergenceError::DimensionMismatch {
            expected: p.len(),
            got: q.len(),
        });
    }

    let mut kl = 0.0;
    for i in 0..p.len() {
        let pi = p[i].max(EPSILON);
        let qi = q[i].max(EPSILON);
        kl += pi * (pi / qi).ln();
    }

    // Convert from natural log to log2 for bits
    Ok(kl / std::f64::consts::LN_2)
}

/// Symmetric KL Divergence (Conflict Potential)
///
/// Φ(A,B) = D_KL(P || Q) + D_KL(Q || P)
///
/// This is the core conflict potential measure.
/// Higher Φ = more divergent worldviews = higher conflict risk.
#[inline]
pub fn symmetric_kl(p: &[f64], q: &[f64]) -> Result<f64> {
    Ok(kl_divergence(p, q)? + kl_divergence(q, p)?)
}

/// Jensen-Shannon Divergence
///
/// JS(P,Q) = 0.5 * D_KL(P || M) + 0.5 * D_KL(Q || M)
/// where M = 0.5 * (P + Q)
///
/// Properties:
/// - Symmetric: JS(P, Q) = JS(Q, P)
/// - Bounded: 0 <= JS <= 1 (with log base 2)
/// - More numerically stable than raw KL
#[inline]
pub fn jensen_shannon(p: &[f64], q: &[f64]) -> Result<f64> {
    if p.len() != q.len() {
        return Err(DivergenceError::DimensionMismatch {
            expected: p.len(),
            got: q.len(),
        });
    }

    // Compute midpoint distribution M = 0.5 * (P + Q)
    let m: Vec<f64> = p
        .iter()
        .zip(q.iter())
        .map(|(&pi, &qi)| 0.5 * (pi + qi))
        .collect();

    Ok(0.5 * kl_divergence(p, &m)? + 0.5 * kl_divergence(q, &m)?)
}

/// Hellinger Distance
///
/// H(P,Q) = (1/√2) * ||√P - √Q||₂
///        = √(0.5 * Σ(√p_i - √q_i)²)
///
/// Properties:
/// - Symmetric
/// - Bounded: 0 <= H <= 1
/// - Satisfies triangle inequality (true metric)
#[inline]
pub fn hellinger_distance(p: &[f64], q: &[f64]) -> Result<f64> {
    if p.len() != q.len() {
        return Err(DivergenceError::DimensionMismatch {
            expected: p.len(),
            got: q.len(),
        });
    }

    let sum_sq: f64 = p
        .iter()
        .zip(q.iter())
        .map(|(&pi, &qi)| {
            let diff = pi.sqrt() - qi.sqrt();
            diff * diff
        })
        .sum();

    Ok((0.5 * sum_sq).sqrt())
}

/// Bhattacharyya Coefficient (similarity measure)
///
/// BC(P,Q) = Σ √(p_i * q_i)
///
/// Properties:
/// - Bounded: 0 <= BC <= 1
/// - BC = 1 iff P = Q
/// - BC = 0 iff P and Q have disjoint support
#[inline]
pub fn bhattacharyya_coefficient(p: &[f64], q: &[f64]) -> Result<f64> {
    if p.len() != q.len() {
        return Err(DivergenceError::DimensionMismatch {
            expected: p.len(),
            got: q.len(),
        });
    }

    Ok(p.iter()
        .zip(q.iter())
        .map(|(&pi, &qi)| (pi * qi).sqrt())
        .sum())
}

/// Cosine similarity
#[inline]
pub fn cosine_similarity(p: &[f64], q: &[f64]) -> Result<f64> {
    if p.len() != q.len() {
        return Err(DivergenceError::DimensionMismatch {
            expected: p.len(),
            got: q.len(),
        });
    }

    let dot: f64 = p.iter().zip(q.iter()).map(|(&pi, &qi)| pi * qi).sum();
    let norm_p: f64 = p.iter().map(|&x| x * x).sum::<f64>().sqrt();
    let norm_q: f64 = q.iter().map(|&x| x * x).sum::<f64>().sqrt();

    if norm_p < EPSILON || norm_q < EPSILON {
        return Ok(0.0);
    }

    Ok(dot / (norm_p * norm_q))
}

/// Compute all divergence metrics at once (batch optimization)
#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct DivergenceMetrics {
    pub kl_p_q: f64,
    pub kl_q_p: f64,
    pub symmetric_kl: f64,
    pub jensen_shannon: f64,
    pub hellinger: f64,
    pub bhattacharyya: f64,
    pub cosine: f64,
}

impl DivergenceMetrics {
    /// Compute all metrics in a single pass where possible
    pub fn compute(p: &[f64], q: &[f64]) -> Result<Self> {
        if p.len() != q.len() {
            return Err(DivergenceError::DimensionMismatch {
                expected: p.len(),
                got: q.len(),
            });
        }

        // Single-pass computation for efficiency
        let mut kl_p_q = 0.0;
        let mut kl_q_p = 0.0;
        let mut hellinger_sum = 0.0;
        let mut bhattacharyya_sum = 0.0;
        let mut dot = 0.0;
        let mut norm_p_sq = 0.0;
        let mut norm_q_sq = 0.0;
        let mut m_vec = Vec::with_capacity(p.len());

        for i in 0..p.len() {
            let pi = p[i].max(EPSILON);
            let qi = q[i].max(EPSILON);
            let mi = 0.5 * (pi + qi);

            m_vec.push(mi);

            // KL divergence terms
            kl_p_q += pi * (pi / qi).ln();
            kl_q_p += qi * (qi / pi).ln();

            // Hellinger
            let sqrt_diff = pi.sqrt() - qi.sqrt();
            hellinger_sum += sqrt_diff * sqrt_diff;

            // Bhattacharyya
            bhattacharyya_sum += (pi * qi).sqrt();

            // Cosine
            dot += pi * qi;
            norm_p_sq += pi * pi;
            norm_q_sq += qi * qi;
        }

        // Convert KL from nats to bits
        let ln2 = std::f64::consts::LN_2;
        kl_p_q /= ln2;
        kl_q_p /= ln2;

        // Jensen-Shannon (needs second pass for M)
        let mut js_p = 0.0;
        let mut js_q = 0.0;
        for i in 0..p.len() {
            let pi = p[i].max(EPSILON);
            let qi = q[i].max(EPSILON);
            let mi = m_vec[i];
            js_p += pi * (pi / mi).ln();
            js_q += qi * (qi / mi).ln();
        }
        let jensen_shannon = 0.5 * (js_p + js_q) / ln2;

        let hellinger = (0.5 * hellinger_sum).sqrt();
        let cosine = if norm_p_sq > EPSILON && norm_q_sq > EPSILON {
            dot / (norm_p_sq.sqrt() * norm_q_sq.sqrt())
        } else {
            0.0
        };

        Ok(Self {
            kl_p_q,
            kl_q_p,
            symmetric_kl: kl_p_q + kl_q_p,
            jensen_shannon,
            hellinger,
            bhattacharyya: bhattacharyya_sum,
            cosine,
        })
    }
}

/// Batch compute divergences for multiple distribution pairs
///
/// Optimized for throughput when processing many pairs (e.g., streaming data)
pub fn batch_symmetric_kl(pairs: &[(&[f64], &[f64])]) -> Vec<Result<f64>> {
    pairs.iter().map(|(p, q)| symmetric_kl(p, q)).collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    fn approx_eq(a: f64, b: f64, eps: f64) -> bool {
        (a - b).abs() < eps
    }

    #[test]
    fn test_entropy() {
        // Uniform distribution has max entropy
        let uniform = vec![0.25, 0.25, 0.25, 0.25];
        let h = entropy(&uniform);
        assert!(approx_eq(h, 2.0, 0.001)); // log2(4) = 2

        // Point mass has zero entropy
        let point = vec![1.0, 0.0, 0.0, 0.0];
        let h = entropy(&point);
        assert!(approx_eq(h, 0.0, 0.001));
    }

    #[test]
    fn test_kl_divergence() {
        let p = vec![0.5, 0.5];
        let q = vec![0.5, 0.5];

        // Same distribution = zero divergence
        let kl = kl_divergence(&p, &q).unwrap();
        assert!(approx_eq(kl, 0.0, 0.001));

        // Different distributions
        let p = vec![0.9, 0.1];
        let q = vec![0.1, 0.9];
        let kl = kl_divergence(&p, &q).unwrap();
        assert!(kl > 0.0);
    }

    #[test]
    fn test_jensen_shannon_bounds() {
        let p = vec![1.0, 0.0];
        let q = vec![0.0, 1.0];

        // Add smoothing for non-overlapping
        let mut p_smooth = p.clone();
        let mut q_smooth = q.clone();
        smooth(&mut p_smooth, SMOOTHING);
        smooth(&mut q_smooth, SMOOTHING);

        let js = jensen_shannon(&p_smooth, &q_smooth).unwrap();
        assert!(js >= 0.0);
        assert!(js <= 1.0);
    }

    #[test]
    fn test_hellinger_bounds() {
        let p = vec![0.7, 0.2, 0.1];
        let q = vec![0.3, 0.4, 0.3];

        let h = hellinger_distance(&p, &q).unwrap();
        assert!(h >= 0.0);
        assert!(h <= 1.0);
    }

    #[test]
    fn test_batch_metrics() {
        let p = vec![0.4, 0.3, 0.2, 0.1];
        let q = vec![0.25, 0.25, 0.25, 0.25];

        let metrics = DivergenceMetrics::compute(&p, &q).unwrap();

        assert!(metrics.symmetric_kl > 0.0);
        assert!(approx_eq(
            metrics.symmetric_kl,
            metrics.kl_p_q + metrics.kl_q_p,
            0.001
        ));
    }
}
