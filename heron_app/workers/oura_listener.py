import json
import time
import base64
import redis
import logging
import threading
from celery import Celery
from celery.signals import worker_ready
from heron_app.db.database import SessionLocal
from heron_app.db.models.transaction import Transaction
from datetime import datetime

# Setup logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
formatter = logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)

logger.propagate = False

# Redis client. XREAD blocks for up to BLOCK_MS, so the socket timeout must be
# longer, or a quiet stream raises TimeoutError.
BLOCK_MS = 5000
redis_client = redis.Redis(host="redis", port=6379, decode_responses=True, socket_timeout=15)
stream_name = "oura.events"

# Celery app
celery = Celery("oura_listener", broker="redis://redis:6379/0")


@celery.task
def handle_oura_event(tx_hash):
    logger.debug(f"✅ Found transaction hash: {tx_hash}")

    session = SessionLocal()
    try:
        tx = session.query(Transaction).filter_by(tx_hash=tx_hash).first()
        if tx and tx.status == "submitted":
            tx.status = "confirmed"
            tx.confirmed_at = datetime.utcnow()
            session.commit()
            logger.info(f"✅ Updated transaction {tx_hash} to 'confirmed'")
        else:
            logger.debug(f"Transaction {tx_hash} not tracked or already confirmed.")
    except Exception as e:
        logger.error(f"❌ DB error confirming tx {tx_hash}: {e}")
        session.rollback()
    finally:
        session.close()


def stream_listener():
    logger.info("Started Redis stream listener thread.")
    last_id = "0"  # Start from new messages only
    while True:
        try:
            results = redis_client.xread({stream_name: last_id}, block=BLOCK_MS, count=10)

            logger.debug(f"Received {len(results)} messages from Redis stream.")
            for stream, messages in results:
                logger.debug(f"Reading {len(messages)} messages from stream: {stream}")
                for msg_id, msg_data in messages:
                    last_id = msg_id
                    raw_event = list(msg_data.values())[0]
                    if raw_event:
                        try:
                            # Oura v2 ParseCbor record: one transaction, hash in base64
                            event = json.loads(raw_event)
                            tx_hash = event.get("hash")
                            if tx_hash:
                                handle_oura_event.delay(base64.b64decode(tx_hash).hex())
                            else:
                                logger.warning("Unknown event format.")
                        except ValueError as e:  # bad JSON or bad base64
                            logger.warning(f"Failed to parse event: {e}")
        except redis.exceptions.TimeoutError:
            # An empty poll that outlived the socket timeout; just poll again.
            logger.debug("Redis stream poll timed out.")
        except Exception as e:
            logger.error(f"Error polling Redis stream: {e}")
            time.sleep(5)


@worker_ready.connect
def start_listener_thread(sender, **kwargs):
    logger.info("Worker is ready. Launching Redis listener thread.")
    t = threading.Thread(target=stream_listener, daemon=True)
    t.start()