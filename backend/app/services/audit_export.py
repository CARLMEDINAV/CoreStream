"""
Formatos de exportación del registro de auditoría (criterio 2 de TRV-08).

Cada formato se describe una sola vez —nombre, media type, extensión y cómo se
renderiza— y el router solo lo busca en el registro. Antes el serializador
vivía aquí y el media type en el router, con un if/else para elegir: añadir un
formato obligaba a tocar dos módulos y era fácil que se desincronizaran. Ahora
añadir uno es registrar un ExportFormat más.
"""

from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass
from typing import Any, Callable, Iterable

from app.services.audit_records import ENTRY_FIELDS, as_row


def render_csv(entries: Iterable[Any]) -> str:
    """CSV con cabecera. La cabecera se mantiene aunque no haya resultados."""
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(ENTRY_FIELDS)
    writer.writerows(as_row(entry) for entry in entries)
    return buffer.getvalue()


def render_jsonl(entries: Iterable[Any]) -> str:
    """Un objeto JSON por línea. Sin resultados, cadena vacía: no una en blanco."""
    lines = [
        json.dumps(
            dict(zip(ENTRY_FIELDS, as_row(entry), strict=True)), ensure_ascii=False
        )
        for entry in entries
    ]
    return "\n".join(lines) + ("\n" if lines else "")


@dataclass(frozen=True)
class ExportFormat:
    name: str
    media_type: str
    extension: str
    render: Callable[[Iterable[Any]], str]


FORMATS: dict[str, ExportFormat] = {
    fmt.name: fmt
    for fmt in (
        ExportFormat("csv", "text/csv", "csv", render_csv),
        ExportFormat("jsonl", "application/x-ndjson", "jsonl", render_jsonl),
    )
}


def get_format(name: str) -> ExportFormat:
    try:
        return FORMATS[name]
    except KeyError:
        raise ValueError(f"Formato de exportación desconocido: {name}") from None
