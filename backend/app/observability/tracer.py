"""全链路追踪"""

import time
import uuid
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Span:
    name: str
    trace_id: str
    span_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    metadata: dict = field(default_factory=dict)

    def finish(self, **meta):
        self.end_time = time.time()
        self.metadata.update(meta)

    @property
    def duration_ms(self) -> float:
        if self.end_time:
            return (self.end_time - self.start_time) * 1000
        return 0


class ConversationTracer:
    """
    一次对话的全链路追踪：
    对话ID → 意图识别(耗时) → RAG检索(命中数) → LLM调用(Token/耗时) → 总耗时/总成本
    """

    def __init__(self, session_id: str):
        self.trace_id = uuid.uuid4().hex
        self.session_id = session_id
        self.spans: list[Span] = []

    def start_span(self, name: str) -> Span:
        span = Span(name=name, trace_id=self.trace_id)
        self.spans.append(span)
        return span

    def summary(self) -> dict:
        return {
            "trace_id": self.trace_id,
            "session_id": self.session_id,
            "total_ms": sum(s.duration_ms for s in self.spans),
            "spans": [
                {
                    "name": s.name,
                    "duration_ms": round(s.duration_ms, 2),
                    **s.metadata,
                }
                for s in self.spans
            ],
        }
