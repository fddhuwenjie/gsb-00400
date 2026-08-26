import faiss
import numpy as np
from pathlib import Path
from typing import List, Dict
import json
import os
import logging
import time

logger = logging.getLogger(__name__)

# 使用国内镜像
os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'
os.environ['TRANSFORMERS_OFFLINE'] = '0'
os.environ['HF_HUB_DOWNLOAD_TIMEOUT'] = '300'

class EmbeddingService:
    """向量化与检索服务"""
    
    def __init__(self, model_name: str = "paraphrase-multilingual-MiniLM-L12-v2"):
        self.model_name = model_name
        self.model = None
        self.model_available = None
        self.dimension = 384
        self.index = None
        self.id_map = {}
        self.index_path = Path(os.environ.get("VECTOR_DB_PATH", "/data/vector_store"))
        self._load_attempts = 0
        self._max_attempts = 3
    
    def _load_model(self) -> bool:
        if self.model is not None:
            return True
        
        # 限制重试次数
        if self._load_attempts >= self._max_attempts:
            return False
        
        self._load_attempts += 1
        
        try:
            from sentence_transformers import SentenceTransformer
            logger.info(f"Loading embedding model: {self.model_name} (attempt {self._load_attempts})")
            self.model = SentenceTransformer(self.model_name)
            self.dimension = self.model.get_sentence_embedding_dimension()
            self.model_available = True
            logger.info(f"Embedding model loaded successfully, dimension: {self.dimension}")
            return True
        except Exception as e:
            logger.warning(f"Failed to load embedding model (attempt {self._load_attempts}): {e}")
            self.model_available = False
            return False
    
    def reset_load_attempts(self):
        """重置加载尝试次数，允许重新尝试加载模型"""
        self._load_attempts = 0
        self.model_available = None
    
    def init_index(self):
        self.index = faiss.IndexFlatIP(self.dimension)
        self.id_map = {}
    
    def load_index(self) -> bool:
        index_file = self.index_path / "faiss.index"
        map_file = self.index_path / "id_map.json"
        try:
            if index_file.exists() and map_file.exists():
                self.index = faiss.read_index(str(index_file))
                with open(map_file, "r") as f:
                    self.id_map = json.load(f)
                return True
        except Exception:
            pass
        self.init_index()
        return False

    def save_index(self):
        self.index_path.mkdir(parents=True, exist_ok=True)
        faiss.write_index(self.index, str(self.index_path / "faiss.index"))
        with open(self.index_path / "id_map.json", "w") as f:
            json.dump(self.id_map, f, ensure_ascii=False)
    
    def add_chunks(self, file_id: int, chunks: List[Dict]) -> List[str]:
        """添加文本块到索引（模型不可用时跳过）"""
        if not self._load_model():
            logger.warning("Embedding model not available, skipping vectorization")
            return []
        
        if self.index is None:
            self.load_index()
        
        vector_ids = []
        texts = [c["content"] for c in chunks]
        if not texts:
            return vector_ids
        
        try:
            embeddings = self.model.encode(texts, normalize_embeddings=True)
            start_id = self.index.ntotal
            
            for i, (chunk, emb) in enumerate(zip(chunks, embeddings)):
                vector_id = f"{file_id}_{chunk['index']}"
                self.index.add(np.array([emb]).astype('float32'))
                self.id_map[str(start_id + i)] = {"file_id": file_id, "chunk_index": chunk["index"], "vector_id": vector_id}
                vector_ids.append(vector_id)
            
            self.save_index()
        except Exception as e:
            logger.error(f"Failed to add chunks: {e}")
        
        return vector_ids
    
    def search(self, query: str, top_k: int = 10) -> List[Dict]:
        """向量检索"""
        if not self._load_model():
            return []
        
        if self.index is None:
            self.load_index()
        
        if self.index.ntotal == 0:
            return []
        
        try:
            query_vec = self.model.encode(query, normalize_embeddings=True)
            query_vec = query_vec.reshape(1, -1).astype('float32')
            scores, indices = self.index.search(query_vec, min(top_k, self.index.ntotal))
            
            results = []
            for score, idx in zip(scores[0], indices[0]):
                if idx >= 0 and str(idx) in self.id_map:
                    info = self.id_map[str(idx)]
                    results.append({"file_id": info["file_id"], "chunk_index": info["chunk_index"], "score": float(score)})
            return results
        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []
