"""Output layer: a checklist to work through in the Beli app."""
from __future__ import annotations

from datetime import date
from pathlib import Path
from urllib.parse import quote_plus



def _maps_link(name: str, address: str, place_id: str) -> str:
    if place_id.startswith("manual:"):
        return f"https://www.google.com/maps/search/?api=1&query={quote_plus(name)}"
    return f"https://www.google.com/maps/search/?api=1&query={quote_plus(name + ' ' + address)}&query_place_id={place_id}"


def write_checklist(entries: list[dict], out_dir: Path, today: date | None = None) -> Path | None:
    """entries: dicts with place_id, name, address, visits (list of ISO dates)."""
    if not entries:
        return None
    today = today or date.today()
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"beli-checklist-{today.isoformat()}.md"
    lines = [f"# Add to Beli: {today.isoformat()}", "", f"{len(entries)} restaurant{'s' if len(entries) != 1 else ''}. Search each in Beli and bookmark it.", ""]
    for e in sorted(entries, key=lambda e: e["name"].lower()):
        n = len(e["visits"])
        visits = f"{n} visit{'s' if n != 1 else ''}: {', '.join(e['visits'])}" if n else "no visits recorded"
        lines.append(f"- [ ] **{e['name']}**, {e['address'] or 'address unknown'}")
        lines.append(f"  - {visits} · [map]({_maps_link(e['name'], e['address'] or '', e['place_id'])})")
    path.write_text("\n".join(lines) + "\n")
    return path
