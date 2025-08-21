# Quy Tắc Viết Prompt Production - Best Practices

## 1. Cấu Trúc Prompt Chuẩn

### Template CLEAR Framework
```
C - Context (Ngữ cảnh)
L - Length (Độ dài mong muốn)
E - Examples (Ví dụ)
A - Audience (Đối tượng)
R - Role (Vai trò)
```

### Cấu trúc cơ bản:
```
[ROLE] + [TASK] + [CONTEXT] + [FORMAT] + [EXAMPLES] + [CONSTRAINTS]
```

## 2. Nguyên Tắc Cốt Lõi

### 2.1 Clarity (Rõ ràng)
- Sử dụng ngôn ngữ đơn giản, cụ thể
- Tránh thuật ngữ mơ hồ hoặc đa nghĩa
- Chia nhỏ các yêu cầu phức tạp

### 2.2 Specificity (Cụ thể)
- Đưa ra yêu cầu chi tiết, không chung chung
- Xác định rõ input/output format
- Bao gồm constraints và limitations

### 2.3 Context (Ngữ cảnh)
- Cung cấp background information đầy đủ
- Giải thích mục đích và use case
- Nêu rõ domain/industry nếu cần

## 3. Cấu Trúc Chi Tiết

### 3.1 Role Definition (Định nghĩa vai trò)
```
Bạn là một [CHUYÊN GIA/CHUYÊN VIÊN] với [X năm kinh nghiệm] trong lĩnh vực [DOMAIN].
Bạn có chuyên môn sâu về [SPECIFIC SKILLS].
```

### 3.2 Task Description (Mô tả nhiệm vụ)
```
Nhiệm vụ của bạn là [ĐỘNG TỪ CỤ THỂ] + [ĐỐI TƯỢNG] + [MỤC ĐÍCH]

Ví dụ:
- "Phân tích và đánh giá tính khả thi của dự án để đưa ra khuyến nghị"
- "Tạo ra một kế hoạch marketing chi tiết cho sản phẩm mới"
```

### 3.3 Context và Background
```
Tình huống:
- [MÔ TẢ TÌNH HUỐNG HIỆN TẠI]
- [CÁC YẾU TỐ LIÊN QUAN]
- [CONSTRAINTS VÀ LIMITATIONS]

Mục tiêu:
- [MỤC TIÊU CHÍNH]
- [KẾT QUẢ MONG ĐỢI]
```

### 3.4 Format Specification
```
Định dạng output:
1. [PHẦN 1]: [MÔ TẢ]
2. [PHẦN 2]: [MÔ TẢ]
3. [PHẦN 3]: [MÔ TẢ]

Độ dài: [SỐ TỪ/CÂU/ĐOẠN VĂN]
Tone: [CHUYÊN NGHIỆP/THÂN THIỆN/FORMAL]
```

## 4. Kỹ Thuật Nâng Cao

### 4.1 Few-shot Learning
Cung cấp 2-5 ví dụ input-output:

```
Ví dụ 1:
Input: [EXAMPLE INPUT 1]
Output: [EXPECTED OUTPUT 1]

Ví dụ 2:
Input: [EXAMPLE INPUT 2]
Output: [EXPECTED OUTPUT 2]

Bây giờ hãy áp dụng với:
Input: [ACTUAL INPUT]
```

### 4.2 Chain of Thought (CoT)
```
Hãy giải quyết bài toán này theo từng bước:

Bước 1: Phân tích vấn đề
Bước 2: Xác định các yếu tố quan trọng
Bước 3: Áp dụng phương pháp/công thức
Bước 4: Kiểm tra và kết luận

Giải thích logic tại mỗi bước.
```

### 4.3 Self-Consistency
```
Hãy giải quyết bài toán này bằng 3 cách khác nhau:

Phương pháp 1: [MÔ TẢ]
Phương pháp 2: [MÔ TẢ]
Phương pháp 3: [MÔ TẢ]

So sánh kết quả và đưa ra kết luận cuối cùng.
```

### 4.4 Tree of Thoughts
```
Hãy khám phá vấn đề này theo nhiều hướng:

Hướng suy nghĩ A: [MÔ TẢ]
├── Khả năng 1: [MÔ TẢ]
├── Khả năng 2: [MÔ TẢ]
└── Đánh giá: [MÔ TẢ]

Hướng suy nghĩ B: [MÔ TẢ]
├── Khả năng 1: [MÔ TẢ]
├── Khả năng 2: [MÔ TẢ]
└── Đánh giá: [MÔ TẢ]

Kết luận tổng hợp từ tất cả các hướng.
```

## 5. Constraints và Guardrails

### 5.1 Output Constraints
```
Giới hạn:
- Độ dài: Tối đa [X] từ
- Format: Sử dụng bullet points/numbering
- Ngôn ngữ: Tiếng Việt, tone chuyên nghiệp
- Không được: [LIỆT KÊ NHỮNG GÌ KHÔNG ĐƯỢC LÀM]
```

### 5.2 Quality Gates
```
Kiểm tra chất lượng:
□ Có trả lời đúng câu hỏi không?
□ Thông tin có chính xác không?
□ Format có đúng yêu cầu không?
□ Độ dài có phù hợp không?
□ Tone có phù hợp với audience không?
```

### 5.3 Error Handling
```
Nếu không đủ thông tin:
- Hãy chỉ rõ thiếu thông tin gì
- Đưa ra các assumption hợp lý
- Yêu cầu bổ sung thông tin cần thiết

Nếu vấn đề nằm ngoài khả năng:
- Giải thích rõ limitation
- Đề xuất hướng giải quyết thay thế
```

## 6. Templates Chuẩn Production

### 6.1 Analysis Template
```
# PHÂN TÍCH [TÊN CHỦ ĐỀ]

## Ngữ cảnh
Bạn là senior analyst với 10+ năm kinh nghiệm trong [DOMAIN]. Bạn được yêu cầu phân tích [SUBJECT] để hỗ trợ [DECISION/GOAL].

## Nhiệm vụ
Phân tích chi tiết [SUBJECT] dựa trên:
- [TIÊU CHÍ 1]
- [TIÊU CHÍ 2]  
- [TIÊU CHÍ 3]

## Input Data
[CUNG CẤP DỮ LIỆU CẦN PHÂN TÍCH]

## Output Format
1. **Executive Summary** (100 từ)
2. **Detailed Analysis** (500 từ)
   - Điểm mạnh
   - Điểm yếu  
   - Cơ hội
   - Thách thức
3. **Recommendations** (200 từ)
4. **Next Steps** (100 từ)

## Constraints
- Sử dụng data được cung cấp
- Đưa ra ít nhất 3 recommendations cụ thể
- Bao gồm timeline cho next steps
```

### 6.2 Content Generation Template
```
# TẠO NỘI DUNG [LOẠI NỘI DUNG]

## Role
Bạn là content creator chuyên nghiệp với expertise trong [DOMAIN].

## Task
Tạo [LOẠI NỘI DUNG] cho [TARGET AUDIENCE] với mục đích [PURPOSE].

## Context
- Brand: [BRAND NAME]
- Industry: [INDUSTRY]
- Target audience: [DEMOGRAPHICS + PSYCHOGRAPHICS]
- Goal: [SPECIFIC GOAL]
- Key message: [MAIN MESSAGE]

## Requirements
- Tone: [TONE DESCRIPTION]
- Length: [WORD COUNT]
- Format: [SPECIFIC FORMAT]
- Include: [MUST-HAVE ELEMENTS]
- Avoid: [THINGS TO AVOID]

## Success Criteria
Nội dung được coi là thành công khi:
- [CRITERIA 1]
- [CRITERIA 2]
- [CRITERIA 3]
```

### 6.3 Problem Solving Template
```
# GIẢI QUYẾT VẤN ĐỀ

## Setup
Bạn là problem-solving expert với khả năng phân tích và đưa ra solution cho các vấn đề phức tạp.

## Problem Statement
[MÔ TẢ CHI TIẾT VẤN ĐỀ]

## Context & Constraints
- Current situation: [MÔ TẢ]
- Available resources: [MÔ TẢ]
- Timeline: [MÔ TẢ]
- Budget: [MÔ TẢ]
- Stakeholders: [MÔ TẢ]

## Solution Framework
Sử dụng phương pháp 5W1H để phân tích:
- What: Vấn đề cụ thể là gì?
- Why: Tại sao vấn đề này xảy ra?
- Who: Ai bị ảnh hưởng?
- When: Khi nào cần giải quyết?
- Where: Ở đâu xảy ra vấn đề?
- How: Làm thế nào để giải quyết?

## Output Format
1. **Problem Analysis** (300 từ)
2. **Root Cause Analysis** (200 từ)
3. **Solution Options** (400 từ)
   - Option 1: [Chi tiết + Pros/Cons]
   - Option 2: [Chi tiết + Pros/Cons]
   - Option 3: [Chi tiết + Pros/Cons]
4. **Recommended Solution** (200 từ)
5. **Implementation Plan** (300 từ)
6. **Risk Mitigation** (200 từ)
```

## 7. Validation và Testing

### 7.1 Prompt Testing Checklist
```
□ Clarity: Prompt có dễ hiểu không?
□ Completeness: Có đủ thông tin để AI hiểu không?
□ Consistency: Output có nhất quán không?
□ Correctness: Kết quả có chính xác không?
□ Constraints: AI có tuân thủ giới hạn không?
```

### 7.2 A/B Testing for Prompts
```
Version A: [PROMPT VARIATION 1]
Version B: [PROMPT VARIATION 2]

Test metrics:
- Response quality
- Task completion rate
- Response time
- User satisfaction
```

## 8. Error Prevention

### 8.1 Common Prompt Mistakes
- ❌ Yêu cầu mơ hồ: "Viết một cái gì đó hay"
- ✅ Yêu cầu cụ thể: "Viết bài blog 800 từ về AI cho doanh nghiệp SME"

- ❌ Thiếu context: "Phân tích data này"
- ✅ Có context: "Phân tích dữ liệu bán hàng Q3 để đề xuất chiến lược Q4"

### 8.2 Best Practices Checklist
```
Before sending prompt:
□ Đã define role rõ ràng?
□ Đã cung cấp đủ context?
□ Đã specify output format?
□ Đã include examples nếu cần?
□ Đã set constraints phù hợp?
□ Đã review lỗi chính tả/ngữ pháp?
```

## 9. Advanced Techniques

### 9.1 Recursive Prompting
```
Step 1: [INITIAL ANALYSIS]
Step 2: "Dựa trên kết quả step 1, hãy [DEEPER ANALYSIS]"
Step 3: "Dựa trên step 1 và 2, hãy [SYNTHESIS/CONCLUSION]"
```

### 9.2 Multi-Agent Approach
```
Agent 1 (Analyst): Phân tích data và tìm insights
Agent 2 (Critic): Review và challenge các insights
Agent 3 (Synthesizer): Tổng hợp và đưa ra conclusion
```

### 9.3 Constitutional AI Approach
```
Principle 1: Luôn đưa ra thông tin chính xác
Principle 2: Thừa nhận khi không biết
Principle 3: Đề xuất alternative approaches
Principle 4: Respect user's constraints
```

## 10. Industry-Specific Templates

### 10.1 Marketing Prompt
```
Bạn là marketing strategist với 15 năm kinh nghiệm trong [INDUSTRY].
Tạo chiến lược marketing cho [PRODUCT] targeting [AUDIENCE].

Context:
- Budget: [AMOUNT]
- Timeline: [TIMEFRAME]
- Goals: [SPECIFIC GOALS]
- Competitors: [COMPETITOR INFO]

Deliverable:
1. Market analysis (200 từ)
2. Strategy recommendations (400 từ)  
3. Tactical execution plan (300 từ)
4. KPI framework (100 từ)
```

### 10.2 Technical Documentation
```
Bạn là technical writer với expertise trong [TECHNOLOGY].
Tạo documentation cho [SYSTEM/FEATURE] dành cho [AUDIENCE LEVEL].

Requirements:
- Clear step-by-step instructions
- Include code examples
- Add troubleshooting section
- Use consistent terminology

Format:
1. Overview
2. Prerequisites  
3. Step-by-step guide
4. Examples
5. Troubleshooting
6. FAQ
```

### 10.3 Financial Analysis
```
Bạn là financial analyst với CFA certification và 12 năm kinh nghiệm.
Phân tích tài chính của [COMPANY] để đưa ra investment recommendation.

Data provided:
- Financial statements (3 years)
- Industry benchmarks
- Market conditions

Analysis framework:
- Liquidity analysis
- Profitability analysis  
- Leverage analysis
- Efficiency analysis
- Valuation analysis

Output: Investment thesis với recommendation (BUY/HOLD/SELL)
```

## Tổng Kết

Prompt engineering là một skill quan trọng trong thời đại AI. Bằng cách áp dụng các best practices trên, bạn có thể tạo ra những prompts chất lượng cao, đáng tin cậy và phù hợp với production environment.

**Key Takeaways:**
- Luôn cung cấp context và role rõ ràng
- Sử dụng examples để guide AI
- Specify output format chi tiết
- Test và iterate prompts thường xuyên
- Apply constraints phù hợp với use case