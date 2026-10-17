import { useState } from "react";
import type { EtatSession, Session } from "./api";
import { terminerSession } from "./api";
import { useRafraichi } from "./rafraichi";
import { TerminalEnDirect } from "./TerminalEnDirect";

/** L’état d’une session ouverte change sans GitHub : relu plus souvent que les repos. */
export const RAFRAICHISSEMENT_SESSION_MS = 5_000;

const LIBELLES_ETAT: Record<EtatSession, string> = {
  ouverte: "Ouverte",
  terminée: "Terminée",
  échouée: "Échouée",
};

/** `/sessions/<id>` : état et durée d’une session `/implement`, son terminal tant qu’elle est
 * ouverte. */
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

function Contenu({ session: lue }: { session: Session }) {
  // Rendue par **Terminer** : plus récente que la dernière lecture.
  const [close, setClose] = useState<Session | null>(null);
  const [refus, setRefus] = useState<string | null>(null);
  const session = close ?? lue;
  const etat = LIBELLES_ETAT[session.etat];

  const terminer = () => {
    if (!window.confirm("Terminer la session ? L’agent sera arrêté.")) return;
    setRefus(null);
    terminerSession(session.id).then(setClose, (erreur: Error) => setRefus(erreur.message));
  };

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
      {session.etat === "ouverte" && (
        <>
          <p>
            <button type="button" onClick={terminer}>
              Terminer
            </button>
          </p>
          {refus && (
            <p role="alert" className="erreur">
              {refus}
            </p>
          )}
          <TerminalEnDirect id={session.id} />
        </>
      )}
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
