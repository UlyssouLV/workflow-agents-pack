import { act, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { VueDetail } from "../src/VueDetail";
import { RAFRAICHISSEMENT_MS } from "../src/rafraichi";
import { CONNECTE, QUESTION, detail, simulerApi } from "./donnees";

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
    expect(within(enfants[1]).getByRole("link")).toHaveAttribute("href", "https://github.com/o/r/issues/22");
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
});
