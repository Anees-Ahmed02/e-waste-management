import json
import hashlib
import datetime
import sqlite3

class Block:
    def __init__(self, block_index, timestamp, data, previous_hash):
        self.block_index = block_index
        # Ensure timestamp is a string
        if isinstance(timestamp, datetime.datetime):
            self.timestamp = timestamp.isoformat()
        else:
            self.timestamp = str(timestamp)
        self.data = data
        self.previous_hash = previous_hash
        self.hash = self.compute_hash()

    def compute_hash(self):
        block_string = json.dumps({
            "block_index": self.block_index,
            "timestamp": self.timestamp,
            "data": self.data,
            "previous_hash": self.previous_hash
        }, sort_keys=True).encode()
        return hashlib.sha256(block_string).hexdigest()

    def to_dict(self):
        return {
            "block_index": self.block_index,
            "timestamp": self.timestamp,
            "data": self.data,
            "previous_hash": self.previous_hash,
            "hash": self.hash
        }

class Blockchain:
    def __init__(self, db_path='ewaste.db'):
        self.db_path = db_path
        self.chain = []
        self.load_chain()

    def load_chain(self):
        """Load blockchain from database or create genesis block."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS blockchain
                     (block_index INTEGER PRIMARY KEY,
                      timestamp TEXT,
                      data TEXT,
                      previous_hash TEXT,
                      hash TEXT)''')
        c.execute("SELECT block_index, timestamp, data, previous_hash, hash FROM blockchain ORDER BY block_index")
        rows = c.fetchall()
        conn.close()

        if rows:
            for row in rows:
                block = Block(row[0], row[1], json.loads(row[2]), row[3])
                block.hash = row[4]  # use stored hash
                self.chain.append(block)
        else:
            # Create genesis block
            genesis_block = Block(0, datetime.datetime.now().isoformat(), {"message": "Genesis Block"}, "0")
            self.chain.append(genesis_block)
            self._save_block(genesis_block)

    def _save_block(self, block):
        """Insert a block into the database."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('''INSERT INTO blockchain (block_index, timestamp, data, previous_hash, hash)
                     VALUES (?, ?, ?, ?, ?)''',
                  (block.block_index, block.timestamp, json.dumps(block.data), block.previous_hash, block.hash))
        conn.commit()
        conn.close()

    def add_block(self, data):
        """Add a new block to the chain."""
        previous_block = self.chain[-1]
        new_index = previous_block.block_index + 1
        # Use ISO format string for timestamp
        new_block = Block(new_index, datetime.datetime.now().isoformat(), data, previous_block.hash)
        self.chain.append(new_block)
        self._save_block(new_block)
        return new_block

    def is_chain_valid(self):
        """Verify integrity of the blockchain."""
        for i in range(1, len(self.chain)):
            current = self.chain[i]
            previous = self.chain[i-1]

            if current.hash != current.compute_hash():
                return False
            if current.previous_hash != previous.hash:
                return False
        return True

    def get_chain_data(self):
        """Return list of block dicts for display."""
        return [block.to_dict() for block in self.chain]