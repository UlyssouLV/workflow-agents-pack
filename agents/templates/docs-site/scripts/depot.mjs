/**
 * Dépôt GitHub courant (owner/repo) : GITHUB_REPOSITORY en CI, sinon le
 * remote de .git/config. Sert aux scripts qui appellent l'API GitHub ou
 * visent le site servi en local (baseUrl `/<repo>/`).
 */
import fs from 'node:fs';
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

/** URL de l'accueil servi par `npm run serve` (port 4173). */
export function urlSiteLocal() {
  const slug = repoSlug();
  const repo = slug ? slug.split('/')[1] : '';
  return `http://127.0.0.1:4173/${repo ? `${repo}/` : ''}`;
}
