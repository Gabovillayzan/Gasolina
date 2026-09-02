# Despliegue

## 1. Subir a GitHub

```bash
git add -A && git commit -m "GasolinApp" && git push
```

El repo es [Gabovillayzan/Gasolina](https://github.com/Gabovillayzan/Gasolina). `data/cache/` está en `.gitignore`: se reconstruye sola en el servidor.

## 2. Desplegar en Streamlit Cloud

1. Entra a [share.streamlit.io](https://share.streamlit.io) con tu cuenta de GitHub.
2. **New app** → repo `Gabovillayzan/Gasolina`, branch `main`, archivo `app.py`.
3. En *Advanced settings* elige **Python 3.12** (o 3.11).
4. **Deploy**. El primer arranque tarda ~1 min: instala dependencias y construye la caché del día.

No hace falta configurar secrets: la app no usa credenciales.

## 3. Revisar antes de publicar

- [ ] `pip install -r requirements.txt && streamlit run app.py` corre limpio en local.
- [ ] Los tres archivos de `data/` están commiteados: los dos Excel de descuentos, `peru_districts.csv` y `evpc_seed.xlsx`.
- [ ] El pie de la app muestra la fecha de carga de Osinergmin y no el aviso de datos desactualizados.
- [ ] Probar en el celular: permitir ubicación, y también negarla para confirmar que la búsqueda manual funciona.
- [ ] Marcar y desmarcar los dos descuentos: con alguno activo salen dos bloques, sin ninguno salen 6 grifos.

## Notas de operación

- **La geolocalización exige HTTPS.** Streamlit Cloud ya lo sirve; en local funciona solo en `localhost`.
- **Osinergmin responde 403 sin `User-Agent` de navegador.** Ya va en `HTTP_HEADERS` (`utils/constants.py`); si algún día falla la descarga, revisa eso primero.
- **La URL del EVPC lleva el año en la ruta.** `EVPC_URL_FALLBACKS` prueba el año actual y el anterior. Si Osinergmin cambia el patrón, actualiza `EVPC_URL`.
- **Reinicio de la app = caché vacía.** Streamlit Cloud borra el disco al reiniciar; el primer usuario paga la reconstrucción (~10 s) y `evpc_seed.xlsx` cubre el caso de que la descarga falle en ese momento.
- Para forzar una reconstrucción: borra `data/cache/` o llama a `utils.data_loader.reset_cache()`.
