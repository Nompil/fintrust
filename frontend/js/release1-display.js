"use strict";
// Display aliases only: never used as database keys, lookup parameters or exports.
const FinTrustDisplay = (() => {
  const uuid = value => typeof value === "string" && /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(value);
  const prefixes = {account_id:"ACC",tx_id:"TX",canonical_tx_id:"TX",batch_id:"BATCH",reprocess_batch_id:"BATCH",risk_event_id:"RISK",quarantine_id:"CASE"};
  function reference(kind, value) {
    if (kind === "risk_event_id" && /^[0-9]+$/.test(String(value))) return "RISK-" + String(value).padStart(4,"0");
    if (!uuid(value)) return value == null ? "Not recorded" : String(value);
    if (kind === "account_id" && /^20000000-0000-4000-8000-00000000000[1-5]$/i.test(value)) return "ACC-" + value.slice(-4);
    // FNV-1a 64-bit, encoded as 13 base36 characters: stable across sort/page/session.
    let hash = 14695981039346656037n;
    for (const c of value.toLowerCase()) hash = BigInt.asUintN(64, (hash ^ BigInt(c.charCodeAt(0))) * 1099511628211n);
    return (prefixes[kind] || "REF") + "-" + hash.toString(36).toUpperCase().padStart(13,"0");
  }
  function value(kind, raw) {
    if (raw === null || raw === undefined || raw === "") return kind === "risk_level" ? "Not assessed" : "Not recorded";
    if (prefixes[kind]) return reference(kind, raw);
    return typeof raw === "object" ? JSON.stringify(raw, null, 2) : String(raw);
  }
  function failure(status, page) {
    if (status === 401) return "Session expired. Sign in again to continue.";
    if (status === 403) return "You do not have permission for this action.";
    if (status === 409) return "Record changed. Refresh and try again.";
    if (page === "Insights") return "Insights unavailable. Refresh and try again.";
    return "Data unavailable. Refresh and try again.";
  }
  function notice(message, severity, page) {
    const title = page === "Insights" && severity === "ERROR" ? "Insight unavailable" : /File rejected/i.test(message) ? "File rejected" : /already processed/i.test(message) ? "Duplicate file" : severity === "WARNING" ? "Rows need attention" : severity === "ERROR" ? "Action unavailable" : severity === "ACTION_REQUIRED" ? "Attention required" : severity === "SUCCESS" ? "Action completed" : "Workspace update";
    return {title, action: page ? "Open " + page : "Refresh and try again."};
  }
  return {uuid, reference, value, failure, notice};
})();
if (typeof module !== "undefined") module.exports = FinTrustDisplay;
