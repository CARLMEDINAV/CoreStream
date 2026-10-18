"""Exportación del registro de auditoría en CSV (criterio 2 de TRV-08)."""

from __future__ import annotations

import csv
import io
from typing import Any, AsyncIterable, AsyncIterator

from app.services.audit_records import ENTRY_FIELDS, as_row

MEDIA_TYPE = "text/csv"
EXTENSION = "csv"

# Filas que se acumulan antes de entregar un trozo del fichero.
_ROWS_PER_CHUNK = 500


def _drain(buffer: io.StringIO) -> str:
    """Devuelve lo escrito y deja el buffer limpio para el trozo siguiente."""
    text = buffer.getvalue()
    buffer.seek(0)
    buffer.truncate(0)
    return text


async def iter_csv(entries: AsyncIterable[Any]) -> AsyncIterator[str]:
    """
    Entrega el CSV por trozos a medida que las entradas llegan de la base.

    Un historial completo no cabe en memoria como una sola cadena, y
    construirlo así era lo que obligaba a ponerle un tope de filas.
    """
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(ENTRY_FIELDS)

    rows = 0
    async for entry in entries:
        writer.writerow(as_row(entry))
        rows += 1
        if rows % _ROWS_PER_CHUNK == 0:
            yield _drain(buffer)

    # La cabecera sale aquí cuando no hubo resultados: el fichero sigue
    # siendo válido y legible.
    remainder = _drain(buffer)
    if remainder:
        yield remainder
