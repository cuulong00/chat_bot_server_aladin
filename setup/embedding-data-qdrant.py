"""Embedding ingestion pipeline for Qdrant.

Improvements in this patch:
 - Robust project root resolution so `src` module can be imported even when script executed from any cwd
 - Path handling via pathlib (removes Windows backslash escape issues & SyntaxWarning)
 - CLI arguments (override files, urls, collection, model, namespace, chunk params)
 - Safety checks for required environment variables (e.g. GOOGLE_API_KEY when using Gemini)
 - Optional automatic USER_AGENT default to reduce warnings
 - Graceful handling when input file missing
"""

from qdrant_client.http.models import VectorParams, Distance

import sys
from pathlib import Path

# --- Project root & import path bootstrap ---
THIS_FILE = Path(__file__).resolve()
PROJECT_ROOT = THIS_FILE.parent.parent  # repo root
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

def get_vector_size(model_key: str) -> int:
    if model_key == "gemini-embedding-exp-03-07":
        return 3072
    # text-embedding-004 và các model Google mới
    return 768


import os
from dotenv import load_dotenv
import logging
from typing import List, Optional, Dict, Any, Callable
import argparse
import json
import google.generativeai as genai
from langchain_community.document_loaders import (
    WebBaseLoader,
    PyPDFLoader,
    TextLoader,
    Docx2txtLoader,
)
from langchain_core.documents import Document
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
try:
    from src.database.qdrant_store import QdrantStore
except ModuleNotFoundError as e:  # Fallback informative error
    raise ModuleNotFoundError(
        "Cannot import 'src'. Ensure you run inside project root or PYTHONPATH includes it. "
        f"PROJECT_ROOT attempted: {PROJECT_ROOT}"
    ) from e

logger = logging.getLogger("embedding_pipeline")

# Embedding model registry: add new models here
EMBEDDING_MODELS: Dict[str, Callable[[], Any]] = {
    # Google official embedding model name: text-embedding-004 (LangChain)
    "google-text-embedding-004": lambda: GoogleGenerativeAIEmbeddings(
        model="models/text-embedding-004"
    ),
    # Direct Gemini API (google.generativeai)
    "gemini-embedding-exp-03-07": lambda: None,  # handled specially below
    # "openai": lambda: OpenAIEmbeddings(...),
    # "nomic": lambda: NomicEmbeddings(...),
}

# --- JSON loader for menu combos ---
def _load_menu_json(file_path: str) -> List[Document]:
    """Load JSON file with menu combos format and convert to documents."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        documents = []
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict) and "embedding_text" in item:
                    # Sử dụng embedding_text làm nội dung chính
                    content = item["embedding_text"]
                    
                    # Tạo metadata từ các field khác
                    metadata = {
                        "source": file_path,
                        "id": item.get("id", ""),
                        "title": item.get("title", ""),
                        "price_vnd": item.get("price_vnd", 0),
                        "currency": item.get("currency", "VND"),
                        "guests": item.get("guests", 1),
                        "image_url": item.get("image_url", ""),
                        "type": "menu_combo"
                    }
                    
                    # Thêm thông tin giảm giá nếu có
                    if item.get("discount_info"):
                        metadata["discount_info"] = item["discount_info"]
                        metadata["original_price_vnd"] = item.get("original_price_vnd", 0)
                    
                    documents.append(Document(page_content=content, metadata=metadata))
        
        logger.info(f"Loaded {len(documents)} menu combo documents from {file_path}")
        return documents
        
    except Exception as e:
        logger.error(f"Failed to load JSON file {file_path}: {e}")
        return []


# --- Robust text loader with encoding fallbacks ---
def _safe_load_text(file_path: str) -> List[Document]:
    """Load a text file trying multiple encodings to avoid UnicodeDecodeError.

    Strategy:
    1. Optional explicit encoding via env TEXT_FILE_ENCODING (comma separated list)
    2. Default candidates: utf-8, utf-8-sig, cp1252, latin-1
    3. On final failure: raise RuntimeError summarizing attempts

    latin-1 is *lossy* but guarantees a decode; we place it last.
    """
    candidates_env = os.getenv("TEXT_FILE_ENCODING")
    if candidates_env:
        candidates = [c.strip() for c in candidates_env.split(",") if c.strip()]
    else:
        candidates = ["utf-8", "utf-8-sig", "cp1252", "latin-1"]
    errors_mode = os.getenv("TEXT_FILE_ENCODING_ERRORS", "strict")
    failures: List[str] = []
    for enc in candidates:
        try:
            with open(file_path, "r", encoding=enc, errors=errors_mode) as rf:
                text = rf.read()
            # Attach chosen encoding into metadata for traceability
            return [Document(page_content=text, metadata={"source": file_path, "encoding": enc})]
        except Exception as e:  # noqa: BLE001 keep broad to collect all attempts
            failures.append(f"{enc}: {e}")
            continue
    raise RuntimeError(
        f"Failed to decode text file '{file_path}' with encodings: {candidates}.\nAttempts: "
        + " | ".join(failures)
    )


# Loader registry for extensibility (order is not relevant except .txt uses robust loader)
LOADER_REGISTRY: Dict[str, Callable[[str], Any]] = {
    ".pdf": lambda f: PyPDFLoader(f).load(),
    ".docx": lambda f: Docx2txtLoader(f).load(),
    ".txt": _safe_load_text,
    ".json": _load_menu_json,
}


def load_documents(
    files: List[str],
    urls: Optional[List[str]] = None,
    extra_metadata: Optional[Dict[str, Any]] = None,
) -> List[Any]:
    """
    Load documents from files and URLs. Attach extra_metadata to each doc.
    """
    docs = []
    urls = urls or []
    for file in files:
        ext = os.path.splitext(file)[-1].lower()
        loader = LOADER_REGISTRY.get(ext)
        if loader:
            loaded = loader(file)
            if extra_metadata:
                for doc in loaded:
                    doc.metadata.update(extra_metadata)
            docs.extend(loaded)
        else:
            logger.warning(f"Unsupported file: {file}")
    for url in urls:
        loaded = WebBaseLoader(url).load()
        if extra_metadata:
            for doc in loaded:
                doc.metadata.update(extra_metadata)
        docs.extend(loaded)
    return docs


def get_embedding_model(model_name: Optional[str] = None):
    """
    Lấy model embedding từ tên thân thiện hoặc biến môi trường. Tự động map các alias phổ biến về registry key.
    Nếu là gemini-embedding-exp-03-07 thì trả về None (dùng API gốc Google).
    """
    load_dotenv()
    model_env = os.getenv("EMBEDDING_MODEL")
    model_name = model_name or model_env or "google-gemini"
    # Map các alias phổ biến về registry key
    model_aliases = {
        "google": "google-text-embedding-004",
        "text-embedding-004": "google-text-embedding-004",
        "models/text-embedding-004": "google-text-embedding-004",
        "google-text-embedding-004": "google-text-embedding-004",
        "gemini-embedding-exp-03-07": "gemini-embedding-exp-03-07",
    }
    model_key = model_aliases.get(model_name.lower(), model_name)
    if model_key not in EMBEDDING_MODELS:
        raise ValueError(
            f"Model '{model_name}' not supported. Available: {list(EMBEDDING_MODELS.keys())}. Bạn có thể dùng: {list(model_aliases.keys())}"
        )
    return model_key, EMBEDDING_MODELS[model_key]()


def embed_and_store(
    docs: List[Any],
    qdrant_store: QdrantStore,
    collection_name: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    chunk_size: int = 800,
    chunk_overlap: int = 200,
    model_name: Optional[str] = None,
    namespace: Optional[str] = None,
):
    """
    Embed documents and store in Qdrant. Metadata (domain, department, user_id, ...) is attached to each chunk.
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size, chunk_overlap=chunk_overlap
    )
    logger.info(f"[embed_and_store] Splitting {len(docs)} docs into chunks...")
    print(f"[embed_and_store] Splitting {len(docs)} docs into chunks...")
    doc_chunks = splitter.split_documents(docs)
    logger.info(
        f"[embed_and_store] Split {len(docs)} docs thành {len(doc_chunks)} chunks"
    )
    print(f"[embed_and_store] Split {len(docs)} docs thành {len(doc_chunks)} chunks")
    model_key, model = get_embedding_model(model_name)
    texts = [chunk.page_content for chunk in doc_chunks]
    logger.info(
        f"[embed_and_store] Embedding {len(texts)} chunks with model {model_key}"
    )
    print(f"[embed_and_store] Embedding {len(texts)} chunks with model {model_key}")
    if model_key == "gemini-embedding-exp-03-07":
        # Dùng API gốc Google Generative AI
        genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
        vectors = []
        for idx, text in enumerate(texts):
            try:
                logger.info(f"[embed_and_store] Embedding chunk {idx+1}/{len(texts)}")
                print(f"[embed_and_store] Embedding chunk {idx+1}/{len(texts)}")
                result = genai.embed_content(
                    model="gemini-embedding-exp-03-07",
                    content=text,
                    task_type="SEMANTIC_SIMILARITY",
                )
                vectors.append(result["embedding"])
            except Exception as e:
                logger.error(f"Lỗi khi embedding với Gemini: {e}")
                print(f"Lỗi khi embedding với Gemini: {e}")
                vectors.append([0.0] * 3072)  # fallback vector size
    else:
        vectors = model.embed_documents(texts)
    logger.info(f"[embed_and_store] Finished embedding. Storing to Qdrant...")
    print(f"[embed_and_store] Finished embedding. Storing to Qdrant...")
    for i, (chunk, vector) in enumerate(zip(doc_chunks, vectors)):
        meta = metadata.copy() if metadata else {}
        meta.update(chunk.metadata)
        ns = namespace or meta.get("namespace") or "default"
        logger.info(
            f"[embed_and_store] Storing chunk {i+1}/{len(doc_chunks)} to Qdrant (namespace={ns})"
        )
        print(
            f"[embed_and_store] Storing chunk {i+1}/{len(doc_chunks)} to Qdrant (namespace={ns})"
        )
        qdrant_store.put(
            namespace=ns,
            key=f"chunk_{i}",
            value={"content": chunk.page_content, "embedding": vector, **meta},
        )
    logger.info(
        f"Đã lưu {len(doc_chunks)} vectors vào Qdrant collection: {qdrant_store.collection_name if not collection_name else collection_name}"
    )
    print(
        f"Đã lưu {len(doc_chunks)} vectors vào Qdrant collection: {qdrant_store.collection_name if not collection_name else collection_name}"
    )


def check_and_recreate_collection(collection_name: str, vector_size: int):
    """
    Kiểm tra collection Qdrant, nếu vector size không khớp thì xóa và tạo lại.
    Nếu collection chưa tồn tại sẽ tự tạo mới.
    """
    from qdrant_client import QdrantClient

    qdrant_host = os.getenv("QDRANT_HOST", "localhost")
    qdrant_port = int(os.getenv("QDRANT_PORT", "6333"))
    qdrant_client = QdrantClient(host=qdrant_host, port=qdrant_port)
    try:
        info = qdrant_client.get_collection(collection_name)
        current_size = info.config.params.vectors.size
        if current_size != vector_size:
            print(
                f"⚠️ Collection '{collection_name}' vector size {current_size} ≠ {vector_size}, sẽ xóa và tạo lại."
            )
            qdrant_client.delete_collection(collection_name)
            qdrant_client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
            )
            print(
                f"✅ Created Qdrant collection: {collection_name} (vector size: {vector_size})"
            )
        else:
            print(
                f"✅ Collection '{collection_name}' đã đúng vector size: {vector_size}"
            )
    except Exception as e:
        # Nếu collection chưa tồn tại thì tạo mới
        print(
            f"ℹ️ Collection '{collection_name}' chưa tồn tại hoặc lỗi khác: {e}. Sẽ tạo mới."
        )
        try:
            qdrant_client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
            )
            print(
                f"✅ Created Qdrant collection: {collection_name} (vector size: {vector_size})"
            )
        except Exception as e2:
            print(f"❌ Không thể tạo collection: {e2}")


def run_embedding_pipeline(
    files: List[str],
    urls: Optional[List[str]] = None,
    collection_name: str = "default",
    domain: Optional[str] = None,
    department: Optional[str] = None,
    user_id: Optional[str] = None,
    chunk_size: int = 800,
    chunk_overlap: int = 200,
    model_name: str = "google",
    namespace: Optional[str] = None,
    force_delete_collection: bool = True,
):
    """
    High-level API: embed files/urls with metadata and store in Qdrant.
    """
    metadata = {}
    if domain:
        metadata["domain"] = domain
    if department:
        metadata["department"] = department
    if user_id:
        metadata["user_id"] = user_id
    logger.info(
        f"[run_embedding_pipeline] Start loading documents: files={files}, urls={urls}"
    )
    print(
        f"[run_embedding_pipeline] Start loading documents: files={files}, urls={urls}"
    )
    docs = load_documents(files, urls, extra_metadata=metadata)
    logger.info(f"[run_embedding_pipeline] Loaded {len(docs)} documents")
    print(f"[run_embedding_pipeline] Loaded {len(docs)} documents")
    # Xác định vector size theo model
    model_key, _ = get_embedding_model(model_name)
    vector_size = get_vector_size(model_key)
    logger.info(
        f"[run_embedding_pipeline] Model: {model_key}, vector_size: {vector_size}"
    )
    print(f"[run_embedding_pipeline] Model: {model_key}, vector_size: {vector_size}")
    check_and_recreate_collection(collection_name, vector_size)
    logger.info(
        f"[run_embedding_pipeline] Collection checked/created: {collection_name}"
    )
    print(f"[run_embedding_pipeline] Collection checked/created: {collection_name}")
    print(f"model_key {model_key}")
    qdrant_store = QdrantStore(collection_name=collection_name, embedding_model=model_key)
    logger.info(f"[run_embedding_pipeline] Start embedding and storing...")
    print(f"[run_embedding_pipeline] Start embedding and storing...")
    embed_and_store(
        docs,
        qdrant_store=qdrant_store,
        collection_name=collection_name,
        metadata=metadata,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        model_name=model_name,
        namespace=namespace,
    )
    logger.info(f"[run_embedding_pipeline] Finished embedding and storing.")
    print(f"[run_embedding_pipeline] Finished embedding and storing.")


def parse_args():
    parser = argparse.ArgumentParser(description="Embed documents & ingest into Qdrant")
    parser.add_argument("--files", nargs="*", default=None, help="List of local file paths")
    parser.add_argument("--urls", nargs="*", default=None, help="List of URLs to load")
    parser.add_argument("--collection", default="tianlong_marketing", help="Qdrant collection name")
    parser.add_argument("--domain", default="marketing", help="Domain metadata tag")
    #parser.add_argument("--namespace", default="marketing", help="Namespace for storage")
    parser.add_argument("--namespace", default="faq", help="Namespace for storage")
    #parser.add_argument("--namespace", default="images", help="Namespace for storage")
    parser.add_argument("--model", default="text-embedding-004", help="Embedding model alias")
    parser.add_argument("--chunk-size", type=int, default=800)
    parser.add_argument("--chunk-overlap", type=int, default=200)
    parser.add_argument("--user-id", default=None)
    parser.add_argument("--department", default=None)
    parser.add_argument("--no-force-delete", action="store_true", help="(reserved) backward compatible placeholder")
    return parser.parse_args()


def ensure_user_agent():
    if not os.getenv("USER_AGENT"):
        # Set a benign default to reduce warning noise; user can override.
        os.environ["USER_AGENT"] = "embedding-pipeline/1.0 (+https://example.local)"


def validate_env_for_model(model_alias: str):
    if model_alias.lower() in {"gemini-embedding-exp-03-07", "google", "text-embedding-004", "google-text-embedding-004", "models/text-embedding-004"}:
        if not os.getenv("GOOGLE_API_KEY"):
            print("⚠️  GOOGLE_API_KEY not set. Gemini embedding calls may fail.")


if __name__ == "__main__":
    load_dotenv()
    ensure_user_agent()
    args = parse_args()

    # Default file if none provided
    #default_file = PROJECT_ROOT / "data" / "menu_combos_for_embedding.json"
    #default_file = PROJECT_ROOT / "data" / "marketing_data.txt"
    default_file = PROJECT_ROOT / "data" / "FAQ.txt"
    resolved_files: List[str] = []
    if args.files:
        for f in args.files:
            p = Path(f)
            if not p.is_file():
                print(f"⚠️  Skipping missing file: {p}")
                continue
            resolved_files.append(str(p))
    else:
        if default_file.is_file():
            resolved_files.append(str(default_file))
        else:
            print(f"❌ Default data file not found: {default_file}")
            sys.exit(1)

    validate_env_for_model(args.model)

    run_embedding_pipeline(
        files=resolved_files,
        urls=args.urls or [],
        collection_name=args.collection,
        domain=args.domain,
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap,
        model_name=args.model,
        namespace=args.namespace,
        user_id=args.user_id,
    )
