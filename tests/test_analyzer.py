"""分析器模块测试"""
import pytest
from src.analyzer import LLMAnalyzer, RuleEngine, StreamingJsonParser
from src.models import FileInfo, AnalysisResult


class TestStreamingJsonParser:
    def test_feed_complete_json(self):
        parser = StreamingJsonParser()
        objects = parser.feed('{"file_path": "test.txt", "size_mb": 10.5, "reason": "old file", "risk_level": "Low"}')
        assert len(objects) == 1
        assert objects[0]["file_path"] == "test.txt"

    def test_feed_incomplete_json(self):
        parser = StreamingJsonParser()
        objects = parser.feed('{"file_path":')
        assert len(objects) == 0

    def test_feed_incremental(self):
        parser = StreamingJsonParser()
        parser.feed('{"file_path": "a.txt", "size_mb": 1.0,')
        objects = parser.feed('"reason": "test", "risk_level": "Low"}')
        assert len(objects) == 1
        assert objects[0]["file_path"] == "a.txt"

    def test_feed_multiple_objects(self):
        parser = StreamingJsonParser()
        chunk = (
            '{"file_path": "a.txt", "size_mb": 1.0, "reason": "r1", "risk_level": "Low"}'
            '{"file_path": "b.txt", "size_mb": 2.0, "reason": "r2", "risk_level": "Medium"}'
        )
        objects = parser.feed(chunk)
        assert len(objects) == 2

    def test_get_all_objects(self):
        parser = StreamingJsonParser()
        parser.feed('{"file_path": "a.txt", "size_mb": 1.0, "reason": "r", "risk_level": "Low"}')
        all_objs = parser.get_all_objects()
        assert len(all_objs) == 1

    def test_clear(self):
        parser = StreamingJsonParser()
        parser.feed('{"file_path": "a.txt", "size_mb": 1.0, "reason": "r", "risk_level": "Low"}')
        parser.clear()
        assert len(parser.get_all_objects()) == 0

    def test_parse_complete_json(self):
        parser = StreamingJsonParser()
        result = parser.parse_complete_json('{"key": "value"}')
        assert result == {"key": "value"}

    def test_parse_complete_json_with_markdown(self):
        parser = StreamingJsonParser()
        result = parser.parse_complete_json('```json\n{"key": "value"}\n```')
        assert result == {"key": "value"}

    def test_parse_complete_json_invalid(self):
        parser = StreamingJsonParser()
        result = parser.parse_complete_json('not json')
        assert result is None


class TestRuleEngine:
    def test_rule_engine_initialization(self):
        engine = RuleEngine()
        assert len(engine.rules) > 0

    def test_get_rules(self):
        engine = RuleEngine()
        rules = engine.get_rules()
        assert isinstance(rules, list)
        assert len(rules) > 0

    def test_add_rule(self):
        engine = RuleEngine()
        from src.models import RiskLevel
        initial_count = len(engine.rules)
        success = engine.add_rule({
            "name": "test_rule",
            "pattern": r"\.test$",
            "risk": RiskLevel.LOW,
            "reason": "test",
            "confidence": 0.8
        })
        assert success
        assert len(engine.rules) == initial_count + 1

    def test_add_rule_invalid(self):
        engine = RuleEngine()
        success = engine.add_rule({"name": "incomplete"})
        assert not success

    def test_clear_rules(self):
        engine = RuleEngine()
        engine.clear_rules()
        assert len(engine.rules) == 0

    def test_reset_to_default(self):
        engine = RuleEngine()
        engine.clear_rules()
        engine.reset_to_default()
        assert len(engine.rules) > 0
