import asyncio
import os
from aiogram import Bot, Dispatcher
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from dotenv import load_dotenv
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

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


# ========================
# Funciones BD
# ========================
def insertar_tarea(usuario, tipo, referencia, tiempo):
    db = SessionLocal()
    tarea = Tarea(usuario=usuario, tipo=tipo, referencia=referencia, tiempo=tiempo)
    db.add(tarea)
    db.commit()
    db.close()


def obtener_tareas():
    db = SessionLocal()
    tareas = db.query(Tarea).order_by(Tarea.fecha.desc()).all()
    db.close()
    return tareas


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
    kb.adjust(2)
    return kb.as_markup()


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
        await message.answer(
            "👋 Hola, soy tu bot de bitácora de soporte.\n\n"
            "Usa /tarea para registrar una actividad o /reporte para ver tus últimas tareas."
        )

    # /tarea → muestra botones
    @dp.message(Command("tarea"))
    async def iniciar_tarea(message: Message, state: FSMContext):
        await state.set_state(TareaForm.tipo)
        await message.answer("📌 Selecciona el tipo de tarea:", reply_markup=tipo_tarea_keyboard())

    # Callback selección tipo
    @dp.callback_query(TareaForm.tipo)
    async def set_tipo(callback: CallbackQuery, state: FSMContext):
        tipo = callback.data
        await state.update_data(tipo=tipo)

        if tipo == "correo":
            await state.set_state(TareaForm.referencia)
            await callback.message.answer("📧 Dame el ID de Freshdesk (ej: FD12345)")
        elif tipo in ["missing", "escalado"]:
            await state.set_state(TareaForm.referencia)
            await callback.message.answer("🆔 Dame el SIN o ID de Freshdesk relacionado")
        elif tipo == "consulta":
            await state.set_state(TareaForm.descripcion)
            await callback.message.answer("❓ Describe brevemente la consulta")
        elif tipo == "reunion":
            await state.set_state(TareaForm.descripcion)
            await callback.message.answer("👥 Describe la reunión (ej: Call con Houston)")
        elif tipo == "auditoria":
            await state.set_state(TareaForm.cantidad)
            await callback.message.answer("🗂 ¿Cuántos tickets fueron auditados?")
        elif tipo == "reporte":
            await state.set_state(TareaForm.nombre_reporte)
            await callback.message.answer("📊 Nombre del reporte (ej: Monthly Pending)")

        await callback.answer()

    # Referencia
    @dp.message(TareaForm.referencia)
    async def set_referencia(message: Message, state: FSMContext):
        await state.update_data(referencia=message.text)
        await state.set_state(TareaForm.tiempo)
        await message.answer("⏱ ¿Cuánto tiempo tomó? (ej: 15min)")

    # Descripción
    @dp.message(TareaForm.descripcion)
    async def set_descripcion(message: Message, state: FSMContext):
        await state.update_data(descripcion=message.text)
        await state.set_state(TareaForm.tiempo)
        await message.answer("⏱ ¿Cuánto tiempo tomó? (ej: 30min)")

    # Auditoría
    @dp.message(TareaForm.cantidad)
    async def set_cantidad(message: Message, state: FSMContext):
        await state.update_data(cantidad=message.text)
        await state.set_state(TareaForm.tiempo)
        await message.answer("⏱ ¿Cuánto tiempo tomó la auditoría? (ej: 5h)")

    # Reporte
    @dp.message(TareaForm.nombre_reporte)
    async def set_reporte(message: Message, state: FSMContext):
        await state.update_data(nombre_reporte=message.text)
        await state.set_state(TareaForm.tiempo)
        await message.answer("⏱ ¿Cuánto tiempo tomó hacer el reporte?")

    # Tiempo → registrar tarea
    @dp.message(TareaForm.tiempo)
    async def set_tiempo(message: Message, state: FSMContext):
        data = await state.get_data()
        usuario = message.from_user.username or message.from_user.first_name
        tipo = data.get("tipo")
        tiempo = message.text

        referencia = data.get("referencia", "")
        descripcion = data.get("descripcion", "")
        cantidad = data.get("cantidad", "")
        reporte = data.get("nombre_reporte", "")

        if tipo == "auditoria":
            referencia = f"{cantidad} tickets"
        elif tipo == "reporte":
            referencia = reporte
        elif tipo in ["consulta", "reunion"]:
            referencia = descripcion

        insertar_tarea(usuario, tipo, referencia, tiempo)

        await message.answer(
            f"✅ Tarea registrada:\n"
            f"👤 {usuario}\n"
            f"📌 {tipo}\n"
            f"🆔 {referencia}\n"
            f"⏱ {tiempo}"
        )

        await state.clear()

    # /reporte
    @dp.message(Command("reporte"))
    async def reporte(message: Message):
        tareas = obtener_tareas()
        if not tareas:
            await message.answer("📭 No hay tareas registradas.")
            return

        texto = "📋 Últimas tareas:\n\n"
        for t in tareas[:5]:
            texto += f"👤 {t.usuario} | 📌 {t.tipo} | 🆔 {t.referencia} | ⏱ {t.tiempo} | 📅 {t.fecha}\n"

        totales = {}
        for t in tareas:
            totales[t.tipo] = totales.get(t.tipo, 0) + 1

        texto += "\n📊 **Resumen por categoría:**\n"
        for tipo, cantidad in totales.items():
            texto += f" - {tipo}: {cantidad}\n"

        await message.answer(texto)

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
