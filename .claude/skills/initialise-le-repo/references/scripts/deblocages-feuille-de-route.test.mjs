// node --test scripts/deblocages-feuille-de-route.test.mjs
import assert from 'node:assert/strict';
import {test} from 'node:test';

import {genererSvg, lireAvancement} from './avancement-feuille-de-route.mjs';
import {calculerDeblocages, lireFeuille, reecrireFeuille} from './deblocages-feuille-de-route.mjs';

function feuille({livrees = [], versions}) {
  const deja = livrees.map((n) => `- **${n}** — livrée.`).join('\n');
  const aVenir = versions
    .map(({numero, bloqueurs}) => {
      const rub = bloqueurs.length
        ? `**Bloquée par.**\n\n${bloqueurs.map((b) => `- **${b}** — raison.`).join('\n')}`
        : '**Bloquée par.** Aucune.';
      return `## Ensuite : ${numero} — Version ${numero}\n\n**Objectif.** Faire.\n\n${rub}\n\n**Hors périmètre.** Aucun.\n`;
    })
    .join('\n');
  return `# Feuille de route de dev\n\n## Déjà livré\n\n${deja}\n\n${aVenir}\n## Plus tard (pas encore numéroté)\n`;
}

const etats = (md) =>
  Object.fromEntries(calculerDeblocages(md).map((v) => [v.numero, v.ouvrable ? 'ouvrable' : v.restants.join('+')]));

test('deux versions en parallèle débloquent chacune la leur, à leur fusion', () => {
  const versions = [
    {numero: '1.1.0', bloqueurs: []},
    {numero: '1.2.0', bloqueurs: []},
    {numero: '1.3.0', bloqueurs: ['1.1.0']},
    {numero: '1.4.0', bloqueurs: ['1.2.0']},
  ];
  // Les deux sont ouvertes, aucune fusionnée : rien ne bouge.
  assert.deepEqual(etats(feuille({versions})), {
    '1.1.0': 'ouvrable',
    '1.2.0': 'ouvrable',
    '1.3.0': '1.1.0',
    '1.4.0': '1.2.0',
  });
  // 1.2.0 fusionnée la première : seule 1.4.0 se débloque.
  assert.deepEqual(
    etats(feuille({livrees: ['1.2.0'], versions: versions.filter((v) => v.numero !== '1.2.0')})),
    {'1.1.0': 'ouvrable', '1.3.0': '1.1.0', '1.4.0': 'ouvrable'},
  );
});

test('une version bloquée par deux autres voit son blocage se réduire', () => {
  const md = feuille({
    livrees: ['1.1.0'],
    versions: [
      {numero: '1.2.0', bloqueurs: []},
      {numero: '1.3.0', bloqueurs: ['1.1.0', '1.2.0']},
    ],
  });
  const {markdown} = reecrireFeuille(md);
  assert.match(markdown, /## Ensuite : 1\.3\.0 — Version 1\.3\.0\n\n\*\*État\.\*\* Bloquée : il reste \*\*1\.2\.0\*\* \(1 sur 2\)\./);
});

test('la Prochaine est la première version ouvrable', () => {
  const md = feuille({
    versions: [
      {numero: '1.1.0', bloqueurs: ['1.2.0']},
      {numero: '1.2.0', bloqueurs: []},
    ],
  });
  const {markdown} = reecrireFeuille(md);
  assert.match(markdown, /## Ensuite : 1\.1\.0/);
  assert.match(markdown, /## Prochaine : 1\.2\.0/);
  assert.match(markdown, /1\.1\.0\n\n\*\*État\.\*\* Bloquée : il reste \*\*1\.2\.0\*\*\./);
});

test('relancer le calcul ne change plus rien', () => {
  const md = feuille({versions: [{numero: '1.1.0', bloqueurs: []}, {numero: '1.2.0', bloqueurs: ['1.1.0']}]});
  const une = reecrireFeuille(md).markdown;
  assert.equal(reecrireFeuille(une).markdown, une);
});

test('refuse une rubrique manquante, un bloqueur inconnu et un cycle', () => {
  assert.throws(
    () => calculerDeblocages('## Déjà livré\n\n## Ensuite : 1.1.0 — A\n\n**Objectif.** x\n'),
    /manquante/,
  );
  assert.throws(() => etats(feuille({versions: [{numero: '1.1.0', bloqueurs: ['9.9.9']}]})), /absente/);
  assert.throws(
    () =>
      etats(
        feuille({
          versions: [
            {numero: '1.1.0', bloqueurs: ['1.2.0']},
            {numero: '1.2.0', bloqueurs: ['1.1.0']},
          ],
        }),
      ),
    /cycle/,
  );
});

// ---- Versions nommées (règle des versions nommées) : Nom, Type, N° prévu calculé. ----

function nommee({livrees = [], versions}) {
  const deja = livrees.join('\n');
  const aVenir = versions
    .map(({nom, type, bloqueurs = [], prevu}) => {
      const rub = bloqueurs.length
        ? `**Bloquée par.**\n\n${bloqueurs.map((b) => `- **${b}** — raison.`).join('\n')}`
        : '**Bloquée par.** Aucune.';
      const ligne = prevu === undefined ? '' : `\n\n**N° prévu.** ${prevu}`;
      return `## Ensuite : Titre de ${nom}\n\n**Nom.** \`${nom}\`\n\n**Type.** ${type}${ligne}\n\n**Objectif.** Faire.\n\n${rub}\n\n**Hors périmètre.** Aucun.\n`;
    })
    .join('\n');
  return `# Feuille de route de dev\n\n## Déjà livré\n\n${deja}\n\n${aVenir}\n## Plus tard (pas encore numéroté)\n`;
}

const RELEASE_1_15 = [
  '- **1.10.0** — Serveur MCP Moduléo (…) : lectures. Livrée en **1.15.0**.',
  '- **1.14.0** — Signés (…) : signés.',
];

const prevus = (md) => Object.fromEntries(calculerDeblocages(md).map((v) => [v.id, v.numeroPrevu]));

test('le N° prévu se calcule après la dernière Release, dans l’ordre de la feuille et selon le type', () => {
  const md = nommee({
    livrees: RELEASE_1_15,
    versions: [
      {nom: 'cycle-de-livraison', type: 'process'},
      {nom: 'https-postes-serveur', type: 'majeure'},
      {nom: 'messagerie-outlook', type: 'mineure'},
      {nom: 'outils-du-modele', type: 'documentation'},
      {nom: 'cartographie', type: 'analyse'},
      {nom: 'jeu-de-cas', type: 'évaluation'},
      {nom: 'serveurs-de-fichiers', type: 'mineure'},
      {nom: 'outils-utiles', type: 'correctif'},
      {nom: 'https-partout', type: 'correctif'},
    ],
  });
  assert.deepEqual(prevus(md), {
    'cycle-de-livraison': null,
    'https-postes-serveur': '2.0.0',
    'messagerie-outlook': '2.1.0',
    'outils-du-modele': null,
    cartographie: null,
    'jeu-de-cas': null,
    'serveurs-de-fichiers': '2.2.0',
    'outils-utiles': '2.2.1',
    'https-partout': '2.2.2',
  });
});

test('la dernière Release se lit dans Déjà livré : numéro de la puce, ou « Livrée en », jamais une puce sans Release', () => {
  const md = nommee({
    livrees: [
      '- **1.7.2** — Doc (…) : site. Sans Release produit.',
      '- **1.9.9** — Doc (…) : site. Sans Release produit.',
      '- **1.5.2** — Écrire (…) : écritures, reportées en **1.10.1**. Livrée en **1.6.3**.',
      '- **1.8.0** — Enregistrer (…) : vidéo.',
      '- **ancienne-doc** — Doc (…) : site. Sans Release.',
    ],
    versions: [{nom: 'suite', type: 'correctif'}],
  });
  assert.equal(lireFeuille(md).derniereRelease, '1.8.0');
  assert.deepEqual(prevus(md), {suite: '1.8.1'});
});

test('la réécriture pose le titre sans numéro, État. et le N° prévu, et ne change plus rien ensuite', () => {
  const md = nommee({
    livrees: RELEASE_1_15,
    versions: [
      {nom: 'documentation-a', type: 'documentation'},
      {nom: 'https-postes-serveur', type: 'majeure', prevu: '9.9.9'},
      {nom: 'messagerie-outlook', type: 'mineure', bloqueurs: ['https-postes-serveur']},
    ],
  });
  const {markdown} = reecrireFeuille(md);
  assert.match(
    markdown,
    /## Prochaine : Titre de documentation-a\n\n\*\*État\.\*\* Ouvrable\.\n\n\*\*Nom\.\*\* `documentation-a`\n\n\*\*Type\.\*\* documentation\n\n\*\*N° prévu\.\*\* Aucun \(pas de Release\)\.\n/,
  );
  assert.match(
    markdown,
    /## Ensuite : Titre de https-postes-serveur\n\n\*\*État\.\*\* Ouvrable\.\n\n\*\*Nom\.\*\* `https-postes-serveur`\n\n\*\*Type\.\*\* majeure\n\n\*\*N° prévu\.\*\* \*\*2\.0\.0\*\*\n/,
  );
  assert.match(markdown, /Titre de messagerie-outlook\n\n\*\*État\.\*\* Bloquée : il reste \*\*https-postes-serveur\*\*\./);
  assert.match(markdown, /\*\*Type\.\*\* mineure\n\n\*\*N° prévu\.\*\* \*\*2\.1\.0\*\*\n/);
  assert.equal(reecrireFeuille(markdown).markdown, markdown);
});

test('un N° prévu faux rend la feuille périmée', () => {
  const md = nommee({livrees: RELEASE_1_15, versions: [{nom: 'a', type: 'mineure', prevu: '**1.16.1**'}]});
  const {markdown} = reecrireFeuille(md);
  assert.notEqual(markdown, md);
  assert.match(markdown, /\*\*N° prévu\.\*\* \*\*1\.16\.0\*\*/);
});

test('un bloqueur cité par son nom est levé quand sa puce est livrée, par son nom ou numérotée avec son nom', () => {
  const versions = [{nom: 'agent', type: 'mineure', bloqueurs: ['cartographie', 'https-postes-serveur']}];
  const avant = calculerDeblocages(
    nommee({
      livrees: RELEASE_1_15,
      versions: [...versions, {nom: 'cartographie', type: 'analyse'}, {nom: 'https-postes-serveur', type: 'majeure'}],
    }),
  );
  assert.deepEqual(avant[0].restants, ['cartographie', 'https-postes-serveur']);
  const livrees = [
    ...RELEASE_1_15,
    '- **cartographie** — Cartographie (…) : fiches. Sans Release.',
    '- **2.0.0** — HTTPS entre les postes et le Serveur BBASS (`https-postes-serveur`, [#462](https://example.org)) : chiffré.',
  ];
  const [agent] = calculerDeblocages(nommee({livrees, versions}));
  assert.equal(agent.ouvrable, true);
  // La Release 2.0.0 compte : la suivante part de là.
  assert.equal(agent.numeroPrevu, '2.1.0');
});

test('le nom d’une puce numérotée est lu même si son titre contient des parenthèses', () => {
  const versions = [{nom: 'agent', type: 'mineure', bloqueurs: ['workflows-n8n']}];
  const livrees = [
    ...RELEASE_1_15,
    '- **1.16.0** — Workflows n8n (socle d’automatisation), branchés (`workflows-n8n`, [#600](https://example.org)) : flux.',
  ];
  const [agent] = calculerDeblocages(nommee({livrees, versions}));
  assert.equal(agent.ouvrable, true);
});

test('un `(`code`, …` dans le résumé d’une ancienne puce n’est pas pris pour un nom', () => {
  const {livrees} = lireFeuille('## Déjà livré\n\n- **1.2.2** — Style ([#1](x)) : rendu (`react-markdown`, allowlist).\n');
  assert.equal(livrees.has('react-markdown'), false);
});

test('refuse un Nom absent ou mal formé, un Type inconnu, un nom en double', () => {
  assert.throws(
    () => calculerDeblocages('## Déjà livré\n\n## Ensuite : Sans nom\n\n**Type.** mineure\n\n**Bloquée par.** Aucune.\n'),
    /Nom/,
  );
  assert.throws(() => calculerDeblocages(nommee({versions: [{nom: 'Pas_Kebab', type: 'mineure'}]})), /Nom/);
  assert.throws(() => calculerDeblocages(nommee({versions: [{nom: 'a', type: 'grosse'}]})), /Type/);
  assert.throws(
    () => calculerDeblocages(nommee({versions: [{nom: 'a', type: 'mineure'}, {nom: 'a', type: 'correctif'}]})),
    /double/,
  );
  assert.throws(
    () => calculerDeblocages(nommee({versions: [{nom: 'a', type: 'mineure', bloqueurs: ['inconnue']}]})),
    /absente/,
  );
});

test('l’ancienne forme numérotée reste lue, à côté d’une version nommée', () => {
  const md = feuille({livrees: ['1.1.0'], versions: [{numero: '1.2.0', bloqueurs: ['1.1.0']}]}).replace(
    '## Plus tard',
    '## Ensuite : Nommée\n\n**Nom.** `nommee`\n\n**Type.** correctif\n\n**Bloquée par.**\n\n- **1.2.0** — raison.\n\n## Plus tard',
  );
  assert.deepEqual(
    calculerDeblocages(md).map((v) => [v.id, v.numero, v.titre, v.restants]),
    [
      ['1.2.0', '1.2.0', 'Version 1.2.0', []],
      ['nommee', null, 'Nommée', ['1.2.0']],
    ],
  );
  const {markdown} = reecrireFeuille(md);
  assert.match(markdown, /## Prochaine : 1\.2\.0 — Version 1\.2\.0\n\n\*\*État\.\*\* Ouvrable\./);
  assert.match(markdown, /## Ensuite : Nommée\n\n\*\*État\.\*\* Bloquée : il reste \*\*1\.2\.0\*\*\./);
});

test('le bandeau compte les puces livrées des deux formes et annonce la Prochaine par son titre', () => {
  const md = nommee({
    livrees: [...RELEASE_1_15, '- **doc-a** — Doc (…) : site. Sans Release.'],
    versions: [{nom: 'https-postes-serveur', type: 'majeure'}],
  });
  const avancement = lireAvancement(reecrireFeuille(md).markdown);
  assert.equal(avancement.livrees, 3);
  assert.equal(avancement.restantes, 1);
  assert.equal(avancement.prochaine.titre, 'Titre de https-postes-serveur');
  assert.match(genererSvg(avancement), /Prochaine : Titre de https-postes-serveur</);
});
