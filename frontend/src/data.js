export const QUESTIONS = [
  {
    id: 'q1',
    category: 'skills',
    text: 'How comfortable are you writing code from scratch?',
    options: [
      { label: 'Never tried it', value: 0 },
      { label: 'A little - copy-paste territory', value: 1 },
      { label: 'Comfortable with guidance', value: 2 },
      { label: 'Very comfortable, do it daily', value: 3 },
    ],
  },
  {
    id: 'q2',
    category: 'interests',
    text: 'What excites you more?',
    options: [
      { label: 'Making things look beautiful', value: 0 },
      { label: 'Solving logical puzzles', value: 1 },
      { label: 'Wrangling data to find patterns', value: 2 },
      { label: 'Keeping complex systems running', value: 3 },
    ],
  },
  {
    id: 'q3',
    category: 'interests',
    // Adaptive: only relevant to logic/data leaners (q2). showIf may reference earlier questions only.
    showIf: { q: 'q2', in: [1, 2] },
    text: 'When you encounter a dataset, you feel…',
    options: [
      { label: 'Overwhelmed - numbers aren\'t my thing', value: 0 },
      { label: 'Indifferent - just give me the answer', value: 1 },
      { label: 'Interested if it helps my project', value: 2 },
      { label: 'Curious - what story is hiding here?', value: 3 },
    ],
  },
  {
    id: 'q4',
    category: 'workstyle',
    text: 'Your ideal work output is…',
    options: [
      { label: 'A polished product people love using', value: 0 },
      { label: 'Elegant code that solves a real problem', value: 1 },
      { label: 'A report that changes a decision', value: 2 },
      { label: 'A system that never goes down', value: 3 },
    ],
  },
  {
    id: 'q5',
    category: 'workstyle',
    text: 'In a team, you naturally drift toward…',
    options: [
      { label: 'Talking to users and shaping the vision', value: 0 },
      { label: 'Writing the actual code', value: 1 },
      { label: 'Analyzing results and reporting findings', value: 2 },
      { label: 'Building the infrastructure everyone depends on', value: 3 },
    ],
  },
  {
    id: 'q6',
    category: 'personality',
    text: 'How do you prefer to work?',
    options: [
      { label: 'Lots of collaboration and whiteboarding', value: 0 },
      { label: 'Mostly heads-down, deep focus', value: 1 },
      { label: 'Mix of analysis and discussion', value: 2 },
      { label: 'Independent, owning a system end-to-end', value: 3 },
    ],
  },
  {
    id: 'q7',
    category: 'interests',
    text: "You're helping build a new app. Which task sounds most appealing to you?",
    options: [
      { label: 'Deciding how the screens should look and making them easy to use', value: 0 },
      { label: 'Building the parts people click and interact with', value: 1 },
      { label: 'Exploring numbers and information to discover useful patterns', value: 2 },
      { label: 'Setting up the behind-the-scenes systems that keep the app running reliably', value: 3 },
    ],
  },
  {
    id: 'q8',
    category: 'personality',
    text: 'When a project goes sideways, you tend to…',
    options: [
      { label: 'Rally the team and re-scope', value: 0 },
      { label: 'Debug alone until it\'s fixed', value: 1 },
      { label: 'Dig into the data to find the root cause', value: 2 },
      { label: 'Trace the infrastructure logs', value: 3 },
    ],
  },
  {
    id: 'q9',
    category: 'skills',
    // Adaptive: only relevant to design/code leaners (q2). showIf may reference earlier questions only.
    showIf: { q: 'q2', in: [0, 1] },
    text: 'How drawn are you to visual design?',
    options: [
      { label: 'Not at all my area', value: 0 },
      { label: 'Functional is fine - polish is bonus', value: 1 },
      { label: 'I appreciate it but don\'t lead it', value: 2 },
      { label: 'It\'s my happy place', value: 3 },
    ],
  },
  {
    id: 'q10',
    category: 'workstyle',
    text: 'Success to you means…',
    options: [
      { label: 'Users loving the product I helped build', value: 0 },
      { label: 'Shipping clean, maintainable code', value: 1 },
      { label: 'Insights that drive real business impact', value: 2 },
      { label: 'Zero-downtime deploys at 3 AM', value: 3 },
    ],
  },
  {
    id: 'q11',
    category: 'interests',
    text: 'Imagine a busy online store during a big holiday sale. Which job would you enjoy most?',
    options: [
      { label: 'Designing the pages shoppers see and click', value: 0 },
      { label: 'Making checkout and payments work correctly behind the scenes', value: 1 },
      { label: 'Studying what people bought to spot trends', value: 2 },
      { label: 'Keeping the site fast and online while millions visit at once', value: 3 },
    ],
  },
  {
    id: 'q12',
    category: 'workstyle',
    text: 'A friend asks for help with their new app idea. What would you do first?',
    options: [
      { label: 'Talk to the people who would use it and map out what to build', value: 0 },
      { label: 'Sketch how the screens should look and feel', value: 1 },
      { label: 'Start building a rough working version right away', value: 2 },
      { label: 'Look for numbers that prove people actually want it', value: 3 },
    ],
  },
  {
    id: 'q13',
    category: 'personality',
    text: 'You just finished a project you are proud of. Which part do you show off?',
    options: [
      { label: 'How beautiful and smooth it looks', value: 0 },
      { label: 'The clever machinery nobody sees that makes it work', value: 1 },
      { label: 'A surprising discovery I found in the numbers', value: 2 },
      { label: 'That it ran for months without breaking once', value: 3 },
    ],
  },
  {
    id: 'q14',
    category: 'interests',
    // Adaptive: visual-family follow-up (q2 = 0). showIf may reference earlier questions only.
    showIf: { q: 'q2', in: [0] },
    text: 'You get a free weekend to build something fun. What would you make?',
    options: [
      { label: 'A website anyone can open in their browser', value: 0 },
      { label: 'An app for phones that people carry everywhere', value: 1 },
      { label: 'A small video game with characters and levels', value: 2 },
      { label: 'Drawings of how an app should look - someone else can build it', value: 3 },
    ],
  },
  {
    id: 'q15',
    category: 'workstyle',
    // Adaptive: builder-family follow-up (q2 = 1).
    showIf: { q: 'q2', in: [1] },
    text: 'On a team building an app, which role sounds most like you?',
    options: [
      { label: 'Building whole features end to end, from the screen to the data behind it', value: 0 },
      { label: 'Drawing the big blueprint that everyone else builds on', value: 1 },
      { label: 'Trying to break the app on purpose to find problems before users do', value: 2 },
      { label: 'Building the hidden engine that quietly makes everything work', value: 3 },
    ],
  },
  {
    id: 'q16',
    category: 'interests',
    // Adaptive: data-family follow-up (q2 = 2).
    showIf: { q: 'q2', in: [2] },
    text: 'Which of these sounds most satisfying?',
    options: [
      { label: 'Making clear charts and reports that show what happened', value: 0 },
      { label: 'Digging into messy numbers to figure out why something happened', value: 1 },
      { label: 'Teaching the computer to predict what will happen next', value: 2 },
      { label: 'Building an app around a smart AI assistant or chatbot', value: 3 },
    ],
  },
  {
    id: 'q17',
    category: 'workstyle',
    // Adaptive: systems-family follow-up (q2 = 3).
    showIf: { q: 'q2', in: [3] },
    text: 'A website crashes in the middle of the night. Which job would you enjoy most?',
    options: [
      { label: 'Getting it back up fast and making sure it never happens again', value: 0 },
      { label: 'Checking whether someone broke in, and locking the doors better', value: 1 },
      { label: "Redesigning the setup so one failure can't take everything down", value: 2 },
      { label: 'Writing the checks that would have caught the problem before launch', value: 3 },
    ],
  },
  {
    id: 'q18',
    category: 'personality',
    text: "You've finished something you're proud of. Which finishing touch sounds most fun?",
    options: [
      { label: 'Writing a simple guide so anyone can use it', value: 0 },
      { label: "Showing it to people and hearing what they'd improve", value: 1 },
      { label: 'Making it look and feel perfect', value: 2 },
      { label: "Tidying up the inside so it's easy to build on later", value: 3 },
    ],
  },
]

// Adaptive path: the in-order subset of questions to ask given answers so far.
// showIf is declarative ({ q, in }) so the backend can serve it as JSON; it must
// reference only earlier questions (see Questionnaire.jsx). Defaults to the
// bundled QUESTIONS; Questionnaire.jsx passes the backend-fetched set when present.
export const visibleQuestions = (answers, questions = QUESTIONS) =>
  questions.filter((q) => !q.showIf || q.showIf.in.includes(answers[q.showIf.q]))

// Mirror of backend/app/data/careers.json (frontend-facing fields only).
// Keep in exact sync with the backend catalog - see CLAUDE.md.
export const CAREERS = [
  {
    "id": "frontend",
    "title": "Frontend Developer",
    "description": "Craft interactive, accessible web interfaces that delight users. You live at the intersection of design and engineering.",
    "keySkills": [
      "React",
      "CSS",
      "TypeScript",
      "Accessibility",
      "Performance"
    ],
    "icon": "Monitor",
    "roadmapKey": "frontend"
  },
  {
    "id": "backend",
    "title": "Backend Engineer",
    "description": "Build the systems and APIs that power products at scale. You love elegant architecture and rock-solid reliability.",
    "keySkills": [
      "Node.js",
      "Databases",
      "APIs",
      "System Design",
      "Security"
    ],
    "icon": "Server",
    "roadmapKey": "backend"
  },
  {
    "id": "data-science",
    "title": "Data Scientist",
    "description": "Transform raw data into insights that steer strategy. You turn numbers into narratives decision-makers can act on.",
    "keySkills": [
      "Python",
      "Statistics",
      "Machine Learning",
      "SQL",
      "Data Viz"
    ],
    "icon": "BarChart2",
    "roadmapKey": "data-science"
  },
  {
    "id": "devops",
    "title": "DevOps Engineer",
    "description": "Own the platform that every engineer depends on. You thrive on automation, reliability, and making deployment invisible.",
    "keySkills": [
      "Kubernetes",
      "CI/CD",
      "Cloud",
      "Terraform",
      "Monitoring"
    ],
    "icon": "Layers",
    "roadmapKey": "devops"
  },
  {
    "id": "product-manager",
    "title": "Product Manager",
    "description": "Define what gets built and why. You bridge user needs, business goals, and technical reality into a coherent vision.",
    "keySkills": [
      "Strategy",
      "User Research",
      "Roadmapping",
      "Metrics",
      "Storytelling"
    ],
    "icon": "Compass",
    "roadmapKey": "product-manager"
  },
  {
    "id": "ux-designer",
    "title": "UX Designer",
    "description": "Champion the user at every step. You research, prototype, and validate experiences that feel intuitive and beautiful.",
    "keySkills": [
      "Figma",
      "User Research",
      "Prototyping",
      "Design Systems",
      "Usability Testing"
    ],
    "icon": "Pen",
    "roadmapKey": "ux-designer"
  },
  {
    "id": "fullstack",
    "title": "Full-Stack Developer",
    "description": "Own features from pixel to database. You ship complete products and jump between UI, APIs, and data without missing a beat.",
    "keySkills": [
      "JavaScript",
      "React",
      "Node.js",
      "SQL",
      "MongoDB"
    ],
    "icon": "Code2",
    "roadmapKey": "fullstack"
  },
  {
    "id": "mobile",
    "title": "Mobile Developer",
    "description": "Build the apps people carry in their pocket. You obsess over smooth, native-feeling experiences on iOS and Android.",
    "keySkills": [
      "Swift",
      "Kotlin",
      "Flutter",
      "iOS",
      "Android"
    ],
    "icon": "Smartphone",
    "roadmapKey": "mobile"
  },
  {
    "id": "data-analyst",
    "title": "Data Analyst",
    "description": "Turn messy data into dashboards and decisions. You speak SQL fluently and translate numbers into plain business language.",
    "keySkills": [
      "SQL",
      "Excel",
      "Python",
      "Tableau",
      "Power BI"
    ],
    "icon": "PieChart",
    "roadmapKey": "data-analyst"
  },
  {
    "id": "machine-learning",
    "title": "Machine Learning Engineer",
    "description": "Train and ship models that learn from data. You blend solid engineering with deep statistical intuition.",
    "keySkills": [
      "Python",
      "PyTorch",
      "TensorFlow",
      "SQL",
      "MLOps"
    ],
    "icon": "Brain",
    "roadmapKey": "machine-learning"
  },
  {
    "id": "ai-engineer",
    "title": "AI Engineer",
    "description": "Build products on top of large language models. You wire LLMs, embeddings, and APIs into experiences that feel like magic.",
    "keySkills": [
      "Python",
      "LLM",
      "RAG",
      "PyTorch",
      "NLP"
    ],
    "icon": "Sparkles",
    "roadmapKey": "ai-engineer"
  },
  {
    "id": "cyber-security",
    "title": "Cybersecurity Analyst",
    "description": "Defend systems and data from attackers. You think like an adversary, read the logs, and stay calm during incidents.",
    "keySkills": [
      "Penetration Testing",
      "Kali Linux",
      "Nmap",
      "Wireshark",
      "Python"
    ],
    "icon": "ShieldCheck",
    "roadmapKey": "cyber-security"
  },
  {
    "id": "qa-engineer",
    "title": "QA Engineer",
    "description": "Break software before users do. You design test strategies and automation that let teams ship with confidence.",
    "keySkills": [
      "Selenium",
      "Python",
      "JIRA",
      "JUnit",
      "Test Automation"
    ],
    "icon": "Bug",
    "roadmapKey": "qa-engineer"
  },
  {
    "id": "game-dev",
    "title": "Game Developer",
    "description": "Craft interactive worlds that run at 60fps. You combine code, math, and art into experiences players love.",
    "keySkills": [
      "Unity",
      "C#",
      "Unreal Engine",
      "OpenGL",
      "Game Design"
    ],
    "icon": "Gamepad2",
    "roadmapKey": "game-dev"
  },
  {
    "id": "technical-writer",
    "title": "Technical Writer",
    "description": "Make complex technology understandable. You turn APIs and systems into docs developers actually enjoy reading.",
    "keySkills": [
      "Documentation",
      "Markdown",
      "APIs",
      "SEO",
      "Git"
    ],
    "icon": "FileText",
    "roadmapKey": "technical-writer"
  },
  {
    "id": "software-architect",
    "title": "Software Architect",
    "description": "Design systems that survive scale and time. You set technical direction and make the trade-offs others build on.",
    "keySkills": [
      "System Design",
      "Microservices",
      "Kubernetes",
      "AWS",
      "Docker"
    ],
    "icon": "Network",
    "roadmapKey": "software-architect"
  }
]

// Weights: for each career, how much each question answer contributes (0-3).
// Score = sum of (answerValue × weight). q11-q18 are pure discriminators
// (zero weight everywhere); their signal comes from BONUSES only.
const WEIGHTS = {
  "frontend": {
    "q1": 2,
    "q2": 3,
    "q3": 0,
    "q4": 2,
    "q5": 2,
    "q6": 1,
    "q7": 3,
    "q8": 1,
    "q9": 2,
    "q10": 1,
    "q11": 0,
    "q12": 0,
    "q13": 0,
    "q14": 0,
    "q15": 0,
    "q16": 0,
    "q17": 0,
    "q18": 0
  },
  "backend": {
    "q1": 3,
    "q2": 2,
    "q3": 1,
    "q4": 2,
    "q5": 2,
    "q6": 2,
    "q7": 2,
    "q8": 2,
    "q9": 0,
    "q10": 2,
    "q11": 0,
    "q12": 0,
    "q13": 0,
    "q14": 0,
    "q15": 0,
    "q16": 0,
    "q17": 0,
    "q18": 0
  },
  "data-science": {
    "q1": 1,
    "q2": 1,
    "q3": 3,
    "q4": 1,
    "q5": 1,
    "q6": 2,
    "q7": 3,
    "q8": 2,
    "q9": 0,
    "q10": 2,
    "q11": 0,
    "q12": 0,
    "q13": 0,
    "q14": 0,
    "q15": 0,
    "q16": 0,
    "q17": 0,
    "q18": 0
  },
  "devops": {
    "q1": 2,
    "q2": 1,
    "q3": 1,
    "q4": 2,
    "q5": 2,
    "q6": 3,
    "q7": 2,
    "q8": 2,
    "q9": 0,
    "q10": 2,
    "q11": 0,
    "q12": 0,
    "q13": 0,
    "q14": 0,
    "q15": 0,
    "q16": 0,
    "q17": 0,
    "q18": 0
  },
  "product-manager": {
    "q1": 0,
    "q2": 0,
    "q3": 2,
    "q4": 1,
    "q5": 3,
    "q6": 1,
    "q7": 0,
    "q8": 3,
    "q9": 1,
    "q10": 1,
    "q11": 0,
    "q12": 0,
    "q13": 0,
    "q14": 0,
    "q15": 0,
    "q16": 0,
    "q17": 0,
    "q18": 0
  },
  "ux-designer": {
    "q1": 1,
    "q2": 0,
    "q3": 0,
    "q4": 1,
    "q5": 1,
    "q6": 1,
    "q7": 0,
    "q8": 1,
    "q9": 3,
    "q10": 1,
    "q11": 0,
    "q12": 0,
    "q13": 0,
    "q14": 0,
    "q15": 0,
    "q16": 0,
    "q17": 0,
    "q18": 0
  },
  "fullstack": {
    "q1": 3,
    "q2": 2,
    "q3": 1,
    "q4": 2,
    "q5": 2,
    "q6": 2,
    "q7": 3,
    "q8": 2,
    "q9": 1,
    "q10": 2,
    "q11": 0,
    "q12": 0,
    "q13": 0,
    "q14": 0,
    "q15": 0,
    "q16": 0,
    "q17": 0,
    "q18": 0
  },
  "mobile": {
    "q1": 3,
    "q2": 1,
    "q3": 0,
    "q4": 1,
    "q5": 2,
    "q6": 2,
    "q7": 2,
    "q8": 1,
    "q9": 2,
    "q10": 1,
    "q11": 0,
    "q12": 0,
    "q13": 0,
    "q14": 0,
    "q15": 0,
    "q16": 0,
    "q17": 0,
    "q18": 0
  },
  "data-analyst": {
    "q1": 1,
    "q2": 2,
    "q3": 3,
    "q4": 2,
    "q5": 2,
    "q6": 2,
    "q7": 2,
    "q8": 2,
    "q9": 0,
    "q10": 2,
    "q11": 0,
    "q12": 0,
    "q13": 0,
    "q14": 0,
    "q15": 0,
    "q16": 0,
    "q17": 0,
    "q18": 0
  },
  "machine-learning": {
    "q1": 3,
    "q2": 2,
    "q3": 3,
    "q4": 1,
    "q5": 1,
    "q6": 2,
    "q7": 3,
    "q8": 2,
    "q9": 0,
    "q10": 2,
    "q11": 0,
    "q12": 0,
    "q13": 0,
    "q14": 0,
    "q15": 0,
    "q16": 0,
    "q17": 0,
    "q18": 0
  },
  "ai-engineer": {
    "q1": 3,
    "q2": 2,
    "q3": 2,
    "q4": 2,
    "q5": 2,
    "q6": 2,
    "q7": 3,
    "q8": 2,
    "q9": 1,
    "q10": 2,
    "q11": 0,
    "q12": 0,
    "q13": 0,
    "q14": 0,
    "q15": 0,
    "q16": 0,
    "q17": 0,
    "q18": 0
  },
  "cyber-security": {
    "q1": 2,
    "q2": 2,
    "q3": 1,
    "q4": 2,
    "q5": 2,
    "q6": 2,
    "q7": 2,
    "q8": 3,
    "q9": 0,
    "q10": 3,
    "q11": 0,
    "q12": 0,
    "q13": 0,
    "q14": 0,
    "q15": 0,
    "q16": 0,
    "q17": 0,
    "q18": 0
  },
  "qa-engineer": {
    "q1": 2,
    "q2": 1,
    "q3": 1,
    "q4": 2,
    "q5": 1,
    "q6": 2,
    "q7": 1,
    "q8": 2,
    "q9": 1,
    "q10": 2,
    "q11": 0,
    "q12": 0,
    "q13": 0,
    "q14": 0,
    "q15": 0,
    "q16": 0,
    "q17": 0,
    "q18": 0
  },
  "game-dev": {
    "q1": 3,
    "q2": 1,
    "q3": 0,
    "q4": 1,
    "q5": 2,
    "q6": 2,
    "q7": 1,
    "q8": 1,
    "q9": 3,
    "q10": 1,
    "q11": 0,
    "q12": 0,
    "q13": 0,
    "q14": 0,
    "q15": 0,
    "q16": 0,
    "q17": 0,
    "q18": 0
  },
  "technical-writer": {
    "q1": 1,
    "q2": 0,
    "q3": 1,
    "q4": 3,
    "q5": 1,
    "q6": 1,
    "q7": 0,
    "q8": 1,
    "q9": 2,
    "q10": 1,
    "q11": 0,
    "q12": 0,
    "q13": 0,
    "q14": 0,
    "q15": 0,
    "q16": 0,
    "q17": 0,
    "q18": 0
  },
  "software-architect": {
    "q1": 2,
    "q2": 2,
    "q3": 1,
    "q4": 2,
    "q5": 3,
    "q6": 2,
    "q7": 2,
    "q8": 2,
    "q9": 0,
    "q10": 2,
    "q11": 0,
    "q12": 0,
    "q13": 0,
    "q14": 0,
    "q15": 0,
    "q16": 0,
    "q17": 0,
    "q18": 0
  }
}

// Bonus rules: an answerValue on a question boosts a specific career.
// Flattened from each career's bonuses in careers.json.
const BONUSES = [
  {
    "qId": "q2",
    "answerValue": 0,
    "careerId": "frontend",
    "bonus": 1
  },
  {
    "qId": "q9",
    "answerValue": 3,
    "careerId": "frontend",
    "bonus": 1
  },
  {
    "qId": "q11",
    "answerValue": 0,
    "careerId": "frontend",
    "bonus": 2
  },
  {
    "qId": "q12",
    "answerValue": 2,
    "careerId": "frontend",
    "bonus": 1
  },
  {
    "qId": "q13",
    "answerValue": 0,
    "careerId": "frontend",
    "bonus": 2
  },
  {
    "qId": "q7",
    "answerValue": 1,
    "careerId": "frontend",
    "bonus": 1
  },
  {
    "qId": "q10",
    "answerValue": 0,
    "careerId": "frontend",
    "bonus": 2
  },
  {
    "qId": "q14",
    "answerValue": 0,
    "careerId": "frontend",
    "bonus": 3
  },
  {
    "qId": "q18",
    "answerValue": 2,
    "careerId": "frontend",
    "bonus": 1
  },
  {
    "qId": "q4",
    "answerValue": 1,
    "careerId": "backend",
    "bonus": 2
  },
  {
    "qId": "q8",
    "answerValue": 1,
    "careerId": "backend",
    "bonus": 1
  },
  {
    "qId": "q10",
    "answerValue": 1,
    "careerId": "backend",
    "bonus": 2
  },
  {
    "qId": "q11",
    "answerValue": 1,
    "careerId": "backend",
    "bonus": 3
  },
  {
    "qId": "q12",
    "answerValue": 2,
    "careerId": "backend",
    "bonus": 1
  },
  {
    "qId": "q13",
    "answerValue": 1,
    "careerId": "backend",
    "bonus": 3
  },
  {
    "qId": "q13",
    "answerValue": 3,
    "careerId": "backend",
    "bonus": 1
  },
  {
    "qId": "q15",
    "answerValue": 3,
    "careerId": "backend",
    "bonus": 3
  },
  {
    "qId": "q18",
    "answerValue": 3,
    "careerId": "backend",
    "bonus": 1
  },
  {
    "qId": "q11",
    "answerValue": 2,
    "careerId": "data-science",
    "bonus": 2
  },
  {
    "qId": "q12",
    "answerValue": 3,
    "careerId": "data-science",
    "bonus": 2
  },
  {
    "qId": "q13",
    "answerValue": 2,
    "careerId": "data-science",
    "bonus": 2
  },
  {
    "qId": "q6",
    "answerValue": 1,
    "careerId": "data-science",
    "bonus": 1
  },
  {
    "qId": "q7",
    "answerValue": 2,
    "careerId": "data-science",
    "bonus": 2
  },
  {
    "qId": "q16",
    "answerValue": 1,
    "careerId": "data-science",
    "bonus": 3
  },
  {
    "qId": "q2",
    "answerValue": 2,
    "careerId": "data-science",
    "bonus": 2
  },
  {
    "qId": "q2",
    "answerValue": 3,
    "careerId": "devops",
    "bonus": 2
  },
  {
    "qId": "q7",
    "answerValue": 3,
    "careerId": "devops",
    "bonus": 3
  },
  {
    "qId": "q4",
    "answerValue": 3,
    "careerId": "devops",
    "bonus": 2
  },
  {
    "qId": "q8",
    "answerValue": 3,
    "careerId": "devops",
    "bonus": 1
  },
  {
    "qId": "q11",
    "answerValue": 3,
    "careerId": "devops",
    "bonus": 3
  },
  {
    "qId": "q13",
    "answerValue": 3,
    "careerId": "devops",
    "bonus": 2
  },
  {
    "qId": "q17",
    "answerValue": 0,
    "careerId": "devops",
    "bonus": 3
  },
  {
    "qId": "q5",
    "answerValue": 0,
    "careerId": "product-manager",
    "bonus": 3
  },
  {
    "qId": "q8",
    "answerValue": 0,
    "careerId": "product-manager",
    "bonus": 2
  },
  {
    "qId": "q12",
    "answerValue": 0,
    "careerId": "product-manager",
    "bonus": 3
  },
  {
    "qId": "q12",
    "answerValue": 3,
    "careerId": "product-manager",
    "bonus": 1
  },
  {
    "qId": "q4",
    "answerValue": 2,
    "careerId": "product-manager",
    "bonus": 2
  },
  {
    "qId": "q11",
    "answerValue": 2,
    "careerId": "product-manager",
    "bonus": 1
  },
  {
    "qId": "q18",
    "answerValue": 1,
    "careerId": "product-manager",
    "bonus": 3
  },
  {
    "qId": "q2",
    "answerValue": 0,
    "careerId": "ux-designer",
    "bonus": 3
  },
  {
    "qId": "q7",
    "answerValue": 0,
    "careerId": "ux-designer",
    "bonus": 3
  },
  {
    "qId": "q9",
    "answerValue": 3,
    "careerId": "ux-designer",
    "bonus": 2
  },
  {
    "qId": "q11",
    "answerValue": 0,
    "careerId": "ux-designer",
    "bonus": 1
  },
  {
    "qId": "q12",
    "answerValue": 1,
    "careerId": "ux-designer",
    "bonus": 3
  },
  {
    "qId": "q13",
    "answerValue": 0,
    "careerId": "ux-designer",
    "bonus": 2
  },
  {
    "qId": "q14",
    "answerValue": 3,
    "careerId": "ux-designer",
    "bonus": 3
  },
  {
    "qId": "q18",
    "answerValue": 2,
    "careerId": "ux-designer",
    "bonus": 1
  },
  {
    "qId": "q4",
    "answerValue": 0,
    "careerId": "fullstack",
    "bonus": 2
  },
  {
    "qId": "q7",
    "answerValue": 1,
    "careerId": "fullstack",
    "bonus": 2
  },
  {
    "qId": "q11",
    "answerValue": 1,
    "careerId": "fullstack",
    "bonus": 2
  },
  {
    "qId": "q12",
    "answerValue": 2,
    "careerId": "fullstack",
    "bonus": 3
  },
  {
    "qId": "q13",
    "answerValue": 1,
    "careerId": "fullstack",
    "bonus": 2
  },
  {
    "qId": "q15",
    "answerValue": 0,
    "careerId": "fullstack",
    "bonus": 3
  },
  {
    "qId": "q2",
    "answerValue": 0,
    "careerId": "mobile",
    "bonus": 2
  },
  {
    "qId": "q4",
    "answerValue": 0,
    "careerId": "mobile",
    "bonus": 2
  },
  {
    "qId": "q9",
    "answerValue": 2,
    "careerId": "mobile",
    "bonus": 1
  },
  {
    "qId": "q10",
    "answerValue": 0,
    "careerId": "mobile",
    "bonus": 1
  },
  {
    "qId": "q11",
    "answerValue": 0,
    "careerId": "mobile",
    "bonus": 1
  },
  {
    "qId": "q12",
    "answerValue": 2,
    "careerId": "mobile",
    "bonus": 1
  },
  {
    "qId": "q13",
    "answerValue": 0,
    "careerId": "mobile",
    "bonus": 1
  },
  {
    "qId": "q14",
    "answerValue": 1,
    "careerId": "mobile",
    "bonus": 3
  },
  {
    "qId": "q1",
    "answerValue": 1,
    "careerId": "data-analyst",
    "bonus": 2
  },
  {
    "qId": "q4",
    "answerValue": 2,
    "careerId": "data-analyst",
    "bonus": 2
  },
  {
    "qId": "q6",
    "answerValue": 2,
    "careerId": "data-analyst",
    "bonus": 2
  },
  {
    "qId": "q11",
    "answerValue": 2,
    "careerId": "data-analyst",
    "bonus": 2
  },
  {
    "qId": "q12",
    "answerValue": 3,
    "careerId": "data-analyst",
    "bonus": 2
  },
  {
    "qId": "q13",
    "answerValue": 2,
    "careerId": "data-analyst",
    "bonus": 2
  },
  {
    "qId": "q16",
    "answerValue": 0,
    "careerId": "data-analyst",
    "bonus": 3
  },
  {
    "qId": "q1",
    "answerValue": 3,
    "careerId": "machine-learning",
    "bonus": 1
  },
  {
    "qId": "q3",
    "answerValue": 3,
    "careerId": "machine-learning",
    "bonus": 2
  },
  {
    "qId": "q7",
    "answerValue": 2,
    "careerId": "machine-learning",
    "bonus": 2
  },
  {
    "qId": "q11",
    "answerValue": 2,
    "careerId": "machine-learning",
    "bonus": 1
  },
  {
    "qId": "q12",
    "answerValue": 2,
    "careerId": "machine-learning",
    "bonus": 1
  },
  {
    "qId": "q13",
    "answerValue": 1,
    "careerId": "machine-learning",
    "bonus": 2
  },
  {
    "qId": "q16",
    "answerValue": 2,
    "careerId": "machine-learning",
    "bonus": 3
  },
  {
    "qId": "q3",
    "answerValue": 2,
    "careerId": "ai-engineer",
    "bonus": 2
  },
  {
    "qId": "q4",
    "answerValue": 0,
    "careerId": "ai-engineer",
    "bonus": 1
  },
  {
    "qId": "q7",
    "answerValue": 2,
    "careerId": "ai-engineer",
    "bonus": 1
  },
  {
    "qId": "q11",
    "answerValue": 2,
    "careerId": "ai-engineer",
    "bonus": 1
  },
  {
    "qId": "q12",
    "answerValue": 2,
    "careerId": "ai-engineer",
    "bonus": 2
  },
  {
    "qId": "q13",
    "answerValue": 1,
    "careerId": "ai-engineer",
    "bonus": 1
  },
  {
    "qId": "q16",
    "answerValue": 3,
    "careerId": "ai-engineer",
    "bonus": 3
  },
  {
    "qId": "q2",
    "answerValue": 3,
    "careerId": "cyber-security",
    "bonus": 1
  },
  {
    "qId": "q6",
    "answerValue": 1,
    "careerId": "cyber-security",
    "bonus": 2
  },
  {
    "qId": "q8",
    "answerValue": 3,
    "careerId": "cyber-security",
    "bonus": 3
  },
  {
    "qId": "q11",
    "answerValue": 3,
    "careerId": "cyber-security",
    "bonus": 2
  },
  {
    "qId": "q13",
    "answerValue": 3,
    "careerId": "cyber-security",
    "bonus": 2
  },
  {
    "qId": "q17",
    "answerValue": 1,
    "careerId": "cyber-security",
    "bonus": 3
  },
  {
    "qId": "q4",
    "answerValue": 3,
    "careerId": "qa-engineer",
    "bonus": 3
  },
  {
    "qId": "q6",
    "answerValue": 1,
    "careerId": "qa-engineer",
    "bonus": 1
  },
  {
    "qId": "q8",
    "answerValue": 1,
    "careerId": "qa-engineer",
    "bonus": 2
  },
  {
    "qId": "q11",
    "answerValue": 1,
    "careerId": "qa-engineer",
    "bonus": 2
  },
  {
    "qId": "q12",
    "answerValue": 3,
    "careerId": "qa-engineer",
    "bonus": 1
  },
  {
    "qId": "q13",
    "answerValue": 3,
    "careerId": "qa-engineer",
    "bonus": 2
  },
  {
    "qId": "q15",
    "answerValue": 2,
    "careerId": "qa-engineer",
    "bonus": 3
  },
  {
    "qId": "q17",
    "answerValue": 3,
    "careerId": "qa-engineer",
    "bonus": 2
  },
  {
    "qId": "q2",
    "answerValue": 1,
    "careerId": "game-dev",
    "bonus": 1
  },
  {
    "qId": "q4",
    "answerValue": 0,
    "careerId": "game-dev",
    "bonus": 2
  },
  {
    "qId": "q6",
    "answerValue": 1,
    "careerId": "game-dev",
    "bonus": 2
  },
  {
    "qId": "q9",
    "answerValue": 3,
    "careerId": "game-dev",
    "bonus": 2
  },
  {
    "qId": "q12",
    "answerValue": 2,
    "careerId": "game-dev",
    "bonus": 1
  },
  {
    "qId": "q13",
    "answerValue": 1,
    "careerId": "game-dev",
    "bonus": 2
  },
  {
    "qId": "q14",
    "answerValue": 2,
    "careerId": "game-dev",
    "bonus": 3
  },
  {
    "qId": "q1",
    "answerValue": 1,
    "careerId": "technical-writer",
    "bonus": 2
  },
  {
    "qId": "q4",
    "answerValue": 2,
    "careerId": "technical-writer",
    "bonus": 3
  },
  {
    "qId": "q9",
    "answerValue": 2,
    "careerId": "technical-writer",
    "bonus": 2
  },
  {
    "qId": "q12",
    "answerValue": 0,
    "careerId": "technical-writer",
    "bonus": 2
  },
  {
    "qId": "q18",
    "answerValue": 0,
    "careerId": "technical-writer",
    "bonus": 3
  },
  {
    "qId": "q4",
    "answerValue": 1,
    "careerId": "software-architect",
    "bonus": 1
  },
  {
    "qId": "q5",
    "answerValue": 3,
    "careerId": "software-architect",
    "bonus": 2
  },
  {
    "qId": "q6",
    "answerValue": 3,
    "careerId": "software-architect",
    "bonus": 3
  },
  {
    "qId": "q11",
    "answerValue": 3,
    "careerId": "software-architect",
    "bonus": 2
  },
  {
    "qId": "q12",
    "answerValue": 0,
    "careerId": "software-architect",
    "bonus": 1
  },
  {
    "qId": "q13",
    "answerValue": 1,
    "careerId": "software-architect",
    "bonus": 2
  },
  {
    "qId": "q15",
    "answerValue": 1,
    "careerId": "software-architect",
    "bonus": 3
  },
  {
    "qId": "q17",
    "answerValue": 2,
    "careerId": "software-architect",
    "bonus": 2
  },
  {
    "qId": "q18",
    "answerValue": 3,
    "careerId": "software-architect",
    "bonus": 1
  }
]

export function computeResults(answers) {
  const scored = CAREERS.map((career) => {
    const weights = WEIGHTS[career.id]
    let score = 0

    QUESTIONS.forEach((q) => {
      const answerVal = answers[q.id] ?? 0
      score += answerVal * (weights[q.id] ?? 0)
    })

    // Apply bonuses
    BONUSES.forEach(({ qId, answerValue, careerId, bonus }) => {
      if (careerId === career.id && answers[qId] === answerValue) {
        score += bonus * 3
      }
    })

    return { ...career, rawScore: score }
  })

  const maxScore = Math.max(...scored.map((c) => c.rawScore), 1)

  const withPercent = scored
    .map((c) => ({
      ...c,
      matchPercent: Math.round((c.rawScore / maxScore) * 100),
    }))
    .sort((a, b) => b.rawScore - a.rawScore)
    .slice(0, 3)

  // Ensure top career is always 95-100%
  const topScore = withPercent[0].rawScore
  return withPercent.map((c) => ({
    ...c,
    matchPercent: Math.min(100, Math.round((c.rawScore / topScore) * 97) + (c.rawScore === topScore ? 3 : 0)),
  }))
}

// Mirror of backend/app/data/roadmaps.json - offline fallback for Roadmap.jsx.
export const ROADMAPS = {
  "frontend": {
    "sections": [
      {
        "id": "web-foundations",
        "label": "Web Foundations",
        "nodes": [
          {
            "id": "how-the-web-works",
            "label": "How the Web Works",
            "level": "beginner",
            "type": "required",
            "description": "HTTP, DNS, domains, and hosting - what actually happens when you type a URL and hit enter.",
            "resources": [
              {
                "title": "MDN - How the Web works",
                "url": "https://developer.mozilla.org/en-US/docs/Learn/Getting_started_with_the_web/How_the_Web_works"
              },
              {
                "title": "roadmap.sh - Frontend",
                "url": "https://roadmap.sh/frontend"
              }
            ]
          },
          {
            "id": "html",
            "label": "HTML",
            "level": "beginner",
            "type": "required",
            "description": "Semantic HTML5: document structure, forms, media, and markup that search engines and screen readers understand.",
            "resources": [
              {
                "title": "MDN Web Docs - HTML",
                "url": "https://developer.mozilla.org/en-US/docs/Web/HTML"
              }
            ]
          },
          {
            "id": "css",
            "label": "CSS",
            "level": "beginner",
            "type": "required",
            "description": "Modern CSS: the box model, flexbox, grid, custom properties, and responsive layouts that work on any screen.",
            "resources": [
              {
                "title": "MDN Web Docs - CSS",
                "url": "https://developer.mozilla.org/en-US/docs/Web/CSS"
              },
              {
                "title": "web.dev - Learn CSS",
                "url": "https://web.dev/learn/css"
              }
            ]
          },
          {
            "id": "javascript",
            "label": "JavaScript",
            "level": "beginner",
            "type": "required",
            "description": "The core language: variables, functions, closures, the DOM, fetch, and async/await.",
            "resources": [
              {
                "title": "javascript.info",
                "url": "https://javascript.info"
              }
            ]
          },
          {
            "id": "accessibility",
            "label": "Accessibility",
            "level": "beginner",
            "type": "required",
            "description": "WCAG basics, semantic markup, keyboard navigation, and ARIA - building interfaces everyone can use.",
            "resources": [
              {
                "title": "MDN - Accessibility",
                "url": "https://developer.mozilla.org/en-US/docs/Web/Accessibility"
              }
            ]
          }
        ]
      },
      {
        "id": "tooling",
        "label": "Tooling & Workflow",
        "nodes": [
          {
            "id": "git-github",
            "label": "Git & GitHub",
            "level": "beginner",
            "type": "required",
            "description": "Version control: commits, branches, merges, pull requests, and collaborating without losing work.",
            "resources": [
              {
                "title": "Pro Git (free book)",
                "url": "https://git-scm.com/book"
              }
            ]
          },
          {
            "id": "package-managers",
            "label": "Package Managers",
            "level": "beginner",
            "type": "required",
            "description": "npm and package.json: installing dependencies, scripts, semver, and lockfiles.",
            "resources": [
              {
                "title": "npm Docs",
                "url": "https://docs.npmjs.com"
              }
            ]
          },
          {
            "id": "build-tools",
            "label": "Build Tools",
            "level": "intermediate",
            "type": "required",
            "description": "Vite and the modern toolchain: dev servers, bundling, transpilation, and environment variables.",
            "resources": [
              {
                "title": "Vite Guide",
                "url": "https://vitejs.dev/guide/"
              }
            ]
          },
          {
            "id": "linters-formatters",
            "label": "Linters & Formatters",
            "level": "intermediate",
            "type": "good-to-know",
            "description": "ESLint and Prettier: catching bugs and style drift automatically before code review.",
            "resources": [
              {
                "title": "ESLint Docs",
                "url": "https://eslint.org/docs/latest/"
              }
            ]
          }
        ]
      },
      {
        "id": "frameworks",
        "label": "Frameworks & Ecosystem",
        "nodes": [
          {
            "id": "react",
            "label": "React",
            "level": "intermediate",
            "type": "required",
            "description": "The component model, JSX, hooks (useState, useEffect, useContext), and thinking in unidirectional data flow.",
            "resources": [
              {
                "title": "React Docs",
                "url": "https://react.dev/learn"
              }
            ]
          },
          {
            "id": "typescript",
            "label": "TypeScript",
            "level": "intermediate",
            "type": "required",
            "description": "Static typing for scalable codebases: types, interfaces, generics, and narrowing.",
            "resources": [
              {
                "title": "TypeScript Handbook",
                "url": "https://www.typescriptlang.org/docs/"
              }
            ]
          },
          {
            "id": "css-architecture",
            "label": "CSS Architecture",
            "level": "intermediate",
            "type": "good-to-know",
            "description": "Scaling styles with utility-first CSS (Tailwind), CSS Modules, and design tokens.",
            "resources": [
              {
                "title": "Tailwind CSS Docs",
                "url": "https://tailwindcss.com/docs"
              }
            ]
          },
          {
            "id": "state-management",
            "label": "State Management",
            "level": "intermediate",
            "type": "required",
            "description": "Local vs server state: Context, Redux Toolkit, and data-fetching libraries like TanStack Query.",
            "resources": [
              {
                "title": "Redux Toolkit",
                "url": "https://redux-toolkit.js.org"
              },
              {
                "title": "TanStack Query",
                "url": "https://tanstack.com/query/latest"
              }
            ]
          }
        ]
      },
      {
        "id": "quality",
        "label": "Quality & Security",
        "nodes": [
          {
            "id": "testing",
            "label": "Testing",
            "level": "intermediate",
            "type": "required",
            "description": "Unit and component tests with Vitest and React Testing Library - testing behavior, not implementation.",
            "resources": [
              {
                "title": "Vitest Docs",
                "url": "https://vitest.dev"
              },
              {
                "title": "Testing Library",
                "url": "https://testing-library.com/docs/"
              }
            ]
          },
          {
            "id": "e2e-testing",
            "label": "End-to-End Testing",
            "level": "intermediate",
            "type": "good-to-know",
            "description": "Browser automation with Playwright or Cypress to verify whole user flows.",
            "resources": [
              {
                "title": "Playwright Docs",
                "url": "https://playwright.dev/docs/intro"
              }
            ]
          },
          {
            "id": "web-security",
            "label": "Web Security Basics",
            "level": "intermediate",
            "type": "required",
            "description": "XSS, CSRF, CORS, and Content Security Policy - the attacks every frontend must defend against.",
            "resources": [
              {
                "title": "OWASP Top 10",
                "url": "https://owasp.org/www-project-top-ten/"
              }
            ]
          },
          {
            "id": "performance",
            "label": "Performance",
            "level": "advanced",
            "type": "required",
            "description": "Core Web Vitals, code splitting, lazy loading, image optimization, and bundle analysis.",
            "resources": [
              {
                "title": "web.dev - Performance",
                "url": "https://web.dev/performance/"
              }
            ]
          }
        ]
      },
      {
        "id": "advanced",
        "label": "Advanced Frontend",
        "nodes": [
          {
            "id": "ssr-frameworks",
            "label": "SSR & Next.js",
            "level": "advanced",
            "type": "good-to-know",
            "description": "Server-side rendering, static generation, and full-stack React with Next.js.",
            "resources": [
              {
                "title": "Next.js Docs",
                "url": "https://nextjs.org/docs"
              }
            ]
          },
          {
            "id": "design-systems",
            "label": "Design Systems",
            "level": "advanced",
            "type": "good-to-know",
            "description": "Reusable component libraries, Storybook, and keeping product UI consistent at scale.",
            "resources": [
              {
                "title": "Storybook Docs",
                "url": "https://storybook.js.org/docs"
              }
            ]
          },
          {
            "id": "pwa",
            "label": "PWAs & Offline",
            "level": "advanced",
            "type": "optional",
            "description": "Service workers, caching strategies, and installable progressive web apps.",
            "resources": [
              {
                "title": "web.dev - Learn PWA",
                "url": "https://web.dev/learn/pwa"
              }
            ]
          },
          {
            "id": "graphql",
            "label": "GraphQL",
            "level": "advanced",
            "type": "optional",
            "description": "Query-language APIs: schemas, queries, mutations, and client caching.",
            "resources": [
              {
                "title": "GraphQL - Learn",
                "url": "https://graphql.org/learn/"
              }
            ]
          }
        ]
      }
    ]
  },
  "backend": {
    "sections": [
      {
        "id": "foundations",
        "label": "Foundations",
        "nodes": [
          {
            "id": "nodejs",
            "label": "Node.js & JavaScript",
            "level": "beginner",
            "type": "required",
            "description": "Pick a backend language and go deep - Node.js with Express or Fastify is a strong default for web APIs.",
            "resources": [
              {
                "title": "Node.js - Learn",
                "url": "https://nodejs.org/en/learn"
              },
              {
                "title": "roadmap.sh - Backend",
                "url": "https://roadmap.sh/backend"
              }
            ]
          },
          {
            "id": "how-internet-works",
            "label": "How the Internet Works",
            "level": "beginner",
            "type": "required",
            "description": "HTTP request/response, DNS, TLS, and what a web server actually does.",
            "resources": [
              {
                "title": "MDN - HTTP",
                "url": "https://developer.mozilla.org/en-US/docs/Web/HTTP"
              }
            ]
          },
          {
            "id": "git",
            "label": "Git & Version Control",
            "level": "beginner",
            "type": "required",
            "description": "Branching, merging, code review flow, and collaborating on a shared codebase.",
            "resources": [
              {
                "title": "Pro Git (free book)",
                "url": "https://git-scm.com/book"
              }
            ]
          },
          {
            "id": "linux-terminal",
            "label": "Linux & Terminal",
            "level": "beginner",
            "type": "required",
            "description": "Shell basics, processes, permissions, and SSH - backends live on Linux servers.",
            "resources": [
              {
                "title": "Linux Journey",
                "url": "https://linuxjourney.com"
              }
            ]
          }
        ]
      },
      {
        "id": "databases",
        "label": "Databases",
        "nodes": [
          {
            "id": "relational-databases",
            "label": "Relational Databases",
            "level": "intermediate",
            "type": "required",
            "description": "PostgreSQL: schema design, normalization, joins, transactions, and constraints.",
            "resources": [
              {
                "title": "PostgreSQL Docs",
                "url": "https://www.postgresql.org/docs/"
              }
            ]
          },
          {
            "id": "sql",
            "label": "SQL",
            "level": "intermediate",
            "type": "required",
            "description": "Fluent querying: SELECT, JOIN, GROUP BY, subqueries, and reading query plans for indexing.",
            "resources": [
              {
                "title": "SQLBolt - Interactive SQL",
                "url": "https://sqlbolt.com"
              }
            ]
          },
          {
            "id": "nosql",
            "label": "NoSQL Databases",
            "level": "intermediate",
            "type": "good-to-know",
            "description": "Document and key-value stores (MongoDB, Redis): when they fit and what you trade away.",
            "resources": [
              {
                "title": "MongoDB Docs",
                "url": "https://www.mongodb.com/docs/"
              }
            ]
          },
          {
            "id": "orms",
            "label": "ORMs & Query Builders",
            "level": "intermediate",
            "type": "good-to-know",
            "description": "Prisma, Drizzle, or SQLAlchemy: productivity layers over SQL - and when to drop to raw queries.",
            "resources": [
              {
                "title": "Prisma Docs",
                "url": "https://www.prisma.io/docs"
              }
            ]
          }
        ]
      },
      {
        "id": "apis",
        "label": "APIs & Services",
        "nodes": [
          {
            "id": "rest-apis",
            "label": "REST APIs",
            "level": "intermediate",
            "type": "required",
            "description": "Resource modeling, HTTP methods and status codes, pagination, versioning, and error contracts.",
            "resources": [
              {
                "title": "REST API Tutorial",
                "url": "https://restfulapi.net"
              }
            ]
          },
          {
            "id": "authentication",
            "label": "Authentication & Security",
            "level": "intermediate",
            "type": "required",
            "description": "Sessions, JWTs, OAuth 2.0, and password hashing - who is calling and what may they do.",
            "resources": [
              {
                "title": "JWT Introduction",
                "url": "https://jwt.io/introduction"
              },
              {
                "title": "OAuth 2.0",
                "url": "https://oauth.net/2/"
              }
            ]
          },
          {
            "id": "websockets",
            "label": "Real-Time & WebSockets",
            "level": "intermediate",
            "type": "good-to-know",
            "description": "Pushing data to clients: WebSockets, server-sent events, and pub/sub patterns.",
            "resources": [
              {
                "title": "MDN - WebSockets API",
                "url": "https://developer.mozilla.org/en-US/docs/Web/API/WebSockets_API"
              }
            ]
          },
          {
            "id": "graphql-apis",
            "label": "GraphQL APIs",
            "level": "advanced",
            "type": "optional",
            "description": "Schema-first APIs with resolvers, dataloaders, and the N+1 problem.",
            "resources": [
              {
                "title": "GraphQL - Learn",
                "url": "https://graphql.org/learn/"
              }
            ]
          }
        ]
      },
      {
        "id": "reliability",
        "label": "Quality & Reliability",
        "nodes": [
          {
            "id": "testing",
            "label": "Testing",
            "level": "intermediate",
            "type": "required",
            "description": "Unit and integration tests, test doubles, and testing the API surface your clients depend on.",
            "resources": [
              {
                "title": "pytest Docs",
                "url": "https://docs.pytest.org"
              }
            ]
          },
          {
            "id": "caching",
            "label": "Caching",
            "level": "advanced",
            "type": "required",
            "description": "Redis, HTTP caching, and CDNs - plus cache invalidation, the famously hard part.",
            "resources": [
              {
                "title": "Redis Docs",
                "url": "https://redis.io/docs/"
              }
            ]
          },
          {
            "id": "web-security",
            "label": "Web Security",
            "level": "advanced",
            "type": "required",
            "description": "OWASP Top 10: injection, broken auth, SSRF - plus rate limiting and secrets handling.",
            "resources": [
              {
                "title": "OWASP Top 10",
                "url": "https://owasp.org/www-project-top-ten/"
              }
            ]
          },
          {
            "id": "observability",
            "label": "Logging & Monitoring",
            "level": "advanced",
            "type": "good-to-know",
            "description": "Structured logs, metrics, and traces so you can debug production without guessing.",
            "resources": [
              {
                "title": "The Twelve-Factor App - Logs",
                "url": "https://12factor.net/logs"
              }
            ]
          }
        ]
      },
      {
        "id": "scale",
        "label": "Architecture & Scale",
        "nodes": [
          {
            "id": "system-design",
            "label": "System Design",
            "level": "advanced",
            "type": "required",
            "description": "Load balancing, replication, sharding, and CAP trade-offs - designing beyond one server.",
            "resources": [
              {
                "title": "System Design Primer",
                "url": "https://github.com/donnemartin/system-design-primer"
              }
            ]
          },
          {
            "id": "message-queues",
            "label": "Message Queues",
            "level": "advanced",
            "type": "good-to-know",
            "description": "Async work with RabbitMQ or Kafka: decoupling services and smoothing traffic spikes.",
            "resources": [
              {
                "title": "Apache Kafka Docs",
                "url": "https://kafka.apache.org/documentation/"
              }
            ]
          },
          {
            "id": "containers",
            "label": "Docker & Containers",
            "level": "advanced",
            "type": "required",
            "description": "Containerizing services for reproducible builds and deploys.",
            "resources": [
              {
                "title": "Docker Docs",
                "url": "https://docs.docker.com"
              }
            ]
          },
          {
            "id": "ci-cd",
            "label": "CI/CD",
            "level": "advanced",
            "type": "good-to-know",
            "description": "Automated test-and-deploy pipelines with GitHub Actions.",
            "resources": [
              {
                "title": "GitHub Actions Docs",
                "url": "https://docs.github.com/actions"
              }
            ]
          },
          {
            "id": "microservices",
            "label": "Microservices",
            "level": "advanced",
            "type": "optional",
            "description": "Service boundaries, inter-service communication, and when a monolith is honestly better.",
            "resources": [
              {
                "title": "microservices.io",
                "url": "https://microservices.io"
              }
            ]
          }
        ]
      }
    ]
  },
  "data-science": {
    "sections": [
      {
        "id": "foundations",
        "label": "Math & Programming",
        "nodes": [
          {
            "id": "statistics-probability",
            "label": "Statistics & Probability",
            "level": "beginner",
            "type": "required",
            "description": "Distributions, expectation, sampling, and hypothesis testing - the language of uncertainty.",
            "resources": [
              {
                "title": "Khan Academy - Statistics & Probability",
                "url": "https://www.khanacademy.org/math/statistics-probability"
              },
              {
                "title": "roadmap.sh - AI & Data Scientist",
                "url": "https://roadmap.sh/ai-data-scientist"
              }
            ]
          },
          {
            "id": "linear-algebra",
            "label": "Linear Algebra",
            "level": "beginner",
            "type": "required",
            "description": "Vectors, matrices, and transformations - what models are actually made of.",
            "resources": [
              {
                "title": "3Blue1Brown - Essence of Linear Algebra",
                "url": "https://www.3blue1brown.com/topics/linear-algebra"
              }
            ]
          },
          {
            "id": "python",
            "label": "Python",
            "level": "beginner",
            "type": "required",
            "description": "Fluent Python: functions, comprehensions, environments, and writing code someone else can run.",
            "resources": [
              {
                "title": "Python Docs - Tutorial",
                "url": "https://docs.python.org/3/tutorial/"
              }
            ]
          }
        ]
      },
      {
        "id": "data-wrangling",
        "label": "Data Wrangling",
        "nodes": [
          {
            "id": "pandas-numpy",
            "label": "Pandas & NumPy",
            "level": "intermediate",
            "type": "required",
            "description": "Arrays, DataFrames, joins, and vectorized thinking - the daily toolkit.",
            "resources": [
              {
                "title": "pandas Docs",
                "url": "https://pandas.pydata.org/docs/"
              },
              {
                "title": "NumPy - Learn",
                "url": "https://numpy.org/learn/"
              }
            ]
          },
          {
            "id": "sql",
            "label": "SQL",
            "level": "intermediate",
            "type": "required",
            "description": "Extracting your own data: joins, aggregations, and window functions against warehouses.",
            "resources": [
              {
                "title": "Mode SQL Tutorial",
                "url": "https://mode.com/sql-tutorial"
              }
            ]
          },
          {
            "id": "eda",
            "label": "Exploratory Data Analysis",
            "level": "intermediate",
            "type": "required",
            "description": "Profiling distributions, spotting outliers and leakage, and forming hypotheses before modeling.",
            "resources": [
              {
                "title": "pandas - 10 Minutes to pandas",
                "url": "https://pandas.pydata.org/docs/user_guide/10min.html"
              }
            ]
          },
          {
            "id": "data-visualization",
            "label": "Data Visualization",
            "level": "intermediate",
            "type": "required",
            "description": "Matplotlib and Seaborn for exploration; clear charts for everyone else.",
            "resources": [
              {
                "title": "Matplotlib Docs",
                "url": "https://matplotlib.org/stable/"
              },
              {
                "title": "Seaborn",
                "url": "https://seaborn.pydata.org"
              }
            ]
          }
        ]
      },
      {
        "id": "machine-learning",
        "label": "Machine Learning",
        "nodes": [
          {
            "id": "ml-fundamentals",
            "label": "ML Fundamentals",
            "level": "intermediate",
            "type": "required",
            "description": "Supervised vs unsupervised, train/test splits, overfitting, and the bias-variance trade-off.",
            "resources": [
              {
                "title": "scikit-learn - User Guide",
                "url": "https://scikit-learn.org/stable/user_guide.html"
              }
            ]
          },
          {
            "id": "classification-regression",
            "label": "Classification & Regression",
            "level": "intermediate",
            "type": "required",
            "description": "Linear/logistic regression, trees, and gradient boosting - the workhorses of tabular data.",
            "resources": [
              {
                "title": "scikit-learn - Supervised Learning",
                "url": "https://scikit-learn.org/stable/supervised_learning.html"
              }
            ]
          },
          {
            "id": "clustering",
            "label": "Clustering & Dimensionality",
            "level": "intermediate",
            "type": "good-to-know",
            "description": "k-means, hierarchical clustering, and PCA for structure-finding and compression.",
            "resources": [
              {
                "title": "scikit-learn - Unsupervised Learning",
                "url": "https://scikit-learn.org/stable/unsupervised_learning.html"
              }
            ]
          },
          {
            "id": "model-evaluation",
            "label": "Model Evaluation",
            "level": "intermediate",
            "type": "required",
            "description": "Precision/recall, ROC-AUC, cross-validation, and calibration - proving a model is actually good.",
            "resources": [
              {
                "title": "scikit-learn - Model Evaluation",
                "url": "https://scikit-learn.org/stable/modules/model_evaluation.html"
              }
            ]
          }
        ]
      },
      {
        "id": "deep-learning",
        "label": "Deep Learning & Modern ML",
        "nodes": [
          {
            "id": "neural-networks",
            "label": "Neural Networks",
            "level": "advanced",
            "type": "required",
            "description": "Perceptrons to backprop: layers, activations, loss functions, and optimizers.",
            "resources": [
              {
                "title": "DeepLearning.AI",
                "url": "https://www.deeplearning.ai"
              }
            ]
          },
          {
            "id": "pytorch-tensorflow",
            "label": "PyTorch / TensorFlow",
            "level": "advanced",
            "type": "good-to-know",
            "description": "Building and training networks in a modern framework - tensors, autograd, and GPUs.",
            "resources": [
              {
                "title": "PyTorch Tutorials",
                "url": "https://pytorch.org/tutorials/"
              }
            ]
          },
          {
            "id": "nlp",
            "label": "NLP & Embeddings",
            "level": "advanced",
            "type": "good-to-know",
            "description": "Text as data: tokenization, embeddings, and transformer models at a practical level.",
            "resources": [
              {
                "title": "Hugging Face - Learn",
                "url": "https://huggingface.co/learn"
              }
            ]
          },
          {
            "id": "genai-llms",
            "label": "Generative AI & LLMs",
            "level": "advanced",
            "type": "optional",
            "description": "Where LLMs fit in a data scientist's toolbox: prompting, evaluation, and augmenting analyses.",
            "resources": [
              {
                "title": "OpenAI - Docs",
                "url": "https://platform.openai.com/docs"
              }
            ]
          }
        ]
      },
      {
        "id": "practice",
        "label": "Production & Practice",
        "nodes": [
          {
            "id": "experiment-design",
            "label": "A/B Testing & Experiments",
            "level": "advanced",
            "type": "good-to-know",
            "description": "Designing experiments that isolate cause: power, randomization, and common pitfalls.",
            "resources": [
              {
                "title": "Khan Academy - Study Design",
                "url": "https://www.khanacademy.org/math/statistics-probability/designing-studies"
              }
            ]
          },
          {
            "id": "mlops-basics",
            "label": "MLOps Basics",
            "level": "advanced",
            "type": "good-to-know",
            "description": "Versioning data and models, deployment, and monitoring drift once a model ships.",
            "resources": [
              {
                "title": "MLflow",
                "url": "https://mlflow.org"
              }
            ]
          },
          {
            "id": "storytelling",
            "label": "Storytelling with Data",
            "level": "advanced",
            "type": "required",
            "description": "Translating models into decisions: narratives, caveats, and recommendations stakeholders trust.",
            "resources": [
              {
                "title": "Storytelling with Data",
                "url": "https://www.storytellingwithdata.com"
              }
            ]
          },
          {
            "id": "portfolio-kaggle",
            "label": "Projects & Kaggle",
            "level": "intermediate",
            "type": "good-to-know",
            "description": "End-to-end projects on real datasets - the fastest way to learn and the best interview evidence.",
            "resources": [
              {
                "title": "Kaggle Learn",
                "url": "https://www.kaggle.com/learn"
              }
            ]
          }
        ]
      }
    ]
  },
  "devops": {
    "sections": [
      {
        "id": "foundations",
        "label": "Foundations",
        "nodes": [
          {
            "id": "linux",
            "label": "Linux & Terminal",
            "level": "beginner",
            "type": "required",
            "description": "Shell scripting, processes, permissions, systemd, and networking tools - DevOps lives in the terminal.",
            "resources": [
              {
                "title": "Linux Journey",
                "url": "https://linuxjourney.com"
              },
              {
                "title": "roadmap.sh - DevOps",
                "url": "https://roadmap.sh/devops"
              }
            ]
          },
          {
            "id": "programming-language",
            "label": "A Programming Language",
            "level": "beginner",
            "type": "required",
            "description": "Python or Go for automation, tooling, and glue - DevOps is software engineering for infrastructure.",
            "resources": [
              {
                "title": "Go - Tour",
                "url": "https://go.dev/tour/"
              }
            ]
          },
          {
            "id": "networking",
            "label": "Networking & Protocols",
            "level": "beginner",
            "type": "required",
            "description": "DNS, HTTP/HTTPS, TCP/IP, load balancing, and TLS - the plumbing you'll spend nights debugging.",
            "resources": [
              {
                "title": "Cloudflare - Learning Center",
                "url": "https://www.cloudflare.com/learning/"
              }
            ]
          },
          {
            "id": "git",
            "label": "Git & Version Control",
            "level": "beginner",
            "type": "required",
            "description": "Everything as code means everything in Git: branching, tags, and reviewing infra changes.",
            "resources": [
              {
                "title": "Pro Git (free book)",
                "url": "https://git-scm.com/book"
              }
            ]
          }
        ]
      },
      {
        "id": "containers",
        "label": "Containers & Orchestration",
        "nodes": [
          {
            "id": "docker",
            "label": "Docker",
            "level": "intermediate",
            "type": "required",
            "description": "Images, layers, registries, and Compose - packaging apps so they run anywhere identically.",
            "resources": [
              {
                "title": "Docker Docs",
                "url": "https://docs.docker.com"
              }
            ]
          },
          {
            "id": "kubernetes",
            "label": "Kubernetes",
            "level": "advanced",
            "type": "required",
            "description": "Pods, deployments, services, ingress, and autoscaling - orchestrating containers at scale.",
            "resources": [
              {
                "title": "Kubernetes Docs",
                "url": "https://kubernetes.io/docs/home/"
              }
            ]
          },
          {
            "id": "container-security",
            "label": "Container Security",
            "level": "advanced",
            "type": "good-to-know",
            "description": "Image scanning, least-privilege, and secrets - hardening the container supply chain.",
            "resources": [
              {
                "title": "Kubernetes - Security",
                "url": "https://kubernetes.io/docs/concepts/security/"
              }
            ]
          },
          {
            "id": "service-mesh",
            "label": "Service Mesh",
            "level": "advanced",
            "type": "optional",
            "description": "Istio/Linkerd: traffic management, mTLS, and observability between microservices.",
            "resources": [
              {
                "title": "Istio Docs",
                "url": "https://istio.io/latest/docs/"
              }
            ]
          }
        ]
      },
      {
        "id": "cloud-iac",
        "label": "Cloud & Infrastructure as Code",
        "nodes": [
          {
            "id": "cloud-providers",
            "label": "Cloud Providers",
            "level": "intermediate",
            "type": "required",
            "description": "AWS (or GCP/Azure) core services: compute, storage, networking, IAM, and managed databases.",
            "resources": [
              {
                "title": "AWS Documentation",
                "url": "https://docs.aws.amazon.com"
              }
            ]
          },
          {
            "id": "terraform",
            "label": "Terraform",
            "level": "intermediate",
            "type": "required",
            "description": "Declarative infrastructure: providers, state, modules, and plan/apply workflows.",
            "resources": [
              {
                "title": "Terraform Docs",
                "url": "https://developer.hashicorp.com/terraform"
              }
            ]
          },
          {
            "id": "configuration-management",
            "label": "Configuration Management",
            "level": "intermediate",
            "type": "good-to-know",
            "description": "Ansible: idempotent playbooks for provisioning and configuring servers.",
            "resources": [
              {
                "title": "Ansible Docs",
                "url": "https://docs.ansible.com"
              }
            ]
          },
          {
            "id": "secret-management",
            "label": "Secret Management",
            "level": "advanced",
            "type": "required",
            "description": "Vault and cloud secret stores: rotating credentials without hardcoding them anywhere.",
            "resources": [
              {
                "title": "HashiCorp Vault",
                "url": "https://developer.hashicorp.com/vault"
              }
            ]
          }
        ]
      },
      {
        "id": "cicd",
        "label": "CI/CD & Automation",
        "nodes": [
          {
            "id": "ci-cd-pipelines",
            "label": "CI/CD Pipelines",
            "level": "intermediate",
            "type": "required",
            "description": "Build, test, and deploy automatically with GitHub Actions or GitLab CI - the DevOps heartbeat.",
            "resources": [
              {
                "title": "GitHub Actions Docs",
                "url": "https://docs.github.com/actions"
              }
            ]
          },
          {
            "id": "gitops",
            "label": "GitOps",
            "level": "advanced",
            "type": "good-to-know",
            "description": "Argo CD / Flux: Git as the single source of truth for cluster state, reconciled automatically.",
            "resources": [
              {
                "title": "Argo CD Docs",
                "url": "https://argo-cd.readthedocs.io"
              }
            ]
          },
          {
            "id": "artifact-management",
            "label": "Artifact Management",
            "level": "advanced",
            "type": "optional",
            "description": "Registries and artifact repositories for versioned, promotable build outputs.",
            "resources": [
              {
                "title": "OCI - Registry Spec",
                "url": "https://github.com/opencontainers/distribution-spec"
              }
            ]
          }
        ]
      },
      {
        "id": "reliability",
        "label": "Reliability & Observability",
        "nodes": [
          {
            "id": "monitoring",
            "label": "Monitoring & Metrics",
            "level": "advanced",
            "type": "required",
            "description": "Prometheus and Grafana: metrics, dashboards, and alerts that page a human before users notice.",
            "resources": [
              {
                "title": "Prometheus Docs",
                "url": "https://prometheus.io/docs/"
              },
              {
                "title": "Grafana Docs",
                "url": "https://grafana.com/docs/"
              }
            ]
          },
          {
            "id": "logging",
            "label": "Log Management",
            "level": "advanced",
            "type": "required",
            "description": "Centralized, structured logs (ELK / Loki) so you can search across every service.",
            "resources": [
              {
                "title": "Grafana Loki",
                "url": "https://grafana.com/docs/loki/latest/"
              }
            ]
          },
          {
            "id": "sre-practices",
            "label": "SRE Practices",
            "level": "advanced",
            "type": "good-to-know",
            "description": "SLOs, error budgets, incident response, and blameless postmortems.",
            "resources": [
              {
                "title": "Google - SRE Book",
                "url": "https://sre.google/books/"
              }
            ]
          },
          {
            "id": "cloud-design-patterns",
            "label": "Cloud Design Patterns",
            "level": "advanced",
            "type": "good-to-know",
            "description": "Retries, circuit breakers, and graceful degradation for systems that fail well.",
            "resources": [
              {
                "title": "Azure - Cloud Design Patterns",
                "url": "https://learn.microsoft.com/en-us/azure/architecture/patterns/"
              }
            ]
          }
        ]
      }
    ]
  },
  "product-manager": {
    "sections": [
      {
        "id": "foundations",
        "label": "PM Foundations",
        "nodes": [
          {
            "id": "what-is-pm",
            "label": "The PM Role",
            "level": "beginner",
            "type": "required",
            "description": "What a PM owns (the why and what, not the how) and how it differs from project and program management.",
            "resources": [
              {
                "title": "SVPG - Articles",
                "url": "https://www.svpg.com/articles/"
              },
              {
                "title": "roadmap.sh - Product Manager",
                "url": "https://roadmap.sh/product-manager"
              }
            ]
          },
          {
            "id": "user-research",
            "label": "User Research",
            "level": "beginner",
            "type": "required",
            "description": "Interviews, surveys, and jobs-to-be-done - understanding problems before proposing solutions.",
            "resources": [
              {
                "title": "NN/g - UX Research Methods",
                "url": "https://www.nngroup.com/articles/which-ux-research-methods/"
              }
            ]
          },
          {
            "id": "market-analysis",
            "label": "Market & Competitive Analysis",
            "level": "beginner",
            "type": "required",
            "description": "TAM/SAM/SOM, positioning, and competitor teardowns to find where you can win.",
            "resources": [
              {
                "title": "Lenny's Newsletter",
                "url": "https://www.lennysnewsletter.com"
              }
            ]
          }
        ]
      },
      {
        "id": "strategy",
        "label": "Product Strategy",
        "nodes": [
          {
            "id": "vision-strategy",
            "label": "Vision & Strategy",
            "level": "intermediate",
            "type": "required",
            "description": "A clear vision, strategy, and value proposition that align the team on where you're going and why.",
            "resources": [
              {
                "title": "SVPG - Product Vision",
                "url": "https://www.svpg.com/product-vision/"
              }
            ]
          },
          {
            "id": "prioritization",
            "label": "Prioritization",
            "level": "intermediate",
            "type": "required",
            "description": "RICE, value vs effort, and opportunity scoring - saying no to good ideas to ship great ones.",
            "resources": [
              {
                "title": "Intercom - RICE",
                "url": "https://www.intercom.com/blog/rice-simple-prioritization-for-product-managers/"
              }
            ]
          },
          {
            "id": "roadmapping",
            "label": "Roadmapping",
            "level": "intermediate",
            "type": "required",
            "description": "Outcome-based roadmaps that communicate direction without over-promising dates.",
            "resources": [
              {
                "title": "SVPG - Product Roadmaps",
                "url": "https://www.svpg.com/product-roadmaps/"
              }
            ]
          },
          {
            "id": "goals-okrs",
            "label": "Goals & OKRs",
            "level": "intermediate",
            "type": "good-to-know",
            "description": "Setting measurable objectives and key results that tie daily work to strategy.",
            "resources": [
              {
                "title": "What Matters - OKRs",
                "url": "https://www.whatmatters.com/get-started"
              }
            ]
          }
        ]
      },
      {
        "id": "execution",
        "label": "Execution & Delivery",
        "nodes": [
          {
            "id": "requirements",
            "label": "Requirements & PRDs",
            "level": "intermediate",
            "type": "required",
            "description": "User stories, acceptance criteria, and crisp PRDs so engineering builds the right thing.",
            "resources": [
              {
                "title": "Atlassian - Product Requirements",
                "url": "https://www.atlassian.com/agile/product-management/requirements"
              }
            ]
          },
          {
            "id": "agile",
            "label": "Agile & Scrum",
            "level": "intermediate",
            "type": "required",
            "description": "Backlogs, sprints, and ceremonies - working effectively inside an agile engineering team.",
            "resources": [
              {
                "title": "Atlassian - Agile Coach",
                "url": "https://www.atlassian.com/agile"
              }
            ]
          },
          {
            "id": "working-with-engineering",
            "label": "Working with Engineering & Design",
            "level": "intermediate",
            "type": "required",
            "description": "The product trio: shared discovery, trade-off conversations, and healthy dev collaboration.",
            "resources": [
              {
                "title": "SVPG - Product Discovery",
                "url": "https://www.svpg.com/product-discovery/"
              }
            ]
          },
          {
            "id": "go-to-market",
            "label": "Go-to-Market",
            "level": "intermediate",
            "type": "good-to-know",
            "description": "Launch planning, positioning, and coordinating marketing, sales, and support.",
            "resources": [
              {
                "title": "Lenny's Newsletter",
                "url": "https://www.lennysnewsletter.com"
              }
            ]
          }
        ]
      },
      {
        "id": "data",
        "label": "Data & Discovery",
        "nodes": [
          {
            "id": "product-metrics",
            "label": "Product Metrics",
            "level": "advanced",
            "type": "required",
            "description": "North-star metrics, activation, retention, and the AARRR funnel - knowing if you're winning.",
            "resources": [
              {
                "title": "Amplitude - Product Metrics",
                "url": "https://amplitude.com/blog/product-metrics"
              }
            ]
          },
          {
            "id": "ab-testing",
            "label": "Experimentation & A/B Testing",
            "level": "advanced",
            "type": "required",
            "description": "Hypotheses, experiment design, and reading results without fooling yourself.",
            "resources": [
              {
                "title": "Optimizely - A/B Testing",
                "url": "https://www.optimizely.com/optimization-glossary/ab-testing/"
              }
            ]
          },
          {
            "id": "analytics-tools",
            "label": "Analytics Tools",
            "level": "intermediate",
            "type": "good-to-know",
            "description": "SQL basics plus Amplitude/Mixpanel - answering your own product questions.",
            "resources": [
              {
                "title": "Mode - SQL Tutorial",
                "url": "https://mode.com/sql-tutorial"
              }
            ]
          },
          {
            "id": "feedback-loops",
            "label": "Feedback Loops",
            "level": "intermediate",
            "type": "good-to-know",
            "description": "Continuous discovery: customer interviews and feedback channels that never turn off.",
            "resources": [
              {
                "title": "Continuous Discovery Habits",
                "url": "https://www.producttalk.org/continuous-discovery/"
              }
            ]
          }
        ]
      },
      {
        "id": "leadership",
        "label": "Leadership & Communication",
        "nodes": [
          {
            "id": "stakeholder-management",
            "label": "Stakeholder Management",
            "level": "advanced",
            "type": "required",
            "description": "Aligning execs, engineering, and go-to-market teams - influence without authority.",
            "resources": [
              {
                "title": "SVPG - Stakeholder Management",
                "url": "https://www.svpg.com/beyond-lip-service/"
              }
            ]
          },
          {
            "id": "communication",
            "label": "Communication & Storytelling",
            "level": "advanced",
            "type": "required",
            "description": "Writing crisply, presenting decisions, and telling the story that gets a roadmap funded.",
            "resources": [
              {
                "title": "Amazon - Working Backwards",
                "url": "https://www.aboutamazon.com/news/workplace/an-insider-look-at-amazons-culture-and-processes"
              }
            ]
          },
          {
            "id": "leadership-influence",
            "label": "Leadership & Influence",
            "level": "advanced",
            "type": "good-to-know",
            "description": "Leading through vision and trust, managing up, and growing from PM to product leader.",
            "resources": [
              {
                "title": "SVPG - Articles",
                "url": "https://www.svpg.com/articles/"
              }
            ]
          }
        ]
      }
    ]
  },
  "ux-designer": {
    "sections": [
      {
        "id": "foundations",
        "label": "Design Foundations",
        "nodes": [
          {
            "id": "design-principles",
            "label": "Design Principles",
            "level": "beginner",
            "type": "required",
            "description": "Hierarchy, contrast, balance, alignment, and Gestalt - the grammar behind every good layout.",
            "resources": [
              {
                "title": "Refactoring UI",
                "url": "https://www.refactoringui.com"
              },
              {
                "title": "roadmap.sh - UX Design",
                "url": "https://roadmap.sh/ux-design"
              }
            ]
          },
          {
            "id": "color-typography",
            "label": "Color & Typography",
            "level": "beginner",
            "type": "required",
            "description": "Type scales, readable text, color systems, and contrast that meets accessibility standards.",
            "resources": [
              {
                "title": "Material - Typography",
                "url": "https://m3.material.io/styles/typography/overview"
              }
            ]
          },
          {
            "id": "ux-vs-ui",
            "label": "UX vs UI",
            "level": "beginner",
            "type": "required",
            "description": "The difference between how it works and how it looks - and why both roles collaborate closely.",
            "resources": [
              {
                "title": "NN/g - UX vs UI",
                "url": "https://www.nngroup.com/articles/definition-user-experience/"
              }
            ]
          },
          {
            "id": "psychology",
            "label": "Human Behavior & Psychology",
            "level": "beginner",
            "type": "good-to-know",
            "description": "Mental models, cognitive load, and behavior-change frameworks like Fogg's model.",
            "resources": [
              {
                "title": "Laws of UX",
                "url": "https://lawsofux.com"
              }
            ]
          }
        ]
      },
      {
        "id": "research",
        "label": "User Research",
        "nodes": [
          {
            "id": "user-research",
            "label": "User Research",
            "level": "intermediate",
            "type": "required",
            "description": "Interviews, surveys, and contextual inquiry - designing from evidence, not assumptions.",
            "resources": [
              {
                "title": "NN/g - UX Research Methods",
                "url": "https://www.nngroup.com/articles/which-ux-research-methods/"
              }
            ]
          },
          {
            "id": "personas-journeys",
            "label": "Personas & Journey Maps",
            "level": "intermediate",
            "type": "required",
            "description": "Synthesizing research into personas, empathy maps, and journey maps the whole team rallies around.",
            "resources": [
              {
                "title": "NN/g - Personas",
                "url": "https://www.nngroup.com/articles/persona/"
              }
            ]
          },
          {
            "id": "information-architecture",
            "label": "Information Architecture",
            "level": "intermediate",
            "type": "required",
            "description": "Card sorting, navigation, and content structure so users always know where they are.",
            "resources": [
              {
                "title": "NN/g - Information Architecture",
                "url": "https://www.nngroup.com/topic/information-architecture/"
              }
            ]
          },
          {
            "id": "competitive-analysis",
            "label": "Competitive Analysis",
            "level": "intermediate",
            "type": "good-to-know",
            "description": "Studying competitors and conventions so your product feels familiar where it should.",
            "resources": [
              {
                "title": "NN/g - Competitive Usability",
                "url": "https://www.nngroup.com/articles/competitive-usability-evaluations/"
              }
            ]
          }
        ]
      },
      {
        "id": "design-process",
        "label": "Design Process",
        "nodes": [
          {
            "id": "wireframing",
            "label": "Wireframing",
            "level": "intermediate",
            "type": "required",
            "description": "Low-fidelity structure first: layout and flow before color and polish.",
            "resources": [
              {
                "title": "Balsamiq - Wireframing Guide",
                "url": "https://balsamiq.com/learn/"
              }
            ]
          },
          {
            "id": "figma",
            "label": "Figma",
            "level": "intermediate",
            "type": "required",
            "description": "The industry-standard tool: frames, auto-layout, components, and real-time collaboration.",
            "resources": [
              {
                "title": "Figma - Learn",
                "url": "https://help.figma.com/hc/en-us/categories/360002051613-Get-started"
              }
            ]
          },
          {
            "id": "prototyping",
            "label": "Prototyping",
            "level": "intermediate",
            "type": "required",
            "description": "Interactive prototypes to test flows and hand off intent before engineers build.",
            "resources": [
              {
                "title": "Figma - Prototyping",
                "url": "https://help.figma.com/hc/en-us/articles/360040314193-Guide-to-prototyping-in-Figma"
              }
            ]
          },
          {
            "id": "interaction-design",
            "label": "Interaction Design",
            "level": "intermediate",
            "type": "good-to-know",
            "description": "Micro-interactions, transitions, and feedback that make interfaces feel responsive and alive.",
            "resources": [
              {
                "title": "NN/g - Microinteractions",
                "url": "https://www.nngroup.com/articles/microinteractions/"
              }
            ]
          }
        ]
      },
      {
        "id": "systems-testing",
        "label": "Systems & Validation",
        "nodes": [
          {
            "id": "design-systems",
            "label": "Design Systems",
            "level": "advanced",
            "type": "required",
            "description": "Reusable components, tokens, and guidelines that keep a product consistent at scale.",
            "resources": [
              {
                "title": "Design Systems - Repo & Examples",
                "url": "https://www.designsystems.com"
              }
            ]
          },
          {
            "id": "accessibility",
            "label": "Accessibility",
            "level": "advanced",
            "type": "required",
            "description": "WCAG, color contrast, focus order, and inclusive patterns - designing for every user.",
            "resources": [
              {
                "title": "W3C - WCAG Overview",
                "url": "https://www.w3.org/WAI/standards-guidelines/wcag/"
              }
            ]
          },
          {
            "id": "usability-testing",
            "label": "Usability Testing",
            "level": "advanced",
            "type": "required",
            "description": "Moderated and unmoderated tests to find where real users struggle - then fixing it.",
            "resources": [
              {
                "title": "NN/g - Usability Testing 101",
                "url": "https://www.nngroup.com/articles/usability-testing-101/"
              }
            ]
          }
        ]
      },
      {
        "id": "professional",
        "label": "Professional Practice",
        "nodes": [
          {
            "id": "design-handoff",
            "label": "Developer Handoff",
            "level": "advanced",
            "type": "good-to-know",
            "description": "Specs, redlines, and collaborating with engineers so the built product matches the design.",
            "resources": [
              {
                "title": "Figma - Dev Mode",
                "url": "https://help.figma.com/hc/en-us/articles/15023124644247-Guide-to-Dev-Mode"
              }
            ]
          },
          {
            "id": "measuring-impact",
            "label": "Measuring Impact",
            "level": "advanced",
            "type": "good-to-know",
            "description": "Success metrics, A/B testing, and analytics to prove design decisions worked.",
            "resources": [
              {
                "title": "NN/g - UX Metrics",
                "url": "https://www.nngroup.com/articles/ux-metrics/"
              }
            ]
          },
          {
            "id": "portfolio",
            "label": "Portfolio & Case Studies",
            "level": "intermediate",
            "type": "required",
            "description": "Case studies that show your process and reasoning, not just polished final screens.",
            "resources": [
              {
                "title": "NN/g - UX Portfolios",
                "url": "https://www.nngroup.com/articles/ux-portfolios/"
              }
            ]
          }
        ]
      }
    ]
  },
  "fullstack": {
    "sections": [
      {
        "id": "frontend-foundations",
        "label": "Frontend Foundations",
        "nodes": [
          {
            "id": "html-css",
            "label": "HTML & CSS",
            "level": "beginner",
            "type": "required",
            "description": "Semantic markup, flexbox, grid, and responsive design - the visible half of every feature.",
            "resources": [
              {
                "title": "MDN - HTML & CSS",
                "url": "https://developer.mozilla.org/en-US/docs/Learn"
              },
              {
                "title": "roadmap.sh - Full Stack",
                "url": "https://roadmap.sh/full-stack"
              }
            ]
          },
          {
            "id": "javascript",
            "label": "JavaScript",
            "level": "beginner",
            "type": "required",
            "description": "One language across the whole stack: fundamentals, the DOM, promises, and async/await.",
            "resources": [
              {
                "title": "javascript.info",
                "url": "https://javascript.info"
              }
            ]
          },
          {
            "id": "react",
            "label": "React",
            "level": "intermediate",
            "type": "required",
            "description": "Components, hooks, and client-side routing - your default UI layer.",
            "resources": [
              {
                "title": "React Docs",
                "url": "https://react.dev/learn"
              }
            ]
          },
          {
            "id": "tailwind",
            "label": "Tailwind CSS",
            "level": "intermediate",
            "type": "good-to-know",
            "description": "Utility-first styling to ship polished UI fast without a custom design system.",
            "resources": [
              {
                "title": "Tailwind CSS Docs",
                "url": "https://tailwindcss.com/docs"
              }
            ]
          }
        ]
      },
      {
        "id": "backend-core",
        "label": "Backend Core",
        "nodes": [
          {
            "id": "nodejs",
            "label": "Node.js & Express",
            "level": "intermediate",
            "type": "required",
            "description": "Building HTTP servers, middleware, routing, and environment-based config.",
            "resources": [
              {
                "title": "Node.js - Learn",
                "url": "https://nodejs.org/en/learn"
              }
            ]
          },
          {
            "id": "rest-apis",
            "label": "REST APIs",
            "level": "intermediate",
            "type": "required",
            "description": "Designing the contract between your frontend and backend: resources, status codes, and validation.",
            "resources": [
              {
                "title": "REST API Tutorial",
                "url": "https://restfulapi.net"
              }
            ]
          },
          {
            "id": "postgresql",
            "label": "PostgreSQL & SQL",
            "level": "intermediate",
            "type": "required",
            "description": "Schema design, joins, and migrations for the relational database behind your app.",
            "resources": [
              {
                "title": "PostgreSQL Docs",
                "url": "https://www.postgresql.org/docs/"
              },
              {
                "title": "SQLBolt - Interactive SQL",
                "url": "https://sqlbolt.com"
              }
            ]
          },
          {
            "id": "mongodb",
            "label": "MongoDB",
            "level": "intermediate",
            "type": "good-to-know",
            "description": "Document storage for flexible schemas - and knowing when relational is the better call.",
            "resources": [
              {
                "title": "MongoDB Docs",
                "url": "https://www.mongodb.com/docs/"
              }
            ]
          }
        ]
      },
      {
        "id": "connecting",
        "label": "Connecting the Stack",
        "nodes": [
          {
            "id": "jwt-auth",
            "label": "Authentication (JWT)",
            "level": "intermediate",
            "type": "required",
            "description": "Full-stack auth: registration, login, JWTs vs sessions, and protecting routes on both ends.",
            "resources": [
              {
                "title": "JWT Introduction",
                "url": "https://jwt.io/introduction"
              }
            ]
          },
          {
            "id": "api-integration",
            "label": "API Integration",
            "level": "intermediate",
            "type": "required",
            "description": "fetch, error handling, loading states, CORS, and keeping client and server contracts in sync.",
            "resources": [
              {
                "title": "MDN - Fetch API",
                "url": "https://developer.mozilla.org/en-US/docs/Web/API/Fetch_API"
              }
            ]
          },
          {
            "id": "fullstack-framework",
            "label": "Full-Stack Framework",
            "level": "advanced",
            "type": "good-to-know",
            "description": "Next.js: SSR, API routes, and one deployable app when a separate backend is overkill.",
            "resources": [
              {
                "title": "Next.js Docs",
                "url": "https://nextjs.org/docs"
              }
            ]
          },
          {
            "id": "redis-caching",
            "label": "Redis & Caching",
            "level": "advanced",
            "type": "good-to-know",
            "description": "Caching hot reads and sessions to keep response times flat as traffic grows.",
            "resources": [
              {
                "title": "Redis Docs",
                "url": "https://redis.io/docs/"
              }
            ]
          }
        ]
      },
      {
        "id": "ship-it",
        "label": "Ship It",
        "nodes": [
          {
            "id": "git-github",
            "label": "Git & GitHub",
            "level": "beginner",
            "type": "required",
            "description": "Branch, commit, review, merge - the collaboration loop for every feature you ship.",
            "resources": [
              {
                "title": "Pro Git (free book)",
                "url": "https://git-scm.com/book"
              }
            ]
          },
          {
            "id": "linux-basics",
            "label": "Linux Basics",
            "level": "intermediate",
            "type": "required",
            "description": "Enough shell to deploy, inspect logs, and manage processes on a server.",
            "resources": [
              {
                "title": "Linux Journey",
                "url": "https://linuxjourney.com"
              }
            ]
          },
          {
            "id": "docker",
            "label": "Docker",
            "level": "advanced",
            "type": "good-to-know",
            "description": "Containerize the whole stack so it runs the same on your laptop and in production.",
            "resources": [
              {
                "title": "Docker Docs",
                "url": "https://docs.docker.com"
              }
            ]
          },
          {
            "id": "aws-basics",
            "label": "AWS Basics",
            "level": "advanced",
            "type": "good-to-know",
            "description": "Core cloud building blocks: EC2, S3, RDS, and what a deploy actually consists of.",
            "resources": [
              {
                "title": "AWS Documentation",
                "url": "https://docs.aws.amazon.com"
              }
            ]
          },
          {
            "id": "ci-cd",
            "label": "CI/CD Pipelines",
            "level": "advanced",
            "type": "required",
            "description": "GitHub Actions: run tests on every push and deploy on every merge.",
            "resources": [
              {
                "title": "GitHub Actions Docs",
                "url": "https://docs.github.com/actions"
              }
            ]
          }
        ]
      },
      {
        "id": "professional",
        "label": "Professional Practice",
        "nodes": [
          {
            "id": "testing",
            "label": "Testing Across the Stack",
            "level": "advanced",
            "type": "required",
            "description": "Unit tests for logic, integration tests for APIs, and a few end-to-end flows that guard the money path.",
            "resources": [
              {
                "title": "Vitest Docs",
                "url": "https://vitest.dev"
              },
              {
                "title": "Playwright Docs",
                "url": "https://playwright.dev/docs/intro"
              }
            ]
          },
          {
            "id": "security-basics",
            "label": "Security Basics",
            "level": "advanced",
            "type": "required",
            "description": "OWASP Top 10 across both tiers: injection, XSS, broken auth, and secure secrets handling.",
            "resources": [
              {
                "title": "OWASP Top 10",
                "url": "https://owasp.org/www-project-top-ten/"
              }
            ]
          },
          {
            "id": "monitoring",
            "label": "Monitoring & Debugging",
            "level": "advanced",
            "type": "good-to-know",
            "description": "Uptime checks, error tracking, and reading production logs when something breaks at 2am.",
            "resources": [
              {
                "title": "The Twelve-Factor App",
                "url": "https://12factor.net"
              }
            ]
          },
          {
            "id": "infrastructure-as-code",
            "label": "Infrastructure as Code",
            "level": "advanced",
            "type": "optional",
            "description": "Terraform and Ansible: version-controlled, repeatable infrastructure.",
            "resources": [
              {
                "title": "Terraform Docs",
                "url": "https://developer.hashicorp.com/terraform"
              }
            ]
          }
        ]
      }
    ]
  },
  "mobile": {
    "sections": [
      {
        "id": "foundations",
        "label": "Foundations",
        "nodes": [
          {
            "id": "platform-language",
            "label": "Swift & Kotlin",
            "level": "beginner",
            "type": "required",
            "description": "Learn a native platform language deeply - Swift for iOS, Kotlin for Android - including optionals, generics, and value types.",
            "resources": [
              {
                "title": "Swift Documentation",
                "url": "https://www.swift.org/documentation/"
              },
              {
                "title": "Kotlin Docs",
                "url": "https://kotlinlang.org/docs/home.html"
              }
            ]
          },
          {
            "id": "mobile-platforms",
            "label": "Platform Fundamentals",
            "level": "beginner",
            "type": "required",
            "description": "App lifecycle, sandboxing, permissions, and how iOS and Android differ under the hood.",
            "resources": [
              {
                "title": "Android Developer Guides",
                "url": "https://developer.android.com/guide"
              }
            ]
          },
          {
            "id": "git",
            "label": "Git & Version Control",
            "level": "beginner",
            "type": "required",
            "description": "Branching and pull-request flow - table stakes on any app team.",
            "resources": [
              {
                "title": "Pro Git (free book)",
                "url": "https://git-scm.com/book"
              }
            ]
          },
          {
            "id": "mobile-ui-principles",
            "label": "Mobile UI Principles",
            "level": "beginner",
            "type": "required",
            "description": "Apple's Human Interface Guidelines and Material Design: navigation patterns, touch targets, and platform conventions.",
            "resources": [
              {
                "title": "Human Interface Guidelines",
                "url": "https://developer.apple.com/design/human-interface-guidelines"
              },
              {
                "title": "Material Design 3",
                "url": "https://m3.material.io"
              }
            ]
          }
        ]
      },
      {
        "id": "native",
        "label": "Native Development",
        "nodes": [
          {
            "id": "ios-swiftui",
            "label": "iOS & SwiftUI",
            "level": "intermediate",
            "type": "required",
            "description": "Declarative UI on iOS: views, state, navigation, and the Xcode toolchain.",
            "resources": [
              {
                "title": "SwiftUI Tutorials",
                "url": "https://developer.apple.com/tutorials/swiftui"
              }
            ]
          },
          {
            "id": "android-compose",
            "label": "Android & Jetpack Compose",
            "level": "intermediate",
            "type": "required",
            "description": "Modern Android UI: composables, state hoisting, and Android Studio workflows.",
            "resources": [
              {
                "title": "Jetpack Compose",
                "url": "https://developer.android.com/compose"
              }
            ]
          },
          {
            "id": "architecture-patterns",
            "label": "App Architecture",
            "level": "intermediate",
            "type": "required",
            "description": "MVVM and unidirectional data flow: keeping view code thin and logic testable.",
            "resources": [
              {
                "title": "Android - Guide to App Architecture",
                "url": "https://developer.android.com/topic/architecture"
              }
            ]
          },
          {
            "id": "local-storage",
            "label": "Local Storage",
            "level": "intermediate",
            "type": "required",
            "description": "Persisting data on device: Core Data / SwiftData, Room, and key-value stores.",
            "resources": [
              {
                "title": "Android - Data & Storage",
                "url": "https://developer.android.com/training/data-storage"
              }
            ]
          }
        ]
      },
      {
        "id": "cross-platform",
        "label": "Cross-Platform",
        "nodes": [
          {
            "id": "react-native",
            "label": "React Native",
            "level": "intermediate",
            "type": "good-to-know",
            "description": "One JavaScript codebase for both stores - components, native modules, and the bridge.",
            "resources": [
              {
                "title": "React Native Docs",
                "url": "https://reactnative.dev/docs/getting-started"
              }
            ]
          },
          {
            "id": "flutter",
            "label": "Flutter",
            "level": "intermediate",
            "type": "good-to-know",
            "description": "Dart and the widget tree: pixel-perfect cross-platform UI with hot reload.",
            "resources": [
              {
                "title": "Flutter Docs",
                "url": "https://docs.flutter.dev"
              }
            ]
          },
          {
            "id": "platform-specific-code",
            "label": "Platform-Specific Code",
            "level": "advanced",
            "type": "optional",
            "description": "Dropping down to native APIs from a cross-platform app when a feature demands it.",
            "resources": [
              {
                "title": "React Native - Native Modules",
                "url": "https://reactnative.dev/docs/native-platform"
              }
            ]
          }
        ]
      },
      {
        "id": "data-networking",
        "label": "Data & Networking",
        "nodes": [
          {
            "id": "networking-apis",
            "label": "Networking & REST APIs",
            "level": "intermediate",
            "type": "required",
            "description": "Consuming JSON APIs, handling flaky connections, retries, and error states gracefully.",
            "resources": [
              {
                "title": "MDN - HTTP Overview",
                "url": "https://developer.mozilla.org/en-US/docs/Web/HTTP/Overview"
              }
            ]
          },
          {
            "id": "async-concurrency",
            "label": "Async & Concurrency",
            "level": "intermediate",
            "type": "required",
            "description": "async/await in Swift and Kotlin coroutines: keeping the main thread free so the UI never janks.",
            "resources": [
              {
                "title": "Kotlin Coroutines",
                "url": "https://kotlinlang.org/docs/coroutines-overview.html"
              }
            ]
          },
          {
            "id": "push-notifications",
            "label": "Push Notifications",
            "level": "intermediate",
            "type": "good-to-know",
            "description": "APNs and Firebase Cloud Messaging: permissions, tokens, and deep links from a tap.",
            "resources": [
              {
                "title": "Firebase Cloud Messaging",
                "url": "https://firebase.google.com/docs/cloud-messaging"
              }
            ]
          },
          {
            "id": "offline-first",
            "label": "Offline-First Design",
            "level": "advanced",
            "type": "good-to-know",
            "description": "Caching, sync, and conflict resolution so the app works on the subway.",
            "resources": [
              {
                "title": "Android - Offline-First",
                "url": "https://developer.android.com/topic/architecture/data-layer/offline-first"
              }
            ]
          }
        ]
      },
      {
        "id": "ship",
        "label": "Quality & Distribution",
        "nodes": [
          {
            "id": "testing",
            "label": "Testing",
            "level": "advanced",
            "type": "required",
            "description": "Unit tests plus UI tests with XCTest and Espresso - catching regressions before users do.",
            "resources": [
              {
                "title": "Android Testing",
                "url": "https://developer.android.com/training/testing"
              }
            ]
          },
          {
            "id": "debugging-profiling",
            "label": "Debugging & Profiling",
            "level": "advanced",
            "type": "required",
            "description": "Instruments and Android Profiler: hunting memory leaks, jank, and battery drain.",
            "resources": [
              {
                "title": "Android Studio Profilers",
                "url": "https://developer.android.com/studio/profile"
              }
            ]
          },
          {
            "id": "ci-cd-mobile",
            "label": "Mobile CI/CD",
            "level": "advanced",
            "type": "good-to-know",
            "description": "Automating builds, signing, and beta distribution with Fastlane and CI runners.",
            "resources": [
              {
                "title": "Fastlane",
                "url": "https://fastlane.tools"
              }
            ]
          },
          {
            "id": "store-distribution",
            "label": "App Store & Play Store",
            "level": "advanced",
            "type": "required",
            "description": "Release management: TestFlight, staged rollouts, review guidelines, and store listings.",
            "resources": [
              {
                "title": "Play Console - Launch",
                "url": "https://developer.android.com/distribute"
              }
            ]
          },
          {
            "id": "crash-analytics",
            "label": "Crash Reporting & Analytics",
            "level": "advanced",
            "type": "optional",
            "description": "Crashlytics and analytics events: knowing what breaks and what users actually use.",
            "resources": [
              {
                "title": "Firebase Crashlytics",
                "url": "https://firebase.google.com/docs/crashlytics"
              }
            ]
          }
        ]
      }
    ]
  },
  "data-analyst": {
    "sections": [
      {
        "id": "foundations",
        "label": "Analytics Foundations",
        "nodes": [
          {
            "id": "what-is-analytics",
            "label": "Types of Analytics",
            "level": "beginner",
            "type": "required",
            "description": "Descriptive, diagnostic, predictive, prescriptive - what question each answers and where analysts spend their time.",
            "resources": [
              {
                "title": "roadmap.sh - Data Analyst",
                "url": "https://roadmap.sh/data-analyst"
              }
            ]
          },
          {
            "id": "excel",
            "label": "Excel",
            "level": "beginner",
            "type": "required",
            "description": "Still the analyst's Swiss army knife: formulas, VLOOKUP/XLOOKUP, pivot tables, and charts.",
            "resources": [
              {
                "title": "Microsoft - Excel Help & Learning",
                "url": "https://support.microsoft.com/en-us/excel"
              }
            ]
          },
          {
            "id": "statistics-fundamentals",
            "label": "Statistics Fundamentals",
            "level": "beginner",
            "type": "required",
            "description": "Central tendency, dispersion, distributions, and sampling - the math behind every honest chart.",
            "resources": [
              {
                "title": "Khan Academy - Statistics & Probability",
                "url": "https://www.khanacademy.org/math/statistics-probability"
              }
            ]
          }
        ]
      },
      {
        "id": "sql-data",
        "label": "SQL & Data Sourcing",
        "nodes": [
          {
            "id": "sql",
            "label": "SQL",
            "level": "beginner",
            "type": "required",
            "description": "The analyst's core language: SELECT, JOIN, GROUP BY, window functions, and CTEs.",
            "resources": [
              {
                "title": "SQLBolt - Interactive SQL",
                "url": "https://sqlbolt.com"
              },
              {
                "title": "Mode SQL Tutorial",
                "url": "https://mode.com/sql-tutorial"
              }
            ]
          },
          {
            "id": "databases",
            "label": "Databases & Warehouses",
            "level": "intermediate",
            "type": "required",
            "description": "Relational schemas, star schemas, and where analytics data actually lives (Postgres, BigQuery, Snowflake).",
            "resources": [
              {
                "title": "PostgreSQL Docs",
                "url": "https://www.postgresql.org/docs/"
              }
            ]
          },
          {
            "id": "data-collection",
            "label": "Data Collection",
            "level": "intermediate",
            "type": "good-to-know",
            "description": "Pulling data from APIs, CSVs, exports, and light web scraping when the table you need doesn't exist.",
            "resources": [
              {
                "title": "pandas - IO Tools",
                "url": "https://pandas.pydata.org/docs/user_guide/io.html"
              }
            ]
          }
        ]
      },
      {
        "id": "programming",
        "label": "Programming for Analysis",
        "nodes": [
          {
            "id": "python-pandas",
            "label": "Python & Pandas",
            "level": "intermediate",
            "type": "required",
            "description": "DataFrames, groupby, merges, and reshaping - analysis that's reproducible instead of click-driven.",
            "resources": [
              {
                "title": "pandas Docs",
                "url": "https://pandas.pydata.org/docs/"
              }
            ]
          },
          {
            "id": "data-cleaning",
            "label": "Data Cleaning",
            "level": "intermediate",
            "type": "required",
            "description": "Missing values, duplicates, outliers, and type fixes - 80% of the job, done systematically.",
            "resources": [
              {
                "title": "pandas - Working with Missing Data",
                "url": "https://pandas.pydata.org/docs/user_guide/missing_data.html"
              }
            ]
          },
          {
            "id": "r-language",
            "label": "R",
            "level": "intermediate",
            "type": "optional",
            "description": "The other analysis language: dplyr and ggplot2, common in research-heavy teams.",
            "resources": [
              {
                "title": "The R Project",
                "url": "https://www.r-project.org"
              }
            ]
          }
        ]
      },
      {
        "id": "visualization",
        "label": "Visualization & BI",
        "nodes": [
          {
            "id": "data-visualization",
            "label": "Data Visualization",
            "level": "intermediate",
            "type": "required",
            "description": "Choosing the right chart, avoiding chartjunk, and designing visuals that make the point in five seconds.",
            "resources": [
              {
                "title": "Storytelling with Data",
                "url": "https://www.storytellingwithdata.com"
              }
            ]
          },
          {
            "id": "tableau",
            "label": "Tableau",
            "level": "intermediate",
            "type": "required",
            "description": "Interactive dashboards: connections, calculated fields, filters, and publishing.",
            "resources": [
              {
                "title": "Tableau Help",
                "url": "https://help.tableau.com"
              }
            ]
          },
          {
            "id": "power-bi",
            "label": "Power BI",
            "level": "intermediate",
            "type": "good-to-know",
            "description": "The Microsoft BI stack: data models, DAX measures, and enterprise reporting.",
            "resources": [
              {
                "title": "Power BI Documentation",
                "url": "https://learn.microsoft.com/en-us/power-bi/"
              }
            ]
          },
          {
            "id": "dashboards",
            "label": "Dashboard Design",
            "level": "intermediate",
            "type": "good-to-know",
            "description": "KPIs, layout hierarchy, and refresh strategy - dashboards people check daily instead of once.",
            "resources": [
              {
                "title": "NN/g - Dashboard Design",
                "url": "https://www.nngroup.com/articles/dashboards-preattentive/"
              }
            ]
          }
        ]
      },
      {
        "id": "advanced",
        "label": "Advanced Analysis",
        "nodes": [
          {
            "id": "statistical-analysis",
            "label": "Statistical Analysis",
            "level": "advanced",
            "type": "required",
            "description": "Hypothesis testing, confidence intervals, correlation vs causation, and regression.",
            "resources": [
              {
                "title": "Khan Academy - Significance Tests",
                "url": "https://www.khanacademy.org/math/statistics-probability/significance-tests-one-sample"
              }
            ]
          },
          {
            "id": "ml-basics",
            "label": "Machine Learning Basics",
            "level": "advanced",
            "type": "good-to-know",
            "description": "Supervised vs unsupervised at a working level - enough to prototype with scikit-learn and talk to DS teams.",
            "resources": [
              {
                "title": "scikit-learn - Getting Started",
                "url": "https://scikit-learn.org/stable/getting_started.html"
              }
            ]
          },
          {
            "id": "big-data",
            "label": "Big Data Tools",
            "level": "advanced",
            "type": "optional",
            "description": "When data outgrows one machine: Spark, distributed queries, and columnar formats.",
            "resources": [
              {
                "title": "Apache Spark Docs",
                "url": "https://spark.apache.org/docs/latest/"
              }
            ]
          },
          {
            "id": "communicating-insights",
            "label": "Communicating Insights",
            "level": "advanced",
            "type": "required",
            "description": "Turning analysis into a recommendation: framing, narrative, and the one-slide answer.",
            "resources": [
              {
                "title": "Storytelling with Data - Blog",
                "url": "https://www.storytellingwithdata.com/blog"
              }
            ]
          }
        ]
      }
    ]
  },
  "machine-learning": {
    "sections": [
      {
        "id": "foundations",
        "label": "Foundations",
        "nodes": [
          {
            "id": "math-for-ml",
            "label": "Math for ML",
            "level": "beginner",
            "type": "required",
            "description": "Linear algebra, calculus (gradients), and probability - enough to read what the optimizer is doing.",
            "resources": [
              {
                "title": "3Blue1Brown - Linear Algebra",
                "url": "https://www.3blue1brown.com/topics/linear-algebra"
              },
              {
                "title": "roadmap.sh - Machine Learning",
                "url": "https://roadmap.sh/machine-learning"
              }
            ]
          },
          {
            "id": "python-engineering",
            "label": "Python Engineering",
            "level": "beginner",
            "type": "required",
            "description": "Beyond notebooks: OOP, typing, virtual environments, and packaging code a team can maintain.",
            "resources": [
              {
                "title": "Python Docs - Tutorial",
                "url": "https://docs.python.org/3/tutorial/"
              }
            ]
          },
          {
            "id": "sql-data-access",
            "label": "SQL & Data Access",
            "level": "beginner",
            "type": "required",
            "description": "Pulling training data yourself: joins, aggregations, and sampling from warehouses.",
            "resources": [
              {
                "title": "SQLBolt - Interactive SQL",
                "url": "https://sqlbolt.com"
              }
            ]
          },
          {
            "id": "data-preprocessing",
            "label": "Data Preprocessing",
            "level": "intermediate",
            "type": "required",
            "description": "Cleaning, encoding, scaling, and feature engineering - where most model quality is won.",
            "resources": [
              {
                "title": "scikit-learn - Preprocessing",
                "url": "https://scikit-learn.org/stable/modules/preprocessing.html"
              }
            ]
          }
        ]
      },
      {
        "id": "core-ml",
        "label": "Core Machine Learning",
        "nodes": [
          {
            "id": "ml-concepts",
            "label": "ML Concepts",
            "level": "intermediate",
            "type": "required",
            "description": "Types of learning, generalization, overfitting, and the bias-variance trade-off.",
            "resources": [
              {
                "title": "Google - ML Crash Course",
                "url": "https://developers.google.com/machine-learning/crash-course"
              }
            ]
          },
          {
            "id": "scikit-learn",
            "label": "Scikit-learn",
            "level": "intermediate",
            "type": "required",
            "description": "Pipelines, estimators, and cross-validation - the standard library of classical ML.",
            "resources": [
              {
                "title": "scikit-learn - User Guide",
                "url": "https://scikit-learn.org/stable/user_guide.html"
              }
            ]
          },
          {
            "id": "supervised-learning",
            "label": "Supervised Learning",
            "level": "intermediate",
            "type": "required",
            "description": "Regression, SVMs, tree ensembles, and gradient boosting (XGBoost/LightGBM) on tabular data.",
            "resources": [
              {
                "title": "scikit-learn - Supervised Learning",
                "url": "https://scikit-learn.org/stable/supervised_learning.html"
              }
            ]
          },
          {
            "id": "unsupervised-learning",
            "label": "Unsupervised Learning",
            "level": "intermediate",
            "type": "good-to-know",
            "description": "Clustering, PCA, and anomaly detection when labels don't exist.",
            "resources": [
              {
                "title": "scikit-learn - Unsupervised Learning",
                "url": "https://scikit-learn.org/stable/unsupervised_learning.html"
              }
            ]
          },
          {
            "id": "model-evaluation",
            "label": "Model Evaluation",
            "level": "intermediate",
            "type": "required",
            "description": "Choosing metrics that match the business problem, validation strategy, and error analysis.",
            "resources": [
              {
                "title": "scikit-learn - Model Evaluation",
                "url": "https://scikit-learn.org/stable/modules/model_evaluation.html"
              }
            ]
          }
        ]
      },
      {
        "id": "deep-learning",
        "label": "Deep Learning",
        "nodes": [
          {
            "id": "neural-networks",
            "label": "Neural Networks",
            "level": "advanced",
            "type": "required",
            "description": "Backpropagation, activation functions, regularization, and training dynamics.",
            "resources": [
              {
                "title": "DeepLearning.AI",
                "url": "https://www.deeplearning.ai"
              }
            ]
          },
          {
            "id": "pytorch",
            "label": "PyTorch",
            "level": "advanced",
            "type": "required",
            "description": "Tensors, autograd, DataLoaders, and custom training loops - the research-to-production default.",
            "resources": [
              {
                "title": "PyTorch Tutorials",
                "url": "https://pytorch.org/tutorials/"
              }
            ]
          },
          {
            "id": "tensorflow-keras",
            "label": "TensorFlow & Keras",
            "level": "advanced",
            "type": "good-to-know",
            "description": "The other major framework - common in production shops and on mobile/edge.",
            "resources": [
              {
                "title": "Keras",
                "url": "https://keras.io"
              }
            ]
          },
          {
            "id": "cnns-vision",
            "label": "CNNs & Computer Vision",
            "level": "advanced",
            "type": "good-to-know",
            "description": "Convolutions, transfer learning, and augmentation for image tasks.",
            "resources": [
              {
                "title": "PyTorch - Vision Tutorials",
                "url": "https://pytorch.org/tutorials/beginner/transfer_learning_tutorial.html"
              }
            ]
          },
          {
            "id": "transformers-nlp",
            "label": "Transformers & NLP",
            "level": "advanced",
            "type": "required",
            "description": "Attention, pre-trained language models, and fine-tuning with the Hugging Face ecosystem.",
            "resources": [
              {
                "title": "Hugging Face - Learn",
                "url": "https://huggingface.co/learn"
              }
            ]
          }
        ]
      },
      {
        "id": "mlops",
        "label": "MLOps & Deployment",
        "nodes": [
          {
            "id": "experiment-tracking",
            "label": "Experiment Tracking",
            "level": "advanced",
            "type": "required",
            "description": "MLflow or Weights & Biases: versioned runs, params, and metrics you can reproduce months later.",
            "resources": [
              {
                "title": "MLflow",
                "url": "https://mlflow.org"
              }
            ]
          },
          {
            "id": "model-serving",
            "label": "Model Serving",
            "level": "advanced",
            "type": "required",
            "description": "Shipping models behind APIs: batch vs real-time, latency budgets, and versioned rollouts.",
            "resources": [
              {
                "title": "FastAPI",
                "url": "https://fastapi.tiangolo.com"
              }
            ]
          },
          {
            "id": "docker-ml",
            "label": "Docker & Environments",
            "level": "advanced",
            "type": "required",
            "description": "Reproducible training and inference environments - the cure for \"works on my GPU\".",
            "resources": [
              {
                "title": "Docker Docs",
                "url": "https://docs.docker.com"
              }
            ]
          },
          {
            "id": "monitoring-drift",
            "label": "Monitoring & Drift",
            "level": "advanced",
            "type": "good-to-know",
            "description": "Data drift, model decay, and alerting - models degrade silently without it.",
            "resources": [
              {
                "title": "MLOps Principles",
                "url": "https://ml-ops.org"
              }
            ]
          }
        ]
      },
      {
        "id": "scale",
        "label": "Scaling & Frontier",
        "nodes": [
          {
            "id": "data-engineering-basics",
            "label": "Data Engineering Basics",
            "level": "advanced",
            "type": "good-to-know",
            "description": "Pipelines, orchestration, and Spark - feeding models reliably at scale.",
            "resources": [
              {
                "title": "Apache Spark Docs",
                "url": "https://spark.apache.org/docs/latest/"
              }
            ]
          },
          {
            "id": "distributed-training",
            "label": "Distributed Training",
            "level": "advanced",
            "type": "optional",
            "description": "Data and model parallelism, mixed precision, and multi-GPU training.",
            "resources": [
              {
                "title": "PyTorch - Distributed",
                "url": "https://pytorch.org/tutorials/beginner/dist_overview.html"
              }
            ]
          },
          {
            "id": "llm-finetuning",
            "label": "LLM Fine-Tuning",
            "level": "advanced",
            "type": "optional",
            "description": "LoRA/PEFT, instruction tuning, and evaluation - adapting foundation models to your domain.",
            "resources": [
              {
                "title": "Hugging Face - PEFT",
                "url": "https://huggingface.co/docs/peft"
              }
            ]
          }
        ]
      }
    ]
  },
  "ai-engineer": {
    "sections": [
      {
        "id": "foundations",
        "label": "Foundations",
        "nodes": [
          {
            "id": "python",
            "label": "Python",
            "level": "beginner",
            "type": "required",
            "description": "The lingua franca of AI tooling: async, typing, and API clients.",
            "resources": [
              {
                "title": "Python Docs - Tutorial",
                "url": "https://docs.python.org/3/tutorial/"
              },
              {
                "title": "roadmap.sh - AI Engineer",
                "url": "https://roadmap.sh/ai-engineer"
              }
            ]
          },
          {
            "id": "llm-fundamentals",
            "label": "LLM Fundamentals",
            "level": "beginner",
            "type": "required",
            "description": "How LLMs work at a practical level: tokens, context windows, temperature, and failure modes like hallucination.",
            "resources": [
              {
                "title": "Anthropic Docs",
                "url": "https://docs.anthropic.com"
              }
            ]
          },
          {
            "id": "nlp-fundamentals",
            "label": "NLP Fundamentals",
            "level": "beginner",
            "type": "good-to-know",
            "description": "Tokenization, embeddings, and classic NLP tasks - the substrate under every LLM product.",
            "resources": [
              {
                "title": "Hugging Face - NLP Course",
                "url": "https://huggingface.co/learn"
              }
            ]
          },
          {
            "id": "prompt-engineering",
            "label": "Prompt Engineering",
            "level": "beginner",
            "type": "required",
            "description": "System prompts, few-shot examples, structured output, and iterating on prompts like code.",
            "resources": [
              {
                "title": "OpenAI - Prompt Engineering Guide",
                "url": "https://platform.openai.com/docs/guides/prompt-engineering"
              }
            ]
          }
        ]
      },
      {
        "id": "models",
        "label": "Working with Models",
        "nodes": [
          {
            "id": "llm-apis",
            "label": "LLM APIs",
            "level": "intermediate",
            "type": "required",
            "description": "Chat completions, streaming, tool/function calling, and multimodal inputs via OpenAI and Anthropic APIs.",
            "resources": [
              {
                "title": "OpenAI - API Docs",
                "url": "https://platform.openai.com/docs"
              },
              {
                "title": "Anthropic - API Docs",
                "url": "https://docs.anthropic.com"
              }
            ]
          },
          {
            "id": "open-source-models",
            "label": "Open-Source Models",
            "level": "intermediate",
            "type": "good-to-know",
            "description": "Hugging Face and Ollama: running Llama-class models locally and when self-hosting beats an API.",
            "resources": [
              {
                "title": "Hugging Face Docs",
                "url": "https://huggingface.co/docs"
              },
              {
                "title": "Ollama",
                "url": "https://ollama.com"
              }
            ]
          },
          {
            "id": "structured-outputs",
            "label": "Structured Outputs & Tool Use",
            "level": "intermediate",
            "type": "required",
            "description": "JSON schemas, function calling, and validation - making probabilistic models emit reliable data.",
            "resources": [
              {
                "title": "OpenAI - Structured Outputs",
                "url": "https://platform.openai.com/docs/guides/structured-outputs"
              }
            ]
          },
          {
            "id": "model-selection",
            "label": "Model Selection & Cost",
            "level": "intermediate",
            "type": "good-to-know",
            "description": "Trading off quality, latency, and price; routing easy requests to cheap models.",
            "resources": [
              {
                "title": "Hugging Face - Open LLM Leaderboard",
                "url": "https://huggingface.co/spaces/open-llm-leaderboard/open_llm_leaderboard"
              }
            ]
          }
        ]
      },
      {
        "id": "rag",
        "label": "Embeddings & RAG",
        "nodes": [
          {
            "id": "embeddings",
            "label": "Embeddings",
            "level": "intermediate",
            "type": "required",
            "description": "Vector representations of meaning: similarity search, chunk embeddings, and their limits.",
            "resources": [
              {
                "title": "OpenAI - Embeddings Guide",
                "url": "https://platform.openai.com/docs/guides/embeddings"
              }
            ]
          },
          {
            "id": "vector-databases",
            "label": "Vector Databases",
            "level": "intermediate",
            "type": "required",
            "description": "Chroma, pgvector, Pinecone: indexing, metadata filtering, and hybrid search.",
            "resources": [
              {
                "title": "Chroma Docs",
                "url": "https://docs.trychroma.com"
              },
              {
                "title": "Pinecone - Learn",
                "url": "https://www.pinecone.io/learn/"
              }
            ]
          },
          {
            "id": "rag-pipelines",
            "label": "RAG Pipelines",
            "level": "intermediate",
            "type": "required",
            "description": "Chunking, retrieval, reranking, and grounding - answers backed by your own data instead of vibes.",
            "resources": [
              {
                "title": "LangChain - RAG Tutorial",
                "url": "https://python.langchain.com/docs/tutorials/rag/"
              }
            ]
          },
          {
            "id": "orchestration-frameworks",
            "label": "LangChain & LlamaIndex",
            "level": "intermediate",
            "type": "good-to-know",
            "description": "Orchestration frameworks for chains, retrievers, and integrations - and when plain code is simpler.",
            "resources": [
              {
                "title": "LangChain Docs",
                "url": "https://python.langchain.com/docs/"
              },
              {
                "title": "LlamaIndex Docs",
                "url": "https://docs.llamaindex.ai"
              }
            ]
          }
        ]
      },
      {
        "id": "agents",
        "label": "Agents & Advanced",
        "nodes": [
          {
            "id": "ai-agents",
            "label": "AI Agents",
            "level": "advanced",
            "type": "required",
            "description": "Tool-using loops: planning, memory, multi-step execution, and knowing when to keep it a single prompt.",
            "resources": [
              {
                "title": "Anthropic - Building Effective Agents",
                "url": "https://www.anthropic.com/research/building-effective-agents"
              }
            ]
          },
          {
            "id": "multimodal",
            "label": "Multimodal AI",
            "level": "advanced",
            "type": "good-to-know",
            "description": "Vision, audio, and document understanding in one pipeline.",
            "resources": [
              {
                "title": "OpenAI - Vision Guide",
                "url": "https://platform.openai.com/docs/guides/vision"
              }
            ]
          },
          {
            "id": "fine-tuning",
            "label": "Fine-Tuning",
            "level": "advanced",
            "type": "good-to-know",
            "description": "When prompting isn't enough: LoRA, instruction tuning, and dataset curation.",
            "resources": [
              {
                "title": "Hugging Face - PEFT",
                "url": "https://huggingface.co/docs/peft"
              }
            ]
          }
        ]
      },
      {
        "id": "production",
        "label": "Production AI",
        "nodes": [
          {
            "id": "evaluation",
            "label": "Evals & Testing",
            "level": "advanced",
            "type": "required",
            "description": "Golden sets, LLM-as-judge, and regression evals - the unit tests of AI products.",
            "resources": [
              {
                "title": "OpenAI - Evals Guide",
                "url": "https://platform.openai.com/docs/guides/evals"
              }
            ]
          },
          {
            "id": "guardrails-security",
            "label": "Guardrails & Security",
            "level": "advanced",
            "type": "required",
            "description": "Prompt injection, jailbreaks, PII handling, and output filtering - the OWASP Top 10 for LLM apps.",
            "resources": [
              {
                "title": "OWASP - GenAI Security",
                "url": "https://genai.owasp.org"
              }
            ]
          },
          {
            "id": "observability-cost",
            "label": "Observability & Cost",
            "level": "advanced",
            "type": "good-to-know",
            "description": "Tracing chains, token budgets, caching, and latency - keeping the product fast and affordable.",
            "resources": [
              {
                "title": "LangSmith Docs",
                "url": "https://docs.smith.langchain.com"
              }
            ]
          },
          {
            "id": "deployment",
            "label": "Deploying AI Apps",
            "level": "advanced",
            "type": "required",
            "description": "Streaming APIs, rate limits, retries, and fallbacks - production plumbing around the model.",
            "resources": [
              {
                "title": "FastAPI",
                "url": "https://fastapi.tiangolo.com"
              }
            ]
          }
        ]
      }
    ]
  },
  "cyber-security": {
    "sections": [
      {
        "id": "it-foundations",
        "label": "IT Foundations",
        "nodes": [
          {
            "id": "networking",
            "label": "Networking",
            "level": "beginner",
            "type": "required",
            "description": "TCP/IP, DNS, subnetting, ports, and the OSI model - you can't defend what you don't understand.",
            "resources": [
              {
                "title": "Professor Messer - Network+",
                "url": "https://www.professormesser.com/network-plus/n10-009/n10-009-training-course/"
              },
              {
                "title": "roadmap.sh - Cyber Security",
                "url": "https://roadmap.sh/cyber-security"
              }
            ]
          },
          {
            "id": "operating-systems",
            "label": "Operating Systems",
            "level": "beginner",
            "type": "required",
            "description": "Windows and Linux internals: processes, permissions, the registry, and file systems.",
            "resources": [
              {
                "title": "Linux Journey",
                "url": "https://linuxjourney.com"
              }
            ]
          },
          {
            "id": "linux-cli",
            "label": "Linux & CLI",
            "level": "beginner",
            "type": "required",
            "description": "Command-line fluency and Kali Linux - the workbench for both offense and defense.",
            "resources": [
              {
                "title": "Kali Linux Docs",
                "url": "https://www.kali.org/docs/"
              }
            ]
          },
          {
            "id": "scripting",
            "label": "Scripting (Python)",
            "level": "beginner",
            "type": "required",
            "description": "Python and Bash to automate scans, parse logs, and build small tools.",
            "resources": [
              {
                "title": "Python Docs - Tutorial",
                "url": "https://docs.python.org/3/tutorial/"
              }
            ]
          }
        ]
      },
      {
        "id": "security-fundamentals",
        "label": "Security Fundamentals",
        "nodes": [
          {
            "id": "security-concepts",
            "label": "Security Concepts",
            "level": "beginner",
            "type": "required",
            "description": "CIA triad, defense in depth, least privilege, and threat modeling - the mental models of the field.",
            "resources": [
              {
                "title": "NIST - Cybersecurity Framework",
                "url": "https://www.nist.gov/cyberframework"
              }
            ]
          },
          {
            "id": "cryptography",
            "label": "Cryptography",
            "level": "intermediate",
            "type": "required",
            "description": "Symmetric/asymmetric encryption, hashing, TLS, and PKI - used correctly, not reinvented.",
            "resources": [
              {
                "title": "Crypto 101",
                "url": "https://www.crypto101.io"
              }
            ]
          },
          {
            "id": "web-security",
            "label": "Web Security (OWASP)",
            "level": "intermediate",
            "type": "required",
            "description": "The OWASP Top 10: injection, XSS, broken auth, SSRF - the most common real-world attacks.",
            "resources": [
              {
                "title": "OWASP Top 10",
                "url": "https://owasp.org/www-project-top-ten/"
              }
            ]
          },
          {
            "id": "identity-access",
            "label": "Identity & Access Management",
            "level": "intermediate",
            "type": "good-to-know",
            "description": "Authentication, authorization, MFA, and SSO - most breaches start with credentials.",
            "resources": [
              {
                "title": "NIST - Digital Identity Guidelines",
                "url": "https://pages.nist.gov/800-63-3/"
              }
            ]
          }
        ]
      },
      {
        "id": "offensive",
        "label": "Offensive Security",
        "nodes": [
          {
            "id": "penetration-testing",
            "label": "Penetration Testing",
            "level": "advanced",
            "type": "required",
            "description": "Recon, exploitation, and post-exploitation - thinking like an attacker to find gaps first.",
            "resources": [
              {
                "title": "TryHackMe",
                "url": "https://tryhackme.com"
              }
            ]
          },
          {
            "id": "vulnerability-assessment",
            "label": "Vulnerability Assessment",
            "level": "advanced",
            "type": "required",
            "description": "Scanning with Nmap and Nessus, CVSS scoring, and prioritizing what to fix first.",
            "resources": [
              {
                "title": "Nmap - Reference Guide",
                "url": "https://nmap.org/book/man.html"
              }
            ]
          },
          {
            "id": "security-tools",
            "label": "Security Tools",
            "level": "advanced",
            "type": "required",
            "description": "Wireshark, Burp Suite, Metasploit - the analyst's daily instruments for traffic and exploits.",
            "resources": [
              {
                "title": "Wireshark - User Guide",
                "url": "https://www.wireshark.org/docs/wsug_html_chunked/"
              }
            ]
          },
          {
            "id": "hands-on-labs",
            "label": "Hands-On Labs & CTFs",
            "level": "advanced",
            "type": "good-to-know",
            "description": "HackTheBox and picoCTF: practicing on legal, deliberately vulnerable targets.",
            "resources": [
              {
                "title": "Hack The Box",
                "url": "https://www.hackthebox.com"
              },
              {
                "title": "picoCTF",
                "url": "https://picoctf.org"
              }
            ]
          }
        ]
      },
      {
        "id": "defensive",
        "label": "Defensive Security",
        "nodes": [
          {
            "id": "siem",
            "label": "SIEM & Log Analysis",
            "level": "advanced",
            "type": "required",
            "description": "Splunk / ELK: correlating events across systems to catch attacks in progress.",
            "resources": [
              {
                "title": "Splunk - Free Fundamentals",
                "url": "https://www.splunk.com/en_us/training/free-courses/splunk-fundamentals-1.html"
              }
            ]
          },
          {
            "id": "incident-response",
            "label": "Incident Response",
            "level": "advanced",
            "type": "required",
            "description": "Detection, containment, eradication, and recovery - staying methodical while the pager screams.",
            "resources": [
              {
                "title": "SANS - Incident Handler's Handbook",
                "url": "https://www.sans.org/white-papers/33901/"
              }
            ]
          },
          {
            "id": "malware-analysis",
            "label": "Malware Analysis",
            "level": "advanced",
            "type": "good-to-know",
            "description": "Static and dynamic analysis in a sandbox to understand what a sample does.",
            "resources": [
              {
                "title": "Malware Unicorn - RE101",
                "url": "https://malwareunicorn.org/workshops/re101.html"
              }
            ]
          },
          {
            "id": "firewalls-ids",
            "label": "Firewalls & IDS/IPS",
            "level": "intermediate",
            "type": "required",
            "description": "Configuring perimeter and host defenses and tuning detection rules.",
            "resources": [
              {
                "title": "Snort Docs",
                "url": "https://docs.snort.org"
              }
            ]
          }
        ]
      },
      {
        "id": "professional",
        "label": "Cloud, Compliance & Certs",
        "nodes": [
          {
            "id": "cloud-security",
            "label": "Cloud Security",
            "level": "advanced",
            "type": "good-to-know",
            "description": "Securing AWS/Azure: IAM, network segmentation, and the shared-responsibility model.",
            "resources": [
              {
                "title": "AWS - Security Best Practices",
                "url": "https://docs.aws.amazon.com/security/"
              }
            ]
          },
          {
            "id": "governance-compliance",
            "label": "Governance & Compliance",
            "level": "advanced",
            "type": "good-to-know",
            "description": "GDPR, SOC 2, ISO 27001, and risk frameworks - security that satisfies auditors too.",
            "resources": [
              {
                "title": "ISO/IEC 27001",
                "url": "https://www.iso.org/standard/27001"
              }
            ]
          },
          {
            "id": "certifications",
            "label": "Certifications",
            "level": "intermediate",
            "type": "good-to-know",
            "description": "Security+, then CEH or OSCP - the credentials hiring managers screen for.",
            "resources": [
              {
                "title": "CompTIA Security+",
                "url": "https://www.comptia.org/certifications/security"
              }
            ]
          }
        ]
      }
    ]
  },
  "qa-engineer": {
    "sections": [
      {
        "id": "foundations",
        "label": "QA Foundations",
        "nodes": [
          {
            "id": "qa-fundamentals",
            "label": "QA Fundamentals",
            "level": "beginner",
            "type": "required",
            "description": "The QA mindset, quality vs testing, verification vs validation, and the cost of a late-caught bug.",
            "resources": [
              {
                "title": "Ministry of Testing",
                "url": "https://www.ministryoftesting.com"
              },
              {
                "title": "roadmap.sh - QA",
                "url": "https://roadmap.sh/qa"
              }
            ]
          },
          {
            "id": "sdlc",
            "label": "SDLC & Agile",
            "level": "beginner",
            "type": "required",
            "description": "Where testing fits across Waterfall, Agile, and shift-left - and working inside Scrum/Kanban.",
            "resources": [
              {
                "title": "Atlassian - Agile Coach",
                "url": "https://www.atlassian.com/agile"
              }
            ]
          },
          {
            "id": "test-design",
            "label": "Test Design Techniques",
            "level": "beginner",
            "type": "required",
            "description": "Boundary values, equivalence partitioning, and decision tables - finding more bugs with fewer cases.",
            "resources": [
              {
                "title": "ISTQB - Foundation Syllabus",
                "url": "https://www.istqb.org/certifications/certified-tester-foundation-level"
              }
            ]
          },
          {
            "id": "web-basics",
            "label": "HTML, CSS & JavaScript",
            "level": "beginner",
            "type": "good-to-know",
            "description": "Enough of the stack to read the DOM, write selectors, and understand what you're automating.",
            "resources": [
              {
                "title": "MDN - Learn Web Development",
                "url": "https://developer.mozilla.org/en-US/docs/Learn"
              }
            ]
          }
        ]
      },
      {
        "id": "manual-testing",
        "label": "Manual Testing",
        "nodes": [
          {
            "id": "test-cases",
            "label": "Test Cases & Scenarios",
            "level": "beginner",
            "type": "required",
            "description": "Writing clear, repeatable cases and organizing them into suites and traceability matrices.",
            "resources": [
              {
                "title": "Ministry of Testing - Dojo",
                "url": "https://www.ministryoftesting.com/dojo"
              }
            ]
          },
          {
            "id": "functional-testing",
            "label": "Functional Testing",
            "level": "beginner",
            "type": "required",
            "description": "Smoke, sanity, regression, and UAT - verifying the product does what it promises.",
            "resources": [
              {
                "title": "Ministry of Testing",
                "url": "https://www.ministryoftesting.com"
              }
            ]
          },
          {
            "id": "exploratory-testing",
            "label": "Exploratory Testing",
            "level": "intermediate",
            "type": "good-to-know",
            "description": "Simultaneous learning, design, and execution - finding what scripted tests miss.",
            "resources": [
              {
                "title": "Satisfice - Exploratory Testing",
                "url": "https://www.satisfice.com/exploratory-testing"
              }
            ]
          },
          {
            "id": "bug-reporting",
            "label": "Bug Reporting & JIRA",
            "level": "beginner",
            "type": "required",
            "description": "Reproducible reports, severity vs priority, and managing the defect lifecycle in JIRA.",
            "resources": [
              {
                "title": "Atlassian - JIRA Guides",
                "url": "https://www.atlassian.com/software/jira/guides"
              }
            ]
          }
        ]
      },
      {
        "id": "automation",
        "label": "Test Automation",
        "nodes": [
          {
            "id": "programming-for-testing",
            "label": "Programming (Python/Java)",
            "level": "intermediate",
            "type": "required",
            "description": "A language for automation - enough Python or Java to write maintainable test code.",
            "resources": [
              {
                "title": "Python Docs - Tutorial",
                "url": "https://docs.python.org/3/tutorial/"
              }
            ]
          },
          {
            "id": "selenium",
            "label": "Selenium",
            "level": "intermediate",
            "type": "required",
            "description": "Browser automation and the Page Object Model - the long-standing UI automation standard.",
            "resources": [
              {
                "title": "Selenium Docs",
                "url": "https://www.selenium.dev/documentation/"
              }
            ]
          },
          {
            "id": "cypress-playwright",
            "label": "Cypress & Playwright",
            "level": "intermediate",
            "type": "required",
            "description": "Modern, fast, flake-resistant end-to-end testing with auto-waiting and tracing.",
            "resources": [
              {
                "title": "Playwright Docs",
                "url": "https://playwright.dev/docs/intro"
              },
              {
                "title": "Cypress Docs",
                "url": "https://docs.cypress.io"
              }
            ]
          },
          {
            "id": "api-testing",
            "label": "API Testing",
            "level": "intermediate",
            "type": "required",
            "description": "Postman and REST Assured: validating endpoints, contracts, and status codes below the UI.",
            "resources": [
              {
                "title": "Postman - Learning Center",
                "url": "https://learning.postman.com"
              }
            ]
          },
          {
            "id": "unit-integration-frameworks",
            "label": "Test Frameworks",
            "level": "intermediate",
            "type": "good-to-know",
            "description": "JUnit, TestNG, and pytest: structuring, parameterizing, and reporting automated tests.",
            "resources": [
              {
                "title": "pytest Docs",
                "url": "https://docs.pytest.org"
              }
            ]
          }
        ]
      },
      {
        "id": "specialized",
        "label": "Specialized Testing",
        "nodes": [
          {
            "id": "performance-testing",
            "label": "Performance & Load Testing",
            "level": "advanced",
            "type": "good-to-know",
            "description": "JMeter and k6: load, stress, and soak tests to find where the system buckles.",
            "resources": [
              {
                "title": "k6 Docs",
                "url": "https://grafana.com/docs/k6/latest/"
              }
            ]
          },
          {
            "id": "security-testing",
            "label": "Security Testing",
            "level": "advanced",
            "type": "good-to-know",
            "description": "Basic OWASP checks and using tools like OWASP ZAP as part of QA.",
            "resources": [
              {
                "title": "OWASP ZAP",
                "url": "https://www.zaproxy.org"
              }
            ]
          },
          {
            "id": "accessibility-testing",
            "label": "Accessibility Testing",
            "level": "advanced",
            "type": "good-to-know",
            "description": "WCAG conformance with axe and WAVE - quality includes users with disabilities.",
            "resources": [
              {
                "title": "Deque - axe",
                "url": "https://www.deque.com/axe/"
              }
            ]
          },
          {
            "id": "mobile-testing",
            "label": "Mobile Testing",
            "level": "advanced",
            "type": "optional",
            "description": "Appium and device farms: automating tests across real iOS and Android devices.",
            "resources": [
              {
                "title": "Appium Docs",
                "url": "https://appium.io/docs/en/latest/"
              }
            ]
          }
        ]
      },
      {
        "id": "cicd-quality",
        "label": "CI/CD & Quality Engineering",
        "nodes": [
          {
            "id": "version-control",
            "label": "Git & Version Control",
            "level": "beginner",
            "type": "required",
            "description": "Managing test code alongside the app - branches, reviews, and shared ownership of quality.",
            "resources": [
              {
                "title": "Pro Git (free book)",
                "url": "https://git-scm.com/book"
              }
            ]
          },
          {
            "id": "ci-cd-integration",
            "label": "CI/CD Integration",
            "level": "advanced",
            "type": "required",
            "description": "Running suites on every push, gating merges on green, and parallelizing for speed.",
            "resources": [
              {
                "title": "GitHub Actions Docs",
                "url": "https://docs.github.com/actions"
              }
            ]
          },
          {
            "id": "reporting-monitoring",
            "label": "Reporting & Monitoring",
            "level": "advanced",
            "type": "good-to-know",
            "description": "Test dashboards, flakiness tracking, and production monitoring to close the quality loop.",
            "resources": [
              {
                "title": "Allure Report",
                "url": "https://allurereport.org"
              }
            ]
          }
        ]
      }
    ]
  },
  "game-dev": {
    "sections": [
      {
        "id": "foundations",
        "label": "Programming Foundations",
        "nodes": [
          {
            "id": "programming-language",
            "label": "C# / C++",
            "level": "beginner",
            "type": "required",
            "description": "Game languages: C# for Unity, C++ for Unreal - memory, performance, and object-oriented design.",
            "resources": [
              {
                "title": "Microsoft - C# Docs",
                "url": "https://learn.microsoft.com/en-us/dotnet/csharp/"
              },
              {
                "title": "roadmap.sh - Game Developer",
                "url": "https://roadmap.sh/game-developer"
              }
            ]
          },
          {
            "id": "game-math",
            "label": "Game Mathematics",
            "level": "beginner",
            "type": "required",
            "description": "Vectors, matrices, quaternions, and trigonometry - the math behind movement, cameras, and rotation.",
            "resources": [
              {
                "title": "Immersive Math - Linear Algebra",
                "url": "https://immersivemath.com/ila/"
              }
            ]
          },
          {
            "id": "version-control",
            "label": "Git & Version Control",
            "level": "beginner",
            "type": "required",
            "description": "Git with LFS for large binary assets - version control that doesn't choke on textures.",
            "resources": [
              {
                "title": "Git LFS",
                "url": "https://git-lfs.com"
              }
            ]
          },
          {
            "id": "programming-patterns",
            "label": "Game Programming Patterns",
            "level": "intermediate",
            "type": "good-to-know",
            "description": "Game loop, component systems, state machines, and object pooling.",
            "resources": [
              {
                "title": "Game Programming Patterns (free book)",
                "url": "https://gameprogrammingpatterns.com"
              }
            ]
          }
        ]
      },
      {
        "id": "engines",
        "label": "Game Engines",
        "nodes": [
          {
            "id": "unity",
            "label": "Unity",
            "level": "intermediate",
            "type": "required",
            "description": "The most popular engine: GameObjects, components, prefabs, physics, and the asset pipeline.",
            "resources": [
              {
                "title": "Unity - Learn",
                "url": "https://learn.unity.com"
              }
            ]
          },
          {
            "id": "unreal",
            "label": "Unreal Engine",
            "level": "intermediate",
            "type": "good-to-know",
            "description": "AAA-grade rendering with Blueprints and C++ - the go-to for high-fidelity 3D.",
            "resources": [
              {
                "title": "Unreal Engine - Learning",
                "url": "https://dev.epicgames.com/community/unreal-engine/learning"
              }
            ]
          },
          {
            "id": "godot",
            "label": "Godot",
            "level": "intermediate",
            "type": "optional",
            "description": "Open-source engine with GDScript - lightweight and increasingly popular for indies.",
            "resources": [
              {
                "title": "Godot Docs",
                "url": "https://docs.godotengine.org"
              }
            ]
          },
          {
            "id": "scene-management",
            "label": "Scenes & Asset Pipeline",
            "level": "intermediate",
            "type": "required",
            "description": "Scenes, prefabs, importing models and audio, and organizing a project that scales.",
            "resources": [
              {
                "title": "Unity - Asset Workflow",
                "url": "https://docs.unity3d.com/Manual/AssetWorkflow.html"
              }
            ]
          }
        ]
      },
      {
        "id": "core-systems",
        "label": "Core Game Systems",
        "nodes": [
          {
            "id": "game-physics",
            "label": "Physics & Collision",
            "level": "intermediate",
            "type": "required",
            "description": "Rigid bodies, colliders, raycasts, and collision detection (AABB, broad/narrow phase).",
            "resources": [
              {
                "title": "Unity - Physics",
                "url": "https://docs.unity3d.com/Manual/PhysicsSection.html"
              }
            ]
          },
          {
            "id": "gameplay-programming",
            "label": "Gameplay Programming",
            "level": "intermediate",
            "type": "required",
            "description": "Input handling, character controllers, camera systems, and game state management.",
            "resources": [
              {
                "title": "Unity - Learn",
                "url": "https://learn.unity.com"
              }
            ]
          },
          {
            "id": "game-ai",
            "label": "Game AI",
            "level": "advanced",
            "type": "good-to-know",
            "description": "Pathfinding (A*), navmeshes, behavior trees, and finite state machines for NPCs.",
            "resources": [
              {
                "title": "Red Blob Games - Pathfinding",
                "url": "https://www.redblobgames.com/pathfinding/a-star/introduction.html"
              }
            ]
          },
          {
            "id": "ui-audio",
            "label": "UI & Audio",
            "level": "intermediate",
            "type": "good-to-know",
            "description": "HUDs, menus, and adaptive audio - the polish players feel but rarely notice.",
            "resources": [
              {
                "title": "Unity - UI Toolkit",
                "url": "https://docs.unity3d.com/Manual/UIElements.html"
              }
            ]
          }
        ]
      },
      {
        "id": "graphics",
        "label": "Graphics & Rendering",
        "nodes": [
          {
            "id": "computer-graphics",
            "label": "Computer Graphics",
            "level": "advanced",
            "type": "good-to-know",
            "description": "The rendering pipeline, rasterization, lighting, and shadow techniques.",
            "resources": [
              {
                "title": "LearnOpenGL",
                "url": "https://learnopengl.com"
              }
            ]
          },
          {
            "id": "shaders",
            "label": "Shaders",
            "level": "advanced",
            "type": "good-to-know",
            "description": "Vertex and fragment shaders (HLSL/GLSL) and shader graphs for custom visual effects.",
            "resources": [
              {
                "title": "The Book of Shaders",
                "url": "https://thebookofshaders.com"
              }
            ]
          },
          {
            "id": "graphics-api",
            "label": "Graphics APIs",
            "level": "advanced",
            "type": "optional",
            "description": "OpenGL, Vulkan, and DirectX - what engines talk to underneath.",
            "resources": [
              {
                "title": "LearnOpenGL",
                "url": "https://learnopengl.com"
              }
            ]
          }
        ]
      },
      {
        "id": "shipping",
        "label": "Optimization & Shipping",
        "nodes": [
          {
            "id": "performance-optimization",
            "label": "Performance Optimization",
            "level": "advanced",
            "type": "required",
            "description": "Profiling frame time, draw calls, and memory to hold a steady 60fps.",
            "resources": [
              {
                "title": "Unity - Profiler",
                "url": "https://docs.unity3d.com/Manual/Profiler.html"
              }
            ]
          },
          {
            "id": "game-design",
            "label": "Game Design Basics",
            "level": "intermediate",
            "type": "good-to-know",
            "description": "Core loops, balancing, and playtesting - the difference between a tech demo and a game.",
            "resources": [
              {
                "title": "The Art of Game Design",
                "url": "https://schellgames.com/art-of-game-design"
              }
            ]
          },
          {
            "id": "building-publishing",
            "label": "Building & Publishing",
            "level": "advanced",
            "type": "required",
            "description": "Platform builds, storefronts (Steam, itch.io, consoles), and release logistics.",
            "resources": [
              {
                "title": "Steamworks Documentation",
                "url": "https://partner.steamgames.com/doc/home"
              }
            ]
          }
        ]
      }
    ]
  },
  "technical-writer": {
    "sections": [
      {
        "id": "foundations",
        "label": "Foundations",
        "nodes": [
          {
            "id": "what-is-tech-writing",
            "label": "What Is Technical Writing?",
            "level": "beginner",
            "type": "required",
            "description": "Turning complex topics into clear, accurate, task-focused content different audiences can act on.",
            "resources": [
              {
                "title": "Google - Technical Writing Courses",
                "url": "https://developers.google.com/tech-writing"
              },
              {
                "title": "roadmap.sh - Technical Writer",
                "url": "https://roadmap.sh/technical-writer"
              }
            ]
          },
          {
            "id": "writing-fundamentals",
            "label": "Writing Fundamentals",
            "level": "beginner",
            "type": "required",
            "description": "Grammar, plain language, active voice, and structure - clarity is the whole job.",
            "resources": [
              {
                "title": "Google - Technical Writing One",
                "url": "https://developers.google.com/tech-writing/one"
              }
            ]
          },
          {
            "id": "audience-analysis",
            "label": "Audience & Personas",
            "level": "beginner",
            "type": "required",
            "description": "Writing for the reader's goals and expertise - a beginner tutorial and an API reference aren't the same.",
            "resources": [
              {
                "title": "Write the Docs - Guide",
                "url": "https://www.writethedocs.org/guide/"
              }
            ]
          },
          {
            "id": "style-guides",
            "label": "Style Guides",
            "level": "beginner",
            "type": "good-to-know",
            "description": "Following (and building) style guides like Microsoft's or Google's for consistent voice.",
            "resources": [
              {
                "title": "Google - Developer Documentation Style Guide",
                "url": "https://developers.google.com/style"
              }
            ]
          }
        ]
      },
      {
        "id": "tooling",
        "label": "Tooling",
        "nodes": [
          {
            "id": "markdown",
            "label": "Markdown",
            "level": "beginner",
            "type": "required",
            "description": "The lingua franca of docs: headings, code blocks, tables, and links.",
            "resources": [
              {
                "title": "CommonMark",
                "url": "https://commonmark.org/help/"
              }
            ]
          },
          {
            "id": "git-version-control",
            "label": "Git & Version Control",
            "level": "beginner",
            "type": "required",
            "description": "Docs-as-code: writing in the repo, pull requests, and reviews alongside engineers.",
            "resources": [
              {
                "title": "Pro Git (free book)",
                "url": "https://git-scm.com/book"
              }
            ]
          },
          {
            "id": "docs-generators",
            "label": "Docs Generators",
            "level": "intermediate",
            "type": "required",
            "description": "Static-site tools like Docusaurus, MkDocs, and Sphinx for versioned, searchable docs sites.",
            "resources": [
              {
                "title": "Docusaurus",
                "url": "https://docusaurus.io"
              }
            ]
          },
          {
            "id": "diagrams-media",
            "label": "Diagrams & Screenshots",
            "level": "intermediate",
            "type": "good-to-know",
            "description": "Diagrams-as-code (Mermaid) and clean screenshots that explain faster than paragraphs.",
            "resources": [
              {
                "title": "Mermaid Docs",
                "url": "https://mermaid.js.org"
              }
            ]
          }
        ]
      },
      {
        "id": "content-types",
        "label": "Types of Content",
        "nodes": [
          {
            "id": "developer-docs",
            "label": "Developer Documentation",
            "level": "intermediate",
            "type": "required",
            "description": "Tutorials, how-to guides, concepts, and reference - the four modes of the Diátaxis framework.",
            "resources": [
              {
                "title": "Diátaxis",
                "url": "https://diataxis.fr"
              }
            ]
          },
          {
            "id": "api-documentation",
            "label": "API Documentation",
            "level": "intermediate",
            "type": "required",
            "description": "Endpoint references, request/response examples, and OpenAPI-driven docs developers can copy-paste.",
            "resources": [
              {
                "title": "Swagger - OpenAPI",
                "url": "https://swagger.io/docs/specification/about/"
              }
            ]
          },
          {
            "id": "tutorials-howtos",
            "label": "Tutorials & How-To Guides",
            "level": "intermediate",
            "type": "required",
            "description": "Step-by-step content that gets a reader from zero to a working result without frustration.",
            "resources": [
              {
                "title": "Write the Docs - Guide",
                "url": "https://www.writethedocs.org/guide/"
              }
            ]
          },
          {
            "id": "release-notes",
            "label": "Release Notes & Changelogs",
            "level": "intermediate",
            "type": "good-to-know",
            "description": "Communicating what changed, why it matters, and any migration steps.",
            "resources": [
              {
                "title": "Keep a Changelog",
                "url": "https://keepachangelog.com"
              }
            ]
          }
        ]
      },
      {
        "id": "research-collab",
        "label": "Research & Collaboration",
        "nodes": [
          {
            "id": "content-research",
            "label": "Content Research",
            "level": "intermediate",
            "type": "required",
            "description": "Interviewing engineers, reading source and specs, and testing the product to document it accurately.",
            "resources": [
              {
                "title": "Write the Docs - Guide",
                "url": "https://www.writethedocs.org/guide/"
              }
            ]
          },
          {
            "id": "information-architecture",
            "label": "Information Architecture",
            "level": "intermediate",
            "type": "required",
            "description": "Organizing docs so readers find answers fast: navigation, structure, and findability.",
            "resources": [
              {
                "title": "NN/g - Information Architecture",
                "url": "https://www.nngroup.com/topic/information-architecture/"
              }
            ]
          },
          {
            "id": "editing-review",
            "label": "Editing & Review",
            "level": "intermediate",
            "type": "required",
            "description": "Self-editing, peer review, and docs linters (Vale) to keep quality high at volume.",
            "resources": [
              {
                "title": "Vale - Linter",
                "url": "https://vale.sh"
              }
            ]
          }
        ]
      },
      {
        "id": "growth",
        "label": "SEO, Metrics & Growth",
        "nodes": [
          {
            "id": "content-seo",
            "label": "Content SEO",
            "level": "advanced",
            "type": "good-to-know",
            "description": "Keywords, titles, and structure so the right docs surface in search when developers need them.",
            "resources": [
              {
                "title": "Google - SEO Starter Guide",
                "url": "https://developers.google.com/search/docs/fundamentals/seo-starter-guide"
              }
            ]
          },
          {
            "id": "content-metrics",
            "label": "Content Metrics",
            "level": "advanced",
            "type": "good-to-know",
            "description": "Analytics, feedback widgets, and search logs to find gaps and measure what docs actually help.",
            "resources": [
              {
                "title": "Write the Docs - Metrics",
                "url": "https://www.writethedocs.org/guide/measuring/"
              }
            ]
          },
          {
            "id": "devrel",
            "label": "Developer Relations",
            "level": "advanced",
            "type": "optional",
            "description": "Where technical writing meets advocacy: blogging, talks, and community support.",
            "resources": [
              {
                "title": "developer-relations resources",
                "url": "https://developerrelations.com"
              }
            ]
          }
        ]
      }
    ]
  },
  "software-architect": {
    "sections": [
      {
        "id": "foundations",
        "label": "Engineering Foundation",
        "nodes": [
          {
            "id": "what-is-architecture",
            "label": "What Is Software Architecture?",
            "level": "intermediate",
            "type": "required",
            "description": "Levels of architecture (application, solution, enterprise) and the architect's responsibilities.",
            "resources": [
              {
                "title": "roadmap.sh - Software Architect",
                "url": "https://roadmap.sh/software-design-architecture"
              },
              {
                "title": "Fundamentals of Software Architecture",
                "url": "https://www.oreilly.com/library/view/fundamentals-of-software/9781492043447/"
              }
            ]
          },
          {
            "id": "programming-depth",
            "label": "Deep Programming Experience",
            "level": "intermediate",
            "type": "required",
            "description": "Years of hands-on coding across paradigms - you can't architect what you've never built.",
            "resources": [
              {
                "title": "roadmap.sh - Backend",
                "url": "https://roadmap.sh/backend"
              }
            ]
          },
          {
            "id": "data-structures-algorithms",
            "label": "Data Structures & Algorithms",
            "level": "intermediate",
            "type": "required",
            "description": "Complexity analysis and the trade-offs behind performance decisions at scale.",
            "resources": [
              {
                "title": "The Algorithm Design Manual",
                "url": "https://www.algorist.com"
              }
            ]
          }
        ]
      },
      {
        "id": "design-principles",
        "label": "Design & Patterns",
        "nodes": [
          {
            "id": "solid-principles",
            "label": "SOLID & Clean Code",
            "level": "intermediate",
            "type": "required",
            "description": "SOLID, DRY, KISP, and separation of concerns - the principles behind maintainable systems.",
            "resources": [
              {
                "title": "Refactoring.Guru - Design Principles",
                "url": "https://refactoring.guru/design-patterns"
              }
            ]
          },
          {
            "id": "design-patterns",
            "label": "Design Patterns",
            "level": "intermediate",
            "type": "required",
            "description": "Creational, structural, and behavioral patterns - and the wisdom not to over-apply them.",
            "resources": [
              {
                "title": "Refactoring.Guru - Design Patterns",
                "url": "https://refactoring.guru/design-patterns/catalog"
              }
            ]
          },
          {
            "id": "architectural-patterns",
            "label": "Architectural Patterns",
            "level": "advanced",
            "type": "required",
            "description": "Layered, hexagonal, MVC, event-driven, CQRS - structuring whole systems, not just classes.",
            "resources": [
              {
                "title": "Microsoft - Architecture Styles",
                "url": "https://learn.microsoft.com/en-us/azure/architecture/guide/architecture-styles/"
              }
            ]
          },
          {
            "id": "domain-driven-design",
            "label": "Domain-Driven Design",
            "level": "advanced",
            "type": "good-to-know",
            "description": "Bounded contexts, aggregates, and a ubiquitous language that maps software to the business.",
            "resources": [
              {
                "title": "DDD Reference (Evans)",
                "url": "https://www.domainlanguage.com/ddd/reference/"
              }
            ]
          }
        ]
      },
      {
        "id": "distributed-systems",
        "label": "Distributed Systems",
        "nodes": [
          {
            "id": "microservices",
            "label": "Microservices",
            "level": "advanced",
            "type": "required",
            "description": "Service boundaries, inter-service communication, sagas, and the monolith-vs-microservices trade-off.",
            "resources": [
              {
                "title": "microservices.io",
                "url": "https://microservices.io/patterns/index.html"
              }
            ]
          },
          {
            "id": "scalability",
            "label": "Scalability & Availability",
            "level": "advanced",
            "type": "required",
            "description": "Horizontal scaling, load balancing, replication, and CAP/PACELC trade-offs.",
            "resources": [
              {
                "title": "System Design Primer",
                "url": "https://github.com/donnemartin/system-design-primer"
              }
            ]
          },
          {
            "id": "data-architecture",
            "label": "Data Architecture",
            "level": "advanced",
            "type": "required",
            "description": "SQL vs NoSQL, sharding, event sourcing, ETL, and data warehouses - where the state lives.",
            "resources": [
              {
                "title": "Designing Data-Intensive Applications",
                "url": "https://dataintensive.net"
              }
            ]
          },
          {
            "id": "apis-integration",
            "label": "APIs & Integration",
            "level": "advanced",
            "type": "required",
            "description": "REST, gRPC, GraphQL, message brokers, and service meshes - how systems talk reliably.",
            "resources": [
              {
                "title": "Microsoft - API Design",
                "url": "https://learn.microsoft.com/en-us/azure/architecture/best-practices/api-design"
              }
            ]
          }
        ]
      },
      {
        "id": "quality-attributes",
        "label": "Cross-Cutting Concerns",
        "nodes": [
          {
            "id": "security-architecture",
            "label": "Security Architecture",
            "level": "advanced",
            "type": "required",
            "description": "AuthN/AuthZ, zero-trust, threat modeling, and secure defaults baked into the design.",
            "resources": [
              {
                "title": "OWASP - Application Security",
                "url": "https://owasp.org/www-project-application-security-verification-standard/"
              }
            ]
          },
          {
            "id": "cloud-infrastructure",
            "label": "Cloud & Infrastructure",
            "level": "advanced",
            "type": "required",
            "description": "Cloud services, Kubernetes, Docker, and infrastructure-as-code as first-class design material.",
            "resources": [
              {
                "title": "AWS - Well-Architected",
                "url": "https://aws.amazon.com/architecture/well-architected/"
              },
              {
                "title": "Kubernetes Docs",
                "url": "https://kubernetes.io/docs/home/"
              }
            ]
          },
          {
            "id": "observability",
            "label": "Observability & Resilience",
            "level": "advanced",
            "type": "good-to-know",
            "description": "Designing for failure: retries, circuit breakers, tracing, and graceful degradation.",
            "resources": [
              {
                "title": "Azure - Reliability Patterns",
                "url": "https://learn.microsoft.com/en-us/azure/architecture/framework/resiliency/reliability-patterns"
              }
            ]
          },
          {
            "id": "performance",
            "label": "Performance Engineering",
            "level": "advanced",
            "type": "good-to-know",
            "description": "Caching layers, profiling, and capacity planning to meet latency and throughput targets.",
            "resources": [
              {
                "title": "System Design Primer",
                "url": "https://github.com/donnemartin/system-design-primer"
              }
            ]
          }
        ]
      },
      {
        "id": "leadership",
        "label": "Leadership & Delivery",
        "nodes": [
          {
            "id": "documentation-communication",
            "label": "Documentation & Communication",
            "level": "advanced",
            "type": "required",
            "description": "ADRs, C4 diagrams, and RFCs - writing decisions down so teams build the same system.",
            "resources": [
              {
                "title": "C4 Model",
                "url": "https://c4model.com"
              }
            ]
          },
          {
            "id": "technical-leadership",
            "label": "Technical Leadership",
            "level": "advanced",
            "type": "required",
            "description": "Mentoring, coaching, and setting technical direction across teams by influence, not decree.",
            "resources": [
              {
                "title": "The Staff Engineer's Path",
                "url": "https://staffeng.com/book"
              }
            ]
          },
          {
            "id": "trade-off-analysis",
            "label": "Trade-off Analysis",
            "level": "advanced",
            "type": "required",
            "description": "Evaluating options against constraints - cost, time, risk - and defending the call with reasons.",
            "resources": [
              {
                "title": "Architecture Decision Records",
                "url": "https://adr.github.io"
              }
            ]
          },
          {
            "id": "estimation-risk",
            "label": "Estimation & Risk",
            "level": "advanced",
            "type": "good-to-know",
            "description": "Identifying, assessing, and mitigating technical risk before it becomes an incident.",
            "resources": [
              {
                "title": "Microsoft - Well-Architected",
                "url": "https://learn.microsoft.com/en-us/azure/well-architected/"
              }
            ]
          }
        ]
      }
    ]
  }
}
