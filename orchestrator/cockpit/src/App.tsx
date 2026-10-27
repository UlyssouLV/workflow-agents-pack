import { VueDetail } from "./VueDetail";
import { VueListe } from "./VueListe";
import { VueLogin } from "./VueLogin";
import { VueSession } from "./VueSession";
import { VueSessions } from "./VueSessions";

const DETAIL = /^\/repos\/([^/]+)\/([^/]+)\/?$/;
const SESSION = /^\/sessions\/([^/]+)(\/codespace)?\/?$/;

/** Routes servies toutes par `index.html` (le runtime) ; les liens rechargent la page. */
export function App({ chemin }: { chemin: string }) {
  if (chemin === "/login" || chemin === "/login/") {
    return <VueLogin />;
  }
  if (chemin === "/sessions" || chemin === "/sessions/") {
    return <VueSessions />;
  }
  const session = SESSION.exec(chemin);
  if (session) {
    return <VueSession id={decodeURIComponent(session[1])} onglet={session[2] ? "codespace" : "terminal"} />;
  }
  const detail = DETAIL.exec(chemin);
  if (detail) {
    return <VueDetail owner={decodeURIComponent(detail[1])} name={decodeURIComponent(detail[2])} />;
  }
  return <VueListe />;
}
