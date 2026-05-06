from __future__ import annotations

import argparse
from pathlib import Path
import sys

from ..agents.chief_agent import ChiefAgent
from ..agents.consensus_chief import ConsensusChiefAgent
from ..config.settings import settings
from ..data.loader import DataLoader


def build_dataframes() -> dict:
    loader = DataLoader(
        data_source=settings.data_source,
        file_paths=settings.file_paths,
    )
    return loader.as_agent_context(loader.load_all())


def run_once(query: str, consensus: bool = False) -> str:
    dataframes = build_dataframes()
    chief = ConsensusChiefAgent() if consensus else ChiefAgent()
    response = chief.run(query=query, context={}, dataframes=dataframes)
    return response.output


def run_loop(consensus: bool = False, llm_panel: str = "") -> int:
    dataframes = build_dataframes()
    chief = ConsensusChiefAgent() if consensus else ChiefAgent()
    print("Procurement Intelligence CLI - Andes Salud")
    print("Escribe 'salir' para terminar.\n")

    if settings.llm_provider == "codex":
        print("Modo Codex/local activo; se usara routing deterministico del workspace.\n")
    if consensus:
        print("Mesa de consenso activa; analistas y revisores compararan resultados.\n")
    if llm_panel:
        print(f"Panel LLM activo: {llm_panel}\n")

    while True:
        try:
            query = input("Consulta> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nSesion finalizada.")
            return 0

        if query.lower() in {"salir", "exit", "quit"}:
            print("Sesion finalizada.")
            return 0
        if not query:
            continue

        context: dict = {}
        providers = [item.strip() for item in (llm_panel or "").split(",") if item.strip()]
        if providers:
            context["llm_panel_providers"] = providers
        response = chief.run(query=query, context=context, dataframes=dataframes)
        print()
        print(response.output)
        print()


def read_room_query(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    start_index = None
    for index, line in enumerate(lines):
        if line.strip() == "## Consulta":
            start_index = index + 1
            break

    if start_index is None:
        return text.strip()

    query_lines = []
    for raw_line in lines[start_index:]:
        if raw_line.startswith("## ") and query_lines:
            break
        if raw_line.strip() == "":
            if query_lines:
                query_lines.append(raw_line)
            continue
        query_lines.append(raw_line)
    return "\n".join(query_lines).strip()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="CLI del equipo virtual de abastecimiento.")
    parser.add_argument("--query", "-q", help="Ejecuta una consulta y termina.")
    parser.add_argument("--room", "-r", help="Lee la consulta desde un archivo markdown de sala.")
    parser.add_argument(
        "--consensus",
        "-c",
        action="store_true",
        help="Ejecuta mesa de consenso con revisores independientes.",
    )
    parser.add_argument(
        "--llm-panel",
        default="",
        help="Revisores externos separados por coma (anthropic,gemini). Requiere API keys en .env.",
    )
    args = parser.parse_args(argv)

    if args.room:
        query = read_room_query(Path(args.room))
        if not query:
            raise SystemExit(f"No se encontro consulta en {args.room}")
        print(_run_cli(query, consensus=args.consensus, llm_panel=args.llm_panel))
        return 0

    if args.query:
        print(_run_cli(args.query, consensus=args.consensus, llm_panel=args.llm_panel))
        return 0
    return run_loop(consensus=args.consensus, llm_panel=args.llm_panel)


def _run_cli(query: str, *, consensus: bool, llm_panel: str) -> str:
    dataframes = build_dataframes()
    chief = ConsensusChiefAgent() if consensus else ChiefAgent()
    context: dict = {}
    providers = [item.strip() for item in (llm_panel or "").split(",") if item.strip()]
    if providers:
        context["llm_panel_providers"] = providers
    response = chief.run(query=query, context=context, dataframes=dataframes)
    return response.output


if __name__ == "__main__":
    sys.exit(main())
