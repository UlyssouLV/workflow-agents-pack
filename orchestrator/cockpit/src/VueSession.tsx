import {
  ArrowLeftIcon,
  ArrowRightIcon,
  BotIcon,
  CodeIcon,
  GitBranchIcon,
  LinkIcon,
  SquareIcon,
  SquareTerminalIcon,
} from "lucide-react";
import { lazy, Suspense, useEffect, useRef, useState, type ReactNode } from "react";
import type { Agent, Session } from "./api";
import { ID_SESSION, terminerSession } from "./api";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "./components/ui/alert-dialog";
import { Alert, AlertDescription } from "./components/ui/alert";
import { Button, buttonVariants } from "./components/ui/button";
import { Card } from "./components/ui/card";
import { BadgeActivite, BadgeEtat, Erreur, LIBELLES_ETAT_SESSION, libelleModele, lienSession } from "./commun";
import { ContenuPage, Coque, EnTetePage } from "./Coque";
import { cn } from "./lib/utils";
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
  const agents = useRafraichi<{ agents: Agent[] }>("/api/agents");
  // Lu une fois : une relecture de la page n’est plus une arrivée par l’enchaînement.
  const [arrivee] = useState(lireEnchainement);
  useEffect(() => ecrireEnchainement(null), []);

  return (
    <Coque courant="sessions">
      {donnees ? (
        <Contenu
          session={donnees}
          erreur={erreur}
          nomAgent={(a) => agents.donnees?.agents.find((x) => x.id === a)?.nom ?? a}
          arrivee={arrivee?.depuis === donnees.precedente ? arrivee : null}
          ongletInitial={onglet}
        />
      ) : (
        erreur && (
          <>
            <EnTetePage ariane={<a href="/sessions">Sessions</a>} titre="Session" />
            <ContenuPage>
              <Erreur>{erreur}</Erreur>
            </ContenuPage>
          </>
        )
      )}
    </Coque>
  );
}

function Contenu({
  session: lue,
  erreur,
  nomAgent,
  arrivee,
  ongletInitial,
}: {
  session: Session;
  erreur: string | null;
  nomAgent: (agent: Agent["id"]) => string;
  arrivee: Enchainement | null;
  ongletInitial: Onglet;
}) {
  // Rendue par **Terminer** : plus récente que la dernière lecture.
  const [close, setClose] = useState<Session | null>(null);
  const [refus, setRefus] = useState<string | null>(null);
  const session = close ?? lue;
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
    setRefus(null);
    terminerSession(session.id).then(setClose, (erreur: Error) => setRefus(erreur.message));
  };
  const titre = session.ticket != null ? `Session /implement #${session.ticket}` : `Session ${session.commande}`;
  const ouverte = session.etat === "ouverte";

  return (
    <>
      <EnTetePage
        ariane={
          <>
            <a href="/">Repos</a> / <a href={`/repos/${session.repo}`}>{session.repo}</a>
          </>
        }
        titre={titre}
        actions={
          ouverte ? (
            <>
              <BadgeActivite session={session} />
              <ConfirmerTerminer terminer={terminer} />
            </>
          ) : (
            <BadgeEtat etat={session.etat}>
              {precision(session) ? `${LIBELLES_ETAT_SESSION[session.etat]} (${precision(session)})` : undefined}
            </BadgeEtat>
          )
        }
      />
      <ContenuPage>
        {erreur && <Erreur>{erreur}</Erreur>}
        {refus && <Erreur>{refus}</Erreur>}
        {arrivee && (
          <Alert variant="agent" role="status">
            <LinkIcon aria-hidden />
            <AlertDescription className="text-foreground">
              <p>Session enchaînée : /implement #{session.ticket}</p>
            </AlertDescription>
          </Alert>
        )}
        <Card role="region" aria-label="Session">
          <dl className="flex flex-wrap gap-x-6 gap-y-3 px-4.5 py-3.5">
            <Meta cle="Titre">{session.titre}</Meta>
            <Meta cle="Agent">
              <BotIcon aria-hidden className="size-4 text-muted-foreground" />
              {nomAgent(session.agent)}
            </Meta>
            {modele && <Meta cle="Modèle">{modele}</Meta>}
            {session.branche && (
              <Meta cle="Branche" className="font-mono text-xs">
                <GitBranchIcon aria-hidden className="size-4 text-muted-foreground" />
                {session.branche}
              </Meta>
            )}
            <Meta cle="Commande">
              <code>{session.commande}</code>
            </Meta>
            <Meta cle="Durée" className="tabular-nums">
              {duree(session.debut, session.fin)}
            </Meta>
          </dl>
          <Chaine session={session} />
        </Card>
        <div className="grid min-w-0 gap-3">
          <div role="tablist" aria-label="Vues de la session" className="flex gap-1 border-b">
            {(["terminal", "codespace"] as const).map((o) => (
              <button
                key={o}
                type="button"
                role="tab"
                id={`onglet-${o}`}
                aria-controls={`panneau-${o}`}
                aria-selected={onglet === o}
                onClick={() => choisir(o)}
                className="-mb-px inline-flex items-center gap-2 border-b-2 border-transparent px-3.5 py-2.5 font-medium text-muted-foreground transition-colors hover:text-foreground aria-selected:border-attention aria-selected:text-foreground [&_svg]:size-4"
              >
                {o === "terminal" ? <SquareTerminalIcon aria-hidden /> : <CodeIcon aria-hidden />}
                {o === "terminal" ? "Terminal" : "Codespace"}
              </button>
            ))}
          </div>
          {/* Caché, pas démonté : le websocket reste ouvert et l’onglet garde la Main. */}
          <div
            role="tabpanel"
            id="panneau-terminal"
            aria-labelledby="onglet-terminal"
            hidden={onglet !== "terminal"}
            className="min-w-0"
          >
            {ouverte ? (
              <TerminalEnDirect
                id={session.id}
                reprendre={arrivee?.main ?? false}
                surRole={(ecriture) => (main.current = ecriture)}
              />
            ) : (
              <RelectureTerminal id={session.id} />
            )}
          </div>
          <div
            role="tabpanel"
            id="panneau-codespace"
            aria-labelledby="onglet-codespace"
            hidden={onglet !== "codespace"}
            className="min-w-0"
          >
            {codespaceVu && (
              <Suspense fallback={<p className="text-muted-foreground">Chargement du codespace…</p>}>
                {/* Remonté à la fermeture : la vue passe du clone en direct à l’instantané. */}
                <Codespace key={String(ouverte)} id={session.id} visible={onglet === "codespace"} enDirect={ouverte} />
              </Suspense>
            )}
          </div>
        </div>
      </ContenuPage>
    </>
  );
}

/** **Terminer** de l’en-tête : arrête l’agent après confirmation (Annuler et Échap ne font rien). */
function ConfirmerTerminer({ terminer }: { terminer: () => void }) {
  return (
    <AlertDialog>
      <AlertDialogTrigger asChild>
        <Button variant="destructive" size="sm">
          <SquareIcon aria-hidden />
          Terminer
        </Button>
      </AlertDialogTrigger>
      <AlertDialogContent className="max-w-md">
        <AlertDialogHeader>
          <AlertDialogTitle>Terminer la session ?</AlertDialogTitle>
          <AlertDialogDescription>
            L’agent sera arrêté et la session passera à l’état <strong className="text-foreground">Arrêtée</strong>.
            L’enregistrement et l’instantané restent consultables.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>Annuler</AlertDialogCancel>
          <AlertDialogAction className={buttonVariants({ variant: "destructive" })} onClick={terminer}>
            <SquareIcon aria-hidden />
            Terminer
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}

function Meta({ cle, className, children }: { cle: string; className?: string; children: ReactNode }) {
  return (
    <div className="grid min-w-0 gap-0.5">
      <dt className="text-[11px] tracking-[0.1em] text-faint uppercase">{cle}</dt>
      <dd className={cn("flex min-w-0 items-center gap-1.5 [overflow-wrap:anywhere]", className)}>{children}</dd>
    </div>
  );
}

/** Précédente et suivante d’une session enchaînée ; rien hors chaîne. */
function Chaine({ session }: { session: Pick<Session, "precedente" | "suivante"> }) {
  const [precedente, suivante] = [lienSession(session.precedente), lienSession(session.suivante)];
  if (!precedente && !suivante) return null;
  const lien = "inline-flex items-center gap-1 text-agent no-underline hover:underline [&_svg]:size-3.5";
  return (
    <p className="flex flex-wrap gap-x-4 gap-y-2 px-4.5 pb-3.5 text-[12.5px]">
      {precedente && (
        <a href={precedente} className={lien}>
          <ArrowLeftIcon aria-hidden />
          Session précédente
        </a>
      )}
      {suivante && (
        <a href={suivante} className={lien}>
          Session suivante
          <ArrowRightIcon aria-hidden />
        </a>
      )}
    </p>
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
