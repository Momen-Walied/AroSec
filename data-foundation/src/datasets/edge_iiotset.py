"""Edge-IIoTset (2022) adapter — secondary/optional in v0.1."""
from __future__ import annotations

from src.datasets.generic_csv import GenericCsvFlowAdapter
from src.schemas.base import SourceDataset


class EdgeIIoTSetAdapter(GenericCsvFlowAdapter):
    dataset_id = "edge_iiotset"
    source = SourceDataset.EDGE_IIOTSET
    manual_notes = (
        "Kaggle download requires an authenticated Kaggle account (no bypass). "
        "Place the CSV(s) in data/raw/edge_iiotset/ to enable normalization. "
        "Kaggle: https://www.kaggle.com/datasets/mohamedamineferrag/edgeiiotset-cyber-security-dataset-of-iot-iiot"
    )
