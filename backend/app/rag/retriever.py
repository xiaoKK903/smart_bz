"""RAG检索器模块"""

from typing import List, Dict, Tuple
import os
import json
import requests
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


class RAGRetriever:
    """增强版RAG检索器"""

    def __init__(self):
        self.knowledge = []
        self.qa_pairs = []
        self.tfidf_vectorizer = TfidfVectorizer()
        self.tfidf_matrix = None
        self._load_knowledge()
        self._initialize_tfidf()

    def _load_knowledge(self):
        """
        加载知识库
        """
        # 加载电商领域的知识
        ecommerce_knowledge_path = os.path.join(
            os.path.dirname(__file__),
            "..", "domains", "ecommerce", "knowledge"
        )
        
        # 加载FAQ
        faq_path = os.path.join(ecommerce_knowledge_path, "常见问题FAQ.md")
        if os.path.exists(faq_path):
            with open(faq_path, "r", encoding="utf-8") as f:
                content = f.read()
                self.knowledge.append({"content": content, "type": "faq"})
        
        # 加载商品目录
        product_path = os.path.join(ecommerce_knowledge_path, "商品目录.md")
        if os.path.exists(product_path):
            with open(product_path, "r", encoding="utf-8") as f:
                content = f.read()
                self.knowledge.append({"content": content, "type": "product"})
        
        # 加载物流说明
        logistics_path = os.path.join(ecommerce_knowledge_path, "物流说明.md")
        if os.path.exists(logistics_path):
            with open(logistics_path, "r", encoding="utf-8") as f:
                content = f.read()
                self.knowledge.append({"content": content, "type": "logistics"})
        
        # 加载退换货政策
        refund_path = os.path.join(ecommerce_knowledge_path, "退换货政策.md")
        if os.path.exists(refund_path):
            with open(refund_path, "r", encoding="utf-8") as f:
                content = f.read()
                self.knowledge.append({"content": content, "type": "refund"})
        
        # 加载QA对
        qa_path = os.path.join(ecommerce_knowledge_path, "qa_pairs.json")
        if os.path.exists(qa_path):
            with open(qa_path, "r", encoding="utf-8") as f:
                self.qa_pairs = json.load(f)
                for pair in self.qa_pairs:
                    content = f"问题: {pair.get('question')}\n答案: {pair.get('answer')}"
                    self.knowledge.append({"content": content, "type": "qa"})

    def _initialize_tfidf(self):
        """
        初始化TF-IDF向量器
        """
        if self.knowledge:
            texts = [item["content"] for item in self.knowledge]
            self.tfidf_matrix = self.tfidf_vectorizer.fit_transform(texts)

    def _get_embedding(self, text: str) -> List[float]:
        """
        获取文本的embedding
        
        Args:
            text: 文本内容
            
        Returns:
            List[float]: embedding向量
        """
        try:
            # 使用DeepSeek API获取embedding
            response = requests.post(
                "https://api.deepseek.com/v1/embeddings",
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {os.getenv('DEEPSEEK_API_KEY', '')}"
                },
                json={
                    "model": "deepseek-embed",
                    "input": text,
                    "encoding_format": "float"
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                return data["data"][0]["embedding"]
            else:
                # 如果API调用失败，返回空向量
                return [0.0] * 1024
        except Exception as e:
            print(f"Embedding API error: {e}")
            # 失败时返回空向量
            return [0.0] * 1024

    def _exact_qa_match(self, query: str) -> List[Dict]:
        """
        精确匹配QA对
        
        Args:
            query: 查询文本
            
        Returns:
            List[Dict]: 匹配的QA对
        """
        matches = []
        query_lower = query.lower()
        
        for i, pair in enumerate(self.qa_pairs):
            question = pair.get("question", "").lower()
            # 检查是否完全匹配或部分匹配
            if query_lower in question or question in query_lower:
                matches.append({
                    "content": f"问题: {pair.get('question')}\n答案: {pair.get('answer')}",
                    "type": "qa",
                    "score": 1.0,  # 精确匹配得分最高
                    "source": "qa_pair"
                })
        
        return matches

    def _semantic_search(self, query: str, top_k: int = 3) -> List[Dict]:
        """
        语义向量搜索
        
        Args:
            query: 查询文本
            top_k: 返回结果数量
            
        Returns:
            List[Dict]: 搜索结果
        """
        # 获取查询的embedding
        query_embedding = self._get_embedding(query)
        
        # 计算与每个知识条目的相似度
        results = []
        for i, item in enumerate(self.knowledge):
            item_embedding = self._get_embedding(item["content"])
            # 计算余弦相似度
            similarity = np.dot(query_embedding, item_embedding) / (
                np.linalg.norm(query_embedding) * np.linalg.norm(item_embedding) + 1e-10
            )
            
            results.append({
                "content": item["content"],
                "type": item["type"],
                "score": float(similarity),
                "source": "semantic"
            })
        
        # 排序并返回前top_k个结果
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]

    def _bm25_search(self, query: str, top_k: int = 3) -> List[Dict]:
        """
        BM25搜索（使用TF-IDF近似）
        
        Args:
            query: 查询文本
            top_k: 返回结果数量
            
        Returns:
            List[Dict]: 搜索结果
        """
        if not self.tfidf_matrix:
            return []
        
        # 转换查询为TF-IDF向量
        query_vector = self.tfidf_vectorizer.transform([query])
        
        # 计算余弦相似度
        similarities = cosine_similarity(query_vector, self.tfidf_matrix)[0]
        
        # 生成结果
        results = []
        for i, score in enumerate(similarities):
            if score > 0:
                results.append({
                    "content": self.knowledge[i]["content"],
                    "type": self.knowledge[i]["type"],
                    "score": float(score),
                    "source": "bm25"
                })
        
        # 排序并返回前top_k个结果
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]

    def retrieve(self, tenant_id: str, query: str, top_k: int = 3) -> List[Dict]:
        """
        混合检索
        
        Args:
            tenant_id: 租户ID
            query: 查询文本
            top_k: 返回结果数量
            
        Returns:
            List[Dict]: 检索结果
        """
        # 1. 首先进行精确QA对匹配
        exact_matches = self._exact_qa_match(query)
        
        # 如果有精确匹配，直接返回
        if exact_matches:
            return exact_matches[:top_k]
        
        # 2. 混合语义搜索和BM25搜索
        semantic_results = self._semantic_search(query, top_k * 2)
        bm25_results = self._bm25_search(query, top_k * 2)
        
        # 3. 合并结果并去重
        merged_results = {}
        
        # 先添加语义搜索结果
        for result in semantic_results:
            key = result["content"]
            if key not in merged_results:
                merged_results[key] = result
            else:
                # 如果已存在，取较高的分数
                if result["score"] > merged_results[key]["score"]:
                    merged_results[key] = result
        
        # 再添加BM25搜索结果
        for result in bm25_results:
            key = result["content"]
            if key not in merged_results:
                merged_results[key] = result
            else:
                # 混合分数：语义分数 * 0.7 + BM25分数 * 0.3
                merged_results[key]["score"] = (
                    merged_results[key]["score"] * 0.7 + result["score"] * 0.3
                )
                merged_results[key]["source"] = "hybrid"
        
        # 4. 排序并返回前top_k个结果
        final_results = list(merged_results.values())
        final_results.sort(key=lambda x: x["score"], reverse=True)
        
        return final_results[:top_k]


# 全局检索器实例
retriever = RAGRetriever()