"""Token 计数与截断"""

import re


def count_tokens(text: str) -> int:
    """
    估算文本的 token 数

    规则：中文约 1.5 token/字，英文约 1 token/word，标点约 1 token
    """
    if not text:
        return 0

    chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
    non_chinese = re.sub(r'[\u4e00-\u9fff]', '', text)
    english_words = len(non_chinese.split())

    return int(chinese_chars * 1.5 + english_words * 1.3)


def truncate_to_tokens(text: str, max_tokens: int) -> str:
    """
    按预估 token 数截断文本

    保留头部（system prompt 核心部分），截断尾部（RAG/记忆等可压缩部分）
    """
    if count_tokens(text) <= max_tokens:
        return text

    # 按字符比例估算截断位置
    ratio = max_tokens / max(count_tokens(text), 1)
    cut_pos = int(len(text) * ratio * 0.95)  # 留5%余量
    return text[:cut_pos] + "\n\n[...内容过长已截断...]"
