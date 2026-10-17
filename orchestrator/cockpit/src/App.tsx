import { VueDetail } from "./VueDetail";
import { VueListe } from "./VueListe";
import { VueSession } from "./VueSession";

const DETAIL = /^\/repos\/([^/]+)\/([^/]+)\/?$/;
const SESSION = /^\/sessions\/([^/]+)\/?$/;

/** Routes servies toutes par `index.html` (le runtime) ; les liens rechargent la page. */
export function App({ chemin }: { chemin: string }) {
  const session = SESSION.exec(chemin);
  if (session) {
    return <VueSession id={decodeURIComponent(session[1])} />;
  }
  const detail = DETAIL.exec(chemin);
  if (detail) {
    return <VueDetail owner={decodeURIComponent(detail[1])} name={decodeURIComponent(detail[2])} />;
  }
  return <VueListe />;
}
