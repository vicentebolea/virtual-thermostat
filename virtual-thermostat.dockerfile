FROM python:3.10

RUN DEBIAN_FRONTEND=noninteractive apt -y --no-install-recommends update && \
    DEBIAN_FRONTEND=noninteractive apt -y --no-install-recommends upgrade && \
    DEBIAN_FRONTEND=noninteractive apt -y --no-install-recommends install git

RUN python3 -mpip install python-kasa

COPY . /opt/virtual-thermostat
RUN pip install /opt/virtual-thermostat

# Default to CLI, but allow override
CMD [ "vthermostat-cli" ]
