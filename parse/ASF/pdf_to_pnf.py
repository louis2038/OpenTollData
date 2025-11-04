#!/usr/bin/env python3
"""
Convertisseur PDF -> PNG simple.

Dépendances:
    pip install pdf2image pillow

Sur certaines plateformes, poppler est nécessaire (apt, brew, choco...).
Ex: sudo apt install poppler-utils
"""

import argparse
import os
import sys
from pathlib import Path
from typing import Optional, List

try:
    from pdf2image import convert_from_path
except Exception as e:
    print("Module 'pdf2image' introuvable. Installez-le avec: pip install pdf2image pillow", file=sys.stderr)
    raise e

def convert_pdf_file(pdf_path: Path, out_dir: Path, dpi: int = 200, grayscale: bool = False,
                     first_page: Optional[int] = None, last_page: Optional[int] = None,
                     poppler_path: Optional[str] = None) -> List[Path]:
    """
    Convertit un fichier PDF en plusieurs PNG (une image par page).
    Retourne la liste des fichiers générés.
    """
    if not pdf_path.exists():
        raise FileNotFoundError(f"{pdf_path} n'existe pas")
    out_dir.mkdir(parents=True, exist_ok=True)

    page_kwargs = {}
    if first_page is not None:
        page_kwargs['first_page'] = first_page
    if last_page is not None:
        page_kwargs['last_page'] = last_page

    images = convert_from_path(
        str(pdf_path),
        dpi=dpi,
        grayscale=grayscale,
        poppler_path=poppler_path,
        **page_kwargs
    )

    generated = []
    base = pdf_path.stem
    for i, img in enumerate(images, start=1 if first_page is None else first_page):
        out_name = f"{base}_page_{i:03d}.png"
        out_path = out_dir / out_name
        img.save(str(out_path), format="PNG")
        generated.append(out_path)
    return generated

def collect_pdfs(input_path: Path) -> List[Path]:
    if input_path.is_dir():
        return sorted([p for p in input_path.iterdir() if p.suffix.lower() == ".pdf"])
    elif input_path.is_file() and input_path.suffix.lower() == ".pdf":
        return [input_path]
    else:
        raise FileNotFoundError(f"Aucun PDF trouvé à: {input_path}")

def parse_page_range(s: str) -> (Optional[int], Optional[int]):
    # formats supportés: "1-3", "2", "" -> None
    if not s:
        return None, None
    parts = s.split("-")
    try:
        if len(parts) == 1:
            p = int(parts[0])
            return p, p
        elif len(parts) == 2:
            a = int(parts[0]) if parts[0] != "" else None
            b = int(parts[1]) if parts[1] != "" else None
            return a, b
    except ValueError:
        pass
    raise argparse.ArgumentTypeError("Format de page invalide. Ex: 1-3 ou 2")

def main():
    parser = argparse.ArgumentParser(description="Convertit des fichiers PDF en PNG (1 image par page).")
    parser.add_argument("input", type=Path, help="Fichier PDF ou dossier contenant des PDFs.")
    parser.add_argument("-o", "--out", type=Path, default=Path("output_pngs"), help="Dossier de sortie.")
    parser.add_argument("--dpi", type=int, default=200, help="Résolution en DPI (par défaut: 200).")
    parser.add_argument("--grayscale", action="store_true", help="Convertir en niveaux de gris.")
    parser.add_argument("--pages", type=str, default="", help="Plage de pages: ex '1-3' ou '2'.")
    parser.add_argument("--poppler-path", type=str, default=None, help="Chemin vers les binaires poppler si besoin.")
    args = parser.parse_args()

    try:
        first_page, last_page = parse_page_range(args.pages)
    except argparse.ArgumentTypeError as e:
        parser.error(str(e))

    try:
        pdfs = collect_pdfs(args.input)
    except Exception as e:
        print(f"Erreur: {e}", file=sys.stderr)
        sys.exit(2)

    if not pdfs:
        print("Aucun fichier PDF trouvé.", file=sys.stderr)
        sys.exit(2)

    total = len(pdfs)
    for idx, pdf in enumerate(pdfs, start=1):
        print(f"[{idx}/{total}] Conversion: {pdf} -> {args.out}")
        try:
            generated = convert_pdf_file(
                pdf_path=pdf,
                out_dir=args.out,
                dpi=args.dpi,
                grayscale=args.grayscale,
                first_page=first_page,
                last_page=last_page,
                poppler_path=args.poppler_path
            )
            print(f"  Généré: {len(generated)} image(s). Exemple: {generated[0] if generated else '—'}")
        except Exception as e:
            print(f"  Erreur lors de la conversion de {pdf}: {e}", file=sys.stderr)

if __name__ == "__main__":
    main()