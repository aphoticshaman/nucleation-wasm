"""
Event-Based Compression Scheme Extraction

Extracts compression schemes from event data (ACLED, GDELT).
Uses action patterns to infer compression schemes.

The pattern of actions reveals how an actor categorizes situations.
If actor consistently responds to context C with action A, they're
"compressing" C into a category that triggers A.

Author: Ryan J Cardwell (Archer Phoenix)
"""
import numpy as np
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
import pandas as pd
from collections import Counter

from .schemes import CompressionScheme, SchemeSource


# GDELT CAMEO event codes (first two digits = root code)
CAMEO_ROOT_CODES = {
    '01': 'MAKE_PUBLIC_STATEMENT',
    '02': 'APPEAL',
    '03': 'EXPRESS_INTENT_COOPERATE',
    '04': 'CONSULT',
    '05': 'DIPLOMATIC_COOPERATION',
    '06': 'MATERIAL_COOPERATION',
    '07': 'PROVIDE_AID',
    '08': 'YIELD',
    '09': 'INVESTIGATE',
    '10': 'DEMAND',
    '11': 'DISAPPROVE',
    '12': 'REJECT',
    '13': 'THREATEN',
    '14': 'PROTEST',
    '15': 'EXHIBIT_FORCE',
    '16': 'REDUCE_RELATIONS',
    '17': 'COERCE',
    '18': 'ASSAULT',
    '19': 'FIGHT',
    '20': 'UNCONVENTIONAL_MASS_VIOLENCE',
}

# ACLED event types
ACLED_EVENT_TYPES = [
    'Battles',
    'Explosions/Remote violence',
    'Violence against civilians',
    'Protests',
    'Riots',
    'Strategic developments',
]

# Broader categories for compression
EVENT_CATEGORIES = [
    'verbal_cooperation',      # CAMEO 01-05
    'material_cooperation',    # CAMEO 06-08
    'verbal_conflict',         # CAMEO 10-14
    'material_conflict',       # CAMEO 15-20
    'neutral',                 # CAMEO 09
]


@dataclass
class EventPattern:
    """Pattern of events for an actor."""
    actor_id: str
    event_counts: Dict[str, int]
    total_events: int
    time_span_days: int
    event_rate: float  # events per day


class EventCompressionExtractor:
    """
    Extracts compression schemes from event data.

    Uses action/event patterns to infer compression schemes.

    Pipeline:
    1. Categorize events into action types
    2. Compute distribution over action categories
    3. This reveals how actor "compresses" situations into actions
    """

    def __init__(
        self,
        n_categories: int = 20,
        event_source: str = 'gdelt',  # 'gdelt' or 'acled'
        use_quad_class: bool = True,  # For GDELT: use QuadClass for broader categories
    ):
        """
        Initialize event extractor.

        Args:
            n_categories: Number of event categories
            event_source: 'gdelt' or 'acled'
            use_quad_class: Use GDELT QuadClass for broader categories
        """
        self.n_categories = n_categories
        self.event_source = event_source
        self.use_quad_class = use_quad_class

        # Initialize category structure
        if event_source == 'gdelt':
            if use_quad_class:
                self.categories = [
                    'verbal_cooperation',
                    'material_cooperation',
                    'verbal_conflict',
                    'material_conflict',
                ]
                self.n_categories = 4
            else:
                self.categories = list(CAMEO_ROOT_CODES.values())
                self.n_categories = len(self.categories)
        else:  # ACLED
            self.categories = ACLED_EVENT_TYPES
            self.n_categories = len(self.categories)

        self.event_type_to_idx: Dict[str, int] = {
            et: i for i, et in enumerate(self.categories)
        }

    def _categorize_gdelt_event(self, event_code: str, quad_class: Optional[int] = None) -> int:
        """Map GDELT event code to category index."""
        if self.use_quad_class and quad_class is not None:
            # QuadClass: 1=verbal coop, 2=material coop, 3=verbal conflict, 4=material conflict
            return max(0, min(quad_class - 1, 3))

        # Use root code
        if not event_code or len(event_code) < 2:
            return 0

        root = event_code[:2]
        root_int = int(root) if root.isdigit() else 0

        if root_int <= 5:
            return 0  # verbal_cooperation
        elif root_int <= 8:
            return 1  # material_cooperation
        elif root_int <= 14:
            return 2  # verbal_conflict
        else:
            return 3  # material_conflict

    def _categorize_acled_event(self, event_type: str) -> int:
        """Map ACLED event type to category index."""
        return self.event_type_to_idx.get(event_type, 0)

    def extract_scheme(
        self,
        events: pd.DataFrame,
        actor_id: str,
        actor_column: str = 'Actor1Code',
        timestamp: Optional[pd.Timestamp] = None,
    ) -> CompressionScheme:
        """
        Extract compression scheme from actor's event patterns.

        Distribution over event types = how actor "compresses" situations
        into action categories.

        Args:
            events: DataFrame with event data
            actor_id: Actor to extract scheme for
            actor_column: Column name for actor (default: GDELT format)
            timestamp: Optional timestamp

        Returns:
            CompressionScheme representing actor's action distribution
        """
        # Filter to actor's events
        actor_events = events[events[actor_column] == actor_id].copy()

        if len(actor_events) == 0:
            return CompressionScheme(
                actor_id=actor_id,
                distribution=np.ones(self.n_categories) / self.n_categories,
                categories=self.categories,
                timestamp=timestamp,
                source=SchemeSource.EVENTS,
                metadata={'n_events': 0, 'method': f'event_patterns_{self.event_source}'},
            )

        # Categorize events
        distribution = np.zeros(self.n_categories)

        if self.event_source == 'gdelt':
            event_col = 'EventCode' if 'EventCode' in events.columns else 'EventRootCode'
            quad_col = 'QuadClass' if 'QuadClass' in events.columns else None

            for _, row in actor_events.iterrows():
                event_code = str(row.get(event_col, ''))
                quad_class = row.get(quad_col) if quad_col else None
                cat_idx = self._categorize_gdelt_event(event_code, quad_class)
                distribution[cat_idx] += 1

        else:  # ACLED
            for _, row in actor_events.iterrows():
                event_type = row.get('event_type', '')
                cat_idx = self._categorize_acled_event(event_type)
                distribution[cat_idx] += 1

        # Normalize
        distribution /= (distribution.sum() + 1e-10)

        return CompressionScheme(
            actor_id=actor_id,
            distribution=distribution,
            categories=self.categories,
            timestamp=timestamp or pd.Timestamp.now(),
            source=SchemeSource.EVENTS,
            metadata={
                'n_events': len(actor_events),
                'method': f'event_patterns_{self.event_source}',
            },
        )

    def extract_temporal_schemes(
        self,
        events: pd.DataFrame,
        actor_id: str,
        date_column: str = 'SQLDATE',
        actor_column: str = 'Actor1Code',
        window_days: int = 30,
        min_events: int = 10,
    ) -> List[CompressionScheme]:
        """
        Extract compression schemes over time with rolling window.

        Args:
            events: DataFrame with event data
            actor_id: Actor to extract schemes for
            date_column: Column with event date
            actor_column: Column with actor identifier
            window_days: Window size in days
            min_events: Minimum events per window

        Returns:
            List of CompressionScheme objects over time
        """
        # Filter to actor
        actor_events = events[events[actor_column] == actor_id].copy()

        if len(actor_events) == 0:
            return []

        # Parse dates
        if date_column in actor_events.columns:
            actor_events['_date'] = pd.to_datetime(
                actor_events[date_column].astype(str),
                format='%Y%m%d' if len(str(actor_events[date_column].iloc[0])) == 8 else None,
                errors='coerce',
            )
            actor_events = actor_events.dropna(subset=['_date'])
            actor_events.set_index('_date', inplace=True)

        schemes = []

        # Rolling window
        for end_date, window_df in actor_events.groupby(pd.Grouper(freq=f'{window_days}D')):
            if len(window_df) < min_events:
                continue

            # Reset index for extraction
            window_df = window_df.reset_index()

            scheme = self.extract_scheme(
                window_df,
                actor_id,
                actor_column=actor_column,
            )
            scheme.timestamp = end_date
            schemes.append(scheme)

        return schemes

    def extract_dyad_patterns(
        self,
        events: pd.DataFrame,
        actor_a: str,
        actor_b: str,
        actor1_col: str = 'Actor1Code',
        actor2_col: str = 'Actor2Code',
    ) -> Tuple[CompressionScheme, CompressionScheme]:
        """
        Extract compression schemes for a specific dyad.

        Filters to events involving both actors and extracts
        their respective action patterns.

        Args:
            events: DataFrame with event data
            actor_a: First actor
            actor_b: Second actor
            actor1_col: Column for source actor
            actor2_col: Column for target actor

        Returns:
            Tuple of (scheme_a, scheme_b)
        """
        # Events where A acts on B
        a_to_b = events[
            (events[actor1_col] == actor_a) &
            (events[actor2_col] == actor_b)
        ]

        # Events where B acts on A
        b_to_a = events[
            (events[actor1_col] == actor_b) &
            (events[actor2_col] == actor_a)
        ]

        # Extract schemes
        scheme_a = self.extract_scheme(a_to_b, actor_a, actor1_col)
        scheme_b = self.extract_scheme(b_to_a, actor_b, actor1_col)

        scheme_a.metadata['dyad_target'] = actor_b
        scheme_b.metadata['dyad_target'] = actor_a

        return scheme_a, scheme_b


class GoldsteinCompressionExtractor:
    """
    Alternative approach: use Goldstein scale distribution as compression scheme.

    Goldstein scale: -10 (most hostile) to +10 (most cooperative)
    Discretize into bins → actor's distribution over hostility levels.
    """

    def __init__(self, n_bins: int = 10):
        """
        Initialize Goldstein-based extractor.

        Args:
            n_bins: Number of bins for Goldstein scale
        """
        self.n_bins = n_bins
        self.bin_edges = np.linspace(-10, 10, n_bins + 1)
        self.categories = [
            f"goldstein_{self.bin_edges[i]:.1f}_to_{self.bin_edges[i+1]:.1f}"
            for i in range(n_bins)
        ]

    def extract_scheme(
        self,
        events: pd.DataFrame,
        actor_id: str,
        actor_column: str = 'Actor1Code',
        goldstein_column: str = 'GoldsteinScale',
        timestamp: Optional[pd.Timestamp] = None,
    ) -> CompressionScheme:
        """
        Extract compression scheme from Goldstein scale distribution.

        Args:
            events: DataFrame with event data
            actor_id: Actor to extract scheme for
            actor_column: Column for actor
            goldstein_column: Column with Goldstein scores
            timestamp: Optional timestamp

        Returns:
            CompressionScheme based on Goldstein distribution
        """
        # Filter to actor
        actor_events = events[events[actor_column] == actor_id]

        if len(actor_events) == 0 or goldstein_column not in events.columns:
            return CompressionScheme(
                actor_id=actor_id,
                distribution=np.ones(self.n_bins) / self.n_bins,
                categories=self.categories,
                timestamp=timestamp,
                source=SchemeSource.EVENTS,
                metadata={'n_events': 0, 'method': 'goldstein_distribution'},
            )

        # Get Goldstein scores
        scores = actor_events[goldstein_column].dropna().values

        # Bin scores
        hist, _ = np.histogram(scores, bins=self.bin_edges)
        distribution = hist.astype(float)
        distribution /= (distribution.sum() + 1e-10)

        return CompressionScheme(
            actor_id=actor_id,
            distribution=distribution,
            categories=self.categories,
            timestamp=timestamp or pd.Timestamp.now(),
            source=SchemeSource.EVENTS,
            metadata={
                'n_events': len(scores),
                'method': 'goldstein_distribution',
                'mean_goldstein': float(np.mean(scores)),
                'std_goldstein': float(np.std(scores)),
            },
        )


class HybridCompressionExtractor:
    """
    Hybrid extractor combining text and event-based compression.

    Concatenates text and event distributions with weighting.
    """

    def __init__(
        self,
        text_extractor,
        event_extractor,
        text_weight: float = 0.5,
    ):
        """
        Initialize hybrid extractor.

        Args:
            text_extractor: TextCompressionExtractor instance
            event_extractor: EventCompressionExtractor instance
            text_weight: Weight for text-based scheme (event weight = 1 - text_weight)
        """
        self.text_extractor = text_extractor
        self.event_extractor = event_extractor
        self.text_weight = text_weight

    def extract_scheme(
        self,
        text_documents: List[str],
        events: pd.DataFrame,
        actor_id: str,
        event_actor_column: str = 'Actor1Code',
        timestamp: Optional[pd.Timestamp] = None,
    ) -> CompressionScheme:
        """
        Extract hybrid compression scheme.

        Args:
            text_documents: Actor's text documents
            events: Actor's event data
            actor_id: Actor identifier
            event_actor_column: Column for actor in events
            timestamp: Optional timestamp

        Returns:
            CompressionScheme combining text and event signals
        """
        # Extract both schemes
        text_scheme = self.text_extractor.extract_scheme(text_documents, actor_id)
        event_scheme = self.event_extractor.extract_scheme(
            events, actor_id, event_actor_column
        )

        # Concatenate distributions with weighting
        text_dist = text_scheme.distribution * self.text_weight
        event_dist = event_scheme.distribution * (1 - self.text_weight)

        combined_dist = np.concatenate([text_dist, event_dist])
        combined_dist /= combined_dist.sum()

        combined_categories = (
            [f"text_{c}" for c in text_scheme.categories] +
            [f"event_{c}" for c in event_scheme.categories]
        )

        return CompressionScheme(
            actor_id=actor_id,
            distribution=combined_dist,
            categories=combined_categories,
            timestamp=timestamp or pd.Timestamp.now(),
            source=SchemeSource.HYBRID,
            metadata={
                'n_text_docs': text_scheme.metadata.get('n_documents', 0),
                'n_events': event_scheme.metadata.get('n_events', 0),
                'method': 'hybrid_text_event',
                'text_weight': self.text_weight,
            },
        )


if __name__ == "__main__":
    print("Testing Event Compression Extractor...")
    print("=" * 70)

    # Create sample GDELT-like data
    sample_events = pd.DataFrame({
        'Actor1Code': ['USA', 'USA', 'USA', 'RUS', 'RUS', 'RUS', 'USA', 'RUS'],
        'Actor2Code': ['RUS', 'CHN', 'GBR', 'USA', 'UKR', 'SYR', 'RUS', 'USA'],
        'EventCode': ['010', '040', '036', '130', '190', '180', '010', '170'],
        'QuadClass': [1, 1, 2, 3, 4, 4, 1, 4],
        'GoldsteinScale': [3.5, 2.0, 5.0, -4.0, -10.0, -9.0, 3.5, -7.0],
        'SQLDATE': ['20240101', '20240102', '20240103', '20240101', '20240102', '20240103', '20240104', '20240104'],
    })

    # Test event extractor
    extractor = EventCompressionExtractor(event_source='gdelt', use_quad_class=True)

    scheme_usa = extractor.extract_scheme(sample_events, 'USA')
    scheme_rus = extractor.extract_scheme(sample_events, 'RUS')

    print("\nEvent-based compression schemes:")
    print(f"\nUSA ({scheme_usa.metadata['n_events']} events):")
    print(f"  Categories: {scheme_usa.categories}")
    print(f"  Distribution: {scheme_usa.distribution}")
    print(f"  Entropy: {scheme_usa.entropy:.3f}")

    print(f"\nRUS ({scheme_rus.metadata['n_events']} events):")
    print(f"  Categories: {scheme_rus.categories}")
    print(f"  Distribution: {scheme_rus.distribution}")
    print(f"  Entropy: {scheme_rus.entropy:.3f}")

    print(f"\nDivergence USA-RUS: {scheme_usa.symmetric_divergence(scheme_rus):.3f}")

    # Test Goldstein extractor
    print("\n" + "-" * 70)
    print("\nGoldstein-based compression:")

    goldstein_extractor = GoldsteinCompressionExtractor(n_bins=5)
    g_scheme_usa = goldstein_extractor.extract_scheme(sample_events, 'USA')
    g_scheme_rus = goldstein_extractor.extract_scheme(sample_events, 'RUS')

    print(f"\nUSA mean Goldstein: {g_scheme_usa.metadata.get('mean_goldstein', 'N/A'):.2f}")
    print(f"RUS mean Goldstein: {g_scheme_rus.metadata.get('mean_goldstein', 'N/A'):.2f}")
    print(f"Divergence: {g_scheme_usa.symmetric_divergence(g_scheme_rus):.3f}")

    print("\n" + "=" * 70)
