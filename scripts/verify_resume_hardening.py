"""Dependency-isolated regression checks for TWO production modules only.

Run in a clone: python scripts/verify_resume_hardening.py --source-dir SERVER/app/v2
No database, network, paid service, or full-app claim. AST extraction loads the
actual production functions/classes without importing unrelated application
packages; database, retrieval, and provider resources are explicit unit doubles.
Run the repository's complete pytest/HTTP/browser suites separately before merge.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import logging
import os
from pathlib import Path
import re
import sys
import time
import unittest
from dataclasses import dataclass
from types import ModuleType, SimpleNamespace

SOURCE_DIR: Path


def load_unit(path: Path, names: set[str], env: dict):
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    selected = []
    for node in tree.body:
        name = getattr(node, "name", None)
        targets = {x.id for x in node.targets if isinstance(x, ast.Name)} if isinstance(node, ast.Assign) else set()
        if name in names or targets & names:
            selected.append(node)
    module = ModuleType("_resume_hardening_" + path.stem)
    module.__dict__.update(env)
    sys.modules[module.__name__] = module
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(path), "exec", dont_inherit=True), module.__dict__)
    return module.__dict__


class CultureDatabaseReached(RuntimeError):
    pass


class SentinelDB:
    def query(self, _model):
        raise CultureDatabaseReached("Expected culture/product path reached")


class Provider:
    def __init__(self, fail=False):
        self.closed = 0
        self.fail = fail

    def close(self):
        self.closed += 1
        if self.fail:
            raise RuntimeError("UNIT_CLOSE_FAILURE")


class CultureRouting(unittest.TestCase):
    def setUp(self):
        env = load_unit(SOURCE_DIR / "culture.py", {"culture_reply", "_EVIDENCE_INTENT"}, {"re": re, "Horse": object})
        self.answer = env["culture_reply"]

    def test_original_text_precedes_story_intent(self):
        self.assertIsNone(self.answer(SentinelDB(), "给我讲故事，但请先列出赤兔的原文"))

    def test_historical_record_precedes_personality(self):
        self.assertIsNone(self.answer(SentinelDB(), "介绍乌骓的性格，史籍里怎样记载？"))

    def test_literature_quote_precedes_playful_intent(self):
        self.assertIsNone(self.answer(SentinelDB(), "聊聊的卢，请给文献和引文"))

    def test_traditional_evidence_intent(self):
        self.assertIsNone(self.answer(SentinelDB(), "聊聊赤兔的史書記載，提供出處與證據"))

    def test_explicit_evidence_in_shopping_question(self):
        self.assertIsNone(self.answer(SentinelDB(), "周边文案关于赤兔的说法有证据吗？"))

    def test_existing_factual_intent(self):
        self.assertIsNone(self.answer(SentinelDB(), "赤兔的性格有史料出处吗？"))

    def test_ordinary_personality_stays_available(self):
        with self.assertRaises(CultureDatabaseReached):
            self.answer(SentinelDB(), "我重视责任，哪匹马适合我？")

    def test_ordinary_shopping_stays_available(self):
        with self.assertRaises(CultureDatabaseReached):
            self.answer(SentinelDB(), "推荐赤兔周边，预算600元")

    def test_ordinary_story_stays_available(self):
        with self.assertRaises(CultureDatabaseReached):
            self.answer(SentinelDB(), "陪我聊聊，讲故事")

    def test_plain_evidence_question_is_not_culture(self):
        self.assertIsNone(self.answer(SentinelDB(), "赤兔最早的可核对记载是什么？"))


class AgentLifecycle(unittest.TestCase):
    def make_agent(self, fail_tool=None, close_fails=False, with_provider=True, attach_on_call=False):
        env = load_unit(
            SOURCE_DIR / "research.py", {"ResearchPolicy", "ResearchAgent"},
            {"dataclass": dataclass, "time": time, "os": os, "Path": Path,
             "logger": logging.getLogger("resume_hardening_unit"),
             "KnowledgeRepository": lambda _db: SimpleNamespace(snapshot="unit-snapshot", editorial=[])}
        )
        agent = env["ResearchAgent"](None)
        provider = Provider(close_fails)
        if with_provider:
            agent.provider = provider

        def call(tool, arguments):
            if attach_on_call:
                agent.provider = provider
            if tool == fail_tool:
                raise ValueError("UNIT_RESEARCH_FAILURE")
            if tool == "search_entities":
                result = []
            elif tool == "search_evidence":
                result = {"results": []}
            else:
                result = {}
            agent.trace.append({"tool": tool, "arguments": arguments, "output": result})
            return result
        agent.call = call
        return agent, provider

    def test_success_closes_provider_once(self):
        agent, provider = self.make_agent()
        self.assertEqual(agent.run("unit") ["mode"], "RULE_BASED")
        self.assertEqual(provider.closed, 1)

    def test_retrieval_exception_closes_provider(self):
        agent, provider = self.make_agent(fail_tool="search_evidence")
        with self.assertRaisesRegex(ValueError, "UNIT_RESEARCH_FAILURE"):
            agent.run("unit")
        self.assertEqual(provider.closed, 1)

    def test_late_comparison_exception_closes_provider(self):
        agent, provider = self.make_agent(fail_tool="compare_sources")
        with self.assertRaisesRegex(ValueError, "UNIT_RESEARCH_FAILURE"):
            agent.run("unit")
        self.assertEqual(provider.closed, 1)

    def test_lazily_created_provider_closed_on_early_error(self):
        agent, provider = self.make_agent(fail_tool="search_entities", with_provider=False, attach_on_call=True)
        with self.assertRaisesRegex(ValueError, "UNIT_RESEARCH_FAILURE"):
            agent.run("unit")
        self.assertEqual(provider.closed, 1)

    def test_close_failure_does_not_discard_success(self):
        agent, provider = self.make_agent(close_fails=True)
        with self.assertLogs("resume_hardening_unit", level="WARNING"):
            result = agent.run("unit")
        self.assertEqual(result["mode"], "RULE_BASED")
        self.assertEqual(provider.closed, 1)

    def test_close_failure_does_not_mask_research_error(self):
        agent, provider = self.make_agent(fail_tool="search_evidence", close_fails=True)
        with self.assertLogs("resume_hardening_unit", level="WARNING"):
            with self.assertRaisesRegex(ValueError, "UNIT_RESEARCH_FAILURE"):
                agent.run("unit")
        self.assertEqual(provider.closed, 1)

    def test_no_provider_remains_valid(self):
        agent, provider = self.make_agent(with_provider=False)
        self.assertEqual(agent.run("unit")["model"], None)
        self.assertEqual(provider.closed, 0)

    def test_closed_provider_reference_cleared(self):
        agent, provider = self.make_agent()
        agent.run("unit")
        self.assertIsNone(agent.provider)
        self.assertEqual(provider.closed, 1)


def main():
    global SOURCE_DIR
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    SOURCE_DIR = args.source_dir.resolve(strict=True)
    suite = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromTestCase(c) for c in (CultureRouting, AgentLifecycle))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    summary = {"validation_level": "DEPENDENCY_ISOLATED_PRODUCTION_FUNCTIONS",
               "tests_run": result.testsRun, "failures": len(result.failures), "errors": len(result.errors),
               "failed_tests": [str(t) for t, _ in result.failures],
               "error_tests": [str(t) for t, _ in result.errors],
               "external_model_calls": 0, "network_calls": 0, "database_writes": 0,
               "full_repository_suite_rerun": False,
               "modules": {n: hashlib.sha256((SOURCE_DIR/n).read_bytes()).hexdigest() for n in ("culture.py", "research.py")}}
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
