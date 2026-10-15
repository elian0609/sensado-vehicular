"""Las fixtures copiadas de MCS_BACKEND no se han modificado a mano.

Compara cada archivo de tests/fixtures/contracts/ con su huella en
MANIFEST.sha256 (generado por MCS_BACKEND/contracts/tools/sync_fixtures.py).
Si falla: volver a sincronizar desde MCS_BACKEND, nunca editar las fixtures.
"""

import hashlib

from tests.conftest import CONTRACTS


def _manifiesto() -> dict:
    lineas = (CONTRACTS / "MANIFEST.sha256").read_text(encoding="utf-8").splitlines()
    return {ruta: digest for digest, ruta in (linea.split("  ", 1) for linea in lineas)}


def _actual() -> dict:
    return {
        p.relative_to(CONTRACTS).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in CONTRACTS.rglob("*")
        if p.is_file() and p.name != "MANIFEST.sha256"
    }


def test_manifiesto_existe_y_no_esta_vacio():
    assert len(_manifiesto()) > 50


def test_fixtures_copiadas_coinciden_con_el_manifiesto():
    esperado, actual = _manifiesto(), _actual()
    assert sorted(esperado.keys() - actual.keys()) == [], "faltan archivos"
    assert sorted(actual.keys() - esperado.keys()) == [], "archivos no sincronizados"
    modificados = sorted(r for r in esperado if esperado[r] != actual[r])
    assert modificados == [], f"archivos modificados a mano: {modificados}"
