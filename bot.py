import asyncio
import os
import re
import io
import pandas as pd
from aiogram import Bot, Dispatcher
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from dotenv import load_dotenv
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from datetime import datetime, date

from db import SessionLocal, Tarea, init_db

# ========================
# CONFIG
# ========================
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")


# ========================
# Estados del flujo FSM
# ========================
class TareaForm(StatesGroup):
    tipo = State()
    referencia = State()
    tiempo = State()
    cantidad = State()
    nombre_reporte = State()
    descripcion = State()
    facility = State()


# ========================
# Funciones BD
# ========================
def insertar_tarea(usuario, tipo, referencia, tiempo):
    db = SessionLocal()
    tarea = Tarea(usuario=usuario, tipo=tipo, referencia=referencia, tiempo=tiempo)
    db.add(tarea)
    db.commit()
    db.close()


def obtener_tareas(usuario=None, fecha=None):
    db = SessionLocal()
    query = db.query(Tarea).order_by(Tarea.fecha.desc())
    if usuario:
        query = query.filter(Tarea.usuario == usuario)
    if fecha:
        inicio = datetime.combine(fecha, datetime.min.time())
        fin = datetime.combine(fecha, datetime.max.time())
        query = query.filter(Tarea.fecha >= inicio, Tarea.fecha <= fin)
    tareas = query.all()
    db.close()
    return tareas


# ========================
# Validación y conversión de tiempo
# ========================
def validar_tiempo(texto: str) -> bool:
    patron = re.compile(r'^(\d+h)?(\d+min)?$')
    return bool(patron.match(texto))


def convertir_a_minutos(texto: str) -> int:
    horas = 0
    minutos = 0
    match = re.match(r'^(?:(\d+)h)?(?:(\d+)min)?$', texto)
    if match:
        if match.group(1):
            horas = int(match.group(1))
        if match.group(2):
            minutos = int(match.group(2))
    return horas * 60 + minutos


def formatear_minutos(mins: int) -> str:
    h, m = divmod(mins, 60)
    return f"{h}h{m:02d}min" if h else f"{m}min"


# ========================
# Teclado de tipos
# ========================
def tipo_tarea_keyboard():
    kb = InlineKeyboardBuilder()
    kb.button(text="📧 Correo", callback_data="correo")
    kb.button(text="📝 Missing field", callback_data="missing")
    kb.button(text="📤 Escalado", callback_data="escalado")
    kb.button(text="❓ Consulta", callback_data="consulta")
    kb.button(text="👥 Reunión", callback_data="reunion")
    kb.button(text="🗂 Auditoría", callback_data="auditoria")
    kb.button(text="📊 Reporte", callback_data="reporte")
    kb.button(text="📞 Llamada", callback_data="llamada")
    kb.button(text="📅 Agenda", callback_data="agenda")
    kb.adjust(2)
    return kb.as_markup()


# ========================
# Resumen de tareas
# ========================
def generar_resumen(tareas):
    if not tareas:
        return "📭 No hay tareas registradas."

    totales = {}
    tiempos = {}
    total_tiempo = 0

    for t in tareas:
        tipo = t.tipo
        totales[tipo] = totales.get(tipo, 0) + 1
        mins = convertir_a_minutos(t.tiempo)
        tiempos[tipo] = tiempos.get(tipo, 0) + mins
        total_tiempo += mins

    total_tareas = sum(totales.values())
    max_valor = max(totales.values())
    escala = 20 / max_valor if max_valor > 20 else 1

    texto = "📊 **Resumen por categoría:**\n"
    for tipo, cantidad in totales.items():
        porcentaje = (cantidad / total_tareas) * 100
        barras = "█" * int(cantidad * escala)
        texto += f"- {tipo.capitalize()}: {cantidad} ({porcentaje:.1f}%) {barras} ({formatear_minutos(tiempos[tipo])})\n"

    texto += f"\n🕒 Tiempo total: {formatear_minutos(total_tiempo)}"
    return texto


# ========================
# Exportar CSV
# ========================
def exportar_csv(tareas, filename="tareas.csv"):
    data = []
    for t in tareas:
        data.append({
            "usuario": t.usuario,
            "tipo": t.tipo,
            "referencia": t.referencia,
            "tiempo": t.tiempo,
            "tiempo_minutos": convertir_a_minutos(t.tiempo),
            "fecha": t.fecha.strftime("%Y-%m-%d %H:%M")
        })
    df = pd.DataFrame(data)
    buffer = io.StringIO()
    df.to_csv(buffer, index=False)
    buffer.seek(0)
    return buffer


# ========================
# MAIN BOT
# ========================
async def main():
    bot = Bot(token=TOKEN)
    dp = Dispatcher()

    # Inicializar DB
    init_db()

    # /start
    @dp.message(Command("start"))
    async def start(message: Message):
        await message.answer("👋 Hola, soy tu bot de bitácora de soporte.\n\n"
                             "Usa /tarea para registrar una actividad.\n"
                             "Comandos disponibles:\n"
                             "• /reporte → Tu resumen personal\n"
                             "• /reporte_hoy → Solo hoy (personal)\n"
                             "• /reporte_fecha YYYY-MM-DD → Una fecha (personal)\n"
                             "• /reporte_general → Todos los usuarios\n"
                             "• /reporte_hoy_general → Todos los usuarios (hoy)\n"
                             "• /reporte_fecha_general YYYY-MM-DD → Todos los usuarios (fecha)\n"
                             "• /export → Descargar CSV personal\n"
                             "• /export_general → Descargar CSV general")

    # ========================
    # Comandos de reportes
    # ========================
    @dp.message(Command("reporte"))
    async def reporte(message: Message):
        tareas = obtener_tareas(usuario=message.from_user.username)
        await message.answer(generar_resumen(tareas), parse_mode="Markdown")

    @dp.message(Command("reporte_hoy"))
    async def reporte_hoy(message: Message):
        tareas = obtener_tareas(usuario=message.from_user.username, fecha=date.today())
        await message.answer(generar_resumen(tareas), parse_mode="Markdown")

    @dp.message(Command("reporte_fecha"))
    async def reporte_fecha(message: Message):
        try:
            fecha_str = message.text.split(" ", 1)[1]
            fecha = datetime.strptime(fecha_str, "%Y-%m-%d").date()
        except:
            await message.answer("⚠️ Usa el formato: /reporte_fecha YYYY-MM-DD")
            return
        tareas = obtener_tareas(usuario=message.from_user.username, fecha=fecha)
        await message.answer(generar_resumen(tareas), parse_mode="Markdown")

    @dp.message(Command("reporte_general"))
    async def reporte_general(message: Message):
        tareas = obtener_tareas()
        await message.answer(generar_resumen(tareas), parse_mode="Markdown")

    @dp.message(Command("reporte_hoy_general"))
    async def reporte_hoy_general(message: Message):
        tareas = obtener_tareas(fecha=date.today())
        await message.answer(generar_resumen(tareas), parse_mode="Markdown")

    @dp.message(Command("reporte_fecha_general"))
    async def reporte_fecha_general(message: Message):
        try:
            fecha_str = message.text.split(" ", 1)[1]
            fecha = datetime.strptime(fecha_str, "%Y-%m-%d").date()
        except:
            await message.answer("⚠️ Usa el formato: /reporte_fecha_general YYYY-MM-DD")
            return
        tareas = obtener_tareas(fecha=fecha)
        await message.answer(generar_resumen(tareas), parse_mode="Markdown")

    # ========================
    # Exportar CSV
    # ========================
    @dp.message(Command("export"))
    async def exportar_personal(message: Message):
        tareas = obtener_tareas(usuario=message.from_user.username)
        buffer = exportar_csv(tareas)
        await message.answer_document(BufferedInputFile(buffer.getvalue().encode(), filename="tareas_personales.csv"))

    @dp.message(Command("export_general"))
    async def exportar_todos(message: Message):
        tareas = obtener_tareas()
        buffer = exportar_csv(tareas)
        await message.answer_document(BufferedInputFile(buffer.getvalue().encode(), filename="tareas_todos.csv"))

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
