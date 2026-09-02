# Twitch Stream Analytics

Real-time chat and audio transcription for Twitch streams.

## Setup

```bash
python3.10 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Configuration

Create `.env`:

```env
DB_NAME=your_database
DB_USER=your_user
DB_PASSWORD=your_password
DB_HOST=localhost
DEEPGRAM_API_KEY=your_key
TWITCH_OAUTH=your_token
```

## Run

```bash
python src/main.py
```

Edit `src/main.py` to add broadcasters:

```python
broadcaster_logins = [
    'shadowkekw',
    'strogo',
    'cutierover',
]
```

## Database

- **User**: Twitch users
- **Message**: Chat messages (IRC)
- **AudioTranscription**: Deepgram transcriptions

Query example:

```python
from models import User, chat

streamer = User.get(User.login == 'shadowkekw')
messages = chat.Message.select().where(chat.Message.broadcaster == streamer)
```

## Structure

```
src/
├── parsers/
│   ├── audio/    # Streamlink + Deepgram
│   └── chat/     # IRC WebSocket
└── models/       # Peewee ORM
```

