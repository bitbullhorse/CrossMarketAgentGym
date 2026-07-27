FROM python:3.11-slim-bookworm AS builder

ARG PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
ARG CMAG_EXTRAS=service
ENV PIP_INDEX_URL=${PIP_INDEX_URL} \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /build
COPY pyproject.toml README.md LICENSE CITATION.cff constraints-cpu.txt ./
COPY src ./src
COPY configs ./configs
COPY data/sample ./data/sample
COPY release ./release
COPY schemas/rc1 ./schemas/rc1
RUN python -m pip wheel \
    --constraint constraints-cpu.txt \
    --wheel-dir /wheels \
    ".[${CMAG_EXTRAS}]"

FROM python:3.11-slim-bookworm AS runtime

ARG CMAG_EXTRAS=service
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

RUN groupadd --gid 10001 cmag \
    && useradd --uid 10001 --gid cmag --create-home cmag
COPY --from=builder /wheels /wheels
RUN python -m pip install --no-index --find-links=/wheels \
    "crossmarket-agent-gym[${CMAG_EXTRAS}]" \
    && rm -rf /wheels

WORKDIR /workspace
COPY --from=builder --chown=10001:10001 /build/configs /workspace/configs
COPY --from=builder --chown=10001:10001 /build/data/sample /workspace/data/sample
RUN mkdir -p /workspace/runs \
    && chown -R cmag:cmag /workspace
USER cmag

ENTRYPOINT ["cmag"]
CMD ["--help"]
