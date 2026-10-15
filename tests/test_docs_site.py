"""docs/ es el sitio publicado en GitHub Pages: solo puede contener lo que genera
tools/build_site.py. La documentación operativa (verificación en hardware, entorno
de referencia, descripciones de PR) va en ops/ y no se publica (BL-33)."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Lista permitida explícita: cualquier otro archivo en docs/ se publicaría por error.
SITIO_PUBLICADO = {
    ".nojekyll",
    "index.html",
    "vocab.html",
    "vocab.ttl",
    "context/ki1.jsonld",
}


def _archivos(raiz: Path) -> set:
    return {p.relative_to(raiz).as_posix() for p in raiz.rglob("*") if p.is_file()}


def test_docs_solo_contiene_el_sitio_publicado():
    ajenos = sorted(_archivos(ROOT / "docs") - SITIO_PUBLICADO)
    assert ajenos == [], f"archivos que no pertenecen al sitio (mover a ops/): {ajenos}"


def test_el_sitio_publicado_esta_completo():
    assert sorted(SITIO_PUBLICADO - _archivos(ROOT / "docs")) == []


def test_build_site_genera_exactamente_la_lista_permitida(tmp_path):
    subprocess.run(
        [sys.executable, "-m", "tools.build_site", str(tmp_path)],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    assert _archivos(tmp_path) == SITIO_PUBLICADO


def test_documentacion_operativa_esta_en_ops():
    for nombre in ("VERIFICACION_HARDWARE.md", "ENTORNO_REFERENCIA.md", "PR_iter-01.md"):
        assert (ROOT / "ops" / nombre).is_file(), nombre
