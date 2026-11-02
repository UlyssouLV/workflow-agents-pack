/**
 * Régénère les aperçus README sur la branche de version (finaliser-la-version,
 * après la Release) — jamais par un commit bot sur main.
 *
 * 1. sync Mermaid architecture → README (si docs/architecture/vue-systeme.md
 *    et les marqueurs README existent)
 * 2. capture #travail-realise du suivi HTML (si docs/suivi-avancement/ existe)
 * 3. build + serve docs-site → aperçus accueil et bugs
 *
 * Opt-in : rien ne se passe tant que le README n'affiche pas un aperçu
 * (`docs/img/apercu-…png`) ni les marqueurs d'architecture.
 * Soft-skip (exit 0) si Playwright / build / serve manquent : un message
 * `[apercus-readme] soft-skip : …` ; le reste du commit docs continue.
 *
 * Usage : node docs-site/scripts/capturer-apercus-readme.mjs
 *     ou : npm run capturer-apercus-readme  (depuis docs-site/)
 */
import {spawn} from 'node:child_process';
import fs from 'node:fs';
import {createRequire} from 'node:module';
import path from 'node:path';
import {fileURLToPath} from 'node:url';

import {REPO_ROOT, urlSiteLocal} from './depot.mjs';

const require = createRequire(import.meta.url);
const __dirname = path.dirname(fileURLToPath(import.meta.url));
const DOCS_SITE = path.resolve(__dirname, '..');
const BASE = urlSiteLocal();
const README = path.join(REPO_ROOT, 'README.md');

function runNode(scriptRel, args = []) {
  return new Promise((resolve, reject) => {
    const child = spawn(
      process.execPath,
      [path.join(DOCS_SITE, 'scripts', scriptRel), ...args],
      {cwd: DOCS_SITE, env: process.env, stdio: 'inherit'},
    );
    child.on('error', reject);
    child.on('exit', (code) => {
      if (code === 0) resolve();
      else reject(new Error(`${scriptRel} exit ${code}`));
    });
  });
}

function softSkip(raison) {
  console.warn(`[apercus-readme] soft-skip : ${raison}`);
  process.exit(0);
}

async function waitReady(url, tries = 90) {
  for (let i = 0; i < tries; i++) {
    try {
      const res = await fetch(url);
      if (res.ok) return;
    } catch {
      /* pas encore prêt */
    }
    await new Promise((r) => setTimeout(r, 1000));
  }
  throw new Error(`serveur docs inaccessible : ${url}`);
}

function npmRunBuild() {
  return new Promise((resolve, reject) => {
    const child = spawn(
      process.platform === 'win32' ? 'npm.cmd' : 'npm',
      ['run', 'build'],
      {
        cwd: DOCS_SITE,
        env: process.env,
        stdio: 'inherit',
        shell: process.platform === 'win32',
      },
    );
    child.on('error', reject);
    child.on('exit', (code) => {
      if (code === 0) resolve();
      else reject(new Error(`npm run build exit ${code}`));
    });
  });
}

async function main() {
  const readme = fs.existsSync(README) ? fs.readFileSync(README, 'utf8') : '';
  const veut = (nom) => readme.includes(`docs/img/apercu-${nom}.png`);
  if (!/docs\/img\/apercu-/.test(readme) && !readme.includes('<!-- sync:vue-systeme-mermaid -->')) {
    softSkip('le README n’affiche aucun aperçu (opt-in)');
  }

  try {
    await runNode('sync-architecture-readme.mjs');
  } catch (err) {
    softSkip(err.message || String(err));
  }

  try {
    require.resolve('playwright');
  } catch {
    softSkip('playwright introuvable : `npm install` puis `npx playwright install chromium` dans docs-site/');
  }

  if (veut('travail-realise') && fs.existsSync(path.join(REPO_ROOT, 'docs/suivi-avancement'))) {
    try {
      await runNode('capturer-travail-realise.mjs');
    } catch (err) {
      softSkip(err.message || String(err));
    }
  }

  if (!veut('docs-accueil') && !veut('docs-bugs')) {
    console.log('[apercus-readme] aperçus README à jour');
    return;
  }

  console.log('[apercus-readme] build docs-site…');
  try {
    await npmRunBuild();
  } catch (err) {
    softSkip(err.message || String(err));
  }

  const buildDir = path.join(DOCS_SITE, 'build');
  if (!fs.existsSync(buildDir)) {
    softSkip('docs-site/build absent après build');
  }

  const serve = spawn(
    process.execPath,
    [
      path.join(DOCS_SITE, 'node_modules/@docusaurus/core/bin/docusaurus.mjs'),
      'serve',
      '--host',
      '127.0.0.1',
      '--port',
      '4173',
      '--no-open',
    ],
    {cwd: DOCS_SITE, stdio: 'ignore', env: process.env},
  );

  try {
    await waitReady(BASE);
    if (veut('docs-accueil')) await runNode('capturer-accueil.mjs', [BASE]);
    if (veut('docs-bugs')) await runNode('capturer-bugs.mjs', [BASE]);
  } catch (err) {
    softSkip(err.message || String(err));
  } finally {
    serve.kill('SIGTERM');
  }

  console.log('[apercus-readme] aperçus README à jour');
}

main().catch((err) => {
  console.error('[apercus-readme]', err);
  process.exit(1);
});
