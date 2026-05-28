# Admin OTP Login Setup

## Prerequisites

1. **Create a Telegram Bot**
   - Message [@BotFather](https://t.me/BotFather) on Telegram
   - Send `/newbot` and follow the prompts
   - Copy the bot token (looks like `123456789:ABCdef...`)

2. **Get your Chat ID**
   - Start a chat with your new bot (send it any message)
   - Visit `https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates`
   - Find `"chat":{"id":123456789,...}` in the response — that number is your chat ID

3. **Configure the backend**

   Add to `backend/.env`:
   ```env
   TELEGRAM_BOT_TOKEN=123456789:ABCdef...
   TELEGRAM_ADMIN_CHAT_ID=123456789
   ```

## Creating Users

Users are created via CLI script only:

```bash
cd backend
python create_user.py --name "John Doe" --email john@example.com --password s3cret
```

To create an admin (superuser):

```bash
python create_user.py --admin --name "Admin" --email admin@local --password adminpass
```

The admin user is required for OTP login to work.

## Admin Login Flow

1. Open the login page
2. Click "Admin Login via OTP"
3. A 6-digit code is sent to your Telegram bot
4. Enter the code and click "Verify & Login"
5. You are logged in as the superuser with full access to all workspaces
