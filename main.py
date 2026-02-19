#!/usr/bin/env python3
"""
Agent Expert M&A — Diagnostic 360° des franchises ANGE (Mandat n°1326)

Utilisation :
    python main.py [--pdf <chemin_pdf>] [--output <rapport.pdf>]

Par défaut, analyse le mémorandum fourni dans le dépôt et génère
le rapport au format PDF dans `rapport_diagnostic.pdf`.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from src.extractor import extract_from_pdf
from src.pdf_report import generate_pdf
from src.report import generate_report


DEFAULT_PDF = Path(__file__).parent / "2026 ☰ memorandum 1326 avec annexes.pdf"
DEFAULT_OUTPUT = Path(__file__).parent / "rapport_diagnostic.pdf"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Expert M&A — Diagnostic financier et valorisation d'entreprise"
    )
    parser.add_argument(
        "--pdf",
        default=str(DEFAULT_PDF),
        help="Chemin vers le mémorandum PDF à analyser",
    )
    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT),
        help="Chemin du fichier de sortie (.pdf ou .md)",
    )
    args = parser.parse_args(argv)

    pdf_path = Path(args.pdf)
    output_path = Path(args.output)

    if not pdf_path.exists():
        print(f"Erreur : le fichier PDF '{pdf_path}' est introuvable.", file=sys.stderr)
        return 1

    print(f"📄 Extraction des données depuis : {pdf_path.name}")
    archange3, lavange = extract_from_pdf(pdf_path)

    print("🔍 Analyse financière en cours…")

    if output_path.suffix.lower() == ".md":
        report_md = generate_report(archange3, lavange)
        output_path.write_text(report_md, encoding="utf-8")
        print(f"✅ Rapport Markdown généré : {output_path}")
        for line in report_md.splitlines():
            if line.startswith("#") or "Valeur des Titres" in line or "EBE normatif" in line:
                print(line)
    else:
        print("📊 Génération du rapport PDF en cours…")
        generate_pdf(archange3, lavange, output_path)
        print(f"✅ Rapport PDF généré : {output_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
