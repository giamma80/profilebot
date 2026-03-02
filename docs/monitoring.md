# Monitoring Stack (Grafana + Prometheus)

Questo documento descrive come avviare e usare lo stack di observability basato su Prometheus e Grafana.

## Componenti

- **Prometheus**: scraping e storage metriche
- **Grafana**: dashboard e visualizzazione
- **redis-exporter**: metriche Redis
- **celery-exporter**: metriche Celery
- **Qdrant**: metriche native (`/metrics`)
- **FastAPI**: metriche API (`/metrics`)

## Avvio stack monitoring

Avvio stack monitoring (Prometheus + Grafana + exporter):
- `make monitoring-up`

Stop stack monitoring:
- `make monitoring-down`

Avvio ambiente dev + monitoring:
- `make system-and-monitoring`

Stop ambiente dev + monitoring:
- `make system-and-monitoring-down`

> Nota: lo stack monitoring usa il profilo `monitoring` di Docker Compose e rimane opzionale. Non impatta `make system` o `make docker-full` se non richiesto.

## URL utili

- Grafana: `http://localhost:3000` (admin/admin)
- Prometheus: `http://localhost:9090`
- FastAPI metrics: `http://localhost:8000/metrics` (quando API è attiva)
- Qdrant metrics: `http://localhost:6333/metrics`

## Grafana provisioning

Grafana viene configurata automaticamente con:
- datasource Prometheus
- dashboard minime per Redis, Celery, Qdrant e API

I file si trovano in:
- `config/monitoring/grafana/provisioning/datasources/`
- `config/monitoring/grafana/provisioning/dashboards/`
- `config/monitoring/grafana/dashboards/`

## Prometheus scraping

Prometheus legge la config in `config/monitoring/prometheus.yml` con scrape interval a 15s.

Targets principali:
- `redis-exporter:9121`
- `celery-exporter:9808`
- `qdrant:6333/metrics`
- `api:8000/metrics`
