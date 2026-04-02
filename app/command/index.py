import sys
import asyncio
from pymongo import ASCENDING, DESCENDING, IndexModel
from config.mongoDb import db
from config.logger import logger

# ==========================================
# CONFIGURATION: DEFINE YOUR INDEXES HERE
# ==========================================

# Define the collection you are targeting
TARGET_COLLECTION = db.collection

# List of indexes to manage. 
# Uncomment or add your indexes here.
INDEXES = [
    # --- SAMPLE: Single Field Index ---
    # IndexModel(
    #     [("user_id", ASCENDING)],
    #     name="idx_user_id",
    #     background=True
    # ),

    # --- SAMPLE: Compound Unique Index ---
    # IndexModel(
    #     [("email", ASCENDING), ("tenant_id", ASCENDING)],
    #     name="idx_email_tenant_unique",
    #     unique=True,
    #     background=True
    # ),

    # --- SAMPLE: TTL Index (Auto-delete after time) ---
    # IndexModel(
    #     [("created_at", ASCENDING)],
    #     name="idx_created_at_ttl",
    #     expireAfterSeconds=3600,  # Delete after 1 hour
    #     background=True
    # ),

    # --- SAMPLE: Compound Index for Sorting/Filtering ---
    # IndexModel(
    #     [("status", ASCENDING), ("updated_at", DESCENDING)],
    #     name="idx_status_updated_at",
    #     background=True
    # ),
]

# ==========================================
# EXECUTION LOGIC
# ==========================================

async def up():
    """
    Creates (Apply) all indexes defined in the configuration.
    """
    try:
        if not INDEXES:
            logger.warning("No indexes defined in configuration to create.")
            return

        result = await TARGET_COLLECTION.create_indexes(INDEXES)
        
        for name in result:
            logger.info(f"  [CREATED] Index: {name}")
            
    except Exception as e:
        logger.error(f"Failed during UP operation: {e}")
        raise

async def down():
    """
    Drops (Delete) only the indexes defined in the configuration.
    Does NOT drop _id or indexes not listed in the config (safer).
    """
    try:
        if not INDEXES:
            logger.warning("No indexes defined in configuration to drop.")
            return

        for index_model in INDEXES:
            index_name = index_model.document.get("name")
            
            if not index_name:
                logger.warning(f"Skipping index without a name: {index_model.document}")
                continue

            try:
                await TARGET_COLLECTION.drop_index(index_name)
            except Exception as inner_e:
                logger.warning(f"  [SKIPPED] Could not drop {index_name}: {inner_e}")

    except Exception as e:
        logger.error(f"Failed during DOWN operation: {e}")
        raise

async def reset():
    """
    Hard Reset: Drops ALL custom indexes on the collection, then runs UP.
    """
    try:
        cursor = await TARGET_COLLECTION.list_indexes()
        async for index in cursor:
            if index['name'] != '_id_':
                await TARGET_COLLECTION.drop_index(index['name'])
                logger.info(f"  [WIPED] {index['name']}")
    except Exception as e:
        logger.error(f"Error wiping indexes: {e}")

    await up()

async def stats():
    """
    Universal Index Stats Viewer - Combined Log Output
    """
    try:
        cursor = await TARGET_COLLECTION.aggregate([{"$indexStats": {}}])
        stats_list = await cursor.to_list(length=None)
        
        if not stats_list:
            logger.info("No index statistics available.")
            return

        report_lines = ["\n=== CURRENT INDEX STATS ==="]
        
        for stat in stats_list:
            entry = (
                f"Name: {stat['name']}\n"
                f"  - Accesses: {stat['accesses']['ops']}\n"
                f"  - Since: {stat['accesses']['since']}"
            )
            report_lines.append(entry)
            
        final_report = "\n\n".join(report_lines)
        logger.info(final_report)

    except Exception as e:
        logger.error(f"Error fetching stats: {e}")

# ==========================================
# MAIN ENTRY POINT
# ==========================================

async def main():
    if len(sys.argv) < 2:
        print("Usage: python mongo_indexer.py [up|down|reset|stats]")
        return

    command = sys.argv[1].lower()

    if command == "up":
        await up()
    elif command == "down":
        await down()
    elif command == "reset":
        await reset()
    elif command == "stats":
        await stats()
    else:
        print(f"Unknown command: {command}")

if __name__ == "__main__":
    asyncio.run(main())