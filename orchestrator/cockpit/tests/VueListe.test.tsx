import { act, render, screen, waitFor, within } from "@testing-library/react";
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
    expect(within(ligne).queryByText("Pilote")).toBeNull();
  });

  it("affiche le badge Pilote sur un repo sous pilote", async () => {
    simulerApi({ "/api/repos": liste({ repos: [repo({ pilote: true, agent: "cursor" })] }) });

    render(<VueListe />);

    const [ligne] = await lignes();
    expect(within(ligne).getByText("Pilote")).toBeInTheDocument();
    expect(within(ligne).queryByText("En pause")).toBeNull();
  });

  it("affiche le badge En pause quand le pilote est stoppé", async () => {
    simulerApi({
      "/api/repos": liste({ repos: [repo({ pilote: true, pilote_stop: "attend" })] }),
    });

    render(<VueListe />);

    const [ligne] = await lignes();
    expect(within(ligne).getByText("Pilote")).toBeInTheDocument();
    expect(within(ligne).getByText("En pause")).toBeInTheDocument();
  });

  describe("notifications pilote", () => {
    function simulerNotifications(permission: NotificationPermission = "default") {
      const recues: { titre: string; corps?: string }[] = [];
      const requestPermission = vi.fn(async () => {
        Faux.permission = "granted";
        return "granted" as NotificationPermission;
      });
      class Faux {
        static permission = permission;
        static requestPermission = requestPermission;
        constructor(titre: string, options?: NotificationOptions) {
          recues.push({ titre, corps: options?.body });
        }
      }
      vi.stubGlobal("Notification", Faux);
      return { recues, requestPermission };
    }

    it("demande la permission et notifie chaque stop", async () => {
      const { recues, requestPermission } = simulerNotifications();
      simulerApi({
        "/api/repos": liste({
          repos: [
            repo({ slug: "o/a", pilote: true, pilote_stop: "attend" }),
            repo({ slug: "o/b", pilote: true, pilote_stop: "echec_lancement" }),
            repo({ slug: "o/c", pilote: true, pilote_stop: null }),
          ],
        }),
      });

      render(<VueListe />);
      await lignes();

      expect(requestPermission).toHaveBeenCalled();
      await waitFor(() => {
        expect(recues).toEqual([
          { titre: "Pilote : o/a", corps: "Réponse attendue" },
          { titre: "Pilote : o/b", corps: "Échec de lancement" },
        ]);
      });
    });

    it("ne renvoie pas la même notification au rafraîchissement", async () => {
      vi.useFakeTimers({ shouldAdvanceTime: true });
      const { recues } = simulerNotifications("granted");
      simulerApi({
        "/api/repos": liste({ repos: [repo({ pilote: true, pilote_stop: "humain_requis" })] }),
      });

      render(<VueListe />);
      await waitFor(() => {
        expect(recues).toEqual([
          { titre: "Pilote : o/r", corps: "Intervention humaine requise" },
        ]);
      });

      await act(() => vi.advanceTimersByTimeAsync(RAFRAICHISSEMENT_MS));

      expect(recues).toHaveLength(1);
    });
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
    const etat = { nouveau: false };
    const fetch = simulerApi({
      "/api/repos": () =>
        liste({ repos: [repo({ slug: etat.nouveau ? "o/nouveau" : "o/r" })] }),
    });
    render(<VueListe />);
    await lignes();
    const avant = fetch.mock.calls.filter(([chemin]) => chemin === "/api/repos").length;

    etat.nouveau = true;
    await act(() => vi.advanceTimersByTimeAsync(RAFRAICHISSEMENT_MS));

    expect(fetch.mock.calls.filter(([chemin]) => chemin === "/api/repos").length).toBeGreaterThan(
      avant,
    );
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
