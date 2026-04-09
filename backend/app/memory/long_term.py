#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
长期情景记忆模块（Layer 3）
使用 ChromaDB 存储三类数据：
  1. user_episodes    — 人生事件 & 情绪体验
  2. consultation_archive — 咨询结论存档
  3. user_feedback    — 用户反馈 & 验证
"""

import chromadb
import json
import os
import time
from datetime import datetime


# ---------- 常量 ----------

EVENT_TYPES = ("travel", "career", "health", "relationship", "finance",
               "education", "family", "legal", "spiritual", "other")

EMOTIONS = ("happy", "sad", "anxious", "calm", "confused",
            "excited", "angry", "neutral")

TOPICS = ("事业", "财运", "婚姻", "健康", "学业", "方位", "流年", "大运", "其他")


class LongTermMemory:
    """长期情景记忆 — 三 Collection 架构"""

    def __init__(self, persist_directory='../data/long_term_memory'):
        self.persist_directory = persist_directory
        os.makedirs(self.persist_directory, exist_ok=True)

        self.client = chromadb.PersistentClient(path=self.persist_directory)

        # ===== Collection 1: 用户情景记忆 =====
        self.episodes = self.client.get_or_create_collection(
            name="user_episodes",
            metadata={"hnsw:space": "cosine"},
        )

        # ===== Collection 2: 咨询结论存档 =====
        self.consultations = self.client.get_or_create_collection(
            name="consultation_archive",
            metadata={"hnsw:space": "cosine"},
        )

        # ===== Collection 3: 用户反馈 =====
        self.feedback = self.client.get_or_create_collection(
            name="user_feedback",
            metadata={"hnsw:space": "cosine"},
        )

        # 向后兼容：保留旧 collection（只读，不再写入）
        try:
            self._legacy = self.client.get_collection("user_memories")
        except Exception:
            self._legacy = None

    # ================================================================
    #  情景记忆 (episodes)
    # ================================================================

    def store_episode(self, user_id: str, tenant_id: str, content: str, *,
                      event_type: str = "other",
                      emotion: str = "neutral",
                      emotion_intensity: float = 0.5,
                      time_ref: str = "",
                      location: str = "",
                      people: str = "",
                      session_id: str = "",
                      source: str = "conversation") -> dict:
        """存储一条情景记忆"""
        ep_id = f"ep_{tenant_id}_{user_id}_{int(time.time() * 1000)}"
        metadata = {
            "user_id": user_id,
            "tenant_id": tenant_id,
            "event_type": event_type if event_type in EVENT_TYPES else "other",
            "emotion": emotion if emotion in EMOTIONS else "neutral",
            "emotion_intensity": max(0.0, min(1.0, emotion_intensity)),
            "time_ref": time_ref or "",
            "location": location or "",
            "people_involved": people or "",
            "source": source,
            "session_id": session_id or "",
            "created_at": time.time(),
        }
        self.episodes.add(ids=[ep_id], documents=[content], metadatas=[metadata])
        return {"success": True, "memory_id": ep_id}

    def recall_episodes(self, user_id: str, tenant_id: str, query: str, top_k: int = 5) -> list:
        """语义检索相关情景记忆"""
        try:
            results = self.episodes.query(
                query_texts=[query],
                where={"user_id": user_id, "tenant_id": tenant_id},
                n_results=top_k,
            )
        except Exception:
            return []
        return self._unpack_query(results)

    def recall_by_emotion(self, user_id: str, tenant_id: str, emotion: str, top_k: int = 3) -> list:
        """按情绪检索"""
        try:
            results = self.episodes.query(
                query_texts=[f"用户感到{emotion}的经历"],
                where={"$and": [{"user_id": user_id}, {"tenant_id": tenant_id}, {"emotion": emotion}]},
                n_results=top_k,
            )
        except Exception:
            return []
        return self._unpack_query(results)

    def recall_by_event_type(self, user_id: str, tenant_id: str, event_type: str, top_k: int = 5) -> list:
        """按事件类型检索"""
        try:
            results = self.episodes.query(
                query_texts=[f"用户的{event_type}相关经历"],
                where={"$and": [{"user_id": user_id}, {"tenant_id": tenant_id}, {"event_type": event_type}]},
                n_results=top_k,
            )
        except Exception:
            return []
        return self._unpack_query(results)

    # ================================================================
    #  咨询结论 (consultations)
    # ================================================================

    def store_consultation(self, user_id: str, tenant_id: str, summary: str, *,
                           topic: str = "其他",
                           advice: str = "",
                           dayun: str = "",
                           liunian: str = "",
                           session_id: str = "") -> dict:
        """存储一次咨询结论"""
        c_id = f"consult_{tenant_id}_{user_id}_{int(time.time() * 1000)}"
        document = summary
        if advice:
            document += f"\n建议：{advice}"
        metadata = {
            "user_id": user_id,
            "tenant_id": tenant_id,
            "topic": topic or "其他",
            "dayun": dayun or "",
            "liunian": liunian or "",
            "session_id": session_id or "",
            "created_at": time.time(),
        }
        self.consultations.add(ids=[c_id], documents=[document], metadatas=[metadata])
        return {"success": True, "memory_id": c_id}

    def recall_consultations(self, user_id: str, tenant_id: str, query: str, top_k: int = 3) -> list:
        """语义检索历史咨询结论"""
        try:
            results = self.consultations.query(
                query_texts=[query],
                where={"user_id": user_id, "tenant_id": tenant_id},
                n_results=top_k,
            )
        except Exception:
            return []
        return self._unpack_query(results)

    def recall_consultations_by_topic(self, user_id: str, tenant_id: str, topic: str, top_k: int = 3) -> list:
        """按主题检索咨询结论"""
        try:
            results = self.consultations.query(
                query_texts=[f"{topic}方面的咨询结论"],
                where={"$and": [{"user_id": user_id}, {"tenant_id": tenant_id}, {"topic": topic}]},
                n_results=top_k,
            )
        except Exception:
            return []
        return self._unpack_query(results)

    # ================================================================
    #  用户反馈 (feedback)
    # ================================================================

    def store_feedback(self, user_id: str, tenant_id: str, content: str, *,
                       feedback_type: str = "neutral",
                       related_consult: str = "",
                       session_id: str = "") -> dict:
        """存储一条用户反馈"""
        fb_id = f"fb_{tenant_id}_{user_id}_{int(time.time() * 1000)}"
        metadata = {
            "user_id": user_id,
            "tenant_id": tenant_id,
            "feedback_type": feedback_type,   # positive / negative / neutral
            "related_consult": related_consult or "",
            "session_id": session_id or "",
            "created_at": time.time(),
        }
        self.feedback.add(ids=[fb_id], documents=[content], metadatas=[metadata])
        return {"success": True, "memory_id": fb_id}

    # ================================================================
    #  通用操作
    # ================================================================

    def get_user_memories(self, user_id: str, tenant_id: str, memory_type: str = None,
                          limit: int = 10) -> dict:
        """获取用户的所有记忆（合并三个 collection）"""
        memories = []

        collections = []
        if memory_type in (None, "episode"):
            collections.append(("episode", self.episodes))
        if memory_type in (None, "consultation"):
            collections.append(("consultation", self.consultations))
        if memory_type in (None, "feedback"):
            collections.append(("feedback", self.feedback))

        for ctype, col in collections:
            try:
                results = col.get(where={"user_id": user_id, "tenant_id": tenant_id}, limit=limit)
                for i in range(len(results["ids"])):
                    memories.append({
                        "id": results["ids"][i],
                        "type": ctype,
                        "content": results["documents"][i],
                        "metadata": results["metadatas"][i],
                    })
            except Exception:
                continue

        # 按 created_at 倒序
        memories.sort(key=lambda m: m["metadata"].get("created_at", 0), reverse=True)
        return {"success": True, "memories": memories[:limit]}

    def delete_memory(self, memory_id: str) -> dict:
        """按 ID 前缀判断并从对应 collection 删除"""
        try:
            if memory_id.startswith("ep_"):
                self.episodes.delete(ids=[memory_id])
            elif memory_id.startswith("consult_"):
                self.consultations.delete(ids=[memory_id])
            elif memory_id.startswith("fb_"):
                self.feedback.delete(ids=[memory_id])
            else:
                # 兼容旧 ID
                for col in (self.episodes, self.consultations, self.feedback):
                    try:
                        col.delete(ids=[memory_id])
                    except Exception:
                        pass
            return {"success": True}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def delete_user_memories(self, user_id: str, tenant_id: str, memory_type: str = None) -> int:
        """删除用户的所有记忆（按类型）"""
        deleted = 0

        collections = []
        if memory_type in (None, "episode"):
            collections.append(self.episodes)
        if memory_type in (None, "consultation"):
            collections.append(self.consultations)
        if memory_type in (None, "feedback"):
            collections.append(self.feedback)

        for col in collections:
            try:
                # 先获取所有匹配的 ID
                results = col.get(where={"user_id": user_id, "tenant_id": tenant_id})
                ids = results.get("ids", [])
                if ids:
                    col.delete(ids=ids)
                    deleted += len(ids)
            except Exception:
                continue

        return deleted

    # ================================================================
    #  向后兼容 — 旧接口代理
    # ================================================================

    def store_memory(self, user_id: str, tenant_id: str, memory: dict) -> dict:
        """旧接口：统一存储入口（代理到新 collection）"""
        content = memory.get("content", "")
        mtype = memory.get("type", "event")
        emotion = memory.get("emotion", "neutral")

        if mtype == "consultation":
            return self.store_consultation(
                user_id, tenant_id, content,
                topic=memory.get("topic", "其他"),
                advice=memory.get("advice", ""),
                session_id=memory.get("session_id", ""),
            )
        elif mtype == "feedback":
            return self.store_feedback(
                user_id, tenant_id, content,
                feedback_type=memory.get("feedback_type", "neutral"),
                related_consult=memory.get("related_consult", ""),
                session_id=memory.get("session_id", ""),
            )
        else:
            return self.store_episode(
                user_id, tenant_id, content,
                event_type=mtype if mtype in EVENT_TYPES else "other",
                emotion=emotion,
                time_ref=memory.get("time_ref", ""),
                location=memory.get("location", ""),
                people=memory.get("related_people", ""),
                session_id=memory.get("session_id", ""),
            )

    def retrieve_memory(self, user_id: str, tenant_id: str, query: str, top_k: int = 5) -> dict:
        """旧接口：语义检索（合并 episodes + consultations）"""
        episodes = self.recall_episodes(user_id, tenant_id, query, top_k=top_k)
        consults = self.recall_consultations(user_id, tenant_id, query, top_k=top_k)
        merged = episodes + consults
        merged.sort(key=lambda m: m.get("distance", 1.0))
        return {"success": True, "memories": merged[:top_k]}

    # ================================================================
    #  内部工具
    # ================================================================

    @staticmethod
    def _unpack_query(results: dict) -> list:
        """将 ChromaDB query 结果展开成列表"""
        if not results or not results.get("ids") or not results["ids"][0]:
            return []
        items = []
        for i in range(len(results["ids"][0])):
            items.append({
                "id": results["ids"][0][i],
                "content": results["documents"][0][i],
                "metadata": results["metadatas"][0][i],
                "distance": results["distances"][0][i] if results.get("distances") else None,
            })
        return items


# 全局实例
long_term_memory = LongTermMemory()