"""Public **binary-only** DUELTRACE update distribution.

This repository must be separately created as PUBLIC and hold ONLY reviewed
Windows ZIP release assets, not the application source, ISOs, credentials,
customer records, or private diagnostic reports. The application never
authenticates to GitHub to check/download these updates.
"""
from __future__ import annotations

import re

PUBLIC_UPDATES_REPO = "guibatoni/dueltrace-releases"
PUBLIC_UPDATES_API = "https://api.github.com/repos/" + PUBLIC_UPDATES_REPO
PUBLIC_UPDATES_WEB = "https://github.com/" + PUBLIC_UPDATES_REPO

# The publisher appends exactly this audited build footer to release notes.
# GitHub release.target_commitish belongs to the PUBLIC repository and is
# intentionally not the SHA of the PRIVATE Windows build.
BUILD_TRAILER = re.compile(
    r"(?m)^Build ([1-9][0-9]{0,14}) \\| Commit ([a-f0-9]{40})"
    r" \\| SHA-256 ZIP: ([a-f0-9]{64})\\s*$"
)


def verified_source_identity(body: str, digest: str,
                             run_id: int | None = None) -> tuple[int,str]:
    """Require a unique source commit/build and exact asset digest."""
    if not isinstance(body,str) or len(body)>128*1024:
        raise ValueError("Notas oficiais de atualização ausentes ou grandes demais.")
    if not isinstance(digest,str) or not re.fullmatch(r"[a-f0-9]{64}",digest):
        raise ValueError("Digest de atualização inválido.")
    records=BUILD_TRAILER.findall(body)
    if len(records)!=1:
        raise ValueError("Identidade de compilação ausente ou ambígua.")
    build,sha,found_digest=records[0]
    number=int(build)
    if found_digest!=digest or (run_id is not None and number!=run_id):
        raise ValueError("Release pública não corresponde ao ZIP validado.")
    return number,sha
