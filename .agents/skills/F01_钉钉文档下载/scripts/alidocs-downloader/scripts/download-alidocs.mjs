#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawn } from 'node:child_process';
import { Readable } from 'node:stream';
import { pipeline } from 'node:stream/promises';
import zlib from 'node:zlib';
import readline from 'node:readline/promises';
import { stdin as input, stdout as output } from 'node:process';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const projectRoot = path.resolve(__dirname, '..');
const defaultConfigPath = path.join(projectRoot, 'config', 'docs.json');

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

class CdpSession {
  constructor(ws) {
    this.ws = ws;
    this.nextId = 1;
    this.pending = new Map();
    this.waiters = [];
    this.events = [];

    ws.onmessage = (event) => {
      const message = JSON.parse(event.data);
      if (message.id && this.pending.has(message.id)) {
        const pending = this.pending.get(message.id);
        this.pending.delete(message.id);
        if (message.error) pending.reject(new Error(JSON.stringify(message.error)));
        else pending.resolve(message.result);
        return;
      }

      if (message.method) {
        this.events.push(message);
        const remaining = [];
        for (const waiter of this.waiters) {
          if (waiter.method !== message.method || !waiter.predicate(message)) {
            remaining.push(waiter);
            continue;
          }
          clearTimeout(waiter.timer);
          waiter.resolve(message);
        }
        this.waiters = remaining;
      }
    };
  }

  static connect(wsUrl) {
    return new Promise((resolve, reject) => {
      const ws = new WebSocket(wsUrl);
      ws.onopen = () => resolve(new CdpSession(ws));
      ws.onerror = reject;
    });
  }

  send(method, params = {}) {
    const id = this.nextId++;
    this.ws.send(JSON.stringify({ id, method, params }));
    return new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject });
    });
  }

  waitForEvent(method, predicate = () => true, timeoutMs = 30000) {
    const previous = this.events.find((event) => event.method === method && predicate(event));
    if (previous) return Promise.resolve(previous);

    return new Promise((resolve, reject) => {
      const waiter = {
        method,
        predicate,
        resolve,
        timer: setTimeout(() => {
          this.waiters = this.waiters.filter((item) => item !== waiter);
          reject(new Error(`Timed out waiting for ${method}`));
        }, timeoutMs),
      };
      this.waiters.push(waiter);
    });
  }

  close() {
    this.ws.close();
  }
}

function parseArgs(argv) {
  const args = {};
  for (let index = 0; index < argv.length; index += 1) {
    const token = argv[index];
    if (!token.startsWith('--')) continue;
    const key = token.slice(2);
    if (key === 'no-launch' || key === 'help') {
      args[key] = true;
      continue;
    }
    args[key] = argv[index + 1];
    index += 1;
  }
  return args;
}

function usage() {
  console.log(`
Usage:
  node scripts/download-alidocs.mjs --doc 标准库

Options:
  --config <path>   Config file path. Defaults to config/docs.json.
  --doc <name>      Document key in config. Defaults to config.defaultDocument.
  --output <name>   Output file name or absolute path.
  --profile-dir <path> Chrome profile directory. Overrides config.chromeProfileDir.
  --download-dir <path> Directory for relative --output paths. Overrides config.downloadDir.
  --port <number>   Chrome remote debugging port.
  --no-launch       Require an existing Chrome CDP instance.
`);
}

function readJson(filePath) {
  return JSON.parse(fs.readFileSync(filePath, 'utf8'));
}

function resolveFromProject(value) {
  if (!value) return value;
  return path.isAbsolute(value) ? value : path.resolve(projectRoot, value);
}

function chromeCandidates() {
  const candidates = [
    process.env.CHROME_PATH,
    'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
    'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe',
    path.join(process.env.LOCALAPPDATA || '', 'Google\\Chrome\\Application\\chrome.exe'),
    'C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe',
    'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
  ].filter(Boolean);

  return candidates.filter((candidate) => fs.existsSync(candidate));
}

async function getJson(url, timeoutMs = 5000) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(url, { signal: controller.signal });
    if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
    return await response.json();
  } finally {
    clearTimeout(timer);
  }
}

async function waitForChrome(port, timeoutMs = 20000) {
  const startedAt = Date.now();
  let lastError;
  while (Date.now() - startedAt < timeoutMs) {
    try {
      return await getJson(`http://127.0.0.1:${port}/json/version`, 2000);
    } catch (error) {
      lastError = error;
      await sleep(500);
    }
  }
  throw new Error(`Chrome CDP did not become ready on port ${port}: ${lastError?.message || 'unknown error'}`);
}

async function ensureChrome({ port, profileDir, initialUrl, noLaunch }) {
  try {
    return await getJson(`http://127.0.0.1:${port}/json/version`, 1500);
  } catch {
    if (noLaunch) {
      throw new Error(`No Chrome CDP instance found on port ${port}. Remove --no-launch or start Chrome first.`);
    }
  }

  const chromeExe = chromeCandidates()[0];
  if (!chromeExe) throw new Error('Chrome or Edge executable was not found.');

  fs.mkdirSync(profileDir, { recursive: true });
  const chromeArgs = [
    `--remote-debugging-port=${port}`,
    `--user-data-dir=${profileDir}`,
    '--no-first-run',
    '--disable-features=Translate',
    '--new-window',
    initialUrl,
  ];

  const child = spawn(chromeExe, chromeArgs, { detached: true, stdio: 'ignore' });
  child.unref();
  console.log(`Started Chrome with profile: ${profileDir}`);
  return waitForChrome(port);
}

async function listTargets(port) {
  return getJson(`http://127.0.0.1:${port}/json/list`, 5000);
}

async function getOrCreatePage(browser, port, url) {
  const targets = await listTargets(port);
  const existing = targets.find((target) => target.type === 'page' && target.url.includes('alidocs.dingtalk.com'));
  if (existing) return existing;

  const { targetId } = await browser.send('Target.createTarget', { url });
  for (let attempt = 0; attempt < 30; attempt += 1) {
    const updated = await listTargets(port);
    const target = updated.find((item) => item.id === targetId);
    if (target) return target;
    await sleep(300);
  }
  throw new Error('Created Chrome target, but could not resolve its page WebSocket URL.');
}

async function evaluate(page, expression) {
  const result = await page.send('Runtime.evaluate', {
    expression,
    returnByValue: true,
    awaitPromise: true,
  });
  if (result.exceptionDetails) {
    throw new Error(result.exceptionDetails.text || 'Runtime.evaluate failed');
  }
  return result.result.value;
}

async function pageSnapshot(page) {
  return evaluate(page, `(() => ({
    title: document.title,
    url: location.href,
    text: document.body ? document.body.innerText.slice(0, 5000) : ''
  }))()`);
}

async function waitForDocumentReady(page, docName, timeoutMs) {
  const startedAt = Date.now();
  while (Date.now() - startedAt < timeoutMs) {
    const snapshot = await pageSnapshot(page);
    if (snapshot.text.includes('菜单') && (snapshot.text.includes(docName) || snapshot.title.includes(docName))) {
      return snapshot;
    }
    await sleep(1000);
  }
  return null;
}

async function promptForLoginIfPossible() {
  if (!process.stdin.isTTY) return;
  const rl = readline.createInterface({ input, output });
  await rl.question('If the page needs login, complete it in Chrome, then press Enter here to continue...');
  rl.close();
}

async function elementBox(page, needle, constraints = {}) {
  const expression = `(() => {
    const needle = ${JSON.stringify(needle)};
    const constraints = ${JSON.stringify(constraints)};
    const normalize = (value) => String(value || '').replace(/\\s+/g, ' ').trim();
    const interactiveSelector = [
      'button',
      'a',
      '[role="button"]',
      '.wd3-toolbar-item',
      '.wd3-listitem',
      '.wd3-button',
      '.wd3-icon-button'
    ].join(',');
    const clickableAncestor = (element) => {
      let current = element;
      for (let depth = 0; current && depth < 6; depth += 1) {
        if (current.matches && current.matches(interactiveSelector)) return current;
        current = current.parentElement;
      }
      return element;
    };
    const visible = (element, rect, style) =>
      rect.width > 0 && rect.height > 0 &&
      style.display !== 'none' && style.visibility !== 'hidden' &&
      rect.x >= (constraints.minX ?? -Infinity) &&
      rect.y >= (constraints.minY ?? -Infinity) &&
      rect.x <= (constraints.maxX ?? Infinity) &&
      rect.y <= (constraints.maxY ?? Infinity);

    const candidates = [];
    for (const element of document.querySelectorAll('*')) {
      const text = normalize(element.innerText || element.textContent);
      const aria = normalize(element.getAttribute('aria-label'));
      const title = normalize(element.getAttribute('title'));
      const haystack = text || aria || title;
      if (!haystack) continue;

      const exact = haystack === needle;
      const starts = haystack.startsWith(needle);
      const includes = haystack.includes(needle);
      if (!exact && !starts && !includes) continue;

      const target = clickableAncestor(element);
      const rect = target.getBoundingClientRect();
      const style = getComputedStyle(target);
      if (!visible(element, rect, style)) continue;

      const lengthScore = haystack.length;
      const matchScore = exact ? 0 : starts ? 10 : 20;
      const areaScore = rect.width * rect.height / 10000;
      candidates.push({
        text: haystack.slice(0, 120),
        x: rect.x,
        y: rect.y,
        w: rect.width,
        h: rect.height,
        cx: rect.x + rect.width / 2,
        cy: rect.y + rect.height / 2,
        score: matchScore + lengthScore / 100 + areaScore,
      });
    }
    candidates.sort((a, b) => a.score - b.score);
    return candidates[0] || null;
  })()`;

  const box = await evaluate(page, expression);
  if (!box) {
    throw new Error(`Could not find visible element containing "${needle}".`);
  }
  return box;
}

async function moveMouse(page, x, y) {
  await page.send('Input.dispatchMouseEvent', { type: 'mouseMoved', x, y, button: 'none' });
}

async function dispatchDomMouse(page, box, action) {
  const events = action === 'hover'
    ? ['pointerover', 'mouseover', 'pointerenter', 'mouseenter', 'mousemove']
    : ['pointerover', 'mouseover', 'mousemove', 'pointerdown', 'mousedown', 'pointerup', 'mouseup', 'click'];

  const expression = `(() => {
    const x = ${JSON.stringify(box.cx)};
    const y = ${JSON.stringify(box.cy)};
    const events = ${JSON.stringify(events)};
    const target = document.elementFromPoint(x, y);
    if (!target) return null;

    const eventInit = (type) => ({
      bubbles: !['mouseenter', 'pointerenter'].includes(type),
      cancelable: true,
      composed: true,
      view: window,
      clientX: x,
      clientY: y,
      screenX: x,
      screenY: y,
      button: 0,
      buttons: ['pointerdown', 'mousedown'].includes(type) ? 1 : 0,
      pointerId: 1,
      pointerType: 'mouse',
      isPrimary: true
    });

    const targets = [];
    let current = target;
    for (let depth = 0; current && depth < 6; depth += 1) {
      targets.push(current);
      current = current.parentElement;
    }

    for (const eventTarget of targets) {
      for (const type of events) {
        const Ctor = type.startsWith('pointer') && window.PointerEvent ? window.PointerEvent : window.MouseEvent;
        eventTarget.dispatchEvent(new Ctor(type, eventInit(type)));
      }
    }

    const rect = target.getBoundingClientRect();
    return {
      tag: target.tagName,
      text: String(target.innerText || target.textContent || '').replace(/\\s+/g, ' ').trim().slice(0, 120),
      x: rect.x,
      y: rect.y,
      w: rect.width,
      h: rect.height
    };
  })()`;

  return evaluate(page, expression);
}

async function dispatchTextMouse(page, needle, constraints = {}, action = 'click') {
  const events = action === 'hover'
    ? ['pointerover', 'mouseover', 'pointerenter', 'mouseenter', 'mousemove']
    : ['pointerover', 'mouseover', 'mousemove', 'pointerdown', 'mousedown', 'pointerup', 'mouseup', 'click'];

  const expression = `(() => {
    const needle = ${JSON.stringify(needle)};
    const constraints = ${JSON.stringify(constraints)};
    const events = ${JSON.stringify(events)};
    const normalize = (value) => String(value || '').replace(/\\s+/g, ' ').trim();
    const interactiveSelector = [
      'button',
      'a',
      '[role="button"]',
      '.wd3-toolbar-item',
      '.wd3-listitem',
      '.wd3-button',
      '.wd3-icon-button'
    ].join(',');
    const clickableAncestor = (element) => {
      let current = element;
      for (let depth = 0; current && depth < 6; depth += 1) {
        if (current.matches && current.matches(interactiveSelector)) return current;
        current = current.parentElement;
      }
      return element;
    };
    const visible = (rect, style) =>
      rect.width > 0 && rect.height > 0 &&
      style.display !== 'none' && style.visibility !== 'hidden' &&
      rect.x >= (constraints.minX ?? -Infinity) &&
      rect.y >= (constraints.minY ?? -Infinity) &&
      rect.x <= (constraints.maxX ?? Infinity) &&
      rect.y <= (constraints.maxY ?? Infinity);

    const candidates = [];
    for (const element of document.querySelectorAll('*')) {
      const text = normalize(element.innerText || element.textContent);
      const aria = normalize(element.getAttribute('aria-label'));
      const title = normalize(element.getAttribute('title'));
      const haystack = text || aria || title;
      if (!haystack) continue;

      const exact = haystack === needle;
      const starts = haystack.startsWith(needle);
      const includes = haystack.includes(needle);
      if (!exact && !starts && !includes) continue;

      const target = clickableAncestor(element);
      const rect = target.getBoundingClientRect();
      const style = getComputedStyle(target);
      if (!visible(rect, style)) continue;

      const lengthScore = haystack.length;
      const matchScore = exact ? 0 : starts ? 10 : 20;
      const areaScore = rect.width * rect.height / 10000;
      candidates.push({
        target,
        text: haystack.slice(0, 120),
        x: rect.x,
        y: rect.y,
        w: rect.width,
        h: rect.height,
        cx: rect.x + rect.width / 2,
        cy: rect.y + rect.height / 2,
        score: matchScore + lengthScore / 100 + areaScore
      });
    }

    candidates.sort((a, b) => a.score - b.score);
    const chosen = candidates[0];
    if (!chosen) return null;

    const eventInit = (type) => ({
      bubbles: !['mouseenter', 'pointerenter'].includes(type),
      cancelable: true,
      composed: true,
      view: window,
      clientX: chosen.cx,
      clientY: chosen.cy,
      screenX: chosen.cx,
      screenY: chosen.cy,
      button: 0,
      buttons: ['pointerdown', 'mousedown'].includes(type) ? 1 : 0,
      pointerId: 1,
      pointerType: 'mouse',
      isPrimary: true
    });

    const pointTarget = (
      chosen.cx >= 0 && chosen.cy >= 0 &&
      chosen.cx <= window.innerWidth && chosen.cy <= window.innerHeight
    ) ? document.elementFromPoint(chosen.cx, chosen.cy) : null;
    const dispatchRoot = pointTarget || chosen.target;

    const targets = [dispatchRoot];
    if (${JSON.stringify(action)} === 'hover') {
      let current = dispatchRoot.parentElement;
      for (let depth = 0; current && depth < 5; depth += 1) {
        targets.push(current);
        current = current.parentElement;
      }
    }

    for (const eventTarget of targets) {
      for (const type of events) {
        const Ctor = type.startsWith('pointer') && window.PointerEvent ? window.PointerEvent : window.MouseEvent;
        eventTarget.dispatchEvent(new Ctor(type, eventInit(type)));
      }
    }

    return {
      text: chosen.text,
      x: chosen.x,
      y: chosen.y,
      w: chosen.w,
      h: chosen.h,
      cx: chosen.cx,
      cy: chosen.cy
    };
  })()`;

  const box = await evaluate(page, expression);
  if (!box) {
    throw new Error(`Could not find element containing "${needle}".`);
  }
  if (box.cx >= 0 && box.cy >= 0) {
    await moveMouse(page, box.cx, box.cy).catch(() => null);
  }
  return box;
}

async function hoverText(page, text, constraints) {
  return dispatchTextMouse(page, text, constraints, 'hover');
}

async function clickText(page, text, constraints) {
  return dispatchTextMouse(page, text, constraints, 'click');
}

async function hasElement(page, text, constraints) {
  try {
    await elementBox(page, text, constraints);
    return true;
  } catch {
    return false;
  }
}

async function pressEscape(page) {
  await page.send('Input.dispatchKeyEvent', { type: 'keyDown', key: 'Escape', code: 'Escape', windowsVirtualKeyCode: 27 });
  await page.send('Input.dispatchKeyEvent', { type: 'keyUp', key: 'Escape', code: 'Escape', windowsVirtualKeyCode: 27 });
}

async function triggerExcelDownload(page) {
  const topMenuConstraints = { minX: 0, maxX: 250, minY: 100, maxY: 190 };
  let menuOpen = await hasElement(page, '表格', topMenuConstraints);
  if (!menuOpen) {
    const menuBox = await clickText(page, '菜单', { minX: 0, maxX: 130, minY: 45, maxY: 130 });
    console.log(`Clicked menu at (${Math.round(menuBox.cx)}, ${Math.round(menuBox.cy)})`);
    await sleep(700);
    menuOpen = await hasElement(page, '表格', topMenuConstraints);
  }
  if (!menuOpen) {
    const menuBox = await clickText(page, '菜单', { minX: 0, maxX: 130, minY: 45, maxY: 130 });
    console.log(`Clicked menu retry at (${Math.round(menuBox.cx)}, ${Math.round(menuBox.cy)})`);
    await sleep(700);
  }
  const tableBox = await hoverText(page, '表格', { minX: 0, maxX: 250, minY: 100, maxY: 190 });
  console.log(`Hovered table menu at (${Math.round(tableBox.cx)}, ${Math.round(tableBox.cy)})`);
  await sleep(500);
  const downloadAsBox = await hoverText(page, '下载为');
  console.log(`Hovered download-as at (${Math.round(downloadAsBox.cx)}, ${Math.round(downloadAsBox.cy)})`);
  await sleep(500);
  const excelBox = await clickText(page, 'Excel');
  console.log(`Clicked Excel export at (${Math.round(excelBox.cx)}, ${Math.round(excelBox.cy)})`);
}

async function downloadFile(url, outputPath) {
  fs.mkdirSync(path.dirname(outputPath), { recursive: true });
  const tempPath = `${outputPath}.part`;
  fs.rmSync(tempPath, { force: true });

  const response = await fetch(url);
  if (!response.ok || !response.body) {
    throw new Error(`Download failed: ${response.status} ${response.statusText}`);
  }

  await pipeline(Readable.fromWeb(response.body), fs.createWriteStream(tempPath));
  fs.rmSync(outputPath, { force: true });
  fs.renameSync(tempPath, outputPath);
}

function xmlDecode(value) {
  return String(value)
    .replace(/&quot;/g, '"')
    .replace(/&apos;/g, "'")
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&amp;/g, '&');
}

function columnNumber(columnLetters) {
  let value = 0;
  for (const letter of columnLetters) {
    value = value * 26 + letter.charCodeAt(0) - 64;
  }
  return value;
}

function readZipEntries(zipPath) {
  const buffer = fs.readFileSync(zipPath);
  if (buffer.readUInt32LE(0) !== 0x04034b50) {
    throw new Error('File is not a valid zip/xlsx container.');
  }

  let eocdOffset = -1;
  for (let offset = buffer.length - 22; offset >= Math.max(0, buffer.length - 65557); offset -= 1) {
    if (buffer.readUInt32LE(offset) === 0x06054b50) {
      eocdOffset = offset;
      break;
    }
  }
  if (eocdOffset < 0) throw new Error('Zip end-of-central-directory was not found.');

  const entryCount = buffer.readUInt16LE(eocdOffset + 10);
  const centralOffset = buffer.readUInt32LE(eocdOffset + 16);
  const entries = new Map();
  let cursor = centralOffset;

  for (let index = 0; index < entryCount; index += 1) {
    if (buffer.readUInt32LE(cursor) !== 0x02014b50) {
      throw new Error('Invalid zip central directory.');
    }
    const method = buffer.readUInt16LE(cursor + 10);
    const compressedSize = buffer.readUInt32LE(cursor + 20);
    const fileNameLength = buffer.readUInt16LE(cursor + 28);
    const extraLength = buffer.readUInt16LE(cursor + 30);
    const commentLength = buffer.readUInt16LE(cursor + 32);
    const localHeaderOffset = buffer.readUInt32LE(cursor + 42);
    const fileName = buffer.toString('utf8', cursor + 46, cursor + 46 + fileNameLength);

    const localNameLength = buffer.readUInt16LE(localHeaderOffset + 26);
    const localExtraLength = buffer.readUInt16LE(localHeaderOffset + 28);
    const dataStart = localHeaderOffset + 30 + localNameLength + localExtraLength;
    const compressed = buffer.subarray(dataStart, dataStart + compressedSize);
    let data;
    if (method === 0) data = compressed;
    else if (method === 8) data = zlib.inflateRawSync(compressed);
    else throw new Error(`Unsupported zip compression method ${method} for ${fileName}.`);

    entries.set(fileName, data);
    cursor += 46 + fileNameLength + extraLength + commentLength;
  }

  return entries;
}

function validateXlsx(xlsxPath, expectedSheets = []) {
  const entries = readZipEntries(xlsxPath);
  const workbook = entries.get('xl/workbook.xml')?.toString('utf8');
  if (!workbook) throw new Error('xl/workbook.xml was not found.');

  const sheetMatches = [...workbook.matchAll(/<sheet\b[^>]*\bname="([^"]+)"[^>]*\br:id="([^"]+)"/g)];
  const rels = entries.get('xl/_rels/workbook.xml.rels')?.toString('utf8') || '';
  const relMap = new Map([...rels.matchAll(/<Relationship\b[^>]*\bId="([^"]+)"[^>]*\bTarget="([^"]+)"/g)].map((match) => [match[1], match[2]]));

  const sheets = sheetMatches.map((match) => {
    const name = xmlDecode(match[1]);
    const target = relMap.get(match[2]);
    const normalizedTarget = target?.startsWith('xl/') ? target : `xl/${target || ''}`;
    const xml = entries.get(normalizedTarget)?.toString('utf8') || '';
    const rowNumbers = [...xml.matchAll(/<row\b[^>]*\br="(\d+)"/g)].map((row) => Number(row[1]));
    const cellRefs = [...xml.matchAll(/<c\b[^>]*\br="([A-Z]+)(\d+)"/g)];
    const maxRow = Math.max(0, ...rowNumbers, ...cellRefs.map((cell) => Number(cell[2])));
    const maxCol = Math.max(0, ...cellRefs.map((cell) => columnNumber(cell[1])));
    return { name, rows: maxRow, cols: maxCol };
  });

  for (const expected of expectedSheets) {
    const sheet = sheets.find((item) => item.name === expected.name);
    if (!sheet) throw new Error(`Expected sheet was not found: ${expected.name}`);
    if (expected.minRows && sheet.rows < expected.minRows) {
      throw new Error(`Sheet ${expected.name} has ${sheet.rows} rows, expected at least ${expected.minRows}.`);
    }
    if (expected.minCols && sheet.cols < expected.minCols) {
      throw new Error(`Sheet ${expected.name} has ${sheet.cols} cols, expected at least ${expected.minCols}.`);
    }
  }

  return sheets;
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  if (args.help) {
    usage();
    return;
  }

  const configPath = path.resolve(args.config || defaultConfigPath);
  const config = readJson(configPath);
  const docName = args.doc || config.defaultDocument || Object.keys(config.documents || {})[0];
  const doc = config.documents?.[docName];
  if (!doc) throw new Error(`Document "${docName}" was not found in ${configPath}.`);

  const port = Number(args.port || config.chromeDebugPort || 9222);
  const profileDir = resolveFromProject(args['profile-dir'] || config.chromeProfileDir || '../.tmp/alidocs-chrome-profile');
  const downloadDir = resolveFromProject(args['download-dir'] || config.downloadDir || '../outputs');
  const outputPath = args.output
    ? (path.isAbsolute(args.output) ? args.output : path.resolve(downloadDir, args.output))
    : path.resolve(downloadDir, doc.outputFile || `${docName}.xlsx`);

  console.log(`Document: ${docName}`);
  console.log(`Output: ${outputPath}`);

  const version = await ensureChrome({
    port,
    profileDir,
    initialUrl: doc.url,
    noLaunch: Boolean(args['no-launch']),
  });
  const browser = await CdpSession.connect(version.webSocketDebuggerUrl);

  try {
    await browser.send('Browser.setDownloadBehavior', {
      behavior: 'allow',
      downloadPath: downloadDir,
      eventsEnabled: true,
    });

    const target = await getOrCreatePage(browser, port, doc.url);
    const page = await CdpSession.connect(target.webSocketDebuggerUrl);

    try {
      await page.send('Runtime.enable');
      await page.send('Page.enable');
      await page.send('Page.navigate', { url: doc.url });
      await sleep(2000);

      let ready = await waitForDocumentReady(page, docName, 30000);
      if (!ready) {
        console.log('The document is not ready yet. Login may be required in the Chrome window.');
        await promptForLoginIfPossible();
        ready = await waitForDocumentReady(page, docName, 120000);
      }
      if (!ready) throw new Error('Timed out waiting for the Alidocs spreadsheet page.');

      console.log(`Page ready: ${ready.title}`);

      const willBeginPromise = browser.waitForEvent(
        'Browser.downloadWillBegin',
        (event) => event.params?.url?.includes('/export/tempres/'),
        90000,
      );

      await triggerExcelDownload(page);
      const willBegin = await willBeginPromise;
      console.log(`Export generated: ${willBegin.params.suggestedFilename}`);

      await browser.waitForEvent(
        'Browser.downloadProgress',
        (event) => event.params?.guid === willBegin.params.guid && ['completed', 'canceled'].includes(event.params?.state),
        30000,
      ).catch(() => null);

      await downloadFile(willBegin.params.url, outputPath);
      const stats = fs.statSync(outputPath);
      const sheets = validateXlsx(outputPath, doc.expectedSheets || []);

      console.log(`Saved: ${outputPath}`);
      console.log(`Bytes: ${stats.size}`);
      console.log('Sheets:');
      for (const sheet of sheets) {
        console.log(`- ${sheet.name}: ${sheet.rows} rows x ${sheet.cols} cols`);
      }
    } finally {
      page.close();
    }
  } finally {
    browser.close();
  }
}

main().catch((error) => {
  console.error(`ERROR: ${error.message}`);
  process.exit(1);
});
