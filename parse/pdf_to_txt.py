# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2025-2026 Louis TRIOULEYRE-ROBERJOT
# This file is part of TollData - Open French Highway Toll Database
from pathlib import Path
import csv

pdf_path = Path("ASF_page7.pdf")
out_text_path = Path("asf_page7.txt")

# --- Texte avec PyPDF2 ---
import PyPDF2
reader = PyPDF2.PdfReader(str(pdf_path))
with out_text_path.open("w", encoding="utf-8") as f:
    for i, page in enumerate(reader.pages, start=1):
        txt = page.extract_text() or ""
        f.write(f"\n\n===== PAGE {i} / {len(reader.pages)} =====\n")
        f.write(txt)