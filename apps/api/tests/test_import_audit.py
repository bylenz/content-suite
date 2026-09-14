"""Static import audit (6.2): provider SDKs stay inside adapter boundaries.

AST-based so it catches `import x`, `from x import y` and aliases anywhere in
`app/`. The rules: common AI provider SDKs (`openai`, `anthropic`, ...) may only
be imported inside `app/ai/providers/` adapters; `langfuse` only inside
`app/observability/langfuse_adapter.py`. Synthetic-violation tests below pin
the detector so an illegal import cannot pass unnoticed.
"""

import ast
from pathlib import Path

# SDK root import names with a dedicated single-file boundary outside ai/providers.
DEDICATED_SDK_BOUNDARIES: dict[str, tuple[str, ...]] = {
    "langfuse": ("app/observability/langfuse_adapter.py",),
}

# Common AI provider SDK roots; only importable inside `app/ai/providers/`.
# `google` covers the google-genai SDK namespace (`from google import genai`,
# `import google.genai`) and any `google.*` helper it ships with.
# Extend when a new provider adapter lands (the directory is the boundary, so
# new entries need no per-file mapping).
PROVIDER_SDK_ROOTS: frozenset[str] = frozenset(
    {"openai", "anthropic", "google", "litellm", "cohere", "mistralai", "groq"}
)

APP_ROOT = Path(__file__).resolve().parents[1] / "app"
PROVIDERS_DIR_PREFIX = "app/ai/providers/"


def _imported_roots(node: ast.AST) -> list[str]:
    if isinstance(node, ast.Import):
        return [alias.name.split(".")[0] for alias in node.names]
    if isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
        return [node.module.split(".")[0]]
    return []


def find_import_violations(relative_path: str, source: str) -> list[str]:
    """Return `path:line imports root` entries for SDK imports outside their boundary."""
    tree = ast.parse(source)
    violations: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Import | ast.ImportFrom):
            continue
        for root in _imported_roots(node):
            allowed = (
                relative_path in DEDICATED_SDK_BOUNDARIES[root]
                if root in DEDICATED_SDK_BOUNDARIES
                else relative_path.startswith(PROVIDERS_DIR_PREFIX)
                if root in PROVIDER_SDK_ROOTS
                else True
            )
            if not allowed:
                violations.append(f"{relative_path}:{node.lineno} imports {root}")
    return violations


def test_no_provider_sdk_imported_outside_adapter_boundaries() -> None:
    violations: list[str] = []
    for path in sorted(APP_ROOT.rglob("*.py")):
        relative = path.relative_to(APP_ROOT.parent).as_posix()
        violations.extend(find_import_violations(relative, path.read_text(encoding="utf-8")))
    assert not violations, f"provider SDK imported outside its adapter: {violations}"


def test_synthetic_provider_imports_are_detected_outside_providers() -> None:
    # Domain/router/service files importing a provider SDK (plain or aliased) fail.
    assert find_import_violations("app/ai/runner.py", "import openai") == [
        "app/ai/runner.py:1 imports openai"
    ]
    assert find_import_violations("app/brand_dna/service.py", "import openai as oai") == [
        "app/brand_dna/service.py:1 imports openai"
    ]
    assert find_import_violations(
        "app/ai/runner.py", "from anthropic import AsyncAnthropic"
    ) == ["app/ai/runner.py:1 imports anthropic"]
    # Google genai SDK style (`from google import genai`, `import google.genai`).
    assert find_import_violations("app/ai/runner.py", "from google import genai") == [
        "app/ai/runner.py:1 imports google"
    ]
    assert find_import_violations("app/brand_dna/service.py", "import google.genai") == [
        "app/brand_dna/service.py:1 imports google"
    ]


def test_synthetic_provider_imports_are_allowed_inside_providers() -> None:
    assert find_import_violations(
        "app/ai/providers/openai_adapter.py", "from openai import AsyncOpenAI"
    ) == []
    assert find_import_violations(
        "app/ai/providers/anthropic_adapter.py", "import anthropic"
    ) == []
    assert find_import_violations(
        "app/ai/providers/google_adapter.py", "from google import genai"
    ) == []


def test_synthetic_langfuse_boundary_is_single_file() -> None:
    assert find_import_violations(
        "app/observability/langfuse_adapter.py", "from langfuse import Langfuse"
    ) == []
    assert find_import_violations("app/ai/providers/langfuse_adapter.py", "import langfuse") == [
        "app/ai/providers/langfuse_adapter.py:1 imports langfuse"
    ]
    assert find_import_violations("app/ai/runner.py", "import langfuse") == [
        "app/ai/runner.py:1 imports langfuse"
    ]


def test_unrelated_and_relative_imports_are_not_flagged() -> None:
    assert find_import_violations("app/ai/runner.py", "from app.config import Settings") == []
    assert find_import_violations("app/ai/runner.py", "from . import ports") == []
    assert find_import_violations("app/health/router.py", "from fastapi import APIRouter") == []


def test_ai_providers_package_files_are_expected() -> None:
    # 006 added the OpenAI embeddings adapter; spec 04 added the text adapter;
    # the 008 follow-up added the GLM vision adapter. The directory remains
    # the only SDK boundary (enforced by the tests above).
    providers_dir = APP_ROOT / "ai" / "providers"
    found = (p.relative_to(APP_ROOT.parent).as_posix() for p in providers_dir.rglob("*.py"))
    assert sorted(found) == [
        "app/ai/providers/__init__.py",
        "app/ai/providers/glm_vision.py",
        "app/ai/providers/openai_embeddings.py",
        "app/ai/providers/openai_text.py",
    ]
