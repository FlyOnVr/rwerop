import os
import sys
import asyncio

import discord
from aiohttp import web
from dotenv import load_dotenv

from database import supabase, run_query

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    sys.exit("DISCORD_TOKEN is missing. Copy .env.example to .env and paste your bot token in it.")

# ID of the role that should be able to see and manage tickets (e.g. your staff/support role).
# Right-click a role in Discord (Developer Mode on) -> Copy Role ID, then paste the number below.
STAFF_ROLE_ID = 1540536304390119564  # <-- replace with your actual staff role ID

# Optional: put tickets under a specific category. Leave as None to create them at the top level.
TICKET_CATEGORY_ID = None  # <-- replace with a category ID, or leave as None

# Link used by the "Download The Menu" button.
MENU_DOWNLOAD_URL = "https://github.com/greenfishyay/CubeClient-Paid/releases/download/ASDASdsQWEZVBAEFSXGFAEFKGqestfyFUYJT/CubeClientPaid-V1.dll"  # <-- replace with your actual link

# Link used by the "SellAuth" button on the dashboard.
SELLAUTH_URL = "https://astre-market.mysellauth.com/product/cube-client"  # <-- replace with your actual SellAuth store link

# Allows the bot's status pings to actually notify the roles (by default, bots can't ping roles).
ALLOWED_ROLE_PING = discord.AllowedMentions(roles=True)

# Small role-mention line sent as message content (outside the embed) so it actually pings.
STATUS_PING_TEXT = "-# <@&1541266539838447707>,<@&1549579814380241037>"


async def open_ticket(interaction: discord.Interaction, topic: str):
    """Shared logic for creating a private ticket channel for a user."""
    guild = interaction.guild
    user = interaction.user

    # Prevent someone from opening multiple tickets at once
    existing = discord.utils.get(guild.text_channels, name=f"ticket-{user.name}".lower())
    if existing:
        await interaction.response.send_message(
            f"You already have an open ticket: {existing.mention}", ephemeral=True
        )
        return

    # Set permissions: hidden from everyone, visible to the ticket opener + staff role
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        user: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
        guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True),
    }

    staff_role = guild.get_role(STAFF_ROLE_ID)
    if staff_role:
        overwrites[staff_role] = discord.PermissionOverwrite(view_channel=True, send_messages=True)

    category = guild.get_channel(TICKET_CATEGORY_ID) if TICKET_CATEGORY_ID else None

    ticket_channel = await guild.create_text_channel(
        name=f"ticket-{user.name}",
        overwrites=overwrites,
        category=category,
    )

    embed = discord.Embed(
        title="Ticket Opened",
        description=f"Thanks for reaching out, {user.mention}! Topic: **{topic}**\nStaff will be with you shortly. Use the button below to close this ticket when you're done.",
        color=discord.Color.green(),
    )
    await ticket_channel.send(embed=embed, view=CloseTicketView())

    await interaction.response.send_message(
        f"Your ticket has been created: {ticket_channel.mention}", ephemeral=True
    )


class CloseTicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Close Ticket", style=discord.ButtonStyle.red, custom_id="close_ticket")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Closing this ticket in 3 seconds...")
        await asyncio.sleep(3)
        await interaction.channel.delete()


class MenuView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        # Link buttons open a URL directly and don't use a callback,
        # so it's added as an item instead of a decorated method.
        self.add_item(discord.ui.Button(
            label="Card",
            style=discord.ButtonStyle.link,
            url=SELLAUTH_URL,
        ))

    @discord.ui.button(label="Buy The Menu(OPENS A TICKET)", style=discord.ButtonStyle.green, custom_id="open_ticket")
    async def buy_menu(self, interaction: discord.Interaction, button: discord.ui.Button):
        await open_ticket(interaction, topic="Buy The Menu")


class BuyerPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        # Link buttons open a URL directly and don't trigger a callback,
        # so they're added as an item instead of a decorated method.
        self.add_item(discord.ui.Button(
            label="Download The Menu",
            style=discord.ButtonStyle.link,
            url=MENU_DOWNLOAD_URL,
        ))

    @discord.ui.button(label="Request HWID Reset", style=discord.ButtonStyle.blurple, custom_id="request_refresh")
    async def request_refresh(self, interaction: discord.Interaction, button: discord.ui.Button):
        await open_ticket(interaction, topic="HWID Reset")


class Client(discord.Client):
    async def setup_hook(self):
        # Tiny web server so Render's Web Service sees an open port and finishes deploying.
        # (aiohttp is already installed as a dependency of discord.py)
        app = web.Application()
        app.router.add_get('/', lambda request: web.Response(text='Bot is running'))
        runner = web.AppRunner(app)
        await runner.setup()
        port = int(os.environ.get('PORT', 10000))
        await web.TCPSite(runner, '0.0.0.0', port).start()
        print(f"Web server listening on port {port}")

    async def on_ready(self):
        print(f'Logged on as {self.user}!')
        # Re-register persistent views so buttons still work after a restart
        self.add_view(MenuView())
        self.add_view(CloseTicketView())
        self.add_view(BuyerPanelView())

        # Announce that the bot is back online in #bot-status, in every server it's in
        for guild in self.guilds:
            status_channel = discord.utils.get(guild.text_channels, name='bot-status')
            if status_channel:
                embed = discord.Embed(
                    title="",
                    description=(
                        "# The Bot Is Currently Online\n"
                        "## You Can Now Buy THe Menu Or Request A HWID Reset"
                    ),
                    color=discord.Color.green(),
                )
                await status_channel.send(embed=embed)

            # Auto-send the dashboard and buyer panel on startup
            menu_channel = discord.utils.get(guild.text_channels, name='dashboard')
            if menu_channel:
                await self.send_menu_embed(menu_channel)

            panel_channel = discord.utils.get(guild.text_channels, name='buyer-panel')
            if panel_channel:
                await self.send_buyer_panel_embed(panel_channel)

    async def send_menu_embed(self, channel):
        embed = discord.Embed(
            title="Buy Lunar Paid",
            description=(
                "## *Payment Methods* \n ### 1000 robux \n ### CashApp(not supported yet)\n### PayPal(not supported yet)\n### Card\n### Server Boost\n-# (menu is not out btw)\n-# this is where you would buy Lunar"
            ),
            color=discord.Color.pink()
        )
        embed.add_field(
            name="",
            value="",
            inline=False
        )
        await channel.send(embed=embed, view=MenuView())

    async def send_buyer_panel_embed(self, channel):
        embed = discord.Embed(
            title="Buyer Panel",
            description="Download the menu below, or request a HWID Reset",
            color=discord.Color.pink(),
        )
        await channel.send(embed=embed, view=BuyerPanelView())

    async def on_message(self, message):
        # Don't let the bot respond to itself
        if message.author == self.user:
            return

        # Respond when someone types "hello"
        if message.content.lower() == 'hello':
            await message.channel.send('Hello!')

        # Owner-only command to resend the dashboard/menu embed
        if message.content == '$dashboard':
            if message.author.id != message.guild.owner_id:
                await message.channel.send("Only the server owner can use this command.")
                return
            await self.send_menu_embed(message.channel)
            try:
                await message.delete()
            except discord.Forbidden:
                print("Missing 'Manage Messages' permission to delete the command message.")

        # Command to send the buyer panel embed
        if message.content == '$buyerpanel':
            await self.send_buyer_panel_embed(message.channel)
            try:
                await message.delete()
            except discord.Forbidden:
                print("Missing 'Manage Messages' permission to delete the command message.")

        # Command to make the bot repeat whatever text follows "$talk "
        if message.content.startswith('$talk '):
            text_to_say = message.content[len('$talk '):]
            await message.channel.send(text_to_say)
            try:
                await message.delete()
            except discord.Forbidden:
                print("Missing 'Manage Messages' permission to delete the command message.")

        # Owner-only command to test the Supabase connection by listing the "todos" table
        if message.content == '$todos':
            if message.author.id != message.guild.owner_id:
                await message.channel.send("Only the server owner can use this command.")
                return
            if supabase is None:
                await message.channel.send("Supabase isn't configured (check SUPABASE_URL / SUPABASE_KEY in .env).")
                return
            try:
                todos = await run_query(lambda: supabase.table('todos').select("*").execute().data)
            except Exception as e:
                await message.channel.send(f"Supabase error: `{e}`")
                return
            if not todos:
                await message.channel.send("The todos table is empty.")
            else:
                await message.channel.send("**Todos**\n" + "\n".join(f"- {t['name']}" for t in todos))

        # Owner-only command to shut the bot down cleanly
        if message.content == '$shutdownbot':
            if message.author.id != message.guild.owner_id:
                await message.channel.send("Only the server owner can use this command.")
                return

            guild = message.guild

            # Delete every message the bot has sent, in every text channel it can see
            for channel in guild.text_channels:
                try:
                    async for msg in channel.history(limit=None):
                        if msg.author == self.user:
                            try:
                                await msg.delete()
                            except (discord.Forbidden, discord.NotFound):
                                pass
                except discord.Forbidden:
                    continue  # bot can't read history in this channel, skip it

            # Post the offline notice in #bot-status
            status_channel = discord.utils.get(guild.text_channels, name='bot-status')
            if status_channel:
                embed = discord.Embed(
                    title="",
                    description=(
                        "# The bot is offline\n"
                        "## DO NOT BUY THE MENU\n"
                        "Please wait, the bot may be under maintenance or UnityCube's PC is off."
                    ),
                    color=discord.Color.red(),
                )
                await status_channel.send(content=STATUS_PING_TEXT, embed=embed, allowed_mentions=ALLOWED_ROLE_PING)

            print("Shutdown command received. Closing bot...")
            await self.close()


intents = discord.Intents.default()
intents.message_content = True

client = Client(intents=intents)
client.run(TOKEN)
sys.exit(0)