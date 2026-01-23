import Database from 'better-sqlite3';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';
import { mkdirSync } from 'fs';
import { createSchema } from './schema.js';
import dotenv from 'dotenv';

dotenv.config();

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const dbPath = process.env.DB_PATH || join(__dirname, '../data/nextstep.db');
const dbDir = dirname(dbPath);

// Create the directory if it doesn't exist
mkdirSync(dbDir, { recursive: true });

const db = new Database(dbPath);

// Enable foreign keys
db.pragma('foreign_keys = ON');

// Create schema
createSchema(db);

export default db;

