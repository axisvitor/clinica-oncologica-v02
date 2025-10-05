#!/bin/sh
# Switch between nginx configurations for different scenarios

set -e

echo "🔄 Nginx Configuration Switcher for Railway"
echo "==========================================="
echo ""

# Check if mode argument is provided
if [ -z "$1" ]; then
    echo "Usage: ./switch-nginx-config.sh [mode]"
    echo ""
    echo "Available modes:"
    echo "  full       - Full config with backend proxy (default)"
    echo "  fallback   - Frontend-only, no backend (503 on /api)"
    echo "  diagnostic - Run diagnostic to help decide"
    echo ""
    echo "Example:"
    echo "  ./switch-nginx-config.sh fallback"
    echo ""
    exit 1
fi

MODE=$1

case $MODE in
    "full")
        echo "📦 Switching to FULL configuration (with backend proxy)"
        echo ""

        if [ ! -f nginx.conf ]; then
            echo "❌ Error: nginx.conf not found"
            exit 1
        fi

        # Update Dockerfile to use full nginx.conf
        if [ -f Dockerfile ]; then
            # Check if using fallback
            if grep -q "nginx.conf.fallback" Dockerfile; then
                echo "🔧 Updating Dockerfile to use nginx.conf..."
                sed -i 's/nginx.conf.fallback/nginx.conf/' Dockerfile
                echo "✅ Dockerfile updated"
            else
                echo "ℹ️  Already using nginx.conf"
            fi
        else
            echo "❌ Error: Dockerfile not found"
            exit 1
        fi

        echo ""
        echo "📋 Next steps:"
        echo "1. Configure environment variables in Railway:"
        echo "   BACKEND_HOST=[backend-service-name].railway.internal"
        echo "   BACKEND_PORT=8000"
        echo ""
        echo "2. Commit and push:"
        echo "   git add Dockerfile"
        echo "   git commit -m 'fix: switch to full nginx config with backend'"
        echo "   git push"
        echo ""
        echo "3. Railway will auto-deploy"
        ;;

    "fallback")
        echo "📦 Switching to FALLBACK configuration (frontend-only)"
        echo ""

        if [ ! -f nginx.conf.fallback ]; then
            echo "❌ Error: nginx.conf.fallback not found"
            exit 1
        fi

        # Update Dockerfile to use fallback nginx.conf
        if [ -f Dockerfile ]; then
            # Check if using full config
            if grep -q "COPY nginx.conf /etc/nginx/nginx.conf.template" Dockerfile; then
                echo "🔧 Updating Dockerfile to use nginx.conf.fallback..."
                sed -i 's/COPY nginx.conf /COPY nginx.conf.fallback /' Dockerfile
                echo "✅ Dockerfile updated"
            else
                echo "ℹ️  Already using nginx.conf.fallback"
            fi
        else
            echo "❌ Error: Dockerfile not found"
            exit 1
        fi

        echo ""
        echo "📋 What this does:"
        echo "✅ Frontend will work (static files)"
        echo "✅ Healthcheck will pass"
        echo "❌ API calls to /api/* will return 503"
        echo "❌ WebSocket will be unavailable"
        echo ""
        echo "📋 Next steps:"
        echo "1. Commit and push:"
        echo "   git add Dockerfile"
        echo "   git commit -m 'fix: use fallback nginx config without backend'"
        echo "   git push"
        echo ""
        echo "2. Railway will auto-deploy"
        echo ""
        echo "3. When backend is ready, run:"
        echo "   ./switch-nginx-config.sh full"
        ;;

    "diagnostic")
        echo "🔍 Running diagnostic to help decide..."
        echo ""

        if [ -f railway-dns-diagnostic.sh ]; then
            chmod +x railway-dns-diagnostic.sh
            ./railway-dns-diagnostic.sh
        else
            echo "❌ railway-dns-diagnostic.sh not found"
            echo ""
            echo "Manual diagnostic:"
            echo "1. Check if backend is deployed in Railway"
            echo "2. If YES → Use 'full' mode with proper BACKEND_HOST"
            echo "3. If NO → Use 'fallback' mode"
        fi
        ;;

    *)
        echo "❌ Invalid mode: $MODE"
        echo ""
        echo "Valid modes: full, fallback, diagnostic"
        exit 1
        ;;
esac

echo ""
echo "🏁 Done!"
