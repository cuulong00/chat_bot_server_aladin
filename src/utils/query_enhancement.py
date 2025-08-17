"""
Query Enhancement Module for improving semantic similarity
Transforms colloquial Vietnamese queries into formal patterns
"""

def enhance_branch_queries(query: str) -> str:
    """
    Transform colloquial branch queries into formal patterns
    that better match the stored content.
    """
    
    query_lower = query.lower()
    
    # Brand name normalization
    brand_variations = [
        ('bên mình', 'Tian Long'),
        ('quán mình', 'Tian Long'),
        ('nhà hàng này', 'nhà hàng Tian Long'),
        ('ở đây', 'Tian Long'),
    ]
    
    enhanced_query = query
    for colloquial, formal in brand_variations:
        if colloquial in query_lower:
            enhanced_query = enhanced_query.replace(colloquial, formal)
            break
    
    # Branch query patterns
    branch_patterns = [
        # Colloquial → Formal
        ('có bao nhiêu chi nhánh', 'Tian Long có bao nhiêu chi nhánh'),
        ('có mấy chi nhánh', 'Tian Long có bao nhiêu chi nhánh'), 
        ('có bao nhiều cơ sở', 'Tian Long có bao nhiêu chi nhánh'),
        ('có mấy cơ sở', 'Tian Long có bao nhiêu chi nhánh'),
        ('ở đâu', 'chi nhánh Tian Long ở đâu'),
        ('địa chỉ', 'địa chỉ chi nhánh Tian Long'),
    ]
    
    for pattern, replacement in branch_patterns:
        if pattern in query_lower and 'Tian Long' not in enhanced_query:
            enhanced_query = replacement
            break
    
    return enhanced_query

# Test cases
if __name__ == "__main__":
    test_queries = [
        "cho anh hỏi bên mình có bao nhiêu chi nhánh",
        "bên mình có mấy chi nhánh", 
        "quán có bao nhiều cơ sở không",
        "nhà hàng này ở đâu",
        "cho em xin địa chỉ"
    ]
    
    print("🔄 QUERY ENHANCEMENT TEST:")
    print("=" * 60)
    
    for original in test_queries:
        enhanced = enhance_branch_queries(original)
        print(f"Original:  '{original}'")
        print(f"Enhanced:  '{enhanced}'")
        print("-" * 60)
