from qdrant_client.http.models import VectorParams, Distance


def get_vector_size(model_key: str) -> int:
    if model_key == "gemini-embedding-exp-03-07":
        return 3072
    # text-embedding-004 và các model Google mới
    return 768


import os
from dotenv import load_dotenv
import google.generativeai as genai
import logging
from typing import List, Optional, Dict, Any, Callable
from langchain_community.document_loaders import (
    WebBaseLoader,
    PyPDFLoader,
    TextLoader,
    Docx2txtLoader,
)
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from src.database.qdrant_store import QdrantStore

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

# Loader registry for extensibility
LOADER_REGISTRY: Dict[str, Callable[[str], Any]] = {
    ".pdf": lambda f: PyPDFLoader(f).load(),
    ".docx": lambda f: Docx2txtLoader(f).load(),
    ".txt": lambda f: TextLoader(f).load(),
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
    chunk_size: int = 384,
    chunk_overlap: int = 64,
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
    chunk_size: int = 384,
    chunk_overlap: int = 64,
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


if __name__ == "__main__":
    # Example usage: customize as needed
    files = []
    urls = [
        "https://uiic.co.in/sites/default/files/uploads/downloadcenter/Rural%20&%20Social%20-%20Dairy%20Package%20Insurance_3.pdf",
        "https://uiic.co.in/sites/default/files/uploads/downloadcenter/Overseas%20Mediclaim%20Schengen%20Policy.pdf",
        "https://uiic.co.in/sites/default/files/uploads/downloadcenter/Loss%20of%20License%20Policy(Individual%20and%20Group).pdf",
    ]
    run_embedding_pipeline(
        files=files,
        urls=urls,
        collection_name="insurance_store",
        domain="insurance",
        chunk_size=384,
        chunk_overlap=64,
        model_name="text-embedding-004",
        namespace="insurance_demo",
    )

    # run_embedding_pipeline(
    #     files=files,
    #     urls=urls,
    #     collection_name="accounting_store",
    #     domain="accounting",
    #     department="finance",
    #     user_id="user123",
    #     chunk_size=384,
    #     chunk_overlap=64,
    #     model_name="google",
    #     namespace="accounting_demo"
    # )
