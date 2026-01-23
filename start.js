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
  
  if (!existsSync(join(PROJECT_ROOT, 'backend/node_modules'))) {
    log('Installing backend dependencies...', 'blue');
    await execAsync('npm install', { cwd: join(PROJECT_ROOT, 'backend') });
  }
  
  if (!existsSync(join(PROJECT_ROOT, 'frontend/node_modules'))) {
    log('Installing frontend dependencies...', 'blue');
    await execAsync('npm install', { cwd: join(PROJECT_ROOT, 'frontend') });
  }
  
  log('✓ Dependencies installed', 'green');
}

// Generate data files
async function generateDataFiles() {
  log('Checking data files...', 'blue');
  
  const dataDir = join(PROJECT_ROOT, 'backend/data');
  const questionsFile = join(dataDir, 'questions.json');
  const rolesFile = join(dataDir, 'roles.json');
  const resourcesFile = join(dataDir, 'resources.json');
  
  if (!existsSync(questionsFile) || !existsSync(rolesFile) || !existsSync(resourcesFile)) {
    log('Generating data files...', 'blue');
    await execAsync('node scripts/generate-data.js', { cwd: join(PROJECT_ROOT, 'backend') });
  }
  
  log('✓ Data files ready', 'green');
}

// Seed database
async function seedDatabase() {
  log('Seeding database...', 'blue');
  await execAsync('npm run seed', { cwd: join(PROJECT_ROOT, 'backend') });
  log('✓ Database seeded', 'green');
}

// Start servers
function startServers() {
  log('Starting servers...', 'blue');
  
  // Start backend
  const backend = spawn('npm', ['run', 'dev'], {
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
