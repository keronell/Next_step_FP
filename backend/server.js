import express from 'express';
import cors from 'cors';
import dotenv from 'dotenv';
import db from './db/index.js';
import { v4 as uuidv4 } from 'uuid';

dotenv.config();

const app = express();
const PORT = process.env.PORT || 3001;

app.use(cors());
app.use(express.json());

// Utility: Parse skill mappings from answer
function computeSkillVector(answers) {
  const skillVector = {};

  for (const answer of answers) {
    const question = db
      .prepare('SELECT skill_mappings, answer_type FROM questions WHERE id = ?')
      .get(answer.question_id);
    
    if (!question) continue;

    const skillMappings = JSON.parse(question.skill_mappings);
    
    // For Likert5: map 1-5 to 0-4 scale
    let normalizedValue = 0;
    if (question.answer_type === 'Likert5') {
      const answerValue = parseFloat(answer.answer_value) || 0;
      normalizedValue = (answerValue - 1) / 4; // Maps 1->0, 5->1
    } else if (question.answer_type === 'SingleChoice') {
      // For single choice, if answered, give partial credit
      normalizedValue = answer.answer_value && answer.answer_value !== 'Not sure' ? 0.5 : 0;
    } else if (question.answer_type === 'MultiChoice') {
      // For multi choice, count selections (comma-separated)
      const selections = answer.answer_value ? answer.answer_value.split(',').filter(v => v && v !== 'Not sure') : [];
      normalizedValue = Math.min(selections.length * 0.3, 1); // Up to 1.0 for multiple selections
    } else if (question.answer_type === 'Numeric') {
      // Normalize numeric (e.g., hours per week: 0-40 -> 0-1)
      const answerValue = parseFloat(answer.answer_value) || 0;
      normalizedValue = Math.min(answerValue / 40, 1);
    }

    for (const [skill, weight] of Object.entries(skillMappings)) {
      if (!skillVector[skill]) {
        skillVector[skill] = 0;
      }
      skillVector[skill] += normalizedValue * weight;
    }
  }

  // Normalize to 0-5 scale
  for (const skill in skillVector) {
    skillVector[skill] = Math.min(5, Math.max(0, skillVector[skill]));
  }

  return skillVector;
}

// Start session
app.post('/api/sessions', (req, res) => {
  const sessionId = uuidv4();
  const stmt = db.prepare('INSERT INTO sessions (id) VALUES (?)');
  stmt.run(sessionId);
  res.json({ session_id: sessionId });
});

// Get questions
app.get('/api/questions', (req, res) => {
  const questions = db
    .prepare('SELECT id, question, category, subcategory, answer_type, options FROM questions ORDER BY id')
    .all();
  res.json(questions);
});

// Submit answer
app.post('/api/sessions/:sessionId/answers', (req, res) => {
  const { sessionId } = req.params;
  const { question_id, answer_value, answer_type } = req.body;

  const stmt = db.prepare(`
    INSERT INTO answers (session_id, question_id, answer_value)
    VALUES (?, ?, ?)
  `);
  stmt.run(sessionId, question_id, answer_value);
  res.json({ success: true });
});

// Compute results and get top 5 roles
app.post('/api/sessions/:sessionId/compute', (req, res) => {
  const { sessionId } = req.params;

  // Get all answers for this session
  const answers = db
    .prepare(`
      SELECT a.question_id, a.answer_value
      FROM answers a
      WHERE a.session_id = ?
    `)
    .all(sessionId);

  // Compute skill vector
  const skillVector = computeSkillVector(answers);

  // Store skill vector
  db.prepare('UPDATE sessions SET skill_vector = ? WHERE id = ?')
    .run(JSON.stringify(skillVector), sessionId);

  // Get all roles
  const roles = db.prepare('SELECT * FROM roles').all();

  // Score each role
  const scoredRoles = roles.map(role => {
    const requiredSkills = JSON.parse(role.required_skills);
    let score = 0;
    let totalWeight = 0;
    const reasons = [];

    for (const [skill, requiredLevel] of Object.entries(requiredSkills)) {
      const userLevel = skillVector[skill] || 0;
      const match = Math.min(userLevel / requiredLevel, 1);
      score += match * requiredLevel;
      totalWeight += requiredLevel;

      if (userLevel < requiredLevel) {
        reasons.push({
          skill,
          gap: requiredLevel - userLevel,
          message: `Need ${requiredLevel - userLevel} more in ${skill}`
        });
      }
    }

    const finalScore = totalWeight > 0 ? (score / totalWeight) * 100 : 0;

    return {
      ...role,
      score: Math.round(finalScore),
      reasons: reasons.slice(0, 3) // Top 3 gaps
    };
  });

  // Sort by score and get top 5
  const top5 = scoredRoles
    .sort((a, b) => b.score - a.score)
    .slice(0, 5);

  // Mark session as completed
  db.prepare('UPDATE sessions SET completed_at = CURRENT_TIMESTAMP WHERE id = ?')
    .run(sessionId);

  res.json({
    skill_vector: skillVector,
    top_roles: top5
  });
});

// Generate roadmap for a role
app.post('/api/sessions/:sessionId/roadmap', (req, res) => {
  const { sessionId } = req.params;
  const { role_id } = req.body;

  // Get user skill vector
  const session = db
    .prepare('SELECT skill_vector FROM sessions WHERE id = ?')
    .get(sessionId);
  
  if (!session || !session.skill_vector) {
    return res.status(400).json({ error: 'Session not found or not completed' });
  }

  const skillVector = JSON.parse(session.skill_vector);

  // Get role requirements
  const role = db.prepare('SELECT * FROM roles WHERE id = ?').get(role_id);
  if (!role) {
    return res.status(404).json({ error: 'Role not found' });
  }

  const requiredSkills = JSON.parse(role.required_skills);

  // Identify gaps
  const gaps = [];
  for (const [skill, requiredLevel] of Object.entries(requiredSkills)) {
    const userLevel = skillVector[skill] || 0;
    if (userLevel < requiredLevel) {
      gaps.push({
        skill,
        current: userLevel,
        required: requiredLevel,
        gap: requiredLevel - userLevel
      });
    }
  }

  // Sort gaps by priority (largest gaps first)
  gaps.sort((a, b) => b.gap - a.gap);

  // Get resources for skills
  const getResources = (skill) => {
    return db
      .prepare('SELECT * FROM resources WHERE skill = ? LIMIT 3')
      .all(skill);
  };

  // Generate roadmap steps (3-5 steps)
  const numSteps = Math.min(5, Math.max(3, gaps.length));
  const roadmapSteps = [];

  for (let i = 0; i < numSteps; i++) {
    const gap = gaps[i];
    if (!gap) break;

    const resources = getResources(gap.skill);
    roadmapSteps.push({
      step_number: i + 1,
      title: `Improve ${gap.skill}`,
      description: `Build your ${gap.skill} skills from ${gap.current.toFixed(1)} to ${gap.required}`,
      skill: gap.skill,
      resources: resources.map(r => ({
        title: r.title,
        url: r.url,
        type: r.type,
        level: r.level
      }))
    });
  }

  // Save roadmap
  const roadmapStmt = db.prepare(`
    INSERT INTO roadmaps (session_id, role_id)
    VALUES (?, ?)
  `);
  const roadmapResult = roadmapStmt.run(sessionId, role_id);
  const roadmapId = roadmapResult.lastInsertRowid;

  // Save roadmap items
  const itemStmt = db.prepare(`
    INSERT INTO roadmap_items (roadmap_id, step_number, title, description, skill, resources)
    VALUES (?, ?, ?, ?, ?, ?)
  `);

  for (const step of roadmapSteps) {
    itemStmt.run(
      roadmapId,
      step.step_number,
      step.title,
      step.description,
      step.skill,
      JSON.stringify(step.resources)
    );
  }

  res.json({
    roadmap_id: roadmapId,
    role: {
      id: role.id,
      name: role.name,
      description: role.description
    },
    steps: roadmapSteps
  });
});

// Get roadmap
app.get('/api/sessions/:sessionId/roadmap', (req, res) => {
  const { sessionId } = req.params;

  const roadmap = db
    .prepare(`
      SELECT r.*, ro.name as role_name, ro.description as role_description
      FROM roadmaps r
      JOIN roles ro ON r.role_id = ro.id
      WHERE r.session_id = ?
      ORDER BY r.created_at DESC
      LIMIT 1
    `)
    .get(sessionId);

  if (!roadmap) {
    return res.status(404).json({ error: 'Roadmap not found' });
  }

  const items = db
    .prepare(`
      SELECT * FROM roadmap_items
      WHERE roadmap_id = ?
      ORDER BY step_number
    `)
    .all(roadmap.id);

  const itemsWithResources = items.map(item => ({
    ...item,
    resources: JSON.parse(item.resources || '[]')
  }));

  // Calculate progress
  const totalItems = items.length;
  const completedItems = items.filter(item => item.status === 'completed').length;
  const progress = totalItems > 0 ? Math.round((completedItems / totalItems) * 100) : 0;

  res.json({
    ...roadmap,
    items: itemsWithResources,
    progress
  });
});

// Update roadmap item status
app.patch('/api/roadmap-items/:itemId', (req, res) => {
  const { itemId } = req.params;
  const { status } = req.body;

  if (status === 'completed') {
    db.prepare(`
      UPDATE roadmap_items
      SET status = ?, completed_at = CURRENT_TIMESTAMP
      WHERE id = ?
    `).run(status, itemId);
  } else {
    db.prepare(`
      UPDATE roadmap_items
      SET status = ?, completed_at = NULL
      WHERE id = ?
    `).run(status, itemId);
  }

  res.json({ success: true });
});

app.listen(PORT, () => {
  console.log(`Server running on http://localhost:${PORT}`);
});

