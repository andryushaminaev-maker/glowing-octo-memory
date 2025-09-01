
import logging
import sqlite3
from datetime import datetime
import re
import pandas as pd

from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

logging.basicConfig(level=logging.INFO)
DB_FILE = "reports.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS reports (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT,
        vehicle TEXT,
        start_time TEXT,
        end_time TEXT,
        work_hours REAL,
        overtime REAL,
        total_km REAL,
        km_mkad REAL
    )
    """)
    conn.commit()
    conn.close()

DATE_PATTERN = re.compile(r"(\d{2}\.\d{2}\.\d{4})")
VEHICLE_PATTERN = re.compile(r"(?:ТС|Смена|Наименование ТС)\s+([^\n]+)")
START_PATTERN = re.compile(r"(?:Начало смены|Начало)\s+(\d{2}:\d{2})")
END_PATTERN = re.compile(r"(?:Окончание смены|Конец смены|Окончание)\s+(\d{2}:\d{2})")
OVERTIME_PATTERN = re.compile(r"(?:Переработка|Переработки)\s+(\d+)(?:\s*(\d+))?")
KM_PATTERN = re.compile(r"(?:Общий пробег|Пробег общий)\s+(\d+)")
KM_MKAD_PATTERN = re.compile(r"(?:Пробег за МКАД)\s+(\d+)")

def parse_report(report_text: str):
    try:
        date_match = DATE_PATTERN.search(report_text)
        if not date_match:
            return None, "Не найдена дата"
        report_date = datetime.strptime(date_match.group(1), "%d.%m.%Y").date()
        vehicle_match = VEHICLE_PATTERN.search(report_text)
        if not vehicle_match:
            return None, "Не найдено наименование ТС"
        vehicle = vehicle_match.group(1).strip()
        start_match = START_PATTERN.search(report_text)
        if not start_match:
            return None, "Не найдено время начала"
        start_time = datetime.strptime(start_match.group(1), "%H:%M").time()
        end_match = END_PATTERN.search(report_text)
        if not end_match:
            return None, "Не найдено время окончания"
        end_time = datetime.strptime(end_match.group(1), "%H:%M").time()
        overtime_match = OVERTIME_PATTERN.search(report_text)
        if not overtime_match:
            return None, "Не найдена переработка"
        hours = float(overtime_match.group(1))
        minutes = float(overtime_match.group(2)) if overtime_match.group(2) else 0
        overtime = hours + minutes / 60
        km_match = KM_PATTERN.search(report_text)
        if not km_match:
            return None, "Не найден общий пробег"
        total_km = float(km_match.group(1))
        km_mkad_match = KM_MKAD_PATTERN.search(report_text)
        km_mkad = float(km_mkad_match.group(1)) if km_mkad_match else 0
        start_dt = datetime.combine(report_date, start_time)
        end_dt = datetime.combine(report_date, end_time)
        work_hours = (end_dt - start_dt).total_seconds() / 3600
        return {
            "date": str(report_date),
            "vehicle": vehicle,
            "start_time": str(start_time),
            "end_time": str(end_time),
            "work_hours": work_hours,
            "overtime": overtime,
            "total_km": total_km,
            "km_mkad": km_mkad
        }, None
    except Exception as e:
        return None, str(e)

def save_report(report_data):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO reports (date, vehicle, start_time, end_time, work_hours, overtime, total_km, km_mkad)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        report_data["date"],
        report_data["vehicle"],
        report_data["start_time"],
        report_data["end_time"],
        report_data["work_hours"],
        report_data["overtime"],
        report_data["total_km"],
        report_data["km_mkad"],
    ))
    conn.commit()
    conn.close()

def format_report(report):
    return (
        f"📅 Дата: {report['date']}\n"
        f"🚘 Машина: {report['vehicle']}\n"
        f"⏰ Смена: {report['start_time']} - {report['end_time']}\n"
        f"⏲️ Общее время: {report['work_hours']:.2f} ч\n"
        f"⚡️ Переработка: {report['overtime']:.2f} ч\n"
        f"🛣 Пробег: {report['total_km']} км (за МКАД {report['km_mkad']} км)"
    )

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [["Отправить отчёт 📝", "Статистика 📊"]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text("Привет! Отправь мне отчёт водителя.", reply_markup=reply_markup)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    report, error = parse_report(text)
    if error:
        await update.message.reply_text(f"⚠️ Ошибка: {error}")
    else:
        save_report(report)
        await update.message.reply_text("✅ Отчёт сохранён!\n\n" + format_report(report))

def main():
    init_db()
    app = Application.builder().token("YOUR_TELEGRAM_BOT_TOKEN").build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling()

if __name__ == "__main__":
    main()
