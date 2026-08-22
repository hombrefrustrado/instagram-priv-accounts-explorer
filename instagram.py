import random
import time
from typing import Any, Dict, List, Optional
import requests
from tqdm import tqdm


class Instagram:
    """
    Cliente de Instagram para consulta de perfiles y relaciones de seguidores
    utilizando una sesión con cabeceras y cookies compartidas.
    """

    BASE_URL = "https://www.instagram.com"

    # Cabeceras globales predeterminadas
    DEFAULT_HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64; rv:135.0) "
            "Gecko/20100101 Firefox/135.0"
        ),
        "Accept": "*/*",
        "Accept-Language": "es-ES,es;q=0.9,en-US;q=0.8,en;q=0.7",
        "X-IG-App-ID": "936619743392459",
        "X-ASBD-ID": "359341",
        "X-IG-WWW-Claim": "0",
        "X-IG-Max-Touch-Points": "0",
        "X-Requested-With": "XMLHttpRequest",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
    }

    def __init__(
        self,
        sessionid: str,
        ds_user_id: str,
        csrftoken: str,
        user_agent: Optional[str] = None,
    ):
        """
        Inicializa la sesión de Instagram configurando las cabeceras y cookies compartidas.
        """
        self.sessionid = str(sessionid)
        self.ds_user_id = str(ds_user_id)
        self.csrftoken = str(csrftoken)

        # Crear una sesión persistente para reusar cabeceras, cookies y conexiones HTTP
        self.session = requests.Session()

        # Configurar cabeceras globales
        headers = self.DEFAULT_HEADERS.copy()
        headers["X-CSRFToken"] = self.csrftoken
        if user_agent:
            headers["User-Agent"] = user_agent
        self.session.headers.update(headers)

        # Hook para actualizar dinámicamente X-IG-WWW-Claim y X-CSRFToken con las respuestas del servidor
        self.session.hooks["response"].append(self._on_response)

        # Configurar cookies globales compartidas
        self.session.cookies.update(
            {
                "sessionid": self.sessionid,
                "ds_user_id": self.ds_user_id,
                "csrftoken": self.csrftoken,
            }
        )

    def _on_response(
        self, response: requests.Response, *args: Any, **kwargs: Any
    ) -> requests.Response:
        """
        Hook ejecutado tras cada respuesta HTTP para sincronizar claims y tokens dinámicos.
        """
        # Actualizar X-IG-WWW-Claim dinámicamente si Instagram envía un nuevo claim
        claim = response.headers.get("x-ig-set-www-claim")
        if claim:
            self.session.headers["X-IG-WWW-Claim"] = claim

        # Actualizar CSRF token si cambia en las cookies de respuesta
        csrf = response.cookies.get("csrftoken")
        if csrf:
            self.session.headers["X-CSRFToken"] = csrf
            self.csrftoken = csrf

        return response

    def get_contacts(
        self,
        target_user_id: str,
        referer: Optional[str] = None,
        max_id: Optional[str] = None,
        count: int = 12,
    ) -> Optional[Dict[str, Any]]:
        """
        Obtiene una página de seguidores de `target_user_id`.
        """
        url = f"{self.BASE_URL}/api/v1/friendships/{target_user_id}/followers/"
        params: Dict[str, str] = {
            "count": str(count),
            "search_surface": "follow_list_page",
        }

        if max_id and str(max_id) != "0":
            params["max_id"] = str(max_id)

        req_headers = {}
        if referer:
            req_headers["Referer"] = (
                f"{self.BASE_URL}/{referer}/"
                if not referer.startswith("http")
                else referer
            )
        else:
            req_headers["Referer"] = f"{self.BASE_URL}/"

        try:
            response = self.session.get(url, params=params, headers=req_headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as err:
            print(
                f"[!] Error HTTP {err.response.status_code}: {err.response.text}"
            )
        except Exception as e:
            print(f"[!] Error inesperado en get_contacts: {e}")
        return None

    def get_all_contacts(
        self,
        target_user_id: str,
        referer: Optional[str] = None,
        delay_range: tuple = (0.5, 1.5),
        show_progress: bool = True,
        total: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Obtiene la lista completa de seguidores paginando automáticamente mediante `next_max_id`.
        Muestra una barra de progreso interactiva con tqdm contando los contactos recolectados.
        """
        print(f"[*] Obteniendo todos los seguidores para ID: {target_user_id}...")
        persons = []
        continuar = True
        max_id = None

        pbar = None
        if show_progress:
            pbar = tqdm(
                total=total,
                unit="contactos",
                desc=f"Recolectando @{referer if referer else target_user_id}",
            )

        try:
            while continuar:
                data = self.get_contacts(
                    target_user_id=target_user_id, referer=referer, max_id=max_id
                )
                if not data:
                    break

                users = data.get("users", [])
                persons.extend(users)

                if pbar:
                    pbar.update(len(users))

                continuar = data.get("has_more", False)
                max_id = data.get("next_max_id")

                if continuar and max_id:
                    time.sleep(random.uniform(*delay_range))
                else:
                    break
        finally:
            if pbar:
                pbar.close()

        print(f"[+] Total de contactos obtenidos: {len(persons)}")
        return persons

    def get_user_id(self, username: str) -> Optional[str]:
        """
        Obtiene el ID numérico de un usuario a partir de su nombre de usuario (web_profile_info).
        """
        clean_user = username.strip().lower()
        url = f"{self.BASE_URL}/api/v1/users/web_profile_info/?username={clean_user}"
        req_headers = {"Referer": f"{self.BASE_URL}/{clean_user}/"}

        try:
            response = self.session.get(url, headers=req_headers)
            response.raise_for_status()
            data = response.json()
            user_info = data.get("data", {}).get("user", {})
            if user_info:
                return user_info.get("id")
            print("[!] El usuario no existe o la cuenta no devolvió datos.")
        except requests.exceptions.HTTPError as err:
            print(
                f"[!] Error HTTP {err.response.status_code} al consultar @{clean_user}"
            )
        except Exception as e:
            print(f"[!] Error en get_user_id: {e}")
        return None

    def get_id_by_search(self, username: str) -> Optional[str]:
        """
        Busca el ID numérico de un usuario utilizando el buscador interno (topsearch).
        """
        clean_user = username.strip().lower()
        url = f"{self.BASE_URL}/web/search/topsearch/"
        params = {"query": clean_user}

        try:
            response = self.session.get(url, params=params)
            if response.status_code == 200:
                data = response.json()
                for item in data.get("users", []):
                    user = item.get("user", {})
                    if user.get("username", "").lower() == clean_user:
                        return user.get("pk")
        except Exception as e:
            print(f"[!] Error en get_id_by_search: {e}")
        return None

    def search_in_followers(
        self, target_user_id: str, search_query: str
    ) -> Optional[Dict[str, Any]]:
        """
        Busca si un usuario o query específico aparece entre los seguidores de `target_user_id`.
        """
        query_clean = search_query.strip().lower()
        url = f"{self.BASE_URL}/api/v1/friendships/{target_user_id}/followers/"

        params = {
            "count": "12",
            "query": query_clean,
            "search_surface": "follow_list_page",
        }
        req_headers = {"Referer": f"{self.BASE_URL}/"}

        try:
            response = self.session.get(url, params=params, headers=req_headers)
            response.raise_for_status()
            data = response.json()
            users = data.get("users", [])

            for user in users:
                if user.get("username", "").lower() == query_clean:
                    return {"is_follower": True, "user_data": user}

            return {"is_follower": False, "similar_results": users}

        except requests.exceptions.HTTPError as err:
            print(
                f"[!] Error HTTP {err.response.status_code}: {err.response.text}"
            )
        except Exception as e:
            print(f"[!] Error inesperado en search_in_followers: {e}")
        return None

    # Alias camelCase para mantener compatibilidad
    getContacts = get_contacts
    getAllcontacts = get_all_contacts


instagram = Instagram


