"""Produce delivery evidence from real artifacts; fail on data loss or failed tests."""
import hashlib
import json
import sqlite3
import shutil
import subprocess
import xml.etree.ElementTree as ET

from paths import ROOT

out=ROOT/'reports/rag-upgrade'
baseline=json.loads((out/'baseline.json').read_text(encoding='utf-8'))
backup=ROOT/baseline['backup']
manifest=json.loads((backup/'private-manifest.json').read_text(encoding='utf-8'))
original=ROOT/'reports/original-video-factory-v2.json'
expected=next(x['sha256'] for x in manifest if x['path'].replace('\\','/')=='reports/original-video-factory-v2.json')
assert hashlib.sha256(original.read_bytes()).hexdigest()==expected
counts={}
with sqlite3.connect((ROOT/'runtime/steedatlas.db').as_uri()+'?mode=ro',uri=True) as db:
    for t in baseline['legacy_table_counts']:
        if not t.startswith('v2_'):
            counts[t]=db.execute('select count(*) from "'+t+'"').fetchone()[0]
assert all(counts[t]==baseline['legacy_table_counts'][t] for t in counts)
xml=ET.parse(out/'final-tests.xml').getroot()
suites=list(xml.iter('testsuite'))
test={'tests':sum(int(s.get('tests',0)) for s in suites),'failures':sum(int(s.get('failures',0)) for s in suites),
      'errors':sum(int(s.get('errors',0)) for s in suites),'seconds':sum(float(s.get('time',0)) for s in suites)}
assert test['failures']==test['errors']==0
probe=subprocess.run(['ffprobe','-v','error','-show_entries','stream=codec_name,width,height,r_frame_rate',
                       '-show_entries','format=duration,size','-of','json',str(ROOT/'deliverables/rag-acceptance.mp4')],capture_output=True,check=True)
result={'python':test,'original_report_preserved':True,'original_legacy_counts_preserved':True,
        'video':json.loads(probe.stdout),'video_sha256':hashlib.sha256((ROOT/'deliverables/rag-acceptance.mp4').read_bytes()).hexdigest(),
        'external_model_calls':0,'paid_cost':0,'publication':'NOT_PERFORMED','scope':'LOCAL_ISOLATED_COPY_DEMO'}
demo=ROOT/(ROOT/'runtime/rag-demo-path.txt').read_text(encoding='utf-8').strip()
with sqlite3.connect(demo.as_uri()+'?mode=ro',uri=True) as db:
    matches=[(job,json.loads(output)) for job,output in db.execute("select job_id,output from v2_nodes where kind='compose'")
             if json.loads(output).get('sha256')==result['video_sha256']]
    assert matches
    job=matches[-1][0]
    subtitle=json.loads(db.execute("select output from v2_nodes where job_id=? and kind='subtitle'",(job,)).fetchone()[0])
    path=(ROOT/'runtime/media'/subtitle['storage_key']).resolve()
    assert path.is_relative_to((ROOT/'runtime/media').resolve())
    shutil.copy2(path,ROOT/'deliverables/rag-acceptance.srt')
    result['srt_sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
    result['srt_cues']=path.read_text(encoding='utf-8').count('-->')
(out/'delivery-evidence.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(result,indent=2))
