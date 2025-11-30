"""
Text-Based Compression Scheme Extraction

Extracts compression schemes from text corpora using embeddings + clustering.
The embedding space captures how an actor "compresses" the world into
meaningful categories.

Author: Ryan J Cardwell (Archer Phoenix)
"""
import numpy as np
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
import pandas as pd
from sklearn.cluster import KMeans, MiniBatchKMeans
from sklearn.decomposition import PCA, TruncatedSVD
from sklearn.feature_extraction.text import TfidfVectorizer, CountVectorizer
from sklearn.decomposition import LatentDirichletAllocation
import warnings

# Try to import sentence-transformers (optional)
try:
    from sentence_transformers import SentenceTransformer
    HAS_SENTENCE_TRANSFORMERS = True
except ImportError:
    HAS_SENTENCE_TRANSFORMERS = False

from .schemes import CompressionScheme, SchemeSource


@dataclass
class CategoryInfo:
    """Information about a category in the compression space."""
    id: int
    label: str
    centroid: np.ndarray
    keywords: List[str]
    size: int  # Number of documents in training


class TextCompressionExtractor:
    """
    Extracts compression schemes from text corpora.

    Uses embeddings + clustering to identify "categories" in actor's worldview.

    Pipeline:
    1. Embed documents into semantic space
    2. Cluster to identify category structure
    3. Actor's scheme = distribution over clusters
    """

    def __init__(
        self,
        embedding_model: str = "all-MiniLM-L6-v2",
        n_categories: int = 50,
        use_gpu: bool = False,
        random_state: int = 42,
    ):
        """
        Initialize extractor.

        Args:
            embedding_model: Sentence transformer model name or 'tfidf' for simple approach
            n_categories: Number of categories in compression space
            use_gpu: Whether to use GPU for embeddings
            random_state: Random seed for reproducibility
        """
        self.embedding_model_name = embedding_model
        self.n_categories = n_categories
        self.random_state = random_state

        # Initialize embedding model
        if embedding_model == 'tfidf':
            self.embedder = None
            self.use_tfidf = True
            self.tfidf = TfidfVectorizer(
                max_features=5000,
                stop_words='english',
                max_df=0.95,
                min_df=2,
            )
        elif HAS_SENTENCE_TRANSFORMERS:
            self.embedder = SentenceTransformer(embedding_model)
            if use_gpu:
                self.embedder = self.embedder.to('cuda')
            self.use_tfidf = False
        else:
            warnings.warn(
                "sentence-transformers not installed. Using TF-IDF fallback. "
                "Install with: pip install sentence-transformers"
            )
            self.embedder = None
            self.use_tfidf = True
            self.tfidf = TfidfVectorizer(
                max_features=5000,
                stop_words='english',
                max_df=0.95,
                min_df=2,
            )

        self.cluster_model: Optional[KMeans] = None
        self.category_info: List[CategoryInfo] = []
        self.pca: Optional[PCA] = None
        self.is_fitted = False

    def fit_categories(
        self,
        reference_corpus: List[str],
        category_labels: Optional[List[str]] = None,
        use_minibatch: bool = True,
    ) -> 'TextCompressionExtractor':
        """
        Fit category structure from large reference corpus.

        This defines the "universal" category space against which
        all actors' compression schemes are measured.

        Args:
            reference_corpus: Large corpus defining the category space
            category_labels: Optional pre-defined category labels
            use_minibatch: Use MiniBatchKMeans for large corpora

        Returns:
            self for chaining
        """
        print(f"Fitting categories from {len(reference_corpus)} documents...")

        # Embed reference corpus
        embeddings = self._embed_documents(reference_corpus)

        # Optionally reduce dimensionality
        if embeddings.shape[1] > 100:
            print(f"  Reducing dimensions from {embeddings.shape[1]} to 100...")
            self.pca = PCA(n_components=100, random_state=self.random_state)
            embeddings = self.pca.fit_transform(embeddings)

        # Cluster to find categories
        print(f"  Clustering into {self.n_categories} categories...")
        if use_minibatch and len(reference_corpus) > 10000:
            self.cluster_model = MiniBatchKMeans(
                n_clusters=self.n_categories,
                random_state=self.random_state,
                batch_size=1024,
                n_init=3,
            )
        else:
            self.cluster_model = KMeans(
                n_clusters=self.n_categories,
                random_state=self.random_state,
                n_init=10,
            )

        cluster_assignments = self.cluster_model.fit_predict(embeddings)

        # Generate category info
        self.category_info = []
        for i in range(self.n_categories):
            mask = cluster_assignments == i
            cluster_docs = [reference_corpus[j] for j in range(len(reference_corpus)) if mask[j]]

            # Extract keywords for this cluster
            keywords = self._extract_cluster_keywords(cluster_docs)

            self.category_info.append(CategoryInfo(
                id=i,
                label=category_labels[i] if category_labels else f"topic_{i}",
                centroid=self.cluster_model.cluster_centers_[i],
                keywords=keywords,
                size=int(np.sum(mask)),
            ))

        self.is_fitted = True
        print(f"  Identified {self.n_categories} categories.")

        return self

    def _embed_documents(self, documents: List[str]) -> np.ndarray:
        """Embed documents into vector space."""
        if self.use_tfidf:
            if not hasattr(self.tfidf, 'vocabulary_') or not self.tfidf.vocabulary_:
                return self.tfidf.fit_transform(documents).toarray()
            else:
                return self.tfidf.transform(documents).toarray()
        else:
            return self.embedder.encode(
                documents,
                show_progress_bar=len(documents) > 100,
                batch_size=32,
            )

    def _extract_cluster_keywords(
        self,
        cluster_docs: List[str],
        n_keywords: int = 5,
    ) -> List[str]:
        """Extract representative keywords for a cluster."""
        if len(cluster_docs) < 3:
            return ["N/A"]

        try:
            tfidf = TfidfVectorizer(
                max_features=100,
                stop_words='english',
                max_df=0.9,
            )
            tfidf_matrix = tfidf.fit_transform(cluster_docs)

            # Get average TF-IDF scores
            avg_scores = np.asarray(tfidf_matrix.mean(axis=0)).flatten()
            feature_names = tfidf.get_feature_names_out()

            top_indices = avg_scores.argsort()[::-1][:n_keywords]
            return [feature_names[i] for i in top_indices]
        except Exception:
            return ["N/A"]

    def extract_scheme(
        self,
        actor_documents: List[str],
        actor_id: str,
        timestamp: Optional[pd.Timestamp] = None,
    ) -> CompressionScheme:
        """
        Extract compression scheme from actor's documents.

        Returns distribution over categories based on document clustering.

        Args:
            actor_documents: Documents associated with the actor
            actor_id: Actor identifier
            timestamp: Optional timestamp for the scheme

        Returns:
            CompressionScheme with category distribution
        """
        if not self.is_fitted:
            raise ValueError("Must call fit_categories first!")

        if len(actor_documents) == 0:
            # Return uniform distribution
            return CompressionScheme(
                actor_id=actor_id,
                distribution=np.ones(self.n_categories) / self.n_categories,
                categories=[c.label for c in self.category_info],
                timestamp=timestamp,
                source=SchemeSource.TEXT,
                metadata={'n_documents': 0, 'method': 'text_clustering'},
            )

        # Embed actor's documents
        embeddings = self._embed_documents(actor_documents)

        # Apply PCA if fitted
        if self.pca is not None:
            embeddings = self.pca.transform(embeddings)

        # Assign to categories
        cluster_assignments = self.cluster_model.predict(embeddings)

        # Compute distribution
        distribution = np.bincount(
            cluster_assignments,
            minlength=self.n_categories,
        ).astype(float)
        distribution /= (distribution.sum() + 1e-10)

        return CompressionScheme(
            actor_id=actor_id,
            distribution=distribution,
            categories=[c.label for c in self.category_info],
            timestamp=timestamp or pd.Timestamp.now(),
            source=SchemeSource.TEXT,
            metadata={
                'n_documents': len(actor_documents),
                'method': 'text_clustering',
                'embedding_model': self.embedding_model_name,
            },
        )

    def extract_temporal_schemes(
        self,
        actor_documents: List[Dict],  # {'text': str, 'date': datetime}
        actor_id: str,
        window_days: int = 30,
        min_docs: int = 5,
    ) -> List[CompressionScheme]:
        """
        Extract compression schemes over time with rolling window.

        Args:
            actor_documents: List of {'text': str, 'date': datetime} dicts
            actor_id: Actor identifier
            window_days: Window size in days
            min_docs: Minimum documents per window

        Returns:
            List of CompressionScheme objects over time
        """
        if not self.is_fitted:
            raise ValueError("Must call fit_categories first!")

        # Sort by date
        docs = sorted(actor_documents, key=lambda x: x['date'])

        # Convert to DataFrame for easy windowing
        df = pd.DataFrame(docs)
        df['date'] = pd.to_datetime(df['date'])
        df.set_index('date', inplace=True)

        schemes = []

        # Rolling window
        for end_date, window_df in df.groupby(pd.Grouper(freq=f'{window_days}D')):
            if len(window_df) < min_docs:
                continue

            scheme = self.extract_scheme(
                window_df['text'].tolist(),
                actor_id,
            )
            scheme.timestamp = end_date
            scheme.metadata['window_start'] = end_date - pd.Timedelta(days=window_days)
            scheme.metadata['window_end'] = end_date
            schemes.append(scheme)

        return schemes

    def get_category_description(self, category_id: int) -> Dict:
        """Get description of a category."""
        if not self.is_fitted:
            raise ValueError("Not fitted!")

        info = self.category_info[category_id]
        return {
            'id': info.id,
            'label': info.label,
            'keywords': info.keywords,
            'size': info.size,
        }


class LDACompressionExtractor:
    """
    LDA-based compression scheme extraction.

    Uses Latent Dirichlet Allocation to define topic space.
    Topic distribution = how actor allocates attention across concepts.
    """

    def __init__(
        self,
        n_categories: int = 50,
        max_features: int = 10000,
        random_state: int = 42,
    ):
        self.n_categories = n_categories
        self.max_features = max_features
        self.random_state = random_state

        self.vectorizer = CountVectorizer(
            max_df=0.95,
            min_df=2,
            max_features=max_features,
            stop_words='english',
        )
        self.lda: Optional[LatentDirichletAllocation] = None
        self.topic_keywords: List[List[str]] = []
        self.is_fitted = False

    def fit(self, reference_corpus: List[str]) -> 'LDACompressionExtractor':
        """Fit LDA model on reference corpus."""
        print(f"Fitting LDA with {self.n_categories} topics on {len(reference_corpus)} docs...")

        # Vectorize
        doc_term_matrix = self.vectorizer.fit_transform(reference_corpus)

        # Fit LDA
        self.lda = LatentDirichletAllocation(
            n_components=self.n_categories,
            random_state=self.random_state,
            max_iter=20,
            learning_method='online',
            batch_size=128,
            n_jobs=-1,
        )
        self.lda.fit(doc_term_matrix)

        # Extract topic keywords
        feature_names = self.vectorizer.get_feature_names_out()
        self.topic_keywords = []
        for topic_idx, topic in enumerate(self.lda.components_):
            top_word_indices = topic.argsort()[:-11:-1]
            self.topic_keywords.append([feature_names[i] for i in top_word_indices])

        self.is_fitted = True
        print(f"  Fitted {self.n_categories} topics.")

        return self

    def extract_scheme(
        self,
        actor_documents: List[str],
        actor_id: str,
        timestamp: Optional[pd.Timestamp] = None,
    ) -> CompressionScheme:
        """Extract compression scheme using LDA topic distribution."""
        if not self.is_fitted:
            raise ValueError("Must call fit first!")

        if len(actor_documents) == 0:
            return CompressionScheme(
                actor_id=actor_id,
                distribution=np.ones(self.n_categories) / self.n_categories,
                categories=[f"topic_{i}" for i in range(self.n_categories)],
                timestamp=timestamp,
                source=SchemeSource.TEXT,
                metadata={'n_documents': 0, 'method': 'lda'},
            )

        # Transform documents
        doc_term_matrix = self.vectorizer.transform(actor_documents)
        doc_topic_matrix = self.lda.transform(doc_term_matrix)

        # Average topic distribution = actor's compression scheme
        distribution = doc_topic_matrix.mean(axis=0)

        return CompressionScheme(
            actor_id=actor_id,
            distribution=distribution,
            categories=[f"topic_{i}: {', '.join(self.topic_keywords[i][:3])}"
                       for i in range(self.n_categories)],
            timestamp=timestamp or pd.Timestamp.now(),
            source=SchemeSource.TEXT,
            metadata={
                'n_documents': len(actor_documents),
                'method': 'lda',
            },
        )


def create_text_extractor(
    method: str = 'embedding',
    n_categories: int = 50,
    **kwargs,
) -> TextCompressionExtractor:
    """
    Factory function to create text compression extractor.

    Args:
        method: 'embedding' (default), 'lda', or 'tfidf'
        n_categories: Number of categories
        **kwargs: Additional arguments

    Returns:
        Configured extractor
    """
    if method == 'lda':
        return LDACompressionExtractor(n_categories=n_categories, **kwargs)
    elif method == 'tfidf':
        return TextCompressionExtractor(
            embedding_model='tfidf',
            n_categories=n_categories,
            **kwargs,
        )
    else:
        return TextCompressionExtractor(
            n_categories=n_categories,
            **kwargs,
        )


if __name__ == "__main__":
    print("Testing Text Compression Extractor...")
    print("=" * 70)

    # Sample documents representing different "worldviews"
    usa_docs = [
        "Freedom and democracy are fundamental American values.",
        "The free market drives economic prosperity and innovation.",
        "Military strength ensures national security and global peace.",
        "Individual rights must be protected from government overreach.",
        "American leadership is essential for global stability.",
    ]

    russia_docs = [
        "NATO expansion threatens Russian security and sovereignty.",
        "Western interference in internal affairs must be resisted.",
        "Traditional values and strong leadership define Russian identity.",
        "Energy resources are key to national power and influence.",
        "Multipolar world order should replace Western hegemony.",
    ]

    china_docs = [
        "Economic development is the primary national goal.",
        "Social harmony and stability require collective effort.",
        "National rejuvenation will restore China's rightful place.",
        "Technology and innovation drive modernization.",
        "One China principle is non-negotiable sovereignty issue.",
    ]

    # Combined reference corpus
    reference = usa_docs + russia_docs + china_docs + [
        "International trade benefits all participating nations.",
        "Climate change requires global cooperation.",
        "Human rights are universal principles.",
        "Economic sanctions are tools of foreign policy.",
        "Diplomacy should precede military action.",
    ]

    # Test with TF-IDF (no external dependencies)
    print("\nUsing TF-IDF method (no external dependencies):")
    extractor = create_text_extractor(method='tfidf', n_categories=5)
    extractor.fit_categories(reference)

    # Extract schemes
    scheme_usa = extractor.extract_scheme(usa_docs, "USA")
    scheme_rus = extractor.extract_scheme(russia_docs, "RUS")
    scheme_chn = extractor.extract_scheme(china_docs, "CHN")

    print(f"\nUSA scheme entropy: {scheme_usa.entropy:.3f}")
    print(f"RUS scheme entropy: {scheme_rus.entropy:.3f}")
    print(f"CHN scheme entropy: {scheme_chn.entropy:.3f}")

    print(f"\nDivergences:")
    print(f"  USA-RUS Φ: {scheme_usa.symmetric_divergence(scheme_rus):.3f}")
    print(f"  USA-CHN Φ: {scheme_usa.symmetric_divergence(scheme_chn):.3f}")
    print(f"  RUS-CHN Φ: {scheme_rus.symmetric_divergence(scheme_chn):.3f}")

    print("\n" + "=" * 70)
