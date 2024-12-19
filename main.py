import discord
import json
import os
import requests
from datetime import datetime
from discord.ext import commands, tasks
from discord.ui import Button, View
from aiohttp import web
import asyncio

# データ保存用のファイルパス
fridge_file = 'fridge_items.json'

# データ保存
def save_fridge_items(items):
    with open(fridge_file, 'w', encoding='utf-8') as f:
        json.dump(items, f, ensure_ascii=False, indent=4)

# データ読み込み
def load_fridge_items():
    if os.path.exists(fridge_file):
        with open(fridge_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

# 初期化時にデータ形式を更新
def migrate_fridge_items(items):
    updated_items = {}
    for item, data in items.items():
        if isinstance(data, int):  # 古い形式なら変換
            updated_items[item] = {'quantity': data, 'added_on': '不明'}
        else:
            if 'added_on' not in data:  # added_on が欠けている場合
                data['added_on'] = '不明'
            updated_items[item] = data
    return updated_items

# 経過日数を計算
def days_elapsed(added_on):
    try:
        added_date = datetime.strptime(added_on, '%Y-%m-%d')
        return (datetime.now() - added_date).days
    except ValueError:
        return None


# ディスコードボットの設定
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='/', intents=intents)

# 冷蔵庫アイテムの初期化
fridge_items = migrate_fridge_items(load_fridge_items())
save_fridge_items(fridge_items)


@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')
    if not hasattr(bot, 'synced'):  # 一度だけ同期
        await bot.tree.sync()
        bot.synced = True
        print("Commands synced successfully.")
    check_expired_items.start()  # 定期タスクを開始


# 定期タスク: 5日以上経過した食材を通知
@tasks.loop(hours=24)
async def check_expired_items():
    channel_id = 1319165421815074816  # 通知を送るチャンネルIDに置き換える
    channel = bot.get_channel(channel_id)
    if not channel:
        return
    expired_items = [
        f'{item}（追加日: {data["added_on"]}, 経過日数: {days_elapsed(data["added_on"])}日）'
        for item, data in fridge_items.items()
        if days_elapsed(data['added_on']) is not None and days_elapsed(data['added_on']) >= 5
    ]
    if expired_items:
        message = "**以下の食材が5日以上経過しています:**\n" + "\n".join(expired_items)
        await channel.send(message)



# /add コマンド
@bot.tree.command(name='add', description='食材を追加します。')
async def add(interaction: discord.Interaction, item: str, quantity: int = 1):
    now = datetime.now()
    date_info = now.strftime('%Y-%m-%d')

    fridge_items[item] = {'quantity': quantity, 'added_on': date_info}
    save_fridge_items(fridge_items)
    await interaction.response.send_message(f'{item} を {quantity} 個追加しました（追加日時: {date_info}）。')

# /remove コマンド
@bot.tree.command(name='remove', description='食材を削除します。')
async def remove(interaction: discord.Interaction, item: str, quantity: int = 1):
    if item in fridge_items:
        fridge_items[item]['quantity'] -= quantity
        if fridge_items[item]['quantity'] <= 0:
            del fridge_items[item]  # 数量が0以下になった場合は削除
        save_fridge_items(fridge_items)
        await interaction.response.send_message(f'{item} を {quantity} 個削除しました。')
    else:
        await interaction.response.send_message(f'{item} は冷蔵庫にありません。')

# /search コマンド
@bot.tree.command(name='search', description='食材をキーワードから検索します。')
async def search(interaction: discord.Interaction, keyword: str):
    # キーワードに一致する食材を検索
    matched_items = {item: data for item, data in fridge_items.items() if keyword.lower() in item.lower()}
    if not matched_items:
        await interaction.response.send_message(f'キーワード "{keyword}" に一致する食材は見つかりませんでした。')
    else:
        result_message = '\n'.join(
            [f'{item}: {data["quantity"]} 個（追加日時: {data["added_on"]}）' for item, data in matched_items.items()]
        )
        await interaction.response.send_message(f'検索結果:\n{result_message}')




# /list コマンド
@bot.tree.command(name='list', description='冷蔵庫の食材リストを表示します。')
async def list_items(interaction: discord.Interaction):
    if not fridge_items:
        await interaction.response.send_message('冷蔵庫は空です。')
    else:
        item_messages = []
        for item, data in fridge_items.items():
            elapsed_days = days_elapsed(data["added_on"])
            color_start = "**" if elapsed_days is not None and elapsed_days >= 5 else ""
            color_end = "**" if color_start else ""
            item_messages.append(
            f'{item}: {data["quantity"]} 個（追加日時: {data["added_on"]}, 経過日数: {elapsed_days if elapsed_days is not None else "不明"}日）'
            )
        
        # 表示するメッセージを組み立て
        message_content = '\n'.join(item_messages)
        
        # ボタンの作成
        view = View()
        edit_button = Button(label="編集", style=discord.ButtonStyle.primary, custom_id="shortcut_edit")
        delete_button = Button(label="削除", style=discord.ButtonStyle.danger, custom_id="shortcut_delete")
        view.add_item(edit_button)
        view.add_item(delete_button)
        
        # メッセージとボタンを送信
        await interaction.response.send_message(message_content, view=view)


# ボタンのインタラクションイベント
@bot.event
async def on_interaction(interaction: discord.Interaction):
    if not interaction.data.get('custom_id'):
        return

    custom_id = interaction.data['custom_id']

    # 編集ボタン
    if custom_id == "shortcut_edit":
        await interaction.response.send_message("編集したいアイテムの名前を入力してください。")

        def check(m):
            return m.author == interaction.user and m.channel == interaction.channel

        try:
            msg = await bot.wait_for('message', timeout=30.0, check=check)
            item = msg.content
            if item not in fridge_items:
                await interaction.followup.send(f"{item} は冷蔵庫にありません。")
                return

            await interaction.followup.send(f"{item} の新しい数量を入力してください。")
            msg = await bot.wait_for('message', timeout=30.0, check=check)
            try:
                new_quantity = int(msg.content)
                fridge_items[item]['quantity'] = new_quantity
                save_fridge_items(fridge_items)
                await interaction.followup.send(f"{item} の数量を {new_quantity} に変更しました。")
            except ValueError:
                await interaction.followup.send("数量は数値で入力してください。")

        except asyncio.TimeoutError:  
            await interaction.followup.send("タイムアウトしました。もう一度やり直してください。")

    # 削除ボタン
    elif custom_id == "shortcut_delete":
        await interaction.response.send_message("削除したいアイテムの名前を入力してください。")

        def check(m):
            return m.author == interaction.user and m.channel == interaction.channel

        try:
            msg = await bot.wait_for('message', timeout=30.0, check=check)
            item = msg.content
            if item not in fridge_items:  # 修正: 削除時にアイテムが存在しない場合の処理
                await interaction.followup.send(f'{item} は冷蔵庫にありません。')
            else:
                del fridge_items[item]
                save_fridge_items(fridge_items)
                await interaction.followup.send(f'{item} を冷蔵庫から削除しました。')
        except asyncio.TimeoutError:  
            await interaction.followup.send("タイムアウトしました。もう一度やり直してください。")



    # --------------------
    # HTTPサーバー設定
    # --------------------
    async def health_check(request):
        return web.Response(text="OK", status=200)

    # HTTP サーバーの非同期実行関数
async def start_http_server():
    app = web.Application()
    app.router.add_get('/health', lambda request: web.Response(text="OK", status=200))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 8080)
    await site.start()

async def main():
    # HTTPサーバー開始
    asyncio.create_task(start_http_server())

    # Discordボット開始
    await bot.start(os.environ['TOKEN'])

if __name__ == "__main__":
    asyncio.run(main())
