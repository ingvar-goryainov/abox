FROM python:3.12-slim

ENV FASTEMBED_CACHE_PATH=/opt/fastembed \
    HF_HOME=/opt/hf

RUN pip install --no-cache-dir mcp-server-qdrant==0.8.1

RUN python -c "from fastembed import TextEmbedding; TextEmbedding('sentence-transformers/all-MiniLM-L6-v2')" \
 && chmod -R a+rX /opt/fastembed /opt/hf

USER 65532:65532

# Default transport is stdio, which is what kmcp adapts to streamable HTTP.
ENTRYPOINT ["/usr/local/bin/mcp-server-qdrant"]
