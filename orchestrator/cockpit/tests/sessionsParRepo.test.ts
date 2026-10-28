import { describe, expect, it } from "vitest";
import { regrouperParRepo } from "../src/sessionsParRepo";
import { session } from "./donnees";

const ids = (sessions: { id: string }[]) => sessions.map((s) => s.id);

describe("regrouperParRepo", () => {
  it("met d’abord les repos qui attendent une réponse, puis ceux qui ont une session ouverte, puis les autres", () => {
    const groupes = regrouperParRepo([
      session({ id: "a1", repo: "o/fermes", etat: "terminée", debut: "2026-10-17T12:00:00+00:00" }),
      session({ id: "b1", repo: "o/ouvert", etat: "ouverte", activite: "travaille" }),
      session({ id: "c1", repo: "o/attend", etat: "ouverte", activite: "attend" }),
    ]);

    expect(groupes.map((g) => g.repo)).toEqual(["o/attend", "o/ouvert", "o/fermes"]);
  });

  it("à rang égal, garde d’abord le repo à la session la plus récente", () => {
    const groupes = regrouperParRepo([
      session({ id: "a1", repo: "o/ancien", etat: "terminée", debut: "2026-10-17T08:00:00+00:00" }),
      session({ id: "b1", repo: "o/recent", etat: "terminée", debut: "2026-10-17T10:00:00+00:00" }),
    ]);

    expect(groupes.map((g) => g.repo)).toEqual(["o/recent", "o/ancien"]);
  });

  it("dans un repo, sépare les ouvertes des fermées, chacune des plus récentes aux plus anciennes", () => {
    const [groupe] = regrouperParRepo([
      session({ id: "f-vieille", etat: "terminée", debut: "2026-10-17T07:00:00+00:00" }),
      session({ id: "o-vieille", etat: "ouverte", debut: "2026-10-17T08:00:00+00:00" }),
      session({ id: "f-recente", etat: "arrêtée", debut: "2026-10-17T11:00:00+00:00" }),
      session({ id: "o-recente", etat: "ouverte", debut: "2026-10-17T09:00:00+00:00" }),
    ]);

    expect(groupe.repo).toBe("o/r");
    expect(ids(groupe.ouvertes)).toEqual(["o-recente", "o-vieille"]);
    expect(ids(groupe.fermees)).toEqual(["f-recente", "f-vieille"]);
  });

  it("compte les sessions ouvertes qui attendent une réponse", () => {
    const [groupe] = regrouperParRepo([
      session({ id: "a", etat: "ouverte", activite: "attend" }),
      session({ id: "b", etat: "ouverte", activite: "travaille" }),
      session({ id: "c", etat: "terminée", activite: "attend" }),
    ]);

    expect(groupe.attendent).toBe(1);
  });

  it("aucune session, aucun groupe", () => {
    expect(regrouperParRepo([])).toEqual([]);
  });
});
