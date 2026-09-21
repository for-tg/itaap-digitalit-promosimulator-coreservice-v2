FROM python:3.12-slim-bookworm

# ROOT SECTION: System setup
RUN groupadd -r appuser -g 1001 && \
    useradd -r -u 1001 -g appuser -s /sbin/nologin -c "Application user" appuser && \
    mkdir -p /home/appuser && \
    chown appuser:appuser /home/appuser && \
    chmod 755 /home/appuser && \
    apt-get update && \
    apt-get install -y --no-install-recommends gcc g++ telnet && \
    rm -rf /var/lib/apt/lists/* && \
    pip install --no-cache-dir --upgrade pip

WORKDIR /app

# Copy application files
COPY requirements.txt requirements.txt
COPY ./app ./app

# Set permissions
RUN chmod -R 444 ./app && \
    find ./app -type d -exec chmod 555 {} \; && \
    chown -R root:appuser ./app && \
    chmod 444 requirements.txt && \
    chown root:appuser requirements.txt

# Docker build arguments
ARG AZURE_PAT
ARG AZURE_ARTIFACTS_URL
ARG ITAAP_PYTHON_UTILS_VERSION

# APPUSER SECTION
USER appuser

RUN pip install --no-cache-dir --user \
    --index-url "https://$AZURE_PAT@$AZURE_ARTIFACTS_URL" \
    "itaap-python-utils==$ITAAP_PYTHON_UTILS_VERSION" && \
    pip install --no-cache-dir --user -r requirements.txt

ENTRYPOINT ["python", "-m", "app.main"]