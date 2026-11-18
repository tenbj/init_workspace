"""Isolated initializer acceptance; never runs against the live workspace."""
import importlib.util
import json
from pathlib import Path
import tempfile
import subprocess


def main():
    src=Path(__file__).resolve().parent
    loader=importlib.util.spec_from_file_location('initws',src/'init_workspace.py')
    module=importlib.util.module_from_spec(loader)
    loader.loader.exec_module(module)
    templates=src/'templates'
    spec=json.loads((templates/'system/standards/workspace-spec.json').read_text(encoding='utf-8'))
    with tempfile.TemporaryDirectory(prefix='initws-release-') as tmp:
        workspace=Path(tmp)
        fresh=module.initialize_workspace(workspace,templates,'初始化')
        assert not fresh['errors'],fresh['errors']
        assert all((workspace/d).is_dir() for d in spec['requiredLayer']['directories'])
        assert (workspace/'output/00_系统治理/目录.md').exists()
        assert not (workspace/'output/00_系统治理_v1.0.0').exists()
        assert (workspace/'.system/standards/Git版本控制标准.md').exists()
        assert len(fresh['skills'])==len(spec['skillsManagement']['registeredSkills'])
        assert (workspace/'.agents/skills/B12_环境维护/SKILL.md').is_file()
        assert all((workspace/'.envs'/name).is_file() for name in spec['environmentManagement']['publicFiles'])
        assert not list((workspace/'.envs').glob('*.env'))
        assert (workspace/'.system/standards/环境管理标准.md').is_file()
        subprocess.run(['git', 'init', '-q', str(workspace)], check=True)
        assert subprocess.run(['git', '-C', str(workspace), 'check-ignore', '-q', '.envs/doris.prod.readonly.env']).returncode == 0
        environment_private = workspace/'.envs/doris.prod.readonly.env'
        environment_private.write_text('DORIS_PASSWORD=SYNTHETIC_ENV_PRIVATE_VALUE_20261015', encoding='utf-8')
        private_before = environment_private.read_bytes()
        environment_catalog = workspace/'.envs/catalog.json'
        environment_catalog.write_text('LOCAL_CATALOG_MARKER', encoding='utf-8')
        environment_ignore = workspace/'.envs/.gitignore'
        ignore_before = environment_ignore.read_bytes()
        for name in spec['skillsManagement']['registeredSkills']:
            assert (workspace/'.claude/commands'/f'{name}.md').read_text(encoding='utf-8').strip()==f'请读取并执行 .agents/skills/{name}/SKILL.md'
        markers=[workspace/'.memory/user-marker.md',workspace/'output/user-marker.txt',workspace/'input/user-marker.txt',workspace/'.Claude.json',workspace/'.claude/settings.local.json']
        for p in markers:
            p.write_text('LOCAL_TEST_CONTENT',encoding='utf-8')
        skill=workspace/'.agents/skills/I01_内网穿透'
        (skill/'user-note.txt').write_text('preserve',encoding='utf-8')
        (skill/'.git').mkdir()
        (skill/'.git/local-marker').write_text('git remains',encoding='utf-8')
        try:
            module.initialize_workspace(workspace,templates,'升级')
        except ValueError as error:
            assert 'Git metadata' in str(error)
        else:
            raise AssertionError('Embedded repository must not be replaced')
        assert (skill/'.git/local-marker').read_text(encoding='utf-8')=='git remains'
        assert (skill/'user-note.txt').read_text(encoding='utf-8')=='preserve'
        (skill/'.git/local-marker').unlink()
        (skill/'.git').rmdir()
        upgraded=module.initialize_workspace(workspace,templates,'升级')
        assert not upgraded['errors'],upgraded['errors']
        assert all(p.read_text(encoding='utf-8')=='LOCAL_TEST_CONTENT' for p in markers)
        assert environment_private.read_bytes()==private_before
        assert environment_catalog.read_text(encoding='utf-8')=='LOCAL_CATALOG_MARKER'
        assert environment_ignore.read_bytes()==ignore_before
        assert all(b'SYNTHETIC_ENV_PRIVATE_VALUE_20261015' not in p.read_bytes()
                   for p in (workspace/'.history').rglob('*') if p.is_file())
        backups=list((workspace/'.history/.agents/skills').glob('I01_*'))
        assert any((p/'user-note.txt').exists() for p in backups)
        assert all(not(p/'.git').exists() for p in backups)
        report={'version':module.SKELETON_VERSION,'spec_version':spec['version'],'registered_skills':len(fresh['skills']),'checks':['fresh SSOT skeleton','stable core paths','B08 progress folders','Git standard present','registered Claude commands','B12 skill and environment public files installed','standalone environment Git ignore','upgrade credentials/catalog/ignore preserved without history copies','upgrade private/memory/input/output retained','embedded repository replacement refused','work content backup retained'],'status':'pass'}
        destination=src.parent/'dist'/f'release-verification-{module.SKELETON_VERSION}.json'
        destination.parent.mkdir(exist_ok=True)
        destination.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
