#!/usr/bin/env node

/**
 * NextStep Career Matcher - One-Click Start Script (Cross-Platform)
 * This script sets up and starts the entire application
 */

import { spawn, exec } from 'child_process';
import { promisify } from 'util';
import { existsSync } from 'fs';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';
import { readFileSync } from 'fs';

const execAsync = promisify(exec);
const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const PROJECT_ROOT = __dirname;

// Colors for output
const colors = {
  reset: '\x1b[0m',
  green: '\x1b[32m',
  blue: '\x1b[34m',
  yellow: '\x1b[33m',
  red: '\x1b[31m'
};

function log(message, color = 'reset') {
  console.log(`${colors[color]}${message}${colors.reset}`);
}

// Check prerequisites
async function checkPrerequisites() {
  log('Checking prerequisites...', 'blue');
  
  try {
    // Check Python
    await execAsync('python3 --version');
    log('✓ Python 3 detected', 'green');
  } catch (error) {
    log('❌ Python 3 is not installed. Please install Python 3.8+ first.', 'red');
    process.exit(1);
  }
  
  try {
    const { stdout: nodeVersion } = await execAsync('node -v');
    const majorVersion = parseInt(nodeVersion.replace('v', '').split('.')[0]);
    
    if (majorVersion < 18) {
      log(`❌ Node.js version 18+ is required. Current version: ${nodeVersion.trim()}`, 'red');
      process.exit(1);
    }
    
    log(`✓ Node.js ${nodeVersion.trim()} detected`, 'green');
  } catch (error) {
    log('❌ Node.js is not installed. Please install Node.js 18+ first.', 'red');
    process.exit(1);
  }
}

// Install dependencies
async function installDependencies() {
  log('Checking dependencies...', 'blue');
  
  // Setup Python virtual environment
  if (!existsSync(join(PROJECT_ROOT, 'backend/venv'))) {
    log('Creating Python virtual environment...', 'blue');
    await execAsync('python3 -m venv venv', { cwd: join(PROJECT_ROOT, 'backend') });
  }
  
  // Install Python dependencies
  const isWindows = process.platform === 'win32';
  const venvPython = isWindows 
    ? join(PROJECT_ROOT, 'backend/venv/Scripts/python.exe')
    : join(PROJECT_ROOT, 'backend/venv/bin/python3');
  const venvPip = isWindows
    ? join(PROJECT_ROOT, 'backend/venv/Scripts/pip.exe')
    : join(PROJECT_ROOT, 'backend/venv/bin/pip3');
  
  log('Installing backend dependencies...', 'blue');
  await execAsync(`${venvPip} install --upgrade pip`, { cwd: join(PROJECT_ROOT, 'backend') });
  await execAsync(`${venvPip} install -r requirements.txt`, { cwd: join(PROJECT_ROOT, 'backend') });
  
  if (!existsSync(join(PROJECT_ROOT, 'frontend/node_modules'))) {
    log('Installing frontend dependencies...', 'blue');
    await execAsync('npm install', { cwd: join(PROJECT_ROOT, 'frontend') });
  }
  
  log('✓ Dependencies installed', 'green');
}

// Generate data files (always regenerate to ensure latest version)
async function generateDataFiles() {
  log('Generating data files...', 'blue');
  
  const isWindows = process.platform === 'win32';
  const venvPython = isWindows
    ? join(PROJECT_ROOT, 'backend/venv/Scripts/python.exe')
    : join(PROJECT_ROOT, 'backend/venv/bin/python3');
  await execAsync(`${venvPython} scripts/generate_data.py`, { cwd: join(PROJECT_ROOT, 'backend') });
  
  log('✓ Data files ready', 'green');
}

// Seed database (delete old database to ensure fresh seed)
async function seedDatabase() {
  log('Seeding database...', 'blue');
  const isWindows = process.platform === 'win32';
  const venvPython = isWindows
    ? join(PROJECT_ROOT, 'backend/venv/Scripts/python.exe')
    : join(PROJECT_ROOT, 'backend/venv/bin/python3');
  
  // Remove old database to ensure fresh seed
  const dbPath = join(PROJECT_ROOT, 'backend/data/nextstep.db');
  if (existsSync(dbPath)) {
    const { unlinkSync } = require('fs');
    unlinkSync(dbPath);
  }
  
  await execAsync(`${venvPython} scripts/seed.py`, { cwd: join(PROJECT_ROOT, 'backend') });
  log('✓ Database seeded', 'green');
}

// Start servers
function startServers() {
  log('Starting servers...', 'blue');
  
  const isWindows = process.platform === 'win32';
  const venvPython = isWindows
    ? join(PROJECT_ROOT, 'backend/venv/Scripts/python.exe')
    : join(PROJECT_ROOT, 'backend/venv/bin/python3');
  
  // Start backend
  const backend = spawn(venvPython, ['app.py'], {
    cwd: join(PROJECT_ROOT, 'backend'),
    stdio: 'inherit',
    shell: true
  });
  
  // Wait a bit for backend to start
  setTimeout(() => {
    // Start frontend
    const frontend = spawn('npm', ['run', 'dev'], {
      cwd: join(PROJECT_ROOT, 'frontend'),
      stdio: 'inherit',
      shell: true
    });
    
    // Cleanup on exit
    const cleanup = () => {
      log('\nShutting down servers...', 'yellow');
      backend.kill();
      frontend.kill();
      process.exit(0);
    };
    
    process.on('SIGINT', cleanup);
    process.on('SIGTERM', cleanup);
    
    setTimeout(() => {
      log('', 'reset');
      log('✅ Application is running!', 'green');
      log('', 'reset');
      log('Backend:  http://localhost:3001', 'blue');
      log('Frontend: http://localhost:3000', 'blue');
      log('', 'reset');
      log('Press Ctrl+C to stop all servers', 'yellow');
      log('', 'reset');
    }, 3000);
  }, 2000);
}

// Main execution
async function main() {
  log('🚀 Starting NextStep Career Matcher...', 'blue');
  log('', 'reset');
  
  try {
    await checkPrerequisites();
    log('', 'reset');
    
    await installDependencies();
    log('', 'reset');
    
    await generateDataFiles();
    log('', 'reset');
    
    await seedDatabase();
    log('', 'reset');
    
    startServers();
  } catch (error) {
    log(`❌ Error: ${error.message}`, 'red');
    process.exit(1);
  }
}

main();
