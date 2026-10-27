import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { EntreeCodespace } from "../src/api";
import { App } from "../src/App";
import { POLLING_CODESPACE_MS } from "../src/Codespace";
import { session, simulerApi } from "./donnees";
import { FauxMonaco, FauxTerminal, FauxWebSocket } from "./simulations";

const ID = "20261017-090000-abcdef";
const API = `/api/sessions/${ID}`;

function entree(nom: string, e: Partial<EntreeCodespace> = {}): EntreeCodespace {
  return { nom, type: "fichier", taille: 10, ignore: false, statut: null, ...e };
}

const RACINE = [
  entree(".git", { type: "dossier", taille: null }),
  entree("node_modules", { type: "dossier", taille: null, ignore: true }),
  entree("src", { type: "dossier", taille: null }),
  entree(".env", { ignore: true }),
  entree("fuite", { type: "lien", taille: null }),
  entree("README.md", { taille: 4 }),
];

function api(routes: Record<string, unknown> = {}) {
  return simulerApi({
    [API]: session(),
    [`${API}/codespace`]: { repo: "o/r", branche: "v0.8.0-codespace", head: "ea80c15", source: "direct" },
    [`${API}/codespace/arbre?chemin=`]: { chemin: "", entrees: RACINE },
    [`${API}/codespace/arbre?chemin=src`]: { chemin: "src", entrees: [entree("app.py", { taille: 17 })] },
    [`${API}/codespace/fichier?chemin=README.md`]: { chemin: "README.md", taille: 4, contenu: "# r\n" },
    [`${API}/codespace/fichier?chemin=src%2Fapp.py`]: {
      chemin: "src/app.py",
      taille: 17,
      contenu: "print('bonjour')\n",
    },
    ...routes,
  });
}

async function ouvrirCodespace() {
  render(<App chemin={`/sessions/${ID}/codespace`} />);
  return screen.findByRole("tabpanel", { name: "Codespace" });
}

function arbre() {
  return screen.getByRole("tree", { name: "Fichiers du codespace" });
}

describe("onglets de la page de session", () => {
  it("Terminal par défaut ; Codespace met l’URL à /sessions/<id>/codespace", async () => {
    api();
    window.history.replaceState(null, "", `/sessions/${ID}`);
    render(<App chemin={`/sessions/${ID}`} />);

    const terminal = await screen.findByRole("tab", { name: "Terminal" });
    expect(terminal).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("tabpanel", { name: "Terminal" })).toBeVisible();

    fireEvent.click(screen.getByRole("tab", { name: "Codespace" }));

    expect(window.location.pathname).toBe(`/sessions/${ID}/codespace`);
    expect(screen.getByRole("tab", { name: "Codespace" })).toHaveAttribute("aria-selected", "true");
    expect(await screen.findByRole("tabpanel", { name: "Codespace" })).toBeVisible();

    fireEvent.click(screen.getByRole("tab", { name: "Terminal" }));

    expect(window.location.pathname).toBe(`/sessions/${ID}`);
  });

  it("/sessions/<id>/codespace ouvre l’onglet Codespace", async () => {
    api();

    expect(await ouvrirCodespace()).toBeVisible();
    expect(screen.getByRole("tab", { name: "Codespace" })).toHaveAttribute("aria-selected", "true");
  });

  it("changer d’onglet garde le terminal monté et ne libère pas la Main", async () => {
    api();
    render(<App chemin={`/sessions/${ID}`} />);
    await waitFor(() => expect(FauxWebSocket.instances).toHaveLength(1));
    const [ws] = FauxWebSocket.instances;
    act(() => ws.role("ecriture"));

    fireEvent.click(screen.getByRole("tab", { name: "Codespace" }));
    await screen.findByRole("tree", { name: "Fichiers du codespace" });
    fireEvent.click(screen.getByRole("tab", { name: "Terminal" }));

    expect(FauxWebSocket.instances.filter((w) => w.url.endsWith("/terminal"))).toEqual([ws]);
    expect(ws.readyState).toBe(FauxWebSocket.OPEN);
    expect(FauxTerminal.instances[0].libere).toBe(false);
    expect(ws.envoyes).not.toContainEqual({ prendre: true });
  });

  it("le bouton Précédent du navigateur revient à l’onglet Terminal", async () => {
    api();
    window.history.replaceState(null, "", `/sessions/${ID}`);
    render(<App chemin={`/sessions/${ID}`} />);
    fireEvent.click(await screen.findByRole("tab", { name: "Codespace" }));

    act(() => {
      window.history.replaceState(null, "", `/sessions/${ID}`);
      window.dispatchEvent(new PopStateEvent("popstate"));
    });

    expect(screen.getByRole("tab", { name: "Terminal" })).toHaveAttribute("aria-selected", "true");
  });
});

describe("codespace en direct", () => {
  it("en-tête : owner/name, branche, HEAD court et lien vers la branche sur GitHub", async () => {
    api();
    const vue = await ouvrirCodespace();

    const entete = await within(vue).findByRole("group", { name: "Identité du codespace" });
    expect(entete).toHaveTextContent("o/r");
    expect(entete).toHaveTextContent("v0.8.0-codespace");
    expect(entete).toHaveTextContent("ea80c15");
    const lien = within(entete).getByRole("link", { name: "v0.8.0-codespace" });
    expect(lien).toHaveAttribute("href", "https://github.com/o/r/tree/v0.8.0-codespace");
    expect(lien).toHaveAttribute("target", "_blank");
    expect(lien).toHaveAttribute("rel", "noopener noreferrer");
  });

  it("arborescence : racine, .git et ignorés listés ; les ignorés grisés", async () => {
    api();
    await ouvrirCodespace();

    const noms = (await within(await screen.findByRole("tree")).findAllByRole("treeitem")).map((e) =>
      e.getAttribute("aria-label"),
    );
    expect(noms).toEqual([".git", "node_modules", "src", ".env", "fuite", "README.md"]);
    expect(screen.getByRole("treeitem", { name: "node_modules" })).toHaveClass("ignore");
    expect(screen.getByRole("treeitem", { name: ".env" })).toHaveClass("ignore");
    expect(screen.getByRole("treeitem", { name: "src" })).not.toHaveClass("ignore");
    expect(screen.getByRole("treeitem", { name: "fuite" })).toHaveTextContent("lien hors du clone");
  });

  it("un dossier se charge à son ouverture, et se replie", async () => {
    const fetch = api();
    await ouvrirCodespace();
    const src = await screen.findByRole("treeitem", { name: "src" });
    expect(fetch.mock.calls.map(([c]) => c)).not.toContain(`${API}/codespace/arbre?chemin=src`);

    fireEvent.click(within(src).getByRole("button", { name: "src" }));

    expect(await within(src).findByRole("treeitem", { name: "app.py" })).toBeInTheDocument();
    expect(src).toHaveAttribute("aria-expanded", "true");
    fireEvent.click(within(src).getByRole("button", { name: "src" }));
    expect(src).toHaveAttribute("aria-expanded", "false");
    expect(within(src).queryByRole("treeitem", { name: "app.py" })).toBeNull();
  });

  it("fichier texte dans Monaco en lecture seule, langage selon son nom", async () => {
    api();
    await ouvrirCodespace();

    fireEvent.click(await within(arbre()).findByRole("button", { name: "README.md" }));

    await waitFor(() => expect(FauxMonaco.editeurs).toHaveLength(1));
    const [editeur] = FauxMonaco.editeurs;
    expect(editeur.options).toMatchObject({ readOnly: true, domReadOnly: true });
    await waitFor(() => expect(editeur.modele?.getValue()).toBe("# r\n"));
    expect(editeur.modele?.uri.path).toBe("/README.md");
  });

  it("plusieurs fichiers en onglets : on passe de l’un à l’autre et on les ferme", async () => {
    api();
    await ouvrirCodespace();
    fireEvent.click(await within(arbre()).findByRole("button", { name: "README.md" }));
    fireEvent.click(within(arbre()).getByRole("button", { name: "src" }));
    fireEvent.click(await within(arbre()).findByRole("button", { name: "app.py" }));

    const onglets = screen.getByRole("tablist", { name: "Fichiers ouverts" });
    await waitFor(() => expect(FauxMonaco.editeurs[0].modele?.getValue()).toBe("print('bonjour')\n"));
    expect(within(onglets).getAllByRole("tab").map((o) => o.textContent)).toEqual([
      expect.stringContaining("README.md"),
      expect.stringContaining("app.py"),
    ]);
    expect(within(onglets).getByRole("tab", { name: /app\.py/ })).toHaveAttribute("aria-selected", "true");

    fireEvent.click(within(onglets).getByRole("tab", { name: /README\.md/ }));
    await waitFor(() => expect(FauxMonaco.editeurs[0].modele?.getValue()).toBe("# r\n"));

    fireEvent.click(within(onglets).getByRole("button", { name: "Fermer README.md" }));
    expect(within(onglets).getAllByRole("tab")).toHaveLength(1);
    await waitFor(() => expect(FauxMonaco.editeurs[0].modele?.getValue()).toBe("print('bonjour')\n"));
  });

  it.each([
    ["binaire", 11, "Fichier binaire : non affiché (11 o)"],
    ["trop_gros", 1024 * 1024 + 1, "Fichier de plus de 1 Mo : non affiché (1,0 Mo)"],
  ] as const)("fichier %s : « non affiché » avec sa taille", async (raison, taille, message) => {
    api({
      [`${API}/codespace/fichier?chemin=README.md`]: {
        chemin: "README.md",
        taille,
        contenu: null,
        non_affiche: raison,
      },
    });
    await ouvrirCodespace();

    fireEvent.click(await within(arbre()).findByRole("button", { name: "README.md" }));

    expect(await screen.findByText(message)).toBeInTheDocument();
    expect(FauxMonaco.editeurs.map((e) => e.modele)).toEqual([null]);
  });

  it("refus du runtime : son message", async () => {
    api({
      [`${API}/codespace`]: new Response(JSON.stringify({ detail: "clone de o/r absent" }), { status: 404 }),
      [`${API}/codespace/arbre?chemin=`]: new Response(JSON.stringify({ detail: "clone de o/r absent" }), {
        status: 404,
      }),
    });
    await ouvrirCodespace();

    expect(await screen.findAllByText("clone de o/r absent")).not.toHaveLength(0);
  });

  it("le codespace n’est lu qu’à la première ouverture de l’onglet", async () => {
    const fetch = api();
    render(<App chemin={`/sessions/${ID}`} />);
    await screen.findByRole("tab", { name: "Codespace" });

    expect(fetch.mock.calls.map(([c]) => c).filter((c) => c.includes("/codespace"))).toEqual([]);
  });
});

describe("Git dans le codespace", () => {
  const RACINE_GIT = [
    entree("node_modules", { type: "dossier", taille: null, ignore: true }),
    entree("src", { type: "dossier", taille: null, statut: "modifie" }),
    entree("docs", { type: "dossier", taille: null, statut: "non_suivi" }),
    entree("ajout.py", { statut: "ajoute" }),
    entree("notes.txt", { statut: "non_suivi" }),
    entree("README.md", { taille: 4, statut: "modifie" }),
    entree("LICENSE"),
  ];

  function apiGit(routes: Record<string, unknown> = {}) {
    return api({
      [`${API}/codespace/arbre?chemin=`]: { chemin: "", entrees: RACINE_GIT },
      [`${API}/codespace/fichier?chemin=README.md`]: {
        chemin: "README.md",
        taille: 13,
        contenu: "# r modifié\n",
      },
      [`${API}/codespace/fichier?chemin=ajout.py`]: {
        chemin: "ajout.py",
        taille: 6,
        contenu: "a = 1\n",
      },
      [`${API}/codespace/fichier?chemin=LICENSE`]: {
        chemin: "LICENSE",
        taille: 3,
        contenu: "MIT",
      },
      [`${API}/codespace/diff?chemin=README.md`]: {
        chemin: "README.md",
        head: "# r\n",
        courant: "# r modifié\n",
      },
      [`${API}/codespace/diff?chemin=ajout.py`]: {
        chemin: "ajout.py",
        head: null,
        courant: "a = 1\n",
      },
      ...routes,
    });
  }

  async function ouvrirFichier(nom: string) {
    await ouvrirCodespace();
    fireEvent.click(await within(arbre()).findByRole("button", { name: nom }));
    await waitFor(() => expect(FauxMonaco.editeurs[0]?.modele).not.toBeNull());
  }

  it("marqueurs modifié / ajouté / non suivi sur les fichiers, ignorés grisés", async () => {
    apiGit();
    await ouvrirCodespace();
    await within(arbre()).findAllByRole("treeitem");

    expect(within(screen.getByRole("treeitem", { name: "README.md" })).getByTitle("Modifié")).toHaveTextContent("M");
    expect(within(screen.getByRole("treeitem", { name: "ajout.py" })).getByTitle("Ajouté")).toHaveTextContent("A");
    expect(within(screen.getByRole("treeitem", { name: "notes.txt" })).getByTitle("Non suivi")).toHaveTextContent("U");
    expect(screen.getByRole("treeitem", { name: "README.md" })).toHaveClass("statut-modifie");
    expect(screen.getByRole("treeitem", { name: "LICENSE" })).not.toHaveClass("statut-modifie");
    expect(within(screen.getByRole("treeitem", { name: "LICENSE" })).queryByTitle(/./)).toBeNull();
    expect(screen.getByRole("treeitem", { name: "node_modules" })).toHaveClass("ignore");
  });

  it("un dossier qui contient des changements est marqué sans être déplié", async () => {
    const fetch = apiGit();
    await ouvrirCodespace();

    const src = await screen.findByRole("treeitem", { name: "src" });
    expect(src).toHaveAttribute("aria-expanded", "false");
    expect(src).toHaveClass("statut-modifie");
    expect(within(src).getByTitle("Contient des changements")).toBeInTheDocument();
    expect(screen.getByRole("treeitem", { name: "docs" })).toHaveClass("statut-non_suivi");
    expect(fetch.mock.calls.map(([c]) => c)).not.toContain(`${API}/codespace/arbre?chemin=src`);
  });

  it("diff d’un fichier modifié : HEAD et courant côte à côte, en lecture seule", async () => {
    apiGit();
    await ouvrirFichier("README.md");

    fireEvent.click(screen.getByRole("button", { name: "Diff avec HEAD" }));

    await waitFor(() => expect(FauxMonaco.editeursDiff).toHaveLength(1));
    const [diff] = FauxMonaco.editeursDiff;
    expect(diff.options).toMatchObject({
      readOnly: true,
      originalEditable: false,
      renderSideBySide: true,
    });
    await waitFor(() => expect(diff.modele?.original.getValue()).toBe("# r\n"));
    expect(diff.modele?.modified.getValue()).toBe("# r modifié\n");
    expect(diff.modele?.modified.uri.path).toBe("/README.md");
    expect(screen.getByRole("button", { name: "Diff avec HEAD" })).toHaveAttribute("aria-pressed", "true");

    fireEvent.click(screen.getByRole("button", { name: "Diff avec HEAD" }));

    expect(diff.libere).toBe(true);
    expect(FauxMonaco.editeurs[0].modele?.getValue()).toBe("# r modifié\n");
  });

  it("diff d’un fichier ajouté ou non suivi : côté HEAD vide", async () => {
    apiGit();
    await ouvrirFichier("ajout.py");

    fireEvent.click(screen.getByRole("button", { name: "Diff avec HEAD" }));

    await waitFor(() => expect(FauxMonaco.editeursDiff[0]?.modele?.modified.getValue()).toBe("a = 1\n"));
    expect(FauxMonaco.editeursDiff[0].modele?.original.getValue()).toBe("");
  });

  it("pas de diff pour un fichier inchangé", async () => {
    apiGit();
    await ouvrirFichier("LICENSE");

    expect(screen.queryByRole("button", { name: "Diff avec HEAD" })).toBeNull();
  });

  it("un fichier ouvert puis modifié par l’agent a son diff, sans le rouvrir", async () => {
    let racine = RACINE_GIT;
    apiGit({ [`${API}/codespace/arbre?chemin=`]: () => ({ chemin: "", entrees: racine }) });
    await ouvrirFichier("LICENSE");
    const ws = await surveillance();
    expect(screen.queryByRole("button", { name: "Diff avec HEAD" })).toBeNull();

    racine = RACINE_GIT.map((e) => (e.nom === "LICENSE" ? { ...e, statut: "modifie" as const } : e));
    act(() => ws.message({ dossiers: [""], fichier: true, entete: false }));

    expect(await screen.findByRole("button", { name: "Diff avec HEAD" })).toBeInTheDocument();
  });

  it("diff non affiché (binaire) ou refusé : son message", async () => {
    apiGit({
      [`${API}/codespace/diff?chemin=README.md`]: {
        chemin: "README.md",
        head: null,
        courant: null,
        non_affiche: "binaire",
      },
      [`${API}/codespace/diff?chemin=ajout.py`]: new Response(JSON.stringify({ detail: "ajout.py absent du clone" }), {
        status: 404,
      }),
    });
    await ouvrirFichier("README.md");
    fireEvent.click(screen.getByRole("button", { name: "Diff avec HEAD" }));

    expect(await screen.findByText("Fichier binaire : diff non affiché")).toBeInTheDocument();
    expect(FauxMonaco.editeursDiff.map((e) => e.modele)).toEqual([null]);

    fireEvent.click(within(arbre()).getByRole("button", { name: "ajout.py" }));
    fireEvent.click(await screen.findByRole("button", { name: "Diff avec HEAD" }));

    expect(await screen.findByText("ajout.py absent du clone")).toBeInTheDocument();
  });
});

/** Le websocket des changements du codespace (à côté de celui du terminal). */
function evenements(): FauxWebSocket[] {
  return FauxWebSocket.instances.filter((ws) => ws.url.endsWith("/codespace/evenements"));
}

async function surveillance(): Promise<FauxWebSocket> {
  await waitFor(() => expect(evenements()).toHaveLength(1));
  const [ws] = evenements();
  act(() => ws.accepter());
  return ws;
}

function appels(fetch: ReturnType<typeof api>, chemin: string): number {
  return fetch.mock.calls.filter(([c]) => c === chemin).length;
}

describe("codespace mis à jour en direct", () => {
  it("s’abonne aux dossiers dépliés et au fichier ouvert, derrière le runtime du cockpit", async () => {
    api();
    await ouvrirCodespace();
    const ws = await surveillance();

    expect(ws.url).toBe(`ws://${window.location.host}${API}/codespace/evenements`);
    expect(ws.envoyes.at(-1)).toEqual({ dossiers: [""], fichier: null });

    fireEvent.click(await within(arbre()).findByRole("button", { name: "src" }));
    await waitFor(() => expect(ws.envoyes.at(-1)).toEqual({ dossiers: ["", "src"], fichier: null }));

    fireEvent.click(await within(arbre()).findByRole("button", { name: "app.py" }));
    await waitFor(() => expect(ws.envoyes.at(-1)).toEqual({ dossiers: ["", "src"], fichier: "src/app.py" }));

    fireEvent.click(within(arbre()).getByRole("button", { name: "src" }));
    await waitFor(() => expect(ws.envoyes.at(-1)).toEqual({ dossiers: [""], fichier: "src/app.py" }));
  });

  it("un sous-dossier d’un dossier replié n’est plus surveillé", async () => {
    api({ [`${API}/codespace/arbre?chemin=src`]: { chemin: "src", entrees: [entree("lib", { type: "dossier" })] } });
    await ouvrirCodespace();
    const ws = await surveillance();
    fireEvent.click(await within(arbre()).findByRole("button", { name: "src" }));
    fireEvent.click(await within(arbre()).findByRole("button", { name: "lib" }));
    await waitFor(() => expect(ws.envoyes.at(-1)).toEqual({ dossiers: ["", "src", "src/lib"], fichier: null }));

    fireEvent.click(within(arbre()).getByRole("button", { name: "src" }));

    await waitFor(() => expect(ws.envoyes.at(-1)).toEqual({ dossiers: [""], fichier: null }));
  });

  it("un événement recharge, une fois, les dossiers concernés et le fichier ouvert", async () => {
    let src = [entree("app.py", { taille: 17 })];
    let contenu = "print('bonjour')\n";
    const fetch = api({
      [`${API}/codespace/arbre?chemin=src`]: () => ({ chemin: "src", entrees: src }),
      [`${API}/codespace/fichier?chemin=src%2Fapp.py`]: () => ({ chemin: "src/app.py", taille: 17, contenu }),
    });
    await ouvrirCodespace();
    const ws = await surveillance();
    fireEvent.click(await within(arbre()).findByRole("button", { name: "src" }));
    fireEvent.click(await within(arbre()).findByRole("button", { name: "app.py" }));
    await waitFor(() => expect(FauxMonaco.editeurs[0].modele?.getValue()).toBe("print('bonjour')\n"));
    const avant = {
      racine: appels(fetch, `${API}/codespace/arbre?chemin=`),
      src: appels(fetch, `${API}/codespace/arbre?chemin=src`),
      identite: appels(fetch, `${API}/codespace`),
    };

    src = [entree("app.py", { taille: 17, statut: "modifie" }), entree("neuf.py", { statut: "non_suivi" })];
    contenu = "print('au revoir')\n";
    act(() => ws.message({ dossiers: ["", "src"], fichier: true, entete: false }));

    expect(await within(arbre()).findByRole("treeitem", { name: "neuf.py" })).toBeInTheDocument();
    await waitFor(() => expect(FauxMonaco.editeurs[0].modele?.getValue()).toBe("print('au revoir')\n"));
    expect(appels(fetch, `${API}/codespace/arbre?chemin=`)).toBe(avant.racine + 1);
    expect(appels(fetch, `${API}/codespace/arbre?chemin=src`)).toBe(avant.src + 1);
    expect(appels(fetch, `${API}/codespace`)).toBe(avant.identite);
  });

  it("un fichier supprimé disparaît de l’arbre", async () => {
    let racine = RACINE;
    api({ [`${API}/codespace/arbre?chemin=`]: () => ({ chemin: "", entrees: racine }) });
    await ouvrirCodespace();
    const ws = await surveillance();
    await within(arbre()).findByRole("treeitem", { name: "README.md" });

    racine = RACINE.filter((e) => e.nom !== "README.md");
    act(() => ws.message({ dossiers: [""], fichier: false, entete: false }));

    await waitFor(() => expect(within(arbre()).queryByRole("treeitem", { name: "README.md" })).toBeNull());
  });

  it("changement de branche ou nouveau commit : l’en-tête suit", async () => {
    let identite = { repo: "o/r", branche: "v0.8.0-codespace", head: "ea80c15", source: "direct" };
    api({ [`${API}/codespace`]: () => identite });
    const vue = await ouvrirCodespace();
    const ws = await surveillance();
    await within(vue).findByText("ea80c15");

    identite = { ...identite, branche: "autre", head: "1234567" };
    act(() => ws.message({ dossiers: [], fichier: false, entete: true }));

    const entete = await within(vue).findByRole("group", { name: "Identité du codespace" });
    await waitFor(() => expect(entete).toHaveTextContent("1234567"));
    expect(within(entete).getByRole("link", { name: "autre" })).toBeInTheDocument();
  });

  it("revenir au Terminal ou quitter la page arrête la surveillance ; revenir la reprend", async () => {
    api();
    window.history.replaceState(null, "", `/sessions/${ID}/codespace`);
    const { unmount } = render(<App chemin={`/sessions/${ID}/codespace`} />);
    const ws = await surveillance();

    fireEvent.click(screen.getByRole("tab", { name: "Terminal" }));
    expect(ws.readyState).toBe(FauxWebSocket.CLOSED);

    fireEvent.click(screen.getByRole("tab", { name: "Codespace" }));
    await waitFor(() => expect(evenements()).toHaveLength(2));
    const suivant = evenements()[1];
    expect(suivant.readyState).not.toBe(FauxWebSocket.CLOSED);

    unmount();
    expect(suivant.readyState).toBe(FauxWebSocket.CLOSED);
  });

  it.each([
    ["surveillance indisponible", (ws: FauxWebSocket) => {
      ws.message({ surveillance: "indisponible" });
      ws.fermer();
    }],
    ["websocket refusé ou coupé", (ws: FauxWebSocket) => ws.fermer()],
  ])("%s : la vue se rafraîchit par polling lent", async (_cas, couper) => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const fetch = api();
    await ouvrirCodespace();
    const ws = await surveillance();
    await within(arbre()).findByRole("treeitem", { name: "README.md" });
    const avant = appels(fetch, `${API}/codespace/arbre?chemin=`);

    act(() => couper(ws));
    await act(() => vi.advanceTimersByTimeAsync(POLLING_CODESPACE_MS - 1000));
    expect(appels(fetch, `${API}/codespace/arbre?chemin=`)).toBe(avant);
    await act(() => vi.advanceTimersByTimeAsync(1000));

    expect(appels(fetch, `${API}/codespace/arbre?chemin=`)).toBe(avant + 1);
    expect(appels(fetch, `${API}/codespace`)).toBeGreaterThan(1);
  });
});

describe("codespace d’une session close : l’instantané", () => {
  const PRIS_LE = "2026-10-26T15:30:00+00:00";

  function apiInstantane(identite: Record<string, unknown>, routes: Record<string, unknown> = {}) {
    return api({
      [API]: session({ etat: "terminée", fin: PRIS_LE, code_sortie: 0 }),
      [`${API}/codespace`]: { repo: "o/r", branche: "v0.8.0-codespace", head: "ea80c15", source: "instantane", ...identite },
      ...routes,
    });
  }

  const PRESENT = { instantane: { etat: "present", pris_le: PRIS_LE } };

  it("bandeau daté, branche et HEAD de l’époque, sans surveillance", async () => {
    apiInstantane(PRESENT);
    const vue = await ouvrirCodespace();

    expect(await within(vue).findByRole("status")).toHaveTextContent(
      `Instantané de fin de session — ${new Date(PRIS_LE).toLocaleString("fr-FR", { dateStyle: "short", timeStyle: "short" })}`,
    );
    const entete = within(vue).getByRole("group", { name: "Identité du codespace" });
    expect(entete).toHaveTextContent("v0.8.0-codespace");
    expect(entete).toHaveTextContent("ea80c15");
    await within(arbre()).findByRole("treeitem", { name: "README.md" });
    expect(evenements()).toEqual([]);
  });

  it("entrées ignorées et .git/ grisées « non conservé », ni dépliables ni ouvrables", async () => {
    apiInstantane(PRESENT, {
      [`${API}/codespace/arbre?chemin=`]: {
        chemin: "",
        entrees: [
          entree(".git", { type: "dossier", taille: null, non_conserve: true }),
          entree("node_modules", { type: "dossier", taille: null, ignore: true, non_conserve: true }),
          entree(".env", { taille: null, ignore: true, non_conserve: true }),
          entree("README.md", { taille: 4, statut: "modifie", non_conserve: false }),
        ],
      },
    });
    await ouvrirCodespace();

    for (const nom of [".git", "node_modules", ".env"]) {
      const item = await within(arbre()).findByRole("treeitem", { name: nom });
      expect(item).toHaveClass("non-conserve");
      expect(item).toHaveTextContent("non conservé");
      expect(within(item).queryByRole("button")).toBeNull();
    }
    expect(within(arbre()).getByRole("treeitem", { name: "README.md" })).toHaveTextContent("M");
  });

  it("diff d’un fichier par rapport au HEAD de l’époque", async () => {
    apiInstantane(PRESENT, {
      [`${API}/codespace/arbre?chemin=`]: { chemin: "", entrees: [entree("README.md", { statut: "modifie" })] },
      [`${API}/codespace/diff?chemin=README.md`]: { chemin: "README.md", head: "# r\n", courant: "# r modifié\n" },
    });
    await ouvrirCodespace();
    fireEvent.click(await within(arbre()).findByRole("button", { name: "README.md" }));

    fireEvent.click(await screen.findByRole("button", { name: "Diff avec HEAD" }));

    await waitFor(() => expect(FauxMonaco.editeursDiff[0]?.modele?.modified.getValue()).toBe("# r modifié\n"));
    expect(FauxMonaco.editeursDiff[0].modele?.original.getValue()).toBe("# r\n");
  });

  it.each([
    [{ instantane: { etat: "absent" } }, "Pas d’instantané (session antérieure à la 0.8.0)"],
    [{ instantane: { etat: "perdu", pris_le: PRIS_LE } }, "Instantané perdu : le clone a été supprimé ou recloné depuis"],
    [
      { instantane: { etat: "erreur", pris_le: PRIS_LE, erreur: "git add a échoué" } },
      "Instantané non pris : git add a échoué",
    ],
  ])("sans instantané lisible : son message, pas d’arbre (%o)", async (identite, message) => {
    apiInstantane(identite);
    const vue = await ouvrirCodespace();

    expect(await within(vue).findByRole("status")).toHaveTextContent(message);
    expect(screen.queryByRole("tree", { name: "Fichiers du codespace" })).toBeNull();
  });
});
