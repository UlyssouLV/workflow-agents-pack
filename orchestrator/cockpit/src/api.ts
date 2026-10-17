// Contrat de l’API du runtime (`wap_runtime.cockpit`), lu sans transformation.

export type EtatAuth = "connecte" | "sans_token" | "token_refuse" | "injoignable";

export interface Auth {
  etat: EtatAuth;
  compte: string | null;
}

/** Un agent de l’encart Agents : `connecte` = token présent dans `secrets.env`. */
export interface Agent {
  id: "claude" | "cursor";
  nom: string;
  connecte: boolean;
  /** À lancer sur l’hôte pour le connecter. */
  commande: string;
}

export interface Etape {
  numero: number | null;
  libelle: string;
  humain: boolean;
}

export type EtatCi = "echec" | "en_cours" | "ok" | "aucune";

export interface Progression {
  completed: number;
  total: number;
}

export interface PrResume {
  numero: number;
  url: string;
  brouillon: boolean;
  ci: EtatCi;
}

export interface VersionResume {
  numero: number;
  titre: string;
  url: string;
  progression: Progression;
  etape: Etape;
  pr: PrResume | null;
}

/** Lien vers la session ouverte de l’instance (une seule à la fois). */
export interface LienSession {
  id: string;
  url: string;
  repo: string;
}

export type EtatSession = "ouverte" | "terminée" | "échouée";

/** `GET /api/sessions/{id}` : `jobs/<id>/session.json`, écrit par le runner. */
export interface Session {
  id: string;
  url: string;
  repo: string;
  ticket: number;
  agent: Agent["id"];
  commande: string;
  debut: string;
  fin: string | null;
  etat: EtatSession;
  code_sortie: number | null;
}

/** Une ligne de `GET /api/repos` : `erreur` non nulle → ni étape ni versions. */
export interface Repo<V = VersionResume> {
  slug: string;
  nom: string | null;
  url: string;
  lu_a: string;
  erreur: string | null;
  etape: Etape | null;
  humain_requis: boolean;
  versions: V[];
  /** Session ouverte sur ce repo (badge « Session en cours »). */
  session: LienSession | null;
}

export interface Liste {
  auth: Auth;
  agents: Agent[];
  /** Registry illisible. */
  erreur: string | null;
  repos: Repo[];
}

export interface Enfant {
  numero: number;
  titre: string;
  url: string;
  ouvert: boolean;
  labels: string[];
  bloque: boolean;
  /** Par agent : pourquoi `/implement #n` est grisé, `null` s’il est possible. */
  lancement: Record<Agent["id"], string | null>;
}

export interface Check {
  nom: string;
  etat: EtatCi;
  url: string | null;
}

export interface Version extends Omit<VersionResume, "pr"> {
  enfants: Enfant[];
  pr: (PrResume & { titre: string; branche: string; checks: Check[] }) | null;
  signaux: Etape[];
}

export interface Bug {
  numero: number;
  titre: string;
  url: string;
  labels: string[];
}

/** `GET /api/repos/{owner}/{name}`. */
export interface Detail extends Omit<Repo<Version>, "session"> {
  bugs: Bug[];
  agents: Agent[];
  /** Session ouverte de l’instance, quel que soit son repo. */
  session: LienSession | null;
}

export class ErreurApi extends Error {
  /** `409` : la session déjà ouverte. */
  session: LienSession | null = null;
}

export async function lire<T>(chemin: string): Promise<T> {
  const reponse = await fetch(chemin, { headers: { Accept: "application/json" } });
  if (!reponse.ok) {
    // FastAPI rend `{"detail": "<message>"}` (404 : repo absent du registry).
    const corps = await reponse.json().catch(() => null);
    throw new ErreurApi(corps?.detail ?? `${chemin} : HTTP ${reponse.status}`);
  }
  return (await reponse.json()) as T;
}

/** `POST /api/sessions` ; le navigateur y joint l’en-tête `Origin` que le runtime vérifie. */
export async function lancerSession(repo: string, ticket: number, agent: Agent["id"]): Promise<Session> {
  const reponse = await fetch("/api/sessions", {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify({ repo, ticket, agent }),
  });
  const corps = await reponse.json().catch(() => null);
  if (!reponse.ok) {
    const erreur = new ErreurApi(corps?.detail ?? `lancement : HTTP ${reponse.status}`);
    erreur.session = corps?.session ?? null;
    throw erreur;
  }
  return corps as Session;
}
