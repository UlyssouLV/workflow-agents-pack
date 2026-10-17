// Réponses `/api/` simulées, à la forme rendue par `wap_runtime.cockpit`.
import { vi } from "vitest";
import type { Agent, Auth, Detail, Etape, Liste, Repo, Session, VersionResume } from "../src/api";

export const CONNECTE: Auth = { etat: "connecte", compte: "octocat" };

export const CLAUDE: Agent = {
  id: "claude",
  nom: "Claude Code",
  connecte: true,
  commande: "sudo wap-runtime auth claude",
};
export const CURSOR: Agent = {
  id: "cursor",
  nom: "Cursor",
  connecte: false,
  commande: "… | sudo wap-runtime auth agent --with-token",
};

export const IMPLEMENT: Etape = { numero: 7, libelle: "Implement", humain: false };
export const QUESTION: Etape = { numero: 1, libelle: "Question en attente", humain: true };
export const PAS_DE_VERSION: Etape = { numero: 9, libelle: "Pas de version ouverte", humain: false };

export function version(v: Partial<VersionResume> = {}): VersionResume {
  return {
    numero: 17,
    titre: "v0.3.0 — registry",
    url: "https://github.com/o/r/issues/17",
    progression: { completed: 2, total: 5 },
    etape: IMPLEMENT,
    pr: { numero: 18, url: "https://github.com/o/r/pull/18", brouillon: true, ci: "ok" },
    ...v,
  };
}

export function repo(r: Partial<Repo> = {}): Repo {
  return {
    slug: "o/r",
    nom: null,
    url: "https://github.com/o/r",
    lu_a: "2026-10-17T09:00:00+00:00",
    erreur: null,
    etape: IMPLEMENT,
    humain_requis: false,
    versions: [version()],
    session: null,
    ...r,
  };
}

export function liste(l: Partial<Liste> = {}): Liste {
  return { auth: CONNECTE, agents: [CLAUDE, CURSOR], erreur: null, repos: [repo()], ...l };
}

export function detail(d: Partial<Detail> = {}): Detail {
  return {
    ...repo(),
    agents: [CLAUDE, CURSOR],
    versions: [
      {
        ...version(),
        enfants: [
          {
            numero: 20,
            titre: "Registry",
            url: "https://github.com/o/r/issues/20",
            ouvert: false,
            labels: [],
            bloque: false,
            lancement: { claude: "enfant fermé", cursor: "enfant fermé" },
          },
          {
            numero: 22,
            titre: "Front du cockpit",
            url: "https://github.com/o/r/issues/22",
            ouvert: true,
            labels: ["ready-for-agent"],
            bloque: true,
            lancement: { claude: "enfant bloqué", cursor: "enfant bloqué" },
          },
          {
            numero: 23,
            titre: "Lancer une session",
            url: "https://github.com/o/r/issues/23",
            ouvert: true,
            labels: ["ready-for-agent"],
            bloque: false,
            lancement: { claude: null, cursor: "agent non connecté" },
          },
        ],
        pr: {
          numero: 18,
          titre: "v0.3.0",
          url: "https://github.com/o/r/pull/18",
          brouillon: true,
          branche: "v0.3.0-registry",
          ci: "echec",
          checks: [{ nom: "pytest", etat: "echec", url: "https://github.com/o/r/runs/1" }],
        },
        signaux: [IMPLEMENT],
      },
    ],
    bugs: [{ numero: 30, titre: "Plantage", url: "https://github.com/o/r/issues/30", labels: ["bug"] }],
    ...d,
  };
}

export function session(s: Partial<Session> = {}): Session {
  return {
    id: "20261017-090000-abcdef",
    url: "/sessions/20261017-090000-abcdef",
    repo: "o/r",
    ticket: 23,
    agent: "claude",
    commande: 'claude "/implement #23"',
    debut: "2026-10-17T09:00:00+00:00",
    fin: null,
    etat: "ouverte",
    code_sortie: null,
    ...s,
  };
}

/** Faux `fetch` : `routes[chemin]` (GET) ou `routes["POST <chemin>"]` est la réponse JSON (ou une
 * fonction appelée à chaque requête, avec ses options). */
export function simulerApi(routes: Record<string, unknown | ((init?: RequestInit) => unknown)>) {
  const repondre = (chemin: string, init?: RequestInit): Response => {
    const cle = init?.method && init.method !== "GET" ? `${init.method} ${chemin}` : chemin;
    if (!(cle in routes)) {
      return new Response(JSON.stringify({ detail: "Not Found" }), { status: 404 });
    }
    const route = routes[cle];
    const corps = typeof route === "function" ? route(init) : route;
    if (corps instanceof Response) return corps;
    return new Response(JSON.stringify(corps), { status: 200 });
  };
  const fetch = vi.fn((chemin: string, init?: RequestInit) => Promise.resolve(repondre(chemin, init)));
  vi.stubGlobal("fetch", fetch);
  return fetch;
}
