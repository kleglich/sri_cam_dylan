"""Autenticación y control de acceso por rol (RF-08, RN-08)."""

from __future__ import annotations

from ..datos.daos import UsuarioDAO
from ..dominio.modelos import Sesion, Usuario
from ..seguridad import hash_contrasena, verificar_contrasena
from ..util import DatosInvalidos, PermisoDenegado, validar_usuario
from .auditoria import AuditoriaServicio

USUARIOS_DEMO = (
    ("secretaria", "Secretaria", "Sri2026*"),
    ("gerencia", "Gerencia", "Sri2026*"),
)


class CredencialesInvalidas(DatosInvalidos):
    pass


class AutenticacionServicio:
    def __init__(self, usuarios: UsuarioDAO, auditoria: AuditoriaServicio):
        self.usuarios = usuarios
        self.auditoria = auditoria

    def asegurar_usuarios_iniciales(self) -> None:
        """Crea los usuarios de demostración solo en una base de datos nueva."""
        if self.usuarios.contar() > 0:
            return
        for nombre, rol, contrasena in USUARIOS_DEMO:
            self.usuarios.crear(nombre, rol, hash_contrasena(contrasena))
        self.auditoria.registrar("SISTEMA", "Base de datos inicializada con usuarios por defecto")

    def iniciar_sesion(self, nombre: str, contrasena: str) -> Sesion:
        fila = self.usuarios.buscar_por_nombre(nombre or "")
        if not fila or not bool(fila["activo"]):
            self.auditoria.registrar("LOGIN_FALLIDO", f"Intento con usuario inexistente: {nombre or '(vacío)'}")
            raise CredencialesInvalidas("Usuario o contraseña incorrectos.")
        if not verificar_contrasena(contrasena or "", fila["contrasena_hash"]):
            self.auditoria.registrar("LOGIN_FALLIDO", f"Contraseña incorrecta para {fila['nombre']}", fila["id"])
            raise CredencialesInvalidas("Usuario o contraseña incorrectos.")

        usuario = Usuario(id=fila["id"], nombre=fila["nombre"], rol=fila["rol"], activo=True)
        self.auditoria.registrar("SESION", "Inicio de sesión correcto", usuario.id)
        return Sesion(usuario)

    def cambiar_contrasena(self, sesion: Sesion, actual: str, nueva: str, confirmacion: str) -> None:
        fila = self.usuarios.buscar_por_nombre(sesion.nombre)
        if not fila or not verificar_contrasena(actual or "", fila["contrasena_hash"]):
            raise CredencialesInvalidas("La contraseña actual no es correcta.")
        if nueva != confirmacion:
            raise DatosInvalidos("La nueva contraseña y su confirmación no coinciden.")
        self.usuarios.actualizar_hash(sesion.usuario_id, hash_contrasena(nueva))
        self.auditoria.registrar("SEGURIDAD", "Cambio de contraseña", sesion.usuario_id)

    def exigir(self, sesion: Sesion, requisito: str) -> None:
        if not sesion.puede(requisito):
            raise PermisoDenegado(
                f"El rol {sesion.rol} no tiene permiso para esta operación ({requisito})."
            )

    def crear_usuario(self, sesion: Sesion, nombre: str, rol: str, contrasena: str) -> int:
        """Administración básica de usuarios (uso interno y de pruebas)."""
        if sesion.rol != "Gerencia":
            raise PermisoDenegado("Solo la Gerencia puede crear usuarios.")
        if rol not in ("Secretaria", "Gerencia"):
            raise DatosInvalidos("El rol debe ser Secretaria o Gerencia.")
        nombre = validar_usuario(nombre)
        if self.usuarios.buscar_por_nombre(nombre):
            raise DatosInvalidos("Ya existe un usuario con ese nombre.")
        nuevo = self.usuarios.crear(nombre, rol, hash_contrasena(contrasena))
        self.auditoria.registrar("SEGURIDAD", f"Usuario {nombre} creado con rol {rol}", sesion.usuario_id)
        return nuevo
