"""Safe upload summaries derived from authoritative reconciliation, never parser details."""
def notification(status, state):
    if status == "DUPLICATE_FILE":
        return {"severity": "warning", "message": "File already processed; no additional transactions created."}
    if status != "COMPLETED" or not state.get("counts_consistent") or state.get("pending", 0):
        return {"severity": "error", "message": "Upload is incomplete. Some rows still require technical reconciliation; review processing details before retrying."}
    accepted, quarantined, duplicates = (state.get(k, 0) for k in ("accepted", "quarantined", "duplicate"))
    if quarantined or duplicates:
        return {"severity": "warning", "message": f"Processing completed — attention required: {accepted} accepted, {quarantined} quarantined, {duplicates} duplicates.", "helper":"The file was accepted, but one or more rows require attention."}
    return {"severity": "success", "message": f"Upload completed successfully: {accepted} rows processed."}
