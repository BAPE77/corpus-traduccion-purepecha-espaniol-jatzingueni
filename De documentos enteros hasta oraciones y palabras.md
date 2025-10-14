# Jerarquización del documento para creación de material adecuado
Hay que cubrir tanto el aspecto de entrenamiento de modelos como de conservación de corpuses lingüísticos así como poder controlar el tamaño del material de entrenamiento para los modelos, por lo que tras un poco de discusión (con modelos de IA) llegué a la conclusión de que ocupamos jerarquías estructurales (como esta estructurado el contenido) con conteo de tokens por elemento de la jerarquía. Estas van a ser descritas con:
- Tipo de miembro de jerarquía: un nombre alusivo a su rol estructural en el documento (por ejemplo: "capítulo", "sección" o "parte") junto con un número indicando su nivel en la jerarquía del documento específico.
- Instancia de miembro de la jerarquía: a su vez cada "capítulo" (o cualquier instancia de miembro de jerarquía) tendrá un número de secuencia así como un nombre descriptivo del capítulo (cuando aplique) para indicar la secuencia de estos en el documento.

Con esto podrías, por ejemplo, definir los siguientes datos para los siguientes libros:
- Biblia (NVI/NIV):
    - Tiene como tipos de estructuras: conjunto de libro (5), libro (4), capítulo (3), párrafo (2), y oraciones (1).
    - Y instancias de miembros en la jerarquía tenemos por ejemplo: la primera instancia de capítulo podría ser "Génesis I" con identificador (1), y la segunda instancia de una oración podría ser "La tierra era un caos total, ...".
- 1984:
    - Como tipos estructurales: libro (5), parte (4), capítulo (3), párrafo (2), oración (1).
    - Y como instancias tendremos una sola instancia de libro, tres instancias de partes, varias de capítulo y muchas más de párrafo y oración.

Y claro, habrá un conteo de tokens (palabras completas) por cada instancia de estructura en el documento, esto para poder seleccionar adecuadamente los datos de entrenamiento para los modelos. Por ejemplo si dijéramos que queremos "capítulos" eso podría ser problemático para el entrenamiento, libros como "No tengo boca y debo gritar" no tienen capítulos, 1984 tiene capítulos de 3000 a 5000 palabras, y la biblia tiene capítulos de menos de 1000 palabras; es entonces necesario no solo ser capaz de pedir "capítulos" sino también poder pedir "unidades textuales de hasta 2000 palabras", así tendrás a tu alcance muchos distintos tipos de obras con distinta clase de complejidad.  

Finalmente esto va a ser la representación un árbol de secciones con nombre variables, cada instancia de sección tendrá uno o varios padres (un párrafo podría tener de padre a un capítulo, y así muchos párrafos dentro de una secuencia) dentro de una entidad `section_instance`, esto permitirá obtener material de entrenamiento como:
- Traducción de palabras individuales a muchas traducciones válidas (una palabra puede variar en otro idioma dependiendo del contexto).
- Oraciones sin contexto: pudiendo escoger de que tamaño queremos las oraciones.
- Unidades de texto con conexión semántica que no pasen de las 1000 palabras.
- Párrafos (sin importar tamaño).
- Capítulos (sin importar tamaño).


## Niveles inferiores
Finalmente, este diseño busca que el nivel 1 siempre sean las oraciones, ya que este es el nivel mínimo para que un modelo pueda hacer traducciones automáticas con coherencia. Conceptualmente definimos también el nivel 0 que corresponde al nivel de token lingüístico (palabra), el nivel -1 para los morfemas y el nivel -2 para dígrafos. Estos últimos dos son requeridos definirlos como parte de las anotaciones morfosintácticas y definición del alfabeto, lo que al final acelerará el entrenamiento y mejorará la calidad del corpus.

## Segmentación
A la hora de tomar material de entrenamiento puede que no encontremos "unidades textuales de entre 200 y hasta 900 palabras" porque, digamos, todos los capítulos de la biblia son de más de 1000 palabras y sus párrafos son de 100 palabras. Para esto también tendremos que implementar algún tipo de 'segmentación' de unidades textuales, de forma que podamos, por ejemplo, cortar "Génesis I" hasta las 870 palabras (evitando párrafos u oraciones cortadas).  El como se hará esto queda pendiente.

## Otras cosas pendientes
- Filtrado de género literario (para evitar demasiado sesgo religioso, o demasiado texto en prosa).
- Mecanismo de alineamiento de documentos a nivel de oración y párrafo, ¿qué pasa cuando un párrafo en Español son dos en Purépecha?.