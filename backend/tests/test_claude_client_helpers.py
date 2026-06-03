from __future__ import annotations

import pytest

from app.adapters.llm._json_parsing import parse_json_object


class TestParseJsonObject:
    def test_plain_json(self) -> None:
        assert parse_json_object('{"a": 1}') == {"a": 1}

    def test_strips_markdown_fence_json(self) -> None:
        wrapped = '```json\n{"a": 1}\n```'
        assert parse_json_object(wrapped) == {"a": 1}

    def test_strips_bare_markdown_fence(self) -> None:
        wrapped = '```\n{"a": 1}\n```'
        assert parse_json_object(wrapped) == {"a": 1}

    def test_strips_surrounding_prose(self) -> None:
        noisy = 'Sure! Here is your answer: {"a": 1} hope it helps.'
        assert parse_json_object(noisy) == {"a": 1}

    def test_nested_object(self) -> None:
        text = '{"outer": {"inner": [1, 2]}}'
        assert parse_json_object(text) == {"outer": {"inner": [1, 2]}}

    def test_raises_when_no_json(self) -> None:
        with pytest.raises(ValueError):
            parse_json_object("there is no json here at all")
