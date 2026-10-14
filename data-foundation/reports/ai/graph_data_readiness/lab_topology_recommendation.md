# Lab Topology Recommendation (non-degenerate)

Design a small IIoT lab with **multiple** high-degree nodes and genuine non-hub-to-non-hub traffic. Do NOT optimise the topology to make the AI look good.

Components: Engineering Workstation · HMI · Historian · PLC-01/02/03 · MQTT Broker · NVR · 2–4 Cameras · IoT Sensor group · DNS · NTP · Gateway · Jump/Admin Workstation.

Zones: IT · OT · Engineering · Control · IoT · Video/CCTV · Infrastructure.

Topology properties:

- ≥ 2 independent local neighbourhoods; more than one high-degree node.
- non-hub-to-non-hub communication (control plane, sensor groups).
- role-consistent edges + rare-but-legitimate edges.
- cross-zone paths (allowed vs disallowed).
- persistent (PLC↔Historian) and ephemeral (camera↔NVR) relationships.

Zones feed ground truth: evaluate *structurally plausible* vs *cross-zone unusual*. Do not assume every customer site uses the same segmentation.

