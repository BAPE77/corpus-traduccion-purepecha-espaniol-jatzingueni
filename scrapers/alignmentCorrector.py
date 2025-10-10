import pandas as pd
from tkinter import Tk, filedialog
import os

Tk().withdraw()
filePath = filedialog.askopenfilename(
    title="Elija su archivo CSV",
    filetypes=[("CSV files", "*.csv")]
)

if not filePath:
    print("No hay archivo seleccionado. Saliendo...")
    exit()

df = pd.read_csv(filePath)
print(f"Archivo cargado: {filePath}")
print("Columnas:", list(df.columns))

while True:
    print("\nCorrector Manual de Alineamiento")
    articleID = input("Ingrese la ID del articulo ('exit' para salir): ").strip()
    if articleID.lower() == 'exit':
        break
    if not articleID.isdigit():
        print("ID de articulo debe ser entero")
        continue
    articleID = int(articleID)
    articleMask = (df['article_id'] == articleID)
    if not articleMask.any():
        print(f"No existe un articulo con la ID {articleID}. Intente de nuevo.")
        continue
    subset = df[articleMask]
    print(f"Articulo {articleID} tiene {len(subset)} sentencias.\n")
    try:
        sentenceNumber = int(input("Ingrese el numero de sentencia donde comienza el desfase: "))
    except ValueError:
        print("Numero invalido")
        continue
    columnToShift = input("Ingrese columna a recorrer (purepecha o spanish): ").strip().lower()
    if columnToShift not in ['purepecha', 'spanish']:
        print("Nombre de columna invalido")
        continue
    coincidence = df[(df['article_id'] == articleID) & (df['sentence_number'] == sentenceNumber)]
    if coincidence.empty:
        print(f"No existe una sentencia {sentenceNumber} en el articulo {articleID}")
        continue
    startID = coincidence.index[0]
    articleIndices = df[articleMask].index
    articlePos = list(articleIndices).index(startID)

    previewRange = range(max(0, articlePos - 3), min(len(subset), articlePos + 4))
    previewdf = subset.iloc[previewRange, :][['sentence_number', 'purepecha', 'spanish']]

    print("\nContexto (3 sentencias atras y adelante)")
    print(previewdf.to_string(index=False))
    confirm = input("\nProceder con el recorrimiento? (y/n): ").strip().lower()

    if confirm != 'y':
        print("Cancelado.\n")
        continue

    newRow = df.loc[startID].copy()
    newRow[columnToShift] = ""
    newRow['sentence_number'] += 0.5

    df = pd.concat(
        [df.iloc[:startID + 1], pd.DataFrame([newRow]), df.iloc[startID + 1:]],
        ignore_index=True
    )

    df.loc[df['article_id'] == articleID, 'sentence_number'] = (
        df[df['article_id'] == articleID]['sentence_number']
        .rank(method='first')
        .astype(int)
    )

    print(f"Sentencia agregada en la columna {columnToShift} despues de la sentencia {sentenceNumber} del articulo {articleID}.\n")

inputFile = os.path.basename(filePath)
outputFile = "outputs/jw/corrected_"+inputFile
df.to_csv(outputFile, index=False)
print(f"\nArchivo corregido guardado en {outputFile}")
