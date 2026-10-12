// Documentation-only renderer. Uses the installed Viz.js Graphviz WASM runtime.
const fs=require('node:fs'),path=require('node:path');
const root=path.resolve(__dirname,'..');
const lib=process.env.FINTRUST_VIZ_MODULE;if(!lib)throw Error('Set FINTRUST_VIZ_MODULE to an installed @viz-js/viz package');
const names=['erd','aws-architecture','activity','use-cases','data-decisions','duplicate-handling','role-separation'];
(async()=>{const viz=await require(lib).instance();const results=[];
for(const name of names){const base=path.join(root,'docs','diagrams','fintrust-release1-'+name);const source=fs.readFileSync(base+'.dot','utf8');const rendered=viz.renderString(source,{format:'svg',engine:['erd','activity','aws-architecture'].includes(name)?'neato':'dot'});if(!rendered.includes('<svg')||!rendered.includes('<text'))throw Error('Empty diagram '+name);fs.writeFileSync(base+'.svg',rendered);results.push({name,status:'RENDERED',engine:['erd','activity','aws-architecture'].includes(name)?'neato':'dot',viewBox:rendered.match(/viewBox="([^"]+)"/)[1]});}console.log(JSON.stringify(results,null,2));})().catch(e=>{console.error(e);process.exitCode=1;});
