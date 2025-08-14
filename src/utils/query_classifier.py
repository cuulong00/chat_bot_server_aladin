"""
Query classification and retrieval optimization utilities.
This module provides a clean, maintainable way to handle query classification
without hardcoding keywords in prompts.
"""
"""
Query classification and retrieval optimization utilities.
This module provides a clean, maintainable way to handle query classification
without hardcoding keywords in prompts.
"""

from typing import Dict, List
from src.domain_configs.keyword_mappings import get_keywords_for_domain


class QueryClassifier:
    """
    Classifies user queries into categories and determines retrieval parameters.
    """

    def __init__(self, domain: str = "restaurant"):
        self.domain = domain
        self._load_keywords()

    def _load_keywords(self) -> None:
        """Load keywords for the current domain."""
        self.menu_keywords = get_keywords_for_domain(self.domain, "menu_keywords")
        self.location_keywords = get_keywords_for_domain(self.domain, "location_keywords")
        self.promotion_keywords = get_keywords_for_domain(self.domain, "promotion_keywords")
        self.faq_keywords = get_keywords_for_domain(self.domain, "faq_keywords")

        self.menu_signals = get_keywords_for_domain(self.domain, "menu_signals")
        self.location_signals = get_keywords_for_domain(self.domain, "location_signals")
        self.promotion_signals = get_keywords_for_domain(self.domain, "promotion_signals")

    def classify_query(self, query: str) -> Dict[str, any]:
        """
        Classify a query and return classification results.
        """
        if not query:
            return self._default_classification()

        query_lower = query.lower()

        # Check for different query types
        is_menu_query = any(keyword in query_lower for keyword in self.menu_keywords)
        is_location_query = any(keyword in query_lower for keyword in self.location_keywords)
        is_promotion_query = any(keyword in query_lower for keyword in self.promotion_keywords)
        is_faq_query = any(keyword in query_lower for keyword in self.faq_keywords)

        # Determine primary category
        primary_category = self._get_primary_category(
            is_menu_query, is_location_query, is_promotion_query, is_faq_query
        )

        # Determine retrieval limit
        retrieval_limit = 8 if is_faq_query else (
            12 if (is_menu_query or is_location_query or is_promotion_query) else 5
        )

        # Get relevant keywords for query expansion
        expansion_keywords = self._get_expansion_keywords(primary_category)

        return {
            "primary_category": primary_category,
            "is_menu_query": is_menu_query,
            "is_location_query": is_location_query,
            "is_promotion_query": is_promotion_query,
            "is_faq_query": is_faq_query,
            "retrieval_limit": retrieval_limit,
            "expansion_keywords": expansion_keywords,
            "signals": self._get_relevant_signals(primary_category),
        }

    def _get_primary_category(self, is_menu: bool, is_location: bool, is_promotion: bool, is_faq: bool) -> str:
        """Determine the primary category for the query."""
        if is_faq:
            return "faq"
        if is_menu:
            return "menu"
        elif is_location:
            return "location"
        elif is_promotion:
            return "promotion"
        else:
            return "general"

    def _get_expansion_keywords(self, category: str) -> List[str]:
        """Get keywords for query expansion based on category."""
        expansion_map = {
            "menu": ["THỰC ĐƠN", "Combo", "giá", "set menu", "Loại lẩu", "Tian Long"],
            "location": [
                "địa chỉ",
                "chi nhánh",
                "branch",
                "Hotline",
                "Hà Nội",
                "Hải Phòng",
                "TP. Hồ Chí Minh",
                "Times City",
                "Vincom",
                "Tian Long",
            ],
            "promotion": [
                "ưu đãi",
                "khuyến mãi",
                "giảm giá",
                "chương trình thành viên",
                "thẻ thành viên",
                "BẠC",
                "VÀNG",
                "KIM CƯƠNG",
                "sinh nhật",
                "Tian Long",
            ],
            "faq": ["hỏi đáp", "câu hỏi", "giải đáp", "Tian Long"],
            "general": ["Tian Long"],
        }
        return expansion_map.get(category, [])

    def _get_relevant_signals(self, category: str) -> List[str]:
        """Get relevant signals for document grading based on category."""
        if category == "menu":
            return self.menu_signals
        elif category == "location":
            return self.location_signals
        elif category == "promotion":
            return self.promotion_signals
        else:
            return []

    def _default_classification(self) -> Dict[str, any]:
        """Return default classification for empty/invalid queries."""
        return {
            "primary_category": "general",
            "is_menu_query": False,
            "is_location_query": False,
            "is_promotion_query": False,
            "retrieval_limit": 5,
            "expansion_keywords": [],
            "signals": [],
        }


def generate_dynamic_prompt_sections(classification: Dict[str, any]) -> Dict[str, str]:
    """
    Generate dynamic prompt sections based on query classification.
    This replaces hardcoded keyword lists in prompts.
    """
    category = classification["primary_category"]
    signals = classification["signals"]

    # Generate relevance boost section
    relevance_boost = ""
    if category == "menu":
        relevance_boost = (
            "RELEVANCE BOOST FOR MENU QUERIES: Documents containing menu signals are highly relevant. "
            f"Menu signals: {', '.join(signals[:10])}..."
        )
    elif category == "location":
        relevance_boost = (
            "RELEVANCE BOOST FOR LOCATION QUERIES: Documents containing location signals are highly relevant. "
            f"Location signals: {', '.join(signals[:10])}..."
        )
    elif category == "promotion":
        relevance_boost = (
            "RELEVANCE BOOST FOR PROMOTION QUERIES: Documents containing promotion signals are highly relevant. "
            f"Promotion signals: {', '.join(signals[:10])}..."
        )
    elif category == "faq":
        relevance_boost = "FAQ MODE: Prioritize concise, policy-level answers from the FAQ knowledge base."

    # Generate rewrite instructions
    expansion_keywords = classification["expansion_keywords"]
    rewrite_instruction = (
        "For this query type, consider appending these relevant keywords: "
        f"{', '.join(expansion_keywords[:8])}..."
    )

    return {
        "relevance_boost": relevance_boost,
        "rewrite_instruction": rewrite_instruction,
    }
