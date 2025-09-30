# db.py

import os
from datetime import datetime
# Importa ZoneInfo para manejar zonas horarias
from zoneinfo import ZoneInfo
from sqlalchemy import create_engine, Column, Integer, String, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# Usamos SQLite por defecto, pero Railway usará DATABASE_URL de PostgreSQL
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///tareas.db")

# Motor y sesión
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Modelo de Tareas
class Tarea(Base):
    __tablename__ = "tareas"

    id = Column(Integer, primary_key=True, index=True)
    usuario = Column(String, nullable=False)
    tipo = Column(String, nullable=False)
    referencia = Column(String, nullable=True)
    tiempo = Column(String, nullable=False)
    # CAMBIO: Usamos una función lambda con la zona horaria correcta
    fecha = Column(DateTime, default=lambda: datetime.now(ZoneInfo("America/Bogota")))

# Inicializar la base de datos
def init_db():
    Base.metadata.create_all(bind=engine)