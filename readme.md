# Library Management (Flask) — versión optimizada para Vercel + MARC21

Versión reescrita de [mituldavid/library-management-flask](https://github.com/mituldavid/library-management-flask),
lista para desplegar en **Vercel** (función serverless Python), con seguridad
reforzada y soporte de catálogo **MARC21**.

## Qué ha cambiado respecto al proyecto original

| Área | Original | Esta versión |
|---|---|---|
| Despliegue | Solo `app.run()` local, MySQL fijo a `localhost` | `api/index.py` + `vercel.json` (serverless), config 100% por variables de entorno |
| Base de datos | `flask_mysqldb` + SQL crudo | SQLAlchemy ORM (Postgres/MySQL/SQLite), sin SQL concatenado en ningún punto |
| Autenticación | Ninguna — cualquiera podía borrar libros/socios | Login obligatorio (`Flask-Login`), contraseñas con hash (`werkzeug.security`), roles admin/bibliotecario |
| CSRF | No | `Flask-WTF` con token CSRF en todos los formularios |
| Cabeceras HTTP | No | `Flask-Talisman`: HSTS, CSP, `X-Content-Type-Options`, cookies `HttpOnly`/`Secure`/`SameSite` |
| Fuerza bruta | Sin límite | `Flask-Limiter` en login/registro, con backend Redis (fiable en serverless; `memory://` no lo es) |
| Escrituras en disco | No aplica | Ninguna en producción (Vercel es de solo lectura salvo `/tmp` efímero); MARC21 se procesa en memoria, la BD es externa |
| Secretos | `app.secret_key = "secret"`, credenciales MySQL en el código | Todo via variables de entorno; falla explícitamente si falta `SECRET_KEY` en producción |
| Subida de ficheros | No aplica | Límite de tamaño (10 MB), validación de extensión, límite de nº de registros por importación |
| Catálogo MARC21 | No existía | Importación (.mrc/.marc/.xml) y exportación (por libro o catálogo completo) en MARC21/MARCXML |
| Idioma | Inglés | Español |

## Estructura

```
library-management-flask-vercel/
├── api/index.py            # entry point WSGI para Vercel
├── run.py                  # servidor de desarrollo local
├── vercel.json
├── requirements.txt
├── library/
│   ├── __init__.py         # app factory (seguridad, blueprints, errores)
│   ├── config.py           # configuración vía variables de entorno
│   ├── extensions.py       # db, login_manager, csrf, limiter
│   ├── models.py           # User, Member, Book, Transaction
│   ├── forms.py            # formularios WTForms con validación
│   ├── marc21.py           # import/export MARC21 con pymarc
│   ├── routes/             # blueprints: auth, main, books, members, transactions, marc21
│   └── templates/
├── scripts/init_db.py      # crea las tablas
└── tests/test_app.py       # pytest
```

## Redis (recomendado en Vercel)

Las funciones serverless de Vercel son de **solo lectura**, salvo `/tmp`
(escribible pero **efímero**: no sobrevive entre invocaciones ni se comparte
entre instancias). Esto hace inútil en producción el backend por defecto
`memory://` de `Flask-Limiter`: cada petición puede caer en una instancia
distinta, así que el contador de intentos de login/registro nunca se
acumula de verdad y el límite de fuerza bruta queda sin efecto.

Con `REDIS_URL` configurada, esta versión usa Redis automáticamente para:

1. **Rate limiting** (`Flask-Limiter`): límite real de intentos de login/registro, compartido entre todas las invocaciones.
2. **Caché corta de `/reports`** (30 s): evita repetir las dos consultas de agregación en cada petición. Se invalida automáticamente al crear/editar/borrar libros o socios, o al prestar/devolver un libro.

Si no defines `REDIS_URL`, la app funciona igual (sin caché, y con rate
limiting en memoria local, no fiable en serverless — verás un aviso en los
logs de Vercel recordándotelo).

Se admite `redis://` (texto plano) y `rediss://` (TLS, el habitual en
proveedores gestionados como Upstash). También se leen `KV_URL` y
`REDISCLOUD_URL` como alias, por si tu proveedor usa otro nombre.

### ¿Es suficiente el free tier de 30 MB?

- **Para rate limiting y caché (el uso que le da esta app): sí, de sobra.** Cada clave ocupa unos pocos bytes (contadores de intentos, o el JSON de `/reports`, que son un puñado de libros/socios). Con 30 MB tienes margen para miles de claves.
- **Para usar Redis como base de datos principal en lugar de Postgres: no lo recomiendo.** Redis es clave-valor, no relacional: perderías las claves foráneas entre `books`/`members`/`transactions` que garantizan la integridad de préstamos y devoluciones, y tendrías que reimplementar a mano joins, búsquedas por texto (`LIKE`) y agregaciones. Además, 30 MB se queda corto en cuanto importes un catálogo MARC21 grande: cada registro MARCXML almacenado (`Book.marc_xml`) pesa entre 1 y 3 KB, así que unos pocos miles de libros ya rozarían el límite. Mi recomendación: mantén Postgres (Neon/Supabase tienen free tiers de 500 MB–3 GB) como base de datos y usa Redis solo para rate limiting/caché, como está configurado aquí.

## Despliegue en Vercel

1. Sube este proyecto a un repositorio de GitHub/GitLab/Bitbucket.
2. En Vercel, importa el repositorio (detecta `vercel.json` automáticamente).
3. Configura las variables de entorno del proyecto (Project Settings → Environment Variables):
   - `SECRET_KEY`: genera una con `python -c "import secrets; print(secrets.token_hex(32))"`
   - `DATABASE_URL`: cadena de conexión Postgres (recomendado: Vercel Postgres, Neon o Supabase — las funciones serverless no pueden alojar una base de datos en el mismo contenedor).
   - Opcional `RATELIMIT_STORAGE_URI`: usa Redis (p.ej. Upstash) si tienes varias instancias concurrentes; por defecto usa memoria local (válido para uso ligero).
4. Despliega. Vercel instalará `requirements.txt` y expondrá `api/index.py`.
5. Tras el primer despliegue, inicializa las tablas ejecutando localmente (con `DATABASE_URL` apuntando a la BD de producción):
   ```bash
   pip install -r requirements.txt
   python scripts/init_db.py
   ```
6. Crea el primer usuario (se convierte automáticamente en administrador) desde `/register`, o localmente con:
   ```bash
   flask --app run create-admin
   ```

## Desarrollo local

```bash
cp .env.example .env          # edítalo con tu SECRET_KEY y DATABASE_URL
pip install -r requirements.txt
python scripts/init_db.py
python run.py                 # http://127.0.0.1:5000
```

## Soporte MARC21

- **Importar** (`/marc21/import`): sube un fichero `.mrc`/`.marc` (ISO 2709) o `.xml` (MARCXML). Se extraen los campos 001, 020, 041, 100/700, 245, 260/264 y 300 y se crea un `Book` por cada registro. Los registros ya importados (mismo campo 001) no se duplican. Límite: 500 registros por fichero.
- **Exportar un libro** (`/marc21/export/<id>`): descarga el libro como registro MARC21 (MARCXML).
- **Exportar catálogo completo** (`/marc21/export`): descarga todos los libros como un único fichero MARCXML, compatible con cualquier ILS (Koha, Alma, etc.).

## Tests

```bash
pip install pytest
pytest tests/ -v
```

## Notas de seguridad

- Nunca se ejecuta SQL crudo: todo el acceso a datos pasa por el ORM de SQLAlchemy con parámetros ligados.
- Todos los formularios de escritura (crear/editar/borrar) exigen sesión iniciada y token CSRF.
- Las cookies de sesión son `HttpOnly`, `SameSite=Lax` y `Secure` en producción.
- La API externa de importación de libros usa `timeout` y un límite de páginas para evitar bloqueos o DoS accidental.
- El registro de nuevas cuentas se deshabilita automáticamente tras crear el primer usuario (administrador); a partir de ahí solo un admin autenticado puede dar de alta cuentas.
