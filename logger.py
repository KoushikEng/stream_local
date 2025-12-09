import logging

# Configure logging
logging.basicConfig(
    level=logging.WARNING,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("StreamLocal")