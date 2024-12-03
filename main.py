import discord
import json
import os
import asyncio
from discord.ext import commands
from discord.ui import Button, View
from aiohttp import web

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

# ディスコードボットの設定
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='/', intents=intents)

# 初期化
fridge_items = load_fridge_items()

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')
    # 初回のみ実行
    await bot.tree.sync()

# /add コマンド
@bot.tree.command(name='add', description='食材を追加します。')
async def add(interaction: discord.Interaction, item: str, quantity: int = 1):
    if item in fridge_items:
        fridge_items[item] += quantity
    else:
        fridge_items[item] = quantity
    save_fridge_items(fridge_items)
    await interaction.response.send_message(f'{item} を {quantity} 個追加しました。')

# /remove コマンド
@bot.tree.command(name='remove', description='食材を削除します。')
async def remove(interaction: discord.Interaction, item: str, quantity: int = 1):
    if item in fridge_items:
        fridge_items[item] -= quantity
        if fridge_items[item] <= 0:
            del fridge_items[item]
        save_fridge_items(fridge_items)
        await interaction.response.send_message(f'{item} を {quantity} 個削除しました。')
    else:
        await interaction.response.send_message(f'{item} は冷蔵庫にありません。')

# /list コマンド
@bot.tree.command(name='list', description='冷蔵庫の食材リストを表示します。')
async def list_items(interaction: discord.Interaction):
    if not fridge_items:
        await interaction.response.send_message('冷蔵庫は空です。')
    else:
        item_messages = [f'{item}: {quantity} 個' for item, quantity in fridge_items.items()]
        view = View()  # 一つの View にボタンを追加

        # 編集ボタン
        edit_button = Button(label="編集", style=discord.ButtonStyle.primary, custom_id="shortcut_edit")
        view.add_item(edit_button)

        # 削除ボタン
        delete_button = Button(label="削除", style=discord.ButtonStyle.danger, custom_id="shortcut_delete")
        view.add_item(delete_button)

        await interaction.response.send_message('\n'.join(item_messages), view=view)

# 検索コマンド
@bot.tree.command(name='search', description='指定されたキーワードで冷蔵庫の食材を検索します。')
async def search(interaction: discord.Interaction, keyword: str):
    matched_items = {item: quantity for item, quantity in fridge_items.items() if keyword.lower() in item.lower()}
    if not matched_items:
        await interaction.response.send_message(f'キーワード "{keyword}" に一致する食材は見つかりませんでした。')
    else:
        result_message = '\n'.join([f'{item}: {quantity} 個' for item, quantity in matched_items.items()])
        await interaction.response.send_message(f'検索結果:\n{result_message}')

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
                fridge_items[item] = new_quantity
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

    app = web.Application()
    app.router.add_get('/health', health_check)

    async def start_http_server():
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, '0.0.0.0', int(os.environ.get("PORT", 49671)))
        await site.start()


# ボット実行
async def main():
    # 両方のタスクを並列で実行
    await asyncio.gather(
        bot.start(os.environ['TOKEN']),
        start_http_server()
    )

if __name__ == '__main__':
    asyncio.run(main())
