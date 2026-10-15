# InfluxDB v2 setup (manual) — OEE Smart Factory

Full step-by-step instructions are in `docs/DATABASE_MANUAL_SETUP_GUIDE.md` (Part 3). This file is the
reference for **what the app expects**.

## Buckets

| Bucket | Retention | Written by | Contents |
|---|---|---|---|
| `telemetry_raw` | **30 days** | backend, batched ≈ every 1 s | raw 500 ms telemetry |
| `telemetry_agg` | **1 year** | backend (hourly OEE rollups) + the Flux task below | aggregated telemetry and OEE |

## Data model

```
measurement: telemetry                       (bucket telemetry_raw)
  tag:    machine_id
  fields: temperature (float)  vibration (float)  status (string)  cycle_count (int)  anomaly_score (float, 0-100)

measurement: oee_hourly                      (bucket telemetry_agg, timestamp = start of the hour)
  tag:    machine_id
  fields: planned_s  run_s  ideal_s  cycles  good  stopped_s   (all float)
```

`oee_hourly` is what the 7-day OEE trend and the downtime-per-shift report are computed from
(`OEE = (run_s / planned_s) x min(ideal_s / run_s, 1) x (good / cycles)`).

## Downsampling task (hourly means into the 1-year bucket)

```flux
option task = {name: "downsample_telemetry_1h", every: 1h}

from(bucket: "telemetry_raw")
  |> range(start: -task.every)
  |> filter(fn: (r) => r._measurement == "telemetry")
  |> filter(fn: (r) => r._field == "temperature" or r._field == "vibration" or r._field == "anomaly_score")
  |> aggregateWindow(every: 1h, fn: mean, createEmpty: false)
  |> to(bucket: "telemetry_agg", org: "oee-org")
```

## Handy queries (Data Explorer → Script Editor)

```flux
// latest temperature per machine
from(bucket: "telemetry_raw") |> range(start: -5m)
  |> filter(fn: (r) => r._measurement == "telemetry" and r._field == "temperature")
  |> last()

// anomaly score history for one machine
from(bucket: "telemetry_raw") |> range(start: -1h)
  |> filter(fn: (r) => r._measurement == "telemetry" and r._field == "anomaly_score" and r.machine_id == "CNC-01")
```

## Check it from the project

```bash
cd backend
python -m app.storage.verify
```
