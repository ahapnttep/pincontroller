import discord
from discord.ext import commands
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")  # Bot token fetched from .env file

# Generic channel names for pinned messages
PIN_CHANNEL_NAME = "pins"  # Default channel for pinned messages
SECRET_PIN_CHANNEL_NAME = "secret-pins"  # Channel for secret/private pins

# List of channel names considered "secret" (can be configured externally if needed)
SECRET_CHANNELS = []  # Empty by default, can be populated via config or environment

# Bot setup with required intents
intents = discord.Intents.default()
intents.guilds = True
intents.messages = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Dictionary to store pinned message data for unpinning control
pinned_messages = {}

# Event triggered when the bot is ready
@bot.event
async def on_ready():
    print(f"**[DEBUG]** Bot is online as {bot.user}")

# Core function to process a pinned message
async def process_pinned_message(message, pinned_message):
    # Check if the bot has permission to manage webhooks
    if not message.guild.me.guild_permissions.manage_webhooks:
        print(f"**[DEBUG]** Missing manage_webhooks permissions in {message.guild.name}.")
        return

    # Determine the appropriate pin channel based on the source channel
    pin_channel_name = SECRET_PIN_CHANNEL_NAME if message.channel.name in SECRET_CHANNELS else PIN_CHANNEL_NAME
    pin_channel = discord.utils.get(message.guild.text_channels, name=pin_channel_name)

    # Create the pin channel if it doesn't exist
    if not pin_channel:
        try:
            pin_channel = await message.guild.create_text_channel(
                pin_channel_name, reason="Auto-created by bot for pin forwarding"
            )
        except Exception as e:
            print(f"**[DEBUG]** Failed to create #{pin_channel_name} channel: {e}")
            return

    try:
        # Generate link to the original message
        original_message_link = f"https://discord.com/channels/{message.guild.id}/{message.channel.id}/{pinned_message.id}"

        # Create an embed notification for the pin channel
        embed = discord.Embed(
            title="📌 MESSAGE PINNED",
            description=(
                f"👤 {message.author.mention} pinned a message from {pinned_message.author.mention} in {message.channel.mention}.\n"
                f"✉️ **[Click here to view the original message]({original_message_link})**\n"
                f"🗑 **Run !unpin {pinned_message.id} to unpin the message.**"
            ),
            color=discord.Color.blue(),
        )
        embed.set_footer(text="🤖 Pin Controller Bot")

        embed_message = await pin_channel.send(embed=embed)

        # Create or fetch a webhook for the pin channel
        webhooks = await pin_channel.webhooks()
        webhook = discord.utils.get(webhooks, name="PinForwarder")

        if not webhook:
            webhook = await pin_channel.create_webhook(name="PinForwarder")

        # Send the pinned message via webhook, mimicking the original author
        avatar_url = pinned_message.author.avatar.url if pinned_message.author.avatar else None
        files = [await attachment.to_file() for attachment in pinned_message.attachments]

        webhook_message = await webhook.send(
            content=pinned_message.content,
            username=pinned_message.author.display_name,
            avatar_url=avatar_url,
            files=files,
            wait=True,
        )
        webhook_message = await pin_channel.fetch_message(webhook_message.id)

        message_link = f"https://discord.com/channels/{pin_channel.guild.id}/{pin_channel.id}/{webhook_message.id}"

        # Store pinned message data for later unpinning
        pinned_messages[str(pinned_message.id)] = {
            "embed_id": embed_message.id,
            "webhook_id": webhook_message.id,
            "origin_channel": message.channel.id,
            "original_message_link": original_message_link,
            "message_link": message_link
        }

        # Unpin the message from the original channel
        await pinned_message.unpin()

        # Send confirmation embed to the original channel
        confirmation_embed = discord.Embed(
            title="📌 MESSAGE PINNED",
            description=(
                f"🗣️ **Message by** {pinned_message.author.mention}\n"
                f"👤 **Pinned by** {message.author.mention}\n"
                f"✉️ **[Click here for original message]({original_message_link})**\n"
                f"📍 **[Click here for pinned message]({message_link})**\n"
                f"🗑 **Unpin with:** !unpin {pinned_message.id}"
            ),
            color=discord.Color.green()
        )
        confirmation_embed.set_footer(text="🤖 Pin Controller Bot")

        await message.channel.send(embed=confirmation_embed)

    except Exception as e:
        print(f"**[DEBUG]** Error processing pinned messages: {e}")

# Command to manually pin a message by ID
@bot.command(name="pin")
async def pin(ctx, message_id: int):
    try:
        await ctx.message.delete()  # Delete the command message
        message = await ctx.channel.fetch_message(message_id)
        await process_pinned_message(ctx.message, message)
    except discord.NotFound:
        await ctx.send("❌ Message not found.", delete_after=5)
    except Exception as e:
        print(f"**[DEBUG]** Error while pinning message: {e}")
        await ctx.send("❌ An error occurred while trying to pin the message.", delete_after=5)

# Event to detect when a message is pinned naturally (via Discord UI)
@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    await bot.process_commands(message)
    if message.type == discord.MessageType.pins_add:
        pinned_messages_list = await message.channel.pins()
        if pinned_messages_list:
            await process_pinned_message(message, pinned_messages_list[0])

# Command to unpin a message by its original ID
@bot.command(name="unpin", aliases=["unfix"])
async def unpin(ctx, message_id: int):
    await ctx.message.delete()  # Delete the command message
    try:
        message_id = str(message_id)  # Ensure ID is treated as string
        if message_id not in pinned_messages:
            await ctx.send("❌ This message is not registered as pinned.", delete_after=5)
            return

        pinned_data = pinned_messages[message_id]

        # Determine the pin channel
        pin_channel_name = SECRET_PIN_CHANNEL_NAME if ctx.channel.name in SECRET_CHANNELS else PIN_CHANNEL_NAME
        pin_channel = discord.utils.get(ctx.guild.text_channels, name=pin_channel_name)

        if not pin_channel:
            await ctx.send("❌ Pin channel not found.", delete_after=5)
            return

        # Delete the embed from the pin channel
        if "embed_id" in pinned_data:
            try:
                embed_message = await pin_channel.fetch_message(pinned_data["embed_id"])
                await embed_message.delete()
            except discord.NotFound:
                print(f"**[DEBUG]** Embed not found for {message_id}, may have been deleted manually.")
            except discord.HTTPException as e:
                print(f"**[DEBUG]** Error deleting embed for {message_id}: {e}")

        # Delete the webhook message from the pin channel
        if "webhook_id" in pinned_data:
            try:
                webhook_message = await pin_channel.fetch_message(pinned_data["webhook_id"])
                await webhook_message.delete()
            except discord.NotFound:
                print(f"**[DEBUG]** Webhook message not found for {message_id}, may have been deleted manually.")
            except discord.HTTPException as e:
                print(f"**[DEBUG]** Error deleting webhook message for {message_id}: {e}")

        # Remove from pinned messages dictionary
        del pinned_messages[message_id]

        # Fetch original message for accurate author mention
        origin_channel = bot.get_channel(pinned_data["origin_channel"])
        original_message = await origin_channel.fetch_message(int(message_id))

        # Notify the pin channel of the unpin action
        unpin_embed = discord.Embed(
            title="🗑 MESSAGE UNPINNED",
            description=f"👤 {ctx.author.mention} unpinned a message from {original_message.author.mention}.",
            color=discord.Color.red(),
        )
        unpin_embed.set_footer(text="🤖 Pin Controller Bot")

        if pin_channel:
            await pin_channel.send(embed=unpin_embed)

        # Confirm unpin in the original channel
        confirmation_embed = discord.Embed(
            title="🗑 MESSAGE UNPINNED",
            description=f"{ctx.author.mention} unpinned a message from {original_message.author.mention}.",
            color=discord.Color.red(),
        )
        confirmation_embed.set_footer(text="🤖 Pin Controller Bot")

        await origin_channel.send(embed=confirmation_embed)

    except discord.NotFound as e:
        print(f"**[DEBUG]** Message not found error while unpinning: {e}")
        await ctx.send("❌ Could not find the message to unpin. It may have been deleted.", delete_after=5)
    except discord.HTTPException as e:
        print(f"**[DEBUG]** HTTP error while unpinning: {e}")
        await ctx.send("❌ An error occurred while trying to unpin. Try again later.", delete_after=5)
    except Exception as e:
        print(f"**[DEBUG]** Unexpected error while unpinning: {e}")
        await ctx.send("❌ An unexpected error occurred while unpinning the message.", delete_after=5)

# Run the bot with the token from .env
bot.run(BOT_TOKEN)
import discord
from discord.ext import commands
import os
from dotenv import load_dotenv

# Load environment variables from the .env file
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID", 0))
PIN_CHANNEL_ID = int(os.getenv("PIN_CHANNEL_ID", 0))
SECRET_PIN_CHANNEL_ID = int(os.getenv("SECRET_PIN_CHANNEL_ID", 0))
SECRET_CHANNELS = [int(cid.strip()) for cid in os.getenv("SECRET_CHANNELS", "").split(",") if cid.strip()]

# Set up bot intents
intents = discord.Intents.default()
intents.guilds = True
intents.messages = True
intents.message_content = True

# Initialize the bot instance
bot = commands.Bot(command_prefix="!", intents=intents)

# ==============================
#  VIEW: Unpin Button Interface
# ==============================
class UnpinButtonView(discord.ui.View):
    """UI view that adds an 'Unpin' button under the pin confirmation message."""

    def __init__(self, message_id: int):
        super().__init__(timeout=None)
        self.message_id = message_id

    @discord.ui.button(label="🗑 Unpin", style=discord.ButtonStyle.danger, custom_id="unpin_button")
    async def unpin_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Handle the Unpin button press."""
        try:
            # Create a fake context object to reuse the existing unpin command
            fake_ctx = type("FakeCtx", (), {})()
            fake_ctx.guild = interaction.guild
            fake_ctx.channel = interaction.channel
            fake_ctx.author = interaction.user
            fake_ctx.message = interaction.message
            fake_ctx.send = interaction.response.send_message

            # Trigger the existing unpin command logic
            await unpin.callback(fake_ctx, int(self.message_id))

        except Exception as e:
            print(f"**[DEBUG]** Error on Unpin button: {e}")
            await interaction.response.send_message("❌ Error while trying to unpin the message.", ephemeral=True)

# Store metadata of pinned messages
pinned_messages = {}

# ==============================
#  BOT READY EVENT
# ==============================
@bot.event
async def on_ready():
    """Triggered when the bot is successfully connected and ready."""
    print(f"**[DEBUG]** Bot online as {bot.user}")

# ==============================
#  CORE LOGIC: PROCESS PIN
# ==============================
async def process_pinned_message(message, pinned_message):
    """Process and forward a pinned message to the designated pins channel."""
    if not message.guild.me.guild_permissions.manage_webhooks:
        print(f"**[DEBUG]** Missing 'Manage Webhooks' permission in {message.guild.name}")
        return

    # Select the proper pin channel (normal or secret)
    if message.channel.id in SECRET_CHANNELS and SECRET_PIN_CHANNEL_ID:
        pin_channel = message.guild.get_channel(SECRET_PIN_CHANNEL_ID)
    else:
        pin_channel = message.guild.get_channel(PIN_CHANNEL_ID)

    if not pin_channel:
        print("**[DEBUG]** Pin channel not found. Check PIN_CHANNEL_ID in .env")
        return

    try:
        # Build link to the original pinned message
        original_message_link = f"https://discord.com/channels/{message.guild.id}/{message.channel.id}/{pinned_message.id}"

        # Create initial notification embed for the pin channel
        embed = discord.Embed(
            title="📌 MESSAGE PINNED",
            description=(
                f"👤 {message.author.mention} pinned a message from {pinned_message.author.mention} in {message.channel.mention}.\n"
                f"✉️ **[Click here to view the original message]({original_message_link})**\n"
                f"🗑 **Run !unpin {pinned_message.id} to unpin the message.**"
            ),
            color=discord.Color.blue(),
        )
        embed.set_footer(text="🤖 Pin Controller Bot")

        # Send embed to the pin channel
        embed_message = await pin_channel.send(embed=embed)

        # Retrieve or create the webhook used to mirror pinned messages
        webhooks = await pin_channel.webhooks()
        webhook = discord.utils.get(webhooks, name="PinForwarder")
        if not webhook:
            webhook = await pin_channel.create_webhook(name="PinForwarder")

        # Forward original message content through the webhook
        avatar_url = pinned_message.author.avatar.url if pinned_message.author.avatar else None
        files = [await attachment.to_file() for attachment in pinned_message.attachments]

        webhook_message = await webhook.send(
            content=pinned_message.content,
            username=pinned_message.author.display_name,
            avatar_url=avatar_url,
            files=files,
            wait=True,
        )

        webhook_message = await pin_channel.fetch_message(webhook_message.id)
        message_link = f"https://discord.com/channels/{pin_channel.guild.id}/{pin_channel.id}/{webhook_message.id}"

        # Store pinned message data in memory
        pinned_messages[str(pinned_message.id)] = {
            "embed_id": embed_message.id,
            "webhook_id": webhook_message.id,
            "origin_channel": message.channel.id,
            "original_message_link": original_message_link,
            "message_link": message_link,
        }

        # Unpin the original message after copying it
        await pinned_message.unpin()

        # Create confirmation embed for the original channel
        confirmation_embed = discord.Embed(
            title="📌 MESSAGE PINNED",
            description=(
                f"🗣️ **Message by** {pinned_message.author.mention}\n"
                f"👤 **Pinned by** {message.author.mention}\n"
                f"✉️ **[Original message]({original_message_link})**\n"
                f"📍 **[Pinned version]({message_link})**\n"
                f"🗑 **Unpin with:** !unpin {pinned_message.id}"
            ),
            color=discord.Color.green(),
        )
        confirmation_embed.set_footer(text="🤖 Pin Controller Bot")

        # Send confirmation embed with the Unpin button
        await message.channel.send(embed=confirmation_embed, view=UnpinButtonView(pinned_message.id))

    except Exception as e:
        print(f"**[DEBUG]** Error processing pinned message: {e}")

# ==============================
#  COMMAND: PIN
# ==============================
@bot.command(name="pin")
async def pin(ctx, message_id: int):
    """Manually pin a message using its ID."""
    try:
        await ctx.message.delete()
        message = await ctx.channel.fetch_message(message_id)
        await process_pinned_message(ctx.message, message)
    except discord.NotFound:
        await ctx.send("❌ Message not found.", delete_after=5)
    except Exception as e:
        print(f"**[DEBUG]** Error while pinning message: {e}")
        await ctx.send("❌ An error occurred while trying to pin the message.", delete_after=5)

# ==============================
#  EVENT: ON MESSAGE
# ==============================
@bot.event
async def on_message(message):
    """Handle automatic pin events and command processing."""
    if message.author == bot.user:
        return

    # Process bot commands normally
    await bot.process_commands(message)

    # Detect system pin event and handle it
    if message.type == discord.MessageType.pins_add:
        pinned_messages_list = await message.channel.pins()
        if pinned_messages_list:
            await process_pinned_message(message, pinned_messages_list[0])

# ==============================
#  COMMAND: UNPIN
# ==============================
@bot.command(name="unpin", aliases=["unfix"])
async def unpin(ctx, message_id: int):
    """Unpin a previously pinned message."""
    await ctx.message.delete()
    try:
        message_id = str(message_id)
        if message_id not in pinned_messages:
            await ctx.send("❌ This message is not registered as pinned.", delete_after=5)
            return

        pinned_data = pinned_messages[message_id]

        # Select the correct pin channel (normal or secret)
        if ctx.channel.id in SECRET_CHANNELS and SECRET_PIN_CHANNEL_ID:
            pin_channel = ctx.guild.get_channel(SECRET_PIN_CHANNEL_ID)
        else:
            pin_channel = ctx.guild.get_channel(PIN_CHANNEL_ID)

        if not pin_channel:
            await ctx.send("❌ Pin channel not found.", delete_after=5)
            return

        # Delete the stored embed message, if exists
        if "embed_id" in pinned_data:
            try:
                embed_message = await pin_channel.fetch_message(pinned_data["embed_id"])
                await embed_message.delete()
            except discord.NotFound:
                pass

        # Delete the webhook-forwarded message, if exists
        if "webhook_id" in pinned_data:
            try:
                webhook_message = await pin_channel.fetch_message(pinned_data["webhook_id"])
                await webhook_message.delete()
            except discord.NotFound:
                pass

        # Remove data from memory
        del pinned_messages[message_id]

        # Build and send confirmation embed
        origin_channel = bot.get_channel(pinned_data["origin_channel"])
        original_message = await origin_channel.fetch_message(int(message_id))

        unpin_embed = discord.Embed(
            title="🗑 MESSAGE UNPINNED",
            description=f"👤 {ctx.author.mention} unpinned a message from {original_message.author.mention}.",
            color=discord.Color.red(),
        )
        unpin_embed.set_footer(text="🤖 Pin Controller Bot")

        await pin_channel.send(embed=unpin_embed)
        await origin_channel.send(embed=unpin_embed)

    except Exception as e:
        print(f"**[DEBUG]** Error while unpinning: {e}")
        await ctx.send("❌ Error while trying to unpin the message.", delete_after=5)

# Run the bot
bot.run(BOT_TOKEN)
