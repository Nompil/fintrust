"use strict";
function rowOutcomeSummary(data){
 const panel=node("section","");panel.className="row-outcome-summary";panel.setAttribute("aria-label","All source row outcomes");
 panel.append(node("h3","All rows in this upload"));
 if(!data){panel.append(node("p","Row and risk totals are not yet available. Refresh processing details."));return panel;}
 const categories=[["low","low risk"],["medium","medium risk"],["high","high risk"],["unassessed","accepted, not assessed"],["quarantined","quarantined"],["duplicates","duplicates"],["technical_failures","technical failures"],["pending","pending"]];
 panel.append(node("p",`${data.rows_received??"Not recorded"} rows received: `+categories.filter(([key])=>Number(data[key])>0).map(([key,label])=>`${data[key]} ${label}`).join("; ")+"."));
 panel.append(metricTiles(categories.map(([key,label])=>[label.charAt(0).toUpperCase()+label.slice(1),data[key]]),"receipt-counts"));
 panel.append(node("p",data.counts_consistent?data.complete?"All source rows reconcile to a recorded outcome.":"Totals reconcile; some source rows are still pending.":"Totals are not yet reconciled. Do not treat this upload as complete."),node("p",data.quarantine_note),node("p",data.risk_scope));
 return panel;
}
