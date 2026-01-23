export function createSchema(db) {
  // Roles table
  db.exec(`
    CREATE TABLE IF NOT EXISTS roles (
      id TEXT PRIMARY KEY,
      name TEXT NOT NULL,
      description TEXT,
      required_skills TEXT NOT NULL
    )
  `);

  // Resources table
  db.exec(`
    CREATE TABLE IF NOT EXISTS resources (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      skill TEXT NOT NULL,
      title TEXT NOT NULL,
      url TEXT NOT NULL,
      type TEXT,
      level TEXT
    )
  `);

  // Questions table
  db.exec(`
    CREATE TABLE IF NOT EXISTS questions (
      id INTEGER PRIMARY KEY,
      question TEXT NOT NULL,
      category TEXT,
      subcategory TEXT,
      answer_type TEXT NOT NULL,
      options TEXT,
      skill_mappings TEXT NOT NULL
    )
  `);

  // Sessions table
  db.exec(`
    CREATE TABLE IF NOT EXISTS sessions (
      id TEXT PRIMARY KEY,
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
      completed_at DATETIME,
      skill_vector TEXT
    )
  `);

  // Answers table
  db.exec(`
    CREATE TABLE IF NOT EXISTS answers (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      session_id TEXT NOT NULL,
      question_id INTEGER NOT NULL,
      answer_value TEXT NOT NULL,
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY (session_id) REFERENCES sessions(id),
      FOREIGN KEY (question_id) REFERENCES questions(id)
    )
  `);

  // Roadmaps table
  db.exec(`
    CREATE TABLE IF NOT EXISTS roadmaps (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      session_id TEXT NOT NULL,
      role_id TEXT NOT NULL,
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY (session_id) REFERENCES sessions(id),
      FOREIGN KEY (role_id) REFERENCES roles(id)
    )
  `);

  // Roadmap items table
  db.exec(`
    CREATE TABLE IF NOT EXISTS roadmap_items (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      roadmap_id INTEGER NOT NULL,
      step_number INTEGER NOT NULL,
      title TEXT NOT NULL,
      description TEXT,
      skill TEXT,
      resources TEXT,
      status TEXT DEFAULT 'pending',
      completed_at DATETIME,
      FOREIGN KEY (roadmap_id) REFERENCES roadmaps(id)
    )
  `);
}

