"""CICIoT2023 adapter — secondary/optional in v0.1 (storage-heavy)."""
from __future__ import annotations

from src.datasets.generic_csv import GenericCsvFlowAdapter
from src.schemas.base import SourceDataset


class CICIoT2023Adapter(GenericCsvFlowAdapter):
    dataset_id = "ciciot2023"
    source = SourceDataset.CICIOT2023
    manual_notes = (
        "UNB CIC registration gate + storage-heavy (verify size first). Not auto-downloaded. "
        "Place the CSV(s) in data/raw/ciciot2023/ to enable normalization. "
        "Info: https://www.unb.ca/cic/datasets/iotdataset-2023.html"
    )
