import { ClockIcon, HandIcon, TriangleAlertIcon } from "lucide-react";
import type { MouseEvent, ReactNode } from "react";
import type { Liste, Repo, VersionResume } from "./api";
import { Alert, AlertDescription } from "./components/ui/alert";
import { Badge } from "./components/ui/badge";
import { Card } from "./components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "./components/ui/table";
import { BadgePause, BadgePilote, BadgeSession, heure, nomAffiche } from "./commun";
import { ContenuPage, Coque, EnTetePage } from "./Coque";
import { cn } from "./lib/utils";
import { useRafraichi } from "./rafraichi";

/** `/` : une ligne par repo lié, ceux qui attendent quelqu’un en tête ; des cartes sur téléphone. */
export function VueListe() {
  const { donnees, erreur } = useRafraichi<Liste>("/api/repos");
  const repos = donnees?.repos ?? [];

  return (
    <Coque courant="repos">
      <EnTetePage
        ariane={donnees && `Instance · ${repos.length} ${pluriel(repos.length, "repo lié", "repos liés")}`}
        titre="Repos"
        actions={repos.length > 0 && <ReluA repos={repos} />}
      />
      <ContenuPage>
        {erreur && <Erreur>Lecture impossible : {erreur}</Erreur>}
        {donnees && <Contenu liste={donnees} />}
      </ContenuPage>
    </Coque>
  );
}

function pluriel(n: number, un: string, plusieurs: string): string {
  return n > 1 ? plusieurs : un;
}

function ReluA({ repos }: { repos: Repo[] }) {
  const dernier = repos.map((r) => r.lu_a).reduce((a, b) => (Date.parse(a) >= Date.parse(b) ? a : b));
  return (
    <span className="flex items-center gap-1.5 text-[12.5px] text-muted-foreground tabular-nums [&_svg]:size-4">
      <ClockIcon aria-hidden />
      Relu à {heure(dernier)}
    </span>
  );
}

function Erreur({ children }: { children: ReactNode }) {
  return (
    <Alert variant="destructive">
      <TriangleAlertIcon aria-hidden />
      <AlertDescription className="text-foreground">
        <p>{children}</p>
      </AlertDescription>
    </Alert>
  );
}

function Contenu({ liste }: { liste: Liste }) {
  return (
    <>
      {liste.erreur && <Erreur>Registry : {liste.erreur}</Erreur>}
      {!liste.erreur && liste.repos.length === 0 && (
        <p className="text-muted-foreground">
          Aucun repo lié. Ajoutez-en un sur l’hôte : <code className="text-foreground">sudo wap-runtime repo add owner/name</code>
        </p>
      )}
      {liste.repos.length > 0 && (
        <>
          <Resume repos={liste.repos} />
          <TableauRepos repos={trier(liste.repos)} />
          <p className="text-[12.5px] text-muted-foreground">
            Ajouter un repo : <code className="text-foreground">sudo wap-runtime repo add owner/name</code> sur l’hôte.
          </p>
        </>
      )}
    </>
  );
}

/** « Humain requis » d’abord ; sinon l’ordre du registry. */
function trier(repos: Repo[]): Repo[] {
  return [...repos].sort((a, b) => Number(b.humain_requis) - Number(a.humain_requis));
}

/** À vous d’agir : une étape humaine ou une session qui attend votre réponse. */
function attendVous(repo: Repo): boolean {
  return repo.humain_requis || repo.session?.activite === "attend";
}

function Resume({ repos }: { repos: Repo[] }) {
  const attendent = repos.filter(attendVous).length;
  const auTravail = repos.filter((r) => r.session?.activite === "travaille").length;
  const enPilote = repos.filter((r) => r.pilote).length;
  const compteurs = [
    {
      n: attendent,
      libelle: pluriel(attendent, "attend une action de votre part", "attendent une action de votre part"),
      couleur: "text-attention",
      encadre: attendent > 0 && "border-attention/45 shadow-[0_0_18px_-4px_var(--attention)]",
    },
    { n: auTravail, libelle: pluriel(auTravail, "agent au travail", "agents au travail"), couleur: "text-agent" },
    { n: enPilote, libelle: pluriel(enPilote, "repo en pilote", "repos en pilote"), couleur: "text-pilote" },
  ];
  return (
    <ul aria-label="Résumé" className="flex flex-wrap gap-2.5">
      {compteurs.map(({ n, libelle, couleur, encadre }) => (
        <li
          key={libelle}
          className={cn("flex min-w-0 items-center gap-2.5 rounded-lg border bg-card px-3.5 py-2.5", encadre)}
        >
          <b className={cn("text-[22px] leading-none tabular-nums", couleur)}>{n}</b>{" "}
          <span className="max-w-[11rem] text-[12.5px] text-muted-foreground">{libelle}</span>
        </li>
      ))}
    </ul>
  );
}

/** Tableau sur ordinateur ; sous `md`, chaque ligne devient une carte (même DOM, pas de doublon). */
function TableauRepos({ repos }: { repos: Repo[] }) {
  return (
    <Card role="region" aria-label="Repos liés" className="max-md:border-0 max-md:bg-transparent">
      <Table className="max-md:block">
        <TableHeader className="max-md:hidden">
          <TableRow className="hover:bg-transparent">
            <TableHead>Repo</TableHead>
            <TableHead>Version ouverte</TableHead>
            <TableHead>Progression</TableHead>
            <TableHead>Étape</TableHead>
            <TableHead>Lu à</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody className="max-md:grid max-md:gap-2.5">
          {repos.map((repo) => (
            <Ligne key={repo.slug} repo={repo} />
          ))}
        </TableBody>
      </Table>
    </Card>
  );
}

const CELLULE_CARTE = "max-md:col-span-full max-md:block max-md:p-0";

function Ligne({ repo }: { repo: Repo }) {
  const href = `/repos/${repo.slug}`;
  // Les liens de la ligne (nom, session, version) gardent leur cible ; le reste ouvre le détail.
  const ouvrir = (e: MouseEvent) => {
    if ((e.target as HTMLElement).closest("a")) return;
    window.location.assign(href);
  };
  return (
    <TableRow
      onClick={ouvrir}
      className={cn(
        "cursor-pointer max-md:grid max-md:grid-cols-[minmax(0,1fr)_auto] max-md:gap-2.5 max-md:rounded-lg max-md:bg-card max-md:p-3.5 max-md:border!",
        repo.humain_requis &&
          "md:[&>td:first-child]:shadow-[inset_2px_0_0_var(--attention)] max-md:border-attention/45 max-md:shadow-[0_0_18px_-4px_var(--attention)]",
      )}
    >
      <TableCell className="min-w-0 max-md:col-span-1 max-md:block max-md:p-0">
        <a href={href} className="font-semibold [overflow-wrap:anywhere]">
          {nomAffiche(repo)}
        </a>
        <Badges repo={repo} />
      </TableCell>
      {repo.erreur ? (
        <TableCell colSpan={3} className={CELLULE_CARTE}>
          <Badge variant="echec" className="whitespace-normal">
            <TriangleAlertIcon aria-hidden />
            {repo.erreur}
          </Badge>
        </TableCell>
      ) : (
        <>
          <TableCell className={cn(CELLULE_CARTE, "max-md:empty:hidden")}>
            {repo.versions.map((v) => (
              <div key={v.numero}>
                <a href={v.url} className="no-underline hover:underline">
                  <span className="mr-1.5 font-mono text-[12.5px] text-muted-foreground">#{v.numero}</span>
                  {v.titre}
                </a>
              </div>
            ))}
            {repo.versions.length === 0 && <span className="text-muted-foreground max-md:hidden">—</span>}
          </TableCell>
          <TableCell className={cn(CELLULE_CARTE, "max-md:empty:hidden")}>
            {repo.versions.map((v) => (
              <Progression key={v.numero} version={v} />
            ))}
          </TableCell>
          <TableCell className={CELLULE_CARTE}>
            <Etape repo={repo} />
          </TableCell>
        </>
      )}
      <TableCell className="text-[12.5px] whitespace-nowrap text-muted-foreground tabular-nums max-md:col-start-2 max-md:row-start-1 max-md:block max-md:p-0">
        {heure(repo.lu_a)}
      </TableCell>
    </TableRow>
  );
}

function Badges({ repo }: { repo: Repo }) {
  if (!repo.pilote && !repo.session) return null;
  return (
    <div className="mt-1.5 flex flex-wrap gap-1.5">
      {repo.pilote && <BadgePilote />}
      {repo.pilote && repo.pilote_stop && <BadgePause stop={repo.pilote_stop} />}
      {repo.session && <BadgeSession session={repo.session} />}
    </div>
  );
}

function Progression({ version }: { version: VersionResume }) {
  const { completed, total } = version.progression;
  return (
    <div className="flex min-w-[120px] items-center gap-2.5">
      <div
        role="progressbar"
        aria-label={`Progression #${version.numero}`}
        aria-valuemin={0}
        aria-valuemax={total}
        aria-valuenow={completed}
        className="h-1.5 flex-1 overflow-hidden rounded-full bg-surface-3"
      >
        <div
          className="h-full rounded-[inherit] bg-foreground"
          style={{ width: `${total > 0 ? (completed / total) * 100 : 0}%` }}
        />
      </div>
      <span className="text-[12.5px] text-muted-foreground tabular-nums">
        {completed}/{total}
      </span>
    </div>
  );
}

function Etape({ repo }: { repo: Repo }) {
  if (repo.etape === null) return null;
  if (!repo.etape.humain) return <span className="text-muted-foreground">{repo.etape.libelle}</span>;
  return (
    <Badge variant="attention" className="whitespace-normal">
      <HandIcon aria-hidden />
      {repo.etape.libelle} · intervention humaine requise
    </Badge>
  );
}
