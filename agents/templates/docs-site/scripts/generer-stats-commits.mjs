/**
 * Compte les commits sur la branche d'intégration + la somme des commits des
 * PR mergées (historique des branches squashées), puis écrit deux fichiers
 * shields.io « endpoint » dans static/stats/, publiés avec le site (Deploy
 * docs, à chaque push). Les badges du README les lisent : aucun commit de bot.
 *
 *   ![commits](https://img.shields.io/endpoint?url=https://<owner>.github.io/<repo>/stats/commits-main.json)
 *   ![commits PR](https://img.shields.io/endpoint?url=https://<owner>.github.io/<repo>/stats/commits-pr.json)
 *
 * Env : GITHUB_TOKEN ou GH_TOKEN, GITHUB_REPOSITORY (owner/repo),
 * STATS_BRANCHE (défaut main).
 *
 * Usage : node scripts/generer-stats-commits.mjs
 */
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';

import {REPO_ROOT, repoSlug} from './depot.mjs';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const SORTIE = path.resolve(__dirname, '../static/stats');
const BRANCHE = process.env.STATS_BRANCHE || 'main';

function token() {
  return process.env.GITHUB_TOKEN || process.env.GH_TOKEN || '';
}

async function ghJson(pathname, {raw = false} = {}) {
  const headers = {
    Accept: 'application/vnd.github+json',
    'X-GitHub-Api-Version': '2022-11-28',
    'User-Agent': 'docs-stats-commits',
  };
  const t = token();
  if (t) headers.Authorization = `Bearer ${t}`;
  const res = await fetch(`https://api.github.com${pathname}`, {headers});
  if (!res.ok) {
    throw new Error(`${pathname} → ${res.status} ${await res.text()}`);
  }
  if (raw) return res;
  return res.json();
}

function parseLastPage(linkHeader) {
  if (!linkHeader) return 1;
  const m = linkHeader.match(/[?&]page=(\d+)>;\s*rel="last"/);
  return m ? Number(m[1]) : 1;
}

async function commitsSurMain(owner, repo) {
  const res = await ghJson(
    `/repos/${owner}/${repo}/commits?sha=${BRANCHE}&per_page=1`,
    {raw: true},
  );
  await res.arrayBuffer();
  return parseLastPage(res.headers.get('link'));
}

async function prsMergees(owner, repo) {
  const out = [];
  let page = 1;
  for (;;) {
    const batch = await ghJson(
      `/repos/${owner}/${repo}/pulls?state=closed&per_page=100&page=${page}`,
    );
    if (!batch.length) break;
    for (const pr of batch) {
      if (pr.merged_at) out.push(pr.number);
    }
    if (batch.length < 100) break;
    page += 1;
  }
  return out;
}

async function commitsDunePr(owner, repo, number) {
  const pr = await ghJson(`/repos/${owner}/${repo}/pulls/${number}`);
  return Number(pr.commits) || 0;
}

function badge(label, message, color) {
  return {schemaVersion: 1, label, message: String(message), color};
}

function ecrireBadges({main, prs}) {
  fs.mkdirSync(SORTIE, {recursive: true});
  const fichiers = {
    'commits-main.json': badge(`commits ${BRANCHE}`, main, 'c8102e'),
    'commits-pr.json': badge('commits PR (historique)', prs, '1e3a5f'),
  };
  for (const [nom, contenu] of Object.entries(fichiers)) {
    fs.writeFileSync(path.join(SORTIE, nom), `${JSON.stringify(contenu)}\n`, 'utf8');
  }
  console.log(`[stats] badges écrits dans ${path.relative(REPO_ROOT, SORTIE)}/`);
}

async function main() {
  const slug = repoSlug();
  if (!slug) {
    console.warn('[stats] soft-skip : dépôt GitHub introuvable (GITHUB_REPOSITORY ou remote)');
    return;
  }
  const [owner, repo] = slug.split('/');
  console.log(`[stats] dépôt ${owner}/${repo}`);

  const mainCount = await commitsSurMain(owner, repo);
  const numeros = await prsMergees(owner, repo);
  let prCommits = 0;
  for (const n of numeros) {
    prCommits += await commitsDunePr(owner, repo, n);
  }

  console.log(`[stats] main=${mainCount} · PR mergées=${numeros.length} · commits PR=${prCommits}`);
  ecrireBadges({main: mainCount, prs: prCommits});
}

main().catch((e) => {
  console.error('[stats]', e);
  process.exit(1);
});
