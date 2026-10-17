import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { App } from "../src/App";
import { VueSession } from "../src/VueSession";
import { session, simulerApi } from "./donnees";
import { FauxTerminal, FauxWebSocket } from "./simulations";

const CHEMIN = "/api/sessions/20261017-090000-abcdef";

function rendre(s = session()) {
  simulerApi({ [CHEMIN]: s });
  return render(<VueSession id="20261017-090000-abcdef" />);
}

describe("page de session", () => {
  it("montre le repo, le ticket, l’agent et la commande", async () => {
    rendre();

    expect(await screen.findByRole("heading", { level: 1 })).toHaveTextContent("Session /implement #23");
    expect(screen.getByRole("link", { name: "o/r" })).toHaveAttribute("href", "/repos/o/r");
    expect(screen.getByText('claude "/implement #23"')).toBeInTheDocument();
  });

  it("session ouverte : état et durée depuis le début", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true, now: new Date("2026-10-17T09:12:05Z") });
    rendre();

    expect(await screen.findByText("Ouverte")).toBeInTheDocument();
    expect(screen.getByText("12 min 5 s")).toBeInTheDocument();
  });

  it.each([
    [0, "terminée", "Terminée"],
    [1, "échouée", "Échouée (code 1)"],
  ] as const)("session close (code %i) : état et durée jusqu’à la fin", async (code, etat, libelle) => {
    rendre(session({ etat, code_sortie: code, fin: "2026-10-17T10:01:00+00:00" }));

    expect(await screen.findByText(libelle)).toBeInTheDocument();
    expect(screen.getByText("1 h 1 min")).toBeInTheDocument();
  });

  it("session inconnue : le message du runtime", async () => {
    simulerApi({ [CHEMIN]: new Response(JSON.stringify({ detail: "session inconnue" }), { status: 404 }) });
    render(<VueSession id="20261017-090000-abcdef" />);

    expect(await screen.findByText("session inconnue")).toBeInTheDocument();
  });

  it("`/sessions/<id>` rend la page de session", async () => {
    simulerApi({ [CHEMIN]: session() });

    render(<App chemin="/sessions/20261017-090000-abcdef" />);

    expect(await screen.findByRole("heading", { level: 1 })).toHaveTextContent("Session /implement #23");
  });
});

describe("terminal en direct", () => {
  async function ouvrir(role: "ecriture" | "lecture" = "ecriture") {
    const { unmount } = rendre();
    await screen.findByRole("region", { name: "Terminal" });
    const [ws] = FauxWebSocket.instances;
    act(() => ws.role(role));
    return { ws, terminal: FauxTerminal.instances[0], unmount };
  }

  it("session ouverte : websocket du terminal sur le cockpit servi", async () => {
    rendre();

    expect(await screen.findByRole("region", { name: "Terminal" })).toBeInTheDocument();
    expect(screen.getByText("Connexion au terminal…")).toBeInTheDocument();
    expect(FauxWebSocket.instances.map((ws) => ws.url)).toEqual([
      `ws://${window.location.host}/api/sessions/20261017-090000-abcdef/terminal`,
    ]);
  });

  it("affiche la sortie et envoie la saisie et la taille quand l’onglet a la main", async () => {
    const { ws, terminal } = await ouvrir("ecriture");

    act(() => ws.sortie("claude prêt"));
    terminal.taper("/clear\r");

    expect(terminal.texte()).toBe("claude prêt");
    expect(terminal.options.disableStdin).toBe(false);
    expect(ws.envoyes).toEqual([{ taille: { colonnes: 120, lignes: 30 } }, { saisie: "/clear\r" }]);
    expect(screen.queryByText(/Lecture seule/)).not.toBeInTheDocument();
  });

  it("deuxième onglet : lecture seule, rien n’est envoyé", async () => {
    const { ws, terminal } = await ouvrir("lecture");

    act(() => ws.sortie("écran"));
    terminal.taper("intrus\r");

    expect(screen.getByText("Lecture seule : un autre onglet a la main.")).toBeInTheDocument();
    expect(terminal.options.disableStdin).toBe(true);
    expect(terminal.texte()).toBe("écran");
    expect(ws.envoyes).toEqual([]);
  });

  it("prend la main quand le runtime l’annonce", async () => {
    const { ws, terminal } = await ouvrir("lecture");

    act(() => ws.role("ecriture"));
    terminal.taper("a");

    expect(screen.queryByText(/Lecture seule/)).not.toBeInTheDocument();
    expect(ws.envoyes).toContainEqual({ saisie: "a" });
  });

  it("websocket fermé : terminal déconnecté, plus de saisie", async () => {
    const { ws, terminal } = await ouvrir();

    act(() => ws.fermer());
    terminal.taper("perdu");

    expect(screen.getByText("Terminal déconnecté.")).toBeInTheDocument();
    expect(ws.envoyes).not.toContainEqual({ saisie: "perdu" });
  });

  it("quitter la page ferme le websocket, pas la session", async () => {
    const { ws, terminal, unmount } = await ouvrir();
    const fetch = vi.mocked(globalThis.fetch);

    unmount();

    expect(ws.readyState).toBe(FauxWebSocket.CLOSED);
    expect(terminal.libere).toBe(true);
    expect(fetch.mock.calls.filter(([, init]) => init?.method === "POST")).toEqual([]);
  });

  it.each(["terminée", "échouée"] as const)("session %s : ni terminal ni Terminer", async (etat) => {
    rendre(session({ etat, code_sortie: etat === "terminée" ? 0 : 1, fin: "2026-10-17T10:01:00+00:00" }));

    await screen.findByRole("heading", { level: 1 });
    expect(screen.queryByRole("region", { name: "Terminal" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Terminer" })).not.toBeInTheDocument();
    expect(FauxWebSocket.instances).toEqual([]);
  });

  it("Terminer : confirmé, la session close remplace le terminal", async () => {
    const close = session({ etat: "échouée", code_sortie: 129, fin: "2026-10-17T09:30:00+00:00" });
    const fetch = simulerApi({ [CHEMIN]: session(), [`POST ${CHEMIN}/terminer`]: close });
    vi.stubGlobal("confirm", vi.fn(() => true));
    render(<VueSession id="20261017-090000-abcdef" />);

    fireEvent.click(await screen.findByRole("button", { name: "Terminer" }));

    expect(await screen.findByText("Échouée (code 129)")).toBeInTheDocument();
    expect(fetch).toHaveBeenCalledWith(`${CHEMIN}/terminer`, expect.objectContaining({ method: "POST" }));
    expect(screen.queryByRole("region", { name: "Terminal" })).not.toBeInTheDocument();
    expect(FauxWebSocket.instances[0].readyState).toBe(FauxWebSocket.CLOSED);
  });

  it("Terminer annulé : rien n’est demandé", async () => {
    const fetch = simulerApi({ [CHEMIN]: session() });
    vi.stubGlobal("confirm", vi.fn(() => false));
    render(<VueSession id="20261017-090000-abcdef" />);

    fireEvent.click(await screen.findByRole("button", { name: "Terminer" }));

    expect(fetch.mock.calls.filter(([, init]) => init?.method === "POST")).toEqual([]);
    expect(screen.getByRole("region", { name: "Terminal" })).toBeInTheDocument();
  });

  it("Terminer refusé : le message du runtime", async () => {
    simulerApi({
      [CHEMIN]: session(),
      [`POST ${CHEMIN}/terminer`]: new Response(JSON.stringify({ detail: "runner injoignable" }), { status: 502 }),
    });
    vi.stubGlobal("confirm", vi.fn(() => true));
    render(<VueSession id="20261017-090000-abcdef" />);

    fireEvent.click(await screen.findByRole("button", { name: "Terminer" }));

    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("runner injoignable"));
  });
});
