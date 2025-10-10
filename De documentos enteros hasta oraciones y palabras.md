# Jerarquización del documento para creación de material adecuado
Hay que cubrir tanto el aspecto de entrenamiento de modelos como de conservación de corpuses lingüísticos así como poder controlar el tamaño del material de entrenamiento para los modelos, por lo que tras un poco de discusión (con modelos de IA) llegué a la conclusión de que ocupamos jerarquías estructurales (como esta estructurado el contenido) con conteo de tokens por elemento de la jerarquía. Estas van a tener un nombre general como "capítulo" o  "sección" y un número asociado que representa en que nivel están en la jerarquía, siendo la palabra obligatoriamente el nivel 0 (a nivel conceptual no almacenado como tal en la base de datos) y la oración el nivel 1 y la unidad mínima significativa para almacenamiento, de forma que todos los textos son almacenados a nivel de oración.
Veamos la diversidad en jerarquías de libros:
- La biblia:
    - Es un conjunto de libros (5), cada libro (4) tiene múltiples capítulos (3), estos tienen párrafo (2) que contienen múltiples oraciones (1).
    - Aquí un capítulo es corto y las oraciones también lo son, no cualquier libro oraciones y capítulos tan cortos.
- 1984:
    - Es libro (5) dividido en tres partes, cada parte (4) tiene varios capítulo, cada capítulo (3) tiene múltiples párrafo (2) y cada uno... oraciones (1).
    - Aquí los capítulos son más densos que aquellos de la biblia, por lo que estos podrían no aparecer en material de entrenamiento si limitamos por cantidad de tokens.
    - Aquí la "parte" tendría el mismo valor que "libro" en la biblia, puede que tengan una cantidad similar de tokens pero tienen una posición semántica distinta.

Esto va a ser básicamente un árbol de secciones representado, donde cada miembro es una entidad de una tabla, esto permitirá obtener material de entrenamiento como:
- Palabras y su traducción directa.
- Oraciones simples (menos de 80 palabras) sin contexto.
- Unidades de texto con conexión semántica que no pasen de las 1000 palabras.
- Párrafos (sin importar tamaño)
- Capítulos (sin importar tamaño).

Y si pido unidades de texto de menos de 1000 palabras puede que obtenga un pequeño fragmento de 1984 o la mitad de No tengo boca y debo gritar, sin importar que uno son varios párrafos y otros son múltiples capítulos.

Tras este tipo de organización de documentos, podríamos incluso entrenar en el futuro a un modelo que sepa hallar conexiones entre documentos "distintos" debido a las agrupaciones que hicimos nosotros.

Algo que queda como problema pendiente es la segmentación de unidades muy grandes, por ejemplo, digamos que el corpus no tiene unidades estructurales de entre 100 y 200 palabras (imaginemos que solo tenemos párrafos muy grandes con oraciones muy pequeñas), entonces hay que implementar una forma de segmentar los párrafos a nivel de oración.
Además quedan cosas con la especificación de género.