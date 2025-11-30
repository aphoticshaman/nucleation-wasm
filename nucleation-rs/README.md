# nucleation-rs

Entropy-based cognitive insight detection primitives in Rust.

## Overview

`nucleation` provides the mathematical foundation for cognitive state detection and active resonance control systems. Built on:

- **Unified Entropy Theory** (Theorems 1-14): Information-theoretic foundations for insight detection
- **Active Cognitive Resonance (ACR)**: Kuramoto-inspired phase-locking controller for insight induction

## Architecture

```
nucleation-rs/
├── src/
│   ├── lib.rs          # Crate root + re-exports
│   ├── entropy.rs      # Shannon, permutation, KL, entropy rate
│   ├── distance.rs     # Hellinger, JS, Fisher-Rao, Wasserstein
│   ├── signal.rs       # Rolling stats, gradients, phase tracking, OEP
│   ├── detector.rs     # NucleationDetector (multi-signal concordance)
│   └── acr.rs          # ACRController (Kuramoto phase-locking)
└── Cargo.toml
```

## Quick Start

```rust
use nucleation::{create_detector, create_controller, CognitiveModality};

// Detection mode
let mut detector = create_detector("balanced");
for event in behavioral_stream {
    if let Some(precursor) = detector.update(event.symbol, event.time, event.weight) {
        println!("Insight phase: {:?}, confidence: {:.2}",
                 precursor.phase, precursor.confidence);
    }
}

// Control mode
let mut controller = create_controller(CognitiveModality::Integration);
let signal = controller.update(timestamp, duration, switching_freq);
match signal.action {
    ControlAction::TriggerInsight => fire_hint(),
    ControlAction::SlowDown => adjust_pacing(signal.pacing_factor),
    _ => {}
}
```

## Mathematical Foundation

### OEP (Oscillatory Entrainment Potential)
```
dE/dt = -E/τ + α·Σδ(t-tᵢ)·Ψ(Oᵢ) + η(t)
```

### ACR Phase Dynamics (extended Kuramoto)
```
dφ_int/dt = ω_int + K(E)·sin(φ_ext - φ_int) + β·u(t)
```

### Resonance Metric
```
R(t) = |⟨exp(i·Δφ)⟩|
```

### Insight Condition
```
I(t) = 1  if  R(t) ≥ Γ_crit  AND  dR/dt > 0  AND  E(t) > E_min
```

## Detector Sensitivities

| Mode | Variance Threshold | Hellinger Threshold | Concordance |
|------|-------------------|---------------------|-------------|
| high_recall | 0.015 | 0.20 | 2 |
| balanced | 0.008 | 0.25 | 4 |
| high_precision | 0.004 | 0.30 | 5 |

## Cognitive Modalities

| Modality | τ (ms) | ω_nat (Hz) | Behavior |
|----------|--------|------------|----------|
| Integration | 15000 | 0.05 | Deep focus, long attention |
| Differentiation | 1200 | 1.25 | Rapid scanning |
| Verification | 2000 | 0.90 | Quick checking |
| Intermittent | 8000 | 0.15 | Mixed pattern |

## Build

```bash
cargo build --release
cargo test
```

## License

MIT OR Apache-2.0

## Roadmap

```
nucleation-rs (this crate)
       ↓
scirust-core (stats, signal, optimize)
       ↓
rusttorch (autograd, tensor ops, optimizers)
       ↓
$1B acquisition target
```
