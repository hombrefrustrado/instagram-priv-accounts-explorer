Este proyecto esta destinado a explorar los contactos de una cuenta de instagram que este en privado.

Esto se consigue si conocemos de manera previa algún seguidor suyo, explorando el grafo de sus contactos. Haciendo peticiones get.

# Advertencias

- Para funcionar necesitas conocer al menos un contacto previo, y extraeras una parte del grafo pero es muy complicado extraer el grafo completo.
- Necesitas introducir datos relativos a tu cuenta de instagram para que esta herramienta funcione.
- Utiliza un gran número de peticiones get, por lo que no aseguro que no sea detectado como botting por parte de los servicios de instagram, usarlo queda bajo tu responsabilidad.
- La responsabilidad de lo que haga esta herramienta recae en la persona que la utiliza, esto es un PoC.


funcion recomendada

```python
contacts_following_to1()
```

para el analisis exploratorio se recomienda usar dorks de busqueda para encontrar contactos indexados en resultados de busqueda.


dork recomendado:
```s
site:instagram.com "@tag_persona" -inurl:tagged
```