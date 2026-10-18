const $ = id => document.getElementById(id);
const fmt = t => t ? new Date(t).toLocaleString() : '尚无';
async function render(){
 const {run,lastError,lastErrorKind,lastSuccess,lastFinished,lastSummary,lastReport}=await chrome.storage.local.get(['run','lastError','lastErrorKind','lastSuccess','lastFinished','lastSummary','lastReport']);
 $('state').textContent=run?`正在采集：${run.stage}`:lastReport?.complete?`本次读取完成。列出 ${lastSummary.listed} 段；保存 ${lastSummary.stored} 段；未变化 ${lastSummary.unchanged} 段。`:lastFinished?'本次采集未完整完成，请查看缺失项。':'尚未采集。请先启动本地程序。';
 $('error').hidden=!lastError;$('error').textContent=lastError||'';$('login').hidden=lastErrorKind!=='login';
 $('last').textContent=`上次完整成功：${fmt(lastSuccess)}`;$('sync').disabled=Boolean(run);$('report').disabled=!lastReport;
 $('details').textContent=lastReport?JSON.stringify(lastReport,null,2):'尚无采集记录。';
}
$('sync').addEventListener('click',()=>chrome.runtime.sendMessage({type:'sync-now'}));
$('report').addEventListener('click',async()=>{
 const {lastReport}=await chrome.storage.local.get('lastReport');if(!lastReport)return;
 const url=URL.createObjectURL(new Blob([JSON.stringify(lastReport,null,2)],{type:'application/json'}));
 const a=document.createElement('a');a.href=url;a.download='capture-report.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
});
chrome.storage.onChanged.addListener(render);render();
