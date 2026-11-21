/**
 * CI éclair (modèle du pack, à brancher sur le ci.yml du projet) : sur une PR, quand **tous** les fichiers changés
 * depuis le dernier HEAD vert de cette PR sont `README.md` ou sous
 * `docs/img/` (le seul commit d'après la Release, à « Finalise la version » :
 * aperçus du README et compteurs de commits), les checks requis de ci.yml
 * répondent sans relancer builds, tests ni e2e. Sinon, CI complète.
 * Sur `main`, ci.yml ne l'appelle pas : tout tourne.
 *
 * Dernier HEAD vert = HEAD du run de ci.yml réussi le plus récent sur la
 * branche de la PR. Il doit être un ancêtre du HEAD courant (pas de
 * force-push depuis), et la base de la PR ne doit pas avoir bougé depuis ce
 * run (le run d'une PR teste la fusion avec la base : une base qui a bougé
 * n'a jamais été testée avec cette branche). Un fichier renommé compte par
 * ses deux chemins. Le moindre doute (pas de run vert, base inconnue ou
 * différente, API en erreur, comparaison tronquée) → CI complète.
 *
 * Usage (job `changes` de ci.yml) :
 *   GH_TOKEN=… GITHUB_REPOSITORY=o/r HEAD_SHA=… HEAD_REF=… BASE_SHA=… node scripts/ci-eclair.mjs
 * Écrit `eclair=true|false` dans $GITHUB_OUTPUT (sinon sur stdout). Sort
 * toujours 0 : une erreur vaut CI complète.
 */
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';

/** Limite de fichiers d'une comparaison de l'API GitHub : au-delà, liste tronquée. */
const MAX_FICHIERS = 300;

const sansRelance = (fichier) => fichier === 'README.md' || fichier.startsWith('docs/img/');

/** Run réussi le plus récent, hors `headSha` ; null sinon. */
function dernierRunVert(runs, headSha) {
  const verts = runs
    .filter((r) => r.conclusion === 'success' && r.head_sha !== headSha)
    .sort((a, b) => String(b.created_at).localeCompare(String(a.created_at)));
  return verts[0] ?? null;
}

/** HEAD du run réussi le plus récent, hors `headSha` ; null sinon. */
export function dernierHeadVert(runs, headSha) {
  return dernierRunVert(runs, headSha)?.head_sha ?? null;
}

/** SHA de la base de la PR au moment du run (champ `pull_requests` de l'API) ; null si inconnue. */
export function baseDuRun(run, headRef) {
  const prs = run?.pull_requests ?? [];
  const pr = prs.find((p) => p.head?.ref === headRef) ?? prs[0];
  return pr?.base?.sha ?? null;
}

/** { eclair, raison } d'après le HEAD vert, les bases (run vert / actuelle) et la comparaison HEAD vert...HEAD. */
export function decisionEclair({headVert, baseVert, baseActuelle, comparaison}) {
  if (!headVert) return {eclair: false, raison: 'aucun HEAD vert dans cette PR : CI complète.'};
  if (!baseVert || !baseActuelle || baseVert !== baseActuelle) {
    return {eclair: false, raison: `base de la PR inconnue ou changée depuis ${headVert} (${baseVert ?? '?'} → ${baseActuelle ?? '?'}) : CI complète.`};
  }
  if (!comparaison || comparaison.status !== 'ahead') {
    return {eclair: false, raison: `${headVert} n’est pas un ancêtre du HEAD (${comparaison?.status ?? 'comparaison absente'}) : CI complète.`};
  }
  const entrees = comparaison.files ?? [];
  if (entrees.length >= MAX_FICHIERS) {
    return {eclair: false, raison: `comparaison tronquée (${entrees.length} fichiers) : CI complète.`};
  }
  // Un renommage compte par ses deux chemins : déplacer du code sous docs/img/ le retire d'ailleurs.
  const fichiers = entrees.flatMap((f) => (f.previous_filename ? [f.previous_filename, f.filename] : [f.filename]));
  const autres = fichiers.filter((f) => !sansRelance(f));
  if (autres.length) {
    return {eclair: false, raison: `changé depuis ${headVert} hors README.md / docs/img/ : ${autres.join(', ')} → CI complète.`};
  }
  return {eclair: true, raison: `depuis ${headVert} (vert), seulement README.md / docs/img/ : CI éclair.`};
}

// --- Ligne de commande ------------------------------------------------------

async function gh(chemin) {
  const headers = {
    Accept: 'application/vnd.github+json',
    'X-GitHub-Api-Version': '2022-11-28',
    'User-Agent': 'ci-eclair',
  };
  const jeton = process.env.GH_TOKEN || process.env.GITHUB_TOKEN;
  if (jeton) headers.Authorization = `Bearer ${jeton}`;
  const res = await fetch(`https://api.github.com${chemin}`, {headers});
  if (!res.ok) throw new Error(`${chemin} → ${res.status}`);
  return res.json();
}

async function decider() {
  const {GITHUB_REPOSITORY: slug, HEAD_SHA: headSha, HEAD_REF: headRef, BASE_SHA: baseActuelle} = process.env;
  if (!slug || !headSha || !headRef || !baseActuelle) throw new Error('GITHUB_REPOSITORY, HEAD_SHA, HEAD_REF et BASE_SHA requis');
  const {workflow_runs: runs = []} = await gh(
    `/repos/${slug}/actions/workflows/ci.yml/runs?event=pull_request&status=success&per_page=30&branch=${encodeURIComponent(headRef)}`,
  );
  const runVert = dernierRunVert(runs, headSha);
  const headVert = runVert?.head_sha ?? null;
  const baseVert = baseDuRun(runVert, headRef);
  const comparaison = headVert && baseVert === baseActuelle ? await gh(`/repos/${slug}/compare/${headVert}...${headSha}`) : null;
  return decisionEclair({headVert, baseVert, baseActuelle, comparaison});
}

async function principal() {
  let d;
  try {
    d = await decider();
  } catch (e) {
    d = {eclair: false, raison: `${e.message} : CI complète.`};
  }
  console.log(`[ci-eclair] ${d.raison}`);
  const ligne = `eclair=${d.eclair}\n`;
  if (process.env.GITHUB_OUTPUT) fs.appendFileSync(process.env.GITHUB_OUTPUT, ligne);
  else process.stdout.write(ligne);
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  await principal();
}
