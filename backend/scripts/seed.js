import db from '../db/index.js';
import { readFileSync } from 'fs';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

function seedRoles() {
  const rolesData = JSON.parse(
    readFileSync(join(__dirname, '../data/roles.json'), 'utf-8')
  );

  const insert = db.prepare(`
    INSERT OR REPLACE INTO roles (id, name, description, required_skills)
    VALUES (?, ?, ?, ?)
  `);

  const insertMany = db.transaction((roles) => {
    for (const role of roles) {
      insert.run(
        role.id,
        role.name,
        role.description,
        JSON.stringify(role.required_skills)
      );
    }
  });

  insertMany(rolesData);
  console.log(`Seeded ${rolesData.length} roles`);
}

function seedResources() {
  const resourcesData = JSON.parse(
    readFileSync(join(__dirname, '../data/resources.json'), 'utf-8')
  );

  const insert = db.prepare(`
    INSERT OR REPLACE INTO resources (skill, title, url, type, level)
    VALUES (?, ?, ?, ?, ?)
  `);

  const insertMany = db.transaction((resources) => {
    for (const skillGroup of resources) {
      for (const resource of skillGroup.resources) {
        insert.run(
          skillGroup.skill,
          resource.title,
          resource.url,
          resource.type,
          resource.level
        );
      }
    }
  });

  insertMany(resourcesData);
  console.log('Seeded resources');
}

function seedQuestions() {
  const questionsData = JSON.parse(
    readFileSync(join(__dirname, '../data/questions.json'), 'utf-8')
  );

  const insert = db.prepare(`
    INSERT OR REPLACE INTO questions (id, question, category, subcategory, answer_type, options, skill_mappings)
    VALUES (?, ?, ?, ?, ?, ?, ?)
  `);

  const insertMany = db.transaction((questions) => {
    for (const question of questions) {
      insert.run(
        question.id,
        question.question,
        question.category,
        question.subcategory,
        question.answer_type,
        question.options || '',
        JSON.stringify(question.skill_mappings)
      );
    }
  });

  insertMany(questionsData);
  console.log(`Seeded ${questionsData.length} questions`);
}

// Main seeding function
function seed() {
  console.log('Starting database seeding...');
  seedRoles();
  seedResources();
  seedQuestions();
  console.log('Database seeding completed!');
}

seed();
db.close();

