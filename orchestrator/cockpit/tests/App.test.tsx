import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { App } from "../src/App";
import { CONNECTE, detail, liste, simulerApi } from "./donnees";

describe("routes du cockpit", () => {
  it("`/` rend la vue liste", async () => {
    simulerApi({ "/api/repos": liste() });

    render(<App chemin="/" />);

    expect(await screen.findByRole("heading", { name: "Cockpit" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Sessions" })).toHaveAttribute("href", "/sessions");
  });

  it("`/repos/<owner>/<name>` rend la vue détail de ce repo", async () => {
    const fetch = simulerApi({ "/api/auth": CONNECTE, "/api/repos/mon-org/mon.repo": detail({ slug: "mon-org/mon.repo" }) });

    render(<App chemin="/repos/mon-org/mon.repo" />);

    expect(await screen.findByRole("heading", { level: 1, name: "mon-org/mon.repo" })).toBeInTheDocument();
    expect(fetch).toHaveBeenCalledWith("/api/repos/mon-org/mon.repo", expect.anything());
  });
});
