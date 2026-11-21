// node --test agents/scripts/criteres-non-coches.test.mjs
import assert from 'node:assert/strict';
import {test} from 'node:test';

import {criteresNonCoches} from './criteres-non-coches.mjs';

const corps = (criteres) => `Part of #529

## What to build

- [ ] Une case hors critères, ignorée.

## Acceptance criteria

${criteres}

## Blocked by

- [ ] Une case hors critères, ignorée.
`;

test('un enfant dont toutes les cases sont cochées peut se fermer', () => {
  assert.deepEqual(criteresNonCoches(corps('- [x] Calcul testé.\n- [X] Tests verts.')), []);
});

test('une case vide des critères empêche la fermeture et est citée', () => {
  assert.deepEqual(criteresNonCoches(corps('- [x] Calcul testé.\n- [ ] Garde testée.\n- [ ] Tests verts (`/t`).')), [
    'Garde testée.',
    'Tests verts (`/t`).',
  ]);
});

test('un critère repris par le plan de tests humains peut rester vide', () => {
  const c = '- [ ] CI éclair sur une PR d’essai — vérifié par un humain : scénario 3 de #540.\n- [x] Tests verts.';
  assert.deepEqual(criteresNonCoches(corps(c)), []);
});

test('les cases imbriquées et les fins de ligne Windows sont lues', () => {
  const c = '- [x] Parent.\r\n  - [ ] Sous-critère.\r\n';
  assert.deepEqual(criteresNonCoches(corps(c).replace(/\n/g, '\r\n')), ['Sous-critère.']);
});

test('un enfant sans partie « Acceptance criteria » n’a rien à refuser', () => {
  assert.deepEqual(criteresNonCoches('## What to build\n\n- [ ] Rien.\n'), []);
});
