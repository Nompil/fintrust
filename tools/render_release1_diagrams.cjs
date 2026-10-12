// Documentation-only renderer. Uses the installed Viz.js Graphviz WASM runtime.
const fs=require('node:fs'),path=require('node:path');
const root=path.resolve(__dirname,'..');
const lib=process.env.FINTRUST_VIZ_MODULE;if(!lib)throw Error('Set FINTRUST_VIZ_MODULE to an installed @viz-js/viz package');
// Marker cells reserve icon space during layout. Embed retained official PNGs so
// the SVG remains portable, with no external files or network requests at viewing time.
function embedAwsIcons(svg) {
  return svg.replace(/<text\b([^>]*)>ICON_([a-z0-9]+)<\/text>/g, (match, attrs, key) => {
    const x=Number(attrs.match(/\bx="([^"]+)"/)[1])+2-24;
    const y=Number(attrs.match(/\by="([^"]+)"/)[1])-24;
    const png=fs.readFileSync(path.join(root,'docs','diagrams','aws-icons',key+'.png'));
    return `<image x="${x}" y="${y}" width="48" height="48" preserveAspectRatio="xMidYMid meet" href="data:image/png;base64,${png.toString('base64')}"/>`;
  });
}
const names=['erd','aws-architecture','activity','use-cases','data-decisions','duplicate-handling','role-separation'];
(async()=>{const viz=await require(lib).instance();const results=[];
for(const name of names){const sourceBase=path.join(root,'docs','presentation','diagram-source','fintrust-release1-'+name);const outputDir=path.join(root,'build','presentation-pdf','svg');fs.mkdirSync(outputDir,{recursive:true});const base=path.join(outputDir,'fintrust-release1-'+name);const source=fs.readFileSync(sourceBase+'.dot','utf8');let rendered=viz.renderString(source,{format:'svg',engine:['erd','activity','aws-architecture'].includes(name)?'neato':'dot'});if(name==='aws-architecture')rendered=embedAwsIcons(rendered);if(!rendered.includes('<svg')||!rendered.includes('<text'))throw Error('Empty diagram '+name);fs.writeFileSync(base+'.svg',rendered);results.push({name,status:'RENDERED',engine:['erd','activity','aws-architecture'].includes(name)?'neato':'dot',viewBox:rendered.match(/viewBox="([^"]+)"/)[1]});}console.log(JSON.stringify(results,null,2));})().catch(e=>{console.error(e);process.exitCode=1;});
