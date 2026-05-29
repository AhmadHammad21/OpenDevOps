# OpenDevOps OSS backend image.
#
# IMPORTANT: build from the REPO ROOT so the opendevops-core path dependency
# (apps/backend -> ../core) is in the build context:
#   docker build -f apps/backend/Dockerfile -t opendevops-backend .
# (The docker-compose files set this context automatically.)

FROM python:3.12.9-slim-bookworm

COPY --from=ghcr.io/astral-sh/uv:0.6.17 /uv /uvx /bin/

# CLIs for the bash execution tool (read-only use): AWS CLI v2, Azure CLI, and
# kubectl + kubelogin (for EKS/AKS). git is needed by uv for any git deps.
# Node.js + the Claude Code CLI enable CLAUDE_CODE_AUTODETECT=true to work in the
# container the same way it does on the host — when ~/.claude is mounted in, the
# OAuth subscription login is reused as the Anthropic backend.
RUN apt-get update && apt-get install -y --no-install-recommends curl unzip ca-certificates git \
    # AWS CLI v2
    && curl -fsSL "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o /tmp/awscliv2.zip \
    && unzip -q /tmp/awscliv2.zip -d /tmp && /tmp/aws/install \
    && rm -rf /tmp/aws /tmp/awscliv2.zip \
    # Azure CLI
    && curl -sL https://aka.ms/InstallAzureCLIDeb | bash \
    # kubectl + kubelogin (Azure's installer drops both on PATH)
    && az aks install-cli \
         --install-location /usr/local/bin/kubectl \
         --kubelogin-install-location /usr/local/bin/kubelogin \
    # Node.js LTS + Claude Code CLI (for CLAUDE_CODE_AUTODETECT)
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && npm install -g @anthropic-ai/claude-code \
    && apt-get purge -y --auto-remove unzip \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app
# core is the path dependency of the backend — copy both, preserving layout.
COPY apps/core/ apps/core/
COPY apps/backend/ apps/backend/

WORKDIR /app/apps/backend
RUN uv sync --frozen --no-dev

RUN groupadd --gid 10001 app \
    && useradd --uid 10001 --gid app --create-home --shell /usr/sbin/nologin app \
    && chown -R app:app /app \
    # /data is the SQLite mount point (docker-compose.sqlite.yml). The named volume
    # inherits this dir's ownership on first mount; without this it stays root-owned
    # and the non-root `app` user can't create agent.db.
    && mkdir -p /data \
    && chown app:app /data

ENV PATH="/app/apps/backend/.venv/bin:$PATH" \
    HOME="/home/app" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

USER app

EXPOSE 8000

CMD ["uvicorn", "api.app:app", "--host", "0.0.0.0", "--port", "8000"]
