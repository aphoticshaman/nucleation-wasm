"""
Synthetic Conflict Data Generator

Generates realistic-looking conflict data for testing when real GDELT
data is unavailable.

Author: Ryan J Cardwell (Archer Phoenix)
"""
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Tuple, Optional


# Known conflict dyads with intensity levels
CONFLICT_DYADS = {
    ('USA', 'RUS'): {'base_intensity': 0.6, 'volatility': 0.2},
    ('USA', 'CHN'): {'base_intensity': 0.4, 'volatility': 0.15},
    ('USA', 'IRN'): {'base_intensity': 0.7, 'volatility': 0.25},
    ('RUS', 'UKR'): {'base_intensity': 0.9, 'volatility': 0.1},
    ('ISR', 'IRN'): {'base_intensity': 0.8, 'volatility': 0.2},
    ('ISR', 'PSE'): {'base_intensity': 0.85, 'volatility': 0.15},
    ('USA', 'PRK'): {'base_intensity': 0.5, 'volatility': 0.3},
    ('IND', 'PAK'): {'base_intensity': 0.55, 'volatility': 0.2},
    ('CHN', 'TWN'): {'base_intensity': 0.5, 'volatility': 0.2},
}

# Cooperative dyads
COOPERATIVE_DYADS = {
    ('USA', 'GBR'): {'base_intensity': 0.1, 'volatility': 0.05},
    ('USA', 'DEU'): {'base_intensity': 0.15, 'volatility': 0.08},
    ('USA', 'FRA'): {'base_intensity': 0.12, 'volatility': 0.06},
    ('DEU', 'FRA'): {'base_intensity': 0.08, 'volatility': 0.04},
    ('GBR', 'FRA'): {'base_intensity': 0.1, 'volatility': 0.05},
}


def generate_synthetic_events(
    n_days: int = 60,
    start_date: Optional[datetime] = None,
    seed: int = 42,
    events_per_day: int = 1000,
) -> pd.DataFrame:
    """
    Generate synthetic GDELT-like events.

    Creates realistic event data with:
    - Proper actor distributions
    - Goldstein scores correlating with known conflict relationships
    - Temporal patterns and trends

    Args:
        n_days: Number of days to generate
        start_date: Start date
        seed: Random seed
        events_per_day: Average events per day

    Returns:
        DataFrame in GDELT format
    """
    np.random.seed(seed)

    if start_date is None:
        start_date = datetime(2024, 1, 1)

    # All actors
    all_actors = list(set(
        [a for dyad in CONFLICT_DYADS.keys() for a in dyad] +
        [a for dyad in COOPERATIVE_DYADS.keys() for a in dyad]
    ))

    events = []
    event_id = 1

    for day_offset in range(n_days):
        current_date = start_date + timedelta(days=day_offset)
        date_str = current_date.strftime("%Y%m%d")

        # Number of events (with some variation)
        n_events = int(events_per_day * (0.8 + 0.4 * np.random.random()))

        for _ in range(n_events):
            # Select actor pair
            if np.random.random() < 0.3:
                # Conflict dyad
                dyad = list(CONFLICT_DYADS.keys())[
                    np.random.randint(len(CONFLICT_DYADS))
                ]
                params = CONFLICT_DYADS[dyad]
            elif np.random.random() < 0.5:
                # Cooperative dyad
                dyad = list(COOPERATIVE_DYADS.keys())[
                    np.random.randint(len(COOPERATIVE_DYADS))
                ]
                params = COOPERATIVE_DYADS[dyad]
            else:
                # Random dyad
                actor1 = all_actors[np.random.randint(len(all_actors))]
                actor2 = all_actors[np.random.randint(len(all_actors))]
                while actor2 == actor1:
                    actor2 = all_actors[np.random.randint(len(all_actors))]
                dyad = (actor1, actor2)
                params = {'base_intensity': 0.3, 'volatility': 0.3}

            # Goldstein score (negative = hostile)
            # Map intensity to Goldstein: 0 → +10, 1 → -10
            base_goldstein = 10 - 20 * params['base_intensity']
            noise = params['volatility'] * np.random.randn() * 5
            goldstein = np.clip(base_goldstein + noise, -10, 10)

            # Quad class based on Goldstein
            if goldstein > 2:
                quad_class = 1 if np.random.random() < 0.6 else 2  # Verbal/material coop
            elif goldstein > -2:
                quad_class = np.random.choice([1, 2, 3])  # Mixed
            else:
                quad_class = 3 if np.random.random() < 0.6 else 4  # Verbal/material conflict

            # Event code
            if quad_class == 1:
                event_code = f"0{np.random.randint(1, 6)}"
            elif quad_class == 2:
                event_code = f"0{np.random.randint(6, 9)}"
            elif quad_class == 3:
                event_code = f"{np.random.randint(10, 15)}"
            else:
                event_code = f"{np.random.randint(15, 21)}"

            events.append({
                'GLOBALEVENTID': event_id,
                'SQLDATE': date_str,
                'Actor1Code': dyad[0],
                'Actor1CountryCode': dyad[0],
                'Actor2Code': dyad[1],
                'Actor2CountryCode': dyad[1],
                'EventCode': event_code,
                'EventRootCode': event_code[:2],
                'QuadClass': quad_class,
                'GoldsteinScale': goldstein,
                'NumMentions': max(1, int(np.random.exponential(5))),
                'AvgTone': goldstein * 0.5 + np.random.randn() * 2,
            })

            event_id += 1

    return pd.DataFrame(events)


def generate_compression_schemes_with_divergence(
    actors: List[str],
    n_categories: int = 10,
    conflict_dyads: Optional[List[Tuple[str, str]]] = None,
    seed: int = 42,
) -> dict:
    """
    Generate compression schemes that have known divergence patterns.

    Conflict dyads will have high divergence, allies will have low divergence.

    Args:
        actors: List of actor IDs
        n_categories: Number of categories
        conflict_dyads: Known conflict pairs
        seed: Random seed

    Returns:
        Dict of actor -> compression scheme distribution
    """
    np.random.seed(seed)

    if conflict_dyads is None:
        conflict_dyads = list(CONFLICT_DYADS.keys())

    # Generate base scheme (reference distribution)
    base_scheme = np.random.dirichlet(np.ones(n_categories) * 2)

    schemes = {}

    # Cluster actors into "worldview groups"
    # Actors in conflict will be in different groups
    group_a = {'USA', 'GBR', 'FRA', 'DEU'}
    group_b = {'RUS', 'CHN', 'IRN', 'PRK'}
    group_c = {'ISR'}
    group_d = {'UKR', 'TWN'}

    # Create group-specific base schemes
    group_schemes = {
        'a': np.random.dirichlet(np.ones(n_categories) * 2),
        'b': np.random.dirichlet(np.ones(n_categories) * 2),
        'c': np.random.dirichlet(np.ones(n_categories) * 2),
        'd': np.random.dirichlet(np.ones(n_categories) * 2),
    }

    for actor in actors:
        if actor in group_a:
            base = group_schemes['a']
        elif actor in group_b:
            base = group_schemes['b']
        elif actor in group_c:
            base = group_schemes['c']
        elif actor in group_d:
            base = group_schemes['d']
        else:
            base = np.random.dirichlet(np.ones(n_categories) * 2)

        # Add actor-specific noise
        noise = np.random.dirichlet(np.ones(n_categories) * 10)
        scheme = 0.7 * base + 0.3 * noise
        scheme = scheme / scheme.sum()

        schemes[actor] = scheme

    return schemes


def generate_validation_dataset(
    n_observations: int = 500,
    seed: int = 42,
) -> pd.DataFrame:
    """
    Generate a validation dataset with known properties.

    Creates data where divergence genuinely predicts conflict,
    for testing the validation framework.

    Args:
        n_observations: Number of observations
        seed: Random seed

    Returns:
        DataFrame with divergence, intensity, and escalation columns
    """
    np.random.seed(seed)

    all_dyads = list(CONFLICT_DYADS.keys()) + list(COOPERATIVE_DYADS.keys())

    data = []
    for i in range(n_observations):
        # Select dyad
        dyad = all_dyads[i % len(all_dyads)]

        # Get base parameters
        if dyad in CONFLICT_DYADS:
            params = CONFLICT_DYADS[dyad]
        else:
            params = COOPERATIVE_DYADS[dyad]

        # Divergence (from compression schemes)
        # Higher for conflict dyads
        divergence = params['base_intensity'] * 0.8 + np.random.randn() * 0.1

        # Intensity (correlated with divergence + noise)
        intensity = 0.6 * divergence + 0.4 * np.random.random()
        intensity = np.clip(intensity, 0, 1)

        # Escalation (binary, higher probability when intensity is high)
        escalation_prob = 0.2 + 0.6 * intensity
        escalation = int(np.random.random() < escalation_prob)

        data.append({
            'actor_a': dyad[0],
            'actor_b': dyad[1],
            'phi': divergence,
            'intensity': intensity,
            'escalation': escalation,
            'date': datetime(2024, 1, 1) + timedelta(days=i % 365),
        })

    return pd.DataFrame(data)


if __name__ == "__main__":
    print("Testing Synthetic Data Generator...")
    print("=" * 70)

    # Generate events
    events = generate_synthetic_events(n_days=30, events_per_day=500)
    print(f"\nGenerated {len(events)} events over 30 days")
    print(f"Actors: {events['Actor1CountryCode'].nunique()} unique")

    # Check Goldstein distribution by dyad type
    print(f"\nGoldstein scale by dyad type:")

    # Conflict dyads
    conflict_mask = events.apply(
        lambda r: (r['Actor1CountryCode'], r['Actor2CountryCode']) in CONFLICT_DYADS or
                  (r['Actor2CountryCode'], r['Actor1CountryCode']) in CONFLICT_DYADS,
        axis=1
    )
    print(f"  Conflict dyads: mean Goldstein = {events[conflict_mask]['GoldsteinScale'].mean():.2f}")

    # Cooperative dyads
    coop_mask = events.apply(
        lambda r: (r['Actor1CountryCode'], r['Actor2CountryCode']) in COOPERATIVE_DYADS or
                  (r['Actor2CountryCode'], r['Actor1CountryCode']) in COOPERATIVE_DYADS,
        axis=1
    )
    print(f"  Cooperative dyads: mean Goldstein = {events[coop_mask]['GoldsteinScale'].mean():.2f}")

    # Generate validation dataset
    print(f"\n" + "-" * 70)
    val_data = generate_validation_dataset(n_observations=200)
    print(f"\nValidation dataset: {len(val_data)} observations")
    print(f"Escalation rate: {val_data['escalation'].mean():.2%}")

    # Check correlation
    from scipy.stats import pearsonr
    r, p = pearsonr(val_data['phi'], val_data['intensity'])
    print(f"Divergence-intensity correlation: r={r:.3f}, p={p:.4f}")

    print("\n" + "=" * 70)
