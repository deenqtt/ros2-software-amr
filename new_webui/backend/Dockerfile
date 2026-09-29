FROM python:3.12-slim

# Fail fast and log straight through, so container logs show a crash rather
# than swallowing it in a buffer.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /srv

# Dependencies first: they change far less often than the source, so this layer
# stays cached across ordinary code edits.
COPY pyproject.toml ./
RUN pip install --upgrade pip && pip install .

COPY app ./app

# Runs as a non-root user. The existing stack writes root-owned files into the
# repository through bind mounts, which is why half that tree cannot be edited
# without sudo.
RUN useradd --create-home --uid 10001 amr \
    && mkdir -p /data /maps \
    && chown -R amr:amr /srv /data /maps
USER amr

ENV AMR_DB_PATH=/data/amr.db \
    AMR_MAPS_DIR=/maps \
    AMR_ROS_MAPS_PATH=/maps \
    AMR_PORT=3002

EXPOSE 3002

HEALTHCHECK --interval=15s --timeout=3s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys;\
sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:3002/ready',timeout=2).status==200 else 1)"

CMD ["uvicorn", "app.asgi:app", "--host", "0.0.0.0", "--port", "3002"]
