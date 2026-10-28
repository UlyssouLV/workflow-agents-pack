import { CircleAlertIcon } from "lucide-react";
import { useState, type FormEvent } from "react";
import { connecterCockpit } from "./api";
import logo from "./assets/logo.png";
import { Alert, AlertDescription } from "./components/ui/alert";
import { Button } from "./components/ui/button";
import { Card } from "./components/ui/card";
import { Label } from "./components/ui/label";

const CHAMP =
  "h-9 w-full min-w-0 rounded-md border bg-background px-3 text-sm outline-none disabled:cursor-not-allowed disabled:opacity-50";

/** `/login` : identifiants cockpit de l’instance (distincts de `wap-runtime auth`). Sans coque. */
export function VueLogin() {
  const [erreur, setErreur] = useState<string | null>(null);
  const [enCours, setEnCours] = useState(false);

  async function soumettre(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    const login = String(form.get("login") ?? "");
    const password = String(form.get("password") ?? "");
    setErreur(null);
    setEnCours(true);
    try {
      await connecterCockpit(login, password);
      window.location.assign("/");
    } catch (err) {
      setErreur(err instanceof Error ? err.message : "connexion impossible");
      setEnCours(false);
    }
  }

  return (
    <main className="grid min-h-dvh place-items-center px-4 py-8">
      <div className="grid w-full max-w-[380px] justify-items-center gap-5.5">
        <img src={logo} alt="HéphaïstOS — Orchestrate · Build · Deploy" className="w-[220px] max-w-[70%] rounded-xl" />
        <Card className="w-full">
          <form onSubmit={soumettre} className="grid gap-3.5 p-5.5">
            <h1 className="text-xl">Connexion</h1>
            <p className="text-muted-foreground">Identifiants cockpit de cette instance.</p>
            <div className="grid gap-1.5">
              <Label htmlFor="login">Identifiant</Label>
              <input
                id="login"
                name="login"
                type="text"
                autoComplete="username"
                required
                disabled={enCours}
                className={CHAMP}
              />
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="password">Mot de passe</Label>
              <input
                id="password"
                name="password"
                type="password"
                autoComplete="current-password"
                required
                disabled={enCours}
                className={CHAMP}
              />
            </div>
            {erreur && (
              <Alert variant="destructive">
                <CircleAlertIcon aria-hidden />
                <AlertDescription className="text-foreground">{erreur}</AlertDescription>
              </Alert>
            )}
            <Button type="submit" size="lg" disabled={enCours}>
              Se connecter
            </Button>
          </form>
        </Card>
        <p className="text-center text-xs text-faint">
          Instance wap-runtime · identifiants créés par <code>sudo wap-runtime cockpit-auth</code>
        </p>
      </div>
    </main>
  );
}
