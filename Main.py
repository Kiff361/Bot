from http.cookiejar import user_domain_match

import discord
from discord.ext import commands, tasks
from datetime import datetime, timezone, timedelta
import os


user_mute_time = {} #время последнего бана пользевателя
spam_counter = {} #счетчик нарушений
last_message_time = {} #время посмледнего сообщения
user_last_channel = {}
banned_users = set() #список заблокироных за спам или рекламу пользователей
user_spam_counts = {} # счетчик спамов (сколько раз пользователь нарушал)
user_spam_times = {} # список таймстампов сообщений для каждого пользователя
user_muting_in_progress = {}

advertising_keywords = ['подпишись','подписка','лайк','подпишитесь','последний шанс']

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

TOKEN = os.getenv('DISCORD_TOKEN')

MUTE_ROLE_NAME = 'muted'

bot = commands.Bot(command_prefix = '/', intents=intents)
#-----------------------------
@bot.event
async def on_message(message):
   await bot.process_commands(message)  # Обработка команд до всего


   guild = message.guild
   if message.author == bot.user or not guild:
       return


   user_id = message.author.id
   now = datetime.now(timezone.utc)


   if user_id in banned_users:
       return


   user_last_channel[user_id] = message.channel


   # Реклама — бан
   msg_txt_lower = message.content.lower()
   if any(keyword in msg_txt_lower for keyword in advertising_keywords):
       try:
           await guild.ban(message.author, reason='Реклама')
           await message.channel.send(f'{message.author.mention} был заблокирован за использование рекламы')
           print(f"Пользователь {message.author} заблокирован за рекламу.")
           banned_users.add(user_id)
           return
       except Exception as e:
           print(f'Ошибка при бане пользователя: {e}')
           return


   # Спам
   last_time = last_message_time.get(user_id)
   if last_time and (now - last_time) < timedelta(seconds=3):
       spam_counter[user_id] = spam_counter.get(user_id, 0) + 1
   else:
       spam_counter[user_id] = max(spam_counter.get(user_id, 0) - 1, 0)


   last_message_time[user_id] = now
   user_spam_times.setdefault(user_id, []).append(now)
   user_spam_times[user_id] = [t for t in user_spam_times[user_id] if now - t <= timedelta(seconds=10)]


   if len(user_spam_times[user_id]) >= 5:
       user_spam_counts[user_id] = user_spam_counts.get(user_id, 0) + 1
       user_spam_times[user_id].clear()


       # Проверка, уже ли мутим
       if user_muting_in_progress.get(user_id):
           return


       user_muting_in_progress[user_id] = True


       member = guild.get_member(user_id)
       if not member:
           return


       mute_role = discord.utils.get(guild.roles, name=MUTE_ROLE_NAME)
       if not mute_role:
           await message.channel.send(f'Роль {MUTE_ROLE_NAME} не найдена.')
           user_muting_in_progress[user_id] = False
           return


       if user_spam_counts[user_id] in [1, 2]:
           # Мут на 1 минуту
           try:
               await member.add_roles(mute_role, reason='Спам')
               user_mute_time[user_id] = now + timedelta(minutes=1)
               await message.channel.send(f'{member.mention} был замьючен на 1 минуту за спам')
               print(f'{member} замьючен на 1 минуту')
           except Exception as e:
               print(f'Ошибка при мьюте пользователя: {e}')
               user_muting_in_progress[user_id] = False


       elif user_spam_counts[user_id] >= 3:
           try:
               await guild.ban(member, reason='Многократный спам')
               banned_users.add(user_id)
               await message.channel.send(f'{member.mention} был забанен за многократный спам')
               print(f'{member} забанен за спам')
               if user_id in user_mute_time:
                   del user_mute_time[user_id]
           except Exception as e:
               print(f'Ошибка при бане: {e}')
               user_muting_in_progress[user_id] = False


@bot.command()
async def привет(ctx):
   await ctx.send('Привет!')


@tasks.loop(seconds=10)
async def check_unmute():
   now = datetime.now(timezone.utc)
   to_unmute = [user_id for user_id, unmute_time in user_mute_time.items() if now >= unmute_time]


   for user_id in to_unmute:
       for guild in bot.guilds:
           member = guild.get_member(user_id)
           if member:
               mute_role = discord.utils.get(guild.roles, name=MUTE_ROLE_NAME)
               if mute_role and mute_role in member.roles:
                   try:
                       await member.remove_roles(mute_role, reason='Автоматический размут')
                       last_channel = user_last_channel.get(user_id)
                       if last_channel:
                           await last_channel.send(f'{member.mention} был размучен')
                       print(f'{member} был размучен')
                   except Exception as e:
                       print(f'Ошибка при размуте пользователя {user_id}: {e}')
       user_mute_time.pop(user_id, None)
       user_muting_in_progress.pop(user_id, None)


bot.run(TOKEN)

# -----------------------------
# Keep Render from stopping bot
# -----------------------------
from flask import Flask
import threading

app = Flask('')

@app.route('/')
def home():
    return "I'm alive!"

def run():
    app.run(host='0.0.0.0', port=8080)

t = threading.Thread(target=run)
t.start()

