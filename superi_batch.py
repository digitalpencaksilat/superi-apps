#!/usr/bin/env python3
"""Reusable Batch per Jam operations for the Textual interface."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Optional


@dataclass(frozen=True)
class BatchOverview:
    data_type: str
    label: str
    date: str
    items: tuple[dict, ...]
    empty_by_period: tuple[tuple[dict, ...], ...]

    @property
    def active_items(self) -> int:
        return sum(1 for item in self.items if item.get("statusCB") != "OFF")

    @property
    def incomplete_periods(self) -> int:
        return sum(bool(items) for items in self.empty_by_period)

    @property
    def actionable_periods(self) -> tuple[int, ...]:
        return tuple(period for period, items in enumerate(self.empty_by_period) if items)


@dataclass
class BatchSuggestion:
    item: dict
    value: Optional[float]
    hv: Optional[float] = None
    info: str = ""

    @property
    def valid(self) -> bool:
        return self.value is not None and (self.hv is not None if "tegangan" in self.item.get("_batch_type", "") else True)


@dataclass(frozen=True)
class BatchResult:
    total: int
    success: int
    failed: int
    failures: tuple[tuple[str, str], ...] = field(default_factory=tuple)


def load_overview(token, data_type: str, gi_id, date_str: str) -> BatchOverview:
    import superi_app as core

    endpoint = core.ENDPOINTS[data_type]
    response = core.api_get(token, endpoint["list"], {"garduIndukId": gi_id, "date": date_str})
    items = tuple(response.get("data", {}).get("items", []))
    data_key = "tegangan" if data_type == "tegangan-trafo" else "beban"
    empty_by_period = []
    for period in range(24):
        empty = []
        for item in items:
            if item.get("statusCB") == "OFF":
                continue
            filled = {entry["periode"] for entry in item.get(data_key, [])}
            if period not in filled:
                empty.append(item)
        empty_by_period.append(tuple(empty))
    return BatchOverview(data_type, endpoint["label"], date_str, items, tuple(empty_by_period))


def analyze_period(overview: BatchOverview, period: int, token, gi_id) -> list[BatchSuggestion]:
    import superi_app as core

    if not 0 <= int(period) <= 23:
        raise ValueError("Periode harus 0-23")
    items = overview.empty_by_period[int(period)]
    date = datetime.strptime(overview.date, "%Y-%m-%d")
    weekend = date.weekday() >= 5
    cache = core.fetch_history_bulk(token, overview.data_type, gi_id, overview.date)
    suggestions = []
    for item in items:
        tagged = dict(item)
        tagged["_batch_type"] = overview.data_type
        if overview.data_type == "tegangan-trafo":
            mv, hv, info = core.smart_suggest_tegangan_from_cache(cache, item["id"], period, weekend)
            suggestions.append(BatchSuggestion(tagged, mv, hv, info or "Tidak ada histori"))
        else:
            value, info = core.smart_suggest_from_cache(cache, item["id"], period, weekend)
            suggestions.append(BatchSuggestion(tagged, value, None, info or "Tidak ada histori"))
    return suggestions


def submit_period(
    overview: BatchOverview,
    period: int,
    suggestions: list[BatchSuggestion],
    token,
    *,
    progress: Optional[Callable[[int, int, str, bool, str], None]] = None,
) -> BatchResult:
    import superi_app as core

    endpoint = core.ENDPOINTS[overview.data_type]
    valid = [suggestion for suggestion in suggestions if suggestion.valid]
    if not valid:
        raise ValueError("Tidak ada item dengan nilai valid")
    if core.hu and hasattr(core.hu, "reset_foto_sequence"):
        core.hu.reset_foto_sequence(overview.date, period)
    date = datetime.strptime(overview.date, "%Y-%m-%d")
    failures = []
    success = 0
    shuffled = core._human_shuffled(valid)
    for index, suggestion in enumerate(shuffled, 1):
        item = suggestion.item
        duration = core._human_durasi(overview.data_type)
        payload = {
            endpoint["id_field"]: item["id"],
            "timezone": "Asia/Jakarta",
            "periode": period,
            "tanggal": date.day,
            "bulan": date.month - 1,
            "tahun": date.year,
            "durasi": duration,
        }
        if overview.data_type == "tegangan-trafo":
            foto_hv, foto_mv = core._human_foto_pair_dicts(overview.date, period, duration)
            payload[endpoint["value_field"]] = suggestion.value
            payload["hv"] = suggestion.hv
            payload["fotoHV"] = foto_hv
            payload["fotoMV"] = foto_mv
            detail = f"MV={suggestion.value} HV={suggestion.hv}"
        else:
            payload[endpoint["value_field"]] = suggestion.value
            payload["foto"] = core._human_foto_dict(overview.date, period, duration, overview.data_type)
            detail = f"{suggestion.value}A"
        try:
            _, result = core.api_post_multipart(
                token, endpoint["input"], payload, core.DUMMY_JPEG,
                endpoint["file_field"], endpoint["num_photos"], item_name=item["nama"],
            )
            ok = bool(result.get("success"))
            photo = result.get("_photo_upload")
            if ok and photo and not photo.get("ok"):
                record_id = (result.get("data") or {}).get("id")
                if record_id:
                    try:
                        core.api_delete(token, f"{endpoint['delete']}/{record_id}")
                    except Exception:
                        pass
                ok = False
                detail = "Foto gagal; record dihapus untuk retry"
            elif not ok:
                detail = str(result.get("message", "error"))[:80]
        except Exception as exc:
            ok = False
            detail = str(exc)[:80]
        if ok:
            success += 1
        else:
            failures.append((item["nama"], detail))
        if progress:
            progress(index, len(valid), item["nama"], ok, detail)
        if index < len(valid):
            core._human_sleep(0.8, 3.2)
    return BatchResult(len(valid), success, len(failures), tuple(failures))
