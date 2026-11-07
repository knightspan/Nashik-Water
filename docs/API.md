# API reference

Base URL: `https://<your-api>.onrender.com` (local: `http://localhost:8000`).
Interactive OpenAPI docs: `/docs`. All times are ISO 8601; the server stores UTC.

Errors use FastAPI's shape: `{"detail": "..."}` (or a list of field errors for 422).

| Status | Meaning |
|---|---|
| 401 | Missing/invalid API key or token |
| 403 | Logged in but not an admin |
| 404 | Unknown (or deactivated) site / alert |
| 409 | Site id already exists |
| 422 | Validation failed (ranges, vocabulary, future `ts`, batch too large) |
| 429 | Rate limit exceeded |

---

## Device endpoints (`X-API-Key`)

### `POST /api/ingest`

The Raspberry Pi's status record. Field names are the data contract — do not rename.

```http
POST /api/ingest
X-API-Key: nwq_8sK...
Content-Type: application/json

{"source": "ramkund", "colour": "GREEN", "label": "Normal", "confidence": 97.0,
 "wqi": 241.6, "ph": 7.81, "tds": 331.2, "turb": 17.8, "temp": 24.6,
 "health": "ok", "synthetic": false, "latency_ms": 12.5,
 "updated": "2026-11-20 13:05:00", "ts": "2026-11-20T07:35:00Z"}
```

| Field | Type | Rule |
|---|---|---|
| `source` | string | an active site id (`^[a-z0-9_]+$`), else **404** |
| `colour` | enum | `GREEN \| AMBER \| RED \| GREY` |
| `label` | enum | `Normal \| Natural change \| Contamination \| Sensor check \| Learning baseline` |
| `confidence` | number? | 0–100 |
| `wqi` | number? | ≥ 0 |
| `ph` / `tds` / `turb` / `temp` | number? | 0–14 / 0–2000 / 0–3000 / 0–50 (null allowed when offline) |
| `health` | enum | `ok \| offline \| flatline \| out_of_range` |
| `synthetic` | bool | `true` for simulated data |
| `latency_ms` | number? | model latency on the Pi |
| `updated` | string? | Pi local time, informational |
| `ts` | ISO 8601? | reading time; **server UTC time if omitted**; may not be > 10 min in the future |

`201 Created`

```json
{"stored": true, "duplicate": false, "alert_id": null}
```

* Re-sending the same `(source, ts)` returns `{"stored": false, "duplicate": true}`.
* A `RED` record creates an alert unless the site already has one within ±30 minutes;
  then `alert_id` is the new alert's id.

### `POST /api/ingest/batch`

Body: a JSON **list** of the records above (1–1000). Used by the Pi to flush its offline queue
and by the simulator. If any `source` is unknown the whole batch is rejected (404).

```json
{"received": 3, "stored": 2, "duplicates": 1, "alerts_created": 0}
```

---

## Public endpoints (60 requests/minute per IP)

### `GET /api/health`

```json
{"status": "ok", "database": "ok", "version": "0.1.0", "time": "2026-11-20T07:35:02Z"}
```
`503` with `"status": "degraded"` when the database is unreachable.

### `GET /api/sources`

```json
[
  {
    "id": "ramkund", "name_en": "Ramkund (Godavari ghats)", "name_mr": "रामकुंड",
    "kind": "river", "lat": 20.0074, "lon": 73.7924, "simulated": false, "active": true,
    "description_en": "...", "description_mr": "...",
    "latest": {
      "ts": "2026-11-20T07:35:00Z", "ph": 7.81, "tds": 331.2, "turb": 17.8, "temp": 24.6,
      "wqi": 241.6, "wqi_band": "unfit", "label": "Normal", "colour": "GREEN",
      "confidence": 97.0, "health": "ok", "synthetic": false, "latency_ms": 12.5
    },
    "stale": false,
    "status_colour": "GREEN"
  }
]
```

`stale` is `true` when there is no reading for 15 minutes (or none at all); `status_colour`
is then `GREY`. Front ends should display `status_colour`.

### `GET /api/sources/{id}`

One object of the shape above.

### `GET /api/sources/{id}/readings?hours=24`

`hours` 1–8760. Resolution is automatic: raw readings up to 24 h, 15-minute means up to 7 days,
hourly means beyond (older than the 90-day retention, from the hourly archive).

```json
{
  "site_id": "tapovan", "hours": 168, "resolution": "15min",
  "points": [
    {"ts": "2026-11-13T07:30:00Z", "ph": 7.71, "tds": 418.2, "turb": 21.9, "temp": 24.8,
     "wqi": 301.4, "colour": "GREEN", "n": 3}
  ]
}
```

`colour` of a bucket is its most serious colour (RED > AMBER > GREY > GREEN); `n` is the
number of readings averaged.

### `GET /api/sources/{id}/stats?days=7`

`days` 1–90.

```json
{
  "site_id": "tapovan", "days": 7, "count": 2016,
  "params": {"ph": {"min": 7.1, "max": 7.89, "mean": 7.71, "median": 7.7}, "tds": {...},
             "turb": {...}, "temp": {...}, "wqi": {...}},
  "wqi_bands": {"excellent": 0.0, "good": 0.0, "poor": 0.0, "very_poor": 0.0, "unfit": 100.0},
  "colours": {"GREEN": 97.1, "AMBER": 2.6, "RED": 0.3, "GREY": 0.0}
}
```
Shares are percentages of readings.

### `GET /api/alerts?limit=50&site=tapovan&acknowledged=false`

```json
[
  {"id": 12, "site_id": "tapovan", "site_name_en": "Tapovan (Godavari)", "site_name_mr": "तपोवन",
   "ts": "2026-11-20T07:35:00Z", "label": "Contamination", "confidence": 93.5, "wqi": 812.4,
   "acknowledged": false, "acknowledged_by": null, "acknowledged_at": null, "note": null}
]
```

### `GET /api/summary`

```json
{"colours": {"GREEN": 5, "AMBER": 0, "RED": 1, "GREY": 1}, "sites": 7, "stale_sites": 1,
 "active_alerts": 1, "last_update": "2026-11-20T07:35:00Z"}
```

### `GET /api/stream` (Server-Sent Events)

```
event: hello
data: {}
retry: 5000

event: reading
data: {...SourceOut, as in /api/sources...}

event: alert
data: {...AlertOut...}

: ping
```

Browser use:

```js
const es = new EventSource(`${API}/api/stream`);
es.addEventListener('reading', (e) => update(JSON.parse(e.data)));
es.addEventListener('alert', (e) => notify(JSON.parse(e.data)));
```

### `GET /api/export/{id}.csv?days=7`

`text/csv` attachment. Simulated sites start with a `# ... SIMULATED demonstration data` line.

```
ts,site_id,ph,tds,turb,temp,wqi,label,colour,confidence,health,synthetic
2026-11-19T07:40:00+00:00,tapovan,7.72,421.3,22.1,24.9,303.2,Normal,GREEN,96.2,ok,True
```

---

## Authentication

### `POST /api/auth/login`

```json
{"email": "admin@example.com", "password": "..."}
```
→
```json
{"access_token": "eyJ...", "refresh_token": "eyJ...", "token_type": "bearer", "expires_in": 1800}
```
Send `Authorization: Bearer <access_token>`. Access tokens last 30 minutes, refresh tokens 7 days.

### `POST /api/auth/refresh` — body `{"refresh_token": "..."}` → a new token pair.
### `GET /api/auth/me` → `{"id": 1, "email": "...", "role": "admin", "created_at": "...", "last_login_at": "..."}`

---

## Admin endpoints (`Authorization: Bearer`, role `admin`)

Every change is recorded in the audit log.

| Request | Body | Response |
|---|---|---|
| `GET /api/admin/sites` | – | all sites, including deactivated |
| `POST /api/admin/sites` | `{"id","name_en","name_mr","kind","lat","lon","simulated","active","description_en","description_mr"}` | `201` site |
| `PUT /api/admin/sites/{id}` | any subset of the fields above except `id` | site |
| `DELETE /api/admin/sites/{id}` | – | site with `"active": false` (history kept) |
| `POST /api/admin/alerts/{id}/ack` | `{"note": "Checked on site"}` (optional) | alert |
| `GET /api/admin/apikeys` | – | `[{"id","name","prefix","active","created_by","created_at","revoked_at","last_used_at"}]` |
| `POST /api/admin/apikeys/rotate` | `{"name": "pi-2026", "revoke_previous": true}` (optional) | `{"key": "nwq_...", "api_key": {...}, "revoked": 1}` — **the key is shown only once** |
| `GET /api/admin/audit?limit=100` | – | `[{"id","user_id","user_email","action","details","ip","ts"}]` |
| `GET /api/admin/ingest-health` | – | per site: `last_received_at`, `last_ts`, `messages_last_hour`, `hourly` (24 counts) |

Example — move a site's coordinates:

```bash
curl -X PUT "$API/api/admin/sites/ramkund" -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" -d '{"lat": 20.0076, "lon": 73.7921}'
```
