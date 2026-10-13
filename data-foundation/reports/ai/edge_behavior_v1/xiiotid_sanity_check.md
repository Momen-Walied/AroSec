# Edge Behavior v1 — X-IIoTID Sanity Check

> **Sanity check only.** X-IIoTID here is the 1,672-row CC BY 4.0 derivative. It is NOT representative of the full 820,834-row dataset and its 77 lateral-movement examples are far too few for a reliable benchmark. The scorer is trained on UNSW (normal) and applied out-of-domain. Do NOT present these numbers as validated detection performance.

| model | rows | attack windows | attack mean | benign mean | ROC-AUC | PR-AUC | attack alert rate | benign alert rate |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| statistical | 1118 | 386 | 0.054 | 0.039 | 0.636 | 0.514 | 0.277 | 0.041 |
| isolation_forest | 1118 | 386 | 0.698 | 0.651 | 0.704 | 0.555 | 0.407 | 0.098 |
| autoencoder | 1118 | 386 | 1.000 | 1.000 | 0.695 | 0.514 | 0.718 | 0.310 |

