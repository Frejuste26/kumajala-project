# ==========================================
# KUMAJALA Backend - Dockerfile pour Render
# ==========================================

# Utiliser Python 3.11 slim pour une image légère
FROM python:3.11-slim

# Métadonnées de l'image
LABEL maintainer="KUMAJALA Team <contact@kumajala.org>"
LABEL description="KUMAJALA API - Traduction vers langues africaines"
LABEL version="1.0.0"

# Définir le répertoire de travail
WORKDIR /app

# Variables d'environnement pour Python
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Installer les dépendances système nécessaires
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copier les fichiers de dépendances
COPY requirements.txt .

# Installer les dépendances Python
RUN pip install --upgrade pip && \
    pip install -r requirements.txt && \
    pip install gunicorn gevent

# Copier le code de l'application
COPY . .

# Créer le dossier data s'il n'existe pas
RUN mkdir -p /app/data

# Créer un utilisateur non-root pour la sécurité
RUN useradd -m -u 1000 kumajala && \
    chown -R kumajala:kumajala /app

# Basculer vers l'utilisateur non-root
USER kumajala

# Exposer le port (Render utilisera la variable PORT)
EXPOSE 5000

# Healthcheck pour vérifier que l'application fonctionne
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:${PORT:-5000}/health || exit 1

# Commande de démarrage avec Gunicorn
# Render définira automatiquement la variable PORT
CMD gunicorn --bind 0.0.0.0:${PORT:-5000} \
    --workers 4 \
    --worker-class gevent \
    --timeout 120 \
    --access-logfile - \
    --error-logfile - \
    --log-level info \
    "app:create_app()"