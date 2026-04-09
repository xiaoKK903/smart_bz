"""安全护栏模块"""

from .input_filter import InputFilter
from .output_validator import OutputValidator
from .sensitive_words import sensitive_words

# 全局实例
input_filter = InputFilter(sensitive_words=sensitive_words)
output_validator = OutputValidator()

__all__ = ["input_filter", "output_validator"]