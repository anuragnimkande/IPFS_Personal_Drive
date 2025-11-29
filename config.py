import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    PINATA_API_KEY = os.getenv("PINATA_API_KEY")
    PINATA_API_SECRET = os.getenv("PINATA_API_SECRET")
    PINATA_JWT = os.getenv("PINATA_JWT")
    PINATA_PIN_FILE_URL = "https://api.pinata.cloud/pinning/pinFileToIPFS"
    PINATA_GATEWAY = "https://gateway.pinata.cloud/ipfs"
    
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///files.db")
    FLASK_SECRET = os.getenv("FLASK_SECRET", "change-this-secret")
    PORT = int(os.getenv("PORT", 5000))