FROM python:3.13-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN chmod +x docker-entrypoint.sh

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD python -c "import http.client; c=http.client.HTTPConnection('localhost',8012); c.request('GET','/api/status'); r=c.getresponse(); exit(0 if r.status==200 else 1)"

RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8012
ENTRYPOINT ["./docker-entrypoint.sh"]
