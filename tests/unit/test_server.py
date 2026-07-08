from __future__ import annotations

import importlib.metadata
from typing import Any

import pytest

from gfi_scout import server


def test_server_parser_defaults_to_stdio() -> None:
    args = server.build_parser().parse_args([])

    assert args.transport == "stdio"
    assert args.host == "127.0.0.1"
    assert args.port == 8000

def test_server_parser_version_flag(capsys: Any) -> None:
    with pytest.raises(SystemExit) as exc_info:
        server.build_parser().parse_args(["--version"])
    assert exc_info.value.code == 0
    assert capsys.readouterr().out.strip() == f"gfi-scout {importlib.metadata.version('gfi-scout')}"

def test_server_main_passes_transport_settings(monkeypatch: Any) -> None:
    captured: dict[str, Any] = {}

    def fake_run(*, transport: str, mount_path: str | None = None) -> None:
        captured["transport"] = transport
        captured["mount_path"] = mount_path

    monkeypatch.setattr(server.mcp, "run", fake_run)

    server.main(
        [
            "--transport",
            "streamable-http",
            "--host",
            "127.0.0.1",
            "--port",
            "8123",
            "--mount-path",
            "/api",
        ]
    )

    assert captured == {"transport": "streamable-http", "mount_path": "/api"}
    assert server.mcp.settings.host == "127.0.0.1"
    assert server.mcp.settings.port == 8123
