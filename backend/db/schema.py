def create_schema(conn):
    """Create database schema"""
    cursor = conn.cursor()
    
    # Roles table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS roles (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            required_skills TEXT NOT NULL
        )
    ''')
    
    # Resources table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS resources (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            skill TEXT NOT NULL,
            title TEXT NOT NULL,
            url TEXT NOT NULL,
            type TEXT,
            level TEXT
        )
    ''')
    
    # Questions table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS questions (
            id INTEGER PRIMARY KEY,
            question TEXT NOT NULL,
            category TEXT,
            subcategory TEXT,
            answer_type TEXT NOT NULL,
            options TEXT,
            skill_mappings TEXT NOT NULL
        )
    ''')
    
    # Sessions table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            completed_at DATETIME,
            skill_vector TEXT,
            adaptive_mode INTEGER DEFAULT 0,
            remaining_jobs TEXT
        )
    ''')
    
    # Answers table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS answers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            question_id INTEGER NOT NULL,
            answer_value TEXT NOT NULL,
            answer_type TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES sessions(id),
            FOREIGN KEY (question_id) REFERENCES questions(id)
        )
    ''')
    
    # Add answer_type column if it doesn't exist (for existing databases)
    try:
        cursor.execute('ALTER TABLE answers ADD COLUMN answer_type TEXT')
    except:
        pass  # Column already exists
    
    # Roadmaps table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS roadmaps (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            role_id TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES sessions(id),
            FOREIGN KEY (role_id) REFERENCES roles(id)
        )
    ''')
    
    # Roadmap items table
    cursor.execute('''
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
    ''')
    
    conn.commit()
