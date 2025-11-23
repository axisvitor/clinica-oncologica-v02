#!/bin/bash
# ============================================================================
# Celery Monitoring Deployment Script
# ============================================================================
# Deploys complete Celery monitoring stack:
#   - Flower UI
#   - Prometheus metrics
#   - Grafana dashboards
#   - Alert rules
#   - Queue monitoring
#
# Usage:
#   ./scripts/deploy_celery_monitoring.sh [--production]
#
# Options:
#   --production: Deploy in production mode with authentication
#   --dev: Deploy in development mode (default)
# ============================================================================

set -e  # Exit on error
set -u  # Exit on undefined variable
set -o pipefail  # Exit on pipe failure

# ============================================================================
# CONFIGURATION
# ============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
MONITORING_DIR="$PROJECT_ROOT/monitoring"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
ENVIRONMENT="dev"
FLOWER_AUTH="${FLOWER_BASIC_AUTH:-admin:admin123}"
GRAFANA_ADMIN_PASSWORD="${GRAFANA_ADMIN_PASSWORD:-admin}"

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_command() {
    if ! command -v "$1" &> /dev/null; then
        log_error "$1 is required but not installed."
        exit 1
    fi
}

wait_for_service() {
    local service_name=$1
    local url=$2
    local max_attempts=30
    local attempt=1

    log_info "Waiting for $service_name to be ready..."

    while [ $attempt -le $max_attempts ]; do
        if curl -f -s "$url" > /dev/null 2>&1; then
            log_success "$service_name is ready!"
            return 0
        fi

        echo -n "."
        sleep 2
        attempt=$((attempt + 1))
    done

    log_error "$service_name failed to start after $max_attempts attempts"
    return 1
}

# ============================================================================
# VALIDATION
# ============================================================================

validate_environment() {
    log_info "Validating environment..."

    # Check required commands
    check_command docker
    check_command docker-compose
    check_command curl

    # Check if monitoring directory exists
    if [ ! -d "$MONITORING_DIR" ]; then
        log_error "Monitoring directory not found: $MONITORING_DIR"
        exit 1
    fi

    # Check if .env file exists
    if [ ! -f "$PROJECT_ROOT/.env" ]; then
        log_warning ".env file not found. Using default values."
    fi

    log_success "Environment validation complete"
}

# ============================================================================
# DOCKER OPERATIONS
# ============================================================================

build_flower_container() {
    log_info "Building Flower container..."

    cd "$PROJECT_ROOT"

    docker build \
        -t hormonia-flower:latest \
        -f flower/Dockerfile \
        flower/

    log_success "Flower container built successfully"
}

start_monitoring_stack() {
    log_info "Starting monitoring stack..."

    cd "$MONITORING_DIR"

    # Export environment variables
    export FLOWER_BASIC_AUTH="$FLOWER_AUTH"
    export GRAFANA_ADMIN_PASSWORD="$GRAFANA_ADMIN_PASSWORD"

    # Start services
    docker-compose -f docker-compose.monitoring.yml up -d

    log_success "Monitoring stack started"
}

stop_monitoring_stack() {
    log_info "Stopping existing monitoring stack..."

    cd "$MONITORING_DIR"
    docker-compose -f docker-compose.monitoring.yml down || true

    log_success "Monitoring stack stopped"
}

# ============================================================================
# PROMETHEUS CONFIGURATION
# ============================================================================

configure_prometheus() {
    log_info "Configuring Prometheus..."

    local prometheus_config="$MONITORING_DIR/prometheus/prometheus.yml"

    # Backup existing config
    if [ -f "$prometheus_config" ]; then
        cp "$prometheus_config" "${prometheus_config}.backup.$(date +%Y%m%d%H%M%S)"
    fi

    # Add Celery worker metrics scrape config if not present
    if ! grep -q "job_name: 'celery_worker'" "$prometheus_config"; then
        log_info "Adding Celery worker scrape configuration..."

        cat >> "$prometheus_config" <<'EOF'

  # Celery Worker Metrics
  - job_name: 'celery_worker'
    static_configs:
      - targets: ['worker:9090']
    scrape_interval: 10s
    scrape_timeout: 5s

  # Celery Beat Metrics
  - job_name: 'celery_beat'
    static_configs:
      - targets: ['beat:9091']
    scrape_interval: 30s
    scrape_timeout: 5s
EOF
    fi

    # Load alert rules
    local alert_rules_dir="$MONITORING_DIR/prometheus/alerts"
    mkdir -p "$alert_rules_dir"

    # Copy Celery alert rules
    if [ -f "$alert_rules_dir/celery_alerts.yml" ]; then
        log_info "Celery alert rules already present"
    else
        log_warning "Celery alert rules not found at expected location"
    fi

    log_success "Prometheus configuration complete"
}

reload_prometheus() {
    log_info "Reloading Prometheus configuration..."

    # Send reload signal to Prometheus
    curl -X POST http://localhost:9090/-/reload || {
        log_warning "Failed to reload Prometheus. It may need manual restart."
    }

    log_success "Prometheus reloaded"
}

# ============================================================================
# GRAFANA CONFIGURATION
# ============================================================================

import_grafana_dashboard() {
    log_info "Importing Celery Grafana dashboard..."

    # Wait for Grafana to be ready
    wait_for_service "Grafana" "http://localhost:3000/api/health" || {
        log_error "Grafana is not accessible"
        return 1
    }

    local dashboard_file="$MONITORING_DIR/grafana/dashboards/celery_dashboard.json"

    if [ ! -f "$dashboard_file" ]; then
        log_error "Dashboard file not found: $dashboard_file"
        return 1
    fi

    # Import dashboard via API
    curl -X POST \
        -H "Content-Type: application/json" \
        -u "admin:${GRAFANA_ADMIN_PASSWORD}" \
        -d @"$dashboard_file" \
        http://localhost:3000/api/dashboards/db || {
        log_warning "Failed to import dashboard via API. Check Grafana logs."
        return 1
    }

    log_success "Grafana dashboard imported successfully"
}

configure_grafana_datasource() {
    log_info "Configuring Grafana Prometheus datasource..."

    # Check if datasource already exists
    local datasource_check=$(curl -s -u "admin:${GRAFANA_ADMIN_PASSWORD}" \
        "http://localhost:3000/api/datasources/name/Prometheus" || echo "not found")

    if echo "$datasource_check" | grep -q '"id"'; then
        log_info "Prometheus datasource already configured"
        return 0
    fi

    # Create datasource
    curl -X POST \
        -H "Content-Type: application/json" \
        -u "admin:${GRAFANA_ADMIN_PASSWORD}" \
        -d '{
            "name": "Prometheus",
            "type": "prometheus",
            "url": "http://prometheus:9090",
            "access": "proxy",
            "isDefault": true
        }' \
        http://localhost:3000/api/datasources || {
        log_warning "Failed to create Prometheus datasource"
        return 1
    }

    log_success "Grafana datasource configured"
}

# ============================================================================
# VERIFICATION
# ============================================================================

verify_deployment() {
    log_info "Verifying deployment..."

    local all_healthy=true

    # Check Flower
    if wait_for_service "Flower" "http://localhost:5555/healthcheck"; then
        log_success "✓ Flower is running"
    else
        log_error "✗ Flower is not accessible"
        all_healthy=false
    fi

    # Check Prometheus
    if wait_for_service "Prometheus" "http://localhost:9090/-/healthy"; then
        log_success "✓ Prometheus is running"
    else
        log_error "✗ Prometheus is not accessible"
        all_healthy=false
    fi

    # Check Grafana
    if wait_for_service "Grafana" "http://localhost:3000/api/health"; then
        log_success "✓ Grafana is running"
    else
        log_error "✗ Grafana is not accessible"
        all_healthy=false
    fi

    # Check Celery metrics endpoint
    if curl -f -s "http://localhost:9090/api/v1/targets" | grep -q "celery_worker"; then
        log_success "✓ Celery metrics are being scraped"
    else
        log_warning "⚠ Celery worker metrics not found in Prometheus targets"
    fi

    if [ "$all_healthy" = true ]; then
        log_success "All monitoring services are healthy!"
        return 0
    else
        log_error "Some services failed health checks"
        return 1
    fi
}

# ============================================================================
# MAIN DEPLOYMENT FLOW
# ============================================================================

print_banner() {
    cat << "EOF"
╔═══════════════════════════════════════════════════════════╗
║         Celery Monitoring Stack Deployment               ║
║         Flower + Prometheus + Grafana                     ║
╚═══════════════════════════════════════════════════════════╝
EOF
}

main() {
    print_banner

    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --production)
                ENVIRONMENT="production"
                shift
                ;;
            --dev)
                ENVIRONMENT="dev"
                shift
                ;;
            *)
                log_error "Unknown option: $1"
                echo "Usage: $0 [--production|--dev]"
                exit 1
                ;;
        esac
    done

    log_info "Deploying in $ENVIRONMENT mode"

    # Step 1: Validate
    validate_environment

    # Step 2: Stop existing stack
    stop_monitoring_stack

    # Step 3: Build Flower
    build_flower_container

    # Step 4: Configure Prometheus
    configure_prometheus

    # Step 5: Start monitoring stack
    start_monitoring_stack

    # Wait for services to stabilize
    sleep 10

    # Step 6: Configure Grafana
    configure_grafana_datasource
    import_grafana_dashboard

    # Step 7: Reload Prometheus
    reload_prometheus

    # Step 8: Verify deployment
    if verify_deployment; then
        log_success "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        log_success "  Celery Monitoring Deployment Complete!"
        log_success "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo ""
        echo "Access the monitoring tools:"
        echo "  🌸 Flower UI:      http://localhost:5555"
        echo "     Credentials:    $FLOWER_AUTH"
        echo ""
        echo "  📊 Prometheus:     http://localhost:9090"
        echo ""
        echo "  📈 Grafana:        http://localhost:3000"
        echo "     Credentials:    admin / $GRAFANA_ADMIN_PASSWORD"
        echo ""
        echo "To view logs:"
        echo "  docker-compose -f $MONITORING_DIR/docker-compose.monitoring.yml logs -f flower"
        echo ""
    else
        log_error "Deployment completed with errors. Check logs above."
        exit 1
    fi
}

# Run main function
main "$@"
