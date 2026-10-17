import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { VueDetail } from "../src/VueDetail";
import { RAFRAICHISSEMENT_MS } from "../src/rafraichi";
import { CONNECTE, QUESTION, detail, session, simulerApi } from "./donnees";

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

  describe("lancement de /implement", () => {
    async function boutons() {
      const version = await screen.findByRole("region", { name: /#17/ });
      return within(version).getAllByRole("button", { name: /^\/implement #/ });
    }

    it("propose les agents dans un sélecteur, le premier connecté choisi", async () => {
      rendre({ "/api/repos/o/r": detail() });

      const selecteur = await screen.findByRole("combobox", { name: "Agent" });
      expect(within(selecteur).getAllByRole("option").map((o) => o.textContent)).toEqual([
        "Claude Code",
        "Cursor (non connecté)",
      ]);
      expect(selecteur).toHaveValue("claude");
    });

    it("un bouton par enfant ouvert : actif si éligible, sinon grisé avec la raison", async () => {
      rendre({ "/api/repos/o/r": detail() });

      const [bloque, eligible] = await boutons();
      expect(bloque).toHaveTextContent("/implement #22");
      expect(bloque).toBeDisabled();
      expect(bloque).toHaveAttribute("title", "enfant bloqué");
      expect(screen.getByText("enfant bloqué")).toBeInTheDocument();
      expect(eligible).toHaveTextContent("/implement #23");
      expect(eligible).toBeEnabled();
    });

    it("la raison suit l’agent choisi", async () => {
      rendre({ "/api/repos/o/r": detail() });
      const selecteur = await screen.findByRole("combobox", { name: "Agent" });

      fireEvent.change(selecteur, { target: { value: "cursor" } });

      const [, eligible] = await boutons();
      expect(eligible).toBeDisabled();
      expect(eligible).toHaveAttribute("title", "agent non connecté");
    });

    it("le clic lance la session avec l’agent choisi puis ouvre sa page", async () => {
      const assign = vi.fn();
      vi.stubGlobal("location", { ...window.location, assign });
      const corps: unknown[] = [];
      const fetch = rendre({
        "/api/repos/o/r": detail(),
        "POST /api/sessions": (init?: RequestInit) => {
          corps.push(JSON.parse(String(init?.body)));
          return new Response(JSON.stringify(session()), { status: 201 });
        },
      });
      const [, eligible] = await boutons();

      fireEvent.click(eligible);

      await waitFor(() => expect(assign).toHaveBeenCalledWith("/sessions/20261017-090000-abcdef"));
      expect(corps).toEqual([{ repo: "o/r", ticket: 23, agent: "claude" }]);
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
      const [, eligible] = await boutons();

      fireEvent.click(eligible);

      await new Promise((r) => setTimeout(r, 20));
      expect(assign).not.toHaveBeenCalled();
    });

    it("un refus 409 montre le lien vers la session ouverte", async () => {
      rendre({
        "/api/repos/o/r": detail(),
        "POST /api/sessions": new Response(
          JSON.stringify({
            detail: "une session est déjà ouverte : /sessions/x",
            session: { id: "x", url: "/sessions/x", repo: "o/autre" },
          }),
          { status: 409 },
        ),
      });
      const [, eligible] = await boutons();

      fireEvent.click(eligible);

      const lien = await screen.findByRole("link", { name: /session ouverte/i });
      expect(lien).toHaveAttribute("href", "/sessions/x");
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
              ? new Response(JSON.stringify(session()), { status: 201 })
              : new Response(JSON.stringify(SALE), { status: 409 });
          },
        });
        return assign;
      }

      it("montre les fichiers modifiés et le diff, sans lancer", async () => {
        const assign = rendreSale([]);
        const [, eligible] = await boutons();

        fireEvent.click(eligible);

        const choix = await screen.findByRole("dialog", { name: /changements non commités/i });
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
        const [, eligible] = await boutons();
        fireEvent.click(eligible);
        const ecran = await screen.findByRole("dialog");

        fireEvent.click(within(ecran).getByRole("button", { name: choix === "jeter" ? "Jeter" : "Reprendre" }));

        await waitFor(() => expect(assign).toHaveBeenCalledWith("/sessions/20261017-090000-abcdef"));
        expect(corps).toEqual([
          { repo: "o/r", ticket: 23, agent: "claude" },
          { repo: "o/r", ticket: 23, agent: "claude", choix },
        ]);
      });

      it("Annuler ferme l’écran sans rien lancer", async () => {
        const corps: unknown[] = [];
        rendreSale(corps);
        const [, eligible] = await boutons();
        fireEvent.click(eligible);
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
      const [, eligible] = await boutons();

      fireEvent.click(eligible);

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
});
