from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Any, TypeVar
from urllib.parse import urlsplit

from pydantic import BaseModel

from .ai_events import (
    AIResearchResult,
    OpenAIEventResearchProvider,
    OpenAIQuotaExceeded,
    PROMPT_VERSION,
    _canonical_url,
    _retain_grounded_items,
)


DEFAULT_CODEX_TIMEOUT_SECONDS = 300
DEFAULT_CODEX_MODEL = "gpt-5.6-sol"
CODEX_APP_BINARY = Path("/Applications/ChatGPT.app/Contents/Resources/codex")

SchemaT = TypeVar("SchemaT", bound=BaseModel)


@dataclass(frozen=True)
class CodexCommandResult:
    returncode: int
    stdout: str
    stderr: str


CodexExecutor = Callable[
    [list[str], str | None, int, dict[str, str]],
    CodexCommandResult,
]


class CodexCliEventResearchProvider(OpenAIEventResearchProvider):
    """Source-grounded event research through a local ChatGPT-authenticated CLI."""

    name = "codex_cli"
    _request_lock = Lock()

    def __init__(
        self,
        *,
        binary: str | None = None,
        model: str | None = None,
        timeout_seconds: int | None = None,
        executor: CodexExecutor | None = None,
        authenticated: bool | None = None,
    ) -> None:
        self.binary = binary or _find_codex_binary()
        self.requested_model = (
            model
            or os.getenv("PRISM_CODEX_MODEL", "").strip()
            or DEFAULT_CODEX_MODEL
        )
        self.model = self.requested_model
        configured_timeout = timeout_seconds or _configured_timeout_seconds(
            os.getenv("PRISM_CODEX_TIMEOUT_SECONDS", "")
        )
        self.timeout_seconds = max(30, min(configured_timeout, 900))
        self.executor = executor or _execute_codex
        self._configured = (
            authenticated
            if authenticated is not None
            else self._probe_chatgpt_login()
        )
        self.configuration_error = (
            None
            if self._configured
            else "Codex CLI is unavailable or not signed in with ChatGPT"
        )

    @property
    def configured(self) -> bool:
        return self._configured

    def _probe_chatgpt_login(self) -> bool:
        if not self.binary:
            return False
        try:
            result = self.executor(
                [self.binary, "login", "status"],
                None,
                10,
                _safe_codex_environment(),
            )
        except (OSError, subprocess.SubprocessError):
            return False
        combined = f"{result.stdout}\n{result.stderr}".lower()
        return result.returncode == 0 and "logged in" in combined

    def _request(
        self,
        *,
        schema_model: type[SchemaT],
        schema_name: str,
        instructions: str,
        input_text: str,
        max_tool_calls: int,
    ) -> AIResearchResult:
        del max_tool_calls
        if not self.configured or not self.binary:
            raise RuntimeError(self.configuration_error or "Codex CLI is unavailable")
        if not self._request_lock.acquire(blocking=False):
            raise RuntimeError("Another Codex AI research job is already running")
        try:
            return self._run_structured_research(
                schema_model=schema_model,
                schema_name=schema_name,
                instructions=instructions,
                input_text=input_text,
            )
        finally:
            self._request_lock.release()

    def _run_structured_research(
        self,
        *,
        schema_model: type[SchemaT],
        schema_name: str,
        instructions: str,
        input_text: str,
    ) -> AIResearchResult:
        with tempfile.TemporaryDirectory(prefix="prism-codex-") as directory:
            runner_dir = Path(directory)
            schema_path = runner_dir / f"{schema_name}.schema.json"
            output_path = runner_dir / f"{schema_name}.result.json"
            schema_path.write_text(
                json.dumps(schema_model.model_json_schema(), sort_keys=True),
                encoding="utf-8",
            )
            prompt = (
                f"{instructions}\n\n"
                "Execution boundary: use web search for this research task. "
                "Do not run shell commands, edit files, call connectors, or access local "
                "user data. Return only JSON that matches the supplied output schema. "
                "For every non-empty result, every source URL or source_references URL "
                "must be an exact public URL retrieved with web search during this run. "
                f"Application prompt version: {PROMPT_VERSION}.\n\n"
                f"Research request:\n{input_text}"
            )
            command = [
                self.binary,
                "--search",
                "-C",
                str(runner_dir),
                "-s",
                "read-only",
                "-a",
                "never",
                "exec",
                "--ephemeral",
                "--skip-git-repo-check",
                "--ignore-user-config",
                "--ignore-rules",
                "--color",
                "never",
                "--json",
                "--output-schema",
                str(schema_path),
                "--output-last-message",
                str(output_path),
            ]
            command.extend(["--model", self.requested_model])
            command.append("-")
            result = self.executor(
                command,
                prompt,
                self.timeout_seconds,
                _safe_codex_environment(),
            )
            if result.returncode != 0:
                _raise_codex_error(result)
            if not output_path.exists():
                raise RuntimeError("Codex CLI returned no structured output file")
            try:
                payload = schema_model.model_validate_json(
                    output_path.read_text(encoding="utf-8")
                )
            except (OSError, ValueError, TypeError) as error:
                raise RuntimeError(
                    "Codex CLI returned invalid structured output"
                ) from error

            events = _parse_jsonl(result.stdout)
            if not _contains_web_search(events):
                raise RuntimeError(
                    "Codex CLI completed without a recorded web search"
                )
            searched_sources = _sources_from_web_search(events)
            payload_urls = _source_urls_from_payload(payload)
            if searched_sources:
                source_map = {
                    _canonical_url(source["url"]): source
                    for source in searched_sources
                }
                sources = [
                    source_map[canonical]
                    for url in payload_urls
                    if (canonical := _canonical_url(url)) in source_map
                ]
            else:
                # Current CLI JSONL records the web-search action but may omit
                # result URLs. The schema-bound final output still preserves the
                # exact URLs selected from that search.
                sources = [
                    {
                        "url": url,
                        "title": urlsplit(url).netloc,
                    }
                    for url in payload_urls
                    if _canonical_url(url)
                ]
            sources = _dedupe_sources(sources)
            payload = _retain_grounded_items(payload, sources)
            metadata = _codex_metadata(events)
            return AIResearchResult(
                payload=payload,
                response_id=metadata["response_id"],
                model=metadata["model"] or self.model,
                sources=sources,
                usage=metadata["usage"],
            )


def _find_codex_binary() -> str | None:
    configured = os.getenv("PRISM_CODEX_BIN", "").strip()
    if configured:
        path = Path(configured).expanduser()
        return str(path) if path.is_file() else None
    discovered = shutil.which("codex")
    if discovered:
        return discovered
    return str(CODEX_APP_BINARY) if CODEX_APP_BINARY.is_file() else None


def _configured_timeout_seconds(value: str) -> int:
    try:
        return int(value) if value.strip() else DEFAULT_CODEX_TIMEOUT_SECONDS
    except ValueError:
        return DEFAULT_CODEX_TIMEOUT_SECONDS


def _safe_codex_environment() -> dict[str, str]:
    allowed = {
        "HOME",
        "USER",
        "LOGNAME",
        "PATH",
        "TMPDIR",
        "LANG",
        "LC_ALL",
        "TERM",
        "CODEX_HOME",
        "HTTPS_PROXY",
        "HTTP_PROXY",
        "ALL_PROXY",
        "NO_PROXY",
    }
    environment = {
        key: value
        for key, value in os.environ.items()
        if key in allowed and value
    }
    environment.setdefault("PATH", "/usr/bin:/bin:/usr/sbin:/sbin")
    environment.setdefault("LANG", "en_US.UTF-8")
    return environment


def _execute_codex(
    command: list[str],
    prompt: str | None,
    timeout_seconds: int,
    environment: dict[str, str],
) -> CodexCommandResult:
    process = subprocess.Popen(
        command,
        stdin=subprocess.PIPE if prompt is not None else subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=environment,
        start_new_session=True,
    )
    try:
        stdout, stderr = process.communicate(
            input=prompt,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as error:
        os.killpg(process.pid, signal.SIGTERM)
        try:
            process.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.communicate()
        raise RuntimeError(
            f"Codex CLI research exceeded {timeout_seconds} seconds"
        ) from error
    return CodexCommandResult(
        returncode=process.returncode,
        stdout=stdout,
        stderr=stderr,
    )


def _raise_codex_error(result: CodexCommandResult) -> None:
    combined = f"{result.stdout}\n{result.stderr}".strip()
    lowered = combined.lower()
    quota_markers = (
        "rate limit",
        "usage limit",
        "quota",
        "credits exhausted",
        "credit balance",
        "limit reached",
    )
    if any(marker in lowered for marker in quota_markers):
        raise OpenAIQuotaExceeded(
            "Codex or ChatGPT usage limit reached; AI research stopped"
        )
    message = _last_nonempty_line(combined)
    raise RuntimeError(
        f"Codex CLI research failed: {message or 'unknown CLI error'}"
    )


def _parse_jsonl(value: str) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for line in value.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict):
            events.append(item)
    return events


def _contains_web_search(events: list[dict[str, Any]]) -> bool:
    return any(_node_has_search_type(event) for event in events)


def _node_has_search_type(value: Any) -> bool:
    if isinstance(value, dict):
        node_type = str(value.get("type", "")).lower()
        if node_type in {"web_search", "web_search_call"}:
            return True
        return any(_node_has_search_type(item) for item in value.values())
    if isinstance(value, list):
        return any(_node_has_search_type(item) for item in value)
    return False


def _sources_from_web_search(
    events: list[dict[str, Any]],
) -> list[dict[str, str]]:
    sources: list[dict[str, str]] = []
    for event in events:
        _collect_search_sources(event, False, sources)
    return _dedupe_sources(sources)


def _collect_search_sources(
    value: Any,
    inside_search: bool,
    sources: list[dict[str, str]],
) -> None:
    if isinstance(value, dict):
        node_type = str(value.get("type", "")).lower()
        now_inside_search = inside_search or node_type in {
            "web_search",
            "web_search_call",
        }
        if now_inside_search:
            url = value.get("url")
            if isinstance(url, str) and _canonical_url(url):
                sources.append(
                    {
                        "url": url,
                        "title": str(value.get("title") or urlsplit(url).netloc),
                    }
                )
        for item in value.values():
            _collect_search_sources(item, now_inside_search, sources)
    elif isinstance(value, list):
        for item in value:
            _collect_search_sources(item, inside_search, sources)


def _source_urls_from_payload(payload: BaseModel) -> list[str]:
    urls: list[str] = []

    def collect(value: Any) -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                if key == "source_urls" and isinstance(item, list):
                    urls.extend(url for url in item if isinstance(url, str))
                elif key == "source_references" and isinstance(item, list):
                    urls.extend(
                        str(reference["url"])
                        for reference in item
                        if isinstance(reference, dict)
                        and isinstance(reference.get("url"), str)
                    )
                else:
                    collect(item)
        elif isinstance(value, list):
            for item in value:
                collect(item)

    collect(payload.model_dump(mode="json"))
    return list(dict.fromkeys(urls))


def _codex_metadata(events: list[dict[str, Any]]) -> dict[str, Any]:
    response_id = ""
    model = ""
    usage: dict[str, Any] = {}
    for event in events:
        if not response_id:
            response_id = str(
                event.get("thread_id")
                or event.get("session_id")
                or event.get("id")
                or ""
            )
        if not model and isinstance(event.get("model"), str):
            model = event["model"]
        candidate_usage = event.get("usage")
        if isinstance(candidate_usage, dict):
            usage = candidate_usage
        item = event.get("item")
        if isinstance(item, dict):
            if not model and isinstance(item.get("model"), str):
                model = item["model"]
            candidate_usage = item.get("usage")
            if isinstance(candidate_usage, dict):
                usage = candidate_usage
    return {
        "response_id": response_id,
        "model": model,
        "usage": usage,
    }


def _dedupe_sources(
    sources: list[dict[str, str]],
) -> list[dict[str, str]]:
    unique: dict[str, dict[str, str]] = {}
    for source in sources:
        canonical = _canonical_url(source.get("url", ""))
        if canonical:
            unique[canonical] = {
                "url": source["url"],
                "title": source.get("title", ""),
            }
    return list(unique.values())


def _last_nonempty_line(value: str) -> str:
    lines = [line.strip() for line in value.splitlines() if line.strip()]
    return lines[-1][:500] if lines else ""
