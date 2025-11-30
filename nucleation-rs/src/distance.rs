//! Distribution distance metrics for cognitive state detection
//!
//! Implements Hellinger, Jensen-Shannon, and Fisher-Rao distances
//! for measuring distributional shift in behavioral patterns.

/// Hellinger distance: d_H(P, Q) = (1/sqrt(2)) * sqrt(sum((sqrt(p) - sqrt(q))^2))
/// Range: [0, 1], where 0 = identical, 1 = disjoint support
pub fn hellinger_distance(p: &[f64], q: &[f64]) -> f64 {
    assert_eq!(p.len(), q.len(), "Distributions must have same length");

    let sum_sq: f64 = p
        .iter()
        .zip(q.iter())
        .map(|(pi, qi)| {
            let diff = pi.sqrt() - qi.sqrt();
            diff * diff
        })
        .sum();

    (sum_sq / 2.0).sqrt()
}

/// Jensen-Shannon divergence: symmetric, bounded KL
/// D_JS(P || Q) = 0.5 * D_KL(P || M) + 0.5 * D_KL(Q || M)
/// where M = 0.5 * (P + Q)
pub fn jensen_shannon_divergence(p: &[f64], q: &[f64]) -> f64 {
    assert_eq!(p.len(), q.len(), "Distributions must have same length");

    // Compute mixture M
    let m: Vec<f64> = p.iter().zip(q.iter()).map(|(pi, qi)| 0.5 * (pi + qi)).collect();

    // KL(P || M) + KL(Q || M)
    let kl_p_m = kl_divergence_internal(p, &m);
    let kl_q_m = kl_divergence_internal(q, &m);

    0.5 * (kl_p_m + kl_q_m)
}

fn kl_divergence_internal(p: &[f64], q: &[f64]) -> f64 {
    let mut div = 0.0;
    for (pi, qi) in p.iter().zip(q.iter()) {
        if *pi > 1e-12 && *qi > 1e-12 {
            div += pi * (pi / qi).ln();
        }
    }
    div
}

/// Jensen-Shannon distance (metric version): sqrt(D_JS)
pub fn jensen_shannon_distance(p: &[f64], q: &[f64]) -> f64 {
    jensen_shannon_divergence(p, q).sqrt()
}

/// Fisher-Rao distance (geodesic on probability simplex)
/// d_FR(P, Q) = 2 * arccos(sum(sqrt(p * q)))
pub fn fisher_rao_distance(p: &[f64], q: &[f64]) -> f64 {
    assert_eq!(p.len(), q.len(), "Distributions must have same length");

    let bhattacharyya: f64 = p
        .iter()
        .zip(q.iter())
        .map(|(pi, qi)| (pi * qi).sqrt())
        .sum();

    // Clamp to valid arccos domain
    let clamped = bhattacharyya.clamp(-1.0, 1.0);
    2.0 * clamped.acos()
}

/// Bhattacharyya coefficient: BC(P, Q) = sum(sqrt(p * q))
/// Range: [0, 1], where 1 = identical
pub fn bhattacharyya_coefficient(p: &[f64], q: &[f64]) -> f64 {
    assert_eq!(p.len(), q.len(), "Distributions must have same length");

    p.iter()
        .zip(q.iter())
        .map(|(pi, qi)| (pi * qi).sqrt())
        .sum()
}

/// Bhattacharyya distance: -ln(BC)
pub fn bhattacharyya_distance(p: &[f64], q: &[f64]) -> f64 {
    let bc = bhattacharyya_coefficient(p, q);
    if bc <= 0.0 {
        f64::INFINITY
    } else {
        -bc.ln()
    }
}

/// Total variation distance: TV(P, Q) = 0.5 * sum(|p - q|)
/// Range: [0, 1]
pub fn total_variation_distance(p: &[f64], q: &[f64]) -> f64 {
    assert_eq!(p.len(), q.len(), "Distributions must have same length");

    0.5 * p
        .iter()
        .zip(q.iter())
        .map(|(pi, qi)| (pi - qi).abs())
        .sum::<f64>()
}

/// Wasserstein-1 (Earth Mover's) distance for 1D distributions
/// Assumes p and q are PMFs over ordered discrete support
pub fn wasserstein_1d(p: &[f64], q: &[f64]) -> f64 {
    assert_eq!(p.len(), q.len(), "Distributions must have same length");

    // Compute CDFs
    let cdf_p: Vec<f64> = p
        .iter()
        .scan(0.0, |acc, &x| {
            *acc += x;
            Some(*acc)
        })
        .collect();

    let cdf_q: Vec<f64> = q
        .iter()
        .scan(0.0, |acc, &x| {
            *acc += x;
            Some(*acc)
        })
        .collect();

    // EMD = integral of |CDF_P - CDF_Q|
    cdf_p
        .iter()
        .zip(cdf_q.iter())
        .map(|(cp, cq)| (cp - cq).abs())
        .sum()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_hellinger_identical() {
        let p = vec![0.25, 0.25, 0.25, 0.25];
        let d = hellinger_distance(&p, &p);
        assert!(d.abs() < 1e-10);
    }

    #[test]
    fn test_hellinger_disjoint() {
        let p = vec![1.0, 0.0, 0.0, 0.0];
        let q = vec![0.0, 1.0, 0.0, 0.0];
        let d = hellinger_distance(&p, &q);
        assert!((d - 1.0).abs() < 1e-10);
    }

    #[test]
    fn test_jensen_shannon_symmetric() {
        let p = vec![0.5, 0.3, 0.2];
        let q = vec![0.3, 0.4, 0.3];
        let d_pq = jensen_shannon_divergence(&p, &q);
        let d_qp = jensen_shannon_divergence(&q, &p);
        assert!((d_pq - d_qp).abs() < 1e-10);
    }

    #[test]
    fn test_total_variation_bounds() {
        let p = vec![0.5, 0.5];
        let q = vec![0.3, 0.7];
        let tv = total_variation_distance(&p, &q);
        assert!(tv >= 0.0 && tv <= 1.0);
    }

    #[test]
    fn test_fisher_rao_identical() {
        let p = vec![0.25, 0.25, 0.25, 0.25];
        let d = fisher_rao_distance(&p, &p);
        assert!(d.abs() < 1e-10);
    }
}
