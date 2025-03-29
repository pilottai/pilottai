import os
import json
import numpy as np
from typing import Any, Dict, List, Optional, Union
from datetime import datetime
import io
import pickle

from pilott.knowledge.source.base_input import BaseInputSource


class VectorInput(BaseInputSource):
    """
    Input source for processing vector embeddings and similarity search.
    Useful for semantic search, nearest neighbors, and knowledge retrieval.
    """

    def __init__(
        self,
        name: str,
        vectors: Optional[Union[List[List[float]], np.ndarray]] = None,
        file_path: Optional[str] = None,
        file_content: Optional[bytes] = None,
        texts: Optional[List[str]] = None,
        metadata: Optional[List[Dict[str, Any]]] = None,
        vector_format: str = "numpy",  # numpy, json, pickle
        distance_metric: str = "cosine",  # cosine, euclidean, dot
        top_k: int = 5,
        **kwargs
    ):
        super().__init__(name=name, **kwargs)
        self.vectors = vectors
        self.file_path = file_path
        self.file_content = file_content
        self.texts = texts or []
        self.item_metadata = metadata or []
        self.vector_format = vector_format.lower()
        self.distance_metric = distance_metric.lower()
        self.top_k = top_k

        # Storage
        self.text_content = None
        self.embeddings = None
        self.vector_dim = None
        self.vector_count = None

        # Validation
        valid_metrics = ["cosine", "euclidean", "dot"]
        if self.distance_metric not in valid_metrics:
            raise ValueError(f"Invalid distance metric: {self.distance_metric}. Must be one of {valid_metrics}")

    async def connect(self) -> bool:
        """Load vector embeddings from the specified source"""
        try:
            # Handle direct vector data
            if self.vectors is not None:
                if isinstance(self.vectors, list):
                    self.embeddings = np.array(self.vectors, dtype=np.float32)
                else:
                    self.embeddings = self.vectors

                self.vector_count, self.vector_dim = self.embeddings.shape
                self.is_connected = True
                return True

            # Handle binary content
            if self.file_content is not None:
                if self.vector_format == "numpy":
                    self.embeddings = np.load(io.BytesIO(self.file_content))
                elif self.vector_format == "json":
                    json_data = json.loads(self.file_content.decode("utf-8"))
                    self.embeddings = np.array(json_data, dtype=np.float32)
                elif self.vector_format == "pickle":
                    self.embeddings = pickle.loads(self.file_content)
                else:
                    raise ValueError(f"Unsupported vector format: {self.vector_format}")

                self.vector_count, self.vector_dim = self.embeddings.shape
                self.is_connected = True
                return True

            # Handle file path
            if self.file_path:
                if not os.path.exists(self.file_path):
                    self.logger.error(f"File not found: {self.file_path}")
                    self.is_connected = False
                    return False

                if not os.access(self.file_path, os.R_OK):
                    self.logger.error(f"File not readable: {self.file_path}")
                    self.is_connected = False
                    return False

                if self.vector_format == "numpy":
                    self.embeddings = np.load(self.file_path)
                elif self.vector_format == "json":
                    with open(self.file_path, 'r') as f:
                        json_data = json.load(f)
                    self.embeddings = np.array(json_data, dtype=np.float32)
                elif self.vector_format == "pickle":
                    with open(self.file_path, 'rb') as f:
                        self.embeddings = pickle.load(f)
                else:
                    raise ValueError(f"Unsupported vector format: {self.vector_format}")

                self.vector_count, self.vector_dim = self.embeddings.shape
                self.is_connected = True
                return True

            self.logger.error("No vector source provided")
            self.is_connected = False
            return False

        except Exception as e:
            self.logger.error(f"Connection error: {str(e)}")
            self.is_connected = False
            return False

    async def query(self, query: str) -> Any:
        """Execute semantic search using vector embeddings"""
        if not self.is_connected or self.embeddings is None:
            if not await self.connect():
                raise ValueError("Could not connect to vector source")

        self.access_count += 1
        self.last_access = datetime.now()

        # If query is a vector string (starts with "[" and ends with "]")
        if query.strip().startswith("[") and query.strip().endswith("]"):
            try:
                query_vector = json.loads(query)
                return await self._vector_search(np.array(query_vector, dtype=np.float32))
            except (json.JSONDecodeError, ValueError):
                pass

        # If query is a specification for nearest neighbors
        if query.lower().startswith("neighbors:"):
            try:
                index = int(query.split(":", 1)[1].strip())
                return await self._get_neighbors(index)
            except (ValueError, IndexError):
                return {"error": "Invalid index for neighbors query"}

        # If query is asking for vector statistics
        if query.lower() == "stats" or query.lower() == "statistics":
            return self._get_vector_stats()

        # Default to embedding the query and searching (if embedding function available)
        if hasattr(self, 'embed_text'):
            try:
                query_embedding = await self.embed_text(query)
                return await self._vector_search(query_embedding)
            except Exception as e:
                return {"error": f"Error embedding query: {str(e)}"}
        else:
            return {"error": "Text embedding not supported for this vector input source"}

    async def _vector_search(self, query_vector: np.ndarray) -> List[Dict[str, Any]]:
        """Search for similar vectors using the specified distance metric"""
        if len(query_vector.shape) == 1:
            # Ensure query vector has correct shape
            query_vector = query_vector.reshape(1, -1)

        if query_vector.shape[1] != self.vector_dim:
            raise ValueError(
                f"Query vector dimension {query_vector.shape[1]} does not match embeddings dimension {self.vector_dim}")

        # Calculate distances
        distances = self._calculate_distances(query_vector, self.embeddings)

        # Get top-k results (smallest distances for euclidean, largest for cosine similarity and dot product)
        if self.distance_metric == "euclidean":
            indices = np.argsort(distances)[:self.top_k]
        else:
            indices = np.argsort(distances)[::-1][:self.top_k]

        # Format results
        results = []
        for i, idx in enumerate(indices):
            result = {
                "index": int(idx),
                "score": float(distances[idx]),
                "rank": i + 1
            }

            # Add text if available
            if idx < len(self.texts):
                result["text"] = self.texts[idx]

            # Add metadata if available
            if idx < len(self.item_metadata):
                result["metadata"] = self.item_metadata[idx]

            results.append(result)

        return results

    def _calculate_distances(self, query_vector: np.ndarray, vectors: np.ndarray) -> np.ndarray:
        """Calculate distances between query vector and all vectors"""
        if self.distance_metric == "cosine":
            # Normalize vectors for cosine similarity
            query_norm = np.linalg.norm(query_vector, axis=1, keepdims=True)
            vectors_norm = np.linalg.norm(vectors, axis=1, keepdims=True)

            # Avoid division by zero
            query_norm = np.maximum(query_norm, 1e-10)
            vectors_norm = np.maximum(vectors_norm, 1e-10)

            normalized_query = query_vector / query_norm
            normalized_vectors = vectors / vectors_norm

            # Cosine similarity
            similarities = np.dot(normalized_query, normalized_vectors.T).flatten()
            return similarities

        elif self.distance_metric == "euclidean":
            # Euclidean distance
            distances = np.sqrt(
                np.sum((query_vector - vectors.reshape(vectors.shape[0], -1)) ** 2, axis=1)
            )
            return distances

        elif self.distance_metric == "dot":
            # Dot product
            dot_products = np.dot(query_vector, vectors.T).flatten()
            return dot_products

        raise ValueError(f"Unsupported distance metric: {self.distance_metric}")

    async def _get_neighbors(self, index: int) -> List[Dict[str, Any]]:
        """Get nearest neighbors of the specified vector"""
        if index < 0 or index >= self.vector_count:
            return {"error": f"Index out of bounds: {index}, valid range: 0-{self.vector_count - 1}"}

        query_vector = self.embeddings[index].reshape(1, -1)

        # Calculate distances to all vectors
        distances = self._calculate_distances(query_vector, self.embeddings)

        # Exclude the query vector itself
        if self.distance_metric == "euclidean":
            # For euclidean, sort ascending (smaller is closer)
            indices = np.argsort(distances)[1:self.top_k + 1]  # Skip the first (self)
        else:
            # For cosine and dot, sort descending (larger is closer)
            indices = np.argsort(distances)[::-1][1:self.top_k + 1]  # Skip the first (self)

        # Format results
        results = []
        for i, idx in enumerate(indices):
            result = {
                "index": int(idx),
                "score": float(distances[idx]),
                "rank": i + 1
            }

            # Add text if available
            if idx < len(self.texts):
                result["text"] = self.texts[idx]

            # Add metadata if available
            if idx < len(self.item_metadata):
                result["metadata"] = self.item_metadata[idx]

            results.append(result)

        return results

    def _get_vector_stats(self) -> Dict[str, Any]:
        """Get statistics about the vector embeddings"""
        stats = {
            "vector_count": self.vector_count,
            "vector_dimension": self.vector_dim,
            "distance_metric": self.distance_metric,
            "format": self.vector_format
        }

        # Calculate basic embedding statistics
        if self.embeddings is not None:
            stats.update({
                "min_value": float(np.min(self.embeddings)),
                "max_value": float(np.max(self.embeddings)),
                "mean_value": float(np.mean(self.embeddings)),
                "std_value": float(np.std(self.embeddings)),
                "l2_norms": {
                    "min": float(np.min(np.linalg.norm(self.embeddings, axis=1))),
                    "max": float(np.max(np.linalg.norm(self.embeddings, axis=1))),
                    "mean": float(np.mean(np.linalg.norm(self.embeddings, axis=1)))
                }
            })

        return stats

    async def validate_content(self) -> bool:
        """Validate that vector embeddings are accessible and well-formed"""
        if not self.is_connected:
            if not await self.connect():
                return False

        # Check if embeddings are loaded
        if self.embeddings is None:
            return False

        # Check if embeddings have valid shape
        if len(self.embeddings.shape) != 2:
            self.logger.error(f"Invalid embedding shape: {self.embeddings.shape}. Expected 2D array.")
            return False

        # Check if metadata and texts match vectors count
        if self.texts and len(self.texts) != self.vector_count:
            self.logger.warning(
                f"Text count ({len(self.texts)}) does not match vector count ({self.vector_count})"
            )

        if self.item_metadata and len(self.item_metadata) != self.vector_count:
            self.logger.warning(
                f"Metadata count ({len(self.item_metadata)}) does not match vector count ({self.vector_count})"
            )

        return True

    async def embed_text(self, text: str) -> np.ndarray:
        """
        Embed text into a vector.
        This is a placeholder - subclasses should implement this with actual embedding logic.
        """
        raise NotImplementedError("Text embedding not implemented for base VectorInput")

    async def _process_content(self) -> None:
        """Process vector embeddings into text representation"""
        if not self.is_connected or self.embeddings is None:
            if not await self.connect():
                return

        # Create text summary of vector data
        summary_parts = [
            f"# Vector Embeddings ({self.name})",
            f"Vector count: {self.vector_count}",
            f"Vector dimension: {self.vector_dim}",
            f"Distance metric: {self.distance_metric}"
        ]

        # Add stats
        stats = self._get_vector_stats()
        stats_text = [f"{k}: {v}" for k, v in stats.items()
                      if k not in ["vector_count", "vector_dimension", "distance_metric"]]
        summary_parts.append("## Statistics\n" + "\n".join(stats_text))

        # Add sample vectors
        sample_count = min(5, self.vector_count)
        samples = []
        for i in range(sample_count):
            vector_sample = self.embeddings[i][:10]  # Show first 10 dimensions
            samples.append(
                f"Vector {i}: [{', '.join(f'{x:.4f}' for x in vector_sample)}...] "
                f"(norm: {np.linalg.norm(self.embeddings[i]):.4f})"
            )

        summary_parts.append("## Sample Vectors\n" + "\n".join(samples))

        # Add associated texts if available
        if self.texts:
            text_samples = []
            for i in range(min(5, len(self.texts))):
                text = self.texts[i]
                if len(text) > 100:
                    text = text[:100] + "..."
                text_samples.append(f"Text {i}: {text}")

            summary_parts.append("## Associated Texts\n" + "\n".join(text_samples))

        self.text_content = "\n\n".join(summary_parts)
        self.chunks = self._chunk_text(self.text_content)

        source_desc = self.file_path if self.file_path else "vector data"
        self.logger.info(f"Created {len(self.chunks)} chunks from {source_desc}")

    def add_text_vector_pair(self, text: str, vector: np.ndarray, metadata: Optional[Dict[str, Any]] = None) -> bool:
        """Add a new text-vector pair to the existing data"""
        try:
            if self.embeddings is None:
                # Initialize embeddings with the first vector
                self.embeddings = vector.reshape(1, -1)
                self.vector_count = 1
                self.vector_dim = vector.shape[0]
            else:
                # Check vector dimension
                if vector.shape[0] != self.vector_dim:
                    raise ValueError(f"Vector dimension mismatch: got {vector.shape[0]}, expected {self.vector_dim}")

                # Append vector
                self.embeddings = np.vstack([self.embeddings, vector.reshape(1, -1)])
                self.vector_count += 1

            # Append text and metadata
            self.texts.append(text)
            self.item_metadata.append(metadata or {})

            return True

        except Exception as e:
            self.logger.error(f"Error adding text-vector pair: {str(e)}")
            return False
