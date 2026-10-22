"use strict";
function cloudUserEditor(){
 if(principal?.role!=="Admin"||authMode!=="cognito")return;
 const form=node("form","");form.id="cloud-user-create-form";
 form.append(node("h3","Create application user"),node("p","Choose the role and assigned accounts. Cognito emails the temporary sign-in invitation; the user chooses a password and configures MFA. No password is entered here."));
 const fields={};
 for(const [key,label]of [["username","Username"],["display_name","Display name"],["email","Invitation email"],["role","Role"],["notes","Reason for granting access"]]){
  const wrap=node("label",label),input=node(key==="role"?"select":key==="notes"?"textarea":"input","");input.name=key;input.required=true;
  if(key==="email")input.type="email";
  if(key==="username"){input.maxLength=80;input.pattern="[A-Za-z0-9][A-Za-z0-9._-]{0,79}";input.autocomplete="off";}
  if(key==="display_name")input.maxLength=100;
  if(key==="notes"){input.minLength=3;input.maxLength=500;}
  if(key==="role")for(const role of ["Risk/Compliance Analyst","Read-only/Auditor","Maintainer","Admin"]){const option=node("option",roleLabel(role));option.value=role;input.append(option);}
  fields[key]=input;wrap.append(input);form.append(wrap);
 }
 const accounts=node("fieldset","");accounts.append(node("legend","Assigned accounts"));const choices=[];
 for(const account of principal.accounts){const label=node("label",FinTrustDisplay.reference("account_id",account)),input=node("input","");input.type="checkbox";input.value=account;label.prepend(input);accounts.append(label);choices.push(input);}
 form.append(accounts,node("p","Grant only the accounts this user needs. Technical maintainers receive no financial account scope."));
 fields.role.onchange=()=>{for(const choice of choices){choice.disabled=fields.role.value==="Maintainer";if(choice.disabled)choice.checked=false;}};
 const outcome=node("p","");outcome.setAttribute("role","status");const submit=node("button","Create user and request invitation");submit.type="submit";
 const check=secondaryButton("Check creation status",async()=>{if(!retry)return;check.disabled=true;try{const result=await request("/v1/user-provisioning?request_id="+encodeURIComponent(retry.id));showState(result.data);}catch(e){error(e);}finally{check.disabled=false;}});check.hidden=true;
 let retry=null;
 const receiptKey="imbokodo.user-provisioning."+principal.user_id;
 try{const prior=sessionStorage.getItem(receiptKey);if(prior){retry={id:prior,signature:null};check.hidden=false;}}catch{}
 function showState(data){
  outcome.textContent="Request "+data.request_id+" — "+data.state.replaceAll("_"," ");
  if(data.state==="INVITATION_REQUESTED"){outcome.append(node("span",". User access is configured and Cognito accepted the invitation request. Inbox delivery is not confirmed."));submit.disabled=true;outcome.append(secondaryButton("Create another user",()=>{try{sessionStorage.removeItem(receiptKey);}catch{}cloudUserEditor();}));}
  else outcome.append(node("span",". Do not create another request for this username. Check this status or ask Technical Operations to reconcile it."));
  check.hidden=false;
 }
 form.onsubmit=async event=>{
  event.preventDefault();const body=Object.fromEntries(Object.entries(fields).map(([key,input])=>[key,input.value.trim()]));body.accounts=choices.filter(input=>input.checked&&!input.disabled).map(input=>input.value);
  if(body.role!=="Maintainer"&&!body.accounts.length){outcome.textContent="Choose at least one assigned account.";return;}
  const signature=JSON.stringify(body);
  if(retry&&retry.signature===null){outcome.textContent="Check the previous creation request before starting a new one.";return;}
  if(retry&&retry.signature!==signature){outcome.textContent="Check the existing request before changing its fields or creating another user.";return;}
  if(!retry)retry={id:crypto.randomUUID(),signature};
  try{sessionStorage.setItem(receiptKey,retry.id);}catch{}
  submit.disabled=true;check.hidden=false;outcome.textContent="Creating the user. Check this request before retrying if the connection is interrupted.";
  try{const result=await request("/v1/user-provisioning",{method:"POST",body:JSON.stringify({...body,request_id:retry.id})});showState(result.data);}
  catch(e){outcome.textContent="Creation outcome is not confirmed. Use Check creation status before retrying.";error(e);}
  finally{submit.disabled=true;}
 };
 form.append(submit,check,secondaryButton("Back to users",()=>load()),outcome);byId("content").replaceChildren(form);
}
