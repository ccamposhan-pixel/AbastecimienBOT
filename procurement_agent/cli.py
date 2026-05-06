from __future__ import annotations

import argparse
import re
import time
from pathlib import Path

from .analyze import analyze_records
from .chief import run_chief_review
from .config import DEFAULT_FX_TO_CLP
from .ingest import load_tables
from .logging_utils import get_logger
from .report import format_clp, write_outputs
from .state import WatchState
from .standardize import parse_number, standardize_tables
from .models import AnalysisResult

logger = get_logger(__name__)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "analyze":
        return analyze_command(args)
    if args.command == "chief":
        return chief_command(args)
    if args.command == "run":
        return run_command(args)
    if args.command == "watch":
        return watch_command(args)

    parser.print_help()
    return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="procurement-agent",
        description="Analiza precios y proveedores para detectar ahorros y consolidacion.",
    )
    subparsers = parser.add_subparsers(dest="command")

    analyze_parser = subparsers.add_parser("analyze", help="Analiza uno o varios CSV.")
    analyze_parser.add_argument("input", help="Archivo CSV o carpeta con CSV.")
    analyze_parser.add_argument("--out", default="reports", help="Carpeta de salida.")
    analyze_parser.add_argument(
        "--fx",
        default="",
        help="Tipos de cambio a CLP separados por coma, por ejemplo USD=950,EUR=1050.",
    )
    analyze_parser.add_argument(
        "--similarity-threshold",
        type=float,
        default=0.86,
        help="Umbral de similitud para agrupar descripciones sin codigo.",
    )
    analyze_parser.add_argument(
        "--long-tail-share",
        type=float,
        default=0.02,
        help="Porcentaje maximo del gasto de categoria para marcar proveedores de cola larga.",
    )

    run_parser = subparsers.add_parser(
        "run",
        help="Ejecuta análisis + revisión del jefe IA en un solo paso.",
    )
    run_parser.add_argument("input", help="Archivo CSV o carpeta con CSV.")
    run_parser.add_argument("--out", default="reports", help="Carpeta de salida.")
    run_parser.add_argument(
        "--fx",
        default="",
        help="Tipos de cambio a CLP separados por coma, por ejemplo USD=950,EUR=1050.",
    )
    run_parser.add_argument(
        "--similarity-threshold",
        type=float,
        default=0.86,
        help="Umbral de similitud para agrupar descripciones sin codigo.",
    )
    run_parser.add_argument(
        "--long-tail-share",
        type=float,
        default=0.02,
        help="Porcentaje maximo del gasto de categoria para marcar proveedores de cola larga.",
    )
    run_parser.add_argument(
        "--question",
        default="",
        help="Solicitud o contexto que el usuario entrega al jefe.",
    )

    chief_parser = subparsers.add_parser(
        "chief",
        help="Convoca al jefe IA para validar resultados del analista y generar minuta de mesa.",
    )
    chief_parser.add_argument("--reports", default="reports", help="Carpeta con salidas del analista.")
    chief_parser.add_argument("--out", default="", help="Carpeta de salida. Por defecto usa --reports.")
    chief_parser.add_argument(
        "--question",
        default="",
        help="Solicitud o contexto que el usuario entrega al jefe.",
    )

    watch_parser = subparsers.add_parser(
        "watch",
        help="Monitorea una carpeta y re-ejecuta análisis cuando aparezcan CSV nuevos.",
    )
    watch_parser.add_argument("input", help="Carpeta con CSV (se monitorea recursivo).")
    watch_parser.add_argument("--out", default="reports", help="Carpeta raíz de salida.")
    watch_parser.add_argument(
        "--fx",
        default="",
        help="Tipos de cambio a CLP separados por coma, por ejemplo USD=950,EUR=1050.",
    )
    watch_parser.add_argument(
        "--interval-seconds",
        type=float,
        default=20.0,
        help="Intervalo de polling en segundos.",
    )
    watch_parser.add_argument(
        "--similarity-threshold",
        type=float,
        default=0.86,
        help="Umbral de similitud para agrupar descripciones sin codigo.",
    )
    watch_parser.add_argument(
        "--long-tail-share",
        type=float,
        default=0.02,
        help="Porcentaje maximo del gasto de categoria para marcar proveedores de cola larga.",
    )
    watch_parser.add_argument(
        "--chief",
        action="store_true",
        help="También genera la revisión del jefe IA por cada corrida.",
    )
    watch_parser.add_argument(
        "--question",
        default="",
        help="Contexto opcional para la revisión del jefe.",
    )
    watch_parser.add_argument(
        "--state",
        default=".abastecimienbot_watch_state.json",
        help="Archivo de estado para no reprocesar.",
    )
    return parser


def analyze_command(args: argparse.Namespace) -> int:
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"No existe la ruta de entrada: {input_path}")
        return 2

    paths, result = run_analysis_pipeline(
        input_path=input_path,
        output_dir=Path(args.out),
        fx_value=args.fx,
        similarity_threshold=args.similarity_threshold,
        long_tail_share=args.long_tail_share,
    )
    if paths is None or result is None:
        return 2

    print("Analisis listo.")
    print(f"Registros estandarizados: {result.summary.record_count}")
    print(f"Gasto total: {format_clp(result.summary.total_spend_clp)}")
    print(f"Ahorro estimado: {format_clp(result.summary.estimated_savings_clp)}")
    print(f"Reporte: {paths['report']}")
    print(f"Datos estandarizados: {paths['standardized_csv']}")
    print(f"Oportunidades JSON: {paths['opportunities_json']}")
    return 0


def chief_command(args: argparse.Namespace) -> int:
    reports_dir = Path(args.reports)
    if not reports_dir.exists():
        print(f"No existe la carpeta de reportes: {reports_dir}")
        return 2

    output_dir = args.out or reports_dir
    paths = run_chief_review(reports_dir, output_dir, args.question)
    print("Jefe IA listo.")
    print(f"Memo ejecutivo: {paths['memo']}")
    print(f"Minuta estructurada: {paths['minutes_json']}")
    return 0


def run_command(args: argparse.Namespace) -> int:
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"No existe la ruta de entrada: {input_path}")
        return 2

    out_dir = Path(args.out)
    paths, result = run_analysis_pipeline(
        input_path=input_path,
        output_dir=out_dir,
        fx_value=args.fx,
        similarity_threshold=args.similarity_threshold,
        long_tail_share=args.long_tail_share,
    )
    if paths is None or result is None:
        return 2

    run_chief_review(out_dir, out_dir, args.question)
    print("Corrida completa.")
    print(f"Reporte: {paths['report']}")
    print(f"Memo jefe: {out_dir / 'chief_memo.md'}")
    return 0


def watch_command(args: argparse.Namespace) -> int:
    input_dir = Path(args.input)
    if not input_dir.exists() or not input_dir.is_dir():
        print(f"No existe la carpeta a monitorear: {input_dir}")
        return 2

    state_path = Path(args.state)
    state = WatchState.load(state_path)
    fx_rates = {**DEFAULT_FX_TO_CLP, **parse_fx(args.fx)}

    print(f"Monitoreando: {input_dir}")
    print("Ctrl+C para terminar.")

    try:
        while True:
            changed = _detect_csv_changes(input_dir, state)
            if changed:
                run_dir = Path(args.out) / time.strftime("%Y%m%d_%H%M%S")
                run_dir.mkdir(parents=True, exist_ok=True)
                logger.info("Detectados %s CSV nuevos/cambiados. Ejecutando análisis en %s", len(changed), run_dir)

                tables = load_tables(input_dir)
                if not tables:
                    logger.warning("No se encontraron CSV en %s", input_dir)
                else:
                    standardized = standardize_tables(tables, fx_rates)
                    result = analyze_records(
                        standardized.records,
                        standardized.issues,
                        similarity_threshold=args.similarity_threshold,
                        long_tail_spend_share=args.long_tail_share,
                    )
                    write_outputs(result, standardized.records, run_dir)

                    if args.chief:
                        run_chief_review(run_dir, run_dir, args.question or "")

                    logger.info("Corrida completada.")

                state.save(state_path)

            time.sleep(max(1.0, float(args.interval_seconds)))
    except KeyboardInterrupt:
        print("\nWatch detenido.")
        state.save(state_path)
        return 0


def run_analysis_pipeline(
    input_path: Path,
    output_dir: Path,
    fx_value: str,
    similarity_threshold: float,
    long_tail_share: float,
) -> tuple[dict[str, Path] | None, AnalysisResult | None]:
    fx_rates = {**DEFAULT_FX_TO_CLP, **parse_fx(fx_value)}
    tables = load_tables(input_path)
    if not tables:
        print(f"No se encontraron CSV en: {input_path}")
        return None, None

    standardized = standardize_tables(tables, fx_rates)
    result = analyze_records(
        standardized.records,
        standardized.issues,
        similarity_threshold=similarity_threshold,
        long_tail_spend_share=long_tail_share,
    )
    paths = write_outputs(result, standardized.records, output_dir)
    return paths, result


def _detect_csv_changes(input_dir: Path, state: WatchState) -> list[Path]:
    changed: list[Path] = []
    for path in sorted(input_dir.rglob("*.csv")):
        if not path.is_file():
            continue
        try:
            stat = path.stat()
        except OSError:
            continue
        key = str(path.resolve())
        fingerprint = {"mtime_ns": stat.st_mtime_ns, "size": stat.st_size}
        previous = state.files.get(key)
        if previous != fingerprint:
            changed.append(path)
            state.files[key] = fingerprint
    return changed


def parse_fx(value: str) -> dict[str, float]:
    rates: dict[str, float] = {}
    if not value:
        return rates

    for part in re.split(r",(?=\s*[A-Za-z]{2,4}\s*=)", value):
        if not part.strip():
            continue
        if "=" not in part:
            raise SystemExit(f"Tipo de cambio invalido: {part}. Use MONEDA=valor.")
        currency, raw_rate = part.split("=", 1)
        currency = currency.strip().upper()
        rate = parse_number(raw_rate, default=None)
        if rate is None:
            raise SystemExit(f"Tipo de cambio invalido para {currency}: {raw_rate}")
        rates[currency] = rate
    return rates
