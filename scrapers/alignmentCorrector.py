import pandas as pd
from tkinter import Tk, filedialog
import os
import numpy as np

def align_corpus_manual(df):
    """
    Función para alinear manualmente el corpus español-purepecha
    """
    while True:
        print("\n=== Corrector Manual de Alineamiento ===")
        print("Opciones:")
        print("1. Español adelantado - insertar vacío (desplaza ABAJO)")
        print("2. Purepecha adelantado - insertar vacío (desplaza ABAJO)") 
        print("3. Español atrasado - insertar vacío (desplaza ARRIBA)")
        print("4. Purepecha atrasado - insertar vacío (desplaza ARRIBA)")
        print("5. Eliminar fila problemática")
        print("6. Ver estadísticas del artículo")
        print("7. Salir")
        
        option = input("\nSeleccione opción (1-7): ").strip()
        
        if option == '7':
            break
            
        # Obtener artículo ID
        articleID = input("Ingrese la ID del artículo: ").strip()
        if not articleID.isdigit():
            print("ID de artículo debe ser entero")
            continue
        articleID = int(articleID)
        
        # Verificar que el artículo existe
        article_mask = (df['article_id'] == articleID)
        if not article_mask.any():
            print(f"No existe un artículo con la ID {articleID}")
            continue
            
        if option == '1':
            df = fix_spanish_ahead_down(df, articleID)
        elif option == '2':
            df = fix_purepecha_ahead_down(df, articleID)
        elif option == '3':
            df = fix_spanish_behind_up(df, articleID)
        elif option == '4':
            df = fix_purepecha_behind_up(df, articleID)
        elif option == '5':
            df = delete_problematic_row(df, articleID)
        elif option == '6':
            show_article_stats(df, articleID)
        else:
            print("Opción inválida")
    
    return df

def fix_spanish_ahead_down(df, article_id):
    """Corrige cuando el español está adelantado - desplaza hacia ABAJO"""
    try:
        start_sentence = int(input("Ingrese el número de sentencia donde COMIENZA la desalineación: "))
    except ValueError:
        print("Número inválido")
        return df
    
    # Obtener el artículo completo
    article_df = df[df['article_id'] == article_id].copy().sort_values('sentence_number')
    
    if start_sentence < 1 or start_sentence > len(article_df):
        print(f"Sentencia {start_sentence} no existe en el artículo")
        return df
    
    # Mostrar contexto antes de la corrección
    print("\n=== ANTES de la corrección ===")
    show_context(df, article_id, start_sentence, context_size=3)
    
    print(f"\nSe insertará español vacío en la sentencia {start_sentence}")
    print("y se desplazará el español hacia ABAJO a partir de ahí")
    
    confirm = input("¿Continuar? (y/n): ")
    if confirm.lower() != 'y':
        return df
    
    # Crear una copia para modificar
    article_indices = article_df.index.tolist()
    start_idx = start_sentence - 1  # Convertir a índice base 0
    
    # Modificar las filas del artículo (desplazar hacia ABAJO)
    for i in range(len(article_df) - 1, start_idx - 1, -1):
        current_idx = article_indices[i]
        
        if i == start_idx:
            # En la sentencia de inicio: mantener purepecha, vaciar español
            df.loc[current_idx, 'spanish'] = ""
        elif i > start_idx:
            # En las siguientes: español toma el valor de la anterior
            prev_idx = article_indices[i-1]
            df.loc[current_idx, 'spanish'] = article_df.iloc[i-1]['spanish']
    
    print("✓ Corrección aplicada")
    print("\n=== DESPUÉS de la corrección ===")
    show_context(df, article_id, start_sentence, context_size=3)
    
    return df

def fix_purepecha_ahead_down(df, article_id):
    """Corrige cuando el purepecha está adelantado - desplaza hacia ABAJO"""
    try:
        start_sentence = int(input("Ingrese el número de sentencia donde COMIENZA la desalineación: "))
    except ValueError:
        print("Número inválido")
        return df
    
    # Obtener el artículo completo
    article_df = df[df['article_id'] == article_id].copy().sort_values('sentence_number')
    
    if start_sentence < 1 or start_sentence > len(article_df):
        print(f"Sentencia {start_sentence} no existe en el artículo")
        return df
    
    # Mostrar contexto antes de la corrección
    print("\n=== ANTES de la corrección ===")
    show_context(df, article_id, start_sentence, context_size=3)
    
    print(f"\nSe insertará purepecha vacío en la sentencia {start_sentence}")
    print("y se desplazará el purepecha hacia ABAJO a partir de ahí")
    
    confirm = input("¿Continuar? (y/n): ")
    if confirm.lower() != 'y':
        return df
    
    # Crear una copia para modificar
    article_indices = article_df.index.tolist()
    start_idx = start_sentence - 1  # Convertir a índice base 0
    
    # Modificar las filas del artículo (desplazar hacia ABAJO)
    for i in range(len(article_df) - 1, start_idx - 1, -1):
        current_idx = article_indices[i]
        
        if i == start_idx:
            # En la sentencia de inicio: mantener español, vaciar purepecha
            df.loc[current_idx, 'purepecha'] = ""
        elif i > start_idx:
            # En las siguientes: purepecha toma el valor de la anterior
            prev_idx = article_indices[i-1]
            df.loc[current_idx, 'purepecha'] = article_df.iloc[i-1]['purepecha']
    
    print("✓ Corrección aplicada")
    print("\n=== DESPUÉS de la corrección ===")
    show_context(df, article_id, start_sentence, context_size=3)
    
    return df

def fix_spanish_behind_up(df, article_id):
    """Corrige cuando el español está atrasado - desplaza hacia ARRIBA"""
    try:
        start_sentence = int(input("Ingrese el número de sentencia donde COMIENZA la desalineación: "))
    except ValueError:
        print("Número inválido")
        return df
    
    # Obtener el artículo completo
    article_df = df[df['article_id'] == article_id].copy().sort_values('sentence_number')
    
    if start_sentence < 1 or start_sentence > len(article_df):
        print(f"Sentencia {start_sentence} no existe en el artículo")
        return df
    
    # Mostrar contexto antes de la corrección
    print("\n=== ANTES de la corrección ===")
    show_context(df, article_id, start_sentence, context_size=3)
    
    print(f"\nSe insertará español vacío en la sentencia {start_sentence}")
    print("y se desplazará el español hacia ARRIBA a partir de ahí")
    
    confirm = input("¿Continuar? (y/n): ")
    if confirm.lower() != 'y':
        return df
    
    # Crear una copia para modificar
    article_indices = article_df.index.tolist()
    start_idx = start_sentence - 1  # Convertir a índice base 0
    
    # Modificar las filas del artículo (desplazar hacia ARRIBA)
    for i in range(start_idx, len(article_df) - 1):
        current_idx = article_indices[i]
        next_idx = article_indices[i + 1]
        
        if i == start_idx:
            # En la sentencia de inicio: mantener purepecha, vaciar español
            df.loc[current_idx, 'spanish'] = ""
        else:
            # En las anteriores: español toma el valor de la siguiente
            df.loc[current_idx, 'spanish'] = article_df.iloc[i + 1]['spanish']
    
    # Para la última sentencia, dejamos español vacío
    if start_idx < len(article_df) - 1:
        last_idx = article_indices[-1]
        df.loc[last_idx, 'spanish'] = ""
    
    print("✓ Corrección aplicada")
    print("\n=== DESPUÉS de la corrección ===")
    show_context(df, article_id, start_sentence, context_size=3)
    
    return df

def fix_purepecha_behind_up(df, article_id):
    """Corrige cuando el purepecha está atrasado - desplaza hacia ARRIBA"""
    try:
        start_sentence = int(input("Ingrese el número de sentencia donde COMIENZA la desalineación: "))
    except ValueError:
        print("Número inválido")
        return df
    
    # Obtener el artículo completo
    article_df = df[df['article_id'] == article_id].copy().sort_values('sentence_number')
    
    if start_sentence < 1 or start_sentence > len(article_df):
        print(f"Sentencia {start_sentence} no existe en el artículo")
        return df
    
    # Mostrar contexto antes de la corrección
    print("\n=== ANTES de la corrección ===")
    show_context(df, article_id, start_sentence, context_size=3)
    
    print(f"\nSe insertará purepecha vacío en la sentencia {start_sentence}")
    print("y se desplazará el purepecha hacia ARRIBA a partir de ahí")
    
    confirm = input("¿Continuar? (y/n): ")
    if confirm.lower() != 'y':
        return df
    
    # Crear una copia para modificar
    article_indices = article_df.index.tolist()
    start_idx = start_sentence - 1  # Convertir a índice base 0
    
    # Modificar las filas del artículo (desplazar hacia ARRIBA)
    for i in range(start_idx, len(article_df) - 1):
        current_idx = article_indices[i]
        next_idx = article_indices[i + 1]
        
        if i == start_idx:
            # En la sentencia de inicio: mantener español, vaciar purepecha
            df.loc[current_idx, 'purepecha'] = ""
        else:
            # En las anteriores: purepecha toma el valor de la siguiente
            df.loc[current_idx, 'purepecha'] = article_df.iloc[i + 1]['purepecha']
    
    # Para la última sentencia, dejamos purepecha vacío
    if start_idx < len(article_df) - 1:
        last_idx = article_indices[-1]
        df.loc[last_idx, 'purepecha'] = ""
    
    print("✓ Corrección aplicada")
    print("\n=== DESPUÉS de la corrección ===")
    show_context(df, article_id, start_sentence, context_size=3)
    
    return df

def delete_problematic_row(df, article_id):
    """Elimina una fila problemática del artículo"""
    try:
        sentence_number = int(input("Ingrese el número de sentencia a eliminar: "))
    except ValueError:
        print("Número inválido")
        return df
        
    mask = (df['article_id'] == article_id) & (df['sentence_number'] == sentence_number)
    matching_rows = df[mask]
    
    if matching_rows.empty:
        print(f"No existe la sentencia {sentence_number} en el artículo {article_id}")
        return df
        
    idx = matching_rows.index[0]
    
    # Mostrar la fila a eliminar
    print("\nFila a eliminar:")
    row_to_delete = df.loc[idx]
    print(f"Sentencia {row_to_delete['sentence_number']}:")
    print(f"  Purepecha: {row_to_delete['purepecha']}")
    print(f"  Español:   {row_to_delete['spanish']}")
    
    confirm = input(f"\n¿Eliminar esta fila? (y/n): ")
    if confirm.lower() != 'y':
        print("Operación cancelada")
        return df
    
    # Eliminar la fila
    df_dropped = df.drop(idx).reset_index(drop=True)
    
    # Re-numerar las sentencias del artículo
    article_mask = df_dropped['article_id'] == article_id
    article_indices = df_dropped[article_mask].index
    df_dropped.loc[article_indices, 'sentence_number'] = range(1, len(article_indices) + 1)
    
    # Asegurar que sentence_number sea entero
    df_dropped['sentence_number'] = df_dropped['sentence_number'].astype(int)
    
    print(f"✓ Sentencia {sentence_number} eliminada")
    print(f"✓ El artículo {article_id} ahora tiene {len(article_indices)} sentencias")
    
    return df_dropped

def show_context(df, article_id, sentence_number, context_size=2):
    """Muestra el contexto alrededor de una sentencia"""
    article_mask = df['article_id'] == article_id
    article_df = df[article_mask].sort_values('sentence_number')
    
    if article_df.empty:
        print("Artículo no encontrado")
        return
    
    # Encontrar la posición de la sentencia
    sentence_positions = article_df['sentence_number'].values
    try:
        current_idx = np.where(sentence_positions == sentence_number)[0][0]
    except IndexError:
        print(f"Sentencia {sentence_number} no encontrada")
        return
    
    # Calcular rangos para mostrar contexto
    start_idx = max(0, current_idx - context_size)
    end_idx = min(len(article_df), current_idx + context_size + 1)
    
    context_df = article_df.iloc[start_idx:end_idx][['sentence_number', 'purepecha', 'spanish']]
    
    print(f"Contexto (sentencias {context_df['sentence_number'].iloc[0]}-{context_df['sentence_number'].iloc[-1]}):")
    for _, row in context_df.iterrows():
        marker = " >>> " if row['sentence_number'] == sentence_number else "     "
        print(f"{marker}Sentencia {int(row['sentence_number'])}:")
        purepecha_preview = str(row['purepecha'])[:50] + "..." if len(str(row['purepecha'])) > 50 else str(row['purepecha'])
        spanish_preview = str(row['spanish'])[:50] + "..." if len(str(row['spanish'])) > 50 else str(row['spanish'])
        print(f"      Purepecha: {purepecha_preview}")
        print(f"      Español:   {spanish_preview}")
        print()

def show_article_stats(df, article_id):
    """Muestra estadísticas del artículo"""
    article_df = df[df['article_id'] == article_id]
    total_rows = len(article_df)
    empty_purepecha = article_df['purepecha'].isna() | (article_df['purepecha'] == '')
    empty_spanish = article_df['spanish'].isna() | (article_df['spanish'] == '')
    
    print(f"\nEstadísticas del artículo {article_id}:")
    print(f"Total de sentencias: {total_rows}")
    print(f"Purepecha vacías: {empty_purepecha.sum()} ({empty_purepecha.sum()/total_rows*100:.1f}%)")
    print(f"Español vacíos: {empty_spanish.sum()} ({empty_spanish.sum()/total_rows*100:.1f}%)")
    print(f"Pares completos: {(~empty_purepecha & ~empty_spanish).sum()} ({(~empty_purepecha & ~empty_spanish).sum()/total_rows*100:.1f}%)")

def auto_detect_problems(df):
    """Detecta automáticamente problemas comunes de alineación"""
    print("\n=== Detección Automática de Problemas ===")
    
    problems_found = 0
    
    for article_id in df['article_id'].unique():
        article_df = df[df['article_id'] == article_id].sort_values('sentence_number')
        
        # Verificar numeración consecutiva
        expected_numbers = list(range(1, len(article_df) + 1))
        actual_numbers = article_df['sentence_number'].tolist()
        
        if actual_numbers != expected_numbers:
            print(f"Artículo {article_id}: Numeración no consecutiva")
            problems_found += 1
            
        # Detectar desalineaciones
        empty_purepecha = article_df['purepecha'].isna() | (article_df['purepecha'] == '')
        empty_spanish = article_df['spanish'].isna() | (article_df['spanish'] == '')
        
        for i in range(len(article_df) - 1):
            # Patrón: español adelantado
            if (not empty_purepecha.iloc[i] and not empty_spanish.iloc[i] and
                not empty_purepecha.iloc[i+1] and empty_spanish.iloc[i+1]):
                print(f"Artículo {article_id}: Español adelantado en sentencia {i+2}")
                problems_found += 1
            # Patrón: purepecha adelantado
            elif (not empty_purepecha.iloc[i] and not empty_spanish.iloc[i] and
                  empty_purepecha.iloc[i+1] and not empty_spanish.iloc[i+1]):
                print(f"Artículo {article_id}: Purepecha adelantado en sentencia {i+2}")
                problems_found += 1
                
    if problems_found == 0:
        print("No se detectaron problemas automáticamente")
    else:
        print(f"\nSe detectaron {problems_found} problemas potenciales")

# Función principal
def main():
    Tk().withdraw()
    filePath = filedialog.askopenfilename(
        title="Elija su archivo CSV",
        filetypes=[("CSV files", "*.csv")]
    )

    if not filePath:
        print("No hay archivo seleccionado. Saliendo...")
        return

    # Cargar el archivo
    df = pd.read_csv(filePath)
    print(f"Archivo cargado: {filePath}")
    print(f"Dimensiones: {df.shape}")
    print("Columnas:", list(df.columns))
    
    # Asegurar que sentence_number sea entero
    if df['sentence_number'].dtype != 'int64':
        df['sentence_number'] = df['sentence_number'].astype(int)
    
    # Mostrar resumen inicial
    print(f"\nResumen inicial:")
    print(f"Total de artículos: {df['article_id'].nunique()}")
    print(f"Total de sentencias: {len(df)}")
    
    # Detección automática
    auto_detect_problems(df)
    
    # Corrección manual
    df = align_corpus_manual(df)
    
    # Guardar resultado
    output_dir = "outputs/jw"
    os.makedirs(output_dir, exist_ok=True)
    input_filename = os.path.basename(filePath)
    output_file = os.path.join(output_dir, f"corrected_{input_filename}")
    
    df.to_csv(output_file, index=False)
    print(f"\nArchivo corregido guardado en: {output_file}")
    
    # Mostrar resumen final
    print(f"\nResumen final:")
    print(f"Total de artículos: {df['article_id'].nunique()}")
    print(f"Total de sentencias: {len(df)}")

if __name__ == "__main__":
    main()