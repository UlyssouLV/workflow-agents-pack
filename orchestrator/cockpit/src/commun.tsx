import { HandIcon, TriangleAlertIcon, ZapIcon } from "lucide-react";
import type { ReactNode } from "react";
import type { ActiviteSession, Etape, EtatSession, LienSession, Repo, Session } from "./api";
import { ID_SESSION } from "./api";
import { Alert, AlertDescription } from "./components/ui/alert";
import { Badge, Pastille } from "./components/ui/badge";
import { LIBELLES_STOP } from "./notifications";

/** Lecture ou registry en échec, en tête de page ou de carte. */
export function Erreur({ children }: { children: ReactNode }) {
  return (
    <Alert variant="destructive">
      <TriangleAlertIcon aria-hidden />
      <AlertDescription className="text-foreground">
        <p>{children}</p>
      </AlertDescription>
    </Alert>
  );
}

export function BadgeHumain() {
  return (
    <Badge variant="attention">
      <HandIcon aria-hidden />
      Intervention humaine requise
    </Badge>
  );
}

export function BadgePilote() {
  return (
    <Badge variant="pilote">
      <ZapIcon aria-hidden />
      Pilote
    </Badge>
  );
}

export function BadgePause({ stop }: { stop: NonNullable<Repo["pilote_stop"]> }) {
  return <Badge variant="pause">En pause · {LIBELLES_STOP[stop]}</Badge>;
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

export const LIBELLES_ACTIVITE: Record<ActiviteSession, string> = {
  travaille: "Travaille",
  attend: "Réponse attendue",
  inconnue: "Inconnue",
};

/** Badge de la vue liste (et détail) : activité inconnue → Session en cours. */
export function libelleBadgeSession(activite?: ActiviteSession | null): string {
  if (activite === "travaille") return LIBELLES_ACTIVITE.travaille;
  if (activite === "attend") return LIBELLES_ACTIVITE.attend;
  return "Session en cours";
}

/** Libellé cockpit : Auto si pas de `--model` ; `null` si l’agent n’est pas Cursor. */
export function libelleModele(session: Pick<Session, "agent" | "modele">): string | null {
  if (session.agent !== "cursor") return null;
  return session.modele ?? "Auto";
}

export function libelleActivite(session: Pick<Session, "activite" | "skill">): string {
  const base = LIBELLES_ACTIVITE[session.activite] ?? LIBELLES_ACTIVITE.inconnue;
  return session.activite === "attend" && session.skill ? `${base} — ${session.skill}` : base;
}

/** Orange quand l’agent attend, bleu sinon ; l’onde dit que la session vit. */
export function BadgeSession({ session }: { session: LienSession }) {
  const attend = session.activite === "attend";
  return (
    <Badge variant={attend ? "attention" : "agent"} asChild>
      <a href={session.url}>
        <Pastille vivant={attend || session.activite === "travaille"} />
        {libelleBadgeSession(session.activite)}
      </a>
    </Badge>
  );
}

export const LIBELLES_ETAT_SESSION: Record<EtatSession, string> = {
  ouverte: "Ouverte",
  terminée: "Terminée",
  arrêtée: "Arrêtée",
  échouée: "Échouée",
  interrompue: "Interrompue",
  enchaînée: "Enchaînée",
};

/** `/sessions/<id>` d’une voisine de la chaîne ; seul un identifiant valide bâtit l’URL. */
export function lienSession(id: string | null): string | null {
  return id && ID_SESSION.test(id) ? `/sessions/${id}` : null;
}

/** Liens vers la précédente et la suivante d’une session enchaînée ; rien hors chaîne. */
export function LiensChaine({
  session,
  libelles,
}: {
  session: Pick<Session, "precedente" | "suivante">;
  libelles: [precedente: string, suivante: string];
}) {
  const [precedente, suivante] = [lienSession(session.precedente), lienSession(session.suivante)];
  return (
    <>
      {precedente && <a href={precedente}>{libelles[0]}</a>}
      {precedente && suivante && " · "}
      {suivante && <a href={suivante}>{libelles[1]}</a>}
    </>
  );
}

/** Date et heure, au fuseau du navigateur, sans les secondes. */
export function dateHeure(iso: string): string {
  return new Date(iso).toLocaleString("fr-FR", { dateStyle: "short", timeStyle: "short" });
}
