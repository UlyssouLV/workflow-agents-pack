import type { Auth, Etape, Repo } from "./api";

const MESSAGES_AUTH: Partial<Record<Auth["etat"], string>> = {
  sans_token: "GitHub non connecté",
  token_refuse: "Token refusé par GitHub",
  injoignable: "GitHub injoignable",
};

/** Bandeau global quand l’instance ne peut pas lire GitHub. */
export function BandeauAuth({ auth }: { auth: Auth }) {
  if (auth.etat === "connecte") {
    return <p className="compte">Connecté à GitHub : {auth.compte}</p>;
  }
  return (
    <p role="alert" className="bandeau">
      {MESSAGES_AUTH[auth.etat]} : lancez <code>sudo wap-runtime auth</code> sur l’hôte.
    </p>
  );
}

export function BadgeHumain() {
  return <span className="badge">Intervention humaine requise</span>;
}

export function LibelleEtape({ etape }: { etape: Etape | null }) {
  if (etape === null) return null;
  return (
    <>
      {etape.libelle} {etape.humain && <BadgeHumain />}
    </>
  );
}

export function nomAffiche(repo: Pick<Repo, "slug" | "nom">): string {
  return repo.nom ?? repo.slug;
}

export function heure(iso: string): string {
  return new Date(iso).toLocaleTimeString("fr-FR");
}
