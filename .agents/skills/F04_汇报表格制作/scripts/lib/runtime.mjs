import fs from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import {createRequire} from 'node:module';
import {pathToFileURL} from 'node:url';
export async function loadRuntime(root,workDir){
 root=path.resolve(root??process.env.F04_RUNTIME_ROOT??process.env.R01_RUNTIME_ROOT??path.join(os.homedir(),'.cache/codex-runtimes/codex-primary-runtime/dependencies'));
 const nodeModules=path.join(root,'node','node_modules');
 const python=path.join(root,'python',process.platform==='win32'?'python.exe':'bin/python');
 await fs.access(nodeModules);await fs.access(python);
 const adapter=path.join(workDir,'.runtime');await fs.mkdir(adapter,{recursive:true});
 const link=path.join(adapter,'node_modules');
 try{await fs.symlink(nodeModules,link,process.platform==='win32'?'junction':'dir');}catch(e){if(e.code!=='EEXIST')throw e;if(await fs.realpath(link)!==await fs.realpath(nodeModules))throw Error('Existing runtime link points to a different dependency directory');}
 const require=createRequire(path.join(adapter,'loader.cjs'));
 const artifact=await import(pathToFileURL(require.resolve('@oai/artifact-tool')).href);
 return {artifact,python,root};
}
