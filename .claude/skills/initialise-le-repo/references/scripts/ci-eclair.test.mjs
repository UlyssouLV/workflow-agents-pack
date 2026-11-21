// node --test scripts/ci-eclair.test.mjs
import assert from 'node:assert/strict';
import {test} from 'node:test';

import {baseDuRun, decisionEclair, dernierHeadVert} from './ci-eclair.mjs';

/** Run de workflow au format de l'API GitHub (GET …/actions/workflows/ci.yml/runs). */
const run = (sha, date, conclusion = 'success') => ({head_sha: sha, created_at: date, conclusion});
/** Comparaison au format de GET /repos/{o}/{r}/compare/{base}...{head}. */
const comparaison = (fichiers, status = 'ahead') => ({status, files: fichiers.map((filename) => ({filename}))});

/** Base de la PR inchangée depuis le run vert. */
const BASES = {baseVert: 'm1', baseActuelle: 'm1'};

const RUNS = [run('aaa', '2026-11-20T10:00:00Z'), run('bbb', '2026-11-20T12:00:00Z'), run('ccc', '2026-11-20T13:00:00Z', 'failure')];

test('le dernier HEAD vert est le run réussi le plus récent, hors HEAD courant', () => {
  assert.equal(dernierHeadVert(RUNS, 'ddd'), 'bbb');
  assert.equal(dernierHeadVert(RUNS, 'bbb'), 'aaa');
  assert.equal(dernierHeadVert([run('ccc', '2026-11-20T13:00:00Z', 'failure')], 'ddd'), null);
});

test('un push qui ne touche que README.md et docs/img/ après un HEAD vert passe en CI éclair', () => {
  const d = decisionEclair({...BASES, headVert: 'bbb', comparaison: comparaison(['README.md', 'docs/img/apercu-docs-accueil.png'])});
  assert.equal(d.eclair, true);
  assert.match(d.raison, /bbb/);
});

test('un autre fichier relance toute la CI, et la raison le cite', () => {
  const d = decisionEclair({...BASES, headVert: 'bbb', comparaison: comparaison(['README.md', 'poste/src/poste/app.py'])});
  assert.equal(d.eclair, false);
  assert.match(d.raison, /poste\/src\/poste\/app\.py/);
});

test('un fichier sous docs/ hors docs/img/, ou un README d’un sous-dossier, relance tout', () => {
  assert.equal(decisionEclair({...BASES, headVert: 'bbb', comparaison: comparaison(['docs/glossaire.md'])}).eclair, false);
  assert.equal(decisionEclair({...BASES, headVert: 'bbb', comparaison: comparaison(['poste/README.md'])}).eclair, false);
});

test('sans HEAD vert dans la PR, toute la CI tourne', () => {
  assert.equal(decisionEclair({headVert: null, comparaison: null}).eclair, false);
});

test('un HEAD vert qui n’est plus un ancêtre (force-push) relance tout', () => {
  assert.equal(decisionEclair({...BASES, headVert: 'bbb', comparaison: comparaison(['README.md'], 'diverged')}).eclair, false);
});

test('une comparaison tronquée (300 fichiers ou plus) relance tout', () => {
  const fichiers = Array.from({length: 300}, (_, i) => `docs/img/a${i}.png`);
  assert.equal(decisionEclair({...BASES, headVert: 'bbb', comparaison: comparaison(fichiers)}).eclair, false);
});

test('aucun fichier changé depuis le HEAD vert (même arbre) : CI éclair', () => {
  assert.equal(decisionEclair({...BASES, headVert: 'bbb', comparaison: comparaison([], 'ahead')}).eclair, true);
});

test('la base lue dans le run vert est celle de la PR de la branche', () => {
  const r = {head_sha: 'bbb', pull_requests: [{head: {ref: 'autre'}, base: {sha: 'x'}}, {head: {ref: 'v1'}, base: {sha: 'm1'}}]};
  assert.equal(baseDuRun(r, 'v1'), 'm1');
  assert.equal(baseDuRun({head_sha: 'bbb', pull_requests: []}, 'v1'), null);
  assert.equal(baseDuRun(null, 'v1'), null);
});

test('une base qui a bougé depuis le run vert, ou inconnue, relance tout', () => {
  const c = comparaison(['README.md']);
  const d = decisionEclair({headVert: 'bbb', baseVert: 'm1', baseActuelle: 'm2', comparaison: c});
  assert.equal(d.eclair, false);
  assert.match(d.raison, /m1 → m2/);
  assert.equal(decisionEclair({headVert: 'bbb', baseVert: null, baseActuelle: 'm1', comparaison: c}).eclair, false);
});

test('un fichier déplacé sous docs/img/ depuis ailleurs relance tout, et la raison cite son ancien chemin', () => {
  const c = {status: 'ahead', files: [{filename: 'docs/img/x.py', previous_filename: 'vm-centrale/src/x.py', status: 'renamed'}]};
  const d = decisionEclair({...BASES, headVert: 'bbb', comparaison: c});
  assert.equal(d.eclair, false);
  assert.match(d.raison, /vm-centrale\/src\/x\.py/);
});

test('un renommage à l’intérieur de docs/img/ reste en CI éclair', () => {
  const c = {status: 'ahead', files: [{filename: 'docs/img/b.png', previous_filename: 'docs/img/a.png', status: 'renamed'}]};
  assert.equal(decisionEclair({...BASES, headVert: 'bbb', comparaison: c}).eclair, true);
});
