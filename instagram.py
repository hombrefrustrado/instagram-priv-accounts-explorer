from collections import deque
import json
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

    def get_user_metrics(
        self,
        user_identifier: Optional[str] = None,
        username: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Consulta las métricas clave de un perfil (conteo de seguidores, seguidos,
        si es privado, si es cuenta profesional/verificada).
        Acepta tanto nombre de usuario (@username) como ID numérico por posición o keyword (username / user_id).
        """
        target = user_id or username or user_identifier
        if not target:
            return None

        clean_target = str(target).strip()
        target_uid = None
        target_uname = None

        if clean_target.isdigit():
            target_uid = clean_target
        else:
            target_uname = clean_target.lower()
            target_uid = self.get_id_by_search(target_uname)

        # 1. Endpoint /api/v1/users/{user_id}/info/ (directo y fiable con sesión activa)
        if target_uid:
            url = f"{self.BASE_URL}/api/v1/users/{target_uid}/info/"
            req_headers = {"Referer": f"{self.BASE_URL}/"}
            try:
                response = self.session.get(url, headers=req_headers)
                if response.status_code == 200:
                    data = response.json()
                    user = data.get("user", {})
                    if user:
                        return {
                            "id": str(user.get("pk") or user.get("id")),
                            "username": user.get("username"),
                            "followers": user.get("follower_count", 0),
                            "following": user.get("following_count", 0),
                            "is_private": user.get("is_private", False),
                            "is_verified": user.get("is_verified", False),
                            "is_business": bool(
                                user.get("is_business")
                                or user.get("is_professional_account")
                                or user.get("account_type", 1) > 1
                            ),
                        }
            except Exception as e:
                print(f"[!] Error consultando /api/v1/users/{target_uid}/info/: {e}")

        # 2. Fallback a web_profile_info si disponemos de username
        uname = target_uname or (clean_target if not clean_target.isdigit() else None)
        if uname:
            url = f"{self.BASE_URL}/api/v1/users/web_profile_info/?username={uname}"
            req_headers = {"Referer": f"{self.BASE_URL}/{uname}/"}
            try:
                response = self.session.get(url, headers=req_headers)
                if response.status_code == 200:
                    data = response.json()
                    user = data.get("data", {}).get("user", {})
                    if user:
                        return {
                            "id": str(user.get("id")),
                            "username": user.get("username"),
                            "followers": user.get("edge_followed_by", {}).get("count", 0),
                            "following": user.get("edge_follow", {}).get("count", 0),
                            "is_private": user.get("is_private", False),
                            "is_verified": user.get("is_verified", False),
                            "is_business": bool(
                                user.get("is_business_account", False)
                                or user.get("is_professional_account", False)
                            ),
                        }
            except Exception as e:
                print(f"[!] Error consultando web_profile_info de @{uname}: {e}")

        return None

    def get_following(
        self,
        target_user_id: str,
        referer: Optional[str] = None,
        max_id: Optional[str] = None,
        count: int = 12,
    ) -> Optional[Dict[str, Any]]:
        """
        Obtiene una página de seguidos (following) de `target_user_id`.
        """
        url = f"{self.BASE_URL}/api/v1/friendships/{target_user_id}/following/"
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
            if "application/json" not in response.headers.get("Content-Type", ""):
                print(f"[!] Respuesta no JSON de Instagram (posible checkpoint/bloqueo). Status: {response.status_code}")
                return None
            return response.json()
        except requests.exceptions.HTTPError as err:
            print(
                f"[!] Error HTTP {err.response.status_code}: {err.response.text}"
            )
        except Exception as e:
            print(f"[!] Error inesperado en get_following: {e}")
        return None

    def get_all_following(
        self,
        target_user_id: str,
        referer: Optional[str] = None,
        delay_range: tuple = (0.5, 1.5),
        show_progress: bool = True,
        total: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Obtiene la lista completa de usuarios a los que sigue `target_user_id` paginando mediante `next_max_id`.
        """
        print(f"[*] Obteniendo todos los seguidos para ID: {target_user_id}...")
        persons = []
        continuar = True
        max_id = None

        pbar = None
        if show_progress:
            pbar = tqdm(
                total=total,
                unit="contactos",
                desc=f"Recolectando seguidos de @{referer if referer else target_user_id}",
            )

        try:
            while continuar:
                data = self.get_following(
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

        print(f"[+] Total de seguidos obtenidos: {len(persons)}")
        return persons

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
            if "application/json" not in response.headers.get("Content-Type", ""):
                print(f"[!] Respuesta no JSON de Instagram (posible checkpoint/bloqueo). Status: {response.status_code}")
                return None
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

    def search_in_following(
        self, target_user_id: str, search_query: str
    ) -> Optional[Dict[str, Any]]:
        """
        Busca si un usuario o query específico aparece en la lista de seguidos (following) de `target_user_id`.
        """
        query_clean = search_query.strip().lower()
        url = f"{self.BASE_URL}/api/v1/friendships/{target_user_id}/following/"

        params = {
            "count": "12",
            "query": query_clean,
            "search_surface": "follow_list_page",
        }
        req_headers = {"Referer": f"{self.BASE_URL}/"}

        try:
            response = self.session.get(url, params=params, headers=req_headers)
            response.raise_for_status()
            if "application/json" not in response.headers.get("Content-Type", ""):
                print(f"[!] Respuesta no JSON de Instagram (posible checkpoint/bloqueo). Status: {response.status_code}")
                return None
            data = response.json()
            users = data.get("users", [])

            for user in users:
                if user.get("username", "").lower() == query_clean:
                    return {"is_following": True, "is_follower": True, "user_data": user}

            return {"is_following": False, "is_follower": False, "similar_results": users}

        except requests.exceptions.HTTPError as err:
            print(
                f"[!] Error HTTP {err.response.status_code}: {err.response.text}"
            )
        except Exception as e:
            print(f"[!] Error inesperado en search_in_following: {e}")
        return None

    # Alias camelCase para mantener compatibilidad
    getContacts = get_contacts
    getAllcontacts = get_all_contacts
    getFollowing = get_following
    getAllfollowing = get_all_following

    def contacts_follow_to(self, contacts, target_id, target_name):
        contacts_clean = [contact for contact in contacts if contact['is_private'] == False and target_id != contact['id']]
        seguidores = []
        for contact in tqdm(contacts_clean):
            respuesta = self.search_in_followers(contact['id'], target_name)

            time.sleep(3+random.random())
            if respuesta and respuesta.get('is_follower'): 
                seguidores.append(respuesta)
        return seguidores

    def contacts_follow_to1(
        self,
        contacts: List[Dict[str, Any]],
        target_id: str | int,
        target_name: str,
        checkpoint_file: Optional[str] = "checkpoint_seguidores.jsonl",
        min_delay: float = 1.5,
        max_delay: float = 3.5,
    ) -> List[Dict[str, Any]]:
        """Busca qué contactos públicos tienen a `target_name` en sus seguidores (followers), con persistencia

        incremental y captura de excepciones.
        """
        target_id_str = str(target_id)
        target_name_clean = target_name.strip().lower()

        # 1. Filtrado seguro usando .get() y normalización a string
        contacts_clean = [
            c
            for c in contacts
            if isinstance(c, dict)
            and not c.get("is_private", True)
            and str(c.get("id", c.get("pk", ""))) != target_id_str
        ]

        seguidores = []

        try:
            for contact in tqdm(contacts_clean, desc="Verificando seguidores"):
                c_id = str(contact.get("id", contact.get("pk", "")))
                if not c_id:
                    continue

                try:
                    respuesta = self.search_in_followers(c_id, target_name_clean)

                    # 2. Validación de respuesta nula antes de indexar
                    if respuesta and isinstance(respuesta, dict):
                        if respuesta.get("is_follower"):
                            seguidores.append(contact)

                            # 3. Guardado incremental (checkpointing en tiempo real)
                            if checkpoint_file:
                                with open(
                                    checkpoint_file, "a", encoding="utf-8"
                                ) as f:
                                    f.write(
                                        json.dumps(contact, ensure_ascii=False)
                                        + "\n"
                                    )

                except Exception as e:
                    print(f"\n[!] Error procesando contacto {c_id}: {e}")

                # 4. Pausa aleatoria con jitter más amplio para evitar bloqueos
                time.sleep(random.uniform(min_delay, max_delay))

        except KeyboardInterrupt:
            print(
                f"\n[!] Proceso pausado manualmente por el usuario. Retornando {len(seguidores)} resultados parciales..."
            )

        return seguidores

    def contacts_following_to1(
        self,
        contacts: List[Dict[str, Any]],
        target_id: str | int,
        target_name: str,
        checkpoint_file: Optional[str] = "checkpoint_siguiendo.jsonl",
        min_delay: float = 1.5,
        max_delay: float = 3.5,
    ) -> List[Dict[str, Any]]:
        """Busca qué contactos públicos siguen a `target_name` consultando la lista de seguidos (following) de cada contacto,

        con persistencia incremental y captura de excepciones.
        """
        target_id_str = str(target_id)
        target_name_clean = target_name.strip().lower()

        # 1. Filtrado seguro ignorando cuentas privadas y al propio target
        contacts_clean = [
            c
            for c in contacts
            if isinstance(c, dict)
            and not c.get("is_private", True)
            and str(c.get("id", c.get("pk", ""))) != target_id_str
        ]

        seguidores = []

        try:
            for contact in tqdm(contacts_clean, desc="Verificando seguidos (following)"):
                c_id = str(contact.get("id", contact.get("pk", "")))
                if not c_id:
                    continue

                try:
                    # Se busca si target_name está en los seguidos del contacto c_id
                    respuesta = self.search_in_following(c_id, target_name_clean)

                    # 2. Validación de respuesta antes de indexar
                    if respuesta and isinstance(respuesta, dict):
                        if respuesta.get("is_following") or respuesta.get("is_follower"):
                            seguidores.append(contact)

                            # 3. Guardado incremental
                            if checkpoint_file:
                                with open(
                                    checkpoint_file, "a", encoding="utf-8"
                                ) as f:
                                    f.write(
                                        json.dumps(contact, ensure_ascii=False)
                                        + "\n"
                                    )

                except Exception as e:
                    print(f"\n[!] Error procesando contacto {c_id}: {e}")

                # 4. Pausa aleatoria
                time.sleep(random.uniform(min_delay, max_delay))

        except KeyboardInterrupt:
            print(
                f"\n[!] Proceso pausado manualmente por el usuario. Retornando {len(seguidores)} resultados parciales..."
            )

        return seguidores
    def contacts_followin_to1_explorer(
        self,
        contacts: List[Dict[str, Any]],
        target_id: str | int,
        target_name: str,
        cant: int = 10,
        checkpoint_file: Optional[str] = "checkpoint_siguiendo.jsonl",
        min_delay: float = 1.5,
        max_delay: float = 3.5,
    ) -> List[Dict[str, Any]]:
        """
        Explora el grafo de contactos usando una cola (BFS) buscando qué usuarios públicos
        siguen a `target_name`. Encola automáticamente nuevos perfiles para seguir la exploración.
        """
        target_id_str = str(target_id)
        target_name_clean = target_name.strip().lower()

        # 1. Conjunto de IDs ya visitados/encolados para evitar ciclos infinitos
        comprobados_ids = {target_id_str}

        # 2. Cola FIFO con los contactos iniciales públicos
        cola = deque()
        for c in contacts:
            if isinstance(c, dict):
                c_id = str(c.get("id", c.get("pk", "")))
                if c_id and not c.get("is_private", True) and c_id != target_id_str:
                    cola.append(c)
                    comprobados_ids.add(c_id)

        seguidores_encontrados: List[Dict[str, Any]] = []

        pbar = tqdm(total=cant, desc="Explorando grafo de seguidores", unit="match")

        try:
            while cola and len(seguidores_encontrados) < cant:
                # Extraemos el primer elemento de la cola (BFS)
                contacto_actual = cola.popleft()
                c_id = str(contacto_actual.get("id", contacto_actual.get("pk", "")))
                username_actual = contacto_actual.get("username", c_id)

                # Paso A: Comprobar si este contacto sigue al target
                try:
                    respuesta = self.search_in_following(c_id, target_name_clean)
                    if respuesta and (respuesta.get("is_following") or respuesta.get("is_follower")):
                        seguidores_encontrados.append(contacto_actual)
                        pbar.update(1)

                        if checkpoint_file:
                            with open(checkpoint_file, "a", encoding="utf-8") as f:
                                f.write(
                                    json.dumps(contacto_actual, ensure_ascii=False) + "\n"
                                )

                except Exception as e:
                    print(f"\n[!] Error comprobando relación para @{username_actual} ({c_id}): {e}")

                time.sleep(random.uniform(min_delay, max_delay))

                if len(seguidores_encontrados) >= cant:
                    break

                # Paso B: Obtener los seguidos de este usuario para expandir el grafo
                try:
                    data_following = self.get_following(c_id)
                    if data_following and isinstance(data_following, dict):
                        nuevos_usuarios = data_following.get("users", [])

                        for u in nuevos_usuarios:
                            u_id = str(u.get("id", u.get("pk", "")))
                            # Si no es privado y no ha sido visitado, lo encolamos
                            if u_id and u_id not in comprobados_ids and not u.get("is_private", True):
                                comprobados_ids.add(u_id)
                                cola.append(u)

                except Exception as e:
                    print(f"\n[!] Error expandiendo seguidos de @{username_actual}: {e}")

                time.sleep(random.uniform(min_delay, max_delay))

        except KeyboardInterrupt:
            print(
                f"\n[!] Proceso pausado manualmente. Retornando {len(seguidores_encontrados)} resultados parciales..."
            )
        finally:
            pbar.close()

        return seguidores_encontrados
instagram = Instagram


