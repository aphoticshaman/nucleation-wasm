//! Entropy calculations for behavioral signal analysis
//!
//! Implements Shannon, permutation, and relative entropy measures
//! calibrated for cognitive event detection.

use std::collections::HashMap;

/// Shannon entropy: H(X) = -sum(p(x) * log2(p(x)))
pub fn shannon_entropy(data: &[u32]) -> f64 {
    if data.is_empty() {
        return 0.0;
    }

    let mut counts: HashMap<u32, usize> = HashMap::new();
    for &val in data {
        *counts.entry(val).or_insert(0) += 1;
    }

    let n = data.len() as f64;
    let mut entropy = 0.0;

    for &count in counts.values() {
        if count > 0 {
            let p = count as f64 / n;
            entropy -= p * p.log2();
        }
    }

    entropy
}

/// Normalized Shannon entropy in [0, 1]
pub fn normalized_entropy(data: &[u32]) -> f64 {
    if data.is_empty() {
        return 0.0;
    }

    let unique_count = data.iter().collect::<std::collections::HashSet<_>>().len();
    if unique_count <= 1 {
        return 0.0;
    }

    let max_entropy = (unique_count as f64).log2();
    let h = shannon_entropy(data);

    h / max_entropy
}

/// Permutation entropy for ordinal patterns
/// Captures temporal structure in time series
pub fn permutation_entropy(data: &[f64], order: usize, delay: usize) -> f64 {
    if data.len() < order * delay {
        return 0.0;
    }

    let mut pattern_counts: HashMap<Vec<usize>, usize> = HashMap::new();
    let n_patterns = data.len() - (order - 1) * delay;

    for i in 0..n_patterns {
        // Extract embedding vector
        let mut indices: Vec<(usize, f64)> = (0..order)
            .map(|j| (j, data[i + j * delay]))
            .collect();

        // Sort by value to get ordinal pattern
        indices.sort_by(|a, b| a.1.partial_cmp(&b.1).unwrap_or(std::cmp::Ordering::Equal));

        let pattern: Vec<usize> = indices.iter().map(|(idx, _)| *idx).collect();
        *pattern_counts.entry(pattern).or_insert(0) += 1;
    }

    // Compute entropy of pattern distribution
    let total = n_patterns as f64;
    let mut entropy = 0.0;

    for &count in pattern_counts.values() {
        if count > 0 {
            let p = count as f64 / total;
            entropy -= p * p.log2();
        }
    }

    entropy
}

/// Relative entropy (KL divergence): D_KL(P || Q)
/// Measures divergence from baseline distribution
pub fn kl_divergence(p: &[f64], q: &[f64]) -> f64 {
    assert_eq!(p.len(), q.len(), "Distributions must have same length");

    let mut divergence = 0.0;
    for (pi, qi) in p.iter().zip(q.iter()) {
        if *pi > 0.0 && *qi > 0.0 {
            divergence += pi * (pi / qi).ln();
        }
    }

    divergence
}

/// Entropy rate estimation using block entropy
/// H_rate = lim(H(X_n | X_1, ..., X_{n-1}))
pub fn entropy_rate(data: &[u32], block_size: usize) -> f64 {
    if data.len() < block_size * 2 {
        return shannon_entropy(data);
    }

    // Compute block entropies
    let h_k = block_entropy(data, block_size);
    let h_k_minus_1 = block_entropy(data, block_size - 1);

    // Entropy rate approximation
    h_k - h_k_minus_1
}

fn block_entropy(data: &[u32], block_size: usize) -> f64 {
    if data.len() < block_size {
        return 0.0;
    }

    let mut block_counts: HashMap<Vec<u32>, usize> = HashMap::new();
    let n_blocks = data.len() - block_size + 1;

    for i in 0..n_blocks {
        let block: Vec<u32> = data[i..i + block_size].to_vec();
        *block_counts.entry(block).or_insert(0) += 1;
    }

    let total = n_blocks as f64;
    let mut entropy = 0.0;

    for &count in block_counts.values() {
        if count > 0 {
            let p = count as f64 / total;
            entropy -= p * p.log2();
        }
    }

    entropy
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_shannon_entropy_uniform() {
        // Uniform distribution over 4 symbols: H = log2(4) = 2
        let data = vec![0, 1, 2, 3, 0, 1, 2, 3];
        let h = shannon_entropy(&data);
        assert!((h - 2.0).abs() < 0.01);
    }

    #[test]
    fn test_shannon_entropy_constant() {
        // Constant: H = 0
        let data = vec![1, 1, 1, 1];
        let h = shannon_entropy(&data);
        assert!(h.abs() < 0.001);
    }

    #[test]
    fn test_normalized_entropy() {
        let data = vec![0, 1, 2, 3];
        let h = normalized_entropy(&data);
        assert!((h - 1.0).abs() < 0.01); // Maximum entropy
    }

    #[test]
    fn test_permutation_entropy() {
        // Regular ascending: low entropy
        let ascending: Vec<f64> = (0..20).map(|x| x as f64).collect();
        let h_asc = permutation_entropy(&ascending, 3, 1);

        // Random-ish: higher entropy
        let mixed = vec![1.0, 4.0, 2.0, 5.0, 3.0, 6.0, 2.0, 5.0, 1.0, 4.0];
        let h_mix = permutation_entropy(&mixed, 3, 1);

        assert!(h_mix > h_asc);
    }
}
