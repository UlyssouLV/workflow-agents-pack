import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { App } from "../src/App";
import { VueSession } from "../src/VueSession";
import { session, simulerApi } from "./donnees";

const CHEMIN = "/api/sessions/20261017-090000-abcdef";

function rendre(s = session()) {
  simulerApi({ [CHEMIN]: s });
  render(<VueSession id="20261017-090000-abcdef" />);
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
