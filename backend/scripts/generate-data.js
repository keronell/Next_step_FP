import { readFileSync, writeFileSync } from 'fs';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

// Read CSV and parse it
function parseCSV(filePath) {
  const content = readFileSync(filePath, 'utf-8');
  const lines = content.split('\n').filter(line => line.trim());
  const headers = lines[0].split(',');
  
  const questions = [];
  for (let i = 1; i < lines.length; i++) {
    const values = [];
    let current = '';
    let inQuotes = false;
    
    for (let j = 0; j < lines[i].length; j++) {
      const char = lines[i][j];
      if (char === '"') {
        inQuotes = !inQuotes;
      } else if (char === ',' && !inQuotes) {
        values.push(current.trim());
        current = '';
      } else {
        current += char;
      }
    }
    values.push(current.trim());
    
    if (values.length >= headers.length) {
      const question = {};
      headers.forEach((header, idx) => {
        question[header] = values[idx] || '';
      });
      questions.push(question);
    }
  }
  
  return questions;
}

// Generate skill mappings based on question content
function generateSkillMappings(question) {
  const mappings = {};
  const questionLower = question.question.toLowerCase();
  const tags = (question.tags || '').toLowerCase();
  
  // Map questions to skills based on keywords
  if (questionLower.includes('ui') || questionLower.includes('interface') || questionLower.includes('visual') || questionLower.includes('design')) {
    mappings['UI/UX Design'] = 0.8;
    mappings['Frontend Development'] = 0.5;
  }
  
  if (questionLower.includes('workflow') || questionLower.includes('automate') || questionLower.includes('prototype')) {
    mappings['Problem Solving'] = 0.7;
    mappings['Backend Development'] = 0.4;
  }
  
  if (questionLower.includes('product') || questionLower.includes('feature')) {
    mappings['Product Management'] = 0.6;
    mappings['Problem Solving'] = 0.4;
  }
  
  if (questionLower.includes('write') || questionLower.includes('story') || questionLower.includes('blog') || questionLower.includes('explanation')) {
    mappings['Technical Writing'] = 0.8;
    mappings['Communication'] = 0.5;
  }
  
  if (questionLower.includes('brainstorm') || questionLower.includes('solution') || questionLower.includes('problem')) {
    mappings['Problem Solving'] = 0.7;
    mappings['Critical Thinking'] = 0.5;
  }
  
  if (questionLower.includes('analogy') || questionLower.includes('concept')) {
    mappings['Communication'] = 0.6;
    mappings['Technical Writing'] = 0.4;
  }
  
  if (questionLower.includes('polish') || questionLower.includes('visualize')) {
    mappings['UI/UX Design'] = 0.7;
    mappings['Frontend Development'] = 0.5;
  }
  
  // Default mappings if none found
  if (Object.keys(mappings).length === 0) {
    mappings['Problem Solving'] = 0.5;
    mappings['Communication'] = 0.3;
  }
  
  return mappings;
}

// Generate questions.json
function generateQuestions() {
  const csvPath = join(__dirname, '../../NextStep_QuestionBank_1702.csv');
  const allQuestions = parseCSV(csvPath);
  
  // Select 30 diverse questions (every Nth question to get variety)
  const selectedQuestions = [];
  const step = Math.floor(allQuestions.length / 30);
  
  for (let i = 0; i < 30 && i * step < allQuestions.length; i++) {
    const q = allQuestions[i * step];
    const skillMappings = generateSkillMappings(q);
    
    selectedQuestions.push({
      id: parseInt(q.id) || i + 1,
      question: q.question,
      category: q.category || 'Personality',
      subcategory: q.subcategory || 'General',
      answer_type: q.answer_type || 'Likert5',
      options: q.options || '',
      skill_mappings: skillMappings
    });
  }
  
  const outputPath = join(__dirname, '../data/questions.json');
  writeFileSync(outputPath, JSON.stringify(selectedQuestions, null, 2));
  console.log(`Generated ${selectedQuestions.length} questions in ${outputPath}`);
}

// Generate roles.json
function generateRoles() {
  const roles = [
    {
      id: 'frontend',
      name: 'Frontend Developer',
      description: 'Builds user-facing web applications using HTML, CSS, and JavaScript',
      required_skills: {
        'Frontend Development': 4,
        'UI/UX Design': 3,
        'JavaScript': 4,
        'React': 3,
        'CSS': 4,
        'HTML': 4
      }
    },
    {
      id: 'backend',
      name: 'Backend Developer',
      description: 'Develops server-side logic and APIs',
      required_skills: {
        'Backend Development': 4,
        'API Design': 4,
        'Database': 3,
        'Problem Solving': 4,
        'System Design': 3
      }
    },
    {
      id: 'fullstack',
      name: 'Full Stack Developer',
      description: 'Works on both frontend and backend systems',
      required_skills: {
        'Frontend Development': 3,
        'Backend Development': 3,
        'JavaScript': 4,
        'Database': 3,
        'Problem Solving': 4
      }
    },
    {
      id: 'qa',
      name: 'QA Engineer',
      description: 'Ensures software quality through testing',
      required_skills: {
        'Testing': 4,
        'Problem Solving': 3,
        'Attention to Detail': 4,
        'Communication': 3
      }
    },
    {
      id: 'devops',
      name: 'DevOps Engineer',
      description: 'Manages infrastructure and deployment pipelines',
      required_skills: {
        'DevOps': 4,
        'System Administration': 3,
        'CI/CD': 4,
        'Cloud': 3,
        'Problem Solving': 3
      }
    },
    {
      id: 'android',
      name: 'Android Developer',
      description: 'Develops mobile applications for Android',
      required_skills: {
        'Mobile Development': 4,
        'Java/Kotlin': 4,
        'Android SDK': 4,
        'UI/UX Design': 3
      }
    },
    {
      id: 'ios',
      name: 'iOS Developer',
      description: 'Develops mobile applications for iOS',
      required_skills: {
        'Mobile Development': 4,
        'Swift': 4,
        'iOS SDK': 4,
        'UI/UX Design': 3
      }
    },
    {
      id: 'architect',
      name: 'Software Architect',
      description: 'Designs system architecture and technical strategy',
      required_skills: {
        'System Design': 5,
        'Architecture': 5,
        'Problem Solving': 4,
        'Technical Leadership': 4
      }
    },
    {
      id: 'tech-writer',
      name: 'Technical Writer',
      description: 'Creates technical documentation and guides',
      required_skills: {
        'Technical Writing': 5,
        'Communication': 4,
        'Documentation': 4
      }
    },
    {
      id: 'ml-engineer',
      name: 'ML Engineer',
      description: 'Builds and deploys machine learning models',
      required_skills: {
        'Machine Learning': 4,
        'Python': 4,
        'Data Science': 3,
        'Statistics': 3
      }
    },
    {
      id: 'ai-engineer',
      name: 'AI Engineer',
      description: 'Develops AI systems and algorithms',
      required_skills: {
        'Artificial Intelligence': 4,
        'Machine Learning': 4,
        'Python': 4,
        'Problem Solving': 4
      }
    },
    {
      id: 'data-scientist',
      name: 'Data Scientist',
      description: 'Analyzes data to extract insights',
      required_skills: {
        'Data Science': 4,
        'Statistics': 4,
        'Python': 4,
        'Data Analysis': 4
      }
    },
    {
      id: 'data-analyst',
      name: 'Data Analyst',
      description: 'Analyzes business data and creates reports',
      required_skills: {
        'Data Analysis': 4,
        'SQL': 3,
        'Statistics': 3,
        'Communication': 3
      }
    },
    {
      id: 'bi-analyst',
      name: 'BI Analyst',
      description: 'Creates business intelligence dashboards and reports',
      required_skills: {
        'Business Intelligence': 4,
        'Data Visualization': 4,
        'SQL': 3,
        'Analytics': 3
      }
    },
    {
      id: 'data-engineer',
      name: 'Data Engineer',
      description: 'Builds data pipelines and infrastructure',
      required_skills: {
        'Data Engineering': 4,
        'Database': 4,
        'ETL': 4,
        'Python': 3
      }
    },
    {
      id: 'mlops',
      name: 'MLOps Engineer',
      description: 'Manages ML model deployment and operations',
      required_skills: {
        'MLOps': 4,
        'Machine Learning': 3,
        'DevOps': 3,
        'Python': 3
      }
    },
    {
      id: 'product-manager',
      name: 'Product Manager',
      description: 'Defines product strategy and roadmap',
      required_skills: {
        'Product Management': 4,
        'Communication': 4,
        'Strategic Thinking': 4,
        'Problem Solving': 3
      }
    },
    {
      id: 'eng-manager',
      name: 'Engineering Manager',
      description: 'Leads engineering teams and projects',
      required_skills: {
        'Technical Leadership': 4,
        'Management': 4,
        'Communication': 4,
        'Problem Solving': 3
      }
    },
    {
      id: 'ux-designer',
      name: 'UX Designer',
      description: 'Designs user experiences and interfaces',
      required_skills: {
        'UI/UX Design': 5,
        'User Research': 4,
        'Prototyping': 4,
        'Communication': 3
      }
    },
    {
      id: 'cybersecurity',
      name: 'Cybersecurity Specialist',
      description: 'Protects systems and data from threats',
      required_skills: {
        'Cybersecurity': 4,
        'Network Security': 4,
        'Problem Solving': 4,
        'Attention to Detail': 4
      }
    },
    {
      id: 'data-engineer-2',
      name: 'Data Engineer (Advanced)',
      description: 'Senior data engineering role',
      required_skills: {
        'Data Engineering': 5,
        'System Design': 4,
        'Big Data': 4,
        'Python': 4
      }
    },
    {
      id: 'fullstack-advanced',
      name: 'Senior Full Stack Developer',
      description: 'Advanced full stack development',
      required_skills: {
        'Frontend Development': 4,
        'Backend Development': 4,
        'System Design': 4,
        'Problem Solving': 4
      }
    }
  ];
  
  const outputPath = join(__dirname, '../data/roles.json');
  writeFileSync(outputPath, JSON.stringify(roles, null, 2));
  console.log(`Generated ${roles.length} roles in ${outputPath}`);
}

// Generate resources.json
function generateResources() {
  const skills = [
    'Frontend Development', 'Backend Development', 'UI/UX Design', 'JavaScript',
    'React', 'CSS', 'HTML', 'API Design', 'Database', 'Problem Solving',
    'System Design', 'Testing', 'DevOps', 'Mobile Development', 'Machine Learning',
    'Data Science', 'Python', 'Technical Writing', 'Communication', 'Product Management'
  ];
  
  const resources = skills.map(skill => ({
    skill: skill,
    resources: [
      {
        title: `${skill} - Beginner Guide`,
        url: `https://example.com/learn/${skill.toLowerCase().replace(/\s+/g, '-')}`,
        type: 'Tutorial',
        level: 'Beginner'
      },
      {
        title: `${skill} - Intermediate Course`,
        url: `https://example.com/course/${skill.toLowerCase().replace(/\s+/g, '-')}`,
        type: 'Course',
        level: 'Intermediate'
      },
      {
        title: `${skill} - Advanced Documentation`,
        url: `https://example.com/docs/${skill.toLowerCase().replace(/\s+/g, '-')}`,
        type: 'Documentation',
        level: 'Advanced'
      }
    ]
  }));
  
  const outputPath = join(__dirname, '../data/resources.json');
  writeFileSync(outputPath, JSON.stringify(resources, null, 2));
  console.log(`Generated resources for ${resources.length} skills in ${outputPath}`);
}

// Main execution
console.log('Generating data files...');
generateQuestions();
generateRoles();
generateResources();
console.log('All data files generated successfully!');
