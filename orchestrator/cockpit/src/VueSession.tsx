import { useEffect, useRef, useState } from "react";
import type { Session } from "./api";
import { ID_SESSION, terminerSession } from "./api";
import { LIBELLES_ETAT_SESSION, LiensChaine, lienSession } from "./commun";
import { useRafraichi } from "./rafraichi";
import { RelectureTerminal } from "./RelectureTerminal";
import { TerminalEnDirect } from "./TerminalEnDirect";

/** L’état d’une session ouverte change sans GitHub : relu plus souvent que les repos. */
export const RAFRAICHISSEMENT_SESSION_MS = 5_000;

/** Clé du `sessionStorage` de l’onglet : la page qui bascule vers la suivante y laisse d’où elle
 * vient et si elle avait la main ; la page de la suivante la lit au chargement. */
const ENCHAINEMENT = "wap:enchainement";

interface Enchainement {
  depuis: string;
  main: boolean;
}

function lireEnchainement(): Enchainement | null {
  try {
    const lu = JSON.parse(sessionStorage.getItem(ENCHAINEMENT) ?? "null");
    return typeof lu?.depuis === "string" && ID_SESSION.test(lu.depuis)
      ? { depuis: lu.depuis, main: lu.main === true }
      : null;
  } catch {
    return null;
  }
}

function ecrireEnchainement(enchainement: Enchainement | null) {
  try {
    // Seul un id de session bien formé est écrit : l’onglet ne garde rien d’autre de l’API.
    if (enchainement && ID_SESSION.test(enchainement.depuis))
      sessionStorage.setItem(
        ENCHAINEMENT,
        JSON.stringify({ depuis: enchainement.depuis, main: enchainement.main === true }),
      );
    else sessionStorage.removeItem(ENCHAINEMENT);
  } catch {
    // Stockage indisponible : la bascule se fait sans bandeau ni reprise de la main.
  }
}

/** `/sessions/<id>` : état et durée d’une session `/implement`, son terminal tant qu’elle est
 * ouverte, sa relecture ensuite. Ouverte sur cette page puis `enchaînée`, elle bascule vers la
 * suivante. */
export function VueSession({ id }: { id: string }) {
  const { donnees, erreur } = useRafraichi<Session>(
    `/api/sessions/${encodeURIComponent(id)}`,
    RAFRAICHISSEMENT_SESSION_MS,
  );
  // Lu une fois : une relecture de la page n’est plus une arrivée par l’enchaînement.
  const [arrivee] = useState(lireEnchainement);
  useEffect(() => ecrireEnchainement(null), []);

  return (
    <main>
      <p>
        <a href="/">← Tous les repos</a>
      </p>
      {erreur && <p className="erreur">{erreur}</p>}
      {donnees && (
        <Contenu session={donnees} arrivee={arrivee?.depuis === donnees.precedente ? arrivee : null} />
      )}
    </main>
  );
}

function Contenu({ session: lue, arrivee }: { session: Session; arrivee: Enchainement | null }) {
  // Rendue par **Terminer** : plus récente que la dernière lecture.
  const [close, setClose] = useState<Session | null>(null);
  const [refus, setRefus] = useState<string | null>(null);
  const session = close ?? lue;
  const etat = LIBELLES_ETAT_SESSION[session.etat];
  const suivante = lienSession(session.suivante);
  // Vue ouverte sur cette page (pas une relecture), et dernier rôle annoncé à l’onglet.
  const vueOuverte = useRef(false);
  const main = useRef(false);

  useEffect(() => {
    if (session.etat === "ouverte") vueOuverte.current = true;
    if (session.etat !== "enchaînée" || !vueOuverte.current || !suivante) return;
    ecrireEnchainement({ depuis: session.id, main: main.current });
    window.location.assign(suivante);
  }, [session.etat, session.id, suivante]);

  const terminer = () => {
    if (!window.confirm("Terminer la session ? L’agent sera arrêté.")) return;
    setRefus(null);
    terminerSession(session.id).then(setClose, (erreur: Error) => setRefus(erreur.message));
  };

  return (
    <>
      <h1>Session /implement #{session.ticket}</h1>
      {arrivee && (
        <p role="status" className="enchainee">
          Session enchaînée : /implement #{session.ticket}
        </p>
      )}
      <p>
        <a href={`/repos/${session.repo}`}>{session.repo}</a> · <code>{session.commande}</code>
      </p>
      {(session.precedente || session.suivante) && (
        <p>
          <LiensChaine session={session} libelles={["Session précédente", "Session suivante"]} />
        </p>
      )}
      <dl>
        <dt>État</dt>
        <dd>{precision(session) ? `${etat} (${precision(session)})` : etat}</dd>
        <dt>Durée</dt>
        <dd>{duree(session.debut, session.fin)}</dd>
      </dl>
      {session.etat === "ouverte" ? (
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
          <TerminalEnDirect
            id={session.id}
            reprendre={arrivee?.main ?? false}
            surRole={(ecriture) => (main.current = ecriture)}
          />
        </>
      ) : (
        <RelectureTerminal id={session.id} />
      )}
    </>
  );
}

function precision(session: Session): string | null {
  if (session.etat === "échouée") return `code ${session.code_sortie}`;
  if (session.etat === "interrompue") return "runner redémarré";
  return null;
}

/** Du début à la fin, ou à maintenant pour une session ouverte. */
export function duree(debut: string, fin: string | null): string {
  const total = Math.max(0, Math.round(((fin ? Date.parse(fin) : Date.now()) - Date.parse(debut)) / 1000));
  const [h, min, s] = [Math.floor(total / 3600), Math.floor((total % 3600) / 60), total % 60];
  if (h > 0) return `${h} h ${min} min`;
  if (min > 0) return `${min} min ${s} s`;
  return `${s} s`;
}
