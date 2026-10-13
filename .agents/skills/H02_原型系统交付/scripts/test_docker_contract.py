"""Docker证据负向回归：合成文件验证拒绝条件，不冒充运行验收。"""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from docker_contract import STAGES, draft_docker, snapshot, validate_docker


class DockerContractTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name).resolve()
        for name in ['compose.yaml','Dockerfile','.dockerignore','docs/Docker部署.md','src/app.py','requirements.txt','docs/architecture.html','docs/erd.html']:
            p=self.root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('synthetic fixture',encoding='utf-8')
        self.d=draft_docker()
        self.d.update(inputs=['src','docs','requirements.txt','compose.yaml','Dockerfile','.dockerignore'],services=['app'])
        self.contract={'delivery_id':'current-delivery','docker':self.d,'diagrams':{k:{'path':'docs/'+k+'.html'} for k in ['architecture','erd']},
                       'checks':[{'name':'docker','status':'passed','evidence':self.d['evidence']}]}
        self.report=dict(passed=True,environment='isolated',delivery_id='current-delivery',run_id='fresh-run',
                         started_at='2026-10-12T10:00:00+00:00',finished_at='2026-10-12T10:05:00+00:00',
                         compose_project='h02test-synthetic',mcp_mode='embedded',inputs=snapshot(self.root,self.d['inputs']),
                         images=[{'service':'app','id':'sha256:'+'a'*64}],
                         checks=[dict(name=n,status='passed',observations={'synthetic':True}) for n in STAGES])

    def errors(self):
        p=self.root/self.d['evidence'];p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(self.report),encoding='utf-8')
        result=[];validate_docker(self.root,self.contract,result);return result

    def test_complete(self):self.assertFalse(self.errors())

    def test_missing_contract_fails(self):
        del self.contract['docker'];self.assertTrue(self.errors())

    def test_missing_deployment_files_fail(self):
        for name in ['compose.yaml','Dockerfile','.dockerignore','docs/Docker部署.md']:
            with self.subTest(name=name):
                p=self.root/name;before=p.read_bytes();p.unlink();self.assertTrue(self.errors());p.write_bytes(before)

    def test_changed_source_dependency_config_and_diagram_fail(self):
        for name in ['src/app.py','requirements.txt','compose.yaml','Dockerfile','docs/erd.html']:
            with self.subTest(name=name):
                p=self.root/name;before=p.read_bytes();p.write_bytes(before+b' changed');self.assertTrue(self.errors());p.write_bytes(before)

    def test_old_or_failed_evidence_fails(self):
        baseline=copy.deepcopy(self.report)
        for field,value in [('passed',False),('delivery_id','old'),('environment','production'),('run_id',''),('mcp_mode','separate'),('inputs',[])]:
            with self.subTest(field=field):
                self.report=copy.deepcopy(baseline);self.report[field]=value;self.assertTrue(self.errors())

    def test_every_required_stage_must_have_success_and_observations(self):
        for row in self.report['checks']:
            with self.subTest(name=row['name']):
                row['status']='failed';self.assertTrue(self.errors());row['status']='passed'
                row['observations']={};self.assertTrue(self.errors());row['observations']={'synthetic':True}

    def test_running_only_is_insufficient(self):
        self.report['checks']=[dict(name='startup',status='passed',observations={'running':True})];self.assertTrue(self.errors())

    def test_image_coverage_and_real_id_required(self):
        for value in [[],[{'service':'app','id':'latest'}],[{'service':'other','id':'sha256:'+'a'*64}]]:
            self.report['images']=value;self.assertTrue(self.errors())

    def test_no_escape_or_secret_input(self):
        for value in ['../outside','/outside',r'C:\secret','.env','.env.production','.env.local']:
            if value.startswith('.env'):(self.root/value).write_text('fixture-secret')
            self.d['inputs']=[value];self.assertTrue(self.errors())

    def test_diagrams_must_be_in_inputs(self):
        self.d['inputs']=['src','compose.yaml','Dockerfile','.dockerignore','requirements.txt','docs/Docker部署.md']
        self.report['inputs']=snapshot(self.root,self.d['inputs']);self.assertTrue(self.errors())

    def test_exclusion_requires_explicit_user_scope(self):
        self.contract['docker']={'required':False};self.assertTrue(self.errors())
        self.contract['docker']['exclusion']={'basis':'environment_failure','instruction':'Docker不可用','reason':'缺环境'};self.assertTrue(self.errors())
        self.contract['docker']['exclusion']={'basis':'user_instruction','instruction':'本次只交原型，不做Docker','reason':'明确范围'};self.assertFalse(self.errors())

    def test_stateful_cannot_skip_persistence(self):
        row=next(r for r in self.report['checks'] if r['name']=='backup_restore')
        row.update(status='not_applicable',reason='想跳过');self.assertTrue(self.errors())
        self.d['stateful']=False;self.assertFalse(self.errors())

    def test_invalid_time_and_duplicate_stages_fail(self):
        self.report['finished_at']='2026-10-11T10:05:00+00:00';self.assertTrue(self.errors())
        self.report['finished_at']='2026-10-12T10:05:00+00:00';self.report['checks'].append(copy.deepcopy(self.report['checks'][0]));self.assertTrue(self.errors())

    def test_default_contract_requires_real_docker(self):
        self.assertTrue(draft_docker()['required']);self.assertEqual(draft_docker()['inputs'],[])

    def test_additional_variant_requires_own_passing_report(self):
        variant=copy.deepcopy(self.d);variant['evidence']='verification/docker-external.json'
        self.d['variants']=[variant]
        self.assertTrue(self.errors())
        (self.root/variant['evidence']).write_text(json.dumps(self.report),encoding='utf-8')
        self.assertFalse(self.errors())
        failed=copy.deepcopy(self.report);failed['passed']=False
        (self.root/variant['evidence']).write_text(json.dumps(failed),encoding='utf-8')
        self.assertTrue(self.errors())

    def test_additional_variant_cannot_reuse_or_exclude(self):
        self.d['variants']=[copy.deepcopy(self.d)];self.assertTrue(self.errors())
        self.d['variants']=[{'required':False}];self.assertTrue(self.errors())
        self.d['variants']=[{'required':True,'evidence':[]}];self.assertTrue(self.errors())


if __name__=='__main__':unittest.main()
