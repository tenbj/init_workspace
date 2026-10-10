import { spawnSync } from 'node:child_process';
import { existsSync } from 'node:fs';
import { dirname, resolve, relative, isAbsolute, extname, sep } from 'node:path';
import { fileURLToPath } from 'node:url';

// Keep the upstream CLI unchanged; scope this convenience entry to workspace output.
const scriptDir = dirname(fileURLToPath(import.meta.url));
const workspace = resolve(scriptDir, '../../../..');
const [draft, output, ...extra] = process.argv.slice(2);
function fail(message) {
  console.error(message);
  process.exit(2);
}
if (!draft || !output || extra.length) fail('用法：node render.mjs <草稿.md> <output子项目中的页面.html>');
if (Number(process.versions.node.split('.')[0]) < 20) fail('需要 Node.js 20 或更高版本。');
const inputPath = resolve(draft);
const outputPath = resolve(output);
const outputRelative = relative(resolve(workspace, 'output'), outputPath);
if (!outputRelative || outputRelative === '..' || outputRelative.startsWith(`..${sep}`) || isAbsolute(outputRelative)) {
  fail('HTML 必须写入本工作区 output 子项目。');
}
if (outputRelative.split(sep).length < 3 || !/\.html?$/i.test(extname(outputPath))) fail('请指定 output/<子项目>/<分类目录>/<页面>.html。');
if (!existsSync(inputPath)) fail(`草稿不存在：${inputPath}`);
const result = spawnSync(process.execPath, [resolve(scriptDir, 'am.mjs'), 'render', inputPath, '-o', outputPath, '--no-open'], {
  cwd: process.cwd(),
  stdio: 'inherit',
  windowsHide: true,
  env: { ...process.env, AM_HOME: resolve(workspace, '.temp/answer-me-with-html-runtime'), AM_NO_UPDATE_CHECK: '1', AM_NO_OPEN: '1' },
});
if (result.error) fail(result.error.message);
process.exit(result.status ?? 1);
