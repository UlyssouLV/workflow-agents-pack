import { useState, type FormEvent } from "react";
import { connecterCockpit } from "./api";

/** `/login` : identifiants cockpit de l’instance (distincts de `wap-runtime auth`). */
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
    <main>
      <h1>Connexion</h1>
      <p>Identifiants cockpit de cette instance.</p>
      <form onSubmit={soumettre}>
        <p>
          <label htmlFor="login">Identifiant</label>
          <br />
          <input id="login" name="login" type="text" autoComplete="username" required disabled={enCours} />
        </p>
        <p>
          <label htmlFor="password">Mot de passe</label>
          <br />
          <input
            id="password"
            name="password"
            type="password"
            autoComplete="current-password"
            required
            disabled={enCours}
          />
        </p>
        {erreur && (
          <p role="alert" className="erreur">
            {erreur}
          </p>
        )}
        <p>
          <button type="submit" disabled={enCours}>
            Se connecter
          </button>
        </p>
      </form>
    </main>
  );
}
