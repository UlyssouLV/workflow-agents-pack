import { CircleUserRoundIcon, FolderIcon, LogOutIcon, MenuIcon, SquareTerminalIcon } from "lucide-react";
import { useEffect, useId, useRef, useState, type ReactNode } from "react";
import type { Agent, Auth, Liste, SessionsDuRepo } from "./api";
import { deconnecterCockpit } from "./api";
import embleme from "./assets/embleme.png";
import { Alert, AlertDescription } from "./components/ui/alert";
import { Badge, Pastille } from "./components/ui/badge";
import { Button } from "./components/ui/button";
import { Sheet, SheetContent, SheetDescription, SheetTitle, SheetTrigger } from "./components/ui/sheet";
import { Toaster } from "./components/ui/sonner";
import { cn } from "./lib/utils";
import { demanderPermissionNotifications, notifierStops } from "./notifications";
import { RAFRAICHISSEMENT_SESSION_MS, useRafraichi } from "./rafraichi";

const TITRE_ONGLET = "HéphaïstOS";

const MESSAGES_AUTH: Partial<Record<Auth["etat"], string>> = {
  sans_token: "GitHub non connecté",
  token_refuse: "Token refusé par GitHub",
  injoignable: "GitHub injoignable",
};

export type PageCoque = "repos" | "sessions";

/** Toutes les pages sauf `/login` : barre latérale (panneau derrière un menu sur téléphone) et contenu. */
export function Coque({ courant, children }: { courant: PageCoque; children: ReactNode }) {
  const { donnees } = useRafraichi<SessionsDuRepo>("/api/sessions", RAFRAICHISSEMENT_SESSION_MS);
  const liste = useRafraichi<Liste>("/api/repos");
  const n = (donnees?.sessions ?? []).filter((s) => s.etat === "ouverte" && s.activite === "attend").length;
  const [ouvert, setOuvert] = useState(false);
  useTitreEtNotifications(n, liste.donnees);
  const navigation = <Navigation courant={courant} attendues={n} liste={liste.donnees} />;

  return (
    <Sheet open={ouvert} onOpenChange={setOuvert}>
      <div className="min-h-dvh md:grid md:grid-cols-[252px_minmax(0,1fr)]">
        <div className="sticky top-0 z-30 flex items-center gap-2.5 border-b bg-sidebar py-2.5 pr-4 pl-2 md:hidden">
          <SheetTrigger asChild>
            <Button variant="ghost" size="icon" aria-label="Ouvrir la navigation">
              <MenuIcon />
            </Button>
          </SheetTrigger>
          <img src={embleme} alt="" className="size-7 rounded-md" />
          <MotSymbole className="text-base" />
          <Badge variant={n > 0 ? "attention" : "neutre"} asChild className="ml-auto">
            <a href="/sessions">{n} réponse(s) attendue(s)</a>
          </Badge>
        </div>
        <aside className="sticky top-0 hidden h-dvh border-r bg-sidebar md:block">{navigation}</aside>
        <SheetContent side="left" fermer="Fermer la navigation" className="md:hidden">
          <SheetTitle className="sr-only">Navigation</SheetTitle>
          <SheetDescription className="sr-only">Pages du cockpit, agents et compte GitHub.</SheetDescription>
          {navigation}
        </SheetContent>
        <main className="min-w-0">{children}</main>
      </div>
      <Toaster position="bottom-right" />
    </Sheet>
  );
}

/** Titre d’onglet `(n) HéphaïstOS` et notifications des arrêts du pilote. */
function useTitreEtNotifications(n: number, liste: Liste | null) {
  const [permission, setPermission] = useState<NotificationPermission | null>(
    typeof Notification === "undefined" ? null : Notification.permission,
  );
  const vus = useRef(new Map<string, string>());
  useEffect(() => {
    document.title = n > 0 ? `(${n}) ${TITRE_ONGLET}` : TITRE_ONGLET;
  }, [n]);
  useEffect(() => {
    void demanderPermissionNotifications().then((p) => p && setPermission(p));
  }, []);
  useEffect(() => {
    if (permission !== "granted" || !liste) return;
    notifierStops(liste.repos, vus.current);
  }, [permission, liste]);
}

function MotSymbole({ className }: { className?: string }) {
  return (
    <span className={cn("leading-none font-bold tracking-tight", className)}>
      Héphaïst<b className="text-attention">OS</b>
    </span>
  );
}

function Navigation({ courant, attendues, liste }: { courant: PageCoque; attendues: number; liste: Liste | null }) {
  const idAttendues = useId();
  const lien = (page: PageCoque) =>
    cn(
      "flex items-center gap-2.5 rounded-md px-2.5 py-2 font-medium text-muted-foreground no-underline hover:bg-surface-2 hover:text-foreground hover:no-underline [&_svg]:size-4",
      courant === page && "bg-surface-3 text-foreground",
    );
  return (
    <nav aria-label="Navigation" className="flex h-full flex-col gap-5 overflow-y-auto px-3.5 py-4.5">
      <a href="/" aria-label="HéphaïstOS" className="flex items-center gap-2.5 px-1 no-underline hover:no-underline">
        <img src={embleme} alt="" className="size-10 rounded-[10px]" />
        <span>
          <MotSymbole className="text-[19px]" />
          <small className="mt-1 block text-[9.5px] tracking-[0.22em] text-muted-foreground">
            ORCHESTRATE · BUILD · DEPLOY
          </small>
        </span>
      </a>
      <div className="h-px bg-border" />
      <div className="grid gap-0.5">
        <a href="/" className={lien("repos")} aria-current={courant === "repos" ? "page" : undefined}>
          <FolderIcon aria-hidden />
          Repos
        </a>
        <a
          href="/sessions"
          className={lien("sessions")}
          aria-current={courant === "sessions" ? "page" : undefined}
          aria-describedby={idAttendues}
        >
          <SquareTerminalIcon aria-hidden />
          Sessions
          {attendues > 0 && (
            <span
              aria-hidden
              className="ml-auto min-w-[22px] rounded-full bg-attention px-1.5 text-center text-xs font-bold text-attention-foreground"
            >
              {attendues}
            </span>
          )}
        </a>
        <span id={idAttendues} className="sr-only">
          {attendues} réponse(s) attendue(s)
        </span>
      </div>
      {liste && <EncartAgents agents={liste.agents} />}
      <div className="mt-auto grid gap-2.5 border-t px-2.5 pt-3 text-[12.5px]">
        {liste && <EtatGithub auth={liste.auth} />}
        <Button variant="ghost" size="sm" className="justify-self-start" onClick={() => void deconnecterCockpit()}>
          <LogOutIcon aria-hidden />
          Déconnexion
        </Button>
      </div>
    </nav>
  );
}

/** Claude Code / Cursor connectés ou non, avec la commande à lancer sur l’hôte. */
function EncartAgents({ agents }: { agents: Agent[] }) {
  const id = useId();
  return (
    <section aria-labelledby={id}>
      <h2 id={id} className="mb-1.5 px-2.5 text-[10.5px] font-medium tracking-[0.14em] text-faint uppercase">
        Agents
      </h2>
      <ul className="grid gap-1.5 px-2.5 text-[13px]">
        {agents.map((agent) => (
          <li key={agent.id}>
            <span className="flex items-center gap-2">
              <Pastille className={agent.connecte ? "text-succes" : "text-attention"} />
              {agent.nom}
              <span className="text-xs text-muted-foreground">
                · {agent.connecte ? "Connecté" : "Non connecté"}
              </span>
            </span>
            {!agent.connecte && (
              <span className="block pl-4 text-[11.5px] text-muted-foreground">
                lancez <code className="break-all text-foreground">{agent.commande}</code> sur l’hôte
              </span>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}

/** Compte GitHub de l’instance, ou bandeau quand elle ne peut pas lire GitHub. */
function EtatGithub({ auth }: { auth: Auth }) {
  if (auth.etat === "connecte") {
    return (
      <p className="flex items-center gap-2 text-muted-foreground">
        <CircleUserRoundIcon aria-hidden className="size-4" />
        <span>
          GitHub : <strong className="font-medium text-foreground">{auth.compte}</strong>
        </span>
      </p>
    );
  }
  return (
    <Alert variant="attention" className="px-3 py-2 text-xs">
      <AlertDescription className="text-foreground">
        <p>
          {MESSAGES_AUTH[auth.etat]} : lancez <code>sudo wap-runtime auth</code> sur l’hôte.
        </p>
      </AlertDescription>
    </Alert>
  );
}

/** En-tête collant d’une page : fil d’Ariane, titre, actions. */
export function EnTetePage({
  ariane,
  titre,
  actions,
}: {
  ariane?: ReactNode;
  titre: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <header className="sticky top-[53px] z-20 flex flex-wrap items-center gap-x-4 gap-y-3 border-b bg-background/90 px-4 py-4 backdrop-blur-sm md:top-0 md:px-7">
      <div className="min-w-0 flex-1">
        {ariane && (
          <div className="text-[11px] font-medium tracking-[0.14em] text-muted-foreground uppercase [&_a]:text-muted-foreground [&_a:hover]:text-foreground">
            {ariane}
          </div>
        )}
        <h1 className="text-xl leading-tight [overflow-wrap:anywhere] md:text-2xl">{titre}</h1>
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </header>
  );
}

/** Corps d’une page sous son en-tête. */
export function ContenuPage({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={cn("grid max-w-[1320px] gap-5 px-4 pt-6 pb-12 md:px-7", className)}>{children}</div>;
}
