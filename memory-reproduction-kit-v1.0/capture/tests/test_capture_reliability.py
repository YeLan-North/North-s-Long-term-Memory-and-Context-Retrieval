import datetime as dt
import json
import pathlib
import tempfile
import unittest
from test_chatgpt_sync import load, conversation, message

class ReliabilityTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        root=pathlib.Path(self.tmp.name)
        self.cs=load({'data_dir':str(root/'data'),'state_dir':str(root/'state')},str(root))
        self.cs.ensure_data_repo()

    def test_timestamp_formats(self):
        for v in [1792306800,1792306800000,'1792306800','2026-10-18T07:00:00Z']:
            self.assertEqual(self.cs.to_epoch(v),1792306800)
        for v in [True,float('nan'),float('inf'),-1,'bad','2026-10-18T07:00:00']:
            with self.assertRaises((ValueError,TypeError)):self.cs.to_epoch(v)

    def test_whitelist_and_path_ids(self):
        for conv in [dict(conversation(),gizmo_id='g-p-other'),conversation(cid='../../outside')]:
            with self.assertRaises(ValueError):self.cs.store(conv,None,{})
        self.assertFalse((pathlib.Path(self.tmp.name)/'outside.json').exists())

    def test_stale_details_and_broken_graph(self):
        conv=conversation()
        with self.assertRaises(ValueError):self.cs.store(conv,{'update_time':conv['update_time']+100},{})
        for parent in ['absent','n2']:
            conv=conversation();conv['mapping']['n1']['parent']=parent
            with self.assertRaises(ValueError):self.cs.store(conv,None,{})

    def test_midnight_and_branches(self):
        conv=conversation();a=message('assistant','before',1792306799);a['id']='msg-a'
        b=message('assistant','after',1792306800);b['id']='msg-b'
        alt=message('user','alternate',1792306799);alt['id']='msg-alt'
        conv['mapping']={'a':{'parent':None,'message':a},'b':{'parent':'a','message':b},'alt':{'parent':'a','message':alt}};conv['current_node']='b'
        rows,missing=self.cs.daily_rows(conv,'g-p-test',dt.date(2026,10,17))
        self.assertFalse(missing);self.assertEqual([r['message_id']for r in rows],['msg-a','msg-alt'])
        self.assertEqual([r['branch']for r in rows],['current','alternative'])
        self.assertEqual(rows[0]['timestamp'],'2026-10-17T23:59:59-07:00')
        rows,_=self.cs.daily_rows(conv,'g-p-test',dt.date(2026,10,18));self.assertEqual([r['message_id']for r in rows],['msg-b'])
        md=self.cs.render_markdown(conv,{'title':'test','update_time':1792306800});self.assertEqual(md.count('## ChatGPT'),2)

    def test_missing_message_time(self):
        conv=conversation();conv['mapping']['n1']['message']['create_time']=None
        _,missing=self.cs.daily_rows(conv,'g-p-test',dt.date(2026,10,17));self.assertTrue(missing)

    def test_dst(self):
        a=dt.datetime(2025,11,2,tzinfo=self.cs.TZ).timestamp();b=dt.datetime(2025,11,3,tzinfo=self.cs.TZ).timestamp()
        self.assertEqual(b-a,25*3600)

    def test_incomplete_export(self):
        out=str(pathlib.Path(self.tmp.name)/'daily');r=self.cs.export_day(dt.date(2026,10,17),out)
        self.assertEqual(r['status'],'partial');self.assertTrue(r['errors'])
        self.assertTrue((pathlib.Path(out)/'2026-10-17.manifest.json').exists())

    def test_complete_export_retains_message(self):
        conv=conversation();conv['mapping']['n1']['message']['create_time']=1792306799
        conv['mapping']['n1']['message']['id']='stable-user-message'
        conv['mapping']['alt']['message']['create_time']=1759500010
        index={};self.cs.store(conv,None,index);self.cs.save_index(index)
        self.cs.write_atomic(self.cs.LAST_SYNC,json.dumps({'status':'complete','project_ids':['g-p-test'],'at':'2026-10-18T09:00:00Z'}))
        out=str(pathlib.Path(self.tmp.name)/'daily');r=self.cs.export_day(dt.date(2026,10,17),out)
        self.assertEqual(r['status'],'complete_for_observed_inventory')
        rows=[json.loads(x)for x in (pathlib.Path(out)/'2026-10-17.jsonl').read_text().splitlines()]
        self.assertEqual(rows[0]['message']['id'],'stable-user-message')
