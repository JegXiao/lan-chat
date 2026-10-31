import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data')
SSL_DIR = os.path.join(BASE_DIR, 'ssl')
TEMPLATES_DIR = os.path.join(BASE_DIR, 'templates')
STATIC_DIR = os.path.join(BASE_DIR, 'static')
CHAT_LOGS_DIR = os.path.join(DATA_DIR, 'chat_logs')
CONFIG_PATH = os.path.join(DATA_DIR, 'config.json')
USERS_PATH = os.path.join(DATA_DIR, 'users.json')
SESSIONS_PATH = os.path.join(DATA_DIR, 'sessions.json')
MESSAGES_PATH = os.path.join(DATA_DIR, 'messages.json')
CERT_PATH = os.path.join(SSL_DIR, 'cert.pem')
KEY_PATH = os.path.join(SSL_DIR, 'key.pem')
PORT = 5000
TOKEN_EXPIRE_DAYS = 7
BCRYPT_ROUNDS = 12
MAX_MESSAGE_LENGTH = 2000
MAX_MESSAGE_RATE = 3
