"""知识库模块"""

from typing import List, Dict
from .retriever import retriever


class KnowledgeBase:
    """知识库"""

    def __init__(self):
        pass

    def retrieve(self, tenant_id: str, query: str, top_k: int = 3) -> List[Dict]:
        """
        检索相关知识
        
        Args:
            tenant_id: 租户 ID
            query: 查询文本
            top_k: 返回结果数量
        
        Returns:
            List[Dict]: 检索结果
        """
        # 使用增强版RAG检索器
        return retriever.retrieve(tenant_id, query, top_k)


# 全局知识库实例
knowledge_base = KnowledgeBase()