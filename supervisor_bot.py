import os
import sqlite3
from collections import Counter
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

TOKEN = os.environ.get('TOKEN')
if not TOKEN:
    raise ValueError("TOKEN غير موجود! تأكد من إضافته في متغيرات البيئة في Render.")

def setup_db():
    """إنشاء قاعدة البيانات والجدول إذا لم يكونا موجودين"""
    conn = sqlite3.connect('project.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS submissions
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_name TEXT,
                  file_name TEXT,
                  comment TEXT,
                  date TEXT)''')
    conn.commit()
    conn.close()

def save_submission(user_name, file_name, comment):
    """حفظ تسليم جديد في قاعدة البيانات"""
    conn = sqlite3.connect('project.db')
    c = conn.cursor()
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    c.execute("INSERT INTO submissions (user_name, file_name, comment, date) VALUES (?, ?, ?, ?)",
              (user_name, file_name, comment, now))
    conn.commit()
    conn.close()

def get_all_submissions():
    """جلب جميع التسليمات"""
    conn = sqlite3.connect('project.db')
    c = conn.cursor()
    c.execute("SELECT user_name, file_name, comment, date FROM submissions ORDER BY date DESC")
    data = c.fetchall()
    conn.close()
    return data

def get_user_submissions(user_name):
    """جلب تسليمات عضو محدد"""
    conn = sqlite3.connect('project.db')
    c = conn.cursor()
    c.execute("SELECT file_name, comment, date FROM submissions WHERE user_name=? ORDER BY date DESC",
              (user_name,))
    data = c.fetchall()
    conn.close()
    return data

# ========== أوامر البوت ==========

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """أمر /start"""
    await update.message.reply_text(
        "👋 **مرحبًا! أنا بوت المشرف الآلي لمشروع التخرج.**\n\n"
        "🎯 **مهمتي:**\n"
        "• أرسل ملفًا مع تعليق وسأقوم بحفظه تلقائيًا.\n"
        "• استخدم /achievements لعرض سجل الفريق.\n"
        "• استخدم /evaluate لرؤية تسليمات عضو معين.\n"
        "• استخدم /remind لإرسال تنبيه للجميع.\n\n"
        "📌 مثال: /evaluate محمد",
        parse_mode='Markdown'
    )

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """استقبال الملفات وحفظها"""
    user = update.message.from_user
    user_name = user.full_name or user.username or "غير معروف"
    file_name = update.message.document.file_name
    comment = update.message.caption or "بدون تعليق"

    save_submission(user_name, file_name, comment)

    await update.message.reply_text(
        f"✅ **تم استلام التسليم بنجاح!**\n\n"
        f"👤 **العضو:** {user_name}\n"
        f"📄 **الملف:** {file_name}\n"
        f"💬 **التعليق:** {comment}\n"
        f"🕒 **التاريخ:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        parse_mode='Markdown'
    )

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """استقبال النصوص (يمكن استخدامها كملاحظات)"""
    user = update.message.from_user
    user_name = user.full_name or user.username or "غير معروف"
    text = update.message.text

    # نحفظ النص كملاحظة
    save_submission(user_name, "ملاحظة نصية", text)

    await update.message.reply_text(
        f"📝 **تم حفظ الملاحظة!**\n\n"
        f"👤 **العضو:** {user_name}\n"
        f"💬 **النص:** {text[:100]}{'...' if len(text) > 100 else ''}",
        parse_mode='Markdown'
    )

async def achievements(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """أمر /achievements - عرض سجل الفريق"""
    data = get_all_submissions()

    if not data:
        await update.message.reply_text("📭 لا توجد أي تسليمات حتى الآن.")
        return

    # تجميع حسب العضو
    user_counts = Counter(row[0] for row in data)

    msg = "📊 **سجل إنجازات الفريق:**\n\n"
    msg += "👥 **ملخص الأعضاء:**\n"
    for user, count in user_counts.items():
        msg += f"   • {user}: {count} تسليم\n"

    msg += f"\n📌 **آخر 5 تسليمات:**\n"
    for row in data[:5]:
        msg += f"   • [{row[3]}] {row[0]} أرسل {row[1]}: _{row[2]}_\n"

    await update.message.reply_text(msg, parse_mode='Markdown')

async def evaluate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """أمر /evaluate [اسم العضو]"""
    if not context.args:
        await update.message.reply_text(
            "⚠️ **الرجاء كتابة اسم العضو.**\n"
            "مثال: /evaluate محمد",
            parse_mode='Markdown'
        )
        return

    user_name = ' '.join(context.args)
    data = get_user_submissions(user_name)

    if not data:
        await update.message.reply_text(f"📭 لا توجد تسليمات للعضو **{user_name}**.", parse_mode='Markdown')
        return

    msg = f"📋 **تسليمات العضو:** {user_name}\n\n"
    for i, row in enumerate(data, 1):
        msg += f"{i}. 📄 {row[0]} | 🕒 {row[2]}\n"
        msg += f"   💬 {row[1]}\n\n"

    msg += f"📊 **المجموع:** {len(data)} تسليم"

    await update.message.reply_text(msg, parse_mode='Markdown')

async def remind_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """أمر /remind [نص التذكير]"""
    reminder_text = ' '.join(context.args) if context.args else "الرجاء تسليم المهام المطلوبة في أقرب وقت."

    await update.message.reply_text(
        f"🔔 **تذكير لجميع الأعضاء:**\n\n"
        f"📢 {reminder_text}\n\n"
        f"👤 _تم الإرسال بواسطة: {update.message.from_user.full_name}_",
        parse_mode='Markdown'
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """أمر /help"""
    await update.message.reply_text(
        "🆘 **قائمة الأوامر المتاحة:**\n\n"
        "/start - بدء البوت\n"
        "/achievements - عرض سجل تسليمات الفريق\n"
        "/evaluate [الاسم] - عرض تسليمات عضو معين\n"
        "/remind [نص] - إرسال تذكير للجميع\n"
        "/help - عرض هذه القائمة\n\n"
        "📎 يمكنك أيضًا إرسال ملف مع تعليق، أو إرسال ملاحظة نصية.",
        parse_mode='Markdown'
    )

# ========== تشغيل البوت ==========

def main():
    print("🔄 جاري إعداد قاعدة البيانات...")
    setup_db()
    print("✅ قاعدة البيانات جاهزة.")

    print("🤖 جاري تشغيل البوت...")
    app = Application.builder().token(TOKEN).build()

    # ربط الأوامر
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('achievements', achievements))
    app.add_handler(CommandHandler('evaluate', evaluate))
    app.add_handler(CommandHandler('remind', remind_all))
    app.add_handler(CommandHandler('help', help_command))

    # ربط استقبال الملفات
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))

    # ربط استقبال النصوص (ما عدا الأوامر)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    print("✅ البوت يعمل الآن...")
    app.run_polling()

if __name__ == '__main__':
    main()
