#!/usr/bin/env python3
"""RPENT_REASONING_EFFORT 旋钮单测(离线,不发请求)。

api_loop._build_model_settings 的三段行为:
  1. env 未设 → 与旧行为完全一致(Anthropic 缓存设置 / plain ModelSettings)
  2. env={low,high,max} + OpenAIChatModel → OpenAIChatModelSettings 直传
     (max 不在 Thinking 枚举里,必须走显式字段)
  3. env 非法值或非 openai 模型 → fail-fast ValueError(模板会把垃圾值静默
     渲染成 Max,绝不能放过)
"""
import os
import sys
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pydantic_ai.models.anthropic import AnthropicModel, AnthropicModelSettings
from pydantic_ai.models.openai import OpenAIChatModel, OpenAIChatModelSettings
from pydantic_ai.providers import Provider

from rpent.planner.api_loop import _build_model_settings


class _DummyProvider(Provider):
    """构造期只需要 client 对象存在,永远不会真的发请求。"""

    @property
    def name(self):
        return "dummy"

    @property
    def base_url(self):
        return "http://127.0.0.1:1"

    @property
    def client(self):
        return MagicMock()


ANTH = AnthropicModel("glm-5.3-flash", provider=_DummyProvider())
OAI = OpenAIChatModel("zai-org/GLM-5.3-Flash", provider=_DummyProvider())


def _env(v):
    return pytest.MonkeyPatch if v is _env else None


def test_unset_env_matches_old_behavior(monkeypatch):
    monkeypatch.delenv("RPENT_REASONING_EFFORT", raising=False)
    s_anth = _build_model_settings(ANTH, 24576)
    assert s_anth["anthropic_cache_instructions"] is True  # 键存在即类型正确
    s_oai = _build_model_settings(OAI, 24576)
    assert "openai_reasoning_effort" not in s_oai  # plain,无 effort 字段
    assert s_oai["max_tokens"] == 24576


@pytest.mark.parametrize("effort", ["low", "high", "max"])
def test_valid_effort_openai(monkeypatch, effort):
    monkeypatch.setenv("RPENT_REASONING_EFFORT", effort)
    s = _build_model_settings(OAI, 24576)
    # TypedDict 运行时就是 dict:断 effort 键值,且不带 anthropic 缓存键
    assert s["openai_reasoning_effort"] == effort
    assert s["max_tokens"] == 24576
    assert "anthropic_cache_instructions" not in s


@pytest.mark.parametrize("bad", ["medium", "", "MAX", "5", "low "])
def test_invalid_effort_fail_fast(monkeypatch, bad):
    monkeypatch.setenv("RPENT_REASONING_EFFORT", bad)
    with pytest.raises(ValueError):
        _build_model_settings(OAI, 24576)


def test_effort_on_anthropic_rejected(monkeypatch):
    # 远端 GLM(anthropic 端点)不受此旋钮影响:误用时 fail-fast 而不是静默
    monkeypatch.setenv("RPENT_REASONING_EFFORT", "max")
    with pytest.raises(ValueError):
        _build_model_settings(ANTH, 24576)
