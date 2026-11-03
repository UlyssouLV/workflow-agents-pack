/**
 * Dépôt GitHub courant (owner/repo) : GITHUB_REPOSITORY en CI, sinon le
 * remote de .git/config. Sert aux scripts qui appellent l'API GitHub ou
 * visent le site servi en local (baseUrl `/<repo>/`).
 */
import {execFileSync} from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {fileURLToPath} from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
export const REPO_ROOT = path.resolve(__dirname, '../..');

export function repoSlug() {
  if (process.env.GITHUB_REPOSITORY) return process.env.GITHUB_REPOSITORY;
  try {
    const config = fs.readFileSync(path.join(REPO_ROOT, '.git', 'config'), 'utf8');
    const m = config.match(/^\s*url\s*=\s*.*github\.com[:/](.+?)(?:\.git)?\s*$/im);
    if (m) return m[1].replaceAll('\\', '/');
  } catch {
    /* dépôt sans .git/config lisible */
  }
  return null;
}

/**
 * Propriétaire et nom du dépôt, pour les liens GitHub des pages générées.
 * Dépôt introuvable → `OWNER` / `REPO` (liens visiblement faux, build non bloqué).
 */
export function proprietaireEtDepot() {
  const [owner, repo] = (repoSlug() || '').split('/', 2);
  return {owner: owner || 'OWNER', repo: repo || 'REPO'};
}

/** URL de l'accueil servi par `npm run serve` (port 4173). */
export function urlSiteLocal() {
  const slug = repoSlug();
  const repo = slug ? slug.split('/')[1] : '';
  return `http://127.0.0.1:4173/${repo ? `${repo}/` : ''}`;
}

const GH_CONNUS = [
  path.join(os.homedir(), '.local', 'bin', 'gh'),
  '/opt/homebrew/bin/gh',
  '/usr/local/bin/gh',
  '/usr/bin/gh',
];

/**
 * Jeton GitHub : GITHUB_TOKEN / GH_TOKEN (CI), sinon celui de `gh auth token`
 * en local (dépôt privé : l'API refuse les appels anonymes).
 */
export function jetonGithub() {
  const env = process.env.GITHUB_TOKEN || process.env.GH_TOKEN;
  if (env) return env;
  // Chemins fixes, pas le PATH : un `gh` planté plus tôt dans le PATH ne lit pas le jeton.
  const gh = GH_CONNUS.find((chemin) => fs.existsSync(chemin));
  if (!gh) return null;
  try {
    return execFileSync(gh, ['auth', 'token'], {
      encoding: 'utf8',
      stdio: ['ignore', 'pipe', 'ignore'],
    }).trim() || null;
  } catch {
    return null; /* gh absent ou non connecté */
  }
}
