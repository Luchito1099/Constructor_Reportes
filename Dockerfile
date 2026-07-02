# Imagen del Panel de Luchito (FastAPI sirve la API + el frontend estático).
FROM python:3.12-slim

WORKDIR /app

# Dependencias primero (mejor caché de capas)
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

# Código del proyecto (frontend en la raíz + backend/)
COPY . .

# La base y las imágenes se guardan en /data (monta un volumen ahí para persistir)
ENV RB_DB_PATH=/data/report_builder.db
RUN mkdir -p /data

WORKDIR /app/backend
EXPOSE 8000

# 1 worker basta para SQLite; sube --workers solo si migras a Postgres.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
