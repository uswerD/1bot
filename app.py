```python
import asyncio
import os
import sqlite3
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder


# =========================================================
# НАСТРОЙКИ
# =========================================================

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

DB_NAME = "tire_service.db"

WORK_START = 9
WORK_END = 19
SLOT_MINUTES = 60


if not TOKEN:
    raise RuntimeError("Не задан BOT_TOKEN")

if not ADMIN_ID:
    raise RuntimeError("Не задан ADMIN_ID")


bot = Bot(TOKEN)
dp = Dispatcher()


# =========================================================
# БАЗА ДАННЫХ
# =========================================================

def db_connect():
    return sqlite3.connect(DB_NAME)


def init_db():
    conn = db_connect()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            phone TEXT NOT NULL,
            date TEXT NOT NULL,
            time TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)

    conn.commit()
    conn.close()


def get_booking(date, time):
    conn = db_connect()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT *
        FROM bookings
        WHERE date = ? AND time = ?
    """, (date, time))

    result = cursor.fetchone()

    conn.close()

    return result


def create_booking(user_id, name, phone, date, time):
    conn = db_connect()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO bookings
        (user_id, name, phone, date, time, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        user_id,
        name,
        phone,
        date,
        time,
        datetime.now().isoformat()
    ))

    conn.commit()
    booking_id = cursor.lastrowid

    conn.close()

    return booking_id


def get_user_bookings(user_id):
    conn = db_connect()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, name, phone, date, time
        FROM bookings
        WHERE user_id = ?
        ORDER BY date, time
    """, (user_id,))

    result = cursor.fetchall()

    conn.close()

    return result


def get_bookings_for_date(date):
    conn = db_connect()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, user_id, name, phone, date, time
        FROM bookings
        WHERE date = ?
        ORDER BY time
    """, (date,))

    result = cursor.fetchall()

    conn.close()

    return result


def delete_booking(booking_id):
    conn = db_connect()
    cursor = conn.cursor()

    cursor.execute("""
        DELETE FROM bookings
        WHERE id = ?
    """, (booking_id,))

    conn.commit()
    deleted = cursor.rowcount

    conn.close()

    return deleted


# =========================================================
# ВРЕМЕННЫЕ СЛОТЫ
# =========================================================

def make_slots():
    slots = []

    current = WORK_START * 60

    while current < WORK_END * 60:
        hour = current // 60
        minute = current % 60

        slots.append(f"{hour:02d}:{minute:02d}")

        current += SLOT_MINUTES

    return slots


# =========================================================
# КЛАВИАТУРЫ
# =========================================================

def main_menu():
    kb = InlineKeyboardBuilder()

    kb.button(
        text="🔧 Записаться",
        callback_data="book"
    )

    kb.button(
        text="📋 Мои записи",
        callback_data="my_bookings"
    )

    kb.button(
        text="📍 Адрес",
        callback_data="address"
    )

    kb.adjust(1)

    return kb.as_markup()


def admin_menu():
    kb = InlineKeyboardBuilder()

    kb.button(
        text="📅 Сегодня",
        callback_data="admin_today"
    )

    kb.button(
        text="📆 Завтра",
        callback_data="admin_tomorrow"
    )

    kb.button(
        text="❌ Удалить запись",
        callback_data="admin_delete"
    )

    kb.adjust(1)

    return kb.as_markup()


# =========================================================
# ВРЕМЕННОЕ ХРАНИЛИЩЕ СОСТОЯНИЯ ПОЛЬЗОВАТЕЛЕЙ
# =========================================================

pending_bookings = {}


# =========================================================
# СТАРТ
# =========================================================

@dp.message(CommandStart())
async def start(message: Message):

    await message.answer(
        "🚗 ШИНОМОНТАЖ\n\n"
        "Запись на шиномонтаж онлайн.\n\n"
        "Выберите действие:",
        reply_markup=main_menu()
    )


# =========================================================
# ЗАПИСЬ
# =========================================================

@dp.callback_query(F.data == "book")
async def choose_date(callback: CallbackQuery):

    kb = InlineKeyboardBuilder()

    today = datetime.now()

    for i in range(7):

        date = today + timedelta(days=i)

        text = date.strftime("%d.%m")

        if i == 0:
            text += " — сегодня"

        elif i == 1:
            text += " — завтра"

        kb.button(
            text=text,
            callback_data=f"date:{date.strftime('%Y-%m-%d')}"
        )

    kb.adjust(2)

    await callback.message.edit_text(
        "📅 Выберите дату:",
        reply_markup=kb.as_markup()
    )

    await callback.answer()


@dp.callback_query(F.data.startswith("date:"))
async def choose_time(callback: CallbackQuery):

    date = callback.data.split(":")[1]

    kb = InlineKeyboardBuilder()

    for slot in make_slots():

        # Проверяем БД
        if get_booking(date, slot):
            continue

        kb.button(
            text=slot,
            callback_data=f"time:{date}:{slot}"
        )

    kb.adjust(3)

    readable_date = datetime.strptime(
        date,
        "%Y-%m-%d"
    ).strftime("%d.%m.%Y")

    await callback.message.edit_text(
        f"📅 {readable_date}\n\n"
        "Выберите свободное время:",
        reply_markup=kb.as_markup()
    )

    await callback.answer()


@dp.callback_query(F.data.startswith("time:"))
async def choose_phone(callback: CallbackQuery):

    _, date, time = callback.data.split(":")

    pending_bookings[callback.from_user.id] = {
        "date": date,
        "time": time
    }

    await callback.message.edit_text(
        f"📅 {datetime.strptime(date, '%Y-%m-%d').strftime('%d.%m.%Y')}\n"
        f"⏰ {time}\n\n"
        "📞 Теперь отправьте номер телефона."
    )

    await callback.answer()


@dp.message(F.text)
async def receive_phone(message: Message):

    user_id = message.from_user.id

    if user_id not in pending_bookings:
        return

    booking = pending_bookings[user_id]

    phone = message.text.strip()

    date = booking["date"]
    time = booking["time"]

    # Повторная проверка
    # вдруг этот слот уже заняли
    if get_booking(date, time):

        del pending_bookings[user_id]

        await message.answer(
            "❌ К сожалению, это время уже заняли.\n\n"
            "Выберите другое время.",
            reply_markup=main_menu()
        )

        return

    booking_id = create_booking(
        user_id=user_id,
        name=message.from_user.full_name,
        phone=phone,
        date=date,
        time=time
    )

    del pending_bookings[user_id]

    readable_date = datetime.strptime(
        date,
        "%Y-%m-%d"
    ).strftime("%d.%m.%Y")

    await message.answer(
        "✅ ЗАПИСЬ ПОДТВЕРЖДЕНА!\n\n"
        f"📅 {readable_date}\n"
        f"⏰ {time}\n"
        f"📞 {phone}\n\n"
        "Ждём вас на шиномонтаже.",
        reply_markup=main_menu()
    )

    # Уведомление администратору
    await bot.send_message(
        ADMIN_ID,
        "🔔 НОВАЯ ЗАПИСЬ\n\n"
        f"№ {booking_id}\n"
        f"👤 {message.from_user.full_name}\n"
        f"📞 {phone}\n"
        f"📅 {readable_date}\n"
        f"⏰ {time}"
    )


# =========================================================
# МОИ ЗАПИСИ
# =========================================================

@dp.callback_query(F.data == "my_bookings")
async def my_bookings(callback: CallbackQuery):

    bookings = get_user_bookings(
        callback.from_user.id
    )

    if not bookings:

        await callback.message.edit_text(
            "📋 У вас пока нет записей.",
            reply_markup=main_menu()
        )

        await callback.answer()
        return

    text = "📋 ВАШИ ЗАПИСИ\n\n"

    for booking in bookings:

        booking_id, name, phone, date, time = booking

        readable_date = datetime.strptime(
            date,
            "%Y-%m-%d"
        ).strftime("%d.%m.%Y")

        text += (
            f"№ {booking_id}\n"
            f"📅 {readable_date}\n"
            f"⏰ {time}\n"
            f"📞 {phone}\n\n"
        )

    await callback.message.edit_text(
        text,
        reply_markup=main_menu()
    )

    await callback.answer()


# =========================================================
# АДРЕС
# =========================================================

@dp.callback_query(F.data == "address")
async def address(callback: CallbackQuery):

    await callback.message.edit_text(
        "📍 НАШ АДРЕС\n\n"
        "г. Челябинск\n"
        "ул. Примерная, 10\n\n"
        "🕘 Работаем ежедневно\n"
        "09:00–19:00",
        reply_markup=main_menu()
    )

    await callback.answer()


# =========================================================
# АДМИНКА
# =========================================================

@dp.message(Command("admin"))
async def admin(message: Message):

    if message.from_user.id != ADMIN_ID:

        await message.answer(
            "⛔ Доступ запрещён."
        )

        return

    await message.answer(
        "👨‍🔧 АДМИН-ПАНЕЛЬ\n\n"
        "Выберите действие:",
        reply_markup=admin_menu()
    )


# =========================================================
# АДМИН — СЕГОДНЯ
# =========================================================

@dp.callback_query(F.data == "admin_today")
async def admin_today(callback: CallbackQuery):

    if callback.from_user.id != ADMIN_ID:
        await callback.answer("Доступ запрещён", show_alert=True)
        return

    date = datetime.now().strftime("%Y-%m-%d")

    bookings = get_bookings_for_date(date)

    if not bookings:

        text = "📅 Сегодня записей нет."

    else:

        text = "📅 ЗАПИСИ НА СЕГОДНЯ\n\n"

        for booking in bookings:

            booking_id, user_id, name, phone, date, time = booking

            text += (
                f"№ {booking_id}\n"
                f"⏰ {time}\n"
                f"👤 {name}\n"
                f"📞 {phone}\n\n"
            )

    await callback.message.edit_text(
        text,
        reply_markup=admin_menu()
    )

    await callback.answer()


# =========================================================
# АДМИН — ЗАВТРА
# =========================================================

@dp.callback_query(F.data == "admin_tomorrow")
async def admin_tomorrow(callback: CallbackQuery):

    if callback.from_user.id != ADMIN_ID:
        await callback.answer("Доступ запрещён", show_alert=True)
        return

    date = (
        datetime.now() + timedelta(days=1)
    ).strftime("%Y-%m-%d")

    bookings = get_bookings_for_date(date)

    if not bookings:

        text = "📆 Завтра записей нет."

    else:

        text = "📆 ЗАПИСИ НА ЗАВТРА\n\n"

        for booking in bookings:

            booking_id, user_id, name, phone, date, time = booking

            text += (
                f"№ {booking_id}\n"
                f"⏰ {time}\n"
                f"👤 {name}\n"
                f"📞 {phone}\n\n"
            )

    await callback.message.edit_text(
        text,
        reply_markup=admin_menu()
    )

    await callback.answer()


# =========================================================
# АДМИН — УДАЛЕНИЕ
# =========================================================

@dp.callback_query(F.data == "admin_delete")
async def admin_delete(callback: CallbackQuery):

    if callback.from_user.id != ADMIN_ID:
        await callback.answer("Доступ запрещён", show_alert=True)
        return

    date = datetime.now().strftime("%Y-%m-%d")

    bookings = get_bookings_for_date(date)

    if not bookings:

        await callback.message.edit_text(
            "Сегодня удалять нечего.",
            reply_markup=admin_menu()
        )

        await callback.answer()
        return

    kb = InlineKeyboardBuilder()

    for booking in bookings:

        booking_id, user_id, name, phone, date, time = booking

        kb.button(
            text=f"❌ {time} — {name}",
            callback_data=f"delete:{booking_id}"
        )

    kb.adjust(1)

    await callback.message.edit_text(
        "❌ Выберите запись для удаления:",
        reply_markup=kb.as_markup()
    )

    await callback.answer()


@dp.callback_query(F.data.startswith("delete:"))
async def delete_booking_callback(callback: CallbackQuery):

    if callback.from_user.id != ADMIN_ID:
        await callback.answer("Доступ запрещён", show_alert=True)
        return

    booking_id = int(
        callback.data.split(":")[1]
    )

    deleted = delete_booking(booking_id)

    if deleted:

        await callback.message.edit_text(
            f"✅ Запись №{booking_id} удалена.",
            reply_markup=admin_menu()
        )

    else:

        await callback.message.edit_text(
            "❌ Запись уже отсутствует.",
            reply_markup=admin_menu()
        )

    await callback.answer()


# =========================================================
# ЗАПУСК
# =========================================================

async def main():

    init_db()

    print("Бот запущен.")
    print("База данных:", DB_NAME)

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
```
