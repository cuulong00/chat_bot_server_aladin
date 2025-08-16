import os
import sys
import argparse
from typing import List

from dotenv import load_dotenv

try:
    from src.database.qdrant_store import QdrantStore
    from src.domain_configs.domain_configs import MARKETING_DOMAIN
    from src.utils.query_classifier import QueryClassifier
except Exception as e:
    print(f"❌ Import lỗi: {e}")
    sys.exit(1)


def uniq(seq: List[str]) -> List[str]:
    seen = set()
    out = []
    for x in seq:
        if x and x not in seen:
            out.append(x)
            seen.add(x)
    return out


def detect_branch_keywords(text: str) -> bool:
    t = (text or "").lower()
    return any(k in t for k in ["chi nhánh", "branch", "địa chỉ", "cơ sở", "hà nội", "tp. hồ chí minh", "sài gòn", "hải phòng"]) 


def detect_delivery_keywords(text: str) -> bool:
    """Detect delivery/shipping related keywords in text"""
    t = (text or "").lower()
    return any(k in t for k in ["ship", "mang về", "giao hàng", "delivery", "đặt ship", "ship mang về", "thu thập thông tin đặt ship", "hoàn tất đặt ship"]) 


def main():
    load_dotenv()

    parser = argparse.ArgumentParser(description="Debug similarity search for a query across namespaces")
    parser.add_argument("--query", default="ship mang về", help="Câu hỏi cần kiểm tra")
    parser.add_argument("--limit", type=int, default=12, help="Số lượng kết quả mỗi namespace")
    parser.add_argument(
        "--namespaces",
        default=None,
        help="Danh sách namespace, phân tách bằng dấu phẩy. Nếu bỏ trống sẽ dùng cấu hình DOMAIN/env",
    )
    parser.add_argument(
        "--collection",
        default=None,
        help="Tên collection Qdrant. Mặc định dùng từ MARKETING_DOMAIN",
    )
    args = parser.parse_args()

    google_key = os.getenv("GOOGLE_API_KEY")
    if not google_key:
        print("❌ Thiếu GOOGLE_API_KEY trong môi trường. Vui lòng set biến môi trường trước khi chạy.")
        sys.exit(2)

    # Domain-driven defaults
    collection_name = args.collection or MARKETING_DOMAIN.get("collection_name", "aladin_maketing")
    embedding_model = MARKETING_DOMAIN.get("embedding_model", "models/text-embedding-004")
    output_dim = MARKETING_DOMAIN.get("output_dimensionality_query", 768)

    # Namespace candidates
    if args.namespaces:
        candidates = [s.strip() for s in args.namespaces.split(",") if s.strip()]
    else:
        default_ns = MARKETING_DOMAIN.get("namespace")
        faq_ns = os.getenv("FAQ_NAMESPACE") or MARKETING_DOMAIN.get("faq_namespace")
        location_ns = os.getenv("LOCATION_NAMESPACE") or MARKETING_DOMAIN.get("location_namespace")
        # Add a few common guesses
        candidates = [location_ns, faq_ns, default_ns, "location", "faq", "maketing"]

    namespaces = uniq(candidates)
    if not namespaces:
        print("❌ Không có namespace nào để kiểm tra.")
        sys.exit(3)

    print("🔧 Cấu hình:")
    print(f"  • Collection: {collection_name}")
    print(f"  • Namespaces: {namespaces}")
    print(f"  • Query: {args.query}")
    print("")

    # Build store
    store = QdrantStore(
        embedding_model=embedding_model,
        output_dimensionality_query=output_dim,
        collection_name=collection_name,
    )

    # Classification-based expansion
    classifier = QueryClassifier(domain="restaurant")
    clf = classifier.classify_query(args.query)
    expansion = clf.get("expansion_keywords", [])
    expanded_query = args.query + (" " + " ".join(expansion) if expansion else "")

    print("🔎 Phân loại truy vấn:")
    print(f"  • primary_category: {clf.get('primary_category')}")
    print(f"  • signals: {clf.get('signals')[:10]}")
    print(f"  • expansion_keywords: {expansion}")
    print("")

    def run_once(label: str, query: str):
        print(f"===== {label} =====")
        for ns in namespaces:
            try:
                results = store.search(namespace=ns, query=query, limit=args.limit)
            except Exception as e:
                print(f"  ⚠️ Namespace '{ns}': lỗi khi search: {e}")
                continue

            print(f"  📂 Namespace '{ns}': {len(results)} kết quả")
            if not results:
                continue
            
            delivery_hits = 0
            branch_hits = 0
            
            for i, item in enumerate(results, 1):
                key, payload, score = item
                content = payload.get("content", "") if isinstance(payload, dict) else str(payload)
                snippet = (content[:200] + "...") if len(content) > 200 else content
                
                has_delivery = detect_delivery_keywords(content)
                has_branch = detect_branch_keywords(content)
                
                if has_delivery:
                    delivery_hits += 1
                if has_branch:
                    branch_hits += 1
                
                markers = []
                if has_delivery:
                    markers.append("🚚")  # delivery truck emoji
                if has_branch:
                    markers.append("✅")  # branch marker
                    
                marker_str = " ".join(markers) if markers else "  "
                
                print(f"    {i:02d}. score={score:.4f} id={key} {marker_str} :: {snippet}")
            
            print(f"  ➜ Văn bản có tín hiệu ship/giao hàng: {delivery_hits}/{len(results)}")
            print(f"  ➜ Văn bản có tín hiệu chi nhánh/địa chỉ: {branch_hits}/{len(results)}\n")

    # Run baseline and expanded
    run_once("KẾT QUẢ: Query gốc", args.query)
    if expanded_query != args.query:
        print("")
        run_once("KẾT QUẢ: Query mở rộng (append expansion keywords)", expanded_query)

    print("Hoàn tất. Dựa trên tỷ lệ kết quả có tín hiệu ship/delivery và chi nhánh/địa chỉ, hãy chỉnh namespace hoặc bổ sung dữ liệu.")


if __name__ == "__main__":
    main()
