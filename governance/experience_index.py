"""Experience Index for fast retrieval of experiences.

This module builds in-memory indices from ExperienceMemory to enable
fast query operations without modifying the existing Phase 14 schema.
"""

import re
from collections import defaultdict
from typing import Dict, List, Optional, Set, Tuple
from datetime import datetime

from governance.experience_memory import ExperienceMemory


class ExperienceIndex:
    """In-memory index for fast experience retrieval.
    
    Builds indices on:
    - Tags: tag → experience_ids
    - Result: success/failure → experience_ids
    - Timestamp: sorted list for recency
    - Keywords: extracted from problem and analysis
    - Confidence: experiences sorted by confidence
    
    Usage:
        memory = ExperienceMemory()
        index = ExperienceIndex(memory)
        index.rebuild()
        
        results = index.get_by_tags(["command", "success"], limit=5)
        results = index.search_keywords("file not found", limit=3)
    """
    
    def __init__(self, memory: ExperienceMemory = None):
        """Initialize the index with an ExperienceMemory instance."""
        self.memory = memory or ExperienceMemory()
        
        # Primary indices
        self._tag_index: Dict[str, List[str]] = defaultdict(list)      # tag → experience_ids
        self._result_index: Dict[str, List[str]] = defaultdict(list)   # result → experience_ids
        self._project_index: Dict[str, List[str]] = defaultdict(list)  # project → experience_ids
        
        # Sorted indices
        self._timestamp_index: List[Tuple[str, str]] = []  # [(timestamp, id)] sorted desc
        self._confidence_index: List[Tuple[float, str]] = []  # [(confidence, id)] sorted desc
        
        # Text indices
        self._keyword_index: Dict[str, List[str]] = defaultdict(list)  # keyword → experience_ids
        self._experience_map: Dict[str, dict] = {}  # id → experience
        
        self._last_rebuild = None
        self._total_count = 0
        
        # Common stopwords for keyword extraction
        self._stopwords = {
            "a", "an", "the", "and", "or", "but", "for", "nor", "on",
            "at", "to", "by", "in", "of", "with", "without", "from",
            "is", "am", "are", "was", "were", "be", "been", "being",
            "has", "have", "had", "do", "does", "did", "will", "would",
            "shall", "should", "may", "might", "must", "can", "could"
        }
    
    def rebuild(self) -> int:
        """Rebuild all indices from the current ExperienceMemory.
        
        Returns:
            int: Number of experiences indexed.
        """
        experiences = [
            exp.to_dict() if hasattr(exp, "to_dict") else exp
            for exp in self.memory.get_all()
        ]
        
        # Clear all indices
        self._tag_index.clear()
        self._result_index.clear()
        self._project_index.clear()
        self._timestamp_index.clear()
        self._confidence_index.clear()
        self._keyword_index.clear()
        self._experience_map.clear()
        
        for exp in experiences:
            exp_id = exp.get("id")
            if not exp_id:
                continue
            
            self._experience_map[exp_id] = exp
            
            # Tag index
            tags = exp.get("tags", [])
            if isinstance(tags, list):
                for tag in tags:
                    self._tag_index[tag.lower()].append(exp_id)
            elif isinstance(tags, str):
                # Handle string tags (legacy)
                for tag in tags.split(","):
                    self._tag_index[tag.strip().lower()].append(exp_id)
            
            # Result index
            result = exp.get("result", "unknown")
            self._result_index[result.lower()].append(exp_id)
            
            # Project index
            project = exp.get("related_project")
            if project:
                self._project_index[project].append(exp_id)
            
            # Timestamp index
            timestamp = exp.get("timestamp", "")
            self._timestamp_index.append((timestamp, exp_id))
            
            # Confidence index
            confidence = exp.get("confidence", 0.0)
            self._confidence_index.append((confidence, exp_id))
            
            # Keyword index
            keywords = self._extract_keywords(exp)
            for keyword in keywords:
                self._keyword_index[keyword].append(exp_id)
        
        # Sort indices
        self._timestamp_index.sort(key=lambda x: x[0], reverse=True)
        self._confidence_index.sort(key=lambda x: x[0], reverse=True)
        
        self._total_count = len(experiences)
        self._last_rebuild = datetime.now()
        
        return self._total_count
    
    def _extract_keywords(self, experience: dict) -> Set[str]:
        """Extract keywords from problem and analysis fields."""
        text = ""
        text += experience.get("problem", "") + " "
        text += experience.get("analysis", "") + " "
        text += experience.get("solution", "")
        
        # Lowercase and split
        words = re.findall(r'\b[\w]+\b', text.lower(), flags=re.UNICODE)
        
        # Filter stopwords and short words
        keywords = set()
        for word in words:
            if len(word) < 3 or word in self._stopwords:
                continue
            keywords.add(word)
        
        return keywords
    
    def get_by_tags(self, tags: List[str], match_all: bool = False, limit: int = 10) -> List[dict]:
        """Get experiences matching tags.
        
        Args:
            tags: List of tags to match.
            match_all: If True, match all tags (AND). If False, match any tag (OR).
            limit: Maximum number of results.
        
        Returns:
            List of experience dicts.
        """
        if not tags:
            return []
        
        normalized_tags = [t.lower() for t in tags]
        ids: Set[str] = set()
        
        if match_all:
            # AND: start with first tag's IDs, intersect with others
            first_tag = normalized_tags[0]
            ids = set(self._tag_index.get(first_tag, []))
            for tag in normalized_tags[1:]:
                ids &= set(self._tag_index.get(tag, []))
                if not ids:
                    break
        else:
            # OR: union all tag IDs
            for tag in normalized_tags:
                ids.update(self._tag_index.get(tag, []))
        
        return self._get_experiences_by_ids(ids, limit)
    
    def get_by_result(self, result: str, limit: int = 10) -> List[dict]:
        """Get experiences by result (success/failure)."""
        result_lower = result.lower()
        ids = self._result_index.get(result_lower, [])
        return self._get_experiences_by_ids(ids, limit)
    
    def get_by_confidence(self, min_confidence: float = 0.7, limit: int = 10) -> List[dict]:
        """Get experiences with confidence >= threshold."""
        results = []
        for confidence, exp_id in self._confidence_index:
            if confidence >= min_confidence:
                exp = self._experience_map.get(exp_id)
                if exp:
                    results.append(exp)
            if len(results) >= limit:
                break
        return results
    
    def get_recent(self, limit: int = 10) -> List[dict]:
        """Get most recent experiences."""
        results = []
        for _, exp_id in self._timestamp_index[:limit]:
            exp = self._experience_map.get(exp_id)
            if exp:
                results.append(exp)
        return results
    
    def search_keywords_scored(
        self,
        query: str,
        limit: int = 10,
    ) -> List[Tuple[dict, int]]:
        """Search experiences and retain explicit keyword relevance scores."""
        keywords = set()
        for word in re.findall(
            r'\b[\w]+\b',
            query.lower(),
            flags=re.UNICODE,
        ):
            if len(word) >= 3 and word not in self._stopwords:
                keywords.add(word)

        if not keywords:
            return []

        scores: Dict[str, int] = defaultdict(int)

        for keyword in keywords:
            for exp_id in self._keyword_index.get(keyword, []):
                scores[exp_id] += 1

        sorted_ids = sorted(
            scores.keys(),
            key=lambda exp_id: scores[exp_id],
            reverse=True,
        )

        results = []

        for exp_id in sorted_ids[:limit]:
            exp = self._experience_map.get(exp_id)
            if exp:
                results.append((exp, scores[exp_id]))

        return results

    def search_keywords(self, query: str, limit: int = 10) -> List[dict]:
        """ for experiences with keyword matches.
        
        Args:
            query: Search query string.
            limit: Maximum number of results.
        
        Returns:
            List of experience dicts, ordered by relevance.
        """
        # Extract keywords from query
        keywords = set()
        for word in re.findall(r'\b[\w]+\b', query.lower(), flags=re.UNICODE):
            if len(word) >= 3 and word not in self._stopwords:
                keywords.add(word)
        
        if not keywords:
            return []
        
        # Score experiences by keyword matches
        scores: Dict[str, int] = defaultdict(int)
        for keyword in keywords:
            for exp_id in self._keyword_index.get(keyword, []):
                scores[exp_id] += 1
        
        # Sort by score (descending)
        sorted_ids = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)
        
        results = []
        for exp_id in sorted_ids[:limit]:
            exp = self._experience_map.get(exp_id)
            if exp:
                results.append(exp)
        
        return results
    
    def get_by_project(self, project: str, limit: int = 10) -> List[dict]:
        """Get experiences by project."""
        ids = self._project_index.get(project, [])
        return self._get_experiences_by_ids(ids, limit)
    
    def get_failures(self, limit: int = 10) -> List[dict]:
        """Get experiences with failure result, sorted by recency."""
        ids = self._result_index.get("failure", [])
        # Sort by recency (use timestamp index)
        sorted_ids = []
        for timestamp, exp_id in self._timestamp_index:
            if exp_id in ids:
                sorted_ids.append(exp_id)
        return self._get_experiences_by_ids(sorted_ids, limit)
    
    def get_success_patterns(self, limit: int = 10, min_confidence: float = 0.8) -> List[dict]:
        """Get successful experiences with high confidence, sorted by confidence."""
        ids = set(self._result_index.get("success", []))
        results = []
        for confidence, exp_id in self._confidence_index:
            if exp_id in ids and confidence >= min_confidence:
                exp = self._experience_map.get(exp_id)
                if exp:
                    results.append(exp)
            if len(results) >= limit:
                break
        return results
    
    def get_stats(self) -> dict:
        """Get statistics about the index."""
        return {
            "total_experiences": self._total_count,
            "unique_tags": len(self._tag_index),
            "unique_keywords": len(self._keyword_index),
            "last_rebuild": self._last_rebuild.isoformat() if self._last_rebuild else None,
            "tag_index_size": sum(len(v) for v in self._tag_index.values()),
        }
    
    def _get_experiences_by_ids(self, ids, limit: int) -> List[dict]:
        """Helper to convert IDs to experience dicts."""
        results = []
        count = 0
        for exp_id in ids:
            if count >= limit:
                break
            exp = self._experience_map.get(exp_id)
            if exp:
                results.append(exp)
                count += 1
        return results
    
    def get_experience_by_id(self, exp_id: str) -> Optional[dict]:
        """Get a single experience by ID from the cache."""
        return self._experience_map.get(exp_id)
