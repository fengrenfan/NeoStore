FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# Where the build fetches its packages from.
#
# These are build args whose defaults are the canonical upstreams, so a build on
# an unrestricted network is unaffected. A build whose network cannot reach them
# — from mainland China both `deb.debian.org` (tens of KB/s) and `pypi.org`
# (unreachable) are the norm — points them at a local mirror through
# docker-compose instead of patching this file.
ARG APT_MIRROR=deb.debian.org
ARG PIP_INDEX_URL=https://pypi.org/simple
ARG PIP_TRUSTED_HOST=pypi.org

WORKDIR /srv

# `build-essential` is here for the day a dependency has no manylinux wheel;
# today's set ships wheels, but the layer is cheap on a mirror and expensive to
# discover missing at deploy time.
RUN if [ "${APT_MIRROR}" != "deb.debian.org" ]; then \
        sed -i "s|deb.debian.org|${APT_MIRROR}|g" /etc/apt/sources.list.d/debian.sources; \
    fi \
    && apt-get update \
    && apt-get install -y --no-install-recommends build-essential curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
COPY app ./app
COPY alembic.ini ./
COPY alembic ./alembic

RUN pip install --index-url "${PIP_INDEX_URL}" --trusted-host "${PIP_TRUSTED_HOST}" .

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=5 \
    CMD curl -fsS http://localhost:8000/healthz || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
