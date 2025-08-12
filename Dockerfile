# should be production-ready container

FROM python:3.11-slim as base

# set environment vars
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# install dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# create non-root user
RUN useradd --create-home --shell /bin/bash app

WORKDIR /app

# copy requirements first for better caching
COPY requirements.txt requirements-dev.txt ./

# dev stage
FROM base as development
RUN pip install -r requirements-dev.txt
USER app
COPY . .
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# production stage
FROM base as production

# install production dependencies only
RUN pip install -r requirements.txt

# copy application code
COPY --chown=app:app . .

# switch to non-root user
USER app

# health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/health || exit 1

# expose port
EXPOSE 8000

# default command
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]