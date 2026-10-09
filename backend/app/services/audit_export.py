"""Exportación del registro de auditoría en CSV (criterio 2 de TRV-08)."""

from __future__ import annotations

import csv
import io
from typing import Any, Iterable

from app.services.audit_records import ENTRY_FIELDS, as_row

MEDIA_TYPE = "text/csv"
EXTENSION = "csv"


def render_csv(entries: Iterable[Any]) -> str:
    """Devuelve el CSV con cabecera, que se mantiene aunque no haya resultados."""
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(ENTRY_FIELDS)
    writer.writerows(as_row(entry) for entry in entries)
    return buffer.getvalue()
