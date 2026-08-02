from __future__ import annotations

import ast
import asyncio
import textwrap
from pathlib import Path
from types import SimpleNamespace
from typing import Any

USAGE_GUIDE = Path(__file__).parents[1] / "docsrc" / "user" / "USAGE_GUIDE.md"
GETTING_STARTED = Path(__file__).parents[1] / "docsrc" / "user" / "GETTING_STARTED.md"


def _python_blocks(markdown: str) -> list[str]:
    blocks: list[str] = []
    current: list[str] | None = None
    for line in markdown.splitlines():
        stripped = line.strip()
        if current is None and stripped.startswith("```python"):
            current = []
        elif current is not None and stripped == "```":
            blocks.append(textwrap.dedent("\n".join(current)))
            current = None
        elif current is not None:
            current.append(line)
    assert current is None, "unclosed Python fence"
    return blocks


class _OutcomeUnknownError(Exception):
    pass


class _ReadbackError(Exception):
    pass


def _without_imports_and_runner(block: str) -> ast.Module:
    tree = ast.parse(block)
    tree.body = [
        node
        for node in tree.body
        if not isinstance(node, (ast.Import, ast.ImportFrom))
        and not (
            isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Call)
            and isinstance(node.value.func, ast.Attribute)
            and isinstance(node.value.func.value, ast.Name)
            and node.value.func.value.id == "asyncio"
            and node.value.func.attr == "run"
        )
    ]
    ast.fix_missing_locations(tree)
    return tree


class _ExpansionClient:
    def __init__(self, *, fail_write_at: int | None = None, fail_read_at: int | None = None) -> None:
        self.fail_write_at = fail_write_at
        self.fail_read_at = fail_read_at
        self.read_count = 0
        self.writes: list[list[int]] = []

    async def __aenter__(self) -> _ExpansionClient:
        return self

    async def __aexit__(self, *_args: object) -> None:
        return None

    async def read(self, unit_no: int, address: int, count: int, *, data_format: str) -> list[int]:
        assert (unit_no, address, count) == (0, 10, 4)
        assert data_format == "U"
        self.read_count += 1
        if self.read_count == self.fail_read_at:
            raise _ReadbackError
        return [10, 11, 12, 13]

    async def write(self, unit_no: int, address: int, values: list[int], *, data_format: str) -> None:
        assert (unit_no, address) == (0, 10)
        assert data_format == "U"
        self.writes.append(list(values))
        if len(self.writes) == self.fail_write_at:
            raise _OutcomeUnknownError


class _TypedClient:
    def __init__(self, *, fail_write_at: int | None = None, fail_read_at: int | None = None) -> None:
        self.fail_write_at = fail_write_at
        self.fail_read_at = fail_read_at
        self.read_count = 0
        self.writes: list[int] = []

    async def __aenter__(self) -> _TypedClient:
        return self

    async def __aexit__(self, *_args: object) -> None:
        return None

    async def read(self, _client: Any, _device: str, _dtype: str) -> int:
        self.read_count += 1
        if self.read_count == self.fail_read_at:
            raise _ReadbackError
        return 77

    async def write(self, _client: Any, _device: str, _dtype: str, value: int) -> None:
        self.writes.append(value)
        if len(self.writes) == self.fail_write_at:
            raise _OutcomeUnknownError


async def _run_expansion_example(block: str, client: _ExpansionClient) -> None:
    async def open_and_connect(_options: Any) -> _ExpansionClient:
        return client

    async def read_buffer(
        _client: Any,
        unit_no: int,
        address: int,
        count: int,
        *,
        data_format: str,
    ) -> list[int]:
        return await client.read(unit_no, address, count, data_format=data_format)

    async def write_buffer(
        _client: Any,
        unit_no: int,
        address: int,
        values: list[int],
        *,
        data_format: str,
    ) -> None:
        await client.write(unit_no, address, values, data_format=data_format)

    namespace = {
        "HostLinkConnectionOptions": lambda **kwargs: SimpleNamespace(**kwargs),
        "open_and_connect": open_and_connect,
        "read_expansion_unit_buffer": read_buffer,
        "write_expansion_unit_buffer": write_buffer,
    }
    exec(compile(_without_imports_and_runner(block), "USAGE_GUIDE.md", "exec"), namespace)
    await namespace["main"]()


async def _run_typed_example(block: str, client: _TypedClient) -> None:
    async def open_and_connect(_options: Any) -> _TypedClient:
        return client

    namespace = {
        "HostLinkConnectionOptions": lambda **kwargs: SimpleNamespace(**kwargs),
        "open_and_connect": open_and_connect,
        "read_typed": client.read,
        "write_typed": client.write,
    }
    exec(compile(_without_imports_and_runner(block), "documentation example", "exec"), namespace)
    await namespace["main"]()


def test_usage_python_blocks_compile() -> None:
    for document in (GETTING_STARTED, USAGE_GUIDE):
        blocks = _python_blocks(document.read_text(encoding="utf-8"))
        assert blocks
        for index, block in enumerate(blocks, 1):
            compile(
                block,
                f"{document.name}#python-{index}",
                "exec",
                flags=ast.PyCF_ALLOW_TOP_LEVEL_AWAIT,
            )


def test_documentation_python_imports_resolve() -> None:
    for document in (GETTING_STARTED, USAGE_GUIDE):
        for index, block in enumerate(_python_blocks(document.read_text(encoding="utf-8")), 1):
            tree = ast.parse(block)
            imports = ast.Module(
                body=[node for node in tree.body if isinstance(node, (ast.Import, ast.ImportFrom))],
                type_ignores=[],
            )
            exec(compile(imports, f"{document.name}#imports-{index}", "exec"), {})


def test_expansion_buffer_example_restores_only_confirmed_write() -> None:
    markdown = USAGE_GUIDE.read_text(encoding="utf-8")
    blocks = _python_blocks(markdown)

    getting_started = [
        block
        for block in _python_blocks(GETTING_STARTED.read_text(encoding="utf-8"))
        if "await write_typed(client, test_address" in block
    ]
    assert len(getting_started) == 1
    assert "write_confirmed = False" in getting_started[0]
    assert "if write_confirmed:" in getting_started[0]

    typed = [block for block in blocks if "await write_typed(client, address" in block]
    assert len(typed) == 1
    assert "write_confirmed = False" in typed[0]
    assert "if write_confirmed:" in typed[0]

    matches = [block for block in blocks if "write_expansion_unit_buffer(" in block]
    assert len(matches) == 1
    block = matches[0]
    assert "write_confirmed = False" in block
    assert "write_confirmed = True" in block
    assert "finally:" in block
    assert "if write_confirmed:" in block
    assert "values=original" in block
    assert "restoration failure requires explicit state reconciliation" in markdown


def test_expansion_example_restores_after_readback_failure_but_not_unknown_write() -> None:
    blocks = _python_blocks(USAGE_GUIDE.read_text(encoding="utf-8"))
    matches = [block for block in blocks if "write_expansion_unit_buffer(" in block]
    assert len(matches) == 1
    block = matches[0]

    client = _ExpansionClient(fail_read_at=2)
    try:
        asyncio.run(_run_expansion_example(block, client))
    except _ReadbackError:
        pass
    else:
        raise AssertionError("the simulated readback failure must propagate")
    assert client.writes == [[1, 2, 3, 4], [10, 11, 12, 13]]

    client = _ExpansionClient(fail_write_at=1)
    try:
        asyncio.run(_run_expansion_example(block, client))
    except _OutcomeUnknownError:
        pass
    else:
        raise AssertionError("the simulated outcome-unknown write must propagate")
    assert client.writes == [[1, 2, 3, 4]]


def test_typed_examples_restore_after_readback_failure_but_not_unknown_write() -> None:
    for document, needle, test_value in (
        (GETTING_STARTED, "await write_typed(client, test_address", 1234),
        (USAGE_GUIDE, "await write_typed(client, address", 42),
    ):
        blocks = _python_blocks(document.read_text(encoding="utf-8"))
        matches = [block for block in blocks if needle in block]
        assert len(matches) == 1
        block = matches[0]

        client = _TypedClient(fail_read_at=2)
        try:
            asyncio.run(_run_typed_example(block, client))
        except _ReadbackError:
            pass
        else:
            raise AssertionError("the simulated readback failure must propagate")
        assert client.writes == [test_value, 77]

        client = _TypedClient(fail_write_at=1)
        try:
            asyncio.run(_run_typed_example(block, client))
        except _OutcomeUnknownError:
            pass
        else:
            raise AssertionError("the simulated outcome-unknown write must propagate")
        assert client.writes == [test_value]
