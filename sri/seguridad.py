"""Seguridad: cifrado AES-GCM de datos personales y hash de contraseñas.

- Los campos personales del suscriptor (nombre, dirección y novedades) se
  cifran con AES-256-GCM antes de guardarse en SQLite (RNF-01).
- El índice ciego (HMAC-SHA256) permite detectar duplicados sin descifrar.
- Las contraseñas usan PBKDF2-HMAC-SHA256 con sal aleatoria (equivalente
  funcional a BCrypt en este prototipo; ver docs/ARQUITECTURA.md, AD-05).
- Los respaldos se cifran con el mismo esquema y una cabecera propia.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from .util import DatosInvalidos

PREFIJO_CIFRADO = "enc:v1:"
CABECERA_RESPALDO = b"SRIBAK1"
ITERACIONES_PBKDF2 = 240_000


class Cifrador:
    """Cifra y descifra textos y archivos con una clave local persistente."""

    def __init__(self, ruta_clave: Path):
        self.ruta_clave = Path(ruta_clave)
        self._clave = self._cargar_o_crear_clave()
        self._aes = AESGCM(self._clave)

    def _cargar_o_crear_clave(self) -> bytes:
        if self.ruta_clave.exists():
            clave = self.ruta_clave.read_bytes()
            if len(clave) != 32:
                raise RuntimeError("La clave local sri.key está dañada. Restaure un respaldo o genere una nueva clave.")
            return clave
        self.ruta_clave.parent.mkdir(parents=True, exist_ok=True)
        clave = secrets.token_bytes(32)
        self.ruta_clave.write_bytes(clave)
        try:
            os.chmod(self.ruta_clave, 0o600)
        except OSError:
            pass
        return clave

    def cifrar(self, texto: str) -> str:
        if texto is None:
            texto = ""
        nonce = secrets.token_bytes(12)
        datos = self._aes.encrypt(nonce, str(texto).encode("utf-8"), None)
        return PREFIJO_CIFRADO + base64.b64encode(nonce + datos).decode("ascii")

    def descifrar(self, valor: str | None) -> str:
        if not valor:
            return ""
        if not valor.startswith(PREFIJO_CIFRADO):
            # Compatibilidad con datos antiguos o de demostración sin cifrar.
            return valor
        try:
            bruto = base64.b64decode(valor[len(PREFIJO_CIFRADO):].encode("ascii"))
            return self._aes.decrypt(bruto[:12], bruto[12:], None).decode("utf-8")
        except Exception as error:  # noqa: BLE001 - se traduce a un error de negocio
            raise DatosInvalidos(
                "No fue posible descifrar un dato personal. Verifique que la clave sri.key "
                "corresponda a la base de datos."
            ) from error

    def indice(self, *partes: str) -> str:
        """Índice ciego determinista para búsquedas y control de duplicados."""
        contenido = "\x1f".join(partes).encode("utf-8")
        return hmac.new(self._clave, contenido, hashlib.sha256).hexdigest()

    def cifrar_bytes(self, datos: bytes) -> bytes:
        nonce = secrets.token_bytes(12)
        return CABECERA_RESPALDO + nonce + self._aes.encrypt(nonce, datos, None)

    def descifrar_bytes(self, contenido: bytes) -> bytes:
        if not contenido.startswith(CABECERA_RESPALDO):
            raise DatosInvalidos("El archivo seleccionado no es un respaldo del SRI.")
        bruto = contenido[len(CABECERA_RESPALDO):]
        try:
            return self._aes.decrypt(bruto[:12], bruto[12:], None)
        except Exception as error:  # noqa: BLE001
            raise DatosInvalidos(
                "No se pudo descifrar el respaldo. Verifique que la clave local corresponda al archivo."
            ) from error


def hash_contrasena(contrasena: str) -> str:
    if not contrasena or len(contrasena) < 8:
        raise DatosInvalidos("La contraseña debe tener al menos 8 caracteres.")
    sal = secrets.token_bytes(16)
    derivada = hashlib.pbkdf2_hmac("sha256", contrasena.encode("utf-8"), sal, ITERACIONES_PBKDF2)
    return "pbkdf2_sha256${}${}${}".format(
        ITERACIONES_PBKDF2,
        base64.b64encode(sal).decode("ascii"),
        base64.b64encode(derivada).decode("ascii"),
    )


def verificar_contrasena(contrasena: str, hash_guardado: str) -> bool:
    try:
        algoritmo, iteraciones, sal, esperado = hash_guardado.split("$", 3)
        if algoritmo != "pbkdf2_sha256":
            return False
        derivada = hashlib.pbkdf2_hmac(
            "sha256",
            contrasena.encode("utf-8"),
            base64.b64decode(sal),
            int(iteraciones),
        )
        return hmac.compare_digest(derivada, base64.b64decode(esperado))
    except (ValueError, TypeError):
        return False
