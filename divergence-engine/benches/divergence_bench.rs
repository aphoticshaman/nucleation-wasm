//! Benchmarks for the divergence engine.
//!
//! Run with: cargo bench

use criterion::{black_box, criterion_group, criterion_main, BenchmarkId, Criterion, Throughput};
use divergence_engine::{
    divergence::{jensen_shannon, kl_divergence, symmetric_kl, DivergenceMetrics},
    CompressionDynamicsModel, CompressionScheme,
};

fn generate_distribution(n: usize, seed: u64) -> Vec<f64> {
    // Simple deterministic pseudo-random for reproducibility
    let mut dist = Vec::with_capacity(n);
    let mut x = seed;
    for _ in 0..n {
        x = x.wrapping_mul(6364136223846793005).wrapping_add(1);
        dist.push((x as f64) / (u64::MAX as f64));
    }
    // Normalize
    let sum: f64 = dist.iter().sum();
    for x in &mut dist {
        *x /= sum;
    }
    dist
}

fn bench_kl_divergence(c: &mut Criterion) {
    let mut group = c.benchmark_group("kl_divergence");

    for size in [10, 50, 100, 500, 1000].iter() {
        let p = generate_distribution(*size, 42);
        let q = generate_distribution(*size, 123);

        group.throughput(Throughput::Elements(*size as u64));
        group.bench_with_input(BenchmarkId::from_parameter(size), size, |b, _| {
            b.iter(|| kl_divergence(black_box(&p), black_box(&q)))
        });
    }

    group.finish();
}

fn bench_symmetric_kl(c: &mut Criterion) {
    let mut group = c.benchmark_group("symmetric_kl");

    for size in [10, 50, 100, 500, 1000].iter() {
        let p = generate_distribution(*size, 42);
        let q = generate_distribution(*size, 123);

        group.throughput(Throughput::Elements(*size as u64));
        group.bench_with_input(BenchmarkId::from_parameter(size), size, |b, _| {
            b.iter(|| symmetric_kl(black_box(&p), black_box(&q)))
        });
    }

    group.finish();
}

fn bench_jensen_shannon(c: &mut Criterion) {
    let mut group = c.benchmark_group("jensen_shannon");

    for size in [10, 50, 100, 500, 1000].iter() {
        let p = generate_distribution(*size, 42);
        let q = generate_distribution(*size, 123);

        group.throughput(Throughput::Elements(*size as u64));
        group.bench_with_input(BenchmarkId::from_parameter(size), size, |b, _| {
            b.iter(|| jensen_shannon(black_box(&p), black_box(&q)))
        });
    }

    group.finish();
}

fn bench_all_metrics(c: &mut Criterion) {
    let mut group = c.benchmark_group("all_metrics");

    for size in [10, 50, 100, 500].iter() {
        let p = generate_distribution(*size, 42);
        let q = generate_distribution(*size, 123);

        group.throughput(Throughput::Elements(*size as u64));
        group.bench_with_input(BenchmarkId::from_parameter(size), size, |b, _| {
            b.iter(|| DivergenceMetrics::compute(black_box(&p), black_box(&q)))
        });
    }

    group.finish();
}

fn bench_scheme_operations(c: &mut Criterion) {
    let mut group = c.benchmark_group("compression_scheme");

    for size in [10, 50, 100].iter() {
        let dist_a = generate_distribution(*size, 42);
        let dist_b = generate_distribution(*size, 123);

        let scheme_a = CompressionScheme::new("A", dist_a.clone(), None);
        let scheme_b = CompressionScheme::new("B", dist_b.clone(), None);

        group.bench_with_input(
            BenchmarkId::new("symmetric_divergence", size),
            size,
            |b, _| {
                b.iter(|| scheme_a.symmetric_divergence(black_box(&scheme_b)))
            },
        );

        group.bench_with_input(BenchmarkId::new("all_metrics", size), size, |b, _| {
            b.iter(|| scheme_a.all_metrics(black_box(&scheme_b)))
        });
    }

    group.finish();
}

fn bench_model_operations(c: &mut Criterion) {
    let mut group = c.benchmark_group("model");

    // Benchmark with different numbers of actors
    for n_actors in [5, 10, 20].iter() {
        let mut model = CompressionDynamicsModel::new(50);

        // Register actors
        for i in 0..*n_actors {
            let dist = generate_distribution(50, i as u64);
            model.register_actor(format!("Actor{}", i), Some(dist), None);
        }

        group.bench_with_input(
            BenchmarkId::new("compute_all_potentials", n_actors),
            n_actors,
            |b, _| {
                b.iter(|| {
                    let mut m = model.clone();
                    m.compute_all_potentials()
                })
            },
        );

        group.bench_with_input(
            BenchmarkId::new("predict_escalation", n_actors),
            n_actors,
            |b, _| {
                b.iter(|| {
                    let mut m = model.clone();
                    m.predict_escalation("Actor0", "Actor1", 0.5, 0.0)
                })
            },
        );
    }

    group.finish();
}

fn bench_batch_updates(c: &mut Criterion) {
    let mut group = c.benchmark_group("batch_updates");

    for batch_size in [10, 100, 1000].iter() {
        let mut model = CompressionDynamicsModel::new(50);
        model.register_actor("A", None, None);

        let observations: Vec<Vec<f64>> = (0..*batch_size)
            .map(|i| generate_distribution(50, i as u64))
            .collect();

        group.throughput(Throughput::Elements(*batch_size as u64));
        group.bench_with_input(
            BenchmarkId::from_parameter(batch_size),
            batch_size,
            |b, _| {
                b.iter(|| {
                    let mut m = model.clone();
                    for obs in &observations {
                        let _ = m.update_scheme("A", obs, None);
                    }
                })
            },
        );
    }

    group.finish();
}

criterion_group!(
    benches,
    bench_kl_divergence,
    bench_symmetric_kl,
    bench_jensen_shannon,
    bench_all_metrics,
    bench_scheme_operations,
    bench_model_operations,
    bench_batch_updates,
);

criterion_main!(benches);
