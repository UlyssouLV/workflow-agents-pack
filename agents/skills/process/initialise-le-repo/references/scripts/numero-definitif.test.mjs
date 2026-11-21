// node --test scripts/numero-definitif.test.mjs
import assert from 'node:assert/strict';
import {test} from 'node:test';

import {lireReleases, numeroDefinitif, versionDeLaFeuille} from './numero-definitif.mjs';

test('une mineure après la Release 1.15.0 sort en 1.16.0', () => {
  assert.deepEqual(numeroDefinitif({type: 'mineure', derniereRelease: '1.15.0', toucheLivrables: true}), {
    numero: '1.16.0',
    incoherence: null,
  });
});

test('un correctif après la Release 2.1.0 sort en 2.1.1', () => {
  assert.equal(numeroDefinitif({type: 'correctif', derniereRelease: '2.1.0', toucheLivrables: true}).numero, '2.1.1');
});

test('une majeure après la Release 1.15.3 sort en 2.0.0', () => {
  assert.equal(numeroDefinitif({type: 'majeure', derniereRelease: '1.15.3', toucheLivrables: true}).numero, '2.0.0');
});

test('le tag de la dernière Release peut garder son v', () => {
  assert.equal(numeroDefinitif({type: 'mineure', derniereRelease: 'v1.15.0', toucheLivrables: true}).numero, '1.16.0');
});

test('premiere Release du dépôt : mineure 0.1.0, correctif 0.0.1, majeure 1.0.0', () => {
  assert.equal(numeroDefinitif({type: 'mineure', derniereRelease: null, toucheLivrables: true}).numero, '0.1.0');
  assert.equal(numeroDefinitif({type: 'correctif', derniereRelease: null, toucheLivrables: true}).numero, '0.0.1');
  assert.equal(numeroDefinitif({type: 'majeure', derniereRelease: null, toucheLivrables: true}).numero, '1.0.0');
});

test('une version de process qui ne touche pas livrables n’a ni numéro ni Release', () => {
  assert.deepEqual(numeroDefinitif({type: 'process', derniereRelease: '1.15.0', toucheLivrables: false}), {
    numero: null,
    incoherence: null,
  });
});

test('une version sans numéro qui touche livrables est une incohérence', () => {
  const r = numeroDefinitif({type: 'documentation', derniereRelease: '1.15.0', toucheLivrables: true});
  assert.equal(r.numero, null);
  assert.match(r.incoherence, /documentation.*livrables/);
});

test('une version numérotée qui ne touche aucun livrable est une incohérence, le numéro reste proposé', () => {
  const r = numeroDefinitif({type: 'mineure', derniereRelease: '1.15.0', toucheLivrables: false});
  assert.equal(r.numero, '1.16.0');
  assert.match(r.incoherence, /mineure.*aucun.*livrables/);
});

test('un type inconnu est refusé', () => {
  assert.throws(() => numeroDefinitif({type: 'patch', derniereRelease: '1.0.0', toucheLivrables: true}), /Type inconnu/);
});

const FEUILLE = `# Feuille de route de dev

## Déjà livré

- **1.15.0** — Moduléo (\`moduleo-mcp\`) : lu.

## Prochaine : Cycle de livraison

**État.** Ouvrable.

**Nom.** \`cycle-de-livraison\`

**Type.** process

**N° prévu.** Aucun (pas de Release).

**Bloquée par.** Aucune.

## Ensuite : HTTPS entre les postes et le Serveur BBASS

**État.** Ouvrable.

**Nom.** \`https-postes-serveur\`

**Type.** majeure

**N° prévu.** **2.0.0**

**Bloquée par.** Aucune.

## Plus tard (pas encore planifié)
`;

test('la feuille donne le Type et le titre d’une version par son Nom', () => {
  assert.deepEqual(versionDeLaFeuille(FEUILLE, 'https-postes-serveur'), {
    nom: 'https-postes-serveur',
    titre: 'HTTPS entre les postes et le Serveur BBASS',
    type: 'majeure',
  });
});

test('un Nom absent de Prochaine / Ensuite est refusé', () => {
  assert.throws(() => versionDeLaFeuille(FEUILLE, 'inconnue'), /inconnue.*ni en Prochaine ni en Ensuite/);
});

// ---- Pré-releases (essai en staging) et rôle livrables optionnel ----

test('sans rôle livrables (null), une version numérotée n’est pas une incohérence', () => {
  assert.equal(numeroDefinitif({type: 'mineure', derniereRelease: '1.15.0', toucheLivrables: null}).incoherence, null);
  assert.equal(numeroDefinitif({type: 'process', derniereRelease: '1.15.0', toucheLivrables: null}).incoherence, null);
});

test('un numéro réservé par la pré-release d’une autre version est sauté', () => {
  assert.equal(numeroDefinitif({type: 'mineure', derniereRelease: '1.15.0', toucheLivrables: true, reserves: ['1.16.0']}).numero, '1.17.0');
  assert.equal(numeroDefinitif({type: 'correctif', derniereRelease: '1.15.0', toucheLivrables: true, reserves: ['1.16.0']}).numero, '1.15.1');
});

test('la version qui a déjà une pré-release garde son numéro', () => {
  assert.equal(numeroDefinitif({type: 'mineure', derniereRelease: '1.16.0', toucheLivrables: true, preRelease: 'v1.16.0-rc.2'}).numero, '1.16.0');
});

const RELEASES = [
  {tag_name: 'v1.15.0', prerelease: false, draft: false, body: 'Version : ancienne (#1)'},
  {tag_name: 'v1.16.0-rc.1', prerelease: true, draft: false, body: 'Pré-release.\n\nVersion : agent (#10)'},
  {tag_name: 'v1.17.0-rc.1', prerelease: true, draft: false, body: 'Pré-release.\n\nVersion : autre (#20)'},
  {tag_name: 'v1.14.0-rc.1', prerelease: true, draft: false, body: 'Version : livree (#5)'},
  {tag_name: 'v1.14.0', prerelease: false, draft: false, body: 'Version : livree (#5)'},
  {tag_name: 'v9.0.0', prerelease: false, draft: true, body: ''},
];

test('les pré-releases ne comptent pas comme dernière Release, les brouillons non plus', () => {
  assert.equal(lireReleases(RELEASES, 'agent').derniereRelease, '1.15.0');
});

test('la pré-release de la version est reconnue par sa ligne Version, les autres réservent leur numéro', () => {
  const lu = lireReleases(RELEASES, 'agent');
  assert.equal(lu.preRelease, 'v1.16.0-rc.1');
  assert.deepEqual(lu.reserves, ['1.17.0']);
});

test('une pré-release dont la finale existe ne réserve rien', () => {
  assert.deepEqual(lireReleases(RELEASES, 'nouvelle').reserves, ['1.16.0', '1.17.0']);
});
