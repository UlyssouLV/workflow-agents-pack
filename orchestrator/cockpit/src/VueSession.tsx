import { lazy, Suspense, useEffect, useRef, useState } from "react";
import type { Session } from "./api";
import { ID_SESSION, terminerSession } from "./api";
import {
  Entete,
  LIBELLES_ETAT_SESSION,
  LiensChaine,
  libelleActivite,
  libelleModele,
  lienSession,
} from "./commun";
import { RAFRAICHISSEMENT_SESSION_MS, useRafraichi } from "./rafraichi";
import { RelectureTerminal } from "./RelectureTerminal";
import { TerminalEnDirect } from "./TerminalEnDirect";

export { RAFRAICHISSEMENT_SESSION_MS } from "./rafraichi";

// Monaco pèse plusieurs Mo : chargé à la première ouverture de l’onglet seulement.
const Codespace = lazy(() => import("./Codespace").then((m) => ({ default: m.Codespace })));

/** Clé du `sessionStorage` de l’onglet : la page qui bascule vers la suivante y laisse d’où elle
 * vient et si elle avait la main ; la page de la suivante la lit au chargement. */
const ENCHAINEMENT = "wap:enchainement";

/** Onglets de la page : `/sessions/<id>` (Terminal) et `/sessions/<id>/codespace`. */
export type Onglet = "terminal" | "codespace";

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
 * ouverte, sa relecture ensuite ; à côté, l’onglet Codespace (`/sessions/<id>/codespace`).
 * Ouverte sur cette page puis `enchaînée`, elle bascule vers la suivante. */
export function VueSession({ id, onglet = "terminal" }: { id: string; onglet?: Onglet }) {
  const { donnees, erreur } = useRafraichi<Session>(
    `/api/sessions/${encodeURIComponent(id)}`,
    RAFRAICHISSEMENT_SESSION_MS,
  );
  // Lu une fois : une relecture de la page n’est plus une arrivée par l’enchaînement.
  const [arrivee] = useState(lireEnchainement);
  useEffect(() => ecrireEnchainement(null), []);

  return (
    <main>
      <Entete />
      {erreur && <p className="erreur">{erreur}</p>}
      {donnees && (
        <Contenu
          session={donnees}
          arrivee={arrivee?.depuis === donnees.precedente ? arrivee : null}
          ongletInitial={onglet}
        />
      )}
    </main>
  );
}

function Contenu({
  session: lue,
  arrivee,
  ongletInitial,
}: {
  session: Session;
  arrivee: Enchainement | null;
  ongletInitial: Onglet;
}) {
  // Rendue par **Terminer** : plus récente que la dernière lecture.
  const [close, setClose] = useState<Session | null>(null);
  const [refus, setRefus] = useState<string | null>(null);
  const session = close ?? lue;
  const etat = LIBELLES_ETAT_SESSION[session.etat];
  const modele = libelleModele(session);
  const suivante = lienSession(session.suivante);
  // Vue ouverte sur cette page (pas une relecture), et dernier rôle annoncé à l’onglet.
  const vueOuverte = useRef(false);
  const main = useRef(false);
  const [onglet, choisir] = useOnglet(session.id, ongletInitial);
  // Monté à la première ouverture de l’onglet, puis gardé (comme le terminal).
  const [codespaceVu, setCodespaceVu] = useState(ongletInitial === "codespace");
  useEffect(() => {
    if (onglet === "codespace") setCodespaceVu(true);
  }, [onglet]);

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
      <h1>{session.ticket != null ? `Session /implement #${session.ticket}` : `Session ${session.commande}`}</h1>
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
        <dt>Titre</dt>
        <dd>{session.titre}</dd>
        {modele && (
          <>
            <dt>Modèle</dt>
            <dd>{modele}</dd>
          </>
        )}
        <dt>Activité</dt>
        <dd>{libelleActivite(session)}</dd>
        <dt>État</dt>
        <dd>{precision(session) ? `${etat} (${precision(session)})` : etat}</dd>
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
        </>
      )}
      <div role="tablist" aria-label="Vues de la session" className="onglets">
        {(["terminal", "codespace"] as const).map((o) => (
          <button
            key={o}
            type="button"
            role="tab"
            id={`onglet-${o}`}
            aria-controls={`panneau-${o}`}
            aria-selected={onglet === o}
            onClick={() => choisir(o)}
          >
            {o === "terminal" ? "Terminal" : "Codespace"}
          </button>
        ))}
      </div>
      {/* Caché, pas démonté : le websocket reste ouvert et l’onglet garde la Main. */}
      <div role="tabpanel" id="panneau-terminal" aria-labelledby="onglet-terminal" hidden={onglet !== "terminal"}>
        {session.etat === "ouverte" ? (
          <TerminalEnDirect
            id={session.id}
            reprendre={arrivee?.main ?? false}
            surRole={(ecriture) => (main.current = ecriture)}
          />
        ) : (
          <RelectureTerminal id={session.id} />
        )}
      </div>
      <div role="tabpanel" id="panneau-codespace" aria-labelledby="onglet-codespace" hidden={onglet !== "codespace"}>
        {codespaceVu && (
          <Suspense fallback={<p className="etat-terminal">Chargement du codespace…</p>}>
            <Codespace id={session.id} />
          </Suspense>
        )}
      </div>
    </>
  );
}

/** L’onglet affiché, suivi dans l’URL sans recharger la page (le terminal reste connecté). */
function useOnglet(id: string, initial: Onglet): [Onglet, (onglet: Onglet) => void] {
  const [onglet, setOnglet] = useState(initial);
  const premier = useRef(true);

  useEffect(() => {
    const revenir = () => setOnglet(window.location.pathname.replace(/\/$/, "").endsWith("/codespace") ? "codespace" : "terminal");
    window.addEventListener("popstate", revenir);
    return () => window.removeEventListener("popstate", revenir);
  }, []);

  useEffect(() => {
    // Caché, le terminal n’a pas pu suivre la taille de la fenêtre : il s’y ajuste au retour.
    if (!premier.current && onglet === "terminal") window.dispatchEvent(new Event("resize"));
    premier.current = false;
  }, [onglet]);

  const choisir = (suivant: Onglet) => {
    if (suivant === onglet) return;
    const base = `/sessions/${encodeURIComponent(id)}`;
    window.history.pushState(null, "", suivant === "codespace" ? `${base}/codespace` : base);
    setOnglet(suivant);
  };
  return [onglet, choisir];
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
