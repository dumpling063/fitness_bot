import logging
import asyncio
import sys
from datetime import datetime, timedelta
import calendar
import sqlite3
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
import os

# Читаем токен из переменных окружения
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", 0))

from database import init_db, save_user, get_user, get_all_users, get_total_users, get_active_users_today, get_active_users_week
from database import save_workout, get_today_workout, mark_workout_done, get_user_workouts, get_user_workouts_by_month

logging.basicConfig(level=logging.INFO)

# ===== ПРИВЕТСТВИЕ ОТ ТРЕНЕРА =====
def get_welcome_text():
    return "Привет! Это твой тренер Энтони Тренболони! Ну что приступим к тренировкам?"

# ===== ГЛОБАЛЬНОЕ ХРАНИЛИЩЕ ДЛЯ РЕГИСТРАЦИИ =====
user_reg_data = {}

def get_reg_data(user_id):
    return user_reg_data.get(user_id, {})

def set_reg_data(user_id, data):
    user_reg_data[user_id] = data

def clear_reg_data(user_id):
    if user_id in user_reg_data:
        del user_reg_data[user_id]

# ========== КЛАВИАТУРЫ ==========

def get_client_keyboard():
    keyboard = [
        ["🏋️ Тренировка сегодня", "📅 Календарь"],
        ["📊 Мой прогресс", "🔄 Обновить анкету"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_admin_keyboard():
    keyboard = [
        ["👥 Клиенты", "📊 Статистика"],
        ["📅 Календарь"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# ========== ТРЕНИРОВКИ ==========

WORKOUTS = [
    {"name": "ГРУДЬ + БИЦЕПС", "muscles": "Грудные, Бицепс", "ex": ["Жим штанги лёжа 4x10", "Разводка гантелей 4x12", "Сведение в кроссовере 3x15", "Подъём штанги на бицепс 4x10", "Молотки 3x12", "Бег 20 мин"]},
    {"name": "СПИНА + ПЛЕЧИ", "muscles": "Спина, Плечи", "ex": ["Тяга штанги 4x10", "Тяга верхнего блока 4x12", "Гиперэкстензия 3x15", "Жим гантелей сидя 4x10", "Разводка в стороны 3x12", "Велотренажёр 25 мин"]},
    {"name": "НОГИ + ПРЕСС", "muscles": "Ноги, Пресс", "ex": ["Приседания 4x12", "Жим ногами 4x15", "Выпады 3x12", "Подъём ног 3x15", "Скручивания 3x20", "Бег 15 мин"]},
    {"name": "ГРУДЬ + ТРИЦЕПС", "muscles": "Грудные, Трицепс", "ex": ["Жим гантелей на наклонной 4x10", "Отжимания на брусьях 3x12", "Кроссовер 3x15", "Французский жим 4x10", "Тяга блока вниз 3x12", "Скакалка 15 мин"]},
    {"name": "СПИНА + БИЦЕПС", "muscles": "Спина, Бицепс", "ex": ["Становая тяга 4x8", "Тяга гантели одной рукой 4x12", "Пуловер 3x12", "Подъём штанги на бицепс 4x10", "Сгибания с гантелями 3x12", "Бег 25 мин"]},
    {"name": "ПЛЕЧИ + ТРАПЕЦИИ", "muscles": "Плечи, Трапеции", "ex": ["Армейский жим 4x10", "Разводка в стороны 4x12", "Подъём перед собой 3x12", "Шраги 4x15", "Тяга к подбородку 3x12", "Эллипсоид 20 мин"]},
    {"name": "НОГИ + ЯГОДИЦЫ", "muscles": "Ноги, Ягодицы", "ex": ["Приседания с гантелями 4x15", "Румынская тяга 4x12", "Выпады назад 3x12", "Ягодичный мостик 4x15", "Махи ногой 3x15", "Ходьба 30 мин"]},
    {"name": "ГРУДЬ + ПЛЕЧИ", "muscles": "Грудные, Плечи", "ex": ["Жим штанги лёжа 4x8", "Разводка 4x10", "Жим гантелей сидя 4x10", "Разводка в стороны 3x12", "Подъём перед собой 3x12", "Бег 20 мин"]},
    {"name": "СПИНА + ПРЕСС", "muscles": "Спина, Пресс", "ex": ["Тяга штанги 4x10", "Тяга верхнего блока 4x12", "Горизонтальная тяга 3x12", "Скручивания 4x20", "Подъём ног 3x15", "Велотренажёр 25 мин"]},
    {"name": "НОГИ + РУКИ", "muscles": "Ноги, Руки", "ex": ["Приседания 4x10", "Жим ногами 4x12", "Сгибание ног 3x15", "Подъём на бицепс 4x10", "Французский жим 4x10", "Бег 20 мин"]},
    {"name": "ГРУДЬ + СПИНА", "muscles": "Грудные, Спина", "ex": ["Жим штанги лёжа 4x8", "Тяга штанги 4x8", "Разводка 4x10", "Пуловер 3x12", "Гиперэкстензия 3x15", "Скакалка 20 мин"]},
    {"name": "ПЛЕЧИ + РУКИ", "muscles": "Плечи, Руки", "ex": ["Армейский жим 4x10", "Разводка 4x12", "Подъём штанги на бицепс 4x10", "Молотки 3x12", "Французский жим 4x10", "Бег 25 мин"]},
    {"name": "НОГИ + ПЛЕЧИ", "muscles": "Ноги, Плечи", "ex": ["Приседания 4x15", "Выпады 3x12", "Жим ногами 4x12", "Жим гантелей сидя 4x10", "Разводка в стороны 3x12", "Велотренажёр 30 мин"]},
    {"name": "ГРУДЬ + БИЦЕПС + ПРЕСС", "muscles": "Грудные, Бицепс, Пресс", "ex": ["Жим гантелей 4x10", "Сведение в кроссовере 3x15", "Подъём штанги на бицепс 4x10", "Скручивания 4x20", "Подъём ног 3x15", "Бег 15 мин"]},
    {"name": "СПИНА + ТРИЦЕПС", "muscles": "Спина, Трицепс", "ex": ["Тяга штанги 4x10", "Тяга верхнего блока 4x12", "Французский жим 4x10", "Тяга блока вниз 3x12", "Разгибание с гантелей 3x12", "Эллипсоид 25 мин"]},
    {"name": "НОГИ + БИЦЕПС", "muscles": "Ноги, Бицепс", "ex": ["Приседания 4x12", "Жим ногами 4x15", "Сгибание ног 3x15", "Подъём штанги на бицепс 4x10", "Молотки 3x12", "Бег 20 мин"]},
    {"name": "ГРУДЬ + ТРИЦЕПС + ПЛЕЧИ", "muscles": "Грудные, Трицепс, Плечи", "ex": ["Жим штанги лёжа 4x8", "Отжимания на брусьях 3x12", "Французский жим 4x10", "Жим гантелей сидя 4x10", "Разводка в стороны 3x12", "Скакалка 20 мин"]},
    {"name": "СПИНА + ПЛЕЧИ + ТРАПЕЦИИ", "muscles": "Спина, Плечи, Трапеции", "ex": ["Становая тяга 4x8", "Тяга штанги 4x10", "Армейский жим 4x10", "Шраги 4x15", "Тяга к подбородку 3x12", "Велотренажёр 30 мин"]},
    {"name": "ВСЁ ТЕЛО (ФУЛБАДИ)", "muscles": "Все группы мышц", "ex": ["Приседания 4x12", "Жим штанги 4x10", "Тяга штанги 4x10", "Армейский жим 4x10", "Становая тяга 4x8", "Бег 15 мин"]},
    {"name": "НОГИ + СПИНА", "muscles": "Ноги, Спина", "ex": ["Приседания 4x12", "Румынская тяга 4x10", "Выпады 3x12", "Тяга штанги 4x10", "Скручивания 4x20", "Бег 20 мин"]},
    {"name": "ГРУДЬ + РУКИ", "muscles": "Грудные, Руки", "ex": ["Жим гантелей 4x10", "Разводка 4x12", "Подъём штанги на бицепс 4x10", "Французский жим 4x10", "Молотки 3x12", "Скакалка 15 мин"]},
    {"name": "СПИНА + РУКИ", "muscles": "Спина, Руки", "ex": ["Тяга штанги 4x10", "Тяга верхнего блока 4x12", "Подъём штанги на бицепс 4x10", "Тяга блока вниз 3x12", "Разгибание с гантелей 3x12", "Бег 25 мин"]},
    {"name": "ПЛЕЧИ + ПРЕСС", "muscles": "Плечи, Пресс", "ex": ["Жим гантелей сидя 4x10", "Разводка в стороны 4x12", "Подъём перед собой 3x12", "Скручивания 4x20", "Подъём ног 3x15", "Велотренажёр 20 мин"]},
    {"name": "НОГИ + ГРУДЬ", "muscles": "Ноги, Грудные", "ex": ["Приседания 4x12", "Выпады 3x12", "Жим ногами 4x15", "Жим гантелей 4x10", "Разводка 4x12", "Бег 20 мин"]},
    {"name": "СПИНА + ГРУДЬ + ПЛЕЧИ", "muscles": "Спина, Грудные, Плечи", "ex": ["Жим штанги 4x8", "Тяга штанги 4x8", "Разводка 4x10", "Армейский жим 4x10", "Шраги 4x15", "Скакалка 25 мин"]},
    {"name": "НОГИ + СПИНА + БИЦЕПС", "muscles": "Ноги, Спина, Бицепс", "ex": ["Приседания 4x10", "Румынская тяга 4x10", "Тяга штанги 4x10", "Подъём штанги на бицепс 4x10", "Молотки 3x12", "Велотренажёр 30 мин"]},
    {"name": "ГРУДЬ + ПЛЕЧИ + ТРИЦЕПС", "muscles": "Грудные, Плечи, Трицепс", "ex": ["Жим штанги 4x8", "Жим гантелей сидя 4x10", "Разводка в стороны 3x12", "Французский жим 4x10", "Тяга блока вниз 3x12", "Бег 20 мин"]},
    {"name": "СПИНА + ПРЕСС + НОГИ", "muscles": "Спина, Пресс, Ноги", "ex": ["Тяга штанги 4x10", "Гиперэкстензия 3x15", "Приседания 4x12", "Выпады 3x12", "Скручивания 4x20", "Эллипсоид 25 мин"]},
    {"name": "ВСЁ ТЕЛО 2", "muscles": "Все группы мышц", "ex": ["Становая тяга 4x8", "Жим гантелей 4x10", "Тяга гантели одной рукой 4x12", "Армейский жим 4x10", "Приседания 4x12", "Бег 15 мин"]},
    {"name": "НОГИ + ЯГОДИЦЫ + ПРЕСС", "muscles": "Ноги, Ягодицы, Пресс", "ex": ["Приседания 4x12", "Румынская тяга 4x10", "Ягодичный мостик 4x15", "Выпады 3x12", "Скручивания 4x20", "Ходьба 30 мин"]},
    {"name": "ГРУДЬ + СПИНА + РУКИ", "muscles": "Грудные, Спина, Руки", "ex": ["Жим штанги 4x8", "Тяга штанги 4x8", "Разводка 4x10", "Подъём штанги на бицепс 4x10", "Французский жим 4x10", "Скакалка 20 мин"]}
]

def get_workout(day):
    return WORKOUTS[(day - 1) % len(WORKOUTS)]

def delete_user(user_id):
    with sqlite3.connect("fitness_bot.db") as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
        cursor.execute("DELETE FROM workouts WHERE user_id = ?", (user_id,))
        conn.commit()
    return True

# ========== ПОКАЗ ТРЕНИРОВКИ ==========

async def show_workout(message, user_id, date_str=None):
    user = get_user(user_id)
    if not user:
        await message.reply_text("Сначала зарегистрируйтесь: /start")
        return
    if date_str:
        day = int(date_str.split("-")[2])
        w = get_workout(day)
        text = f"🏋️ *{w['name']}*\n\n🎯 *{w['muscles']}*\n\n📋 Упражнения:\n" + "\n".join(f"• {ex}" for ex in w['ex'])
        workout_id = save_workout(user_id, text, date_str)
    else:
        today = datetime.now().day
        w = get_workout(today)
        text = f"🏋️ *{w['name']}*\n\n🎯 *{w['muscles']}*\n\n📋 Упражнения:\n" + "\n".join(f"• {ex}" for ex in w['ex'])
        existing = get_today_workout(user_id)
        if existing:
            workout_id, _, completed = existing
            if completed:
                await message.reply_text("✅ Сегодня уже выполнено!")
                return
        else:
            workout_id = save_workout(user_id, text)
    keyboard = [[InlineKeyboardButton("✅ Выполнено!", callback_data=f"complete_{workout_id}")]]
    await message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

# ========== КАЛЕНДАРЬ ==========

async def show_calendar(message, user_id, year, month):
    workouts = get_user_workouts_by_month(user_id, year, month)
    workouts_dict = {row[0]: bool(row[1]) for row in workouts}
    cal = calendar.monthcalendar(year, month)
    month_name = calendar.month_name[month]
    text = f"📅 *{month_name} {year}*\n\nНажмите на день:\n\n"
    keyboard = []
    keyboard.append([InlineKeyboardButton(d, callback_data="ignore") for d in ["Пн","Вт","Ср","Чт","Пт","Сб","Вс"]])
    today_str = datetime.now().date().isoformat()
    for week in cal:
        row = []
        for day in week:
            if day == 0:
                row.append(InlineKeyboardButton(" ", callback_data="ignore"))
            else:
                date_str = f"{year}-{month:02d}-{day:02d}"
                if date_str in workouts_dict and workouts_dict[date_str]:
                    icon = f"✅{day}"
                elif date_str == today_str:
                    icon = f"🔵{day}"
                else:
                    icon = str(day)
                row.append(InlineKeyboardButton(icon, callback_data=f"day_{date_str}"))
        keyboard.append(row)
    prev = (year, month-1) if month > 1 else (year-1, 12)
    next = (year, month+1) if month < 12 else (year+1, 1)
    keyboard.append([
        InlineKeyboardButton("◀️", callback_data=f"cal_{prev[0]}_{prev[1]}"),
        InlineKeyboardButton(f"{month}/{year}", callback_data="ignore"),
        InlineKeyboardButton("▶️", callback_data=f"cal_{next[0]}_{next[1]}")
    ])
    keyboard.append([InlineKeyboardButton("🔙 Меню", callback_data="main_menu")])
    await message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

# ========== ПОКАЗ КЛИЕНТОВ ==========

async def show_clients(message):
    users = get_all_users()
    if not users:
        await message.reply_text("Нет клиентов")
        return
    keyboard = []
    for user_id, name in users:
        keyboard.append([InlineKeyboardButton(f"❌ {name}", callback_data=f"delete_{user_id}")])
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="back_to_admin")])
    await message.reply_text(
        "👥 *Список клиентов*\n\nНажмите ❌ чтобы удалить:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

# ========== РЕГИСТРАЦИЯ И ПРИВЕТСТВИЕ ==========

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user(user_id)
    if user:
        kb = get_admin_keyboard() if user_id == ADMIN_ID else get_client_keyboard()
        await update.message.reply_text(get_welcome_text(), reply_markup=kb)
        return
    clear_reg_data(user_id)
    set_reg_data(user_id, {'step': 'name'})
    await update.message.reply_text(get_welcome_text())
    await update.message.reply_text("Как вас зовут?")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text
    user = get_user(user_id)
    if user:
        if text == "🏋️ Тренировка сегодня":
            await show_workout(update.message, user_id)
        elif text == "📅 Календарь":
            now = datetime.now()
            await show_calendar(update.message, user_id, now.year, now.month)
        elif text == "📊 Мой прогресс":
            workouts = get_user_workouts(user_id)
            if not workouts:
                await update.message.reply_text("Нет тренировок")
            else:
                msg = "📊 *Прогресс (7 дней)*\n\n"
                for date, ex, comp in workouts:
                    msg += f"{date}: {'✅' if comp else '❌'}\n"
                await update.message.reply_text(msg, parse_mode="Markdown")
        elif text == "🔄 Обновить анкету":
            clear_reg_data(user_id)
            set_reg_data(user_id, {'step': 'name'})
            await update.message.reply_text("Давайте обновим анкету. Как вас зовут?")
        elif user_id == ADMIN_ID and text == "👥 Клиенты":
            await show_clients(update.message)
        elif user_id == ADMIN_ID and text == "📊 Статистика":
            msg = f"📊 *Статистика*\n\n👥 Всего: {get_total_users()}\n🏋️ Сегодня: {get_active_users_today()}\n📆 За неделю: {get_active_users_week()}"
            await update.message.reply_text(msg, parse_mode="Markdown")
        return
    data = get_reg_data(user_id)
    step = data.get('step', 'name')
    if step == 'name':
        data['name'] = text
        data['step'] = 'age'
        set_reg_data(user_id, data)
        await update.message.reply_text("Сколько вам лет? (введите число)")
    elif step == 'age':
        try:
            data['age'] = int(text)
            data['step'] = 'height'
            set_reg_data(user_id, data)
            await update.message.reply_text("Ваш рост (в см)?")
        except:
            await update.message.reply_text("Введите число.")
    elif step == 'height':
        try:
            data['height'] = float(text.replace(',', '.'))
            data['step'] = 'weight'
            set_reg_data(user_id, data)
            await update.message.reply_text("Ваш вес (в кг)?")
        except:
            await update.message.reply_text("Введите число, например 175.5")
    elif step == 'weight':
        try:
            data['weight'] = float(text.replace(',', '.'))
            data['step'] = 'goal'
            set_reg_data(user_id, data)
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("1️⃣ Похудение", callback_data="goal_Похудение")],
                [InlineKeyboardButton("2️⃣ Набор массы", callback_data="goal_Набор массы")],
                [InlineKeyboardButton("3️⃣ Поддержание формы", callback_data="goal_Поддержание формы")]
            ])
            await update.message.reply_text("Выберите цель:", reply_markup=keyboard)
        except:
            await update.message.reply_text("Введите число.")

# ========== ОБРАБОТЧИК КНОПОК ==========

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    data = query.data
    user = get_user(user_id)
    
    if data == "ignore":
        return
    if data == "main_menu":
        kb = get_admin_keyboard() if user_id == ADMIN_ID else get_client_keyboard()
        await query.edit_message_text("Главное меню:", reply_markup=kb)
        return
    if data == "back_to_admin":
        await query.edit_message_text("Главное меню:", reply_markup=get_admin_keyboard())
        return
    if data.startswith("delete_"):
        if user_id != ADMIN_ID:
            await query.edit_message_text("У вас нет прав!")
            return
        client_id = int(data.split("_")[1])
        client = get_user(client_id)
        if client:
            name = client[1]
            delete_user(client_id)
            await query.edit_message_text(f"✅ Клиент {name} удалён!")
            await show_clients(query.message)
        else:
            await query.edit_message_text("❌ Клиент не найден")
        return
    if data.startswith("day_"):
        date_str = data.replace("day_", "")
        await show_workout(query.message, user_id, date_str)
        await query.delete_message()
        return
    if data.startswith("cal_"):
        parts = data.split("_")
        if len(parts) == 3:
            year = int(parts[1])
            month = int(parts[2])
            await show_calendar(query.message, user_id, year, month)
            await query.delete_message()
        return
    if data.startswith("complete_"):
        workout_id = int(data.split("_")[1])
        mark_workout_done(workout_id)
        await query.edit_message_text("✅ Выполнено! 🎉")
        return
    
    # === РЕГИСТРАЦИЯ: ВЫБОР ЦЕЛИ ===
    if data.startswith("goal_"):
        goal = data.replace("goal_", "")
        reg_data = get_reg_data(user_id)
        if not reg_data:
            reg_data = {}
        reg_data['goal'] = goal
        reg_data['step'] = 'level'
        set_reg_data(user_id, reg_data)
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("1️⃣ Начинающий", callback_data="level_Начинающий")],
            [InlineKeyboardButton("2️⃣ Средний", callback_data="level_Средний")],
            [InlineKeyboardButton("3️⃣ Продвинутый", callback_data="level_Продвинутый")]
        ])
        await query.edit_message_text("Выберите уровень подготовки:", reply_markup=keyboard)
        return
    
    # === РЕГИСТРАЦИЯ: ВЫБОР УРОВНЯ ===
    if data.startswith("level_"):
        level = data.replace("level_", "")
        reg_data = get_reg_data(user_id)
        if not reg_data:
            await query.edit_message_text("❌ Ошибка: начните заново с /start")
            return
        reg_data['level'] = level
        set_reg_data(user_id, reg_data)
        required = ['name', 'age', 'height', 'weight', 'goal']
        if any(k not in reg_data for k in required):
            await query.edit_message_text("❌ Не все данные введены. Начните заново с /start")
            clear_reg_data(user_id)
            return
        try:
            save_user(
                user_id,
                reg_data['name'],
                int(reg_data['age']),
                float(reg_data['height']),
                float(reg_data['weight']),
                reg_data['goal'],
                level
            )
        except Exception as e:
            await query.edit_message_text(f"❌ Ошибка: {e}\nНапишите /start заново.")
            clear_reg_data(user_id)
            return
        clear_reg_data(user_id)
        kb = get_admin_keyboard() if user_id == ADMIN_ID else get_client_keyboard()
        await query.edit_message_text("✅ Регистрация завершена!")
        await query.message.reply_text(get_welcome_text(), reply_markup=kb)
        return

# ========== ЗАПУСК ==========

def main():
    if not BOT_TOKEN:
        print("❌ Ошибка: BOT_TOKEN не найден. Убедитесь, что переменная окружения BOT_TOKEN установлена.")
        return
    
    init_db()
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    print("🚀 Бот запущен!")
    app.run_polling(allowed_updates=[])

if __name__ == "__main__":
    main()