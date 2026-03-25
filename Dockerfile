# Stage 1: Install translit-rs wheel into a venv
FROM python:3.12-slim AS build

ARG TRANSLIT_VERSION
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

RUN pip install --no-cache-dir translit-rs${TRANSLIT_VERSION:+==$TRANSLIT_VERSION}

# Copy the CLI entrypoint (not included in the PyPI wheel)
COPY python/translit/__main__.py /opt/venv/lib/python3.12/site-packages/translit/__main__.py

# Stage 2: Minimal runtime image
FROM python:3.12-slim

# Create non-root user
RUN groupadd --gid 1000 translit && \
    useradd --uid 1000 --gid translit --no-create-home translit

# Copy venv from build stage
COPY --from=build /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

USER translit

ENTRYPOINT ["python", "-m", "translit"]
