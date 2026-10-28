import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { VueListe } from "../src/VueListe";
import { RAFRAICHISSEMENT_MS } from "../src/rafraichi";
import { PAS_DE_VERSION, QUESTION, liste, repo, simulerApi, version } from "./donnees";

async function lignes() {
  const tableau = await screen.findByRole("table");
  return within(tableau).getAllByRole("row").slice(1);
}

describe("vue liste", () => {
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
    expect(within(ligne).getByRole("progressbar", { name: "Progression #17" })).toHaveAttribute(
      "aria-valuenow",
      "2",
    );
    expect(ligne).toHaveTextContent("2/5");
    expect(ligne).toHaveTextContent("Implement");
    expect(ligne).toHaveTextContent("09:00:00");
    expect(within(ligne).queryByText(/intervention humaine requise/)).toBeNull();
    expect(within(ligne).queryByText("Pilote")).toBeNull();
  });

  it("affiche le badge Pilote sur un repo sous pilote", async () => {
    simulerApi({ "/api/repos": liste({ repos: [repo({ pilote: true, agent: "cursor" })] }) });

    render(<VueListe />);

    const [ligne] = await lignes();
    expect(within(ligne).getByText("Pilote")).toBeInTheDocument();
    expect(within(ligne).queryByText("Réponse attendue")).toBeNull();
  });

  it("affiche la raison du stop quand le pilote est en pause", async () => {
    simulerApi({
      "/api/repos": liste({ repos: [repo({ pilote: true, pilote_stop: "attend" })] }),
    });

    render(<VueListe />);

    const [ligne] = await lignes();
    expect(within(ligne).getByText("Pilote")).toBeInTheDocument();
    expect(within(ligne).getByText("En pause · Réponse attendue")).toBeInTheDocument();
  });

  it("montre une session arrêtée par Terminer sur la liste", async () => {
    simulerApi({ "/api/repos": liste({ repos: [repo({ pilote: true, pilote_stop: "arretee" })] }) });

    render(<VueListe />);

    const [ligne] = await lignes();
    expect(within(ligne).getByText("En pause · Session arrêtée")).toBeInTheDocument();
  });

  it("montre humain requis et échec de lancement sur la liste", async () => {
    simulerApi({
      "/api/repos": liste({
        repos: [
          repo({ slug: "o/a", pilote: true, pilote_stop: "humain_requis" }),
          repo({ slug: "o/b", pilote: true, pilote_stop: "echec_lancement" }),
        ],
      }),
    });

    render(<VueListe />);

    const [a, b] = await lignes();
    expect(within(a).getByText("En pause · Intervention humaine requise")).toBeInTheDocument();
    expect(within(b).getByText("En pause · Échec de lancement")).toBeInTheDocument();
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
    expect(
      within(premiere).getByText("Question en attente · intervention humaine requise"),
    ).toBeInTheDocument();
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
    expect(within(ligne).getByRole("progressbar", { name: "Progression #40" })).toBeInTheDocument();
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
    expect(within(enErreur).getByText("o/absent introuvable sur GitHub")).toBeInTheDocument();
    expect(within(enErreur).queryByRole("progressbar")).toBeNull();
    expect(ok).toHaveTextContent("Implement");
    expect(ok).not.toHaveTextContent("introuvable");
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

    expect(await screen.findByText(/Aucun repo lié/)).toHaveTextContent(
      "sudo wap-runtime repo add owner/name",
    );
    expect(screen.queryByRole("table")).toBeNull();
  });

  it("affiche l’erreur d’un registry illisible", async () => {
    simulerApi({ "/api/repos": liste({ repos: [], erreur: "repos.toml illisible" }) });

    render(<VueListe />);

    expect(await screen.findByRole("alert")).toHaveTextContent("Registry : repos.toml illisible");
    expect(screen.queryByText(/Aucun repo lié/)).toBeNull();
  });

  it("signale en alerte une liste illisible", async () => {
    simulerApi({
      "/api/repos": () => new Response(JSON.stringify({ detail: "runtime arrêté" }), { status: 500 }),
    });

    render(<VueListe />);

    expect(await screen.findByRole("alert")).toHaveTextContent("Lecture impossible : runtime arrêté");
  });

  it("titre la page Repos, avec le nombre de repos liés et l’heure de lecture", async () => {
    simulerApi({
      "/api/repos": liste({
        repos: [repo({ slug: "o/a" }), repo({ slug: "o/b", lu_a: "2026-10-17T09:00:05+00:00" })],
      }),
    });

    render(<VueListe />);

    expect(await screen.findByRole("heading", { level: 1, name: "Repos" })).toBeInTheDocument();
    expect(screen.getByText("Instance · 2 repos liés")).toBeInTheDocument();
    expect(screen.getByText(/Relu à 09:00:05/)).toBeInTheDocument();
  });

  describe("résumé", () => {
    function compteurs() {
      return within(screen.getByRole("list", { name: "Résumé" }))
        .getAllByRole("listitem")
        .map((item) => item.textContent);
    }

    it("compte les repos qui attendent, les agents au travail et les repos en pilote", async () => {
      simulerApi({
        "/api/repos": liste({
          repos: [
            repo({ slug: "o/a", etape: QUESTION, humain_requis: true }),
            repo({
              slug: "o/b",
              pilote: true,
              pilote_stop: "attend",
              session: { id: "b", url: "/sessions/b", repo: "o/b", activite: "attend" },
            }),
            repo({
              slug: "o/c",
              pilote: true,
              session: { id: "c", url: "/sessions/c", repo: "o/c", activite: "travaille" },
            }),
            repo({ slug: "o/d", pilote: true }),
            repo({ slug: "o/e" }),
          ],
        }),
      });

      render(<VueListe />);
      await lignes();

      expect(compteurs()).toEqual([
        "2 attendent une action de votre part",
        "1 agent au travail",
        "3 repos en pilote",
      ]);
    });

    it("à zéro sans rien à faire", async () => {
      simulerApi({ "/api/repos": liste() });

      render(<VueListe />);
      await lignes();

      expect(compteurs()).toEqual([
        "0 attend une action de votre part",
        "0 agent au travail",
        "0 repo en pilote",
      ]);
    });
  });

  describe("ligne cliquable", () => {
    function simulerNavigation() {
      const assign = vi.fn();
      vi.stubGlobal("location", { ...window.location, assign });
      return assign;
    }

    it("un clic n’importe où sur la ligne ouvre le détail du repo", async () => {
      const assign = simulerNavigation();
      simulerApi({ "/api/repos": liste({ repos: [repo({ slug: "o/a" }), repo({ slug: "o/b" })] }) });

      render(<VueListe />);
      const [, b] = await lignes();
      fireEvent.click(within(b).getByText("2/5"));

      expect(assign).toHaveBeenCalledWith("/repos/o/b");
    });

    it("ouvre aussi le détail d’un repo en erreur", async () => {
      const assign = simulerNavigation();
      simulerApi({
        "/api/repos": liste({ repos: [repo({ erreur: "introuvable", etape: null, versions: [] })] }),
      });

      render(<VueListe />);
      const [ligne] = await lignes();
      fireEvent.click(within(ligne).getByText("introuvable"));

      expect(assign).toHaveBeenCalledWith("/repos/o/r");
    });

    it("laisse les liens de la ligne faire leur travail", async () => {
      const assign = simulerNavigation();
      simulerApi({
        "/api/repos": liste({
          repos: [repo({ session: { id: "x", url: "/sessions/x", repo: "o/r", activite: "travaille" } })],
        }),
      });

      render(<VueListe />);
      const [ligne] = await lignes();
      for (const lien of within(ligne).getAllByRole("link")) {
        lien.addEventListener("click", (e) => e.preventDefault());
        fireEvent.click(lien);
      }

      expect(within(ligne).getAllByRole("link").map((l) => l.getAttribute("href"))).toEqual([
        "/repos/o/r",
        "/sessions/x",
        "https://github.com/o/r/issues/17",
      ]);
      expect(assign).not.toHaveBeenCalled();
    });
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
