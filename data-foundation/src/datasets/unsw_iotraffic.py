"""UNSW-IoTraffic 2025 adapter (open access, Dryad).

Long-duration NORMAL IoT behaviour (27 devices, ~203 days). No attack labels.
Used for historical edge baselines: edge_age, historical_peer_count, new_peer,
protocol novelty, time-of-day.
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
from src.datasets.http_util import adopt_local, fetch, find_in_downloads
from src.schemas.base import SourceDataset

DRYAD_FLOWS_ZIP = "https://datadryad.org/downloads/file_stream/4322594"
DRYAD_SUMMARY_CSV = "https://datadryad.org/downloads/file_stream/4322597"

_IP_PROTO = {1: "ICMP", 2: "IGMP", 6: "TCP", 17: "UDP", 58: "ICMPV6", 47: "GRE", 50: "ESP"}
_NA = {"", "*", "null", "nan", "none"}


def _proto_name(value: object) -> str | None:
    text = str(value).strip()
    if text in _NA:
        return None
    try:
        return _IP_PROTO.get(int(float(text)), f"IP-{int(float(text))}")
    except (ValueError, TypeError):
        return text.upper()


class UnswIoTrafficAdapter(DatasetAdapter):
    dataset_id = "unsw_iotraffic"
    source = SourceDataset.UNSW_IOTRAFFIC

    @property
    def flows_dir(self):
        return self.raw_dir / "flows"

    def inspect(self) -> InspectionReport:
        files: list[dict[str, object]] = []
        present = self.raw_dir.exists()
        if present:
            for path in sorted(self.raw_dir.rglob("*")):
                if path.is_file():
                    files.append({"path": str(path.relative_to(self.raw_dir)), "size": path.stat().st_size})
        return InspectionReport(
            dataset_id=self.dataset_id,
            status="AVAILABLE" if (self.flows_dir.exists()) else "NOT_CHECKED",
            local_path=str(self.raw_dir),
            present=present,
            files=files,
            notes="flow CSVs under flows/; device summary at device_pcap_summary.csv",
        )

    def download(self, mode: str = "sample") -> DownloadResult:
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        result = DownloadResult(dataset_id=self.dataset_id, status="AVAILABLE")
        summary_dest = self.raw_dir / "device_pcap_summary.csv"
        if not summary_dest.exists():
            outcome = fetch(DRYAD_SUMMARY_CSV, summary_dest, timeout=self.settings.http_timeout_seconds)
            if outcome.ok:
                result.fetched.append("device_pcap_summary.csv")
                result.bytes_total += outcome.bytes
            else:
                local = find_in_downloads("device_pcap_summary.csv")
                if local:
                    adopt_local(local, summary_dest)
                    result.fetched.append("device_pcap_summary.csv (from ~/Downloads)")
        else:
            result.skipped.append("device_pcap_summary.csv")

        flows_zip = self.raw_dir / "flows.zip"
        if not self.flows_dir.exists():
            if not flows_zip.exists():
                outcome = fetch(DRYAD_FLOWS_ZIP, flows_zip, timeout=self.settings.http_timeout_seconds)
                if outcome.ok:
                    result.fetched.append("flows.zip")
                    result.bytes_total += outcome.bytes
                elif outcome.blocked_by_antibot:
                    local = find_in_downloads("flows.zip")
                    if local:
                        adopt_local(local, flows_zip)
                        result.fetched.append("flows.zip (from ~/Downloads)")
                    else:
                        result.status = "MANUAL_DOWNLOAD_REQUIRED"
                        result.notes = (
                            "Dryad flows.zip is behind an anti-bot challenge. Open "
                            f"{DRYAD_FLOWS_ZIP} in a real browser, then re-run (file is adopted from ~/Downloads)."
                        )
                        return result
            if flows_zip.exists():
                import zipfile

                with zipfile.ZipFile(flows_zip) as zf:
                    zf.extractall(self.raw_dir)
                result.fetched.append("flows/ (extracted)")
        else:
            result.skipped.append("flows/")
        return result

    def validate_raw(self) -> RawValidationResult:
        res = RawValidationResult(dataset_id=self.dataset_id, ok=True)
        res.add("flows_dir_exists", self.flows_dir.exists(), str(self.flows_dir))
        if self.flows_dir.exists():
            csvs = sorted(self.flows_dir.glob("*_flows.csv"))
            res.add("flow_csv_count>0", len(csvs) > 0, f"{len(csvs)} files")
            if csvs:
                cols = pd.read_csv(csvs[0], nrows=1).columns.tolist()
                res.add("schema_has_5tuple", {"time", "srcIp", "dstIp", "srcPort", "dstPort"}.issubset(cols), "")
        return res

    def load_raw(self) -> RawBundle:
        bundle = RawBundle()
        if not self.flows_dir.exists():
            return bundle
        cap = self.settings.sample_max_flow_rows if self.settings.data_mode == "sample" else None
        remaining = cap
        for csv_path in sorted(self.flows_dir.glob("*_flows.csv")):
            if remaining is not None and remaining <= 0:
                break
            nrows = remaining
            df = pd.read_csv(csv_path, nrows=nrows, low_memory=False)
            bundle.observations.extend(self._rows_to_observations(df))
            if remaining is not None:
                remaining -= len(df)
        return bundle

    @staticmethod
    def _rows_to_observations(df: pd.DataFrame) -> list[RawObservation]:
        out: list[RawObservation] = []
        for row in df.to_dict(orient="records"):
            ts = pd.to_datetime(row.get("time"), utc=True, errors="coerce")
            if pd.isna(ts):
                continue
            app = str(row.get("protocol", "")).strip()
            app_proto = None if app.lower() in _NA else app.upper()
            src_mac = str(row.get("srcMac", "")).strip()
            dst_mac = str(row.get("dstMac", "")).strip()
            packets = int(row.get("srcNumPackets", 0) or 0) + int(row.get("dstNumPackets", 0) or 0)
            out.append(
                RawObservation(
                    timestamp=ts.to_pydatetime(),
                    src_ip=str(row.get("srcIp", "")).strip() or None,
                    dst_ip=str(row.get("dstIp", "")).strip() or None,
                    src_mac=None if src_mac.lower() in _NA else src_mac,
                    dst_mac=None if dst_mac.lower() in _NA else dst_mac,
                    src_port=_int_or_none(row.get("srcPort")),
                    dst_port=_int_or_none(row.get("dstPort")),
                    network_protocol=_proto_name(row.get("ipProto")),
                    application_protocol=app_proto,
                    bytes_out=_int_or_none(row.get("srcPayloadSize")) or 0,
                    bytes_in=_int_or_none(row.get("dstPayloadSize")) or 0,
                    packet_count=max(packets, 0),
                    evidence_source="unsw_iotraffic:flows",
                )
            )
        return out


def _int_or_none(value: object) -> int | None:
    if value is None:
        return None
    text = str(value).strip()
    if text.lower() in _NA:
        return None
    try:
        return int(float(text))
    except (ValueError, TypeError):
        return None
