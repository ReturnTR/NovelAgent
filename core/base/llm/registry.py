"""
LLM Provider 注册表

管理 LLM Provider 的注册和获取
"""

from typing import Dict, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .base import LLMProvider

# Provider 注册表
_providers: Dict[str, "LLMProvider"] = {}

# 当前激活的 provider
_current_provider_name: Optional[str] = None


def register_provider(name: str, provider: "LLMProvider") -> None:
    """
    注册 LLM Provider

    Args:
        name: provider 名称 (如 "openai", "anthropic")
        provider: LLMProvider 实例
    """
    global _current_provider_name
    _providers[name] = provider
    if _current_provider_name is None:
        _current_provider_name = name


def get_provider(name: Optional[str] = None) -> Optional["LLMProvider"]:
    """
    获取 Provider 实例

    Args:
        name: provider 名称，不提供则返回当前激活的

    Returns:
        LLMProvider 实例
    """
    if name is None:
        name = _current_provider_name
    return _providers.get(name)


def get_current_llm() -> Optional["LLMProvider"]:
    """
    获取当前激活的 LLM

    Returns:
        当前 LLMProvider
    """
    return get_provider(_current_provider_name)


def list_providers() -> list:
    """
    列出所有已注册的 provider

    Returns:
        provider 名称列表
    """
    return list(_providers.keys())


def set_current_provider(name: str) -> bool:
    """
    设置当前激活的 provider

    Args:
        name: provider 名称

    Returns:
        是否设置成功
    """
    global _current_provider_name
    if name in _providers:
        _current_provider_name = name
        return True
    return False
