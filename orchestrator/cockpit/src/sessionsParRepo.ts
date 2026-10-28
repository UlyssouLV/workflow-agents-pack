import type { Session } from "./api";

export interface GroupeSessions {
  repo: string;
  /** Plus récentes d’abord. */
  ouvertes: Session[];
  /** Plus récentes d’abord. */
  fermees: Session[];
  /** Sessions ouvertes dont l’agent attend une réponse. */
  attendent: number;
}

/** Une entrée par repo : ceux qui attendent une réponse, puis ceux qui ont une session ouverte,
 * puis les autres ; à rang égal, la session la plus récente d’abord. */
export function regrouperParRepo(sessions: Session[]): GroupeSessions[] {
  const parRepo = new Map<string, Session[]>();
  for (const s of [...sessions].sort(plusRecenteDabord)) {
    parRepo.set(s.repo, [...(parRepo.get(s.repo) ?? []), s]);
  }
  const groupes = [...parRepo].map(([repo, liste]) => {
    const ouvertes = liste.filter((s) => s.etat === "ouverte");
    return {
      repo,
      ouvertes,
      fermees: liste.filter((s) => s.etat !== "ouverte"),
      attendent: ouvertes.filter((s) => s.activite === "attend").length,
    };
  });
  // Tri stable : l’ordre d’insertion (session la plus récente) départage un rang égal.
  return groupes.sort((a, b) => rang(a) - rang(b));
}

function plusRecenteDabord(a: Session, b: Session): number {
  return Date.parse(b.debut) - Date.parse(a.debut);
}

function rang(groupe: GroupeSessions): number {
  if (groupe.attendent > 0) return 0;
  return groupe.ouvertes.length > 0 ? 1 : 2;
}
