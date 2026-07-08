from typing import Any

try:
    from tabulate import tabulate
except ImportError:
    tabulate = None


def format_table(rows: list[list[Any]], headers: list[str]) -> str:
    """Formatea una lista de filas como una tabla de texto con cabeceras.

    Usa la librería `tabulate` si está disponible; de lo contrario,
    genera una tabla en texto plano con alineación manual.
    """
    if tabulate:
        return tabulate(rows, headers=headers, tablefmt="github")

    # Calcular el ancho máximo de cada columna
    widths = [len(h) for h in headers]
    for row in rows:
        for i, col in enumerate(row):
            widths[i] = max(widths[i], len(str(col)))

    def fmt_line(values: list[Any]) -> str:
        """Formatea una sola fila de la tabla."""
        cells = [str(v).ljust(widths[i]) for i, v in enumerate(values)]
        return "| " + " | ".join(cells) + " |"

    sep = "| " + " | ".join("-" * w for w in widths) + " |"
    lines = [fmt_line(headers), sep]
    lines.extend(fmt_line(row) for row in rows)
    return "\n".join(lines)
