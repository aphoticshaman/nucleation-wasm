"""
UCDP Data Loader

Uppsala Conflict Data Program - academic conflict dataset.
https://ucdp.uu.se/

Provides validated, coded conflict data since 1946.

Author: Ryan J Cardwell (Archer Phoenix)
"""
import urllib.request
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Optional, List, Dict
from dataclasses import dataclass


# UCDP data URLs
UCDP_URLS = {
    'prio_acd': 'https://ucdp.uu.se/downloads/ucdpprio/ucdp-prio-acd-231.csv',
    'dyadic': 'https://ucdp.uu.se/downloads/ucdpdyadic/ucdp-dyadic-231.csv',
    'ged': 'https://ucdp.uu.se/downloads/ged/ged231-csv.zip',  # Georeferenced event data
    'brd': 'https://ucdp.uu.se/downloads/brd/ucdp-brd-dyadic-231.csv',  # Battle deaths
}


@dataclass
class UCDPConflict:
    """Represents a UCDP conflict."""
    conflict_id: int
    conflict_name: str
    side_a: str
    side_b: str
    year: int
    intensity_level: int  # 1 = minor (25-999 deaths), 2 = war (1000+ deaths)
    type_of_conflict: int  # 1=extrasystemic, 2=interstate, 3=internal, 4=internationalized internal
    region: str
    cumulative_intensity: int


class UCDPLoader:
    """
    Loader for UCDP conflict data.

    UCDP provides the most comprehensive and validated academic
    dataset on armed conflicts since 1946.
    """

    def __init__(self, data_dir: Optional[Path] = None):
        """
        Initialize UCDP loader.

        Args:
            data_dir: Directory to store downloaded data
        """
        self.data_dir = data_dir or Path("data/raw/ucdp")
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def download_prio_acd(self, force: bool = False) -> Path:
        """
        Download UCDP/PRIO Armed Conflict Dataset.

        This is the main conflict-year dataset.

        Args:
            force: Force re-download even if file exists

        Returns:
            Path to downloaded file
        """
        local_path = self.data_dir / "ucdp-prio-acd.csv"

        if local_path.exists() and not force:
            print(f"Using cached UCDP data: {local_path}")
            return local_path

        print("Downloading UCDP/PRIO Armed Conflict Dataset...")
        try:
            urllib.request.urlretrieve(UCDP_URLS['prio_acd'], local_path)
            print(f"  Saved to {local_path}")
            return local_path
        except Exception as e:
            print(f"  Download failed: {e}")
            # Try alternative path
            alt_url = 'https://ucdp.uu.se/downloads/ucdpprio/ucdp-prio-acd-221.csv'
            try:
                urllib.request.urlretrieve(alt_url, local_path)
                print(f"  Saved to {local_path} (using alternative URL)")
                return local_path
            except Exception as e2:
                raise RuntimeError(f"Failed to download UCDP data: {e2}")

    def load_conflicts(self) -> pd.DataFrame:
        """
        Load UCDP conflict data.

        Returns:
            DataFrame with conflict data
        """
        path = self.download_prio_acd()
        df = pd.read_csv(path, encoding='utf-8')

        # Standardize column names
        df.columns = [c.lower().replace(' ', '_') for c in df.columns]

        return df

    def get_conflict_intensity_series(
        self,
        conflict_id: Optional[int] = None,
        region: Optional[str] = None,
        conflict_type: Optional[int] = None,
    ) -> pd.DataFrame:
        """
        Get conflict intensity time series.

        Args:
            conflict_id: Filter to specific conflict
            region: Filter to region (e.g., 'Europe', 'Middle East')
            conflict_type: Filter to type (2=interstate, 3=internal, etc.)

        Returns:
            DataFrame with year and intensity columns
        """
        df = self.load_conflicts()

        # Apply filters
        if conflict_id is not None:
            df = df[df['conflict_id'] == conflict_id]
        if region is not None:
            df = df[df['region'].str.contains(region, case=False, na=False)]
        if conflict_type is not None:
            df = df[df['type_of_conflict'] == conflict_type]

        # Aggregate by year
        intensity_col = 'intensity_level' if 'intensity_level' in df.columns else 'int'

        yearly = df.groupby('year').agg({
            intensity_col: ['mean', 'max', 'sum'],
            'conflict_id': 'nunique',
        }).reset_index()

        yearly.columns = ['year', 'avg_intensity', 'max_intensity', 'total_intensity', 'n_conflicts']

        return yearly.sort_values('year')

    def get_dyad_conflicts(
        self,
        side_a: Optional[str] = None,
        side_b: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        Get conflict data for specific dyad.

        Args:
            side_a: First party (country or group)
            side_b: Second party

        Returns:
            DataFrame filtered to dyad
        """
        df = self.load_conflicts()

        if side_a is not None:
            df = df[
                df['side_a'].str.contains(side_a, case=False, na=False) |
                df['side_b'].str.contains(side_a, case=False, na=False)
            ]

        if side_b is not None:
            df = df[
                df['side_a'].str.contains(side_b, case=False, na=False) |
                df['side_b'].str.contains(side_b, case=False, na=False)
            ]

        return df

    def get_interstate_wars(self, min_year: int = 1946) -> pd.DataFrame:
        """
        Get interstate wars (type_of_conflict = 2).

        Args:
            min_year: Minimum year

        Returns:
            DataFrame of interstate conflicts
        """
        df = self.load_conflicts()
        df = df[(df['type_of_conflict'] == 2) & (df['year'] >= min_year)]
        return df

    def extract_conflict_list(self) -> List[UCDPConflict]:
        """Extract list of UCDPConflict objects."""
        df = self.load_conflicts()
        conflicts = []

        for _, row in df.iterrows():
            try:
                conflicts.append(UCDPConflict(
                    conflict_id=int(row.get('conflict_id', 0)),
                    conflict_name=str(row.get('conflict_name', row.get('location', ''))),
                    side_a=str(row.get('side_a', '')),
                    side_b=str(row.get('side_b', '')),
                    year=int(row.get('year', 0)),
                    intensity_level=int(row.get('intensity_level', row.get('int', 1))),
                    type_of_conflict=int(row.get('type_of_conflict', 3)),
                    region=str(row.get('region', '')),
                    cumulative_intensity=int(row.get('cumulative_intensity', row.get('cum_int', 1))),
                ))
            except (ValueError, KeyError):
                continue

        return conflicts


def load_ucdp_conflicts(
    data_dir: Optional[str] = None,
    region: Optional[str] = None,
    min_year: int = 1946,
) -> pd.DataFrame:
    """
    Convenience function to load UCDP data.

    Args:
        data_dir: Optional data directory
        region: Filter to region
        min_year: Minimum year

    Returns:
        DataFrame of conflicts
    """
    loader = UCDPLoader(Path(data_dir) if data_dir else None)
    df = loader.load_conflicts()

    if region:
        df = df[df['region'].str.contains(region, case=False, na=False)]

    df = df[df['year'] >= min_year]

    return df


def create_ucdp_intensity_dataset(
    loader: UCDPLoader,
    actors: List[str],
) -> pd.DataFrame:
    """
    Create conflict intensity dataset for specific actors.

    Maps UCDP data to actor-year intensity scores for validation.

    Args:
        loader: UCDPLoader instance
        actors: List of actor names/countries

    Returns:
        DataFrame with actor, year, has_conflict, intensity
    """
    df = loader.load_conflicts()

    results = []
    years = range(df['year'].min(), df['year'].max() + 1)

    for actor in actors:
        for year in years:
            # Check if actor involved in any conflict that year
            year_conflicts = df[df['year'] == year]
            actor_conflicts = year_conflicts[
                year_conflicts['side_a'].str.contains(actor, case=False, na=False) |
                year_conflicts['side_b'].str.contains(actor, case=False, na=False)
            ]

            has_conflict = len(actor_conflicts) > 0
            intensity_col = 'intensity_level' if 'intensity_level' in df.columns else 'int'
            max_intensity = actor_conflicts[intensity_col].max() if has_conflict else 0

            results.append({
                'actor': actor,
                'year': year,
                'has_conflict': int(has_conflict),
                'max_intensity': max_intensity,
                'n_conflicts': len(actor_conflicts),
            })

    return pd.DataFrame(results)


# Region mappings
UCDP_REGIONS = {
    1: 'Europe',
    2: 'Middle East',
    3: 'Asia',
    4: 'Africa',
    5: 'Americas',
}

# Conflict type mappings
CONFLICT_TYPES = {
    1: 'Extrasystemic',  # Colonial/imperial
    2: 'Interstate',      # Between states
    3: 'Internal',        # Civil war
    4: 'Internationalized Internal',  # Civil war with foreign intervention
}


if __name__ == "__main__":
    print("Testing UCDP Loader...")
    print("=" * 70)

    loader = UCDPLoader()

    try:
        df = loader.load_conflicts()
        print(f"\nLoaded {len(df)} conflict-year observations")
        print(f"Years: {df['year'].min()} - {df['year'].max()}")
        print(f"\nColumns: {df.columns.tolist()[:10]}...")

        # Summary by type
        type_col = 'type_of_conflict' if 'type_of_conflict' in df.columns else None
        if type_col:
            print(f"\nConflicts by type:")
            for type_id, type_name in CONFLICT_TYPES.items():
                count = len(df[df[type_col] == type_id]['conflict_id'].unique())
                print(f"  {type_name}: {count} unique conflicts")

        # Recent high-intensity conflicts
        intensity_col = 'intensity_level' if 'intensity_level' in df.columns else 'int'
        recent = df[(df['year'] >= 2020) & (df[intensity_col] == 2)]
        if len(recent) > 0:
            print(f"\nRecent wars (2020+):")
            for _, row in recent.drop_duplicates('conflict_id').head(10).iterrows():
                name = row.get('conflict_name', row.get('location', 'Unknown'))
                print(f"  - {name}")

        # Interstate conflicts
        interstate = loader.get_interstate_wars(2000)
        print(f"\nInterstate conflicts since 2000: {len(interstate['conflict_id'].unique())}")

    except Exception as e:
        print(f"Error loading UCDP data: {e}")
        print("You may need to download manually from https://ucdp.uu.se/downloads/")

    print("\n" + "=" * 70)
