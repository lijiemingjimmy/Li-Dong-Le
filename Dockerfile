ARG PYTHON_IMAGE=python:3.13-slim-bookworm@sha256:281d39ff02e3b389401586134ff9e6572954687822a58055ec07a60ded4e0b7f
FROM ${PYTHON_IMAGE}
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 LDL_STATE_DIR=/data/state ADB_TARGET=android:5555 FRIDA_TARGET=android:27042
ARG DEBIAN_MIRROR=deb.debian.org
RUN sed -i "s|http://deb.debian.org|https://${DEBIAN_MIRROR}|g" /etc/apt/sources.list.d/debian.sources \
    && apt-get -o Acquire::Retries=3 update && apt-get -o Acquire::Retries=3 install -y --no-install-recommends adb tzdata ca-certificates \
    && rm -rf /var/lib/apt/lists/*
ARG PIP_INDEX_URL=https://pypi.org/simple
RUN pip install --no-cache-dir --index-url "$PIP_INDEX_URL" frida==16.7.19
WORKDIR /app
COPY app/ /app/
COPY web/ /web/
COPY LICENSE THIRD_PARTY.md /licenses/
EXPOSE 6080
ENTRYPOINT ["python3", "/app/controller.py"]
CMD ["serve"]
