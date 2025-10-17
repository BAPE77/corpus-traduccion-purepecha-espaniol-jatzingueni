"""
Inicialización de Base de Datos PostgreSQL
Crea la base de datos y ejecuta el schema.sql

Uso:
    python scripts/init_database.py [--drop] [--skip-create]
"""

import os
import sys
import argparse
from pathlib import Path

import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from dotenv import load_dotenv

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

# Load environment variables
load_dotenv()


def create_database(
    host: str,
    port: int,
    user: str,
    password: str,
    db_name: str,
    drop_existing: bool = False
):
    """
    Create PostgreSQL database
    
    Args:
        host: Database host
        port: Database port
        user: Database user
        password: Database password
        db_name: Database name to create
        drop_existing: Drop database if exists
    """
    print(f"\n{'='*60}")
    print(f"Creando base de datos: {db_name}")
    print(f"{'='*60}\n")
    
    # Connect to default 'postgres' database
    try:
        conn = psycopg2.connect(
            host=host,
            port=port,
            database='postgres',
            user=user,
            password=password
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cur = conn.cursor()
        
        # Check if database exists
        cur.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s",
            (db_name,)
        )
        exists = cur.fetchone()
        
        if exists:
            if drop_existing:
                print(f"⚠️  Base de datos '{db_name}' existe. Eliminando...")
                
                # Terminate connections
                cur.execute(f"""
                    SELECT pg_terminate_backend(pg_stat_activity.pid)
                    FROM pg_stat_activity
                    WHERE pg_stat_activity.datname = '{db_name}'
                    AND pid <> pg_backend_pid()
                """)
                
                # Drop database
                cur.execute(f"DROP DATABASE {db_name}")
                print(f"✓ Base de datos '{db_name}' eliminada")
            else:
                print(f"ℹ️  Base de datos '{db_name}' ya existe. Usando existente.")
                cur.close()
                conn.close()
                return
        
        # Create database
        cur.execute(f"CREATE DATABASE {db_name}")
        print(f"✓ Base de datos '{db_name}' creada exitosamente")
        
        cur.close()
        conn.close()
        
    except psycopg2.Error as e:
        print(f"✗ Error creando base de datos: {e}")
        sys.exit(1)


def execute_schema(
    host: str,
    port: int,
    user: str,
    password: str,
    db_name: str,
    schema_path: Path
):
    """
    Execute schema.sql file
    
    Args:
        host: Database host
        port: Database port
        user: Database user
        password: Database password
        db_name: Database name
        schema_path: Path to schema.sql file
    """
    print(f"\n{'='*60}")
    print(f"Ejecutando schema SQL")
    print(f"{'='*60}\n")
    
    if not schema_path.exists():
        print(f"✗ Schema file no encontrado: {schema_path}")
        sys.exit(1)
    
    # Read schema file
    with open(schema_path, 'r', encoding='utf-8') as f:
        schema_sql = f.read()
    
    # Connect to database
    try:
        conn = psycopg2.connect(
            host=host,
            port=port,
            database=db_name,
            user=user,
            password=password
        )
        cur = conn.cursor()
        
        print("Ejecutando schema.sql...")
        print("  - Creando extensiones...")
        print("  - Creando tipos ENUM...")
        print("  - Creando tablas...")
        
        # Execute schema
        cur.execute(schema_sql)
        conn.commit()
        
        print("✓ Schema ejecutado exitosamente")
        
        # Verify tables created
        cur.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
            ORDER BY table_name
        """)
        tables = cur.fetchall()
        
        print(f"\n✓ Tablas creadas ({len(tables)}):")
        for table in tables:
            print(f"  - {table[0]}")
        
        cur.close()
        conn.close()
        
    except psycopg2.Error as e:
        print(f"✗ Error ejecutando schema: {e}")
        sys.exit(1)


def verify_installation(
    host: str,
    port: int,
    user: str,
    password: str,
    db_name: str
):
    """Verify database installation"""
    print(f"\n{'='*60}")
    print(f"Verificando instalación")
    print(f"{'='*60}\n")
    
    try:
        conn = psycopg2.connect(
            host=host,
            port=port,
            database=db_name,
            user=user,
            password=password
        )
        cur = conn.cursor()
        
        # Check extensions
        cur.execute("""
            SELECT extname FROM pg_extension 
            WHERE extname IN ('pg_trgm', 'postgis', 'btree_gin')
        """)
        extensions = [row[0] for row in cur.fetchall()]
        
        print("Extensiones instaladas:")
        for ext in ['pg_trgm', 'postgis', 'btree_gin']:
            status = '✓' if ext in extensions else '✗'
            print(f"  {status} {ext}")
        
        # Check custom types
        cur.execute("""
            SELECT typname FROM pg_type 
            WHERE typname IN ('language_code', 'document_genre', 
                              'alignment_method', 'processing_status', 'purepecha_dialect')
        """)
        types = [row[0] for row in cur.fetchall()]
        
        print(f"\nTipos ENUM creados: {len(types)}")
        
        # Check tables
        cur.execute("""
            SELECT COUNT(*) FROM information_schema.tables 
            WHERE table_schema = 'public'
        """)
        table_count = cur.fetchone()[0]
        
        print(f"Tablas creadas: {table_count}")
        
        cur.close()
        conn.close()
        
        print("\n✓ Instalación verificada correctamente")
        
    except psycopg2.Error as e:
        print(f"✗ Error verificando instalación: {e}")
        sys.exit(1)


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Inicializar base de datos J\'atzingueni Corpus'
    )
    parser.add_argument(
        '--drop',
        action='store_true',
        help='Eliminar base de datos existente antes de crear'
    )
    parser.add_argument(
        '--skip-create',
        action='store_true',
        help='Omitir creación de base de datos (solo ejecutar schema)'
    )
    parser.add_argument(
        '--schema',
        type=str,
        default='database/schema.sql',
        help='Path al archivo schema.sql (default: database/schema.sql)'
    )
    
    args = parser.parse_args()
    
    # Get database configuration from environment
    host = os.getenv('DB_HOST', 'localhost')
    port = int(os.getenv('DB_PORT', 5432))
    user = os.getenv('DB_USER', 'postgres')
    password = os.getenv('DB_PASSWORD', '')
    db_name = os.getenv('DB_NAME', 'jatzingueni_corpus')
    
    # Get schema path
    script_dir = Path(__file__).parent.parent
    schema_path = script_dir / args.schema
    
    print(f"\n{'='*60}")
    print(f"J'atzingueni Corpus - Inicialización de Base de Datos")
    print(f"{'='*60}\n")
    print(f"Host: {host}:{port}")
    print(f"Usuario: {user}")
    print(f"Base de datos: {db_name}")
    print(f"Schema: {schema_path}")
    
    # Step 1: Create database
    if not args.skip_create:
        create_database(host, port, user, password, db_name, args.drop)
    else:
        print("\nℹ️  Omitiendo creación de base de datos")
    
    # Step 2: Execute schema
    execute_schema(host, port, user, password, db_name, schema_path)
    
    # Step 3: Verify installation
    verify_installation(host, port, user, password, db_name)
    
    print(f"\n{'='*60}")
    print(f"✓ Inicialización completada")
    print(f"{'='*60}\n")
    print("Siguiente paso:")
    print("  python scripts/migrate_csv_to_db.py")


if __name__ == '__main__':
    main()
