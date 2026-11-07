"""Recover a *same-ISO* resource and 40-block scan hints for Alpha.

The legacy fusion selector rejects renamed containers unless seven banks are
conflict-free. This read-only adapter uses an existing independently validated
weight-family scan as an alternative route, and revalidates all table bytes
before displaying any reward candidates.
"""
from __future__ import annotations

from pathlib import Path
from auto_mods import load_json

MAX_REPORT_BYTES=8*1024*1024
MAX_RESOURCE_BYTES=96*1024*1024


def _family_good(value):
    if not isinstance(value,dict):
        return False
    if value.get("scanComplete") is not True:
        return False
    clusters=value.get("clusters",[])
    return (isinstance(clusters,list)
            and any(isinstance(x,dict)
                    and x.get("consecutiveBlockCount")==40
                    and x.get("possible39BlockWindows")==2
                    for x in clusters))


def recover_scan_resource(home: Path, profile: dict, sha: str,
                          indexed_files: dict) -> tuple[str,dict] | None:
    """Return unique resource name & evidence, or None. No raw bytes exposed."""
    if (not isinstance(profile,dict) or profile.get("rom_sha256")!=sha
            or not isinstance(indexed_files,dict)):
        return None
    folder_text=profile.get("scan_result_dir")
    if not isinstance(folder_text,str) or not folder_text:
        return None
    try:
        root=(Path(home)/"analises").resolve(strict=True)
        folder=Path(folder_text).resolve(strict=True)
        report=(folder/"relatorio.json").resolve(strict=True)
        if (not folder.is_relative_to(root) or
                not report.is_relative_to(root)
                or not report.is_file()
                or report.stat().st_size>MAX_REPORT_BYTES):
            return None
        meta=load_json(report,{})
    except (OSError,ValueError,TypeError):
        return None
    if not isinstance(meta,dict) or meta.get("sha256")!=sha:
        return None

    choices=[]
    family=meta.get("mod_family_evidence")
    raw_source=meta.get("wa_resource_selection")
    if isinstance(raw_source,dict) and _family_good(family):
        name=raw_source.get("source")
        if isinstance(name,str):
            choices.append((name,family))

    if not choices:
        audit=meta.get("mod_family_audit",{})
        rows=audit.get("resourcesScanned",[]) if isinstance(audit,dict) else []
        if isinstance(rows,list):
            for row in rows[:8]:
                if isinstance(row,dict) and _family_good(row.get("weightFamily")):
                    choices.append((row.get("resource"),row["weightFamily"]))
    # Never infer which of two different resources is the real one.
    unique={x[0] for x in choices if isinstance(x[0],str)}
    if len(unique)!=1:
        return None
    name, detected=choices[0]
    entry=indexed_files.get(name)
    if (not isinstance(entry,tuple) or len(entry)!=2
            or type(entry[1]) is not int
            or not 40*0x1800<=entry[1]<=MAX_RESOURCE_BYTES):
        return None
    return name,detected
