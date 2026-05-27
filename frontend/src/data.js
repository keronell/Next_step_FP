export const QUESTIONS = [
  {
    id: 'q1',
    category: 'skills',
    text: 'How comfortable are you writing code from scratch?',
    options: [
      { label: 'Never tried it', value: 0 },
      { label: 'A little — copy-paste territory', value: 1 },
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
    text: 'When you encounter a dataset, you feel…',
    options: [
      { label: 'Curious — what story is hiding here?', value: 3 },
      { label: 'Interested if it helps my project', value: 2 },
      { label: 'Indifferent — just give me the answer', value: 1 },
      { label: 'Overwhelmed — numbers aren\'t my thing', value: 0 },
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
    text: 'Which of these tools sounds most appealing?',
    options: [
      { label: 'Figma / design systems', value: 0 },
      { label: 'React / TypeScript / APIs', value: 1 },
      { label: 'Python / Jupyter / SQL', value: 2 },
      { label: 'Kubernetes / Terraform / CI pipelines', value: 3 },
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
    text: 'How drawn are you to visual design?',
    options: [
      { label: 'It\'s my happy place', value: 3 },
      { label: 'I appreciate it but don\'t lead it', value: 2 },
      { label: 'Functional is fine — polish is bonus', value: 1 },
      { label: 'Not at all my area', value: 0 },
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
]

export const CAREERS = [
  {
    id: 'frontend',
    title: 'Frontend Developer',
    description: 'Craft interactive, accessible web interfaces that delight users. You live at the intersection of design and engineering.',
    keySkills: ['React', 'CSS', 'TypeScript', 'Accessibility', 'Performance'],
    icon: 'Monitor',
    roadmapKey: 'frontend',
  },
  {
    id: 'backend',
    title: 'Backend Engineer',
    description: 'Build the systems and APIs that power products at scale. You love elegant architecture and rock-solid reliability.',
    keySkills: ['Node.js', 'Databases', 'APIs', 'System Design', 'Security'],
    icon: 'Server',
    roadmapKey: 'backend',
  },
  {
    id: 'data-science',
    title: 'Data Scientist',
    description: 'Transform raw data into insights that steer strategy. You turn numbers into narratives decision-makers can act on.',
    keySkills: ['Python', 'Statistics', 'Machine Learning', 'SQL', 'Data Viz'],
    icon: 'BarChart2',
    roadmapKey: 'data-science',
  },
  {
    id: 'devops',
    title: 'DevOps Engineer',
    description: 'Own the platform that every engineer depends on. You thrive on automation, reliability, and making deployment invisible.',
    keySkills: ['Kubernetes', 'CI/CD', 'Cloud', 'Terraform', 'Monitoring'],
    icon: 'Layers',
    roadmapKey: 'devops',
  },
  {
    id: 'product-manager',
    title: 'Product Manager',
    description: 'Define what gets built and why. You bridge user needs, business goals, and technical reality into a coherent vision.',
    keySkills: ['Strategy', 'User Research', 'Roadmapping', 'Metrics', 'Storytelling'],
    icon: 'Compass',
    roadmapKey: 'product-manager',
  },
  {
    id: 'ux-designer',
    title: 'UX Designer',
    description: 'Champion the user at every step. You research, prototype, and validate experiences that feel intuitive and beautiful.',
    keySkills: ['Figma', 'User Research', 'Prototyping', 'Design Systems', 'Usability Testing'],
    icon: 'Pen',
    roadmapKey: 'ux-designer',
  },
]

// Weights: for each career, how much each question answer contributes.
// Answer values are 0-3. This maps career × question → weight multiplier.
// Score = sum of (answerValue × weight). Normalized to % of max possible.
const WEIGHTS = {
  frontend:          { q1: 2, q2: 3, q3: 0, q4: 2, q5: 2, q6: 1, q7: 3, q8: 1, q9: 2, q10: 1 },
  backend:           { q1: 3, q2: 2, q3: 1, q4: 2, q5: 2, q6: 2, q7: 2, q8: 2, q9: 0, q10: 2 },
  'data-science':    { q1: 1, q2: 1, q3: 3, q4: 1, q5: 1, q6: 2, q7: 3, q8: 2, q9: 0, q10: 2 },
  devops:            { q1: 2, q2: 1, q3: 1, q4: 2, q5: 2, q6: 3, q7: 2, q8: 2, q9: 0, q10: 3 },
  'product-manager': { q1: 0, q2: 0, q3: 2, q4: 1, q5: 3, q6: 1, q7: 0, q8: 3, q9: 1, q10: 1 },
  'ux-designer':     { q1: 1, q2: 0, q3: 0, q4: 1, q5: 1, q6: 1, q7: 0, q8: 1, q9: 3, q10: 1 },
}

// Special bonus rules: certain answer values on certain questions bonus specific careers.
// q2: 0=visual→ux+2,frontend+1 | q7: 0=figma→ux+3 | q5: 0=product→pm+3
const BONUSES = [
  { qId: 'q2', answerValue: 0, careerId: 'ux-designer', bonus: 3 },
  { qId: 'q2', answerValue: 0, careerId: 'frontend', bonus: 1 },
  { qId: 'q7', answerValue: 0, careerId: 'ux-designer', bonus: 3 },
  { qId: 'q5', answerValue: 0, careerId: 'product-manager', bonus: 3 },
  { qId: 'q8', answerValue: 0, careerId: 'product-manager', bonus: 2 },
  { qId: 'q9', answerValue: 3, careerId: 'ux-designer', bonus: 2 },
  { qId: 'q9', answerValue: 3, careerId: 'frontend', bonus: 1 },
  { qId: 'q2', answerValue: 3, careerId: 'devops', bonus: 2 },
  { qId: 'q7', answerValue: 3, careerId: 'devops', bonus: 3 },
  { qId: 'q4', answerValue: 3, careerId: 'devops', bonus: 2 },
]

export function computeResults(answers) {
  const maxPossibleBase = 3 * 3 * 10 // max answer (3) × max weight (3) × 10 questions

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

export const ROADMAPS = {
  frontend: {
    nodes: [
      {
        id: 'html-css',
        label: 'HTML & CSS',
        level: 'beginner',
        description: 'Learn semantic HTML5 and modern CSS: flexbox, grid, and custom properties.',
        resource: { title: 'MDN Web Docs — HTML', url: 'https://developer.mozilla.org/en-US/docs/Web/HTML' },
        x: 400, y: 60, parentId: null,
      },
      {
        id: 'js-basics',
        label: 'JavaScript',
        level: 'beginner',
        description: 'Core JS: variables, functions, async/await, and DOM manipulation.',
        resource: { title: 'javascript.info', url: 'https://javascript.info' },
        x: 400, y: 160, parentId: 'html-css',
      },
      {
        id: 'react',
        label: 'React',
        level: 'intermediate',
        description: 'Component model, hooks (useState, useEffect, useContext), and state management.',
        resource: { title: 'React Docs', url: 'https://react.dev' },
        x: 240, y: 280, parentId: 'js-basics',
      },
      {
        id: 'typescript',
        label: 'TypeScript',
        level: 'intermediate',
        description: 'Static typing for scalable codebases. Types, interfaces, generics.',
        resource: { title: 'TypeScript Handbook', url: 'https://www.typescriptlang.org/docs/' },
        x: 560, y: 280, parentId: 'js-basics',
      },
      {
        id: 'testing',
        label: 'Testing',
        level: 'intermediate',
        description: 'Unit and integration tests with Vitest and React Testing Library.',
        resource: { title: 'Vitest Docs', url: 'https://vitest.dev' },
        x: 240, y: 400, parentId: 'react',
      },
      {
        id: 'performance',
        label: 'Performance',
        level: 'advanced',
        description: 'Core Web Vitals, code splitting, lazy loading, and bundle optimization.',
        resource: { title: 'web.dev Performance', url: 'https://web.dev/performance/' },
        x: 560, y: 400, parentId: 'typescript',
      },
      {
        id: 'advanced-patterns',
        label: 'Advanced Patterns',
        level: 'advanced',
        description: 'Render optimization, compound components, custom hooks, and design systems.',
        resource: { title: 'patterns.dev', url: 'https://www.patterns.dev' },
        x: 400, y: 500, parentId: 'testing',
      },
    ],
  },
  backend: {
    nodes: [
      {
        id: 'programming',
        label: 'Programming Basics',
        level: 'beginner',
        description: 'Pick a language: Node.js, Python, or Go. Learn data structures and algorithms.',
        resource: { title: 'The Odin Project', url: 'https://www.theodinproject.com' },
        x: 400, y: 60, parentId: null,
      },
      {
        id: 'databases',
        label: 'Databases',
        level: 'beginner',
        description: 'Relational (PostgreSQL) and NoSQL (MongoDB). SQL fundamentals.',
        resource: { title: 'PostgreSQL Tutorial', url: 'https://www.postgresqltutorial.com' },
        x: 400, y: 160, parentId: 'programming',
      },
      {
        id: 'apis',
        label: 'REST & GraphQL',
        level: 'intermediate',
        description: 'Design and build APIs: REST principles, authentication, rate limiting.',
        resource: { title: 'REST API Tutorial', url: 'https://restfulapi.net' },
        x: 240, y: 280, parentId: 'databases',
      },
      {
        id: 'auth',
        label: 'Auth & Security',
        level: 'intermediate',
        description: 'JWT, OAuth2, session management, and OWASP Top 10 vulnerabilities.',
        resource: { title: 'OWASP Top 10', url: 'https://owasp.org/www-project-top-ten/' },
        x: 560, y: 280, parentId: 'databases',
      },
      {
        id: 'caching',
        label: 'Caching & Queues',
        level: 'intermediate',
        description: 'Redis for caching, message queues (RabbitMQ / BullMQ) for async work.',
        resource: { title: 'Redis Docs', url: 'https://redis.io/docs/' },
        x: 240, y: 400, parentId: 'apis',
      },
      {
        id: 'system-design',
        label: 'System Design',
        level: 'advanced',
        description: 'Scalability, load balancing, microservices, and distributed systems.',
        resource: { title: 'System Design Primer', url: 'https://github.com/donnemartin/system-design-primer' },
        x: 560, y: 400, parentId: 'auth',
      },
      {
        id: 'observability',
        label: 'Observability',
        level: 'advanced',
        description: 'Structured logging, distributed tracing (OpenTelemetry), and alerting.',
        resource: { title: 'OpenTelemetry Docs', url: 'https://opentelemetry.io/docs/' },
        x: 400, y: 500, parentId: 'caching',
      },
    ],
  },
  'data-science': {
    nodes: [
      {
        id: 'python',
        label: 'Python',
        level: 'beginner',
        description: 'Python fundamentals: lists, dicts, functions, comprehensions, and OOP.',
        resource: { title: 'Python.org Tutorial', url: 'https://docs.python.org/3/tutorial/' },
        x: 400, y: 60, parentId: null,
      },
      {
        id: 'stats',
        label: 'Statistics & Math',
        level: 'beginner',
        description: 'Probability, distributions, hypothesis testing, and linear algebra basics.',
        resource: { title: 'Khan Academy Stats', url: 'https://www.khanacademy.org/math/statistics-probability' },
        x: 400, y: 160, parentId: 'python',
      },
      {
        id: 'pandas',
        label: 'Pandas & NumPy',
        level: 'intermediate',
        description: 'Data wrangling: cleaning, transforming, and exploring datasets at scale.',
        resource: { title: 'Pandas Docs', url: 'https://pandas.pydata.org/docs/' },
        x: 240, y: 280, parentId: 'stats',
      },
      {
        id: 'sql',
        label: 'SQL',
        level: 'intermediate',
        description: 'Query relational databases: joins, aggregations, window functions, CTEs.',
        resource: { title: 'SQLZoo', url: 'https://sqlzoo.net' },
        x: 560, y: 280, parentId: 'stats',
      },
      {
        id: 'ml',
        label: 'Machine Learning',
        level: 'intermediate',
        description: 'Scikit-learn: regression, classification, clustering, and model evaluation.',
        resource: { title: 'Scikit-learn User Guide', url: 'https://scikit-learn.org/stable/user_guide.html' },
        x: 240, y: 400, parentId: 'pandas',
      },
      {
        id: 'viz',
        label: 'Data Visualization',
        level: 'intermediate',
        description: 'Communicate insights with Matplotlib, Seaborn, and Plotly.',
        resource: { title: 'Matplotlib Tutorials', url: 'https://matplotlib.org/stable/tutorials/index.html' },
        x: 560, y: 400, parentId: 'sql',
      },
      {
        id: 'deep-learning',
        label: 'Deep Learning',
        level: 'advanced',
        description: 'Neural networks with PyTorch or TensorFlow: CNNs, transformers, fine-tuning.',
        resource: { title: 'fast.ai', url: 'https://www.fast.ai' },
        x: 400, y: 500, parentId: 'ml',
      },
    ],
  },
  devops: {
    nodes: [
      {
        id: 'linux',
        label: 'Linux & Shell',
        level: 'beginner',
        description: 'Terminal fluency: bash scripting, file permissions, processes, and networking.',
        resource: { title: 'The Linux Command Line', url: 'https://linuxcommand.org/tlcl.php' },
        x: 400, y: 60, parentId: null,
      },
      {
        id: 'git',
        label: 'Git & Version Control',
        level: 'beginner',
        description: 'Branching strategies, merging, rebasing, and pull request workflows.',
        resource: { title: 'Pro Git Book', url: 'https://git-scm.com/book' },
        x: 400, y: 160, parentId: 'linux',
      },
      {
        id: 'docker',
        label: 'Docker',
        level: 'intermediate',
        description: 'Containerize applications: Dockerfiles, images, volumes, and networking.',
        resource: { title: 'Docker Docs', url: 'https://docs.docker.com' },
        x: 240, y: 280, parentId: 'git',
      },
      {
        id: 'cicd',
        label: 'CI/CD',
        level: 'intermediate',
        description: 'Automate builds and deploys with GitHub Actions, GitLab CI, or Jenkins.',
        resource: { title: 'GitHub Actions Docs', url: 'https://docs.github.com/en/actions' },
        x: 560, y: 280, parentId: 'git',
      },
      {
        id: 'kubernetes',
        label: 'Kubernetes',
        level: 'advanced',
        description: 'Orchestrate containers at scale: pods, deployments, services, and Helm charts.',
        resource: { title: 'Kubernetes Docs', url: 'https://kubernetes.io/docs/home/' },
        x: 240, y: 400, parentId: 'docker',
      },
      {
        id: 'terraform',
        label: 'Terraform / IaC',
        level: 'advanced',
        description: 'Define infrastructure as code. Provision cloud resources reproducibly.',
        resource: { title: 'Terraform Docs', url: 'https://developer.hashicorp.com/terraform/docs' },
        x: 560, y: 400, parentId: 'cicd',
      },
      {
        id: 'monitoring',
        label: 'Monitoring & SRE',
        level: 'advanced',
        description: 'SLOs, error budgets, Prometheus, Grafana, and incident management.',
        resource: { title: 'Google SRE Book', url: 'https://sre.google/sre-book/table-of-contents/' },
        x: 400, y: 500, parentId: 'kubernetes',
      },
    ],
  },
  'product-manager': {
    nodes: [
      {
        id: 'user-research',
        label: 'User Research',
        level: 'beginner',
        description: 'Interviews, surveys, and usability tests. Finding real user pain points.',
        resource: { title: 'Nielsen Norman Group', url: 'https://www.nngroup.com/articles/' },
        x: 400, y: 60, parentId: null,
      },
      {
        id: 'product-thinking',
        label: 'Product Thinking',
        level: 'beginner',
        description: 'Jobs-to-be-done, problem framing, and opportunity sizing.',
        resource: { title: 'Inspired by Marty Cagan', url: 'https://www.svpg.com/inspired-how-to-create-products-customers-love/' },
        x: 400, y: 160, parentId: 'user-research',
      },
      {
        id: 'prioritization',
        label: 'Prioritization',
        level: 'intermediate',
        description: 'RICE, MoSCoW, opportunity scoring, and managing stakeholder expectations.',
        resource: { title: 'Intercom Product Blog', url: 'https://www.intercom.com/blog/product-management/' },
        x: 240, y: 280, parentId: 'product-thinking',
      },
      {
        id: 'metrics',
        label: 'Metrics & Analytics',
        level: 'intermediate',
        description: 'Define KPIs, set up A/B tests, and analyze funnel data.',
        resource: { title: 'Mixpanel Product Analytics', url: 'https://mixpanel.com/blog/' },
        x: 560, y: 280, parentId: 'product-thinking',
      },
      {
        id: 'roadmapping',
        label: 'Roadmapping',
        level: 'intermediate',
        description: 'Outcome-based roadmaps, quarterly planning, and communicating strategy.',
        resource: { title: 'Product Plan Blog', url: 'https://www.productplan.com/learn/product-roadmap/' },
        x: 240, y: 400, parentId: 'prioritization',
      },
      {
        id: 'go-to-market',
        label: 'Go-to-Market',
        level: 'advanced',
        description: 'Launch strategy, positioning, pricing, and cross-functional alignment.',
        resource: { title: 'Lenny\'s Newsletter', url: 'https://www.lennysnewsletter.com' },
        x: 560, y: 400, parentId: 'metrics',
      },
      {
        id: 'leadership',
        label: 'PM Leadership',
        level: 'advanced',
        description: 'Influence without authority, executive communication, and building PM culture.',
        resource: { title: 'Reforge Programs', url: 'https://www.reforge.com' },
        x: 400, y: 500, parentId: 'roadmapping',
      },
    ],
  },
  'ux-designer': {
    nodes: [
      {
        id: 'design-basics',
        label: 'Design Fundamentals',
        level: 'beginner',
        description: 'Visual hierarchy, typography, color theory, and layout principles.',
        resource: { title: 'Refactoring UI', url: 'https://www.refactoringui.com' },
        x: 400, y: 60, parentId: null,
      },
      {
        id: 'figma',
        label: 'Figma',
        level: 'beginner',
        description: 'Frames, components, auto-layout, variables, and prototyping.',
        resource: { title: 'Figma Learn', url: 'https://help.figma.com/hc/en-us/categories/360002051613' },
        x: 400, y: 160, parentId: 'design-basics',
      },
      {
        id: 'ux-research',
        label: 'UX Research',
        level: 'intermediate',
        description: 'Moderated usability testing, card sorting, and synthesis techniques.',
        resource: { title: 'UX Research Cheat Sheet', url: 'https://www.nngroup.com/articles/ux-research-cheat-sheet/' },
        x: 240, y: 280, parentId: 'figma',
      },
      {
        id: 'information-arch',
        label: 'Information Architecture',
        level: 'intermediate',
        description: 'Navigation patterns, user flows, mental models, and content strategy.',
        resource: { title: 'IA Institute', url: 'https://www.iainstitute.org' },
        x: 560, y: 280, parentId: 'figma',
      },
      {
        id: 'design-systems',
        label: 'Design Systems',
        level: 'intermediate',
        description: 'Build component libraries, tokens, and documentation that scale.',
        resource: { title: 'Storybook Design Systems Guide', url: 'https://storybook.js.org/tutorials/design-systems-for-developers/' },
        x: 240, y: 400, parentId: 'ux-research',
      },
      {
        id: 'interaction-design',
        label: 'Interaction Design',
        level: 'advanced',
        description: 'Motion design, microinteractions, and advanced Figma prototyping.',
        resource: { title: 'Interaction Design Foundation', url: 'https://www.interaction-design.org' },
        x: 560, y: 400, parentId: 'information-arch',
      },
      {
        id: 'accessibility',
        label: 'Accessibility',
        level: 'advanced',
        description: 'WCAG 2.1 guidelines, screen reader testing, and inclusive design patterns.',
        resource: { title: 'WebAIM Resources', url: 'https://webaim.org/resources/' },
        x: 400, y: 500, parentId: 'design-systems',
      },
    ],
  },
}
