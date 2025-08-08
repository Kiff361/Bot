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

@bot.event
async def on_ready():
    print(f'Вы вошли как{bot.user.name}')
    check_unmute.start()

@bot.event
async def on_message(message):
    guild = message.guild
    if message.author == bot.user: #Если это сообщение бота, его игнорируем
        return

    user_id = message.author.id

    if user_id in banned_users: #Если пользователь уже заброкирован, его игнорируем
        return

    if guild is None: #Если пользователь пишет в личные сообщения или просто не удалось найти гильдию, его игнорируем
        return

    msg_txt_lower = message.content.lower()
    if any(keyword in msg_txt_lower for keyword in advertising_keywords ):
        member = message.author
        banned_users.add(user_id)

        try:
            await guild.ban(member, reason='Реклама')
            await message.channel.send(f'{member.mention} был заблокирован за использание рекламы')
            print(f"Пользователь {member} заблокирован за рекламу.")
        except Exception as e:
            print(f'Ошибка при бане пользователя{e}')

    now = datetime.now(timezone.utc)
    user_last_channel[user_id] = message.channel

    #проверка времени последнего сообщения
    last_time = last_message_time.get(user_id)
    if last_time:
        delta = now - last_time
        if delta<timedelta(seconds=3):
            spam_counter[user_id] = spam_counter.get(user_id, 0) +1
        else:
            spam_counter[user_id] = max(spam_counter.get(user_id, 0) -1, 0) # уменьшаем счетчик спама со времени
    else:
        spam_counter[user_id] = spam_counter.get(user_id, 0) +1

    last_message_time[user_id] = now

    user_spam_times.setdefault(user_id,[])
    user_spam_times[user_id].append(now)
    user_spam_times[user_id] = [t for t in user_spam_times[user_id] if now - t <= timedelta(seconds=10)]

    spam_count_in_window = len(user_spam_times[user_id])
    if spam_count_in_window >=5:
        user_spam_counts[user_id] = user_spam_counts.get(user_id, 0) +1
        # если пользователь заспамил первый раз мутим его на минуту
        if user_spam_counts[user_id] == 1:
            if not user_muting_in_progress.get(user_id, False):
                try:
                    user_muting_in_progress[user_id] =True
                    guilds = bot.guilds
                    for guild in guilds:
                        member = guild.get_member(user_id)
                        if member:
                            mute_role = discord.utils.get(guild.roles, name=MUTE_ROLE_NAME)
                            if mute_role:
                                await message.channel.send(f'{message.author.mention} был/а замьючен на 1 минуту за спам')
                                await member.add_roles(mute_role, reason='Spam')
                                user_mute_time[user_id] = now + timedelta(seconds=30)
                                print(f'{member}был замьючен на минуту за спам')
                            else:
                                print(f'Роль{MUTE_ROLE_NAME} не была найдена в гильдии{guild.name}')
                    spam_counter[user_id] = 0
                except Exception as e:
                    print(f'Ошибка при при мьюте пользователя {e}')


        elif user_spam_counts[user_id] == 2:
            if not user_muting_in_progress.get(user_id, False):
                try:
                    user_muting_in_progress[user_id] = True
                    guilds = bot.guilds
                    for guild in guilds:
                        member = guild.get_member(user_id)
                        if member:
                            mute_role = discord.utils.get(guild.roles, name=MUTE_ROLE_NAME)
                            if mute_role:
                                await message.channel.send(
                                    f'{message.author.mention} был/а замьючен на 1 минуту за спам')
                                await member.add_roles(mute_role, reason='Spam')
                                user_mute_time[user_id] = now + timedelta(seconds=30)
                                print(f'{member}был замьючен на минуту за спам')
                            else:
                                print(f'Роль{MUTE_ROLE_NAME} не была найдена в гильдии{guild.name}')
                    spam_counter[user_id] = 0

                except Exception as e:
                    print(f'Ошибка при при мьюте пользователя {e}')

        elif user_spam_counts[user_id] >= 3:
            if not user_muting_in_progress.get(user_id, False):
                try:
                    user_muting_in_progress[user_id] = True
                    guilds = bot.guilds
                    for guild in guilds:
                        member = guild.get_member(user_id)
                        if member:
                            await message.channel.send(f'{message.author.mention} был/а забанен за многократный спам')
                            await guild.ban(member, reason='Многократный  спам')
                            print(f'{member}был/а забанен за многократный спам')
                            banned_users.add(user_id)
                except Exception as e:
                    print(f'Ошибка при при бане пользователя {e}')
        user_spam_times[user_id].clear()


    await bot.process_commands(message)
    # await message.channel.send(f'{message.author.mention} был/а забанен на 10 минут за спам')
    # await message.author.ban(reason='Спам',delete_message_days=0)
    # user_mute_time[user_id] = now + timedelta(minutes=1)
@bot.command()
async def привет(ctx):
    await ctx.send('Привет!')

@tasks.loop(seconds=10) #каждые 10 секунд проверяем нужно ли размьютить пользователя
async def check_unmute():
    print('Общая проверка размута запущена')
    now = datetime.now(timezone.utc)
    to_unmute = []

    for user_id, unmute_time in list(user_mute_time.items()):
        if now >= unmute_time:
            to_unmute.append(user_id)
    for user_id in to_unmute:
        guilds = bot.guilds
        for guild in bot.guilds:
            member = guild.get_member(user_id)
            if member:
                mute_role = discord.utils.get(guild.roles, name=MUTE_ROLE_NAME)
                if mute_role and mute_role in member.roles:
                    try:
                        ###
                        last_channel = user_last_channel.get(user_id)
                        if last_channel:
                            await  last_channel.send(f'{member.mention} был размучен')
                        await member.remove_roles(mute_role, reason= 'Автомотичиский размут')
                        print(f'{member} был размучен')
                    ###
                    except Exception as e:
                        print(f'Ошибка при размуте {user_id}: {e}')
        del user_mute_time[user_id]
        if user_id  in user_muting_in_progress:
            del user_muting_in_progress[user_id]

bot.run(TOKEN)