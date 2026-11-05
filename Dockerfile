FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
COPY catalog ./catalog
COPY config ./config
RUN pip install --no-cache-dir .

ENTRYPOINT ["wanderlens"]
CMD ["models", "list"]
