# Dataset Registry

_Generated 2026-10-10T15:30:39.882732+00:00_

| dataset | year | access | status | pcap | flows | labels | stages | lateral | provenance | time | size |
|---|---:|---|---|:-:|:-:|:-:|:-:|:-:|:-:|---|---|
| cicapt_iiot | 2024 | REGISTRATION_FORM | MANUAL_DOWNLOAD_REQUIRED | Y | Y | Y | Y | Y | Y | exact | unknown (not verifiable while gated; described as multi-GB with PCAPs) |
| x_iiotid | 2021 | LOGIN_REQUIRED | MANUAL_DOWNLOAD_REQUIRED | N | Y | Y | N | Y | N | exact | approx 1 GB (not verified while login-gated) |
| unsw_iotraffic | 2025 | OPEN_ACCESS_ANTIBOT | NORMALIZED | Y | Y | N | N | N | N | exact | 28.47 GB total; flows.zip 95.51 MB; device_pcap_summary.csv 1.84 KB; pcaps.zip 13.92 GB |
| edge_iiotset | 2022 | KAGGLE_AUTH | NOT_CHECKED | Y | Y | Y | N | N | N | exact | approx 3-4 GB (not verified while auth-gated) |
| ciciot2023 | 2023 | REGISTRATION_FORM | NOT_CHECKED | Y | Y | Y | N | ~ | N | exact | large (CSV ~ several GB) — verify before download |

## Build manifest (normalized outputs)

| dataset:window | raw obs | assets | edges | labels | campaigns | events | node feats | edge feats |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| cicapt_iiot:30s | 13 | 6 | 9 | 8 | 1 | 15 | 9 | 9 |
| unsw_iotraffic:30s | 100000 | 63 | 77102 | 0 | 0 | 77165 | 35909 | 77102 |
| x_iiotid:30s | 1672 | 29 | 1118 | 728 | 0 | 1147 | 1117 | 1118 |

## v0.2 build manifest (authoritative)

| dataset:window | raw | assets | bindings | relationships | observations | pair-windows | events |
|---|---:|---:|---:|---:|---:|---:|---:|
| cicapt_iiot:30s | 13 | 6 | 10 | 6 | 13 | 9 | 39 |
| unsw_iotraffic:30s | 98747 | 63 | 63 | 74 | 98747 | 67885 | 197593 |
| x_iiotid:30s | 1567 | 29 | 29 | 29 | 1566 | 1118 | 3176 |
