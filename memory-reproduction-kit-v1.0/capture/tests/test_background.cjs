const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const source=fs.readFileSync(path.join(__dirname,'../extension/background.js'),'utf8');
const id='65000000-1111-2222-3333-444444444444';
async function scenario(mode){
 const state={lastSuccess:123},calls=[],posts=[],event={addListener(){}};
 const chrome={storage:{local:{async get(k){return{[k]:state[k]}},async set(v){Object.assign(state,v)}}},runtime:{onInstalled:event,onStartup:event,onMessage:event},alarms:{create(){},onAlarm:event},action:{async setBadgeText(){},async setBadgeBackgroundColor(){},async setTitle(){}}};
 const response=(status,data)=>({status,ok:status>=200&&status<300,headers:{get(){return null}},async json(){return data}});
 async function fetch(url,opts={}){
  calls.push(url);
  if(url.startsWith('http://127.0.0.1:8765')){
   const body=opts.body?JSON.parse(opts.body):null;if(body)posts.push({url,body});
   if(url.endsWith('/config'))return response(200,{capture_version:2,project_ids:mode==='no_whitelist'?[]:mode==='two_projects'?['g-p-first','g-p-second']:['g-p-test']});
   if(url.endsWith('/state'))return response(200,{ids:mode==='unchanged'?{[id]:1792306800}:{}});
   if(url.endsWith('/conversations'))return response(200,{accepted_ids:mode==='store_reject'?[]:[id],errors:mode==='store_reject'?[{error:'bad'}]:[]});
   if(url.endsWith('/sync-done'))return response(mode==='report_fail'?500:200,{complete:mode==='report_partial'?false:body.complete});
   throw Error('unknown local request');
  }
  if(url.endsWith('/api/auth/session'))return response(mode==='logged_out'?401:200,mode==='logged_out'?{}:{accessToken:'synthetic-token'});
  if(url.includes('/gizmos/g-p-first/conversations'))return response(403,{});
  if(url.includes('/gizmos/')&&url.includes('/conversations?')){
   if(mode==='inventory403')return response(403,{});
   if(mode==='bad_shape')return response(200,{unexpected:[]});
   if(mode==='empty')return response(200,{items:[],cursor:null});
   if(mode==='bad_id')return response(200,{items:[{id:'../../bad',update_time:1792306800}]});
   if(mode==='missing_cursor')return response(200,{items:[],has_more:true});
   const update_time=mode==='bad_time'?'invalid':mode==='milliseconds'?1792306800000:mode==='iso'?'2026-10-18T07:00:00Z':1792306800;
   return response(200,{items:[{id,update_time}],cursor:mode==='repeat_cursor'?'0':null});
  }
  if(url.includes('/backend-api/conversation/')){
   if(mode==='detail403')return response(403,{});
   return response(200,{conversation_id:mode==='wrong_id'?'wrong':id,gizmo_id:mode==='wrong_project'?'g-p-other':mode==='two_projects'?'g-p-second':'g-p-test',update_time:mode==='stale'?1792306700:1792306800,current_node:'n',mapping:mode==='bad_tree'?{}:{n:{parent:null,message:null}}});
  }
  throw Error('unexpected mocked URL');
 }
 const context=vm.createContext({chrome,fetch,AbortSignal,Date,Promise,Map,Set,encodeURIComponent,setTimeout(fn){fn();}});
 vm.runInContext(source,context);const report=await vm.runInContext('runSync()',context);return{state,calls,posts,report};
}
(async()=>{
 let count=0;
 for(const mode of ['numeric','milliseconds','iso','empty','unchanged']){
  const r=await scenario(mode);assert.equal(r.report.complete,true,mode);assert.equal(r.report.errors.length,0);assert.ok(r.state.lastSuccess>123);
  if(!['empty','unchanged'].includes(mode))assert.equal(r.report.summary.stored,1);
  assert.ok(!r.calls.some(u=>u.includes('/snorlax/sidebar')||u.includes('/backend-api/conversations?')));
  assert.ok(!JSON.stringify(r.state).includes('synthetic-token'));assert.ok(!JSON.stringify(r.posts).includes('synthetic-token'));count++;
 }
 for(const mode of ['inventory403','bad_shape','bad_id','missing_cursor','bad_time','repeat_cursor','detail403','wrong_id','wrong_project','stale','bad_tree','store_reject','report_fail','report_partial','no_whitelist','logged_out']){
  const r=await scenario(mode);assert.equal(r.report.complete,false,mode);assert.equal(r.state.lastSuccess,123,mode);assert.ok(r.report.errors.length,mode);count++;
 }
 const mixed=await scenario('two_projects');assert.equal(mixed.report.complete,false);assert.equal(mixed.report.summary.stored,1);assert.equal(mixed.report.inventories.length,2);count++;
 const blocked=await scenario('no_whitelist');assert.ok(!blocked.calls.some(x=>x.startsWith('https://chatgpt.com')));
 console.log(`${count} background scenarios passed (mocked browser/network only)`);
})().catch(e=>{console.error(e);process.exitCode=1});
