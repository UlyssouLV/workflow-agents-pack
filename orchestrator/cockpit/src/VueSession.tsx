import type { EtatSession, Session } from "./api";
import { useRafraichi } from "./rafraichi";

/** L’état d’une session ouverte change sans GitHub : relu plus souvent que les repos. */
export const RAFRAICHISSEMENT_SESSION_MS = 5_000;

const LIBELLES_ETAT: Record<EtatSession, string> = {
  ouverte: "Ouverte",
  terminée: "Terminée",
  échouée: "Échouée",
};

/** `/sessions/<id>` : état et durée d’une session `/implement`. */
export function VueSession({ id }: { id: string }) {
  const { donnees, erreur } = useRafraichi<Session>(
    `/api/sessions/${encodeURIComponent(id)}`,
    RAFRAICHISSEMENT_SESSION_MS,
  );

  return (
    <main>
      <p>
        <a href="/">← Tous les repos</a>
      </p>
      {erreur && <p className="erreur">{erreur}</p>}
      {donnees && <Contenu session={donnees} />}
    </main>
  );
}

function Contenu({ session }: { session: Session }) {
  const etat = LIBELLES_ETAT[session.etat];
  return (
    <>
      <h1>Session /implement #{session.ticket}</h1>
      <p>
        <a href={`/repos/${session.repo}`}>{session.repo}</a> · <code>{session.commande}</code>
      </p>
      <dl>
        <dt>État</dt>
        <dd>{session.etat === "échouée" ? `${etat} (code ${session.code_sortie})` : etat}</dd>
        <dt>Durée</dt>
        <dd>{duree(session.debut, session.fin)}</dd>
      </dl>
    </>
  );
}

/** Du début à la fin, ou à maintenant pour une session ouverte. */
export function duree(debut: string, fin: string | null): string {
  const total = Math.max(0, Math.round(((fin ? Date.parse(fin) : Date.now()) - Date.parse(debut)) / 1000));
  const [h, min, s] = [Math.floor(total / 3600), Math.floor((total % 3600) / 60), total % 60];
  if (h > 0) return `${h} h ${min} min`;
  if (min > 0) return `${min} min ${s} s`;
  return `${s} s`;
}
