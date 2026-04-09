"""全链路追踪模块"""

from typing import Dict, Any, Optional, List
import time
import uuid


class Tracer:
    """全链路追踪器"""

    def __init__(self):
        self.traces = {}  # trace_id -> trace_data

    def start_trace(self, tenant_id: str, session_id: str, user_id: str) -> str:
        """
        开始追踪
        
        Args:
            tenant_id: 租户ID
            session_id: 会话ID
            user_id: 用户ID
            
        Returns:
            str: 追踪ID
        """
        trace_id = str(uuid.uuid4())
        self.traces[trace_id] = {
            "trace_id": trace_id,
            "tenant_id": tenant_id,
            "session_id": session_id,
            "user_id": user_id,
            "start_time": time.time(),
            "end_time": None,
            "duration": None,
            "steps": [],
            "metrics": {
                "total_tokens": 0,
                "input_tokens": 0,
                "output_tokens": 0,
                "llm_calls": 0,
                "rag_calls": 0,
                "intent_calls": 0
            }
        }
        return trace_id

    def add_step(self, trace_id: str, step_name: str, data: Optional[Dict] = None):
        """
        添加追踪步骤
        
        Args:
            trace_id: 追踪ID
            step_name: 步骤名称
            data: 步骤数据
        """
        if trace_id not in self.traces:
            return
        
        step = {
            "step": step_name,
            "timestamp": time.time(),
            "data": data or {}
        }
        self.traces[trace_id]["steps"].append(step)

    def add_metrics(self, trace_id: str, metrics: Dict[str, int]):
        """
        添加指标
        
        Args:
            trace_id: 追踪ID
            metrics: 指标数据
        """
        if trace_id not in self.traces:
            return
        
        for key, value in metrics.items():
            if key in self.traces[trace_id]["metrics"]:
                self.traces[trace_id]["metrics"][key] += value
            else:
                self.traces[trace_id]["metrics"][key] = value

    def end_trace(self, trace_id: str):
        """
        结束追踪
        
        Args:
            trace_id: 追踪ID
        """
        if trace_id not in self.traces:
            return
        
        self.traces[trace_id]["end_time"] = time.time()
        self.traces[trace_id]["duration"] = self.traces[trace_id]["end_time"] - self.traces[trace_id]["start_time"]

    def get_trace(self, trace_id: str) -> Optional[Dict[str, Any]]:
        """
        获取追踪数据
        
        Args:
            trace_id: 追踪ID
            
        Returns:
            Optional[Dict[str, Any]]: 追踪数据
        """
        return self.traces.get(trace_id)

    def get_tenant_traces(self, tenant_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        获取租户的追踪数据
        
        Args:
            tenant_id: 租户ID
            limit: 限制数量
            
        Returns:
            List[Dict[str, Any]]: 追踪数据列表
        """
        traces = []
        for trace in self.traces.values():
            if trace["tenant_id"] == tenant_id:
                traces.append(trace)
        
        # 按时间排序，返回最近的
        traces.sort(key=lambda x: x["start_time"], reverse=True)
        return traces[:limit]

    def cleanup_old_traces(self, hours: int = 24):
        """
        清理旧追踪数据
        
        Args:
            hours: 保留小时数
        """
        cutoff_time = time.time() - (hours * 3600)
        
        for trace_id in list(self.traces.keys()):
            if self.traces[trace_id]["start_time"] < cutoff_time:
                del self.traces[trace_id]


# 全局追踪器实例
tracer = Tracer()