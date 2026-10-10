"""Generic CSV flow adapter used by secondary datasets (Edge-IIoTset, CICIoT2023).

These datasets are optional in v0.1. The adapter is ready to ingest a provided
CSV (label columns are auto-detected); the datasets themselves are NOT
auto-downloaded (Kaggle / UNB registration gates).
"""
from __future__ import annotations

import pandas as pd

from src.datasets.base import (
    DatasetAdapter,
    DownloadResult,
    InspectionReport,
    RawBundle,
    RawValidationResult,
)
from src.datasets.columns import canonicalize_flow_frame, resolve
from src.datasets.flow_map import canonical_frame_to_observations
from src.schemas.base import SourceDataset


class GenericCsvFlowAdapter(DatasetAdapter):
    source = SourceDataset.SYNTHETIC
    manual_notes = ""

    def _csvs(self) -> list:
        if not self.raw_dir.exists():
            return []
        return sorted(self.raw_dir.rglob("*.csv"), key=lambda p: p.stat().st_size, reverse=True)

    def inspect(self) -> InspectionReport:
        files = []
        if self.raw_dir.exists():
            for path in sorted(self.raw_dir.rglob("*")):
                if path.is_file():
                    files.append({"path": str(path.relative_to(self.raw_dir)), "size": path.stat().st_size})
        return InspectionReport(
            dataset_id=self.dataset_id,
            status="AVAILABLE" if files else "NOT_CHECKED",
            local_path=str(self.raw_dir),
            present=self.raw_dir.exists(),
            files=files,
            notes=self.manual_notes,
        )

    def download(self, mode: str = "sample") -> DownloadResult:
        return DownloadResult(dataset_id=self.dataset_id, status="MANUAL_DOWNLOAD_REQUIRED", notes=self.manual_notes)

    def validate_raw(self) -> RawValidationResult:
        res = RawValidationResult(dataset_id=self.dataset_id, ok=True)
        csvs = self._csvs()
        res.add("csv_present", bool(csvs), csvs[0].name if csvs else "none")
        if csvs:
            cols = pd.read_csv(csvs[0], nrows=1).columns.tolist()
            res.add("has_src_ip", resolve(pd.DataFrame(columns=cols), "src_ip") is not None, "")
        return res

    def load_raw(self) -> RawBundle:
        bundle = RawBundle()
        cap = self.settings.sample_max_flow_rows if self.settings.data_mode == "sample" else None
        for csv_path in self._csvs():
            df = pd.read_csv(csv_path, nrows=cap, low_memory=False)
            canonical = canonicalize_flow_frame(df)
            bundle.observations.extend(
                canonical_frame_to_observations(canonical, f"{self.dataset_id}:csv")
            )
            if cap is not None:
                break
        return bundle
