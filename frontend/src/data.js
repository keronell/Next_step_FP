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
    // Adaptive: only relevant to logic/data leaners (q2). showIf may reference earlier questions only.
    showIf: (a) => a.q2 === 1 || a.q2 === 2,
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
    // Adaptive: only relevant to design/code leaners (q2). showIf may reference earlier questions only.
    showIf: (a) => a.q2 === 0 || a.q2 === 1,
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

// Adaptive path: the in-order subset of QUESTIONS to ask given answers so far.
// A question's showIf must reference only earlier questions (see Questionnaire.jsx).
export const visibleQuestions = (answers) =>
  QUESTIONS.filter((q) => !q.showIf || q.showIf(answers))

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
    sections: [
      {
        id: 'foundations',
        label: 'Foundations',
        nodes: [
          {
            id: 'html-css',
            label: 'HTML & CSS',
            level: 'beginner',
            type: 'required',
            description: 'Learn semantic HTML5 and modern CSS: flexbox, grid, and custom properties.',
            resources: [{ title: 'MDN Web Docs — HTML', url: 'https://developer.mozilla.org/en-US/docs/Web/HTML' }],
          },
          {
            id: 'js-basics',
            label: 'JavaScript',
            level: 'beginner',
            type: 'required',
            description: 'Core JS: variables, functions, async/await, and DOM manipulation.',
            resources: [{ title: 'javascript.info', url: 'https://javascript.info' }],
          },
        ],
      },
      {
        id: 'core-stack',
        label: 'Core Stack',
        nodes: [
          {
            id: 'react',
            label: 'React',
            level: 'intermediate',
            type: 'required',
            description: 'Component model, hooks (useState, useEffect, useContext), and state management.',
            resources: [{ title: 'React Docs', url: 'https://react.dev' }],
          },
          {
            id: 'typescript',
            label: 'TypeScript',
            level: 'intermediate',
            type: 'good-to-know',
            description: 'Static typing for scalable codebases. Types, interfaces, generics.',
            resources: [{ title: 'TypeScript Handbook', url: 'https://www.typescriptlang.org/docs/' }],
          },
          {
            id: 'testing',
            label: 'Testing',
            level: 'intermediate',
            type: 'good-to-know',
            description: 'Unit and integration tests with Vitest and React Testing Library.',
            resources: [{ title: 'Vitest Docs', url: 'https://vitest.dev' }],
          },
        ],
      },
      {
        id: 'advanced',
        label: 'Advanced',
        nodes: [
          {
            id: 'performance',
            label: 'Performance',
            level: 'advanced',
            type: 'required',
            description: 'Core Web Vitals, code splitting, lazy loading, and bundle optimization.',
            resources: [{ title: 'web.dev Performance', url: 'https://web.dev/performance/' }],
          },
          {
            id: 'advanced-patterns',
            label: 'Advanced Patterns',
            level: 'advanced',
            type: 'optional',
            description: 'Render optimization, compound components, custom hooks, and design systems.',
            resources: [{ title: 'patterns.dev', url: 'https://www.patterns.dev' }],
          },
        ],
      },
    ],
  },
  backend: {
    sections: [
      {
        id: 'foundations',
        label: 'Foundations',
        nodes: [
          {
            id: 'programming',
            label: 'Programming Basics',
            level: 'beginner',
            type: 'required',
            description: 'Pick a language: Node.js, Python, or Go. Learn data structures and algorithms.',
            resources: [{ title: 'The Odin Project', url: 'https://www.theodinproject.com' }],
          },
          {
            id: 'databases',
            label: 'Databases',
            level: 'beginner',
            type: 'required',
            description: 'Relational (PostgreSQL) and NoSQL (MongoDB). SQL fundamentals.',
            resources: [{ title: 'PostgreSQL Tutorial', url: 'https://www.postgresqltutorial.com' }],
          },
        ],
      },
      {
        id: 'api-layer',
        label: 'API Layer',
        nodes: [
          {
            id: 'apis',
            label: 'REST & GraphQL',
            level: 'intermediate',
            type: 'required',
            description: 'Design and build APIs: REST principles, authentication, rate limiting.',
            resources: [{ title: 'REST API Tutorial', url: 'https://restfulapi.net' }],
          },
          {
            id: 'auth',
            label: 'Auth & Security',
            level: 'intermediate',
            type: 'required',
            description: 'JWT, OAuth2, session management, and OWASP Top 10 vulnerabilities.',
            resources: [{ title: 'OWASP Top 10', url: 'https://owasp.org/www-project-top-ten/' }],
          },
          {
            id: 'caching',
            label: 'Caching & Queues',
            level: 'intermediate',
            type: 'good-to-know',
            description: 'Redis for caching, message queues (RabbitMQ / BullMQ) for async work.',
            resources: [{ title: 'Redis Docs', url: 'https://redis.io/docs/' }],
          },
        ],
      },
      {
        id: 'scale',
        label: 'Scale & Reliability',
        nodes: [
          {
            id: 'system-design',
            label: 'System Design',
            level: 'advanced',
            type: 'required',
            description: 'Scalability, load balancing, microservices, and distributed systems.',
            resources: [{ title: 'System Design Primer', url: 'https://github.com/donnemartin/system-design-primer' }],
          },
          {
            id: 'observability',
            label: 'Observability',
            level: 'advanced',
            type: 'good-to-know',
            description: 'Structured logging, distributed tracing (OpenTelemetry), and alerting.',
            resources: [{ title: 'OpenTelemetry Docs', url: 'https://opentelemetry.io/docs/' }],
          },
        ],
      },
    ],
  },
  'data-science': {
    sections: [
      {
        id: 'foundations',
        label: 'Foundations',
        nodes: [
          {
            id: 'python',
            label: 'Python',
            level: 'beginner',
            type: 'required',
            description: 'Python fundamentals: lists, dicts, functions, comprehensions, and OOP.',
            resources: [{ title: 'Python.org Tutorial', url: 'https://docs.python.org/3/tutorial/' }],
          },
          {
            id: 'stats',
            label: 'Statistics & Math',
            level: 'beginner',
            type: 'required',
            description: 'Probability, distributions, hypothesis testing, and linear algebra basics.',
            resources: [{ title: 'Khan Academy Stats', url: 'https://www.khanacademy.org/math/statistics-probability' }],
          },
        ],
      },
      {
        id: 'core-tools',
        label: 'Core Tools',
        nodes: [
          {
            id: 'pandas',
            label: 'Pandas & NumPy',
            level: 'intermediate',
            type: 'required',
            description: 'Data wrangling: cleaning, transforming, and exploring datasets at scale.',
            resources: [{ title: 'Pandas Docs', url: 'https://pandas.pydata.org/docs/' }],
          },
          {
            id: 'sql',
            label: 'SQL',
            level: 'intermediate',
            type: 'required',
            description: 'Query relational databases: joins, aggregations, window functions, CTEs.',
            resources: [{ title: 'SQLZoo', url: 'https://sqlzoo.net' }],
          },
          {
            id: 'ml',
            label: 'Machine Learning',
            level: 'intermediate',
            type: 'required',
            description: 'Scikit-learn: regression, classification, clustering, and model evaluation.',
            resources: [{ title: 'Scikit-learn User Guide', url: 'https://scikit-learn.org/stable/user_guide.html' }],
          },
        ],
      },
      {
        id: 'advanced-ml',
        label: 'Advanced ML',
        nodes: [
          {
            id: 'viz',
            label: 'Data Visualization',
            level: 'intermediate',
            type: 'good-to-know',
            description: 'Communicate insights with Matplotlib, Seaborn, and Plotly.',
            resources: [{ title: 'Matplotlib Tutorials', url: 'https://matplotlib.org/stable/tutorials/index.html' }],
          },
          {
            id: 'deep-learning',
            label: 'Deep Learning',
            level: 'advanced',
            type: 'optional',
            description: 'Neural networks with PyTorch or TensorFlow: CNNs, transformers, fine-tuning.',
            resources: [{ title: 'fast.ai', url: 'https://www.fast.ai' }],
          },
        ],
      },
    ],
  },
  devops: {
    sections: [
      {
        id: 'foundations',
        label: 'Foundations',
        nodes: [
          {
            id: 'linux',
            label: 'Linux & Shell',
            level: 'beginner',
            type: 'required',
            description: 'Terminal fluency: bash scripting, file permissions, processes, and networking.',
            resources: [{ title: 'The Linux Command Line', url: 'https://linuxcommand.org/tlcl.php' }],
          },
          {
            id: 'git',
            label: 'Git & Version Control',
            level: 'beginner',
            type: 'required',
            description: 'Branching strategies, merging, rebasing, and pull request workflows.',
            resources: [{ title: 'Pro Git Book', url: 'https://git-scm.com/book' }],
          },
        ],
      },
      {
        id: 'containers',
        label: 'Containers & Automation',
        nodes: [
          {
            id: 'docker',
            label: 'Docker',
            level: 'intermediate',
            type: 'required',
            description: 'Containerize applications: Dockerfiles, images, volumes, and networking.',
            resources: [{ title: 'Docker Docs', url: 'https://docs.docker.com' }],
          },
          {
            id: 'cicd',
            label: 'CI/CD',
            level: 'intermediate',
            type: 'required',
            description: 'Automate builds and deploys with GitHub Actions, GitLab CI, or Jenkins.',
            resources: [{ title: 'GitHub Actions Docs', url: 'https://docs.github.com/en/actions' }],
          },
        ],
      },
      {
        id: 'infra-scale',
        label: 'Infrastructure at Scale',
        nodes: [
          {
            id: 'kubernetes',
            label: 'Kubernetes',
            level: 'advanced',
            type: 'required',
            description: 'Orchestrate containers at scale: pods, deployments, services, and Helm charts.',
            resources: [{ title: 'Kubernetes Docs', url: 'https://kubernetes.io/docs/home/' }],
          },
          {
            id: 'terraform',
            label: 'Terraform / IaC',
            level: 'advanced',
            type: 'good-to-know',
            description: 'Define infrastructure as code. Provision cloud resources reproducibly.',
            resources: [{ title: 'Terraform Docs', url: 'https://developer.hashicorp.com/terraform/docs' }],
          },
          {
            id: 'monitoring',
            label: 'Monitoring & SRE',
            level: 'advanced',
            type: 'required',
            description: 'SLOs, error budgets, Prometheus, Grafana, and incident management.',
            resources: [{ title: 'Google SRE Book', url: 'https://sre.google/sre-book/table-of-contents/' }],
          },
        ],
      },
    ],
  },
  'product-manager': {
    sections: [
      {
        id: 'research',
        label: 'Research & Thinking',
        nodes: [
          {
            id: 'user-research',
            label: 'User Research',
            level: 'beginner',
            type: 'required',
            description: 'Interviews, surveys, and usability tests. Finding real user pain points.',
            resources: [{ title: 'Nielsen Norman Group', url: 'https://www.nngroup.com/articles/' }],
          },
          {
            id: 'product-thinking',
            label: 'Product Thinking',
            level: 'beginner',
            type: 'required',
            description: 'Jobs-to-be-done, problem framing, and opportunity sizing.',
            resources: [{ title: 'Inspired by Marty Cagan', url: 'https://www.svpg.com/inspired-how-to-create-products-customers-love/' }],
          },
        ],
      },
      {
        id: 'execution',
        label: 'Execution',
        nodes: [
          {
            id: 'prioritization',
            label: 'Prioritization',
            level: 'intermediate',
            type: 'required',
            description: 'RICE, MoSCoW, opportunity scoring, and managing stakeholder expectations.',
            resources: [{ title: 'Intercom Product Blog', url: 'https://www.intercom.com/blog/product-management/' }],
          },
          {
            id: 'metrics',
            label: 'Metrics & Analytics',
            level: 'intermediate',
            type: 'required',
            description: 'Define KPIs, set up A/B tests, and analyze funnel data.',
            resources: [{ title: 'Mixpanel Product Analytics', url: 'https://mixpanel.com/blog/' }],
          },
          {
            id: 'roadmapping',
            label: 'Roadmapping',
            level: 'intermediate',
            type: 'good-to-know',
            description: 'Outcome-based roadmaps, quarterly planning, and communicating strategy.',
            resources: [{ title: 'Product Plan Blog', url: 'https://www.productplan.com/learn/product-roadmap/' }],
          },
        ],
      },
      {
        id: 'strategy',
        label: 'Strategy & Leadership',
        nodes: [
          {
            id: 'go-to-market',
            label: 'Go-to-Market',
            level: 'advanced',
            type: 'required',
            description: 'Launch strategy, positioning, pricing, and cross-functional alignment.',
            resources: [{ title: "Lenny's Newsletter", url: 'https://www.lennysnewsletter.com' }],
          },
          {
            id: 'leadership',
            label: 'PM Leadership',
            level: 'advanced',
            type: 'optional',
            description: 'Influence without authority, executive communication, and building PM culture.',
            resources: [{ title: 'Reforge Programs', url: 'https://www.reforge.com' }],
          },
        ],
      },
    ],
  },
  'ux-designer': {
    sections: [
      {
        id: 'foundations',
        label: 'Foundations',
        nodes: [
          {
            id: 'design-basics',
            label: 'Design Fundamentals',
            level: 'beginner',
            type: 'required',
            description: 'Visual hierarchy, typography, color theory, and layout principles.',
            resources: [{ title: 'Refactoring UI', url: 'https://www.refactoringui.com' }],
          },
          {
            id: 'figma',
            label: 'Figma',
            level: 'beginner',
            type: 'required',
            description: 'Frames, components, auto-layout, variables, and prototyping.',
            resources: [{ title: 'Figma Learn', url: 'https://help.figma.com/hc/en-us/categories/360002051613' }],
          },
        ],
      },
      {
        id: 'research-arch',
        label: 'Research & Architecture',
        nodes: [
          {
            id: 'ux-research',
            label: 'UX Research',
            level: 'intermediate',
            type: 'required',
            description: 'Moderated usability testing, card sorting, and synthesis techniques.',
            resources: [{ title: 'UX Research Cheat Sheet', url: 'https://www.nngroup.com/articles/ux-research-cheat-sheet/' }],
          },
          {
            id: 'information-arch',
            label: 'Information Architecture',
            level: 'intermediate',
            type: 'required',
            description: 'Navigation patterns, user flows, mental models, and content strategy.',
            resources: [{ title: 'IA Institute', url: 'https://www.iainstitute.org' }],
          },
          {
            id: 'design-systems',
            label: 'Design Systems',
            level: 'intermediate',
            type: 'good-to-know',
            description: 'Build component libraries, tokens, and documentation that scale.',
            resources: [{ title: 'Storybook Design Systems Guide', url: 'https://storybook.js.org/tutorials/design-systems-for-developers/' }],
          },
        ],
      },
      {
        id: 'advanced-craft',
        label: 'Advanced Craft',
        nodes: [
          {
            id: 'interaction-design',
            label: 'Interaction Design',
            level: 'advanced',
            type: 'required',
            description: 'Motion design, microinteractions, and advanced Figma prototyping.',
            resources: [{ title: 'Interaction Design Foundation', url: 'https://www.interaction-design.org' }],
          },
          {
            id: 'accessibility',
            label: 'Accessibility',
            level: 'advanced',
            type: 'required',
            description: 'WCAG 2.1 guidelines, screen reader testing, and inclusive design patterns.',
            resources: [{ title: 'WebAIM Resources', url: 'https://webaim.org/resources/' }],
          },
        ],
      },
    ],
  },
}
