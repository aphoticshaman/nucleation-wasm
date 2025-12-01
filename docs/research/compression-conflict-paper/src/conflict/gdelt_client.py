"""
GDELT Data Client

Fetches and processes data from the GDELT project.
http://www.gdeltproject.org/

GDELT tracks news coverage worldwide and extracts event data.
Key fields:
- Actor1/Actor2: Countries or organizations involved
- EventCode: CAMEO code for event type
- GoldsteinScale: -10 to +10 conflict/cooperation score
- Tone: Average tone of news coverage

Author: Ryan J Cardwell (Archer Phoenix)
"""
import urllib.request
import zipfile
import io
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import pandas as pd
import numpy as np


# GDELT v2.0 column indices
GDELT_V2_COLUMNS = {
    'GLOBALEVENTID': 0,
    'SQLDATE': 1,
    'MonthYear': 2,
    'Year': 3,
    'FractionDate': 4,
    'Actor1Code': 5,
    'Actor1Name': 6,
    'Actor1CountryCode': 7,
    'Actor1KnownGroupCode': 8,
    'Actor1EthnicCode': 9,
    'Actor1Religion1Code': 10,
    'Actor1Religion2Code': 11,
    'Actor1Type1Code': 12,
    'Actor1Type2Code': 13,
    'Actor1Type3Code': 14,
    'Actor2Code': 15,
    'Actor2Name': 16,
    'Actor2CountryCode': 17,
    'Actor2KnownGroupCode': 18,
    'Actor2EthnicCode': 19,
    'Actor2Religion1Code': 20,
    'Actor2Religion2Code': 21,
    'Actor2Type1Code': 22,
    'Actor2Type2Code': 23,
    'Actor2Type3Code': 24,
    'IsRootEvent': 25,
    'EventCode': 26,
    'EventBaseCode': 27,
    'EventRootCode': 28,
    'QuadClass': 29,
    'GoldsteinScale': 30,
    'NumMentions': 31,
    'NumSources': 32,
    'NumArticles': 33,
    'AvgTone': 34,
}

# Columns to keep (for memory efficiency)
KEEP_COLUMNS = [
    'GLOBALEVENTID', 'SQLDATE', 'Actor1Code', 'Actor1CountryCode',
    'Actor2Code', 'Actor2CountryCode', 'EventCode', 'EventRootCode',
    'QuadClass', 'GoldsteinScale', 'NumMentions', 'AvgTone',
]


class GDELTClient:
    """
    Client for fetching GDELT event data.

    Data source: http://data.gdeltproject.org/events/
    """

    BASE_URL = "http://data.gdeltproject.org/events/"

    def __init__(self, cache_dir: Optional[Path] = None):
        """
        Initialize GDELT client.

        Args:
            cache_dir: Directory to cache downloaded files
        """
        self.cache_dir = cache_dir or Path(".gdelt_cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def fetch_day(self, date: datetime) -> Optional[pd.DataFrame]:
        """
        Fetch GDELT events for a single day.

        Args:
            date: Date to fetch

        Returns:
            DataFrame of events or None if fetch fails
        """
        date_str = date.strftime("%Y%m%d")
        cache_file = self.cache_dir / f"{date_str}.parquet"

        # Check cache
        if cache_file.exists():
            return pd.read_parquet(cache_file)

        # Download
        url = f"{self.BASE_URL}{date_str}.export.CSV.zip"

        try:
            print(f"  Fetching {date_str}...", end=" ", flush=True)
            with urllib.request.urlopen(url, timeout=60) as response:
                zip_data = response.read()

            # Extract CSV from zip
            with zipfile.ZipFile(io.BytesIO(zip_data)) as zf:
                csv_name = zf.namelist()[0]
                csv_data = zf.read(csv_name).decode('utf-8', errors='ignore')

            # Parse
            df = self._parse_gdelt_csv(csv_data)

            # Cache as parquet (more efficient)
            df.to_parquet(cache_file)

            print(f"{len(df)} events")
            return df

        except Exception as e:
            print(f"failed ({e})")
            return None

    def _parse_gdelt_csv(self, csv_data: str) -> pd.DataFrame:
        """Parse GDELT CSV into DataFrame."""
        rows = []

        for line in csv_data.strip().split('\n'):
            fields = line.split('\t')

            if len(fields) < 35:
                continue

            try:
                row = {}
                for col_name, col_idx in GDELT_V2_COLUMNS.items():
                    if col_name in KEEP_COLUMNS:
                        value = fields[col_idx] if col_idx < len(fields) else None
                        row[col_name] = value

                # Convert numeric fields
                row['GoldsteinScale'] = float(row['GoldsteinScale']) if row['GoldsteinScale'] else np.nan
                row['NumMentions'] = int(row['NumMentions']) if row['NumMentions'] else 0
                row['AvgTone'] = float(row['AvgTone']) if row['AvgTone'] else 0.0
                row['QuadClass'] = int(row['QuadClass']) if row['QuadClass'] else 0

                rows.append(row)

            except (ValueError, IndexError):
                continue

        return pd.DataFrame(rows)

    def fetch_range(
        self,
        start_date: datetime,
        end_date: datetime,
        progress: bool = True,
    ) -> pd.DataFrame:
        """
        Fetch GDELT events for a date range.

        Args:
            start_date: Start date
            end_date: End date
            progress: Print progress

        Returns:
            DataFrame of all events
        """
        all_dfs = []
        current = start_date

        if progress:
            print(f"Fetching GDELT data from {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}...")

        while current <= end_date:
            df = self.fetch_day(current)
            if df is not None:
                all_dfs.append(df)
            current += timedelta(days=1)

        if not all_dfs:
            return pd.DataFrame()

        combined = pd.concat(all_dfs, ignore_index=True)
        print(f"\nTotal events: {len(combined):,}")

        return combined

    def fetch_actor_events(
        self,
        actor: str,
        start_date: datetime,
        end_date: datetime,
    ) -> pd.DataFrame:
        """
        Fetch events involving a specific actor.

        Args:
            actor: Actor code (e.g., 'USA', 'RUS')
            start_date: Start date
            end_date: End date

        Returns:
            DataFrame of events involving the actor
        """
        all_events = self.fetch_range(start_date, end_date)

        if all_events.empty:
            return all_events

        # Filter to actor
        mask = (
            (all_events['Actor1CountryCode'] == actor) |
            (all_events['Actor2CountryCode'] == actor)
        )
        return all_events[mask].copy()

    def fetch_dyad_events(
        self,
        actor_a: str,
        actor_b: str,
        start_date: datetime,
        end_date: datetime,
    ) -> pd.DataFrame:
        """
        Fetch events between two actors.

        Args:
            actor_a: First actor code
            actor_b: Second actor code
            start_date: Start date
            end_date: End date

        Returns:
            DataFrame of events between the actors
        """
        all_events = self.fetch_range(start_date, end_date)

        if all_events.empty:
            return all_events

        # Filter to dyad (both directions)
        mask = (
            ((all_events['Actor1CountryCode'] == actor_a) &
             (all_events['Actor2CountryCode'] == actor_b)) |
            ((all_events['Actor1CountryCode'] == actor_b) &
             (all_events['Actor2CountryCode'] == actor_a))
        )
        return all_events[mask].copy()


def fetch_gdelt_events(
    start_date: str,
    end_date: str,
    cache_dir: Optional[str] = None,
) -> pd.DataFrame:
    """
    Convenience function to fetch GDELT events.

    Args:
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
        cache_dir: Optional cache directory

    Returns:
        DataFrame of events
    """
    client = GDELTClient(Path(cache_dir) if cache_dir else None)
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")
    return client.fetch_range(start, end)


def aggregate_dyad_intensity(
    events: pd.DataFrame,
    window_days: int = 7,
    intensity_method: str = 'goldstein',
) -> pd.DataFrame:
    """
    Aggregate event data to dyad-level conflict intensity.

    Args:
        events: GDELT events DataFrame
        window_days: Aggregation window in days
        intensity_method: 'goldstein' (average), 'count', or 'weighted'

    Returns:
        DataFrame with columns: actor_a, actor_b, date, intensity, event_count
    """
    if events.empty:
        return pd.DataFrame()

    # Ensure date column
    events = events.copy()
    events['date'] = pd.to_datetime(events['SQLDATE'].astype(str), format='%Y%m%d', errors='coerce')
    events = events.dropna(subset=['date'])

    # Create dyad identifier (sorted to avoid A-B vs B-A duplicates)
    events['actor_a'] = events.apply(
        lambda r: min(str(r['Actor1CountryCode'] or ''), str(r['Actor2CountryCode'] or '')),
        axis=1,
    )
    events['actor_b'] = events.apply(
        lambda r: max(str(r['Actor1CountryCode'] or ''), str(r['Actor2CountryCode'] or '')),
        axis=1,
    )

    # Filter out missing actors
    events = events[(events['actor_a'] != '') & (events['actor_b'] != '')]

    # Aggregate
    events.set_index('date', inplace=True)

    results = []
    for (actor_a, actor_b), dyad_df in events.groupby(['actor_a', 'actor_b']):
        for end_date, window_df in dyad_df.groupby(pd.Grouper(freq=f'{window_days}D')):
            if len(window_df) == 0:
                continue

            if intensity_method == 'goldstein':
                # Average Goldstein (negative = more hostile)
                intensity = -window_df['GoldsteinScale'].mean()  # Negate so higher = more conflict
            elif intensity_method == 'count':
                intensity = len(window_df)
            elif intensity_method == 'weighted':
                # Weight by mentions
                weights = window_df['NumMentions'].fillna(1)
                intensity = -np.average(window_df['GoldsteinScale'], weights=weights)
            else:
                intensity = len(window_df)

            results.append({
                'actor_a': actor_a,
                'actor_b': actor_b,
                'date': end_date,
                'intensity': intensity,
                'event_count': len(window_df),
                'avg_goldstein': window_df['GoldsteinScale'].mean(),
                'avg_tone': window_df['AvgTone'].mean(),
            })

    return pd.DataFrame(results)


def compute_conflict_intensity_series(
    events: pd.DataFrame,
    actor_a: str,
    actor_b: str,
    window_days: int = 7,
) -> pd.DataFrame:
    """
    Compute conflict intensity time series for a specific dyad.

    Args:
        events: GDELT events DataFrame
        actor_a: First actor
        actor_b: Second actor
        window_days: Aggregation window

    Returns:
        DataFrame with date and intensity columns
    """
    # Filter to dyad
    events = events.copy()
    mask = (
        ((events['Actor1CountryCode'] == actor_a) &
         (events['Actor2CountryCode'] == actor_b)) |
        ((events['Actor1CountryCode'] == actor_b) &
         (events['Actor2CountryCode'] == actor_a))
    )
    dyad_events = events[mask]

    if dyad_events.empty:
        return pd.DataFrame()

    # Aggregate
    intensity_df = aggregate_dyad_intensity(dyad_events, window_days)
    intensity_df = intensity_df.sort_values('date')

    return intensity_df[['date', 'intensity', 'event_count', 'avg_goldstein']]


# Country code mappings
COUNTRY_CODES = {
    'USA': 'United States',
    'RUS': 'Russia',
    'CHN': 'China',
    'UKR': 'Ukraine',
    'ISR': 'Israel',
    'IRN': 'Iran',
    'SYR': 'Syria',
    'IRQ': 'Iraq',
    'AFG': 'Afghanistan',
    'PAK': 'Pakistan',
    'IND': 'India',
    'GBR': 'United Kingdom',
    'FRA': 'France',
    'DEU': 'Germany',
    'TUR': 'Turkey',
    'SAU': 'Saudi Arabia',
    'EGY': 'Egypt',
    'NGA': 'Nigeria',
    'ZAF': 'South Africa',
    'BRA': 'Brazil',
    'MEX': 'Mexico',
    'JPN': 'Japan',
    'KOR': 'South Korea',
    'PRK': 'North Korea',
    'TWN': 'Taiwan',
    'PSE': 'Palestine',
    'LBN': 'Lebanon',
    'YEM': 'Yemen',
}


if __name__ == "__main__":
    print("Testing GDELT Client...")
    print("=" * 70)

    # Fetch a small sample
    client = GDELTClient()

    # Get yesterday's data (today may be incomplete)
    yesterday = datetime.now() - timedelta(days=2)

    df = client.fetch_day(yesterday)

    if df is not None:
        print(f"\nSample data shape: {df.shape}")
        print(f"\nColumns: {df.columns.tolist()}")

        # Top actors
        actor_counts = df['Actor1CountryCode'].value_counts().head(10)
        print(f"\nTop source countries:")
        for code, count in actor_counts.items():
            name = COUNTRY_CODES.get(code, code)
            print(f"  {name}: {count}")

        # Aggregate intensity
        intensity = aggregate_dyad_intensity(df, window_days=1)
        if not intensity.empty:
            print(f"\nTop conflict dyads:")
            top_dyads = intensity.nlargest(10, 'intensity')
            for _, row in top_dyads.iterrows():
                a = COUNTRY_CODES.get(row['actor_a'], row['actor_a'])
                b = COUNTRY_CODES.get(row['actor_b'], row['actor_b'])
                print(f"  {a}-{b}: intensity={row['intensity']:.2f}, events={row['event_count']}")

    print("\n" + "=" * 70)
