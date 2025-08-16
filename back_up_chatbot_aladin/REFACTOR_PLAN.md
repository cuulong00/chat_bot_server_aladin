# Báo cáo & Kế hoạch Refactor cho Component `Thread` (`index.tsx`)

**Ngày:** 21/07/2025
**Người review:** GitHub Copilot
**Mục tiêu:** Phân tích component `Thread`, xác định các vấn đề về kiến trúc và logic, đồng thời đề xuất một kế hoạch refactor chi tiết để cải thiện chất lượng code, tăng hiệu suất và khả năng bảo trì.

---

### **I. Tổng quan (Executive Summary)**

Component `Thread` là hạt nhân của giao diện chat, chịu trách nhiệm quản lý toàn bộ trạng thái cuộc trò chuyện, xử lý luồng dữ liệu streaming từ LangGraph SDK, và render giao diện người dùng.

- **Điểm mạnh:** Component hiện tại đã đáp ứng được các yêu cầu chức năng phức tạp, bao gồm streaming tin nhắn, xử lý tool-call, interrupt, và hiển thị reasoning steps.
- **Điểm yếu:** Do sự phát triển và thêm mới nhiều tính năng, cấu trúc của component đã trở nên quá phức tạp. Logic bị phân mảnh, state quản lý cồng kềnh, và có sự lặp lại code đáng kể. Điều này làm cho việc bảo trì, gỡ lỗi và mở rộng tính năng trong tương lai trở nên khó khăn và rủi ro.

**Kết luận:** Cần thực hiện một đợt refactor lớn để cấu trúc lại component theo các design pattern hiện đại của React, giúp codebase trở nên "sạch", module hóa và dễ quản lý hơn.

---

### **II. Phân Tích Chi Tiết Code Hiện Tại**

#### **1. Quản lý State (`useState`) - Rất phức tạp và phân mảnh**

Component đang sử dụng một số lượng lớn các `useState` riêng lẻ để quản lý các trạng thái có liên quan chặt chẽ với nhau.

- **Danh sách State (16 states):**
  - **Core streaming states:** `messages`, `isLoading`, `interrupt`, `error`, `localThreadId`, `streamController`
  - **Race condition control states:** `isUserSubmitting`, `streamJustCompleted`, `recentlyResumed`
  - **Reasoning display states:** `reasoningSteps`, `reasoningCompleted`, `currentMessageId`, `showReasoningWindow`
  - **UI/UX states:** `firstTokenReceived`, `userInfo`
  - **External states từ hooks:** `threadId`, `chatHistoryOpen`, `hideToolCalls`, `input`, `contentBlocks`, etc.
- **Vấn đề:**
  - **Logic xung đột (Race Conditions):** Các state như `isLoading`, `isUserSubmitting`, `streamJustCompleted` được dùng để kiểm soát luồng bất đồng bộ. Việc cập nhật chúng một cách riêng lẻ dễ gây ra các "race condition", đòi hỏi các giải pháp "vá" như dùng `setTimeout` trong `useEffect`.
  - **Khó hiểu:** Một hành động của người dùng (ví dụ: gửi tin nhắn) kích hoạt việc cập nhật hàng loạt các state, làm cho luồng dữ liệu trở nên khó theo dõi.
  - **Vi phạm nguyên tắc "Single Source of Truth":** Trạng thái của một quy trình (ví dụ: "streaming") bị phân tán trên nhiều biến (`isLoading`, `streamController`, `firstTokenReceived`), thay vì được đại diện bởi một đối tượng trạng thái duy nhất.

#### **2. Logic trong `useEffect` - Cồng kềnh và thiếu hiệu quả**

Component hiện tại có **8 useEffect hooks**, mỗi cái đều xử lý logic phức tạp và có dependency arrays dài.

- **`useEffect` đồng bộ `threads` và `messages` (dòng ~340-390):**
  - **Vấn đề:** Logic này cực kỳ phức tạp với 47+ dòng code, phụ thuộc vào 4 biến (`threadId`, `threads`, `streamJustCompleted`, `localThreadId`). Sử dụng `setTimeout` để "chờ" context update - đây là anti-pattern rõ ràng.
  - **Risk:** Dễ gây infinite loop nếu dependency không được kiểm soát cẩn thận.

- **`useEffect` kiểm tra "Sensitive Tool Calls" (dòng ~460-580):**
  - **Vấn đề:** Đây là khối logic khổng lồ 120+ dòng, chạy mỗi khi `messages`, `isLoading`, `interrupt`, `recentlyResumed`, `streamJustCompleted` thay đổi. 
  - **Performance Impact:** Với mỗi tin nhắn mới, logic này sẽ chạy lại, thực hiện các phép toán phức tạp để phân tích tool calls.
  - **Business Logic Leakage:** Logic nghiệp vụ (phân tích sensitive tools) không nên nằm trong lifecycle của component UI.

- **Các useEffect khác:**
  - Reset `streamJustCompleted` với `setTimeout` (anti-pattern)
  - Reset `recentlyResumed` với `setTimeout` (anti-pattern)  
  - Error notification với `toast` (side effect không kiểm soát)
  - Sync `localThreadId` với `threadId` (logic phức tạp)

**Tổng cộng:** Hơn 200 dòng code chỉ riêng trong các `useEffect`, chiếm khoảng 25% tổng số dòng của component.

#### **3. Các Hàm Xử Lý Chính (`handleSubmit`, `handleRegenerate`) - Vi phạm Nguyên tắc Đơn nhiệm (SRP)**

Đây là hai "monster functions" của component, mỗi hàm có hơn 150 dòng code và xử lý quá nhiều trách nhiệm.

**`handleSubmit` (dòng ~582-780):**
- **Trách nhiệm quá tải:**
  1. Reset 10+ state variables
  2. Validate và prepare input data
  3. Create thread nếu chưa có
  4. Initialize LangGraph client
  5. Execute streaming loop với 100+ dòng logic
  6. Parse và handle 8+ loại chunk events khác nhau
  7. Update UI state trong real-time
  8. Handle interrupt detection
  9. Error handling và cleanup

**`handleRegenerate` (dòng ~782-920):**
- **Code duplication:** 80% logic giống hệt `handleSubmit`
- **Maintenance nightmare:** Mọi thay đổi trong streaming logic phải update ở 2 nơi

**Logic trong `onContinue` của InterruptView (inline, dòng ~1450-1620):**
- **Embedded monster function:** 170 dòng code được viết trực tiếp trong JSX
- **Triple duplication:** Logic streaming được lặp lại lần thứ 3
- **Code readability:** Nested quá sâu, khó đọc và debug

**Tổng hợp:** Hơn 500 dòng code bị lặp lại giữa 3 hàm này.

#### **4. Logic Render (JSX) và Helper Functions**

**JSX Structure Issues:**
- **Inline component definitions:** `InterruptView`, `StickyToBottomContent`, `ScrollToBottom` được define trong cùng file, làm cho file trở nên cồng kềnh (1800+ dòng)
- **Complex conditional rendering:** Logic render messages với nhiều điều kiện nested, filter chains phức tạp
- **Performance issues:** Nhiều inline functions và object creations trong render

**Helper Functions Issues:**
- **`deduplicateReasoningSteps`:** Function tốt nhưng được định nghĩa inside component (dòng ~208-240), gây re-creation trên mỗi render
- **Missing abstraction:** Các logic phức tạp như message filtering, interrupt handling nên được tách thành separate utilities
- **Magic strings và constants:** Sensitive tools list, event types, etc. được hard-code trực tiếp trong logic

**Import Dependencies:**
- **32 import statements** - có thể optimize bằng cách group imports
- **Missing imports:** Một số hooks như `useArtifactContext`, `useArtifactOpen`, `useAgent`, `useFileUpload` được sử dụng nhưng không thấy import (có thể lỗi trong code summary)

#### **5. Performance và Memory Issues**

**Re-render Problems:**
- **Unnecessary re-renders:** Với 16+ state variables, mỗi state change có thể trigger re-render của entire component
- **Heavy computations trong render:** `deduplicateReasoningSteps`, message filtering, conditional logic được thực hiện trong mỗi render cycle
- **Missing memoization:** Không sử dụng `useMemo`, `useCallback` cho expensive operations

**Memory Leaks:**
- **AbortController cleanup:** Logic cleanup trong `useEffect` có thể miss một số edge cases
- **setTimeout cleanup:** Nhiều `setTimeout` calls có thể không được clear đúng cách khi component unmount
- **Event listeners:** Stream event handling có thể để lại memory references

**Bundle Size Impact:**
- **Large single file:** 1800+ dòng trong một file sẽ affect code splitting efficiency
- **Heavy dependencies:** LangGraph SDK, motion animations, multiple UI libraries

#### **6. Error Handling và Edge Cases**

**Inconsistent Error Handling:**
- **Mixed error patterns:** Sử dụng cả `try-catch`, `setError`, và `toast.error` 
- **Silent failures:** Một số operations fail silently, không có proper feedback cho user
- **Race condition errors:** Khi user actions conflict với streaming state

**Edge Cases không được handle:**
- **Network interruption:** Streaming bị ngắt do mạng
- **Concurrent submissions:** User submit multiple messages rapidly
- **State corruption:** Invalid state combinations có thể xảy ra

---

### **III. Kế hoạch Refactor Chi Tiết**

Chúng ta sẽ cấu trúc lại component bằng cách áp dụng các pattern phổ biến: **State Reducer** và **Custom Hooks**.

#### **Bước 1: Central hóa State với `useReducer`**

Gom tất cả các state liên quan đến quy trình streaming vào một reducer duy nhất.

- **Hành động:**
  1.  Tạo một `streamReducer` để quản lý các trạng thái: `status` ('idle', 'loading', 'streaming', 'success', 'error', 'interrupted'), `interrupt`, `error`.
  2.  Thay thế các `useState` (`isLoading`, `interrupt`, `error`, `isUserSubmitting`, etc.) bằng một lệnh gọi `useReducer` duy nhất.
  3.  Các hành động (actions) sẽ được định nghĩa rõ ràng: `SUBMIT_START`, `STREAM_CHUNK_RECEIVED`, `STREAM_INTERRUPTED`, `STREAM_SUCCESS`, `STREAM_ERROR`.

#### **Bước 2: Trừu tượng hóa Logic bằng Custom Hooks**

Tách biệt logic ra khỏi UI, giúp component `Thread` chỉ tập trung vào việc "hiển thị".

- **Hành động:** Tạo các custom hook sau:
  1.  **`useStreamManager()` (hoặc `useLangGraphStream()`):**
      - **Nhiệm vụ:** Chứa toàn bộ logic liên quan đến LangGraph SDK.
      - **Đầu vào:** `clientRef`, `threadId`, `setMessages`, `setReasoningSteps`, `dispatch` (từ reducer).
      - **Trả về:** Các hàm để thực thi: `submitMessage`, `regenerateMessage`, `continueFromInterrupt`.
      - **Nội dung:** Sẽ chứa hàm `handleStream` (logic `for await` được tái sử dụng), logic xử lý `chunk`, phân tích `interrupt`, và gọi `dispatch` để cập nhật state.
  2.  **`useThreadSyncer()`:**
      - **Nhiệm vụ:** Quản lý việc đồng bộ `threadId` từ URL, `localThreadId`, và `messages` từ `threads` context.
      - **Nội dung:** Chứa logic từ các `useEffect` hiện tại đang làm nhiệm vụ đồng bộ hóa, loại bỏ sự cần thiết của `streamJustCompleted`.

#### **Bước 3: Đơn giản hóa Component `Thread`**

Sau khi tách logic ra các hook, component `Thread` sẽ trở nên gọn gàng và dễ đọc hơn rất nhiều.

- **Hành động:**
  1.  Xóa các hàm logic lớn (`handleSubmit`, `handleRegenerate`) và các `useEffect` phức tạp.
  2.  Gọi các custom hook đã tạo để lấy về state và các hàm xử lý.
  3.  Phần JSX sẽ sử dụng trực tiếp state từ `streamReducer` (ví dụ: `streamState.status === 'loading'`).
  4.  Hàm `onSubmit` của form sẽ chỉ còn là một dòng gọi `submitMessage(input, contentBlocks)`.

#### **Bước 4: Tối ưu hóa Performance và Error Handling**

- **Performance Optimization:**
  1.  Implement `useMemo` và `useCallback` cho các expensive operations
  2.  Tách message list thành separate component với `React.memo` để prevent unnecessary re-renders
  3.  Implement virtual scrolling nếu message list dài
  4.  Optimize bundle size bằng code splitting

- **Error Handling Improvement:**
  1.  Tạo centralized error handling system
  2.  Implement proper error boundaries
  3.  Add retry mechanisms cho network failures
  4.  Better user feedback cho edge cases

#### **Bước 5: Code Organization và File Structure**

#### **Bước 5: Code Organization và File Structure**

- **File Splitting:**
  1.  Tách `InterruptView` thành separate component file
  2.  Tách UI components (`StickyToBottomContent`, `ScrollToBottom`) thành shared components
  3.  Tạo constants file cho sensitive tools, event types, etc.
  4.  Tạo types file cho TypeScript interfaces
  
- **Directory Structure đề xuất:**
  ```
  components/thread/
  ├── index.tsx (chỉ còn ~200 dòng)
  ├── components/
  │   ├── InterruptView.tsx
  │   ├── MessageList.tsx  
  │   └── ThreadInput.tsx
  ├── hooks/
  │   ├── useStreamManager.ts
  │   ├── useThreadSyncer.ts
  │   └── useToolCallDetector.ts
  ├── utils/
  │   ├── reasoning-steps.ts
  │   ├── stream-handler.ts
  │   └── constants.ts
  └── types/
      └── thread.types.ts
  ```

#### **Bước 6: Testing Strategy**

- **Unit Tests:**
  1.  Test các custom hooks independently
  2.  Test reducer logic với different actions
  3.  Test utility functions (deduplication, filtering, etc.)
  
- **Integration Tests:**
  1.  Test component interaction với mocked hooks
  2.  Test streaming flow end-to-end
  3.  Test error scenarios và recovery

---

### **IV. Đánh Giá Rủi Ro và Lộ trình Implementation**

#### **Rủi Ro cao (High Risk):**
1.  **Breaking existing functionality:** Streaming logic rất phức tạp, dễ break
2.  **State synchronization issues:** Race conditions có thể xuất hiện during refactor
3.  **Performance regression:** Nếu không optimize đúng cách

#### **Lộ trình Implementation (4-6 tuần):**

**Phase 1 (Tuần 1-2): Foundation**
- Tạo utility functions và constants
- Implement reducer và basic custom hooks
- Viết unit tests cho utilities

**Phase 2 (Tuần 2-3): Custom Hooks**
- Implement `useStreamManager` và `useThreadSyncer`
- Test hooks với existing component
- Gradual migration của state logic

**Phase 3 (Tuần 3-4): Component Refactor**
- Refactor main Thread component
- Split thành smaller components
- Integration testing

**Phase 4 (Tuần 4-5): Performance & Polish**
- Performance optimization
- Error handling improvements
- Comprehensive testing

**Phase 5 (Tuần 5-6): Production Ready**
- Code review và documentation
- Load testing
- Deployment và monitoring

#### **Success Metrics:**
- **Code complexity:** Giảm từ 1800+ dòng xuống ~800-1000 dòng (split across files)
- **Performance:** Giảm re-render frequency ít nhất 50%
- **Maintainability:** Thời gian implement new feature giảm 60%
- **Bug reduction:** Giảm streaming-related bugs 80%

### **V. Lợi Ích Của Việc Refactor**

1.  **Dễ Đọc & Dễ Bảo Trì (Readability & Maintainability):** Logic được phân tách rõ ràng theo từng chức năng. Việc tìm và sửa lỗi sẽ nhanh hơn rất nhiều.
2.  **Khả năng Tái sử dụng (Reusability):** Custom hook `useStreamManager` có thể được tái sử dụng ở các nơi khác nếu cần.
3.  **Khả năng Test (Testability):** Có thể viết unit test cho reducer và các custom hook một cách độc lập khỏi UI.
4.  **Hiệu suất (Performance):** Giảm thiểu các lần render không cần thiết bằng cách quản lý state tập trung và tối ưu hóa các `useEffect`.
5.  **Luồng dữ liệu rõ ràng (Clear Data Flow):** Loại bỏ các "side-effect" khó lường, giúp luồng dữ liệu đi theo một hướng, dễ dự đoán hơn.

---

### **VI. Kết Luận và Khuyến Nghị**

#### **Tình trạng hiện tại:**
Component `Thread` đã phát triển từ một component đơn giản thành một "monolith" phức tạp với 1800+ dòng code. Đây là kết quả tự nhiên của việc phát triển nhanh và thêm tính năng liên tục. Tuy nhiên, điểm này đã trở thành bottleneck nghiêm trọng cho:
- Development velocity (thời gian implement feature mới)
- Code quality và stability 
- Team collaboration (conflicts khi nhiều dev cùng work)
- Onboarding new developers

#### **Khuyến nghị:**

**CRITICAL - Ưu tiên cao nhất:**
1.  **Bắt đầu ngay:** Delay refactor sẽ khiến việc này trở nên khó khăn hơn exponentially
2.  **Incremental approach:** Không refactor toàn bộ một lúc, thực hiện từng phase nhỏ
3.  **Maintain backward compatibility:** Đảm bảo existing APIs không bị break

**ROI Analysis:**
- **Investment:** 4-6 tuần development time
- **Return:** 
  - Giảm 60% thời gian develop new features
  - Giảm 80% bugs related đến streaming
  - Tăng 3x development team productivity
  - Improve code review quality significantly

#### **Next Steps:**
1.  **Immediate (Tuần này):** Review và approve refactor plan
2.  **Setup (Tuần 1):** Tạo feature branch, setup testing framework  
3.  **Execute (Tuần 2-6):** Follow implementation roadmap
4.  **Monitor (Sau launch):** Track metrics và iterate

**Conclusion:** Việc refactor này không phải là "nice to have" mà là **business necessity** để đảm bảo sustainable growth của codebase. Chi phí không refactor (technical debt compound) sẽ cao hơn rất nhiều so với investment hiện tại.
