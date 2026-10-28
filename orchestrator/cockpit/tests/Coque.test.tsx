import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { App } from "../src/App";
import { Coque } from "../src/Coque";
import { CLAUDE, CURSOR, liste, session, simulerApi } from "./donnees";

function attend(id: string, repo = "o/r") {
  return session({ id, repo, etat: "ouverte", activite: "attend" });
}

async function navigation() {
  return within(await screen.findByRole("navigation", { name: "Navigation" }));
}

describe("coque HéphaïstOS", () => {
  it("montre la marque, Repos et Sessions, la page courante marquée", async () => {
    simulerApi({ "/api/repos": liste(), "/api/sessions": { sessions: [] } });

    render(
      <Coque courant="sessions">
        <p>contenu</p>
      </Coque>,
    );

    const nav = await navigation();
    expect(nav.getByRole("link", { name: "HéphaïstOS" })).toHaveAttribute("href", "/");
    expect(nav.getByRole("link", { name: "Repos" })).toHaveAttribute("href", "/");
    expect(nav.getByRole("link", { name: "Repos" })).not.toHaveAttribute("aria-current");
    expect(nav.getByRole("link", { name: "Sessions" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("main")).toHaveTextContent("contenu");
  });

  it("compte les réponses attendues des sessions ouvertes, dans la navigation et le titre d’onglet", async () => {
    simulerApi({
      "/api/repos": liste(),
      "/api/sessions": {
        sessions: [
          attend("20261017-100000-aaaaaa"),
          attend("20261017-100000-bbbbbb", "o/autre"),
          session({ id: "20261017-110000-cccccc", etat: "ouverte", activite: "travaille" }),
          session({ id: "20261017-080000-dddddd", etat: "terminée", activite: "attend" }),
        ],
      },
    });

    render(<Coque courant="repos">{null}</Coque>);

    expect(await screen.findByRole("link", { name: "2 réponse(s) attendue(s)" })).toHaveAttribute(
      "href",
      "/sessions",
    );
    expect((await navigation()).getByRole("link", { name: "Sessions" })).toHaveAccessibleDescription(
      "2 réponse(s) attendue(s)",
    );
    await waitFor(() => expect(document.title).toBe("(2) HéphaïstOS"));
  });

  it("titre d’onglet « HéphaïstOS » sans réponse attendue", async () => {
    simulerApi({ "/api/repos": liste(), "/api/sessions": { sessions: [] } });

    render(<Coque courant="repos">{null}</Coque>);

    await screen.findByRole("link", { name: "0 réponse(s) attendue(s)" });
    expect(document.title).toBe("HéphaïstOS");
  });

  describe("encart Agents", () => {
    async function agents() {
      return within(await screen.findByRole("region", { name: "Agents" }));
    }

    it("dit quel agent est connecté, et la commande à lancer pour l’autre", async () => {
      simulerApi({ "/api/repos": liste() });

      render(<Coque courant="repos">{null}</Coque>);

      const [claude, cursor] = (await agents()).getAllByRole("listitem");
      expect(claude).toHaveTextContent(/Claude Code\W+Connecté/);
      expect(claude).not.toHaveTextContent("sudo");
      expect(cursor).toHaveTextContent(/Cursor\W+Non connecté/);
      expect(cursor).toHaveTextContent("… | sudo wap-runtime auth agent --with-token");
    });

    it("donne la commande de chaque agent non connecté", async () => {
      simulerApi({
        "/api/repos": liste({ agents: [{ ...CLAUDE, connecte: false }, { ...CURSOR, connecte: true }] }),
      });

      render(<Coque courant="repos">{null}</Coque>);

      const [claude, cursor] = (await agents()).getAllByRole("listitem");
      expect(claude).toHaveTextContent(/Claude Code\W+Non connecté/);
      expect(claude).toHaveTextContent("sudo wap-runtime auth claude");
      expect(cursor).toHaveTextContent(/Cursor\W+Connecté/);
      expect(cursor).not.toHaveTextContent("sudo");
    });
  });

  describe("état GitHub", () => {
    it("montre le compte GitHub connecté, sans bandeau", async () => {
      simulerApi({ "/api/repos": liste() });

      render(<Coque courant="repos">{null}</Coque>);

      expect(await (await navigation()).findByText("octocat")).toBeInTheDocument();
      expect(screen.queryByRole("alert")).toBeNull();
    });

    it.each([
      ["sans_token", /non connecté/i],
      ["token_refuse", /token refusé/i],
      ["injoignable", /injoignable/i],
    ] as const)("affiche le bandeau d’erreur quand l’état est %s", async (etat, motif) => {
      simulerApi({ "/api/repos": liste({ auth: { etat, compte: null } }) });

      render(<Coque courant="repos">{null}</Coque>);

      const bandeau = await screen.findByRole("alert");
      expect(bandeau).toHaveTextContent(motif);
      expect(bandeau).toHaveTextContent("sudo wap-runtime auth");
    });
  });

  it("propose la déconnexion", async () => {
    simulerApi({ "/api/repos": liste() });

    render(<Coque courant="repos">{null}</Coque>);

    expect((await navigation()).getByRole("button", { name: "Déconnexion" })).toBeInTheDocument();
  });

  describe("panneau mobile", () => {
    it("le bouton menu ouvre la navigation dans un panneau, Échap la ferme", async () => {
      simulerApi({ "/api/repos": liste(), "/api/sessions": { sessions: [attend("20261017-100000-aaaaaa")] } });
      render(<Coque courant="repos">{null}</Coque>);
      const menu = await screen.findByRole("button", { name: "Ouvrir la navigation" });
      expect(menu).toHaveAttribute("aria-expanded", "false");

      fireEvent.click(menu);

      const panneau = await screen.findByRole("dialog", { name: "Navigation" });
      expect(menu).toHaveAttribute("aria-expanded", "true");
      expect(within(panneau).getByRole("link", { name: "Sessions" })).toHaveAttribute("href", "/sessions");
      expect(within(panneau).getByRole("region", { name: "Agents" })).toBeInTheDocument();
      expect(within(panneau).getByRole("button", { name: "Déconnexion" })).toBeInTheDocument();

      fireEvent.keyDown(panneau, { key: "Escape" });

      await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
      expect(menu).toHaveAttribute("aria-expanded", "false");
    });

    it("le bouton Fermer ferme le panneau", async () => {
      simulerApi({ "/api/repos": liste() });
      render(<Coque courant="repos">{null}</Coque>);

      fireEvent.click(await screen.findByRole("button", { name: "Ouvrir la navigation" }));
      fireEvent.click(
        within(await screen.findByRole("dialog")).getByRole("button", { name: "Fermer la navigation" }),
      );

      await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    });
  });

  describe("routes", () => {
    it.each([
      ["/", "Repos"],
      ["/repos/o/r", "Repos"],
      ["/sessions", "Sessions"],
      ["/sessions/20261017-100000-aaaaaa", "Sessions"],
      ["/sessions/20261017-100000-aaaaaa/codespace", "Sessions"],
    ])("%s s’affiche dans la coque (%s courant)", async (chemin, courant) => {
      simulerApi({ "/api/repos": liste() });

      render(<App chemin={chemin} />);

      expect((await navigation()).getByRole("link", { name: courant })).toHaveAttribute("aria-current", "page");
    });

    it("`/login` s’affiche sans coque, avec le logo", async () => {
      render(<App chemin="/login" />);

      expect(screen.queryByRole("navigation")).toBeNull();
      expect(screen.getByRole("img", { name: /HéphaïstOS/ })).toBeInTheDocument();
      expect(screen.getByRole("heading", { name: "Connexion" })).toBeInTheDocument();
    });
  });
});
