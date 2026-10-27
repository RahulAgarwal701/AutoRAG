import ast
import operator
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import httpx

from app.core.config import Settings, get_settings


class ToolError(RuntimeError):
    pass


_BINARY_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_UNARY_OPERATORS = {ast.UAdd: operator.pos, ast.USub: operator.neg}


def calculate(expression: str) -> float | int:
    if len(expression) > 200:
        raise ToolError("Calculator expression is too long")
    tree = ast.parse(expression, mode="eval")

    def evaluate(node: ast.AST) -> float | int:
        if isinstance(node, ast.Expression):
            return evaluate(node.body)
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            return node.value
        if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY_OPERATORS:
            return _UNARY_OPERATORS[type(node.op)](evaluate(node.operand))
        if isinstance(node, ast.BinOp) and type(node.op) in _BINARY_OPERATORS:
            left, right = evaluate(node.left), evaluate(node.right)
            if isinstance(node.op, ast.Pow) and abs(right) > 10:
                raise ToolError("Calculator exponent is too large")
            result = _BINARY_OPERATORS[type(node.op)](left, right)
            if abs(result) > 1e100:
                raise ToolError("Calculator result is too large")
            return result
        raise ToolError("Only numeric arithmetic is allowed")

    return evaluate(tree)


@dataclass(frozen=True)
class ToolResult:
    name: str
    output: str


class ToolExecutor:
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    async def run(self, tools: Sequence[Mapping[str, Any]], query: str) -> ToolResult | None:
        enabled = [tool for tool in tools if tool.get("enabled", True)]
        lowered = query.strip().lower()
        calculator = next((tool for tool in enabled if tool.get("type") == "calculator"), None)
        if calculator is not None and lowered.startswith("calculate "):
            expression = query.strip()[len("calculate ") :]
            return ToolResult("calculator", str(calculate(expression)))

        web_search = next((tool for tool in enabled if tool.get("type") == "web_search"), None)
        if web_search is not None and lowered.startswith("search web for "):
            search_query = query.strip()[len("search web for ") :]
            return await self._web_search(search_query)

        for tool in enabled:
            if tool.get("type") != "webhook":
                continue
            name = str(tool.get("name", "")).strip()
            prefix = f"use {name.lower()}:"
            if name and lowered.startswith(prefix):
                payload = query.strip()[len(prefix) :].strip()
                return await self._webhook(name, str(tool.get("url", "")), payload)
        return None

    async def _web_search(self, query: str) -> ToolResult:
        if not self._settings.web_search_url:
            raise ToolError("WEB_SEARCH_URL is not configured")
        headers: dict[str, str] = {}
        if self._settings.web_search_api_key is not None:
            headers["Authorization"] = (
                f"Bearer {self._settings.web_search_api_key.get_secret_value()}"
            )
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                self._settings.web_search_url,
                json={"query": query},
                headers=headers,
            )
            response.raise_for_status()
        return ToolResult("web_search", response.text[:10_000])

    async def _webhook(self, name: str, url: str, query: str) -> ToolResult:
        parsed = urlparse(url)
        allowed = {host.lower() for host in self._settings.tool_webhook_allowed_hosts}
        if parsed.scheme != "https" or not parsed.hostname:
            raise ToolError("Webhook tools must use HTTPS")
        if parsed.hostname.lower() not in allowed:
            raise ToolError("Webhook host is not in TOOL_WEBHOOK_ALLOWED_HOSTS")
        async with httpx.AsyncClient(timeout=10, follow_redirects=False) as client:
            response = await client.post(url, json={"query": query})
            response.raise_for_status()
        return ToolResult(name, response.text[:10_000])
