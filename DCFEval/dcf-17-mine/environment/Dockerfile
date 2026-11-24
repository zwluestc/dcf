FROM debian:12-slim
RUN set -eu; \
    if [ -f /etc/apt/sources.list.d/debian.sources ]; then \
      cp /etc/apt/sources.list.d/debian.sources /tmp/debian.sources.bak; \
      sed -i 's|deb.debian.org|mirrors.aliyun.com|g' /etc/apt/sources.list.d/debian.sources; \
      if ! apt-get -o Acquire::Retries=2 -o Acquire::http::Timeout=15 update; then \
        mv /tmp/debian.sources.bak /etc/apt/sources.list.d/debian.sources; \
        apt-get -o Acquire::Retries=2 update; \
      fi; \
      rm -f /tmp/debian.sources.bak; \
    else \
      apt-get -o Acquire::Retries=2 update; \
    fi; \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      bash python3 python3-openpyxl libreoffice-calc ca-certificates && \
    rm -rf /var/lib/apt/lists/*
WORKDIR /work
COPY data /work/data
