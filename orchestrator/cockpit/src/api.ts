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
}

export interface Check {
  nom: string;
  etat: EtatCi;
  url: string | null;
}

export interface Version extends Omit<VersionResume, "pr"> {
  enfants: Enfant[];
  pr: (PrResume & { titre: string; checks: Check[] }) | null;
  signaux: Etape[];
}

export interface Bug {
  numero: number;
  titre: string;
  url: string;
  labels: string[];
}

/** `GET /api/repos/{owner}/{name}`. */
export interface Detail extends Repo<Version> {
  bugs: Bug[];
}

export class ErreurApi extends Error {}

export async function lire<T>(chemin: string): Promise<T> {
  const reponse = await fetch(chemin, { headers: { Accept: "application/json" } });
  if (!reponse.ok) {
    // FastAPI rend `{"detail": "<message>"}` (404 : repo absent du registry).
    const corps = await reponse.json().catch(() => null);
    throw new ErreurApi(corps?.detail ?? `${chemin} : HTTP ${reponse.status}`);
  }
  return (await reponse.json()) as T;
}
