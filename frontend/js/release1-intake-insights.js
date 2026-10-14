"use strict";
// Analyst presentation only: requirements, receipts and analytical counts come from existing APIs.
let currentCsvContract=null;

function renderCsvRequirements(contract){
 currentCsvContract=contract;
 const box=byId("csv-contract");box.replaceChildren();
 const details=node("details","");details.id="csv-requirements";
 const summary=node("summary","");summary.append(node("strong","CSV requirements"),node("span",`UTF-8 CSV · Max ${contract.max_file_bytes===1048576?"1 MiB":contract.max_file_bytes.toLocaleString()+" bytes"} · Max ${contract.max_rows.toLocaleString()} rows`));details.append(summary);
 const fields=node("div","");fields.className="csv-requirement-groups";
 for(const[label,values]of [["Required",contract.required],["Identity",contract.identity_one_of],["Optional",contract.optional]]){const group=node("section","");group.append(node("h4",label));const list=node("div","");list.className="csv-field-list";for(const value of values)list.append(node("code",value));if(label==="Identity")group.append(node("p","Include at least one source identity."));group.append(list);fields.append(group);}
 details.append(fields);box.append(details);
 const sample=secondaryButton("Download sample CSV",downloadSampleCsv);sample.id="download-sample-csv";sample.disabled=!principal?.accounts?.length;box.append(sample,node("small","Uses an assigned account and sample source values. Check the file before submitting."));
}

function downloadSampleCsv(){
 if(!currentCsvContract||!principal?.accounts?.length)return;
 const account=byId("account").value||principal.accounts[0];if(!principal.accounts.includes(account))return;
 const identity=currentCsvContract.identity_one_of.includes("source_reference")?"source_reference":currentCsvContract.identity_one_of[0];
 const fields=[...currentCsvContract.required,identity,...currentCsvContract.optional.filter(x=>x==="merchant")];
 const values={account_id:account,amount:"10.00",country:"ZA",currency:"ZAR",source_system:"imbokodo-sample",tx_date:new Date().toISOString(),tx_type:"debit",merchant:"Sample merchant",[identity]:"SAMPLE-"+crypto.randomUUID()};
 const quote=value=>'"'+String(value??"").replaceAll('"','""')+'"';
 const csv=fields.map(quote).join(",")+"\r\n"+fields.map(k=>quote(values[k])).join(",")+"\r\n";
 const url=URL.createObjectURL(new Blob([csv],{type:"text/csv;charset=utf-8"}));const link=node("a","");link.href=url;link.download="imbokodo-sample-transactions.csv";document.body.append(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);
}

function selectedAccountLabel(){const select=byId("account");return select.selectedOptions[0]?.textContent||"All assigned accounts";}
function refreshSelectedFile(){
 const file=byId("csv-file").files[0],box=byId("selected-file-details");box.replaceChildren();byId("process-file").disabled=!file;byId("clear-file-selection").disabled=!file;
 byId("selected-file-name").textContent=file?file.name:"No file selected";
 if(file){box.append(node("span",file.size<1024?file.size+" bytes":(file.size/1024).toFixed(1)+" KiB"),node("span",selectedAccountLabel()));box.title=file.size.toLocaleString()+" bytes · scope is checked against the account_id values in the file.";}
 byId("upload-scope-note").textContent="Known accounts in the file must be assigned to you. Account scope filters visible history; unknown or malformed account rows may enter quarantine.";
}
function clearFileSelection(){byId("csv-file").value="";refreshSelectedFile();}

function renderProcessingResult(result){
 const r=result.reconciliation||{},card=node("article","");card.className="processing-result-card";card.dataset.batchId=result.batch_id;
 const head=node("header","");head.className="processing-result-header";head.append(node("h3",uploadOutcomeHeading(result)));const state=node("span",r.pending?"Pending outcomes":r.failed_technical?"Recovery required":r.quarantined||r.duplicate?"Review exceptions":"Reconciled");state.className="status-badge "+(r.pending||r.failed_technical||r.quarantined?"status-medium":"status-low");head.append(state);card.append(head);
 if(result.notification?.helper)card.append(node("p",result.notification.helper));else if(r.quarantined||r.duplicate)card.append(node("p","The file was accepted, but one or more rows require attention."));
 const metadata=node("dl","");metadata.className="receipt-metadata";
 const receipt=uploadReceipts.get(result.batch_id)||result;
 for(const[label,value]of [["Processing Run",FinTrustDisplay.reference("batch_id",result.batch_id)],["Source file",result.original_filename||result.filename],["Submitted by",receipt.submitted_by||"Not recorded"],["Submitted at",receipt.submitted_at?FinTrustDisplay.time(receipt.submitted_at):"Not recorded"]])metadata.append(node("dt",label),node("dd",value||"Not recorded"));
 card.append(metadata,metricTiles([["Rows received",r.rows_received],["Accepted",r.accepted],["Quarantined",r.quarantined],["Duplicates",r.duplicate],["Failed",r.failed_technical],["Pending",r.pending]],"receipt-counts"));
 const parts=[[r.accepted,"accepted"],[r.quarantined,"quarantined"],[r.duplicate,"duplicate"],[r.failed_technical,"failed"],[r.pending,"pending"]].filter(([n])=>Number(n)>0).map(([n,label])=>`${n} ${label}`);
 card.append(dashboardSegments("Recorded processing outcome",[{label:"Accepted",count:r.accepted||0},{label:"Quarantined",count:r.quarantined||0},{label:"Duplicates",count:r.duplicate||0},{label:"Technical failures",count:r.failed_technical||0},{label:"Pending",count:r.pending||0}]));card.append(node("p",r.rows_received==null?"Rows received not recorded.":`${r.rows_received} received = ${parts.length?parts.join(" + "):"0 recorded outcomes"}`));
 const actions=node("div","");actions.className="receipt-actions";actions.setAttribute("aria-label","Processing next actions");
 const entries=[["View accepted transactions",r.accepted,"No accepted transactions in this processing run.",()=>sameScopeNavigation("Transactions",{batch_id:result.batch_id})],["Review quarantined rows",r.quarantined,"No quarantined rows in this processing run.",()=>openRunQuarantine(result.batch_id,result.filename)],["View risk events",receipt.risk_event_counts?.risk_events??result.risk_event_counts?.risk_events??null,"No risk events recorded in this processing run.",()=>openRunRiskEvents(result.batch_id)], ["View processing details",null,"",()=>openBatch(result.batch_id)]];
 for(const[label,count,help,action]of entries){const wrapper=node("div","");const b=button(label,action);if(label==="View processing details")b.classList.add("secondary-action");if(count!==null&&Number(count)===0){b.disabled=true;b.title=help;wrapper.append(b,node("small",help));}else wrapper.append(b);actions.append(wrapper);}card.append(actions);
 const notice=byId("upload-notice"),message=byId("upload-notice-message");message.replaceChildren(card);const previous=notices.filter(item=>!item.acknowledged&&["Ingestion Batches","Rejected Uploads"].includes(item.page)&&item.id!==notices[0]?.id);if(previous.length){const earlier=node("section","");earlier.className="earlier-upload-notices";earlier.append(node("strong","Earlier unread upload notices"));for(const item of previous){const entry=node("article",item.message);entry.className="notification "+item.severity.toLowerCase();earlier.append(entry);}message.append(earlier);}byId("acknowledge-upload").title="Mark these upload notices as read. This does not approve transactions or change processing results.";notice.hidden=false;notice.dataset.severity=result.notification?.severity||"info";return card;
}

async function openRunRiskEvents(batch){
 // The existing transaction filter supplies immutable run scope. Its matching rows lead to risk cases.
 sameScopeNavigation("Risk Events",{batch_id:batch});
}

async function enrichReceiptMetadata(result){
 const receipt=uploadReceipts.get(result.batch_id);if(!receipt)return;
 try{const data=(await request(`/v1/batches/${result.batch_id}?limit=1`)).data;const b=data.batch;receipt.submitted_by=b.submitted_by||null;receipt.submitted_at=b.submitted_at||null;receipt.risk_event_counts=b.risk_event_counts;if(byId("upload-notice").hidden===false&&byId("upload-notice-message").querySelector(`[data-batch-id="${result.batch_id}"]`))renderProcessingResult(result);}catch(errorValue){if(errorValue.staleSession||errorValue.sessionExpired)return;}
}

function renderRecentProcessingRuns(rows){renderCompactProcessingHistory(rows,"Recent Processing Runs");}
function renderCompactProcessingHistory(rows,title="Processing Runs"){
 const panel=node("section","");panel.className="recent-processing-runs processing-history-compact";panel.append(node("h3",title),node("p","Newest recorded runs first · current authorized account scope."));
 const sorted=[...rows].sort((a,b)=>Date.parse(b.received_at||0)-Date.parse(a.received_at||0)).map(row=>({...row,outcome_summary:[["Accepted",row.accepted],["Quarantine",row.quarantined],["Duplicate",row.duplicate],["Failed",row.failed_technical],["Pending",row.pending]].map(([label,value])=>label+" "+(value==null?"Not recorded":value)).join(" · ")}));
 panel.append(table(sorted,["batch_id","filename","actor","received_at","display_status","rows_received","outcome_summary"],(td,row)=>td.append(button("View processing details",()=>openBatch(row.batch_id)))));byId("content").replaceChildren(panel);
}

function configureExperiencePage(page){
 const toolbar=byId("insights-toolbar"),filters=byId("filters");
 if(page==="Insights"){toolbar.prepend(filters);toolbar.hidden=false;}else{if(filters.parentElement===toolbar)document.querySelector("main").insertBefore(filters,byId("transaction-filters"));toolbar.hidden=true;}
 const label=filters.querySelector("label");if(label?.firstChild?.nodeType===3)label.firstChild.textContent=page==="Upload Transactions"?"Account scope ":"Account ";
 const process=byId("upload-process-indicator");process.hidden=page!=="Upload Transactions";
 if(page==="Upload Transactions")refreshSelectedFile();
}

function insightsScopeLabel(){const period=byId("insights-days").selectedOptions[0]?.textContent||"Current period",risk=document.querySelector('[data-insights-filter="risk_level"]').value||"All risk levels";return selectedAccountLabel()+" · "+period+" · "+risk+(lastInsightsScope.country?" · "+lastInsightsScope.country:"")+" · SAST";}
function resetInsightsFilters(){byId("account").value="";byId("insights-days").value="30";for(const control of document.querySelectorAll("[data-insights-filter]"))control.value="";configureInsightPeriod();offset=0;load();}

function preciseMetric(label,value,note){const tile=node("div","");tile.className="decision-metric";tile.append(node("span",label),node("strong",value==null?"Not recorded":String(value)));tile.title=note;const helper=node("small",note);tile.append(helper);return tile;}
function insightQuestion(title,helper){const section=node("section","");section.className="decision-question";section.append(node("h3",title),node("p",helper));const metrics=node("div","");metrics.className="decision-metrics";const charts=node("div","");charts.className="insights-grid";section.append(metrics,charts);return {section,metrics,charts};}
function scopeRate(value){return value==null?"No scored entries":value+"%";}
function matchingTransactionsTable(rows){
 const box=node("div","");box.className="table-scroll matching-transactions";const t=node("table","");const head=node("tr","");for(const label of ["Transaction","Account","Amount","Risk","Primary reason","Review status","Assigned to","Time","Action"]){const th=node("th",label);th.scope="col";head.append(th);}t.append(head);
 for(const row of rows){const tr=node("tr","");if(assessmentPresentation(row).state==="HISTORICAL")tr.className="historical-row";const amount=tableCell("amount",row.amount);amount.prepend(node("small",(row.currency||"")+" "));const risk=node("td","");risk.append(assessmentBadge(row));const status=node("td","");status.append(reviewBadge(row));const owner=row.review_state==="NOT_REQUIRED"?"Not applicable":row.review_state==="HISTORICAL"?"Not recorded":row.assignee_label||row.reviewer_subject||(row.review_status?"Unassigned":"Not recorded");tr.append(tableCell("tx_id",row.tx_id),tableCell("account_id",row.account_id),amount,risk,node("td",primaryReason(row)),status,node("td",owner),tableCell("tx_date",row.tx_date));const action=node("td","");action.append(button(canInvestigate(row)?"Investigate":assessmentPresentation(row).state==="HISTORICAL"?"View history":"View details",()=>canInvestigate(row)?openInvestigation(row):openTransaction(row.tx_id)));tr.append(action);wireQueueRow(tr,row);t.append(tr);}if(rows.length)box.append(t);else box.append(node("p","No transactions match the current filters."));return box;
}

function renderDecisionInsights(data){
 const panel=node("div","");panel.className="decision-workspace";const scope=insightsScopeLabel();byId("insights-current-scope").querySelector("span").textContent=scope;
 const m=data.metrics||{},rateNote="Recorded risk assessments in the selected transaction scope. Historical unscored transactions are excluded.";const qualityNote="Account scope and upload/intake period. Accepted-transaction risk, review, country and type filters do not apply.";
 const activity=insightQuestion("WHAT HAPPENED?","Accepted activity in the selected period; processing exceptions use the upload period.");
 const international=(data.cross_border||[]).filter(x=>x.label==="Cross-border").reduce((sum,x)=>sum+Number(x.count),0);
 activity.metrics.append(preciseMetric("Risk-assessed transactions",m.scored_transactions,"Accepted transactions with a complete recorded risk assessment."),preciseMetric("Accepted transactions",m.transactions,"Accepted ledger entries matching the current filters, including historical entries."),preciseMetric("Cross-border activity",international,"Accepted transactions recorded as cross-border in this transaction scope."),preciseMetric("Processing failures",m.processing_failures,qualityNote));
 activity.charts.append(dashboardArea("Transaction volume · SAST",data.activity),dashboardRing("Cross-border vs domestic",data.cross_border,"transactions","Transactions","cross_border"));panel.append(activity.section);
 const risk=insightQuestion("WHERE IS THE RISK?","Recorded dimensions explain investigation priority; a risk score is not a fraud probability.");risk.metrics.append(preciseMetric("High-risk rate",scopeRate(m.high_risk_rate),"HIGH assessments / all complete recorded assessments. "+rateNote),preciseMetric("Medium-risk rate",scopeRate(m.medium_risk_rate),"MEDIUM assessments / all complete recorded assessments. "+rateNote),preciseMetric("Open reviews",m.open_reviews,"Current OPEN, UNDER REVIEW and ESCALATED reviews in the matching transaction scope."));
 risk.charts.append(dashboardRing("Risk distribution",data.risk,"assessed","Transactions","risk_level"),dashboardRanking("Risk dimensions",data.rules,"Transactions","scenario"),dashboardRanking("High-risk accounts",data.high_accounts,"Transactions","account_id",{...lastInsightsScope,risk_level:"High"}),dashboardArea("HIGH-risk trend · SAST",data.risk_trend,"Transactions",{...lastInsightsScope,risk_level:"High"}));if(data.rule_count_note)risk.section.append(node("p",data.rule_count_note));if(data.scoring_versions?.length){const detail=node("details","");detail.append(node("summary","Recorded scoring versions"),table(data.scoring_versions,["label","count"]));risk.section.append(detail);}panel.append(risk.section);
 const work=insightQuestion("WHAT NEEDS ATTENTION?","Current review deadlines and data-quality exceptions; overlapping views are not additive.");const sla=data.sla_policy?.enabled===false;
 work.metrics.append(preciseMetric("Due today",sla?"Not configured":m.due_today??m.reviews_due_today,"Active reviews due during the current SAST calendar day. May overlap with overdue reviews."),preciseMetric("Overdue",sla?"Not configured":m.overdue??m.reviews_over_sla,"Active reviews beyond the configured deadline. No automatic decision is made."),preciseMetric("Unassigned",m.unassigned??m.unassigned_reviews,"Active visible reviews with no recorded assigned Analyst."),preciseMetric("Quarantine requiring action",m.quarantine_open,"Open visible quarantine cases. "+qualityNote));
 const distribution=data.sla_state_counts||m.sla_state_counts;
 if(Array.isArray(distribution))work.charts.append(dashboardSla(m,data.sla_policy,lastInsightsScope));else{const box=node("section","");box.className="insight-chart";box.append(node("h3","Reviews by SLA state"),node("p",sla?"Review SLA not configured.":"Full-scope SLA distribution is not recorded. Open reviews to inspect recorded deadlines."),secondaryButton("Open overdue reviews",()=>sameScopeNavigation("Review Queue",{...lastInsightsScope,queue:"overdue"})));work.charts.append(box);}
 work.charts.append(dashboardRanking("Quarantine reasons",data.quality,"Quarantine","reason_code",qualityScope()));const actions=node("div","");actions.className="decision-actions";if(editable())actions.append(button("Open my work",()=>sameScopeNavigation("Review Queue",{...lastInsightsScope,queue:"my_work"})));actions.append(secondaryButton("Open overdue reviews",()=>sameScopeNavigation("Review Queue",{...lastInsightsScope,queue:"overdue"})),secondaryButton("Review quarantine",()=>sameScopeNavigation("Quarantine",qualityScope({status:"OPEN"}))));work.section.append(actions);panel.append(work.section);
 const outcomes=insightQuestion("WHAT WAS THE OUTCOME?","Current case outcomes for transactions in this period; processing counts use the upload period.");outcomes.metrics.append(preciseMetric("Cleared",m.cleared,"Current CLEARED reviews in the matching transaction scope."),preciseMetric("Confirmed risk",m.confirmed_risk,"Current CONFIRMED RISK reviews. This training system does not legally establish fraud."),preciseMetric("Specialist review",m.escalated,"Current referred/ESCALATED reviews. Referral is separate from assignment."));outcomes.charts.append(dashboardRing("Review outcomes",data.reviews,"cases","Review Queue","status"),dashboardSegments("Processing outcomes · row counts",data.batch_outcomes,"Ingestion Batches"));panel.append(outcomes.section);
 const matches=node("section","");matches.className="matching-records";matches.append(node("h3","Matching Transactions"),node("p","Transactions matching the current filters."),node("small","Up to 25 recent matches. Analytical totals cover the full matching authorized scope."),matchingTransactionsTable(data.transactions||[]));panel.append(matches);
 if(data.quality_scope_note){const note=node("details","");note.className="analytics-scope-notes";note.append(node("summary","How counts are scoped"),node("p",data.quality_scope_note));panel.append(note);}if(data.batches_bounded||data.quarantine_bounded)panel.append(node("p","Quality totals are bounded; older records may be excluded."));byId("content").replaceChildren(panel);
}

byId("csv-file").addEventListener("change",refreshSelectedFile);
byId("clear-file-selection").onclick=clearFileSelection;
byId("account").addEventListener("change",()=>{if(view==="Upload Transactions")refreshSelectedFile();});
byId("reset-insights-filters").onclick=resetInsightsFilters;
