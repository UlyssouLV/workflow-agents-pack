import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { App } from "../src/App";
import { CLAUDE, CURSOR, session, simulerApi } from "./donnees";

describe("page Sessions", () => {
  it("`/sessions` liste toutes les sessions : repo, agent, branche, titre, état", async () => {
    simulerApi({
      "/api/agents": { agents: [CLAUDE, CURSOR] },
      "/api/sessions": {
        sessions: [
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
          session({ etat: "terminée", fin: "2026-10-17T09:10:00+00:00", titre: "Claude Code" }),
        ],
      },
    });

    render(<App chemin="/sessions" />);

    expect(await screen.findByRole("heading", { name: "Sessions" })).toBeInTheDocument();
    const lignes = within(screen.getByRole("table")).getAllByRole("row").slice(1);
    expect(within(lignes[0]).getByRole("link", { name: "Ouvre la version" })).toHaveAttribute(
      "href",
      "/sessions/20261017-100000-bbbbbb",
    );
    expect(lignes[0]).toHaveTextContent("o/autre");
    expect(lignes[0]).toHaveTextContent("Cursor");
    expect(lignes[0]).toHaveTextContent("feat");
    expect(lignes[0]).toHaveTextContent("Ouverte");
    expect(lignes[0]).toHaveTextContent("Réponse attendue — grilling");
    expect(within(lignes[1]).getByRole("link", { name: "Claude Code" })).toHaveAttribute(
      "href",
      "/sessions/20261017-090000-abcdef",
    );
    expect(lignes[1]).toHaveTextContent("o/r");
    expect(lignes[1]).toHaveTextContent("Claude Code");
    expect(lignes[1]).toHaveTextContent("v0.3.0-registry");
    expect(lignes[1]).toHaveTextContent("Terminée");
  });

  it("affiche Auto ou l’ID du modèle pour Cursor, rien pour Claude", async () => {
    simulerApi({
      "/api/agents": { agents: [CLAUDE, CURSOR] },
      "/api/sessions": {
        sessions: [
          session({ agent: "cursor", modele: "composer-2", titre: "Cursor" }),
          session({
            agent: "cursor",
            id: "20261017-100000-cccccc",
            url: "/sessions/c",
            modele: null,
            titre: "Libre",
          }),
          session({ etat: "terminée", fin: "2026-10-17T09:10:00+00:00", titre: "Claude Code" }),
        ],
      },
    });

    render(<App chemin="/sessions" />);

    const lignes = within(await screen.findByRole("table")).getAllByRole("row").slice(1);
    expect(lignes[0]).toHaveTextContent("composer-2");
    expect(lignes[1]).toHaveTextContent("Auto");
    expect(lignes[2]).not.toHaveTextContent("Auto");
    expect(lignes[2]).not.toHaveTextContent("composer-2");
  });

  it("aucune session", async () => {
    simulerApi({ "/api/agents": { agents: [CLAUDE] }, "/api/sessions": { sessions: [] } });

    render(<App chemin="/sessions" />);

    expect(await screen.findByText("Aucune session.")).toBeInTheDocument();
  });
});
