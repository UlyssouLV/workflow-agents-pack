import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { App } from "../src/App";
import { VueSession } from "../src/VueSession";
import { session, simulerApi } from "./donnees";
import { FauxTerminal, FauxWebSocket } from "./simulations";

const CAST = [
  JSON.stringify({ version: 2, width: 100, height: 20, timestamp: 1792227600 }),
  JSON.stringify([0.01, "o", "claude prêt\r\n"]),
  JSON.stringify([0.02, "o", "au revoir"]),
].join("\n");

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
    [null, "interrompue", "Interrompue (runner redémarré)"],
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
    // L’effet qui ouvre le websocket peut passer après le rendu de la région.
    await waitFor(() => expect(FauxWebSocket.instances).toHaveLength(1));
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

  it("lecture seule : Prendre la main la demande, puis l’onglet peut taper", async () => {
    const { ws, terminal } = await ouvrir("lecture");

    fireEvent.click(screen.getByRole("button", { name: "Prendre la main" }));
    expect(ws.envoyes).toEqual([{ prendre: true }]);
    act(() => ws.role("ecriture"));
    terminal.taper("a");

    expect(screen.queryByRole("button", { name: "Prendre la main" })).not.toBeInTheDocument();
    expect(terminal.options.disableStdin).toBe(false);
    expect(ws.envoyes).toContainEqual({ saisie: "a" });
  });

  it("perdre la main : retour en lecture seule avec Prendre la main", async () => {
    const { ws, terminal } = await ouvrir("ecriture");

    act(() => ws.role("lecture"));
    terminal.taper("perdu");

    expect(screen.getByText("Lecture seule : un autre onglet a la main.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Prendre la main" })).toBeInTheDocument();
    expect(ws.envoyes).not.toContainEqual({ saisie: "perdu" });
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

  it("quitter la page sans fermer l’onglet ferme le websocket", async () => {
    // Les liens rechargent le document : le composant n’est pas démonté, la page peut rester
    // en mémoire (cache de l’historique) avec son websocket.
    const { ws } = await ouvrir();

    act(() => {
      window.dispatchEvent(new PageTransitionEvent("pagehide", { persisted: true }));
    });

    expect(ws.readyState).toBe(FauxWebSocket.CLOSED);
  });

  it("revenir par l’historique rouvre le terminal", async () => {
    const { ws } = await ouvrir();
    act(() => {
      window.dispatchEvent(new PageTransitionEvent("pagehide", { persisted: true }));
    });

    act(() => {
      window.dispatchEvent(new PageTransitionEvent("pageshow", { persisted: true }));
    });

    await waitFor(() => expect(FauxWebSocket.instances).toHaveLength(2));
    expect(ws.readyState).toBe(FauxWebSocket.CLOSED);
    expect(screen.getByText("Connexion au terminal…")).toBeInTheDocument();
    act(() => FauxWebSocket.instances[1].role("ecriture"));
    expect(screen.queryByText(/Connexion|Lecture seule|déconnecté/)).not.toBeInTheDocument();
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

describe("relecture", () => {
  const CLOSE = session({ etat: "terminée", code_sortie: 0, fin: "2026-10-17T10:01:00+00:00" });

  function rejouer(cast: unknown = new Response(CAST), s = CLOSE) {
    const fetch = simulerApi({ [CHEMIN]: s, [`${CHEMIN}/terminal.cast`]: cast });
    render(<VueSession id="20261017-090000-abcdef" />);
    return fetch;
  }

  it.each(["terminée", "échouée", "interrompue"] as const)(
    "session %s : rejoue le terminal enregistré, sans saisie ni websocket",
    async (etat) => {
      rejouer(new Response(CAST), session({ etat, code_sortie: null, fin: "2026-10-17T10:01:00+00:00" }));

      const relecture = await screen.findByRole("region", { name: "Relecture" });
      await waitFor(() => expect(FauxTerminal.instances[0]?.texte()).toBe("claude prêt\r\nau revoir"));
      const [terminal] = FauxTerminal.instances;
      expect(terminal.options.disableStdin).toBe(true);
      expect([terminal.cols, terminal.rows]).toEqual([100, 20]);
      expect(FauxWebSocket.instances).toEqual([]);
      expect(await within(relecture).findByRole("button", { name: "Rejouer" })).toBeInTheDocument();
    },
  );

  it("Rejouer repart du début", async () => {
    rejouer();
    const bouton = await screen.findByRole("button", { name: "Rejouer" });
    const [terminal] = FauxTerminal.instances;

    fireEvent.click(bouton);

    expect(terminal.texte()).toBe("");
    await waitFor(() => expect(terminal.texte()).toBe("claude prêt\r\nau revoir"));
  });

  it("Pause, Reprendre et Aller à la fin pendant la lecture", async () => {
    const lent = [
      JSON.stringify({ version: 2, width: 80, height: 24 }),
      JSON.stringify([0.01, "o", "a"]),
      JSON.stringify([30, "o", "b"]),
    ].join("\n");
    rejouer(new Response(lent));
    await waitFor(() => expect(FauxTerminal.instances[0]?.texte()).toBe("a"));
    const [terminal] = FauxTerminal.instances;

    fireEvent.click(screen.getByRole("button", { name: "Pause" }));
    fireEvent.click(await screen.findByRole("button", { name: "Reprendre" }));
    fireEvent.click(screen.getByRole("button", { name: "Aller à la fin" }));

    expect(terminal.texte()).toBe("ab");
    expect(await screen.findByRole("button", { name: "Rejouer" })).toBeInTheDocument();
  });

  it("sans enregistrement : le message du runtime", async () => {
    rejouer(new Response(JSON.stringify({ detail: "aucun enregistrement" }), { status: 404 }));

    expect(await screen.findByText("aucun enregistrement")).toBeInTheDocument();
    expect(FauxTerminal.instances).toEqual([]);
  });

  it("quitter la page arrête la relecture", async () => {
    rejouer();
    await screen.findByRole("button", { name: "Rejouer" });

    cleanup();

    expect(FauxTerminal.instances[0].libere).toBe(true);
  });

  it("session ouverte : pas de relecture", async () => {
    const fetch = rejouer(new Response(CAST), session());

    await screen.findByRole("region", { name: "Terminal" });
    expect(screen.queryByRole("region", { name: "Relecture" })).not.toBeInTheDocument();
    expect(fetch).not.toHaveBeenCalledWith(`${CHEMIN}/terminal.cast`, expect.anything());
  });
});
