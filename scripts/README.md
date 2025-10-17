# Scripts de Inicialización y Migración

Este directorio contiene scripts para inicializar la base de datos PostgreSQL y migrar datos existentes.

## 📋 Requisitos Previos

1. **PostgreSQL 12+** instalado y ejecutándose
2. **PostGIS** extensión instalada
3. **Python 3.8+** con dependencias instaladas:
   ```bash
   pip install -r requirements.txt
   ```
4. **Archivo .env** configurado con credenciales de base de datos

## 🚀 Orden de Ejecución

### 1. Configurar Variables de Entorno

Edita el archivo `.env` en la raíz del proyecto:

```bash
DB_HOST=localhost
DB_PORT=5432
DB_NAME=jatzingueni_corpus
DB_USER=postgres
DB_PASSWORD=tu_contraseña
```

### 2. Inicializar Base de Datos

Crea la base de datos y ejecuta el schema:

```bash
python scripts/init_database.py
```

Opciones disponibles:
- `--drop`: Elimina la base de datos existente antes de crear
- `--skip-create`: Omite la creación de BD (solo ejecuta schema)
- `--schema PATH`: Usa un archivo schema.sql diferente

**Ejemplo con eliminación de BD existente:**
```bash
python scripts/init_database.py --drop
```

### 3. Aplicar Parches de Schema (Temporal)

Este paso es necesario mientras se implementa el sistema completo de jerarquías:

```bash
python scripts/patch_schema.py
```

Este script hace que algunos campos sean opcionales para permitir la migración de datos existentes.

### 4. Migrar CSVs Existentes

Migra los archivos CSV generados por `jw_scraper.py` a PostgreSQL:

```bash
python scripts/migrate_csv_to_db.py
```

Opciones disponibles:
- `--csv-dir PATH`: Directorio con CSVs (default: `outputs/jw`)
- `--csv-file FILENAME`: Migrar solo un archivo específico
- `--dry-run`: Simular sin insertar datos

**Ejemplos:**

Migrar un archivo específico:
```bash
python scripts/migrate_csv_to_db.py --csv-file sentences_20251007_210713.csv
```

Simular migración (dry run):
```bash
python scripts/migrate_csv_to_db.py --dry-run
```

## 📊 Verificar Instalación

Después de ejecutar los scripts, verifica que todo funcione:

```bash
# Conectar a PostgreSQL
psql -h localhost -U postgres -d jatzingueni_corpus

# Ver tablas creadas
\dt

# Ver estadísticas
SELECT 
    (SELECT COUNT(*) FROM sources) as fuentes,
    (SELECT COUNT(*) FROM documents) as documentos,
    (SELECT COUNT(*) FROM sentences) as sentencias,
    (SELECT COUNT(*) FROM alignments) as alineamientos;

# Salir
\q
```

## 🔧 Resolución de Problemas

### Error: "database does not exist"
Ejecuta primero `init_database.py` sin `--skip-create`

### Error: "role does not exist"
Crea el usuario en PostgreSQL:
```bash
psql -U postgres
CREATE ROLE jatzingueni_app WITH LOGIN PASSWORD 'tu_contraseña';
GRANT ALL PRIVILEGES ON DATABASE jatzingueni_corpus TO jatzingueni_app;
\q
```

### Error: "extension does not exist"
Instala PostGIS:
```bash
# Ubuntu/Debian
sudo apt-get install postgresql-postgis

# macOS (Homebrew)
brew install postgis

# Luego reconecta y ejecuta:
psql -U postgres -d jatzingueni_corpus
CREATE EXTENSION postgis;
\q
```

### Error al migrar CSV: "parent_id cannot be null"
Ejecuta `patch_schema.py` antes de la migración.

## 📝 Notas Importantes

1. **Backup antes de `--drop`**: Si tienes datos importantes, haz backup antes de usar `--drop`
2. **Schema patches son temporales**: Una vez implementadas las jerarquías completas, estos parches se revertirán
3. **Performance**: La primera migración puede tardar dependiendo del tamaño de los CSVs

## 🔄 Flujo Completo (desde cero)

```bash
# 1. Configurar entorno
cp .env.example .env
# Editar .env con tus credenciales

# 2. Inicializar BD
python scripts/init_database.py --drop

# 3. Aplicar parches temporales
python scripts/patch_schema.py

# 4. Migrar datos existentes
python scripts/migrate_csv_to_db.py

# 5. Verificar
python -c "from utils.database import get_corpus_db; db = get_corpus_db(); print(db.get_corpus_stats())"
```

## 📚 Próximos Pasos

Después de la migración exitosa:

1. Implementar sistema de jerarquías (`document_section`)
2. Ejecutar alineamiento automático con `fast_align`
3. Agregar anotaciones morfológicas
4. Exportar corpus en formatos estándar (TMX, CoNLL-U)

## 🆘 Soporte

Si encuentras problemas:
1. Revisa los logs en `logs/`
2. Verifica la configuración en `.env`
3. Consulta la documentación del schema en `database/schema.sql`
