import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { VueDetail } from "../src/VueDetail";
import { RAFRAICHISSEMENT_MS } from "../src/rafraichi";
import { CLAUDE, CONNECTE, CURSOR_CONNECTE, MODELES, QUESTION, detail, session, simulerApi } from "./donnees";

function rendre(routes: Record<string, unknown>) {
  const fetch = simulerApi({ "/api/auth": CONNECTE, ...routes });
  render(<VueDetail owner="o" name="r" />);
  return fetch;
}

describe("vue détail", () => {
  it("montre le repo, son étape et le lien GitHub", async () => {
    rendre({ "/api/repos/o/r": detail({ etape: QUESTION, humain_requis: true }) });

    const titre = await screen.findByRole("heading", { level: 1 });
    expect(titre).toHaveTextContent("o/r");
    expect(screen.getByRole("link", { name: "github.com/o/r" })).toHaveAttribute("href", "https://github.com/o/r");
    expect(screen.getByText("Question en attente", { selector: "strong" })).toBeInTheDocument();
    expect(screen.getAllByText("Intervention humaine requise").length).toBeGreaterThan(0);
    expect(screen.getByText(/09:00:00/)).toBeInTheDocument();
  });

  it("montre le parent, sa progression et ses enfants (état, labels, bloqué)", async () => {
    rendre({ "/api/repos/o/r": detail() });

    const version = await screen.findByRole("region", { name: /#17 v0\.3\.0 — registry/ });
    expect(within(version).getByRole("link", { name: "#17 v0.3.0 — registry" })).toHaveAttribute(
      "href",
      "https://github.com/o/r/issues/17",
    );
    expect(version).toHaveTextContent("2/5");
    const enfants = within(within(version).getByRole("table", { name: "Enfants" })).getAllByRole("row").slice(1);
    expect(enfants[0]).toHaveTextContent("#20 Registry");
    expect(enfants[0]).toHaveTextContent("fermé");
    expect(enfants[1]).toHaveTextContent("#22 Front du cockpit");
    expect(enfants[1]).toHaveTextContent("ouvert");
    expect(enfants[1]).toHaveTextContent("ready-for-agent");
    expect(enfants[1]).toHaveTextContent("bloqué");
    expect(within(enfants[1]).getAllByRole("link")[0]).toHaveAttribute("href", "https://github.com/o/r/issues/22");
  });

  it("montre tous les signaux de la version, même un seul", async () => {
    rendre({ "/api/repos/o/r": detail() });

    const version = await screen.findByRole("region", { name: /#17/ });
    expect(version).toHaveTextContent("Signaux : Implement");
  });

  it("montre la PR de version et ses checks", async () => {
    rendre({ "/api/repos/o/r": detail() });

    const version = await screen.findByRole("region", { name: /#17/ });
    expect(within(version).getByRole("link", { name: "PR #18 v0.3.0" })).toHaveAttribute(
      "href",
      "https://github.com/o/r/pull/18",
    );
    expect(version).toHaveTextContent("brouillon");
    expect(within(version).getByRole("link", { name: "pytest" })).toHaveAttribute(
      "href",
      "https://github.com/o/r/runs/1",
    );
    expect(within(version).getByRole("listitem", { name: "pytest" })).toHaveTextContent("en échec");
  });

  it("signale une version sans PR", async () => {
    const d = detail();
    rendre({ "/api/repos/o/r": { ...d, versions: [{ ...d.versions[0], pr: null }] } });

    const version = await screen.findByRole("region", { name: /#17/ });
    expect(version).toHaveTextContent("Aucune PR de version");
  });

  it("liste les bugs ouverts", async () => {
    rendre({ "/api/repos/o/r": detail() });

    const bugs = await screen.findByRole("region", { name: "Bugs ouverts" });
    expect(within(bugs).getByRole("link", { name: "#30 Plantage" })).toHaveAttribute(
      "href",
      "https://github.com/o/r/issues/30",
    );
  });

  it("affiche l’erreur du repo inaccessible", async () => {
    rendre({
      "/api/repos/o/r": detail({ erreur: "accès refusé à o/r", etape: null, versions: [], bugs: [] }),
    });

    expect(await screen.findByText(/accès refusé à o\/r/)).toBeInTheDocument();
  });

  it("affiche le message du runtime pour un repo absent du registry", async () => {
    rendre({
      "/api/repos/o/r": new Response(
        JSON.stringify({ detail: "o/r absent du registry : `sudo wap-runtime repo add o/r`" }),
        { status: 404 },
      ),
    });

    expect(await screen.findByText(/o\/r absent du registry/)).toBeInTheDocument();
  });

  it("affiche le bandeau d’auth sans token", async () => {
    rendre({ "/api/auth": { etat: "sans_token", compte: null }, "/api/repos/o/r": detail() });

    const bandeau = await screen.findByRole("alert");
    expect(bandeau).toHaveTextContent("sudo wap-runtime auth");
  });

  it("relit le détail à chaque rafraîchissement", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    let appel = 0;
    const fetch = rendre({
      "/api/repos/o/r": () => (++appel === 1 ? detail() : detail({ bugs: [] })),
    });
    await screen.findByRole("link", { name: "#30 Plantage" });

    await act(() => vi.advanceTimersByTimeAsync(RAFRAICHISSEMENT_MS));

    expect(fetch.mock.calls.filter(([chemin]) => chemin === "/api/repos/o/r")).toHaveLength(2);
    expect(screen.queryByRole("link", { name: "#30 Plantage" })).toBeNull();
  });

  describe("pilote", () => {
    it("montre le toggle et l’agent préféré persistés", async () => {
      rendre({ "/api/repos/o/r": detail({ pilote: true, agent: "cursor" }) });

      expect(await screen.findByRole("checkbox", { name: "Pilote" })).toBeChecked();
      expect(screen.getByRole("combobox", { name: "Agent" })).toHaveValue("cursor");
    });

    it("enregistre le toggle et l’agent auprès du runtime", async () => {
      const fetch = rendre({
        "/api/repos/o/r": detail({ pilote: false, agent: "claude" }),
        "PATCH /api/repos/o/r": { pilote: true, agent: "cursor" },
      });
      const toggle = await screen.findByRole("checkbox", { name: "Pilote" });

      fireEvent.click(toggle);

      await waitFor(() => {
        const corps = fetch.mock.calls.find(([, init]) => init?.method === "PATCH")?.[1]?.body;
        expect(corps).toEqual(JSON.stringify({ pilote: true, agent: "claude" }));
      });

      fireEvent.change(screen.getByRole("combobox", { name: "Agent" }), { target: { value: "cursor" } });

      await waitFor(() => {
        const patchs = fetch.mock.calls.filter(([, init]) => init?.method === "PATCH");
        expect(patchs.at(-1)?.[1]?.body).toEqual(JSON.stringify({ pilote: true, agent: "cursor" }));
      });
    });
  });

  describe("nouvelle session", () => {
    async function boutonNouvelle() {
      await screen.findByRole("heading", { level: 1 });
      return screen.getByRole("button", { name: "Nouvelle session" });
    }

    it("propose les agents et les branches, PR de version par défaut", async () => {
      rendre({ "/api/repos/o/r": detail() });

      const agents = await screen.findByRole("combobox", { name: "Agent" });
      expect(within(agents).getAllByRole("option").map((o) => o.textContent)).toEqual([
        "Claude Code",
        "Cursor (non connecté)",
      ]);
      expect(agents).toHaveValue("claude");
      const branches = screen.getByRole("combobox", { name: "Branche" });
      expect(within(branches).getAllByRole("option").map((o) => o.textContent)).toEqual([
        "main",
        "v0.3.0-registry",
      ]);
      expect(branches).toHaveValue("v0.3.0-registry");
    });

    it("n’affiche plus de bouton /implement par ticket", async () => {
      rendre({ "/api/repos/o/r": detail() });

      await screen.findByRole("link", { name: "#23 Lancer une session" });
      expect(screen.queryByRole("button", { name: /^\/implement #/ })).toBeNull();
    });

    it("bouton grisé si l’agent n’est pas connecté", async () => {
      rendre({ "/api/repos/o/r": detail() });
      const selecteur = await screen.findByRole("combobox", { name: "Agent" });

      fireEvent.change(selecteur, { target: { value: "cursor" } });

      const bouton = await boutonNouvelle();
      expect(bouton).toBeDisabled();
      expect(bouton).toHaveAttribute("title", "agent non connecté");
      expect(screen.getByText("agent non connecté")).toBeInTheDocument();
    });

    it("bouton grisé avec le lien si une session est déjà ouverte sur ce repo", async () => {
      rendre({ "/api/repos/o/r": detail({ session: { id: "x", url: "/sessions/x", repo: "o/r" } }) });

      const bouton = await boutonNouvelle();
      expect(bouton).toBeDisabled();
      expect(bouton).toHaveAttribute("title", "session déjà ouverte sur ce repo");
      expect(screen.getByRole("link", { name: /session ouverte/i })).toHaveAttribute("href", "/sessions/x");
    });

    it("bouton non grisé si la session ouverte est sur un autre repo", async () => {
      rendre({
        "/api/repos/o/r": detail({ session: null }),
        "/api/sessions": {
          sessions: [session({ repo: "o/autre", activite: "attend", skill: "grilling" })],
        },
      });

      const bouton = await boutonNouvelle();
      expect(bouton).toBeEnabled();
    });

    it("bouton grisé si une session d’un autre repo travaille", async () => {
      const autre = session({
        id: "20261017-100000-bbbbbb",
        url: "/sessions/20261017-100000-bbbbbb",
        repo: "o/autre",
        activite: "travaille",
      });
      rendre({
        "/api/repos/o/r": detail({ session: null }),
        "/api/sessions": { sessions: [autre] },
      });

      const bouton = await boutonNouvelle();
      expect(bouton).toBeDisabled();
      expect(bouton).toHaveAttribute("title", "une session travaille sur o/autre");
      expect(screen.getByRole("link", { name: /session ouverte/i })).toHaveAttribute(
        "href",
        "/sessions/20261017-100000-bbbbbb",
      );
    });

    it("le clic lance la session avec l’agent et la branche puis ouvre sa page", async () => {
      const assign = vi.fn();
      vi.stubGlobal("location", { ...window.location, assign });
      const corps: unknown[] = [];
      const fetch = rendre({
        "/api/repos/o/r": detail(),
        "POST /api/sessions": (init?: RequestInit) => {
          corps.push(JSON.parse(String(init?.body)));
          return new Response(JSON.stringify(session({ ticket: null, commande: "claude" })), { status: 201 });
        },
      });
      fireEvent.click(await boutonNouvelle());

      await waitFor(() => expect(assign).toHaveBeenCalledWith("/sessions/20261017-090000-abcdef"));
      expect(corps).toEqual([{ repo: "o/r", agent: "claude", branche: "v0.3.0-registry" }]);
      const [, init] = fetch.mock.calls.find(([, i]) => i?.method === "POST")!;
      expect(init?.headers).toMatchObject({ "Content-Type": "application/json" });
    });

    it("ne quitte pas le cockpit sur l’URL rendue par le serveur", async () => {
      const assign = vi.fn();
      vi.stubGlobal("location", { ...window.location, assign });
      const rendue = session({ id: "//ailleurs.example", url: "https://ailleurs.example/" });
      rendre({
        "/api/repos/o/r": detail(),
        "POST /api/sessions": () => new Response(JSON.stringify(rendue), { status: 201 }),
      });
      fireEvent.click(await boutonNouvelle());

      await new Promise((r) => setTimeout(r, 20));
      expect(assign).not.toHaveBeenCalled();
    });

    describe("clone sale", () => {
      const SALE = {
        detail: "le clone a des changements non commités : Reprendre ou Jeter",
        clone: {
          fichiers: [
            { statut: "M", chemin: "src/a.py" },
            { statut: "??", chemin: "notes.txt" },
          ],
          diff: "--- a/src/a.py\n+++ b/src/a.py\n-avant\n+après\n",
          branche: "travail-en-cours",
        },
      };

      function rendreSale(corps: unknown[], assign = vi.fn()) {
        vi.stubGlobal("location", { ...window.location, assign });
        rendre({
          "/api/repos/o/r": detail(),
          "POST /api/sessions": (init?: RequestInit) => {
            const demande = JSON.parse(String(init?.body));
            corps.push(demande);
            return demande.choix
              ? new Response(JSON.stringify(session({ ticket: null })), { status: 201 })
              : new Response(JSON.stringify(SALE), { status: 409 });
          },
        });
        return assign;
      }

      it("montre la branche actuelle, le nombre de fichiers, la liste et le diff, sans lancer", async () => {
        const assign = rendreSale([]);
        fireEvent.click(await boutonNouvelle());

        const choix = await screen.findByRole("dialog", { name: /changements non commités/i });
        expect(choix).toHaveTextContent("travail-en-cours");
        expect(choix).toHaveTextContent("2 fichiers modifiés");
        expect(within(choix).getByRole("list", { name: "Fichiers modifiés" })).toHaveTextContent(
          /M src\/a\.py.*\?\? notes\.txt/,
        );
        expect(within(choix).getByLabelText("Diff")).toHaveTextContent("+après");
        expect(within(choix).getByRole("button", { name: "Reprendre" })).toBeEnabled();
        expect(within(choix).getByRole("button", { name: "Jeter" })).toBeEnabled();
        expect(assign).not.toHaveBeenCalled();
      });

      it.each(["reprendre", "jeter"])("%s relance avec ce choix puis ouvre la session", async (choix) => {
        const corps: unknown[] = [];
        const assign = rendreSale(corps);
        fireEvent.click(await boutonNouvelle());
        const ecran = await screen.findByRole("dialog");

        fireEvent.click(within(ecran).getByRole("button", { name: choix === "jeter" ? "Jeter" : "Reprendre" }));

        await waitFor(() => expect(assign).toHaveBeenCalledWith("/sessions/20261017-090000-abcdef"));
        expect(corps).toEqual([
          { repo: "o/r", agent: "claude", branche: "v0.3.0-registry" },
          { repo: "o/r", agent: "claude", branche: "v0.3.0-registry", choix },
        ]);
      });

      it("Annuler ferme l’écran sans rien lancer", async () => {
        const corps: unknown[] = [];
        rendreSale(corps);
        fireEvent.click(await boutonNouvelle());
        const ecran = await screen.findByRole("dialog");

        fireEvent.click(within(ecran).getByRole("button", { name: "Annuler" }));

        expect(screen.queryByRole("dialog")).toBeNull();
        expect(corps).toHaveLength(1);
      });
    });

    it("un autre refus affiche son message", async () => {
      rendre({
        "/api/repos/o/r": detail(),
        "POST /api/sessions": new Response(JSON.stringify({ detail: "git fetch a échoué" }), { status: 422 }),
      });
      fireEvent.click(await boutonNouvelle());

      expect(await screen.findByText(/git fetch a échoué/)).toBeInTheDocument();
    });

    it("montre la session ouverte de l’instance", async () => {
      rendre({ "/api/repos/o/r": detail({ session: { id: "x", url: "/sessions/x", repo: "o/r" } }) });

      const lien = await screen.findByRole("link", { name: /session en cours/i });
      expect(lien).toHaveAttribute("href", "/sessions/x");
    });
  });

  describe("sessions du repo", () => {
    const SESSIONS = "/api/repos/o/r/sessions";

    it("liste les sessions, plus récente d’abord : date, agent, commande, état et lien", async () => {
      rendre({
        "/api/repos/o/r": detail(),
        [SESSIONS]: {
          sessions: [
            session({ id: "b", url: "/sessions/b", debut: "2026-10-17T10:30:00+00:00", agent: "cursor",
              commande: 'agent "/implement #23"' }),
            session({ id: "a", url: "/sessions/a", etat: "interrompue", fin: "2026-10-17T09:10:00+00:00" }),
          ],
        },
      });

      const section = await screen.findByRole("region", { name: "Sessions" });
      const lignes = (await within(section).findAllByRole("row")).slice(1);
      expect(lignes).toHaveLength(2);
      expect(lignes[0]).toHaveTextContent("17/10/2026 10:30");
      expect(lignes[0]).toHaveTextContent("Cursor");
      expect(lignes[0]).toHaveTextContent('agent "/implement #23"');
      expect(lignes[0]).toHaveTextContent("Ouverte");
      expect(within(lignes[0]).getByRole("link")).toHaveAttribute("href", "/sessions/b");
      expect(lignes[1]).toHaveTextContent("Claude Code");
      expect(lignes[1]).toHaveTextContent("Interrompue");
      expect(within(lignes[1]).getByRole("link")).toHaveAttribute("href", "/sessions/a");
    });

    it("aucune session", async () => {
      rendre({ "/api/repos/o/r": detail(), [SESSIONS]: { sessions: [] } });

      const section = await screen.findByRole("region", { name: "Sessions" });
      expect(await within(section).findByText("Aucune session.")).toBeInTheDocument();
    });

    it("listées même quand GitHub est en erreur", async () => {
      rendre({
        "/api/repos/o/r": detail({ erreur: "GitHub injoignable", versions: [] }),
        [SESSIONS]: { sessions: [session()] },
      });

      const section = await screen.findByRole("region", { name: "Sessions" });
      expect(await within(section).findByText('claude "/implement #23"')).toBeInTheDocument();
    });

    it("affiche Auto ou l’ID du modèle sur une session Cursor, rien sur Claude", async () => {
      rendre({
        "/api/repos/o/r": detail(),
        [SESSIONS]: {
          sessions: [
            session({ id: "c", url: "/sessions/c", agent: "cursor", modele: "composer-2" }),
            session({ id: "b", url: "/sessions/b", agent: "cursor", modele: null }),
            session({ id: "a", url: "/sessions/a" }),
          ],
        },
      });

      const section = await screen.findByRole("region", { name: "Sessions" });
      const [cursorId, cursorAuto, claude] = (await within(section).findAllByRole("row")).slice(1);
      expect(cursorId).toHaveTextContent("composer-2");
      expect(cursorAuto).toHaveTextContent("Auto");
      expect(claude).not.toHaveTextContent("Auto");
      expect(claude).not.toHaveTextContent("composer-2");
    });

    it("sans session Cursor, pas de colonne Modèle", async () => {
      rendre({
        "/api/repos/o/r": detail(),
        [SESSIONS]: { sessions: [session({ titre: "Claude Code" })] },
      });

      const section = await screen.findByRole("region", { name: "Sessions" });
      expect(await within(section).findByRole("columnheader", { name: "Agent" })).toBeInTheDocument();
      expect(within(section).queryByRole("columnheader", { name: "Modèle" })).toBeNull();
    });

    it("chaîne : état enchaînée, liens précédente et suivante", async () => {
      const [a, b] = ["20261017-090000-aaaaaa", "20261017-093000-bbbbbb"];
      rendre({
        "/api/repos/o/r": detail(),
        [SESSIONS]: {
          sessions: [
            session({ id: b, url: `/sessions/${b}`, ticket: 24, commande: 'claude "/implement #24"', precedente: a }),
            session({ id: a, url: `/sessions/${a}`, etat: "enchaînée", fin: "2026-10-17T09:30:00+00:00", suivante: b }),
          ],
        },
      });

      const section = await screen.findByRole("region", { name: "Sessions" });
      const [suivante, enchainee] = (await within(section).findAllByRole("row")).slice(1);
      expect(within(suivante).getByRole("link", { name: "précédente" })).toHaveAttribute("href", `/sessions/${a}`);
      expect(within(suivante).queryByRole("link", { name: "suivante" })).not.toBeInTheDocument();
      expect(enchainee).toHaveTextContent("Enchaînée");
      expect(within(enchainee).getByRole("link", { name: "suivante" })).toHaveAttribute("href", `/sessions/${b}`);
      expect(within(enchainee).queryByRole("link", { name: "précédente" })).not.toBeInTheDocument();
    });
  });

  describe("modèle Cursor", () => {
    const agents = [CLAUDE, CURSOR_CONNECTE];
    const cursor = (extra: Parameters<typeof detail>[0] = {}) =>
      detail({ agents, agent: "cursor", modele: "composer-2", ...extra });

    it("n’affiche pas le select si l’agent est Claude", async () => {
      rendre({
        "/api/repos/o/r": detail({ agents, agent: "claude" }),
        "/api/modeles": MODELES,
      });

      await screen.findByRole("combobox", { name: "Agent" });
      expect(screen.queryByRole("combobox", { name: /^Modèle/ })).toBeNull();
    });

    it("n’affiche pas le select si Cursor n’est pas connecté", async () => {
      rendre({ "/api/repos/o/r": detail({ agent: "cursor" }) });

      await screen.findByRole("combobox", { name: "Agent" });
      expect(screen.queryByRole("combobox", { name: /^Modèle/ })).toBeNull();
    });

    it("affiche le select prérempli si agent Cursor et Cursor connecté", async () => {
      rendre({ "/api/repos/o/r": cursor(), "/api/modeles": MODELES });

      expect(await screen.findByRole("combobox", { name: "Modèle" })).toHaveValue("composer-2");
      expect(screen.getByRole("combobox", { name: "Modèle de la session" })).toHaveValue("composer-2");
    });

    it("enregistre la préférence modèle sans lancer", async () => {
      const fetch = rendre({
        "/api/repos/o/r": cursor(),
        "/api/modeles": MODELES,
        "PATCH /api/repos/o/r": { pilote: false, agent: "cursor", modele: "grok-4.6" },
      });

      fireEvent.change(await screen.findByRole("combobox", { name: "Modèle" }), {
        target: { value: "grok-4.6" },
      });

      await waitFor(() => {
        const corps = fetch.mock.calls.find(([, init]) => init?.method === "PATCH")?.[1]?.body;
        expect(corps).toEqual(JSON.stringify({ pilote: false, agent: "cursor", modele: "grok-4.6" }));
      });
      expect(fetch.mock.calls.some(([, init]) => init?.method === "POST")).toBe(false);
    });

    it("Nouvelle session envoie l’override et ne PATCH pas le repo", async () => {
      const assign = vi.fn();
      vi.stubGlobal("location", { ...window.location, assign });
      const corps: unknown[] = [];
      const fetch = rendre({
        "/api/repos/o/r": cursor(),
        "/api/modeles": MODELES,
        "POST /api/sessions": (init?: RequestInit) => {
          corps.push(JSON.parse(String(init?.body)));
          return new Response(JSON.stringify(session({ ticket: null, agent: "cursor" })), { status: 201 });
        },
      });
      fireEvent.change(await screen.findByRole("combobox", { name: "Modèle de la session" }), {
        target: { value: "grok-4.6" },
      });
      fireEvent.click(screen.getByRole("button", { name: "Nouvelle session" }));

      await waitFor(() => expect(assign).toHaveBeenCalled());
      expect(corps).toEqual([
        { repo: "o/r", agent: "cursor", branche: "v0.3.0-registry", modele: "grok-4.6" },
      ]);
      expect(fetch.mock.calls.some(([, init]) => init?.method === "PATCH")).toBe(false);
    });

    it("Auto est prérempli et envoyé comme null", async () => {
      const assign = vi.fn();
      vi.stubGlobal("location", { ...window.location, assign });
      const corps: unknown[] = [];
      rendre({
        "/api/repos/o/r": cursor({ modele: null }),
        "/api/modeles": MODELES,
        "POST /api/sessions": (init?: RequestInit) => {
          corps.push(JSON.parse(String(init?.body)));
          return new Response(JSON.stringify(session({ ticket: null, agent: "cursor" })), { status: 201 });
        },
      });
      expect(await screen.findByRole("combobox", { name: "Modèle de la session" })).toHaveValue("");
      fireEvent.click(screen.getByRole("button", { name: "Nouvelle session" }));

      await waitFor(() => expect(assign).toHaveBeenCalled());
      expect(corps).toEqual([{ repo: "o/r", agent: "cursor", branche: "v0.3.0-registry", modele: null }]);
    });

    it("liste en échec : pas de lancement Cursor, message du runtime", async () => {
      rendre({
        "/api/repos/o/r": cursor(),
        "/api/modeles": new Response(
          JSON.stringify({ detail: "liste des modèles Cursor indisponible : quota exceeded" }),
          { status: 503 },
        ),
      });

      const bouton = await screen.findByRole("button", { name: "Nouvelle session" });
      await waitFor(() => expect(bouton).toBeDisabled());
      expect(await screen.findByText("liste des modèles Cursor indisponible : quota exceeded")).toBeInTheDocument();
    });
  });
});
