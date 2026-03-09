from __future__ import annotations

from math import log

import pytest

from src.core.skills.weight import SkillWeight, calculate_skill_weight, calculate_years_factor


def test_skill_weight__computes_expected_fields() -> None:
    skill = SkillWeight(name="python", years=3.0, certified=True)

    assert skill.name == "python"
    assert skill.years_factor == pytest.approx(log(1 + 3.0))
    assert skill.cert_bonus == pytest.approx(0.5)
    assert skill.weight == pytest.approx(calculate_skill_weight(3.0, True))
    assert skill.total_weight == pytest.approx(skill.weight)


def test_skill_weight__defaults_to_base_weight() -> None:
    skill = SkillWeight(name="fastapi")

    assert skill.years_factor == pytest.approx(0.0)
    assert skill.cert_bonus == pytest.approx(0.0)
    assert skill.weight == pytest.approx(1.0)


def test_calculate_years_factor__negative_years_clamps_to_zero() -> None:
    result = calculate_years_factor(-5.0)

    assert result == pytest.approx(0.0)
