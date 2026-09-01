# Da Nang Real-Time Water Level Snapshot Sampling

> ## ⏹ STOPPED — this repo is no longer collecting data
>
> Collection ran from **2026-08-26 22:45 to 2026-09-01 01:10** (212 sampling
> rounds, 19,716 rows). It has been **permanently stopped**:
>
> - The local Windows Task Scheduler job (`Danang_WaterLevel_Sampling`) has
>   been **unregistered** — no scheduled process on any machine calls this
>   API anymore.
> - Both GitHub Actions workflows in this repo
>   (`collect_water_level.yml` and `diagnose.yml`) are **disabled**, including
>   the manual-trigger diagnostic one — nothing in this repo will call
>   `muangap-api.danang.gov.vn` again unless a workflow is explicitly
>   re-enabled and re-run by a human.
> - Reason for stopping: analysis of the collected data found the "real-time"
>   readings from `Thap bao ngap` (street flood sensors) do not behave like
>   live sensor data — see *Data quality finding* below. The project pivoted
>   to a statistical rainfall→water-level model calibrated on the existing
>   512 real flood reports instead, which needs no further calls to this API.
>
> `water_level_samples.csv` in this repo is the final, complete dataset from
> the run described above — read-only from this point on.

Automated collection of real-time flood/water-level sensor readings across
Da Nang, Vietnam, sampled every 15 minutes from 2026-08-26 to 2026-09-01
(see stop notice above). Collected as a substitute historical time series for
the flood predictive engine, because the official history endpoint is broken
(see below).

**Data source:** [muangap-api.danang.gov.vn](https://muangap.danang.gov.vn) — the
official Da Nang flood/rain map, `GET /v2/client/water_station/list_all`
(public, no API key required)
**Collection:** Windows Task Scheduler on a local machine, every 15 minutes,
results committed and pushed to this repo (see *Why not GitHub Actions* below)
**Cost:** free, no rate limit on this endpoint observed

## Why not GitHub Actions: the API blocks cloud IP ranges

The collection was originally set up as a GitHub Actions scheduled workflow
(`.github/workflows/collect_water_level.yml`, now **disabled**). Every run
died with `requests.exceptions.ConnectTimeout` while the identical request
from a Vietnamese residential connection succeeded in ~1.1s at the same
moment.

A diagnostic workflow (`.github/workflows/diagnose.yml`, manual trigger)
established the mechanism:

```
DNS resolve        103.101.76.42          OK
TCP connect :443   BLOCKED / TIMEOUT
traceroute         * * *  (all hops)
runner public IP   135.119.239.52  (AS8075 Microsoft, Azure eastus2)
```

The block is a **packet-level firewall drop at the Da Nang government
datacenter**, not an application-layer rejection — so it cannot be worked
around with headers, user agents, or request shaping. Host-by-host results
from the same runner:

| Host | Result |
|---|---|
| `muangap-api.danang.gov.vn` (103.101.76.42) | timeout |
| `muangap.danang.gov.vn` | timeout |
| `congdulieu.vn` (city open-data portal) | timeout |
| `danang.gov.vn` (main city portal) | **HTTP 200** |

The main city portal is hosted elsewhere and remains reachable; the flood
system and the open-data portal share the blocked `103.101.76.0/24` range.

**The blocklist is selective, not "all datacenters."** Tested egress points:

| Source | ASN | Result |
|---|---|---|
| Vietnamese residential ISP | — | reachable, ~1.1s |
| Anthropic infrastructure (US datacenter) | — | reachable |
| GitHub Actions | AS8075 Microsoft | blocked |
| Cloudflare Workers (`wrangler dev --remote`) | AS13335 Cloudflare | blocked |
| Google Apps Script (`UrlFetchApp`) | AS15169 Google | blocked — confirmed after isolating with a 3-URL control test (a known-good URL and `danang.gov.vn` both succeeded from the same script; only the muangap-api target failed) |

**All three major clouds tested (Microsoft, Cloudflare, Google) are blocked.**
The pattern is consistent with a curated blocklist of large cloud/CDN ASNs
commonly used for scraping, rather than geographic filtering — and given 3/3
of the largest providers are blocked, further hosted-cloud platforms were not
tried; the marginal chance of finding an unblocked one did not justify the
time against a one-week deadline.

**Consequence for reproducibility:** anyone attempting to re-run this
collection from a hosted CI service or serverless platform will likely hit
the same wall. Collection must run from an un-blocked network — in this
project, a local machine on a Vietnamese ISP, scheduled via Windows Task
Scheduler, which commits and pushes to this same repo. Only the execution
host changed; the data stays in one public place.

---

## Why this exists: the official history endpoint is broken

Da Nang operates 93 water-level sensors across 4 types (`Tháp báo ngập` /
flood towers, `Tháp báo lũ` / flood warning towers, `Trạm đo mực nước` / river
gauges, `Trạm mực nước hồ` / reservoir gauges), all queryable in real time via
`list_all`. The city's own history endpoint,
`GET /v2/client/water_station/detail_report?waterStationId=...&startTime=...&endTime=...`,
should return exactly the time series this project needs — but it does not
work:

- Every query for a station that actually exists **times out** (no response
  within 25s) or eventually returns **502 Bad Gateway**.
- Querying with a syntactically valid but non-existent station ID returns
  fast (~0.2s) with a leaked backend error: `(BadValue) $in needs an array` —
  a MongoDB error, indicating the historical-data query itself never
  completes for real stations (most likely a missing index or an unfiltered
  scan), not a client-side mistake. Parameter name, HTTP method (`GET`, not
  `POST`), time range size, and timestamp units were all verified against the
  working sibling endpoint for rain stations
  (`/v2/client/stations/detail_hourly_report`), which behaves identically in
  shape but works correctly.
- This has been reported to the operating agency (Sở Khoa học và Công nghệ
  Đà Nẵng). Until/unless it is fixed, no historical water-level series can be
  retrieved through the public API.

**This repo is the workaround**: since only the current snapshot is
reliable, polling it frequently and committing each snapshot builds up a
real time series going forward, even though it cannot recover the past.

## Method

1. `GET /v2/client/water_station/list_all` — one request returns all 93
   stations' current state in ~0.1–0.2s.
2. Append one row per station to `water_level_samples.csv`, tagged with the
   sampling timestamp.
3. Flag each station `is_core_urban = true/false` using the same bounding
   box used throughout this project (`lat 15.95–16.15, lng 108.10–108.30`) to
   mark whether it falls in urban Da Nang proper (vs. mountain areas / the
   former Quảng Nam territory merged into Đà Nẵng in 2025).

A Windows scheduled task (`Danang_WaterLevel_Sampling`) runs `run_hidden.vbs`
→ `run_sample.bat` every 15 minutes, which collects a sample and pushes it to
this repo. The script itself stops appending after **2026-09-01** (one week
from setup) to avoid silently accumulating data past the intended window if
the task is forgotten; extend `COLLECTION_END` in `collect_water_level.py` to
keep going.

To stop collection early:

```powershell
Unregister-ScheduledTask -TaskName Danang_WaterLevel_Sampling -Confirm:$false
```

---

## `water_level_samples.csv` — column reference

One row = one station, sampled at one point in time.

| Column | Type | Description |
|---|---|---|
| `sampled_at_vn` | datetime | Sampling time, Vietnam local time (UTC+7) |
| `sampled_at_utc` | datetime | Same instant, UTC, ISO 8601 |
| `weekday` | string | `Mon`–`Sun`, from Vietnam local time |
| `hour_vn` | int (0–23) | Hour of day, Vietnam local time |
| `station_id` | string | muangap-api station ID |
| `code` | string | Station code (e.g. `431068`) |
| `name` | string | Station name/location label |
| `station_type` | string | `Thap bao ngap` (street flood depth sensor — primary interest), `Thap bao lu` (flood warning tower), `Tram do muc nuoc` (river gauge), `Tram muc nuoc ho` (reservoir gauge) |
| `area`, `district` | string | Administrative area as reported by the station |
| `lat`, `lng` | float | Station coordinates (WGS 84) |
| `depth_m` | float | **Current reading, metres.** For `Thap bao ngap`/`Thap bao lu` this is street flood depth; for river/reservoir gauges it is a continuous water level, not comparable to flood depth |
| `is_core_urban` | bool | Whether the station falls inside the urban Da Nang bounding box used elsewhere in this project |

## Data quality finding: readings do not behave like live sensors

Across the full 6-day collection (19,716 rows, 212 rounds), two independent
patterns show up that are inconsistent with real water rising and falling,
and were the reason collection was stopped rather than continuing for the
full planned week:

**1. Urban flood towers were perfectly static.** The four `Thap bao ngap`
stations in urban districts that ever showed a nonzero reading (Gầm cầu Đỏ,
Chợ Thanh Vinh, Tổ 8 Thanh Khê Tây, UBND Hòa Thọ Tây) held the **exact same
value to the centimetre for all 212 rounds** — 0.19 m, 0.01 m, 0.15 m, 0.01 m
respectively, with zero variation. A live sensor, even reporting "no flood,"
should show at least some noise over 6 days; a value frozen to 2 decimal
places is more consistent with a cached/default value than a live reading.

**2. Two mountain-area stations toggled between two fixed values.**
`Thôn Thái Lai - Hòa Nhơn` (Bà Nà) alternated **exactly** between `0.0` and
`0.97` every 15-minute round for 6+ hours straight (2026-08-30 21:55 to
2026-08-31 03:25), never taking any intermediate value. `Thôn Thạch Nham Tây
- Hòa Nhơn` (also Bà Nà) held `1.02` for 4 consecutive rounds (90 minutes),
then dropped straight back to near-zero. Real water rising/falling passes
through intermediate values continuously; toggling between two fixed numbers
looks like an artifact of the backend serving from two out-of-sync sources
(e.g. alternating replicas or a stale cache), not a genuine flood event —
though this cannot be fully ruled out without independent rainfall data for
that specific location and window.

Both `Bà Nà` stations fall inside the coordinate bounding box used for
`is_core_urban` but are geographically mountainous, outside the urban core
this project targets (see the district-name-based scope filter used
elsewhere in this project, e.g. `scraper/parse.py` in the `flood_detection`
repo, which this dataset's simpler bbox-only check does not replicate).

**Conclusion:** the `list_all` snapshot endpoint should not be treated as a
reliable live measurement for this project's purposes. This finding, along
with the broken `detail_report` history endpoint, is worth reporting to the
operating agency.

## Notes and limitations

1. **This cannot recover history.** Data starts from whenever this workflow
   was first triggered; it says nothing about past events (including
   14/10/2022).
2. **`depth_m` is not directly comparable across station types.** River/
   reservoir gauges (`Tram do muc nuoc`, `Tram muc nuoc ho`) read a
   continuous baseline water level (often several metres) that is normal,
   not flooding. Only `Thap bao ngap`/`Thap bao lu` readings represent street
   flood depth.
3. **Small nonzero readings on flood towers are likely sensor noise**, not
   real flooding, when observed outside rain events — e.g. ±0.01 m. Treat
   readings below roughly 0.05 m with caution absent corroborating rainfall
   data.
4. **Collected during the dry season.** Da Nang's flood season is
   October–November (94% of historical flood reports in this project's
   dataset fall in those two months). Data collected in this one-week window
   mostly captures baseline/no-flood conditions — useful for establishing a
   "no flood" reference, not for observing an actual flood event.
