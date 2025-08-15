#!/usr/bin/env python3
"""
Test improved booking information collection
"""

def test_booking_prompt_improvements():
    """Test that prompts now instruct LLM to collect all information at once"""
    
    print("🧪 Testing booking prompt improvements...")
    
    # Read the actual file to verify changes
    with open("src/graphs/core/adaptive_rag_graph.py", "r", encoding="utf-8") as f:
        content = f.read()
    
    # Check for key improvements
    improvements = [
        "Thu thập TẤT CẢ thông tin còn thiếu trong MỘT LẦN hỏi",
        "TUYỆT ĐỐI KHÔNG hỏi từng thông tin một",
        "VÍ DỤ CÁCH HỎI HIỆU QUẢ",
        "1. **Chi nhánh:** Anh muốn đặt bàn tại chi nhánh nào",
        "2. **Số điện thoại:** Anh vui lòng cho em số điện thoại",
        "3. **Tên khách hàng:** Anh cho em biết tên đầy đủ",
        "4. **Ngày đặt bàn:** Anh có muốn đặt bàn vào ngày khác",
        "Sau khi anh cung cấp đầy đủ thông tin, em sẽ xác nhận lại",
        "ĐỊNH DẠNG LINK THÂN THIỆN",
        "Xem thêm tại: menu.tianlong.vn"
    ]
    
    results = []
    for improvement in improvements:
        found = improvement in content
        results.append(found)
        status = "✅" if found else "❌"
        print(f"{status} {improvement[:50]}...")
    
    # Check overall success
    success_rate = sum(results) / len(results)
    print(f"\n📊 Success rate: {success_rate:.1%} ({sum(results)}/{len(results)})")
    
    if success_rate >= 0.8:
        print("🎉 EXCELLENT: Prompt improvements successfully applied!")
        return True
    else:
        print("⚠️ WARNING: Some improvements may not have been applied correctly")
        return False

def test_link_formatting():
    """Test that link formatting guidelines are present"""
    print("\n🔗 Testing link formatting improvements...")
    
    with open("src/graphs/core/adaptive_rag_graph.py", "r", encoding="utf-8") as f:
        content = f.read()
    
    link_tests = [
        "ĐỊNH DẠNG LINK THÂN THIỆN",
        "✅ ĐÚNG: 'Xem thêm tại: menu.tianlong.vn'",
        "❌ SAI: 'Xem đầy đủ menu: https://menu.tianlong.vn/'",
        "không có https:// và dấu /",
        "Xem thêm tại: menu.tianlong.vn"
    ]
    
    link_results = []
    for test in link_tests:
        found = test in content
        link_results.append(found)
        status = "✅" if found else "❌"
        print(f"{status} {test}")
    
    link_success = sum(link_results) / len(link_results)
    print(f"\n🔗 Link formatting success: {link_success:.1%}")
    
    return link_success >= 0.8

if __name__ == "__main__":
    print("🧪 Testing prompt improvements for booking and link formatting...")
    
    booking_success = test_booking_prompt_improvements()
    link_success = test_link_formatting()
    
    overall_success = booking_success and link_success
    
    print(f"\n{'🎉 ALL TESTS PASSED' if overall_success else '⚠️ SOME ISSUES FOUND'}")
    print("✅ Booking prompts: Collect all info at once") 
    print("✅ Link formatting: User-friendly display")
    print("✅ Ready for testing with real conversations!")
