import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { App } from "../src/App";
import { CLAUDE, CURSOR, session, simulerApi } from "./donnees";

function lignes(conteneur: HTMLElement) {
  return within(within(conteneur).getByRole("table")).getAllByRole("row").slice(1);
}

describe("page Sessions", () => {
  it("regroupe par repo : le repo qui attend une réponse d’abord, son en-tête et sa pastille", async () => {
    simulerApi({
      "/api/agents": { agents: [CLAUDE, CURSOR] },
      "/api/sessions": {
        sessions: [
          session({ etat: "terminée", fin: "2026-10-17T09:10:00+00:00", debut: "2026-10-17T11:00:00+00:00" }),
          session({
            id: "20261017-100000-bbbbbb",
            url: "/sessions/20261017-100000-bbbbbb",
            repo: "o/autre",
            agent: "cursor",
            branche: "feat",
            titre: "Ouvre la version",
            etat: "ouverte",
            activite: "attend",
            skill: "grilling",
          }),
        ],
      },
    });

    render(<App chemin="/sessions" />);

    expect(await screen.findByRole("heading", { name: "Sessions" })).toBeInTheDocument();
    const [autre, r] = await screen.findAllByRole("region", { name: /^Sessions de / });
    expect(autre).toHaveAccessibleName("Sessions de o/autre");
    expect(r).toHaveAccessibleName("Sessions de o/r");

    expect(within(autre).getByRole("link", { name: "o/autre" })).toHaveAttribute("href", "/repos/o/autre");
    expect(autre).toHaveTextContent("1 session");
    expect(within(autre).getByText("1 réponse attendue")).toBeInTheDocument();
    const [ligne] = lignes(autre);
    expect(within(ligne).getByRole("link", { name: "Ouvre la version" })).toHaveAttribute(
      "href",
      "/sessions/20261017-100000-bbbbbb",
    );
    expect(ligne).toHaveTextContent("Cursor");
    expect(ligne).toHaveTextContent("feat");
    expect(ligne).toHaveTextContent("Ouverte");
    expect(ligne).toHaveTextContent("Réponse attendue — grilling");

    expect(within(r).getByRole("link", { name: "o/r" })).toHaveAttribute("href", "/repos/o/r");
    expect(within(r).getByText("aucune ouverte")).toBeInTheDocument();
  });

  it("montre « N ouverte » sur un repo dont une session travaille", async () => {
    simulerApi({
      "/api/agents": { agents: [CLAUDE] },
      "/api/sessions": { sessions: [session({ activite: "travaille" })] },
    });

    render(<App chemin="/sessions" />);

    const groupe = await screen.findByRole("region", { name: "Sessions de o/r" });
    expect(within(groupe).getByText("1 ouverte")).toBeInTheDocument();
    expect(lignes(groupe)[0]).toHaveTextContent("Travaille");
  });

  it("replie les sessions fermées, dépliables au clic (un vrai bouton, donc au clavier)", async () => {
    simulerApi({
      "/api/agents": { agents: [CLAUDE] },
      "/api/sessions": {
        sessions: [
          session({ titre: "En cours", activite: "travaille" }),
          session({
            id: "20261016-090000-aaaaaa",
            url: "/sessions/20261016-090000-aaaaaa",
            titre: "Finie",
            etat: "terminée",
            debut: "2026-10-16T09:00:00+00:00",
          }),
          session({
            id: "20261015-090000-aaaaaa",
            url: "/sessions/20261015-090000-aaaaaa",
            titre: "Arrêtée",
            etat: "arrêtée",
            debut: "2026-10-15T09:00:00+00:00",
          }),
        ],
      },
    });

    render(<App chemin="/sessions" />);

    const groupe = await screen.findByRole("region", { name: "Sessions de o/r" });
    expect(groupe).toHaveTextContent("3 sessions");
    expect(within(groupe).getByRole("link", { name: "En cours" })).toBeInTheDocument();
    expect(within(groupe).queryByRole("link", { name: "Finie" })).toBeNull();
    const bouton = within(groupe).getByRole("button", { name: "2 sessions fermées" });
    expect(bouton).toHaveAttribute("aria-expanded", "false");

    fireEvent.click(bouton);
    expect(bouton).toHaveAttribute("aria-expanded", "true");
    const fermees = within(groupe).getAllByRole("table")[1];
    const [finie, arretee] = within(fermees).getAllByRole("row").slice(1);
    expect(within(finie).getByRole("link", { name: "Finie" })).toHaveAttribute(
      "href",
      "/sessions/20261016-090000-aaaaaa",
    );
    expect(finie).toHaveTextContent("Terminée");
    expect(finie).not.toHaveTextContent("Travaille");
    expect(arretee).toHaveTextContent("Arrêtée");

    fireEvent.click(bouton);
    expect(within(groupe).queryByRole("link", { name: "Finie" })).toBeNull();
    expect(bouton.tagName).toBe("BUTTON");
  });

  it("affiche Auto ou l’ID du modèle pour Cursor, rien pour Claude", async () => {
    simulerApi({
      "/api/agents": { agents: [CLAUDE, CURSOR] },
      "/api/sessions": {
        sessions: [
          session({ agent: "cursor", modele: "composer-2", titre: "Cursor" }),
          session({
            agent: "cursor",
            id: "20261017-080000-cccccc",
            url: "/sessions/c",
            modele: null,
            titre: "Libre",
            debut: "2026-10-17T08:00:00+00:00",
          }),
          session({
            id: "20261017-070000-dddddd",
            url: "/sessions/d",
            titre: "Claude Code",
            debut: "2026-10-17T07:00:00+00:00",
          }),
        ],
      },
    });

    render(<App chemin="/sessions" />);

    const groupe = await screen.findByRole("region", { name: "Sessions de o/r" });
    expect(within(groupe).getByRole("columnheader", { name: "Modèle" })).toBeInTheDocument();
    const [cursor, libre, claude] = lignes(groupe);
    expect(cursor).toHaveTextContent("composer-2");
    expect(libre).toHaveTextContent("Auto");
    expect(claude).not.toHaveTextContent("Auto");
    expect(claude).not.toHaveTextContent("composer-2");
  });

  it("sans session Cursor, pas de colonne Modèle", async () => {
    simulerApi({
      "/api/agents": { agents: [CLAUDE] },
      "/api/sessions": { sessions: [session({ titre: "Claude Code" })] },
    });

    render(<App chemin="/sessions" />);

    expect(await screen.findByRole("columnheader", { name: "Agent" })).toBeInTheDocument();
    expect(screen.queryByRole("columnheader", { name: "Modèle" })).toBeNull();
  });

  it("aucune session", async () => {
    simulerApi({ "/api/agents": { agents: [CLAUDE] }, "/api/sessions": { sessions: [] } });

    render(<App chemin="/sessions" />);

    expect(await screen.findByText("Aucune session.")).toBeInTheDocument();
  });
});
