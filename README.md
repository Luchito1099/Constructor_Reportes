# Panel de Luchito — 3 herramientas en una

Un solo panel (con login por usuario) que reúne tres módulos, accesibles desde el menú
lateral:

1. **Constructor** — construye queries de Databricks desde un banco de queries que ya
   funcionan, ajústalas rápido (fechas, brandpacks, gerencia…) con bloques o con IA, y
   ensambla notebooks tipo *rompecabezas* que terminan en PDF / imagen / correo / Excel.
   Arma el código listo para pegar/correr en Databricks + previsualización simulada.
2. **Reportes por horario** — agenda diaria estilo kanban (Pendientes / Enviados) con la
   hora de cada reporte, canal (WhatsApp/correo), etiquetas de gerencia y tipo, % de
   cumplimiento, **notificaciones + sonido** antes/al vencer, y reseteo diario. Incluye un
   botón para **cargar una agenda de ejemplo** (26 reportes) de un clic.
3. **Solicitudes** — historial de lo que te piden: fecha de solicitud, descripción,
   prioridad, periodo/fecha límite, notas, adjunto (enlace) y **capturas de pantalla**
   (pega con Ctrl+V, arrastra o sube), con buscador y filtros por prioridad y por fecha.
4. **Links** — guarda tus enlaces de BI y otras herramientas con **nombre, URL y
   descripción**; se abren en un clic (banco compartido con el equipo).

Las API keys de IA viven **solo en el servidor**, nunca en el navegador. La estética usa la
paleta del Dashboard (teal + sidebar navy + fondo claro, fuente *Plus Jakarta Sans*), con
modo claro/oscuro.

### Roles (compartir con tu equipo)

- **Administrador** (tú): crea/edita todo — banco de queries, catálogo, reportes,
  solicitudes, plantillas, IA.
- **Solo consulta** (*viewer*): entra y ve **solo el Constructor** en modo lectura; elige
  una query, llena los **bloques rápidos** (rango de fechas, brandpack…), *Genera* y
  **copia/descarga** la query final. No puede editar el SQL, ni crear/borrar, ni usar IA,
  ni ver Reportes/Solicitudes.

El **primer usuario** que se registra queda **administrador**; el resto entra como *solo
consulta*. Desde el menú **Usuarios** (solo admin) promueves/quitas administradores y, por
cada viewer, **habilitas funciones** con un clic: *Reportes por horario*, *Solicitudes*,
*Links* y *Asistente IA* (además del Constructor, que siempre ven). La seguridad se aplica
en el backend: un viewer recibe **403** en cualquier escritura o en funciones no
habilitadas. El **banco de queries, el catálogo y los links son compartidos** (todos ven
los del admin).

---

## Arquitectura

- **Frontend**: `Reportes.dc.html` (una app React sobre el runtime `support.js`). Se sirve
  como estático.
- **Backend**: FastAPI + SQLite en `backend/`. Auth por cookie de sesión firmada, CRUD por
  usuario y un proxy de IA (`/api/ai`).

```
Reportes.dc.html · support.js        frontend (lo sirve el backend)
Dockerfile · docker-compose.yaml     despliegue de un comando (Coolify/Docker)
backend/
  main.py         app FastAPI + sirve el frontend
  config.py       lee variables de entorno / .env
  db.py           modelos SQLModel + SQLite (con migración ligera de columnas)
  auth.py         hash bcrypt + cookie de sesión
  routes_auth.py  register / login / logout / me
  routes_data.py  CRUD: queries, templates, output-blocks, reports,
                  scheduled-reports, requests, catalog
  ai_proxy.py     /api/ai  (key server-side)
  requirements.txt
```

---

## Correr en local

```bash
cd backend
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
# source .venv/bin/activate

pip install -r requirements.txt

# Configura tus secretos:
cp .env.example .env          # (en Windows: copy .env.example .env)
#   edita .env y pon RB_SESSION_SECRET y tus API keys de IA

uvicorn main:app --reload
```

Abre <http://localhost:8000>, **regístrate** y empieza. La base `report_builder.db` se crea
sola en `backend/`.

### Variables de entorno (`.env`)

| Variable              | Para qué sirve                                            |
|-----------------------|----------------------------------------------------------|
| `RB_SESSION_SECRET`   | Firma la cookie de sesión. **Cámbialo** por algo largo.  |
| `ANTHROPIC_API_KEY`   | Habilita el proveedor Anthropic en el asistente/cruce IA.|
| `OPENAI_API_KEY`      | Habilita OpenAI.                                          |
| `DEEPSEEK_API_KEY`    | Habilita DeepSeek.                                        |
| `RB_ALLOW_REGISTER`   | `0` cierra el registro tras crear tu usuario.            |
| `RB_COOKIE_SECURE`    | `1` cuando sirvas por HTTPS.                              |
| `RB_DB_PATH`          | Ruta alterna del archivo SQLite.                         |

---

## Flujo del módulo Constructor

1. **Banco (Base)** — crea/pega tus queries que ya jalan al 100%, en categorías.
   Selecciona una y ajústala con **bloques rápidos** (rango de fechas, brandpack, gerencia)
   o pídele el cambio al **Asistente IA**; pulsa *Generar query* para ver la query final.
2. **Colector** — la pill central va juntando las queries que marcas con *Añadir al
   colector*. Cuando tengas las que quieres, *Enviar a notebook*.
3. **Notebook (Rompecabezas)** — las queries entran como piezas; *Cruzar con IA* arma la
   tabla final; arrastra **bloques de salida** (PDF/Excel/correo/imagen) que tú pegaste;
   mira la **previsualización** y *Guardar reporte*. Puedes guardar un lienzo como
   **plantilla** reutilizable.

---

## Subir a GitHub

El repo ya está listo: `.gitignore` excluye `.env`, la base `*.db` y `/data`.

```bash
git init
git add .
git commit -m "Panel de Luchito"
git branch -M main
git remote add origin git@github.com:TU_USUARIO/panel-luchito.git
git push -u origin main
```

## Desplegar en tu servidor

### Opción A — Docker (recomendada, un comando)

En el VPS, con Docker instalado:

```bash
git clone <tu-repo> && cd <repo>
cp .env.example .env          # edita RB_SESSION_SECRET, RB_COOKIE_SECURE=1 y tus API keys
docker compose up -d --build
```

Queda escuchando en el puerto **8000**. La base y las capturas se guardan en el volumen
`rbdata` (persisten aunque recrees el contenedor). Para actualizar: `git pull && docker
compose up -d --build`.

**Con Coolify**: crea un recurso con **Build Pack = Docker Compose**, apunta al repo, deja
*Base Directory* = `/` y *Docker Compose Location* = `/docker-compose.yaml`. En
**Environment Variables** pon `RB_SESSION_SECRET` y tus API keys; en **Persistent Storage**
Coolify mantiene el volumen `rbdata`. Asigna un **dominio** al servicio `web` (Coolify lo
enruta al puerto 8000 con HTTPS) y deja `RB_COOKIE_SECURE=1`.

### Opción B — Sin Docker (uvicorn/gunicorn)

```bash
cd backend && pip install -r requirements.txt gunicorn
gunicorn main:app -k uvicorn.workers.UvicornWorker -b 127.0.0.1:8000
```

### Nginx + HTTPS (para cualquiera de las dos)

```nginx
server {
  server_name reportes.tudominio.com;
  location / {
    proxy_pass http://127.0.0.1:8000;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
  }
}
```

Usa Certbot (Let's Encrypt) para el certificado y pon `RB_COOKIE_SECURE=1`. Tras crear tu
usuario, `RB_ALLOW_REGISTER=0` cierra el registro.

**Respaldo**: copia `report_builder.db` (con Docker está en el volumen `rbdata`; sin Docker,
en `backend/`). **Nunca subas** tu `.env` ni la base a un repo público.

---

## Notas

- **Primera vez en Reportes por horario**: pulsa *Cargar agenda por defecto* (o el botón en
  *Ajustes*) para sembrar los 26 reportes de ejemplo; luego edítalos a tu gusto.
- La migración de la base es automática al arrancar (`db.py` añade columnas nuevas sin
  borrar datos).
- Para probar el backend sin navegador: `TestClient` de FastAPI.
