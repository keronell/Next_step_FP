#!/usr/bin/env python3
import csv
import json
from pathlib import Path


def parse_csv(file_path):
    """Parse CSV file"""
    questions = []
    with open(file_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            questions.append(row)
    return questions


def generate_skill_mappings(question):
    """Generate skill mappings based on question content"""
    mappings = {}
    question_lower = question.get('question', '').lower()
    tags = question.get('tags', '').lower()
    
    # Map questions to skills based on keywords
    if 'ui' in question_lower or 'interface' in question_lower or 'visual' in question_lower or 'design' in question_lower:
        mappings['UI/UX Design'] = 0.8
        mappings['Frontend Development'] = 0.5
    
    if 'workflow' in question_lower or 'automate' in question_lower or 'prototype' in question_lower:
        mappings['Problem Solving'] = 0.7
        mappings['Backend Development'] = 0.4
    
    if 'product' in question_lower or 'feature' in question_lower:
        mappings['Product Management'] = 0.6
        mappings['Problem Solving'] = 0.4
    
    if 'write' in question_lower or 'story' in question_lower or 'blog' in question_lower or 'explanation' in question_lower:
        mappings['Technical Writing'] = 0.8
        mappings['Communication'] = 0.5
    
    if 'brainstorm' in question_lower or 'solution' in question_lower or 'problem' in question_lower:
        mappings['Problem Solving'] = 0.7
        mappings['Critical Thinking'] = 0.5
    
    if 'analogy' in question_lower or 'concept' in question_lower:
        mappings['Communication'] = 0.6
        mappings['Technical Writing'] = 0.4
    
    if 'polish' in question_lower or 'visualize' in question_lower:
        mappings['UI/UX Design'] = 0.7
        mappings['Frontend Development'] = 0.5
    
    # Default mappings if none found
    if not mappings:
        mappings['Problem Solving'] = 0.5
        mappings['Communication'] = 0.3
    
    return mappings


def generate_questions():
    """Generate questions.json"""
    project_root = Path(__file__).parent.parent.parent
    csv_path = project_root / 'NextStep_QuestionBank_1702.csv'
    
    if not csv_path.exists():
        print(f"Warning: {csv_path} not found. Skipping questions generation.")
        return
    
    all_questions = parse_csv(csv_path)
    
    # Select 10 diverse questions (every Nth question to get variety)
    selected_questions = []
    step = len(all_questions) // 10
    
    for i in range(10):
        if i * step >= len(all_questions):
            break
        q = all_questions[i * step]
        skill_mappings = generate_skill_mappings(q)
        
        selected_questions.append({
            'id': int(q.get('id', i + 1)) if q.get('id') else i + 1,
            'question': q.get('question', ''),
            'category': q.get('category', 'Personality'),
            'subcategory': q.get('subcategory', 'General'),
            'answer_type': q.get('answer_type', 'Likert5'),
            'options': q.get('options', ''),
            'skill_mappings': skill_mappings
        })
    
    data_dir = Path(__file__).parent.parent / 'data'
    data_dir.mkdir(exist_ok=True)
    output_path = data_dir / 'questions.json'
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(selected_questions, f, indent=2, ensure_ascii=False)
    
    print(f'Generated {len(selected_questions)} questions in {output_path}')


def generate_roles():
    """Generate roles.json"""
    roles = [
        {
            'id': 'frontend',
            'name': 'Frontend Developer',
            'description': 'Builds user-facing web applications using HTML, CSS, and JavaScript',
            'required_skills': {
                'Frontend Development': 4,
                'UI/UX Design': 3,
                'JavaScript': 4,
                'React': 3,
                'CSS': 4,
                'HTML': 4
            }
        },
        {
            'id': 'backend',
            'name': 'Backend Developer',
            'description': 'Develops server-side logic and APIs',
            'required_skills': {
                'Backend Development': 4,
                'API Design': 4,
                'Database': 3,
                'Problem Solving': 4,
                'System Design': 3
            }
        },
        {
            'id': 'fullstack',
            'name': 'Full Stack Developer',
            'description': 'Works on both frontend and backend systems',
            'required_skills': {
                'Frontend Development': 3,
                'Backend Development': 3,
                'JavaScript': 4,
                'Database': 3,
                'Problem Solving': 4
            }
        },
        {
            'id': 'qa',
            'name': 'QA Engineer',
            'description': 'Ensures software quality through testing',
            'required_skills': {
                'Testing': 4,
                'Problem Solving': 3,
                'Attention to Detail': 4,
                'Communication': 3
            }
        },
        {
            'id': 'devops',
            'name': 'DevOps Engineer',
            'description': 'Manages infrastructure and deployment pipelines',
            'required_skills': {
                'DevOps': 4,
                'System Administration': 3,
                'CI/CD': 4,
                'Cloud': 3,
                'Problem Solving': 3
            }
        },
        {
            'id': 'android',
            'name': 'Android Developer',
            'description': 'Develops mobile applications for Android',
            'required_skills': {
                'Mobile Development': 4,
                'Java/Kotlin': 4,
                'Android SDK': 4,
                'UI/UX Design': 3
            }
        },
        {
            'id': 'ios',
            'name': 'iOS Developer',
            'description': 'Develops mobile applications for iOS',
            'required_skills': {
                'Mobile Development': 4,
                'Swift': 4,
                'iOS SDK': 4,
                'UI/UX Design': 3
            }
        },
        {
            'id': 'architect',
            'name': 'Software Architect',
            'description': 'Designs system architecture and technical strategy',
            'required_skills': {
                'System Design': 5,
                'Architecture': 5,
                'Problem Solving': 4,
                'Technical Leadership': 4
            }
        },
        {
            'id': 'tech-writer',
            'name': 'Technical Writer',
            'description': 'Creates technical documentation and guides',
            'required_skills': {
                'Technical Writing': 5,
                'Communication': 4,
                'Documentation': 4
            }
        },
        {
            'id': 'ml-engineer',
            'name': 'ML Engineer',
            'description': 'Builds and deploys machine learning models',
            'required_skills': {
                'Machine Learning': 4,
                'Python': 4,
                'Data Science': 3,
                'Statistics': 3
            }
        },
        {
            'id': 'ai-engineer',
            'name': 'AI Engineer',
            'description': 'Develops AI systems and algorithms',
            'required_skills': {
                'Artificial Intelligence': 4,
                'Machine Learning': 4,
                'Python': 4,
                'Problem Solving': 4
            }
        },
        {
            'id': 'data-scientist',
            'name': 'Data Scientist',
            'description': 'Analyzes data to extract insights',
            'required_skills': {
                'Data Science': 4,
                'Statistics': 4,
                'Python': 4,
                'Data Analysis': 4
            }
        },
        {
            'id': 'data-analyst',
            'name': 'Data Analyst',
            'description': 'Analyzes business data and creates reports',
            'required_skills': {
                'Data Analysis': 4,
                'SQL': 3,
                'Statistics': 3,
                'Communication': 3
            }
        },
        {
            'id': 'bi-analyst',
            'name': 'BI Analyst',
            'description': 'Creates business intelligence dashboards and reports',
            'required_skills': {
                'Business Intelligence': 4,
                'Data Visualization': 4,
                'SQL': 3,
                'Analytics': 3
            }
        },
        {
            'id': 'data-engineer',
            'name': 'Data Engineer',
            'description': 'Builds data pipelines and infrastructure',
            'required_skills': {
                'Data Engineering': 4,
                'Database': 4,
                'ETL': 4,
                'Python': 3
            }
        },
        {
            'id': 'mlops',
            'name': 'MLOps Engineer',
            'description': 'Manages ML model deployment and operations',
            'required_skills': {
                'MLOps': 4,
                'Machine Learning': 3,
                'DevOps': 3,
                'Python': 3
            }
        },
        {
            'id': 'product-manager',
            'name': 'Product Manager',
            'description': 'Defines product strategy and roadmap',
            'required_skills': {
                'Product Management': 4,
                'Communication': 4,
                'Strategic Thinking': 4,
                'Problem Solving': 3
            }
        },
        {
            'id': 'eng-manager',
            'name': 'Engineering Manager',
            'description': 'Leads engineering teams and projects',
            'required_skills': {
                'Technical Leadership': 4,
                'Management': 4,
                'Communication': 4,
                'Problem Solving': 3
            }
        },
        {
            'id': 'ux-designer',
            'name': 'UX Designer',
            'description': 'Designs user experiences and interfaces',
            'required_skills': {
                'UI/UX Design': 5,
                'User Research': 4,
                'Prototyping': 4,
                'Communication': 3
            }
        },
        {
            'id': 'cybersecurity',
            'name': 'Cybersecurity Specialist',
            'description': 'Protects systems and data from threats',
            'required_skills': {
                'Cybersecurity': 4,
                'Network Security': 4,
                'Problem Solving': 4,
                'Attention to Detail': 4
            }
        },
        {
            'id': 'data-engineer-2',
            'name': 'Data Engineer (Advanced)',
            'description': 'Senior data engineering role',
            'required_skills': {
                'Data Engineering': 5,
                'System Design': 4,
                'Big Data': 4,
                'Python': 4
            }
        },
        {
            'id': 'fullstack-advanced',
            'name': 'Senior Full Stack Developer',
            'description': 'Advanced full stack development',
            'required_skills': {
                'Frontend Development': 4,
                'Backend Development': 4,
                'System Design': 4,
                'Problem Solving': 4
            }
        }
    ]
    
    data_dir = Path(__file__).parent.parent / 'data'
    data_dir.mkdir(exist_ok=True)
    output_path = data_dir / 'roles.json'
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(roles, f, indent=2, ensure_ascii=False)
    
    print(f'Generated {len(roles)} roles in {output_path}')


def generate_resources():
    """Generate resources.json"""
    skills = [
        'Frontend Development', 'Backend Development', 'UI/UX Design', 'JavaScript',
        'React', 'CSS', 'HTML', 'API Design', 'Database', 'Problem Solving',
        'System Design', 'Testing', 'DevOps', 'Mobile Development', 'Machine Learning',
        'Data Science', 'Python', 'Technical Writing', 'Communication', 'Product Management'
    ]
    
    resources = []
    for skill in skills:
        resources.append({
            'skill': skill,
            'resources': [
                {
                    'title': f'{skill} - Beginner Guide',
                    'url': f'https://example.com/learn/{skill.lower().replace(" ", "-").replace("/", "-")}',
                    'type': 'Tutorial',
                    'level': 'Beginner'
                },
                {
                    'title': f'{skill} - Intermediate Course',
                    'url': f'https://example.com/course/{skill.lower().replace(" ", "-").replace("/", "-")}',
                    'type': 'Course',
                    'level': 'Intermediate'
                },
                {
                    'title': f'{skill} - Advanced Documentation',
                    'url': f'https://example.com/docs/{skill.lower().replace(" ", "-").replace("/", "-")}',
                    'type': 'Documentation',
                    'level': 'Advanced'
                }
            ]
        })
    
    data_dir = Path(__file__).parent.parent / 'data'
    data_dir.mkdir(exist_ok=True)
    output_path = data_dir / 'resources.json'
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(resources, f, indent=2, ensure_ascii=False)
    
    print(f'Generated resources for {len(resources)} skills in {output_path}')


def main():
    """Main execution"""
    print('Generating data files...')
    generate_questions()
    generate_roles()
    generate_resources()
    print('All data files generated successfully!')


if __name__ == '__main__':
    main()
