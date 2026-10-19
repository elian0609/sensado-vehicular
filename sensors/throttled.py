"""Evidencia de alimentación de la Raspberry Pi (BL-51, Iteración 4b).

Al cerrar cada ventana, M1 guarda en raw.throttled el valor de `vcgencmd get_throttled` en
hexadecimal ("0x0" = nunca hubo bajo voltaje ni estrangulamiento desde el arranque). Los bits
16–19 son acumulados desde el arranque: el valor dice que hubo un problema, no en qué ventana.
Es evidencia, no un quality_flag (decisión del autor, 2026-10-19: el bajo voltaje se resuelve en
hardware con un cable adecuado).

No hay interfaz equivalente en /sys en el kernel de la Pi de referencia: solo
`/sys/class/hwmon/hwmon*/in0_lcrit_alarm` (rpi_volt), que da el bajo voltaje actual (0/1) y no
el valor hexadecimal. Por eso se lanza vcgencmd (~3 ms medidos en la Pi 3B), con un límite de 1 s.
"""

import logging
import re
import subprocess
from collections.abc import Callable

log = logging.getLogger("edge_node.throttled")

TIMEOUT_S = 1.0
_SALIDA = re.compile(r"^throttled=0x([0-9a-f]+)$", re.IGNORECASE)


def leer_vcgencmd(run: Callable[..., subprocess.CompletedProcess] = subprocess.run) -> str:
    """Valor de `vcgencmd get_throttled` como "0x…" en minúsculas.

    OSError si el comando no está o falla (incluido el límite de tiempo); ValueError si la
    salida no tiene la forma esperada. `run` solo se sustituye en pruebas.
    """
    try:
        resultado = run(
            ["vcgencmd", "get_throttled"], capture_output=True, text=True, timeout=TIMEOUT_S
        )
    except subprocess.TimeoutExpired as exc:
        raise OSError(f"vcgencmd get_throttled superó {TIMEOUT_S} s") from exc
    if resultado.returncode != 0:
        raise OSError(f"vcgencmd get_throttled terminó con código {resultado.returncode}")
    coincidencia = _SALIDA.match(resultado.stdout.strip())
    if not coincidencia:
        raise ValueError(f"salida inesperada de vcgencmd: {resultado.stdout.strip()!r}")
    return f"0x{coincidencia.group(1).lower()}"


class ThrottledProbe:
    """Lee el valor y nunca falla: si el lector no está disponible devuelve None y lo avisa
    una sola vez (vuelve a intentarlo en cada ventana, por si es transitorio)."""

    def __init__(self, lector: Callable[[], str | None] = leer_vcgencmd):
        self._lector = lector
        self._avisado = False

    def read(self) -> str | None:
        try:
            return self._lector()
        except (OSError, ValueError) as exc:
            if not self._avisado:
                log.warning(
                    "raw.throttled no disponible (%s): se guardará null; el nodo sigue", exc
                )
                self._avisado = True
            return None
