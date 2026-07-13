"""
Caché opcional respaldada por Redis (mismo REDIS_URL que el rate limiter).

Se usa para vistas de solo lectura y coste relativamente alto (ej. /reports,
que hace dos consultas de agregación) en las que un TTL corto reduce carga
en la base de datos sin arriesgar a servir datos muy desactualizados.

Diseño defensivo: si Redis no está configurado, o falla en tiempo de
ejecución (caído, red, cuota superada, etc.), la caché se desactiva sola y
la app sigue funcionando consultando directamente la base de datos — nunca
debe ser un punto único de fallo.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Callable

from flask import current_app

logger = logging.getLogger(__name__)

_redis_client = None
_redis_unavailable = False


def _get_client():
    """Crea (una vez) y devuelve el cliente de Redis, o None si no aplica."""
    global _redis_client, _redis_unavailable

    if _redis_unavailable:
        return None
    if not current_app.config.get("CACHE_ENABLED"):
        return None
    if _redis_client is not None:
        return _redis_client

    try:
        import redis  # import perezoso: si no hay Redis configurado, no hace falta el paquete instalado en runtime

        kwargs = {"decode_responses": True, "socket_connect_timeout": 2, "socket_timeout": 2}
        if current_app.config.get("REDIS_INSECURE_TLS") and current_app.config["REDIS_URL"].startswith("rediss://"):
            kwargs["ssl_cert_reqs"] = None
        _redis_client = redis.from_url(current_app.config["REDIS_URL"], **kwargs)
        _redis_client.ping()
    except Exception as exc:
        logger.warning("Redis no disponible, se continúa sin caché: %s", exc)
        _redis_unavailable = True
        _redis_client = None

    return _redis_client


def cached_json(key: str, ttl_seconds: int, builder: Callable[[], Any]) -> Any:
    """Devuelve `builder()`, cacheando el resultado (serializado en JSON) en
    Redis durante `ttl_seconds`. Si Redis falla, se ejecuta `builder()`
    directamente sin romper la petición.
    """
    client = _get_client()
    if client is None:
        return builder()

    try:
        raw = client.get(key)
        if raw is not None:
            return json.loads(raw)
    except Exception as exc:
        logger.warning("Fallo leyendo caché de Redis (%s): %s", key, exc)
        return builder()

    value = builder()
    try:
        client.setex(key, ttl_seconds, json.dumps(value, default=str))
    except Exception as exc:
        logger.warning("Fallo escribiendo caché en Redis (%s): %s", key, exc)
    return value


def invalidate(*keys: str) -> None:
    """Borra manualmente una o varias claves (ej. tras crear/editar un libro)."""
    client = _get_client()
    if client is None or not keys:
        return
    try:
        client.delete(*keys)
    except Exception as exc:
        logger.warning("Fallo invalidando caché de Redis: %s", exc)
