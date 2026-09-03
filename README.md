# ⛽ GasolinApp

App mobile-first que responde una sola pregunta: **¿cuál es el grifo más conveniente cerca de mí?**
Combina precio final, distancia y descuentos de marca sobre los precios oficiales de Osinergmin. Cobertura nacional (Perú), optimizada para Lima.

## Qué hace

- Pide el GPS **al abrir la app**, con alta precisión, y muestra **tu dirección real**.
- Una sola caja arriba hace de indicador y de buscador: escribe encima para cambiar de sitio,
  incluso un cruce como *"Larco con Benavides"*.
- Combustible **Regular** o **Premium** (Premium por defecto).
- Radio de 5 / 10 / 20 km con distancia Haversine.
- Descuentos opcionales de Repsol (S/ 2.5) y Primax (S/ 1.0) sobre el precio por galón.
- Ranking de conveniencia que mezcla precio final, cercanía y descuento.
- **Mejor opción cerca de ti** destacada arriba, con el ahorro por tanque lleno (14 gal).
- Mapa con tu posición y los grifos numerados igual que las tarjetas.
- Enlaces directos a Google Maps y Waze.
- **Tema claro y oscuro** que sigue al dispositivo.

## Fuentes

| Fuente | Uso |
|---|---|
| [Osinergmin EVPC](https://www.osinergmin.gob.pe/empresas/hidrocarburos/scop/documentos-scop) | Maestro de grifos y precios (universo principal, ~5.300 estaciones) |
| `data/repsol_con_descuento_final.xlsx` | Estaciones Repsol con descuento |
| `data/primax_con_descuento_completado.xlsx` | Estaciones Primax/Coesti con descuento |
| `data/peru_districts.csv` | Centroides de los 1.874 distritos del Perú ([ubigeo-peru-aumentado](https://github.com/jmcastagnetto/ubigeo-peru-aumentado)) |
| [Photon](https://photon.komoot.io) (OpenStreetMap) | Buscar direcciones y nombrar tu ubicación |

## Correr en local

```bash
pip install -r requirements.txt
```

```bash
streamlit run app.py
```

La primera ejecución descarga y procesa el Excel de Osinergmin (~10 s). Las siguientes leen el parquet ya construido.

## Desplegar

Ver [DEPLOY.md](DEPLOY.md).

## Tema e interfaz

Tema **Ruta**: ámbar de señalización vial sobre gris asfalto, con lenguaje algo
brutalista — aristas de 3 px, bordes de 2 px, sombra sólida sin difuminar y
numeración en bloque. Tipografía Inter.

El color se define como **roles** (fondo, superficie, texto, acción, estado) en
`THEME` de `utils/constants.py`, y los mismos valores viven en `[theme]` y
`[theme.dark]` del `config.toml` para que los widgets nativos concuerden. El
modo oscuro está diseñado aparte, no es el claro invertido.

`config.toml` **no** fija `base`: así Streamlit sigue el tema del dispositivo.
El CSS cambia con `prefers-color-scheme`, sin coste de rerun. El basemap del
mapa se elige al cargar según `st.context.theme`; si cambias el tema del sistema
a mitad de sesión, la interfaz se adapta al instante pero el mapa mantiene su
estilo hasta que recargues.

## Rendimiento

- La ubicación se pide en el primer render, en paralelo con la carga de datos.
  Antes iba detrás de un botón y encadenaba un rerun antes de siquiera preguntar.
- Filtros, resultados y mapa viven en un `@st.fragment`: tocar un filtro no
  reejecuta la carga del dataset ni vuelve a resolver la ubicación.
- `compute_results` cachea el ranking por combinación de filtros.
- Medido en local: dataset desde parquet **92 ms**, ranking **6 ms**.
- Dos elementos invisibles abrían ~58 px muertos arriba: el bloque que solo
  contiene el `<style>` inyectado y el iframe del geolocalizador, cada uno con
  su gap de 16 px. El primero va en `display:none`; el segundo sale del flujo
  con `position:absolute` porque tiene que seguir ejecutándose para leer el GPS.

## Decisiones importantes

### Caché en dos capas

El Excel maestro **no se descarga ni procesa por sesión**. El flujo corre una vez al día en el servidor y todos los usuarios consumen el resultado:

```
descarga  -> data/cache/evpc_raw_YYYYMMDD.xlsx
limpieza  -> data/cache/evpc_processed_YYYYMMDD.parquet
+ descuentos -> data/cache/joined_dataset_YYYYMMDD.parquet   <- lo que sirve la app
```

Encima va `@st.cache_data(ttl=86400)` para no releer el parquet en cada interacción. Si la descarga del día falla, se sirve el último parquet válido y la UI avisa. Como último recurso está `data/evpc_seed.xlsx`, incluido en el repo para que un despliegue en frío nunca arranque vacío.

`warm_cache()` precalienta la caché (útil en un cron) y `purge_old_cache()` conserva solo los últimos días.

### Matching de descuentos

El plan original era cruzar por `CODIGO_OSINERG`. **Los datos no lo permiten:** las listas de beneficios y el maestro EVPC usan numeraciones distintas. La misma estación física (Repsol, Av. Primavera 1095, San Borja) es `14662` en la lista y `18871` en el maestro; de 290 códigos solo 12 existen en ambos, y 6 de esos 12 apuntaban a marcas distintas, o sea colisiones casuales. `NRO_REGISTRO` cruza en 0 casos.

La llave real es **marca + distrito + dirección**. El maestro identifica la marca en `RAZON` (112 Repsol, 239 Primax, consistente con las 352 filas de las listas), lo que reduce cada decisión a unas pocas candidatas. Cascada, de mayor a menor confianza:

| Nivel | Método | Confianza |
|---|---|---|
| 1 | `CODIGO_OSINERG` idéntico **y** marca coincidente | 1.00 |
| 2 | marca + distrito + dirección normalizada exacta | 0.95 |
| 3 | marca + distrito con una sola estación y una sola entrada | 0.90 |
| 4 | marca + distrito + dirección similar (asignación mutua) | 0.85 / 0.80 |

El nivel 4 no compara fila por fila: dentro de cada marca y distrito resuelve una **asignación** (el mejor par se lleva ambos lados), de modo que dos estaciones no pueden reclamar la misma entrada. El puntaje limpia ruido de lote/manzana/urbanización y premia o castiga la numeración municipal.

Todo lo que quede bajo `MATCH_MIN_CONFIDENCE` (0.70) **no recibe descuento**. Resultado: 196 de 351 estaciones de marca (56%) con descuento confirmado y cero contradicciones de marca. Bajar `FUZZY_MIN_SCORE` en `utils/constants.py` sube la cobertura a costa de precisión.

### Saneamiento de texto

Las fuentes traen mojibake real (UTF-8 y latin-1 leídos como CP932): `AV. JESUS Nﾂｺ 2307`, `IBAﾑEZ`, `BREﾑA`. `utils/cleaners.py` lo repara en dos pasadas — roundtrip completo UTF-8 y, si falla, reconstrucción byte a byte — y **solo toca cadenas con síntomas**, para no dañar texto ya correcto. Es idempotente. `ftfy` se descartó: empeora este caso concreto.

Cada campo se guarda dos veces: `*_display` (legible, con tildes, para la UI) y `*_norm` (mayúsculas sin tildes ni puntuación, para joins). Los alias de división política se resuelven ahí mismo (`PROV. CONST. DEL CALLAO` → `CALLAO`).

### Ubicación

Una sola caja arriba: su placeholder lleva la dirección ya resuelta, así que
indica dónde estás y acepta otra dirección sin salir de ahí. Antes había que
bajar hasta el pie de la página para cambiarla.

El geocoder es **Photon**, no Nominatim: resuelve cómo habla la gente aquí.
*"Larco con Benavides"* cae en la esquina correcta de Miraflores, algo que
Nominatim devuelve vacío. Se usa en los dos sentidos — texto a punto para
buscar, punto a texto para nombrar tu ubicación.

Es un servicio público y gratuito, así que se le pide poco: la búsqueda se
cachea 1 h por consulta y el reverse 24 h por coordenada redondeada a 4
decimales (~11 m, de sobra para nombrar la calle y suficiente para que el caché
sirva a toda la cuadra). **Si Photon falla o tarda, la app sigue igual**: la
caja muestra "Tu ubicación actual" y todo lo demás funciona. La
geocodificación es una comodidad, nunca un requisito.

Cuando el GPS falla, el aviso distingue qué hay que arreglar consultando la
Permissions API: permiso denegado en el navegador, o permiso concedido con la
ubicación del teléfono apagada. Son dos fallos que se ven iguales y se
resuelven distinto. Una página web no puede abrir los ajustes del sistema ni
forzar el prompt, así que lo único útil es decir exactamente qué revisar.

### Mapa

`st.map` no admite marcadores distintos ni etiquetas, así que el mapa usa
`st.pydeck_chart` (pydeck ya viene con Streamlit, sin dependencia nueva): tu
posición como punto azul con halo, y los grifos como puntos ámbar numerados.

Las estaciones sin coordenada exacta comparten el centroide de su distrito, así
que se abren en abanico determinista de ~145 m (`MAP_JITTER_DEG`) para poder
distinguirlas. Es holgadamente menor que el error que ya arrastra un centroide
distrital, donde un distrito de Lima mide kilómetros.

Detalle de pydeck: convierte los valores de texto de una capa en accesores de
datos (`"@@=Inter, sans-serif"`), lo que rompe silenciosamente `TextLayer`. Por
eso esa capa solo recibe constantes no textuales, y los literales van con doble
comilla.

### Coordenadas

**El maestro EVPC no trae coordenadas.** Sin ellas no hay distancia, así que cada estación recibe el centroide de su distrito (cobertura 100% con respaldo distrito → departamento+distrito → provincia). Cuando el match con una lista de beneficios aporta lat/lon real, esa reemplaza al centroide: hoy 196 estaciones tienen ubicación exacta y el resto se muestra con la etiqueta *ubicación aprox.*

Por lo mismo las coordenadas **no** se usan como llave de cruce: al ser centroides, cualquier estación del distrito quedaría a distancia cero de las demás.

## Limitaciones

- La distancia de las estaciones sin coordenada exacta es aproximada al centro del distrito, así que varias comparten el mismo valor.
- La cobertura de descuentos es del 56% de las estaciones de marca; el resto no alcanzó la confianza mínima y aparece sin descuento.
- Los montos de descuento son fijos (`DISCOUNTS` en `utils/constants.py`) y no reflejan condiciones por tarjeta, día o tope de galones.
- Los precios son los que cada grifo reporta a Osinergmin; pueden estar desactualizados respecto al surtidor.
- La distancia es en línea recta, no por ruta de manejo.
- En el mapa, las estaciones de un mismo distrito sin coordenada exacta aparecen
  repartidas en abanico alrededor del centro del distrito, no en su dirección real.
