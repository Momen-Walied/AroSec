# Disagreement Analysis

Interpretation only — **no example is called an attack**.

## A. Edge HIGH / Graph LOW — relationship-local novelty but structurally plausible

| relationship | window | edge | graph | src bucket | dst bucket | new structural edge |
|---|---|---|---|---|---|---|
| rel:asset:unsw:203.5.76.16|asset:unsw:192.168.1.240|COMMUNICATES_WITH | 2016-10-27 19:54:00+00:00 | 0.766 | 0.593 | low | hub | False |
| rel:asset:unsw:192.168.1.240|asset:unsw:23.23.78.14|COMMUNICATES_WITH | 2016-10-27 22:10:00+00:00 | 0.764 | 0.498 | hub | low | True |
| rel:asset:unsw:192.168.1.240|asset:unsw:205.251.242.2|COMMUNICATES_WITH | 2016-10-27 05:45:00+00:00 | 0.735 | 0.652 | hub | low | True |
| rel:asset:unsw:192.168.1.240|asset:unsw:129.6.15.29|COMMUNICATES_WITH | 2016-10-27 22:10:30+00:00 | 0.731 | 0.68 | hub | low | True |
| rel:asset:unsw:192.168.1.240|asset:unsw:192.96.202.120|COMMUNICATES_WITH | 2016-10-27 22:10:30+00:00 | 0.723 | 0.68 | hub | low | True |

## B. Edge LOW / Graph HIGH — communication looks normal but the neighborhood changed

| relationship | window | edge | graph | src bucket | dst bucket | new structural edge |
|---|---|---|---|---|---|---|
| rel:asset:unsw:192.168.1.240|asset:unsw:192.96.202.120|COMMUNICATES_WITH | 2016-10-27 23:07:00+00:00 | 0.213 | 0.955 | hub | low | False |
| rel:asset:unsw:192.168.1.240|asset:unsw:207.171.178.6|COMMUNICATES_WITH | 2016-10-27 23:08:00+00:00 | 0.187 | 0.955 | hub | low | False |
| rel:asset:unsw:192.168.1.240|asset:unsw:72.21.207.109|COMMUNICATES_WITH | 2016-10-27 22:54:30+00:00 | 0.22 | 0.954 | hub | low | False |
| rel:asset:unsw:192.168.1.240|asset:unsw:192.96.202.120|COMMUNICATES_WITH | 2016-10-27 22:52:30+00:00 | 0.217 | 0.948 | hub | low | False |
| rel:asset:unsw:192.168.1.240|asset:unsw:204.9.54.119|COMMUNICATES_WITH | 2016-10-27 22:53:30+00:00 | 0.307 | 0.948 | hub | low | False |

