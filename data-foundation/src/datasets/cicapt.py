"""CICAPT-IIoT 2024 adapter.

APT provenance + network dataset. Official distribution is a registration form
(access control) and is therefore NOT auto-downloaded (status
MANUAL_DOWNLOAD_REQUIRED). This adapter parses the real files once provided and
also supports a synthetic CICAPT-shaped fixture for end-to-end demos/tests.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.config import PROJECT_ROOT
from src.datasets.base import (
    CampaignSeed,
    DatasetAdapter,
    DownloadResult,
    InspectionReport,
    RawBundle,
    RawObservation,
    RawValidationResult,
)
from src.datasets.columns import canonicalize_flow_frame
from src.datasets.flow_map import canonical_frame_to_observations
from src.identity.keys import resolve_asset_identity
from src.schemas.asset import Asset
from src.schemas.base import AssetType, IdentityMethod, SourceDataset

SYNTHETIC_FIXTURE = PROJECT_ROOT / "tests" / "fixtures" / "cicapt_scenario.csv"
SYNTHETIC_CAMPAIGN = "phase2"


class CicaptAdapter(DatasetAdapter):
    dataset_id = "cicapt_iiot"
    source = SourceDataset.CICAPT_IIOT

    def __init__(self, settings=None, synthetic: bool = False) -> None:
        super().__init__(settings)
        self.synthetic = synthetic

    def _find(self, *patterns: str) -> list[Path]:
        out: list[Path] = []
        if self.raw_dir.exists():
            for pattern in patterns:
                out.extend(sorted(self.raw_dir.rglob(pattern)))
        return out

    def _network_csvs(self) -> list[Path]:
        return self._find("*etwork*.csv", "*pcap2csv*.csv", "*flows*.csv")

    def _attack_info_csvs(self) -> list[Path]:
        return self._find("*ttack*info*.csv", "*ttack_info*.csv", "*attack*.csv")

    def _provenance_csvs(self) -> list[Path]:
        return self._find("*rovenance*.csv")

    def inspect(self) -> InspectionReport:
        files = []
        if self.raw_dir.exists():
            for path in sorted(self.raw_dir.rglob("*")):
                if path.is_file():
                    files.append({"path": str(path.relative_to(self.raw_dir)), "size": path.stat().st_size})
        notes = (
            "Registration gate: place provenance CSVs, network CSV and Attack_info.csv under "
            "data/raw/cicapt_iiot/. Not auto-downloaded."
        )
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
                "Access is a registration form at https://cicresearch.ca/IOTDataset/CICAPT-IIoT%20Dataset/ "
                "(insert.php -> browse.php). We do NOT bypass it. Steps: (1) submit the short form; "
                "(2) download Provenance logs, Network traffic and Supplementary material; "
                "(3) unzip into data/raw/cicapt_iiot/ keeping Attack_info.csv. "
                "Note: unlicensed third-party mirrors exist but are not endorsed; obtain via the official form."
            ),
        )

    def validate_raw(self) -> RawValidationResult:
        res = RawValidationResult(dataset_id=self.dataset_id, ok=True)
        net = self._network_csvs()
        prov = self._provenance_csvs()
        atk = self._attack_info_csvs()
        res.add("network_csv", bool(net), net[0].name if net else "missing")
        res.add("provenance_csv", bool(prov), f"{len(prov)} files")
        res.add("attack_info_csv", bool(atk), atk[0].name if atk else "missing")
        res.ok = res.ok or not (net or prov or atk)
        return res

    def load_raw(self) -> RawBundle:
        if self.synthetic:
            return self._load_fixture()
        bundle = RawBundle()
        self._load_network(bundle)
        self._load_attack_info(bundle)
        self._load_provenance(bundle)
        return bundle

    def _load_fixture(self) -> RawBundle:
        if not SYNTHETIC_FIXTURE.exists():
            return RawBundle()
        df = pd.read_csv(SYNTHETIC_FIXTURE)
        bundle = RawBundle()
        bundle.observations.extend(canonical_frame_to_observations(df, "cicapt_iiot:scenario"))
        stage_labels = sorted(set(str(s) for s in df.get("stage", pd.Series(dtype=str)).dropna().unique()))
        bundle.campaign_seeds.append(
            CampaignSeed(
                campaign_id_source=SYNTHETIC_CAMPAIGN,
                stage_labels=stage_labels or ["Discovery", "Lateral Movement", "Command and Control"],
                ground_truth_available=True,
            )
        )
        return bundle

    def _load_network(self, bundle: RawBundle) -> None:
        cap = self.settings.sample_max_flow_rows if self.settings.data_mode == "sample" else None
        for csv_path in self._network_csvs():
            df = pd.read_csv(csv_path, nrows=cap, low_memory=False)
            canonical = canonicalize_flow_frame(df)
            bundle.observations.extend(canonical_frame_to_observations(canonical, "cicapt_iiot:network"))

    def _load_attack_info(self, bundle: RawBundle) -> None:
        for csv_path in self._attack_info_csvs():
            df = pd.read_csv(csv_path, low_memory=False)
            cols = {str(c).strip().lower(): c for c in df.columns}
            time_col = cols.get("attack time") or cols.get("time") or cols.get("timestamp")
            cat_col = cols.get("category") or cols.get("tactic") or cols.get("attack type")
            tech_col = cols.get("technique") or cols.get("technique id")
            stages: list[str] = []
            first_ts = last_ts = None
            for row in df.to_dict(orient="records"):
                ts = pd.to_datetime(row.get(time_col), utc=True, errors="coerce") if time_col else None
                category = str(row.get(cat_col, "")).strip() if cat_col else ""
                technique = str(row.get(tech_col, "")).strip() if tech_col else ""
                if category and category not in stages:
                    stages.append(category)
                if ts is not None and not pd.isna(ts):
                    first_ts = ts if first_ts is None else min(first_ts, ts)
                    last_ts = ts if last_ts is None else max(last_ts, ts)
                    bundle.observations.append(
                        RawObservation(
                            timestamp=ts.to_pydatetime(),
                            original_label=category or "attack",
                            original_sub_label=technique or None,
                            campaign_key=SYNTHETIC_CAMPAIGN,
                            evidence_source="cicapt_iiot:attack_info",
                        )
                    )
            bundle.campaign_seeds.append(
                CampaignSeed(
                    campaign_id_source=SYNTHETIC_CAMPAIGN,
                    start_time=first_ts.to_pydatetime() if first_ts is not None else None,
                    end_time=last_ts.to_pydatetime() if last_ts is not None else None,
                    stage_labels=stages,
                    ground_truth_available=True,
                )
            )

    def _load_provenance(self, bundle: RawBundle) -> None:
        for csv_path in self._provenance_csvs():
            df = pd.read_csv(csv_path, nrows=self.settings.sample_max_provenance_rows, low_memory=False)
            cols = {str(c).strip().lower(): c for c in df.columns}
            id_col = cols.get("id") or cols.get("node id") or cols.get("uuid")
            type_col = cols.get("type") or cols.get("node type") or cols.get("entity")
            name_col = cols.get("name") or cols.get("node_name") or cols.get("label")
            if not id_col:
                continue
            seen: set[str] = set()
            for row in df.to_dict(orient="records"):
                node_id = str(row.get(id_col, "")).strip()
                if not node_id or node_id in seen:
                    continue
                seen.add(node_id)
                node_type = str(row.get(type_col, "")).strip().lower() if type_col else ""
                name = str(row.get(name_col, "")).strip() if name_col else ""
                ident = resolve_asset_identity(self.source.value, fallback_key=f"prov-{node_id[:12]}")
                asset_type = AssetType.PROCESS if node_type == "process" else AssetType.UNKNOWN
                bundle.extra_assets.append(
                    Asset(
                        asset_id=ident.asset_id,
                        asset_type=asset_type,
                        hostname=name or None,
                        identity_method=IdentityMethod.DATASET_DERIVED,
                        identity_confidence=ident.identity_confidence,
                        evidence_sources=["cicapt_iiot:provenance"],
                        dataset_source=self.source,
                    )
                )
