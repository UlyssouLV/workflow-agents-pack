import { act, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { VueListe } from "../src/VueListe";
import { RAFRAICHISSEMENT_MS } from "../src/rafraichi";
import { CLAUDE, CURSOR, PAS_DE_VERSION, QUESTION, liste, repo, session, simulerApi, version } from "./donnees";

async function lignes() {
  const tableau = await screen.findByRole("table");
  return within(tableau).getAllByRole("row").slice(1);
}

describe("vue liste", () => {
  it("compte les réponses attendues dans l’en-tête et le titre d’onglet", async () => {
    simulerApi({
      "/api/repos": liste(),
      "/api/sessions": {
        sessions: [
          session({ activite: "attend", etat: "ouverte" }),
          session({
            id: "20261017-100000-bbbbbb",
            activite: "attend",
            etat: "ouverte",
            repo: "o/autre",
          }),
          session({ activite: "travaille", etat: "ouverte", id: "20261017-110000-cccccc" }),
          session({ activite: "attend", etat: "terminée", id: "20261017-080000-dddddd" }),
        ],
      },
    });

    render(<VueListe />);

    expect(await screen.findByRole("link", { name: "2 réponse(s) attendue(s)" })).toHaveAttribute(
      "href",
      "/sessions",
    );
    expect(document.title).toBe("(2) Cockpit wap-runtime");
  });

  it("ne change pas le titre d’onglet sans réponse attendue", async () => {
    simulerApi({
      "/api/repos": liste(),
      "/api/sessions": { sessions: [session({ activite: "travaille" })] },
    });

    render(<VueListe />);

    await screen.findByRole("link", { name: "0 réponse(s) attendue(s)" });
    expect(document.title).toBe("Cockpit wap-runtime");
  });

  it("montre une ligne par repo : nom, version ouverte, X/Y, étape, heure de lecture", async () => {
    simulerApi({ "/api/repos": liste() });

    render(<VueListe />);

    const [ligne] = await lignes();
    expect(within(ligne).getByRole("link", { name: "o/r" })).toHaveAttribute("href", "/repos/o/r");
    expect(screen.getByRole("link", { name: "Sessions" })).toHaveAttribute("href", "/sessions");
    expect(screen.getByRole("link", { name: "0 réponse(s) attendue(s)" })).toHaveAttribute(
      "href",
      "/sessions",
    );
    expect(within(ligne).getByRole("link", { name: /v0\.3\.0 — registry/ })).toHaveAttribute(
      "href",
      "https://github.com/o/r/issues/17",
    );
    expect(ligne).toHaveTextContent("2/5");
    expect(ligne).toHaveTextContent("Implement");
    expect(ligne).toHaveTextContent("09:00:00");
    expect(within(ligne).queryByText("Intervention humaine requise")).toBeNull();
  });

  it("affiche le nom d’affichage du registry à la place du slug", async () => {
    simulerApi({ "/api/repos": liste({ repos: [repo({ nom: "Mon produit" })] }) });

    render(<VueListe />);

    const [ligne] = await lignes();
    expect(within(ligne).getByRole("link", { name: "Mon produit" })).toHaveAttribute("href", "/repos/o/r");
  });

  it("met les repos « humain requis » en tête, avec le badge", async () => {
    simulerApi({
      "/api/repos": liste({
        repos: [
          repo({ slug: "o/a" }),
          repo({ slug: "o/b", etape: QUESTION, humain_requis: true, versions: [version({ etape: QUESTION })] }),
          repo({ slug: "o/c" }),
        ],
      }),
    });

    render(<VueListe />);

    const [premiere, ...autres] = await lignes();
    expect(premiere).toHaveTextContent("o/b");
    expect(within(premiere).getByText("Intervention humaine requise")).toBeInTheDocument();
    expect(autres.map((l) => within(l).getAllByRole("link")[0].textContent)).toEqual(["o/a", "o/c"]);
  });

  it("montre une version par sous-ligne quand plusieurs sont ouvertes", async () => {
    simulerApi({
      "/api/repos": liste({
        repos: [
          repo({
            versions: [
              version(),
              version({ numero: 40, titre: "v0.4.0", progression: { completed: 0, total: 3 } }),
            ],
          }),
        ],
      }),
    });

    render(<VueListe />);

    const [ligne] = await lignes();
    expect(within(ligne).getByRole("link", { name: /v0\.4\.0/ })).toBeInTheDocument();
    expect(ligne).toHaveTextContent("0/3");
  });

  it("affiche l’étape « Pas de version ouverte » sans version", async () => {
    simulerApi({ "/api/repos": liste({ repos: [repo({ etape: PAS_DE_VERSION, versions: [] })] }) });

    render(<VueListe />);

    const [ligne] = await lignes();
    expect(ligne).toHaveTextContent("Pas de version ouverte");
  });

  it("met en erreur la seule ligne d’un repo inaccessible, les autres s’affichent", async () => {
    simulerApi({
      "/api/repos": liste({
        repos: [
          repo({ slug: "o/absent", erreur: "o/absent introuvable sur GitHub", etape: null, versions: [] }),
          repo({ slug: "o/ok" }),
        ],
      }),
    });

    render(<VueListe />);

    const [enErreur, ok] = await lignes();
    expect(enErreur).toHaveTextContent("o/absent introuvable sur GitHub");
    expect(ok).toHaveTextContent("Implement");
    expect(ok).not.toHaveTextContent("introuvable");
  });

  it.each([
    ["sans_token", /non connecté/i],
    ["token_refuse", /token refusé/i],
  ] as const)("affiche le bandeau d’auth quand l’état est %s", async (etat, motif) => {
    simulerApi({ "/api/repos": liste({ auth: { etat, compte: null } }) });

    render(<VueListe />);

    const bandeau = await screen.findByRole("alert");
    expect(bandeau).toHaveTextContent(motif);
    expect(bandeau).toHaveTextContent("sudo wap-runtime auth");
  });

  it("n’affiche pas de bandeau d’auth quand l’instance est connectée", async () => {
    simulerApi({ "/api/repos": liste() });

    render(<VueListe />);

    await lignes();
    expect(screen.queryByRole("alert")).toBeNull();
    expect(screen.getByText(/octocat/)).toBeInTheDocument();
  });

  it("guide l’ajout d’un repo quand le registry est vide", async () => {
    simulerApi({ "/api/repos": liste({ repos: [] }) });

    render(<VueListe />);

    expect(await screen.findByText(/sudo wap-runtime repo add owner\/name/)).toBeInTheDocument();
  });

  it("affiche l’erreur d’un registry illisible", async () => {
    simulerApi({ "/api/repos": liste({ repos: [], erreur: "repos.toml illisible" }) });

    render(<VueListe />);

    expect(await screen.findByText(/repos\.toml illisible/)).toBeInTheDocument();
  });

  it("se relit toutes les 60 s", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    let appel = 0;
    const fetch = simulerApi({
      "/api/repos": () =>
        ++appel === 1 ? liste() : liste({ repos: [repo({ slug: "o/nouveau" })] }),
    });
    render(<VueListe />);
    await lignes();

    await act(() => vi.advanceTimersByTimeAsync(RAFRAICHISSEMENT_MS));

    expect(fetch.mock.calls.filter(([chemin]) => chemin === "/api/repos")).toHaveLength(2);
    expect(await screen.findByRole("link", { name: "o/nouveau" })).toBeInTheDocument();
  });

  describe("encart Agents", () => {
    async function encart() {
      return within(await screen.findByRole("region", { name: "Agents" }));
    }

    it("dit quel agent est connecté, et la commande à lancer pour l’autre", async () => {
      simulerApi({ "/api/repos": liste() });

      render(<VueListe />);

      const agents = await encart();
      const [claude, cursor] = agents.getAllByRole("listitem");
      expect(claude).toHaveTextContent("Claude Code : Connecté");
      expect(claude).not.toHaveTextContent("sudo");
      expect(cursor).toHaveTextContent("Cursor : Non connecté");
      expect(cursor).toHaveTextContent("… | sudo wap-runtime auth agent --with-token");
    });

    it("donne la commande de chaque agent non connecté", async () => {
      simulerApi({
        "/api/repos": liste({ agents: [{ ...CLAUDE, connecte: false }, { ...CURSOR, connecte: true }] }),
      });

      render(<VueListe />);

      const [claude, cursor] = (await encart()).getAllByRole("listitem");
      expect(claude).toHaveTextContent("Claude Code : Non connecté");
      expect(claude).toHaveTextContent("sudo wap-runtime auth claude");
      expect(cursor).toHaveTextContent("Cursor : Connecté");
      expect(cursor).not.toHaveTextContent("sudo");
    });
  });

  it.each([
    [undefined, "Session en cours"],
    ["inconnue", "Session en cours"],
    ["travaille", "Travaille"],
    ["attend", "Réponse attendue"],
  ] as const)("badge d’activité %s : %s", async (activite, libelle) => {
    simulerApi({
      "/api/repos": liste({
        repos: [
          repo({ slug: "o/a" }),
          repo({
            slug: "o/b",
            session: { id: "x", url: "/sessions/x", repo: "o/b", ...(activite && { activite }) },
          }),
        ],
      }),
    });

    render(<VueListe />);

    const [a, b] = await lignes();
    expect(within(a).queryByText(libelle)).toBeNull();
    expect(within(b).getByRole("link", { name: libelle })).toHaveAttribute("href", "/sessions/x");
  });
});
