# Analytics API - Usage Examples

## Table of Contents
1. [Patient Analytics](#patient-analytics)
2. [Quiz Analytics](#quiz-analytics)
3. [Dashboard Analytics](#dashboard-analytics)
4. [Caching Examples](#caching-examples)
5. [Error Handling](#error-handling)

---

## Patient Analytics

### Get Patient Engagement

**Endpoint**: `GET /api/v2/analytics/patient-engagement`

**Request**:
```bash
curl -X GET "https://api.example.com/api/v2/analytics/patient-engagement" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json"
```

**Response**:
```json
{
  "engagement_levels": {
    "no_quizzes": 45,
    "low_engagement": 120,
    "high_engagement": 35
  },
  "average_quizzes_per_patient": 3.45,
  "total_active_patients": 200
}
```

**Python Example**:
```python
import requests

response = requests.get(
    "https://api.example.com/api/v2/analytics/patient-engagement",
    headers={"Authorization": f"Bearer {token}"}
)

data = response.json()
print(f"Total patients: {data['total_active_patients']}")
print(f"Average quizzes: {data['average_quizzes_per_patient']}")
```

**JavaScript Example**:
```javascript
const response = await fetch(
  'https://api.example.com/api/v2/analytics/patient-engagement',
  {
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json'
    }
  }
);

const data = await response.json();
console.log('Engagement levels:', data.engagement_levels);
```

---

### Get Risk Assessment

**Endpoint**: `GET /api/v2/analytics/risk-assessment`

**Query Parameters**:
- `risk_level` (optional): Filter by risk level (low, medium, high, critical)
- `limit` (optional): Max patients (1-200, default 50)
- `lookback_days` (optional): Days to analyze (1-90, default 7)

**Request**:
```bash
curl -X GET "https://api.example.com/api/v2/analytics/risk-assessment?risk_level=high&limit=10&lookback_days=14" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**Response**:
```json
{
  "success": true,
  "risk_level_filter": "high",
  "risk_assessments": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "patient_id": "550e8400-e29b-41d4-a716-446655440000",
      "name": "João Silva",
      "risk_level": "high",
      "risk_factors": [
        "no_response_7d",
        "missed_quiz",
        "medication_skip"
      ],
      "last_response": "2025-11-23T10:30:00",
      "recommended_actions": [
        "send_reminder",
        "schedule_call",
        "alert_physician"
      ]
    }
  ],
  "total_patients": 10,
  "generated_at": "2025-11-30T13:00:00",
  "lookback_days": 14
}
```

**Python Example**:
```python
# Get all critical risk patients
response = requests.get(
    "https://api.example.com/api/v2/analytics/risk-assessment",
    params={"risk_level": "critical", "limit": 100},
    headers={"Authorization": f"Bearer {token}"}
)

critical_patients = response.json()["risk_assessments"]

for patient in critical_patients:
    print(f"⚠️  {patient['name']} - {', '.join(patient['risk_factors'])}")
    print(f"   Actions: {', '.join(patient['recommended_actions'])}")
```

---

## Quiz Analytics

### Get Quiz Status Distribution

**Endpoint**: `GET /api/v2/analytics/quiz-status`

**Query Parameters**:
- `month` (optional): Month filter (1-12)
- `year` (optional): Year filter (2020+)

**Request**:
```bash
# Get status for November 2025
curl -X GET "https://api.example.com/api/v2/analytics/quiz-status?month=11&year=2025" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**Response**:
```json
{
  "distribution": {
    "started": 45,
    "completed": 120,
    "cancelled": 5
  },
  "total": 170,
  "filters": {
    "month": 11,
    "year": 2025
  }
}
```

**Chart.js Example**:
```javascript
const response = await fetch('/api/v2/analytics/quiz-status?month=11&year=2025');
const data = await response.json();

const chart = new Chart(ctx, {
  type: 'doughnut',
  data: {
    labels: ['Started', 'Completed', 'Cancelled'],
    datasets: [{
      data: [
        data.distribution.started,
        data.distribution.completed,
        data.distribution.cancelled
      ],
      backgroundColor: ['#f59e0b', '#10b981', '#ef4444']
    }]
  }
});
```

---

### Get Completion Trend

**Endpoint**: `GET /api/v2/analytics/completion-trend`

**Query Parameters**:
- `months` (optional): Number of months (1-24, default 6)

**Request**:
```bash
# Get last 12 months trend
curl -X GET "https://api.example.com/api/v2/analytics/completion-trend?months=12" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**Response**:
```json
{
  "trend": [
    {
      "year": 2025,
      "month": 1,
      "total": 150,
      "completed": 120,
      "completion_rate": 80.0
    },
    {
      "year": 2025,
      "month": 2,
      "total": 160,
      "completed": 135,
      "completion_rate": 84.38
    }
  ],
  "period": {
    "months": 12,
    "start_date": "2024-12-01T00:00:00",
    "end_date": "2025-11-30T13:00:00"
  }
}
```

**Recharts Example (React)**:
```jsx
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip } from 'recharts';

function CompletionTrendChart() {
  const [data, setData] = useState([]);

  useEffect(() => {
    fetch('/api/v2/analytics/completion-trend?months=12')
      .then(res => res.json())
      .then(result => {
        const formatted = result.trend.map(item => ({
          name: `${item.month}/${item.year}`,
          rate: item.completion_rate
        }));
        setData(formatted);
      });
  }, []);

  return (
    <LineChart width={600} height={300} data={data}>
      <CartesianGrid strokeDasharray="3 3" />
      <XAxis dataKey="name" />
      <YAxis />
      <Tooltip />
      <Line type="monotone" dataKey="rate" stroke="#2563eb" />
    </LineChart>
  );
}
```

---

## Dashboard Analytics

### Get Overview

**Endpoint**: `GET /api/v2/analytics/overview`

**Query Parameters**:
- `start_date` (optional): Start date (ISO format)
- `end_date` (optional): End date (ISO format)

**Request**:
```bash
# Get overview for November 2025
curl -X GET "https://api.example.com/api/v2/analytics/overview?start_date=2025-11-01T00:00:00&end_date=2025-11-30T23:59:59" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**Response**:
```json
{
  "total_patients": 200,
  "total_quizzes": 450,
  "completed_quizzes": 380,
  "completion_rate": 84.44,
  "active_patients_30d": 156,
  "period": {
    "start_date": "2025-11-01T00:00:00",
    "end_date": "2025-11-30T23:59:59"
  }
}
```

**Dashboard Component (React)**:
```jsx
function DashboardOverview() {
  const [metrics, setMetrics] = useState(null);

  useEffect(() => {
    fetch('/api/v2/analytics/overview')
      .then(res => res.json())
      .then(setMetrics);
  }, []);

  if (!metrics) return <Loading />;

  return (
    <div className="grid grid-cols-4 gap-4">
      <MetricCard
        title="Total Patients"
        value={metrics.total_patients}
        icon={<UsersIcon />}
      />
      <MetricCard
        title="Total Quizzes"
        value={metrics.total_quizzes}
        icon={<ClipboardIcon />}
      />
      <MetricCard
        title="Completion Rate"
        value={`${metrics.completion_rate}%`}
        icon={<CheckCircleIcon />}
      />
      <MetricCard
        title="Active (30d)"
        value={metrics.active_patients_30d}
        icon={<ActivityIcon />}
      />
    </div>
  );
}
```

---

### Get Treatment Distribution

**Endpoint**: `GET /api/v2/analytics/treatment-distribution`

**Query Parameters**:
- `period`: Time period (7d, 30d, 90d, all)

**Request**:
```bash
curl -X GET "https://api.example.com/api/v2/analytics/treatment-distribution?period=30d" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**Response**:
```json
{
  "period": "30d",
  "total_patients": 200,
  "distribution": [
    {
      "treatment_type": "Quimioterapia",
      "count": 85,
      "percentage": 42.5,
      "color": "#2563eb"
    },
    {
      "treatment_type": "Radioterapia",
      "count": 65,
      "percentage": 32.5,
      "color": "#10b981"
    },
    {
      "treatment_type": "Imunoterapia",
      "count": 50,
      "percentage": 25.0,
      "color": "#f59e0b"
    }
  ],
  "trend_data": [
    {"week": "2025-11-01", "count": 45},
    {"week": "2025-11-08", "count": 52},
    {"week": "2025-11-15", "count": 48},
    {"week": "2025-11-22", "count": 55}
  ],
  "last_updated": "2025-11-30T13:00:00"
}
```

**D3.js Pie Chart Example**:
```javascript
const response = await fetch('/api/v2/analytics/treatment-distribution?period=30d');
const data = await response.json();

const svg = d3.select('#chart')
  .append('svg')
  .attr('width', 400)
  .attr('height', 400);

const pie = d3.pie()
  .value(d => d.count);

const arc = d3.arc()
  .innerRadius(0)
  .outerRadius(150);

const g = svg.selectAll('.arc')
  .data(pie(data.distribution))
  .enter()
  .append('g')
  .attr('class', 'arc')
  .attr('transform', 'translate(200, 200)');

g.append('path')
  .attr('d', arc)
  .style('fill', d => d.data.color);

g.append('text')
  .attr('transform', d => `translate(${arc.centroid(d)})`)
  .text(d => `${d.data.treatment_type}: ${d.data.percentage}%`);
```

---

## Caching Examples

### Check Cache Status

```python
import redis

# Connect to Redis
r = redis.Redis(host='localhost', port=6379, db=0)

# Check if analytics are cached
cache_key = "analytics:v2:overview:*"
cached_keys = r.keys(cache_key)

print(f"Cached analytics: {len(cached_keys)}")
for key in cached_keys:
    ttl = r.ttl(key)
    print(f"  {key.decode()}: {ttl}s remaining")
```

### Clear Analytics Cache

```bash
# Clear all analytics cache
redis-cli --scan --pattern "analytics:v2:*" | xargs redis-cli del

# Clear specific endpoint cache
redis-cli --scan --pattern "analytics:v2:overview:*" | xargs redis-cli del
```

### Bypass Cache (Force Refresh)

```python
# Option 1: Clear cache before request
r.delete("analytics:v2:overview:...")

# Option 2: Add timestamp to force new cache key
import time
response = requests.get(
    f"/api/v2/analytics/overview?_={int(time.time())}"
)
```

---

## Error Handling

### Handle API Errors

```python
import requests
from requests.exceptions import RequestException

def get_analytics_overview():
    try:
        response = requests.get(
            "https://api.example.com/api/v2/analytics/overview",
            headers={"Authorization": f"Bearer {token}"},
            timeout=30
        )
        response.raise_for_status()
        return response.json()

    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 401:
            print("Authentication failed")
        elif e.response.status_code == 403:
            print("Access denied")
        elif e.response.status_code == 500:
            print("Server error")
        else:
            print(f"HTTP error: {e}")

    except requests.exceptions.Timeout:
        print("Request timeout")

    except requests.exceptions.ConnectionError:
        print("Connection error")

    except RequestException as e:
        print(f"Request failed: {e}")

    return None
```

### Retry Logic

```python
import time
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10)
)
def get_analytics_with_retry():
    response = requests.get(
        "https://api.example.com/api/v2/analytics/overview",
        headers={"Authorization": f"Bearer {token}"}
    )
    response.raise_for_status()
    return response.json()

# Usage
try:
    data = get_analytics_with_retry()
    print(data)
except Exception as e:
    print(f"Failed after retries: {e}")
```

### JavaScript Error Handling

```javascript
async function getAnalytics() {
  try {
    const response = await fetch('/api/v2/analytics/overview', {
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      }
    });

    if (!response.ok) {
      if (response.status === 401) {
        throw new Error('Authentication required');
      } else if (response.status === 403) {
        throw new Error('Access denied');
      } else if (response.status >= 500) {
        throw new Error('Server error');
      } else {
        throw new Error(`HTTP ${response.status}`);
      }
    }

    return await response.json();

  } catch (error) {
    console.error('Analytics fetch failed:', error);

    // Show user-friendly message
    if (error.message.includes('Authentication')) {
      redirectToLogin();
    } else if (error.message.includes('Server')) {
      showErrorMessage('Server is temporarily unavailable');
    } else {
      showErrorMessage('Failed to load analytics');
    }

    return null;
  }
}
```

---

## Rate Limiting

### Respect Rate Limits

```python
import time

def get_all_analytics():
    """Get all analytics with rate limiting."""

    endpoints = [
        '/overview',
        '/quiz-status',
        '/completion-trend',
        '/patient-engagement',
        '/treatment-distribution',
        '/risk-assessment'
    ]

    results = {}

    for endpoint in endpoints:
        response = requests.get(
            f"https://api.example.com/api/v2/analytics{endpoint}",
            headers={"Authorization": f"Bearer {token}"}
        )

        results[endpoint] = response.json()

        # Avoid rate limiting (60 req/min = 1 req/sec)
        time.sleep(1)

    return results
```

---

## WebSocket Real-time Updates

```javascript
// Subscribe to real-time analytics updates
const ws = new WebSocket('wss://api.example.com/ws/analytics');

ws.onmessage = (event) => {
  const update = JSON.parse(event.data);

  switch (update.type) {
    case 'overview_update':
      updateDashboard(update.data);
      break;

    case 'new_risk_patient':
      alertRiskPatient(update.data);
      break;

    case 'quiz_completed':
      updateCompletionChart(update.data);
      break;
  }
};

ws.onerror = (error) => {
  console.error('WebSocket error:', error);
  // Fallback to polling
  setInterval(pollAnalytics, 30000);
};
```

---

## Export Analytics

```python
import csv
import pandas as pd

def export_to_csv(endpoint, filename):
    """Export analytics to CSV."""

    response = requests.get(
        f"https://api.example.com/api/v2/analytics{endpoint}",
        headers={"Authorization": f"Bearer {token}"}
    )

    data = response.json()

    # Convert to pandas DataFrame
    if 'trend' in data:
        df = pd.DataFrame(data['trend'])
    elif 'distribution' in data:
        df = pd.DataFrame(data['distribution'])
    elif 'risk_assessments' in data:
        df = pd.DataFrame(data['risk_assessments'])
    else:
        df = pd.DataFrame([data])

    # Export to CSV
    df.to_csv(filename, index=False)
    print(f"✓ Exported to {filename}")

# Usage
export_to_csv('/completion-trend?months=12', 'completion_trend.csv')
export_to_csv('/risk-assessment?risk_level=high', 'high_risk_patients.csv')
```

---

## Additional Resources

- **API Documentation**: `/docs` (Swagger UI)
- **Developer Guide**: `app/api/v2/routers/analytics/README.md`
- **Refactoring Details**: `docs/ANALYTICS_REFACTORING.md`
- **Quick Summary**: `docs/ANALYTICS_REFACTORING_SUMMARY.md`
