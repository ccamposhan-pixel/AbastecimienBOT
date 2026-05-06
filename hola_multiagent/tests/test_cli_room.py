from __future__ import annotations

from hola_multiagent.interface.cli import read_room_query


def test_read_room_query_uses_exact_heading(tmp_path):
    room = tmp_path / "room.md"
    room.write_text(
        "# Sala\n\n"
        "Texto que menciona `## Consulta` sin ser encabezado.\n\n"
        "## Consulta\n\n"
        "Revisar cobertura critica.\n\n"
        "## Protocolo\n\n"
        "No incluir esto.",
        encoding="utf-8",
    )

    assert read_room_query(room) == "Revisar cobertura critica."
