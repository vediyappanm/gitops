"""Failure Pattern Memory using vector database for historical context"""
import logging
import hashlib
import json
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
import numpy as np

logger = logging.getLogger(__name__)


# Constants
SIMILARITY_THRESHOLD = 0.75  # Minimum similarity to consider a match
MAX_SIMILAR_PATTERNS = 5  # Return top 5 similar patterns
EMBEDDING_DIMENSION = 1536  # OpenAI ada-002 embedding dimension


@dataclass
class FailurePattern:
    """Stored failure pattern with fix"""
    pattern_id: str
    repository: str
    branch: str
    failure_reason: str
    failure_category: str
    error_signature: str  # Normalized error for matching
    proposed_fix: str
    fix_successful: bool
    files_modified: List[str] = field(default_factory=list)
    fix_commands: List[str] = field(default_factory=list)
    risk_score: int = 5
    resolution_time_ms: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    embedding: Optional[List[float]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "pattern_id": self.pattern_id,
            "repository": self.repository,
            "branch": self.branch,
            "failure_reason": self.failure_reason,
            "failure_category": self.failure_category,
            "error_signature": self.error_signature,
            "proposed_fix": self.proposed_fix,
            "fix_successful": self.fix_successful,
            "files_modified": self.files_modified,
            "fix_commands": self.fix_commands,
            "risk_score": self.risk_score,
            "resolution_time_ms": self.resolution_time_ms,
            "created_at": self.created_at.isoformat(),
            "has_embedding": self.embedding is not None
        }


@dataclass
class SimilarPattern:
    """Similar pattern with similarity score"""
    pattern: FailurePattern
    similarity_score: float
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "pattern": self.pattern.to_dict(),
            "similarity_score": self.similarity_score
        }


class FailurePatternMemory:
    """Store and retrieve failure patterns using vector similarity"""

    def __init__(self, database, openai_api_key: Optional[str] = None,
                 use_local_embeddings: bool = False):
        """
        Initialize failure pattern memory.
        
        Args:
            database: Database instance for storage
            openai_api_key: OpenAI API key for embeddings (optional)
            use_local_embeddings: Use local embeddings instead of OpenAI
            
        Raises:
            ValueError: If database is None
        """
        if database is None:
            raise ValueError("database cannot be None")
        
        self.database = database
        self.openai_api_key = openai_api_key
        self.use_local_embeddings = use_local_embeddings
        
        # In-memory cache for fast lookups
        self.pattern_cache: Dict[str, FailurePattern] = {}
        
        # Load existing patterns into cache
        self._load_patterns_from_db()
        
        logger.info(f"FailurePatternMemory initialized: "
                   f"use_local_embeddings={use_local_embeddings}, "
                   f"cached_patterns={len(self.pattern_cache)}")

    def store_pattern(self, failure_id: str, repository: str, branch: str,
                     failure_reason: str, failure_category: str,
                     proposed_fix: str, fix_successful: bool,
                     files_modified: List[str], fix_commands: List[str],
                     risk_score: int, resolution_time_ms: int) -> FailurePattern:
        """
        Store a failure pattern with its fix.
        
        Args:
            failure_id: Unique failure identifier
            repository: Repository name
            branch: Branch name
            failure_reason: Failure reason/error message
            failure_category: Category of failure
            proposed_fix: Fix that was applied
            fix_successful: Whether fix was successful
            files_modified: List of files modified
            fix_commands: List of commands executed
            risk_score: Risk score of the fix
            resolution_time_ms: Time to resolve in milliseconds
            
        Returns:
            Stored FailurePattern
            
        Raises:
            ValueError: If required fields are invalid
        """
        if not failure_id or not isinstance(failure_id, str):
            raise ValueError(f"failure_id must be non-empty string, got {type(failure_id)}")
        if not repository or not isinstance(repository, str):
            raise ValueError(f"repository must be non-empty string, got {type(repository)}")
        if not failure_reason or not isinstance(failure_reason, str):
            raise ValueError(f"failure_reason must be non-empty string, got {type(failure_reason)}")
        
        try:
            # Normalize error signature for matching
            error_signature = self._normalize_error(failure_reason)
            
            # Generate embedding
            embedding = self._generate_embedding(failure_reason, failure_category)
            
            # Create pattern
            pattern = FailurePattern(
                pattern_id=failure_id,
                repository=repository,
                branch=branch,
                failure_reason=failure_reason,
                failure_category=failure_category,
                error_signature=error_signature,
                proposed_fix=proposed_fix,
                fix_successful=fix_successful,
                files_modified=files_modified,
                fix_commands=fix_commands,
                risk_score=risk_score,
                resolution_time_ms=resolution_time_ms,
                created_at=datetime.now(timezone.utc),
                embedding=embedding
            )
            
            # Store in database
            self.database.store_failure_pattern(pattern)
            
            # Add to cache
            self.pattern_cache[failure_id] = pattern
            
            logger.info(f"Stored failure pattern: {failure_id} "
                       f"(category={failure_category}, successful={fix_successful})")
            
            return pattern
            
        except Exception as e:
            logger.error(f"Failed to store pattern: {e}")
            raise

    def find_similar_patterns(self, failure_reason: str, failure_category: str,
                             repository: Optional[str] = None,
                             only_successful: bool = True,
                             max_results: int = MAX_SIMILAR_PATTERNS) -> List[SimilarPattern]:
        """
        Find similar failure patterns from history.
        
        Args:
            failure_reason: Current failure reason
            failure_category: Current failure category
            repository: Optional repository filter
            only_successful: Only return patterns with successful fixes
            max_results: Maximum number of results to return
            
        Returns:
            List of similar patterns sorted by similarity
            
        Raises:
            ValueError: If inputs are invalid
        """
        if not failure_reason or not isinstance(failure_reason, str):
            raise ValueError(f"failure_reason must be non-empty string, got {type(failure_reason)}")
        if max_results <= 0:
            raise ValueError(f"max_results must be positive, got {max_results}")
        
        try:
            logger.info(f"Finding similar patterns for: {failure_reason[:100]}...")
            
            # Generate embedding for current failure
            query_embedding = self._generate_embedding(failure_reason, failure_category)
            
            # Get candidate patterns
            candidates = list(self.pattern_cache.values())
            
            # Filter by repository if specified
            if repository:
                candidates = [p for p in candidates if p.repository == repository]
            
            # Filter by success if specified
            if only_successful:
                candidates = [p for p in candidates if p.fix_successful]
            
            # Filter by category (prefer same category)
            same_category = [p for p in candidates if p.failure_category == failure_category]
            other_category = [p for p in candidates if p.failure_category != failure_category]
            
            # Calculate similarities
            similar_patterns = []
            
            # Check same category first
            for pattern in same_category:
                if pattern.embedding:
                    similarity = self._calculate_similarity(query_embedding, pattern.embedding)
                    if similarity >= SIMILARITY_THRESHOLD:
                        similar_patterns.append(SimilarPattern(pattern, similarity))
            
            # If not enough matches, check other categories
            if len(similar_patterns) < max_results:
                for pattern in other_category:
                    if pattern.embedding:
                        similarity = self._calculate_similarity(query_embedding, pattern.embedding)
                        # Higher threshold for different categories
                        if similarity >= SIMILARITY_THRESHOLD + 0.1:
                            similar_patterns.append(SimilarPattern(pattern, similarity))
            
            # Sort by similarity (descending)
            similar_patterns.sort(key=lambda x: x.similarity_score, reverse=True)
            
            # Return top N
            results = similar_patterns[:max_results]
            
            logger.info(f"Found {len(results)} similar patterns "
                       f"(threshold={SIMILARITY_THRESHOLD})")
            
            return results
            
        except Exception as e:
            logger.error(f"Failed to find similar patterns: {e}")
            return []

    def get_historical_context(self, failure_reason: str, failure_category: str,
                              repository: Optional[str] = None) -> str:
        """
        Get formatted historical context for AI analysis.
        
        Args:
            failure_reason: Current failure reason
            failure_category: Current failure category
            repository: Optional repository filter
            
        Returns:
            Formatted string with historical context
        """
        try:
            similar_patterns = self.find_similar_patterns(
                failure_reason,
                failure_category,
                repository,
                only_successful=True,
                max_results=3
            )
            
            if not similar_patterns:
                return "No similar historical failures found."
            
            context_parts = ["HISTORICAL CONTEXT - Similar Past Failures:\n"]
            
            for i, similar in enumerate(similar_patterns, 1):
                pattern = similar.pattern
                context_parts.append(
                    f"\n{i}. Similar Failure (similarity: {similar.similarity_score:.2f}):\n"
                    f"   Repository: {pattern.repository}\n"
                    f"   Category: {pattern.failure_category}\n"
                    f"   Error: {pattern.failure_reason[:200]}...\n"
                    f"   Successful Fix Applied:\n"
                    f"   {pattern.proposed_fix[:300]}...\n"
                    f"   Files Modified: {', '.join(pattern.files_modified[:5])}\n"
                    f"   Resolution Time: {pattern.resolution_time_ms / 1000:.1f}s\n"
                )
            
            context_parts.append(
                "\nUse these historical fixes as reference, but adapt to current context."
            )
            
            return "".join(context_parts)
            
        except Exception as e:
            logger.error(f"Failed to get historical context: {e}")
            return "Error retrieving historical context."

    def _normalize_error(self, error: str) -> str:
        """
        Normalize error message for matching.
        
        Args:
            error: Raw error message
            
        Returns:
            Normalized error signature
        """
        import re
        
        normalized = error.lower()
        
        # Remove timestamps
        normalized = re.sub(r'\d{4}-\d{2}-\d{2}', '', normalized)
        normalized = re.sub(r'\d{2}:\d{2}:\d{2}', '', normalized)
        
        # Remove line numbers
        normalized = re.sub(r'line \d+', 'line X', normalized)
        normalized = re.sub(r':\d+:', ':X:', normalized)
        
        # Remove file paths
        normalized = re.sub(r'/[\w/.-]+\.(py|js|ts|java|go)', '/path/file.ext', normalized)
        
        # Remove UUIDs
        normalized = re.sub(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', 'UUID', normalized)
        
        # Remove memory addresses
        normalized = re.sub(r'0x[0-9a-f]+', '0xADDR', normalized)
        
        # Normalize whitespace
        normalized = re.sub(r'\s+', ' ', normalized).strip()
        
        return normalized[:500]  # Limit length

    def _generate_embedding(self, failure_reason: str, failure_category: str) -> List[float]:
        """
        Generate embedding vector for failure.
        
        Args:
            failure_reason: Failure reason
            failure_category: Failure category
            
        Returns:
            Embedding vector
        """
        try:
            if self.use_local_embeddings:
                return self._generate_local_embedding(failure_reason, failure_category)
            else:
                return self._generate_openai_embedding(failure_reason, failure_category)
        except Exception as e:
            logger.error(f"Failed to generate embedding: {e}")
            # Return zero vector as fallback
            return [0.0] * EMBEDDING_DIMENSION

    def _generate_openai_embedding(self, failure_reason: str, failure_category: str) -> List[float]:
        """
        Generate embedding using OpenAI API.
        
        Args:
            failure_reason: Failure reason
            failure_category: Failure category
            
        Returns:
            Embedding vector
        """
        if not self.openai_api_key:
            logger.warning("OpenAI API key not provided, using local embeddings")
            return self._generate_local_embedding(failure_reason, failure_category)
        
        try:
            import requests
            
            # Combine failure reason and category for better context
            text = f"Category: {failure_category}\nError: {failure_reason}"
            
            headers = {
                "Authorization": f"Bearer {self.openai_api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "input": text[:8000],  # Limit input length
                "model": "text-embedding-ada-002"
            }
            
            response = requests.post(
                "https://api.openai.com/v1/embeddings",
                headers=headers,
                json=payload,
                timeout=30
            )
            
            if response.status_code != 200:
                logger.error(f"OpenAI API error: {response.status_code}")
                return self._generate_local_embedding(failure_reason, failure_category)
            
            data = response.json()
            embedding = data["data"][0]["embedding"]
            
            logger.debug(f"Generated OpenAI embedding: {len(embedding)} dimensions")
            return embedding
            
        except Exception as e:
            logger.error(f"Failed to generate OpenAI embedding: {e}")
            return self._generate_local_embedding(failure_reason, failure_category)

    def _generate_local_embedding(self, failure_reason: str, failure_category: str) -> List[float]:
        """
        Generate simple local embedding (fallback).
        
        Args:
            failure_reason: Failure reason
            failure_category: Failure category
            
        Returns:
            Embedding vector
        """
        # Simple hash-based embedding for fallback
        text = f"{failure_category}:{failure_reason}"
        
        # Generate multiple hashes for different dimensions
        embedding = []
        for i in range(EMBEDDING_DIMENSION // 32):
            hash_input = f"{text}:{i}".encode()
            hash_value = hashlib.sha256(hash_input).digest()
            
            # Convert bytes to floats
            for j in range(0, len(hash_value), 4):
                if len(embedding) >= EMBEDDING_DIMENSION:
                    break
                chunk = hash_value[j:j+4]
                value = int.from_bytes(chunk, byteorder='big') / (2**32)
                embedding.append(value)
        
        # Pad if needed
        while len(embedding) < EMBEDDING_DIMENSION:
            embedding.append(0.0)
        
        return embedding[:EMBEDDING_DIMENSION]

    def _calculate_similarity(self, embedding1: List[float], embedding2: List[float]) -> float:
        """
        Calculate cosine similarity between embeddings.
        
        Args:
            embedding1: First embedding vector
            embedding2: Second embedding vector
            
        Returns:
            Similarity score (0-1)
        """
        try:
            # Convert to numpy arrays
            vec1 = np.array(embedding1)
            vec2 = np.array(embedding2)
            
            # Calculate cosine similarity
            dot_product = np.dot(vec1, vec2)
            norm1 = np.linalg.norm(vec1)
            norm2 = np.linalg.norm(vec2)
            
            if norm1 == 0 or norm2 == 0:
                return 0.0
            
            similarity = dot_product / (norm1 * norm2)
            
            # Clamp to [0, 1]
            return max(0.0, min(1.0, float(similarity)))
            
        except Exception as e:
            logger.error(f"Failed to calculate similarity: {e}")
            return 0.0

    def _load_patterns_from_db(self) -> None:
        """Load existing patterns from database into cache"""
        try:
            patterns = self.database.get_all_failure_patterns()
            for pattern in patterns:
                self.pattern_cache[pattern.pattern_id] = pattern
            
            logger.info(f"Loaded {len(patterns)} patterns from database")
            
        except Exception as e:
            logger.warning(f"Failed to load patterns from database: {e}")

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about stored patterns.
        
        Returns:
            Dictionary with statistics
        """
        patterns = list(self.pattern_cache.values())
        
        if not patterns:
            return {
                "total_patterns": 0,
                "successful_fixes": 0,
                "failed_fixes": 0,
                "success_rate": 0.0,
                "categories": {},
                "repositories": {}
            }
        
        successful = sum(1 for p in patterns if p.fix_successful)
        
        categories = {}
        for p in patterns:
            categories[p.failure_category] = categories.get(p.failure_category, 0) + 1
        
        repositories = {}
        for p in patterns:
            repositories[p.repository] = repositories.get(p.repository, 0) + 1
        
        return {
            "total_patterns": len(patterns),
            "successful_fixes": successful,
            "failed_fixes": len(patterns) - successful,
            "success_rate": (successful / len(patterns)) * 100,
            "categories": categories,
            "repositories": repositories
        }
