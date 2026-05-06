from __future__ import annotations

import argparse
from pathlib import Path
import sys

from ..agents.email_triage_agent import EmailTriageAgent
from ..config.settings import load_env_file
from ..data.email_loader import EmailAccountConfig, EmailLoader, MicrosoftGraphConfig
from ..reports.email_html_report import write_email_triage_html


DEFAULT_QUERY = (
    "Leer correos pendientes, resumir puntos criticos, listar tareas con prioridad "
    "y deadlines, y sugerir respuestas."
)


def run_once(
    query: str = DEFAULT_QUERY,
    source: str = "csv",
    csv_path: str | Path = "data/mock/emails.csv",
    limit: int = 50,
    unread_only: bool = False,
    folder: str | None = None,
) -> str:
    return build_response(
        query=query,
        source=source,
        csv_path=csv_path,
        limit=limit,
        unread_only=unread_only,
        folder=folder,
    ).output


def build_response(
    query: str = DEFAULT_QUERY,
    source: str = "csv",
    csv_path: str | Path = "data/mock/emails.csv",
    limit: int = 50,
    unread_only: bool = False,
    folder: str | None = None,
):
    load_env_file()
    normalized_source = source.lower()
    config = EmailAccountConfig.from_env(folder=folder) if normalized_source == "imap" else None
    graph_config = MicrosoftGraphConfig.from_env(folder=folder) if normalized_source == "graph" else None
    loader = EmailLoader(
        source=normalized_source,
        csv_path=csv_path,
        account_config=config,
        graph_config=graph_config,
        limit=limit,
        unread_only=unread_only,
    )
    emails = loader.load()
    agent = EmailTriageAgent()
    return agent.run(
        query=query,
        context={"limit": limit},
        dataframes=loader.as_agent_context(emails),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="CLI del agente de correo.")
    parser.add_argument("--query", "-q", default=DEFAULT_QUERY, help="Consulta o foco del analisis.")
    parser.add_argument(
        "--source",
        choices=["csv", "imap", "graph"],
        default="csv",
        help="Fuente de correos. Usa graph para Outlook/Microsoft 365.",
    )
    parser.add_argument(
        "--file",
        default="data/mock/emails.csv",
        help="Ruta CSV con correos normalizados o exportados.",
    )
    parser.add_argument("--limit", type=int, default=50, help="Maximo de correos a revisar.")
    parser.add_argument("--folder", default=None, help="Carpeta de correo, por ejemplo inbox.")
    parser.add_argument(
        "--unread-only",
        action="store_true",
        help="Leer solo correos no leidos cuando la fuente lo soporte.",
    )
    parser.add_argument(
        "--output",
        "-o",
        help="Guarda el resultado. Usa extension .html para informe visual o .md para Markdown.",
    )
    args = parser.parse_args(argv)

    response = build_response(
        query=args.query,
        source=args.source,
        csv_path=args.file,
        limit=args.limit,
        unread_only=args.unread_only,
        folder=args.folder,
    )
    output = response.output

    if args.output:
        path = Path(args.output)
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.suffix.lower() in {".html", ".htm"}:
            write_email_triage_html(response, path)
        else:
            path.write_text(output, encoding="utf-8")
    print(output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
