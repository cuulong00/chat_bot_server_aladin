"""
Domain-specific keyword mappings for query classification and retrieval optimization.
This configuration-based approach makes it easy to maintain and extend keywords
without modifying core prompt logic.
"""

from typing import Dict, List

# Restaurant domain keyword mappings
RESTAURANT_KEYWORDS = {
    "menu_keywords": [
        # Vietnamese
        "menu", "thực đơn", "món", "món gì", "giá", "combo", "set menu", 
        "bảng giá", "món đặc biệt", "món ăn", "đồ ăn",
        # English
        "food", "dish", "price", "meal", "cuisine"
    ],
    
    "location_keywords": [
        # Vietnamese
        "địa chỉ", "ở đâu", "chi nhánh", "cơ sở", "hotline", "liên hệ",
        "quận", "huyện", "thành phố", "tỉnh",
        # English  
        "address", "location", "branch", "contact", "where"
    ],
    
    "promotion_keywords": [
        # Vietnamese
        "ưu đãi", "khuyến mãi", "giảm giá", "chương trình", "thành viên",
        "giảm", "sale", "thẻ", "ưu tiên", "khuyến khích",
        # English
        "promotion", "discount", "offer", "membership", "program", "deal"
    ],
    
    "menu_signals": [
        "THỰC ĐƠN", "THỰC ĐƠN TIÊU BIỂU", "Combo", "Lẩu", 
        "đ", "k", "VND", "menu.tianlong.vn"
    ],
    
    "location_signals": [
        "Hà Nội", "Hải Phòng", "TP. Hồ Chí Minh", "Huế", "Times City", 
        "Vincom", "Lê Văn Sỹ", "Trần Thái Tông", "TIAN LONG"
    ],
    
    "promotion_signals": [
        "BẠC", "VÀNG", "KIM CƯƠNG", "%", "sinh nhật", "Ngày hội", 
        "thành viên", "chương trình", "giảm", "ưu đãi"
    ]
}

# Generic keyword mappings that can be extended for other domains
DOMAIN_KEYWORD_MAPPINGS: Dict[str, Dict[str, List[str]]] = {
    "restaurant": RESTAURANT_KEYWORDS,
    # Future domains can be added here:
    # "hotel": HOTEL_KEYWORDS,
    # "retail": RETAIL_KEYWORDS,
}

def get_keywords_for_domain(domain: str, category: str) -> List[str]:
    """
    Get keywords for a specific domain and category.
    
    Args:
        domain: Domain name (e.g., "restaurant")
        category: Keyword category (e.g., "menu_keywords", "promotion_keywords")
    
    Returns:
        List of keywords for the specified domain and category
    """
    return DOMAIN_KEYWORD_MAPPINGS.get(domain, {}).get(category, [])

def get_all_keywords_for_domain(domain: str) -> Dict[str, List[str]]:
    """
    Get all keyword mappings for a specific domain.
    
    Args:
        domain: Domain name (e.g., "restaurant")
    
    Returns:
        Dictionary containing all keyword categories for the domain
    """
    return DOMAIN_KEYWORD_MAPPINGS.get(domain, {})

def add_keywords_to_domain(domain: str, category: str, new_keywords: List[str]) -> None:
    """
    Dynamically add keywords to a domain category.
    
    Args:
        domain: Domain name
        category: Keyword category  
        new_keywords: List of new keywords to add
    """
    if domain not in DOMAIN_KEYWORD_MAPPINGS:
        DOMAIN_KEYWORD_MAPPINGS[domain] = {}
    
    if category not in DOMAIN_KEYWORD_MAPPINGS[domain]:
        DOMAIN_KEYWORD_MAPPINGS[domain][category] = []
    
    DOMAIN_KEYWORD_MAPPINGS[domain][category].extend(new_keywords)
