import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { App } from "../src/App";
import { liste, simulerApi } from "./donnees";

describe("page de login cockpit", () => {
  it("`/login` affiche le formulaire, pas le contenu du cockpit", () => {
    simulerApi({ "/api/repos": liste() });

    render(<App chemin="/login" />);

    expect(screen.getByRole("heading", { name: "Connexion" })).toBeInTheDocument();
    expect(screen.getByLabelText("Identifiant")).toBeInTheDocument();
    expect(screen.getByLabelText("Mot de passe")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Se connecter" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Cockpit" })).not.toBeInTheDocument();
  });

  it("login réussi : bascule vers le cockpit", async () => {
    const assign = vi.fn();
    vi.stubGlobal("location", { ...window.location, assign });
    const fetch = simulerApi({
      "POST /api/cockpit/login": new Response(null, { status: 204 }),
    });

    render(<App chemin="/login" />);
    fireEvent.change(screen.getByLabelText("Identifiant"), { target: { value: "ops" } });
    fireEvent.change(screen.getByLabelText("Mot de passe"), { target: { value: "s3cret" } });
    fireEvent.click(screen.getByRole("button", { name: "Se connecter" }));

    await waitFor(() => expect(assign).toHaveBeenCalledWith("/"));
    expect(fetch).toHaveBeenCalledWith(
      "/api/cockpit/login",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ login: "ops", password: "s3cret" }),
      }),
    );
  });

  it("login refusé : message d’erreur, reste sur la page", async () => {
    const assign = vi.fn();
    vi.stubGlobal("location", { ...window.location, assign });
    simulerApi({
      "POST /api/cockpit/login": new Response(JSON.stringify({ detail: "identifiants invalides" }), {
        status: 401,
      }),
    });

    render(<App chemin="/login" />);
    fireEvent.change(screen.getByLabelText("Identifiant"), { target: { value: "ops" } });
    fireEvent.change(screen.getByLabelText("Mot de passe"), { target: { value: "mauvais" } });
    fireEvent.click(screen.getByRole("button", { name: "Se connecter" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("identifiants invalides");
    expect(assign).not.toHaveBeenCalled();
  });

  it("déconnexion : retour à la surface de login", async () => {
    const assign = vi.fn();
    vi.stubGlobal("location", { ...window.location, assign });
    const fetch = simulerApi({
      "/api/repos": liste(),
      "/api/sessions": { sessions: [] },
      "POST /api/cockpit/logout": new Response(null, { status: 204 }),
    });

    render(<App chemin="/" />);
    fireEvent.click(await screen.findByRole("button", { name: "Déconnexion" }));

    await waitFor(() => expect(assign).toHaveBeenCalledWith("/login"));
    expect(fetch).toHaveBeenCalledWith(
      "/api/cockpit/logout",
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("API 401 hors login : redirection vers `/login`", async () => {
    const assign = vi.fn();
    vi.stubGlobal("location", { ...window.location, assign });
    simulerApi({
      "/api/repos": new Response(JSON.stringify({ detail: "authentification requise" }), {
        status: 401,
      }),
    });

    render(<App chemin="/" />);

    await waitFor(() => expect(assign).toHaveBeenCalledWith("/login"));
  });
});
