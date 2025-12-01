# The Divergence Report #1: USA-China Compression Gap

**TL;DR**: Using information theory to measure how differently the US and China "see" the world. Current Φ(USA, CHN) = 0.48. That's MODERATE risk—meaningful divergence, but not yet critical. Here's what the numbers actually mean.

---

## What is Compression Divergence?

Every nation has a "compression scheme"—a mental model of what matters in the world. The US compresses reality one way (democracy, markets, rules-based order). China compresses it another way (sovereignty, development, multipolarity).

When these compression schemes diverge, conflict potential rises. Not because anyone is "evil," but because they're genuinely surprised by each other's actions. They're using different maps of the same territory.

The math is simple:

```
Φ(A,B) = D_KL(A‖B) + D_KL(B‖A)
```

This is the symmetric KL divergence—a measure from information theory. Higher Φ = more divergent worldviews = higher conflict risk.

---

## This Week's Numbers

| Dyad | Φ (Conflict Potential) | Risk Level |
|------|------------------------|------------|
| USA ↔ CHN | 0.48 | MODERATE |
| USA ↔ RUS | 0.89 | MODERATE |
| RUS ↔ UKR | 1.24 | ELEVATED |
| ISR ↔ IRN | 1.67 | ELEVATED |
| CHN ↔ TWN | 0.31 | LOW |
| USA ↔ EUR | 0.12 | LOW |

**Key insight**: USA-China divergence (0.48) is actually lower than USA-Russia (0.89). The compression schemes are more aligned than the headlines suggest.

Why? Both the US and China prioritize economic exchange and diplomatic cooperation in their worldview distributions. They disagree on *who* should lead, but they agree on *what* matters.

Russia's compression scheme is fundamentally different—heavier weight on military posture, territorial claims, and historical grievance. That's why Φ(USA, RUS) is nearly double Φ(USA, CHN).

---

## What Would Move the Needle?

For USA-CHN to hit ELEVATED (Φ > 1.0), we'd need to see:

1. **Taiwan military exercises** that shift China's compression toward "military posture" category
2. **Tech decoupling** that reduces shared "economic exchange" weight
3. **Narrative divergence** where both sides stop using shared vocabulary (currently both still talk about "win-win cooperation" even if they don't mean it)

Watch for these signals in the coming weeks.

---

## The Reconciliation Path

The model also identifies which categories are driving divergence. For USA-CHN:

1. **Ideological narrative** (28% of divergence contribution)
2. **Security threat perception** (23%)
3. **Resource competition** (19%)

If you wanted to reduce Φ, you'd focus dialogue on these three areas—not on Taiwan directly, but on the underlying compression differences.

> "Reconciliation doesn't require agreeing on the past. Only aligning predictions about the future."

---

## Methodology

- Compression schemes derived from GDELT event data (2020-2024)
- 9 categories based on CAMEO event classification
- Updated weekly as new event data arrives
- Full code: [github.com/aphoticshaman/nucleation-wasm](https://github.com/aphoticshaman/nucleation-wasm)
- Paper: [zenodo.org/records/17766946](https://zenodo.org/records/17766946)

---

## Subscribe for Weekly Updates

Every week I'll publish:
- Updated Φ values for major dyads
- Analysis of what's driving changes
- Early warning signals for escalation

**Free tier**: Weekly summary
**Paid tier ($10/mo)**: Full data tables, API access, custom dyad requests

---

*Conflict is compression divergence. Peace is alignment.*

[@Benthic_Shadow](https://twitter.com/Benthic_Shadow)
