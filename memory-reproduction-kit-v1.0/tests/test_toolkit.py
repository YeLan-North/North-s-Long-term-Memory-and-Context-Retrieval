import importlib.util,json,subprocess,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from export_reader import capture_module,load_conversations

def synthetic():
    def node(parent,role,text,stamp,hidden=False):
        return {'parent':parent,'message':{'id':'m-'+text,'author':{'role':role},'create_time':stamp,'content':{'content_type':'text','parts':[text]},'metadata':{'is_visually_hidden_from_conversation':hidden}}}
    return {'conversation_id':'11111111-1111-4111-8111-111111111111','title':'Synthetic conversation','current_node':'b','mapping':{
        'root':{'parent':None,'message':None},
        'a':node('root','user','测试问题','2026-10-17T22:00:00-07:00'),
        'b':node('a','assistant','当前回答','2026-10-17T22:01:00-07:00'),
        'c':node('a','assistant','另一分支','2026-10-17T22:02:00-07:00'),
        'hidden':node('b','assistant','隐藏技术上下文','2026-10-17T22:03:00-07:00',True),
        'next':node('b','user','跨日消息','2026-10-18T00:01:00-07:00')}}

class Tests(unittest.TestCase):
    def test_all_history_and_branch(self):
        m=capture_module('America/Vancouver');rows,missing=m['daily_rows'](synthetic(),None,None)
        self.assertEqual(len(rows),4);self.assertEqual(missing,[])
        self.assertEqual(next(x for x in rows if x['node_id']=='b')['branch'],'current')
        self.assertEqual(next(x for x in rows if x['node_id']=='c')['branch'],'alternative')
        self.assertEqual(next(x for x in rows if x['node_id']=='a')['message'],synthetic()['mapping']['a']['message'])
    def test_date_cutoff(self):
        import datetime
        m=capture_module('America/Vancouver');rows,_=m['daily_rows'](synthetic(),None,datetime.date(2026,10,17))
        self.assertEqual(len(rows),3);self.assertNotIn('next',[x['node_id'] for x in rows])
    def test_changed_snapshot_not_silently_deduped(self):
        with tempfile.TemporaryDirectory() as tmp:
            a=Path(tmp)/'a.json';b=Path(tmp)/'b.json';c=synthetic();a.write_text(json.dumps([c]));c['title']='changed';b.write_text(json.dumps([c]))
            with self.assertRaises(ValueError):load_conversations([a,b])
    def test_reader_end_to_end(self):
        with tempfile.TemporaryDirectory() as tmp:
            a=Path(tmp)/'a.json';a.write_text(json.dumps([synthetic()],ensure_ascii=False));out=Path(tmp)/'output'
            subprocess.run([sys.executable,str(ROOT/'scripts/export_reader.py'),str(a),'--output',str(out)],check=True,capture_output=True)
            rows=[json.loads(x) for x in (out/'selected-messages.jsonl').read_text().splitlines()]
            self.assertEqual(len(rows),4);self.assertNotIn('隐藏技术上下文',(out/'selected-conversations.md').read_text())
    def test_missing_time_report(self):
        c=synthetic();c['mapping']['a']['message']['create_time']=None
        rows,missing=capture_module('UTC')['daily_rows'](c,None,None)
        self.assertEqual(missing[0]['node_id'],'a')
    def test_cycle_rejected(self):
        c=synthetic();c['mapping']['root']['parent']='b'
        with self.assertRaises(ValueError):capture_module('UTC')['daily_rows'](c,None,None)

if __name__=='__main__':unittest.main()
