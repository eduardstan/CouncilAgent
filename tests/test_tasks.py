"""Tests for tasks/profiles.py — TaskProfile dataclass and registry."""

from __future__ import annotations

import dataclasses

import pytest


def test_task_profile_has_required_fields() -> None:
    from tasks.profiles import TaskProfile

    profile = TaskProfile(
        name="test",
        description="A test task",
        answer_format="free",
    )
    assert profile.name == "test"
    assert profile.description == "A test task"
    assert profile.answer_format == "free"


def test_task_profile_is_frozen() -> None:
    from tasks.profiles import TaskProfile

    profile = TaskProfile(name="t", description="d", answer_format="numeric")
    with pytest.raises(dataclasses.FrozenInstanceError):
        profile.name = "other"  # type: ignore[misc]


def test_gsm8k_profile_is_registered() -> None:
    from tasks.profiles import REGISTRY

    assert "gsm8k" in REGISTRY
    gsm8k = REGISTRY["gsm8k"]
    assert gsm8k.name == "gsm8k"
    assert gsm8k.answer_format == "numeric"


def test_registry_profiles_are_valid() -> None:
    from tasks.profiles import REGISTRY, TaskProfile

    for name, profile in REGISTRY.items():
        assert isinstance(profile, TaskProfile)
        assert profile.name == name
        assert profile.answer_format in ("numeric", "free", "code", "json")


def test_task_profile_surface_overrides_default_empty() -> None:
    from tasks.profiles import TaskProfile

    profile = TaskProfile(name="t", description="d", answer_format="free")
    assert profile.surface_overrides == {}
