# Pin Controller Bot

A Discord bot designed to manage pinned messages by forwarding them to a dedicated channel, unpinning them from the original channel, and providing easy unpin functionality. Built with `discord.py`, this bot enhances message organization in Discord servers.

## Features
- Automatically forwards pinned messages to a designated pin channel.
- Supports a separate channel for "secret" pins from specific channels.
- Uses webhooks to replicate the original author's message style.
- Provides commands: `!pin <message_id>` to pin and `!unpin <message_id>` to unpin.
- Sends embed notifications with links to both original and pinned messages.

## Prerequisites
- Python 3.8 or higher
- A Discord bot token (create one via the [Discord Developer Portal](https://discord.com/developers/applications))
- A Discord server where the bot has `Manage Webhooks` and `Send Messages` permissions

## Setup

### 1. Clone the Repository
    git clone https://github.com/yourusername/pin-controller-bot.git
    cd pin-controller-bot

### 2. Install Dependencies

Install the required Python packages listed in requirements.txt

    pip install -r requirements.txt

### 3. Configure Environment Variables

Create a .env file in the root directory and add your bot token:
Replace your_discord_bot_token_here with the token from the Discord Developer Portal.

    BOT_TOKEN=your_discord_bot_token_here

4. Customize Channel Names

Edit the following variables in bot.py if you want custom channel names:

    PIN_CHANNEL_NAME: Default is "pins". Where pinned messages are sent.
    SECRET_PIN_CHANNEL_NAME: Default is "secret-pins". For pins from secret channels.
    SECRET_CHANNELS: Default is an empty list. Add channel names (e.g., ["private-channel"]) to treat them as secret.

5. Run the Bot

Start the bot with

    python pincontroller.py
