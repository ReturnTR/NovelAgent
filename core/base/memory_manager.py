from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import asyncio

# ---------- 数据模型（与之前一致，方便直接使用） ----------
class MemoryType(Enum):
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    PROCEDURAL = "procedural"

@dataclass
class RawInteraction:
    session_id: str
    user_id: str
    query: str
    response: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)

@dataclass
class MemoryFragment:
    id: Optional[str] = None
    user_id: str = ""
    content: str = ""
    memory_type: MemoryType = MemoryType.EPISODIC
    importance: float = 0.5
    embedding: Optional[List[float]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    last_accessed_at: Optional[datetime] = None
    access_count: int = 0

# ---------- 依赖接口（抽象基类，便于替换具体实现） ----------
from abc import ABC, abstractmethod

class EmbeddingProvider(ABC):
    @abstractmethod
    async def embed(self, texts: List[str]) -> List[List[float]]:
        pass

class VectorStore(ABC):
    @abstractmethod
    async def upsert(self, fragments: List[MemoryFragment]) -> List[str]:
        """插入或更新记忆片段，返回 ID 列表"""
        pass

    @abstractmethod
    async def query(
        self,
        query_vector: List[float],
        user_id: str,
        top_k: int = 5,
        filter: Optional[Dict] = None,
        hybrid_weight: float = 0.7
    ) -> List[MemoryFragment]:
        """混合检索（语义 + 关键词）"""
        pass

    @abstractmethod
    async def delete(self, ids: List[str]) -> bool:
        pass

    @abstractmethod
    async def update_metadata(self, id: str, updates: Dict[str, Any]) -> bool:
        pass

# ---------- MemoryManager 核心类 ----------
class MemoryManager:
    """
    AI Agent 记忆管理器，封装记忆生命周期的五个阶段：
    抽取 (extract) -> 整合 (consolidate) -> 存储 (store) -> 检索 (retrieve) -> 遗忘 (forget)
    """

    def __init__(
        self,
        embedding_provider: EmbeddingProvider,
        vector_store: VectorStore,
        extractor_llm=None,          # 可为抽取阶段单独配置的 LLM 客户端
        consolidator_llm=None,       # 可为整合阶段单独配置的 LLM 客户端
        default_importance: float = 0.5
    ):
        self.embedding = embedding_provider
        self.vector_store = vector_store
        self.extractor_llm = extractor_llm
        self.consolidator_llm = consolidator_llm
        self.default_importance = default_importance

    # ---------- 1. 抽取阶段 ----------
    async def extract_memories(self, interaction: RawInteraction) -> List[MemoryFragment]:
        """
        从单次交互中抽取值得保留的记忆片段。
        实际实现可调用 LLM 判断哪些信息重要，此处提供一个示例占位逻辑。
        """
        # 占位实现：直接将问答拼接为一条情景记忆
        content = f"User: {interaction.query}\nAgent: {interaction.response}"
        fragment = MemoryFragment(
            user_id=interaction.user_id,
            content=content,
            memory_type=MemoryType.EPISODIC,
            importance=self.default_importance,
            metadata={"session_id": interaction.session_id, **interaction.metadata}
        )
        return [fragment]

    # ---------- 2. 整合阶段 ----------
    async def consolidate_memories(self, fragments: List[MemoryFragment]) -> List[MemoryFragment]:
        """
        对抽取出的片段进行去重、冲突解决、摘要和结构化处理。
        这里返回原列表，实际可调用 LLM 进行合并或改写。
        """
        # 占位：直接返回输入片段（无变化）
        return fragments

    # ---------- 3. 存储阶段 ----------
    async def store_memories(self, fragments: List[MemoryFragment]) -> List[str]:
        """
        将整合后的记忆持久化到向量存储。
        步骤：1) 生成嵌入向量  2) 调用向量存储 upsert
        """
        if not fragments:
            return []

        # 生成嵌入向量（只对尚未包含向量的片段）
        texts_to_embed = [f.content for f in fragments if f.embedding is None]
        if texts_to_embed:
            embeddings = await self.embedding.embed(texts_to_embed)
            idx = 0
            for frag in fragments:
                if frag.embedding is None:
                    frag.embedding = embeddings[idx]
                    idx += 1

        # 存储
        return await self.vector_store.upsert(fragments)

    # ---------- 4. 检索阶段 ----------
    async def retrieve_memories(
        self,
        query: str,
        user_id: str,
        top_k: int = 5,
        memory_types: Optional[List[MemoryType]] = None,
        hybrid_weight: float = 0.7
    ) -> List[MemoryFragment]:
        """
        根据查询文本检索相关记忆（混合检索：向量语义 + 关键词）。
        """
        # 生成查询向量
        query_vector = (await self.embedding.embed([query]))[0]

        # 构造过滤条件（如果限定记忆类型）
        filter_dict = None
        if memory_types:
            filter_dict = {"memory_type": {"$in": [t.value for t in memory_types]}}

        return await self.vector_store.query(
            query_vector=query_vector,
            user_id=user_id,
            top_k=top_k,
            filter=filter_dict,
            hybrid_weight=hybrid_weight
        )

    # ---------- 5. 遗忘阶段 ----------
    async def forget_memories(self, user_id: str, policy: str = "time_based") -> int:
        """
        执行遗忘策略，清理过时、冗余或低价值记忆。
        返回被删除的记忆数量。
        """
        # 占位实现：可调用向量存储的过滤删除接口，此处演示策略框架
        # 实际应根据策略（如基于时间、重要性、访问频率）筛选要删除的记忆ID
        if policy == "time_based":
            # 示例：删除创建时间超过 90 天的记忆（需向量存储支持按字段删除）
            # 此处仅作示意，返回 0
            return 0
        elif policy == "importance_based":
            # 删除重要性低于阈值的记忆
            return 0
        else:
            return 0

    # ---------- 辅助方法：更新单条记忆 ----------
    async def update_memory(self, memory_id: str, updates: Dict[str, Any]) -> bool:
        """
        更新记忆片段的元数据或内容。
        若内容更新需重新生成嵌入向量。
        """
        if "content" in updates:
            # 重新生成嵌入
            new_embedding = (await self.embedding.embed([updates["content"]]))[0]
            updates["embedding"] = new_embedding
        return await self.vector_store.update_metadata(memory_id, updates)

    # ---------- 便捷的完整写入流程 ----------
    async def process_interaction(self, interaction: RawInteraction) -> List[str]:
        """
        完整的记忆写入流水线：抽取 -> 整合 -> 存储
        返回存储成功的记忆 ID 列表。
        """
        fragments = await self.extract_memories(interaction)
        if not fragments:
            return []
        consolidated = await self.consolidate_memories(fragments)
        return await self.store_memories(consolidated)