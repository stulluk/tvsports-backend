FROM python:3.11-slim-bookworm

WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN pip install --no-cache-dir .

ENV TZ=Europe/Istanbul
ENV PYTHONUNBUFFERED=1
VOLUME ["/srv"]

CMD ["python", "-m", "tvsports_backend", "--output-dir", "/srv", "--loop"]
