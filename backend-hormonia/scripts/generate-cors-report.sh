#!/bin/bash
###############################################################################
# Generate CORS Validation Report
# Purpose: Combine validation results into a comprehensive report
# Usage: ./generate-cors-report.sh
###############################################################################

set -e

REPORT_DIR="/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia"
TEXT_REPORT="$REPORT_DIR/cors-validation-report.txt"
JSON_REPORT="$REPORT_DIR/cors-validation-report.json"
HTML_REPORT="$REPORT_DIR/cors-validation-report.html"

echo "Generating CORS validation report..."

# Check if reports exist
if [ ! -f "$TEXT_REPORT" ] && [ ! -f "$JSON_REPORT" ]; then
    echo "Error: No validation reports found"
    exit 1
fi

# Generate HTML report from JSON if available
if [ -f "$JSON_REPORT" ]; then
    cat > "$HTML_REPORT" << 'EOF'
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CORS Validation Report</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background: #f5f5f5;
        }
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            border-radius: 10px;
            margin-bottom: 30px;
        }
        .summary {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        .metric-card {
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .metric-value {
            font-size: 2em;
            font-weight: bold;
            margin: 10px 0;
        }
        .pass { color: #10b981; }
        .fail { color: #ef4444; }
        .warning { color: #f59e0b; }
        .test-section {
            background: white;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .test-header {
            display: flex;
            align-items: center;
            margin-bottom: 15px;
        }
        .test-status {
            margin-left: auto;
            padding: 5px 15px;
            border-radius: 20px;
            font-weight: bold;
        }
        .status-pass { background: #d1fae5; color: #065f46; }
        .status-fail { background: #fee2e2; color: #991b1b; }
        .status-warning { background: #fef3c7; color: #92400e; }
        pre {
            background: #f9fafb;
            padding: 15px;
            border-radius: 5px;
            overflow-x: auto;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>CORS Validation Report</h1>
        <p id="timestamp"></p>
    </div>

    <div class="summary" id="summary"></div>
    <div id="tests"></div>

    <script>
        fetch('cors-validation-report.json')
            .then(response => response.json())
            .then(data => {
                // Update timestamp
                document.getElementById('timestamp').textContent =
                    `Generated: ${new Date(data.timestamp).toLocaleString()}`;

                // Update summary
                const summary = document.getElementById('summary');
                summary.innerHTML = `
                    <div class="metric-card">
                        <div>Total Tests</div>
                        <div class="metric-value">${data.summary.total}</div>
                    </div>
                    <div class="metric-card">
                        <div>Passed</div>
                        <div class="metric-value pass">${data.summary.passed}</div>
                    </div>
                    <div class="metric-card">
                        <div>Failed</div>
                        <div class="metric-value fail">${data.summary.failed}</div>
                    </div>
                    <div class="metric-card">
                        <div>Warnings</div>
                        <div class="metric-value warning">${data.summary.warnings}</div>
                    </div>
                    <div class="metric-card">
                        <div>Pass Rate</div>
                        <div class="metric-value ${data.summary.passRate >= 95 ? 'pass' : 'warning'}">
                            ${data.summary.passRate}%
                        </div>
                    </div>
                `;

                // Update tests
                const tests = document.getElementById('tests');
                tests.innerHTML = data.tests.map(test => `
                    <div class="test-section">
                        <div class="test-header">
                            <h3>${test.name}</h3>
                            <span class="test-status status-${test.status}">
                                ${test.status.toUpperCase()}
                            </span>
                        </div>
                        <pre>${JSON.stringify(test.details, null, 2)}</pre>
                    </div>
                `).join('');
            });
    </script>
</body>
</html>
EOF

    echo "✓ HTML report generated: $HTML_REPORT"
fi

# Display summary
if [ -f "$TEXT_REPORT" ]; then
    echo ""
    echo "=== Report Summary ==="
    tail -n 10 "$TEXT_REPORT"
fi

echo ""
echo "Reports available:"
echo "  - Text: $TEXT_REPORT"
[ -f "$JSON_REPORT" ] && echo "  - JSON: $JSON_REPORT"
[ -f "$HTML_REPORT" ] && echo "  - HTML: $HTML_REPORT"
