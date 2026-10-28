import { ChevronRightIcon } from "lucide-react";
import type { Agent, EtatSession, Session, SessionsDuRepo } from "./api";
import { Badge, Pastille } from "./components/ui/badge";
import { Card, CardHeader, CardTitle } from "./components/ui/card";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "./components/ui/collapsible";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "./components/ui/table";
import { Erreur, LIBELLES_ETAT_SESSION, libelleActivite, libelleModele } from "./commun";
import { ContenuPage, Coque, EnTetePage } from "./Coque";
import { cn } from "./lib/utils";
import { RAFRAICHISSEMENT_SESSION_MS, useRafraichi } from "./rafraichi";
import { type GroupeSessions, regrouperParRepo } from "./sessionsParRepo";

const VARIANTES_ETAT: Record<EtatSession, "agent" | "succes" | "pilote" | "neutre" | "echec"> = {
  ouverte: "agent",
  terminée: "succes",
  enchaînée: "pilote",
  arrêtée: "neutre",
  interrompue: "neutre",
  échouée: "echec",
};

/** Ce que chaque ligne affiche hors des données de la session elle-même. */
interface Colonnes {
  nomAgent: (id: Agent["id"]) => string;
  /** Colonne Modèle : seulement s’il y a au moins une session Cursor dans la page. */
  avecModele: boolean;
}

/** `/sessions` : toutes les sessions de l’instance, regroupées par repo (ceux qui attendent d’abord). */
export function VueSessions() {
  const { donnees, erreur } = useRafraichi<SessionsDuRepo>("/api/sessions", RAFRAICHISSEMENT_SESSION_MS);
  const agents = useRafraichi<{ agents: Agent[] }>("/api/agents");
  const sessions = donnees?.sessions ?? [];
  const colonnes: Colonnes = {
    nomAgent: (id) => agents.donnees?.agents.find((a) => a.id === id)?.nom ?? id,
    avecModele: sessions.some((s) => s.agent === "cursor"),
  };

  return (
    <Coque courant="sessions">
      <EnTetePage ariane="Toutes les sessions · regroupées par repo" titre="Sessions" />
      <ContenuPage>
        {erreur && <Erreur>{erreur}</Erreur>}
        {donnees &&
          (sessions.length === 0 ? (
            <p className="text-muted-foreground">Aucune session.</p>
          ) : (
            <>
              {regrouperParRepo(sessions).map((groupe) => (
                <Groupe key={groupe.repo} groupe={groupe} colonnes={colonnes} />
              ))}
              <p className="text-xs text-muted-foreground">
                Ordre : les repos qui attendent une réponse, puis ceux qui ont une session ouverte, puis les autres.
                Dans un repo : sessions ouvertes d’abord, puis les plus récentes.
              </p>
            </>
          ))}
      </ContenuPage>
    </Coque>
  );
}

function pluriel(n: number, mot: string): string {
  return `${n} ${mot}${n > 1 ? "s" : ""}`;
}

function Groupe({ groupe, colonnes }: { groupe: GroupeSessions; colonnes: Colonnes }) {
  const { repo, ouvertes, fermees, attendent } = groupe;
  const [owner, name] = repo.split("/");
  return (
    <Card
      role="region"
      aria-label={`Sessions de ${repo}`}
      className={cn("overflow-hidden", attendent > 0 && "border-attention/40")}
    >
      <CardHeader className={cn(fermees.length > 0 && ouvertes.length === 0 && "border-b-0")}>
        <CardTitle>
          <h2>
            <a href={`/repos/${repo}`} className="no-underline hover:underline [overflow-wrap:anywhere]">
              <span className="font-normal text-muted-foreground">{owner}/</span>
              {name}
            </a>
          </h2>
        </CardTitle>
        <span className="text-xs text-muted-foreground">{pluriel(ouvertes.length + fermees.length, "session")}</span>
        <span className="ml-auto">
          <PastilleGroupe groupe={groupe} />
        </span>
      </CardHeader>
      {ouvertes.length > 0 && <TableauSessions sessions={ouvertes} colonnes={colonnes} />}
      {fermees.length > 0 && (
        <Collapsible className={cn(ouvertes.length > 0 && "border-t")}>
          <CollapsibleTrigger className="group flex w-full cursor-pointer items-center gap-2 px-4.5 py-2.5 text-left text-sm text-muted-foreground hover:text-foreground">
            <ChevronRightIcon
              aria-hidden
              className="size-4 transition-transform group-data-[state=open]:rotate-90"
            />
            {pluriel(fermees.length, "session")} {fermees.length > 1 ? "fermées" : "fermée"}
          </CollapsibleTrigger>
          <CollapsibleContent className="border-t">
            <TableauSessions sessions={fermees} colonnes={colonnes} />
          </CollapsibleContent>
        </Collapsible>
      )}
    </Card>
  );
}

function PastilleGroupe({ groupe }: { groupe: GroupeSessions }) {
  if (groupe.attendent > 0) return <Badge variant="attention">{groupe.attendent} réponse attendue</Badge>;
  if (groupe.ouvertes.length > 0) return <Badge variant="agent">{groupe.ouvertes.length} ouverte</Badge>;
  return <Badge>aucune ouverte</Badge>;
}

const CELLULE_CARTE = "max-md:block max-md:p-0";

/** Tableau sur ordinateur ; sous `md`, chaque ligne devient une carte (même DOM, pas de doublon). */
function TableauSessions({ sessions, colonnes }: { sessions: Session[]; colonnes: Colonnes }) {
  return (
    <Table className="max-md:block">
      <TableHeader className="max-md:hidden">
        <TableRow className="hover:bg-transparent">
          <TableHead>Titre</TableHead>
          <TableHead>Agent</TableHead>
          {colonnes.avecModele && <TableHead>Modèle</TableHead>}
          <TableHead>Branche</TableHead>
          <TableHead>État</TableHead>
          <TableHead>Activité</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody className="max-md:grid max-md:gap-2.5 max-md:p-3">
        {sessions.map((s) => (
          <Ligne key={s.id} session={s} colonnes={colonnes} />
        ))}
      </TableBody>
    </Table>
  );
}

function Ligne({ session, colonnes }: { session: Session; colonnes: Colonnes }) {
  const modele = libelleModele(session);
  return (
    <TableRow className="max-md:grid max-md:grid-cols-[minmax(0,1fr)_auto] max-md:gap-x-2.5 max-md:gap-y-1.5 max-md:rounded-lg max-md:bg-card max-md:p-3.5 max-md:border!">
      <TableCell className={cn(CELLULE_CARTE, "min-w-0 font-semibold [overflow-wrap:anywhere]")}>
        <a href={session.url}>{session.titre}</a>
      </TableCell>
      <TableCell className={cn(CELLULE_CARTE, "max-md:col-span-full max-md:row-start-2 max-md:text-xs max-md:text-muted-foreground")}>
        {colonnes.nomAgent(session.agent)}
      </TableCell>
      {colonnes.avecModele && (
        <TableCell
          className={cn(
            CELLULE_CARTE,
            "font-mono text-xs max-md:col-span-full max-md:text-muted-foreground max-md:empty:hidden",
          )}
        >
          {modele}
        </TableCell>
      )}
      <TableCell
        className={cn(
          CELLULE_CARTE,
          "font-mono text-xs [overflow-wrap:anywhere] max-md:col-span-full max-md:text-muted-foreground md:max-w-60",
        )}
      >
        {session.branche ?? "—"}
      </TableCell>
      <TableCell className={cn(CELLULE_CARTE, "max-md:col-start-2 max-md:row-start-1")}>
        <Badge variant={VARIANTES_ETAT[session.etat]}>{LIBELLES_ETAT_SESSION[session.etat]}</Badge>
      </TableCell>
      <TableCell className={cn(CELLULE_CARTE, "max-md:col-span-full", session.etat !== "ouverte" && "max-md:hidden")}>
        <Activite session={session} />
      </TableCell>
    </TableRow>
  );
}

/** Seulement pour une session ouverte : orange quand l’agent attend, bleu quand il travaille. */
function Activite({ session }: { session: Session }) {
  if (session.etat !== "ouverte") return <span className="text-muted-foreground">—</span>;
  const vivant = session.activite !== "inconnue";
  const variante = session.activite === "attend" ? "attention" : session.activite === "travaille" ? "agent" : "neutre";
  return (
    <Badge variant={variante} className="whitespace-normal">
      <Pastille vivant={vivant} />
      {libelleActivite(session)}
    </Badge>
  );
}
