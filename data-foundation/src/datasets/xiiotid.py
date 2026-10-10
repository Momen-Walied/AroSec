"""X-IIoTID 2021 adapter.

Connectivity-/device-agnostic IIoT intrusion dataset (MQTT, Modbus, TCP, CoAP)
with explicit lateral-movement samples. Full dataset is login-gated (IEEE
DataPort / Kaggle) -> MANUAL_DOWNLOAD_REQUIRED. A small CC BY 4.0 derivative
(Zenodo) is used only to validate the adapter/schema.
"""
from __future__ import annotations

import pandas as pd

from src.datasets.base import (
    DatasetAdapter,
    DownloadResult,
    InspectionReport,
    RawBundle,
    RawObservation,
    RawValidationResult,
)
from src.schemas.base import SourceDataset

_NA = {"", "*", "null", "nan", "none", "-"}


class XIIoTIDAdapter(DatasetAdapter):
    dataset_id = "x_iiotid"
    source = SourceDataset.X_IIOTID

    def _csv_candidates(self) -> list:
        if not self.raw_dir.exists():
            return []
        preferred = sorted(
            self.raw_dir.glob("*.csv"),
            key=lambda p: ("X-IIoTID dataset" in p.name or "XIIoTID" in p.name, p.stat().st_size),
            reverse=True,
        )
        return preferred

    def inspect(self) -> InspectionReport:
        files = []
        if self.raw_dir.exists():
            for path in sorted(self.raw_dir.rglob("*")):
                if path.is_file():
                    files.append({"path": str(path.relative_to(self.raw_dir)), "size": path.stat().st_size})
        notes = "Full CSV requires login (IEEE DataPort / Kaggle). Place it in data/raw/x_iiotid/."
        candidates = self._csv_candidates()
        if candidates:
            head = pd.read_csv(candidates[0], nrows=2)
            labels = [c for c in ("class1", "class2", "class3") if c in head.columns]
            notes = f"columns={len(head.columns)}; label_cols={labels}; file={candidates[0].name}"
        return InspectionReport(
            dataset_id=self.dataset_id,
            status="MANUAL_DOWNLOAD_REQUIRED",
            local_path=str(self.raw_dir),
            present=self.raw_dir.exists(),
            files=files,
            notes=notes,
        )

    def download(self, mode: str = "sample") -> DownloadResult:
        return DownloadResult(
            dataset_id=self.dataset_id,
            status="MANUAL_DOWNLOAD_REQUIRED",
            notes=(
                "Login required (no bypass). Option A: IEEE DataPort 'X-IIoTID-dataset.zip' -> unzip "
                "'X-IIoTID dataset.csv' into data/raw/x_iiotid/. Option B: Kaggle "
                "'munaalhawawreh/xiiotid-iiot-intrusion-dataset' -> 'X-IIoTID dataset.csv'. "
                "A CC BY 4.0 derivative subset is already present for schema validation only."
            ),
        )

    def validate_raw(self) -> RawValidationResult:
        res = RawValidationResult(dataset_id=self.dataset_id, ok=True)
        candidates = self._csv_candidates()
        res.add("csv_present", bool(candidates), candidates[0].name if candidates else "none")
        if candidates:
            cols = pd.read_csv(candidates[0], nrows=1).columns.tolist()
            needed = {"Timestamp", "Scr_IP", "Des_IP"}
            res.add("required_columns", needed.issubset(set(cols)), f"missing={sorted(needed - set(cols))}")
            res.add("label_columns", {"class1", "class2", "class3"}.issubset(set(cols)), "")
        return res

    def load_raw(self) -> RawBundle:
        bundle = RawBundle()
        candidates = self._csv_candidates()
        if not candidates:
            return bundle
        cap = self.settings.sample_max_flow_rows if self.settings.data_mode == "sample" else None
        df = pd.read_csv(candidates[0], nrows=cap, low_memory=False)
        for row in df.to_dict(orient="records"):
            ts = _timestamp(row.get("Timestamp")) or _timestamp(row.get("Date"))
            if ts is None:
                continue
            class3 = _text(row.get("class3"))
            class1 = _text(row.get("class1"))
            class2 = _text(row.get("class2"))
            is_attack_row = class3 is not None and class3.lower() == "attack"
            label = class1 if (is_attack_row and class1) else (
                "benign" if (class3 and class3.lower() == "normal") else class1
            )
            packets = (_int(row.get("Scr_pkts")) or 0) + (_int(row.get("Des_pkts")) or 0)
            if packets == 0:
                packets = _int(row.get("total_packet")) or 1
            bundle.observations.append(
                RawObservation(
                    timestamp=ts,
                    src_ip=_text(row.get("Scr_IP")),
                    dst_ip=_text(row.get("Des_IP")),
                    src_port=_int(row.get("Scr_port")),
                    dst_port=_int(row.get("Des_port")),
                    network_protocol=(_text(row.get("Protocol")) or "").upper() or None,
                    application_protocol=(_text(row.get("Service")) or "").upper() or None,
                    bytes_out=_int(row.get("Scr_bytes")) or 0,
                    bytes_in=_int(row.get("Des_bytes")) or 0,
                    packet_count=max(packets, 0),
                    original_label=label,
                    original_sub_label=class2,
                    campaign_key=None,
                    evidence_source="x_iiotid:csv",
                )
            )
        return bundle


def _text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if text.lower() in _NA:
        return None
    return text


def _int(value: object) -> int | None:
    text = _text(value)
    if text is None:
        return None
    try:
        return int(float(text))
    except (ValueError, TypeError):
        return None


def _timestamp(value: object):
    text = _text(value)
    if text is None:
        return None
    if text.replace(".", "", 1).isdigit():
        return pd.to_datetime(float(text), unit="s", utc=True).to_pydatetime()
    parsed = pd.to_datetime(text, utc=True, errors="coerce")
    return None if pd.isna(parsed) else parsed.to_pydatetime()
