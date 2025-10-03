# Grafana Provisioning Configuration

This directory contains Grafana provisioning configurations for automated setup of datasources and dashboards.

## Directory Structure

```
grafana/
├── datasources/          # Datasource configurations
│   └── prometheus.yml    # Prometheus datasource config
├── dashboards/           # Dashboard provider configurations
│   └── default.yml       # Default dashboard provider
└── README.md            # This file
```

## Datasources

### Prometheus (`datasources/prometheus.yml`)

Configures Prometheus as the primary datasource for metrics collection:

- **URL**: `http://prometheus:9090`
- **Query Timeout**: 60 seconds
- **Time Interval**: 15 seconds
- **HTTP Method**: POST (for better performance with large queries)

## Dashboard Providers

### Default Provider (`dashboards/default.yml`)

Configures the default dashboard provider:

- **Path**: `/var/lib/grafana/dashboards`
- **Update Interval**: 30 seconds
- **UI Updates**: Allowed
- **Auto-reload**: Enabled

## Adding New Dashboards

1. **Export Dashboard**: Export your dashboard as JSON from Grafana UI
2. **Place File**: Save the JSON file in the dashboards directory
3. **Mount Volume**: Ensure the dashboards directory is mounted to `/var/lib/grafana/dashboards` in your Docker container
4. **Restart**: Grafana will automatically detect and load new dashboards within 30 seconds

## Adding New Datasources

1. **Create YAML File**: Create a new `.yml` file in the `datasources/` directory
2. **Follow Format**: Use the same structure as `prometheus.yml`
3. **Restart Grafana**: Restart Grafana container to load new datasources

## Docker Compose Integration

Add these volume mounts to your Grafana service:

```yaml
volumes:
  - ./config/monitoring/grafana/datasources:/etc/grafana/provisioning/datasources:ro
  - ./config/monitoring/grafana/dashboards:/etc/grafana/provisioning/dashboards:ro
  - ./config/monitoring/grafana-dashboards.json:/var/lib/grafana/dashboards/main.json:ro
```

## Environment Variables

Recommended Grafana environment variables:

```yaml
environment:
  - GF_SECURITY_ADMIN_PASSWORD=admin
  - GF_PROVISIONING_ENABLED=true
  - GF_INSTALL_PLUGINS=grafana-clock-panel,grafana-simple-json-datasource
```

## Troubleshooting

- **Datasource not loading**: Check YAML syntax and Grafana logs
- **Dashboard not appearing**: Verify file permissions and JSON format
- **Connection issues**: Ensure Prometheus is accessible at configured URL
- **Performance issues**: Adjust query timeout and time interval settings