ARG TARGETARCH
FROM --platform=linux/amd64 docker.io/python:3.10 AS base-amd64
FROM --platform=linux/arm64 docker.io/python:3.10 AS base-arm64
FROM --platform=linux/arm/v6 docker.io/arm32v6/python:3-alpine AS base-arm

FROM base-${TARGETARCH}

ARG TARGETARCH
RUN if [ "${TARGETARCH}" = "arm" ]; then \
      apk update && \
      apk add \
        cargo \
        g++ \
        gcc \
        libffi-dev \
        openssl-dev \
        rust \
        ; \
    fi

RUN python3 -mpip install --verbose python-kasa

COPY . /opt/virtual-thermostat
RUN pip install --verbose /opt/virtual-thermostat

# Default to CLI, but allow override
CMD [ "vthermostat-cli" ]
