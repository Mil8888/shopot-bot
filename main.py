import os
from aiohttp import web
from aiohttp.web import Response, json_response
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# ====== НАСТРОЙКИ ======
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
CHANNEL_ID = os.getenv("CHANNEL_ID")  # опционально
WEBHOOK_PATH = os.getenv("WEBHOOK_PATH", "/webhook")
PUBLIC_URL = os.getenv("PUBLIC_URL") or os.getenv("RENDER_EXTERNAL_URL")

bot = Bot(token=BOT_TOKEN, parse_mode=types.ParseMode.HTML)
dp = Dispatcher(bot)

# ====== СТРАНИЦА С ФОРМОЙ ======
HTML_PAGE = """
<!doctype html><html lang="ru"><head>
<meta charset="utf-8"/><meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Шёпот — анонимный вопрос</title>
<style>
body{font-family:system-ui,-apple-system,Segoe UI,Roboto,Arial;margin:0;background:#0f1115;color:#fff}
.wrap{max-width:720px;margin:0 auto;padding:24px}
.card{background:#151923;border-radius:16px;padding:20px;box-shadow:0 10px 30px rgba(0,0,0,.25)}
h1{margin:0 0 8px;font-size:28px} p{margin:0 0 16px;opacity:.85}
textarea{width:100%;min-height:140px;border-radius:12px;border:1px solid #2a3346;background:#0f1115;color:#fff;padding:12px;font-size:16px;outline:none}
button{margin-top:12px;width:100%;padding:14px;border:none;border-radius:12px;background:#4c7cff;color:#fff;font-weight:600;font-size:16px}
.ok{background:#1f8b4c;padding:12px;border-radius:10px;margin-top:12px;display:none}
.err{background:#8b2a2a;padding:12px;border-radius:10px;margin-top:12px;display:none}
.foot{margin-top:16px;opacity:.6;font-size:13px;text-align:center}
</style></head><body>
<div class="wrap"><div class="card">
<h1>Шёпот — анонимный вопрос</h1>
<p>Напишите всё, что хотите спросить. Это анонимно.</p>
<form id="f">
  <textarea name="text" placeholder="Ваш анонимный вопрос…" maxlength="1500" required></textarea>
  <button type="submit">Отправить анонимно</button>
  <div id="ok" class="ok">Спасибо! Ваш вопрос отправлен.</div>
  <div id="err" class="err">Ошибка отправки. Попробуйте позже.</div>
</form>
<div class="foot">Анти-спам и бережная модерация включены.</div>
</div></div>
<script>
const f=document.getElementById('f');
f.addEventListener('submit',async(e)=>{
  e.preventDefault();
  const fd=new FormData(f);
  const res=await fetch('/ask',{method:'POST',body:fd});
  document.getElementById(res.ok?'ok':'err').style.display='block';
  if(res.ok) f.reset();
});
</script>
</body></html>
"""

# ====== HTTP-роуты ======
async def index_handler(request: web.Request):
    return Response(text=HTML_PAGE, content_type="text/html")

async def ask_handler(request: web.Request):
    text = None
    if request.can_read_body:
        ct = request.headers.get("Content-Type","")
        if "application/json" in ct:
            data = await request.json()
            text = (data or {}).get("text")
        else:
            data = await request.post()
            text = data.get("text")
    text = (text or "").strip()
    if not text:
        return json_response({"ok": False, "error": "no text"}, status=400)
    if len(text) > 1500:
        text = text[:1500] + "…"

    if ADMIN_ID:
        kb = None
        if CHANNEL_ID:
            kb = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="Опубликовать в канал", callback_data="pub"),
            ]])
        await bot.send_message(chat_id=ADMIN_ID, text=f"🕊 <b>Аноним</b> написал:\n\n{text}", reply_markup=kb)
    return json_response({"ok": True})

async def webhook_handler(request: web.Request):
    data = await request.json()
    update = types.Update(**data)
    await dp.process_update(update)
    return web.Response()

# ====== Кнопка публикации ======
@dp.callback_query_handler(lambda c: c.data == "pub")
async def on_pub(c: types.CallbackQuery):
    if not CHANNEL_ID:
        await c.answer("CHANNEL_ID не настроен", show_alert=True)
        return
    original = c.message.html_text.replace("🕊 <b>Аноним<
/b> написал:\n\n", "")
    pub_text = f"❓ <b>Аноним спросил</b>:\n\n{original}\n\n— Ответ ниже —"
    try:
        await bot.send_message(chat_id=int(CHANNEL_ID), text=pub_text)
        await c.answer("Опубликовано")
    except Exception as e:
        await c.answer(f"Ошибка публикации: {e}", show_alert=True)

# ====== Команды ======
@dp.message_handler(commands=["start"])
async def cmd_start(m: types.Message):
    ask_link = (PUBLIC_URL or "").rstrip("/") + "/"
    await m.answer("Привет! Это <b>Шёпот</b>.\n"
                   f"Задавать анонимные вопросы можно здесь: {ask_link}\n\n"
                   "Команды:\n/link — моя ссылка\n/help — помощь")

@dp.message_handler(commands=["link"])
async def cmd_link(m: types.Message):
    ask_link = (PUBLIC_URL or "").rstrip("/") + "/"
    await m.answer(f"Твоя ссылка для вопросов: {ask_link}")

@dp.message_handler(commands=["help"])
async def cmd_help(m: types.Message):
    await m.answer("Как работает:\n"
                   "1) Люди пишут анонимно через веб-страницу.\n"
                   "2) Вопросы приходят администратору в этот бот.\n"
                   "3) Кнопкой можно публиковать в канал (если настроен CHANNEL_ID).")

# ====== Запуск приложения ======
async def on_startup(app):
    if PUBLIC_URL:
        await bot.set_webhook(PUBLIC_URL.rstrip("/") + WEBHOOK_PATH)

async def on_shutdown(app):
    await bot.delete_webhook()

def make_app():
    app = web.Application()
    app.router.add_get("/", index_handler)
    app.router.add_post("/ask", ask_handler)
    app.router.add_post(WEBHOOK_PATH, webhook_handler)
    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)
    return app

if __name__ == "__main__":
    if not BOT_TOKEN:
        raise RuntimeError("Нет BOT_TOKEN в переменных окружения")
    web.run_app(make_app(), host="0.0.0.0", port=int(os.getenv("PORT", "10000")))
