"""排队管理模块"""

from typing import Dict, List, Optional
import time
import uuid


class HandoffQueue:
    """转人工排队队列"""

    def __init__(self):
        self.queue = []  # 排队队列
        self.active_sessions = {}  # 活跃会话（已分配给坐席）
        self.max_wait_time = 300  # 最长等待时间（秒）

    def add_to_queue(self, session_id: str, user_id: str, tenant_id: str, reason: str) -> Dict:
        """
        添加到排队队列
        
        Args:
            session_id: 会话ID
            user_id: 用户ID
            tenant_id: 租户ID
            reason: 转人工原因
            
        Returns:
            Dict: 排队信息
        """
        ticket_id = str(uuid.uuid4())
        queue_item = {
            "ticket_id": ticket_id,
            "session_id": session_id,
            "user_id": user_id,
            "tenant_id": tenant_id,
            "reason": reason,
            "queue_time": time.time(),
            "status": "queued",
            "position": len(self.queue) + 1
        }
        
        self.queue.append(queue_item)
        return queue_item

    def get_next_in_queue(self) -> Optional[Dict]:
        """
        获取队列中的下一个会话
        
        Returns:
            Optional[Dict]: 会话信息
        """
        if not self.queue:
            return None
        
        # 移除并返回队列头部的会话
        queue_item = self.queue.pop(0)
        queue_item["status"] = "processing"
        queue_item["assign_time"] = time.time()
        
        # 更新剩余队列的位置
        for i, item in enumerate(self.queue):
            item["position"] = i + 1
        
        # 添加到活跃会话
        self.active_sessions[queue_item["session_id"]] = queue_item
        
        return queue_item

    def remove_from_queue(self, session_id: str) -> bool:
        """
        从队列中移除会话
        
        Args:
            session_id: 会话ID
            
        Returns:
            bool: 是否成功移除
        """
        # 从排队队列中移除
        for i, item in enumerate(self.queue):
            if item["session_id"] == session_id:
                self.queue.pop(i)
                # 更新剩余队列的位置
                for j, remaining_item in enumerate(self.queue[i:]):
                    remaining_item["position"] = i + j + 1
                return True
        
        # 从活跃会话中移除
        if session_id in self.active_sessions:
            del self.active_sessions[session_id]
            return True
        
        return False

    def get_queue_status(self, session_id: str) -> Optional[Dict]:
        """
        获取会话的排队状态
        
        Args:
            session_id: 会话ID
            
        Returns:
            Optional[Dict]: 状态信息
        """
        # 检查排队队列
        for item in self.queue:
            if item["session_id"] == session_id:
                wait_time = time.time() - item["queue_time"]
                return {
                    "status": item["status"],
                    "position": item["position"],
                    "wait_time": int(wait_time),
                    "estimated_wait": int(wait_time * (item["position"] / max(1, len(self.queue))))
                }
        
        # 检查活跃会话
        if session_id in self.active_sessions:
            item = self.active_sessions[session_id]
            process_time = time.time() - item.get("assign_time", item["queue_time"])
            return {
                "status": item["status"],
                "position": 0,
                "wait_time": 0,
                "process_time": int(process_time)
            }
        
        return None

    def get_queue_stats(self, tenant_id: str) -> Dict:
        """
        获取队列统计信息
        
        Args:
            tenant_id: 租户ID
            
        Returns:
            Dict: 统计信息
        """
        tenant_queue = [item for item in self.queue if item["tenant_id"] == tenant_id]
        tenant_active = [item for item in self.active_sessions.values() if item["tenant_id"] == tenant_id]
        
        return {
            "queue_length": len(tenant_queue),
            "active_count": len(tenant_active),
            "average_wait_time": self._calculate_average_wait_time(tenant_queue)
        }

    def _calculate_average_wait_time(self, queue_items: List[Dict]) -> float:
        """
        计算平均等待时间
        
        Args:
            queue_items: 队列项目
            
        Returns:
            float: 平均等待时间（秒）
        """
        if not queue_items:
            return 0.0
        
        total_wait = 0
        for item in queue_items:
            total_wait += time.time() - item["queue_time"]
        
        return total_wait / len(queue_items)

    def cleanup_timeout(self):
        """
        清理超时的排队请求
        """
        current_time = time.time()
        timeout_items = []
        
        # 清理排队队列中的超时项
        for item in self.queue:
            if current_time - item["queue_time"] > self.max_wait_time:
                timeout_items.append(item)
        
        for item in timeout_items:
            self.queue.remove(item)
        
        # 更新剩余队列的位置
        for i, item in enumerate(self.queue):
            item["position"] = i + 1
        
        return len(timeout_items)


# 全局队列实例
queue = HandoffQueue()