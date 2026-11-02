FROM python:3.11-slim

# Installer FFmpeg
RUN apt-get update && apt-get install -y \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Configurer le workspace
WORKDIR /app

# Copier les fichiers de projet
COPY pyproject.toml .
COPY src/ ./src/
COPY assets/ ./assets/

# Installer les dépendances
RUN pip install --no-cache-dir -e .

# Créer le répertoire workspace
RUN mkdir -p /app/workspace

# Configuration par défaut
ENV CLIPFORGE_WORKSPACE=/app/workspace

# Point d'entrée
CMD ["clipforge", "--help"]
